<template>
  <div class="space-y-3.5">
    <div class="flex items-center gap-2 flex-wrap">
      <div class="flex gap-1 bg-white border border-line rounded-chip p-1 w-fit shadow-card">
        <button v-for="v in VIEWS" :key="v.k" class="px-3.5 py-1.5 rounded-lg text-[12px] font-semibold whitespace-nowrap inline-flex items-center gap-1.5" :class="view === v.k ? 'bg-app-warm text-accent-dark shadow-card' : 'text-ink-3 hover:text-ink'" @click="view = v.k">
          <Icon :name="v.icon" :size="13" />{{ v.label() }}<span v-if="v.k==='recurring' && dueBadge" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-rose-100 text-rose-700">{{ dueBadge }}</span>
        </button>
      </div>
      <button v-if="can('post_entries')" type="button" class="ms-auto inline-flex items-center gap-1.5 h-9 px-3.5 rounded-chip text-[12.5px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand" @click="openNew">
        <Icon name="plus" :size="14" />{{ L("New expense", "مصروف جديد", "Nouvelle dépense") }}
      </button>
    </div>

    <RecurringExpenses v-if="view === 'recurring'" @counts="onCounts" @record="onRecord" />

    <!-- ── TRANSACTIONS ── -->
    <template v-else-if="view === 'transactions'">
      <DateFilterBar :df="df" />
      <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
        <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2 flex-wrap">
          <div class="flex gap-1 bg-app-warm/50 rounded-chip p-0.5">
            <button v-for="gp in GROUPS" :key="gp.k" class="px-2.5 py-1 rounded-lg text-[11px] font-semibold" :class="tx.filters.value.group === gp.k ? 'bg-white text-accent-dark shadow-card' : 'text-ink-3'" @click="setGroup(gp.k)">{{ gp.label() }}</button>
          </div>
          <select :value="tx.filters.value.category" class="h-8 bg-app-warm/40 border border-line-2 rounded-[9px] px-2 text-[11.5px] focus:outline-none focus:border-accent/40" @change="setCat($event.target.value)">
            <option value="all">{{ L("All categories", "كل الفئات", "Toutes catégories") }}</option>
            <option v-for="c in CATS" :key="c" :value="c">{{ catLabel(c) }}</option>
          </select>
          <div class="inline-flex items-center gap-1 text-[11px] text-ink-muted">
            <span>≥</span>
            <input type="number" min="0" :value="tx.filters.value.min_amount" placeholder="0" class="w-20 h-8 bg-app-warm/40 border border-line-2 rounded-[9px] px-2 text-[11.5px] text-end tnum focus:outline-none focus:border-accent/40" @change="setMin($event.target.value)" />
          </div>
          <div class="ms-auto relative">
            <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="14" /></span>
            <input v-model.trim="tx.search.value" :placeholder="L('account · voucher · memo…','حساب · مستند · ملاحظة…','compte · pièce…')" class="w-44 sm:w-60 h-8 bg-app-warm/40 border border-line-2 rounded-[9px] ps-8 pe-3 text-[12px] focus:outline-none focus:border-accent/40 focus:bg-white" />
          </div>
        </div>
        <TableLoading v-if="tx.loading.value" :rows="8" />
        <div v-else class="overflow-x-auto">
          <table class="w-full text-[12px]">
            <thead><tr style="background:#fafaf9" class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">
              <th class="px-4 py-2 text-start">{{ L("Date", "التاريخ", "Date") }}</th>
              <th class="px-3 py-2 text-start">{{ L("Category", "الفئة", "Catégorie") }}</th>
              <th class="px-3 py-2 text-start">{{ L("Account", "الحساب", "Compte") }}</th>
              <th class="px-3 py-2 text-start hidden md:table-cell">{{ L("Voucher", "المستند", "Pièce") }}</th>
              <th class="px-4 py-2 text-end">{{ L("Amount", "المبلغ", "Montant") }}</th>
            </tr></thead>
            <tbody>
              <tr v-for="r in tx.rows.value" :key="r.id" class="border-t border-line-hair hover:bg-app-warm/40" :class="canOpen(r) ? 'cursor-pointer group' : ''" @click="openVoucher(r)">
                <td class="px-4 py-2.5 whitespace-nowrap text-ink-2">{{ r.posting_date }}</td>
                <td class="px-3 py-2.5"><span class="text-[10px] font-semibold px-1.5 py-0.5 rounded-chip whitespace-nowrap" :style="`background:${catColor(r.category)}18;color:${catColor(r.category)}`">{{ catLabel(r.category) }}</span></td>
                <td class="px-3 py-2.5"><div class="font-semibold truncate max-w-[240px]" :class="canOpen(r) ? 'group-hover:text-accent-dark' : ''">{{ r.nm }}</div><div v-if="r.remarks" class="text-[10px] text-ink-muted truncate max-w-[240px]">{{ r.remarks }}</div></td>
                <td class="px-3 py-2.5 hidden md:table-cell"><div class="font-mono text-[10.5px] text-ink-3">{{ r.voucher_no }}</div><div class="text-[9.5px] text-ink-muted">{{ r.voucher_type }}<span v-if="r.party"> · {{ r.party }}</span></div></td>
                <td class="px-4 py-2.5 text-end whitespace-nowrap">
                  <span class="tnum font-bold" :class="r.amount < 0 ? 'text-rose-500' : ''">{{ money(r.amount) }}</span>
                  <button v-if="can('post_entries') && canDup(r)" type="button" class="ms-2 align-middle text-ink-muted hover:text-accent-dark opacity-0 group-hover:opacity-100 transition" :title="L('Duplicate','تكرار','Dupliquer')" @click.stop="duplicate(r)"><Icon name="copy" :size="13" /></button>
                </td>
              </tr>
              <tr v-if="!tx.rows.value.length"><td colspan="5" class="px-4 py-10 text-center text-ink-muted">{{ L("No expense transactions match.", "لا مصروفات مطابقة.", "Aucune dépense.") }}</td></tr>
            </tbody>
          </table>
        </div>
        <ServerPager v-if="tx.total.value" :t="tx" />
      </div>
    </template>

    <!-- ── BREAKDOWN ── -->
    <template v-else>
    <DateFilterBar :df="df" />

    <TableLoading v-if="loading" :rows="6" />
    <div v-else-if="err" class="bg-white rounded-card border border-rose-200 shadow-card px-4 py-10 text-center">
      <Icon name="alert" :size="20" color="#e11d48" class="inline-block mb-2" />
      <p class="text-[12.5px] text-ink-2">{{ L("Couldn't load expenses.","تعذّر تحميل المصروفات.","Échec du chargement.") }}</p>
      <button type="button" class="mt-2 h-8 px-3 rounded-chip border border-line-2 text-[12px] font-semibold hover:bg-app-warm" @click="load">{{ L("Retry","إعادة","Réessayer") }}</button>
    </div>

    <template v-else>
      <!-- the split the user wants: cost of sales vs operating expenses -->
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div class="bg-white rounded-card border border-line shadow-card px-4 py-3.5">
          <div class="text-[10px] font-bold uppercase tracking-wider text-ink-muted flex items-center gap-1.5"><Icon name="layers" :size="13" color="#0f766e" />{{ L("Cost of sales","تكلفة المبيعات","Coût des ventes") }}</div>
          <div class="text-[20px] font-extrabold mt-1 tnum" style="color:#0f766e">{{ money(g.cost_of_sales) }} <span class="text-[12px] text-ink-muted font-bold">{{ ccy }}</span></div>
          <div class="text-[10.5px] text-ink-muted mt-0.5">{{ L("COGS + freight & logistics","تكلفة البضاعة + الشحن","CMV + fret") }}</div>
        </div>
        <div class="bg-white rounded-card border border-line shadow-card px-4 py-3.5">
          <div class="text-[10px] font-bold uppercase tracking-wider text-ink-muted flex items-center gap-1.5"><Icon name="building" :size="13" color="#7c3aed" />{{ L("Operating expenses","المصروفات التشغيلية","Charges d'exploitation") }}</div>
          <div class="text-[20px] font-extrabold mt-1 tnum" style="color:#7c3aed">{{ money(g.opex) }} <span class="text-[12px] text-ink-muted font-bold">{{ ccy }}</span></div>
          <div class="text-[10.5px] text-ink-muted mt-0.5">{{ L("payroll · rent · marketing · taxes…","رواتب · إيجار · تسويق · ضرائب…","paie · loyer · marketing…") }}</div>
        </div>
        <div class="bg-white rounded-card border border-line shadow-card px-4 py-3.5">
          <div class="text-[10px] font-bold uppercase tracking-wider text-ink-muted flex items-center gap-1.5"><Icon name="wallet" :size="13" color="#0369a1" />{{ L("Total expense","إجمالي المصروف","Total") }}</div>
          <div class="text-[20px] font-extrabold mt-1 tnum">{{ money(data.total) }} <span class="text-[12px] text-ink-muted font-bold">{{ ccy }}</span></div>
          <div class="text-[10.5px] text-ink-muted mt-0.5">{{ (data.categories||[]).length }} {{ L("categories","فئات","catégories") }}</div>
        </div>
      </div>

      <!-- category breakdown -->
      <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
        <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2">
          <Icon name="list" :size="14" color="#0b5c4f" /><span class="text-[12px] font-bold">{{ L("By category","حسب الفئة","Par catégorie") }}</span>
          <span class="text-[10px] text-ink-muted">{{ L("click to see accounts","اضغط لعرض الحسابات","cliquer pour les comptes") }}</span>
        </div>
        <div v-for="c in data.categories" :key="c.cat" class="border-t border-line-hair first:border-t-0">
          <button type="button" class="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-app-warm/40 text-start" @click="toggle(c.cat)">
            <span class="w-2.5 h-2.5 rounded-sm shrink-0" :style="`background:${c.color}`"></span>
            <span class="text-[12.5px] font-semibold w-40 shrink-0">{{ catLabel(c.cat) }}</span>
            <span class="text-[10px] font-semibold px-1.5 py-0.5 rounded-chip shrink-0" :class="c.group==='cost_of_sales' ? 'bg-teal-50 text-teal-700' : 'bg-violet-50 text-violet-700'">{{ c.group==='cost_of_sales' ? L('COS','ت.مبيعات','CV') : L('OPEX','تشغيلي','OPEX') }}</span>
            <span class="flex-1 hidden sm:block"><span class="block h-2 rounded-full" :style="`width:${bar(c.amount)}%;background:${c.color};opacity:.55`"></span></span>
            <span class="text-[10.5px] text-ink-muted tnum w-10 text-end shrink-0">{{ pct(c.amount) }}%</span>
            <span class="tnum font-bold text-[13px] w-28 text-end shrink-0">{{ money(c.amount) }}</span>
            <Icon name="arrow" :size="12" color="#cbd5e1" class="shrink-0 transition-transform" :class="open[c.cat] ? 'rotate-90' : ''" />
          </button>
          <div v-if="open[c.cat]" class="bg-app-warm/30 px-4 py-1">
            <button v-for="a in (data.by_account[c.cat]||[])" :key="a.num" type="button" class="w-full flex items-center gap-2 py-1.5 text-[11.5px] border-b border-line-hair/60 last:border-b-0 hover:text-accent-dark text-start" @click="drillAccount(a)">
              <span class="font-mono text-[10px] text-ink-muted w-24 shrink-0">{{ a.num || "—" }}</span>
              <span class="flex-1 truncate text-ink-2">{{ a.name }}</span>
              <span class="tnum font-semibold" :class="a.amount < 0 ? 'text-rose-500' : ''">{{ money(a.amount) }}</span>
            </button>
          </div>
        </div>
      </div>

      <!-- monthly trend -->
      <div v-if="(data.months||[]).length" class="bg-white rounded-card border border-line shadow-card px-4 py-3">
        <div class="flex items-center gap-2 mb-3 flex-wrap">
          <Icon name="chart" :size="14" color="#0b5c4f" /><span class="text-[12px] font-bold">{{ L("Monthly trend","الاتجاه الشهري","Tendance mensuelle") }}</span>
          <span class="ms-auto flex items-center gap-2.5 flex-wrap text-[9.5px] text-ink-muted">
            <span v-for="c in data.categories" :key="c.cat" class="inline-flex items-center gap-1"><span class="w-2 h-2 rounded-sm" :style="`background:${c.color}`"></span>{{ catLabel(c.cat) }}</span>
          </span>
        </div>
        <div class="flex items-end gap-2 h-36">
          <div v-for="mo in data.months" :key="mo.m" class="flex-1 flex flex-col items-center gap-1 min-w-0">
            <div class="w-full flex-1 flex flex-col justify-end" :title="mo.m + ' · ' + money(monthTotal(mo)) + ' ' + ccy">
              <div v-for="c in data.categories" :key="c.cat" v-show="(mo[c.cat]||0) > 0" :style="`height:${segH(mo[c.cat])}%;background:${c.color};min-height:1px`"></div>
            </div>
            <span class="text-[9.5px] text-ink-muted whitespace-nowrap">{{ mLabel(mo.m) }}</span>
          </div>
        </div>
      </div>
    </template>
    </template>

    <NewExpenseModal v-if="showNew" :prefill="newPrefill" @close="closeNew" @posted="onPosted" />
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter, useRoute } from "vue-router";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import DateFilterBar from "@/components/DateFilterBar.vue";
import ServerPager from "@/components/ServerPager.vue";
import RecurringExpenses from "@/pages/accountant/RecurringExpenses.vue";
import NewExpenseModal from "@/components/NewExpenseModal.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";
import { useAuth } from "@/composables/useAuth";
import { useToast } from "@/composables/useToast";
import { useDateFilter } from "@/composables/useDateFilter";
import { useServerTable } from "@/composables/useServerTable";
import { fmtMoney } from "@/utils/helpers";

