"""
Booking summary (M5) and change requests (M7 / R9).

Traveler:
    GET  /api/bookings                             -> every booking, newest first
    GET  /api/bookings/{booking_number}            -> booking summary, or 404 "not found"
    POST /api/bookings/{booking_number}/changes    -> ask for a new flight and/or pickup

Supplier:
    GET  /api/suppliers/{company_id}/changes       -> change requests for this supplier's bookings
    POST /api/changes/{change_id}/accept           -> accept (only if R2 holds and the car is free)
    POST /api/changes/{change_id}/reject           -> reject (the old booking stays)
"""
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import rules
from ..db import get_db
from ..models import Booking, ChangeRequest, Company, Flight, Offer
from ..rules import RuleError, RuleViolation
from ..schemas import ChangeIn, DecisionIn, flight_out, iso, request_out, vehicle_out

router = APIRouter(tags=["bookings"])


# =============================================================================
# Helpers
# =============================================================================

def _get_booking(db: Session, booking_number: str) -> Booking:
    """Load a booking by its 10-digit number, or answer 404 "not found" (M5)."""
    booking = db.get(Booking, booking_number.strip())
    if not booking:
        raise RuleViolation(
            [RuleError("NOT_FOUND", f"Booking {booking_number} not found. Check the 10-digit number.")],
            status_code=404,
        )
    return booking


def _get_change(db: Session, change_id: int) -> ChangeRequest:
    """Load a change request by ID, or answer 404."""
    change = db.get(ChangeRequest, change_id)
    if not change:
        raise RuleViolation(
            [RuleError("NOT_FOUND", f"Change request {change_id} not found.")],
            status_code=404,
        )
    return change


def change_out(change: ChangeRequest) -> dict:
    return {
        "change_id": change.id,
        "booking_number": change.booking_number,
        "old_flight": flight_out(change.old_flight),
        "old_pickup": iso(change.old_pickup),
        "new_flight": flight_out(change.new_flight),
        "new_pickup": iso(change.new_pickup),
        "status": change.status,      # WAITING | ACCEPTED | REJECTED
        "reason": change.reason,      # why it was rejected (empty when accepted)
        "created_at": iso(change.created_at),
        "decided_at": iso(change.decided_at),
    }


def booking_summary(db: Session, booking: Booking) -> dict:
    """Everything M5 asks for: flight, hotel, pickup, supplier, car and price, plus change requests."""
    ride_request = booking.offer.request
    route = rules.request_route(db, ride_request)
    offer = booking.offer
    return {
        "booking_number": booking.booking_number,
        "request": request_out(ride_request, route),   # flight, hotel, pickup, travelers, bags
        "supplier": {"company_id": offer.company.company_id, "name": offer.company.name,
                     "rating": offer.company.rating},
        "vehicle": vehicle_out(offer.vehicle),
        "price_inr": offer.price_inr,
        "busy_start": iso(booking.busy_start),
        "busy_end": iso(booking.busy_end),
        "changes": [change_out(c) for c in reversed(booking.changes)],   # newest first
        "has_waiting_change": any(c.status == "WAITING" for c in booking.changes),
    }


def _change_problems(db: Session, change: ChangeRequest) -> list[RuleError]:
    """R9: the new pickup must follow R2, and the same car must be free at the new time."""
    booking = change.booking
    errors = rules.check_pickup(change.new_pickup, change.new_flight)

    # The route does not change (same airport, same hotel), so the busy time
    # keeps its length: pickup -> pickup + 2 x drive_minutes.
    new_start = change.new_pickup
    new_end = new_start + (booking.busy_end - booking.busy_start)
    errors += rules.check_car_free(db, booking.vehicle_id, new_start, new_end,
                                   ignore_booking=booking.booking_number)
    return errors


def _check_supplier_owns(change: ChangeRequest, company_id: str) -> None:
    """Only the supplier of the booking may answer its change request (403)."""
    owner = change.booking.offer.company_id      # booking -> offer -> supplier
    if owner != company_id:
        raise RuleViolation(
            [RuleError("R9", "Only the supplier of this booking can answer its change request.")],
            status_code=403,
        )


