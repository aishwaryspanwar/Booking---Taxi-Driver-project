"""Business rules R1-R8. Every check returns a list of RuleError (empty = OK).

Each error names the rule it breaks, so the API can say why something is refused.
"""
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (Airport, BookedRide, Booking, Company, Flight, Hotel, RideRequest,
                     Route, Vehicle)

CAR_TYPES = ("HATCHBACK", "SEDAN", "SUV", "BUS")
MIN_PICKUP_DELAY = timedelta(minutes=60)


@dataclass
class RuleError:
    rule: str
    message: str

    def to_dict(self):
        return asdict(self)


class RuleViolation(Exception):
    """Raised by routers; turned into a 4xx JSON response in main.py."""

    def __init__(self, errors: list[RuleError], status_code: int = 400):
        self.errors = errors
        self.status_code = status_code


def inr(n: int) -> str:
    return f"₹{n:,}"


# ---------- R1 / R3: flight + hotel -> route ----------

def resolve_trip(db: Session, flight_id: str, hotel_id: str):
    """Return (flight, hotel, route, errors). Checks R1 (catalog + airport serves city)."""
    errors: list[RuleError] = []
    flight = db.get(Flight, flight_id) if flight_id else None
    hotel = db.get(Hotel, hotel_id) if hotel_id else None
    if not flight:
        errors.append(RuleError("R1", f"Flight '{flight_id}' is not in the catalog."))
    if not hotel:
        errors.append(RuleError("R1", f"Hotel '{hotel_id}' is not in the catalog."))
    if errors:
        return flight, hotel, None, errors

    airport = db.get(Airport, flight.to_airport)
    serves = (airport.serves_cities if airport else None) or []
    if hotel.city not in serves:
        errors.append(RuleError(
            "R1", f"Flight {flight.flight_number} lands at {flight.to_airport}, which does not serve "
                  f"{hotel.city} (the hotel's city)."))
        return flight, hotel, None, errors

    route = find_route(db, flight.to_airport, hotel.city, hotel.area)
    if not route:  # should not happen per DATA_DICTIONARY, but be explicit
        errors.append(RuleError("R3", f"No route from {flight.to_airport} to {hotel.city} / {hotel.area}."))
    return flight, hotel, route, errors


def find_route(db: Session, airport: str, city: str, area: str) -> Route | None:
    return db.scalar(select(Route).where(Route.airport == airport, Route.city == city, Route.area == area))


def check_price(price: int, route: Route, who: str = "The price") -> list[RuleError]:
    if price < route.price_min_inr or price > route.price_max_inr:
        return [RuleError("R3", f"{who} {inr(price)} is outside the suggested range "
                                f"{inr(route.price_min_inr)} – {inr(route.price_max_inr)} for this route.")]
    return []


# ---------- R1 / R2: travelers and pickup ----------

def check_travelers(adults: int, child_ages: list[int], large_bags: int, small_bags: int,
                    car_type: str | None) -> list[RuleError]:
    errors = []
    if adults < 1:
        errors.append(RuleError("R1", "At least 1 adult must travel."))
    for age in child_ages:
        if age < 0 or age > 17:
            errors.append(RuleError("R1", f"Child age {age} is not valid: a child is 0 to 17 years old."))
    if large_bags < 0 or small_bags < 0:
        errors.append(RuleError("R1", "Bag counts cannot be negative."))
    if car_type is not None and car_type not in CAR_TYPES:
        errors.append(RuleError("R5", f"Car type '{car_type}' is not valid. Use one of {', '.join(CAR_TYPES)}."))
    return errors


def earliest_pickup(flight: Flight) -> datetime:
    return flight.arrival_local + MIN_PICKUP_DELAY


def check_pickup(pickup: datetime, flight: Flight) -> list[RuleError]:
    earliest = earliest_pickup(flight)
    if pickup < earliest:
        return [RuleError("R2", f"Pickup {fmt(pickup)} is too early. The flight lands at "
                                f"{fmt(flight.arrival_local)}; the earliest pickup is {fmt(earliest)}.")]
    return []


def fmt(d: datetime) -> str:
    return d.strftime("%d %b %Y %H:%M")


# ---------- R4: supplier can serve ----------

def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def is_open_at(company: Company, when: datetime) -> bool:
    """Opening hours are inclusive and may cross midnight (e.g. 05:00-01:00)."""
    t = when.hour * 60 + when.minute
    start, end = _minutes(company.service_from), _minutes(company.service_until)
    if start <= end:
        return start <= t <= end
    return t >= start or t <= end


def check_company_serves(company: Company, airport: str, city: str, area: str,
                         pickup: datetime) -> list[RuleError]:
    errors = []
    if airport not in company.airports:
        errors.append(RuleError("R4", f"{company.name} does not work at {airport}."))
    if {"city": city, "area": area} not in company.areas:
        errors.append(RuleError("R4", f"{company.name} does not drive to {city} / {area}."))
    if not is_open_at(company, pickup):
        errors.append(RuleError("R4", f"{company.name} is closed at {pickup:%H:%M} "
                                      f"(open {company.service_from}–{company.service_until})."))
    return errors


