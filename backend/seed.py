"""Load all JSON data into the database.

Idempotent: drops every table (including app data) and recreates it.
Run from the backend folder:  python seed.py
"""
import json
from datetime import datetime
from pathlib import Path

from app.db import Base, SessionLocal, engine
from app.models import (Airport, BookedRide, Company, Flight, Hotel, RideRequest,
                        Route, Vehicle)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load(rel_path: str):
    with open(DATA_DIR / rel_path, encoding="utf-8") as f:
        return json.load(f)


def dt(value: str) -> datetime:
    # Accepts "YYYY-MM-DDTHH:MM" and "YYYY-MM-DDTHH:MM:SS"
    return datetime.fromisoformat(value)


def seed():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    with SessionLocal() as db:
        for a in load("catalog/airports.json"):
            db.add(Airport(code=a["code"], name=a["name"], city=a["city"], country=a["country"],
                           timezone=a["timezone"], serves_cities=a.get("serves_cities", [])))

        for f in load("catalog/flights.json"):
            db.add(Flight(flight_id=f["flight_id"], airline=f["airline"], flight_number=f["flight_number"],
                          from_airport=f["from"], to_airport=f["to"],
                          departure_local=dt(f["departure_local"]), arrival_local=dt(f["arrival_local"])))

        for h in load("catalog/hotels.json"):
            db.add(Hotel(hotel_id=h["hotel_id"], name=h["name"], city=h["city"], area=h["area"],
                         stars=h.get("stars")))

        for r in load("problem-2/routes.json"):
            db.add(Route(**r))

        for c in load("problem-2/taxi_companies.json"):
            db.add(Company(company_id=c["company_id"], name=c["name"], airports=c["airports"],
                           areas=c["areas"], service_from=c["service_from"],
                           service_until=c["service_until"], rating=c["rating"]))
            for v in c["vehicles"]:
                db.add(Vehicle(company_id=c["company_id"], **v))
        db.flush()  # companies/vehicles must exist before rows that reference them

        for b in load("problem-2/booked_rides.json"):
            db.add(BookedRide(ride_id=b["ride_id"], company_id=b["company_id"], vehicle_id=b["vehicle_id"],
                              start=dt(b["start"]), end=dt(b["end"])))

        for q in load("problem-2/open_requests.json"):
            db.add(RideRequest(request_id=q["request_id"], traveler_name=q["traveler_name"],
                               flight_id=q["flight_id"], hotel_id=q["hotel_id"], adults=q["adults"],
                               child_ages=q["child_ages"], large_bags=q["large_bags"],
                               small_bags=q["small_bags"], pickup=dt(q["pickup"]),
                               car_type=q["car_type"], price_inr=q["price_inr"], status="OPEN"))
        db.commit()

        counts = {m.__tablename__: db.query(m).count()
                  for m in (Airport, Flight, Hotel, Route, Company, Vehicle, BookedRide, RideRequest)}
    print("Seeded:", counts)


if __name__ == "__main__":
    seed()
