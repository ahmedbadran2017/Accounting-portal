<template>
  <div class="space-y-3.5">
    <div class="flex items-center gap-2">
      <span class="inline-flex items-center gap-1.5 text-[10.5px] font-bold uppercase tracking-wider px-2 py-1 rounded-chip"
            :class="live ? 'text-success-dark bg-success-soft' : 'text-amber-700 bg-amber-50'">
        <span class="w-1.5 h-1.5 rounded-full" :class="live ? 'bg-success' : 'bg-amber-500'"></span>{{ live ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échantillon") }}
      </span>
      <span class="text-[11px] text-ink-muted">{{ L("VAT declaration — monthly (DGI Morocco · déclaration le 20)","ض.ق.م — تصريح شهري (المديرية العامة للضرائب · حتى 20)","TVA — déclaration mensuelle (DGI)") }}</span>
    </div>

    <!-- Next declaration headline -->
    <button v-if="nextDue" @click="" class="w-full bg-white rounded-card border p-4 shadow-card text-start" :style="{ borderColor: nextStatus.c + '55' }">
      <div class="flex items-center gap-3 flex-wrap">
        <span class="w-10 h-10 rounded-[12px] grid place-items-center flex-shrink-0" :style="{ background: nextStatus.bg }"><Icon name="percent" :size="18" :color="nextStatus.c" /></span>
        <div class="flex-1 min-w-0">
          <div class="text-[11px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Next VAT declaration","التصريح القادم","Prochaine déclaration") }}</div>
          <div class="text-[14px] font-bold">{{ monthLabel(nextDue.month) }} · <span :style="{ color: nextStatus.c }">{{ nextStatus.label }}</span></div>
          <div class="text-[11px] text-ink-muted mt-0.5">{{ L("deadline","الموعد النهائي","échéance") }} {{ nextDue.deadline }}</div>
        </div>
        <div class="text-end">
          <div class="text-[22px] font-extrabold tnum" :style="{ color: nextDue.net >= 0 ? '#be123c' : '#047857' }">{{ money0(Math.abs(nextDue.net)) }}<span class="text-[11px] text-ink-muted ms-1">MAD</span></div>
          <div class="text-[10.5px] text-ink-muted">{{ nextDue.net >= 0 ? L("net payable","صافي مستحق","net à payer") : L("credit","رصيد دائن","crédit") }}</div>
        </div>
      </div>
    </button>

    <!-- Monthly tracker -->
    <div class="bg-white rounded-card border border-line overflow-hidden shadow-card">
      <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><Icon name="clock" :size="14" color="#0b5c4f" /><span class="text-[12px] font-bold">{{ L("Declaration tracker","متتبّع التصاريح","Suivi des déclarations") }}</span><span class="text-[10px] text-ink-muted">{{ periods.length }} {{ L("months","شهر","mois") }}</span></div>
      <div class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead><tr style="background:#fafaf9">
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Period","الفترة","Période") }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Output","المخرجات","Collectée") }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Input","المدخلات","Déductible") }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Net payable","الصافي المستحق","Net à payer") }}</th>
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Deadline","الموعد","Échéance") }}</th>
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Status","الحالة","Statut") }}</th>
          </tr></thead>
          <tbody>
            <tr v-for="p in periods" :key="p.month" class="border-t border-line-hair hover:bg-app-warm/60">
              <td class="px-4 py-2.5 font-semibold whitespace-nowrap">{{ monthLabel(p.month) }}</td>
              <td class="px-4 py-2.5 text-end tnum text-success-dark">{{ money0(p.output) }}</td>
              <td class="px-4 py-2.5 text-end tnum text-ink-3">{{ money0(p.input) }}</td>
              <td class="px-4 py-2.5 text-end tnum font-bold" :class="p.net >= 0 ? '' : 'text-success-dark'">{{ money0(Math.abs(p.net)) }}{{ p.net < 0 ? " CR" : "" }}</td>
              <td class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ p.deadline }}</td>
              <td class="px-4 py-2.5"><span class="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full" :style="{ background: stat(p).bg, color: stat(p).c }"><span class="w-1.5 h-1.5 rounded-full" :style="{ background: stat(p).c }"></span>{{ stat(p).label }}</span></td>
            </tr>
            <tr v-if="!periods.length"><td colspan="6" class="px-4 py-8 text-center text-ink-muted text-[12px]">{{ L("No VAT activity.","لا نشاط ضريبي.","Aucune activité TVA.") }}</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- FY by-account breakdown -->
    <div class="grid sm:grid-cols-2 gap-3.5">
      <div class="bg-white rounded-card border border-line overflow-hidden shadow-card">
        <div class="px-4 py-3 border-b border-line text-[13px] font-bold">{{ L("Output VAT by account (FY)","ض.ق.م المخرجات حسب الحساب","TVA collectée par compte") }}</div>
        <table class="w-full text-[12px]"><tbody>
          <tr v-for="(r,i) in vat.output" :key="i" class="border-b border-line-hair last:border-0"><td class="px-4 py-2 text-ink-2">{{ r.name }}</td><td class="px-4 py-2 text-end tnum font-semibold text-success-dark">{{ money0(r.amount) }}</td></tr>
          <tr v-if="!vat.output.length"><td class="px-4 py-6 text-center text-ink-muted text-[12px]" colspan="2">{{ L("No output VAT","لا ض.ق.م مخرجات","Aucune TVA collectée") }}</td></tr>
        </tbody></table>
      </div>
      <div class="bg-white rounded-card border border-line overflow-hidden shadow-card">
        <div class="px-4 py-3 border-b border-line text-[13px] font-bold">{{ L("Input VAT by account (FY)","ض.ق.م المدخلات حسب الحساب","TVA déductible par compte") }}</div>
        <table class="w-full text-[12px]"><tbody>
          <tr v-for="(r,i) in vat.input" :key="i" class="border-b border-line-hair last:border-0"><td class="px-4 py-2 text-ink-2">{{ r.name }}</td><td class="px-4 py-2 text-end tnum font-semibold">{{ money0(Math.abs(r.amount)) }}</td></tr>
          <tr v-if="!vat.input.length"><td class="px-4 py-6 text-center text-ink-muted text-[12px]" colspan="2">{{ L("No input VAT","لا ض.ق.م مدخلات","Aucune TVA déductible") }}</td></tr>
        </tbody></table>
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
import { loadVat, money0 } from "@/composables/useReports";

