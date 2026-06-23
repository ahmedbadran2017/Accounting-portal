// Accountant — journals (maker-checker), chart of accounts, general ledger,
// trial balance. Justyol June-2026 snapshot from the JoyAgent Books handoff.
// Anomalies the auditor flagged are carried through (153.01 spike, 120.01
// negative debtor). Replaced by live ERPNext GL queries later.

const pick = (l, en, ar, fr) => (l === "ar" ? ar : l === "fr" ? fr : en);

// ── Maker-checker queue ──
export const JOURNAL_STATUS = {
  blocked: { bg: "#fef2f2", fg: "#dc2626", bd: "#fecaca", en: "Blocked · posting halted", ar: "محظور · أُوقف الترحيل", fr: "Bloquée · passation arrêtée" },
  pending: { bg: "#fffbeb", fg: "#b45309", bd: "#fde68a", en: "Pending approval", ar: "بانتظار الموافقة", fr: "En attente d’approbation" },
  approved: { bg: "#ecfdf5", fg: "#047857", bd: "#a7f3d0", en: "Approved · posted", ar: "معتمد · مُرحَّل", fr: "Approuvée · passée" },
  rejected: { bg: "#f1f5f9", fg: "#64748b", bd: "#cbd5e1", en: "Bounced to maker", ar: "أُرجع للصانع", fr: "Renvoyée au maker" },
};

export const JOURNALS = [
  { ref: "STE-05935", status: "blocked", icon: "alert", iconColor: "#dc2626", iconBg: "#fef2f2", amount: "676,000,000", account: "2999 Suspense", blocked: true,
    desc: (l) => pick(l, "Manual journal to Suspense · blocked by auditor", "قيد يدوي إلى حساب التعليق · أوقفه المدقّق", "Écriture manuelle vers compte d’attente · bloquée par l’auditeur"),
    why: (l) => pick(l, "Posts 676,000,000 MAD to Suspense 2999. The 90-day average for this account is 161,000 MAD — 4,200× the norm. Likely a decimal-point error.",
      "يُرحّل ٦٧٦ مليون درهم لحساب التعليق ٢٩٩٩. متوسط ٩٠ يوماً لهذا الحساب ١٦١ ألف — أي ٤٢٠٠ ضعف المعتاد. غالباً خطأ في الفاصلة العشرية.",
      "Passe 676 000 000 MAD vers le compte d’attente 2999. La moyenne 90 j est de 161 000 MAD — 4 200× la norme. Probable erreur de virgule.") },
  { ref: "JE-2041", status: "pending", icon: "clock", iconColor: "#b45309", iconBg: "#fffbeb", amount: "4,166", account: "6810 Depreciation", blocked: false,
    desc: (l) => pick(l, "Monthly depreciation · VW ID.4 · needs approval", "إهلاك شهري · VW ID.4 · يحتاج موافقة", "Amortissement mensuel · VW ID.4 · à approuver") },
  { ref: "JE-2040", status: "pending", icon: "layers", iconColor: "#7c3aed", iconBg: "#f5f3ff", amount: "412,000", account: "1450 Due from", blocked: false,
    desc: (l) => pick(l, "Intercompany invoice · Maslak → SARL", "فاتورة ضمن المجموعة · Maslak → SARL", "Facture intra-groupe · Maslak → SARL") },
];

// ── Chart of accounts (grouped; anomalies flagged) ──
export const COA = [
  { head: true, name: (l) => pick(l, "Assets", "الأصول", "Actif") },
  { code: "153.01", name: "Türkiye Stock in Hand", bal: "168,822,581", anomaly: true },
  { code: "120.01", name: "Debtors", bal: "(2,095)", anomaly: true },
  { code: "108.021.003", name: "Cathadis Transactions – COD clearing", bal: "471,081", isNew: true },
  { code: "102.02.01.01", name: "BMCE Bank", bal: "(11,164)" },
  { head: true, name: (l) => pick(l, "Liabilities", "الالتزامات", "Passif") },
  { code: "320.01", name: "Creditors TRY", bal: "108,292" },
  { code: "320.101", name: "Creditors USD", bal: "1,386" },
  { code: "391.620", name: "VAT %20 (MAD)", bal: "61,312" },
  { head: true, name: (l) => pick(l, "Income & Expense", "الإيراد والمصروف", "Produits & charges") },
  { code: "600.002", name: "Good Sales at Morocco", bal: "376,581" },
  { code: "71.801", name: "Cost of Goods Sold", bal: "368,161" },
  { code: "770.07", name: "Freight & Forwarding", bal: "21,825", isNew: true },
];

// ── General ledger (recent entries) ──
export const GL = [
  { date: "21 Jun", ref: "BTB…167144", account: "120.01 Debtors – JM", dim: "COD · Cathadis", dr: "129.00", cr: "" },
  { date: "21 Jun", ref: "BTB…167144", account: "600.002 Good Sales at Morocco", dim: "—", dr: "", cr: "107.50" },
  { date: "21 Jun", ref: "BTB…167144", account: "391.620 VAT %20 (MAD)", dim: "TVA", dr: "", cr: "21.50" },
  { date: "21 Jun", ref: "BTB…167144", account: "71.801 Cost of Goods Sold – JM", dim: "—", dr: "45.15", cr: "" },
  { date: "20 Jun", ref: "PAY-22475", account: "120.01 Debtors – JM", dim: "—", dr: "", cr: "298.00" },
  { date: "20 Jun", ref: "PAY-22475", account: "108.021.003 Cathadis clearing", dim: "COD", dr: "298.00", cr: "" },
];

// ── Trial balance (derived; anomalies flagged) ──
export const TRIAL = [
  { code: "153.01", name: "Türkiye Stock in Hand", dr: "168,822,581", cr: "", anomaly: true },
  { code: "108.021.003", name: "Cathadis – COD clearing", dr: "471,081", cr: "" },
  { code: "120.01", name: "Debtors", dr: "", cr: "2,095", anomaly: true },
  { code: "102.02.01.01", name: "BMCE Bank", dr: "", cr: "11,164" },
  { code: "320.01", name: "Creditors TRY", dr: "", cr: "108,292" },
  { code: "320.101", name: "Creditors USD", dr: "", cr: "1,386" },
  { code: "391.620", name: "VAT %20 (MAD)", dr: "", cr: "61,312" },
  { code: "600.002", name: "Good Sales at Morocco", dr: "", cr: "376,581" },
  { code: "71.801", name: "Cost of Goods Sold", dr: "368,161", cr: "" },
  { code: "770.07", name: "Freight & Forwarding", dr: "21,825", cr: "" },
];

export const journalStatusLabel = (s, l) => { const x = JOURNAL_STATUS[s] || JOURNAL_STATUS.pending; return x[l] || x.en; };
