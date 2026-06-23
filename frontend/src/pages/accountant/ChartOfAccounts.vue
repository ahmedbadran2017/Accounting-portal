<template>
  <div class="bg-white rounded-card border border-line overflow-hidden">
    <table class="w-full text-[12px]">
      <tbody>
        <template v-for="(c, i) in COA" :key="i">
          <tr v-if="c.head" class="bg-app-warm/50">
            <td colspan="3" class="px-4 py-2 text-[11px] font-bold uppercase tracking-wider text-ink">{{ c.name(locale) }}</td>
          </tr>
          <tr v-else class="border-t border-line-hair" :class="c.anomaly ? 'bg-rose-50/40' : 'hover:bg-app-warm/60'">
            <td class="px-4 py-2.5 font-mono text-ink-3 whitespace-nowrap w-px">{{ c.code }}</td>
            <td class="px-4 py-2.5">
              <span class="inline-flex items-center gap-1.5">
                {{ c.name }}
                <span v-if="c.isNew" class="text-[9px] font-bold px-1.5 py-0.5 rounded-badge" style="background:#eff6ff;color:#0369a1;border:1px solid #bae6fd">{{ L("New","جديد","Nouveau") }}</span>
                <Icon v-if="c.anomaly" name="alert" :size="12" color="#be123c" />
              </span>
            </td>
            <td class="px-4 py-2.5 text-end tnum font-semibold whitespace-nowrap" :class="c.anomaly ? 'text-sale' : ''">{{ c.bal }}</td>
          </tr>
        </template>
      </tbody>
    </table>
    <div class="px-4 py-2.5 border-t border-line text-[11px] text-amber-700 flex items-start gap-1.5">
      <Icon name="alert" :size="13" color="#b45309" class="flex-shrink-0 mt-px" />
      {{ L("153.01 shows 168.8M MAD — a stock-movement spike under audit. 120.01 carries a credit balance (unmatched COD).",
            "153.01 يُظهر ١٦٨٫٨ مليون — قفزة حركة مخزون قيد التدقيق. و120.01 برصيد دائن (تحصيل COD غير مطابق).",
            "153.01 affiche 168,8M — pic de mouvement de stock sous audit. 120.01 a un solde créditeur (COD non lettré).") }}
    </div>
  </div>
</template>

<script setup>
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { COA } from "@/data/accountant";
const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
</script>
