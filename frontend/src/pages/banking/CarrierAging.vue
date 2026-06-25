<template>
  <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
    <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
      <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#fff4e0"><Icon name="clock" :size="14" color="#b45309" /></span>
      <span class="text-[13px] font-bold">{{ L("Carrier receivable aging", "تقادم ذمم الناقلين", "Ancienneté créances transporteurs") }}</span>
      <span v-if="live !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="live ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ live ? "Live" : "Sample" }}</span>
      <span class="text-[11px] text-ink-muted">{{ L("Cash held by carriers, by age", "النقد لدى الناقلين، حسب العمر", "Cash détenu, par âge") }}</span>
    </div>
    <div v-if="loading" class="px-1"><TableLoading :rows="4" /></div>
    <div v-else class="overflow-x-auto">
      <table class="w-full text-[12px]">
        <thead>
          <tr style="background:#fafaf9">
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Carrier", "الناقل", "Transporteur") }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">0–3d</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">4–7d</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">8–14d</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">15d+</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Total", "الإجمالي", "Total") }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Avg days", "متوسط الأيام", "Jours moy.") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in carriers" :key="r.carrier" class="border-t border-line-hair">
            <td class="px-4 py-3 font-bold whitespace-nowrap"><span class="inline-flex items-center gap-1.5">{{ r.carrier }}<Icon v-if="r.alert" name="alert" :size="12" color="#d97706" /></span></td>
            <td class="px-4 py-3 text-end tnum" style="color:#047857">{{ fmt(r.d0_3) }}</td>
            <td class="px-4 py-3 text-end tnum" style="color:#b45309">{{ fmt(r.d4_7) }}</td>
            <td class="px-4 py-3 text-end tnum" style="color:#c2410c">{{ fmt(r.d8_14) }}</td>
            <td class="px-4 py-3 text-end tnum" :style="{ color: r.d15p ? '#be123c' : '#a8a29e' }">{{ r.d15p ? fmt(r.d15p) : "0" }}</td>
            <td class="px-4 py-3 text-end tnum font-bold">{{ fmt(r.total) }}</td>
            <td class="px-4 py-3 text-end tnum" :style="{ color: r.alert ? '#c2410c' : '#57534e' }">{{ r.avg_days }}d</td>
          </tr>
          <tr v-if="!carriers.length"><td colspan="7" class="px-4 py-10 text-center text-ink-muted text-[12px]">{{ L("No carrier float — all delivered cash is collected. ✓", "لا عهدة لدى الناقلين. ✓", "Aucun encours transporteur. ✓") }}</td></tr>
        </tbody>
      </table>
    </div>
    <div v-if="worst" class="flex items-center gap-2.5 px-4 py-3 border-t border-line-hair" style="background:#fffbeb">
      <Icon name="alert" :size="15" color="#b45309" class="flex-shrink-0" />
      <span class="text-[11.5px] flex-1" style="color:#92400e">{{ worst.carrier }} {{ L("holds", "يحتجز", "détient") }} {{ fmt(worst.aged) }} MAD {{ L("aged beyond 8 days — chase remittance before it slips past 15d.", "متجاوزة 8 أيام — تابِع التحصيل قبل تجاوز 15 يوماً.", "au-delà de 8 jours — relancer avant 15 j.") }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";

const { locale } = useI18n();
const { entityId } = useUi();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US");

const carriers = ref([]);
const live = ref(null);
const loading = ref(false);
const worst = computed(() => {
  let w = null;
  for (const r of carriers.value) { const aged = (Number(r.d8_14) || 0) + (Number(r.d15p) || 0); if (r.alert && (!w || aged > w.aged)) w = { carrier: r.carrier, aged }; }
  return w;
});

const SAMPLE = [
  { carrier: "Cathedis", d0_3: 182000, d4_7: 96000, d8_14: 40000, d15p: 12000, total: 330000, avg_days: 5.2, alert: false },
  { carrier: "Sendit", d0_3: 48000, d4_7: 31000, d8_14: 22000, d15p: 18400, total: 119400, avg_days: 9.8, alert: true },
];
async function load() {
  loading.value = true;
  try { carriers.value = (await api.call("accounting_portal.api.cod.carrier_aging", { company: currentCompany() })).carriers || []; live.value = true; }
  catch { carriers.value = SAMPLE; live.value = false; }
  finally { loading.value = false; }
}
watch(entityId, load, { immediate: true });
</script>
