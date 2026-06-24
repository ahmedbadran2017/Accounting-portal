<template>
  <div class="space-y-3.5">
    <!-- CFO summary strip — GMV, AOV, realised value, backlog, RTO (month-to-date) -->
    <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
      <div v-for="m in summaryCards" :key="m.label"
           class="relative bg-white border border-line rounded-[14px] p-3.5 shadow-card overflow-hidden">
        <div class="absolute -top-8 -end-8 w-20 h-20 rounded-full blur-2xl pointer-events-none" :style="{ background: m.glow, opacity: .07 }"></div>
        <div class="relative text-[9.5px] text-ink-muted font-bold uppercase tracking-wider">{{ m.label }}</div>
        <div class="relative text-[19px] font-extrabold tnum mt-1 tracking-tight" :style="{ color: m.color }">{{ m.value }}</div>
        <div class="relative text-[10px] text-ink-3 mt-0.5">{{ m.sub }}</div>
      </div>
    </div>

    <!-- State-machine strip (connected, click to filter) -->
    <div class="bg-white border border-line rounded-[14px] p-3.5 shadow-card overflow-x-auto">
      <div class="flex items-center gap-1 min-w-[680px]">
        <template v-for="(st, i) in MACHINE" :key="st">
          <button class="flex flex-col items-start flex-1 px-3 py-1.5 rounded-lg"
                  :class="filterState === st ? 'bg-app-warm' : 'hover:bg-app-warm/60'"
                  @click="filterState = filterState === st ? null : st">
            <span class="text-[18px] font-bold tnum leading-none" :style="{ color: filterState === st ? STATE_META[st].fg : '#1c1917' }">{{ machineCounts[st].toLocaleString() }}</span>
            <span class="text-[10.5px] font-semibold mt-[3px]" :class="filterState === st ? 'text-accent-dark' : 'text-ink-3'">{{ stateLabel(st, locale) }}</span>
          </button>
          <Icon v-if="i < MACHINE.length - 1" name="chev" :size="15" color="#d6d3d1" class="flex-shrink-0 rtl:rotate-180" />
        </template>
      </div>
    </div>

    <!-- Toolbar -->
    <div class="flex items-center gap-2">
      <div class="relative flex-1 max-w-xs">
        <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
        <input v-model.trim="tt.search.value" :placeholder="t('module.search')"
               class="w-full h-9 bg-white border border-line-2 rounded-[10px] ps-9 pe-3 text-[12.5px] focus:outline-none focus:border-accent/40" />
      </div>
      <span v-if="isLive !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border"
            :style="isLive ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">
        {{ isLive ? "Live" : "Sample" }}
      </span>
      <span v-if="filterState" class="inline-flex items-center gap-1 text-[11px] font-semibold px-2.5 py-1 rounded-chip"
            :style="{ background: STATE_META[filterState].bg, color: STATE_META[filterState].fg }">
        {{ stateLabel(filterState, locale) }}
        <button class="opacity-70 hover:opacity-100" @click="filterState = null"><Icon name="close" :size="12" /></button>
      </span>
      <span v-if="customerFilter" class="inline-flex items-center gap-1.5 text-[11px] font-semibold px-2.5 py-1 rounded-chip" style="background:#eff6ff;color:#0369a1">
        <Icon name="user" :size="12" />{{ customerFilter }}
        <button class="opacity-70 hover:opacity-100" @click="clearCustomer"><Icon name="close" :size="12" /></button>
      </span>
      <button class="inline-flex items-center gap-1.5 text-[12px] font-semibold text-white bg-accent hover:bg-accent-dark px-3 py-1.5 rounded-chip shadow-prim ms-auto">
        <Icon name="plus" :size="14" />{{ t("module.new") }}
      </button>
    </div>

    <!-- Table -->
    <div class="bg-white rounded-card border border-line overflow-hidden shadow-card">
      <TableToolbar :t="tt" />
      <div class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead>
            <tr style="background:#fafaf9">
              <th v-for="c in cols" v-show="!tt.hidden.value.has(c.key)" :key="c.key"
                  class="px-4 py-2.5 text-[10px] font-bold uppercase tracking-wider text-ink-muted whitespace-nowrap select-none cursor-pointer hover:text-ink-2"
                  :class="c.align === 'e' ? 'text-end' : 'text-start'"
                  @click="tt.toggleSort(c.key)">
                <span class="inline-flex items-center gap-1" :class="c.align === 'e' ? 'flex-row-reverse' : ''">{{ c.label }}
                  <Icon v-if="tt.sortKey.value === c.key" name="chevDown" :size="11" :class="tt.sortDir.value === 1 ? '' : 'rotate-180'" color="#a33a22" /></span>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="o in tt.pageRows.value" :key="o.id"
                class="border-t border-line-hair hover:bg-app-warm/70 cursor-pointer"
                @click="open(o.id)">
              <td v-show="!tt.hidden.value.has('id')" class="px-4 py-2.5 font-mono font-semibold text-ink whitespace-nowrap">{{ o.id }}</td>
              <td v-show="!tt.hidden.value.has('date')" class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ o.date || "—" }}</td>
              <td v-show="!tt.hidden.value.has('customer')" class="px-4 py-2.5">
                <span class="flex items-center gap-2">
                  <span class="w-6 h-6 rounded-full grid place-items-center text-white text-[9px] font-bold flex-shrink-0"
                        :style="{ background: AV[o.av] }">{{ o.initials }}</span>
                  <span class="truncate max-w-[160px]">{{ o.customer }}</span>
                </span>
              </td>
              <td v-show="!tt.hidden.value.has('city')" class="px-4 py-2.5 text-ink-2 whitespace-nowrap">{{ o.city }}</td>
              <td v-show="!tt.hidden.value.has('carrier')" class="px-4 py-2.5 text-ink-2 whitespace-nowrap">{{ o.carrier }}</td>
              <td v-show="!tt.hidden.value.has('trackStatus')" class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ o.trackStatus }}</td>
              <td v-show="!tt.hidden.value.has('state')" class="px-4 py-2.5">
                <span class="inline-block text-[10px] font-bold px-2 py-0.5 rounded-badge border"
                      :style="{ background: STATE_META[o.state].bg, color: STATE_META[o.state].fg, borderColor: STATE_META[o.state].bd }">
                  {{ stateLabel(o.state, locale) }}
                </span>
              </td>
              <td v-show="!tt.hidden.value.has('posting')" class="px-4 py-2.5">
                <span class="inline-block text-[10px] font-bold px-2 py-0.5 rounded-badge border"
                      :style="postingInfo(o.state, locale).posted ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#f5f5f4;color:#a8a29e;border-color:#e7e5e4'">
                  {{ postingInfo(o.state, locale).label }}
                </span>
              </td>
              <td v-show="!tt.hidden.value.has('value')" class="px-4 py-2.5 text-end font-bold tnum whitespace-nowrap">{{ o.value }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="!tt.sorted.value.length" class="py-14 text-center text-[12px] text-ink-muted">{{ lbl("No orders match your filters.", "لا توجد طلبات مطابقة.", "Aucune commande.") }}</div>
      <TablePager :t="tt" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { ORDERS, STATE_META, stateLabel, MACHINE, machineCounts, AV, postingInfo } from "@/data/orders";
import { useCreated } from "@/composables/useCreated";
import { liveOrSample, avFor, iniOf, currentCompany } from "@/composables/useLive";
import { fmtMAD } from "@/composables/useReconciliation";
import api from "@/services/api";
import TableToolbar from "@/components/TableToolbar.vue";
import TablePager from "@/components/TablePager.vue";
import { useTableTools } from "@/composables/useTableTools";

const { t, locale } = useI18n();
const router = useRouter();
const route = useRoute();
const { createdOrders } = useCreated();
const customerFilter = ref(route.query.customer || null);
function clearCustomer() { customerFilter.value = null; router.replace({ path: "/accounting/sales/orders" }); }

const filterState = ref(null);

// Live ERPNext orders (fallback to the June sample); merged with in-session creations.
const loaded = ref(ORDERS);
const isLive = ref(null);
const summary = ref(null);
onMounted(async () => {
  const res = await liveOrSample(
    "accounting_portal.api.sales.list_orders", { company: currentCompany(), limit: 500, customer: customerFilter.value || undefined }, () => ORDERS,
    (rows) => rows.map((r, i) => ({
      id: r.name, customer: r.customer, date: String(r.date || ""), city: r.city || "—", carrier: r.carrier || "—",
      trackStatus: r.custom_track_shipment_status || "Pending", state: r.state,
      value: r.value, initials: iniOf(r.customer), av: avFor(i),
    })),
  );
  loaded.value = res.data;
  isLive.value = res.live;
  try { summary.value = await api.call("accounting_portal.api.sales.orders_summary", { company: currentCompany() }); } catch { /* sample */ }
});

// CFO month-to-date metrics (live; sample headline until the endpoint lands).
const SUMMARY_SAMPLE = { gmv: 1525056, orders: 7553, aov: 202, delivered_value: 547566, delivery_rate: 36.8, pending: 4092, exceptions: 92, rto_rate: 1.2 };
const summaryCards = computed(() => {
  const d = summary.value && summary.value.company ? summary.value : SUMMARY_SAMPLE;
  return [
    { label: lbl("GMV (MTD)", "إجمالي المبيعات", "GMV (mois)"), value: fmtMAD(d.gmv), color: "#1c1917", glow: "#a8a29e", sub: `${(d.orders || 0).toLocaleString()} ${lbl("orders", "طلب", "commandes")}` },
    { label: lbl("Avg order", "متوسط الطلب", "Panier moyen"), value: fmtMAD(d.aov), color: "#1c1917", glow: "#a8a29e", sub: "AOV · MAD" },
    { label: lbl("Realised", "المُحقَّق", "Réalisé"), value: fmtMAD(d.delivered_value), color: "#047857", glow: "#34d399", sub: `${d.delivery_rate}% ${lbl("delivered", "مُسلّم", "livré")}` },
    { label: lbl("Backlog", "المعلّق", "En attente"), value: (d.pending || 0).toLocaleString(), color: "#b45309", glow: "#f59e0b", sub: lbl("pending fulfilment", "بانتظار التنفيذ", "à exécuter") },
    { label: "RTO", value: `${d.rto_rate}%`, color: "#be123c", glow: "#f87171", sub: `${d.exceptions} ${lbl("exceptions", "استثناء", "exceptions")}` },
  ];
});

function lbl(en, ar, fr) { return locale.value === "ar" ? ar : locale.value === "fr" ? fr : en; }
const cols = [
  { key: "id", label: lbl("Order", "الطلب", "Commande") },
  { key: "date", label: lbl("Date", "التاريخ", "Date") },
  { key: "customer", label: lbl("Customer", "العميل", "Client") },
  { key: "city", label: lbl("City", "المدينة", "Ville") },
  { key: "carrier", label: lbl("Carrier", "الناقل", "Transporteur") },
  { key: "trackStatus", label: lbl("Shipment", "الشحن", "Expédition") },
  { key: "state", label: lbl("State", "الحالة", "État") },
  { key: "posting", label: lbl("Posting", "الترحيل", "Passation") },
  { key: "value", label: lbl("Value", "القيمة", "Valeur"), align: "e" },
];

// State-funnel filter feeds the shared table tools (search · date · sort · page).
const baseRows = computed(() => {
  let r = [...createdOrders, ...loaded.value];
  if (filterState.value) r = r.filter((o) => o.state === filterState.value);
  return r;
});
const tt = useTableTools(baseRows, cols, {
  dateKey: "date", defaultSort: "date", defaultDir: -1,
  facets: [
    { key: "carrier", label: lbl("carrier", "ناقل", "transp.") },
    { key: "city", label: lbl("city", "مدينة", "ville") },
    { key: "state", label: lbl("state", "حالة", "état"), format: (v) => stateLabel(v, locale.value) },
  ],
});

function open(id) { router.push({ path: "/accounting/sales/orders", query: { id } }); }
</script>
