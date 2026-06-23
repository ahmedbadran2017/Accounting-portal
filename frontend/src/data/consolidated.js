// Consolidated (Justyol Holding) group rollup — a genuine multi-entity view,
// not the Morocco COD cockpit. June-2026 snapshot from the JoyAgent Books
// handoff; converted to the USD reporting base for the group. Replaced by live
// ERPNext consolidation queries (with real FX) in a later slice.

const pick = (l, en, ar, fr) => (l === "ar" ? ar : l === "fr" ? fr : en);

// Illustrative reporting-base FX (1 USD = …). Live rates wired later.
const FX = { MAD: 10.1, TRY: 32.8, USD: 1 };
const toUsd = (amount, ccy) => amount / (FX[ccy] || 1);
const usd = (n) => "$" + Math.round(n).toLocaleString("en-US");
const usdK = (n) => (Math.abs(n) >= 1e6 ? "$" + (n / 1e6).toFixed(2) + "M" : "$" + Math.round(n / 1000) + "K");

export function buildConsolVM(lang) {
  // Per-entity headline figures in local currency (from the handoff).
  const entities = [
    {
      id: "sarl", code: "MA", name: "Justyol Morocco", ccy: "MAD", badge: "linear-gradient(135deg,#e17f62,#a33a22)",
      role: pick(lang, "Storefront · COD sales", "المتجر · مبيعات COD", "Boutique · ventes COD"),
      cashLocal: 1_150_000, payLocal: 3_600_000, interco: false,
    },
    {
      id: "maslak", code: "TR", name: "Maslak LTD", ccy: "TRY", badge: "linear-gradient(135deg,#38bdf8,#0369a1)",
      role: pick(lang, "Türkiye supply · procurement", "التوريد التركي · مشتريات", "Approvisionnement Turquie"),
      cashLocal: 0, payLocal: 5_965, spendYtdLocal: 13_990_000, interco: false,
    },
    {
      id: "hk", code: "CN", name: "Justyol China", ccy: "USD", badge: "linear-gradient(135deg,#34d399,#047857)",
      role: pick(lang, "China sourcing · intercompany", "المصادر الصيني · بين الشركات", "Sourcing Chine · intra-groupe"),
      cashLocal: 0, payLocal: 21_525, interco: true,
    },
  ];

  const rows = entities.map((e) => {
    const payUsd = toUsd(e.payLocal, e.ccy);
    const cashUsd = toUsd(e.cashLocal, e.ccy);
    return {
      ...e,
      payUsd, cashUsd,
      payLabel: e.payLocal.toLocaleString("en-US") + " " + e.ccy,
      payUsdLabel: usd(payUsd),
      cashUsdLabel: cashUsd ? usd(cashUsd) : "—",
      spendLabel: e.spendYtdLocal ? e.spendYtdLocal.toLocaleString("en-US") + " " + e.ccy : null,
    };
  });

  const groupPay = rows.reduce((s, r) => s + r.payUsd, 0);
  const groupCash = rows.reduce((s, r) => s + r.cashUsd, 0);
  // share of group payables per entity (for the breakdown bar)
  rows.forEach((r) => (r.payShare = groupPay ? (r.payUsd / groupPay) * 100 : 0));

  const kpis = [
    { label: pick(lang, "Group cash", "نقد المجموعة", "Trésorerie groupe"), value: usdK(groupCash), icon: "coins", ic: "#047857", ibg: "#ecfdf5",
      sub: pick(lang, "all entities · USD base", "كل الكيانات · أساس الدولار", "toutes entités · base USD") },
    { label: pick(lang, "Group payables", "دائنو المجموعة", "Dettes groupe"), value: usdK(groupPay), icon: "receipt", ic: "#be123c", ibg: "#fff1f2",
      sub: pick(lang, "TR + CN + MA suppliers", "موردون TR + CN + MA", "fournisseurs TR + CN + MA") },
    { label: pick(lang, "Entities", "الكيانات", "Entités"), value: "3", unit: "", icon: "layers", ic: "#7c3aed", ibg: "#faf5ff",
      sub: pick(lang, "consolidated into Holding", "موحَّدة في القابضة", "consolidées dans la holding") },
    { label: pick(lang, "Reporting base", "عملة التقرير", "Devise de reporting"), value: "USD", icon: "scale", ic: "#0369a1", ibg: "#eff6ff",
      sub: pick(lang, "1$ = 10.1 MAD · 32.8 TRY", "١$ = ١٠٫١ درهم · ٣٢٫٨ ليرة", "1$ = 10,1 MAD · 32,8 TRY") },
  ];

  const digest = pick(lang,
    "Justyol Holding posts no transactions of its own — it consolidates three operating entities. Morocco is the revenue engine (COD storefront); Maslak (Türkiye) and Justyol China are supply/sourcing and carry the group's payables. Figures below are rolled to a USD base at illustrative June rates; intercompany balances with Justyol China are flagged and eliminate on consolidation.",
    "شركة Justyol القابضة لا تُسجّل حركات خاصة بها — تُوحّد ثلاثة كيانات تشغيلية. المغرب هو محرك الإيراد (متجر COD)؛ وMaslak (تركيا) وJustyol China للتوريد والمصادر ويحملان دائني المجموعة. الأرقام أدناه محوَّلة لأساس الدولار بأسعار يونيو الاسترشادية؛ أرصدة Justyol China بين الشركات مُعلَّمة وتُستبعد عند التوحيد.",
    "Justyol Holding ne passe aucune écriture propre — elle consolide trois entités opérationnelles. Le Maroc est le moteur du revenu (boutique COD) ; Maslak (Turquie) et Justyol China portent les dettes du groupe. Les montants ci-dessous sont convertis en base USD aux taux indicatifs de juin ; les soldes intra-groupe avec Justyol China sont signalés et s'éliminent à la consolidation.");

  return { kpis, rows, digest, groupPayLabel: usdK(groupPay) };
}
