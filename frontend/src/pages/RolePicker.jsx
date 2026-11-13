import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import Errors, { toErrors } from "../components/Errors.jsx";
import Icon from "../components/Icon.jsx";
import { when } from "../format.js";

export default function RolePicker() {
  const navigate = useNavigate();
  const [companies, setCompanies] = useState([]);
  const [errors, setErrors] = useState(null);
  const [companyId, setCompanyId] = useState("");
  const [bookings, setBookings] = useState([]);   // bookings whose ride is not over yet
  const [bookingNumber, setBookingNumber] = useState("");

  useEffect(() => {
    api.companies().then(setCompanies, (e) => setErrors(toErrors(e)));
    api.activeBookings().then(setBookings, (e) => setErrors(toErrors(e)));
  }, []);

  // Two bookings under the same name get their booking number so they can be told apart.
  const sameName = (b) => bookings.filter((x) => x.traveler_name === b.traveler_name).length > 1;
  const chosenBooking = bookings.find((b) => b.booking_number === bookingNumber);
  const chosenCompany = companies.find((c) => c.company_id === companyId);

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
          <span className="over with-icon"><Icon name="luggage" size={14} />Traveler</span>
          <h3>I need a ride to my hotel</h3>
          <p className="grow">
            Pick your flight and hotel, see the suggested price range, post your price, then book the taxi you like.
          </p>
          <div>
            <button className="primary lg" onClick={() => navigate("/traveler")}>Start as a new traveler</button>
          </div>
          {bookings.length > 0 && (
            <>
              <label htmlFor="booking" style={{ marginTop: 20 }}>Or open an existing booking</label>
              <div className="row">
                <select id="booking" style={{ flex: 1, minWidth: 240 }} value={bookingNumber}
                  onChange={(e) => setBookingNumber(e.target.value)}>
                  <option value="">Select your name…</option>
                  {bookings.map((b) => (
                    <option key={b.booking_number} value={b.booking_number}>
                      {sameName(b) ? `${b.traveler_name} (${b.booking_number})` : b.traveler_name}
                    </option>
                  ))}
                </select>
                <button className="primary" disabled={!bookingNumber}
                  onClick={() => navigate(`/bookings/${bookingNumber}`)}>
                  Continue
                </button>
              </div>
              {chosenBooking && (
                <p className="hint">
                  {chosenBooking.booking_number} · {chosenBooking.hotel}, {chosenBooking.city} ·
                  pickup {when(chosenBooking.pickup)} · {chosenBooking.supplier}
                </p>
              )}
            </>
          )}
        </div>

        <div className="card">
          <span className="over with-icon"><Icon name="car" size={14} />Taxi supplier</span>
          <h3>I drive airport rides</h3>
          <label htmlFor="supplier">Choose your company</label>
          <div className="row">
          <select id="supplier" style={{ flex: 1, minWidth: 240 }} value={companyId}
            onChange={(e) => setCompanyId(e.target.value)}>
            <option value="">Select a taxi supplier…</option>
            {companies.map((c) => (
              <option key={c.company_id} value={c.company_id}>
                {c.name}
              </option>
            ))}
          </select>
          <button className="primary" disabled={!companyId} onClick={() => navigate(`/supplier/${companyId}`)}>
            Continue
          </button>
          </div>
          {chosenCompany && (
            <p className="hint">
              {chosenCompany.airports.join(", ")} · {chosenCompany.vehicles.length} cars ·
              open {chosenCompany.service_from}–{chosenCompany.service_until}
            </p>
          )}
        </div>
      </div>
    </>
  );
}
