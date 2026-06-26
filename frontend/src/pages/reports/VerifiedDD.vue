<template>
  <div class="space-y-3.5">
    <div class="flex items-center gap-2 flex-wrap">
      <span class="text-[13px] font-bold">{{ L("Verified due diligence","العناية الواجبة المُتحقَّقة","Due diligence vérifiée") }}</span>
      <span v-if="isLive !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="isLive ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ isLive ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échant.") }}</span>
      <span class="text-[11px] text-ink-muted">{{ L("every figure tied to the GL — investor / audit ready","كل رقم مطابق للأستاذ — جاهز للمستثمر/التدقيق","chaque chiffre lié au GL") }}</span>
      <span class="ms-auto inline-flex items-center gap-1.5 text-[11.5px] font-bold px-2.5 py-1 rounded-full" :style="scoreStyle"><Icon name="shield" :size="13" :color="scoreFg" />{{ d.score }}/{{ d.total }} {{ L("checks pass","فحص ناجح","contrôles OK") }}</span>
    </div>

    <!-- Verified metric cards -->
    <div class="grid grid-cols-2 lg:grid-cols-5 gap-3">
      <div v-for="m in metricCards" :key="m.label" class="bg-white border border-line rounded-[14px] p-4 shadow-card">
        <div class="flex items-center justify-between"><span class="text-[10.5px] font-semibold text-ink-3">{{ m.label }}</span><span class="inline-flex items-center gap-1 text-[8.5px] font-bold px-1.5 py-0.5 rounded-full" style="background:#ecfdf5;color:#047857"><Icon name="check" :size="9" />GL</span></div>
        <div class="text-[19px] font-bold tnum mt-1.5" :style="m.color ? { color: m.color } : {}">{{ m.value }}</div>
      </div>
    </div>

    <!-- DD checklist -->
    <div class="bg-white border border-line rounded-card shadow-card overflow-hidden">
      <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2"><Icon name="shield" :size="14" color="#7c3aed" /><span class="text-[13px] font-bold">{{ L("Diligence checklist","قائمة العناية الواجبة","Checklist DD") }}</span></div>
      <div class="flex flex-col">
        <div v-for="(c, i) in d.checklist" :key="i" class="flex items-center gap-3 px-4 py-3 border-t border-line-hair">
          <span class="w-7 h-7 rounded-[8px] grid place-items-center flex-shrink-0" :style="badgeBg(c.status)"><Icon :name="icon(c.status)" :size="14" :color="badgeFg(c.status)" /></span>
          <div class="flex-1 min-w-0">
            <div class="text-[12.5px] font-bold">{{ areaLabel(c.area) }}</div>
            <div class="text-[10.5px] text-ink-muted">{{ c.note }}</div>
          </div>
          <span class="text-[12px] font-bold tnum text-ink-2 whitespace-nowrap">{{ c.value }}</span>
          <span class="text-[9.5px] font-bold px-2 py-0.5 rounded-badge w-[52px] text-center" :style="badgeChip(c.status)">{{ statusLabel(c.status) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";

const { locale } = useI18n();
const { entityId } = useUi();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const money = (n) => { n = Number(n) || 0; const a = Math.abs(n); return (n < 0 ? "−" : "") + (a >= 1e6 ? (a / 1e6).toFixed(1) + "M" : a >= 1e3 ? Math.round(a / 1e3) + "K" : Math.round(a).toLocaleString()); };

const SAMPLE = { currency: "MAD", score: 1, total: 6, metrics: { revenue: 7810557, gross_margin: -44.7, cash: 675192, debtors: -2851136, exposure: 693526151 }, checklist: [
  { area: "Gross margin quality", status: "fail", value: "−44.7%", note: "COGS exceeds revenue — inventory/COGS posting is broken" },
  { area: "Receivables integrity", status: "fail", value: "−2,851,136 MAD", note: "Debtors carry a credit balance — collections unapplied" },
] };
const d = ref(SAMPLE);
const isLive = ref(null);
async function load() {
  try { d.value = await api.call("accounting_portal.api.reports.verified_dd", { company: currentCompany() }); isLive.value = true; }
  catch { d.value = SAMPLE; isLive.value = false; }
}
onMounted(load);
watch(entityId, load);

const metricCards = computed(() => {
  const m = d.value.metrics || {};
  return [
    { label: L("Revenue (FY)", "الإيراد", "Produits"), value: money(m.revenue) + " " + d.value.currency },
    { label: L("Gross margin", "هامش إجمالي", "Marge brute"), value: m.gross_margin + "%", color: m.gross_margin < 0 ? "#be123c" : "#047857" },
    { label: L("Cash", "النقد", "Trésorerie"), value: money(m.cash), color: m.cash < 0 ? "#be123c" : undefined },
    { label: L("Debtors", "المدينون", "Débiteurs"), value: money(m.debtors), color: m.debtors < 0 ? "#be123c" : undefined },
    { label: L("Risk exposure", "التعرّض", "Exposition"), value: money(m.exposure), color: "#b45309" },
  ];
});

const AREAS = {
  "Revenue recognition": ["Revenue recognition", "إثبات الإيراد", "Reconnaissance produits"],
  "Gross margin quality": ["Gross margin quality", "جودة الهامش", "Qualité de marge"],
  "Receivables integrity": ["Receivables integrity", "سلامة المدينين", "Intégrité créances"],
  "Liquidity": ["Liquidity", "السيولة", "Liquidité"],
  "Audit findings": ["Audit findings", "ملاحظات التدقيق", "Constats d'audit"],
  "Document compliance": ["Document compliance", "اكتمال المستندات", "Conformité documents"],
};
function areaLabel(a) { const x = AREAS[a]; return x ? L(x[0], x[1], x[2]) : a; }
const ST = {
  pass: { en: "Pass", ar: "ناجح", fr: "OK", bg: "#ecfdf5", fg: "#047857" },
  watch: { en: "Watch", ar: "مراقبة", fr: "Surv.", bg: "#fffbeb", fg: "#b45309" },
  fail: { en: "Fail", ar: "فشل", fr: "Échec", bg: "#fef2f2", fg: "#b91c1c" },
};
const statusLabel = (s) => { const x = ST[s] || ST.watch; return locale.value === "ar" ? x.ar : locale.value === "fr" ? x.fr : x.en; };
const icon = (s) => (s === "pass" ? "check" : s === "fail" ? "alert" : "clock");
const badgeBg = (s) => `background:${(ST[s] || ST.watch).bg}`;
const badgeFg = (s) => (ST[s] || ST.watch).fg;
const badgeChip = (s) => { const x = ST[s] || ST.watch; return `background:${x.bg};color:${x.fg}`; };
const scoreStyle = computed(() => { const r = (d.value.score || 0) / (d.value.total || 1); return r >= 0.7 ? "background:#ecfdf5;color:#047857" : r >= 0.4 ? "background:#fffbeb;color:#b45309" : "background:#fef2f2;color:#b91c1c"; });
const scoreFg = computed(() => { const r = (d.value.score || 0) / (d.value.total || 1); return r >= 0.7 ? "#047857" : r >= 0.4 ? "#b45309" : "#b91c1c"; });
</script>
