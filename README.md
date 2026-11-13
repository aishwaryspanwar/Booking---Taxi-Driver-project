# Airport Taxi → Ride Offers (Problem 2)

Travelers post a ride request from the airport to their hotel with their own price. Taxi
suppliers see the requests they can serve and assign a car with a price: the traveler's price
to accept it, or a different price as a counter-offer. The traveler then books one taxi or
rejects it. The booking number opens a summary, and the traveler can ask for a change if the
flight changes.

Status: **all must-haves (M1–M7) are done.**

## Run it

You need Python 3.10+, Node 18+, and a local PostgreSQL.

```bash
# 1. Backend (from backend/)
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env            # then set DATABASE_URL (create the database first, e.g. `createdb airport_taxi`)
python seed.py                    # drops and reloads all tables from data/ (safe to re-run)
uvicorn app.main:app --reload     # http://localhost:8000  (API docs: /docs)

# 2. Frontend (from frontend/)
npm install
npm run dev                       # http://localhost:5173
```

The frontend calls `http://localhost:8000/api` by default. Set `VITE_API_URL` in
`frontend/.env` to change it.

## Architecture

```
frontend/ (React + Vite)      ──fetch──►   backend/ (FastAPI)      ──SQLAlchemy──►  PostgreSQL
  src/api.js  all API calls                  app/routers/*  HTTP only
  src/pages/* one file per screen            app/rules.py   every rule R1–R9
                                             app/models.py  tables
                                             seed.py        data/*.json → tables
```

- **All logic is in the backend.** `app/rules.py` has one function per rule. Each one returns a
  list of `RuleError(rule, message)`, so a refusal always names the rule it breaks.
- **One error shape:** every 4xx response is `{"errors": [{"rule": "R3", "message": "..."}]}`.
  Bad input (wrong types) uses `rule: "INPUT"`.
- **Busy cars (R6)** come from two tables: `booked_rides` (seeded from the data file) and
  `bookings` (made in the app). A car is busy from pickup to pickup + 2 × `drive_minutes`. Times
  that only touch (one ends exactly when the next starts) do not overlap.
- **Times** are stored as naive local time of the arrival airport, the same as in the data.
  There is no time zone conversion.
- Tables are created with `create_all` on startup. `seed.py` drops and recreates everything,
  including requests and bookings made in the app.

### Data model

| Table | Source | Notes |
|---|---|---|
| airports, flights, hotels, routes, companies, vehicles, booked_rides | `data/` files | read-only catalog |
| ride_requests | app + `open_requests.json` | status `OPEN` / `BOOKED` |
| offers | app | one car + price from one supplier; `OPEN` / `BOOKED` / `REJECTED` / `NOT_CHOSEN` |
| bookings | app | 10-digit `booking_number`, the car, and its busy window |
| change_requests | app | old and new flight + pickup; `WAITING` / `ACCEPTED` / `REJECTED`, with the reason when rejected |

### API

| Method | Path | What it does |
|---|---|---|
| GET | `/api/flights`, `/api/hotels` | Catalog. Only flights that land at NRT/HND/KIX/DXB/AUH are listed. |
| GET | `/api/price-range?flight_id=&hotel_id=` | R1 check, suggested range (R3), earliest pickup (R2) |
| POST | `/api/requests` | Create a request. Checks R1, R2, R3 (and the car type). |
| GET | `/api/requests`, `/api/requests/{id}` | List requests or get one with its offers. When no supplier can serve it, says why (M2). |
| POST | `/api/offers/{id}/book` | Book a taxi (R8). Checks the car again for R6, returns the booking number, and marks the other offers not chosen. |
| POST | `/api/offers/{id}/reject` | Reject a taxi (R8) |
| GET | `/api/companies` | Suppliers with their cars (role picker) |
| GET | `/api/suppliers/{company_id}/requests` | Open requests this supplier can serve (R4–R6). Each car is marked "fits and is free" or lists the rules it breaks. |
| GET | `/api/suppliers/{company_id}/offers` | Taxis this supplier assigned, with status `OPEN` / `BOOKED` / `REJECTED` / `NOT_CHOSEN` |
| POST | `/api/requests/{id}/offers` | Assign a car + price (R7). Body `{company_id, vehicle_id, price_inr}`. Price = traveler's price (accept) or another price in range (counter-offer). Checks R3–R7. |
| GET | `/api/bookings/{booking_number}` | Booking summary (M5): flight, hotel, pickup, supplier, car, price, change requests. Wrong number: 404 "not found". |
| POST | `/api/bookings/{booking_number}/changes` | Traveler asks for a change (R9). Body `{flight_id?, pickup?}`. Checks R1 and R2 for the new flight/pickup. |
| GET | `/api/suppliers/{company_id}/changes` | Change requests for this supplier's bookings. A waiting one shows in advance whether accepting would pass R2/R6. |
| POST | `/api/changes/{id}/accept` | Supplier accepts (R9). Body `{company_id}`. Only if the new pickup follows R2 and the same car is free; otherwise the platform refuses and the old booking stays. |
| POST | `/api/changes/{id}/reject` | Supplier rejects. The old booking stays. |

