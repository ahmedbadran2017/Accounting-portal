<template>
  <div class="space-y-3.5">
    <!-- KPI strip -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <button v-for="k in kpis" :key="k.key" @click="setStatus(k.filter)"
              class="relative bg-white border rounded-[16px] p-4 text-start overflow-hidden transition-all"
              :class="status === k.filter ? 'shadow-cardHover -translate-y-0.5' : 'border-line shadow-card hover:-translate-y-0.5 hover:shadow-cardHover'"
              :style="status === k.filter ? { borderColor: k.color + '66' } : {}">
        <span class="absolute top-0 inset-x-0 h-[3px]" :style="{ background: k.color, opacity: status === k.filter ? 1 : .25 }"></span>
        <div class="flex items-center gap-2">
          <span class="w-8 h-8 rounded-[10px] grid place-items-center" :style="{ background: k.tint }"><Icon :name="k.icon" :size="15" :color="k.color" /></span>
          <span class="text-[10.5px] text-ink-muted font-bold uppercase tracking-wider leading-tight">{{ k.label() }}</span>
        </div>
        <div class="text-[22px] font-extrabold tnum mt-2 leading-none" :style="{ color: status === k.filter ? k.color : '#1c1917' }">{{ k.count }}</div>
        <div class="text-[11px] text-ink-3 font-semibold mt-1 tnum">{{ money(k.value) }} <span class="text-ink-muted font-normal">MAD</span></div>
      </button>
    </div>

    <!-- Table -->
    <div class="bg-white rounded-card border border-line overflow-hidden shadow-card">
      <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
        <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#fffbeb"><Icon name="doc" :size="14" color="#b45309" /></span>
        <span class="text-[13px] font-bold">{{ L("Cheque register", "سجل الشيكات", "Registre des chèques") }}</span>
        <span v-if="live !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="live ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ live ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échant.") }}</span>
        <span class="hidden lg:inline text-[11px] text-ink-muted">{{ rows.length }} {{ L("cheques", "شيك", "chèques") }}<span v-if="status"> · {{ statusLabel(status) }}</span></span>
        <div class="relative ms-auto">
          <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
          <input v-model.trim="srch" :placeholder="L('Cheque no / supplier…', 'رقم الشيك / المورّد…', 'N° chèque / fournisseur…')" class="w-44 sm:w-60 h-9 bg-app-warm/40 border border-line-2 rounded-[10px] ps-9 pe-3 text-[12.5px] focus:outline-none focus:border-accent/40 focus:bg-white" />
        </div>
      </div>

      <div class="flex items-center gap-2 px-4 py-2.5 border-b border-line-hair flex-wrap bg-app-warm/20">
        <button v-for="f in FILTERS" :key="f.key" class="text-[11px] font-semibold px-2.5 py-1 rounded-full border transition"
                :class="status === f.key ? 'bg-ink text-white border-ink' : 'bg-white text-ink-3 border-line-2 hover:bg-app-warm'" @click="setStatus(f.key)">{{ f.label() }}</button>
        <span v-if="loading" class="ms-2 text-[11px] text-ink-muted inline-flex items-center gap-1.5"><span class="w-1.5 h-1.5 rounded-full bg-accent animate-pulse"></span>{{ L("loading…", "تحميل…", "…") }}</span>
      </div>

      <TableToolbar :t="tt" filename="cheques" />
      <div v-if="loading" class="px-1"><TableLoading :rows="6" /></div>
      <div v-else class="overflow-x-auto">
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
            <tr v-for="o in tt.pageRows.value" :key="o.name" class="border-t border-line-hair hover:bg-app-warm/70 cursor-pointer" :class="tt.isSelected(o) ? 'bg-accent/5' : ''" @click="open(o.name)">
              <td class="px-3 py-2.5 w-9" @click.stop><input type="checkbox" :checked="tt.isSelected(o)" @change="tt.toggleRow(o)" class="accent-accent w-3.5 h-3.5 align-middle" /></td>
              <td v-show="!tt.hidden.value.has('cheque_no')" class="px-4 py-2.5 font-mono font-semibold whitespace-nowrap">{{ o.cheque_no || "—" }}</td>
              <td v-show="!tt.hidden.value.has('supplier_name')" class="px-4 py-2.5 truncate max-w-[200px]">{{ o.supplier_name }}</td>
              <td v-show="!tt.hidden.value.has('due')" class="px-4 py-2.5 whitespace-nowrap">
                <span :class="o.status === 'outstanding' && o.due && o.due < today ? 'text-sale font-semibold' : 'text-ink-2'">{{ o.due || "—" }}</span>
              </td>
              <td v-show="!tt.hidden.value.has('bank')" class="px-4 py-2.5 text-ink-3 truncate max-w-[180px]">{{ o.bank }}</td>
              <td v-show="!tt.hidden.value.has('status')" class="px-4 py-2.5">
                <span class="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full" :style="stStyle(o.status)"><span class="w-1.5 h-1.5 rounded-full" :style="{ background: ST[o.status].c }"></span>{{ statusLabel(o.status) }}</span>
              </td>
              <td v-show="!tt.hidden.value.has('amount')" class="px-4 py-2.5 text-end font-bold tnum whitespace-nowrap">{{ o.currency }} {{ fmt(o.amount) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="!loading && !tt.sorted.value.length" class="py-12 text-center text-[12px] text-ink-muted">{{ L("No cheques here.", "لا شيكات هنا.", "Aucun chèque.") }}</div>
      <TablePager :t="tt" />
    </div>

    <BulkBar :t="tt" filename="cheques-selected" :note="bulkNote" :actions="bulkActions" />
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableToolbar from "@/components/TableToolbar.vue";
import TablePager from "@/components/TablePager.vue";
import TableLoading from "@/components/TableLoading.vue";
import BulkBar from "@/components/BulkBar.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { usePersistedRef } from "@/composables/usePersistedRef";
import { useUi } from "@/composables/useUi";
import { useToast } from "@/composables/useToast";
import { useTableTools } from "@/composables/useTableTools";

const { locale } = useI18n();
const { entityId } = useUi();
const toast = useToast();
const router = useRouter();
function open(name) { router.push({ path: "/accounting/purchases/payments", query: { id: name } }); }
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const money = (n) => { n = Number(n) || 0; const a = Math.abs(n); return a >= 1e6 ? (n / 1e6).toFixed(2) + "M" : a >= 1e3 ? Math.round(n / 1e3) + "K" : Math.round(n).toLocaleString(); };
const today = new Date().toISOString().slice(0, 10);

const ST = {
  outstanding: { c: "#b45309", bg: "#fffbeb", l: () => L("Outstanding", "معلّق", "En cours") },
  postdated: { c: "#0369a1", bg: "#eff6ff", l: () => L("Post-dated", "مؤجّل", "Postdaté") },
  cleared: { c: "#047857", bg: "#ecfdf5", l: () => L("Cleared", "تصرّف", "Encaissé") },
};
const stStyle = (s) => { const m = ST[s] || ST.outstanding; return { background: m.bg, color: m.c }; };
const statusLabel = (s) => (ST[s] || ST.outstanding).l();

const FILTERS = [
  { key: "", label: () => L("All", "الكل", "Tout") },
  { key: "outstanding", label: () => L("Outstanding", "معلّق", "En cours") },
  { key: "postdated", label: () => L("Post-dated", "مؤجّل", "Postdaté") },
  { key: "cleared", label: () => L("Cleared", "تصرّف", "Encaissé") },
];
const cols = [
  { key: "cheque_no", label: L("Cheque no", "رقم الشيك", "N° chèque"), align: "s" },
  { key: "supplier_name", label: L("Supplier", "المورّد", "Fournisseur"), align: "s" },
  { key: "due", label: L("Cheque date", "تاريخ الشيك", "Date chèque"), align: "s" },
  { key: "bank", label: L("Bank", "البنك", "Banque"), align: "s" },
  { key: "status", label: L("Status", "الحالة", "Statut"), align: "s" },
  { key: "amount", label: L("Amount", "المبلغ", "Montant"), align: "e" },
];

const rows = ref([]);
const sum = ref({});
const live = ref(null);
const loading = ref(false);
const srch = ref("");
const status = usePersistedRef("ap_cheques_status", "");
const tt = useTableTools(rows, cols, { storeKey: "cheques", keyField: "name", defaultSort: "due", defaultDir: 1 });

const kpis = computed(() => [
  { key: "out", filter: "outstanding", color: "#b45309", tint: "#fffbeb", icon: "doc", label: () => L("Outstanding", "معلّق", "En cours"), count: sum.value.outstanding_n || 0, value: sum.value.outstanding || 0 },
  { key: "due", filter: "outstanding", color: "#be123c", tint: "#fef2f2", icon: "clock", label: () => L("Due ≤ 7 days", "مستحق ≤ 7 أيام", "Échéance ≤ 7j"), count: sum.value.due_week_n || 0, value: sum.value.due_week || 0 },
  { key: "post", filter: "postdated", color: "#0369a1", tint: "#eff6ff", icon: "clock", label: () => L("Post-dated", "مؤجّلة", "Postdatés"), count: sum.value.postdated_n || 0, value: sum.value.postdated || 0 },
  { key: "clr", filter: "cleared", color: "#047857", tint: "#ecfdf5", icon: "check", label: () => L("Cleared", "تصرّفت", "Encaissés"), count: sum.value.cleared_n || 0, value: sum.value.cleared || 0 },
]);
const bulkNote = computed(() => { const t = tt.selectedRows.value.reduce((a, r) => a + (Number(r.amount) || 0), 0); return t ? fmt(t) + " MAD" : ""; });

const SAMPLE_SUM = { outstanding_n: 12, outstanding: 394430, due_week_n: 11, due_week: 327050, postdated_n: 2, postdated: 67380, cleared_n: 0, cleared: 0 };
const SAMPLE = [
  { name: "PAY-20199", supplier_name: "BISFOR LOGISTIC SARL", cheque_no: "CHQ 2772334", due: "2026-07-21", bank: "BMCE - MAD", amount: 52638, currency: "MAD", status: "postdated" },
  { name: "PAY-20198", supplier_name: "BISFOR LOGISTIC SARL", cheque_no: "CHQ 2772224", due: "2026-06-15", bank: "BMCE - MAD", amount: 26208, currency: "MAD", status: "outstanding" },
];
async function loadSummary() {
  try { sum.value = await api.call("accounting_portal.api.purchases.cheques_summary", { company: currentCompany() }) || SAMPLE_SUM; }
  catch { sum.value = SAMPLE_SUM; }
}
async function loadRows() {
  loading.value = true;
  try {
    rows.value = await api.call("accounting_portal.api.purchases.list_cheques", { company: currentCompany(), search: srch.value || undefined, status: status.value || undefined, limit: 500 }) || [];
    live.value = true;
  } catch { rows.value = SAMPLE.filter((r) => !status.value || r.status === status.value); live.value = false; }
  finally { loading.value = false; }
}
function setStatus(s) { status.value = s; tt.clearSelection(); loadRows(); }

const bulkActions = computed(() => [{
  key: "clear", label: L("Mark cleared", "علّم تصرّف", "Encaisser"), icon: "check", color: "#047857",
  confirm: (r) => L(`Mark ${r.length} cheque(s) cleared today (${today})?`, `علّم ${r.length} شيك كمتصرّف اليوم؟`, `Marquer ${r.length} chèque(s) encaissé(s) ?`),
  run: async (r) => {
    try {
      await api.call("accounting_portal.api.purchases.mark_cheques_cleared", { company: currentCompany(), names: r.map((x) => x.name), clearance_date: today });
      toast.success(L("Cheques marked cleared", "تم تعليم الشيكات", "Chèques encaissés"));
      tt.clearSelection(); loadSummary(); loadRows();
    } catch (e) { toast.error(String((e && e.message) || L("Failed", "فشل", "Échec")).slice(0, 160)); }
  },
}]);

let timer;
watch(entityId, () => { tt.clearSelection(); loadSummary(); loadRows(); }, { immediate: true });
watch(srch, () => { clearTimeout(timer); timer = setTimeout(loadRows, 300); });
</script>
