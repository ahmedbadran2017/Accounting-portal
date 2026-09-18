// Create an item from inside a picker, the way the Desk's link field offers
// "Create a new Item" when what you typed matches nothing.
//
// The accountant types the code off the supplier's invoice. If it is a new
// article — a desk, a fee, a subscription — the list comes back empty and the
// line stays blank: she has to leave the bill, open Items, create it, come back
// and start the line again. This keeps her on the bill.
//
// It creates a NON-STOCK item, through api/items.create_service_item, which is
// audited and reversible while the item is unused. Anything that has to move
// through a warehouse is not a two-field decision and belongs in Items.
import { ref } from "vue";
import api from "@/services/api";

export function useQuickItem() {
  const form = ref(null);            // null = closed; otherwise the draft
  const opts = ref({ groups: [], uoms: [] });
  const busy = ref(false);
  const error = ref("");
  let loaded = false;

  async function open(code) {
    error.value = "";
    form.value = { item_code: (code || "").trim(), item_name: "", item_group: "", uom: "Nos" };
    if (!loaded) {
      try {
        const o = await api.call("accounting_portal.api.items.service_item_options", {}) || {};
        opts.value = { groups: o.groups || [], uoms: o.uoms || [] };
        loaded = true;
      } catch (e) { error.value = String(e?.message || e).slice(0, 140); }
    }
    if (!form.value.item_group) form.value.item_group = opts.value.groups[0] || "";
    if (!opts.value.uoms.includes(form.value.uom)) form.value.uom = opts.value.uoms[0] || "Nos";
  }
  function close() { form.value = null; error.value = ""; }

  // Resolves to the created item in the shape the pickers already render, so the
  // caller can select it straight onto the line.
  async function create() {
    const f = form.value;
    if (!f || !f.item_code || !f.item_group) { error.value = "Code and group are required"; return null; }
    busy.value = true; error.value = "";
    try {
      await api.call("accounting_portal.api.items.create_service_item", {
        item_code: f.item_code, item_name: f.item_name || f.item_code,
        item_group: f.item_group, uom: f.uom });
      const made = { item_code: f.item_code, item_name: f.item_name || f.item_code,
                     sku: "", image: "", description: "", variant_of: null, rate: 0 };
      close();
      return made;
    } catch (e) { error.value = String(e?.message || e).slice(0, 200); return null; }
    finally { busy.value = false; }
  }
  return { form, opts, busy, error, open, close, create };
}
