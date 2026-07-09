import api from "@/services/api";
import { findInvoice, invoiceJournal, invStatusFromRow } from "@/data/invoices";

// Invoice detail: live ERPNext (get_invoice — lines, totals, payment, posted
// journal) with sample fallback. Returns { inv, paid, journal }.

const f2 = (n) => (n || n === 0 ? Number(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "");

function liveVM(d) {
  const paid = (Number(d.outstanding_amount) || 0) <= 0;
  return {
    inv: {
      id: d.name, customer: d.customer, date: String(d.posting_date || ""),
      city: d.city && d.city !== "—" ? d.city : "", phone: d.phone || "",
      status: invStatusFromRow(d), is_return: !!d.is_return, outstanding: Number(d.outstanding_amount) || 0,
      net: d.net_total, vat: d.total_taxes_and_charges, gross: d.grand_total,
      credit_note: d.credit_note || null,
      lines: (d.lines || []).map((l) => ({ name: l.name, image: l.image, qty: l.qty, rate: f2(l.rate), amount: f2(l.amount) })),
      track: "Cathadis", pay: "COD",
    },
    paid,
    related: { orders: d.related_orders || [], deliveries: d.related_deliveries || [], payments: d.related_payments || [] },
    journal: (d.journal || []).map((j) => ({ acc: j.acc, dr: j.dr ? f2(j.dr) : "", cr: j.cr ? f2(j.cr) : "" })),
  };
}

function sampleVM(inv) {
  return { inv, paid: inv?.status === "paid", related: { orders: [], deliveries: [], payments: [] }, journal: invoiceJournal(inv) };
}

export function useInvoices() {
  async function loadDetail(id) {
    if (!id) return null;
    try {
      const d = await api.call("accounting_portal.api.sales.get_invoice", { name: id });
      return liveVM(d);
    } catch {
      const s = findInvoice(id);
      return s ? sampleVM(s) : null;
    }
  }
  return { loadDetail };
}
