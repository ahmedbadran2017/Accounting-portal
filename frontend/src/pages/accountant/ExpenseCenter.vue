<template>
  <div class="space-y-3.5">
    <div class="flex gap-1 bg-white border border-line rounded-chip p-1 w-fit shadow-card">
      <button v-for="v in VIEWS" :key="v.k" class="px-3.5 py-1.5 rounded-lg text-[12px] font-semibold whitespace-nowrap inline-flex items-center gap-1.5" :class="view === v.k ? 'bg-app-warm text-accent-dark shadow-card' : 'text-ink-3 hover:text-ink'" @click="view = v.k">
        <Icon :name="v.icon" :size="13" />{{ v.label() }}<span v-if="v.k==='recurring' && dueBadge" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-rose-100 text-rose-700">{{ dueBadge }}</span>
      </button>
    </div>

    <RecurringExpenses v-if="view === 'recurring'" @counts="onCounts" />
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
          <div class="text-[22px] font-extrabold mt-1 tnum" style="color:#0f766e">{{ money(g.cost_of_sales) }} <span class="text-[12px] text-ink-muted font-bold">{{ ccy }}</span></div>
          <div class="text-[10.5px] text-ink-muted mt-0.5">{{ L("COGS + freight & logistics","تكلفة البضاعة + الشحن","CMV + fret") }}</div>
        </div>
        <div class="bg-white rounded-card border border-line shadow-card px-4 py-3.5">
          <div class="text-[10px] font-bold uppercase tracking-wider text-ink-muted flex items-center gap-1.5"><Icon name="building" :size="13" color="#7c3aed" />{{ L("Operating expenses","المصروفات التشغيلية","Charges d'exploitation") }}</div>
          <div class="text-[22px] font-extrabold mt-1 tnum" style="color:#7c3aed">{{ money(g.opex) }} <span class="text-[12px] text-ink-muted font-bold">{{ ccy }}</span></div>
          <div class="text-[10.5px] text-ink-muted mt-0.5">{{ L("payroll · rent · marketing · taxes…","رواتب · إيجار · تسويق · ضرائب…","paie · loyer · marketing…") }}</div>
        </div>
        <div class="bg-white rounded-card border border-line shadow-card px-4 py-3.5">
          <div class="text-[10px] font-bold uppercase tracking-wider text-ink-muted flex items-center gap-1.5"><Icon name="wallet" :size="13" color="#0369a1" />{{ L("Total expense","إجمالي المصروف","Total") }}</div>
          <div class="text-[22px] font-extrabold mt-1 tnum">{{ money(data.total) }} <span class="text-[12px] text-ink-muted font-bold">{{ ccy }}</span></div>
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
            <span class="tnum font-bold text-[13px] w-24 text-end shrink-0">{{ money(c.amount) }}</span>
            <Icon name="arrow" :size="12" color="#cbd5e1" class="shrink-0 transition-transform" :class="open[c.cat] ? 'rotate-90' : ''" />
          </button>
          <div v-if="open[c.cat]" class="bg-app-warm/30 px-4 py-1">
            <div v-for="a in (data.by_account[c.cat]||[])" :key="a.num" class="flex items-center gap-2 py-1.5 text-[11.5px] border-b border-line-hair/60 last:border-b-0">
              <span class="font-mono text-[10px] text-ink-muted w-24 shrink-0">{{ a.num || "—" }}</span>
              <span class="flex-1 truncate text-ink-2">{{ a.name }}</span>
              <span class="tnum font-semibold" :class="a.amount < 0 ? 'text-rose-500' : ''">{{ money(a.amount) }}</span>
            </div>
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
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import DateFilterBar from "@/components/DateFilterBar.vue";
import RecurringExpenses from "@/pages/accountant/RecurringExpenses.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";
import { useDateFilter } from "@/composables/useDateFilter";

const { locale } = useI18n();
const { entityId } = useUi();
const view = ref("breakdown");
const dueBadge = ref(0);
const VIEWS = [
  { k: "breakdown", icon: "list", label: () => L("Breakdown", "التفصيل", "Répartition") },
  { k: "recurring", icon: "clock", label: () => L("Recurring & due", "المتكرّر والمستحق", "Récurrent") },
];
const onCounts = (c) => { dueBadge.value = (c.due || 0) + (c.overdue || 0); };
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const money = (n) => { n = Number(n) || 0; const a = Math.abs(n); return (n < 0 ? "−" : "") + (a >= 1e6 ? (a / 1e6).toFixed(2) + "M" : a >= 1e3 ? Math.round(a / 1e3) + "K" : Math.round(a).toLocaleString()); };

const CAT_AR = { "COGS": "تكلفة البضاعة", "Freight & Logistics": "الشحن واللوجيستيك", "Payroll": "الرواتب", "Marketing": "التسويق", "Rent, Office & Utilities": "الإيجار والمكتب", "Taxes": "الضرائب", "Financial": "مصاريف مالية", "Other": "أخرى" };
const CAT_FR = { "COGS": "CMV", "Freight & Logistics": "Fret & logistique", "Payroll": "Paie", "Marketing": "Marketing", "Rent, Office & Utilities": "Loyer & bureau", "Taxes": "Taxes", "Financial": "Frais financiers", "Other": "Autres" };
const catLabel = (c) => (locale.value === "ar" ? (CAT_AR[c] || c) : locale.value === "fr" ? (CAT_FR[c] || c) : c);

const data = ref({});
const loading = ref(true);
const err = ref(false);
const open = reactive({});
const ccy = computed(() => data.value.currency || "MAD");
const g = computed(() => data.value.groups || {});

const df = useDateFilter("expcenter", () => load(), "year");

async function load() {
  loading.value = true; err.value = false;
  try { data.value = await api.call("accounting_portal.api.expenses.expense_cockpit", { company: currentCompany(), ...df.filterValue() }) || {}; }
  catch { data.value = {}; err.value = true; }
  finally { loading.value = false; }
}
load();
watch(entityId, load);

// fetch the due/overdue count once so the "Recurring" tab shows a reminder badge
// even before the user opens it.
async function loadBadge() {
  try { const r = await api.call("accounting_portal.api.recurring.recurring_overview", { company: currentCompany() }); dueBadge.value = (r?.due || 0) + (r?.overdue || 0); }
  catch { /* ignore */ }
}
loadBadge();
watch(entityId, loadBadge);

const maxCat = computed(() => Math.max(1, ...(data.value.categories || []).map((c) => Math.abs(c.amount))));
const bar = (v) => Math.max(2, Math.round(Math.abs(Number(v) || 0) / maxCat.value * 100));
const pct = (v) => { const t = (data.value.total || 0); return t ? Math.round(Math.abs(Number(v) || 0) / Math.abs(t) * 100) : 0; };
function toggle(c) { open[c] = !open[c]; }

const monthTotal = (mo) => (data.value.categories || []).reduce((s, c) => s + (Number(mo[c.cat]) || 0), 0);
const maxMonth = computed(() => Math.max(1, ...(data.value.months || []).map((mo) => (data.value.categories || []).reduce((s, c) => s + Math.max(0, Number(mo[c.cat]) || 0), 0))));
const segH = (v) => Math.max(0, Math.round(Math.max(0, Number(v) || 0) / maxMonth.value * 100));
const mLabel = (m) => { const p = String(m || "").split("-"); return p.length === 2 ? p[1] + "/" + p[0].slice(2) : m; };
</script>
