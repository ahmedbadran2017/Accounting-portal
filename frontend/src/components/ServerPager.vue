<template>
  <div class="flex items-center justify-between px-4 py-3 border-t border-line-hair text-[12px]">
    <span class="text-ink-muted">{{ L("Showing","عرض","Affichage") }} <b>{{ t.rangeStart.value }}–{{ t.rangeEnd.value }}</b> {{ L("of","من","sur") }} <b>{{ (t.total.value || 0).toLocaleString() }}</b></span>
    <div class="flex items-center gap-1.5">
      <button class="h-8 px-3 rounded-[8px] text-[11.5px] font-semibold border border-line-2 disabled:opacity-40 inline-flex items-center gap-1" :disabled="t.page.value <= 1 || t.loading.value" @click="t.prev()"><Icon name="arrow" :size="12" class="rtl:rotate-180" />{{ L("Prev","السابق","Préc.") }}</button>
      <span class="text-ink-3 px-1">{{ t.page.value }} / {{ t.totalPages.value }}</span>
      <button class="h-8 px-3 rounded-[8px] text-[11.5px] font-semibold border border-line-2 disabled:opacity-40 inline-flex items-center gap-1" :disabled="t.page.value >= t.totalPages.value || t.loading.value" @click="t.next()">{{ L("Next","التالي","Suiv.") }}<Icon name="arrow" :size="12" class="rotate-180 rtl:rotate-0" /></button>
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
