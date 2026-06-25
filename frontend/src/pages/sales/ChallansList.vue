<template>
  <div class="space-y-3.5">
    <!-- Delivery funnel insights -->
    <div v-if="ins" class="grid grid-cols-2 lg:grid-cols-4 gap-2.5">
      <div v-for="s in statCards" :key="s.label" class="bg-white rounded-[13px] border border-line px-4 py-3 shadow-card">
        <div class="text-[10.5px] text-ink-muted font-semibold">{{ s.label }}</div>
        <div class="text-[19px] font-bold tnum mt-0.5" :class="s.cls">{{ s.value }}</div>
      </div>
    </div>

    <div class="bg-white rounded-card border border-line overflow-hidden shadow-card">
      <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
        <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#eef6ff"><Icon name="truck" :size="14" color="#0369a1" /></span>
        <span class="text-[13px] font-bold">{{ L("Delivery notes","سندات التسليم","Bons de livraison") }}</span>
        <span v-if="isLive !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="isLive ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ isLive ? L("Live","مباشر","Live") : L("Sample","عينة","Échant.") }}</span>
        <span class="hidden lg:inline text-[11px] text-ink-muted">{{ rows.length }} · {{ L("carrier shipments","شحنات الناقل","expéditions") }}</span>
        <div class="ms-auto relative">
          <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
          <input v-model.trim="tt.search.value" :placeholder="L('Search DN / customer / tracking…','بحث…','Rechercher…')" class="w-44 sm:w-64 h-9 bg-app-warm/40 border border-line-2 rounded-[10px] ps-9 pe-3 text-[12.5px] focus:outline-none focus:border-accent/40 focus:bg-white" />
        </div>
      </div>

      <TableToolbar :t="tt" />
      <TableLoading v-if="loading" :rows="8" />
      <div v-else class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead><tr style="background:#fafaf9">
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Delivery note","السند","Bon") }}</th>
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Customer","العميل","Client") }}</th>
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Carrier","الناقل","Transporteur") }}</th>
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Status","الحالة","Statut") }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Date","التاريخ","Date") }}</th>
          </tr></thead>
          <tbody>
            <tr v-for="r in tt.pageRows.value" :key="r.name" class="border-t border-line-hair hover:bg-app-warm/50 cursor-pointer" @click="open(r.name)">
              <td class="px-4 py-2.5 font-mono text-[11.5px] font-semibold">{{ r.name }}</td>
              <td class="px-4 py-2.5 truncate max-w-[200px]">{{ r.customer }}</td>
              <td class="px-4 py-2.5 text-ink-3">{{ r.carrier }}<span v-if="r.tracking && r.tracking !== '—'" class="text-ink-muted"> · {{ r.tracking }}</span></td>
              <td class="px-4 py-2.5"><span class="inline-flex text-[10.5px] font-bold px-2 py-0.5 rounded-badge" :style="statusBadge(r.status)">{{ r.status }}</span></td>
              <td class="px-4 py-2.5 text-end text-ink-3 whitespace-nowrap">{{ r.date }}</td>
            </tr>
            <tr v-if="!tt.pageRows.value.length"><td colspan="5" class="px-4 py-12 text-center text-ink-muted text-[12px]">{{ L("No delivery notes.","لا توجد سندات تسليم.","Aucun bon.") }}</td></tr>
          </tbody>
        </table>
      </div>
      <TablePager :t="tt" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableToolbar from "@/components/TableToolbar.vue";
import TablePager from "@/components/TablePager.vue";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";
import { liveOrSample, currentCompany } from "@/composables/useLive";
import { useTableTools } from "@/composables/useTableTools";
import { useUi } from "@/composables/useUi";

const { locale } = useI18n();
const { entityId } = useUi();
const router = useRouter();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US");

const cols = [
  { key: "name", label: "DN", align: "s" },
  { key: "customer", label: L("Customer", "العميل", "Client"), align: "s" },
  { key: "status", label: L("Status", "الحالة", "Statut"), align: "s", facet: true },
  { key: "date", label: L("Date", "التاريخ", "Date"), align: "e" },
];
const SAMPLE = [
  { name: "MAT-DN-2026-0001", customer: "COD customer", carrier: "Cathedis", tracking: "CTH123", status: "Delivered", date: "2026-06-20" },
  { name: "MAT-DN-2026-0002", customer: "COD customer", carrier: "Cathedis", tracking: "CTH124", status: "In Transit", date: "2026-06-21" },
];
const rows = ref([]);
const isLive = ref(null);
const loading = ref(true);
const ins = ref(null);
const tt = useTableTools(rows, cols, { keyField: "name", dateKey: "date", defaultSort: "date", defaultDir: -1, facets: [{ key: "status", label: L("status", "الحالة", "statut") }] });

async function load() {
  loading.value = true;
  try {
    const res = await liveOrSample("accounting_portal.api.sales.list_challans", { company: currentCompany(), limit: 300 }, () => SAMPLE);
    rows.value = res.data; isLive.value = res.live;
    try { ins.value = await api.call("accounting_portal.api.sales.challans_summary", { company: currentCompany() }); } catch { ins.value = null; }
  } finally { loading.value = false; }
}
onMounted(load);
watch(entityId, load);

const statCards = computed(() => {
  const s = ins.value || {};
  return [
    { label: L("This month", "هذا الشهر", "Ce mois"), value: fmt(s.total), cls: "" },
    { label: L("Delivered", "تم التسليم", "Livrés"), value: fmt(s.delivered), cls: "text-success-dark" },
    { label: L("In transit", "قيد النقل", "En transit"), value: fmt(s.in_transit), cls: "text-accent-dark" },
    { label: L("Delivery rate", "نسبة التسليم", "Taux livraison"), value: (s.delivery_rate || 0) + "%", cls: "" },
  ];
});

function open(name) { router.push({ path: "/accounting/sales/challans", query: { id: name } }); }

function statusBadge(s) {
  const v = String(s || "").toLowerCase();
  if (v.includes("deliver") && !v.includes("out") && !v.includes("excep")) return "background:#ecfdf5;color:#047857";
  if (v.includes("transit") || v.includes("out for")) return "background:#eff6ff;color:#0369a1";
  if (v.includes("excep") || v.includes("fail") || v.includes("return")) return "background:#fef2f2;color:#b91c1c";
  return "background:#f5f5f4;color:#57534e";
}
</script>
