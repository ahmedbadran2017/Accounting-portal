// Sales · COD orders — Justyol Morocco, June-2026 snapshot from the JoyAgent
// Books handoff. Replaced by live ERPNext Sales Order queries in a later slice.

const pick = (l, en, ar, fr) => (l === "ar" ? ar : l === "fr" ? fr : en);

// state → chip palette + trilingual label (mirrors the design's stateMeta).
export const STATE_META = {
  placed:    { c: "#0ea5e9", bg: "#eff6ff", fg: "#0369a1", bd: "#bae6fd", en: "Placed",    ar: "مُسجَّل",    fr: "Passée" },
  confirmed: { c: "#8b5cf6", bg: "#f5f3ff", fg: "#7c3aed", bd: "#ddd6fe", en: "Confirmed", ar: "مؤكَّد",    fr: "Confirmée" },
  transit:   { c: "#f59e0b", bg: "#fff7ed", fg: "#c2410c", bd: "#fed7aa", en: "In transit",ar: "في الطريق", fr: "En transit" },
  delivered: { c: "#10b981", bg: "#ecfdf5", fg: "#047857", bd: "#a7f3d0", en: "Delivered", ar: "تم التسليم", fr: "Livrée" },
  undelivered:{c: "#f59e0b", bg: "#fff7ed", fg: "#c2410c", bd: "#fed7aa", en: "Undelivered",ar:"لم تُسلَّم",  fr: "Non livrée" },
  settled:   { c: "#059669", bg: "#ecfdf5", fg: "#065f46", bd: "#6ee7b7", en: "Settled",   ar: "تمت التسوية",fr: "Réglée" },
  cancelled: { c: "#94a3b8", bg: "#f1f5f9", fg: "#64748b", bd: "#cbd5e1", en: "Cancelled", ar: "مُلغى",      fr: "Annulée" },
};
export const stateLabel = (state, l) => { const m = STATE_META[state] || STATE_META.placed; return m[l] || m.en; };

// State-machine progression for the order-detail header.
export const MACHINE = ["placed", "confirmed", "transit", "delivered", "settled"];
export const machineCounts = { placed: 7697, confirmed: 6556, transit: 6207, delivered: 5772, settled: 6019 };

export const AV = {
  rose: "linear-gradient(135deg,#fb7185,#be123c)", violet: "linear-gradient(135deg,#a78bfa,#6d28d9)",
  sky: "linear-gradient(135deg,#38bdf8,#0369a1)", amber: "linear-gradient(135deg,#fbbf24,#b45309)",
  emerald: "linear-gradient(135deg,#34d399,#047857)", accent: "linear-gradient(135deg,#e17f62,#a33a22)",
};

