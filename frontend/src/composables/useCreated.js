import { reactive } from "vue";

// Records created in-session via the global Create modal. Kept reactive and
// module-scoped so the Sales list + order detail pick them up immediately.
// (Persistence lands when the Create forms are wired to ERPNext.)
const createdOrders = reactive([]);
let seq = 0;
const AVS = ["rose", "sky", "amber", "emerald", "violet", "accent"];

function initials(name) {
  return (name || "?").trim().split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
}

/** Create a COD sales order from the modal form; net/VAT derive from gross value. */
export function addOrder({ customer, value, city, item }) {
  const gross = Number(value) || 0;
  const net = Math.round((gross / 1.2) * 100) / 100;
  const vat = Math.round((gross - net) * 100) / 100;
  const id = "YC-" + String(900200 + ++seq);
  const o = {
    id, customer, city: city || "—", item: item || "—",
    value: gross, net, vat, cost: Math.round(gross * 0.35 * 100) / 100,
    carrier: "Cathedis", state: "confirmed", date: "today",
    salesStatus: "Confirmed", logiStatus: "Pending", trackStatus: "Pending",
    initials: initials(customer), av: AVS[seq % AVS.length], created: true,
  };
  createdOrders.unshift(o);
  return o;
}

export function findCreatedOrder(id) { return createdOrders.find((o) => o.id === id) || null; }

export function useCreated() { return { createdOrders, addOrder, findCreatedOrder }; }
