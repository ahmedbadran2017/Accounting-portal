import api from "@/services/api";
import { findBill } from "@/data/purchases";

// Bill detail: live ERPNext (get_bill — 3-way match legs + real posted journal)
// with sample fallback. Returns { b, matched, legs, journal }.

const f2 = (n) => (n || n === 0 ? Number(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "");
const pick = (l, en, ar, fr) => (l === "ar" ? ar : l === "fr" ? fr : en);

function legsFor(matched, l) {
  return [
    { key: "po", label: pick(l, "Purchase order", "أمر الشراء", "Bon de commande"), ok: true, state: pick(l, "Linked", "مرتبط", "Lié") },
    { key: "grn", label: pick(l, "Goods receipt", "سند الاستلام", "Réception"), ok: matched, state: matched ? pick(l, "Received", "مستلَم", "Reçu") : pick(l, "Qty short", "نقص كمية", "Qté manquante") },
    { key: "inv", label: pick(l, "Invoice", "الفاتورة", "Facture"), ok: matched, state: matched ? pick(l, "Matched", "مطابقة", "Rapprochée") : pick(l, "Price gap", "فرق سعر", "Écart prix") },
  ];
}

function liveVM(d, l) {
  const matched = !!(d.match && d.match.matched);
  const sign = d.is_return ? "-" : "";
  return {
    b: {
      id: d.name, vendor: d.supplier, date: String(d.posting_date || ""), bill_no: d.bill_no || "",
      amount: sign + Math.round(Math.abs(Number(d.grand_total) || 0)).toLocaleString("en-US"),
      currency: d.currency || "MAD",
      status: d.status_norm || "overdue", match: matched ? "ok" : "exc",
    },
    matched,
    items: (d.items || []).map((it) => ({ name: it.name, code: it.item_code, sku: it.sku, image: it.image, qty: it.qty, rate: f2(it.rate), amount: f2(it.amount), po: it.po, pr: it.pr })),
    legs: legsFor(matched, l),
    related: { orders: d.related_orders || [], receipts: d.related_receipts || [], payments: d.related_payments || [] },
    journal: (d.journal || []).map((j) => ({ acc: j.acc, dr: j.dr ? f2(j.dr) : "", cr: j.cr ? f2(j.cr) : "" })),
  };
}

function sampleVM(bill, l) {
  if (!bill) return null;
  const matched = bill.match === "ok";
  const isReturn = bill.amount.includes("-");
  const amt = bill.amount.replace(/[^0-9.\-]/g, "");
  const journal = isReturn
    ? [{ acc: "320.01 Creditors", dr: amt.replace("-", ""), cr: "" }, { acc: "71.801 Cost of Goods Sold / Stock", dr: "", cr: amt.replace("-", "") }]
    : [{ acc: "153.01 Stock in Hand / Expense", dr: amt, cr: "" }, { acc: "320.01 Creditors", dr: "", cr: amt }];
  return { b: bill, matched, legs: legsFor(matched, l), related: { orders: [], receipts: [], payments: [] }, journal };
}

export function useBills() {
  async function loadDetail(id, locale) {
    if (!id) return null;
    try {
      const d = await api.call("accounting_portal.api.purchases.get_bill", { name: id });
      return liveVM(d, locale);
    } catch {
      return sampleVM(findBill(id), locale);
    }
  }
  return { loadDetail };
}