export const ORDERS = [
  { id: "YC-000189", customer: "Fatiha", initials: "FA", av: "rose", city: "Temara", carrier: "Cathedis", value: 89, cost: 31.15, vat: 14.83, net: 74.17, state: "transit", date: "22 Jun", salesStatus: "Confirmed", logiStatus: "Shipped", trackStatus: "Pending" },
  { id: "YC-000188", customer: "امقران نادية", initials: "AN", av: "sky", city: "إنزكان", carrier: "Cathedis", value: 129, cost: 45.15, vat: 21.5, net: 107.5, state: "transit", date: "22 Jun", salesStatus: "Confirmed", logiStatus: "Shipped", trackStatus: "Pending" },
  { id: "YC-000186", customer: "Omniya", initials: "OM", av: "amber", city: "Laayoune", carrier: "—", value: 89, cost: 31.15, vat: 14.83, net: 74.17, state: "cancelled", date: "22 Jun", salesStatus: "Cancelled", logiStatus: "Pending", trackStatus: "—" },
  { id: "YC-000185", customer: "ايمان", initials: "AY", av: "emerald", city: "وجدة", carrier: "Cathedis", value: 89, cost: 31.15, vat: 14.83, net: 74.17, state: "transit", date: "22 Jun", salesStatus: "Confirmed", logiStatus: "Shipped", trackStatus: "Pending" },
  { id: "YC-000183", customer: "Sanae", initials: "SA", av: "violet", city: "Salé", carrier: "Cathedis", value: 129, cost: 45.15, vat: 21.5, net: 107.5, state: "transit", date: "21 Jun", salesStatus: "Confirmed", logiStatus: "Shipped", trackStatus: "Pending" },
  { id: "YC-000179", customer: "Sefiani Fadwa", initials: "SF", av: "accent", city: "Casablanca", carrier: "Cathedis", value: 129, cost: 45.15, vat: 21.5, net: 107.5, state: "transit", date: "21 Jun", salesStatus: "Confirmed", logiStatus: "Shipped", trackStatus: "Pending" },
  { id: "YC-000177", customer: "برا زهرة", initials: "BZ", av: "rose", city: "آسفي", carrier: "Cathedis", value: 89, cost: 31.15, vat: 14.83, net: 74.17, state: "transit", date: "21 Jun", salesStatus: "Confirmed", logiStatus: "Shipped", trackStatus: "Pending" },
  { id: "#242385", customer: "Siham Elfilali", initials: "SE", av: "sky", city: "—", carrier: "Cathedis", value: 298, cost: 104.3, vat: 49.67, net: 248.33, state: "delivered", date: "20 Jun", salesStatus: "Confirmed", logiStatus: "Delivered", trackStatus: "Delivered" },
  { id: "#242542", customer: "Jihad Elouarti", initials: "JE", av: "amber", city: "—", carrier: "Cathedis", value: 546, cost: 191.1, vat: 91, net: 455, state: "settled", date: "20 Jun", salesStatus: "Confirmed", logiStatus: "Delivered", trackStatus: "Delivered" },
  { id: "#242458", customer: "مليكة بلالي", initials: "MB", av: "emerald", city: "—", carrier: "Cathedis", value: 149, cost: 52.15, vat: 24.83, net: 124.17, state: "settled", date: "20 Jun", salesStatus: "Confirmed", logiStatus: "Delivered", trackStatus: "Delivered" },
  { id: "#242397", customer: "Khadija", initials: "KH", av: "violet", city: "—", carrier: "Cathedis", value: 149, cost: 52.15, vat: 24.83, net: 124.17, state: "undelivered", date: "19 Jun", salesStatus: "Confirmed", logiStatus: "Shipped", trackStatus: "Delivery Exception" },
  { id: "#240956", customer: "Attman", initials: "AT", av: "accent", city: "—", carrier: "Cathedis", value: 144, cost: 50.4, vat: 24, net: 120, state: "undelivered", date: "18 Jun", salesStatus: "Confirmed", logiStatus: "Shipped", trackStatus: "Delivery Exception" },
  { id: "YC-000182", customer: "Mouhcin", initials: "MO", av: "sky", city: "Salé", carrier: "—", value: 129, cost: 45.15, vat: 21.5, net: 107.5, state: "cancelled", date: "21 Jun", salesStatus: "Cancelled", logiStatus: "Pending", trackStatus: "—" },
];

export const findOrder = (id) => ORDERS.find((o) => o.id === id) || null;
const f2 = (n) => n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const L = (l, en, ar, fr) => (l === "ar" ? ar : l === "fr" ? fr : en);

// Posting state for the list/detail: delivered & settled orders have auto-posted
// their revenue journal; everything earlier is awaiting delivery.
export function postingInfo(state, l) {
  const posted = state === "delivered" || state === "settled";
  return {
    posted,
    label: posted ? L(l, "Auto-posted", "تم الترحيل تلقائياً", "Passation auto")
                   : L(l, "Awaiting delivery", "بانتظار التسليم", "En attente livraison"),
  };
}

// Lifecycle timeline — 5 events; "reached" depends on the order's state.
export function orderTimeline(o, l) {
  if (!o) return [];
  const reached = { settled: 5, delivered: 4, transit: 3, undelivered: 3, confirmed: 2, placed: 1, cancelled: 1 }[o.state] || 1;
  const defs = [
    { icon: "receipt", title: L(l, "Order placed", "الطلب مُسجَّل", "Commande passée"), desc: L(l, "From Shopify · no GL", "من Shopify · لا قيد محاسبي", "Depuis Shopify · aucun GL") },
    { icon: "check", title: L(l, "Confirmed", "تم التأكيد", "Confirmée"), desc: L(l, "Confirmed by agent · soft reservation", "تأكيد عبر الوكيل · حجز مخزون", "Confirmée par l’agent · réservation") },
    { icon: "truck", title: L(l, "Shipped — in transit", "شُحنت — في الطريق", "Expédiée — en transit"), desc: L(l, "Delivery note → Stock in Transit posted", "إذن تسليم → مخزون في الطريق", "Bon de livraison → stock en transit") },
    { icon: "check", title: L(l, "Delivered — collected", "تم التسليم — تحصيل", "Livrée — encaissée"), desc: L(l, "Recognition point: revenue + VAT + COGS", "نقطة الاعتراف: إيراد + ضريبة + تكلفة", "Reconnaissance : revenu + TVA + COGS") },
    { icon: "coins", title: L(l, "Settled", "تمت التسوية", "Réglée"), desc: L(l, "Carrier remitted cash − fee", "حوّل الناقل النقد ناقصاً الرسوم", "Transporteur a versé le cash − frais") },
  ];
  return defs.map((d, i) => ({ ...d, done: i + 1 <= reached, time: i + 1 <= reached ? o.date : "—", last: i === defs.length - 1 }));
}

