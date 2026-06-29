<template>
  <div class="bg-white rounded-[14px] border border-line shadow-card overflow-hidden">
    <!-- Header -->
    <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
      <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#fff4e0"><Icon name="doc" :size="14" color="#b45309" /></span>
      <span class="text-[13px] font-bold">{{ L("Bills","الفواتير","Factures") }}</span>
      <span v-if="isLive !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border"
            :style="isLive ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ isLive ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échant.") }}</span>
      <span class="hidden lg:inline text-[11px] text-ink-muted">{{ L("Purchase Invoice · 3-way match vs PO + Goods Receipt","فاتورة شراء · مطابقة ثلاثية","Facture d’achat · rappr. 3 voies") }}</span>
      <div class="relative ms-auto">
        <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
        <input v-model.trim="st.search.value" :placeholder="L('Search bill / vendor…','بحث…','Rechercher…')" class="w-44 sm:w-64 h-9 bg-app-warm/40 border border-line-2 rounded-[10px] ps-9 pe-3 text-[12.5px] focus:outline-none focus:border-accent/40 focus:bg-white transition" />
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
          <tr v-for="b in displayRows" :key="b.id" class="border-t border-line-hair hover:bg-app-warm/70 cursor-pointer" @click="open(b.id)">
            <td class="px-4 py-2.5 font-mono font-semibold whitespace-nowrap">{{ b.id }}</td>
            <td class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ b.date || "—" }}</td>
            <td class="px-4 py-2.5 truncate max-w-[200px]">{{ b.vendor }}</td>
            <td class="px-4 py-2.5">
              <span class="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-badge border"
                    :style="{ background: MATCH_META[b.match].bg, color: MATCH_META[b.match].c, borderColor: MATCH_META[b.match].bd }">
                <Icon :name="b.match === 'ok' ? 'check' : 'alert'" :size="11" />{{ matchLabel(b.match, locale) }}
              </span>
            </td>
            <td class="px-4 py-2.5 text-end font-bold tnum whitespace-nowrap" :class="b.amount < 0 ? 'text-sale' : ''">{{ b.currency }} {{ fmt(b.amount) }}</td>
            <td class="px-4 py-2.5">
              <span class="inline-block text-[10px] font-bold px-2 py-0.5 rounded-badge border"
                    :style="{ background: BILL_STATUS[b.status].bg, color: BILL_STATUS[b.status].fg, borderColor: BILL_STATUS[b.status].bd }">
                {{ billStatusLabel(b.status, locale) }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <TableLoading v-if="st.loading.value" />
    <div v-else-if="!displayRows.length" class="py-12 text-center text-[12px] text-ink-muted">{{ L("No bills match your filters.","لا توجد فواتير مطابقة.","Aucune facture.") }}</div>
    <ServerPager :t="st" />
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import ServerPager from "@/components/ServerPager.vue";
import { MATCH_META, BILL_STATUS, matchLabel, billStatusLabel } from "@/data/purchases";
import { currentCompany } from "@/composables/useLive";
import { useServerTable } from "@/composables/useServerTable";
import { useUi } from "@/composables/useUi";
import api from "@/services/api";

const { locale } = useI18n();
const router = useRouter();
const { entityId } = useUi();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US", { maximumFractionDigits: 2 });

const cols = [
  { key: "id", label: L("Bill", "الفاتورة", "Facture"), align: "s", sort: "id" },
  { key: "date", label: L("Date", "التاريخ", "Date"), align: "s", sort: "date" },
  { key: "vendor", label: L("Vendor", "المورّد", "Fournisseur"), align: "s", sort: "supplier" },
  { key: "match", label: L("3-way match", "المطابقة", "Rappr."), align: "s" },
  { key: "amount", label: L("Amount", "المبلغ", "Montant"), align: "e", sort: "amount" },
  { key: "status", label: L("Status", "الحالة", "Statut"), align: "s" },
];

const isLive = ref(null);
const st = useServerTable(
  (params) => api.call("accounting_portal.api.purchases.list_bills", { company: currentCompany(), ...params }).then((r) => { isLive.value = true; return r; }),
  { pageSize: 25, sortField: "date", sortDir: "desc" },
);
st.load();
watch(entityId, () => { st.page.value = 1; st.load(); });

const displayRows = computed(() => (st.rows.value || []).map((r) => ({
  id: r.name, date: String(r.date || ""), vendor: r.supplier, match: r.match,
  amount: Number(r.amount) || 0, currency: r.currency || "MAD", status: r.status_norm,
})));

function open(id) { router.push({ path: "/accounting/purchases/bills", query: { id } }); }
</script>
