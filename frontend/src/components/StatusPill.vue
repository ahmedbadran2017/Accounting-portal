<template>
  <span class="inline-flex items-center gap-1.5 font-bold border whitespace-nowrap"
        :class="small ? 'text-[10px] px-2 py-0.5 rounded-full' : 'text-[11px] px-2.5 py-1 rounded-[7px]'"
        :style="style">
    <span v-if="dot" class="w-1.5 h-1.5 rounded-full" :style="{ background: style.color }"></span>{{ label }}
  </span>
</template>

<script setup>
import { computed } from "vue";

// One pill for every status in the portal.
//
// The audit counted seventeen separate status maps plus the same green written
// inline 105 times, across three border radii. A status is one of five things —
// it is fine, it needs attention, it is wrong, it is finished, or it is nothing
// yet — and every doctype's vocabulary maps onto those five.
const TONES = {
  neutral: { background: "#f5f5f4", color: "#57534e", borderColor: "#e7e5e4" },
  good:    { background: "#ecfdf5", color: "#047857", borderColor: "#a7f3d0" },
  warn:    { background: "#fffbeb", color: "#b45309", borderColor: "#fde68a" },
  bad:     { background: "#fef2f2", color: "#b91c1c", borderColor: "#fecaca" },
  done:    { background: "#eff6ff", color: "#0369a1", borderColor: "#bfdbfe" },
  accent:  { background: "#f0fdf9", color: "#0b5c4f", borderColor: "#a7f3d0" },
};

const props = defineProps({
  label: { type: String, required: true },
  tone: { type: String, default: "neutral" },
  small: { type: Boolean, default: false },
  dot: { type: Boolean, default: false },
});

const style = computed(() => TONES[props.tone] || TONES.neutral);
</script>
