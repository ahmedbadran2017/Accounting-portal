<template>
  <div class="space-y-3.5">
    <!-- Insights (operating accounts only — the parked ones don't distort the cockpit) -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <div class="relative bg-white border border-line rounded-[16px] p-4 shadow-card overflow-hidden">
        <span class="absolute top-0 inset-x-0 h-[3px]" style="background:#0b5c4f;opacity:.3"></span>
        <div class="flex items-center gap-2"><span class="w-8 h-8 rounded-[10px] grid place-items-center" style="background:#faf6f4"><Icon name="scale" :size="15" color="#0b5c4f" /></span><span class="text-[10.5px] text-ink-muted font-bold uppercase tracking-wider">{{ L("Cash position", "المركز النقدي", "Trésorerie") }}</span></div>
        <div class="text-[22px] font-extrabold tnum mt-2 leading-none" :class="ins.position < 0 ? 'text-sale' : ''">{{ money(ins.position) }}<span class="text-[11px] text-ink-muted ms-1">{{ baseCcy }}</span></div>
        <div class="text-[11px] text-ink-muted mt-1.5">{{ counts.operating }} {{ L("operating accounts", "حساب تشغيلي", "comptes actifs") }}</div>
      </div>
      <div class="relative bg-white border border-line rounded-[16px] p-4 shadow-card overflow-hidden">
        <span class="absolute top-0 inset-x-0 h-[3px]" style="background:#0369a1;opacity:.3"></span>
        <div class="flex items-center gap-2"><span class="w-8 h-8 rounded-[10px] grid place-items-center" style="background:#eff6ff"><Icon name="bank" :size="15" color="#0369a1" /></span><span class="text-[10.5px] text-ink-muted font-bold uppercase tracking-wider">{{ L("In banks", "في البنوك", "En banque") }}</span></div>
        <div class="text-[22px] font-extrabold tnum mt-2 leading-none">{{ money(ins.bank) }}<span class="text-[11px] text-ink-muted ms-1">{{ baseCcy }}</span></div>
        <div class="text-[11px] text-ink-muted mt-1.5">{{ L("Cash on hand", "نقد بالخزينة", "Caisse") }} {{ money(ins.cash) }}</div>
      </div>
      <button @click="goRec" class="relative bg-white border rounded-[16px] p-4 shadow-card overflow-hidden text-start hover:-translate-y-0.5 hover:shadow-cardHover transition-all" style="border-color:#fde68a">
        <span class="absolute top-0 inset-x-0 h-[3px]" style="background:#b45309;opacity:.4"></span>
        <div class="flex items-center gap-2"><span class="w-8 h-8 rounded-[10px] grid place-items-center" style="background:#fffbeb"><Icon name="clock" :size="15" color="#b45309" /></span><span class="text-[10.5px] text-ink-muted font-bold uppercase tracking-wider">{{ L("Unreconciled", "غير مُسوّى", "Non rapproché") }}</span></div>
        <div class="text-[22px] font-extrabold tnum mt-2 leading-none" style="color:#b45309">{{ money(ins.uncleared) }}<span class="text-[11px] text-ink-muted ms-1">{{ baseCcy }}</span></div>
        <div class="text-[11px] text-brand font-semibold mt-1.5">{{ ins.uncleared_n }} {{ L("entries → reconcile", "قيد → سوِّ", "écritures") }}</div>
      </button>
      <!-- Under audit — the parked balances, held out of the cockpit -->
      <button @click="viewMode = 'audit'" class="relative bg-white border rounded-[16px] p-4 shadow-card overflow-hidden text-start hover:-translate-y-0.5 hover:shadow-cardHover transition-all" :style="{ borderColor: counts.audit ? '#ddd6fe' : '#e7e5e4' }">
        <span class="absolute top-0 inset-x-0 h-[3px]" :style="{ background: counts.audit ? '#7c3aed' : '#a8a29e', opacity: .35 }"></span>
        <div class="flex items-center gap-2"><span class="w-8 h-8 rounded-[10px] grid place-items-center" :style="{ background: counts.audit ? '#f5f3ff' : '#f5f5f4' }"><Icon name="shield" :size="15" :color="counts.audit ? '#7c3aed' : '#a8a29e'" /></span><span class="text-[10.5px] text-ink-muted font-bold uppercase tracking-wider">{{ L("Under audit", "تحت المراجعة", "En audit") }}</span></div>
        <div class="text-[22px] font-extrabold tnum mt-2 leading-none" :class="counts.audit ? 'text-violet-700' : 'text-ink-muted'">{{ counts.audit }}</div>
        <div class="text-[11px] mt-1.5" :class="counts.audit ? 'text-violet-600 font-semibold' : 'text-ink-muted'">{{ counts.audit ? money(ins.parked_v) + " " + baseCcy + " " + L("held out", "معزولة", "isolés") : L("none parked", "لا شيء معزول", "aucun") }}</div>
      </button>
    </div>

    <!-- Accounts table -->
    <div class="bg-white rounded-card border border-line overflow-hidden shadow-card">
      <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
        <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#eff6ff"><Icon name="bank" :size="14" color="#0369a1" /></span>
        <span class="text-[13px] font-bold">{{ L("Bank & cash accounts", "حسابات البنوك والنقد", "Comptes bancaires & caisse") }}</span>
        <span v-if="live !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="live ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ live ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échant.") }}</span>
        <!-- Operating / Under audit / All -->
        <div class="inline-flex rounded-[10px] border border-line-2 overflow-hidden bg-app-warm/40 text-[11.5px] font-semibold">
          <button v-for="m in modes" :key="m.k" @click="viewMode = m.k" class="px-2.5 h-8 transition-colors" :class="viewMode === m.k ? 'bg-white text-accent-dark shadow-sm' : 'text-ink-muted hover:text-ink-2'">{{ m.label }} <span class="text-[10px] opacity-70">{{ m.n }}</span></button>
        </div>
        <div class="relative ms-auto">
          <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
          <input v-model.trim="tt.search.value" :placeholder="L('Account…', 'حساب…', 'Compte…')" class="w-40 sm:w-52 h-9 bg-app-warm/40 border border-line-2 rounded-[10px] ps-9 pe-3 text-[12.5px] focus:outline-none focus:border-accent/40 focus:bg-white" />
        </div>
      </div>

      <!-- Bulk park bar -->
      <div v-if="canWrite && selected.size" class="flex items-center gap-2 px-4 py-2.5 bg-violet-50/60 border-b border-violet-100 text-[12px]">
        <span class="font-semibold text-violet-800">{{ selected.size }} {{ L("selected", "محدد", "sélectionné") }}</span>
        <button v-if="viewMode !== 'audit'" @click="bulkPark(true)" :disabled="busy" class="ms-auto h-8 px-3 rounded-chip font-semibold text-white bg-violet-600 hover:bg-violet-700 disabled:opacity-50 inline-flex items-center gap-1.5"><Icon name="shield" :size="13" color="#fff" />{{ L("Park under audit", "عزل تحت المراجعة", "Mettre en audit") }}</button>
        <button v-if="viewMode !== 'operating'" @click="bulkPark(false)" :disabled="busy" class="h-8 px-3 rounded-chip font-semibold text-accent-dark border border-line-2 hover:bg-app-warm disabled:opacity-50 inline-flex items-center gap-1.5" :class="viewMode === 'audit' ? 'ms-auto' : ''"><Icon name="check" :size="13" />{{ L("Return to operating", "إرجاع للتشغيل", "Réactiver") }}</button>
        <button @click="selected = new Set()" class="h-8 px-2.5 rounded-chip text-ink-muted hover:bg-app-warm">{{ L("Clear", "مسح", "Effacer") }}</button>
      </div>

      <div v-if="viewMode === 'audit'" class="px-4 py-2.5 border-b border-line-hair text-[11px] text-violet-700 bg-violet-50/30 flex items-start gap-1.5">
        <Icon name="shield" :size="13" color="#7c3aed" class="flex-shrink-0 mt-px" />
        {{ L("Parked accounts — held out of the cash cockpit until audited. Their balances stay in the trial balance & balance sheet. Return one to operating once it’s reconciled.",
              "حسابات معزولة — خارج شاشة الكاش لحين مراجعتها. أرصدتها تظل في ميزان المراجعة والميزانية. أرجعها للتشغيل بعد تسويتها.",
              "Comptes isolés — hors trésorerie jusqu’à l’audit. Leurs soldes restent au bilan.") }}
      </div>

      <TableToolbar :t="tt" filename="bank-accounts" />
      <div v-if="loading" class="px-1"><TableLoading :rows="4" /></div>
      <div v-else class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead><tr style="background:#fafaf9">
            <th v-if="canWrite" class="ps-4 pe-1 py-2.5 w-8"><input type="checkbox" :checked="allSelected" @change="toggleAll" class="align-middle accent-violet-600" /></th>
            <th v-for="c in cols" v-show="!tt.hidden.value.has(c.key)" :key="c.key"
                class="px-4 py-2.5 text-[10px] font-bold uppercase tracking-wider text-ink-muted whitespace-nowrap cursor-pointer select-none hover:text-ink-2" :class="c.align === 'e' ? 'text-end' : 'text-start'" @click="tt.toggleSort(c.key)">
              <span class="inline-flex items-center gap-1" :class="c.align === 'e' ? 'flex-row-reverse' : ''">{{ c.label }}<Icon v-if="tt.sortKey.value === c.key" name="chevDown" :size="11" :class="tt.sortDir.value === 1 ? '' : 'rotate-180'" color="#0b5c4f" /></span>
            </th>
            <th v-if="canWrite" class="px-4 py-2.5"></th>
          </tr></thead>
          <tbody>
            <tr v-for="o in tt.pageRows.value" :key="o.name" class="border-t border-line-hair hover:bg-app-warm/70 cursor-pointer" :class="o.under_audit ? 'bg-violet-50/20' : ''" @click="open(o.name)">
              <td v-if="canWrite" class="ps-4 pe-1 py-2.5" @click.stop>
                <input type="checkbox" :checked="selected.has(o.name)" @change="toggleSel(o.name)" class="align-middle accent-violet-600" />
              </td>
              <td v-show="!tt.hidden.value.has('account_name')" class="px-4 py-2.5">
                <div class="font-semibold truncate max-w-[280px] inline-flex items-center gap-1.5">{{ o.account_name }}<span v-if="o.under_audit" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-violet-100 text-violet-700 whitespace-nowrap">{{ L("audit", "مراجعة", "audit") }}</span></div>
                <div class="text-[10px] text-ink-muted font-mono">{{ o.name.split(' - ')[0] }}</div>
              </td>
              <td v-show="!tt.hidden.value.has('account_type')" class="px-4 py-2.5"><span class="text-[10px] font-bold px-2 py-0.5 rounded-full" :style="o.account_type === 'Cash' ? 'background:#fffbeb;color:#b45309' : 'background:#eff6ff;color:#0369a1'">{{ o.account_type }}</span></td>
              <td v-show="!tt.hidden.value.has('ccy')" class="px-4 py-2.5 text-ink-3">{{ o.ccy }}</td>
              <td v-show="!tt.hidden.value.has('uncleared_n')" class="px-4 py-2.5 text-end tnum" :class="o.uncleared_n ? 'text-brand font-semibold' : 'text-ink-muted'">{{ o.uncleared_n || "—" }}</td>
              <td v-show="!tt.hidden.value.has('book')" class="px-4 py-2.5 text-end font-bold tnum whitespace-nowrap" :class="(o.period ? o.closing : o.book) < 0 ? 'text-sale' : ''">
                {{ fmt(o.period ? o.closing : o.book) }}
                <div v-if="o.period" class="text-[9.5px] font-normal text-ink-muted tnum">{{ fmt(o.opening) }} <span class="text-teal-600">+{{ fmt(o.period_in) }}</span> <span class="text-rose-500">−{{ fmt(o.period_out) }}</span></div>
              </td>
              <td v-if="canWrite" class="px-4 py-2.5 text-end" @click.stop>
                <button @click="togglePark(o)" :disabled="busy" class="h-7 px-2.5 rounded-chip text-[11px] font-semibold border transition-colors disabled:opacity-50 inline-flex items-center gap-1"
                        :class="o.under_audit ? 'text-accent-dark border-line-2 hover:bg-app-warm' : 'text-violet-700 border-violet-200 hover:bg-violet-50'">
                  <Icon :name="o.under_audit ? 'check' : 'shield'" :size="12" :color="o.under_audit ? '#0b5c4f' : '#7c3aed'" />
                  {{ o.under_audit ? L("Operating", "تشغيل", "Actif") : L("Park", "عزل", "Isoler") }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="!loading && !tt.sorted.value.length" class="py-12 text-center text-[12px] text-ink-muted">
        {{ viewMode === 'audit' ? L("No accounts under audit.", "لا حسابات تحت المراجعة.", "Aucun compte en audit.") : L("No accounts.", "لا حسابات.", "Aucun compte.") }}
      </div>
      <TablePager :t="tt" />
    </div>
  </div>
</template>

<script setup>
import { fmtAmount } from "@/utils/helpers";
import { ref, computed, watch } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableToolbar from "@/components/TableToolbar.vue";
import TablePager from "@/components/TablePager.vue";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";
import { useFiscalYear } from "@/composables/useFiscalYear";
import { useTableTools } from "@/composables/useTableTools";
import { useAuth } from "@/composables/useAuth";
import { useToast } from "@/composables/useToast";

const { locale } = useI18n();
const router = useRouter();
const { entityId } = useUi();
const fyc = useFiscalYear();
const { can } = useAuth();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const money = (n) => fmtAmount(n);
const canWrite = computed(() => can("post_entries"));

const cols = [
  { key: "account_name", label: L("Account", "الحساب", "Compte"), align: "s" },
  { key: "account_type", label: L("Type", "النوع", "Type"), align: "s" },
  { key: "ccy", label: L("Currency", "العملة", "Devise"), align: "s" },
  { key: "uncleared_n", label: L("Uncleared", "غير مُسوّى", "Non rappr."), align: "e" },
  { key: "book", label: L("Balance", "الرصيد", "Solde"), align: "e" },
];

const accounts = ref([]);
const live = ref(null);
const loading = ref(false);
const busy = ref(false);
const viewMode = ref("operating"); // operating | audit | all
const selected = ref(new Set());

const baseCcy = computed(() => accounts.value[0]?.base_ccy || "MAD");
const counts = computed(() => {
  const ua = accounts.value.filter((a) => a.under_audit).length;
  return { operating: accounts.value.length - ua, audit: ua, all: accounts.value.length };
});
const modes = computed(() => [
  { k: "operating", label: L("Operating", "تشغيلي", "Actifs"), n: counts.value.operating },
  { k: "audit", label: L("Under audit", "تحت المراجعة", "En audit"), n: counts.value.audit },
  { k: "all", label: L("All", "الكل", "Tous"), n: counts.value.all },
]);

const visible = computed(() => {
  if (viewMode.value === "audit") return accounts.value.filter((a) => a.under_audit);
  if (viewMode.value === "all") return accounts.value;
  return accounts.value.filter((a) => !a.under_audit);
});
const tt = useTableTools(visible, cols, { storeKey: "bankaccts", keyField: "name", defaultSort: "book", defaultDir: -1, accessor: (r, k) => (k === "book" || k === "uncleared_n" ? Number(r[k]) || 0 : r[k]) });

// Cards read ONLY operating accounts, summed in the company base currency so a
// TRY-based entity (Maslak) doesn't show 0 while all its cash is TRY.
const ins = computed(() => {
  const op = accounts.value.filter((a) => !a.under_audit);
  const sum = (f) => op.reduce((s, a) => s + (f(a) ? Number(a.book_base) || 0 : 0), 0);
  const od = op.filter((a) => Number(a.book_base) < 0);
  const parked = accounts.value.filter((a) => a.under_audit);
  return {
    position: sum(() => true),
    bank: sum((a) => a.account_type === "Bank"),
    cash: sum((a) => a.account_type === "Cash"),
    uncleared: op.reduce((s, a) => s + (Number(a.uncleared_v) || 0), 0),
    uncleared_n: op.reduce((s, a) => s + (Number(a.uncleared_n) || 0), 0),
    parked_v: parked.reduce((s, a) => s + (Number(a.book_base) || 0), 0),
  };
});

const allSelected = computed(() => {
  const rows = tt.pageRows.value;
  return rows.length > 0 && rows.every((r) => selected.value.has(r.name));
});
function toggleAll() {
  const s = new Set(selected.value);
  const rows = tt.pageRows.value;
  if (rows.every((r) => s.has(r.name))) rows.forEach((r) => s.delete(r.name));
  else rows.forEach((r) => s.add(r.name));
  selected.value = s;
}
function toggleSel(name) {
  const s = new Set(selected.value);
  s.has(name) ? s.delete(name) : s.add(name);
  selected.value = s;
}

async function togglePark(o) {
  if (busy.value) return;
  busy.value = true;
  const next = o.under_audit ? 0 : 1;
  try {
    await api.call("accounting_portal.api.bank_status.set_status", { company: currentCompany(), account: o.name, under_audit: next });
    o.under_audit = next;
    toast.success(next ? L("Parked under audit", "تم العزل تحت المراجعة", "Mis en audit") : L("Returned to operating", "أُرجع للتشغيل", "Réactivé"));
  } catch (e) { toast.error(String(e?.message || e).slice(0, 160)); }
  finally { busy.value = false; }
}
async function bulkPark(flag) {
  if (busy.value || !selected.value.size) return;
  busy.value = true;
  const accs = [...selected.value];
  try {
    const r = await api.call("accounting_portal.api.bank_status.set_status_bulk", { company: currentCompany(), accounts: accs, under_audit: flag ? 1 : 0 });
    const set = new Set(accs);
    accounts.value.forEach((a) => { if (set.has(a.name)) a.under_audit = flag ? 1 : 0; });
    selected.value = new Set();
    toast.success(flag ? L(`Parked ${r.changed} under audit`, `عُزل ${r.changed} تحت المراجعة`, `${r.changed} mis en audit`) : L(`Returned ${r.changed} to operating`, `أُرجع ${r.changed} للتشغيل`, `${r.changed} réactivés`));
  } catch (e) { toast.error(String(e?.message || e).slice(0, 160)); }
  finally { busy.value = false; }
}

const SAMPLE = [
  { name: "108.021.003 - Cathedis - JM", account_name: "Cathedis", account_type: "Bank", ccy: "MAD", book: 471081, book_base: 471081, base_ccy: "MAD", uncleared_n: 642, uncleared_v: 1208400, under_audit: 0 },
  { name: "102.02.01.01 - BMCE - JM", account_name: "BMCE-…130355", account_type: "Bank", ccy: "MAD", book: 12483, book_base: 12483, base_ccy: "MAD", uncleared_n: 3407, uncleared_v: 44372442, under_audit: 0 },
  { name: "100.002.002 - Petty cash - JM", account_name: "Petty cash", account_type: "Cash", ccy: "MAD", book: -845264, book_base: -845264, base_ccy: "MAD", uncleared_n: 120, uncleared_v: 280000, under_audit: 1 },
];
async function load() {
  loading.value = true;
  selected.value = new Set();
  try { accounts.value = await api.call("accounting_portal.api.reconciliation.bank_rec_accounts", { company: currentCompany(), ...fyc.filterValue() }) || []; live.value = true; }
  catch { accounts.value = SAMPLE; live.value = false; }
  finally { loading.value = false; }
}
function open(name) { router.push({ path: "/accounting/banking/accounts", query: { id: name } }); }
function goRec() { router.push("/accounting/banking/bankrec"); }
watch(entityId, load, { immediate: true });
watch(fyc.selected, load);
</script>
