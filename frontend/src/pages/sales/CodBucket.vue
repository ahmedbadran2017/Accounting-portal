<template>
  <div class="space-y-3.5">
    <!-- Pipeline strip -->
    <div class="grid grid-cols-2 lg:grid-cols-5 gap-3">
      <button v-for="b in PIPE" :key="b.key" class="group relative bg-white border rounded-[16px] p-4 text-start transition-all overflow-hidden"
              :class="bucket === b.key ? 'shadow-cardHover -translate-y-0.5' : 'border-line shadow-card hover:-translate-y-0.5 hover:shadow-cardHover'"
              :style="bucket === b.key ? { borderColor: b.color + '66', boxShadow: '0 10px 30px -12px ' + b.glow + '88' } : {}"
              @click="goBucket(b.key)">
        <span class="absolute top-0 inset-x-0 h-[3px]" :style="{ background: b.color, opacity: bucket === b.key ? 1 : .25 }"></span>
        <div class="absolute -top-10 -end-10 w-28 h-28 rounded-full blur-2xl pointer-events-none transition-opacity" :style="{ background: b.glow, opacity: bucket === b.key ? .16 : .06 }"></div>
        <div class="relative flex items-start gap-2.5">
          <span class="w-9 h-9 rounded-[11px] grid place-items-center flex-shrink-0" :style="{ background: b.tint }"><Icon :name="b.icon" :size="17" :color="b.color" /></span>
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-1.5">
              <span class="text-[10.5px] text-ink-muted font-bold uppercase tracking-wider">{{ b.label() }}</span>
              <span v-if="dateScope" class="text-[8.5px] font-bold px-1.5 py-px rounded-full" :style="{ background: b.tint, color: b.color }">{{ dateScope }}</span>
            </div>
            <div class="text-[24px] font-extrabold tnum leading-tight tracking-tight transition-colors" :style="{ color: bucket === b.key ? b.color : '#1c1917' }">{{ cardCount(b.key).toLocaleString() }}</div>
          </div>
          <span class="text-[10px] font-bold tnum mt-0.5" :style="{ color: b.color, opacity: .8 }">{{ cardShare(b.key) }}%</span>
        </div>
        <div class="relative mt-2 text-[11px] text-ink-3 font-semibold tnum">{{ fmt(cardValue(b.key)) }} <span class="text-ink-muted font-normal">MAD</span></div>
        <div class="relative mt-2 h-1 rounded-full bg-app-warm overflow-hidden">
          <div class="h-full rounded-full transition-all" :style="{ width: Math.max(3, cardShare(b.key)) + '%', background: b.color, opacity: bucket === b.key ? 1 : .45 }"></div>
        </div>
      </button>
    </div>

    <!-- Table -->
    <div class="bg-white rounded-card border border-line overflow-hidden shadow-card">
      <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
        <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" :style="{ background: active.tint }"><Icon :name="active.icon" :size="14" :color="active.color" /></span>
        <span class="text-[13px] font-bold">{{ active.label() }}</span>
        <span v-if="live !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="live ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ live ? "Live" : "Sample" }}</span>
        <span class="hidden lg:inline text-[11px] text-ink-muted">{{ bucketCount.toLocaleString() }} {{ L("orders","طلب","commandes") }} · {{ scopeLabel || "FY 2026" }}<span v-if="bucketCount > rows.length"> · {{ L("showing first","عرض أول","premiers") }} {{ rows.length }}</span></span>
        <button class="ms-auto inline-flex items-center gap-1.5 text-[12px] font-bold text-white bg-brand hover:bg-brand-dark px-3 py-1.5 rounded-chip shadow-brand" @click="showRecon = true">
          <Icon name="trend" :size="14" />{{ L("Reconcile Cathedis file","مطابقة ملف كاتدييس","Rapprocher fichier Cathedis") }}
        </button>
        <div class="relative">
          <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
          <input v-model.trim="srch" :placeholder="L('Order / customer / invoice / ref…','أوردر / عميل / فاتورة / مرجع…','Commande / client / facture…')" class="w-40 sm:w-64 h-9 bg-app-warm/40 border border-line-2 rounded-[10px] ps-9 pe-3 text-[12.5px] focus:outline-none focus:border-accent/40 focus:bg-white" />
        </div>
      </div>

      <!-- Date filter (server-side — runs over the whole bucket) -->
      <div class="flex items-center gap-2 px-4 py-2.5 border-b border-line-hair flex-wrap bg-app-warm/20">
        <Icon name="clock" :size="13" color="#a8a29e" />
        <button v-for="p in DATE_PRESETS" :key="p.key" class="text-[11px] font-semibold px-2.5 py-1 rounded-full border transition"
                :class="datePreset === p.key ? 'bg-ink text-white border-ink' : 'bg-white text-ink-3 border-line-2 hover:bg-app-warm'" @click="setPreset(p.key)">{{ p.label() }}</button>
        <div v-if="datePreset === 'range'" class="flex items-center gap-1">
          <input type="date" v-model="dateFrom" class="h-7 border border-line-2 rounded-chip px-2 text-[11px] focus:outline-none focus:border-accent/40" />
          <span class="text-ink-muted text-[11px]">→</span>
          <input type="date" v-model="dateTo" class="h-7 border border-line-2 rounded-chip px-2 text-[11px] focus:outline-none focus:border-accent/40" />
        </div>
        <span v-if="loading" class="ms-2 text-[11px] text-ink-muted inline-flex items-center gap-1.5"><span class="w-1.5 h-1.5 rounded-full bg-accent animate-pulse"></span>{{ L("loading…","تحميل…","…") }}</span>
      </div>

      <TableToolbar :t="tt" :filename="bucket" />
      <div class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead>
            <tr style="background:#fafaf9">
              <th class="px-3 py-2.5 w-9"><input type="checkbox" :checked="tt.allFilteredSelected.value" @change="tt.toggleAllFiltered()" class="accent-accent w-3.5 h-3.5 align-middle" /></th>
              <th v-for="c in cols" v-show="!tt.hidden.value.has(c.key)" :key="c.key"
                  class="px-4 py-2.5 text-[10px] font-bold uppercase tracking-wider text-ink-muted whitespace-nowrap cursor-pointer select-none hover:text-ink-2"
                  :class="c.align === 'e' ? 'text-end' : 'text-start'" @click="tt.toggleSort(c.key)">
                <span class="inline-flex items-center gap-1" :class="c.align === 'e' ? 'flex-row-reverse' : ''">{{ colLabel(c) }}
                  <Icon v-if="tt.sortKey.value === c.key" name="chevDown" :size="11" :class="tt.sortDir.value === 1 ? '' : 'rotate-180'" color="#0b5c4f" /></span>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="o in tt.pageRows.value" :key="o.name" class="border-t border-line-hair hover:bg-app-warm/70 cursor-pointer" :class="tt.isSelected(o) ? 'bg-accent/5' : ''" @click="open(o.name)">
              <td class="px-3 py-2.5 w-9" @click.stop><input type="checkbox" :checked="tt.isSelected(o)" @change="tt.toggleRow(o)" class="accent-accent w-3.5 h-3.5 align-middle" /></td>
              <td v-show="!tt.hidden.value.has('name')" class="px-4 py-2.5 font-mono font-semibold whitespace-nowrap">{{ o.name }}</td>
              <td v-show="!tt.hidden.value.has('date')" class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ o.date }}</td>
              <td v-show="!tt.hidden.value.has('customer')" class="px-4 py-2.5 truncate max-w-[180px]">{{ o.customer }}</td>
              <td v-show="!tt.hidden.value.has('city')" class="px-4 py-2.5 text-ink-2 whitespace-nowrap">{{ o.city || "—" }}</td>
              <td v-show="!tt.hidden.value.has('carrier')" class="px-4 py-2.5 text-ink-2 whitespace-nowrap">{{ o.carrier || "—" }}</td>
              <td v-show="!tt.hidden.value.has('track')" class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ o.track || "—" }}</td>
              <td v-show="!tt.hidden.value.has('reference')" class="px-4 py-2.5 whitespace-nowrap">
                <span v-if="isReturnBucket && o.return_shipment" class="inline-flex items-center gap-1.5 hover:underline" @click.stop="openRet = o.return_shipment">
                  <span class="font-mono text-[11px] text-accent-dark font-semibold">{{ o.return_shipment }}</span>
                  <span class="text-[9px] font-bold px-1.5 py-0.5 rounded-full" :style="retStatusStyle(o.return_status)">{{ o.return_status || "—" }}</span>
                </span>
                <span v-else class="font-mono text-[11px] text-ink-3">{{ o.reference || "—" }}</span>
              </td>
              <td v-show="!tt.hidden.value.has('value')" class="px-4 py-2.5 text-end font-bold tnum whitespace-nowrap">{{ fmt(o.value) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="!tt.sorted.value.length && !loading" class="py-12 text-center text-[12px] text-ink-muted">{{ L("No orders in this bucket.","لا طلبات في هذه المرحلة.","Aucune commande.") }}</div>
      <TablePager :t="tt" />
    </div>

    <BulkBar :t="tt" :filename="`${bucket}-selected`" :note="bulkNote" :actions="[]" />

    <CathedisReconcile v-if="showRecon" @close="showRecon = false" @applied="onApplied" />
    <ReturnShipmentModal v-if="openRet" :name="openRet" @close="openRet = null" />
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableToolbar from "@/components/TableToolbar.vue";
import TablePager from "@/components/TablePager.vue";
import CathedisReconcile from "@/components/CathedisReconcile.vue";
import ReturnShipmentModal from "@/components/ReturnShipmentModal.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";
import { useTableTools } from "@/composables/useTableTools";
import BulkBar from "@/components/BulkBar.vue";

const route = useRoute();
const router = useRouter();
const { locale } = useI18n();
const { entityId } = useUi();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US");

const PIPE = [
  { key: "todeliver", label: () => L("To deliver", "للتسليم", "À livrer"), color: "#0369a1", glow: "#38bdf8", icon: "truck", tint: "#eff6ff" },
  { key: "delivered", label: () => L("Delivered", "مُسلّمة", "Livrées"), color: "#047857", glow: "#34d399", icon: "check", tint: "#ecfdf5" },
  { key: "collected", label: () => L("Collected", "محصّلة", "Encaissées"), color: "#7c3aed", glow: "#a78bfa", icon: "coins", tint: "#f5f3ff" },
  { key: "toreturn", label: () => L("To return", "للإرجاع", "À retourner"), color: "#b45309", glow: "#fbbf24", icon: "clock", tint: "#fffbeb" },
  { key: "returned", label: () => L("Returned", "مرتجعة", "Retournées"), color: "#be123c", glow: "#f87171", icon: "refresh", tint: "#fef2f2" },
];
const bucket = computed(() => (PIPE.some((b) => b.key === route.params.sub) ? route.params.sub : "delivered"));
const active = computed(() => PIPE.find((b) => b.key === bucket.value) || PIPE[1]);
const isReturnBucket = computed(() => ["toreturn", "returned"].includes(bucket.value));
function colLabel(c) { return c.key === "reference" && isReturnBucket.value ? L("Return shipment", "شحنة الإرجاع", "Retour") : c.label; }
function retStatusStyle(s) {
  if (s === "Returned") return "background:#ecfdf5;color:#047857";
  if (s === "Cancelled") return "background:#fef2f2;color:#b91c1c";
  if (!s || s === "Draft") return "background:#f1efe8;color:#5f5e5a";
  return "background:#fffbeb;color:#b45309"; // in progress — AWB/Item scanning, Ready for Return
}

const DATE_PRESETS = [
  { key: "all", label: () => L("All", "الكل", "Tout") },
  { key: "today", label: () => L("Today", "اليوم", "Auj.") },
  { key: "yesterday", label: () => L("Yesterday", "أمس", "Hier") },
  { key: "7d", label: () => L("7 days", "7 أيام", "7 j") },
  { key: "30d", label: () => L("30 days", "30 يوم", "30 j") },
  { key: "month", label: () => L("This month", "هذا الشهر", "Ce mois") },
  { key: "range", label: () => L("Range", "نطاق", "Plage") },
];

const cols = [
  { key: "name", label: L("Order", "الطلب", "Commande"), align: "s" },
  { key: "date", label: L("Date", "التاريخ", "Date"), align: "s" },
  { key: "customer", label: L("Customer", "العميل", "Client"), align: "s" },
  { key: "city", label: L("City", "المدينة", "Ville"), align: "s" },
  { key: "carrier", label: L("Carrier", "الناقل", "Transp."), align: "s" },
  { key: "track", label: L("Shipment", "الشحن", "Suivi"), align: "s" },
  { key: "reference", label: L("Remittance ref", "مرجع التحويل", "Réf."), align: "s" },
  { key: "value", label: L("Value", "القيمة", "Valeur"), align: "e" },
];

const rows = ref([]);
const sum = ref({});
const live = ref(null);
const loading = ref(false);
const showRecon = ref(false);
const openRet = ref(null);
const srch = ref("");
const datePreset = ref("month");
const dateFrom = ref("");
const dateTo = ref("");
// Date + search are server-side; carrier/city facets + sort/page are client-side
// over the returned rows (no dateKey, so TableToolbar hides its own date row).
const tt = useTableTools(rows, cols, { defaultSort: "date", defaultDir: -1, facets: [{ key: "carrier", label: L("carrier", "ناقل", "transp.") }, { key: "city", label: L("city", "مدينة", "ville") }] });

const isFiltered = computed(() => datePreset.value !== "all" || !!srch.value || Object.values(tt.facetActive.value).some(Boolean));
const bulkNote = computed(() => { const tot = tt.selectedRows.value.reduce((a, r) => a + (Number(r.value) || 0), 0); return tot ? fmt(tot) + " MAD" : ""; });
const scopeLabel = computed(() => {
  if (datePreset.value !== "all") { const p = DATE_PRESETS.find((x) => x.key === datePreset.value); return p ? p.label() : ""; }
  if (srch.value || Object.values(tt.facetActive.value).some(Boolean)) return L("filtered", "مفلتر", "filtré");
  return "";
});
// Date scope only (cards follow the date, not search) — shown on every card.
const dateScope = computed(() => {
  if (datePreset.value === "all") return "";
  const p = DATE_PRESETS.find((x) => x.key === datePreset.value);
  return p ? p.label() : "";
});
// Every card reads from the same date-scoped summary → consistent counts AND
// shares (no mixing a filtered bucket with full-year totals).
const totalCount = computed(() => Math.max(1, Object.values(sum.value).reduce((s, b) => s + ((b && b.count) || 0), 0)));
function cardCount(k) { return (sum.value[k] && sum.value[k].count) || 0; }
function cardValue(k) { return (sum.value[k] && sum.value[k].value) || 0; }
function cardShare(k) { return Math.round(((sum.value[k] && sum.value[k].count) || 0) / totalCount.value * 100); }

const bucketCount = ref(0);
const bucketValue = ref(0);

function bounds(key) {
  const iso = (d) => d.toISOString().slice(0, 10);
  const now = new Date(); const t = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  if (key === "today") return [iso(t), iso(now)];
  if (key === "yesterday") { const y = new Date(t); y.setDate(y.getDate() - 1); return [iso(y), iso(t)]; }
  if (key === "7d") { const s = new Date(t); s.setDate(s.getDate() - 7); return [iso(s), iso(now)]; }
  if (key === "30d") { const s = new Date(t); s.setDate(s.getDate() - 30); return [iso(s), iso(now)]; }
  if (key === "month") return [iso(new Date(now.getFullYear(), now.getMonth(), 1)), iso(now)];
  if (key === "range") return [dateFrom.value || null, dateTo.value || null];
  return [null, null];
}

async function loadSummary() {
  // All four cards share the active date scope (a coherent cohort funnel).
  const [fd, td] = bounds(datePreset.value);
  try {
    try { sum.value = await api.call("accounting_portal.api.cod.cod_summary", { company: currentCompany(), from_date: fd || undefined, to_date: td || undefined }) || {}; }
    catch { sum.value = await api.call("accounting_portal.api.cod.cod_summary", { company: currentCompany() }) || {}; }  // old backend: FY totals
  } catch { sum.value = { todeliver: { count: 481, value: 96000 }, delivered: { count: 44911, value: 8980000 }, collected: { count: 2626, value: 475000 }, toreturn: { count: 2063, value: 419716 }, returned: { count: 9705, value: 1924827 } }; }
}
async function loadRows() {
  loading.value = true;
  const [fd, td] = bounds(datePreset.value);
  const base = { company: currentCompany(), bucket: bucket.value, search: srch.value || undefined, limit: 500 };
  try {
    let r;
    try { r = await api.call("accounting_portal.api.cod.list_bucket", { ...base, from_date: fd || undefined, to_date: td || undefined }); }
    catch (e) { r = await api.call("accounting_portal.api.cod.list_bucket", base); }  // old backend: no date params
    if (Array.isArray(r)) {
      // Legacy shape (server Python not yet restarted): filter the returned window client-side.
      let d = r;
      if (fd) d = d.filter((x) => String(x.date) >= fd);
      if (td) d = d.filter((x) => String(x.date) <= td);
      rows.value = d; bucketCount.value = d.length; bucketValue.value = d.reduce((s, x) => s + (Number(x.value) || 0), 0);
    } else {
      rows.value = r.rows || []; bucketCount.value = r.count || 0; bucketValue.value = r.value || 0;
    }
    live.value = true;
  } catch { rows.value = []; bucketCount.value = 0; bucketValue.value = 0; live.value = false; }
  finally { loading.value = false; }
}

// The summary (all 5 card counts) depends only on company + date scope — NOT on
// which bucket is active — so switching cards must NOT re-run that ~1.2s query.
// Bucket change reloads only the table; date/entity change reloads both.
function setPreset(k) { datePreset.value = k; if (k !== "range") { loadSummary(); loadRows(); } }
let timer;
watch(entityId, loadSummary, { immediate: true });
watch([bucket, entityId], () => { tt.reset(); tt.clearSelection(); loadRows(); }, { immediate: true });
watch([dateFrom, dateTo], () => { clearTimeout(timer); timer = setTimeout(() => { loadSummary(); loadRows(); }, 300); });
watch(srch, () => { clearTimeout(timer); timer = setTimeout(loadRows, 300); });

function goBucket(k) { router.push(`/accounting/sales/${k}`); }
function open(name) { router.push({ path: "/accounting/sales/orders", query: { id: name } }); }
function onApplied() {
  // Remittance files cover PAST orders, so the default "This month" view would
  // hide the orders we just collected. Jump to Collected · All to show the result.
  showRecon.value = false;
  datePreset.value = "all";
  loadSummary();  // the bucket counts changed after collecting
  if (bucket.value !== "collected") router.push("/accounting/sales/collected");
  else loadRows();
}
</script>
