"""Read-only catalog endpoints and the price range lookup (R3)."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import rules
from ..db import get_db
from ..models import Airport, Flight, Hotel
from ..schemas import flight_out, hotel_out, iso, route_out

router = APIRouter(tags=["catalog"])


@router.get("/flights")
def list_flights(db: Session = Depends(get_db)):
    """Only flights that land at an airport serving a city (Japan / UAE)."""
    serving = [a.code for a in db.scalars(select(Airport)) if a.serves_cities]
    flights = db.scalars(select(Flight).where(Flight.to_airport.in_(serving))
                         .order_by(Flight.arrival_local)).all()
    return [flight_out(f) for f in flights]


@router.get("/hotels")
def list_hotels(db: Session = Depends(get_db)):
    return [hotel_out(h) for h in db.scalars(select(Hotel).order_by(Hotel.city, Hotel.area, Hotel.name))]


@router.get("/price-range")
def price_range(flight_id: str, hotel_id: str, db: Session = Depends(get_db)):
    """Suggested price range for flight + hotel. Also returns the earliest pickup (R2)."""
    flight, hotel, route, errors = rules.resolve_trip(db, flight_id, hotel_id)
    if errors:
        raise rules.RuleViolation(errors)
    return {"route": route_out(route), "price_min_inr": route.price_min_inr,
            "price_max_inr": route.price_max_inr, "arrival_local": iso(flight.arrival_local),
            "earliest_pickup": iso(rules.earliest_pickup(flight))}
