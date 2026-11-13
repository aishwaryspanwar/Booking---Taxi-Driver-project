# Data Dictionary: Problem 2 (Airport Taxi → Ride Offers)

This file explains the mock data in this pack: what each file holds, what one record means, how the files link, and how your app uses them.

- All data is **synthetic** (invented). Real names are used only for cities, airports, and city areas.
- The data is **read-only**. Do not change the files. Judges use the same files.
- Flights cover **1 to 20 April 2027** only.
- **All prices are in INR** (whole rupees). There is no currency conversion.
- **All times are local times** of the place. See section 5.

---

## 1. Files at a glance

| File | One record is | Records | Your app uses it to |
|---|---|---|---|
| `data/problem-2/taxi_companies.json` | One taxi supplier, with its cars | 11 suppliers, 28 cars | Show a dashboard per supplier (M2). Decide who sees a request (R4) and which car fits (R5). |
| `data/problem-2/routes.json` | One drive from an airport to one hotel area | 33 | Suggest the price range (R3). Get the drive time for the busy time of a car (R6). |
| `data/problem-2/booked_rides.json` | One ride booked before the event | 6 | Keep those cars busy at those times (R6) |
| `data/problem-2/open_requests.json` | One ride request posted before the event | 3 | Show requests on supplier dashboards from the start |
| `data/catalog/flights.json` | One flight on one date | 469 | The traveler picks the arrival flight. Its arrival time gives the earliest pickup (R2). |
| `data/catalog/hotels.json` | One hotel | 49 | The traveler picks the hotel. Its city and area pick the route (R3) and the suppliers (R4). |
| `data/catalog/airports.json` | One airport | 10 | Check that the arrival airport serves the hotel's city (R1) |

---

## 2. How the files connect

```
open_requests.flight_id ──► flights.flight_id
open_requests.hotel_id  ──► hotels.hotel_id

flights.to (arrival airport) ──► airports.code ──► airports.serves_cities  must contain  hotels.city   (R1)

flights.to + hotels.city + hotels.area ──► routes (airport, city, area)
                                              ├─ price_min_inr, price_max_inr   (R3)
                                              └─ drive_minutes                  (R6)

taxi_companies.airports  must contain  flights.to                               (R4)
taxi_companies.areas     must contain  { hotels.city, hotels.area }             (R4)
taxi_companies.vehicles[].vehicle_id ◄── booked_rides.vehicle_id                (R6)
```

### Worked example: the Menon family

| Step | Read | Result |
|---|---|---|
| 1. The flight | `flights.json`, `flight_id` = `FL-401` | `to` = `NRT`, `arrival_local` = `2027-04-10T10:30:00` |
| 2. The hotel | `hotels.json`, `hotel_id` = `HTL-TYO-004` | Ueno Garden Inn, `city` = `Tokyo`, `area` = `Ueno` |
| 3. Airport serves the city? | `airports.json`, `code` = `NRT` | `serves_cities` = `["Tokyo"]`. Yes (R1). |
| 4. Earliest pickup | Arrival + 60 minutes | 10 April 2027, 11:30 (R2) |
| 5. Route | `routes.json`, `airport` = `NRT`, `city` = `Tokyo`, `area` = `Ueno` | `drive_minutes` = 90, price range ₹10,200 – ₹16,800 (R3) |
| 6. Busy time of a car | Pickup 11:30 + 2 × 90 minutes | The car is busy 11:30 – 14:30 (R6) |
| 7. Passengers and bags | The request | 2 adults + 1 child = 3 passengers, 3 large bags, 2 small bags (R5) |
| 8. Who sees the request | `taxi_companies.json`, `booked_rides.json` | Suppliers that work at `NRT`, drive to Tokyo / Ueno, are open at 11:30, and have a car that fits and is free 11:30 – 14:30 (R4) |

---

## 3. Files in detail

### `data/problem-2/taxi_companies.json`

**What it is:** the taxi suppliers on your platform. Each supplier lists the airports where it picks up, the hotel areas it drives to, its opening hours, and its cars.

**Why you need it:** the user can act as any of these suppliers (Flow 2). A supplier sees a request only if it can serve it (R4). It assigns one of its own cars (R5, R7).

