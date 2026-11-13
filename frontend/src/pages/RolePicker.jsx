import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import Errors, { toErrors } from "../components/Errors.jsx";

export default function RolePicker() {
  const navigate = useNavigate();
  const [companies, setCompanies] = useState([]);
  const [errors, setErrors] = useState(null);
  const [companyId, setCompanyId] = useState("");

  useEffect(() => {
    api.companies().then(setCompanies, (e) => setErrors(toErrors(e)));
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
            <button className="primary lg" onClick={() => navigate("/traveler")}>Request a ride</button>
          </div>
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
