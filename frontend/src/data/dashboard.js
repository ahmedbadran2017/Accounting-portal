// Dashboard cockpit view-model for the JoyAgent Books design.
// June-2026 Justyol Morocco snapshot used as the initial display; each block
// maps to an ERPNext query that will replace these constants slice by slice
// (see api/dashboard.py — get_overview already returns receivable/payable/cash).

const pick = (lang, en, ar, fr) => (lang === "ar" ? ar : lang === "fr" ? fr : en);

// Real Payment-Entry daily money-in / money-out (June, MAD).
const CIN = { "01": 7015, "02": 44436, "03": 85871, "04": 139932, "05": 118969, "06": 347, "07": 268, "08": 144247, "09": 46910, "10": 67514, "11": 52830, "12": 102024, "13": 43856, "14": 2211, "15": 15865, "16": 60979, "17": 33187, "18": 47697, "19": 78321, "20": 47619, "21": 2225, "22": 9842 };
const COUT = { "01": 14742, "05": 8516, "08": 19132, "09": 92233, "10": 50000, "12": 44800, "15": 33155, "16": 8000, "18": 28185, "19": 46186, "20": 130, "21": 52638 };

const ENTITY_BANNERS = {
  maslak: { name: "Maslak LTD", ccy: "TRY",
    role: (l) => pick(l, "Türkiye supply entity — procurement & export, no COD sales", "كيان التوريد التركي — شراء وتصدير، بلا مبيعات COD", "Entité d’approvisionnement turque — achats & export, pas de ventes COD"),
    figs: [["Bills YTD", "768"], ["Spend YTD", "13.99M TRY"], ["Open payable", "5,965 TRY"]] },
  hk: { name: "Justyol China", ccy: "USD",
    role: (l) => pick(l, "China sourcing entity — intercompany procurement", "كيان المصادر الصيني — مشتريات بين الشركات", "Entité sourcing Chine — achats intra-groupe"),
    figs: [["Bills YTD", "1"], ["Open payable", "21,525 USD"], ["Sales", "—"]] },
  group: { name: "Justyol Holding", ccy: "USD",
    role: (l) => pick(l, "Holding — consolidated view, no direct transactions", "الكيان القابض — عرض موحَّد، بلا حركات تشغيلية", "Holding — vue consolidée, pas de transactions"),
    figs: [["Direct txns", "0"], ["Consolidates", "3 entities"], ["Base", "USD"]] },
};