const { locale } = useI18n();
const { entityId } = useUi();
const { can } = useAuth();
const toast = useToast();
const router = useRouter();
const route = useRoute();
// Keep the active tab in the URL (?t=…) so Back / reload return here.
const TABS = ["breakdown", "transactions", "recurring"];
const view = ref(TABS.includes(route.query.t) ? route.query.t : "breakdown");
watch(view, (v) => { if (route.query.t !== v) router.replace({ query: { ...route.query, t: v } }); });
const dueBadge = ref(0);
const showNew = ref(false);
const newPrefill = ref(null);
const VIEWS = [
  { k: "breakdown", icon: "list", label: () => L("Breakdown", "التفصيل", "Répartition") },
  { k: "transactions", icon: "receipt", label: () => L("Transactions", "الحركات", "Transactions") },
  { k: "recurring", icon: "clock", label: () => L("Recurring & due", "المتكرّر والمستحق", "Récurrent") },
];
const GROUPS = [
  { k: "opex", label: () => L("Operating", "تشغيلية", "Exploitation") },
  { k: "cost_of_sales", label: () => L("Cost of sales", "تكلفة المبيعات", "Coût ventes") },
  { k: "all", label: () => L("All", "الكل", "Tout") },
];
const CATS = ["COGS", "Freight & Logistics", "Payroll", "Marketing", "Taxes", "Financial", "Rent, Office & Utilities", "Other"];
const CAT_COLOR = { COGS: "#0f766e", "Freight & Logistics": "#0369a1", Payroll: "#7c3aed", Marketing: "#db2777", Taxes: "#0891b2", Financial: "#4f46e5", "Rent, Office & Utilities": "#b45309", Other: "#78716c" };
const catColor = (c) => CAT_COLOR[c] || "#78716c";
const onCounts = (c) => { dueBadge.value = (c.due || 0) + (c.overdue || 0); };
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
// Accounting precision: exact, grouped, 2 decimals — no K/M abbreviation.
const money = (n) => fmtMoney(n, "", 2);

