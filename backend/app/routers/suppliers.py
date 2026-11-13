"""
Supplier APIs.

    GET  /api/companies                        -> suppliers and their cars (role picker)
    GET  /api/suppliers/{company_id}/requests  -> open requests this supplier can serve (M2)
    GET  /api/suppliers/{company_id}/offers    -> taxis this supplier assigned, with status
    POST /api/requests/{request_id}/offers     -> assign a car with a price (M3, R7),
                                                  several cars per request (G1),
                                                  optional end time (G4)

Every rule check lives in rules.py. When anything fails we raise RuleViolation,
and main.py sends it back as {"errors": [{"rule": "R6", "message": "..."}]}.
"""
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import rules
from ..db import get_db
from ..models import Company, Offer, RideRequest, Vehicle
from ..rules import RuleError, RuleViolation
from ..schemas import OfferIn, company_out, iso, offer_out, request_out, vehicle_out

# A group of endpoints. main.py adds the "/api" prefix to every path here.
router = APIRouter(tags=["supplier"])


# =============================================================================
# Helper (not an endpoint)
# =============================================================================

def _get_company(db: Session, company_id: str) -> Company:
    """Load a supplier by ID, or answer 404."""
    company = db.get(Company, company_id)
    if not company:
        raise RuleViolation(
            [RuleError("NOT_FOUND", f"Supplier {company_id} not found.")],
            status_code=404,
        )
    return company


# =============================================================================
# GET /api/companies
#
# Purpose : list every supplier with its cars, for the role picker dropdown.
# Output  : list of companies (airports, areas, opening hours, rating, vehicles)
# =============================================================================
@router.get("/companies")
def list_companies(db: Session = Depends(get_db)):
    query = select(Company).order_by(Company.name)
    companies = db.scalars(query)

    # with_vehicles=True adds each company's cars, so the dropdown can show "4 cars"
    return [company_out(company, with_vehicles=True) for company in companies]


# =============================================================================
# GET /api/suppliers/{company_id}/requests
#
# Purpose : the supplier dashboard. Only the OPEN requests this supplier can
#           serve (R4) and has not offered a car on yet, each with every car
#           marked "fits and is free" or the rules it breaks (R5, R6).
#           Booked requests and requests it already offered on are left out
#           (those show in "Your taxis"). The dashboard calls this every 5 seconds.
# Output  : {"company": {...}, "requests": [{..., "cars": [...]}]}
# Errors  : 404 if the supplier does not exist
# =============================================================================
@router.get("/suppliers/{company_id}/requests")
def supplier_requests(company_id: str, db: Session = Depends(get_db)):
    company = _get_company(db, company_id)

    # 1. Every open request, earliest pickup first (booked ones drop off the dashboard)
    query = (
        select(RideRequest)
        .where(RideRequest.status == "OPEN")
        .order_by(RideRequest.pickup)
    )
    open_requests = db.scalars(query).all()

    result = []
    for ride_request in open_requests:
        route = rules.request_route(db, ride_request)
        if not route:
            continue  # safety net: no route, nothing to serve

        # 2. R4 for the company (airport, area, open at pickup) + R5/R6 for every car
        company_errors, cars = rules.company_view_of_request(db, company, ride_request, route)

        # 3. G1: a supplier may assign several cars to one request. A car that is
        #    already offered here (open and not ended, G4) cannot be offered again.
        live_offers = [
            offer for offer in ride_request.offers
            if offer.company_id == company.company_id and offer.is_live
        ]
        offered_ids = {offer.vehicle_id for offer in live_offers}
        cars = [
            (vehicle, car_errors + ([RuleError("G1", f"{vehicle.vehicle_id} is already offered on "
                                                     f"{ride_request.request_id}.")]
                                    if vehicle.vehicle_id in offered_ids else []))
            for vehicle, car_errors in cars
        ]

        # 4. Skip it if the company fails R4, or if no car is left that fits, is free
        #    and is not offered yet. It then shows only in "Your taxis".
        has_good_car = any(not car_errors for _, car_errors in cars)
        if company_errors or not has_good_car:
            continue

        # 5. Build the card: request details + when the car would be busy until
        _, busy_end = rules.busy_window(ride_request, route)
        item = request_out(ride_request, route)
        item["busy_end"] = iso(busy_end)
        item["your_offer_count"] = len(live_offers)   # G1: cars already offered here

        # 6. Every car with "ok" or its problems (the dashboard's car dropdown)
        item["cars"] = [
            vehicle_out(vehicle) | {
                "ok": not car_errors,
                "problems": [error.to_dict() for error in car_errors],
            }
            for vehicle, car_errors in cars
        ]
        result.append(item)

    return {"company": company_out(company, with_vehicles=True), "requests": result}