def _check_waiting(change: ChangeRequest) -> None:
    """A change request can be decided only once (409)."""
    if change.status != "WAITING":
        raise RuleViolation(
            [RuleError("R9", f"This change request is already {change.status.lower()}.")],
            status_code=409,
        )


# =============================================================================
# GET /api/bookings
#
# Purpose : every booking, newest first, for the "My booking" page list.
#           (No login, so everyone sees every booking.)
# Output  : list of booking summaries (same shape as GET /api/bookings/{number})
# =============================================================================
@router.get("/bookings")
def list_bookings(db: Session = Depends(get_db)):
    query = select(Booking).order_by(Booking.created_at.desc())
    bookings = db.scalars(query).all()

    return [booking_summary(db, booking) for booking in bookings]


# =============================================================================
# GET /api/bookings/{booking_number}   (M5)
#
# Purpose : the booking number opens a summary of the ride.
# Output  : flight, hotel, pickup, supplier, car, price, busy time, change requests
# Errors  : 404 "not found" for a wrong number
# Note    : read from the database, so it works after a backend restart.
# =============================================================================
@router.get("/bookings/{booking_number}")
def get_booking(booking_number: str, db: Session = Depends(get_db)):
    return booking_summary(db, _get_booking(db, booking_number))


# =============================================================================
# POST /api/bookings/{booking_number}/changes   (M7, traveler)
#
# Purpose : after booking, ask for a new flight and/or a new pickup time.
# Input   : {"flight_id": "FL-402" | null, "pickup": "2027-04-10T13:00" | null}
#           At least one must be given. No pickup = earliest pickup of the new flight.
# Rules   : R1 - the new flight is in the catalog
#           R2 - the new pickup is at least 60 minutes after the new flight lands
#           The new flight must land at the same airport: the supplier, the route
#           and the price were agreed for that airport.
# Output  : 201 + the booking summary, with the change "WAITING" for the supplier
# Errors  : 400 broken rule; 404 booking not found; 409 a change is already waiting
# =============================================================================
@router.post("/bookings/{booking_number}/changes", status_code=201)
def request_change(booking_number: str, body: ChangeIn, db: Session = Depends(get_db)):
    booking = _get_booking(db, booking_number)
    ride_request = booking.offer.request

    # At least one thing must change
    if body.flight_id is None and body.pickup is None:
        raise RuleViolation(
            [RuleError("INPUT", "Choose a new flight, a new pickup time, or both.")],
        )

    # Only one change can wait for the supplier at a time
    if any(change.status == "WAITING" for change in booking.changes):
        raise RuleViolation(
            [RuleError("R9", "A change request is already waiting for the supplier.")],
            status_code=409,
        )

    # ---- Step 1: the new flight (or keep the booked one) -------------------
    old_flight = ride_request.flight
    new_flight = old_flight
    if body.flight_id:
        new_flight = db.get(Flight, body.flight_id)

        # R1: the new flight must be in the catalog
        if not new_flight:
            raise RuleViolation(
                [RuleError("R1", f"Flight '{body.flight_id}' is not in the catalog.")],
            )

        # Same airport: the supplier, route and price were agreed for it
        if new_flight.to_airport != old_flight.to_airport:
            raise RuleViolation(
                [RuleError("R9", f"Flight {new_flight.flight_number} lands at {new_flight.to_airport}. "
                                 f"The new flight must land at {old_flight.to_airport}, "
                                 "the airport of this booking.")],
            )

    # ---- Step 2: the new pickup, and R2 ------------------------------------
    # No pickup given -> 60 minutes after the (new) flight lands
    new_pickup = body.pickup or rules.earliest_pickup(new_flight)
    errors = rules.check_pickup(new_pickup, new_flight)

    # A "change" that changes nothing is refused
    nothing_changes = (new_flight.flight_id == old_flight.flight_id
                       and new_pickup == ride_request.pickup)
    if nothing_changes:
        errors.append(RuleError("R9", "This is the same flight and pickup as the booking; "
                                      "nothing would change."))
    if errors:
        raise RuleViolation(errors)

    # ---- Step 3: save it, waiting for the supplier -------------------------
    db.add(ChangeRequest(
        booking_number=booking.booking_number,
        old_flight_id=old_flight.flight_id,
        old_pickup=ride_request.pickup,
        new_flight_id=new_flight.flight_id,
        new_pickup=new_pickup,
        status="WAITING",
    ))
    db.commit()
    db.refresh(booking)
    return booking_summary(db, booking)


