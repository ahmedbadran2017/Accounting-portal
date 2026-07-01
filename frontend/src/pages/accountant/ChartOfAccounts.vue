<template>
  <div class="space-y-3.5">
    <div class="flex gap-1 bg-white border border-line rounded-chip p-1 w-fit shadow-card">
      <button v-for="v in VIEWS" :key="v.k" class="px-3.5 py-1.5 rounded-lg text-[12px] font-semibold whitespace-nowrap inline-flex items-center gap-1.5" :class="coaView === v.k ? 'bg-app-warm text-accent-dark shadow-card' : 'text-ink-3 hover:text-ink'" @click="coaView = v.k">
        <Icon :name="v.icon" :size="13" />{{ v.label() }}
      </button>
    </div>

    <AccountCleanup v-if="coaView === 'cleanup'" />
    <template v-else>
    <!-- Toolbar -->
    <div class="flex items-center gap-2 flex-wrap">
      <span class="text-[13px] font-bold">{{ L("Chart of accounts","دليل الحسابات","Plan comptable") }}</span>
      <span v-if="isLive !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="isLive ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ isLive ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échant.") }}</span>
      <span class="hidden md:inline text-[11px] text-ink-muted">{{ L("live balances · click any account to open its ledger","أرصدة حيّة · اضغط أي حساب لفتح الأستاذ","soldes en direct") }}</span>
      <div class="ms-auto flex items-center gap-2">
        <button type="button" @click="onlyAnomalies = !onlyAnomalies" class="inline-flex items-center gap-1.5 h-9 px-3 rounded-[10px] border text-[12px] font-semibold transition" :class="onlyAnomalies ? 'bg-rose-50 border-rose-200 text-rose-700' : 'bg-white border-line-2 text-ink-2 hover:bg-app-warm/50'">
          <Icon name="alert" :size="13" :color="onlyAnomalies ? '#be123c' : '#9a8f86'" />
          {{ L("Anomalies","الشذوذ","Anomalies") }}
          <span v-if="anomalyCount" class="tnum text-[10px] font-bold px-1.5 py-0.5 rounded-full" :class="onlyAnomalies ? 'bg-rose-600 text-white' : 'bg-rose-100 text-rose-700'">{{ anomalyCount }}</span>
        </button>
        <div class="relative">
          <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
          <input v-model.trim="q" :placeholder="L('Search account…','بحث…','Rechercher…')" class="w-44 sm:w-60 h-9 bg-app-warm/40 border border-line-2 rounded-[10px] ps-9 pe-3 text-[12.5px] focus:outline-none focus:border-accent/40 focus:bg-white" />
        </div>
      </div>
    </div>

    <!-- Summary strip -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <div class="bg-white rounded-card border border-line shadow-card px-4 py-3">
        <div class="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-ink-muted"><Icon name="list" :size="12" color="#0b5c4f" />{{ L("Accounts","الحسابات","Comptes") }}</div>
        <div class="text-[22px] font-extrabold tnum mt-1 leading-none">{{ rows.length.toLocaleString() }}</div>
        <div class="text-[11px] text-ink-3 mt-1">{{ L("with live balances","لها أرصدة حيّة","avec soldes") }}</div>
      </div>
      <button type="button" @click="anomalyCount && (onlyAnomalies = !onlyAnomalies)" class="text-start bg-white rounded-card border shadow-card px-4 py-3 transition" :class="anomalyCount ? (onlyAnomalies ? 'border-rose-300 ring-1 ring-rose-300' : 'border-line hover:border-rose-200') : 'border-line'">
        <div class="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider" :class="anomalyCount ? 'text-rose-600' : 'text-ink-muted'"><Icon name="alert" :size="12" :color="anomalyCount ? '#be123c' : '#9a8f86'" />{{ L("Anomalies","شذوذ","Anomalies") }}</div>
        <div class="text-[22px] font-extrabold tnum mt-1 leading-none" :class="anomalyCount ? 'text-rose-600' : 'text-ink'">{{ anomalyCount }}</div>
        <div class="text-[11px] mt-1" :class="anomalyCount ? 'text-rose-500' : 'text-ink-3'">{{ anomalyCount ? L("click to filter","اضغط للفلترة","cliquer pour filtrer") : L("none flagged","لا شيء","aucune") }}</div>
      </button>
      <div class="bg-white rounded-card border border-line shadow-card px-4 py-3">
        <div class="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-ink-muted"><Icon name="wallet" :size="12" color="#0f766e" />{{ L("Total assets","إجمالي الأصول","Total actifs") }}</div>
        <div class="text-[22px] font-extrabold tnum mt-1 leading-none text-teal-700">{{ money(rootTotal('Asset')) }}</div>
        <div class="text-[11px] text-ink-3 mt-1">{{ ccy }}</div>
      </div>
      <div class="bg-white rounded-card border shadow-card px-4 py-3" :class="balanced ? 'border-line' : 'border-amber-200'">
        <div class="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-ink-muted"><Icon name="scale" :size="12" color="#7c3aed" />{{ L("Trial balance","ميزان المراجعة","Balance") }}</div>
        <div class="text-[15px] font-extrabold mt-1.5 leading-none flex items-center gap-1.5" :class="balanced ? 'text-teal-700' : 'text-amber-700'">
          <Icon :name="balanced ? 'check' : 'alert'" :size="15" :color="balanced ? '#0f766e' : '#b45309'" />
          {{ balanced ? L("Balanced","متزن","Équilibré") : money(Math.abs(grandTotal)) }}
        </div>
        <div class="text-[11px] mt-1.5" :class="balanced ? 'text-ink-3' : 'text-amber-600'">{{ balanced ? L("debits = credits","مدين = دائن","débit = crédit") : L("net imbalance","فرق غير متزن","écart net") }}</div>
      </div>
    </div>

    <!-- Accounts -->
    <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
      <TableLoading v-if="loading" :rows="12" />
      <template v-else>
        <div v-for="g in groups" :key="g.key" class="border-b border-line last:border-b-0">
          <!-- Group header (sticky, collapsible) -->
          <button type="button" @click="toggle(g.key)" class="sticky top-0 z-10 w-full flex items-center gap-2.5 px-4 py-2.5 bg-app-warm/90 backdrop-blur border-b border-line-hair text-start">
            <span class="w-1 h-4 rounded-full" :style="`background:${g.color}`"></span>
            <svg :class="collapsed[g.key] ? '-rotate-90' : ''" class="transition-transform shrink-0" width="11" height="11" viewBox="0 0 12 12" fill="none"><path d="M2.5 4.5L6 8l3.5-3.5" :stroke="g.color" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
            <Icon :name="g.icon" :size="14" :color="g.color" />
            <span class="text-[11.5px] font-bold uppercase tracking-wider" :style="`color:${g.color}`">{{ g.label }}</span>
            <span class="tnum text-[10px] font-bold text-ink-muted bg-white/70 border border-line-hair px-1.5 py-0.5 rounded-full">{{ g.rows.length }}</span>
            <span v-if="g.anomalies" class="tnum text-[10px] font-bold text-rose-600 bg-rose-50 border border-rose-200 px-1.5 py-0.5 rounded-full inline-flex items-center gap-1"><Icon name="alert" :size="9" color="#be123c" />{{ g.anomalies }}</span>
            <span class="ms-auto tnum text-[12.5px] font-extrabold" :class="g.anomalies ? 'text-ink' : 'text-ink-2'">{{ money(g.total) }} <span class="text-[10px] font-semibold text-ink-muted">{{ ccy }}</span></span>
          </button>

          <!-- Rows -->
          <div v-show="!collapsed[g.key]">
            <div v-for="(c, i) in g.rows" :key="i" @click="drill(c)"
                 class="group grid grid-cols-[auto_1fr_auto] items-center gap-3 px-4 py-2 border-t border-line-hair first:border-t-0 cursor-pointer transition"
                 :class="c.anomaly ? 'bg-rose-50/40 hover:bg-rose-50' : 'hover:bg-app-warm/60'">
              <span class="font-mono text-[11px] text-ink-3 bg-app-warm/70 rounded px-1.5 py-0.5 whitespace-nowrap tnum">{{ c.code || "—" }}</span>
              <div class="min-w-0 flex items-center gap-2">
                <span class="truncate text-[12.5px] group-hover:text-accent-dark" :class="c.anomaly ? 'font-semibold text-rose-900' : 'text-ink'">{{ c.name }}</span>
                <span v-if="c.account_type" class="hidden sm:inline shrink-0 text-[9.5px] font-semibold text-ink-muted bg-app-warm border border-line-hair px-1.5 py-0.5 rounded">{{ c.account_type }}</span>
                <span v-if="c.anomaly" class="shrink-0 inline-flex" :title="anomalyText(c)"><Icon name="alert" :size="12.5" color="#be123c" /></span>
              </div>
              <div class="flex flex-col items-end gap-1 w-[120px] sm:w-[150px]">
                <span class="tnum text-[12.5px] font-bold whitespace-nowrap" :class="c.anomaly ? 'text-rose-600' : 'text-ink'">{{ money(c.bal) }}</span>
                <span class="block h-[3px] rounded-full" :style="`width:${barW(c, g)}%;background:${c.anomaly ? '#f43f5e' : g.color};opacity:${c.anomaly ? 0.7 : 0.3}`"></span>
              </div>
            </div>
          </div>
        </div>

        <div v-if="!groups.length" class="px-4 py-14 text-center">
          <Icon :name="onlyAnomalies ? 'check' : 'search'" :size="24" :color="onlyAnomalies ? '#0f766e' : '#c4bdb5'" class="inline-block mb-2" />
          <p class="text-[12.5px] text-ink-muted">{{ onlyAnomalies ? L("No anomalies — every account has the expected balance sign.","لا شذوذ — كل الحسابات بإشارة الرصيد المتوقعة.","Aucune anomalie.") : (q ? L("No account matches your search.","لا حساب يطابق بحثك.","Aucun compte.") : L("No accounts.","لا حسابات.","Aucun compte.")) }}</p>
        </div>
      </template>
    </div>
    </template>
  </div>
