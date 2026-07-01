<template>
  <div class="flex items-center gap-2 flex-wrap">
    <span class="text-[10px] font-bold uppercase tracking-wider text-ink-muted inline-flex items-center gap-1.5"><Icon name="chart" :size="12" color="#0b5c4f" />{{ L("Fiscal year", "السنة المالية", "Exercice") }}</span>
    <div class="flex gap-1 bg-white border border-line rounded-chip p-1 shadow-card overflow-x-auto">
      <button type="button" class="px-2.5 py-1 rounded-lg text-[11.5px] font-semibold whitespace-nowrap" :class="fy.selected.value === 'all' ? 'bg-app-warm text-accent-dark shadow-card' : 'text-ink-3 hover:text-ink'" @click="pick('all')">{{ L("All time", "الكل", "Tout") }}</button>
      <button v-for="y in fy.years.value" :key="y.name" type="button" class="px-2.5 py-1 rounded-lg text-[11.5px] font-semibold whitespace-nowrap" :class="fy.selected.value === y.name ? 'bg-app-warm text-accent-dark shadow-card' : 'text-ink-3 hover:text-ink'" @click="pick(y.name)">
        {{ y.name }}<span v-if="fy.current.value === y.name" class="ms-1 text-[8px] font-bold text-teal-600">•</span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { useFiscalYear } from "@/composables/useFiscalYear";

const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fy = useFiscalYear();
onMounted(fy.loadYears);
function pick(name) { fy.selected.value = name; }
</script>
