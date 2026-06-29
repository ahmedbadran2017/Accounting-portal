<template>
  <div class="bg-white rounded-card border border-line overflow-hidden shadow-card">
    <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
      <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#fef2f2"><Icon name="refresh" :size="14" color="#b91c1c" /></span>
      <span class="text-[13px] font-bold">{{ L("Returns & credit notes","المرتجعات وإشعارات الدائن","Retours & avoirs") }}</span>
      <span v-if="isLive !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="isLive ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ isLive ? L("Live","مباشر","Live") : L("Sample","عينة","Échant.") }}</span>
      <span class="hidden lg:inline text-[11px] text-ink-muted">{{ rows.length }} · {{ L("returned / exception orders","مرتجع / استثناء","retours / exceptions") }}</span>
      <div class="ms-auto relative">
        <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
        <input v-model.trim="tt.search.value" :placeholder="L('Search order / customer…','بحث…','Rechercher…')" class="w-44 sm:w-60 h-9 bg-app-warm/40 border border-line-2 rounded-[10px] ps-9 pe-3 text-[12.5px] focus:outline-none focus:border-accent/40 focus:bg-white" />
      </div>
    </div>

    <TableToolbar :t="tt" />
    <TableLoading v-if="loading" :rows="8" />
    <div v-else class="overflow-x-auto">
      <table class="w-full text-[12px]">
        <thead><tr style="background:#fafaf9">
          <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Order","الطلب","Commande") }}</th>
          <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Customer","العميل","Client") }}</th>
          <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Reason","السبب","Motif") }}</th>
          <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Amount","المبلغ","Montant") }}</th>
          <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Date","التاريخ","Date") }}</th>
        </tr></thead>
        <tbody>
          <tr v-for="r in tt.pageRows.value" :key="r.name" class="border-t border-line-hair hover:bg-app-warm/50 cursor-pointer" @click="open(r.name)">
            <td class="px-4 py-2.5 font-mono text-[11.5px] font-semibold">{{ r.name }}</td>
            <td class="px-4 py-2.5 truncate max-w-[200px]">{{ r.customer }}</td>
            <td class="px-4 py-2.5"><span class="inline-flex text-[10.5px] font-bold px-2 py-0.5 rounded-badge" :style="reasonBadge(r.reason)">{{ r.reason || '—' }}</span></td>
            <td class="px-4 py-2.5 text-end tnum font-semibold text-sale">{{ fmt(r.amount) }}</td>
            <td class="px-4 py-2.5 text-end text-ink-3 whitespace-nowrap">{{ r.date }}</td>
          </tr>
          <tr v-if="!tt.pageRows.value.length"><td colspan="5" class="px-4 py-12 text-center text-ink-muted text-[12px]">{{ L("No returns.","لا مرتجعات.","Aucun retour.") }}</td></tr>
        </tbody>
      </table>
    </div>
    <TablePager :t="tt" />
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableToolbar from "@/components/TableToolbar.vue";
import TablePager from "@/components/TablePager.vue";
import TableLoading from "@/components/TableLoading.vue";
import { liveOrSample, currentCompany } from "@/composables/useLive";
import { useTableTools } from "@/composables/useTableTools";
import { useUi } from "@/composables/useUi";

const { locale } = useI18n();
const { entityId } = useUi();
const router = useRouter();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US");

const cols = [
  { key: "name", label: L("Order", "الطلب", "Commande"), align: "s" },
  { key: "customer", label: L("Customer", "العميل", "Client"), align: "s" },
  { key: "reason", label: L("Reason", "السبب", "Motif"), align: "s", facet: true },
  { key: "amount", label: L("Amount", "المبلغ", "Montant"), align: "e" },
  { key: "date", label: L("Date", "التاريخ", "Date"), align: "e" },
];
const SAMPLE = [
  { name: "#100001", customer: "COD customer", reason: "Returned", amount: 299, date: "2026-06-18" },
  { name: "#100002", customer: "COD customer", reason: "Delivery Exception", amount: 199, date: "2026-06-19" },
];
const rows = ref([]);
const isLive = ref(null);
const loading = ref(true);
const tt = useTableTools(rows, cols, { storeKey: "credits", keyField: "name", dateKey: "date", defaultSort: "date", defaultDir: -1, facets: [{ key: "reason", label: L("reason", "السبب", "motif") }] });

async function load() {
  loading.value = true;
  try {
    const res = await liveOrSample("accounting_portal.api.sales.list_credits", { company: currentCompany(), limit: 300 }, () => SAMPLE);
    rows.value = res.data; isLive.value = res.live;
  } finally { loading.value = false; }
}
onMounted(load);
watch(entityId, load);

// Returns are Sales Orders — open the order detail.
function open(name) { router.push({ path: "/accounting/sales/orders", query: { id: name } }); }

function reasonBadge(r) {
  const v = String(r || "").toLowerCase();
  if (v.includes("return")) return "background:#fef2f2;color:#b91c1c";
  if (v.includes("excep") || v.includes("fail")) return "background:#fffbeb;color:#b45309";
  return "background:#f5f5f4;color:#57534e";
}
</script>
