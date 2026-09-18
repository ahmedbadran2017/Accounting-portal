<template>
  <div class="space-y-3.5">
    <!-- KPI cards (whole filtered set, computed server-side) -->
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
      <StatCard :label="L('Received','المُحصّل','Encaissé')" :value="money(kpi.total)" sub="MAD" :tag="filterTag" icon="coins" color="#0f766e" glow="#5dcaa5" tint="#e1f5ee" valueColor="#0f766e" />
      <StatCard :label="L('Payments','الدفعات','Paiements')" :value="kpi.count.toLocaleString()" :sub="L('records','سجل','enreg.')" :tag="filterTag" icon="receipt" color="#1c1917" glow="#a8a29e" tint="#fafaf9" />
      <StatCard :label="L('Average','المتوسّط','Moyenne')" :value="money(kpi.avg)" sub="MAD" :tag="filterTag" icon="scale" color="#0369a1" glow="#85b7eb" tint="#eff6ff" />
      <StatCard :label="L('Via Cathedis','عبر كاتدييس','Via Cathedis')" :value="kpi.cath.toLocaleString()" :sub="kpi.count ? Math.round(kpi.cath / kpi.count * 100) + '%' : '—'" :tag="filterTag" icon="truck" color="#7c3aed" glow="#a78bfa" tint="#f5f3ff" />
    </div>

    <DateFilterBar :df="df" />

    <div class="bg-white rounded-card border border-line overflow-hidden shadow-card">
      <!-- Header -->
      <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
        <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#e1f5ee"><Icon name="wallet" :size="14" color="#0b5c4f" /></span>
        <span class="text-[13px] font-bold">{{ L("Payments received","المدفوعات المُحصّلة","Encaissements") }}</span>
        <LiveBadge :live="isLive" />
        <span class="hidden lg:inline text-[11px] text-ink-muted">{{ (st.total.value || 0).toLocaleString() }} {{ L("records","سجل","enreg.") }}</span>
        <div class="relative ms-auto">
          <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
          <input v-model.trim="st.search.value" :placeholder="L('Search payment / customer…','بحث…','Rechercher…')" class="fld fld-md fld-sunk w-44 sm:w-64" />
        </div>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead>
            <tr style="background:#fafaf9">
              <th class="w-8 px-3"><input type="checkbox" :checked="st.allSelected.value" @change="st.toggleAll()" /></th>
            <th v-for="c in cols" :key="c.key"
                  class="px-4 py-2.5 text-[11px] font-bold uppercase tracking-wider text-ink-muted whitespace-nowrap select-none"
                  :class="[c.align === 'e' ? 'text-end' : 'text-start', c.sort ? 'cursor-pointer hover:text-ink-2' : '']" @click="c.sort && st.setSort(c.sort)">
                <span class="inline-flex items-center gap-1" :class="c.align === 'e' ? 'flex-row-reverse' : ''">{{ c.label }}
                  <Icon v-if="c.sort && st.sortField.value === c.sort" name="chevDown" :size="11" :class="st.sortDir.value === 'asc' ? 'rotate-180' : ''" color="#0b5c4f" /></span>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in displayRows" :key="p.name" class="border-t border-line-hair hover:bg-app-warm/70 cursor-pointer" @click="open(p.name)">
              <td class="px-3 py-2" @click.stop><input type="checkbox" :checked="st.selected.value.has(p.name)" @change="st.toggle(p.name)" /></td>
              <td class="px-4 py-2.5 font-mono font-semibold whitespace-nowrap">{{ p.name }}<span v-if="p.docstatus === 0" class="ms-1.5 text-[11px] font-bold px-1.5 py-0.5 rounded-full font-sans" style="background:#fffbeb;color:#b45309">{{ L("Draft","مسودة","Brouillon") }}</span></td>
              <td class="px-4 py-2.5 truncate max-w-[200px]">{{ p.customer }}</td>
              <td class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ p.date }}</td>
              <td class="px-4 py-2.5 whitespace-nowrap">
                <span v-if="p.method && p.method !== '—'" class="inline-flex items-center gap-1.5 text-[11px] font-semibold px-2 py-0.5 rounded-full" :style="methodStyle(p.method)">
                  <Icon v-if="/cath/i.test(p.method)" name="truck" :size="11" />{{ p.method }}
                </span>
                <span v-else class="text-ink-muted">—</span>
              </td>
              <td class="px-4 py-2.5 text-end tnum font-bold whitespace-nowrap">{{ fmt2(p.amount) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <TableLoading v-if="st.loading.value" />
      <div v-else-if="!displayRows.length" class="py-12 text-center text-[12px] text-ink-muted">{{ L("No payments match your filters.","لا توجد مدفوعات مطابقة.","Aucun paiement.") }}</div>
      <ListToolbar v-model:status="listStatus" v-model:pageSize="listPageSize" :total="st.total.value" export-key="payments_in" :export-filters="exportFilters" :extra-statuses="extraStatuses" />
    <ServerPager :t="st" />
    <BulkBar :t="st" :actions="bulkActions" filename="payments-received" />
    </div>
  </div>
</template>

<script setup>
import { fmtAmount } from "@/utils/helpers";
import { computed, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import LiveBadge from "@/components/LiveBadge.vue";
import StatCard from "@/components/StatCard.vue";
import TableLoading from "@/components/TableLoading.vue";
import ServerPager from "@/components/ServerPager.vue";
import ListToolbar from "@/components/ListToolbar.vue";
import BulkBar from "@/components/BulkBar.vue";
import { useBulkDocs } from "@/composables/useBulkDocs";
import { currentCompany } from "@/composables/useLive";
import { useServerTable } from "@/composables/useServerTable";
import { usePersistedRef } from "@/composables/usePersistedRef";
import { useDateFilter } from "@/composables/useDateFilter";
import DateFilterBar from "@/components/DateFilterBar.vue";
import { useUi } from "@/composables/useUi";
import api from "@/services/api";

const { locale } = useI18n();
const router = useRouter();
const { entityId } = useUi();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
function open(name) { router.push({ path: "/accounting/sales/payments", query: { id: name } }); }
const money = (n) => fmtAmount(n);
const fmt2 = (n) => Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
function methodStyle(m) { return /cath/i.test(m) ? "background:#f5f3ff;color:#6d28d9" : "background:#eff6ff;color:#0369a1"; }

const cols = [
  { key: "name", label: L("Payment", "الدفعة", "Paiement"), align: "s", sort: "id" },
  { key: "customer", label: L("Customer", "العميل", "Client"), align: "s", sort: "customer" },
  { key: "date", label: L("Date", "التاريخ", "Date"), align: "s", sort: "date" },
  { key: "method", label: L("Method", "الطريقة", "Méthode"), align: "s" },
  { key: "amount", label: L("Amount", "المبلغ", "Montant"), align: "e", sort: "collected" },
];

const isLive = ref(null);
const df = useDateFilter("receipts", (f) => st.setFilters(f));
const { actions: bulkActions } = useBulkDocs("Payment Entry", () => st);
const st = useServerTable(
  (params) => api.call("accounting_portal.api.sales.list_receipts", { company: currentCompany(), ...params }).then((r) => { isLive.value = true; return r; }),
  { pageSize: 25, sortField: "date", sortDir: "desc", filters: df.filterValue() , storeKey: "pay_in" },
);
// Status chips + page size + full-list Excel (ListToolbar).
const listStatus = usePersistedRef("ap_ls_payments_in", "open");
const listPageSize = usePersistedRef("ap_lps_payments_in", 25);
const extraStatuses = [];
const exportFilters = computed(() => ({ ...st.filters.value, search: st.search.value || undefined, status: listStatus.value }));
let _lsFirst = true;
watch([listStatus, listPageSize], () => {
  st.pageSize.value = listPageSize.value;
  // First run seeds the filter before the page's own initial load, so opening
  // the list costs one request, not two.
  if (_lsFirst) { _lsFirst = false; st.filters.value = { ...st.filters.value, status: listStatus.value }; return; }
  st.setFilters({ status: listStatus.value });
}, { immediate: true });

st.load();
watch(entityId, () => { st.page.value = 1; st.load(); });

const displayRows = computed(() => (st.rows.value || []).map((r) => ({
  name: r.name, customer: r.customer, date: String(r.date || ""), method: r.method || "—", amount: Number(r.collected) || 0,
})));

const kpi = computed(() => {
  const s = (st.extra.value && st.extra.value.summary) || {};
  return { count: s.count || st.total.value || 0, total: s.total || 0, avg: s.avg || 0, cath: s.cath || 0 };
});
const filterTag = computed(() => (st.search.value ? L("filtered", "مفلتر", "filtré") : ""));
</script>
