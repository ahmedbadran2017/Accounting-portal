<template>
  <div class="space-y-3.5">
    <!-- KPI cards (reflect the filtered view) -->
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
      <StatCard :label="L('Received','المُحصّل','Encaissé')" :value="money(kpi.total)" sub="MAD" :tag="filterTag" icon="coins" color="#0f766e" glow="#5dcaa5" tint="#e1f5ee" valueColor="#0f766e" />
      <StatCard :label="L('Payments','الدفعات','Paiements')" :value="kpi.count.toLocaleString()" :sub="L('records','سجل','enreg.')" :tag="filterTag" icon="receipt" color="#1c1917" glow="#a8a29e" tint="#fafaf9" />
      <StatCard :label="L('Average','المتوسّط','Moyenne')" :value="money(kpi.avg)" sub="MAD" :tag="filterTag" icon="scale" color="#0369a1" glow="#85b7eb" tint="#eff6ff" />
      <StatCard :label="L('Via Cathedis','عبر كاتدييس','Via Cathedis')" :value="kpi.cath.toLocaleString()" :sub="kpi.count ? Math.round(kpi.cath / kpi.count * 100) + '%' : '—'" :tag="filterTag" icon="truck" color="#7c3aed" glow="#a78bfa" tint="#f5f3ff" />
    </div>

    <div class="bg-white rounded-card border border-line overflow-hidden shadow-card">
      <!-- Header -->
      <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
        <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#e1f5ee"><Icon name="wallet" :size="14" color="#0b5c4f" /></span>
        <span class="text-[13px] font-bold">{{ L("Payments received","المدفوعات المُحصّلة","Encaissements") }}</span>
        <span v-if="isLive !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="isLive ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ isLive ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échant.") }}</span>
        <span class="hidden lg:inline text-[11px] text-ink-muted">{{ rows.length }} {{ L("records","سجل","enreg.") }}</span>
        <div class="relative ms-auto">
          <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
          <input v-model.trim="tt.search.value" :placeholder="L('Search payment / customer…','بحث…','Rechercher…')" class="w-44 sm:w-64 h-9 bg-app-warm/40 border border-line-2 rounded-[10px] ps-9 pe-3 text-[12.5px] focus:outline-none focus:border-accent/40 focus:bg-white transition" />
        </div>
      </div>

      <TableToolbar :t="tt" filename="payments" />

      <div class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead>
            <tr style="background:#fafaf9">
              <th class="px-3 py-2.5 w-9"><input type="checkbox" :checked="tt.allFilteredSelected.value" @change="tt.toggleAllFiltered()" class="accent-accent w-3.5 h-3.5 align-middle" /></th>
              <th v-for="c in cols" v-show="!tt.hidden.value.has(c.key)" :key="c.key"
                  class="px-4 py-2.5 text-[10px] font-bold uppercase tracking-wider text-ink-muted whitespace-nowrap cursor-pointer select-none hover:text-ink-2"
                  :class="c.align === 'e' ? 'text-end' : 'text-start'" @click="tt.toggleSort(c.key)">
                <span class="inline-flex items-center gap-1" :class="c.align === 'e' ? 'flex-row-reverse' : ''">{{ c.label }}
                  <Icon v-if="tt.sortKey.value === c.key" name="chevDown" :size="11" :class="tt.sortDir.value === 1 ? '' : 'rotate-180'" color="#0b5c4f" /></span>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in tt.pageRows.value" :key="p.name" class="border-t border-line-hair hover:bg-app-warm/70 cursor-pointer" :class="tt.isSelected(p) ? 'bg-accent/5' : ''" @click="open(p.name)">
              <td class="px-3 py-2.5 w-9" @click.stop><input type="checkbox" :checked="tt.isSelected(p)" @change="tt.toggleRow(p)" class="accent-accent w-3.5 h-3.5 align-middle" /></td>
              <td v-show="!tt.hidden.value.has('name')" class="px-4 py-2.5 font-mono font-semibold whitespace-nowrap">{{ p.name }}</td>
              <td v-show="!tt.hidden.value.has('customer')" class="px-4 py-2.5 truncate max-w-[200px]">{{ p.customer }}</td>
              <td v-show="!tt.hidden.value.has('date')" class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ p.date }}</td>
              <td v-show="!tt.hidden.value.has('method')" class="px-4 py-2.5 whitespace-nowrap">
                <span v-if="p.method && p.method !== '—'" class="inline-flex items-center gap-1.5 text-[11px] font-semibold px-2 py-0.5 rounded-full" :style="methodStyle(p.method)">
                  <Icon v-if="/cath/i.test(p.method)" name="truck" :size="11" />{{ p.method }}
                </span>
                <span v-else class="text-ink-muted">—</span>
              </td>
              <td v-show="!tt.hidden.value.has('amount')" class="px-4 py-2.5 text-end tnum font-bold whitespace-nowrap">{{ fmt2(p.amount) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <TableLoading v-if="loading" />
      <div v-else-if="!tt.sorted.value.length" class="py-12 text-center text-[12px] text-ink-muted">{{ L("No payments match your filters.","لا توجد مدفوعات مطابقة.","Aucun paiement.") }}</div>
      <TablePager :t="tt" />
    </div>

    <BulkBar :t="tt" filename="payments-received-selected" :actions="bulkActions" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import StatCard from "@/components/StatCard.vue";
import TableToolbar from "@/components/TableToolbar.vue";
import TablePager from "@/components/TablePager.vue";
import TableLoading from "@/components/TableLoading.vue";
import { liveOrSample, currentCompany } from "@/composables/useLive";
import { useTableTools } from "@/composables/useTableTools";
import BulkBar from "@/components/BulkBar.vue";
import { useBulkDocActions } from "@/composables/useBulkActions";

const { locale } = useI18n();
const router = useRouter();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
function open(name) { router.push({ path: "/accounting/sales/payments", query: { id: name } }); }
const money = (n) => { n = Number(n) || 0; return Math.abs(n) >= 1e6 ? (n / 1e6).toFixed(2) + "M" : Math.abs(n) >= 1e3 ? Math.round(n / 1e3) + "K" : Math.round(n).toLocaleString(); };
const fmt2 = (n) => Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
function methodStyle(m) { return /cath/i.test(m) ? "background:#f5f3ff;color:#6d28d9" : "background:#eff6ff;color:#0369a1"; }

const SAMPLE = [
  { name: "PAY-22493", customer: "Lachhed najia", date: "2026-06-20", method: "Cathadis Transactions", amount: 129 },
  { name: "PAY-22491", customer: "زكرياء الرحماني", date: "2026-06-21", method: "Cathadis Transactions", amount: 129 },
  { name: "PAY-22475", customer: "Siham Elfilali", date: "2026-06-20", method: "Cathadis Transactions", amount: 298 },
];
const cols = [
  { key: "name", label: L("Payment", "الدفعة", "Paiement"), align: "s" },
  { key: "customer", label: L("Customer", "العميل", "Client"), align: "s" },
  { key: "date", label: L("Date", "التاريخ", "Date"), align: "s" },
  { key: "method", label: L("Method", "الطريقة", "Méthode"), align: "s" },
  { key: "amount", label: L("Amount", "المبلغ", "Montant"), align: "e" },
];

const rows = ref([]);
const isLive = ref(null);
const loading = ref(true);
const tt = useTableTools(rows, cols, {
  keyField: "name", dateKey: "date", defaultSort: "date", defaultDir: -1,
  facets: [{ key: "method", label: L("method", "طريقة", "méthode") }],
});

async function load() {
  loading.value = true;
  try {
    const res = await liveOrSample(
      "accounting_portal.api.sales.list_receipts", { company: currentCompany(), limit: 500 }, () => SAMPLE,
      (data) => data.map((r) => ({ name: r.name, customer: r.customer, date: String(r.date || ""), method: r.method || "—", amount: Number(r.collected) || 0 })),
    );
    rows.value = res.data;
    isLive.value = res.live;
  } finally { loading.value = false; }
}
onMounted(load);
const bulkActions = useBulkDocActions("Payment Entry", { keyField: "name", ops: ["cancel"], onDone: () => { tt.clearSelection(); load(); }, L });

const kpi = computed(() => {
  const rs = tt.sorted.value;
  const total = rs.reduce((s, r) => s + (Number(r.amount) || 0), 0);
  const cath = rs.filter((r) => /cath/i.test(r.method || "")).length;
  return { count: rs.length, total, avg: rs.length ? total / rs.length : 0, cath };
});
const filterTag = computed(() => (tt.search.value || tt.datePreset.value !== "month" || Object.values(tt.facetActive.value).some(Boolean)) ? L("filtered", "مفلتر", "filtré") : "");
</script>
