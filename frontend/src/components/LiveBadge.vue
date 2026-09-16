<template>
  <span v-if="live !== null && live !== undefined"
        class="inline-flex items-center gap-1.5 text-[9px] font-bold px-1.5 py-0.5 rounded-full border whitespace-nowrap"
        :style="live ? OK : BAD">
    <span v-if="dot" class="w-1.5 h-1.5 rounded-full" :style="{ background: live ? '#047857' : '#b45309' }"></span>
    {{ live ? L("Live", "مباشر", "Live") : L("Load failed", "فشل التحميل", "Échec") }}
  </span>
</template>

<script setup>
// One badge for "is this screen showing real data".
//
// There were 41 copies of this across the pages, in three shapes — pill with a
// border, pill without, dot-and-text — two wordings, and one that only ever
// rendered the failure. Six of them still said "Sample", left over from when a
// failed load substituted invented rows.
import { useI18n } from "vue-i18n";

defineProps({
  live: { type: Boolean, default: null },
  dot: { type: Boolean, default: false },
});

const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

const OK = "background:#ecfdf5;color:#047857;border-color:#a7f3d0";
const BAD = "background:#fffbeb;color:#b45309;border-color:#fde68a";
</script>
