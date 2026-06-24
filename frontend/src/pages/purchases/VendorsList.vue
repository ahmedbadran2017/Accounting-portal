<template>
  <div class="space-y-3.5">
    <div class="bg-white rounded-card border border-line overflow-hidden shadow-card">
      <!-- Header -->
      <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
        <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#fff4e0"><Icon name="building" :size="14" color="#b45309" /></span>
        <span class="text-[13px] font-bold">{{ L("Suppliers","الموردون","Fournisseurs") }}</span>
        <span v-if="isLive !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="isLive ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ isLive ? "Live" : "Sample" }}</span>
        <span class="hidden lg:inline text-[11px] text-ink-muted">{{ rows.length }} · {{ L("ranked by payable","حسب المستحق","par dû") }}</span>
        <!-- view toggle -->
        <div class="ms-auto flex items-center gap-1 bg-app-warm/60 rounded-chip p-0.5">
          <button v-for="v in ['list','cards']" :key="v" class="px-2.5 py-1 rounded-lg text-[11px] font-semibold inline-flex items-center gap-1" :class="view === v ? 'bg-white shadow-card text-ink' : 'text-ink-3'" @click="view = v">
            <Icon :name="v === 'list' ? 'list' : 'grid'" :size="12" />{{ v === 'list' ? L("List","قائمة","Liste") : L("Cards","بطاقات","Cartes") }}
          </button>
        </div>
        <div class="relative">
          <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
          <input v-model.trim="tt.search.value" :placeholder="L('Search supplier…','بحث…','Rechercher…')" class="w-44 sm:w-60 h-9 bg-app-warm/40 border border-line-2 rounded-[10px] ps-9 pe-3 text-[12.5px] focus:outline-none focus:border-accent/40 focus:bg-white" />
        </div>
      </div>

      <TableToolbar :t="tt" filename="suppliers" />

      <!-- List view -->
      <div v-if="view === 'list'" class="overflow-x-auto">
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
            <tr v-for="(v, i) in tt.pageRows.value" :key="v.name" class="border-t border-line-hair hover:bg-app-warm/70 cursor-pointer" @click="open(v.name)">
              <td v-show="!tt.hidden.value.has('supplier_name')" class="px-4 py-2.5">
                <span class="flex items-center gap-2.5">
                  <span class="w-7 h-7 rounded-[8px] grid place-items-center text-white text-[9px] font-bold flex-shrink-0" :style="{ background: badge(i) }">{{ ini(v.supplier_name) }}</span>
                  <span class="font-semibold truncate max-w-[260px]">{{ v.supplier_name }}</span>
                </span>
              </td>
              <td v-show="!tt.hidden.value.has('group')" class="px-4 py-2.5 text-ink-2">{{ v.group || "—" }}</td>
              <td v-show="!tt.hidden.value.has('n_bills')" class="px-4 py-2.5 text-end tnum">{{ v.n_bills }}</td>
              <td v-show="!tt.hidden.value.has('payable')" class="px-4 py-2.5 text-end tnum font-bold" :class="v.payable < 0 ? 'text-success-dark' : ''">{{ fmt(v.payable) }} <span class="text-[10px] text-ink-muted">{{ v.currency }}</span></td>
            </tr>
          </tbody>
        </table>
        <TableLoading v-if="loading" />
        <div v-else-if="!tt.sorted.value.length" class="py-12 text-center text-[12px] text-ink-muted">{{ L("No suppliers match.","لا موردين مطابقين.","Aucun fournisseur.") }}</div>
        <TablePager :t="tt" />
      </div>

      <!-- Cards view -->
      <div v-else class="p-3 grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        <button v-for="(v, i) in tt.pageRows.value" :key="v.name" class="yo-card text-start bg-white border border-line rounded-[14px] p-4 shadow-card w-full" @click="open(v.name)">
          <div class="flex items-center gap-2.5">
            <span class="w-[30px] h-[30px] rounded-[8px] grid place-items-center text-white text-[9.5px] font-bold flex-shrink-0" :style="{ background: badge(i) }">{{ ini(v.supplier_name) }}</span>
            <div class="flex-1 min-w-0"><div class="text-[12.5px] font-bold truncate">{{ v.supplier_name }}</div><div class="text-[10.5px] text-ink-muted">{{ v.group || "—" }}</div></div>
          </div>
          <div class="text-[20px] font-bold tnum mt-2.5" :class="v.payable < 0 ? 'text-success-dark' : ''">{{ fmt(v.payable) }}<span class="text-[11px] text-ink-muted ms-0.5">{{ v.currency }}</span></div>
          <div class="text-[10.5px] text-ink-muted mt-0.5">{{ v.n_bills }} {{ L("bills · payable","فاتورة · مستحق","factures") }}</div>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableToolbar from "@/components/TableToolbar.vue";
import TablePager from "@/components/TablePager.vue";
import TableLoading from "@/components/TableLoading.vue";
import { VENDORS } from "@/data/purchases";
import { liveOrSample, currentCompany } from "@/composables/useLive";
import { useTableTools } from "@/composables/useTableTools";

const { locale } = useI18n();
const router = useRouter();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US");
const ini = (n) => String(n || "?").trim().split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
const PALETTE = ["#2563eb", "#7c3aed", "#0891b2", "#c2410c", "#16a34a", "#be123c", "#a16207", "#4f46e5"];
const badge = (i) => `linear-gradient(135deg,${PALETTE[i % PALETTE.length]},${PALETTE[(i + 3) % PALETTE.length]})`;

const view = ref("list");
const cols = [
  { key: "supplier_name", label: L("Supplier", "المورّد", "Fournisseur"), align: "s" },
  { key: "group", label: L("Group", "المجموعة", "Groupe"), align: "s" },
  { key: "n_bills", label: L("Bills", "الفواتير", "Factures"), align: "e" },
  { key: "payable", label: L("Payable", "المستحق", "Dû"), align: "e" },
];

const SAMPLE = VENDORS.map((v) => ({ name: v.id, supplier_name: v.name, group: v.place, payable: Number(String(v.payable).replace(/,/g, "")) || 0, currency: v.ccy, n_bills: 0 }));
const rows = ref([]);
const isLive = ref(null);
const loading = ref(true);
const tt = useTableTools(rows, cols, { defaultSort: "payable", defaultDir: -1, facets: [{ key: "group", label: L("group", "مجموعة", "groupe") }] });

onMounted(async () => {
  try {
    const res = await liveOrSample(
      "accounting_portal.api.purchases.list_vendors", { company: currentCompany(), limit: 200 }, () => SAMPLE,
      (data) => data.map((r) => ({ name: r.name, supplier_name: r.supplier_name || r.name, group: r.supplier_group, payable: Number(r.payable) || 0, currency: r.currency || "MAD", n_bills: r.n_bills || 0 })),
    );
    rows.value = res.data; isLive.value = res.live;
  } finally { loading.value = false; }
});

function open(name) { router.push({ path: "/accounting/purchases/vendors", query: { id: name } }); }
</script>
