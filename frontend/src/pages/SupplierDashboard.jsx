import { useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api.js";
import Errors, { toErrors } from "../components/Errors.jsx";
import { inr, passengersText, priceLabel, statusText, timeOnly, when } from "../format.js";
import usePolling from "../usePolling.js";

export default function SupplierDashboard() {
  const { companyId } = useParams();
  const dash = usePolling(() => api.supplierRequests(companyId), [companyId]);
  const mine = usePolling(() => api.supplierOffers(companyId), [companyId]);

  const reloadAll = () => { dash.reload(); mine.reload(); };

  if (dash.error && !dash.data) return <Errors errors={toErrors(dash.error)} />;
  if (!dash.data) return <p className="muted">Loading…</p>;
  const { company, requests } = dash.data;

  return (
    <>
      <h1>{company.name}</h1>
      <p className="muted small">
        Airports {company.airports.join(", ")} · open {company.service_from}–{company.service_until} ·
        areas: {company.areas.map((a) => a.area).join(", ")}
      </p>

      <h2>Requests you can serve ({requests.length})</h2>
      {requests.length === 0 && <p className="muted">No open requests you can serve right now. Refreshes every 5 seconds.</p>}
      {requests.map((r) => (
        <RequestCard key={r.request_id} req={r} company={company} onAssigned={reloadAll} />
      ))}

      <h2>Your taxis</h2>
      {!mine.data || mine.data.length === 0 ? (
        <p className="muted">You have not assigned any car yet.</p>
      ) : (
        <div className="table-scroll">
          <table>
            <thead><tr><th>Request</th><th>Traveler</th><th>Pickup</th><th>Car</th><th>Price</th><th>Status</th></tr></thead>
            <tbody>
              {mine.data.map((o) => (
                <tr key={o.offer_id}>
                  <td>{o.request_id}</td>
                  <td>{o.traveler_name}<div className="small muted">{o.hotel}</div></td>
                  <td>{when(o.pickup)}</td>
                  <td>{o.vehicle.type} · {o.vehicle.vehicle_id}</td>
                  <td>{inr(o.price_inr)}</td>
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

function RequestCard({ req, company, onAssigned }) {
  const firstOk = req.cars.find((c) => c.ok)?.vehicle_id || "";
  const [vehicleId, setVehicleId] = useState(firstOk);
  const [showCounter, setShowCounter] = useState(false);
  const [counterPrice, setCounterPrice] = useState("");
  const [errors, setErrors] = useState(null);
  const [message, setMessage] = useState(null);
  const [busy, setBusy] = useState(false);

  async function assign(price) {
    setErrors(null);
    setMessage(null);
    setBusy(true);
    try {
      const offer = await api.assignCar(req.request_id, {
        company_id: company.company_id,
        vehicle_id: vehicleId,
        price_inr: price,
      });
      setMessage(`Assigned ${offer.vehicle.vehicle_id} at ${inr(offer.price_inr)}.`);
      setShowCounter(false);
      setCounterPrice("");
      onAssigned();
    } catch (err) {
      setErrors(toErrors(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <h3>{req.traveler_name} · {req.request_id}</h3>
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
              {c.ok ? "fits and is free" : c.problems.map((p) => `${p.rule}: ${p.message}`).join(" ")}
            </option>
          ))}
        </select>
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
      {message && <div className="success">{message}</div>}

      {req.my_offers.length > 0 && (
        <p className="small muted">
          Your offers here: {req.my_offers.map((o) => `${o.vehicle.vehicle_id} ${inr(o.price_inr)} (${statusText(o.status)})`).join(", ")}
        </p>
      )}
    </div>
  );
}
