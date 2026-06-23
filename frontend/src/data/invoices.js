// Sales invoices — Justyol Morocco, June-2026 snapshot from the JoyAgent Books
// handoff (Sales Invoice = revenue, recognised on delivery; VAT 20%).
// Replaced by live ERPNext Sales Invoice queries later.

const pick = (l, en, ar, fr) => (l === "ar" ? ar : l === "fr" ? fr : en);

export const INV_STATUS = {
  paid:    { bg: "#ecfdf5", fg: "#047857", bd: "#a7f3d0", en: "Paid", ar: "مدفوعة", fr: "Payée" },
  overdue: { bg: "#fef2f2", fg: "#be123c", bd: "#fecaca", en: "Overdue", ar: "متأخرة", fr: "En retard" },
};
export const invStatusLabel = (s, l) => { const x = INV_STATUS[s] || INV_STATUS.paid; return x[l] || x.en; };

const f2 = (n) => n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const RAW = [
  { id: "BTB2026003167144", customer: "زكرياء الرحماني", date: "21 Jun 2026", status: "paid", track: "Cathedis", pay: "PAY-22491",
    items: [["Set de 12 pots à épices avec support", 1, 107.5]] },
  { id: "BTB2026003154001", customer: "Salsabil El Kati", date: "19 Jun 2026", status: "overdue", track: "Cathedis", pay: "—",
    items: [["Set 4 boîtes de rangement 6 L", 1, 101], ["Set 2 bouteilles d’huile en verre 750", 1, 122.33]] },
  { id: "BTB2026003168233", customer: "Lachhed najia", date: "20 Jun 2026", status: "paid", track: "Cathedis", pay: "PAY-22493",
    items: [["Set 12 contenants carrés 1205 ml", 1, 107.5]] },
  { id: "BTB2026003165980", customer: "Siham Elfilali", date: "20 Jun 2026", status: "paid", track: "Cathedis", pay: "PAY-22475",
    items: [["Organisateur de cuisine 3 niveaux", 1, 248.33]] },
  { id: "BTB2026003159042", customer: "Khadija", date: "18 Jun 2026", status: "overdue", track: "Cathedis", pay: "—",
    items: [["Set de 12 contenants 1205 ml", 1, 124.17]] },
];

// Derive net / VAT / gross from line items.
export const INVOICES = RAW.map((d) => {
  const net = Math.round(d.items.reduce((a, it) => a + it[1] * it[2], 0) * 100) / 100;
  const vat = Math.round(net * 0.2 * 100) / 100;
  const gross = Math.round((net + vat) * 100) / 100;
  return { ...d, net, vat, gross,
    lines: d.items.map((it) => ({ name: it[0], qty: it[1], rate: f2(it[2]), amount: f2(it[1] * it[2]) })) };
});

export const findInvoice = (id) => INVOICES.find((i) => i.id === id) || null;
export const fmt2 = f2;

// Header tiles for the list (real June figures).
export function invoiceTiles(l) {
  return [
    { label: pick(l, "Invoices · June", "فواتير · يونيو", "Factures · juin"), value: "6,038", color: "#1c1917" },
    { label: pick(l, "Net revenue", "إيراد صافٍ", "Revenu net"), value: "933K", color: "#047857" },
    { label: pick(l, "VAT output", "ضريبة مُحصَّلة", "TVA collectée"), value: "209K", color: "#b45309" },
    { label: pick(l, "Overdue", "متأخرة", "En retard"), value: "19", color: "#be123c" },
  ];
}

// Posted journal for an invoice (revenue recognition on delivery).
export function invoiceJournal(inv) {
  if (!inv) return [];
  return [
    { acc: "120.01 Debtors – JM", dr: f2(inv.gross), cr: "" },
    { acc: "600.002 Good Sales at Morocco", dr: "", cr: f2(inv.net) },
    { acc: "391.620 VAT %20 (MAD)", dr: "", cr: f2(inv.vat) },
  ];
}
