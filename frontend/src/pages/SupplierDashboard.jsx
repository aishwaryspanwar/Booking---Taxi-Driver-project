import { useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api.js";
import Errors, { toErrors } from "../components/Errors.jsx";
import { endsAt, inr, passengersText, priceLabel, statusText, timeOnly, when } from "../format.js";
import usePolling from "../usePolling.js";

export default function SupplierDashboard() {
  const { companyId } = useParams();
  const dash = usePolling(() => api.supplierRequests(companyId), [companyId]);
  const mine = usePolling(() => api.supplierOffers(companyId), [companyId]);

  const [notice, setNotice] = useState(null);   // "Assigned SC-3 at ₹12,000 ..." after an offer

  // After an offer: show the confirmation, then reload both lists. The request stays in
  // "Requests you can serve" while another of your cars fits and is free (G1).
  const afterAssign = (message) => { setNotice(message); dash.reload(); mine.reload(); };

  if (dash.error && !dash.data) return <Errors errors={toErrors(dash.error)} />;
  if (!dash.data) return <p className="muted">Loading…</p>;
  const { company, requests } = dash.data;

  return (
    <>
      <div className="page-head">
        <span className="over">Supplier dashboard</span>
        <h1>{company.name}</h1>
      </div>
      <p className="muted small" style={{ marginTop: -16, marginBottom: 8 }}>
        Airports {company.airports.join(", ")} · open {company.service_from}–{company.service_until} ·
        areas: {company.areas.map((a) => a.area).join(", ")}
      </p>

      {notice && <div className="success">{notice}</div>}

      <h2>Requests you can serve ({requests.length})</h2>
      {requests.length === 0 && (
        <p className="muted">
          No new requests you can serve right now. Requests where all your fitting cars are already
          offered are in “Your taxis”.
          Refreshes every 5 seconds.
        </p>
      )}
      {requests.map((r) => (
        <RequestCard key={r.request_id} req={r} company={company} onAssigned={afterAssign} />
      ))}

      <ChangeRequests companyId={company.company_id} />

      <h2>Your taxis</h2>
      {!mine.data || mine.data.length === 0 ? (
        <p className="muted">You have not assigned any car yet.</p>
      ) : (
        <div className="table-scroll">
          <table>
            <thead><tr><th>Request</th><th>Traveler</th><th>Pickup</th><th>Car</th><th>Price</th><th>Ends</th><th>Status</th></tr></thead>
            <tbody>
              {mine.data.map((o) => (
                <tr key={o.offer_id}>
                  <td>{o.request_id}</td>
                  <td>{o.traveler_name}<div className="small muted">{o.hotel}</div></td>
                  <td>{when(o.pickup)}</td>
                  <td>{o.vehicle.type} · {o.vehicle.vehicle_id}</td>
                  <td>{inr(o.price_inr)}</td>
                  <td>{o.expires_at ? endsAt(o.expires_at) : <span className="muted">never</span>}</td>
                  <td><span className={`tag ${o.status.toLowerCase()}`}>{statusText(o.status)}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

// M7: change requests for this supplier's bookings. Accept works only if the
// new pickup follows R2 and the same car is free (R9); the backend decides.
function ChangeRequests({ companyId }) {
  const { data: changes, reload } = usePolling(() => api.supplierChanges(companyId), [companyId]);
  const [errors, setErrors] = useState(null);
  const [busyId, setBusyId] = useState(null);

  async function decide(change, accept) {
    setErrors(null);
    setBusyId(change.change_id);
    try {
      if (accept) await api.acceptChange(change.change_id, companyId);
      else await api.rejectChange(change.change_id, companyId);
    } catch (err) {
      setErrors(toErrors(err));   // e.g. the platform refused: car busy at the new time
    } finally {
      setBusyId(null);
      reload();
    }
  }

  if (!changes || changes.length === 0) return null;
  const waiting = changes.filter((c) => c.status === "WAITING").length;

  return (
    <>
      <h2>Change requests {waiting > 0 && <span className="tag waiting">{waiting} waiting</span>}</h2>
      <Errors errors={errors} />
      <div className="table-scroll">
        <table>
          <thead>
            <tr><th>Booking</th><th>Traveler</th><th>From</th><th>To</th><th>Status</th><th></th></tr>
          </thead>
          <tbody>
            {changes.map((c) => (
              <tr key={c.change_id}>
                <td>{c.booking_number}<div className="small muted">car {c.vehicle_id}</div></td>
                <td>{c.traveler_name}<div className="small muted">{c.hotel}</div></td>
                <td>{c.old_flight.flight_number}<div className="small muted">pickup {when(c.old_pickup)}</div></td>
                <td>{c.new_flight.flight_number}<div className="small muted">pickup {when(c.new_pickup)}</div></td>
                <td>
                  <span className={`tag ${c.status.toLowerCase()}`}>{statusText(c.status)}</span>
                  {c.reason && <div className="small muted" style={{ maxWidth: 260 }}>{c.reason}</div>}
                </td>
                <td>
                  {c.status === "WAITING" && (
                    <>
                      <div className="row">
                        <button className="primary" disabled={busyId === c.change_id} onClick={() => decide(c, true)}>Accept</button>
                        <button disabled={busyId === c.change_id} onClick={() => decide(c, false)}>Reject</button>
                      </div>
                      <div className="small" style={{ marginTop: 6, maxWidth: 280 }}>
                        {c.problems.length === 0
                          ? <span className="diff-same">Car is free at the new time.</span>
                          : <span style={{ color: "var(--danger)" }}>{c.problems.map((p) => `${p.rule}: ${p.message}`).join(" ")}</span>}
                      </div>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

// Text after each car in the dropdown: "fits and is free", or the rules it breaks.
function carStatus(car) {
  if (car.ok) return "fits and is free";
  return car.problems.map((p) => `${p.rule}: ${p.message}`).join(" ");
}

function RequestCard({ req, company, onAssigned }) {
  const firstOk = req.cars.find((c) => c.ok)?.vehicle_id || "";
  const [chosenId, setVehicleId] = useState(firstOk);
  // G1: after a car is assigned it is no longer "ok"; move to the next good car
  const vehicleId = req.cars.some((c) => c.vehicle_id === chosenId && c.ok) ? chosenId : firstOk;
  const [expiresAt, setExpiresAt] = useState("");   // G4: "" = the offer never ends
  const [showCounter, setShowCounter] = useState(false);
  const [counterPrice, setCounterPrice] = useState("");
  const [errors, setErrors] = useState(null);
  const [busy, setBusy] = useState(false);

  async function assign(price) {
    setErrors(null);
    setBusy(true);
    try {
      const offer = await api.assignCar(req.request_id, {
        company_id: company.company_id,
        vehicle_id: vehicleId,
        price_inr: price,
        // datetime-local is the supplier's local time; send it as UTC
        expires_at: expiresAt ? new Date(expiresAt).toISOString() : null,
      });
      onAssigned(`Assigned ${offer.vehicle.vehicle_id} at ${inr(offer.price_inr)} to ${req.request_id}` +
        (offer.expires_at ? `, ends ${endsAt(offer.expires_at)}` : "") +
        ". It is in “Your taxis”. You can assign more cars to this request while one is free.");
    } catch (err) {
      setErrors(toErrors(err));   // e.g. R6: car busy, R3: price out of range
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <h3>
        {req.traveler_name} · {req.request_id}
        {req.your_offer_count > 0 && (
          <span className="tag open" style={{ marginLeft: 8 }}>
            {req.your_offer_count} car{req.your_offer_count > 1 ? "s" : ""} offered
          </span>
        )}
      </h3>
      <div className="grid small">
        <div><label>Flight</label>{req.flight.flight_number} ({req.flight.from}→{req.flight.to}), lands {when(req.flight.arrival_local)}</div>
        <div><label>Hotel</label>{req.hotel.name}, {req.hotel.area}, {req.hotel.city}</div>
        <div><label>Pickup → car busy</label>{when(req.pickup)} → {timeOnly(req.busy_end)}</div>
        <div><label>Travelers</label>{passengersText(req)} ({req.passengers} seats)</div>
        <div><label>Bags</label>{req.large_bags} large, {req.small_bags} small</div>
        <div><label>Car type</label>{req.car_type || "Any"}</div>
        <div><label>Traveler's price</label><strong>{inr(req.price_inr)}</strong></div>
        <div><label>Allowed range</label>{inr(req.route.price_min_inr)} – {inr(req.route.price_max_inr)}</div>
      </div>

      <div style={{ marginTop: 12 }}>
        <label htmlFor={`car-${req.request_id}`}>Car</label>
        <select id={`car-${req.request_id}`} value={vehicleId} onChange={(e) => setVehicleId(e.target.value)}>
          {req.cars.map((c) => (
            <option key={c.vehicle_id} value={c.vehicle_id}>
              {c.vehicle_id} · {c.type} · {c.seats} seats · {c.large_bags}L/{c.small_bags}S bags —{" "}
              {carStatus(c)}
            </option>
          ))}
        </select>
        {req.car_type && (
          <div className="small muted">The traveler asked for a {req.car_type}; only that type can be assigned.</div>
        )}
      </div>

      <div style={{ marginTop: 12, maxWidth: 280 }}>
        <label htmlFor={`exp-${req.request_id}`}>Offer ends (optional)</label>
        <input id={`exp-${req.request_id}`} type="datetime-local" value={expiresAt}
          onChange={(e) => setExpiresAt(e.target.value)} />
        <div className="small muted">Your time zone. After this time the traveler cannot book this taxi.</div>
      </div>

      <div className="row" style={{ marginTop: 12 }}>
        <button className="primary" disabled={busy || !vehicleId} onClick={() => assign(req.price_inr)}>
          Accept at {inr(req.price_inr)}
        </button>
        <button disabled={busy} onClick={() => setShowCounter(!showCounter)}>Offer a different price</button>
      </div>

      {showCounter && (
        <div className="row" style={{ marginTop: 12 }}>
          <input type="number" style={{ maxWidth: 200 }} value={counterPrice} placeholder="Price in ₹"
            onChange={(e) => setCounterPrice(e.target.value)} />
          <button className="primary" disabled={busy || counterPrice === ""} onClick={() => assign(counterPrice)}>
            Send offer
          </button>
          {counterPrice !== "" && !isNaN(Number(counterPrice)) && (
            <span className="small muted">{priceLabel(Number(counterPrice), req.price_inr)} vs traveler</span>
          )}
        </div>
      )}

      <Errors errors={errors} />
    </div>
  );
}
