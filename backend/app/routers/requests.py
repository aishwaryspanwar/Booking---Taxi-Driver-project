"""
Ride request APIs (traveler side).

    POST /api/requests                 -> post a ride request (M1)
    GET  /api/requests                 -> list all requests
    GET  /api/requests/{request_id}    -> one request with its taxis and booking
    POST /api/offers/{offer_id}/reject -> reject a taxi (R8)
    POST /api/offers/{offer_id}/book   -> book a taxi, get a 10-digit number (R8)

Every rule check lives in rules.py. Each check returns a list of RuleError
(an empty list = OK). When anything fails we raise RuleViolation, and main.py
sends it back as {"errors": [{"rule": "R2", "message": "..."}]}.
"""
import secrets

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import rules
from ..db import get_db
from ..models import Booking, Company, Offer, RideRequest
from ..rules import RuleError, RuleViolation
from ..schemas import RideRequestIn, booking_out, offer_out, request_out

# A group of endpoints. main.py adds the "/api" prefix to every path here.
router = APIRouter(tags=["traveler"])


# =============================================================================
# Helpers (not endpoints)
# =============================================================================

def _next_request_id(db: Session) -> str:
    """Next ID in the REQ-0001 format: highest existing number + 1."""
    numbers = []
    for request_id in db.scalars(select(RideRequest.request_id)):
        prefix, _, number = request_id.partition("-")
        if prefix == "REQ" and number.isdigit():
            numbers.append(int(number))

    next_number = max(numbers, default=0) + 1
    return f"REQ-{next_number:04d}"          # 4 -> "REQ-0004"


def _new_booking_number(db: Session) -> str:
    """A random, unique, 10-digit booking number."""
    while True:
        # randbelow(9_000_000_000) gives 0 .. 8,999,999,999.
        # Adding 1,000,000,000 gives 1,000,000,000 .. 9,999,999,999: always 10 digits.
        # `secrets` makes the number hard to guess.
        number = str(secrets.randbelow(9_000_000_000) + 1_000_000_000)

        # Very unlikely, but if the number is already used, try again.
        if not db.get(Booking, number):
            return number


def _get_request(db: Session, request_id: str) -> RideRequest:
    """Load a request by ID, or answer 404."""
    ride_request = db.get(RideRequest, request_id)
    if not ride_request:
        raise RuleViolation(
            [RuleError("NOT_FOUND", f"Request {request_id} not found.")],
            status_code=404,
        )
    return ride_request


def _get_offer(db: Session, offer_id: int) -> Offer:
    """Load an offer (a taxi assigned by a supplier) by ID, or answer 404."""
    offer = db.get(Offer, offer_id)
    if not offer:
        raise RuleViolation(
            [RuleError("NOT_FOUND", f"Offer {offer_id} not found.")],
            status_code=404,
        )
    return offer


def request_detail(db: Session, ride_request: RideRequest) -> dict:
    """
    The full picture of one request, sent back by create, get, reject and book,
    so the frontend always gets the same shape.

    Contains: the request, its route, every taxi offered, the booking (if any),
    and, while nobody has offered a taxi yet, who can serve it or why nobody can (M2).
    """
    route = rules.request_route(db, ride_request)

    # Basic request fields (flight, hotel, travelers, bags, pickup, price, status)
    detail = request_out(ride_request, route)

    # Every taxi assigned to this request, with its status
    detail["offers"] = [offer_out(offer) for offer in ride_request.offers]

    # The booking, if the traveler has booked one
    booking = db.scalar(
        select(Booking).where(Booking.request_id == ride_request.request_id)
    )
    detail["booking"] = booking_out(booking) if booking else None

    # M2: while the request is open and has no taxis yet, say who can serve it.
    # If nobody can, explain why for each supplier.
    detail["no_supplier_reasons"] = []
    if ride_request.status == "OPEN" and not ride_request.offers:
        servable = [
            company
            for company in db.scalars(select(Company))
            if rules.can_serve(db, company, ride_request, route)
        ]
        detail["servable_by"] = [company.name for company in servable]

        if not servable:
            detail["no_supplier_reasons"] = rules.why_no_supplier(db, ride_request, route)

    return detail


