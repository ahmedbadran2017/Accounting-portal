<template>
  <div class="space-y-3.5">
    <!-- KPI cards (whole filtered set, computed server-side) -->
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
      <StatCard :label="L('Invoices','الفواتير','Factures')" :value="kpi.count.toLocaleString()" :sub="L('in view','في العرض','vues')" :tag="filterTag" icon="receipt" color="#1c1917" glow="#a8a29e" tint="#fafaf9" />
      <StatCard :label="L('Net revenue','صافي الإيراد','Produits HT')" :value="money(kpi.net)" sub="MAD" :tag="filterTag" icon="trend" color="#047857" glow="#34d399" tint="#ecfdf5" valueColor="#047857" />
      <StatCard :label="L('VAT output','ض.ق.م مخرجات','TVA collectée')" :value="money(kpi.vat)" sub="MAD" :tag="filterTag" icon="scale" color="#b45309" glow="#f59e0b" tint="#fffbeb" />
      <StatCard :label="L('Overdue','متأخّرة','En retard')" :value="kpi.overdue.toLocaleString()" :sub="L('unpaid','غير مدفوعة','impayées')" :tag="filterTag" icon="alert" color="#be123c" glow="#f87171" tint="#fef2f2" :valueColor="kpi.overdue ? '#be123c' : undefined" />
    </div>

    <DateFilterBar :df="df" />

    <div class="bg-white rounded-card border border-line overflow-hidden shadow-card">
      <!-- Header -->
      <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
        <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#faf6f4"><Icon name="receipt" :size="14" color="#0b5c4f" /></span>
        <span class="text-[13px] font-bold">{{ L("Invoices","الفواتير","Factures") }}</span>
        <span v-if="isLive !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="isLive ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ isLive ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échant.") }}</span>
        <span class="hidden lg:inline text-[11px] text-ink-muted">{{ (st.total.value || 0).toLocaleString() }} {{ L("records","سجل","enreg.") }}</span>
        <div class="relative ms-auto">
          <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
          <input v-model.trim="st.search.value" :placeholder="L('Search invoice / customer…','بحث…','Rechercher…')" class="w-44 sm:w-64 h-9 bg-app-warm/40 border border-line-2 rounded-[10px] ps-9 pe-3 text-[12.5px] focus:outline-none focus:border-accent/40 focus:bg-white transition" />
        </div>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead>
            <tr style="background:#fafaf9">
              <th v-for="c in cols" :key="c.key"
                  class="px-4 py-2.5 text-[10px] font-bold uppercase tracking-wider text-ink-muted whitespace-nowrap select-none"
                  :class="[c.align === 'e' ? 'text-end' : 'text-start', c.sort ? 'cursor-pointer hover:text-ink-2' : '']" @click="c.sort && st.setSort(c.sort)">
                <span class="inline-flex items-center gap-1" :class="c.align === 'e' ? 'flex-row-reverse' : ''">{{ c.label }}
                  <Icon v-if="c.sort && st.sortField.value === c.sort" name="chevDown" :size="11" :class="st.sortDir.value === 'asc' ? 'rotate-180' : ''" color="#0b5c4f" /></span>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="inv in displayRows" :key="inv.id" class="border-t border-line-hair hover:bg-app-warm/70 cursor-pointer" @click="open(inv.id)">
              <td class="px-4 py-2.5 font-mono font-semibold whitespace-nowrap">{{ inv.id }}</td>
              <td class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ inv.date }}</td>
              <td class="px-4 py-2.5 truncate max-w-[180px]">{{ inv.customer }}</td>
              <td class="px-4 py-2.5 text-end tnum">{{ fmt2(inv.net) }}</td>
              <td class="px-4 py-2.5 text-end tnum text-ink-3">{{ fmt2(inv.vat) }}</td>
              <td class="px-4 py-2.5 text-end tnum font-bold">{{ fmt2(inv.gross) }}</td>
              <td class="px-4 py-2.5">
                <span class="inline-block text-[10px] font-bold px-2 py-0.5 rounded-badge border"
                      :style="{ background: INV_STATUS[inv.status].bg, color: INV_STATUS[inv.status].fg, borderColor: INV_STATUS[inv.status].bd }">{{ invStatusLabel(inv.status, locale) }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <TableLoading v-if="st.loading.value" />
      <div v-else-if="!displayRows.length" class="py-12 text-center text-[12px] text-ink-muted">{{ L("No invoices match your filters.","لا توجد فواتير مطابقة.","Aucune facture.") }}</div>
      <ServerPager :t="st" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import StatCard from "@/components/StatCard.vue";
import TableLoading from "@/components/TableLoading.vue";
import ServerPager from "@/components/ServerPager.vue";
import { INV_STATUS, invStatusLabel, invStatusFromRow, fmt2 } from "@/data/invoices";
import { currentCompany } from "@/composables/useLive";
import { useServerTable } from "@/composables/useServerTable";
import { useDateFilter } from "@/composables/useDateFilter";
import DateFilterBar from "@/components/DateFilterBar.vue";
import { useUi } from "@/composables/useUi";
import api from "@/services/api";

const { locale } = useI18n();
const router = useRouter();
const { entityId } = useUi();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const money = (n) => { n = Number(n) || 0; return Math.abs(n) >= 1e6 ? (n / 1e6).toFixed(2) + "M" : Math.abs(n) >= 1e3 ? Math.round(n / 1e3) + "K" : Math.round(n).toLocaleString(); };

const cols = [
  { key: "id", label: L("Invoice", "الفاتورة", "Facture"), align: "s", sort: "id" },
  { key: "date", label: L("Date", "التاريخ", "Date"), align: "s", sort: "date" },
  { key: "customer", label: L("Customer", "العميل", "Client"), align: "s", sort: "customer" },
  { key: "net", label: L("Net", "الصافي", "HT"), align: "e" },
  { key: "vat", label: L("VAT 20%", "ضريبة 20%", "TVA 20%"), align: "e" },
  { key: "gross", label: L("Gross", "الإجمالي", "TTC"), align: "e", sort: "gross" },
  { key: "status", label: L("Status", "الحالة", "Statut"), align: "s" },
];

const isLive = ref(null);
const df = useDateFilter("invoices", (f) => st.setFilters(f));
const st = useServerTable(
  (params) => api.call("accounting_portal.api.sales.list_invoices", { company: currentCompany(), ...params }).then((r) => { isLive.value = true; return r; }),
  { pageSize: 25, sortField: "date", sortDir: "desc", filters: df.filterValue() },
);
st.load();
watch(entityId, () => { st.page.value = 1; st.load(); });

const displayRows = computed(() => (st.rows.value || []).map((r) => ({
  id: r.name, date: String(r.date || ""), customer: r.customer, net: r.net, vat: r.vat,
  gross: r.gross, outstanding: r.outstanding_amount, status: invStatusFromRow(r),
})));

// KPI cards from the server-side summary (whole filtered set, not just this page).
const kpi = computed(() => {
  const s = (st.extra.value && st.extra.value.summary) || {};
  return { count: s.count || st.total.value || 0, net: s.net || 0, vat: s.vat || 0, overdue: s.overdue || 0 };
});
const filterTag = computed(() => (st.search.value ? L("filtered", "مفلتر", "filtré") : ""));

function open(id) { router.push({ path: "/accounting/sales/invoices", query: { id } }); }
</script>
