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

export function varianceMsg(l) {
  return pick(l,
    "Collected is short of what the orders expected — 2 orders never collected, 1 partial. Post the matched portion and send the variance to the variance queue.",
    "المُحصَّل أقل مما تتوقعه الطلبات — طلبان لم يُحصَّلا وواحد جزئي. رحِّل الجزء المطابق وأرسل الفرق لطابور الفروق.",
    "Le collecté est inférieur à l’attendu — 2 commandes non collectées, 1 partielle. Passez la partie rapprochée et envoyez l’écart à la file des écarts.");
}
