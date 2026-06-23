// Items & margin — Landed Cost Vouchers (the ★Justyol "true SKU margin" hero).
// Freight, customs, duties & insurance are capitalised into inventory and
// allocated across SKUs so margin is computed on the real landed cost — this
// closes the "custom_margin = 0 on all 7,697 orders" anomaly the auditor flags.
// June-2026 snapshot from the JoyAgent Books handoff; live ERPNext later.

const pick = (l, en, ar, fr) => (l === "ar" ? ar : l === "fr" ? fr : en);

export const LCV_STATUS = {
  posted: { bg: "#ecfdf5", fg: "#047857", bd: "#a7f3d0", en: "Posted", ar: "مُرحَّل", fr: "Passé" },
  draft:  { bg: "#fffbeb", fg: "#b45309", bd: "#fde68a", en: "Draft", ar: "مسودة", fr: "Brouillon" },
};
export const lcvStatusLabel = (s, l) => { const x = LCV_STATUS[s] || LCV_STATUS.posted; return x[l] || x.en; };

export function landedVM(l) {
  const vouchers = [
    { id: "LCV-0042", ship: "Maslak — denim", freight: "18,400", customs: "9,200", duties: "22,600", total: "53,300", basis: pick(l, "By value", "بالقيمة", "Par valeur"), status: "posted" },
    { id: "LCV-0041", ship: "Yiwu — hoodies", freight: "12,100", customs: "6,400", duties: "14,900", total: "34,800", basis: pick(l, "By weight", "بالوزن", "Par poids"), status: "posted" },
    { id: "LCV-0040", ship: "Yiwu — accessories", freight: "4,200", customs: "1,900", duties: "5,100", total: "11,800", basis: pick(l, "By qty", "بالكمية", "Par qté"), status: "draft" },
  ];
  const alloc = [
    { item: "JY-JKT-0301 · Veste en Jean", basis: "252,000 (52%)", rate: "+27,716", sku: "+11.5 / u" },
    { item: "JY-DRS-0392 · Robe Plissée", basis: "160,000 (33%)", rate: "+17,589", sku: "+8.4 / u" },
    { item: "JY-PNT-0145 · Pantalon Cargo", basis: "73,000 (15%)", rate: "+7,995", sku: "+9.2 / u", flagged: true },
  ];
  const journal = [
    { acc: "Inventory — JY-JKT-0301", dr: "27,716.00", cr: "" },
    { acc: "Inventory — JY-DRS-0392", dr: "17,589.00", cr: "" },
    { acc: "Inventory — JY-PNT-0145", dr: "7,995.00", cr: "" },
    { acc: "Landed Cost Clearing", dr: "", cr: "53,300.00" },
  ];
  return {
    vouchers, alloc, journal,
    title: pick(l, "Landed cost vouchers", "سندات التكلفة المحمَّلة", "Bons de coût de revient"),
    sub: pick(l, "Freight, customs, duties & insurance capitalised into inventory", "الشحن والجمارك والرسوم والتأمين تُرسمَل في المخزون", "Fret, douane, droits & assurance capitalisés en stock"),
    allocTitle: pick(l, "Allocation · LCV-0042 by value", "التوزيع · LCV-0042 بالقيمة", "Répartition · LCV-0042 par valeur"),
    journalTitle: pick(l, "Capitalisation journal", "قيد الرسملة", "Écriture de capitalisation"),
    flagTitle: "JY-PNT-0145",
    flagDesc: pick(l, "Now valued — this SKU was the COGS-gap the auditor flagged. Allocating LCV-0042 closes it.",
      "الآن مُقيَّم — هذا الصنف كان فجوة التكلفة التي رصدها المدقّق. توزيع LCV-0042 يغلقها.",
      "Maintenant valorisé — ce SKU était l’écart signalé. La répartition du LCV-0042 le corrige."),
    cols: {
      voucher: pick(l, "Voucher", "السند", "Bon"), shipment: pick(l, "Shipment", "الشحنة", "Expédition"),
      freight: pick(l, "Freight", "شحن", "Fret"), customs: pick(l, "Customs", "جمارك", "Douane"),
      duties: pick(l, "Duties", "رسوم", "Droits"), total: pick(l, "Total", "الإجمالي", "Total"),
      basis: pick(l, "Basis", "الأساس", "Base"), status: pick(l, "Status", "الحالة", "Statut"),
      item: pick(l, "Item", "الصنف", "Article"), receipt: pick(l, "Receipt value", "قيمة الاستلام", "Valeur réception"),
      allocated: pick(l, "Allocated", "المُوزَّع", "Réparti"), perUnit: pick(l, "Per unit", "للوحدة", "Par unité"),
    },
  };
}
