<template>
  <!-- Sixteen list pages read their rows from useServerTable and none of them
       rendered its `error`. A failed load produced an empty table and a cheerful
       "Nothing awaiting invoice" — the one wrong answer that looks like good
       news. Every page that shows a pager now shows the failure too. -->
  <div v-if="t.error.value" class="flex items-start gap-2 px-4 py-2.5 border-t text-[12px]"
       style="background:#fef2f2;border-color:#fecaca;color:#b91c1c">
    <Icon name="alert" :size="14" color="#b91c1c" class="shrink-0 mt-[1px]" />
    <span class="min-w-0"><b>{{ L("This list failed to load — it is not empty.","فشل تحميل هذه القائمة — وهي ليست فارغة.","Échec du chargement — la liste n'est pas vide.") }}</b>
      <span class="ms-1 opacity-80 break-all">{{ t.error.value }}</span></span>
    <button class="ms-auto shrink-0 h-7 px-2.5 rounded-[8px] text-[11px] font-bold border" style="border-color:#fecaca" @click="t.load()">{{ L("Retry","إعادة المحاولة","Réessayer") }}</button>
  </div>
  <div class="flex items-center justify-between px-4 py-3 border-t border-line-hair text-[12px]">
    <span class="text-ink-muted">{{ L("Showing","عرض","Affichage") }} <b>{{ t.rangeStart.value }}–{{ t.rangeEnd.value }}</b> {{ L("of","من","sur") }} <b>{{ (t.total.value || 0).toLocaleString() }}</b></span>
    <div class="flex items-center gap-1.5">
      <button class="h-7 px-2.5 rounded-chip text-[11.5px] font-semibold border border-line-2 bg-white hover:bg-app-warm disabled:opacity-40 inline-flex items-center gap-1" :disabled="t.page.value <= 1 || t.loading.value" @click="t.prev()"><Icon name="arrow" :size="12" class="rotate-180 rtl:rotate-0" />{{ L("Prev","السابق","Préc.") }}</button>
      <span class="text-ink-3 px-1">{{ t.page.value }} / {{ t.totalPages.value }}</span>
      <button class="h-7 px-2.5 rounded-chip text-[11.5px] font-semibold border border-line-2 bg-white hover:bg-app-warm disabled:opacity-40 inline-flex items-center gap-1" :disabled="t.page.value >= t.totalPages.value || t.loading.value" @click="t.next()">{{ L("Next","التالي","Suiv.") }}<Icon name="arrow" :size="12" class="rtl:rotate-180" /></button>
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
