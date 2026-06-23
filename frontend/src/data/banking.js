// Banking & COD — carrier remittance batches. Justyol June-2026 snapshot from
// the JoyAgent Books handoff. COD remittance = reconcile what a carrier
// collected vs what it remitted (net of fees); variance is queued for review.
// Replaced by live ERPNext Payment Entry / bank-feed matching later.

export const BATCH_STATUS = {
  draft:   { bg: "#fffbeb", fg: "#b45309", bd: "#fde68a", en: "Draft · needs match", ar: "مسودة · تحتاج مطابقة", fr: "Brouillon · à rapprocher" },
  matched: { bg: "#eff6ff", fg: "#0369a1", bd: "#bae6fd", en: "Matched", ar: "مطابَق", fr: "Rapproché" },
  posted:  { bg: "#ecfdf5", fg: "#047857", bd: "#a7f3d0", en: "Posted", ar: "مُرحَّل", fr: "Passé" },
};

export const BATCHES = [
  { id: "RB-0418", carrier: "Sendit", date: "21 Jun", ref: "SND-2026-0618", collected: 78400, fees: 6200, net: 72200, variance: -12400, lineCount: 31, status: "draft" },
  { id: "RB-0417", carrier: "Cathedis", date: "19 Jun", ref: "CTH-44192", collected: 54300, fees: 4100, net: 50200, variance: 0, lineCount: 24, status: "posted" },
  { id: "RB-0416", carrier: "Ozon Express", date: "17 Jun", ref: "OZ-8841", collected: 31200, fees: 2800, net: 28400, variance: 0, lineCount: 18, status: "posted" },
  { id: "RB-0415", carrier: "Sendit", date: "14 Jun", ref: "SND-2026-0611", collected: 69100, fees: 5400, net: 63700, variance: 0, lineCount: 28, status: "posted" },
];

export const findBatch = (id) => BATCHES.find((b) => b.id === id) || null;
export const batchStatusLabel = (s, l) => { const x = BATCH_STATUS[s] || BATCH_STATUS.posted; return x[l] || x.en; };
export const money = (n) => n.toLocaleString("en-US");

const pick = (l, en, ar, fr) => (l === "ar" ? ar : l === "fr" ? fr : en);

// Bank & cash accounts (Justyol Morocco) shown atop the banking list.
export const BANK_ACCOUNTS = [
  { name: "Cathadis – COD clearing", no: "108.021.003", balance: "471,081", ccy: "MAD", bg: "#fff4e0", color: "#b45309" },
  { name: "BMCE Bank", no: "••• 1303", balance: "12,483", ccy: "MAD", bg: "#eff6ff", color: "#0369a1" },
  { name: "Petty cash", no: "100.002.002", balance: "375", ccy: "MAD", bg: "#ecfdf5", color: "#047857" },
];

// Per-order reconciliation line states.
export const LINE_MATCH = {
  matched:       { bg: "#ecfdf5", fg: "#047857", bd: "#a7f3d0", en: "Matched", ar: "مطابَق", fr: "Rapproché" },
  partial:       { bg: "#fff7ed", fg: "#c2410c", bd: "#fed7aa", en: "Partial", ar: "جزئي", fr: "Partiel" },
  not_collected: { bg: "#fef2f2", fg: "#be123c", bd: "#fecaca", en: "Not collected", ar: "لم يُحصَّل", fr: "Non collecté" },
};
export const lineMatchLabel = (s, l) => { const x = LINE_MATCH[s] || LINE_MATCH.matched; return x[l] || x.en; };

// Reconciliation lines for a batch (carrier collected vs expected, per order).
// Illustrative set for the variance batch; live ERPNext mapping later.
export function reconLines(batch) {
  if (!batch) return [];
  if (batch.variance) {
    return [
      { order: "YC-000189", expected: 129, collected: 129, fee: 10, variance: 0, match: "matched" },
      { order: "YC-000188", expected: 89, collected: 89, fee: 7, variance: 0, match: "matched" },
      { order: "YC-000185", expected: 149, collected: 0, fee: 0, variance: -149, match: "not_collected" },
      { order: "YC-000183", expected: 129, collected: 60, fee: 5, variance: -69, match: "partial" },
      { order: "YC-000177", expected: 89, collected: 0, fee: 0, variance: -89, match: "not_collected" },
      { order: "YC-000179", expected: 129, collected: 129, fee: 10, variance: 0, match: "matched" },
    ];
  }
  return [
    { order: "YC-000200", expected: 149, collected: 149, fee: 11, variance: 0, match: "matched" },
    { order: "YC-000201", expected: 129, collected: 129, fee: 10, variance: 0, match: "matched" },
    { order: "YC-000202", expected: 89, collected: 89, fee: 7, variance: 0, match: "matched" },
  ];
}

