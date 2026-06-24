import { ref } from "vue";
import api from "@/services/api";
import { CUSTOMERS, findCustomer, customerDetail } from "@/data/customers";

// Live ⇄ sample bridge for the Customers cycle. Each call tries the ERPNext
// endpoint first; if it's not reachable yet (app not installed / 403 pre-login)
// it falls back to the June sample so the UI always renders. `live` reflects
// which path served the last call — surfaced as a small badge in the UI.
const live = ref(null); // null = unknown, true = live ERPNext, false = sample

const L = (l, en, ar, fr) => (l === "ar" ? ar : l === "fr" ? fr : en);

// Where a ledger voucher opens. Only types with a detail screen are clickable.
function voucherRoute(type, doc) {
  if (type === "Sales Invoice") return { path: "/accounting/sales/invoices", query: { id: doc } };
  if (type === "Payment Entry") return { path: "/accounting/sales/payments", query: { id: doc } };
  return null;
}

/** Map the live get_customer payload into the detail view-model the page renders. */
function normalizeDetail(d, l) {
  const credit = d.store_credit ? "+" + Math.round(d.store_credit).toLocaleString() : "0";
  return {
    id: d.name,
    name: d.customer_name || d.name,
    av: "accent",
    city: d.city || "—",
    phone: d.mobile_no || "—",
    email: d.email_id || "—",
    since: d.since || "—",
    credit,
    creditLabel: L(l, "Store credit", "رصيد المتجر", "Avoir client"),
    sinceLabel: L(l, "since", "منذ", "depuis"),
    stats: [
      { label: "LTV", value: Math.round(d.stats.ltv).toLocaleString() + " MAD" },
      { label: L(l, "Orders", "الطلبات", "Commandes"), value: String(d.stats.orders) },
      { label: L(l, "Delivery", "التسليم", "Livraison"), value: d.stats.delivery_rate + "%" },
      { label: "RTO", value: d.stats.rto_rate + "%" },
    ],
    connections: [
      { label: L(l, "Orders", "الطلبات", "Commandes"), value: String(d.connections.orders), go: { module: "sales", sub: "orders", customer: d.name } },
      { label: L(l, "Invoices", "الفواتير", "Factures"), value: String(d.connections.invoices), go: { module: "sales", sub: "invoices", customer: d.name } },
      { label: L(l, "Receipts", "السندات", "Reçus"), value: String(d.connections.receipts), go: { module: "sales", sub: "payments", customer: d.name } },
      { label: L(l, "Returns", "الإرجاع", "Retours"), value: String(d.connections.returns), go: { module: "sales", sub: "credits", customer: d.name } },
    ],
    contact: [
      { k: L(l, "Phone", "الهاتف", "Téléphone"), v: d.mobile_no || "—" },
      { k: L(l, "Email", "البريد", "E-mail"), v: d.email_id || "—" },
      { k: L(l, "City", "المدينة", "Ville"), v: d.city || "—" },
      { k: L(l, "Customer group", "مجموعة العميل", "Groupe"), v: d.customer_group || "—" },
      { k: L(l, "Segment (RFM)", "الشريحة (RFM)", "Segment (RFM)"), v: d.segment + (d.segment_computed ? " ·~" : "") },
      { k: L(l, "Lifecycle", "دورة الحياة", "Cycle de vie"), v: d.lifecycle },
    ],
    raw: { name: d.name, customer_name: d.customer_name || d.name, phone: d.mobile_no || "", email: d.email_id || "", city: d.city && d.city !== "—" ? d.city : "" },
    // No dedicated activity feed server-side yet → derive it from the ledger.
    activity: (d.ledger || []).slice(0, 4).map((e) => ({
      icon: e.type === "Payment Entry" ? "coins" : "receipt",
      iconBg: e.type === "Payment Entry" ? "#eff6ff" : "#faf6f4",
      iconColor: e.type === "Payment Entry" ? "#0369a1" : "#a33a22",
      title: e.type === "Payment Entry" ? L(l, "Payment received", "تم استلام دفعة", "Paiement reçu") : L(l, "Invoice issued", "صدرت فاتورة", "Facture émise"),
      meta: e.doc, time: e.date,
    })),
    ledger: (d.ledger || []).map((e) => ({
      date: e.date, doc: e.doc, type: e.type,
      dr: e.dr ? Number(e.dr).toFixed(2) : "", cr: e.cr ? Number(e.cr).toFixed(2) : "",
      bal: e.balance != null ? Number(e.balance).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "",
      go: voucherRoute(e.type, e.doc),
    })),
    contactTitle: L(l, "Contact & segment", "التواصل والشريحة", "Contact & segment"),
    activityTitle: L(l, "Recent activity", "النشاط الأخير", "Activité récente"),
    ledgerTitle: L(l, "Customer ledger", "كشف حساب العميل", "Grand livre client"),
  };
}

export function useCustomers() {
  async function loadList(search) {
    try {
      const rows = await api.call("accounting_portal.api.customers.list_customers", { search: search || null });
      live.value = true;
      return rows;
    } catch {
      live.value = false;
      const q = (search || "").toLowerCase();
      return q ? CUSTOMERS.filter((c) => (c.name + c.city).toLowerCase().includes(q)) : CUSTOMERS;
    }
  }
  async function loadDetail(name, locale) {
    try {
      const d = await api.call("accounting_portal.api.customers.get_customer", { name });
      live.value = true;
      return normalizeDetail(d, locale);
    } catch {
      live.value = false;
      return customerDetail(findCustomer(name), locale);
    }
  }
  /** Create on the server; throws on failure so the caller can surface it. */
  function createCustomer(form) {
    return api.call("accounting_portal.api.customers.create_customer", form);
  }
  /** Edit core customer data (name/phone/email/city); throws on failure. */
  function updateCustomer(form) {
    return api.call("accounting_portal.api.customers.update_customer", form);
  }
  return { loadList, loadDetail, createCustomer, updateCustomer, live };
}
