<template>
  <div class="space-y-3.5">
    <!-- Summary bar -->
    <div class="flex items-center gap-2.5 px-[15px] py-[13px] rounded-[13px]" style="background:#fff7ed;border:1px solid #fed7aa">
      <span class="w-[30px] h-[30px] rounded-[8px] grid place-items-center flex-shrink-0" style="background:#ffedd5"><Icon name="alert" :size="16" color="#ea580c" /></span>
      <div class="flex-1">
        <div class="text-[12.5px] font-bold" style="color:#9a3412">{{ VARIANCE_QUEUE.length }} {{ L("lines","سطر","lignes") }} · {{ VARIANCE_TOTAL }} MAD</div>
        <div class="text-[11.5px] mt-px" style="color:#c2410c">{{ L("COD collected short of order value — investigate or write off","التحصيل أقل من قيمة الطلب — تحقّق أو اشطب","Encaissement inférieur à la commande — enquêter ou passer en perte") }}</div>
      </div>
      <span class="inline-flex items-center gap-1 text-[10px] font-bold px-2.5 py-[3px] rounded-full flex-shrink-0" style="background:#f5f3ff;color:#7c3aed;border:1px solid #ddd6fe"><Icon name="shield" :size="11" />{{ L("Auditor","المدقّق","Auditeur") }}</span>
    </div>

    <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead>
            <tr style="background:#fafaf9">
              <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Order","الطلب","Commande") }}</th>
              <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Carrier","الناقل","Transporteur") }}</th>
              <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Expected","المتوقَّع","Attendu") }}</th>
              <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Collected","المُحصَّل","Collecté") }}</th>
              <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Variance","الفرق","Écart") }}</th>
              <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Type","النوع","Type") }}</th>
              <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Age","العمر","Âge") }}</th>
              <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in VARIANCE_QUEUE" :key="r.order" class="border-t border-line-hair">
              <td class="px-4 py-2.5 font-mono font-semibold whitespace-nowrap">{{ r.order }}</td>
              <td class="px-4 py-2.5 text-ink-2 whitespace-nowrap">{{ r.carrier }}</td>
              <td class="px-4 py-2.5 text-end tnum text-ink-3">{{ r.expected }}</td>
              <td class="px-4 py-2.5 text-end tnum font-semibold">{{ r.collected }}</td>
              <td class="px-4 py-2.5 text-end tnum font-bold text-sale">{{ r.variance }}</td>
              <td class="px-4 py-2.5">
                <span class="inline-block text-[10px] font-bold px-2 py-0.5 rounded-badge border" :style="{ background: VAR_TYPE[r.type].bg, color: VAR_TYPE[r.type].fg, borderColor: VAR_TYPE[r.type].bd }">{{ varTypeLabel(r.type, locale) }}</span>
              </td>
              <td class="px-4 py-2.5 text-end text-ink-muted tnum">{{ r.age }}</td>
              <td class="px-4 py-2.5 text-end whitespace-nowrap">
                <span class="inline-flex gap-1.5">
                  <button class="h-[27px] px-2.5 rounded-[7px] bg-white border border-line-2 text-ink-3 text-[10.5px] font-semibold hover:bg-app-warm">{{ L("Dispute","اعتراض","Contester") }}</button>
                  <button class="h-[27px] px-2.5 rounded-[7px] text-[10.5px] font-bold" style="background:#fef2f2;border:1px solid #fecaca;color:#be123c">{{ L("Write off","شطب","Passer en perte") }}</button>
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { VARIANCE_QUEUE, VARIANCE_TOTAL, VAR_TYPE, varTypeLabel } from "@/data/banking";
const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
</script>
