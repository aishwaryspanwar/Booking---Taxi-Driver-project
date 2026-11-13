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
      <h1>Who are you?</h1>
      <p className="muted">No login needed. Pick a role; you can switch at any time.</p>
      <Errors errors={errors} />

      <h2>Traveler</h2>
      <div className="roles">
        <button className="role-btn" onClick={() => navigate("/traveler")}>
          <strong>I am a traveler</strong>
          Request a ride from the airport to my hotel
        </button>
      </div>

      <h2>Taxi supplier</h2>
      <div className="card">
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
    </>
  );
}
