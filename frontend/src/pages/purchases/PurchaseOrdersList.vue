<template>
  <div class="space-y-3">
    <DateFilterBar :df="df" />
    <div class="bg-white rounded-[14px] border border-line shadow-card overflow-hidden">
      <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
        <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#eff6ff"><Icon name="cart" :size="14" color="#0369a1" /></span>
        <span class="text-[13px] font-semibold">{{ L("Purchase orders", "أوامر الشراء", "Commandes d'achat") }}</span>
        <LiveBadge :live="isLive" />
        <span class="hidden lg:inline text-[11px] text-ink-muted">
          {{ L("Every order — receiving and billing tracked separately",
                "كل الأوامر — الاستلام والفوترة كل واحد لوحده",
                "Toutes les commandes — réception et facturation suivies séparément") }}
        </span>
        <div class="relative ms-auto">
          <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
          <input v-model.trim="st.search.value" :placeholder="L('Search order / vendor…','بحث بالرقم أو المورّد…','Rechercher…')" class="fld fld-md fld-sunk w-44 sm:w-64" />
        </div>
        <UiButton v-if="canWrite" variant="create" size="sm" icon="plus" @click="$emit('new')">
          {{ L("New PO", "أمر شراء", "Nouvelle CA") }}
        </UiButton>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead>
            <tr style="background:#fafaf9">
              <th class="w-8 px-3"><input type="checkbox" :checked="st.allSelected.value" @change="st.toggleAll()" /></th>
              <th v-for="c in cols" :key="c.key"
                  class="px-4 py-2.5 text-[11px] font-bold uppercase tracking-wider text-ink-muted whitespace-nowrap select-none"
                  :class="[c.align === 'e' ? 'text-end' : 'text-start', c.sort ? 'cursor-pointer hover:text-ink-2' : '']"
                  @click="c.sort && st.setSort(c.sort)">
                <span class="inline-flex items-center gap-1" :class="c.align === 'e' ? 'flex-row-reverse' : ''">{{ c.label }}
                  <Icon v-if="c.sort && st.sortField.value === c.sort" name="chevDown" :size="11"
                        :class="st.sortDir.value === 'asc' ? 'rotate-180' : ''" color="#0b5c4f" /></span>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="o in rows" :key="o.id" class="border-t border-line-hair hover:bg-app-warm/70 cursor-pointer" @click="open(o.id)">
              <td class="px-3 py-2" @click.stop><input type="checkbox" :checked="st.selected.value.has(o.id)" @change="st.toggle(o.id)" /></td>
              <td class="px-4 py-2.5 font-mono font-medium whitespace-nowrap">{{ o.id }}</td>
              <td class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ o.date || "—" }}</td>
              <td class="px-4 py-2.5 truncate max-w-[200px]">{{ o.vendor }}</td>
              <!-- Received and billed are two separate journeys and an order can
                   be finished on one and untouched on the other — which is
                   exactly the state that used to make an order disappear. -->
              <td class="px-4 py-2.5"><Progress :pct="o.received" :label="L('received','مستلم','reçu')" /></td>
              <td class="px-4 py-2.5"><Progress :pct="o.billed" :label="L('billed','مفوتر','facturé')" /></td>
              <td class="px-4 py-2.5 text-end font-semibold tnum whitespace-nowrap">{{ o.currency }} {{ fmt(o.amount) }}</td>
              <td class="px-4 py-2.5">
                <span class="inline-block text-[11px] font-medium px-2 py-0.5 rounded-badge border whitespace-nowrap"
                      :style="chip(o)">{{ statusLabel(o) }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <TableLoading v-if="st.loading.value" />
      <div v-else-if="!rows.length" class="py-12 text-center text-[12px] text-ink-muted">
        {{ L("No purchase orders match your filters.", "لا توجد أوامر شراء مطابقة.", "Aucune commande.") }}
      </div>

      <ListToolbar v-model:status="listStatus" v-model:pageSize="listPageSize" v-model:owner="listOwner"
                   owner-doctype="Purchase Order" :total="st.total.value" export-key="purchase_orders"
                   :export-filters="exportFilters" :extra-statuses="extraStatuses" />
      <ServerPager :t="st" />
      <BulkBar :t="st" :actions="bulkActions" filename="purchase-orders" />
    </div>
  </div>
</template>

<script setup>
// The purchase-order list the portal never had.
//
// Orders were reachable only through the procure-to-pay strip, and its "To buy"
// stage is defined as `per_received < 100`. The moment an order was fully
// received it left that bucket — and appeared nowhere else. On Justyol Morocco
// in 2026 that hid 1,696 orders still waiting to be billed plus 228 completed
// ones: 1,924 documents, 14.7M, findable on the Desk and not here. PUR-ORD-2026-00033
// was one of them.
//
// The strip answers "what is the pipeline doing". This answers "where is that
// order". They are different questions and the second had no screen.
import { computed, h, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import UiButton from "@/components/UiButton.vue";
import LiveBadge from "@/components/LiveBadge.vue";
import TableLoading from "@/components/TableLoading.vue";
import ServerPager from "@/components/ServerPager.vue";
import ListToolbar from "@/components/ListToolbar.vue";
import BulkBar from "@/components/BulkBar.vue";
import DateFilterBar from "@/components/DateFilterBar.vue";
import { useBulkDocs } from "@/composables/useBulkDocs";
import { useServerTable } from "@/composables/useServerTable";
import { usePersistedRef } from "@/composables/usePersistedRef";
import { useDateFilter } from "@/composables/useDateFilter";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";
import { useAuth } from "@/composables/useAuth";
import api from "@/services/api";

defineEmits(["new"]);
const { locale } = useI18n();
const route = useRoute();
const router = useRouter();
const { entityId } = useUi();
const { can } = useAuth();
const canWrite = computed(() => can("post_entries"));
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US", { maximumFractionDigits: 2 });

// A bar reads faster than "100.0" in a column you scan down.
const Progress = {
  props: { pct: { type: Number, default: 0 }, label: { type: String, default: "" } },
  setup(p) {
    return () => {
      const v = Math.max(0, Math.min(100, Number(p.pct) || 0));
      const c = v >= 100 ? "#047857" : v > 0 ? "#b45309" : "#d6d3d1";
      return h("div", { class: "flex items-center gap-1.5 min-w-[92px]", title: `${v}% ${p.label}` }, [
        h("span", { class: "h-1.5 flex-1 rounded-full overflow-hidden", style: "background:#eee9e3" },
          [h("span", { class: "block h-full rounded-full", style: `width:${v}%;background:${c}` })]),
        h("span", { class: "text-[10px] tnum w-8 text-end", style: `color:${c}` }, v ? `${v}%` : "—"),
      ]);
    };
  },
};

const cols = [
  { key: "id", label: L("Order", "الأمر", "Commande"), align: "s", sort: "id" },
  { key: "date", label: L("Date", "التاريخ", "Date"), align: "s", sort: "date" },
  { key: "vendor", label: L("Vendor", "المورّد", "Fournisseur"), align: "s", sort: "supplier" },
  { key: "received", label: L("Received", "المستلم", "Reçu"), align: "s" },
  { key: "billed", label: L("Billed", "المفوتر", "Facturé"), align: "s" },
  { key: "amount", label: L("Amount", "المبلغ", "Montant"), align: "e", sort: "amount" },
  { key: "status", label: L("Status", "الحالة", "Statut"), align: "s" },
];

const isLive = ref(null);
const df = useDateFilter("purchase_orders", (f) => st.setFilters(f));
const { actions: bulkActions } = useBulkDocs("Purchase Order", () => st);
const st = useServerTable(
  (params) => api.call("accounting_portal.api.purchases.list_purchase_orders",
    { company: currentCompany(), ...params }).then((r) => { isLive.value = true; return r; }),
  { pageSize: 25, sortField: "date", sortDir: "desc", filters: df.filterValue(), storeKey: "purchase_orders" },
);

const listStatus = usePersistedRef("ap_ls_purchase_orders", "open");
const listPageSize = usePersistedRef("ap_lps_purchase_orders", 25);
const listOwner = usePersistedRef("ap_lo_purchase_orders", "");
const extraStatuses = [
  { k: "toreceive", label: () => L("To receive", "للاستلام", "À recevoir") },
  { k: "tobill", label: () => L("To bill", "للفوترة", "À facturer") },
  { k: "completed", label: () => L("Completed", "مكتمل", "Terminées") },
  { k: "closed", label: () => L("Closed", "مقفول", "Clôturées") },
];
const exportFilters = computed(() => ({
  ...st.filters.value, search: st.search.value || undefined,
  status: listStatus.value, owner: listOwner.value || undefined,
}));
let _lsFirst = true;
watch([listStatus, listPageSize, listOwner], () => {
  st.pageSize.value = listPageSize.value;
  if (_lsFirst) {
    _lsFirst = false;
    st.filters.value = { ...st.filters.value, status: listStatus.value, owner: listOwner.value || undefined };
    return;
  }
  st.setFilters({ status: listStatus.value, owner: listOwner.value || undefined });
}, { immediate: true });

watch(() => route.query.supplier, (v) => { if (v) st.search.value = String(v); }, { immediate: true });
st.load();
watch(entityId, () => { st.page.value = 1; st.load(); });

const rows = computed(() => (st.rows.value || []).map((r) => ({
  id: r.name, date: String(r.date || ""), vendor: r.supplier_name || r.supplier,
  received: Number(r.per_received) || 0, billed: Number(r.per_billed) || 0,
  amount: Number(r.amount) || 0, currency: r.currency || "MAD",
  status: r.status, docstatus: r.docstatus,
})));

const CHIP = {
  "To Receive and Bill": ["#eff6ff", "#0369a1", "#bfdbfe"],
  "To Receive":          ["#fffbeb", "#b45309", "#fde68a"],
  "To Bill":             ["#fffbeb", "#b45309", "#fde68a"],
  Completed:             ["#ecfdf5", "#047857", "#a7f3d0"],
  Closed:                ["#fafaf9", "#57534e", "#e7e5e4"],
  Draft:                 ["#fafaf9", "#57534e", "#e7e5e4"],
  Cancelled:             ["#fef2f2", "#b91c1c", "#fecaca"],
};
const LABEL = {
  "To Receive and Bill": () => L("To receive & bill", "للاستلام والفوترة", "À recevoir & facturer"),
  "To Receive":          () => L("To receive", "للاستلام", "À recevoir"),
  "To Bill":             () => L("To bill", "للفوترة", "À facturer"),
  Completed:             () => L("Completed", "مكتمل", "Terminée"),
  Closed:                () => L("Closed", "مقفول", "Clôturée"),
  Draft:                 () => L("Draft", "مسودة", "Brouillon"),
  Cancelled:             () => L("Cancelled", "ملغي", "Annulée"),
};
const statusLabel = (o) => (LABEL[o.status] ? LABEL[o.status]() : o.status || "—");
function chip(o) {
  const [bg, color, borderColor] = CHIP[o.status] || CHIP.Draft;
  return { background: bg, color, borderColor };
}

function open(id) {
  router.push({ path: "/accounting/purchases/pos", query: { id } });
}
</script>