## What is done

- **M1 Ride request.** The form shows the suggested range as soon as you pick a flight and
  hotel. Errors name the rule, for example `R2 · Pickup 10 Apr 2027 11:00 is too early…`.
- **M2 Supplier dashboard.** A supplier sees only the requests it can serve. When nobody can
  serve a request, the traveler sees why, per supplier (for example REQ-0002: no sedan at KIX).
- **M3 Assign a car.** "Accept at ₹{traveler price}" or "Offer a different price". The car list
  shows every car of the supplier, including ones that don't fit, so a refusal can be shown.
  The backend refuses with every broken rule (R3, R4, R5, R6, R7).
- **M4 Book or reject.** The offers page refreshes every 5 s and labels each taxi "Your price" or
  "+₹X / −₹X". Booking gives a unique 10-digit number. A rejected taxi cannot be booked, and
  booking a car that became busy is refused.
- **M5 Booking summary.** "My booking" opens a booking by its 10-digit number: flight, hotel,
  pickup, supplier, car, price and the car's busy time. A wrong number shows "Booking not found".
  It is read from the database, so it works after a backend restart.
- **M6 No double booking.** Booking checks the car again against `booked_rides` and every app
  booking. If the busy times overlap, the booking is refused with an R6 message.
- **M7 Flight change.** On the booking page the traveler picks a new flight and/or pickup. The
  supplier sees it under "Change requests" and accepts or rejects it. Accept works only if the
  new pickup is at least 60 min after the new flight lands (R2) and the same car is free at the
  new time (R6, ignoring the booking's own old time). If not, the platform refuses it, the
  change becomes rejected with the reason, and the old booking stays. The booking page shows
  every change and its result.
- **G1 Several cars per supplier.** A supplier can assign several of its cars to one request,
  each with its own price. The request stays on the dashboard while another of its cars fits,
  is free and is not offered yet. The same car cannot be offered twice while its first offer is
  open.
- **G2 Car type.** The traveler can pick Hatchback, Sedan, SUV or Bus (or Any). A supplier can
  only assign a car of that type (R5); other cars show the reason in the dropdown.
- **G4 Offer expiry.** A supplier can set an optional end time when assigning a car. After that
  time the taxi shows as "expired" and booking it is refused (409, rule G4). The end time must
  be in the future. On startup the backend adds the `offers.expires_at` column to an existing
  database.
- **G5 Sort and filter.** On the request page the traveler can sort taxis by price (low to high
  or high to low) and filter them by car type.
- Seeded busy rides block cars. In the Menon case, Sakura's SC-2 is busy 11:00–14:00
  (RIDE-0001), so only SC-3 can be assigned.

## Not built yet / known limitations

- **Change requests:** the new flight must land at the same airport as the booking, because
  the supplier, route and price were agreed for that airport. One change can wait at a time.
  Accepting checks R2 and the car's free time, as R9 says; it does not re-check the
  supplier's opening hours, so the supplier should reject a time it can't serve.
- **S1/S2:** not built.
- **Offer end time (G4)** is stored in UTC. The supplier picks it in their own time zone and the
  traveler sees it in theirs. It is precise to the minute.
- There is no login, so the traveler page lists every request.
- Polling every 5 s instead of push updates.
- `seed.py` wipes the app data too, which is what the spec asked for ("drop + recreate").
