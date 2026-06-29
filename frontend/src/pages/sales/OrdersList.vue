<template>
  <div class="space-y-3.5">
    <!-- CFO summary strip (month-to-date) -->
    <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
      <StatCard v-for="m in summaryCards" :key="m.label" :label="m.label" :value="m.value" :sub="m.sub" :icon="m.icon" :color="m.color" :glow="m.glow" :tint="m.tint" :value-color="m.color" />
    </div>

    <!-- State-machine strip — LIVE counts, click to filter server-side -->
    <div class="bg-white border border-line rounded-[14px] p-3.5 shadow-card overflow-x-auto">
      <div class="flex items-center gap-1 min-w-[680px]">
        <template v-for="(s, i) in MACHINE" :key="s">
          <button class="flex flex-col items-start flex-1 px-3 py-1.5 rounded-lg" :class="filterState === s ? 'bg-app-warm' : 'hover:bg-app-warm/60'" @click="toggleState(s)">
            <span class="text-[18px] font-bold tnum leading-none" :style="{ color: filterState === s ? STATE_META[s].fg : '#1c1917' }">{{ (stateCounts[s] || 0).toLocaleString() }}</span>
            <span class="text-[10.5px] font-semibold mt-[3px]" :class="filterState === s ? 'text-accent-dark' : 'text-ink-3'">{{ stateLabel(s, locale) }}</span>
          </button>
          <Icon v-if="i < MACHINE.length - 1" name="chev" :size="15" color="#d6d3d1" class="flex-shrink-0 rtl:rotate-180" />
        </template>
      </div>
    </div>

    <!-- Toolbar -->
    <div class="flex items-center gap-2 flex-wrap">
      <div class="relative flex-1 max-w-xs">
        <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
        <input v-model.trim="st.search.value" :placeholder="t('module.search')" class="w-full h-9 bg-white border border-line-2 rounded-[10px] ps-9 pe-3 text-[12.5px] focus:outline-none focus:border-accent/40" />
      </div>
      <span v-if="isLive !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="isLive ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ isLive ? lbl("Live","مباشر","Live") : lbl("Sample","عيّنة","Échant.") }}</span>
      <div class="flex items-center gap-1 bg-app-warm/60 rounded-chip p-0.5" :title="lbl('Active = confirmed onward','النشطة = من التأكيد فصاعدًا','Actives = à partir de la confirmation')">
        <button class="px-2.5 py-1 rounded-lg text-[11px] font-semibold" :class="activeOnly ? 'bg-white shadow-card text-ink' : 'text-ink-3'" @click="setActive(true)">{{ lbl("Active","النشطة","Actives") }}</button>
        <button class="px-2.5 py-1 rounded-lg text-[11px] font-semibold" :class="!activeOnly ? 'bg-white shadow-card text-ink' : 'text-ink-3'" @click="setActive(false)">{{ lbl("All","الكل","Toutes") }}</button>
      </div>
      <span v-if="filterState" class="inline-flex items-center gap-1 text-[11px] font-semibold px-2.5 py-1 rounded-chip" :style="{ background: STATE_META[filterState].bg, color: STATE_META[filterState].fg }">
        {{ stateLabel(filterState, locale) }}<button class="opacity-70 hover:opacity-100" @click="toggleState(filterState)"><Icon name="close" :size="12" /></button>
      </span>
      <span v-if="customerFilter" class="inline-flex items-center gap-1.5 text-[11px] font-semibold px-2.5 py-1 rounded-chip" style="background:#eff6ff;color:#0369a1">
        <Icon name="user" :size="12" />{{ customerFilter }}<button class="opacity-70 hover:opacity-100" @click="clearCustomer"><Icon name="close" :size="12" /></button>
      </span>
      <button class="inline-flex items-center gap-1.5 text-[12px] font-semibold text-white bg-brand hover:bg-brand-dark px-3 py-1.5 rounded-chip shadow-brand ms-auto" @click="$emit('new')">
        <Icon name="plus" :size="14" />{{ t("module.new") }}
      </button>
    </div>

    <!-- Date filter (by order date) -->
    <div class="flex items-center gap-1.5 flex-wrap -mt-1">
      <Icon name="clock" :size="13" color="#a8a29e" />
      <button v-for="p in DATE_PRESETS" :key="p.key" @click="setDatePreset(p.key)" class="text-[11px] font-semibold px-2.5 py-1 rounded-full border transition" :class="datePreset === p.key ? 'bg-ink text-white border-ink' : 'bg-white text-ink-3 border-line-2 hover:bg-app-warm'">{{ p.label() }}</button>
      <template v-if="datePreset === 'range'">
        <input type="date" v-model="dateFrom" @change="applyRange" class="h-7 border border-line-2 rounded-chip px-2 text-[11px] focus:outline-none focus:border-accent/40" />
        <span class="text-ink-muted text-[11px]">→</span>
        <input type="date" v-model="dateTo" @change="applyRange" class="h-7 border border-line-2 rounded-chip px-2 text-[11px] focus:outline-none focus:border-accent/40" />
      </template>
    </div>

    <!-- Table -->
    <div class="bg-white rounded-card border border-line overflow-hidden shadow-card">
      <div class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead>
            <tr style="background:#fafaf9">
              <th v-for="c in cols" :key="c.key" class="px-4 py-2.5 text-[10px] font-bold uppercase tracking-wider text-ink-muted whitespace-nowrap select-none" :class="[c.align === 'e' ? 'text-end' : 'text-start', c.sort ? 'cursor-pointer hover:text-ink-2' : '']" @click="c.sort && st.setSort(c.sort)">
                <span class="inline-flex items-center gap-1" :class="c.align === 'e' ? 'flex-row-reverse' : ''">{{ c.label }}
                  <Icon v-if="c.sort && st.sortField.value === c.sort" name="chevDown" :size="11" :class="st.sortDir.value === 'asc' ? 'rotate-180' : ''" color="#0b5c4f" /></span>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="o in displayRows" :key="o.id" class="border-t border-line-hair hover:bg-app-warm/70 cursor-pointer" @click="open(o.id)">
              <td class="px-4 py-2.5 font-mono font-semibold text-ink whitespace-nowrap">{{ o.id }}</td>
              <td class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ o.date || "—" }}</td>
              <td class="px-4 py-2.5"><span class="flex items-center gap-2"><span class="w-6 h-6 rounded-full grid place-items-center text-white text-[9px] font-bold flex-shrink-0" :style="{ background: AV[o.av] }">{{ o.initials }}</span><span class="truncate max-w-[160px]">{{ o.customer }}</span></span></td>
              <td class="px-4 py-2.5 text-ink-2 whitespace-nowrap">{{ o.city || "—" }}</td>
              <td class="px-4 py-2.5 text-ink-2 whitespace-nowrap">{{ o.carrier || "—" }}</td>
              <td class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ o.trackStatus }}</td>
              <td class="px-4 py-2.5"><span class="inline-block text-[10px] font-bold px-2 py-0.5 rounded-badge border" :style="{ background: STATE_META[o.state].bg, color: STATE_META[o.state].fg, borderColor: STATE_META[o.state].bd }">{{ stateLabel(o.state, locale) }}</span></td>
              <td class="px-4 py-2.5"><span class="inline-block text-[10px] font-bold px-2 py-0.5 rounded-badge border" :style="postingInfo(o.state, locale).posted ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#f5f5f4;color:#a8a29e;border-color:#e7e5e4'">{{ postingInfo(o.state, locale).label }}</span></td>
              <td class="px-4 py-2.5 text-end font-bold tnum whitespace-nowrap">{{ fmtMAD(o.value) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <TableLoading v-if="st.loading.value" />
      <div v-else-if="!displayRows.length" class="py-14 text-center text-[12px] text-ink-muted">{{ lbl("No orders match your filters.", "لا توجد طلبات مطابقة.", "Aucune commande.") }}</div>

      <!-- Server pager -->
      <div class="flex items-center justify-between px-4 py-3 border-t border-line-hair text-[12px]">
        <span class="text-ink-muted">{{ lbl("Showing","عرض","Affichage") }} <b>{{ st.rangeStart.value }}–{{ st.rangeEnd.value }}</b> {{ lbl("of","من","sur") }} <b>{{ st.total.value.toLocaleString() }}</b></span>
        <div class="flex items-center gap-1.5">
          <button class="h-8 px-3 rounded-[8px] text-[11.5px] font-semibold border border-line-2 disabled:opacity-40 inline-flex items-center gap-1" :disabled="st.page.value <= 1 || st.loading.value" @click="st.prev()"><Icon name="arrow" :size="12" class="rtl:rotate-180" />{{ lbl("Prev","السابق","Préc.") }}</button>
          <span class="text-ink-3 px-1">{{ st.page.value }} / {{ st.totalPages.value }}</span>
          <button class="h-8 px-3 rounded-[8px] text-[11.5px] font-semibold border border-line-2 disabled:opacity-40 inline-flex items-center gap-1" :disabled="st.page.value >= st.totalPages.value || st.loading.value" @click="st.next()">{{ lbl("Next","التالي","Suiv.") }}<Icon name="arrow" :size="12" class="rotate-180 rtl:rotate-0" /></button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { STATE_META, stateLabel, MACHINE, AV, postingInfo } from "@/data/orders";
import { avFor, iniOf, currentCompany } from "@/composables/useLive";
import { fmtMAD } from "@/composables/useReconciliation";
import { useServerTable } from "@/composables/useServerTable";
import { usePersistedRef } from "@/composables/usePersistedRef";
import { useUi } from "@/composables/useUi";
import api from "@/services/api";
import TableLoading from "@/components/TableLoading.vue";
import StatCard from "@/components/StatCard.vue";

defineEmits(["new"]);
const { t, locale } = useI18n();
const router = useRouter();
const route = useRoute();
const { entityId } = useUi();
const lbl = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

const customerFilter = ref(route.query.customer || null);
function clearCustomer() { customerFilter.value = null; router.replace({ path: "/accounting/sales/orders" }); st.setFilters({ customer: undefined }); }

const activeOnly = ref(true);
const filterState = ref(null);
const isLive = ref(null);

// Date filter (by order date) — persisted, applied server-side so the pipeline
// counts + totals all reflect the chosen window.
const DATE_PRESETS = [
  { key: "all", label: () => lbl("All time", "كل الوقت", "Tout") },
  { key: "month", label: () => lbl("This month", "هذا الشهر", "Ce mois") },
  { key: "lastmonth", label: () => lbl("Last month", "الشهر الماضي", "Mois dern.") },
  { key: "quarter", label: () => lbl("This quarter", "هذا الربع", "Trimestre") },
  { key: "year", label: () => lbl("This year", "هذه السنة", "Année") },
  { key: "range", label: () => lbl("Range", "نطاق", "Plage") },
];
const datePreset = usePersistedRef("ap_orders_preset", "all");
const dateFrom = usePersistedRef("ap_orders_from", "");
const dateTo = usePersistedRef("ap_orders_to", "");
function dateBounds(key) {
  const iso = (d) => d.toISOString().slice(0, 10);
  const now = new Date(), y = now.getFullYear(), m = now.getMonth();
  if (key === "month") return [iso(new Date(y, m, 1)), iso(now)];
  if (key === "lastmonth") return [iso(new Date(y, m - 1, 1)), iso(new Date(y, m, 0))];
  if (key === "quarter") { const q = Math.floor(m / 3) * 3; return [iso(new Date(y, q, 1)), iso(now)]; }
  if (key === "year") return [iso(new Date(y, 0, 1)), iso(now)];
  if (key === "range") return [dateFrom.value || null, dateTo.value || null];
  return [null, null];
}
function dateFilter() { const [fd, td] = dateBounds(datePreset.value); return { from_date: fd || undefined, to_date: td || undefined }; }

// Server-side paginated orders.
const st = useServerTable(
  (params) => api.call("accounting_portal.api.sales.list_orders", { company: currentCompany(), customer: customerFilter.value || undefined, active: activeOnly.value ? 1 : 0, state: filterState.value || undefined, ...params }).then((r) => { isLive.value = true; return r; }),
  { pageSize: 25, sortField: "date", sortDir: "desc", filters: dateFilter() },
);
st.load();

function setDatePreset(k) { datePreset.value = k; if (k !== "range") st.setFilters(dateFilter()); }
function applyRange() { if (dateFrom.value && dateTo.value) st.setFilters(dateFilter()); }
watch(entityId, () => { filterState.value = null; activeOnly.value = true; st.page.value = 1; st.load(); });

function setActive(v) { activeOnly.value = v; if (v) filterState.value = null; st.setFilters({ active: v ? 1 : 0, state: undefined }); }
function toggleState(s) {
  filterState.value = filterState.value === s ? null : s;
  if (filterState.value) activeOnly.value = false;
  st.setFilters({ state: filterState.value || undefined, active: filterState.value ? 0 : (activeOnly.value ? 1 : 0) });
}

const stateCounts = computed(() => (st.extra.value && st.extra.value.state_counts) || {});
const displayRows = computed(() => (st.rows.value || []).map((r, i) => ({
  id: r.name, customer: r.customer, date: String(r.date || ""), city: r.city, carrier: r.carrier,
  trackStatus: r.custom_track_shipment_status || "Pending", state: r.state || "placed", value: r.value,
  initials: iniOf(r.customer), av: avFor(i),
})));

const cols = [
  { key: "id", label: lbl("Order", "الطلب", "Commande"), sort: "id" },
  { key: "date", label: lbl("Date", "التاريخ", "Date"), sort: "date" },
  { key: "customer", label: lbl("Customer", "العميل", "Client"), sort: "customer" },
  { key: "city", label: lbl("City", "المدينة", "Ville") },
  { key: "carrier", label: lbl("Carrier", "الناقل", "Transporteur") },
  { key: "trackStatus", label: lbl("Shipment", "الشحن", "Expédition") },
  { key: "state", label: lbl("State", "الحالة", "État") },
  { key: "posting", label: lbl("Posting", "الترحيل", "Passation") },
  { key: "value", label: lbl("Value", "القيمة", "Valeur"), align: "e", sort: "value" },
];

// CFO month-to-date metrics.
const summary = ref(null);
api.call("accounting_portal.api.sales.orders_summary", { company: currentCompany() }).then((r) => { summary.value = r; }).catch(() => {});
const SUMMARY_ZERO = { gmv: 0, orders: 0, aov: 0, delivered_value: 0, delivery_rate: 0, pending: 0, exceptions: 0, rto_rate: 0 };
const summaryCards = computed(() => {
  const d = summary.value && summary.value.company ? summary.value : SUMMARY_ZERO;
  return [
    { label: lbl("GMV (MTD)", "إجمالي المبيعات", "GMV (mois)"), value: fmtMAD(d.gmv), color: "#1c1917", glow: "#a8a29e", tint: "#fafaf9", icon: "cart", sub: `${(d.orders || 0).toLocaleString()} ${lbl("orders", "طلب", "commandes")}` },
    { label: lbl("Avg order", "متوسط الطلب", "Panier moyen"), value: fmtMAD(d.aov), color: "#0369a1", glow: "#38bdf8", tint: "#eff6ff", icon: "scale", sub: "AOV · MAD" },
    { label: lbl("Realised", "المُحقَّق", "Réalisé"), value: fmtMAD(d.delivered_value), color: "#047857", glow: "#34d399", tint: "#ecfdf5", icon: "check", sub: `${d.delivery_rate}% ${lbl("delivered", "مُسلّم", "livré")}` },
    { label: lbl("Backlog", "المعلّق", "En attente"), value: (d.pending || 0).toLocaleString(), color: "#b45309", glow: "#f59e0b", tint: "#fffbeb", icon: "clock", sub: lbl("pending fulfilment", "بانتظار التنفيذ", "à exécuter") },
    { label: "RTO", value: `${d.rto_rate}%`, color: "#be123c", glow: "#f87171", tint: "#fef2f2", icon: "refresh", sub: `${d.exceptions} ${lbl("exceptions", "استثناء", "exceptions")}` },
  ];
});

function open(id) { router.push({ path: "/accounting/sales/orders", query: { id } }); }
</script>
