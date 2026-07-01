<template>
  <div class="space-y-3.5">
    <div class="flex items-center gap-2 flex-wrap">
      <span class="text-[13px] font-bold">{{ L("Cash forecast","توقّع النقد","Prévision de trésorerie") }}</span>
      <span v-if="isLive !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="isLive ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ isLive ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échant.") }}</span>
      <span class="text-[11px] text-ink-muted">{{ L("cash now + carrier COD coming in − cheques & bills going out","النقد الآن + تحصيل COD القادم − الشيكات والفواتير","trésorerie + COD entrant − chèques & factures") }}</span>
    </div>

    <!-- 7-day liquidity check -->
    <div class="rounded-card p-5 text-white" :style="d.liquidity_7d_ok ? 'background:linear-gradient(115deg,#064e3b,#047857 60%,#059669)' : 'background:linear-gradient(115deg,#7f1d1d,#b91c1c 60%,#dc2626)'">
      <div class="flex items-center gap-2 mb-1.5"><Icon :name="d.liquidity_7d_ok ? 'check' : 'alert'" :size="16" color="#fff" /><span class="text-[12.5px] font-bold">{{ L("7-day liquidity","سيولة 7 أيام","Liquidité 7 j") }}</span></div>
      <div class="text-[26px] font-extrabold tnum">{{ money(d.proj_7d) }} <span class="text-[13px] font-normal opacity-80">{{ d.currency }}</span></div>
      <p class="text-[12px] mt-1 opacity-90">{{ d.liquidity_7d_ok ? L("Cash covers the next 7 days of cheques and near-term bills.","النقد يغطّي الشيكات والفواتير القريبة.","La trésorerie couvre les 7 prochains jours.") : L("Projected short within 7 days — cheques and bills due exceed cash on hand and expected COD.","عجز متوقّع خلال 7 أيام — المستحقات تتجاوز النقد والتحصيل المتوقّع.","Déficit projeté sous 7 jours.") }}</p>
    </div>

    <!-- Components -->
    <div class="grid grid-cols-2 lg:grid-cols-3 gap-3">
      <div v-for="c in comps" :key="c.label" class="bg-white rounded-[13px] border px-4 py-3 shadow-card" :style="{ borderColor: c.bd || '#f0efed' }">
        <div class="flex items-center gap-1.5"><Icon :name="c.icon" :size="13" :color="c.ic" /><span class="text-[10.5px] text-ink-muted font-semibold uppercase tracking-wide">{{ c.label }}</span></div>
        <div class="text-[19px] font-bold tnum mt-1" :style="c.color ? { color: c.color } : {}">{{ c.sign }}{{ money(c.value) }}</div>
        <div class="text-[10px] text-ink-muted mt-0.5">{{ c.sub }}</div>
      </div>
    </div>

    <!-- Waterfall -->
    <div class="bg-white rounded-card border border-line p-5 shadow-card">
      <div class="text-[12.5px] font-bold mb-3">{{ L("30-day projection","توقّع 30 يوم","Projection 30 j") }}</div>
      <div class="space-y-2.5">
        <div v-for="w in waterfall" :key="w.label" class="flex items-center gap-3">
          <span class="text-[11.5px] w-32 flex-shrink-0" :class="w.bold ? 'font-bold' : 'text-ink-3'">{{ w.label }}</span>
          <div class="flex-1 h-6 bg-app-warm/40 rounded-[6px] relative overflow-hidden">
            <div class="h-full rounded-[6px]" :style="{ width: w.pct + '%', background: w.color, marginInlineStart: w.offset + '%' }"></div>
          </div>
          <span class="text-[12px] tnum font-semibold w-24 text-end flex-shrink-0" :class="w.value < 0 ? 'text-sale' : ''">{{ w.value < 0 ? '−' : (w.delta ? '+' : '') }}{{ money(Math.abs(w.value)) }}</span>
        </div>
      </div>
      <div class="flex items-center justify-between mt-4 pt-3 border-t border-line-hair">
        <span class="text-[12.5px] font-bold">{{ L("Projected cash in 30 days","النقد المتوقّع خلال 30 يوم","Trésorerie projetée à 30 j") }}</span>
        <span class="text-[20px] font-extrabold tnum" :class="d.proj_30d < 0 ? 'text-sale' : 'text-success-dark'">{{ money(d.proj_30d) }} <span class="text-[11px] text-ink-muted font-normal">{{ d.currency }}</span></span>
      </div>
    </div>

    <p class="text-[10.5px] text-ink-muted">{{ L("Carrier float is delivered COD still with the carrier (expected to land). 7-day view assumes ~40% of float collects and half of bills fall due. Modeled timing — actuals vary.","رصيد الناقل هو COD المسلَّم لدى الناقل (متوقّع وصوله). توقيت تقديري.","Le flottant transporteur = COD livré chez le transporteur. Calendrier estimé.") }}</p>
  </div>
