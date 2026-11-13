"""SQLAlchemy models.

Catalog tables (airports, flights, hotels, routes, companies, vehicles, booked_rides)
are loaded from the read-only JSON files by seed.py. The other tables hold app data.
All datetimes are naive local time of the arrival airport (DATA_DICTIONARY section 5).
"""
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


# ---------- Catalog (loaded from data files) ----------

class Airport(Base):
    __tablename__ = "airports"
    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    name: Mapped[str] = mapped_column(String)
    city: Mapped[str] = mapped_column(String)
    country: Mapped[str] = mapped_column(String(2))
    timezone: Mapped[str] = mapped_column(String)
    serves_cities: Mapped[list] = mapped_column(JSON, default=list)


class Flight(Base):
    __tablename__ = "flights"
    flight_id: Mapped[str] = mapped_column(String, primary_key=True)
    airline: Mapped[str] = mapped_column(String)
    flight_number: Mapped[str] = mapped_column(String)
    from_airport: Mapped[str] = mapped_column(String(3))
    to_airport: Mapped[str] = mapped_column(String(3))
    departure_local: Mapped[datetime] = mapped_column(DateTime)
    arrival_local: Mapped[datetime] = mapped_column(DateTime)


class Hotel(Base):
    __tablename__ = "hotels"
    hotel_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    city: Mapped[str] = mapped_column(String)
    area: Mapped[str] = mapped_column(String)
    stars: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Route(Base):
    __tablename__ = "routes"
    __table_args__ = (UniqueConstraint("airport", "city", "area"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    airport: Mapped[str] = mapped_column(String(3))
    city: Mapped[str] = mapped_column(String)
    area: Mapped[str] = mapped_column(String)
    distance_km: Mapped[float] = mapped_column(Float)
    drive_minutes: Mapped[int] = mapped_column(Integer)
    price_min_inr: Mapped[int] = mapped_column(Integer)
    price_max_inr: Mapped[int] = mapped_column(Integer)


class Company(Base):
    __tablename__ = "companies"
    company_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    airports: Mapped[list] = mapped_column(JSON)   # ["NRT", "HND"]
    areas: Mapped[list] = mapped_column(JSON)      # [{"city": "Tokyo", "area": "Ueno"}, ...]
    service_from: Mapped[str] = mapped_column(String(5))   # "HH:MM", inclusive
    service_until: Mapped[str] = mapped_column(String(5))  # "HH:MM", inclusive, may cross midnight
    rating: Mapped[float] = mapped_column(Float)
    vehicles: Mapped[list["Vehicle"]] = relationship(back_populates="company", order_by="Vehicle.vehicle_id")


class Vehicle(Base):
    __tablename__ = "vehicles"
    vehicle_id: Mapped[str] = mapped_column(String, primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.company_id"))
    type: Mapped[str] = mapped_column(String)  # HATCHBACK | SEDAN | SUV | BUS
    seats: Mapped[int] = mapped_column(Integer)
    large_bags: Mapped[int] = mapped_column(Integer)
    small_bags: Mapped[int] = mapped_column(Integer)
    company: Mapped[Company] = relationship(back_populates="vehicles")


class BookedRide(Base):
    """Rides booked before the event. They only block a car (R6)."""
    __tablename__ = "booked_rides"
    ride_id: Mapped[str] = mapped_column(String, primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.company_id"))
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.vehicle_id"))
    start: Mapped[datetime] = mapped_column(DateTime)
    end: Mapped[datetime] = mapped_column(DateTime)


# ---------- App data ----------

class RideRequest(Base):
    __tablename__ = "ride_requests"
    request_id: Mapped[str] = mapped_column(String, primary_key=True)
    traveler_name: Mapped[str] = mapped_column(String)
    flight_id: Mapped[str] = mapped_column(ForeignKey("flights.flight_id"))
    hotel_id: Mapped[str] = mapped_column(ForeignKey("hotels.hotel_id"))
    adults: Mapped[int] = mapped_column(Integer)
    child_ages: Mapped[list] = mapped_column(JSON, default=list)
    large_bags: Mapped[int] = mapped_column(Integer)
    small_bags: Mapped[int] = mapped_column(Integer)
    pickup: Mapped[datetime] = mapped_column(DateTime)
    car_type: Mapped[str | None] = mapped_column(String, nullable=True)
    price_inr: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String, default="OPEN")  # OPEN | BOOKED
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    flight: Mapped[Flight] = relationship()
    hotel: Mapped[Hotel] = relationship()
    offers: Mapped[list["Offer"]] = relationship(back_populates="request", order_by="Offer.id")

    @property
    def passengers(self) -> int:
        return self.adults + len(self.child_ages or [])


class Offer(Base):
    """A taxi assigned by a supplier to a request: one car + a price."""
    __tablename__ = "offers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(ForeignKey("ride_requests.request_id"))
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.company_id"))
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.vehicle_id"))
    price_inr: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String, default="OPEN")  # OPEN | BOOKED | REJECTED | NOT_CHOSEN
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    request: Mapped[RideRequest] = relationship(back_populates="offers")
    company: Mapped[Company] = relationship()
    vehicle: Mapped[Vehicle] = relationship()


class Booking(Base):
    __tablename__ = "bookings"
    booking_number: Mapped[str] = mapped_column(String(10), primary_key=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id"), unique=True)
    request_id: Mapped[str] = mapped_column(ForeignKey("ride_requests.request_id"))
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.vehicle_id"))
    busy_start: Mapped[datetime] = mapped_column(DateTime)
    busy_end: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    offer: Mapped[Offer] = relationship()
    changes: Mapped[list["ChangeRequest"]] = relationship(back_populates="booking", order_by="ChangeRequest.id")


class ChangeRequest(Base):
    """The traveler asks for a new flight and/or pickup after booking (R9, M7).

    The supplier accepts or rejects it. On accept the booking moves to the new
    time; on reject the old booking stays as it was.
    """
    __tablename__ = "change_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    booking_number: Mapped[str] = mapped_column(ForeignKey("bookings.booking_number"))
    old_flight_id: Mapped[str] = mapped_column(ForeignKey("flights.flight_id"))
    old_pickup: Mapped[datetime] = mapped_column(DateTime)
    new_flight_id: Mapped[str] = mapped_column(ForeignKey("flights.flight_id"))
    new_pickup: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String, default="WAITING")  # WAITING | ACCEPTED | REJECTED
    reason: Mapped[str | None] = mapped_column(String, nullable=True)  # why it was rejected
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    booking: Mapped[Booking] = relationship(back_populates="changes")
    old_flight: Mapped[Flight] = relationship(foreign_keys=[old_flight_id])
    new_flight: Mapped[Flight] = relationship(foreign_keys=[new_flight_id])