const { locale } = useI18n();
const { entityId } = useUi();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const today = new Date().toISOString().slice(0, 10);
const curMonth = today.slice(0, 7);
const MN = { en: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], fr: ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."], ar: ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"] };
function monthLabel(m) { const [y, mo] = m.split("-"); const arr = MN[locale.value] || MN.en; return `${arr[+mo - 1]} ${y}`; }

const live = ref(false);
const vat = ref({ output: [], input: [], output_total: 0, input_total: 0, net_payable: 0 });
const periods = ref([]);

function stat(p) {
  if (p.month === curMonth) return { c: "#0369a1", bg: "#eff6ff", label: L("In progress", "جارية", "En cours") };
  if (p.deadline >= today) return { c: "#b45309", bg: "#fffbeb", label: L("Due", "مستحق", "À déclarer") };
  return { c: "#78716c", bg: "#f5f5f4", label: L("Past deadline", "انتهى الموعد", "Échue") };
}
const SAMPLE_P = [
  { month: "2026-06", output: 143286, input: 1229, net: 142057, deadline: "2026-07-20" },
  { month: "2026-05", output: 229403, input: 10057, net: 219346, deadline: "2026-06-20" },
  { month: "2026-04", output: 258603, input: 13663, net: 244940, deadline: "2026-05-20" },
];
// Next to declare = most recent month whose deadline is still upcoming (else the latest).
const nextDue = computed(() => periods.value.find((p) => p.deadline >= today) || periods.value[0] || null);
const nextStatus = computed(() => (nextDue.value ? stat(nextDue.value) : { c: "#0369a1", bg: "#eff6ff", label: "" }));

async function load() {
  const r = await loadVat();
  live.value = r.live; vat.value = r.data;
  try { periods.value = (await api.call("accounting_portal.api.reports.vat_periods", { company: currentCompany() })).periods || []; }
  catch { periods.value = SAMPLE_P; }
}
onMounted(load);
watch(entityId, load);
</script>