# =============================================================================
# POST /api/requests
#
# Purpose : the traveler posts a ride request with their own price (M1).
# Input   : JSON body (see RideRequestIn in schemas.py), e.g.
#           {"traveler_name": "Menon family", "flight_id": "FL-401",
#            "hotel_id": "HTL-TYO-004", "adults": 2, "child_ages": [6],
#            "large_bags": 3, "small_bags": 2, "pickup": "2027-04-10T11:30",
#            "car_type": null, "price_inr": 12000}
# Output  : 201 + the full request (see request_detail)
# Rules   : R1 - flight/hotel exist, the airport serves the city, at least 1 adult, children 0-17
#           R2 - pickup at least 60 min after landing (empty pickup = landing + 60 min)
#           R3 - price inside the route's range (both ends allowed)
# Errors  : 400 with every broken rule at once; 422 if a field has the wrong type
# =============================================================================
@router.post("/requests", status_code=201)
def create_request(body: RideRequestIn, db: Session = Depends(get_db)):
    # ---- Step 1: check every rule and collect all errors -------------------

    # R1: flight + hotel exist, and the arrival airport serves the hotel's city
    flight, hotel, route, errors = rules.resolve_trip(db, body.flight_id, body.hotel_id)

    # R1: at least 1 adult, children 0-17, no negative bags, valid car type
    errors += rules.check_travelers(
        body.adults,
        body.child_ages,
        body.large_bags,
        body.small_bags,
        body.car_type,
    )

    # R2: pickup time (we need the flight's landing time for this)
    pickup = None
    if flight:
        # No pickup given -> use the earliest allowed one (landing + 60 min)
        pickup = body.pickup or rules.earliest_pickup(flight)
        errors += rules.check_pickup(pickup, flight)

    # R3: the traveler's price must be inside the route's range
    if route:
        errors += rules.check_price(body.price_inr, route, "Your price")

    # Anything wrong? Send every error. Nothing has been saved yet.
    if errors:
        raise RuleViolation(errors)

    # ---- Step 2: save the request ------------------------------------------
    ride_request = RideRequest(
        request_id=_next_request_id(db),
        traveler_name=body.traveler_name.strip() or "Traveler",
        flight_id=flight.flight_id,
        hotel_id=hotel.hotel_id,
        adults=body.adults,
        child_ages=body.child_ages,
        large_bags=body.large_bags,
        small_bags=body.small_bags,
        pickup=pickup,                 # the final pickup, never empty
        car_type=body.car_type,
        price_inr=body.price_inr,
        status="OPEN",                 # waiting for taxis
    )
    db.add(ride_request)      # add it to the "to save" list
    db.commit()               # write it to the database (survives a restart)
    db.refresh(ride_request)  # reload it so relationships (flight, hotel) are filled

    # ---- Step 3: reply with the full request -------------------------------
    return request_detail(db, ride_request)


# =============================================================================
# GET /api/requests
#
# Purpose : list all requests (there is no login), newest first.
# Output  : list of requests, each with "offer_count" (number of taxis offered)
#           and "booking_number" (None until booked; used by the
#           "Change flight" button, M7)
# =============================================================================
@router.get("/requests")
def list_requests(db: Session = Depends(get_db)):
    query = select(RideRequest).order_by(RideRequest.created_at.desc())
    ride_requests = db.scalars(query).all()

    # request_id -> booking number, in one query
    booking_numbers = dict(db.execute(select(Booking.request_id, Booking.booking_number)).all())

    result = []
    for ride_request in ride_requests:
        route = rules.request_route(db, ride_request)
        item = request_out(ride_request, route)
        item["offer_count"] = len(ride_request.offers)
        item["booking_number"] = booking_numbers.get(ride_request.request_id)
        result.append(item)
    return result


# =============================================================================
# GET /api/requests/{request_id}
#
# Purpose : one request with its taxis, booking, and why nobody can serve it (if so).
#           The offers page calls this every 5 seconds to show new taxis.
# Input   : request_id in the path, e.g. /api/requests/REQ-0004
# Output  : the full request (see request_detail)
# Errors  : 404 if the request does not exist
# =============================================================================
@router.get("/requests/{request_id}")
def get_request(request_id: str, db: Session = Depends(get_db)):
    ride_request = _get_request(db, request_id)
    return request_detail(db, ride_request)