export function buildDashVM(lang, entity) {
  const cmax = Math.max(...Object.keys(CIN).map((d) => Math.max(CIN[d] || 0, COUT[d] || 0)));
  const cashflow = {
    title: pick(lang, "Cash flow — money in vs out", "حركة الكاش — داخل مقابل خارج", "Flux de trésorerie — entrées / sorties"),
    sub: pick(lang, "22 days · real payment entries", "٢٢ يوم · قيود الدفع الفعلية", "22 jours · écritures de paiement réelles"),
    totalIn: "1.15M", totalOut: "405K", net: "+747K",
    inLbl: pick(lang, "In", "داخل", "Entrées"), outLbl: pick(lang, "Out", "خارج", "Sorties"),
    days: Object.keys(CIN).map((d) => ({
      d,
      inH: Math.round((CIN[d] || 0) / cmax * 60) + 2,
      outH: Math.round((COUT[d] || 0) / cmax * 60) + 2,
      title: `${d} Jun · +${Math.round((CIN[d] || 0) / 1000)}k / −${Math.round((COUT[d] || 0) / 1000)}k`,
    })),
  };

  const _inA = Object.values(CIN), _outA = Object.values(COUT);
  const _netA = Object.keys(CIN).map((d) => (CIN[d] || 0) - (COUT[d] || 0));
  const _sp = (arr) => {
    const a = arr && arr.length > 1 ? arr : [0, 0];
    const mn = Math.min(...a), mx = Math.max(...a), rg = mx - mn || 1, w = 100, h = 26, p = 3;
    return a.map((v, i) => `${((i / (a.length - 1)) * w).toFixed(1)},${(h - p - ((v - mn) / rg) * (h - 2 * p)).toFixed(1)}`).join(" ");
  };
  const kpis = [
    { label: pick(lang, "Cash collected (MTD)", "نقد مُحصَّل (الشهر)", "Encaissé (mois)"), value: "1.15", unit: "M", up: true, icon: "coins", ic: "#047857", ibg: "#ecfdf5", spark: _sp(_inA),
      sub: pick(lang, "6,106 payments · June", "٦٬١٠٦ دفعة · يونيو", "6 106 paiements · juin") },
    { label: pick(lang, "Paid out (MTD)", "مدفوعات صادرة", "Décaissé"), value: "405", unit: "K", up: false, icon: "wallet", ic: "#b45309", ibg: "#fff4e0", spark: _sp(_outA),
      sub: pick(lang, "suppliers, fees & FX", "موردون ورسوم وصرف", "fourn., frais & change") },
    { label: pick(lang, "Net cash movement", "صافي حركة النقد", "Flux net"), value: "+747", unit: "K", up: true, icon: "trend", ic: "#0369a1", ibg: "#eff6ff", spark: _sp(_netA),
      sub: pick(lang, "collected − paid", "محصَّل − مدفوع", "encaissé − décaissé") },
    { label: pick(lang, "Payables (AP)", "دائنون (AP)", "Dettes (AP)"), value: "3.60", unit: "M", up: false, icon: "receipt", ic: "#be123c", ibg: "#fff1f2", spark: _sp(_outA),
      sub: pick(lang, "89 suppliers open", "٨٩ مورّد مفتوح", "89 fournisseurs") },
  ];

  const channels = [
    { name: pick(lang, "Cathadis (COD clearing)", "Cathadis (مقاصّة COD)", "Cathadis (clearing COD)"), sub: "108.021.003", amount: "1,139,307", share: 98.9, bar: "linear-gradient(90deg,#fcd34d,#d97706)", warn: true },
    { name: "BMCE Bank", sub: "••• 1303", amount: "12,483", share: 1.1, bar: "linear-gradient(90deg,#6ee7b7,#059669)", warn: false },
    { name: pick(lang, "Petty cash", "كاش (نثرية)", "Caisse"), sub: "100.002.002", amount: "375", share: 0.03, bar: "linear-gradient(90deg,#7dd3fc,#0ea5e9)", warn: false },
  ];
  const channelMeta = {
    title: pick(lang, "Collection by channel", "التحصيل بالقناة", "Encaissement par canal"),
    sub: pick(lang, "Where June cash landed", "وين نزل نقد يونيو", "Où le cash de juin a atterri"),
    warn: pick(lang,
      "98.9% via one Cathadis clearing account. Carrier is tagged on orders but isn’t a GL dimension — can’t be sub-ledgered per carrier.",
      "٩٨٫٩٪ من التحصيل عبر حساب مقاصّة Cathadis واحد. الناقل مُسجَّل على الطلبات لكنه ليس بُعداً في الـ GL — لا يمكن فصله لكل ناقل.",
      "98,9% via un seul compte de clearing Cathadis. Le transporteur est renseigné sur les commandes mais n’est pas une dimension du GL."),
  };

  const arap = {
    title: pick(lang, "Working capital", "رأس المال العامل", "Fonds de roulement"),
    sub: pick(lang, "AR / AP — live from ERPNext", "AR / AP — حقيقي من ERPNext", "AR / AP — réel ERPNext"),
    arVal: "−2.85M", arRows: "315", apVal: "3.60M", apRows: "89",
    arLabel: pick(lang, "Receivables (AR)", "مدينون (AR)", "Créances (AR)"),
    apLabel: pick(lang, "Payables (AP)", "دائنون (AP)", "Dettes (AP)"),
    arNote: pick(lang, "Negative debtor balance: customers carry credit balances — COD collection not matched to invoices.",
      "رصيد مدينون سالب: العملاء أرصدتهم دائنة — تحصيل COD غير متطابق مع الفواتير.",
      "Solde créances négatif : les clients ont des soldes créditeurs — encaissement COD non lettré."),
    apNote: pick(lang, "Owed to suppliers (TR/CN/MA)", "مستحق للموردين (TR/CN/MA)", "Dû aux fournisseurs (TR/CN/MA)"),
  };

  const digestChips = [
    { label: pick(lang, "Net cash +747K", "صافي نقد +٧٤٧ ألف", "Flux net +747k"), dot: "#34d399", go: { module: "banking" } },
    { label: pick(lang, "98.9% via Cathadis", "٩٨٫٩٪ عبر Cathadis", "98,9% via Cathadis"), dot: "#fbbf24", go: { module: "banking", sub: "variance" } },
    { label: pick(lang, "Margin 0/7,697", "الهامش ٠ من ٧٬٦٩٧", "Marge 0/7 697"), dot: "#f87171", go: { module: "items", sub: "landed" } },
  ];
  const digest = pick(lang,
    "I audited Justyol Morocco for June: 1.15M MAD collected vs 405K paid — net +747K, 98.9% routed through one Cathadis clearing account. The carrier is tagged on 80.6% of orders but never reaches the GL — so revenue can’t be sliced by carrier or city, and margin is computed on 0 of 7,697 orders. Debtors sit at −2.85M (unmatched credit balances). I recommend a per-carrier COD receivable sub-ledger and landed-cost margin.",
    "راجعتُ Justyol Morocco ليونيو: مُحصَّل ١٫١٥ مليون درهم مقابل ٤٠٥ ألف مدفوع — صافي +٧٤٧ ألف، ٩٨٫٩٪ منه عبر حساب مقاصّة Cathadis واحد. الناقل مُسجَّل على ٨٠٫٦٪ من الطلبات لكنه لا يصل للـ GL — فما ينفع تقطيع الإيراد حسب الناقل أو المدينة، والهامش محسوب على ٠ من ٧٬٦٩٧ طلب. المدينون −٢٫٨٥ مليون (أرصدة دائنة غير متطابقة).",
    "J’ai audité Justyol Morocco pour juin : 1,15M MAD encaissés contre 405K décaissés — net +747K, dont 98,9% via un seul compte de clearing Cathadis. Le transporteur est renseigné sur 80,6% des commandes mais n’atteint jamais le grand livre. Créances à −2,85M (soldes créditeurs non lettrés).");

  const eb = ENTITY_BANNERS[entity];
  const entityBanner = eb ? {
    name: eb.name, ccy: eb.ccy, role: eb.role(lang), figs: eb.figs.map(([label, value]) => ({ label, value })),
    note: pick(lang,
      "The COD cards below are Justyol Morocco’s. This entity’s books are shaped differently — switch to Morocco for the full COD cycle.",
      "بطاقات COD أدناه تخص Justyol Morocco. هذا الكيان دفاتره مختلفة — بدّل لـ Morocco لعرض دورة COD الكاملة.",
      "Les cartes COD ci-dessous concernent Justyol Morocco. Basculez vers Morocco pour le cycle COD complet."),
  } : null;

  return { digest, digestChips, kpis, cashflow, channels, channelMeta, arap, entityBanner };
}
