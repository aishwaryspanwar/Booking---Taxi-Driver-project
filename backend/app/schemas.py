"""Pydantic input models and plain-dict serializers for API output."""
from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator

from .models import Booking, Company, Flight, Hotel, Offer, RideRequest, Route, Vehicle


# ---------- Inputs ----------

class RideRequestIn(BaseModel):
    traveler_name: str = Field(default="Traveler", max_length=100)
    flight_id: str
    hotel_id: str
    adults: int
    child_ages: list[int] = []
    large_bags: int = 0
    small_bags: int = 0
    pickup: datetime | None = None   # local time at the arrival airport; None = earliest pickup
    car_type: str | None = None      # HATCHBACK | SEDAN | SUV | BUS | None (any)
    price_inr: int

    @field_validator("pickup")
    @classmethod
    def drop_timezone(cls, v):
        # All times are local; ignore any offset the client may send.
        return v.replace(tzinfo=None, second=0, microsecond=0) if v else v

    @field_validator("car_type", mode="before")
    @classmethod
    def blank_car_type(cls, v):
        return v or None


class OfferIn(BaseModel):
    company_id: str
    vehicle_id: str
    price_inr: int
    # G4: when the offer ends. The browser sends an ISO time with an offset
    # (e.g. "2027-04-10T09:00:00.000Z"); it is stored as naive UTC. None = never ends.
    expires_at: datetime | None = None

    @field_validator("expires_at", mode="before")
    @classmethod
    def blank_expiry(cls, v):
        return v or None

    @field_validator("expires_at")
    @classmethod
    def to_naive_utc(cls, v):
        if v is None:
            return v
        if v.tzinfo is not None:
            v = v.astimezone(timezone.utc).replace(tzinfo=None)
        return v.replace(second=0, microsecond=0)


class ChangeIn(BaseModel):
    """Traveler's change request (R9): a new flight, a new pickup, or both."""
    flight_id: str | None = None     # None = keep the booked flight
    pickup: datetime | None = None   # None = earliest pickup of the (new) flight

    @field_validator("pickup")
    @classmethod
    def drop_timezone(cls, v):
        return v.replace(tzinfo=None, second=0, microsecond=0) if v else v

    @field_validator("flight_id", mode="before")
    @classmethod
    def blank_flight(cls, v):
        return v or None


class DecisionIn(BaseModel):
    """Supplier's answer to a change request. company_id proves it is their booking."""
    company_id: str


# ---------- Outputs ----------

def iso(d: datetime | None) -> str | None:
    return d.strftime("%Y-%m-%dT%H:%M") if d else None


def flight_out(f: Flight) -> dict:
    return {"flight_id": f.flight_id, "airline": f.airline, "flight_number": f.flight_number,
            "from": f.from_airport, "to": f.to_airport, "arrival_local": iso(f.arrival_local)}


def hotel_out(h: Hotel) -> dict:
    return {"hotel_id": h.hotel_id, "name": h.name, "city": h.city, "area": h.area, "stars": h.stars}


def route_out(r: Route) -> dict:
    return {"airport": r.airport, "city": r.city, "area": r.area, "distance_km": r.distance_km,
            "drive_minutes": r.drive_minutes, "price_min_inr": r.price_min_inr,
            "price_max_inr": r.price_max_inr}


def vehicle_out(v: Vehicle) -> dict:
    return {"vehicle_id": v.vehicle_id, "type": v.type, "seats": v.seats,
            "large_bags": v.large_bags, "small_bags": v.small_bags}


def company_out(c: Company, with_vehicles: bool = False) -> dict:
    out = {"company_id": c.company_id, "name": c.name, "airports": c.airports, "areas": c.areas,
           "service_from": c.service_from, "service_until": c.service_until, "rating": c.rating}
    if with_vehicles:
        out["vehicles"] = [vehicle_out(v) for v in c.vehicles]
    return out


def offer_out(o: Offer) -> dict:
    return {"offer_id": o.id, "request_id": o.request_id, "company_id": o.company_id,
            "company_name": o.company.name, "company_rating": o.company.rating,
            "vehicle": vehicle_out(o.vehicle), "price_inr": o.price_inr,
            "status": o.effective_status,     # OPEN | EXPIRED | BOOKED | REJECTED | NOT_CHOSEN
            # G4: UTC with a "Z" so the browser shows it in the viewer's own time zone
            "expires_at": utc_iso(o.expires_at),
            "created_at": iso(o.created_at)}


def utc_iso(d: datetime | None) -> str | None:
    return d.strftime("%Y-%m-%dT%H:%M:00Z") if d else None


def booking_out(b: Booking) -> dict:
    return {"booking_number": b.booking_number, "offer_id": b.offer_id, "request_id": b.request_id,
            "vehicle_id": b.vehicle_id, "busy_start": iso(b.busy_start), "busy_end": iso(b.busy_end)}


def request_out(r: RideRequest, route: Route | None) -> dict:
    return {"request_id": r.request_id, "traveler_name": r.traveler_name,
            "flight": flight_out(r.flight), "hotel": hotel_out(r.hotel),
            "route": route_out(route) if route else None,
            "adults": r.adults, "child_ages": r.child_ages, "passengers": r.passengers,
            "large_bags": r.large_bags, "small_bags": r.small_bags, "pickup": iso(r.pickup),
            "car_type": r.car_type, "price_inr": r.price_inr, "status": r.status}
