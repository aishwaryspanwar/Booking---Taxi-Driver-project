import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import Errors, { toErrors } from "../components/Errors.jsx";

export default function RolePicker() {
  const navigate = useNavigate();
  const [companies, setCompanies] = useState([]);
  const [errors, setErrors] = useState(null);
  const [companyId, setCompanyId] = useState("");
  const [travelers, setTravelers] = useState([]);   // requests still open or booked
  const [requestId, setRequestId] = useState("");

  useEffect(() => {
    api.companies().then(setCompanies, (e) => setErrors(toErrors(e)));
    api.listRequests().then(
      (list) => setTravelers(list.filter((r) => r.status === "OPEN" || r.status === "BOOKED")),
      (e) => setErrors(toErrors(e))
    );
  }, []);

  return (
    <>
      <section className="hero">
        <span className="over">Airport taxi · Ride offers</span>
        <h1 className="display">Your ride from the airport,<br />at the price you choose.</h1>
        <p className="lede">
          Travelers post a ride with their price. Taxi suppliers answer with a car and a price.
          No login needed: pick who you are, and switch at any time.
        </p>
      </section>
      <Errors errors={errors} />

      <div className="roles">
        <div className="card">
          <span className="over">Traveler</span>
          <h3>I need a ride to my hotel</h3>
          <p className="grow">
            Pick your flight and hotel, see the suggested price range, post your price, then book the taxi you like.
          </p>
          <div>
            <button className="primary lg" onClick={() => navigate("/traveler")}>Start as a new traveler</button>
          </div>
          {travelers.length > 0 && (
            <>
              <label htmlFor="traveler" style={{ marginTop: 20 }}>Or continue an existing request</label>
              <div className="row">
                <select id="traveler" style={{ flex: 1, minWidth: 240 }} value={requestId}
                  onChange={(e) => setRequestId(e.target.value)}>
                  <option value="">Select your traveler ID…</option>
                  {travelers.map((r) => (
                    <option key={r.request_id} value={r.request_id}>
                      {r.request_id} · {r.traveler_name} · {r.hotel.city} ·{" "}
                      {r.status === "BOOKED" ? `Booked ${r.booking_number ?? ""}`.trim() : `Open, ${r.offer_count} taxi offers`}
                    </option>
                  ))}
                </select>
                <button className="primary" disabled={!requestId}
                  onClick={() => navigate(`/traveler/requests/${requestId}`)}>
                  Continue
                </button>
              </div>
            </>
          )}
        </div>

        <div className="card">
          <span className="over">Taxi supplier</span>
          <h3>I drive airport rides</h3>
          <label htmlFor="supplier">Choose your company</label>
          <div className="row">
          <select id="supplier" style={{ flex: 1, minWidth: 240 }} value={companyId}
            onChange={(e) => setCompanyId(e.target.value)}>
            <option value="">Select a taxi supplier…</option>
            {companies.map((c) => (
              <option key={c.company_id} value={c.company_id}>
                {c.name} · {c.airports.join(", ")} · {c.vehicles.length} cars · open {c.service_from}–{c.service_until}
              </option>
            ))}
          </select>
          <button className="primary" disabled={!companyId} onClick={() => navigate(`/supplier/${companyId}`)}>
            Continue
          </button>
          </div>
        </div>
      </div>
    </>
  );
}
