// Customers — Justyol Morocco. Real LTV/orders are computed from invoices in
// ERPNext (e.g. Khadija 24,374 MAD / 155 orders; 12,917 customers, 17.9% repeat).
// June-2026 snapshot from the JoyAgent Books handoff; live ERPNext later.

export const CUSTOMERS = [
  { name: "Khadija", city: "Casablanca", orders: 155, delivery: "82%", rto: "14%", ltv: "24,374", credit: "+340", av: "rose" },
  { name: "Fatima Khartouf", city: "Rabat", orders: 48, delivery: "79%", rto: "17%", ltv: "7,210", credit: "0", av: "sky" },
  { name: "Siham Elfilali", city: "Marrakech", orders: 31, delivery: "88%", rto: "9%", ltv: "5,940", credit: "+129", av: "amber" },
  { name: "مليكة بلالي", city: "Tanger", orders: 27, delivery: "74%", rto: "22%", ltv: "4,180", credit: "0", av: "emerald" },
  { name: "Jihad Elouarti", city: "Fès", orders: 22, delivery: "91%", rto: "5%", ltv: "6,015", credit: "+546", av: "violet" },
  { name: "Ali Okahim", city: "Agadir", orders: 19, delivery: "77%", rto: "19%", ltv: "3,420", credit: "0", av: "accent" },
];

export const initials = (name) => (name || "?").trim().split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
// Delivery rate ≥80% reads healthy; RTO ≥18% is a concern.
export const deliveryColor = (d) => (parseInt(d) >= 80 ? "#047857" : "#b45309");
export const rtoColor = (r) => (parseInt(r) >= 18 ? "#be123c" : parseInt(r) >= 12 ? "#c2410c" : "#a8a29e");