# =============================================================================
# POST /api/offers/{offer_id}/reject
#
# Purpose : the traveler rejects one taxi (R8).
# Input   : offer_id in the path
# Output  : the full request, with this taxi now "REJECTED"
# Rules   : R8 - only an OPEN taxi can be rejected
# Errors  : 404 offer not found; 409 if the taxi is not open any more
# =============================================================================
@router.post("/offers/{offer_id}/reject")
def reject_offer(offer_id: int, db: Session = Depends(get_db)):
    offer = _get_offer(db, offer_id)

    # Only an open taxi can be rejected (not a booked, rejected, not chosen or ended one)
    if offer.effective_status != "OPEN":
        status_text = offer.effective_status.lower().replace("_", " ")   # NOT_CHOSEN -> "not chosen"
        raise RuleViolation(
            [RuleError("R8", f"This taxi is {status_text}; only an open taxi can be rejected.")],
            status_code=409,
        )

    offer.status = "REJECTED"
    db.commit()

    return request_detail(db, offer.request)


# =============================================================================
# POST /api/offers/{offer_id}/book
#
# Purpose : the traveler books one taxi (R8).
# Input   : offer_id in the path
# Output  : the full request, with "booking": {"booking_number": "1234567890", ...}
# Rules   : R8 - a rejected taxi cannot be booked; a request is booked only once;
#                the other open taxis become "NOT_CHOSEN"
#           R6 - the car must still be free (it may have been booked on another
#                request since it was offered)
# Errors  : 404 offer not found; 409 rejected / already booked / car now busy
# =============================================================================
@router.post("/offers/{offer_id}/book")
def book_offer(offer_id: int, db: Session = Depends(get_db)):
    offer = _get_offer(db, offer_id)
    ride_request = offer.request

    # ---- Step 1: is booking allowed? (R8) ----------------------------------
    if offer.status == "REJECTED":
        raise RuleViolation(
            [RuleError("R8", "You rejected this taxi; a rejected taxi cannot be booked.")],
            status_code=409,
        )
    if offer.status != "OPEN" or ride_request.status != "OPEN":
        raise RuleViolation(
            [RuleError("R8", "This request is already booked.")],
            status_code=409,
        )

    # G4: the supplier set an end time for this taxi, and it has passed
    if offer.is_expired():
        raise RuleViolation(
            [RuleError("G4", f"This taxi offer ended at {offer.expires_at:%d %b %Y %H:%M} UTC; "
                             "an ended taxi cannot be booked.")],
            status_code=409,
        )

    # ---- Step 2: is the car still free? (R6, M6) ---------------------------
    # The car is busy from pickup until pickup + 2 x drive time (there and back).
    route = rules.request_route(db, ride_request)
    busy_start, busy_end = rules.busy_window(ride_request, route)

    busy_errors = rules.check_car_free(db, offer.vehicle_id, busy_start, busy_end)
    if busy_errors:
        raise RuleViolation(busy_errors, status_code=409)

    # ---- Step 3: create the booking ----------------------------------------
    # Storing the busy time makes this car busy for every later check (R6).
    booking = Booking(
        booking_number=_new_booking_number(db),
        offer_id=offer.id,
        request_id=ride_request.request_id,
        vehicle_id=offer.vehicle_id,
        busy_start=busy_start,
        busy_end=busy_end,
    )
    db.add(booking)

    # ---- Step 4: update the statuses ---------------------------------------
    offer.status = "BOOKED"
    for other_offer in ride_request.offers:
        # Every other taxi that is still open was "not chosen" (rejected ones stay rejected).
        # Ended (G4) offers become "not chosen" too: the request is booked now.
        if other_offer.id != offer.id and other_offer.status == "OPEN":
            other_offer.status = "NOT_CHOSEN"
    ride_request.status = "BOOKED"     # suppliers stop seeing this request

    # ---- Step 5: save everything together ----------------------------------
    # One commit = one transaction: the booking and all status changes are
    # saved together, or none of them are.
    db.commit()

    return request_detail(db, ride_request)
