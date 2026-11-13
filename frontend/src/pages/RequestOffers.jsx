import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api.js";
import Errors, { toErrors } from "../components/Errors.jsx";
import { CAR_TYPES, endsAt, inr, passengersText, priceLabel, statusText, timeOnly, when } from "../format.js";
import usePolling from "../usePolling.js";

export default function RequestOffers() {
  const { requestId } = useParams();
  const navigate = useNavigate();
  const { data: req, error, setData } = usePolling(() => api.getRequest(requestId), [requestId]);
  const [actionErrors, setActionErrors] = useState(null);
  const [busy, setBusy] = useState(false);
  // G5: sort by price and filter by car type (done in the browser; the list is small)
  const [sort, setSort] = useState("");          // "" (offer order) | "asc" | "desc"
  const [typeFilter, setTypeFilter] = useState("");  // "" = all types

  async function act(fn) {
    setActionErrors(null);
    setBusy(true);
    try {
      setData(await fn());
    } catch (err) {
      setActionErrors(toErrors(err));
    } finally {
      setBusy(false);
    }
  }

  if (error && !req) return <Errors errors={toErrors(error)} />;
  if (!req) return <p className="muted">Loading…</p>;

  const booked = req.offers.find((o) => o.status === "BOOKED");

  const shownOffers = req.offers.filter((o) => !typeFilter || o.vehicle.type === typeFilter);
  if (sort) shownOffers.sort((a, b) => (sort === "asc" ? a.price_inr - b.price_inr : b.price_inr - a.price_inr));

  return (
    <>
      <div className="page-head">
        <Link to="/traveler" className="btn-link">← All requests</Link>
        <span className="over">Ride request · {req.request_id}</span>
        <h1>{req.traveler_name}</h1>
      </div>

      <div className="card grid">
        <div><label>Flight</label>{req.flight.flight_number} ({req.flight.from}→{req.flight.to}), lands {when(req.flight.arrival_local)}</div>
        <div><label>Hotel</label>{req.hotel.name}, {req.hotel.area}, {req.hotel.city}</div>
        <div><label>Pickup</label>{when(req.pickup)}</div>
        <div><label>Travellers</label>{passengersText(req)}</div>
        <div><label>Bags</label>{req.large_bags} large, {req.small_bags} small</div>
        <div><label>Car type</label>{req.car_type || "Any"}</div>
        <div><label>Your price</label><strong>{inr(req.price_inr)}</strong></div>
        <div><label>Suggested range</label>{inr(req.route.price_min_inr)} – {inr(req.route.price_max_inr)}</div>
      </div>

      {req.booking && booked && (
        <div className="success">
          <div>Booked. Your booking number:</div>
          <div className="booking-number">{req.booking.booking_number}</div>
          <div>
            {booked.company_name} · {booked.vehicle.type} {booked.vehicle.vehicle_id} · {inr(booked.price_inr)} ·
            pickup {when(req.pickup)} at {req.flight.to} → {req.hotel.name}
          </div>
          <div className="row" style={{ marginTop: 12 }}>
            <button className="primary" onClick={() => navigate(`/bookings/${req.booking.booking_number}`)}>
              Open booking summary
            </button>
            {/* M7: flight changed? ask the supplier for a new flight or pickup */}
            <button onClick={() => navigate(`/bookings/${req.booking.booking_number}?change=1`)}>
              Change flight or pickup
            </button>
          </div>
        </div>
      )}

      {req.no_supplier_reasons.length > 0 && (
        <div className="errors">
          <strong>No supplier can serve this request.</strong>
          <ul>{req.no_supplier_reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
        </div>
      )}

      <h2>Taxis offered</h2>
      <Errors errors={actionErrors} />
      {req.offers.length === 0 ? (
        <p className="muted">
          Waiting for suppliers… this page refreshes every 5 seconds.
          {req.servable_by?.length > 0 && <> Suppliers who can serve you: {req.servable_by.join(", ")}.</>}
        </p>
      ) : (
        <>
        <div className="row" style={{ marginBottom: 12, alignItems: "flex-end" }}>
          <div>
            <label htmlFor="offer-sort">Sort by price</label>
            <select id="offer-sort" value={sort} onChange={(e) => setSort(e.target.value)}>
              <option value="">As offered</option>
              <option value="asc">Price: low to high</option>
              <option value="desc">Price: high to low</option>
            </select>
          </div>
          <div>
            <label htmlFor="offer-type">Car type</label>
            <select id="offer-type" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
              <option value="">All types</option>
              {CAR_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <span className="small muted">Showing {shownOffers.length} of {req.offers.length}</span>
        </div>
        {shownOffers.length === 0 ? (
          <p className="muted">No taxi of type {typeFilter}. Choose another car type.</p>
        ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr><th>Supplier</th><th>Car</th><th>Price</th><th></th><th>Status</th><th></th></tr>
            </thead>
            <tbody>
              {shownOffers.map((o) => {
                const diff = o.price_inr - req.price_inr;
                return (
                  <tr key={o.offer_id}>
                    <td>{o.company_name}<div className="small muted">rating {o.company_rating}</div></td>
                    <td>
                      {o.vehicle.type} · {o.vehicle.vehicle_id}
                      <div className="small muted">
                        {o.vehicle.seats} seats · {o.vehicle.large_bags} large · {o.vehicle.small_bags} small bags
                      </div>
                    </td>
                    <td><strong>{inr(o.price_inr)}</strong></td>
                    <td className={diff === 0 ? "diff-same" : diff > 0 ? "diff-up" : "diff-down"}>
                      {priceLabel(o.price_inr, req.price_inr)}
                    </td>
                    <td>
                      <span className={`tag ${o.status.toLowerCase()}`}>{statusText(o.status)}</span>
                      {o.expires_at && (
                        <div className="small muted">
                          {o.status === "EXPIRED" ? "ended" : "ends"} {endsAt(o.expires_at)}
                        </div>
                      )}
                    </td>
                    <td>
                      {o.status === "OPEN" && req.status === "OPEN" && (
                        <div className="row">
                          <button className="primary" disabled={busy} onClick={() => act(() => api.bookOffer(o.offer_id))}>Book</button>
                          <button disabled={busy} onClick={() => act(() => api.rejectOffer(o.offer_id))}>Reject</button>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        )}
        </>
      )}
      {req.booking && (
        <p className="small muted">
          Car busy {when(req.booking.busy_start)} – {timeOnly(req.booking.busy_end)} (to the hotel and back).
        </p>
      )}
    </>
  );
}
