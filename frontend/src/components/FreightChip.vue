<template>
  <!-- ONE way to render a shipment's freight state everywhere:
       green = actual (bills or confirmed rate) · amber = estimate · red = none -->
  <span class="text-[10px] font-bold px-1.5 py-0.5 rounded-full whitespace-nowrap" :style="style">{{ label }}</span>
</template>

<script setup>
import { computed } from "vue";
import { useI18n } from "vue-i18n";

const props = defineProps({ source: { type: String, default: "none" } });
const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

const actual = computed(() => ["bills", "rate"].includes(props.source));
const style = computed(() =>
  actual.value ? "background:#ecfdf5;color:#047857"
  : props.source === "est" ? "background:#fffbeb;color:#b45309"
  : "background:#fef2f2;color:#b91c1c");
const label = computed(() =>
  actual.value ? L("actual", "فعلي", "réel")
  : props.source === "est" ? L("est.", "تقديري", "est.")
  : L("none", "بدون", "aucun"));
</script>
