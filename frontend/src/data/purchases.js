// Purchases — vendors & bills. Justyol June-2026 snapshot from the JoyAgent
// Books handoff (Purchase Invoice = bills, 3-way match vs PO + Goods Receipt).
// Replaced by live ERPNext Purchase Invoice / Supplier queries later.

const pick = (l, en, ar, fr) => (l === "ar" ? ar : l === "fr" ? fr : en);

export const VENDORS = [
  { id: "meta", name: "Facebook ADS / Meta", place: "Dublin, IE", code: "Ad", badge: "linear-gradient(135deg,#60a5fa,#2563eb)", payable: "734,812", ccy: "MAD", interco: false,
    terms: (l) => pick(l, "Prepaid · weekly", "مسبق · أسبوعي", "Prépayé · hebdo"),
    note: (l) => pick(l, "Ad spend · largest payable", "إنفاق إعلاني · أكبر مستحق", "Pub · plus gros dû") },
  { id: "china", name: "Justyol China", place: "Shenzhen, CN", code: "CN", badge: "linear-gradient(135deg,#fb7185,#be123c)", payable: "248,305", ccy: "USD", interco: true,
    terms: (l) => pick(l, "Intercompany", "ضمن المجموعة", "Intra-groupe"),
    note: (l) => pick(l, "Payable · intercompany", "مستحق · ضمن المجموعة", "À payer · intra-groupe") },
  { id: "sla", name: "SLA Import & Export", place: "Casablanca, MA", code: "MA", badge: "linear-gradient(135deg,#fbbf24,#b45309)", payable: "191,906", ccy: "MAD", interco: false,
    terms: (l) => pick(l, "Logistics · customs", "لوجستيك · جمارك", "Logistique · douane"),
    note: (l) => pick(l, "Payable · freight/customs", "مستحق · شحن/جمارك", "À payer · fret/douane") },
  { id: "tommy", name: "TOMMYLIFE", place: "İstanbul, TR", code: "TR", badge: "linear-gradient(135deg,#38bdf8,#0369a1)", payable: "181,505", ccy: "TRY", interco: false,
    terms: (l) => pick(l, "Net 30 · sourcing", "صافي ٣٠ · توريد", "Net 30 · sourcing"),
    note: (l) => pick(l, "Payable · 4 bills", "مستحق · ٤ فواتير", "À payer · 4 factures") },
];

// 3-way match state: ok = PO + Goods Receipt + Invoice agree; exc = exception.
export const MATCH_META = {
  ok:  { c: "#047857", bg: "#ecfdf5", bd: "#a7f3d0", en: "3-way matched", ar: "مطابقة ثلاثية", fr: "Rappr. 3 voies" },
  exc: { c: "#be123c", bg: "#fef2f2", bd: "#fecaca", en: "Match exception", ar: "استثناء مطابقة", fr: "Écart rappr." },
};
export const BILL_STATUS = {
  paid:    { bg: "#ecfdf5", fg: "#047857", bd: "#a7f3d0", en: "Paid", ar: "مدفوعة", fr: "Payée" },
  overdue: { bg: "#fef2f2", fg: "#be123c", bd: "#fecaca", en: "Overdue", ar: "متأخرة", fr: "En retard" },
  ret:     { bg: "#f1f5f9", fg: "#64748b", bd: "#cbd5e1", en: "Return", ar: "مرتجع", fr: "Retour" },
};

export const BILLS = [
  { id: "PUR-INV-05851", vendor: "Neon Terlik", amount: "TRY 52,800", match: "ok", status: "paid" },
  { id: "PUR-INV-05849", vendor: "Digitronics", amount: "MAD 390", match: "ok", status: "paid" },
  { id: "PUR-INV-05845", vendor: "BDM Pharma", amount: "MAD 274", match: "ok", status: "paid" },
  { id: "PUR-INV-05844", vendor: "BDM Pharma", amount: "MAD 47.82", match: "exc", status: "overdue" },
  { id: "PUR-INV-05834", vendor: "Vienev", amount: "MAD -2,651", match: "ok", status: "ret" },
  { id: "PUR-INV-05853", vendor: "OSOULY", amount: "MAD 130", match: "ok", status: "paid" },
];

export const findBill = (id) => BILLS.find((b) => b.id === id) || null;
export const matchLabel = (m, l) => { const x = MATCH_META[m] || MATCH_META.ok; return x[l] || x.en; };
export const billStatusLabel = (s, l) => { const x = BILL_STATUS[s] || BILL_STATUS.paid; return x[l] || x.en; };
