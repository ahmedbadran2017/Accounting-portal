<template>
  <BankStatementWorkbench v-if="route.query.imp" :key="route.query.imp" :import-name="String(route.query.imp)" @back="closeWorkbench" />
  <div v-else class="space-y-3.5">
    <!-- Account picker -->
    <div class="flex gap-3 overflow-x-auto pb-1">
      <button v-for="a in accounts" :key="a.name" @click="pick(a)"
              class="flex-shrink-0 w-56 bg-white border rounded-[16px] p-4 text-start transition-all"
              :class="sel === a.name ? 'shadow-cardHover -translate-y-0.5 border-accent/50' : 'border-line shadow-card hover:-translate-y-0.5'">
        <div class="flex items-center gap-2">
          <span class="w-8 h-8 rounded-[10px] grid place-items-center" :style="{ background: a.account_type === 'Cash' ? '#fffbeb' : '#eff6ff' }"><Icon :name="a.account_type === 'Cash' ? 'coins' : 'bank'" :size="15" :color="a.account_type === 'Cash' ? '#b45309' : '#0369a1'" /></span>
          <span class="text-[11px] font-bold text-ink-2 truncate flex-1">{{ a.account_name }}</span>
        </div>
        <div class="text-[18px] font-extrabold tnum mt-2" :class="(a.period ? a.closing : a.book) < 0 ? 'text-sale' : ''">{{ money(a.period ? a.closing : a.book) }} <span class="text-[10px] text-ink-muted">{{ a.ccy }}</span></div>
        <div v-if="a.period" class="text-[10px] text-ink-muted mt-1 tnum leading-tight">
          <span :title="L('carried forward','مُرحّل','reporté')">{{ money(a.opening) }}</span>
          <span class="text-teal-600 font-semibold"> +{{ money(a.period_in) }}</span>
          <span class="text-rose-500 font-semibold"> −{{ money(a.period_out) }}</span>
        </div>
        <div class="text-[10.5px] mt-1" :class="a.uncleared_n ? 'text-brand font-semibold' : 'text-ink-muted'">{{ a.uncleared_n }} {{ L("uncleared", "غير مُسوّى", "non rapprochés") }}</div>
      </button>
      <div v-if="!accounts.length && !loadingAcc" class="text-[12px] text-ink-muted py-8">{{ L("No bank accounts.", "لا حسابات بنكية.", "Aucun compte.") }}</div>
    </div>

    <!-- Statement history — every upload is a resumable work session -->
    <div v-if="imports.length" class="bg-white rounded-card border border-line shadow-card overflow-hidden">
      <div class="px-4 py-2.5 border-b border-line-hair text-[12px] font-bold flex items-center gap-2">
        <Icon name="doc" :size="14" color="#0b5c4f" />{{ L("Imported statements", "الكشوف المرفوعة", "Relevés importés") }}
        <span class="text-[10px] text-ink-muted">{{ inProgressImports.length }} {{ L("in progress", "جارية", "en cours") }}</span>
        <button v-if="doneImportsN || imports.length > visibleImports.length || showAllImports" type="button" class="ms-auto text-[10.5px] font-semibold text-accent-dark hover:underline" @click="showAllImports = !showAllImports">
          {{ showAllImports ? L("Hide completed", "اخفي المكتمل", "Masquer") : L(`Show all (${imports.length})`, `عرض الكل (${imports.length})`, `Tout (${imports.length})`) }}
        </button>
      </div>
      <div class="overflow-x-auto"><table class="w-full text-[12px]">
        <tbody>
          <tr v-for="im in visibleImports" :key="im.name" class="border-t border-line-hair hover:bg-app-warm/40 cursor-pointer" @click="openWorkbench(im.name)">
            <td class="px-4 py-2.5"><div class="font-medium truncate max-w-[220px]">{{ im.file_name }}</div><div class="text-[10px] text-ink-muted font-mono">{{ im.name }} · {{ im.account.split(" - ")[0] }}</div></td>
            <td class="px-3 py-2.5 text-[11px] text-ink-3 whitespace-nowrap">{{ im.from_date }} → {{ im.to_date }}</td>
            <td class="px-3 py-2.5 whitespace-nowrap text-[11px] tnum">
              <span class="text-emerald-700 font-semibold">✓{{ im.n_matched }}</span>
              <span class="text-sky-700 font-semibold ms-1.5">➕{{ im.n_created }}</span>
              <span class="text-ink-muted ms-1.5">👁{{ im.n_ignored }}</span>
              <span class="text-ink-muted ms-1.5">/ {{ im.n_total }}</span>
            </td>
            <td class="px-3 py-2.5"><span class="text-[10.5px] font-bold px-2 py-0.5 rounded-chip" :class="im.status==='Done' ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-800'">{{ im.status }}</span></td>
            <td class="px-3 py-2.5 text-[10.5px] text-ink-muted whitespace-nowrap">{{ (im.owner || "").split("@")[0] }} · {{ im.modified }}</td>
            <td class="px-4 py-2.5 text-end"><span class="text-[11px] font-bold text-accent-dark">{{ im.status==='Done' ? L("open","افتح","ouvrir") : L("resume →","استئناف ←","reprendre →") }}</span></td>
          </tr>
          <tr v-if="!visibleImports.length"><td class="px-4 py-4 text-center text-[11px] text-ink-muted">{{ L("Nothing in progress — all statements are done 🎉", "مفيش كشوف جارية — كله مكتمل 🎉", "Tout est terminé") }}</td></tr>
        </tbody>
      </table></div>
    </div>

    <!-- Entries -->
    <div v-if="sel" class="bg-white rounded-card border border-line overflow-hidden shadow-card">
      <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
        <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#eff6ff"><Icon name="bank" :size="14" color="#0369a1" /></span>
        <span class="text-[13px] font-bold truncate max-w-[260px]">{{ selName }}</span>
        <span v-if="live !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="live ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ live ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échant.") }}</span>
        <span class="hidden lg:inline text-[11px] text-ink-muted">{{ rows.length }} {{ L("uncleared entries", "قيد غير مُسوّى", "écritures") }}</span>
        <button v-if="carryover.n" type="button" class="inline-flex items-center gap-1 text-[10.5px] font-semibold px-2 py-1 rounded-chip bg-amber-50 text-amber-800 border border-amber-200 hover:bg-amber-100" @click="showAllTime" :title="L('Old outstanding items still count toward this year\'s closing balance — click to include them','قيود قديمة معلّقة لسه بتأثر على رصيد إقفال السنة دي — اضغط لعرضها','Anciens en suspens')">
          ⏳ {{ carryover.n }} {{ L("carried over from before", "مُرحّل من قبل", "reportés") }} ({{ fmt(carryover.v) }})
        </button>
        <button type="button" class="ms-auto inline-flex items-center gap-1.5 h-9 px-3 rounded-chip text-[12px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand" @click="showImport = true">
          <Icon name="doc" :size="13" />{{ L("Import statement", "استيراد كشف", "Importer relevé") }}
        </button>
        <div class="relative">
          <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
          <input v-model.trim="srch" :placeholder="L('Voucher / party / ref…', 'مستند / طرف…', 'Pièce / tiers…')" class="w-44 sm:w-56 h-9 bg-app-warm/40 border border-line-2 rounded-[10px] ps-9 pe-3 text-[12.5px] focus:outline-none focus:border-accent/40 focus:bg-white" />
        </div>
      </div>

      <TableToolbar :t="tt" filename="bankrec" />
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
            <tr v-for="o in tt.pageRows.value" :key="o.voucher" class="border-t border-line-hair hover:bg-app-warm/70 cursor-pointer" :class="tt.isSelected(o) ? 'bg-accent/5' : ''" @click="open(o)">
              <td class="px-3 py-2.5 w-9" @click.stop><input type="checkbox" :checked="tt.isSelected(o)" @change="tt.toggleRow(o)" class="accent-accent w-3.5 h-3.5 align-middle" /></td>
              <td v-show="!tt.hidden.value.has('date')" class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ o.date }}</td>
              <td v-show="!tt.hidden.value.has('voucher')" class="px-4 py-2.5 font-mono font-semibold whitespace-nowrap">{{ o.voucher }}</td>
              <td v-show="!tt.hidden.value.has('doctype')" class="px-4 py-2.5"><span class="text-[10px] font-bold px-2 py-0.5 rounded-full" :style="o.doctype === 'Payment Entry' ? 'background:#ecfdf5;color:#047857' : 'background:#f5f3ff;color:#6d28d9'">{{ o.doctype === 'Payment Entry' ? 'PE' : 'JE' }}</span></td>
              <td v-show="!tt.hidden.value.has('party')" class="px-4 py-2.5 truncate max-w-[180px]">{{ o.party || o.ref || "—" }}</td>
              <td v-show="!tt.hidden.value.has('amount')" class="px-4 py-2.5 text-end font-bold tnum whitespace-nowrap" :class="o.amount < 0 ? 'text-sale' : 'text-success-dark'">{{ o.amount < 0 ? "−" : "+" }}{{ fmt(Math.abs(o.amount)) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="!loading && !tt.sorted.value.length" class="py-12 text-center text-[12px] text-ink-muted">{{ L("Everything here is reconciled. ✓", "كل شيء مُسوّى. ✓", "Tout est rapproché. ✓") }}</div>
      <TablePager :t="tt" />
    </div>
    <div v-else class="bg-white rounded-card border border-line shadow-card py-12 text-center text-[12px] text-ink-muted">{{ L("Pick a bank account to reconcile.", "اختر حسابًا بنكيًا للتسوية.", "Choisissez un compte.") }}</div>

    <BulkBar :t="tt" filename="bankrec-selected" :note="bulkNote" :actions="bulkActions" />
    <StatementImportModal v-if="showImport && sel" :account="sel" :account-name="selName" @close="showImport = false" @done="onImported" @workbench="openWorkbench" />
  </div>
</template>

<script setup>
import { fmtAmount } from "@/utils/helpers";
import { ref, computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableToolbar from "@/components/TableToolbar.vue";
import TablePager from "@/components/TablePager.vue";
import TableLoading from "@/components/TableLoading.vue";
import BulkBar from "@/components/BulkBar.vue";
import StatementImportModal from "@/components/StatementImportModal.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";
import { useToast } from "@/composables/useToast";
import { useTableTools } from "@/composables/useTableTools";
import { useFiscalYear } from "@/composables/useFiscalYear";
import BankStatementWorkbench from "@/pages/banking/BankStatementWorkbench.vue";

const { locale } = useI18n();
const { entityId } = useUi();
const fyc = useFiscalYear();
const fyFilter = () => fyc.filterValue();
const toast = useToast();
const router = useRouter();
const route = useRoute();
function open(o) {
  if (o.doctype === "Payment Entry") router.push({ path: "/accounting/purchases/payments", query: { id: o.voucher } });
  else router.push({ path: "/accounting/accountant/journals", query: { id: o.voucher } });
}
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const money = (n) => fmtAmount(n);

const cols = [
  { key: "date", label: L("Date", "التاريخ", "Date"), align: "s" },
  { key: "voucher", label: L("Voucher", "المستند", "Pièce"), align: "s" },
  { key: "doctype", label: L("Type", "النوع", "Type"), align: "s" },
  { key: "party", label: L("Party / ref", "الطرف / مرجع", "Tiers / réf"), align: "s" },
  { key: "amount", label: L("Amount", "المبلغ", "Montant"), align: "e" },
];

const accounts = ref([]);
const loadingAcc = ref(false);
const sel = ref("");
const selName = ref("");
const rows = ref([]);
const live = ref(null);
const loading = ref(false);
const srch = ref("");
const showImport = ref(false);
function onImported() { loadAccounts(); loadRows(); }
const tt = useTableTools(rows, cols, { storeKey: "bankrec", keyField: "voucher", defaultSort: "date", defaultDir: -1 });
const bulkNote = computed(() => { const t = tt.selectedRows.value.reduce((a, r) => a + Math.abs(Number(r.amount) || 0), 0); return t ? fmt(t) + " MAD" : ""; });

const SAMPLE_ACC = [
  { name: "102.02.01.01", account_name: "BMCE-…130355", account_type: "Bank", ccy: "MAD", book: 918294, uncleared_n: 3407, uncleared_v: 44372442 },
  { name: "108.021.003", account_name: "Cathedis Transactions", account_type: "Bank", ccy: "MAD", book: 453101, uncleared_n: 642, uncleared_v: 1208400 },
];
const SAMPLE_ROWS = [
  { voucher: "PAY-20199", doctype: "Payment Entry", date: "2026-06-24", party: "BISFOR LOGISTIC SARL", ref: "CHQ 2772334", amount: -52638 },
  { voucher: "PAY-22493", doctype: "Payment Entry", date: "2026-06-20", party: "Lachhed najia", ref: "", amount: 129 },
];

async function loadAccounts() {
  loadingAcc.value = true;
  try { accounts.value = await api.call("accounting_portal.api.reconciliation.bank_rec_accounts", { company: currentCompany(), ...fyFilter() }) || []; }
  catch { accounts.value = SAMPLE_ACC; }
  finally { loadingAcc.value = false; }
  if (accounts.value.length && !sel.value) pick(accounts.value[0]);
}
const carryover = ref({ n: 0, v: 0 });
function showAllTime() { fyc.selected.value = "all"; }

// statement-import history (the workbench sessions)
const imports = ref([]);
const showAllImports = ref(false);
// In-progress sessions are the daily work; Done files fold into the archive.
const inProgressImports = computed(() => imports.value.filter((i) => i.status !== "Done"));
const doneImportsN = computed(() => imports.value.length - inProgressImports.value.length);
const visibleImports = computed(() => (showAllImports.value ? imports.value : inProgressImports.value.slice(0, 5)));
async function loadImports() {
  try { imports.value = await api.call("accounting_portal.api.bank_workbench.list_imports", { company: currentCompany() }, { fresh: true }) || []; }
  catch { imports.value = []; }
}
loadImports();
function openWorkbench(name) { router.replace({ query: { ...route.query, imp: name } }); }
function closeWorkbench() {
  const q = { ...route.query }; delete q.imp;
  router.replace({ query: q });
  loadImports(); loadAccounts(); loadRows();
}
async function loadRows() {
  if (!sel.value) return;
  loading.value = true;
  try {
    const res = await api.call("accounting_portal.api.reconciliation.bank_uncleared",
      { company: currentCompany(), account: sel.value, search: srch.value || undefined, limit: 500, ...fyFilter() });
    // New shape {rows, carryover_*}; tolerate the old plain array.
    rows.value = Array.isArray(res) ? res : (res?.rows || []);
    carryover.value = Array.isArray(res) ? { n: 0, v: 0 } : { n: res?.carryover_n || 0, v: res?.carryover_v || 0 };
    live.value = true;
  } catch { rows.value = SAMPLE_ROWS; carryover.value = { n: 0, v: 0 }; live.value = false; }
  finally { loading.value = false; }
}
function pick(a) { sel.value = a.name; selName.value = a.account_name; tt.clearSelection(); loadRows(); }

const bulkActions = computed(() => [{
  key: "clear", label: L("Mark reconciled", "علّم مُسوّى", "Rapprocher"), icon: "check", color: "#047857",
  confirm: (r) => L(`Mark ${r.length} entr(ies) reconciled?`, `علّم ${r.length} قيد كمُسوّى؟`, `Rapprocher ${r.length} ?`),
  run: async (r) => {
    try {
      await api.call("accounting_portal.api.reconciliation.mark_bank_cleared", { company: currentCompany(), entries: r.map((x) => ({ doctype: x.doctype, name: x.voucher })) });
      toast.success(L("Reconciled", "تمت التسوية", "Rapproché"));
      tt.clearSelection(); loadAccounts(); loadRows();
    } catch (e) { toast.error(String((e && e.message) || L("Failed", "فشل", "Échec")).slice(0, 160)); }
  },
}]);

let timer;
watch(entityId, () => { sel.value = ""; tt.clearSelection(); loadAccounts(); }, { immediate: true });
watch(fyc.selected, () => { loadAccounts(); loadRows(); });
watch(srch, () => { clearTimeout(timer); timer = setTimeout(loadRows, 300); });
</script>
