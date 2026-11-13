// All backend calls live here. Errors come back as {errors: [{rule, message}]}.
const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

export class ApiError extends Error {
  constructor(errors, status) {
    super(errors.map((e) => e.message).join(" "));
    this.errors = errors;
    this.status = status;
  }
}

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(BASE + path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch {
    throw new ApiError([{ rule: "NETWORK", message: "Cannot reach the backend. Is it running on port 8000?" }], 0);
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    throw new ApiError(data?.errors || [{ rule: "HTTP", message: `Request failed (${res.status}).` }], res.status);
  }
  return data;
}

const post = (path, body) => request(path, { method: "POST", body: body ? JSON.stringify(body) : undefined });

export const api = {
  flights: () => request("/flights"),
  // 
  hotels: (flightId) =>
    request(flightId ? `/hotels?flight_id=${encodeURIComponent(flightId)}` : "/hotels"),
  companies: () => request("/companies"),
  priceRange: (flightId, hotelId) =>
    request(`/price-range?flight_id=${encodeURIComponent(flightId)}&hotel_id=${encodeURIComponent(hotelId)}`),

  createRequest: (body) => post("/requests", body),
  listRequests: () => request("/requests"),
  getRequest: (id) => request(`/requests/${encodeURIComponent(id)}`),
  bookOffer: (offerId) => post(`/offers/${offerId}/book`),
  rejectOffer: (offerId) => post(`/offers/${offerId}/reject`),

  supplierRequests: (companyId) => request(`/suppliers/${encodeURIComponent(companyId)}/requests`),
  supplierOffers: (companyId) => request(`/suppliers/${encodeURIComponent(companyId)}/offers`),
  assignCar: (requestId, body) => post(`/requests/${encodeURIComponent(requestId)}/offers`, body),

  // Booking summary (M5) and change requests (M7)
  listBookings: () => request("/bookings"),
  getBooking: (number) => request(`/bookings/${encodeURIComponent(number)}`),
  requestChange: (number, body) => post(`/bookings/${encodeURIComponent(number)}/changes`, body),
  supplierChanges: (companyId) => request(`/suppliers/${encodeURIComponent(companyId)}/changes`),
  acceptChange: (changeId, companyId) => post(`/changes/${changeId}/accept`, { company_id: companyId }),
  rejectChange: (changeId, companyId) => post(`/changes/${changeId}/reject`, { company_id: companyId }),
};
