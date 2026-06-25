<template>
  <div class="space-y-3.5">
    <!-- Exposure header -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-2.5">
      <div class="bg-white rounded-[13px] border border-line px-4 py-3 shadow-card">
        <div class="text-[10.5px] text-ink-muted font-semibold">{{ L("Awaiting invoice","بانتظار الفوترة","À facturer") }}</div>
        <div class="text-[19px] font-bold tnum mt-0.5 text-sale">{{ money(sum.value) }} <span class="text-[11px] text-ink-muted font-normal">{{ sum.currency || 'MAD' }}</span></div>
      </div>
      <div class="bg-white rounded-[13px] border border-line px-4 py-3 shadow-card">
        <div class="text-[10.5px] text-ink-muted font-semibold">{{ L("Delivery notes","سندات التسليم","Bons") }}</div>
        <div class="text-[19px] font-bold tnum mt-0.5">{{ (sum.count || 0).toLocaleString() }}</div>
      </div>
      <div class="bg-white rounded-[13px] border px-4 py-3 shadow-card" :style="(sum.value_over_60 ? 'border-color:#fecaca;background:#fff5f5' : 'border-color:#f0efed')">
        <div class="text-[10.5px] text-ink-muted font-semibold">{{ L("Aged > 60 days","أقدم من 60 يوم","> 60 jours") }}</div>
        <div class="text-[19px] font-bold tnum mt-0.5 text-sale">{{ money(sum.value_over_60) }} <span class="text-[11px] text-ink-muted font-normal">{{ sum.currency || 'MAD' }}</span></div>
      </div>
      <div class="bg-white rounded-[13px] border border-line px-4 py-3 shadow-card">
        <div class="text-[10.5px] text-ink-muted font-semibold mb-1.5">{{ L("Aging","التقادم","Ancienneté") }}</div>
        <div class="flex items-end gap-1 h-[26px]">
          <div v-for="a in agingBars" :key="a.k" class="flex-1 rounded-t-sm" :style="{ height: a.h + '%', minHeight: '3px', background: a.color }" :title="`${a.label}: ${a.n}`"></div>
        </div>
        <div class="flex justify-between text-[8px] text-ink-muted mt-1"><span>7d</span><span>30</span><span>60</span><span>60+</span></div>
      </div>
    </div>

    <div class="rounded-[12px] border border-amber-200 bg-amber-50 px-4 py-2.5 flex items-center gap-2.5">
      <Icon name="alert" :size="15" color="#b45309" />
      <span class="text-[11.5px] text-ink-2">{{ L("These orders are delivered but not yet invoiced — revenue isn't recognised until you bill them.","هذه الطلبات سُلّمت لكن لم تُفوتر بعد — لا يُعترف بالإيراد حتى تُفوتر.","Ces commandes sont livrées mais pas encore facturées — le revenu n'est pas reconnu.") }}</span>
    </div>

    <div class="bg-white rounded-card border border-line overflow-hidden shadow-card">
      <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
        <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#fff4e0"><Icon name="receipt" :size="14" color="#b45309" /></span>
        <span class="text-[13px] font-bold">{{ L("To bill","للفوترة","À facturer") }}</span>
        <span v-if="isLive !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="isLive ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ isLive ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échant.") }}</span>
        <span class="hidden lg:inline text-[11px] text-ink-muted">{{ L("oldest first","الأقدم أولاً","plus anciens") }}</span>
        <div class="ms-auto relative">
          <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
          <input v-model.trim="tt.search.value" :placeholder="L('Search DN / customer…','بحث…','Rechercher…')" class="w-44 sm:w-60 h-9 bg-app-warm/40 border border-line-2 rounded-[10px] ps-9 pe-3 text-[12.5px] focus:outline-none focus:border-accent/40 focus:bg-white" />
        </div>
      </div>

      <TableToolbar :t="tt" />
      <TableLoading v-if="loading" :rows="8" />
      <div v-else class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead><tr style="background:#fafaf9">
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Delivery note","السند","Bon") }}</th>
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Customer","العميل","Client") }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Age","العمر","Âge") }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Value","القيمة","Valeur") }}</th>
          </tr></thead>
          <tbody>
            <tr v-for="r in tt.pageRows.value" :key="r.name" class="border-t border-line-hair hover:bg-app-warm/50 cursor-pointer" @click="open(r.name)">
              <td class="px-4 py-2.5 font-mono text-[11.5px] font-semibold">{{ r.name }}</td>
              <td class="px-4 py-2.5 truncate max-w-[220px]">{{ r.customer }}</td>
              <td class="px-4 py-2.5 text-end"><span class="text-[10.5px] font-bold px-2 py-0.5 rounded-badge" :style="ageBadge(r.age)">{{ r.age }}{{ L("d","ي","j") }}</span></td>
              <td class="px-4 py-2.5 text-end tnum font-semibold">{{ fmt(r.value) }}</td>
            </tr>
            <tr v-if="!tt.pageRows.value.length"><td colspan="4" class="px-4 py-12 text-center text-ink-muted text-[12px]">{{ L("Nothing awaiting invoice. 🎉","لا شيء بانتظار الفوترة. 🎉","Rien à facturer. 🎉") }}</td></tr>
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
import { currentCompany } from "@/composables/useLive";
import { useTableTools } from "@/composables/useTableTools";
import { useUi } from "@/composables/useUi";