// ── Variance queue ──
export const VAR_TYPE = {
  uncollected: { bg: "#fef2f2", fg: "#be123c", bd: "#fecaca", en: "Uncollected", ar: "غير مُحصَّل", fr: "Non collecté" },
  partial:     { bg: "#fff7ed", fg: "#c2410c", bd: "#fed7aa", en: "Partial", ar: "جزئي", fr: "Partiel" },
  fee_gap:     { bg: "#eff6ff", fg: "#0369a1", bd: "#bae6fd", en: "Fee gap", ar: "فرق رسوم", fr: "Écart frais" },
};
export const varTypeLabel = (s, l) => { const x = VAR_TYPE[s] || VAR_TYPE.uncollected; return x[l] || x.en; };
export const VARIANCE_QUEUE = [
  { order: "YC-000185", carrier: "Sendit", expected: "149", collected: "0", variance: "-149", type: "uncollected", age: "4d" },
  { order: "YC-000177", carrier: "Sendit", expected: "89", collected: "0", variance: "-89", type: "uncollected", age: "4d" },
  { order: "YC-000183", carrier: "Sendit", expected: "129", collected: "60", variance: "-69", type: "partial", age: "4d" },
  { order: "#242397", carrier: "Cathedis", expected: "149", collected: "140", variance: "-9", type: "fee_gap", age: "6d" },
  { order: "#240956", carrier: "Cathedis", expected: "144", collected: "0", variance: "-144", type: "uncollected", age: "7d" },
  { order: "YC-000150", carrier: "Ozon Express", expected: "99", collected: "90", variance: "-9", type: "fee_gap", age: "9d" },
];
export const VARIANCE_TOTAL = "469";

// ── Carrier aging ──
export const CARRIER_AGING = [
  { carrier: "Cathedis", b0: "182,000", b1: "96,000", b2: "40,000", b3: "12,000", total: "330,000", days: "5.2d", alert: false },
  { carrier: "Sendit", b0: "48,000", b1: "31,000", b2: "22,000", b3: "18,400", total: "119,400", days: "9.8d", alert: true },
  { carrier: "Ozon Express", b0: "21,000", b1: "8,000", b2: "2,800", b3: "0", total: "31,800", days: "3.1d", alert: false },
];

// ── Bank reconciliation ──
export const REC_STATUS = {
  matched:   { bg: "#eff6ff", fg: "#0369a1", bd: "#bae6fd", en: "Matched", ar: "مطابَق", fr: "Rapproché" },
  unmatched: { bg: "#fffbeb", fg: "#b45309", bd: "#fde68a", en: "Needs review", ar: "يحتاج مراجعة", fr: "À revoir" },
  posted:    { bg: "#ecfdf5", fg: "#047857", bd: "#a7f3d0", en: "Posted", ar: "مُرحَّل", fr: "Passé" },
};
export const recStatusLabel = (s, l) => { const x = REC_STATUS[s] || REC_STATUS.matched; return x[l] || x.en; };
export const BANK_REC = {
  bank: "BMCE Bank", matchedPct: "83%", unmatched: "2",
  rows: [
    { date: "21 Jun", desc: "COD remittance · Sendit", amount: "+63,700", to: "108.021.003", status: "matched" },
    { date: "20 Jun", desc: "Supplier payment · Meta Ads", amount: "-44,800", to: "320.01", status: "matched" },
    { date: "19 Jun", desc: "Bank fee", amount: "-130", to: "—", status: "unmatched" },
    { date: "18 Jun", desc: "COD remittance · Cathedis", amount: "+50,200", to: "108.021.003", status: "matched" },
    { date: "17 Jun", desc: "FX transfer out", amount: "-31,214", to: "—", status: "unmatched" },
    { date: "16 Jun", desc: "COD remittance · Ozon", amount: "+28,400", to: "108.021.003", status: "posted" },
  ],
};

export function varianceMsg(l) {
  return pick(l,
    "Collected is short of what the orders expected — 2 orders never collected, 1 partial. Post the matched portion and send the variance to the variance queue.",
    "المُحصَّل أقل مما تتوقعه الطلبات — طلبان لم يُحصَّلا وواحد جزئي. رحِّل الجزء المطابق وأرسل الفرق لطابور الفروق.",
    "Le collecté est inférieur à l’attendu — 2 commandes non collectées, 1 partielle. Passez la partie rapprochée et envoyez l’écart à la file des écarts.");
}
