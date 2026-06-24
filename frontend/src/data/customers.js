// Customers — Justyol Morocco. Real LTV/orders are computed from invoices in
// ERPNext (e.g. Khadija 24,374 MAD / 155 orders; 12,917 customers, 17.9% repeat).
// June-2026 snapshot from the JoyAgent Books handoff; live ERPNext later.

export const CUSTOMERS = [
  { name: "Khadija", city: "Casablanca", orders: 155, delivery: "82%", rto: "14%", ltv: "24,374", credit: "+340", av: "rose", tags: ["risk", "vip"] },
  { name: "Fatima Khartouf", city: "Rabat", orders: 48, delivery: "79%", rto: "17%", ltv: "7,210", credit: "0", av: "sky", tags: ["risk", "vip"] },
  { name: "Siham Elfilali", city: "Marrakech", orders: 31, delivery: "88%", rto: "9%", ltv: "5,940", credit: "+129", av: "amber", tags: ["vip"] },
  { name: "مليكة بلالي", city: "Tanger", orders: 27, delivery: "74%", rto: "22%", ltv: "4,180", credit: "0", av: "emerald", tags: ["risk", "vip"] },
  { name: "Jihad Elouarti", city: "Fès", orders: 22, delivery: "91%", rto: "5%", ltv: "6,015", credit: "+546", av: "violet", tags: ["vip"] },
  { name: "Ali Okahim", city: "Agadir", orders: 19, delivery: "77%", rto: "19%", ltv: "3,420", credit: "0", av: "accent", tags: ["risk", "loyal"] },
];

export const findCustomer = (name) => CUSTOMERS.find((c) => c.name === name) || null;
const pick = (l, en, ar, fr) => (l === "ar" ? ar : l === "fr" ? fr : en);

// Rich customer detail (header stats, connections, contact, activity, ledger).
// Derived from the list row + representative June data; live ERPNext later.
export function customerDetail(c, l) {
  if (!c) return null;
  const repeat = c.orders > 30;
  const digits = String(10000000 + c.name.length * 372841).slice(0, 8);
  const phone = "+212 6" + digits.replace(/(\d{2})(\d{2})(\d{2})(\d{2})/, " $1 $2 $3 $4");
  return {
    ...c,
    phone,
    since: "2024",
    stats: [
      { label: "LTV", value: c.ltv + " MAD" },
      { label: pick(l, "Orders", "الطلبات", "Commandes"), value: String(c.orders) },
      { label: pick(l, "Delivery", "التسليم", "Livraison"), value: c.delivery },
      { label: "RTO", value: c.rto },
    ],
    connections: [
      { label: pick(l, "Orders", "الطلبات", "Commandes"), value: String(c.orders), go: { module: "sales", sub: "orders" } },
      { label: pick(l, "Invoices", "الفواتير", "Factures"), value: String(Math.round(c.orders * 0.9)), go: { module: "sales", sub: "invoices" } },
      { label: pick(l, "Receipts", "السندات", "Reçus"), value: String(Math.round(c.orders * 0.8)), go: { module: "sales", sub: "receipts" } },
      { label: pick(l, "Returns", "الإرجاع", "Retours"), value: String(Math.round(c.orders * parseInt(c.rto) / 100)), go: { module: "sales", sub: "credits" } },
    ],
    contact: [
      { k: pick(l, "Phone", "الهاتف", "Téléphone"), v: phone },
      { k: pick(l, "City", "المدينة", "Ville"), v: c.city },
      { k: pick(l, "Default carrier", "الناقل", "Transporteur"), v: "Cathedis" },
      { k: pick(l, "Segment (RFM)", "الشريحة (RFM)", "Segment (RFM)"), v: repeat ? pick(l, "Loyal · high value", "وفيّ · قيمة عالية", "Fidèle · haute valeur") : pick(l, "Promising", "واعد", "Prometteur") },
      { k: pick(l, "Lifecycle", "دورة الحياة", "Cycle de vie"), v: repeat ? pick(l, "Repeat", "متكرر", "Récurrent") : pick(l, "New", "جديد", "Nouveau") },
    ],
    activity: [
      { icon: "check", iconBg: "#ecfdf5", iconColor: "#047857", title: pick(l, "Order delivered", "تم تسليم الطلب", "Commande livrée"), meta: "Cathedis · " + c.city, time: "2d" },
      { icon: "coins", iconBg: "#eff6ff", iconColor: "#0369a1", title: pick(l, "COD payment received", "تم استلام دفعة COD", "Paiement COD reçu"), meta: c.credit !== "0" ? c.credit + " MAD credit" : "—", time: "2d" },
      { icon: "receipt", iconBg: "#faf6f4", iconColor: "#a33a22", title: pick(l, "Order placed", "تم تسجيل طلب", "Commande passée"), meta: "Shopify", time: "5d" },
      { icon: "truck", iconBg: "#fff7ed", iconColor: "#c2410c", title: pick(l, "Shipped", "تم الشحن", "Expédiée"), meta: "Cathedis", time: "4d" },
    ],
    ledger: [
      { date: "21 Jun", doc: "BTB…167144", type: pick(l, "Invoice", "فاتورة", "Facture"), dr: "129.00", cr: "", bal: "129.00" },
      { date: "21 Jun", doc: "PAY-22491", type: pick(l, "Receipt", "سند قبض", "Reçu"), dr: "", cr: "129.00", bal: "0.00" },
      { date: "18 Jun", doc: "BTB…159042", type: pick(l, "Invoice", "فاتورة", "Facture"), dr: "124.17", cr: "", bal: "124.17" },
    ],
    contactTitle: pick(l, "Contact & segment", "التواصل والشريحة", "Contact & segment"),
    activityTitle: pick(l, "Recent activity", "النشاط الأخير", "Activité récente"),
    ledgerTitle: pick(l, "Customer ledger", "كشف حساب العميل", "Grand livre client"),
    creditLabel: pick(l, "Store credit", "رصيد المتجر", "Avoir client"),
    sinceLabel: pick(l, "since", "منذ", "depuis"),
  };
}

export const initials = (name) => (name || "?").trim().split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
// Delivery rate ≥80% reads healthy; RTO ≥18% is a concern.
export const deliveryColor = (d) => (parseInt(d) >= 80 ? "#047857" : "#b45309");
export const rtoColor = (r) => (parseInt(r) >= 18 ? "#be123c" : parseInt(r) >= 12 ? "#c2410c" : "#a8a29e");
