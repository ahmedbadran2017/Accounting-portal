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