// Auto-posted journal grouped by stage (the design's right column). Each stage
// is balanced; placed/confirmed/cancelled post nothing before delivery.
export function orderStageJournals(o, l) {
  if (!o) return { stages: [], noJournal: true, msg: "" };
  const id6 = o.id.slice(-6);
  const ln = (acc, dr, cr, indent) => ({ acc, dr: dr ? f2(dr) : "", cr: cr ? f2(cr) : "", indent: !!indent });
  const stages = [];
  if (["transit", "undelivered", "delivered", "settled"].includes(o.state)) {
    stages.push({ stage: L(l, "Shipped — in transit", "شحن — في الطريق", "Expédition — transit"), ref: "DN-" + id6, dot: "#d97706",
      lines: [ln("Stock in Transit – COD", o.cost, 0), ln("Inventory", 0, o.cost, true)] });
  }
  if (["delivered", "settled"].includes(o.state)) {
    stages.push({ stage: L(l, "Delivered — revenue", "تسليم — اعتراف بالإيراد", "Livraison — revenu"), ref: o.id, dot: "#10b981",
      lines: [ln("COD Receivable – " + o.carrier, o.value, 0), ln("Sales Revenue", 0, o.net, true), ln("VAT Output Payable", 0, o.vat, true)] });
    stages.push({ stage: L(l, "Delivered — COGS", "تسليم — تكلفة البضاعة", "Livraison — COGS"), ref: o.id, dot: "#10b981",
      lines: [ln("COGS", o.cost, 0), ln("Stock in Transit – COD", 0, o.cost, true)] });
  }
  if (o.state === "settled") {
    const fee = Math.round(o.value * 0.04);
    stages.push({ stage: L(l, "Remittance — settled", "تحصيل — تسوية", "Versement — règlement"), ref: "PE-" + id6, dot: "#065f46",
      lines: [ln("Bank", o.value - fee, 0), ln("Carrier Fee Expense", fee, 0), ln("COD Receivable – " + o.carrier, 0, o.value, true)] });
  }
  const noJournal = stages.length === 0;
  return { stages, noJournal,
    msg: L(l, "No GL before delivery — this is status & inventory movement only. Revenue is recognised only on delivery.",
      "لا قيد محاسبي قبل التسليم — هذه مجرد حركة حالة ومخزون. الإيراد يُعترف به عند التسليم فقط.",
      "Aucun GL avant la livraison — simple changement d’état et de stock. Le revenu n’est reconnu qu’à la livraison.") };
}

// Dimensions row (header chips) for the order detail.
export function orderDims(o, l) {
  if (!o) return [];
  return [
    { k: L(l, "Confirmation", "حالة التأكيد", "Confirmation"), v: o.salesStatus },
    { k: L(l, "Logistics", "اللوجستيات", "Logistique"), v: o.logiStatus },
    { k: L(l, "Tracking", "التتبع", "Suivi"), v: o.trackStatus },
    { k: L(l, "Carrier", "الناقل", "Transporteur"), v: o.carrier },
    { k: L(l, "City", "المدينة", "Ville"), v: o.city },
  ];
}

/**
 * Auto-posted journal for an order. In-transit orders only move goods into
 * Stock-in-Transit (revenue deferred); delivered/settled orders post the full
 * Revenue / VAT / COGS set. Cancelled orders post nothing.
 */
export function orderJournal(o, l) {
  if (!o || o.state === "cancelled") return { lines: [], note: pick(l, "No journal — order cancelled before delivery.", "لا قيد — أُلغي الطلب قبل التسليم.", "Aucune écriture — annulée avant livraison.") };
  if (o.state === "delivered" || o.state === "settled") {
    return {
      note: pick(l, "Revenue recognised on delivery.", "الإيراد مُعترف به عند التسليم.", "Revenu reconnu à la livraison."),
      lines: [
        { acc: "120.01 Debtors – JM", dr: f2(o.value), cr: "" },
        { acc: "600.002 Good Sales at Morocco", dr: "", cr: f2(o.net) },
        { acc: "391.620 VAT %20 (MAD)", dr: "", cr: f2(o.vat) },
        { acc: "71.801 Cost of Goods Sold – JM", dr: f2(o.cost), cr: "" },
        { acc: "153.01 Stock in Hand", dr: "", cr: f2(o.cost) },
      ],
    };
  }
  // transit / undelivered → goods in transit only
  return {
    note: pick(l, "In transit — only Stock-in-Transit posted. Revenue recognised on delivery.", "في الطريق — مخزون في الطريق فقط. الإيراد عند التسليم.", "En transit — seul le stock-en-transit est passé. Revenu à la livraison."),
    lines: [
      { acc: "153.05 Stock in Transit – JM", dr: f2(o.cost), cr: "" },
      { acc: "153.01 Stock in Hand", dr: "", cr: f2(o.cost) },
    ],
  };
}
