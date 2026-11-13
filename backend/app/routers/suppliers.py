"""Supplier flow: pick a company, see requests it can serve (M2), assign a car (M3)."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import rules
from ..db import get_db
from ..models import Company, Offer, RideRequest, Vehicle
from ..rules import RuleError, RuleViolation
from ..schemas import OfferIn, company_out, iso, offer_out, request_out, vehicle_out

router = APIRouter(tags=["supplier"])


def _get_company(db: Session, company_id: str) -> Company:
    company = db.get(Company, company_id)
    if not company:
        raise RuleViolation([RuleError("NOT_FOUND", f"Supplier {company_id} not found.")], 404)
    return company


@router.get("/companies")
def list_companies(db: Session = Depends(get_db)):
    """Suppliers with their cars (role picker)."""
    return [company_out(c, with_vehicles=True)
            for c in db.scalars(select(Company).order_by(Company.name))]


@router.get("/suppliers/{company_id}/requests")
def supplier_requests(company_id: str, db: Session = Depends(get_db)):
    """Open requests this supplier can serve (R4-R6), each car marked fits/free or why not."""
    company = _get_company(db, company_id)
    reqs = db.scalars(select(RideRequest).where(RideRequest.status == "OPEN")
                      .order_by(RideRequest.pickup)).all()
    out = []
    for req in reqs:
        route = rules.request_route(db, req)
        if not route:
            continue
        company_errors, cars = rules.company_view_of_request(db, company, req, route)
        if company_errors or not any(not errs for _, errs in cars):
            continue
        _, busy_end = rules.busy_window(req, route)
        item = request_out(req, route)
        item["busy_end"] = iso(busy_end)
        item["cars"] = [vehicle_out(v) | {"ok": not errs, "problems": [e.to_dict() for e in errs]}
                        for v, errs in cars]
        item["my_offers"] = [offer_out(o) for o in req.offers if o.company_id == company.company_id]
        out.append(item)
    return {"company": company_out(company, with_vehicles=True), "requests": out}


@router.get("/suppliers/{company_id}/offers")
def supplier_offers(company_id: str, db: Session = Depends(get_db)):
    """Taxis this supplier assigned, newest first, with their status."""
    company = _get_company(db, company_id)
    offers = db.scalars(select(Offer).where(Offer.company_id == company.company_id)
                        .order_by(Offer.created_at.desc(), Offer.id.desc())).all()
    return [offer_out(o) | {"traveler_name": o.request.traveler_name,
                            "hotel": f"{o.request.hotel.name}, {o.request.hotel.area}",
                            "pickup": iso(o.request.pickup),
                            "request_status": o.request.status}
            for o in offers]


@router.post("/requests/{request_id}/offers", status_code=201)
def assign_car(request_id: str, body: OfferIn, db: Session = Depends(get_db)):
    """Assign a car and a price (R7).

    The price is the traveler's price (accept) or a different one (counter-offer);
    either way it must be inside the route's range (R3).
    """
    req = db.get(RideRequest, request_id)
    if not req:
        raise RuleViolation([RuleError("NOT_FOUND", f"Request {request_id} not found.")], 404)
    company = _get_company(db, body.company_id)
    if req.status != "OPEN":
        raise RuleViolation([RuleError("R7", f"Request {request_id} is already booked; "
                                             "a car can only be assigned to an open request.")], 409)

    vehicle = db.get(Vehicle, body.vehicle_id)
    if not vehicle or vehicle.company_id != company.company_id:
        raise RuleViolation([RuleError("R7", f"{body.vehicle_id} is not a car of {company.name}; "
                                             "a supplier can only assign its own cars.")])

    route = rules.request_route(db, req)
    errors = rules.check_vehicle_for_request(db, company, vehicle, req, route)
    errors += rules.check_price(body.price_inr, route, "The offered price")
    if any(o.vehicle_id == vehicle.vehicle_id and o.status == "OPEN" for o in req.offers):
        errors.append(RuleError("R7", f"{vehicle.vehicle_id} is already assigned to {request_id}."))
    if errors:
        raise RuleViolation(errors)

    offer = Offer(request_id=req.request_id, company_id=company.company_id,
                  vehicle_id=vehicle.vehicle_id, price_inr=body.price_inr, status="OPEN")
    db.add(offer)
    db.commit()
    db.refresh(offer)
    return offer_out(offer)
