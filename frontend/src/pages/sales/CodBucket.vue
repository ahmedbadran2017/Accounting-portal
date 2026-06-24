<template>
  <div class="space-y-3.5">
    <!-- Pipeline strip -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <button v-for="b in PIPE" :key="b.key" class="relative bg-white border rounded-[14px] p-3.5 shadow-card text-start transition"
              :class="bucket === b.key ? 'border-accent/50 ring-1 ring-accent/20' : 'border-line hover:border-line-2'"
              @click="goBucket(b.key)">
        <div class="absolute -top-8 -end-8 w-20 h-20 rounded-full blur-2xl pointer-events-none" :style="{ background: b.glow, opacity: .08 }"></div>
        <div class="relative flex items-center gap-1.5">
          <span class="w-1.5 h-1.5 rounded-full" :style="{ background: b.color }"></span>
          <span class="text-[10px] text-ink-muted font-bold uppercase tracking-wider">{{ b.label() }}</span>
        </div>
        <div class="relative text-[20px] font-extrabold tnum mt-1 tracking-tight" :style="{ color: bucket === b.key ? b.color : '#1c1917' }">{{ (sum[b.key] && sum[b.key].count || 0).toLocaleString() }}</div>
        <div class="relative text-[10.5px] text-ink-3 mt-0.5">{{ fmt(sum[b.key] && sum[b.key].value) }} MAD</div>
      </button>
    </div>

    <!-- Table -->
    <div class="bg-white rounded-card border border-line overflow-hidden shadow-card">
      <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
        <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" :style="{ background: active.tint }"><Icon :name="active.icon" :size="14" :color="active.color" /></span>
        <span class="text-[13px] font-bold">{{ active.label() }}</span>
        <span v-if="live !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="live ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ live ? "Live" : "Sample" }}</span>
        <span class="hidden lg:inline text-[11px] text-ink-muted">{{ rows.length }} {{ L("orders · FY 2026","طلب · سنة 2026","commandes · 2026") }}</span>
        <button class="ms-auto inline-flex items-center gap-1.5 text-[12px] font-bold text-white bg-accent hover:bg-accent-dark px-3 py-1.5 rounded-chip shadow-prim" @click="showRecon = true">
          <Icon name="trend" :size="14" />{{ L("Reconcile Cathedis file","مطابقة ملف كاتدييس","Rapprocher fichier Cathedis") }}
        </button>
        <div class="relative">
          <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
          <input v-model.trim="tt.search.value" :placeholder="L('Search order / customer…','بحث…','Rechercher…')" class="w-40 sm:w-56 h-9 bg-app-warm/40 border border-line-2 rounded-[10px] ps-9 pe-3 text-[12.5px] focus:outline-none focus:border-accent/40 focus:bg-white" />
        </div>
      </div>

      <TableToolbar :t="tt" :filename="bucket" />
      <div class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead>
            <tr style="background:#fafaf9">
              <th v-for="c in cols" v-show="!tt.hidden.value.has(c.key)" :key="c.key"
                  class="px-4 py-2.5 text-[10px] font-bold uppercase tracking-wider text-ink-muted whitespace-nowrap cursor-pointer select-none hover:text-ink-2"
                  :class="c.align === 'e' ? 'text-end' : 'text-start'" @click="tt.toggleSort(c.key)">
                <span class="inline-flex items-center gap-1" :class="c.align === 'e' ? 'flex-row-reverse' : ''">{{ c.label }}
                  <Icon v-if="tt.sortKey.value === c.key" name="chevDown" :size="11" :class="tt.sortDir.value === 1 ? '' : 'rotate-180'" color="#a33a22" /></span>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="o in tt.pageRows.value" :key="o.name" class="border-t border-line-hair hover:bg-app-warm/70 cursor-pointer" @click="open(o.name)">
              <td v-show="!tt.hidden.value.has('name')" class="px-4 py-2.5 font-mono font-semibold whitespace-nowrap">{{ o.name }}</td>
              <td v-show="!tt.hidden.value.has('date')" class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ o.date }}</td>
              <td v-show="!tt.hidden.value.has('customer')" class="px-4 py-2.5 truncate max-w-[180px]">{{ o.customer }}</td>
              <td v-show="!tt.hidden.value.has('city')" class="px-4 py-2.5 text-ink-2 whitespace-nowrap">{{ o.city || "—" }}</td>
              <td v-show="!tt.hidden.value.has('carrier')" class="px-4 py-2.5 text-ink-2 whitespace-nowrap">{{ o.carrier || "—" }}</td>
              <td v-show="!tt.hidden.value.has('track')" class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ o.track || "—" }}</td>
              <td v-show="!tt.hidden.value.has('reference')" class="px-4 py-2.5 font-mono text-[11px] text-ink-3 whitespace-nowrap">{{ o.reference || "—" }}</td>
              <td v-show="!tt.hidden.value.has('value')" class="px-4 py-2.5 text-end font-bold tnum whitespace-nowrap">{{ fmt(o.value) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="!tt.sorted.value.length" class="py-12 text-center text-[12px] text-ink-muted">{{ L("No orders in this bucket.","لا طلبات في هذه المرحلة.","Aucune commande.") }}</div>
      <TablePager :t="tt" />
    </div>

    <CathedisReconcile v-if="showRecon" @close="showRecon = false" @applied="onApplied" />
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
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";
import { useTableTools } from "@/composables/useTableTools";

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
  { key: "returned", label: () => L("Returned", "مرتجعة", "Retournées"), color: "#be123c", glow: "#f87171", icon: "refresh", tint: "#fef2f2" },
];
const bucket = computed(() => (PIPE.some((b) => b.key === route.params.sub) ? route.params.sub : "delivered"));
const active = computed(() => PIPE.find((b) => b.key === bucket.value) || PIPE[1]);

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
const showRecon = ref(false);
const tt = useTableTools(rows, cols, { dateKey: "date", defaultSort: "date", defaultDir: -1, defaultDate: "all", facets: [{ key: "carrier", label: L("carrier", "ناقل", "transp.") }, { key: "city", label: L("city", "مدينة", "ville") }] });

async function loadSummary() {
  try { sum.value = await api.call("accounting_portal.api.cod.cod_summary", { company: currentCompany() }) || {}; }
  catch { sum.value = { todeliver: { count: 481, value: 96000 }, delivered: { count: 44999, value: 9100000 }, collected: { count: 2626, value: 530000 }, returned: { count: 11652, value: 2300000 } }; }
}
async function loadRows() {
  try { rows.value = await api.call("accounting_portal.api.cod.list_bucket", { company: currentCompany(), bucket: bucket.value, limit: 500 }) || []; live.value = true; }
  catch { rows.value = []; live.value = false; }
}
function load() { loadSummary(); loadRows(); }
watch([bucket, entityId], load, { immediate: true });

function goBucket(k) { router.push(`/accounting/sales/${k}`); }
function open(name) { router.push({ path: "/accounting/sales/orders", query: { id: name } }); }
function onApplied() { showRecon.value = false; load(); }
</script>
