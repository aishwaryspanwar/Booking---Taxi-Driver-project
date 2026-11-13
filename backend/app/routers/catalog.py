"""
Catalog APIs (traveler side, read-only).

These endpoints give the traveler's form what it needs:
    GET /api/flights       -> flights to pick from
    GET /api/hotels        -> hotels to pick from
    GET /api/price-range   -> suggested price range + earliest pickup for a flight + hotel

Nothing here writes to the database.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import rules
from ..db import get_db
from ..models import Airport, Flight, Hotel
from ..schemas import flight_out, hotel_out, iso, route_out

# A group of endpoints. main.py adds the "/api" prefix to every path here.
router = APIRouter(tags=["catalog"])


# -----------------------------------------------------------------------------
# GET /api/flights
#
# Purpose : list the flights a traveler can arrive on.
# Input   : none
# Output  : list of flights, earliest landing first
# Note    : flights.json is shared with other problems and also has flights
#           that land in India. Only airports with "serves_cities" have taxis,
#           so we keep flights landing at NRT, HND, KIX, DXB and AUH.
# -----------------------------------------------------------------------------
@router.get("/flights")
def list_flights(db: Session = Depends(get_db)):
    # 1. Codes of airports that serve at least one city (an empty list or no field = no taxis)
    serving_airports = [
        airport.code
        for airport in db.scalars(select(Airport))
        if airport.serves_cities
    ]

    # 2. Flights that land at one of those airports, earliest landing first
    query = (
        select(Flight)
        .where(Flight.to_airport.in_(serving_airports))
        .order_by(Flight.arrival_local)
    )
    flights = db.scalars(query).all()

    # 3. Turn each database row into a plain dict (FastAPI sends it as JSON)
    return [flight_out(flight) for flight in flights]


# -----------------------------------------------------------------------------
# GET /api/hotels
#
# Purpose : list every hotel for the hotel dropdown.
# Input   : none
# Output  : list of hotels, sorted by city, then area, then name
#           (the frontend groups them by city)
# -----------------------------------------------------------------------------
@router.get("/hotels")
def list_hotels(db: Session = Depends(get_db)):
    query = select(Hotel).order_by(Hotel.city, Hotel.area, Hotel.name)
    hotels = db.scalars(query)

    return [hotel_out(hotel) for hotel in hotels]


# -----------------------------------------------------------------------------
# GET /api/price-range?flight_id=FL-401&hotel_id=HTL-TYO-004
#
# Purpose : show the suggested price range on the form as soon as the
#           traveler picks a flight and a hotel.
# Input   : flight_id, hotel_id (query string, both required)
# Output  : route details, price_min_inr, price_max_inr, landing time and
#           earliest pickup (landing + 60 minutes)
# Rules   : R1 - flight and hotel exist, and the arrival airport serves the hotel's city
#           R2 - earliest pickup is 60 minutes after landing
#           R3 - the range comes from routes.json (airport + city + area)
# Errors  : 400 with an R1 message, e.g. a Narita flight with an Osaka hotel
# -----------------------------------------------------------------------------
@router.get("/price-range")
def price_range(flight_id: str, hotel_id: str, db: Session = Depends(get_db)):
    # 1. Find the flight, the hotel and the route, and check R1
    flight, _hotel, route, errors = rules.resolve_trip(db, flight_id, hotel_id)

    # 2. Stop if anything is wrong. main.py turns this into {"errors": [...]}
    if errors:
        raise rules.RuleViolation(errors)

    # 3. Send the range, the route and the earliest allowed pickup
    return {
        "route": route_out(route),
        "price_min_inr": route.price_min_inr,
        "price_max_inr": route.price_max_inr,
        "arrival_local": iso(flight.arrival_local),
        "earliest_pickup": iso(rules.earliest_pickup(flight)),
    }
