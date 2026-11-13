import { useRef } from "react";
import { Link, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import useReveal from "./useReveal.js";
import RolePicker from "./pages/RolePicker.jsx";
import TravelerHome from "./pages/TravelerHome.jsx";
import RequestOffers from "./pages/RequestOffers.jsx";
import SupplierDashboard from "./pages/SupplierDashboard.jsx";
import BookingSummary from "./pages/BookingSummary.jsx";

// Small wave mark next to the name, like the reference logo.
function Logo() {
  return (
    <Link to="/" className="logo">
      <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
        <path d="M2 12c2-2.5 4-2.5 6 0s4 2.5 6 0 4-2.5 6 0" />
        <path d="M2 17c2-2.5 4-2.5 6 0s4 2.5 6 0 4-2.5 6 0" opacity=".55" />
        <path d="M2 7c2-2.5 4-2.5 6 0s4 2.5 6 0 4-2.5 6 0" opacity=".3" />
      </svg>
      <b>Airport<span>Taxi</span></b>
    </Link>
  );
}

function NavBar() {

  const navigate = useNavigate();
 
  return (
    <header className="nav-top">
      <Logo />
      
      <div className="nav-right">
        <button onClick={() => navigate("/bookings")}>Bookings</button>
      </div>
    </header>
  );
}

export default function App() {
  const mainRef = useRef(null);
  const { pathname } = useLocation();
  useReveal(mainRef, pathname);
  return (
    <>
      <NavBar />
      <main className="page" ref={mainRef}>
        <Routes>
          <Route path="/" element={<RolePicker />} />
          <Route path="/traveler" element={<TravelerHome />} />
          <Route path="/traveler/requests/:requestId" element={<RequestOffers />} />
          <Route path="/supplier/:companyId" element={<SupplierDashboard />} />
          <Route path="/bookings" element={<BookingSummary />} />
          <Route path="/bookings/:number" element={<BookingSummary />} />
          <Route path="*" element={<p>Page not found. <Link to="/">Go home</Link></p>} />
        </Routes>
      </main>
      <footer className="footer">
        <div className="inner">
          <span>Airport Taxi · Ride offers</span>
          <span>All prices in INR · All times are local to the airport</span>
        </div>
      </footer>
    </>
  );
}
