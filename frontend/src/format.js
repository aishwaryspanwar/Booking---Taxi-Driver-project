export const inr = (n) => "₹" + Number(n).toLocaleString("en-IN");

// "2027-04-10T11:30" -> "10 Apr 2027, 11:30" (times are already local; no timezone conversion)
export function when(iso) {
  if (!iso) return "";
  const [date, time] = iso.split("T");
  const [y, m, d] = date.split("-");
  const month = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][Number(m) - 1];
  return `${Number(d)} ${month} ${y}, ${time.slice(0, 5)}`;
}

// G4: offer end times come as UTC ("...Z") and show in the viewer's own time zone.
export function endsAt(isoUtc) {
  if (!isoUtc) return "";
  return new Date(isoUtc).toLocaleString("en-GB", {
    day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

export const CAR_TYPES = ["HATCHBACK", "SEDAN", "SUV", "BUS"];

export const timeOnly =(iso) => (iso ? iso.split("T")[1].slice(0, 5) : "");

export function priceLabel(offerPrice, travelerPrice) {
  const diff = offerPrice - travelerPrice;
  if (diff === 0) return "Your price";
  return diff > 0 ? `+${inr(diff)}` : `−${inr(-diff)}`;
}

export const statusText = (s) => s.toLowerCase().replace("_", " ");

export function passengersText(r) {
  const kids = r.child_ages.length ? ` + ${r.child_ages.length} child (age ${r.child_ages.join(", ")})` : "";
  return `${r.adults} adult${r.adults > 1 ? "s" : ""}${kids}`;
}

// "2027-04-10T11:30" -> "10 Apr"
export function shortDate(iso) {
  if (!iso) return "";
  const [, m, d] = iso.split("T")[0].split("-");
  return `${Number(d)} ${["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][Number(m) - 1]}`;
}

// Dropdown label for a flight: just the flight number. When the same number flies
// more than once in the list, add the landing date so the options stay distinct.
export function flightLabels(flights) {
  const count = {};
  flights.forEach((f) => { count[f.flight_number] = (count[f.flight_number] || 0) + 1; });
  return (f) => (count[f.flight_number] > 1 ? `${f.flight_number} · ${shortDate(f.arrival_local)}` : f.flight_number);
}

// One line of detail for the flight chosen in a dropdown.
export const flightDetail = (f) => (f ? `${f.from} → ${f.to} · lands ${when(f.arrival_local)}` : "");
