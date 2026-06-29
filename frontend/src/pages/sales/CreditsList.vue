<template>
  <div class="space-y-3">
    <DateFilterBar :df="df" />
    <div class="bg-white rounded-card border border-line overflow-hidden shadow-card">
      <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
        <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#fef2f2"><Icon name="refresh" :size="14" color="#b91c1c" /></span>
        <span class="text-[13px] font-bold">{{ L("Returns & credit notes","المرتجعات وإشعارات الدائن","Retours & avoirs") }}</span>
        <span v-if="isLive !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="isLive ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ isLive ? L("Live","مباشر","Live") : L("Sample","عينة","Échant.") }}</span>
        <span class="hidden lg:inline text-[11px] text-ink-muted">{{ (st.total.value || 0).toLocaleString() }} · {{ L("returned / exception orders","مرتجع / استثناء","retours / exceptions") }}</span>
        <div class="ms-auto relative">
          <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
          <input v-model.trim="st.search.value" :placeholder="L('Search order / customer…','بحث…','Rechercher…')" class="w-44 sm:w-60 h-9 bg-app-warm/40 border border-line-2 rounded-[10px] ps-9 pe-3 text-[12.5px] focus:outline-none focus:border-accent/40 focus:bg-white" />
        </div>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead><tr style="background:#fafaf9">
            <th v-for="c in cols" :key="c.key" class="px-4 py-2.5 text-[10px] font-bold uppercase tracking-wider text-ink-muted whitespace-nowrap select-none"
                :class="[c.align === 'e' ? 'text-end' : 'text-start', c.sort ? 'cursor-pointer hover:text-ink-2' : '']" @click="c.sort && st.setSort(c.sort)">
              <span class="inline-flex items-center gap-1" :class="c.align === 'e' ? 'flex-row-reverse' : ''">{{ c.label }}
                <Icon v-if="c.sort && st.sortField.value === c.sort" name="chevDown" :size="11" :class="st.sortDir.value === 'asc' ? 'rotate-180' : ''" color="#0b5c4f" /></span>
            </th>
          </tr></thead>
          <tbody>
            <tr v-for="r in st.rows.value" :key="r.name" class="border-t border-line-hair hover:bg-app-warm/50 cursor-pointer" @click="open(r.name)">
              <td class="px-4 py-2.5 font-mono text-[11.5px] font-semibold">{{ r.name }}</td>
              <td class="px-4 py-2.5 truncate max-w-[200px]">{{ r.customer }}</td>
              <td class="px-4 py-2.5"><span class="inline-flex text-[10.5px] font-bold px-2 py-0.5 rounded-badge" :style="reasonBadge(r.reason)">{{ r.reason || '—' }}</span></td>
              <td class="px-4 py-2.5 text-end tnum font-semibold text-sale">{{ fmt(r.amount) }}</td>
              <td class="px-4 py-2.5 text-end text-ink-3 whitespace-nowrap">{{ String(r.date || "") }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <TableLoading v-if="st.loading.value" :rows="8" />
      <div v-else-if="!st.rows.value.length" class="px-4 py-12 text-center text-ink-muted text-[12px]">{{ L("No returns.","لا مرتجعات.","Aucun retour.") }}</div>
      <ServerPager :t="st" />
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import ServerPager from "@/components/ServerPager.vue";
import TableLoading from "@/components/TableLoading.vue";
import DateFilterBar from "@/components/DateFilterBar.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useServerTable } from "@/composables/useServerTable";
import { useDateFilter } from "@/composables/useDateFilter";
import { useUi } from "@/composables/useUi";

const { locale } = useI18n();
const { entityId } = useUi();
const router = useRouter();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US");

const cols = [
  { key: "name", label: L("Order", "الطلب", "Commande"), align: "s", sort: "id" },
  { key: "customer", label: L("Customer", "العميل", "Client"), align: "s", sort: "customer" },
  { key: "reason", label: L("Reason", "السبب", "Motif"), align: "s" },
  { key: "amount", label: L("Amount", "المبلغ", "Montant"), align: "e", sort: "amount" },
  { key: "date", label: L("Date", "التاريخ", "Date"), align: "e", sort: "date" },
];

const isLive = ref(null);
const df = useDateFilter("credits", (f) => st.setFilters(f));
const st = useServerTable(
  (params) => api.call("accounting_portal.api.sales.list_credits", { company: currentCompany(), ...params }).then((r) => { isLive.value = true; return r; }),
  { pageSize: 25, sortField: "date", sortDir: "desc", filters: df.filterValue() },
);
st.load();
watch(entityId, () => { st.page.value = 1; st.load(); });

// Returns are Sales Orders — open the order detail.
function open(name) { router.push({ path: "/accounting/sales/orders", query: { id: name } }); }

function reasonBadge(r) {
  const v = String(r || "").toLowerCase();
  if (v.includes("return")) return "background:#fef2f2;color:#b91c1c";
  if (v.includes("excep") || v.includes("fail")) return "background:#fffbeb;color:#b45309";
  return "background:#f5f5f4;color:#57534e";
}
</script>
