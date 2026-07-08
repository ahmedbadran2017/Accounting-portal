<template>
  <div class="space-y-3">
    <FiscalYearBar />
    <div class="bg-white rounded-[14px] border border-line shadow-card overflow-hidden">
      <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair">
        <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#ecfdf5"><Icon name="list" :size="14" color="#047857" /></span>
        <span class="text-[13px] font-bold">{{ L("Trial balance","ميزان المراجعة","Balance") }}</span>
        <span class="text-[11px] text-ink-muted">{{ period ? L("opening → movement → closing, this year","افتتاحي ← حركة ← ختامي، هذه السنة","ouverture → mouvement → clôture") : L("net balance per account · reconciled to the GL","الرصيد الصافي لكل حساب","solde net par compte") }}</span>
        <button type="button" class="ms-auto h-8 px-3 rounded-chip text-[11.5px] font-semibold text-accent-dark border border-line-2 hover:bg-app-warm disabled:opacity-50 inline-flex items-center gap-1.5" :disabled="pdfBusy" @click="downloadPdf"><Icon name="doc" :size="13" />{{ pdfBusy ? "…" : L("PDF","PDF","PDF") }}</button>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead>
            <tr class="border-b border-line text-[10px] font-bold uppercase tracking-wider text-ink-muted">
              <th class="px-4 py-2.5 text-start">{{ L("Code","الرمز","Code") }}</th>
              <th class="px-4 py-2.5 text-start">{{ L("Account","الحساب","Compte") }}</th>
              <template v-if="period">
                <th class="px-4 py-2.5 text-end">{{ L("Opening","افتتاحي","Ouverture") }}</th>
                <th class="px-4 py-2.5 text-end">{{ L("Debit","مدين","Débit") }}</th>
                <th class="px-4 py-2.5 text-end">{{ L("Credit","دائن","Crédit") }}</th>
                <th class="px-4 py-2.5 text-end">{{ L("Closing","ختامي","Clôture") }}</th>
              </template>
              <template v-else>
                <th class="px-4 py-2.5 text-end">{{ L("Debit","مدين","Débit") }}</th>
                <th class="px-4 py-2.5 text-end">{{ L("Credit","دائن","Crédit") }}</th>
              </template>
            </tr>
          </thead>
          <tbody v-if="loading">
            <tr v-for="n in 8" :key="'sk'+n" class="border-b border-line-hair animate-pulse" :style="{ opacity: Math.max(0.3, 1-(n-1)*0.1) }">
              <td class="px-4 py-3" :colspan="period ? 6 : 4"><div class="h-3 rounded-full bg-app-warm" style="max-width:320px"></div></td>
            </tr>
          </tbody>
          <tbody v-else>
            <tr v-for="(r,i) in rows" :key="i" class="border-b border-line-hair" :class="r.anomaly ? 'bg-rose-50/40' : 'hover:bg-app-warm/60'">
              <td class="px-4 py-2.5 font-mono text-ink-3 whitespace-nowrap">{{ r.code }}</td>
              <td class="px-4 py-2.5"><span class="inline-flex items-center gap-1.5">{{ r.name }}<Icon v-if="r.anomaly" name="alert" :size="12" color="#be123c" /></span></td>
              <template v-if="period">
                <td class="px-4 py-2.5 text-end tnum text-ink-3">{{ money(r.opening) }}</td>
                <td class="px-4 py-2.5 text-end tnum text-teal-700">{{ money(r.period_dr) }}</td>
                <td class="px-4 py-2.5 text-end tnum text-rose-600">{{ money(r.period_cr) }}</td>
                <td class="px-4 py-2.5 text-end tnum font-bold" :class="r.anomaly ? 'text-sale' : ''">{{ money(r.closing) }}</td>
              </template>
              <template v-else>
                <td class="px-4 py-2.5 text-end tnum font-semibold" :class="r.anomaly && r.dr ? 'text-sale' : ''">{{ money(r.dr) }}</td>
                <td class="px-4 py-2.5 text-end tnum font-semibold" :class="r.anomaly && r.cr ? 'text-sale' : ''">{{ money(r.cr) }}</td>
              </template>
            </tr>
            <tr v-if="!rows.length"><td :colspan="period ? 6 : 4" class="px-4 py-10 text-center text-ink-muted">{{ L("No balances.","لا أرصدة.","Aucun solde.") }}</td></tr>
          </tbody>
          <tfoot v-if="!period">
            <tr class="border-t-2 border-line-2 font-bold">
              <td class="px-4 py-2.5" colspan="2">{{ L("Total","الإجمالي","Total") }}</td>
              <td class="px-4 py-2.5 text-end tnum">{{ money(totals.dr) }}</td>
              <td class="px-4 py-2.5 text-end tnum">{{ money(totals.cr) }}</td>
            </tr>
          </tfoot>
        </table>
      </div>
      <div class="px-4 py-2.5 border-t border-line text-[11px] text-amber-700 flex items-start gap-1.5">
        <Icon name="alert" :size="13" color="#b45309" class="flex-shrink-0 mt-px" />
        {{ L("Pick a fiscal year to isolate each year’s movement (opening carried forward + this year’s Dr/Cr = closing).",
              "اختر سنة مالية لعزل حركة كل سنة (الافتتاحي المُرحّل + مدين/دائن السنة = الختامي).",
              "Choisissez un exercice pour isoler le mouvement de l’année.") }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import FiscalYearBar from "@/components/FiscalYearBar.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";
import { useFiscalYear } from "@/composables/useFiscalYear";
import { fmtAmount } from "@/utils/helpers";

const { locale } = useI18n();
const { entityId } = useUi();
const fyc = useFiscalYear();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const money = (n) => (Number(n) ? fmtAmount(n) : "—");

const rows = ref([]);
const loading = ref(true);
const period = ref(false);
const totals = ref({ dr: 0, cr: 0 });
const pdfBusy = ref(false);
async function downloadPdf() {
  if (pdfBusy.value) return;
  pdfBusy.value = true;
  try {
    const r = await api.call("accounting_portal.api.reports.report_pdf", { report: "trial_balance", company: currentCompany(), ...fyc.filterValue() });
    if (r?.file_url) window.open(r.file_url, "_blank");
  } catch { /* */ } finally { pdfBusy.value = false; }
}

async function load() {
  loading.value = true;
  try {
    const r = await api.call("accounting_portal.api.ledger.trial_balance", { company: currentCompany(), ...fyc.filterValue() });
    rows.value = r.rows || [];
    period.value = !!r.period;
    totals.value = { dr: r.total_dr || 0, cr: r.total_cr || 0 };
  } catch { rows.value = []; }
  finally { loading.value = false; }
}
load();
watch(entityId, load);
watch(fyc.selected, load);
</script>