const CAT_AR = { "COGS": "تكلفة البضاعة", "Freight & Logistics": "الشحن واللوجيستيك", "Payroll": "الرواتب", "Marketing": "التسويق", "Rent, Office & Utilities": "الإيجار والمكتب", "Taxes": "الضرائب", "Financial": "مصاريف مالية", "Other": "أخرى" };
const CAT_FR = { "COGS": "CMV", "Freight & Logistics": "Fret & logistique", "Payroll": "Paie", "Marketing": "Marketing", "Rent, Office & Utilities": "Loyer & bureau", "Taxes": "Taxes", "Financial": "Frais financiers", "Other": "Autres" };
const catLabel = (c) => (locale.value === "ar" ? (CAT_AR[c] || c) : locale.value === "fr" ? (CAT_FR[c] || c) : c);

const data = ref({});
const loading = ref(true);
const err = ref(false);
const open = reactive({});
const ccy = computed(() => data.value.currency || "MAD");
const g = computed(() => data.value.groups || {});

const df = useDateFilter("expcenter", () => { load(); if (view.value === "transactions") tx.load(); }, "year");

async function load() {
  loading.value = true; err.value = false;
  try { data.value = await api.call("accounting_portal.api.expenses.expense_cockpit", { company: currentCompany(), ...df.filterValue() }) || {}; }
  catch { data.value = {}; err.value = true; }
  finally { loading.value = false; }
}
load();

