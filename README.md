# Airport Taxi → Ride Offers

Travelers post a ride from the airport to their hotel **at the price they choose**. Taxi
suppliers see only the requests they can actually serve and answer with a car and a price,
either accepting the traveler's price or making a counter-offer. The traveler books one taxi,
gets a 10-digit booking number, and can ask for a change if the flight changes.

### ▶ [Watch the video demo](https://drive.google.com/drive/folders/1WMvM0tYfHAtw5ykQm_G7BWRP34-BkzZI?usp=sharing)

![Home page](assets/readme/home.png)

**Status:** all must-haves (M1–M7) are done, plus G1, G2, G4 and G5.

---

## Contents

- [Video demo](https://drive.google.com/drive/folders/1WMvM0tYfHAtw5ykQm_G7BWRP34-BkzZI?usp=sharing)
- [Screenshots](#screenshots)
- [Tech stack](#tech-stack)
- [Setup](#setup)
- [Project structure](#project-structure)
- [User flows](#user-flows)
- [Data model (ER diagram)](#data-model-er-diagram)
- [Architecture](#architecture)
- [API](#api)
- [Business rules](#business-rules)
- [What is done](#what-is-done)
- [Known limitations](#known-limitations)
- [Troubleshooting](#troubleshooting)

---

## Screenshots

### Home: pick who you are
A traveler starts fresh or opens a booking that is still going. A supplier picks their company.
No login.

![Home page](assets/readme/home.png)

### Traveler: request a ride
Flight and hotel dropdowns show the suggested price range (R3) and the earliest pickup (R2) as
soon as both are chosen. Steppers for travelers and bags, chips for car type.

![Request a ride form](assets/readme/request-form.png)

### Traveler: taxis offered
The request page refreshes every 5 seconds. While no taxi is offered yet, it says which
suppliers can serve the ride, or why nobody can.

![Request page with offers](assets/readme/request-offers.png)

### Supplier dashboard
Only requests this supplier can serve (airport, area, opening hours, a car that fits and is
free). Choose a car, then accept the traveler's price or offer a different one.

![Supplier dashboard](assets/readme/supplier-dashboard.png)

### Bookings
Open a booking by its 10-digit number, or pick it from the list.

![Bookings page](assets/readme/bookings.png)

### Mobile

<img src="assets/readme/mobile-request-form.png" alt="Request form on a phone" width="320">

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 18, React Router 6, Vite 5, plain CSS (no UI library) |
| Backend | Python 3.10+, FastAPI, Pydantic 2, SQLAlchemy 2 |
| Database | PostgreSQL (psycopg 3 driver) |
| Data | Read-only JSON catalog in `data/`, loaded by `backend/seed.py` |

---

## Setup

### Prerequisites

- **Python 3.10+**
- **Node.js 18+** (with npm)
- **PostgreSQL 14+** running locally

### 1. Create the database

```bash
createdb airport_taxi
# or in psql:  CREATE DATABASE airport_taxi;
```

### 2. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate             # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env             # macOS/Linux: cp .env.example .env
```

Edit `backend/.env` and set your PostgreSQL password:

| Variable | Example | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://postgres:secret@localhost:5432/airport_taxi` | Database connection |
| `FRONTEND_ORIGIN` | `http://localhost:5173` | Origin allowed by CORS |

Load the data and start the API:

```bash
python seed.py                     # drops and reloads every table from data/ (safe to re-run)
uvicorn app.main:app --reload      # http://localhost:8000   API docs: http://localhost:8000/docs
```

> **`seed.py` wipes app data.** It drops and recreates every table, including requests,
> offers and bookings made in the app. Run it again any time you want a clean start.

### 3. Frontend

```bash
cd frontend
npm install
copy .env.example .env             # optional; macOS/Linux: cp .env.example .env
npm run dev                        # http://localhost:5173
```

| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000/api` | Where the frontend sends API calls |

### 4. Try it

1. Open http://localhost:5173 and click **Start as a new traveler**.
2. Pick a flight that lands at NRT, HND, KIX, DXB or AUH, then a hotel. The suggested price
   range appears. Enter a price inside it and post the request.
3. Go back home and pick a **taxi supplier** that serves that airport (for example
   *Capital Cabs* for AUH). Your request is on its dashboard. Accept it or counter-offer.
4. Back on the request page (it refreshes every 5 s), click **Book**. You get a booking number.
5. The booking now appears in the home page dropdown under **Or open an existing booking**.

### Production build

```bash
cd frontend
npm run build                      # output in frontend/dist/
```

---

## Project structure

```
.
├── backend/
│   ├── app/
│   │   ├── main.py           FastAPI app, CORS, error handlers, startup migration
│   │   ├── db.py             engine + session (reads DATABASE_URL)
│   │   ├── models.py         SQLAlchemy tables
│   │   ├── schemas.py        request bodies (Pydantic) and JSON output shapes
│   │   ├── rules.py          every business rule R1–R9, one function each
│   │   └── routers/
│   │       ├── catalog.py    flights, hotels, price range
│   │       ├── requests.py   ride requests, book / reject an offer
│   │       ├── suppliers.py  companies, supplier dashboard, assign a car
│   │       └── bookings.py   booking summary, active bookings, change requests
│   ├── seed.py               data/*.json → tables
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── api.js            every backend call
│       ├── App.jsx           routes, nav bar, page reveal animation
│       ├── useReveal.js      fade-in of page blocks as they scroll into view
│       ├── usePolling.js     5-second refresh
│       ├── format.js         ₹, dates, flight labels
│       ├── components/       Errors, Icon
│       └── pages/            RolePicker, TravelerHome, RequestOffers,
│                             SupplierDashboard, BookingSummary
├── data/
│   ├── catalog/              airports, flights, hotels
│   └── problem-2/            routes, taxi companies, booked rides, open requests
├── assets/readme/            screenshots used in this README
└── DATA_DICTIONARY.md        meaning of every data field and rule
```

---

## User flows

### Traveler

```mermaid
flowchart TD
    A([Home]) --> B{New or returning?}
    B -- Start as a new traveler --> C[Request a ride form]
    B -- Pick an existing booking --> K[Booking summary]

    C --> D[Choose flight + hotel]
    D --> E[See suggested price range<br/>and earliest pickup]
    E --> F[Travelers, bags, pickup,<br/>car type, your price]
    F --> G{POST /requests<br/>R1 · R2 · R3 pass?}
    G -- No --> G1[Error names the rule<br/>e.g. R3 price outside range] --> F
    G -- Yes --> H[Request page<br/>refreshes every 5 s]

    H --> I{Any taxi offered?}
    I -- Not yet --> I1[Shows who can serve it,<br/>or why nobody can] --> H
    I -- Yes --> J{Book or reject?}
    J -- Reject --> H
    J -- Book --> J1{Car still free? R6/R8}
    J1 -- No --> J2[Refused, pick another taxi] --> H
    J1 -- Yes --> K

    K --> L{Flight changed?}
    L -- Yes --> M[Send change request<br/>new flight and/or pickup]
    M --> N[Waiting for the supplier]
    N --> K
```

### Taxi supplier

```mermaid
flowchart TD
    A([Home]) --> B[Choose your company]
    B --> C[Supplier dashboard]
    C --> D[Requests you can serve<br/>airport · area · hours · car fits and is free]
    D --> E[Choose a car<br/>optional offer end time]
    E --> F{Price}
    F -- Accept traveler's price --> G[POST offer]
    F -- Offer a different price --> G
    G --> H{R3–R7 pass?}
    H -- No --> H1[Error names every broken rule] --> E
    H -- Yes --> I[Your taxis<br/>OPEN → BOOKED / REJECTED / NOT_CHOSEN / EXPIRED]

    C --> J[Change requests]
    J --> K{Accept or reject?}
    K -- Reject --> L[Old booking stays]
    K -- Accept --> M{New pickup ≥ 60 min after landing<br/>and same car free? R2 · R6}
    M -- Yes --> N[Booking moves to the new time]
    M -- No --> O[Refused with the reason<br/>old booking stays]
```

### Booking, end to end

```mermaid
sequenceDiagram
    actor T as Traveler
    participant FE as Frontend
    participant API as FastAPI
    participant DB as PostgreSQL
    actor S as Supplier

    T->>FE: Fill the request form
    FE->>API: GET /price-range
    API-->>FE: Suggested range, earliest pickup
    FE->>API: POST /requests
    API->>DB: Insert ride_request (OPEN)
    S->>FE: Open dashboard
    FE->>API: GET /suppliers/{id}/requests
    API-->>FE: Requests this supplier can serve
    S->>FE: Assign car + price
    FE->>API: POST /requests/{id}/offers
    API->>DB: Insert offer (OPEN)
    loop every 5 s
        FE->>API: GET /requests/{id}
    end
    T->>FE: Book
    FE->>API: POST /offers/{id}/book
    API->>DB: Re-check car (R6), insert booking, mark other offers NOT_CHOSEN
    API-->>FE: 10-digit booking number
```

### Status lifecycles

```mermaid
stateDiagram-v2
    direction LR
    state "Ride request" as RR {
        [*] --> OPEN
        OPEN --> BOOKED: traveler books a taxi
    }
    state "Offer" as OF {
        [*] --> O_OPEN
        O_OPEN: OPEN
        O_OPEN --> O_BOOKED: traveler books it
        O_OPEN --> O_REJECTED: traveler rejects it
        O_OPEN --> O_NOT_CHOSEN: another taxi was booked
        O_OPEN --> O_EXPIRED: end time passed (G4)
        O_BOOKED: BOOKED
        O_REJECTED: REJECTED
        O_NOT_CHOSEN: NOT_CHOSEN
        O_EXPIRED: EXPIRED (shown, not stored)
    }
    state "Change request" as CR {
        [*] --> WAITING
        WAITING --> ACCEPTED: supplier accepts, R2 and R6 hold
        WAITING --> REJECTED: supplier rejects, or the rules fail
    }
```

---

## Data model (ER diagram)

Catalog tables (top) are loaded from `data/` by `seed.py` and never changed by the app. The
app tables (bottom) hold requests, offers, bookings and change requests.

```mermaid
erDiagram
    AIRPORT {
        string code PK "e.g. NRT"
        string name
        string city
        string country
        string timezone
        json serves_cities
    }
    FLIGHT {
        string flight_id PK
        string airline
        string flight_number
        string from_airport "airport code"
        string to_airport "airport code"
        datetime departure_local
        datetime arrival_local
    }
    HOTEL {
        string hotel_id PK
        string name
        string city
        string area
        int stars
    }
    ROUTE {
        int id PK
        string airport "UK with city + area"
        string city
        string area
        float distance_km
        int drive_minutes
        int price_min_inr
        int price_max_inr
    }
    COMPANY {
        string company_id PK
        string name
        json airports
        json areas
        string service_from "HH:MM"
        string service_until "HH:MM"
        float rating
    }
    VEHICLE {
        string vehicle_id PK
        string company_id FK
        string type "HATCHBACK SEDAN SUV BUS"
        int seats
        int large_bags
        int small_bags
    }
    BOOKED_RIDE {
        string ride_id PK
        string company_id FK
        string vehicle_id FK
        datetime start
        datetime end
    }
    RIDE_REQUEST {
        string request_id PK "REQ-0001"
        string traveler_name
        string flight_id FK
        string hotel_id FK
        int adults
        json child_ages
        int large_bags
        int small_bags
        datetime pickup
        string car_type "nullable"
        int price_inr
        string status "OPEN BOOKED"
        datetime created_at
    }
    OFFER {
        int id PK
        string request_id FK
        string company_id FK
        string vehicle_id FK
        int price_inr
        string status "OPEN BOOKED REJECTED NOT_CHOSEN"
        datetime expires_at "UTC, nullable"
        datetime created_at
    }
    BOOKING {
        string booking_number PK "10 digits"
        int offer_id FK,UK
        string request_id FK
        string vehicle_id FK
        datetime busy_start
        datetime busy_end
        datetime created_at
    }
    CHANGE_REQUEST {
        int id PK
        string booking_number FK
        string old_flight_id FK
        datetime old_pickup
        string new_flight_id FK
        datetime new_pickup
        string status "WAITING ACCEPTED REJECTED"
        string reason "why rejected"
        datetime created_at
        datetime decided_at
    }

    AIRPORT ||--o{ FLIGHT : "lands at (to_airport)"
    AIRPORT ||--o{ ROUTE : "starts at"
    HOTEL }o..|| ROUTE : "same city + area"
    COMPANY ||--|{ VEHICLE : owns
    COMPANY ||--o{ BOOKED_RIDE : has
    VEHICLE ||--o{ BOOKED_RIDE : "busy in"
    FLIGHT ||--o{ RIDE_REQUEST : "arrives on"
    HOTEL ||--o{ RIDE_REQUEST : "goes to"
    RIDE_REQUEST ||--o{ OFFER : receives
    COMPANY ||--o{ OFFER : makes
    VEHICLE ||--o{ OFFER : "offered as"
    OFFER ||--o| BOOKING : "becomes"
    RIDE_REQUEST ||--o| BOOKING : "booked as"
    VEHICLE ||--o{ BOOKING : "reserved in"
    BOOKING ||--o{ CHANGE_REQUEST : has
    FLIGHT ||--o{ CHANGE_REQUEST : "old / new flight"
```

`from_airport`/`to_airport` on flights and the route ↔ hotel match (by city + area) are
logical links. They are joined in code and are not foreign keys in the database.

| Table | Source | Notes |
|---|---|---|
| airports, flights, hotels, routes, companies, vehicles, booked_rides | `data/` files | read-only catalog |
| ride_requests | app + `open_requests.json` | status `OPEN` / `BOOKED` |
| offers | app | one car + price from one supplier; `OPEN` / `BOOKED` / `REJECTED` / `NOT_CHOSEN` (shown as `EXPIRED` after its end time) |
| bookings | app | 10-digit `booking_number`, the car, and its busy window |
| change_requests | app | old and new flight + pickup; `WAITING` / `ACCEPTED` / `REJECTED`, with the reason when rejected |

---

## Architecture

```mermaid
flowchart LR
    subgraph Browser
        FE["React + Vite<br/>src/pages/* one file per screen<br/>src/api.js all API calls"]
    end
    subgraph Backend["FastAPI (backend/app)"]
        R["routers/*<br/>HTTP only"] --> RU["rules.py<br/>R1–R9"]
        R --> M["models.py"]
        RU --> M
    end
    FE -- "fetch JSON /api/*" --> R
    M -- SQLAlchemy --> DB[(PostgreSQL)]
    S["seed.py"] -- "data/*.json" --> DB
```

- **All logic is in the backend.** `app/rules.py` has one function per rule. Each returns a list
  of `RuleError(rule, message)`, so a refusal always names the rule it breaks.
- **One error shape:** every 4xx response is `{"errors": [{"rule": "R3", "message": "..."}]}`.
  Bad input (wrong types) uses `rule: "INPUT"`.
- **Busy cars (R6)** come from two tables: `booked_rides` (seeded) and `bookings` (made in the
  app). A car is busy from pickup to pickup + 2 × `drive_minutes`. Times that only touch do not
  overlap.
- **Times** are stored as naive local time of the arrival airport, as in the data. The one
  exception is the offer end time (G4), which is stored in UTC.
- Tables are created with `create_all` on startup. `seed.py` drops and recreates everything.

---

## API

Base URL: `http://localhost:8000/api`. Interactive docs at http://localhost:8000/docs.

| Method | Path | What it does |
|---|---|---|
| GET | `/flights`, `/hotels?flight_id=` | Catalog. Only flights that land at NRT/HND/KIX/DXB/AUH. Hotels only in cities that flight's airport serves. |
| GET | `/price-range?flight_id=&hotel_id=` | R1 check, suggested range (R3), earliest pickup (R2) |
| POST | `/requests` | Create a request. Checks R1, R2, R3 and the car type. |
| GET | `/requests`, `/requests/{id}` | List requests, or one with its offers. With no supplier able to serve it, says why (M2). |
| POST | `/offers/{id}/book` | Book a taxi (R8). Re-checks the car (R6), returns the booking number, marks other offers not chosen. |
| POST | `/offers/{id}/reject` | Reject a taxi (R8) |
| GET | `/companies` | Suppliers with their cars |
| GET | `/suppliers/{company_id}/requests` | Open requests this supplier can serve (R4–R6), each car marked "fits and is free" or with the rules it breaks |
| GET | `/suppliers/{company_id}/offers` | Taxis this supplier assigned, with status |
| POST | `/requests/{id}/offers` | Assign a car + price (R7). Body `{company_id, vehicle_id, price_inr, expires_at?}`. Checks R3–R7. |
| GET | `/bookings` | Every booking, newest first |
| GET | `/bookings/active` | Bookings whose ride is not over yet (car's busy end is after "now" at the arrival airport). Used by the home page dropdown. |
| GET | `/bookings/{booking_number}` | Booking summary (M5). Wrong number: 404 "not found". |
| POST | `/bookings/{booking_number}/changes` | Traveler asks for a change (R9). Body `{flight_id?, pickup?}`. Checks R1 and R2. |
| GET | `/suppliers/{company_id}/changes` | Change requests for this supplier's bookings, with whether accepting would pass R2/R6 |
| POST | `/changes/{id}/accept` | Supplier accepts. Body `{company_id}`. Only if R2 holds and the same car is free; otherwise refused and the old booking stays. |
| POST | `/changes/{id}/reject` | Supplier rejects. The old booking stays. |

Example error:

```json
{ "errors": [{ "rule": "R3", "message": "The price ₹9,000 is outside the suggested range ₹2,400 – ₹4,500 for this route." }] }
```

---

## Business rules

Full wording is in [DATA_DICTIONARY.md](DATA_DICTIONARY.md). In short:

| Rule | Meaning |
|---|---|
| R1 | The hotel must be in a city served by the flight's arrival airport |
| R2 | Pickup is at least 60 min after landing (no pickup time = earliest pickup) |
| R3 | Prices must be within the route's suggested range |
| R4 | The supplier serves that airport and hotel area, and is open at pickup time |
| R5 | The car has enough seats and bag space, and matches the requested car type |
| R6 | The car is free from pickup until it is back (pickup + 2 × drive time) |
| R7 | A supplier can only assign its own cars |
| R8 | The traveler books or rejects an offer; a rejected or busy one can't be booked |
| R9 | A booked ride can ask for a new flight/pickup; the supplier accepts or rejects |

---

## What is done

- **M1 Ride request.** The suggested range appears as soon as a flight and hotel are chosen.
  Errors name the rule, for example `R2 · Pickup 10 Apr 2027 11:00 is too early…`.
- **M2 Supplier dashboard.** A supplier sees only requests it can serve. When nobody can serve a
  request, the traveler sees why, per supplier (for example REQ-0002: no sedan at KIX).
- **M3 Assign a car.** "Accept at ₹{traveler price}" or "Offer a different price". Every car of
  the supplier is listed, with the reason when it can't be used.
- **M4 Book or reject.** The request page refreshes every 5 s and labels each taxi "Your price" or
  "+₹X / −₹X". Booking gives a unique 10-digit number.
- **M5 Booking summary.** Opens by booking number: flight, hotel, pickup, supplier, car, price and
  the car's busy time. Read from the database, so it survives a backend restart.
- **M6 No double booking.** Booking re-checks the car against `booked_rides` and every app booking.
- **M7 Flight change.** The traveler asks for a new flight and/or pickup; the supplier accepts or
  rejects. Accept works only if R2 holds and the same car is free at the new time.
- **G1 Several cars per supplier.** A supplier can offer several cars on one request, each with
  its own price.
- **G2 Car type.** Hatchback, Sedan, SUV, Bus or Any. Only that type can be assigned (R5).
- **G4 Offer expiry.** Optional end time per offer; after it the taxi shows as expired and
  booking is refused.
- **G5 Sort and filter.** Taxis can be sorted by price and filtered by car type.
- **Returning travelers.** The home page lists bookings that are still going
  (`GET /bookings/active`), so a traveler can jump straight to their booking.
- **UI.** Dark navy glass theme, line icons on key fields, number steppers and car-type chips in
  the request form, details of the chosen item shown under each dropdown, and a smooth
  fade-in of page blocks as they scroll into view (off when the system asks for reduced
  motion). Works down to phone width.

---

## Known limitations

- **No login.** Anyone can open any request, booking or supplier dashboard.
- **Change requests:** the new flight must land at the same airport. One change can wait at a
  time. Accepting checks R2 and the car's free time, not the supplier's opening hours.
- **Polling** every 5 s instead of push updates.
- **S1/S2** (stretch goals) are not built.
- `seed.py` wipes app data too ("drop + recreate", as the spec asks).

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `DATABASE_URL is not set` | Copy `backend/.env.example` to `backend/.env` and fill it in. |
| `ModuleNotFoundError: dotenv` | The virtualenv is not active. Run `.venv\Scripts\activate` (or `source .venv/bin/activate`). |
| Frontend shows "Cannot reach the backend" | Start the API with `uvicorn app.main:app --reload` on port 8000, or set `VITE_API_URL`. |
| White screen after editing files | The Vite dev server cached a half-saved file. Stop it and run `npm run dev` again, then hard-refresh (Ctrl+Shift+R). |
| Data looks wrong or old | Run `python seed.py` for a clean database. This deletes requests and bookings. |