```json
{ "company_id": "TX-JP-01", "name": "Sakura Cabs", "airports": ["NRT", "HND"],
  "areas": [{ "city": "Tokyo", "area": "Asakusa" }, { "city": "Tokyo", "area": "Ueno" }, ...],
  "service_from": "06:00", "service_until": "23:00", "rating": 4.4,
  "vehicles": [
    { "vehicle_id": "SC-1", "type": "SEDAN", "seats": 4, "large_bags": 2, "small_bags": 2 },
    { "vehicle_id": "SC-2", "type": "SUV", "seats": 6, "large_bags": 4, "small_bags": 3 }, ...] }
```

| Field | Meaning | How you use it |
|---|---|---|
| `company_id` | Unique ID of the supplier | The supplier the user acts as. Links to `booked_rides.company_id`. |
| `name` | Supplier name | Display |
| `airports` | Airport codes where it picks up | R4: must contain the arrival airport (`flights.to`) |
| `areas` | Hotel areas it drives to: list of `{ "city", "area" }` | R4: must contain the hotel's `city` and `area` |
| `service_from`, `service_until` | Opening hours, local time of the airport. Both ends included. | R4: the pickup time is inside the hours |
| `rating` | Supplier rating, 4.0 to 4.8 (scale 0–5) | Display, sort (optional) |
| `vehicles` | The supplier's cars | The supplier assigns one of these |
| `vehicles[].vehicle_id` | Unique ID of the car (unique in the whole file) | Links to `booked_rides.vehicle_id`. Store it on an assigned taxi. |
| `vehicles[].type` | `HATCHBACK`, `SEDAN`, `SUV`, `BUS` | R5: if the traveler chose a car type, the car has that type |
| `vehicles[].seats` | Passenger seats | R5: seats ≥ passengers (adults + children) |
| `vehicles[].large_bags`, `small_bags` | Bag space for large and small bags | R5: car `large_bags` ≥ request `large_bags`, and car `small_bags` ≥ request `small_bags`. Each size is checked on its own. |

What to know:
- `00:00`–`23:59` means open all day.
- `05:00`–`01:00` (Marina Rides) crosses midnight: a pickup at 00:30 is inside the hours.

### `data/problem-2/routes.json`

**What it is:** one record for each drive from an airport to a hotel area. Every hotel area has a route from every airport that serves its city.

**Why you need it:** the route gives the suggested price range (R3) and the drive time that makes a car busy (R6).

```json
{ "airport": "NRT", "city": "Tokyo", "area": "Ueno", "distance_km": 73.3, "drive_minutes": 90,
  "price_min_inr": 10200, "price_max_inr": 16800 }
```

| Field | Meaning | How you use it |
|---|---|---|
| `airport`, `city`, `area` | The route: from this airport to hotels in this city area. Together they are the key. | Find the route with `flights.to`, `hotels.city`, and `hotels.area` |
| `distance_km` | Road distance | Display only |
| `drive_minutes` | Drive time one way, airport to hotel. The drive back takes the same time. | R6: the car is busy from pickup to pickup + 2 × `drive_minutes` |
| `price_min_inr`, `price_max_inr` | The suggested price range, in INR. Both ends are allowed. | R3: the form shows this range. The traveler's price and every supplier price must be inside it. |

### `data/problem-2/booked_rides.json`

**What it is:** rides that suppliers booked before the event (outside your platform).

**Why you need it:** each ride keeps a car busy. A supplier cannot assign that car to a ride whose busy time overlaps (R6).

```json
{ "ride_id": "RIDE-0001", "company_id": "TX-JP-01", "vehicle_id": "SC-2",
  "start": "2027-04-10T11:00", "end": "2027-04-10T14:00" }
```

| Field | Meaning | How you use it |
|---|---|---|
| `ride_id` | Unique ID | Display |
| `company_id` | The supplier | Links to `taxi_companies.company_id` |
| `vehicle_id` | The busy car | Links to `vehicles[].vehicle_id` |
| `start`, `end` | The car is busy from `start` to `end` (local time of the airport) | R6: a new busy time of this car must not overlap. A time that starts exactly at `end` does not overlap. |

What to know:
- A booked ride has no traveler, no request, and no price. It only blocks the car. Do not show it to travelers.

### `data/problem-2/open_requests.json`

**What it is:** ride requests that travelers posted before the event. They are open: no supplier has assigned a car yet.

**Why you need it:** load them into your app at the start, so supplier dashboards are not empty. They have the same fields as a request that a traveler posts in your app (M1).