// ── transactions (server-paginated + filtered) ──
const tx = useServerTable(
  (p) => api.call("accounting_portal.api.expenses.expense_transactions", {
    company: currentCompany(), ...df.filterValue(),
    group: p.group, category: p.category,
    min_amount: p.min_amount ? Number(p.min_amount) : undefined,
    search: p.search, start: p.start, page_size: p.page_size,
  }),
  { pageSize: 25, filters: { group: "opex", category: "all", min_amount: "" } });
const setGroup = (gp) => tx.setFilters({ group: gp, category: "all" });
const setCat = (c) => tx.setFilters({ category: c });
const setMin = (m) => tx.setFilters({ min_amount: m });
// Map each voucher type to the portal detail screen that opens it.
const VOUCHER_ROUTE = {
  "Journal Entry": "/accounting/accountant/journals",
  "Purchase Invoice": "/accounting/purchases/bills",
  "Payment Entry": "/accounting/purchases/payments",
  "Sales Invoice": "/accounting/sales/invoices",
  "Delivery Note": "/accounting/sales/challans",
  "Purchase Receipt": "/accounting/purchases/received",
};
const canOpen = (r) => !!(r.voucher_no && VOUCHER_ROUTE[r.voucher_type]);
function openVoucher(r) {
  const path = VOUCHER_ROUTE[r.voucher_type];
  if (path && r.voucher_no) router.push({ path, query: { id: r.voucher_no } });
}

