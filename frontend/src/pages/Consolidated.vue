<template>
  <div class="space-y-3.5">
    <!-- Group digest banner -->
    <div class="rounded-card p-5 text-white" style="background:linear-gradient(115deg,#1e1b3a,#3b2566 55%,#6d28d9)">
      <div class="flex items-center gap-2 mb-2.5 flex-wrap">
        <Icon name="layers" :size="17" color="#e9d5ff" />
        <span class="text-[13px] font-bold">{{ L("Consolidated · Justyol Holding", "موحَّد · Justyol Holding", "Consolidé · Justyol Holding") }}</span>
        <span class="inline-flex items-center gap-1.5 text-[11px] font-semibold bg-white/15 px-2.5 py-1 rounded-full ms-1">{{ d.base || "USD" }}</span>
        <span v-if="isLive !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full" :style="isLive ? 'background:rgba(52,211,153,.22);color:#a7f3d0' : 'background:rgba(251,191,36,.22);color:#fde68a'">{{ isLive ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échant.") }}</span>
      </div>
      <p class="text-[13px] leading-relaxed text-violet-50/95 max-w-4xl">{{ digest }}</p>
    </div>

    <!-- Group KPI row -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
      <div v-for="k in kpis" :key="k.label" class="yo-card bg-white rounded-card border border-line p-4">
        <div class="flex items-start justify-between mb-3"><span class="w-8 h-8 rounded-[9px] grid place-items-center" :style="{ background: k.ibg }"><Icon :name="k.icon" :size="15" :color="k.ic" /></span></div>
        <div class="text-[22px] font-bold tracking-tight tnum" :style="k.color ? { color: k.color } : {}">{{ k.value }}</div>
        <div class="text-[11.5px] text-ink-3 mt-0.5">{{ k.label }}</div>
        <div class="text-[10.5px] text-ink-muted mt-1.5">{{ k.sub }}</div>
      </div>
    </div>

    <!-- Inventory distortion note -->
    <div v-if="distorted" class="rounded-[12px] border border-amber-200 bg-amber-50 px-4 py-2.5 flex items-center gap-2.5">
      <Icon name="alert" :size="15" color="#b45309" />
      <span class="text-[11.5px] text-ink-2 flex-1">{{ L("Group net is inflated by Justyol Morocco's unrelieved inventory (the 685M stock / COGS break). Consolidated figures inherit that distortion until it's corrected.","صافي المجموعة متضخّم بسبب مخزون مغرب غير المُرحَّل لتكلفة المبيعات.","Le résultat groupe est gonflé par le stock non soldé du Maroc.") }}</span>
      <button class="text-[11px] font-bold text-amber-700 hover:underline whitespace-nowrap" @click="goAuditor">{{ L("Open auditor","افتح المدقّق","Auditeur") }} →</button>
    </div>

    <!-- Per-entity contribution -->
    <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
      <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><Icon name="layers" :size="14" color="#7c3aed" /><span class="text-[12px] font-bold">{{ L("Per-entity contribution","مساهمة كل كيان","Contribution par entité") }}</span><span class="text-[10px] text-ink-muted">{{ L("translated to","محوَّل إلى","converti en") }} {{ d.base }}</span></div>
      <div class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead><tr style="background:#fafaf9">
            <th class="px-4 py-2 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Entity","الكيان","Entité") }}</th>
            <th class="px-4 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("FX","سعر","Taux") }}</th>
            <th class="px-4 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Net (FY)","الصافي","Résultat") }}</th>
            <th class="px-4 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Assets","الأصول","Actifs") }}</th>
            <th class="px-4 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Cash","النقد","Trésorerie") }}</th>
          </tr></thead>
          <tbody>
            <tr v-for="(e, i) in d.rows" :key="i" class="border-t border-line-hair hover:bg-app-warm/50 cursor-pointer" @click="goEntity(e.company)">
              <td class="px-4 py-2.5"><span class="flex items-center gap-2"><span class="w-7 h-7 rounded-[8px] grid place-items-center text-white text-[9.5px] font-bold" :style="{ background: badge(e.company) }">{{ e.abbr || e.company.slice(0,2) }}</span><span><span class="block font-semibold">{{ e.company }}</span><span class="block text-[10px] text-ink-muted">{{ e.currency }}</span></span></span></td>
              <td class="px-4 py-2.5 text-end tnum text-ink-3">{{ e.currency === d.base ? "—" : e.rate }}</td>
              <td class="px-4 py-2.5 text-end tnum font-semibold" :class="e.base.net < 0 ? 'text-sale' : ''">{{ money(e.base.net) }}</td>
              <td class="px-4 py-2.5 text-end tnum">{{ money(e.base.assets) }}</td>
              <td class="px-4 py-2.5 text-end tnum" :class="e.base.cash < 0 ? 'text-sale' : ''">{{ money(e.base.cash) }}</td>
            </tr>
          </tbody>
          <tfoot>
            <tr class="border-t-2 border-line-2 font-bold" style="background:#fafaf9">
              <td class="px-4 py-2.5">{{ L("Group","المجموعة","Groupe") }}</td>
              <td class="px-4 py-2.5"></td>
              <td class="px-4 py-2.5 text-end tnum">{{ money(d.totals.net) }}</td>
              <td class="px-4 py-2.5 text-end tnum">{{ money(d.totals.assets) }}</td>
              <td class="px-4 py-2.5 text-end tnum">{{ money(d.totals.cash) }}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>

    <!-- Group assets share -->
    <div class="bg-white rounded-card border border-line p-4 shadow-card">
      <div class="text-[13px] font-bold">{{ L("Group assets by entity","أصول المجموعة حسب الكيان","Actifs du groupe par entité") }}</div>
      <div class="text-[11px] text-ink-muted mb-3">{{ d.base }} {{ L("base · total","أساس · الإجمالي","base · total") }} {{ money(d.totals.assets) }}</div>
      <div class="flex h-3 rounded-full overflow-hidden bg-app-warm">
        <div v-for="(e, i) in d.rows" :key="i" class="h-full" :style="{ width: share(e) + '%', background: badge(e.company) }" :title="`${e.company} · ${money(e.base.assets)}`"></div>
      </div>
      <div class="flex flex-wrap gap-x-5 gap-y-1 mt-3">
        <div v-for="(e, i) in d.rows" :key="i" class="flex items-center gap-1.5 text-[11px]">
          <span class="w-2.5 h-2.5 rounded-sm" :style="{ background: badge(e.company) }"></span>
          <span class="font-medium">{{ e.company }}</span><span class="text-ink-muted tnum">{{ money(e.base.assets) }} · {{ Math.round(share(e)) }}%</span>
        </div>
      </div>
      <div v-if="d.rate_warnings && d.rate_warnings.length" class="text-[10.5px] text-amber-700 mt-2">{{ L("No FX rate for","لا سعر صرف لـ","Pas de taux pour") }}: {{ d.rate_warnings.join(", ") }} — {{ L("translated at 1.0","محوَّل بسعر 1.0","converti à 1,0") }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import api from "@/services/api";

const { locale } = useI18n();
const router = useRouter();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const money = (n) => { n = Number(n) || 0; const a = Math.abs(n); return (n < 0 ? "−" : "") + (a >= 1e6 ? (a / 1e6).toFixed(2) + "M" : a >= 1e3 ? Math.round(a / 1e3) + "K" : Math.round(a).toLocaleString()); };

const SAMPLE = { base: "USD", rows: [{ company: "Justyol Morocco", abbr: "JM", currency: "MAD", rate: 0.105, base: { net: 70695385, assets: 72183437, cash: 71073 } }], totals: { income: 2580000, net: 70536553, assets: 73035766, cash: 232584 }, rate_warnings: [] };
const d = ref({ rows: [], totals: {} });
const isLive = ref(null);
async function load() {
  try { d.value = await api.call("accounting_portal.api.consolidation.consolidated_financials", { base: "USD" }); isLive.value = true; }
  catch { d.value = SAMPLE; isLive.value = false; }
}
onMounted(load);

const distorted = computed(() => (d.value.totals?.assets || 0) > 50000000);
const digest = computed(() => {
  const t = d.value.totals || {};
  return L(
    `${d.value.entities || d.value.rows?.length || 0} entities consolidated to ${d.value.base || "USD"}. Group assets ${money(t.assets)}, net ${money(t.net)} (FY), cash on hand ${money(t.cash)}. Morocco is the operating engine; Türkiye/China source; Holding holds the cap table.`,
    `${d.value.entities || 0} كيانات موحّدة إلى ${d.value.base || "USD"}. أصول المجموعة ${money(t.assets)}، الصافي ${money(t.net)}، النقد ${money(t.cash)}.`,
    `${d.value.entities || 0} entités consolidées en ${d.value.base || "USD"}. Actifs ${money(t.assets)}, résultat ${money(t.net)}.`);
});
const kpis = computed(() => {
  const t = d.value.totals || {};
  return [
    { label: L("Group revenue (FY)", "إيراد المجموعة", "Produits groupe"), value: money(t.income), sub: d.value.base, icon: "trend", ibg: "#ecfdf5", ic: "#047857" },
    { label: L("Group net (FY)", "صافي المجموعة", "Résultat groupe"), value: money(t.net), sub: L("distorted by stock", "متأثر بالمخزون", "faussé par le stock"), icon: "scale", ibg: "#faf5ff", ic: "#7c3aed", color: t.net < 0 ? "#be123c" : undefined },
    { label: L("Group assets", "أصول المجموعة", "Actifs groupe"), value: money(t.assets), sub: d.value.base, icon: "bank", ibg: "#eff6ff", ic: "#0369a1" },
    { label: L("Cash on hand", "النقد", "Trésorerie"), value: money(t.cash), sub: L("all entities", "كل الكيانات", "toutes entités"), icon: "coins", ibg: "#fff7ed", ic: "#c2410c", color: (t.cash || 0) < 0 ? "#be123c" : undefined },
  ];
});

const PALETTE = ["#7c3aed", "#0369a1", "#047857", "#b45309", "#be123c"];
function badge(co) { let h = 0; for (const c of String(co)) h = (h * 31 + c.charCodeAt(0)) % PALETTE.length; return PALETTE[h]; }
function share(e) { const tot = d.value.rows.reduce((s, r) => s + Math.abs(r.base.assets), 0) || 1; return Math.abs(e.base.assets) / tot * 100; }
function goAuditor() { router.push("/accounting/copilot"); }
function goEntity() { router.push("/accounting/reports/pl"); }
</script>