```json
{ "request_id": "REQ-0002", "traveler_name": "Arjun and Meera", "flight_id": "FL-501", "hotel_id": "HTL-OSA-001",
  "adults": 2, "child_ages": [], "large_bags": 2, "small_bags": 2, "pickup": "2027-04-09T10:15",
  "car_type": "SEDAN", "price_inr": 9000 }
```

| Field | Meaning | How you use it |
|---|---|---|
| `request_id` | Unique ID | Your own new requests can use your own ID format |
| `traveler_name` | Name of the traveler | Display |
| `flight_id` | The arrival flight | Links to `flights.flight_id` |
| `hotel_id` | The hotel | Links to `hotels.hotel_id` |
| `adults` | Number of adults (at least 1) | R5: passengers = `adults` + number of `child_ages` |
| `child_ages` | Age of each child, 0 to 17. Empty list = no children. | Each child is one passenger with a seat |
| `large_bags`, `small_bags` | Bags of the traveler | R5: the car has space for them |
| `pickup` | Pickup time, local time of the arrival airport | R2: at least 60 minutes after landing |
| `car_type` | `HATCHBACK`, `SEDAN`, `SUV`, `BUS`, or `null` = any type | R5 (G2) |
| `price_inr` | The traveler's price, in INR | R3: inside the route's range |

### `data/catalog/flights.json`

**What it is:** flights between India and Japan or the UAE, in both directions. This file is shared with other problems.

**Why you need it:** the traveler picks the flight they arrive on. Use only flights that arrive in Japan or the UAE: `to` is `NRT`, `HND`, `KIX`, `DXB`, or `AUH` (240 flights). Flights to India have no use in this problem.

```json
{ "flight_id": "FL-401", "airline": "AirVeda", "flight_number": "AV 520", "from": "BLR", "to": "NRT",
  "departure_local": "2027-04-09T23:50:00", "arrival_local": "2027-04-10T10:30:00", "stops": 0,
  "duration_minutes": 430, "price_per_seat": { "amount": 25200, "currency": "INR" }, "seats_left": 9, "cabin": "ECONOMY" }
```

| Field | Meaning | How you use it |
|---|---|---|
| `flight_id` | Unique ID of this flight on this date | The traveler picks it. Store it on the request. |
| `airline`, `flight_number` | One flight number repeats on several dates, each with its own `flight_id` | Display (for example "AV 520, lands 10:30") |
| `from` | Departure airport | Display |
| `to` | Arrival airport | R1, R3, R4: the pickup airport |
| `arrival_local` | Landing time, local time at the `to` airport | R2: the earliest pickup is 60 minutes later. With no pickup time, use the earliest pickup. |
| `departure_local`, `stops`, `duration_minutes`, `cabin` | Flight details | Display only |
| `price_per_seat`, `seats_left` | Flight price and free seats | Not used in this problem |

### `data/catalog/hotels.json`

**What it is:** fictional hotels in Tokyo, Kyoto, Osaka, Dubai, and Abu Dhabi. This file is shared with other problems.

**Why you need it:** the traveler picks the hotel. The hotel's `city` and `area` decide the route (R3) and the suppliers (R4).

```json
{ "hotel_id": "HTL-TYO-004", "name": "Ueno Garden Inn", "aliases": [], "city": "Tokyo", "area": "Ueno",
  "lat": 35.712, "lng": 139.7728, "rating": 7.9, "stars": 3, "check_in_from": "15:00", "check_out_until": "11:00",
  "family_friendly": true, "image": "images/hotels/HOTEL-BUSINESS-1.jpg" }
```

| Field | Meaning | How you use it |
|---|---|---|
| `hotel_id` | Unique ID | The traveler picks it. Store it on the request. |
| `name` | Hotel name | Display |
| `city` | City of the hotel | R1: the arrival airport serves it. R3, R4: route and supplier areas. |
| `area` | Part of the city, for example `Ueno` | R3, R4: route and supplier areas |
| `aliases`, `lat`, `lng`, `rating`, `stars`, `check_in_from`, `check_out_until`, `family_friendly` | Hotel details | Display only (optional) |
| `image` | A photo path. The photos are **not** in this pack. | Ignore it |

### `data/catalog/airports.json`

**What it is:** every airport in the data. This file is shared with other problems.

