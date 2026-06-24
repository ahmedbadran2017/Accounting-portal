<template>
  <div class="space-y-3.5">
    <!-- Tiles -->
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
      <div v-for="ti in tiles" :key="ti.label" class="bg-white rounded-card border border-line p-3">
        <div class="text-[10px] text-ink-muted uppercase tracking-wide">{{ ti.label }}</div>
        <div class="text-[18px] font-bold tnum mt-0.5" :style="{ color: ti.color }">{{ ti.value }}</div>
      </div>
    </div>

    <div class="bg-white rounded-card border border-line overflow-hidden shadow-card">
      <!-- Header -->
      <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
        <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#faf6f4"><Icon name="receipt" :size="14" color="#a33a22" /></span>
        <span class="text-[13px] font-bold">{{ L("Invoices","الفواتير","Factures") }}</span>
        <span v-if="isLive !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="isLive ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ isLive ? "Live" : "Sample" }}</span>
        <span class="hidden lg:inline text-[11px] text-ink-muted">{{ rows.length }} {{ L("records","سجل","enreg.") }}</span>
        <div class="relative ms-auto">
          <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
          <input v-model.trim="tt.search.value" :placeholder="L('Search invoice / customer…','بحث…','Rechercher…')" class="w-44 sm:w-64 h-9 bg-app-warm/40 border border-line-2 rounded-[10px] ps-9 pe-3 text-[12.5px] focus:outline-none focus:border-accent/40 focus:bg-white transition" />
        </div>
      </div>

      <TableToolbar :t="tt" filename="invoices" />

      <div class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead>
            <tr style="background:#fafaf9">
              <th v-for="c in cols" v-show="!tt.hidden.value.has(c.key)" :key="c.key"
                  class="px-4 py-2.5 text-[10px] font-bold uppercase tracking-wider text-ink-muted whitespace-nowrap cursor-pointer select-none hover:text-ink-2"
                  :class="c.align === 'e' ? 'text-end' : 'text-start'" @click="tt.toggleSort(c.key)">
                <span class="inline-flex items-center gap-1" :class="c.align === 'e' ? 'flex-row-reverse' : ''">{{ c.label }}
                  <Icon v-if="tt.sortKey.value === c.key" name="chevDown" :size="11" :class="tt.sortDir.value === 1 ? '' : 'rotate-180'" color="#a33a22" /></span>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="inv in tt.pageRows.value" :key="inv.id" class="border-t border-line-hair hover:bg-app-warm/70 cursor-pointer" @click="open(inv.id)">
              <td v-show="!tt.hidden.value.has('id')" class="px-4 py-2.5 font-mono font-semibold whitespace-nowrap">{{ inv.id }}</td>
              <td v-show="!tt.hidden.value.has('date')" class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ inv.date }}</td>
              <td v-show="!tt.hidden.value.has('customer')" class="px-4 py-2.5 truncate max-w-[180px]">{{ inv.customer }}</td>
              <td v-show="!tt.hidden.value.has('net')" class="px-4 py-2.5 text-end tnum">{{ fmt2(inv.net) }}</td>
              <td v-show="!tt.hidden.value.has('vat')" class="px-4 py-2.5 text-end tnum text-ink-3">{{ fmt2(inv.vat) }}</td>
              <td v-show="!tt.hidden.value.has('gross')" class="px-4 py-2.5 text-end tnum font-bold">{{ fmt2(inv.gross) }}</td>
              <td v-show="!tt.hidden.value.has('status')" class="px-4 py-2.5">
                <span class="inline-block text-[10px] font-bold px-2 py-0.5 rounded-badge border"
                      :style="{ background: INV_STATUS[inv.status].bg, color: INV_STATUS[inv.status].fg, borderColor: INV_STATUS[inv.status].bd }">{{ invStatusLabel(inv.status, locale) }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="!tt.sorted.value.length" class="py-12 text-center text-[12px] text-ink-muted">{{ L("No invoices match your filters.","لا توجد فواتير مطابقة.","Aucune facture.") }}</div>
      <TablePager :t="tt" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableToolbar from "@/components/TableToolbar.vue";
import TablePager from "@/components/TablePager.vue";
import { INVOICES, INV_STATUS, invStatusLabel, invoiceTiles, fmt2 } from "@/data/invoices";
import { liveOrSample, currentCompany } from "@/composables/useLive";
import { useTableTools } from "@/composables/useTableTools";

const { locale } = useI18n();
const router = useRouter();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const tiles = computed(() => invoiceTiles(locale.value));

const cols = [
  { key: "id", label: L("Invoice", "الفاتورة", "Facture"), align: "s" },
  { key: "date", label: L("Date", "التاريخ", "Date"), align: "s" },
  { key: "customer", label: L("Customer", "العميل", "Client"), align: "s" },
  { key: "net", label: L("Net", "الصافي", "HT"), align: "e" },
  { key: "vat", label: L("VAT 20%", "ضريبة 20%", "TVA 20%"), align: "e" },
  { key: "gross", label: L("Gross", "الإجمالي", "TTC"), align: "e" },
  { key: "status", label: L("Status", "الحالة", "Statut"), align: "s" },
];

const rows = ref(INVOICES);
const isLive = ref(null);
const tt = useTableTools(rows, cols, {
  dateKey: "date", defaultSort: "date", defaultDir: -1,
  facets: [{ key: "status", label: L("status", "حالة", "statut"), format: (v) => invStatusLabel(v, locale.value) }],
});

onMounted(async () => {
  const res = await liveOrSample(
    "accounting_portal.api.sales.list_invoices", { company: currentCompany(), limit: 500 }, () => INVOICES,
    (data) => data.map((r) => ({ id: r.name, date: String(r.date || ""), customer: r.customer, net: r.net, vat: r.vat, gross: r.gross, status: (r.status || "").toLowerCase().includes("paid") ? "paid" : "overdue" })),
  );
  rows.value = res.data;
  isLive.value = res.live;
});

function open(id) { router.push({ path: "/accounting/sales/invoices", query: { id } }); }
</script>
