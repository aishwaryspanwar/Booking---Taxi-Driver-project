import { Link, Route, Routes } from "react-router-dom";
import RolePicker from "./pages/RolePicker.jsx";
import TravelerHome from "./pages/TravelerHome.jsx";
import RequestOffers from "./pages/RequestOffers.jsx";
import SupplierDashboard from "./pages/SupplierDashboard.jsx";

export default function App() {
  return (
    <div className="page">
      <header className="topbar">
        <Link to="/" className="brand">Airport Taxi Offers</Link>
        <Link to="/">Switch role</Link>
      </header>
      <Routes>
        <Route path="/" element={<RolePicker />} />
        <Route path="/traveler" element={<TravelerHome />} />
        <Route path="/traveler/requests/:requestId" element={<RequestOffers />} />
        <Route path="/supplier/:companyId" element={<SupplierDashboard />} />
        <Route path="*" element={<p>Page not found. <Link to="/">Go home</Link></p>} />
      </Routes>
    </div>
  );
}
