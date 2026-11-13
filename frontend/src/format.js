export const inr = (n) => "₹" + Number(n).toLocaleString("en-IN");

// "2027-04-10T11:30" -> "10 Apr 2027, 11:30" (times are already local; no timezone conversion)
export function when(iso) {
  if (!iso) return "";
  const [date, time] = iso.split("T");
  const [y, m, d] = date.split("-");
  const month = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][Number(m) - 1];
  return `${Number(d)} ${month} ${y}, ${time.slice(0, 5)}`;
}

export const timeOnly = (iso) => (iso ? iso.split("T")[1].slice(0, 5) : "");

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
