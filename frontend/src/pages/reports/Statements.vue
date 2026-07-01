<template>
  <div class="space-y-3.5 print-statement">
    <!-- Controls -->
    <div class="flex items-center gap-2 flex-wrap no-print">
      <div class="inline-flex bg-white border border-line rounded-chip p-1 shadow-card">
        <button v-for="s in TABS" :key="s.key" @click="tab = s.key" class="px-3.5 py-1.5 rounded-lg text-[12px] font-semibold transition" :class="tab === s.key ? 'bg-app-warm text-accent-dark shadow-card' : 'text-ink-3 hover:text-ink'">{{ s.label() }}</button>
      </div>
      <span v-if="live !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="live ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ live ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échant.") }}</span>
      <div class="ms-auto flex items-center gap-1.5">
        <template v-if="tab !== 'monthly'">
          <button v-for="p in PRESETS" :key="p.key" @click="setPreset(p.key)" class="text-[11px] font-semibold px-2.5 py-1 rounded-full border transition" :class="preset === p.key ? 'bg-ink text-white border-ink' : 'bg-white text-ink-3 border-line-2 hover:bg-app-warm'">{{ p.label() }}</button>
          <button @click="compare = compare ? 0 : 1, load()" class="text-[11px] font-semibold px-2.5 py-1 rounded-full border transition" :class="compare ? 'bg-accent/10 text-accent-dark border-accent/30' : 'bg-white text-ink-3 border-line-2'">{{ L("Compare","مقارنة","Comparer") }}</button>
        </template>
        <button @click="printIt" class="h-7 px-2.5 rounded-full text-[11px] font-bold text-white bg-ink inline-flex items-center gap-1"><Icon name="doc" :size="12" color="#fff" />{{ L("Print","طباعة","Imprimer") }}</button>
      </div>
    </div>
    <div v-if="tab !== 'monthly'" class="text-[11px] text-ink-muted no-print tnum">{{ d.from_date }} → {{ d.to_date }}<span v-if="compare && d.prior_from"> · {{ L("vs","مقابل","vs") }} {{ d.prior_from }} → {{ d.prior_to }}</span></div>

    <div v-if="loading && tab !== 'monthly'" class="bg-white rounded-card border border-line shadow-card py-16 text-center text-ink-muted text-[12px]">{{ L("Loading…","تحميل…","…") }}</div>

    <!-- ── Profit & Loss ── -->
    <div v-else-if="tab === 'pnl'" class="space-y-3">
      <div v-if="d.pnl.anomaly" class="rounded-[12px] border border-amber-200 bg-amber-50 px-4 py-2.5 flex items-center gap-2.5">
        <Icon name="alert" :size="15" color="#b45309" /><span class="text-[11.5px] text-ink-2">{{ L("Net is distorted by","الصافي متأثر بـ","Faussé par") }} “{{ d.pnl.anomaly.name }}” ({{ money(d.pnl.anomaly.amount) }}) — {{ L("the broken stock/COGS posting. Read net with care.","قيد المخزون/التكلفة المعطّل. اقرأ الصافي بحذر.","écriture stock/CMV cassée.") }}</span>
      </div>
      <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
        <div class="px-5 py-3 border-b border-line-hair flex items-center gap-2"><Icon name="scale" :size="15" color="#0b5c4f" /><span class="text-[13px] font-bold">{{ L("Profit & loss","الأرباح والخسائر","Compte de résultat") }}</span><span class="text-[10px] text-ink-muted">{{ d.currency }}</span></div>
        <table class="w-full text-[12.5px]">
          <thead v-if="compare"><tr style="background:#fafaf9"><th></th><th class="px-5 py-1.5 text-end text-[10px] font-bold uppercase tracking-wide text-ink-muted">{{ L("Current","الحالية","Actuel") }}</th><th class="px-5 py-1.5 text-end text-[10px] font-bold uppercase tracking-wide text-ink-muted">{{ L("Prior","السابقة","Précéd.") }}</th><th class="px-5 py-1.5 text-end text-[10px] font-bold uppercase tracking-wide text-ink-muted">Δ</th></tr></thead>
          <tbody>
            <template v-for="sec in pnlSections" :key="sec.key">
              <tr class="border-t border-line-hair" style="background:#fcfcfb"><td class="px-5 py-1.5 font-bold text-[11px] uppercase tracking-wide text-ink-3" :colspan="compare ? 4 : 2">{{ sec.title }}</td></tr>
              <tr v-for="(a, i) in sec.accounts" :key="i" class="border-t border-line-hair hover:bg-app-warm/40" :class="a.account && 'cursor-pointer'" @click="a.account && drill(a.account)">
                <td class="px-5 py-1.5 ps-8 text-ink-2 truncate max-w-[280px] hover:text-accent-dark">{{ a.name }}</td>
                <td class="px-5 py-1.5 text-end tnum">{{ fmt(a.amount) }}</td>
                <template v-if="compare"><td class="px-5 py-1.5 text-end tnum text-ink-muted">{{ fmt(a.prior) }}</td><td class="px-5 py-1.5 text-end tnum" :class="delta(a.amount, a.prior).c">{{ delta(a.amount, a.prior).t }}</td></template>
              </tr>
              <tr v-if="sec.subtotal != null" class="border-t border-line-2 font-bold" style="background:#fafaf9">
                <td class="px-5 py-2">{{ sec.subtotalLabel }}</td><td class="px-5 py-2 text-end tnum" :class="sec.subtotal < 0 ? 'text-sale' : ''">{{ fmt(sec.subtotal) }}</td>
                <template v-if="compare"><td class="px-5 py-2 text-end tnum text-ink-muted">{{ fmt(sec.subtotalPrior) }}</td><td class="px-5 py-2 text-end tnum" :class="delta(sec.subtotal, sec.subtotalPrior).c">{{ delta(sec.subtotal, sec.subtotalPrior).t }}</td></template>
              </tr>
            </template>
            <tr class="border-t-2 border-ink font-extrabold" style="background:#faf6f4">
              <td class="px-5 py-2.5 text-[13px]">{{ L("Net profit","صافي الربح","Résultat net") }}</td>
              <td class="px-5 py-2.5 text-end tnum text-[14px]" :class="d.pnl.net < 0 ? 'text-sale' : 'text-success-dark'">{{ fmt(d.pnl.net) }}</td>
              <template v-if="compare"><td class="px-5 py-2.5 text-end tnum text-ink-muted">{{ fmt(d.pnl.net_prior) }}</td><td class="px-5 py-2.5 text-end tnum" :class="delta(d.pnl.net, d.pnl.net_prior).c">{{ delta(d.pnl.net, d.pnl.net_prior).t }}</td></template>
            </tr>
          </tbody>
        </table>
        <div class="px-5 py-2 border-t border-line-hair text-[11px] text-ink-muted">{{ L("Gross margin","هامش إجمالي","Marge brute") }} {{ d.pnl.gross_margin }}%</div>
      </div>
    </div>

    <!-- ── Balance Sheet ── -->
    <div v-else-if="tab === 'bs'" class="bg-white rounded-card border border-line shadow-card overflow-hidden">
      <div class="px-5 py-3 border-b border-line-hair flex items-center gap-2"><Icon name="bank" :size="15" color="#0369a1" /><span class="text-[13px] font-bold">{{ L("Balance sheet","الميزانية العمومية","Bilan") }}</span><span class="text-[10px] text-ink-muted">{{ L("as on","حتى","au") }} {{ d.balance_sheet.as_on }}</span>
        <span class="ms-auto text-[9.5px] font-bold px-2 py-0.5 rounded-full" :style="Math.abs(d.balance_sheet.check) < 2 ? 'background:#ecfdf5;color:#047857' : 'background:#fef2f2;color:#b91c1c'">{{ Math.abs(d.balance_sheet.check) < 2 ? L("Balanced","متوازنة","Équilibré") : L("Off by","فرق","Écart") + " " + money(d.balance_sheet.check) }}</span>
      </div>
      <table class="w-full text-[12.5px]">
        <tbody>
          <BsBlock :title="L('Assets','الأصول','Actifs')" :sections="d.balance_sheet.assets" :total="d.balance_sheet.assets_total" :compare="compare" :on-drill="drill" />
          <BsBlock :title="L('Liabilities','الخصوم','Passifs')" :sections="d.balance_sheet.liabilities" :total="d.balance_sheet.liabilities_total" :compare="compare" :on-drill="drill" />
          <BsBlock :title="L('Equity','حقوق الملكية','Capitaux')" :sections="d.balance_sheet.equity" :total="d.balance_sheet.equity_total" :compare="compare" :on-drill="drill" />
        </tbody>
      </table>
    </div>

    <!-- ── Cash Flow ── -->
    <div v-else-if="tab === 'cf'" class="bg-white rounded-card border border-line shadow-card overflow-hidden">
      <div class="px-5 py-3 border-b border-line-hair flex items-center gap-2"><Icon name="coins" :size="15" color="#7c3aed" /><span class="text-[13px] font-bold">{{ L("Cash flow statement","قائمة التدفّق النقدي","Flux de trésorerie") }}</span><span class="text-[10px] text-ink-muted">{{ L("direct method","الطريقة المباشرة","méthode directe") }}</span>
        <span class="ms-auto text-[9.5px] font-bold px-2 py-0.5 rounded-full" :style="d.cash_flow.reconciles ? 'background:#ecfdf5;color:#047857' : 'background:#fffbeb;color:#b45309'">{{ d.cash_flow.reconciles ? L("Reconciles","متطابق","Rapproché") : L("Check","راجع","Vérifier") }}</span>
      </div>
      <table class="w-full text-[12.5px]">
        <tbody>
          <tr class="border-t border-line-hair"><td class="px-5 py-2 font-semibold">{{ L("Opening cash","نقد افتتاحي","Trésorerie d'ouverture") }}</td><td class="px-5 py-2 text-end tnum" :class="d.cash_flow.open_cash < 0 ? 'text-sale' : ''">{{ fmt(d.cash_flow.open_cash) }}</td></tr>
          <tr class="border-t border-line-hair"><td class="px-5 py-2 ps-8 text-success-dark">{{ L("Cash received","مقبوضات","Encaissements") }}</td><td class="px-5 py-2 text-end tnum text-success-dark">+{{ fmt(d.cash_flow.cash_in) }}</td></tr>
          <tr class="border-t border-line-hair"><td class="px-5 py-2 ps-8 text-sale">{{ L("Cash paid","مدفوعات","Décaissements") }}</td><td class="px-5 py-2 text-end tnum text-sale">−{{ fmt(d.cash_flow.cash_out) }}</td></tr>
          <tr class="border-t border-line-2 font-bold" style="background:#fafaf9"><td class="px-5 py-2">{{ L("Net change","صافي التغيّر","Variation nette") }}</td><td class="px-5 py-2 text-end tnum" :class="d.cash_flow.net_change < 0 ? 'text-sale' : ''">{{ fmt(d.cash_flow.net_change) }}</td></tr>
          <tr class="border-t-2 border-ink font-extrabold" style="background:#faf6f4"><td class="px-5 py-2.5 text-[13px]">{{ L("Closing cash","نقد ختامي","Trésorerie de clôture") }}</td><td class="px-5 py-2.5 text-end tnum text-[14px]" :class="d.cash_flow.close_cash < 0 ? 'text-sale' : 'text-success-dark'">{{ fmt(d.cash_flow.close_cash) }} <span class="text-[10px] text-ink-muted">{{ d.currency }}</span></td></tr>
        </tbody>
      </table>
    </div>

    <!-- ── P&L by month ── -->
    <div v-else-if="tab === 'monthly'" class="bg-white rounded-card border border-line shadow-card overflow-hidden">
      <div class="px-5 py-3 border-b border-line-hair flex items-center gap-2 flex-wrap no-print">
        <Icon name="scale" :size="15" color="#0b5c4f" /><span class="text-[13px] font-bold">{{ L("P&L by month","الأرباح والخسائر بالشهر","Résultat par mois") }}</span>
        <span class="text-[10px] text-ink-muted">{{ dm.currency }} · {{ mYear }}</span>
        <div class="ms-auto flex items-center gap-1.5">
          <button v-for="yr in [y, y - 1]" :key="yr" @click="setYear(yr)" class="text-[11px] font-semibold px-2.5 py-1 rounded-full border transition" :class="mYear === yr ? 'bg-ink text-white border-ink' : 'bg-white text-ink-3 border-line-2 hover:bg-app-warm'">{{ yr }}</button>
          <button @click="mCsv" class="h-7 px-2.5 rounded-full text-[11px] font-bold text-white bg-ink inline-flex items-center gap-1"><Icon name="doc" :size="12" color="#fff" />CSV</button>
        </div>
      </div>
      <div v-if="mLoading" class="py-16 text-center text-ink-muted text-[12px]">{{ L("Loading…","تحميل…","…") }}</div>
      <div v-else-if="dm.months && dm.months.length" class="overflow-x-auto">
        <table class="text-[12px] min-w-full whitespace-nowrap">
          <thead><tr style="background:#fafaf9">
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted sticky start-0 z-10" style="background:#fafaf9">{{ L("Account","الحساب","Compte") }}</th>
            <th v-for="ym in dm.months" :key="ym" class="px-3 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ monLabel(ym) }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-2">{{ L("Total","الإجمالي","Total") }}</th>
          </tr></thead>
          <tbody>
            <template v-for="sk in ['revenue', 'cogs', 'opex']" :key="sk">
              <tr style="background:#fcfcfb"><td :colspan="dm.months.length + 2" class="px-4 py-1.5 font-bold text-[11px] uppercase tracking-wide text-ink-3 sticky start-0" >{{ secLabel(sk) }}</td></tr>
              <tr v-for="(a, i) in mSection(sk).accounts" :key="sk + i" class="border-t border-line-hair hover:bg-app-warm/40 cursor-pointer" @click="a.account && drill(a.account)">
                <td class="px-4 py-1.5 truncate max-w-[220px] sticky start-0 bg-white hover:text-accent-dark">{{ a.name }}</td>
                <td v-for="(v, j) in a.monthly" :key="j" class="px-3 py-1.5 text-end tnum" :class="v < 0 ? 'text-sale' : 'text-ink-2'">{{ v ? money(v) : "·" }}</td>
                <td class="px-4 py-1.5 text-end tnum font-semibold">{{ money(a.total) }}</td>
              </tr>
              <tr class="border-t border-line-2 font-bold" style="background:#fafaf9">
                <td class="px-4 py-1.5 sticky start-0" style="background:#fafaf9">{{ L("Total","إجمالي","Total") }} {{ secLabel(sk).toLowerCase() }}</td>
                <td v-for="(v, j) in mSection(sk).monthly_total" :key="j" class="px-3 py-1.5 text-end tnum" :class="v < 0 ? 'text-sale' : ''">{{ money(v) }}</td>
                <td class="px-4 py-1.5 text-end tnum">{{ money(mSection(sk).total) }}</td>
              </tr>
              <tr v-if="sk === 'cogs'" :key="'gp'" class="border-t border-line-2 font-bold" style="background:#f3f8f6">
                <td class="px-4 py-1.5 sticky start-0" style="background:#f3f8f6">{{ L("Gross profit","الربح الإجمالي","Marge brute") }}</td>
                <td v-for="(v, j) in dm.gross_monthly" :key="j" class="px-3 py-1.5 text-end tnum" :class="v < 0 ? 'text-sale' : ''">{{ money(v) }}</td>
                <td class="px-4 py-1.5 text-end tnum">{{ money(dm.gross_total) }}</td>
              </tr>
            </template>
            <tr class="border-t-2 border-ink font-extrabold" style="background:#faf6f4">
              <td class="px-4 py-2 sticky start-0" style="background:#faf6f4">{{ L("Net profit","صافي الربح","Résultat net") }}</td>
              <td v-for="(v, j) in dm.net_monthly" :key="j" class="px-3 py-2 text-end tnum" :class="v < 0 ? 'text-sale' : 'text-success-dark'">{{ money(v) }}</td>
              <td class="px-4 py-2 text-end tnum">{{ money(dm.net_total) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="py-16 text-center text-ink-muted text-[12px]">{{ L("No data for this year.","لا بيانات لهذه السنة.","Aucune donnée.") }}</div>
    </div>
  </div>
</template>

<script setup>
import { fmtAmount } from "@/utils/helpers";
import { ref, computed, onMounted, watch, h } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";
import { usePersistedRef } from "@/composables/usePersistedRef";

const { locale } = useI18n();
const router = useRouter();
const { entityId } = useUi();
function drill(account) { if (account) router.push({ path: "/accounting/accountant/gl", query: { account } }); }
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US");
const money = (n) => fmtAmount(n);

const TABS = [
  { key: "pnl", label: () => L("P&L", "أ.خ", "Résultat") },
  { key: "bs", label: () => L("Balance sheet", "الميزانية", "Bilan") },
  { key: "cf", label: () => L("Cash flow", "التدفّق النقدي", "Trésorerie") },
  { key: "monthly", label: () => L("By month", "بالشهر", "Par mois") },
];
const tab = usePersistedRef("ap_stmt_tab", "pnl");
watch(tab, (t) => { if (t === "monthly" && !dm.value.months) loadMonthly(); });

const y = new Date().getFullYear();
const pad = (n) => String(n).padStart(2, "0");
const iso = (dt) => `${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())}`;
const PRESETS = [
  { key: "ytd", label: () => L("YTD", "السنة", "Cumul") },
  { key: "quarter", label: () => L("Quarter", "الربع", "Trim.") },
  { key: "month", label: () => L("Month", "الشهر", "Mois") },
  { key: "lastyear", label: () => L("Last year", "السنة الماضية", "An passé") },
];
const preset = usePersistedRef("ap_stmt_preset", "ytd");
function range() {
  const now = new Date(), m = now.getMonth();
  if (preset.value === "month") return { from: iso(new Date(y, m, 1)), to: iso(now) };
  if (preset.value === "quarter") return { from: iso(new Date(y, Math.floor(m / 3) * 3, 1)), to: iso(now) };
  if (preset.value === "lastyear") return { from: `${y - 1}-01-01`, to: `${y - 1}-12-31` };
  return { from: `${y}-01-01`, to: iso(now) };
}

const d = ref({ pnl: { revenue: [], cogs: {}, opex: [], anomaly: null }, balance_sheet: { assets: [], liabilities: [], equity: [] }, cash_flow: {} });
const live = ref(null);
const loading = ref(true);
const compare = usePersistedRef("ap_stmt_compare", 1);
async function load() {
  loading.value = true;
  const r = range();
  try { d.value = await api.call("accounting_portal.api.reports.financial_statements", { company: currentCompany(), from_date: r.from, to_date: r.to, compare: compare.value }); live.value = true; }
  catch { live.value = false; }
  finally { loading.value = false; }
}
function setPreset(k) { preset.value = k; load(); }
onMounted(() => { load(); if (tab.value === "monthly") loadMonthly(); });
watch(entityId, () => { load(); dm.value = {}; if (tab.value === "monthly") loadMonthly(); });

// ── By-month P&L ──
const dm = ref({});
const mLoading = ref(false);
const mYear = ref(y);
const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MON_AR = ["ينا", "فبر", "مار", "أبر", "ماي", "يون", "يول", "أغس", "سبت", "أكت", "نوف", "ديس"];
const monLabel = (ym) => { const m = +String(ym).slice(5, 7) - 1; return (locale.value === "ar" ? MON_AR : MON)[m] || ym; };
async function loadMonthly() {
  mLoading.value = true;
  try { dm.value = await api.call("accounting_portal.api.reports.pnl_monthly", { company: currentCompany(), year: mYear.value }); }
  catch { dm.value = { months: [], sections: [] }; }
  finally { mLoading.value = false; }
}
function setYear(yr) { mYear.value = yr; loadMonthly(); }
const mSection = (k) => (dm.value.sections || []).find((s) => s.key === k) || { accounts: [], monthly_total: [], total: 0 };
const secLabel = (k) => ({ revenue: L("Revenue", "الإيرادات", "Produits"), cogs: L("Cost of goods sold", "تكلفة المبيعات", "CMV"), opex: L("Operating expenses", "المصروفات التشغيلية", "Charges") }[k] || k);
function mCsv() {
  const mo = dm.value.months || [];
  const head = ["Section", "Account", ...mo.map(monLabel), "Total"];
  const lines = [head.join(",")];
  const push = (sec, name, arr, tot) => lines.push([sec, `"${String(name).replace(/"/g, '""')}"`, ...arr, tot].join(","));
  ["revenue", "cogs", "opex"].forEach((k) => { const s = mSection(k); s.accounts.forEach((a) => push(s.label, a.name, a.monthly, a.total)); push(s.label, "Total " + s.label, s.monthly_total, s.total); });
  push("", "Gross profit", dm.value.gross_monthly || [], dm.value.gross_total);
  push("", "Net profit", dm.value.net_monthly || [], dm.value.net_total);
  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = `pnl-by-month-${mYear.value}.csv`; a.click(); URL.revokeObjectURL(a.href);
}

const pnlSections = computed(() => {
  const p = d.value.pnl || {};
  const secs = [];
  (p.revenue || []).forEach((s) => secs.push({ key: "rev", title: L("Revenue", "الإيرادات", "Produits"), accounts: s.accounts }));
  secs.push({ key: "revtot", title: "", accounts: [], subtotal: p.revenue_total, subtotalPrior: p.revenue_prior, subtotalLabel: L("Total revenue", "إجمالي الإيراد", "Total produits") });
  if (p.cogs && p.cogs.accounts) { secs.push({ key: "cogs", title: L("Cost of goods sold", "تكلفة المبيعات", "CMV"), accounts: p.cogs.accounts }); secs.push({ key: "gp", title: "", accounts: [], subtotal: p.gross_profit, subtotalPrior: p.gross_prior, subtotalLabel: L("Gross profit", "الربح الإجمالي", "Marge brute") }); }
  (p.opex || []).forEach((s) => secs.push({ key: "opex" + s.section, title: s.section, accounts: s.accounts }));
  secs.push({ key: "opextot", title: "", accounts: [], subtotal: p.opex_total, subtotalPrior: p.opex_prior, subtotalLabel: L("Total operating expenses", "إجمالي المصروفات", "Total charges") });
  return secs;
});

function delta(cur, prior) {
  const dv = (Number(cur) || 0) - (Number(prior) || 0);
  if (!prior) return { t: "—", c: "text-ink-muted" };
  const pct = Math.round(dv / Math.abs(prior) * 100);
  return { t: (dv >= 0 ? "+" : "") + pct + "%", c: dv >= 0 ? "text-success-dark" : "text-sale" };
}
function printIt() { window.print(); }

const BsBlock = {
  props: ["title", "sections", "total", "compare", "onDrill"],
  setup(p) {
    return () => [
      h("tr", { style: "background:#fcfcfb", class: "border-t border-line-hair" }, [h("td", { class: "px-5 py-1.5 font-bold text-[11px] uppercase tracking-wide text-ink-3", colspan: p.compare ? 4 : 2 }, p.title)]),
      ...(p.sections || []).flatMap((s) => [
        h("tr", { class: "border-t border-line-hair", style: "background:#fff" }, [h("td", { class: "px-5 py-1 ps-7 font-semibold text-ink-2 text-[11.5px]", colspan: p.compare ? 4 : 2 }, s.section)]),
        ...(s.accounts || []).map((a) => h("tr", { class: "border-t border-line-hair hover:bg-app-warm/40" + (a.account ? " cursor-pointer" : ""), onClick: () => a.account && p.onDrill && p.onDrill(a.account) }, [
          h("td", { class: "px-5 py-1 ps-10 text-ink-3 truncate hover:text-accent-dark", style: "max-width:280px" }, a.name),
          h("td", { class: "px-5 py-1 text-end tnum" }, fmt(a.amount)),
          ...(p.compare ? [h("td", { class: "px-5 py-1 text-end tnum text-ink-muted" }, fmt(a.prior)), h("td", { class: "px-5 py-1 text-end tnum" })] : []),
        ])),
        h("tr", { class: "border-t border-line-hair font-semibold", style: "background:#fafaf9" }, [
          h("td", { class: "px-5 py-1 ps-7 text-[11.5px]" }, s.section + " " + L("subtotal", "إجمالي", "s/total")),
          h("td", { class: "px-5 py-1 text-end tnum" }, fmt(s.total)),
          ...(p.compare ? [h("td", { class: "px-5 py-1 text-end tnum text-ink-muted" }, fmt(s.prior)), h("td")] : []),
        ]),
      ]),
      h("tr", { class: "border-t-2 border-line-2 font-extrabold", style: "background:#faf6f4" }, [
        h("td", { class: "px-5 py-2" }, L("Total", "إجمالي", "Total") + " " + p.title),
        h("td", { class: "px-5 py-2 text-end tnum" }, fmt(p.total)),
        ...(p.compare ? [h("td"), h("td")] : []),
      ]),
    ];
  },
};
</script>

<style>
@media print {
  body * { visibility: hidden !important; }
  .print-statement, .print-statement * { visibility: visible !important; }
  .print-statement { position: absolute; left: 0; top: 0; width: 100%; }
  .no-print { display: none !important; }
}
</style>
