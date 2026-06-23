<template>
  <div class="bg-white rounded-card border border-line overflow-hidden">
    <div class="overflow-x-auto">
      <table class="w-full text-[12px]">
        <thead>
          <tr class="border-b border-line">
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Code","الرمز","Code") }}</th>
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Account","الحساب","Compte") }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Debit","مدين","Débit") }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Credit","دائن","Crédit") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(r, i) in TRIAL" :key="i" class="border-b border-line-hair" :class="r.anomaly ? 'bg-rose-50/40' : 'hover:bg-app-warm/60'">
            <td class="px-4 py-2.5 font-mono text-ink-3 whitespace-nowrap">{{ r.code }}</td>
            <td class="px-4 py-2.5">
              <span class="inline-flex items-center gap-1.5">{{ r.name }}<Icon v-if="r.anomaly" name="alert" :size="12" color="#be123c" /></span>
            </td>
            <td class="px-4 py-2.5 text-end tnum font-semibold" :class="r.anomaly && r.dr ? 'text-sale' : ''">{{ r.dr || "—" }}</td>
            <td class="px-4 py-2.5 text-end tnum font-semibold" :class="r.anomaly && r.cr ? 'text-sale' : ''">{{ r.cr || "—" }}</td>
          </tr>
        </tbody>
        <tfoot>
          <tr class="border-t-2 border-line-2 font-bold">
            <td class="px-4 py-2.5" colspan="2">{{ L("Total","الإجمالي","Total") }}</td>
            <td class="px-4 py-2.5 text-end tnum">{{ totalDr }}</td>
            <td class="px-4 py-2.5 text-end tnum">{{ totalCr }}</td>
          </tr>
        </tfoot>
      </table>
    </div>
    <div class="px-4 py-2.5 border-t border-line text-[11px] text-amber-700 flex items-start gap-1.5">
      <Icon name="alert" :size="13" color="#b45309" class="flex-shrink-0 mt-px" />
      {{ L("Totals are skewed by the 168.8M 153.01 spike — exclude it to see the operating trial balance.",
            "الإجماليات متأثرة بقفزة 153.01 البالغة ١٦٨٫٨ مليون — استبعدها لرؤية ميزان التشغيل.",
            "Les totaux sont faussés par le pic 153.01 de 168,8M — excluez-le pour la balance d’exploitation.") }}
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { TRIAL } from "@/data/accountant";

const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const sum = (k) => TRIAL.reduce((s, r) => s + Number((r[k] || "0").replace(/,/g, "")), 0);
const totalDr = computed(() => sum("dr").toLocaleString("en-US"));
const totalCr = computed(() => sum("cr").toLocaleString("en-US"));
</script>