const { locale } = useI18n();
const { entityId } = useUi();
const router = useRouter();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US");
const money = (n) => { n = Number(n) || 0; return Math.abs(n) >= 1e6 ? (n / 1e6).toFixed(2) + "M" : Math.abs(n) >= 1e3 ? Math.round(n / 1e3) + "K" : Math.round(n).toLocaleString(); };

const cols = [
  { key: "name", label: "DN", align: "s" },
  { key: "customer", label: L("Customer", "العميل", "Client"), align: "s" },
  { key: "age", label: L("Age", "العمر", "Âge"), align: "e" },
  { key: "value", label: L("Value", "القيمة", "Valeur"), align: "e" },
];
const SAMPLE = [
  { name: "MAT-DN-2025-00962", customer: "COD customer", age: 120, value: 91 },
  { name: "MAT-DN-2025-00979", customer: "COD customer", age: 95, value: 114 },
];
const rows = ref([]);
const sum = ref({});
const isLive = ref(null);
const loading = ref(true);
const tt = useTableTools(rows, cols, { keyField: "name", defaultSort: "age", defaultDir: -1 });

async function load() {
  loading.value = true;
  try {
    const r = await api.call("accounting_portal.api.sales.to_bill_queue", { company: currentCompany(), limit: 400 });
    rows.value = r.rows || []; sum.value = r.summary || {}; isLive.value = true;
  } catch { rows.value = SAMPLE; sum.value = { count: 2, value: 205, currency: "MAD", value_over_60: 205, aging: { w1: 0, w2: 0, w3: 0, w4: 2 } }; isLive.value = false; }
  finally { loading.value = false; }
}
onMounted(load);
watch(entityId, load);

const agingBars = computed(() => {
  const a = sum.value.aging || {};
  const max = Math.max(a.w1 || 0, a.w2 || 0, a.w3 || 0, a.w4 || 0, 1);
  return [
    { k: "w1", label: "≤7d", n: a.w1 || 0, h: ((a.w1 || 0) / max) * 100, color: "#34d399" },
    { k: "w2", label: "8-30", n: a.w2 || 0, h: ((a.w2 || 0) / max) * 100, color: "#fbbf24" },
    { k: "w3", label: "31-60", n: a.w3 || 0, h: ((a.w3 || 0) / max) * 100, color: "#fb923c" },
    { k: "w4", label: ">60", n: a.w4 || 0, h: ((a.w4 || 0) / max) * 100, color: "#f87171" },
  ];
});

function open(name) { router.push({ path: "/accounting/sales/challans", query: { id: name } }); }
function ageBadge(d) {
  d = Number(d) || 0;
  if (d > 60) return "background:#fef2f2;color:#b91c1c";
  if (d > 30) return "background:#fff7ed;color:#c2410c";
  if (d > 7) return "background:#fffbeb;color:#b45309";
  return "background:#ecfdf5;color:#047857";
}
</script>
