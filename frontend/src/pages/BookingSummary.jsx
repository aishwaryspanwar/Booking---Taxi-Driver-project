import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api.js";
import Errors, { toErrors } from "../components/Errors.jsx";
import { inr, passengersText, statusText, timeOnly, when } from "../format.js";
import usePolling from "../usePolling.js";

// M5: the booking number opens a summary. M7: send a change request and see the result.
export default function BookingSummary() {
  const { number } = useParams();

  return (
    <>
      <div className="page-head">
        <span className="over">My booking</span>
        <h1>{number ? `Booking ${number}` : "Bookings"}</h1>
      </div>
      <Lookup initial={number || ""} />
      {number ? <Summary key={number} number={number} /> : <AllBookings />}
    </>
  );
}

// Every booking, newest first. Click a row to open its summary.
function AllBookings() {
  const navigate = useNavigate();
  const { data: bookings, error } = usePolling(() => api.listBookings(), []);

  if (error && !bookings) return <Errors errors={toErrors(error)} />;
  if (!bookings) return <p className="muted">Loading…</p>;

  return (
    <>
      <h2>All bookings ({bookings.length})</h2>
      {bookings.length === 0 ? (
        <p className="muted">
          No bookings yet. A booking appears here after the traveler clicks <strong>Book</strong> on a taxi.
        </p>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr><th>Booking</th><th>Traveler</th><th>Ride</th><th>Pickup</th><th>Supplier · car</th><th>Price</th><th>Change</th></tr>
            </thead>
            <tbody>
              {bookings.map((b) => {
                const latest = b.changes[0];   // newest first
                return (
                  <tr key={b.booking_number} style={{ cursor: "pointer" }}
                    onClick={() => navigate(`/bookings/${b.booking_number}`)}>
                    <td><strong>{b.booking_number}</strong></td>
                    <td>{b.request.traveler_name}</td>
                    <td>{b.request.flight.to} → {b.request.hotel.name}</td>
                    <td>{when(b.request.pickup)}</td>
                    <td>{b.supplier.name}<div className="small muted">{b.vehicle.type} · {b.vehicle.vehicle_id}</div></td>
                    <td>{inr(b.price_inr)}</td>
                    <td>{latest ? <span className={`tag ${latest.status.toLowerCase()}`}>{statusText(latest.status)}</span> : "–"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function Lookup({ initial }) {
  const navigate = useNavigate();
  const [value, setValue] = useState(initial);

  function open(e) {
    e.preventDefault();
    if (value.trim()) navigate(`/bookings/${value.trim()}`);
  }

  return (
    <form className="card" onSubmit={open}>
      <label htmlFor="booking-number">Booking number</label>
      <div className="row">
        <input id="booking-number" style={{ flex: 1, minWidth: 220 }} value={value} inputMode="numeric"
          placeholder="10-digit number, e.g. 8820122160" onChange={(e) => setValue(e.target.value)} />
        <button className="primary" type="submit" disabled={!value.trim()}>Open booking</button>
      </div>
    </form>
  );
}

function Summary({ number }) {
  const { data: booking, error, reload } = usePolling(() => api.getBooking(number), [number]);

  // Opened from a "Change flight" button (?change=1): jump to the change form once
  const [searchParams] = useSearchParams();
  const wantsChange = searchParams.get("change") === "1";
  const jumped = useRef(false);
  useEffect(() => {
    if (!booking || !wantsChange || jumped.current) return;
    jumped.current = true;
    document.getElementById("change-request")?.scrollIntoView({ behavior: "smooth", block: "start" });
    document.getElementById("new-flight")?.focus({ preventScroll: true });
  }, [booking, wantsChange]);

  if (error && !booking) {
    if (error.status === 404) {
      return <div className="errors"><strong>Booking not found.</strong> No booking has the number {number}. Check the 10 digits.</div>;
    }
    return <Errors errors={toErrors(error)} />;
  }
  if (!booking) return <p className="muted">Loading…</p>;

  const r = booking.request;
  return (
    <>
      <div className="card">
        <span className="over">Confirmed ride</span>
        <div className="booking-number">{booking.booking_number}</div>
        <div className="grid">
          <div><label>Flight</label>{r.flight.flight_number} ({r.flight.from}→{r.flight.to}), lands {when(r.flight.arrival_local)}</div>
          <div><label>Hotel</label>{r.hotel.name}, {r.hotel.area}, {r.hotel.city}</div>
          <div><label>Pickup</label>{when(r.pickup)} at {r.flight.to}</div>
          <div><label>Travelers</label>{passengersText(r)}</div>
          <div><label>Bags</label>{r.large_bags} large, {r.small_bags} small</div>
          <div><label>Supplier</label>{booking.supplier.name} <span className="small muted">· rating {booking.supplier.rating}</span></div>
          <div><label>Car</label>{booking.vehicle.type} · {booking.vehicle.vehicle_id} <span className="small muted">({booking.vehicle.seats} seats)</span></div>
          <div><label>Price</label><strong>{inr(booking.price_inr)}</strong></div>
        </div>
        <p className="small muted" style={{ marginTop: 16 }}>
          The car is reserved {when(booking.busy_start)} – {timeOnly(booking.busy_end)} (to the hotel and back).
        </p>
      </div>

      <h2 id="change-request">Change flight or pickup</h2>
      {booking.has_waiting_change ? (
        <div className="range">Your change request is waiting for {booking.supplier.name}. This page refreshes every 5 seconds.</div>
      ) : (
        <ChangeForm booking={booking} onSent={reload} />
      )}

      {booking.changes.length > 0 && <ChangeHistory changes={booking.changes} />}
    </>
  );
}

function ChangeForm({ booking, onSent }) {
  const airport = booking.request.flight.to;
  const [flights, setFlights] = useState([]);
  const [flightId, setFlightId] = useState("");
  const [pickup, setPickup] = useState("");
  const [errors, setErrors] = useState(null);
  const [busy, setBusy] = useState(false);

  // Only flights that land at the airport of this booking can replace it.
  useEffect(() => {
    api.flights().then((all) => setFlights(all.filter((f) => f.to === airport)), (e) => setErrors(toErrors(e)));
  }, [airport]);

  async function send(e) {
    e.preventDefault();
    setErrors(null);
    setBusy(true);
    try {
      await api.requestChange(booking.booking_number, { flight_id: flightId || null, pickup: pickup || null });
      setFlightId("");
      setPickup("");
      onSent();
    } catch (err) {
      setErrors(toErrors(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card" onSubmit={send} noValidate>
      <p className="muted small" style={{ marginBottom: 16 }}>
        Flight changed? Choose the new flight, a new pickup time, or both. With no pickup time we use 60 minutes
        after the new flight lands. {booking.supplier.name} accepts or rejects it.
      </p>
      <div className="grid">
        <div>
          <label htmlFor="new-flight">New flight (optional)</label>
          <select id="new-flight" value={flightId} onChange={(e) => setFlightId(e.target.value)}>
            <option value="">Keep {booking.request.flight.flight_number} ({booking.request.flight.flight_id})</option>
            {flights.map((f) => (
              <option key={f.flight_id} value={f.flight_id}>
                {f.flight_number} · {f.from}→{f.to} · lands {when(f.arrival_local)} ({f.flight_id})
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="new-pickup">New pickup time (optional, local)</label>
          <input id="new-pickup" type="datetime-local" value={pickup} onChange={(e) => setPickup(e.target.value)} />
        </div>
      </div>
      <Errors errors={errors} />
      <div className="row" style={{ marginTop: 16 }}>
        <button className="primary" type="submit" disabled={busy || (!flightId && !pickup)}>
          {busy ? "Sending…" : "Send change request"}
        </button>
      </div>
    </form>
  );
}

function ChangeHistory({ changes }) {
  return (
    <div className="table-scroll" style={{ marginTop: 20 }}>
      <table>
        <thead>
          <tr><th>Change</th><th>From</th><th>To</th><th>Status</th><th>Result</th></tr>
        </thead>
        <tbody>
          {changes.map((c) => (
            <tr key={c.change_id}>
              <td>#{c.change_id}</td>
              <td>{c.old_flight.flight_number}<div className="small muted">pickup {when(c.old_pickup)}</div></td>
              <td>{c.new_flight.flight_number}<div className="small muted">pickup {when(c.new_pickup)}</div></td>
              <td><span className={`tag ${c.status.toLowerCase()}`}>{statusText(c.status)}</span></td>
              <td className="small">
                {c.status === "ACCEPTED" && "Your booking now uses the new flight and pickup."}
                {c.status === "REJECTED" && `${c.reason} Your booking did not change.`}
                {c.status === "WAITING" && "Waiting for the supplier."}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
