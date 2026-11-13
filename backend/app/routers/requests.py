"""Traveler flow: post a ride request (M1), see offers, book or reject (M4)."""
import secrets

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import rules
from ..db import get_db
from ..models import Booking, Company, Offer, RideRequest
from ..rules import RuleError, RuleViolation
from ..schemas import RideRequestIn, booking_out, offer_out, request_out

router = APIRouter(tags=["traveler"])


def _next_request_id(db: Session) -> str:
    nums = [int(rid.split("-")[1]) for rid in db.scalars(select(RideRequest.request_id))
            if rid.startswith("REQ-") and rid.split("-")[1].isdigit()]
    return f"REQ-{(max(nums, default=0) + 1):04d}"


def _new_booking_number(db: Session) -> str:
    while True:
        number = str(secrets.randbelow(9_000_000_000) + 1_000_000_000)  # always 10 digits
        if not db.get(Booking, number):
            return number


def _get_request(db: Session, request_id: str) -> RideRequest:
    req = db.get(RideRequest, request_id)
    if not req:
        raise RuleViolation([RuleError("NOT_FOUND", f"Request {request_id} not found.")], 404)
    return req


def request_detail(db: Session, req: RideRequest) -> dict:
    route = rules.request_route(db, req)
    out = request_out(req, route)
    out["offers"] = [offer_out(o) for o in req.offers]
    booking = db.scalar(select(Booking).where(Booking.request_id == req.request_id))
    out["booking"] = booking_out(booking) if booking else None
    # M2: tell the traveler when nobody can serve the request, and why.
    out["no_supplier_reasons"] = []
    if req.status == "OPEN" and not req.offers:
        servable = [c for c in db.scalars(select(Company)) if rules.can_serve(db, c, req, route)]
        out["servable_by"] = [c.name for c in servable]
        if not servable:
            out["no_supplier_reasons"] = rules.why_no_supplier(db, req, route)
    return out


@router.post("/requests", status_code=201)
def create_request(body: RideRequestIn, db: Session = Depends(get_db)):
    flight, hotel, route, errors = rules.resolve_trip(db, body.flight_id, body.hotel_id)
    errors += rules.check_travelers(body.adults, body.child_ages, body.large_bags,
                                    body.small_bags, body.car_type)
    pickup = None
    if flight:
        pickup = body.pickup or rules.earliest_pickup(flight)
        errors += rules.check_pickup(pickup, flight)
    if route:
        errors += rules.check_price(body.price_inr, route, "Your price")
    if errors:
        raise RuleViolation(errors)

    req = RideRequest(request_id=_next_request_id(db), traveler_name=body.traveler_name.strip() or "Traveler",
                      flight_id=flight.flight_id, hotel_id=hotel.hotel_id, adults=body.adults,
                      child_ages=body.child_ages, large_bags=body.large_bags, small_bags=body.small_bags,
                      pickup=pickup, car_type=body.car_type, price_inr=body.price_inr, status="OPEN")
    db.add(req)
    db.commit()
    db.refresh(req)
    return request_detail(db, req)


@router.get("/requests")
def list_requests(db: Session = Depends(get_db)):
    reqs = db.scalars(select(RideRequest).order_by(RideRequest.created_at.desc())).all()
    return [request_out(r, rules.request_route(db, r)) | {"offer_count": len(r.offers)} for r in reqs]


@router.get("/requests/{request_id}")
def get_request(request_id: str, db: Session = Depends(get_db)):
    return request_detail(db, _get_request(db, request_id))


def _get_offer(db: Session, offer_id: int) -> Offer:
    offer = db.get(Offer, offer_id)
    if not offer:
        raise RuleViolation([RuleError("NOT_FOUND", f"Offer {offer_id} not found.")], 404)
    return offer


@router.post("/offers/{offer_id}/reject")
def reject_offer(offer_id: int, db: Session = Depends(get_db)):
    offer = _get_offer(db, offer_id)
    if offer.status != "OPEN":
        raise RuleViolation([RuleError("R8", f"This taxi is {offer.status.lower().replace('_', ' ')}; "
                                             "only an open taxi can be rejected.")], 409)
    offer.status = "REJECTED"
    db.commit()
    return request_detail(db, offer.request)


@router.post("/offers/{offer_id}/book")
def book_offer(offer_id: int, db: Session = Depends(get_db)):
    offer = _get_offer(db, offer_id)
    req = offer.request
    if offer.status == "REJECTED":
        raise RuleViolation([RuleError("R8", "You rejected this taxi; a rejected taxi cannot be booked.")], 409)
    if offer.status != "OPEN" or req.status != "OPEN":
        raise RuleViolation([RuleError("R8", "This request is already booked.")], 409)

    # R6 / M6: the car may have become busy since the offer was made.
    route = rules.request_route(db, req)
    start, end = rules.busy_window(req, route)
    busy = rules.check_car_free(db, offer.vehicle_id, start, end)
    if busy:
        raise RuleViolation(busy, 409)

    booking = Booking(booking_number=_new_booking_number(db), offer_id=offer.id, request_id=req.request_id,
                      vehicle_id=offer.vehicle_id, busy_start=start, busy_end=end)
    db.add(booking)
    offer.status = "BOOKED"
    for other in req.offers:
        if other.id != offer.id and other.status == "OPEN":
            other.status = "NOT_CHOSEN"
    req.status = "BOOKED"
    db.commit()
    return request_detail(db, req)
