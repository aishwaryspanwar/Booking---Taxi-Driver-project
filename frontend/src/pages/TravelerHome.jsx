import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api.js";
import Errors, { toErrors } from "../components/Errors.jsx";
import { inr, when } from "../format.js";

const EMPTY = {
  traveler_name: "",
  flight_id: "",
  hotel_id: "",
  adults: "1",
  child_ages: "",
  large_bags: "0",
  small_bags: "0",
  pickup: "",
  car_type: "",
  price_inr: "",
};

export default function TravelerHome() {
  const navigate = useNavigate();
  const [flights, setFlights] = useState([]);
  const [hotels, setHotels] = useState([]);
  const [myRequests, setMyRequests] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [range, setRange] = useState(null);
  const [rangeErrors, setRangeErrors] = useState(null);
  const [errors, setErrors] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    Promise.all([api.flights(), api.hotels(), api.listRequests()]).then(
      ([f, h, r]) => { setFlights(f); setHotels(h); setMyRequests(r); },
      (e) => setErrors(toErrors(e))
    );
  }, []);

  // Live price range (R3) and R1 check whenever flight + hotel are both chosen.
  useEffect(() => {
    setRange(null);
    setRangeErrors(null);
    if (!form.flight_id || !form.hotel_id) return;
    api.priceRange(form.flight_id, form.hotel_id).then(setRange, (e) => setRangeErrors(toErrors(e)));
  }, [form.flight_id, form.hotel_id]);

  const hotelsByCity = useMemo(() => {
    const groups = {};
    hotels.forEach((h) => (groups[h.city] ||= []).push(h));
    return groups;
  }, [hotels]);

  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setErrors(null);
    // Send raw values; the backend validates every rule and explains what is wrong.
    const body = {
      ...form,
      child_ages: form.child_ages.split(",").map((s) => s.trim()).filter(Boolean),
      pickup: form.pickup || null,
      car_type: form.car_type || null,
    };
    setSubmitting(true);
    try {
      const created = await api.createRequest(body);
      navigate(`/traveler/requests/${created.request_id}`);
    } catch (err) {
      setErrors(toErrors(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <div className="page-head">
        <span className="over">Traveler</span>
        <h1>Request a ride</h1>
        <p className="lede">Choose your flight and hotel to see the suggested price range, then post your price.</p>
      </div>
      <form className="card" onSubmit={submit} noValidate>
        <div className="grid">
          <div>
            <label htmlFor="name">Your name</label>
            <input id="name" value={form.traveler_name} onChange={set("traveler_name")} placeholder="Menon family" />
          </div>
          <div>
            <label htmlFor="flight">Arrival flight</label>
            <select id="flight" value={form.flight_id} onChange={set("flight_id")}>
              <option value="">Choose a flight…</option>
              {flights.map((f) => (
                <option key={f.flight_id} value={f.flight_id}>
                  {f.flight_number} · {f.from}→{f.to} · lands {when(f.arrival_local)} ({f.flight_id})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="hotel">Hotel</label>
            <select id="hotel" value={form.hotel_id} onChange={set("hotel_id")}>
              <option value="">Choose a hotel…</option>
              {Object.entries(hotelsByCity).map(([city, list]) => (
                <optgroup key={city} label={city}>
                  {list.map((h) => (
                    <option key={h.hotel_id} value={h.hotel_id}>
                      {h.name} · {h.area} ({h.hotel_id})
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </div>
        </div>

        {range && (
          <div className="range">
            Suggested price for {range.route.airport} → {range.route.city} / {range.route.area}:{" "}
            <strong>{inr(range.price_min_inr)} – {inr(range.price_max_inr)}</strong>
            <div className="small">
              {range.route.distance_km} km, about {range.route.drive_minutes} min. Lands {when(range.arrival_local)};
              earliest pickup {when(range.earliest_pickup)}.
            </div>
          </div>
        )}
        <Errors errors={rangeErrors} />

        <div className="grid">
          <div>
            <label htmlFor="adults">Adults</label>
            <input id="adults" type="number" min="1" value={form.adults} onChange={set("adults")} />
          </div>
          <div>
            <label htmlFor="kids">Children's ages (comma separated)</label>
            <input id="kids" value={form.child_ages} onChange={set("child_ages")} placeholder="e.g. 6, 9" />
          </div>
          <div>
            <label htmlFor="large">Large bags</label>
            <input id="large" type="number" min="0" value={form.large_bags} onChange={set("large_bags")} />
          </div>
          <div>
            <label htmlFor="small">Small bags</label>
            <input id="small" type="number" min="0" value={form.small_bags} onChange={set("small_bags")} />
          </div>
          <div>
            <label htmlFor="pickup">Pickup time (optional, local)</label>
            <input id="pickup" type="datetime-local" value={form.pickup} onChange={set("pickup")} />
          </div>
          <div>
            <label htmlFor="type">Car type</label>
            <select id="type" value={form.car_type} onChange={set("car_type")}>
              <option value="">Any</option>
              <option>HATCHBACK</option>
              <option>SEDAN</option>
              <option>SUV</option>
              <option>BUS</option>
            </select>
          </div>
          <div>
            <label htmlFor="price">Your price (₹)</label>
            <input id="price" type="number" value={form.price_inr} onChange={set("price_inr")}
              placeholder={range ? `${range.price_min_inr} – ${range.price_max_inr}` : ""} />
          </div>
        </div>

        <Errors errors={errors} />
        <div className="row" style={{ marginTop: 16 }}>
          <button className="primary" type="submit" disabled={submitting}>
            {submitting ? "Posting…" : "Post request"}
          </button>
        </div>
      </form>

      <h2>Requests</h2>
      {myRequests.length === 0 ? (
        <p className="muted">No requests yet.</p>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr><th>Request</th><th>Traveler</th><th>Route</th><th>Pickup</th><th>Price</th><th>Taxis</th><th>Status</th><th></th></tr>
            </thead>
            <tbody>
              {myRequests.map((r) => (
                <tr key={r.request_id}>
                  <td><Link to={`/traveler/requests/${r.request_id}`}>{r.request_id}</Link></td>
                  <td>{r.traveler_name}</td>
                  <td>{r.flight.to} → {r.hotel.name}</td>
                  <td>{when(r.pickup)}</td>
                  <td>{inr(r.price_inr)}</td>
                  <td>{r.offer_count}</td>
                  <td><span className={`tag ${r.status.toLowerCase()}`}>{r.status.toLowerCase()}</span></td>
                  <td>
                    {/* M7: a booked ride can ask for a new flight or pickup */}
                    {r.booking_number && (
                      <button onClick={() => navigate(`/bookings/${r.booking_number}?change=1`)}>
                        Change flight
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
