<template>
  <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
    <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair">
      <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#fff4e0"><Icon name="clock" :size="14" color="#b45309" /></span>
      <span class="text-[13px] font-bold">{{ L("Carrier receivable aging","تقادم ذمم الناقلين","Ancienneté créances transporteurs") }}</span>
      <span class="text-[11px] text-ink-muted">{{ L("Cash held by carriers, by age","النقد لدى الناقلين، حسب العمر","Cash détenu par les transporteurs, par âge") }}</span>
    </div>
    <div class="overflow-x-auto">
      <table class="w-full text-[12px]">
        <thead>
          <tr style="background:#fafaf9">
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Carrier","الناقل","Transporteur") }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">0–3d</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">4–7d</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">8–14d</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">15d+</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Total","الإجمالي","Total") }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Avg days","متوسط الأيام","Jours moy.") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in CARRIER_AGING" :key="r.carrier" class="border-t border-line-hair">
            <td class="px-4 py-3 font-bold whitespace-nowrap">
              <span class="inline-flex items-center gap-1.5">{{ r.carrier }}<Icon v-if="r.alert" name="alert" :size="12" color="#d97706" /></span>
            </td>
            <td class="px-4 py-3 text-end tnum" style="color:#047857">{{ r.b0 }}</td>
            <td class="px-4 py-3 text-end tnum" style="color:#b45309">{{ r.b1 }}</td>
            <td class="px-4 py-3 text-end tnum" style="color:#c2410c">{{ r.b2 }}</td>
            <td class="px-4 py-3 text-end tnum" :style="{ color: r.b3 !== '0' ? '#be123c' : '#a8a29e' }">{{ r.b3 }}</td>
            <td class="px-4 py-3 text-end tnum font-bold">{{ r.total }}</td>
            <td class="px-4 py-3 text-end tnum" :style="{ color: r.alert ? '#c2410c' : '#57534e' }">{{ r.days }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="flex items-center gap-2.5 px-4 py-3 border-t border-line-hair" style="background:#fffbeb">
      <Icon name="alert" :size="15" color="#b45309" class="flex-shrink-0" />
      <span class="text-[11.5px] flex-1" style="color:#92400e">{{ L("Sendit holds 40,400 MAD aged beyond 8 days — chase remittance before it slips past 15d.","Sendit يحتجز ٤٠٬٤٠٠ درهم متجاوزة ٨ أيام — تابِع التحصيل قبل تجاوز ١٥ يوماً.","Sendit détient 40 400 MAD au-delà de 8 jours — relancer avant 15 j.") }}</span>
    </div>
  </div>
</template>

<script setup>
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { CARRIER_AGING } from "@/data/banking";
const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
</script>
