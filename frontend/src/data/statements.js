// Reports — Financial statements (P&L / Balance Sheet / Cash Flow). Per-entity,
// revenue recognised on delivery, in MAD. June-2026 snapshot from the JoyAgent
// Books handoff; live ERPNext consolidation later.

const pick = (l, en, ar, fr) => (l === "ar" ? ar : l === "fr" ? fr : en);

// kind: 'line' | 'sub' (muted) | 'total' (bold) | 'pos' (green emphasis)
const r = (label, value, kind = "line") => ({ label, value, kind });

export function statementsVM(l) {
  const pl = [
    r(pick(l, "Net delivered revenue", "إيراد مُسلَّم صافٍ", "Revenu net livré"), "3,140,000"),
    r("COGS", "(1,980,400)", "sub"),
    r(pick(l, "Gross profit", "مجمل الربح", "Marge brute"), "1,159,600", "total"),
    r(pick(l, "Carrier fees", "رسوم الناقلين", "Frais transporteurs"), "(128,600)", "sub"),
    r(pick(l, "RTO / returns", "إرجاع", "Retours"), "(74,100)", "sub"),
    r(pick(l, "Ad spend", "إنفاق إعلاني", "Publicité"), "(377,400)", "sub"),
    r(pick(l, "Opex (rent, salaries, SaaS)", "تشغيل", "Charges"), "(201,200)", "sub"),
    r("EBITDA", "378,300", "pos"),
  ];
  const bs = [
    r(pick(l, "Inventory", "المخزون", "Stock"), "1,840,200"),
    r(pick(l, "Stock in transit – COD", "مخزون في الطريق", "Stock en transit"), "486,300", "sub"),
    r(pick(l, "COD receivable", "ذمم COD", "Créances COD"), "612,000", "sub"),
    r(pick(l, "Bank", "البنك", "Banque"), "862,400", "sub"),
    r(pick(l, "Total assets", "إجمالي الأصول", "Total actif"), "3,800,900", "total"),
    r(pick(l, "Accounts payable", "الموردون", "Fournisseurs"), "(2,262,800)", "sub"),
    r(pick(l, "VAT payable", "ضريبة مستحقة", "TVA à payer"), "(628,000)", "sub"),
    r(pick(l, "Equity", "حقوق الملكية", "Capitaux propres"), "910,100", "total"),
  ];
  const cf = [
    r(pick(l, "Cash from operations", "تدفق التشغيل", "Flux d’exploitation"), "612,400"),
    r(pick(l, "Cash collected (COD)", "نقد محصَّل", "Encaissé"), "2,610,000", "sub"),
    r(pick(l, "Paid to suppliers", "مدفوع للموردين", "Payé fournisseurs"), "(1,640,000)", "sub"),
    r(pick(l, "Investing", "استثماري", "Investissement"), "(84,000)", "sub"),
    r(pick(l, "Financing", "تمويلي", "Financement"), "0", "sub"),
    r(pick(l, "Net change in cash", "صافي التغيّر", "Variation nette"), "528,400", "total"),
  ];
  return {
    cards: [
      { key: "pl", title: pick(l, "Profit & Loss", "قائمة الدخل", "Compte de résultat"), rows: pl },
      { key: "bs", title: pick(l, "Balance Sheet", "الميزانية", "Bilan"), rows: bs },
      { key: "cf", title: pick(l, "Cash Flow", "التدفق النقدي", "Flux de trésorerie"), rows: cf },
    ],
    note: pick(l, "Per entity · recognised on delivery · in MAD", "لكل كيان · بالاعتراف عند التسليم · بالدرهم", "Par entité · revenu à la livraison · en MAD"),
  };
}