</template>

<script setup>
import { fmtAmount } from "@/utils/helpers";
import { ref, computed, onMounted, watch } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";

const { locale } = useI18n();
const { entityId } = useUi();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const money = (n) => fmtAmount(n);

const SAMPLE = { currency: "MAD", cash: 675192, carrier_float: 5720000, runrate_30d: 1009125, cheques_7d: 341792, cheques_out: 3407000, bills_due: 7302975, proj_7d: -2700000, proj_30d: -4710000, liquidity_7d_ok: false };
const d = ref(SAMPLE);
const isLive = ref(null);
async function load() {
  try { d.value = await api.call("accounting_portal.api.reports.cash_forecast", { company: currentCompany() }); isLive.value = true; }
  catch { d.value = SAMPLE; isLive.value = false; }
}
onMounted(load);
watch(entityId, load);

const comps = computed(() => [
  { label: L("Cash now", "النقد الآن", "Trésorerie"), value: d.value.cash, sign: "", icon: "bank", ic: "#0369a1", sub: L("bank + cash", "بنك + نقد", "banque + caisse"), color: d.value.cash < 0 ? "#be123c" : undefined, bd: d.value.cash < 0 ? "#fecaca" : undefined },
  { label: L("Carrier float (in)", "رصيد الناقل", "Flottant (entrée)"), value: d.value.carrier_float, sign: "+", icon: "truck", ic: "#047857", sub: L("delivered COD coming", "COD مُسلَّم قادم", "COD livré à venir"), color: "#047857" },
  { label: L("Collections / 30d", "تحصيلات/30ي", "Encaiss./30j"), value: d.value.runrate_30d, sign: "", icon: "coins", ic: "#7c3aed", sub: L("recent run-rate", "المعدّل الأخير", "rythme récent") },
  { label: L("Cheques due", "شيكات مستحقة", "Chèques dus"), value: d.value.cheques_out, sign: "−", icon: "doc", ic: "#b45309", sub: L("uncleared", "غير مُحصّلة", "non compensés"), color: "#b45309", bd: "#fde68a" },
  { label: L("Bills due", "فواتير مستحقة", "Factures dues"), value: d.value.bills_due, sign: "−", icon: "cart", ic: "#be123c", sub: L("payable now/overdue", "مستحق/متأخّر", "dû/en retard"), color: "#be123c", bd: "#fecaca" },
  { label: L("Cheques ≤7d", "شيكات ≤7ي", "Chèques ≤7j"), value: d.value.cheques_7d, sign: "−", icon: "clock", ic: "#c2410c", sub: L("clearing this week", "تُحصّل هذا الأسبوع", "cette semaine") },
]);

const waterfall = computed(() => {
  const max = Math.max(Math.abs(d.value.cash), d.value.carrier_float, d.value.cheques_out, d.value.bills_due, 1);
  const bar = (v, color, label, delta = false, bold = false) => ({ label, value: v, color, pct: Math.min(100, Math.abs(v) / max * 100), offset: 0, delta, bold });
  return [
    bar(d.value.cash, "#0369a1", L("Cash now", "النقد الآن", "Trésorerie"), false, true),
    bar(d.value.carrier_float, "#34d399", L("+ Carrier float", "+ رصيد الناقل", "+ Flottant"), true),
    bar(-d.value.cheques_out, "#f59e0b", L("− Cheques", "− شيكات", "− Chèques")),
    bar(-d.value.bills_due, "#f87171", L("− Bills due", "− فواتير", "− Factures")),
  ];
});
</script>
