<template>
  <div v-if="t.sorted.value.length" class="flex items-center gap-3 px-4 py-2.5 border-t border-line-hair text-[11.5px] text-ink-3 flex-wrap">
    <span>{{ L("Showing","عرض","Affichage") }} <b class="text-ink">{{ t.rangeStart.value }}–{{ t.rangeEnd.value }}</b> {{ L("of","من","sur") }} <b class="text-ink">{{ t.sorted.value.length }}</b></span>
    <div class="ms-auto flex items-center gap-1">
      <button class="h-7 px-2.5 rounded-chip border border-line-2 bg-white text-ink-2 font-semibold disabled:opacity-40 hover:bg-app-warm inline-flex items-center gap-1" :disabled="t.page.value <= 1" @click="t.page.value--"><Icon name="arrow" :size="12" class="rotate-180 rtl:rotate-0" />{{ L("Prev","السابق","Préc.") }}</button>
      <span class="px-2 font-semibold text-ink">{{ t.page.value }} / {{ t.totalPages.value }}</span>
      <button class="h-7 px-2.5 rounded-chip border border-line-2 bg-white text-ink-2 font-semibold disabled:opacity-40 hover:bg-app-warm inline-flex items-center gap-1" :disabled="t.page.value >= t.totalPages.value" @click="t.page.value++">{{ L("Next","التالي","Suiv.") }}<Icon name="arrow" :size="12" class="rtl:rotate-180" /></button>
    </div>
  </div>
</template>

<script setup>
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
defineProps({ t: { type: Object, required: true } });
const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
</script>
