<template>
  <div class="bg-white rounded-[14px] border border-line shadow-card overflow-hidden">
    <!-- Header -->
    <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
      <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#fff4e0"><Icon name="doc" :size="14" color="#b45309" /></span>
      <span class="text-[13px] font-bold">{{ L("Bills","الفواتير","Factures") }}</span>
      <span v-if="isLive !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border"
            :style="isLive ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ isLive ? "Live" : "Sample" }}</span>
      <span class="hidden lg:inline text-[11px] text-ink-muted">{{ L("Purchase Invoice · 3-way match vs PO + Goods Receipt","فاتورة شراء · مطابقة ثلاثية","Facture d’achat · rappr. 3 voies") }}</span>
      <div class="relative ms-auto">
        <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
        <input v-model.trim="tt.search.value" :placeholder="L('Search bill / vendor…','بحث…','Rechercher…')" class="w-44 sm:w-64 h-9 bg-app-warm/40 border border-line-2 rounded-[10px] ps-9 pe-3 text-[12.5px] focus:outline-none focus:border-accent/40 focus:bg-white transition" />
      </div>
    </div>

    <TableToolbar :t="tt" filename="bills" />

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
          <tr v-for="b in tt.pageRows.value" :key="b.id" class="border-t border-line-hair hover:bg-app-warm/70 cursor-pointer" :class="tt.isSelected(b) ? 'bg-accent/5' : ''" @click="open(b.id)">
            <td class="px-3 py-2.5 w-9" @click.stop><input type="checkbox" :checked="tt.isSelected(b)" @change="tt.toggleRow(b)" class="accent-accent w-3.5 h-3.5 align-middle" /></td>
            <td v-show="!tt.hidden.value.has('id')" class="px-4 py-2.5 font-mono font-semibold whitespace-nowrap">{{ b.id }}</td>
            <td v-show="!tt.hidden.value.has('date')" class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ b.date || "—" }}</td>
            <td v-show="!tt.hidden.value.has('vendor')" class="px-4 py-2.5 truncate max-w-[200px]">{{ b.vendor }}</td>
            <td v-show="!tt.hidden.value.has('match')" class="px-4 py-2.5">
              <span class="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-badge border"
                    :style="{ background: MATCH_META[b.match].bg, color: MATCH_META[b.match].c, borderColor: MATCH_META[b.match].bd }">
                <Icon :name="b.match === 'ok' ? 'check' : 'alert'" :size="11" />{{ matchLabel(b.match, locale) }}
              </span>
            </td>
            <td v-show="!tt.hidden.value.has('amount')" class="px-4 py-2.5 text-end font-bold tnum whitespace-nowrap" :class="b.amount < 0 ? 'text-sale' : ''">{{ b.currency }} {{ fmt(b.amount) }}</td>
            <td v-show="!tt.hidden.value.has('status')" class="px-4 py-2.5">
              <span class="inline-block text-[10px] font-bold px-2 py-0.5 rounded-badge border"
                    :style="{ background: BILL_STATUS[b.status].bg, color: BILL_STATUS[b.status].fg, borderColor: BILL_STATUS[b.status].bd }">
                {{ billStatusLabel(b.status, locale) }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="!tt.sorted.value.length" class="py-12 text-center text-[12px] text-ink-muted">{{ L("No bills match your filters.","لا توجد فواتير مطابقة.","Aucune facture.") }}</div>
    <TablePager :t="tt" />

    <BulkBar :t="tt" filename="bills-selected" :actions="bulkActions" />
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableToolbar from "@/components/TableToolbar.vue";
import TablePager from "@/components/TablePager.vue";
import { BILLS, MATCH_META, BILL_STATUS, matchLabel, billStatusLabel } from "@/data/purchases";
import { liveOrSample, currentCompany } from "@/composables/useLive";
import { useTableTools } from "@/composables/useTableTools";
import BulkBar from "@/components/BulkBar.vue";
import { useBulkDocActions } from "@/composables/useBulkActions";

const { locale } = useI18n();
const router = useRouter();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US", { maximumFractionDigits: 2 });

const cols = [
  { key: "id", label: L("Bill", "الفاتورة", "Facture"), align: "s" },
  { key: "date", label: L("Date", "التاريخ", "Date"), align: "s" },
  { key: "vendor", label: L("Vendor", "المورّد", "Fournisseur"), align: "s" },
  { key: "match", label: L("3-way match", "المطابقة", "Rappr."), align: "s" },
  { key: "amount", label: L("Amount", "المبلغ", "Montant"), align: "e" },
  { key: "status", label: L("Status", "الحالة", "Statut"), align: "s" },
];

const rows = ref(normalizeSample(BILLS));
const isLive = ref(null);
const tt = useTableTools(rows, cols, {
  keyField: "id", dateKey: "date", defaultSort: "date", defaultDir: -1,
  facets: [
    { key: "status", label: L("status", "حالة", "statut"), format: (v) => billStatusLabel(v, locale.value) },
    { key: "match", label: L("match", "مطابقة", "rappr."), format: (v) => matchLabel(v, locale.value) },
  ],
});

// Sample rows store amount as a formatted string; normalise to {amount:number, currency}.
function normalizeSample(list) {
  return list.map((b) => {
    if (typeof b.amount === "number") return b;
    const m = String(b.amount || "").match(/^([^\d-]*)\s*(-?[\d.,]+)/);
    return { ...b, date: b.date || "", currency: (m && m[1].trim()) || "MAD", amount: m ? Number(m[2].replace(/,/g, "")) : 0 };
  });
}

async function load() {
  const res = await liveOrSample(
    "accounting_portal.api.purchases.list_bills", { company: currentCompany(), limit: 500 }, () => normalizeSample(BILLS),
    (data) => data.map((r) => ({
      id: r.name, date: String(r.date || ""), vendor: r.supplier, match: r.match,
      amount: Number(r.amount) || 0, currency: r.currency || "MAD", status: r.status_norm,
    })),
  );
  rows.value = res.data;
  isLive.value = res.live;
}
onMounted(load);
const bulkActions = useBulkDocActions("Purchase Invoice", { keyField: "id", onDone: () => { tt.clearSelection(); load(); }, L });

function open(id) { router.push({ path: "/accounting/purchases/bills", query: { id } }); }
</script>