# =============================================================================
# GET /api/suppliers/{company_id}/changes   (M7, supplier)
#
# Purpose : change requests for this supplier's bookings, newest first.
#           For a waiting one, "problems" shows now whether accepting would work.
# =============================================================================
@router.get("/suppliers/{company_id}/changes")
def supplier_changes(company_id: str, db: Session = Depends(get_db)):
    if not db.get(Company, company_id):
        raise RuleViolation(
            [RuleError("NOT_FOUND", f"Supplier {company_id} not found.")],
            status_code=404,
        )

    # change_requests -> bookings -> offers, keeping only this supplier's offers
    query = (
        select(ChangeRequest)
        .join(Booking, ChangeRequest.booking_number == Booking.booking_number)
        .join(Offer, Booking.offer_id == Offer.id)
        .where(Offer.company_id == company_id)
        .order_by(ChangeRequest.id.desc())
    )
    result = []
    for change in db.scalars(query):
        ride_request = change.booking.offer.request
        item = change_out(change)
        item["traveler_name"] = ride_request.traveler_name
        item["hotel"] = f"{ride_request.hotel.name}, {ride_request.hotel.area}"
        item["vehicle_id"] = change.booking.vehicle_id

        # For a waiting change, say now whether accepting would pass (R2 + car free)
        item["problems"] = []
        if change.status == "WAITING":
            item["problems"] = [error.to_dict() for error in _change_problems(db, change)]
        result.append(item)
    return result


# =============================================================================
# POST /api/changes/{change_id}/accept   (M7, supplier)
#
# Input   : {"company_id": "TX-JP-01"}  (must be the supplier of the booking)
# Rules   : R9 - accepted only if the new pickup follows R2 and the same car is
#                free at the new time. Otherwise the platform refuses: the change
#                becomes REJECTED with the reason, and the old booking stays.
# Output  : the change request (ACCEPTED). The booking now has the new flight,
#           pickup and busy time.
# Errors  : 403 not your booking; 409 already decided, or the platform refused it
# =============================================================================
@router.post("/changes/{change_id}/accept")
def accept_change(change_id: int, body: DecisionIn, db: Session = Depends(get_db)):
    change = _get_change(db, change_id)
    _check_supplier_owns(change, body.company_id)   # 403 if not this supplier's booking
    _check_waiting(change)                          # 409 if already decided

    # R9: the new pickup must follow R2 and the same car must be free
    problems = _change_problems(db, change)
    if problems:
        # The platform refuses: record why, keep the old booking, and tell the supplier.
        change.status = "REJECTED"
        change.reason = "Refused by the platform: " + " ".join(p.message for p in problems)
        change.decided_at = datetime.utcnow()
        db.commit()
        raise RuleViolation(problems, 409)

    # Move the booking to the new time. The drive time is the same (same route).
    booking = change.booking
    duration = booking.busy_end - booking.busy_start
    booking.busy_start = change.new_pickup
    booking.busy_end = change.new_pickup + duration

    ride_request = booking.offer.request
    ride_request.flight_id = change.new_flight_id
    ride_request.pickup = change.new_pickup

    change.status = "ACCEPTED"
    change.decided_at = datetime.utcnow()
    db.commit()
    return change_out(change)


# =============================================================================
# POST /api/changes/{change_id}/reject   (M7, supplier)
#
# Input   : {"company_id": "TX-JP-01"}
# Output  : the change request (REJECTED). The old booking does not change.
# =============================================================================
@router.post("/changes/{change_id}/reject")
def reject_change(change_id: int, body: DecisionIn, db: Session = Depends(get_db)):
    change = _get_change(db, change_id)
    _check_supplier_owns(change, body.company_id)   # 403 if not this supplier's booking
    _check_waiting(change)                          # 409 if already decided

    # The booking keeps its old flight and pickup
    change.status = "REJECTED"
    change.reason = "Rejected by the supplier."
    change.decided_at = datetime.utcnow()
    db.commit()
    return change_out(change)