# ---------- R5: car fits ----------

def check_car_fits(vehicle: Vehicle, req: RideRequest) -> list[RuleError]:
    errors = []
    if vehicle.seats < req.passengers:
        errors.append(RuleError("R5", f"{vehicle.vehicle_id} has {vehicle.seats} seats; "
                                      f"{req.passengers} passengers need a seat."))
    if vehicle.large_bags < req.large_bags:
        errors.append(RuleError("R5", f"{vehicle.vehicle_id} fits {vehicle.large_bags} large bags; "
                                      f"the request has {req.large_bags}."))
    if vehicle.small_bags < req.small_bags:
        errors.append(RuleError("R5", f"{vehicle.vehicle_id} fits {vehicle.small_bags} small bags; "
                                      f"the request has {req.small_bags}."))
    if req.car_type and vehicle.type != req.car_type:
        errors.append(RuleError("R5", f"{vehicle.vehicle_id} is a {vehicle.type}; "
                                      f"the traveller asked for a {req.car_type}."))
    return errors


# ---------- R6: car is free ----------

def busy_window(req: RideRequest, route: Route) -> tuple[datetime, datetime]:
    """Car is busy from pickup until pickup + 2 x drive_minutes (there and back)."""
    return req.pickup, req.pickup + timedelta(minutes=2 * route.drive_minutes)


def check_car_free(db: Session, vehicle_id: str, start: datetime, end: datetime,
                   ignore_booking: str | None = None) -> list[RuleError]:
    """Overlap = one starts before the other ends. Touching ends do not overlap.

    ignore_booking: a booking number to leave out. Used for a change request (R9),
    so the booking does not clash with its own old time.
    """
    ride = db.scalar(select(BookedRide).where(
        BookedRide.vehicle_id == vehicle_id, BookedRide.start < end, BookedRide.end > start))
    if ride:
        return [RuleError("R6", f"{vehicle_id} is busy {fmt(ride.start)} – {ride.end:%H:%M} "
                                f"(ride {ride.ride_id}); this ride needs it {fmt(start)} – {end:%H:%M}.")]
    query = select(Booking).where(
        Booking.vehicle_id == vehicle_id, Booking.busy_start < end, Booking.busy_end > start)
    if ignore_booking:
        query = query.where(Booking.booking_number != ignore_booking)
    booking = db.scalar(query)
    if booking:
        return [RuleError("R6", f"{vehicle_id} is already booked {fmt(booking.busy_start)} – "
                                f"{booking.busy_end:%H:%M}; this ride needs it {fmt(start)} – {end:%H:%M}.")]
    return []


# ---------- Combined checks ----------

def request_route(db: Session, req: RideRequest) -> Route:
    return find_route(db, req.flight.to_airport, req.hotel.city, req.hotel.area)


def check_vehicle_for_request(db: Session, company: Company, vehicle: Vehicle,
                              req: RideRequest, route: Route) -> list[RuleError]:
    """R4 + R5 + R6 for one car of one company on one request."""
    errors = check_company_serves(company, req.flight.to_airport, req.hotel.city, req.hotel.area, req.pickup)
    errors += check_car_fits(vehicle, req)
    start, end = busy_window(req, route)
    errors += check_car_free(db, vehicle.vehicle_id, start, end)
    return errors


def company_view_of_request(db: Session, company: Company, req: RideRequest, route: Route):
    """Return (company_errors, [(vehicle, errors), ...]).

    The company can serve the request (R4) when company_errors is empty and at
    least one vehicle has no errors.
    """
    company_errors = check_company_serves(company, req.flight.to_airport, req.hotel.city,
                                          req.hotel.area, req.pickup)
    start, end = busy_window(req, route)
    cars = [(v, check_car_fits(v, req) + check_car_free(db, v.vehicle_id, start, end))
            for v in company.vehicles]
    return company_errors, cars


def can_serve(db: Session, company: Company, req: RideRequest, route: Route) -> bool:
    company_errors, cars = company_view_of_request(db, company, req, route)
    return not company_errors and any(not errs for _, errs in cars)


def why_no_supplier(db: Session, req: RideRequest, route: Route) -> list[str]:
    """Explain, per supplier at this airport, why nobody can serve the request."""
    airport = req.flight.to_airport
    companies = db.scalars(select(Company).order_by(Company.company_id)).all()
    at_airport = [c for c in companies if airport in c.airports]
    if not at_airport:
        return [f"No supplier works at {airport}."]
    reasons = []
    for c in at_airport:
        company_errors, cars = company_view_of_request(db, c, req, route)
        if company_errors:
            reasons.append("; ".join(e.message for e in company_errors))
            continue
        car_reasons = [f"{v.vehicle_id}: {errs[0].message}" for v, errs in cars if errs]
        reasons.append(f"{c.name} has no car that fits and is free — " + " | ".join(car_reasons))
    return reasons
