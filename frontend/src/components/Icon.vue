<template>
  <span class="inline-flex items-center" :style="{ color, lineHeight: 0 }" aria-hidden="true">
    <svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         :stroke-width="strokeWidth" stroke-linecap="round" stroke-linejoin="round">
      <path :d="path" />
    </svg>
  </span>
</template>

<script setup>
import { computed } from "vue";

// Single-stroke 24px icon paths (Lucide-equivalent), matching the design's ICONS map.
const ICONS = {
  grid: "M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z",
  receipt: "M5 3h14v18l-3-2-3 2-3-2-3 2zM8 8h8M8 12h8M8 16h5",
  cart: "M3 4h2l2.4 12.5a1 1 0 001 .8h9.2a1 1 0 001-.8L21 8H6M9 20a1 1 0 100-2 1 1 0 000 2zM18 20a1 1 0 100-2 1 1 0 000 2z",
  box: "M21 8l-9-5-9 5 9 5zM3 8v8l9 5 9-5V8M12 13v8",
  bank: "M3 10l9-6 9 6M5 10v8M19 10v8M9 10v8M15 10v8M3 21h18",
  ledger: "M4 4h13a1 1 0 011 1v15H6a2 2 0 01-2-2zM4 4a2 2 0 002 2h12",
  chart: "M3 3v18h18M7 14l3-4 3 2 4-7",
  gear: "M12 9a3 3 0 100 6 3 3 0 000-6zM19 12a7 7 0 00-.1-1l2-1.6-2-3.4-2.4 1a7 7 0 00-1.7-1l-.3-2.5H9.5l-.3 2.5a7 7 0 00-1.7 1l-2.4-1-2 3.4 2 1.6a7 7 0 000 2l-2 1.6 2 3.4 2.4-1a7 7 0 001.7 1l.3 2.5h4.9l.3-2.5a7 7 0 001.7-1l2.4 1 2-3.4-2-1.6c.1-.3.1-.7.1-1z",
  shield: "M12 2l8 3.5v6c0 5-3.5 8-8 10-4.5-2-8-5-8-10v-6zM8.5 12l2.2 2.2L15.5 9.5",
  search: "M11 4a7 7 0 100 14 7 7 0 000-14zM21 21l-4.3-4.3",
  chevDown: "M6 9l6 6 6-6",
  chev: "M9 6l6 6-6 6",
  alert: "M12 3l9.5 17H2.5zM12 9v5M12 18h.01",
  check: "M20 6L9 17l-5-5",
  bell: "M18 8a6 6 0 00-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 01-3.4 0",
  arrow: "M5 12h14M13 6l6 6-6 6",
  plus: "M12 5v14M5 12h14",
  spark: "M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1L12 3z",
  close: "M18 6L6 18M6 6l12 12",
  filter: "M3 5h18l-7 8v6l-4 2v-8z",
  truck: "M3 6h11v9H3zM14 9h4l3 3v3h-7zM7 18a1.6 1.6 0 100-3.2 1.6 1.6 0 000 3.2zM18 18a1.6 1.6 0 100-3.2 1.6 1.6 0 000 3.2z",
  clock: "M12 7v5l3 2M12 3a9 9 0 100 18 9 9 0 000-18z",
  coins: "M12 8c4 0 7-1.3 7-3s-3-3-7-3-7 1.3-7 3 3 3 7 3zM5 5v6c0 1.7 3 3 7 3s7-1.3 7-3V5M5 11v6c0 1.7 3 3 7 3s7-1.3 7-3v-6",
  wallet: "M3 7h15a2 2 0 012 2v8a2 2 0 01-2 2H4a1 1 0 01-1-1V6a2 2 0 012-2h11M17 13h.01",
  trend: "M3 17l5-5 4 3 6-8M21 7h-4M21 7v4",
  users: "M9 11a4 4 0 100-8 4 4 0 000 8zM3 21a6 6 0 0112 0M17 11a4 4 0 000-8M21 21a6 6 0 00-5-5.9",
  user: "M12 12a4 4 0 100-8 4 4 0 000 8zM4 21a8 8 0 0116 0",
  layers: "M12 2l9 5-9 5-9-5zM3 12l9 5 9-5M3 17l9 5 9-5",
  building: "M3 21h18M5 21V5a2 2 0 012-2h6a2 2 0 012 2v16M9 7h.01M9 11h.01M9 15h.01M12 7h.01M12 11h.01M12 15h.01M19 21V11a2 2 0 00-2-2h-2",
  list: "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01",
  send: "M4 12l16-8-6 16-3-6z",
  refresh: "M21 12a9 9 0 11-2.6-6.3M21 4v5h-5",
  doc: "M6 2h8l4 4v16H6zM14 2v4h4",
  scale: "M12 3v18M5 21h14M7 7l-4 6a4 4 0 008 0zM17 7l-4 6a4 4 0 008 0zM7 7l5-2 5 2",
};

const props = defineProps({
  name: { type: String, required: true },
  size: { type: [Number, String], default: 16 },
  color: { type: String, default: "currentColor" },
  strokeWidth: { type: [Number, String], default: 1.7 },
});

const path = computed(() => ICONS[props.name] || "");
</script>
