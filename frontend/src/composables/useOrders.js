import api from "@/services/api";
import { iniOf } from "@/composables/useLive";
import { findOrder, orderDims, orderTimeline, orderStageJournals } from "@/data/orders";
import { useCreated } from "@/composables/useCreated";

// Order detail: live ERPNext (get_order) with sample fallback. Returns the full
// view-model the page binds to ({ o, dims, timeline, journal }) so the template
// is identical whether the data is live or sample.

const L = (l, en, ar, fr) => (l === "ar" ? ar : l === "fr" ? fr : en);
const intFmt = (n) => Math.round(Number(n) || 0).toLocaleString("en-US");
const fmt2 = (n) => (n ? Number(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "");

// The COD lifecycle, in order. `done` flags every stage up to the current state.
const STAGES = [
  { s: "placed", t: ["Order placed", "تسجيل الطلب", "Commande passée"], icon: "receipt" },
  { s: "confirmed", t: ["Confirmed", "تأكيد", "Confirmée"], icon: "check" },
  { s: "transit", t: ["In transit", "في الشحن", "En transit"], icon: "truck" },
  { s: "delivered", t: ["Delivered", "تم التسليم", "Livrée"], icon: "check" },
  { s: "settled", t: ["Settled · COD collected", "تسوية · تحصيل COD", "Réglée · COD encaissé"], icon: "coins" },
];
const SEQ = ["placed", "confirmed", "transit", "delivered", "settled"];

function liveVM(d, l) {
  const ci = SEQ.indexOf(d.state);
  const timeline = STAGES.map((st, i) => ({
    title: L(l, ...st.t), icon: st.icon, time: "", desc: "",
    done: ci >= 0 && i <= ci, last: i === STAGES.length - 1,
  }));

  const lines = (d.journal || []).map((j) => ({
    acc: j.acc, dr: j.dr ? fmt2(j.dr) : "", cr: j.cr ? fmt2(j.cr) : "", indent: !j.dr,
  }));
  const journal = lines.length
    ? { noJournal: false, stages: [{ stage: L(l, "Posted to GL", "مُرحّل للأستاذ", "Passé au GL"), ref: d.name, dot: "#059669", lines }] }
    : { noJournal: true, msg: L(l, "No journal yet — this order hasn't reached a posting state.", "لا قيد بعد — الطلب لم يصل لحالة ترحيل.", "Aucune écriture — la commande n'a pas atteint un état de passation.") };

  return {
    o: {
      id: d.name, customer: d.customer, av: "accent", initials: iniOf(d.customer),
      city: d.custom_shipping_city || "—", carrier: d.custom_tracking_company || "—",
      date: String(d.transaction_date || ""), value: intFmt(d.grand_total), state: d.state,
    },
    dims: [
      { k: L(l, "Sales", "المبيعات", "Ventes"), v: d.custom_sales_status || "—" },
      { k: L(l, "Logistics", "اللوجستيك", "Logistique"), v: d.custom_logistics_status || "—" },
      { k: L(l, "Shipment", "الشحن", "Expédition"), v: d.custom_track_shipment_status || "—" },
      { k: L(l, "Carrier", "الناقل", "Transporteur"), v: d.custom_tracking_company || "—" },
      { k: L(l, "Tracking", "التتبّع", "Suivi"), v: d.custom_tracking_number || d.custom_awb || "—" },
      { k: L(l, "City", "المدينة", "Ville"), v: d.custom_shipping_city || "—" },
      { k: L(l, "Delivered", "مُسلّم", "Livré"), v: `${Math.round(d.per_delivered || 0)}%` },
      { k: L(l, "Billed", "مفوتر", "Facturé"), v: `${Math.round(d.per_billed || 0)}%` },
      { k: L(l, "Net", "الصافي", "Net"), v: intFmt(d.net_total) },
      { k: L(l, "VAT", "ض.ق.م", "TVA"), v: intFmt(d.total_taxes_and_charges) },
    ],
    timeline, journal,
  };
}

function sampleVM(ord, l) {
  return { o: ord, dims: orderDims(ord, l), timeline: orderTimeline(ord, l), journal: orderStageJournals(ord, l) };
}

export function useOrders() {
  const { findCreatedOrder } = useCreated();

  async function loadDetail(id, locale) {
    if (!id) return null;
    const created = findCreatedOrder(id);
    if (created) return sampleVM(created, locale);
    try {
      const d = await api.call("accounting_portal.api.sales.get_order", { name: id });
      return liveVM(d, locale);
    } catch {
      const s = findOrder(id);
      return s ? sampleVM(s, locale) : null;
    }
  }
  return { loadDetail };
}