watch(view, (v) => { if (v === "transactions" && !tx.rows.value.length) tx.load(); });
watch(entityId, () => { load(); loadBadge(); if (view.value === "transactions") tx.load(); });

// fetch the due/overdue count once so the "Recurring" tab shows a reminder badge
async function loadBadge() {
  try { const r = await api.call("accounting_portal.api.recurring.recurring_overview", { company: currentCompany() }); dueBadge.value = (r?.due || 0) + (r?.overdue || 0); }
  catch { /* ignore */ }
}
loadBadge();

function openNew() { newPrefill.value = null; showNew.value = true; }
function onRecord(prefill) { newPrefill.value = prefill; showNew.value = true; }
// Duplicate an existing bill / cash expense → open the form pre-filled.
const canDup = (r) => ["Purchase Invoice", "Journal Entry"].includes(r.voucher_type) && r.voucher_no;
async function duplicate(r) {
  try {
    const pre = await api.call("accounting_portal.api.expenses.duplicate_source", {
      company: currentCompany(), source_type: r.voucher_type, source_name: r.voucher_no });
    newPrefill.value = pre; showNew.value = true;
  } catch (e) { toast.error(String(e?.message || e).slice(0, 160)); }
}
function closeNew() { showNew.value = false; newPrefill.value = null; }
function onPosted(res) {
  const proposed = res && res.status === "Proposed";
  if (proposed) toast.success(L("Sent for approval", "أُرسل للموافقة", "Envoyé pour approbation"));
  else toast.success(L("Expense recorded", "تم تسجيل المصروف", "Dépense enregistrée"));
  load();
  if (view.value === "transactions") tx.load();
}

const maxCat = computed(() => Math.max(1, ...(data.value.categories || []).map((c) => Math.abs(c.amount))));
const bar = (v) => Math.max(2, Math.round(Math.abs(Number(v) || 0) / maxCat.value * 100));
const pct = (v) => { const t = (data.value.total || 0); return t ? Math.round(Math.abs(Number(v) || 0) / Math.abs(t) * 100) : 0; };
function toggle(c) { open[c] = !open[c]; }
function drillAccount(a) { view.value = "transactions"; tx.setFilters({ group: "all", category: "all" }); tx.search.value = a.name; }

const monthTotal = (mo) => (data.value.categories || []).reduce((s, c) => s + (Number(mo[c.cat]) || 0), 0);
const maxMonth = computed(() => Math.max(1, ...(data.value.months || []).map((mo) => (data.value.categories || []).reduce((s, c) => s + Math.max(0, Number(mo[c.cat]) || 0), 0))));
const segH = (v) => Math.max(0, Math.round(Math.max(0, Number(v) || 0) / maxMonth.value * 100));
const mLabel = (m) => { const p = String(m || "").split("-"); return p.length === 2 ? p[1] + "/" + p[0].slice(2) : m; };
</script>