**Why you need it:** the arrival airport must serve the hotel's city (R1).

```json
{ "code": "NRT", "name": "Narita International Airport", "city": "Tokyo", "country": "JP",
  "timezone": "Asia/Tokyo", "lat": 35.772, "lng": 140.3929, "serves_cities": ["Tokyo"] }
```

| Field | Meaning | How you use it |
|---|---|---|
| `code` | IATA airport code | Matches `flights.to`, `routes.airport`, `taxi_companies.airports` |
| `name`, `city`, `country`, `lat`, `lng` | Airport details | Display |
| `timezone` | IANA time zone | Pickup and busy times at this airport are local to this zone |
| `serves_cities` | Cities a traveler can reach from this airport | R1: must contain the hotel's city |

What to know:
- `KIX` serves Osaka and Kyoto. `DXB` serves Dubai and Abu Dhabi. `AUH` serves Abu Dhabi. `NRT` and `HND` serve Tokyo.
- The 4 Indian airports have no `serves_cities` field. `ITM` has an empty list. No arrival flight lands at them.

---

## 4. Data your app creates

The files are read-only. Your app keeps its own data in its own database. It must survive a backend restart.

| Your data | Created when | Holds (minimum) |
|---|---|---|
| Ride request | A traveler posts the form (M1). The 3 open requests are loaded at the start. | Flight, hotel, adults, child ages, bags, pickup, car type, price, status |
| Assigned taxi (offer) | A supplier assigns a car (M3) | Request, supplier, car, price, status (open, booked, rejected, not chosen) |
| Booking | The traveler books a taxi (M4) | A unique 10-digit booking number, the taxi, the busy time of the car |
| Change request | The traveler asks for a new flight or pickup (M7) | Booking, new flight or pickup, status (waiting, accepted, rejected) |

A car is busy at the times in `booked_rides.json` **and** at the busy times of the bookings in your app.

---

## 5. Conventions

| Topic | Rule |
|---|---|
| Times | Local time of the place. The strings have no UTC offset. Flight arrival, pickup, opening hours, and busy times are all in the local time of the arrival airport, so you never convert time zones. |
| Time zones | Japan `Asia/Tokyo` (UTC+09:00), UAE `Asia/Dubai` (UTC+04:00), India `Asia/Kolkata` (UTC+05:30). No daylight saving time. |
| Date-times | `YYYY-MM-DDTHH:MM` or `YYYY-MM-DDTHH:MM:SS` |
| Clock times | `HH:MM`. Both ends of a window are included. A window like `05:00`–`01:00` runs past midnight. |
| Prices | Whole INR. `price_min_inr`, `price_max_inr`, and `price_inr` are numbers. Flights use `{ "amount", "currency": "INR" }`. |
| Passengers | Adults + children. A child is 0 to 17 years old, needs a seat, and counts as a passenger. |
| Overlap | Two busy times overlap if one starts before the other ends. 11:00–14:00 and 14:00–16:00 do not overlap. |
| IDs | Stable text IDs, for example `TX-JP-01`, `SC-2`, `FL-401`, `HTL-TYO-004`, `REQ-0001`, `RIDE-0001`. Use them as keys. |

---

## 6. Data FAQ

**Why are there flights to India in `flights.json`?** The file is shared with other problems. Use only flights that arrive at `NRT`, `HND`, `KIX`, `DXB`, or `AUH`.

**What if the flight lands at an airport that does not serve the hotel's city (for example `NRT` and a hotel in Osaka)?** The request breaks R1. Refuse it with a clear message.

**Is there a route for every flight and hotel pair?** There is a route for every hotel area from every airport that serves its city. If R1 is true, a route exists.

**What if the traveler gives no pickup time?** Use the earliest pickup: landing + 60 minutes.

**Is the price range the price per person?** No. It is the price for the whole ride (one car).

**Do the booked rides belong to a traveler on our platform?** No. They only make a car busy. They have no price and no request.

**Must we use the 3 open requests?** Load them at the start, so suppliers have requests to see. The judges also post new requests.

**Can a large bag go into small-bag space?** No. Check large bags and small bags separately.

**Is the hotel photo (`image`) available?** No. Photos are not in this pack. Ignore the field.

**Are `distance_km`, `rating`, and the flight price used by any rule?** No. They are for display.

**Can we add our own data?** Yes, in your own database. Do not change the files in `data/`.