</template>

<script setup>
import { fmtAmount } from "@/utils/helpers";
import { ref, reactive, computed, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import AccountCleanup from "@/pages/accountant/AccountCleanup.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";

const { locale } = useI18n();
const { entityId } = useUi();
const router = useRouter();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const coaView = ref("balances");
const VIEWS = [
  { k: "balances", icon: "scale", label: () => L("Balances", "الأرصدة", "Soldes") },
  { k: "cleanup", icon: "grid", label: () => L("Cleanup", "تنظيف", "Nettoyage") },
];
const money = (n) => fmtAmount(n);

const rows = ref([]);
const isLive = ref(null);
const loading = ref(true);
const q = ref("");
const ccy = ref("MAD");
const onlyAnomalies = ref(false);
const collapsed = reactive({});

async function load() {
  loading.value = true;
  try {
    rows.value = await api.call("accounting_portal.api.ledger.chart_of_accounts", { company: currentCompany() }) || [];
    isLive.value = true;
  } catch { rows.value = []; isLive.value = false; }
  finally { loading.value = false; }
}
onMounted(load);
watch(entityId, load);

const ROOTS = [
  { key: "Asset", icon: "wallet", color: "#0f766e", label: () => L("Assets", "الأصول", "Actifs") },
  { key: "Liability", icon: "scale", color: "#b45309", label: () => L("Liabilities", "الخصوم", "Passifs") },
  { key: "Equity", icon: "building", color: "#7c3aed", label: () => L("Equity", "حقوق الملكية", "Capitaux") },
  { key: "Income", icon: "coins", color: "#0369a1", label: () => L("Income", "الإيرادات", "Produits") },
  { key: "Expense", icon: "chart", color: "#be123c", label: () => L("Expenses", "المصروفات", "Charges") },
];

const anomalyCount = computed(() => rows.value.filter((r) => r.anomaly).length);
const grandTotal = computed(() => rows.value.reduce((s, r) => s + (Number(r.bal) || 0), 0));
const balanced = computed(() => Math.abs(grandTotal.value) < 1);
const rootTotal = (k) => rows.value.filter((r) => r.root_type === k).reduce((s, r) => s + (Number(r.bal) || 0), 0);

const groups = computed(() => {
  const needle = q.value.toLowerCase();
  let filtered = rows.value;
  if (onlyAnomalies.value) filtered = filtered.filter((r) => r.anomaly);
  if (needle) filtered = filtered.filter((r) => String(r.name).toLowerCase().includes(needle) || String(r.code || "").includes(needle));
  return ROOTS.map((g) => {
    const gr = filtered.filter((r) => r.root_type === g.key);
    const max = gr.reduce((m, r) => Math.max(m, Math.abs(Number(r.bal) || 0)), 0);
    return { key: g.key, icon: g.icon, color: g.color, label: g.label(), rows: gr, max,
      total: gr.reduce((s, r) => s + (Number(r.bal) || 0), 0),
      anomalies: gr.filter((r) => r.anomaly).length };
  }).filter((g) => g.rows.length);
});

const barW = (c, g) => { const v = Math.abs(Number(c.bal) || 0); return g.max ? Math.max(4, Math.round((v / g.max) * 100)) : 4; };

function toggle(k) { collapsed[k] = !collapsed[k]; }

function anomalyText(c) {
  const r = c.anomaly_reason;
  if (r === "oversized") return L("Balance exceeds 50M — likely a posting error.", "الرصيد يتجاوز 50 مليون — غالباً خطأ ترحيل.", "Solde > 50M — erreur probable.");
  if (r === "credit_balance") return L("Asset/expense account carrying a credit balance.", "حساب أصول/مصروفات برصيد دائن.", "Compte d’actif/charge avec solde créditeur.");
  if (r === "debit_balance") return L("Liability/income/equity account carrying a debit balance.", "حساب خصوم/إيرادات برصيد مدين.", "Compte de passif/produit avec solde débiteur.");
  return L("Unusual balance.", "رصيد غير معتاد.", "Solde inhabituel.");
}

function drill(c) {
  const acct = c.account || (c.code ? `${c.code} - ${c.name}` : c.name);
  router.push({ path: "/accounting/accountant/gl", query: { account: acct } });
}
</script>
