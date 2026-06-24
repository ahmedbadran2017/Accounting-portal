<template>
  <div class="space-y-3.5">
    <div class="flex items-center gap-2">
      <span class="inline-flex items-center gap-1.5 text-[10.5px] font-bold uppercase tracking-wider px-2 py-1 rounded-chip"
            :class="live ? 'text-success-dark bg-success-soft' : 'text-amber-700 bg-amber-50'">
        <span class="w-1.5 h-1.5 rounded-full" :class="live ? 'bg-success' : 'bg-amber-500'"></span>{{ live ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échantillon") }}
      </span>
      <span class="text-[11px] text-ink-muted">{{ L("VAT — fiscal year to date (DGI Morocco)","ض.ق.م — السنة المالية حتى اليوم","TVA — exercice à ce jour") }}</span>
    </div>

    <div class="grid sm:grid-cols-3 gap-3.5">
      <div class="bg-white rounded-card border border-line p-4 shadow-card">
        <div class="text-[10.5px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Output VAT (collected)","ض.ق.م المحصّلة","TVA collectée") }}</div>
        <div class="text-[22px] font-extrabold tnum mt-1 text-success-dark">{{ money0(vat.output_total) }}</div>
        <div class="text-[11px] text-ink-muted">MAD</div>
      </div>
      <div class="bg-white rounded-card border border-line p-4 shadow-card">
        <div class="text-[10.5px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Input VAT (recoverable)","ض.ق.م القابلة للاسترداد","TVA déductible") }}</div>
        <div class="text-[22px] font-extrabold tnum mt-1 text-ink">{{ money0(vat.input_total) }}</div>
        <div class="text-[11px] text-ink-muted">MAD</div>
      </div>
      <div class="rounded-card border p-4 shadow-card" :class="vat.net_payable>=0 ? 'bg-accent/5 border-accent/20' : 'bg-success-soft border-success/20'">
        <div class="text-[10.5px] font-bold uppercase tracking-wider text-ink-muted">{{ vat.net_payable>=0 ? L("Net VAT payable","صافي ض.ق.م المستحقة","TVA nette à payer") : L("Net VAT credit","رصيد ض.ق.م الدائن","Crédit de TVA") }}</div>
        <div class="text-[22px] font-extrabold tnum mt-1" :class="vat.net_payable>=0 ? 'text-accent-dark' : 'text-success-dark'">{{ money0(Math.abs(vat.net_payable)) }}</div>
        <div class="text-[11px] text-ink-muted">MAD</div>
      </div>
    </div>

    <div class="grid sm:grid-cols-2 gap-3.5">
      <div class="bg-white rounded-card border border-line overflow-hidden shadow-card">
        <div class="px-4 py-3 border-b border-line text-[13px] font-bold">{{ L("Output VAT by account","ض.ق.م المخرجات حسب الحساب","TVA collectée par compte") }}</div>
        <table class="w-full text-[12px]"><tbody>
          <tr v-for="(r,i) in vat.output" :key="i" class="border-b border-line-hair last:border-0"><td class="px-4 py-2 text-ink-2">{{ r.name }}</td><td class="px-4 py-2 text-end tnum font-semibold text-success-dark">{{ money0(r.amount) }}</td></tr>
          <tr v-if="!vat.output.length"><td class="px-4 py-6 text-center text-ink-muted text-[12px]">{{ L("No output VAT in period","لا ض.ق.م مخرجات","Aucune TVA collectée") }}</td></tr>
        </tbody></table>
      </div>
      <div class="bg-white rounded-card border border-line overflow-hidden shadow-card">
        <div class="px-4 py-3 border-b border-line text-[13px] font-bold">{{ L("Input VAT by account","ض.ق.م المدخلات حسب الحساب","TVA déductible par compte") }}</div>
        <table class="w-full text-[12px]"><tbody>
          <tr v-for="(r,i) in vat.input" :key="i" class="border-b border-line-hair last:border-0"><td class="px-4 py-2 text-ink-2">{{ r.name }}</td><td class="px-4 py-2 text-end tnum font-semibold">{{ money0(Math.abs(r.amount)) }}</td></tr>
          <tr v-if="!vat.input.length"><td class="px-4 py-6 text-center text-ink-muted text-[12px]">{{ L("No input VAT in period","لا ض.ق.م مدخلات","Aucune TVA déductible") }}</td></tr>
        </tbody></table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useUi } from "@/composables/useUi";
import { loadVat, money0 } from "@/composables/useReports";

const { locale } = useI18n();
const { entityId } = useUi();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

const live = ref(false);
const vat = ref({ output: [], input: [], output_total: 0, input_total: 0, net_payable: 0 });

async function load() {
  const r = await loadVat();
  live.value = r.live; vat.value = r.data;
}
onMounted(load);
watch(entityId, load);
</script>