# =============================================================================
# GET /api/suppliers/{company_id}/offers
#
# Purpose : the "Your taxis" table: every taxi this supplier assigned, newest
#           first, so it sees "booked with you" or "not chosen".
# Output  : list of offers + traveler name, hotel, pickup and request status
# Errors  : 404 if the supplier does not exist
# =============================================================================
@router.get("/suppliers/{company_id}/offers")
def supplier_offers(company_id: str, db: Session = Depends(get_db)):
    company = _get_company(db, company_id)

    query = (
        select(Offer)
        .where(Offer.company_id == company.company_id)
        .order_by(Offer.created_at.desc(), Offer.id.desc())
    )
    offers = db.scalars(query).all()

    result = []
    for offer in offers:
        ride_request = offer.request
        item = offer_out(offer)                     # supplier, car, price, status
        item["traveler_name"] = ride_request.traveler_name
        item["hotel"] = f"{ride_request.hotel.name}, {ride_request.hotel.area}"
        item["pickup"] = iso(ride_request.pickup)
        item["request_status"] = ride_request.status
        result.append(item)
    return result


# =============================================================================
# POST /api/requests/{request_id}/offers
#
# Purpose : the supplier assigns one of its cars with a price (M3, R7).
#           Price = traveler's price ("Accept") or another price ("counter-offer").
# Input   : {"company_id": "TX-JP-01", "vehicle_id": "SC-3", "price_inr": 12000}
# Rules   : R7 - only its own car, only on an open request
#           R4 - works at the airport, drives to the area, open at the pickup time
#           R5 - seats, large bags, small bags and car type fit
#           R6 - the car is free (seeded rides + app bookings)
#           R3 - the price is inside the route's range
# Output  : 201 + the new offer (status OPEN)
# Errors  : 404 request/supplier not found; 409 request already booked;
#           400 with every broken rule at once
# =============================================================================
@router.post("/requests/{request_id}/offers", status_code=201)
def assign_car(request_id: str, body: OfferIn, db: Session = Depends(get_db)):
    # ---- Step 1: the request, the supplier and the car must be valid --------
    ride_request = db.get(RideRequest, request_id)
    if not ride_request:
        raise RuleViolation(
            [RuleError("NOT_FOUND", f"Request {request_id} not found.")],
            status_code=404,
        )

    company = _get_company(db, body.company_id)

    if ride_request.status != "OPEN":
        raise RuleViolation(
            [RuleError("R7", f"Request {request_id} is already booked; "
                             "a car can only be assigned to an open request.")],
            status_code=409,
        )

    # R7: a supplier can only assign its own cars
    vehicle = db.get(Vehicle, body.vehicle_id)
    if not vehicle or vehicle.company_id != company.company_id:
        raise RuleViolation(
            [RuleError("R7", f"{body.vehicle_id} is not a car of {company.name}; "
                             "a supplier can only assign its own cars.")],
        )

    # ---- Step 2: check every rule and collect all errors -------------------
    route = rules.request_route(db, ride_request)

    # R4 (company) + R5 (car fits) + R6 (car is free)
    errors = rules.check_vehicle_for_request(db, company, vehicle, ride_request, route)

    # R3: the offered price must be inside the range (it may differ from the traveler's)
    errors += rules.check_price(body.price_inr, route, "The offered price")

    # G1: several cars per request are fine, but the same car cannot be offered
    # twice while the first offer is still open and has not ended (G4)
    already_offered = any(
        offer.vehicle_id == vehicle.vehicle_id and offer.is_live
        for offer in ride_request.offers
    )
    if already_offered:
        errors.append(RuleError("G1", f"{vehicle.vehicle_id} is already assigned to {request_id}."))

    # G4: an end time, if given, must be in the future
    if body.expires_at is not None and body.expires_at <= datetime.utcnow():
        errors.append(RuleError("G4", "The offer end time must be in the future."))

    # Anything wrong? Send every error. Nothing has been saved yet.
    if errors:
        raise RuleViolation(errors)

    # ---- Step 3: save the offer ---------------------------------------------
    offer = Offer(
        request_id=ride_request.request_id,
        company_id=company.company_id,
        vehicle_id=vehicle.vehicle_id,
        price_inr=body.price_inr,
        expires_at=body.expires_at,   # G4: None = never ends
        status="OPEN",             # waiting for the traveler to book or reject
    )
    db.add(offer)
    db.commit()
    db.refresh(offer)

    # The traveler's page shows it on its next 5-second poll
    return offer_out(offer)
