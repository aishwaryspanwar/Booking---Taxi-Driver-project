import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api.js";
import Errors, { toErrors } from "../components/Errors.jsx";
import { flightDetail, flightLabels, inr, when } from "../format.js";
import Icon from "../components/Icon.jsx";

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

const CAR_TYPES = [["", "Any"], ["HATCHBACK", "Hatchback"], ["SEDAN", "Sedan"], ["SUV", "SUV"], ["BUS", "Bus"]];

// Number field with − / + buttons. Typing works too; the buttons stay within min–max.
function Stepper({ id, label, min, max, value, onChange }) {
  const n = Number(value) || 0;
  const setTo = (v) => onChange({ target: { value: String(Math.min(max, Math.max(min, v))) } });
  return (
    <div>
      <label htmlFor={id}>{label}</label>
      <div className="stepper">
        <button type="button" onClick={() => setTo(n - 1)} disabled={n <= min} aria-label={`Fewer ${label.toLowerCase()}`}>−</button>
        <input id={id} type="number" inputMode="numeric" min={min} max={max} value={value} onChange={onChange} />
        <button type="button" onClick={() => setTo(n + 1)} disabled={n >= max} aria-label={`More ${label.toLowerCase()}`}>+</button>
      </div>
    </div>
  );
}

export default function TravelerHome() {
  const navigate = useNavigate();
  const [flights, setFlights] = useState([]);
  const [hotels, setHotels] = useState([]);
  const [myRequests, setMyRequests] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [range, setRange] = useState(null);
  const [rangeErrors, setRangeErrors] = useState(null);
  const [hotelErrors, setHotelErrors] = useState(null);
  const [hotelsFor, setHotelsFor] = useState(""); // flight id the current hotel list was loaded for
  const [errors, setErrors] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    Promise.all([api.flights(), api.listRequests()]).then(
      ([f, r]) => { setFlights(f); setMyRequests(r); },
      (e) => setErrors(toErrors(e))
    );
  }, []);

  // Hotels depend on the chosen flight: the backend returns only hotels in cities
  // served by the flight's arrival airport. Refetch every time the flight changes.
  useEffect(() => {
    setHotelErrors(null);
    if (!form.flight_id) {
      setHotels([]);
      setHotelsFor("");
      setForm((f) => (f.hotel_id ? { ...f, hotel_id: "" } : f));
      return;
    }
    let cancelled = false; // ignore late answers if the flight changes again
    const flightId = form.flight_id;
    api.hotels(flightId).then(
      (list) => {
        if (cancelled) return;
        setHotels(list);
        setHotelsFor(flightId);
        // Drop the previously chosen hotel if it is not valid for the new flight.
        setForm((f) => (list.some((h) => h.hotel_id === f.hotel_id) ? f : { ...f, hotel_id: "" }));
      },
      (e) => {
        if (cancelled) return;
        setHotels([]);
        setForm((f) => ({ ...f, hotel_id: "" }));
        setHotelErrors(toErrors(e));
      }
    );
    return () => { cancelled = true; };
  }, [form.flight_id]);

  const hotelsLoading = Boolean(form.flight_id) && hotelsFor !== form.flight_id && !hotelErrors;

  // Live price range (R3) and R1 check whenever flight + hotel are both chosen.
  // Waits until the hotel list matches the chosen flight, so a hotel left over
  // from the previous flight never triggers a false R1 error.
  useEffect(() => {
    setRange(null);
    setRangeErrors(null);
    if (!form.flight_id || !form.hotel_id || hotelsFor !== form.flight_id) return;
    api.priceRange(form.flight_id, form.hotel_id).then(setRange, (e) => setRangeErrors(toErrors(e)));
  }, [form.flight_id, form.hotel_id, hotelsFor]);

  const hotelsByCity = useMemo(() => {
    const groups = {};
    hotels.forEach((h) => (groups[h.city] ||= []).push(h));
    return groups;
  }, [hotels]);

  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value });
  const flightLabel = useMemo(() => flightLabels(flights), [flights]);
  const chosenFlight = flights.find((f) => f.flight_id === form.flight_id);
  const chosenHotel = hotels.find((h) => h.hotel_id === form.hotel_id);

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
        <span className="over">Traveller</span>
        <h1>Request a ride</h1>
        <p className="lede">Choose your flight and hotel to see the suggested price range, then post your price.</p>
      </div>
      <form className="card req-form" onSubmit={submit} noValidate>
        <fieldset>
          <legend>Trip</legend>
          <div className="form-grid trip">
            <div>
              <label htmlFor="name" className="with-icon"><Icon name="user" size={13} />Your name</label>
              <input id="name" value={form.traveler_name} onChange={set("traveler_name")}
                placeholder="Menon family" autoComplete="name" />
            </div>
            <div>
              <label htmlFor="flight" className="with-icon"><Icon name="plane" size={13} />Arrival flight</label>
              <select id="flight" value={form.flight_id} onChange={set("flight_id")}>
                <option value="">Choose a flight…</option>
                {flights.map((f) => (
                  <option key={f.flight_id} value={f.flight_id}>
                    {flightLabel(f)}
                  </option>
                ))}
              </select>
              {chosenFlight && <p className="hint">{chosenFlight.airline} · {flightDetail(chosenFlight)}</p>}
            </div>
            <div>
              <label htmlFor="hotel" className="with-icon"><Icon name="hotel" size={13} />Hotel</label>
              <select id="hotel" value={form.hotel_id} onChange={set("hotel_id")}
                disabled={!form.flight_id || hotelsLoading}>
                <option value="">
                  {!form.flight_id ? "Choose a flight first…"
                    : hotelsLoading ? "Loading hotels…"
                    : hotels.length === 0 ? "No hotels for this destination"
                    : "Choose a hotel…"}
                </option>
                {Object.entries(hotelsByCity).map(([city, list]) => (
                  <optgroup key={city} label={city}>
                    {list.map((h) => (
                      <option key={h.hotel_id} value={h.hotel_id}>
                        {h.name}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
              {chosenHotel && <p className="hint">{chosenHotel.area}, {chosenHotel.city}</p>}
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
          <Errors errors={hotelErrors} />
          <Errors errors={rangeErrors} />
        </fieldset>

        <fieldset>
          <legend>Travellers and luggage</legend>
          <div className="form-grid people">
            <Stepper id="adults" label="Adults" min={1} max={9} value={form.adults} onChange={set("adults")} />
            <Stepper id="large" label="Large bags" min={0} max={6} value={form.large_bags} onChange={set("large_bags")} />
            <Stepper id="small" label="Small bags" min={0} max={6} value={form.small_bags} onChange={set("small_bags")} />
            <div>
              <label htmlFor="kids">Children's ages</label>
              <input id="kids" value={form.child_ages} onChange={set("child_ages")}
                placeholder="e.g. 6, 9" aria-describedby="kids-hint" />
              <p id="kids-hint" className="hint">Comma separated. Leave empty if none.</p>
            </div>
          </div>
        </fieldset>

        <fieldset>
          <legend>Pickup and price</legend>
          <div className="form-grid">
            <div>
              <label htmlFor="pickup" className="with-icon"><Icon name="clock" size={13} />Pickup time <span className="opt">(optional, local)</span></label>
              <input id="pickup" type="datetime-local" value={form.pickup} onChange={set("pickup")}
                min={range?.earliest_pickup || undefined} aria-describedby="pickup-hint" />
              <p id="pickup-hint" className="hint">
                {range ? (
                  <>Earliest {when(range.earliest_pickup)}.{" "}
                    <button type="button" className="btn-link"
                      onClick={() => setForm({ ...form, pickup: range.earliest_pickup })}>Use earliest</button>
                  </>
                ) : "Leave empty for the earliest pickup after landing."}
              </p>
            </div>
            <div>
              <span className="label with-icon" id="type-label"><Icon name="car" size={13} />Car type</span>
              <div className="chips" role="radiogroup" aria-labelledby="type-label">
                {CAR_TYPES.map(([value, text]) => (
                  <label key={value} className={`chip${form.car_type === value ? " on" : ""}`}>
                    <input type="radio" name="car_type" value={value}
                      checked={form.car_type === value} onChange={set("car_type")} />
                    {text}
                  </label>
                ))}
              </div>
            </div>
            <div className="wide">
              <label htmlFor="price">Your price</label>
              <div className="prefix-input">
                  <span aria-hidden="true">₹</span>
                  <input id="price" type="number" inputMode="numeric" min={range?.price_min_inr}
                    max={range?.price_max_inr} step="50" value={form.price_inr} onChange={set("price_inr")}
                    placeholder={range ? `${range.price_min_inr} – ${range.price_max_inr}` : "Amount in INR"}
                    aria-describedby="price-hint" />
              </div>
              <p id="price-hint" className="hint">
                {range ? `Must be within ${inr(range.price_min_inr)} – ${inr(range.price_max_inr)}.`
                  : "Choose a flight and hotel to see the suggested range."}
              </p>
            </div>
          </div>
        </fieldset>

        <Errors errors={errors} />
        <div className="form-actions">
          <button className="primary lg" type="submit" disabled={submitting}>
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
              <tr><th>Request</th><th>Traveller</th><th>Route</th><th>Pickup</th><th>Price</th><th>Taxis</th><th>Status</th><th></th></tr>
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
