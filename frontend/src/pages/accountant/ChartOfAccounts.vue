<template>
  <div class="space-y-3">
    <div class="flex items-center gap-2 flex-wrap">
      <span class="text-[13px] font-bold">{{ L("Chart of accounts","دليل الحسابات","Plan comptable") }}</span>
      <span v-if="isLive !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="isLive ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ isLive ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échant.") }}</span>
      <span class="text-[11px] text-ink-muted">{{ L("live balances · anomalies in red · click to open the ledger","أرصدة حيّة · الشذوذ بالأحمر · اضغط لفتح الأستاذ","soldes en direct") }}</span>
      <div class="ms-auto relative">
        <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
        <input v-model.trim="q" :placeholder="L('Search account…','بحث…','Rechercher…')" class="w-44 sm:w-60 h-9 bg-app-warm/40 border border-line-2 rounded-[10px] ps-9 pe-3 text-[12.5px] focus:outline-none focus:border-accent/40 focus:bg-white" />
      </div>
    </div>

    <div class="bg-white rounded-[14px] border border-line shadow-card overflow-hidden">
      <TableLoading v-if="loading" :rows="10" />
      <table v-else class="w-full text-[12px]">
        <tbody>
          <template v-for="g in groups" :key="g.key">
            <tr class="bg-app-warm/50">
              <td colspan="2" class="px-4 py-2 text-[11px] font-bold uppercase tracking-wider text-ink">{{ g.label }}</td>
              <td class="px-4 py-2 text-end tnum text-[11px] font-bold text-ink-3">{{ money(g.total) }} {{ ccy }}</td>
            </tr>
            <tr v-for="(c, i) in g.rows" :key="i" class="border-t border-line-hair cursor-pointer" :class="c.anomaly ? 'bg-rose-50/40' : 'hover:bg-app-warm/60'" @click="drill(c)">
              <td class="px-4 py-2.5 font-mono text-ink-3 whitespace-nowrap w-px">{{ c.code || "—" }}</td>
              <td class="px-4 py-2.5"><span class="inline-flex items-center gap-1.5 hover:text-accent-dark">{{ c.name }}<Icon v-if="c.anomaly" name="alert" :size="12" color="#be123c" /></span></td>
              <td class="px-4 py-2.5 text-end tnum font-semibold whitespace-nowrap" :class="c.anomaly ? 'text-sale' : ''">{{ money(c.bal) }}</td>
            </tr>
          </template>
          <tr v-if="!groups.length"><td colspan="3" class="px-4 py-10 text-center text-ink-muted">{{ loading ? "" : L("No accounts.","لا حسابات.","Aucun compte.") }}</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";

const { locale } = useI18n();
const { entityId } = useUi();
const router = useRouter();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const money = (n) => { n = Number(n) || 0; const a = Math.abs(n); return (n < 0 ? "−" : "") + (a >= 1e6 ? (a / 1e6).toFixed(2) + "M" : a >= 1e3 ? (a / 1e3).toFixed(0) + "K" : Math.round(a).toLocaleString()); };

const rows = ref([]);
const isLive = ref(null);
const loading = ref(true);
const q = ref("");
const ccy = ref("MAD");

async function load() {
  loading.value = true;
  try {
    rows.value = await api.call("accounting_portal.api.ledger.chart_of_accounts", { company: currentCompany() }) || [];
    isLive.value = true;
  } catch { rows.value = []; isLive.value = false; }
  finally { loading.value = false; }
}
onMounted(load);
watch(entityId, load);

const ROOTS = [
  { key: "Asset", label: () => L("Assets", "الأصول", "Actifs") },
  { key: "Liability", label: () => L("Liabilities", "الخصوم", "Passifs") },
  { key: "Equity", label: () => L("Equity", "حقوق الملكية", "Capitaux") },
  { key: "Income", label: () => L("Income", "الإيرادات", "Produits") },
  { key: "Expense", label: () => L("Expenses", "المصروفات", "Charges") },
];
const groups = computed(() => {
  const needle = q.value.toLowerCase();
  const filtered = needle ? rows.value.filter((r) => String(r.name).toLowerCase().includes(needle) || String(r.code || "").includes(needle)) : rows.value;
  return ROOTS.map((g) => {
    const gr = filtered.filter((r) => r.root_type === g.key);
    return { key: g.key, label: g.label(), rows: gr, total: gr.reduce((s, r) => s + (Number(r.bal) || 0), 0) };
  }).filter((g) => g.rows.length);
});

function drill(c) {
  const acct = c.account || (c.code ? `${c.code} - ${c.name}` : c.name);
  router.push({ path: "/accounting/accountant/gl", query: { account: acct } });
}
</script>
