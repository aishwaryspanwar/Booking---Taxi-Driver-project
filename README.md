# Airport Taxi → Ride Offers (Problem 2)

Travelers post a ride request from the airport to their hotel with their own price. Taxi
suppliers see the requests they can serve and assign a car with a price: the traveler's price
to accept it, or a different price as a counter-offer. The traveler then books one taxi or
rejects it.

Scope of this pass: **M1–M4** (ride request, supplier dashboard, assign a car, book or reject).

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
  src/pages/* one file per screen            app/rules.py   every rule R1–R8
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

### API

| Method | Path | What it does |
|---|---|---|
| GET | `/api/flights`, `/api/hotels` | Catalog. Only flights that land at NRT/HND/KIX/DXB/AUH are listed. |
| GET | `/api/price-range?flight_id=&hotel_id=` | R1 check, suggested range (R3), earliest pickup (R2) |
| POST | `/api/requests` | Create a request. Checks R1, R2, R3 (and the car type). |
| GET | `/api/requests`, `/api/requests/{id}` | List requests or get one with its offers. When no supplier can serve it, says why (M2). |
| POST | `/api/offers/{id}/book` | Book a taxi (R8). Checks the car again for R6, returns the booking number, and marks the other offers not chosen. |
| POST | `/api/offers/{id}/reject` | Reject a taxi (R8) |

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
- Car type (G2) is enforced, because `open_requests.json` uses it.
- Seeded busy rides block cars. In the Menon case, Sakura's SC-2 is busy 11:00–14:00
  (RIDE-0001), so only SC-3 can be assigned.

## Not built yet / known limitations

- **Supplier APIs are in progress (being built separately):** `GET /api/companies`,
  `GET /api/suppliers/{company_id}/requests`, `GET /api/suppliers/{company_id}/offers`,
  `POST /api/requests/{id}/offers`. The frontend's supplier pages already call these paths.

- **M5 Booking summary page and lookup by number:** not built. The booking number and the ride
  details show on the request page, and they are saved in the database.
- **M7 / R9 Change requests:** no routes yet.
- **G1/G4/G5, S1/S2:** not built. A supplier can already assign several different cars to one
  request.
- There is no login, so the traveler page lists every request.
- Polling every 5 s instead of push updates.
- `seed.py` wipes the app data too, which is what the spec asked for ("drop + recreate").
