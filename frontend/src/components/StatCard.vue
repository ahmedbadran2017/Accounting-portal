<template>
  <div class="group relative bg-white border border-line rounded-[16px] p-4 shadow-card hover:-translate-y-0.5 hover:shadow-cardHover transition-all overflow-hidden">
    <span class="absolute top-0 inset-x-0 h-[3px]" :style="{ background: color, opacity: .3 }"></span>
    <div class="absolute -top-10 -end-10 w-28 h-28 rounded-full blur-2xl pointer-events-none" :style="{ background: glow || color, opacity: .07 }"></div>
    <div class="relative flex items-start gap-2.5">
      <span v-if="icon" class="w-9 h-9 rounded-[11px] grid place-items-center flex-shrink-0" :style="{ background: tint }"><Icon :name="icon" :size="17" :color="color" /></span>
      <div class="min-w-0 flex-1">
        <div class="flex items-center gap-1.5">
          <span class="text-[10.5px] text-ink-muted font-bold uppercase tracking-wider">{{ label }}</span>
          <span v-if="tag" class="text-[8.5px] font-bold px-1.5 py-px rounded-full" :style="{ background: tint, color }">{{ tag }}</span>
        </div>
        <div class="text-[22px] font-extrabold tnum leading-tight tracking-tight" :style="{ color: valueColor || '#1c1917' }">{{ value }}</div>
      </div>
    </div>
    <div v-if="sub" class="relative mt-1.5 text-[11px] text-ink-3">{{ sub }}</div>
  </div>
</template>

<script setup>
import Icon from "@/components/Icon.vue";
defineProps({
  label: String, value: [String, Number], sub: String, tag: String,
  icon: String, color: { type: String, default: "#a8a29e" },
  glow: String, tint: { type: String, default: "#fafaf9" }, valueColor: String,
});
</script>
