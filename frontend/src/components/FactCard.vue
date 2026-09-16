<template>
  <div class="bg-white rounded-[14px] border border-line p-4 shadow-card">
    <div class="flex items-center gap-2 mb-2.5">
      <span class="w-[24px] h-[24px] rounded-[7px] grid place-items-center" :style="{ background: tint }">
        <Icon :name="icon" :size="13" :color="color" />
      </span>
      <span class="text-[12.5px] font-bold">{{ title }}</span>
      <slot name="header" />
    </div>

    <dl v-if="shown.length" class="space-y-1.5 text-[12px]">
      <div v-for="f in shown" :key="f.label"
           class="flex justify-between gap-2" :class="f.rule ? 'pt-1 border-t border-line-hair' : ''">
        <dt :class="f.strong ? 'font-semibold' : 'text-ink-muted'">{{ f.label }}</dt>
        <dd class="text-end" :class="[f.strong ? 'font-bold' : 'font-medium', f.mono ? 'font-mono' : '', f.num ? 'tnum' : '']">
          <a v-if="f.href" :href="f.href" target="_blank" rel="noopener" class="text-accent hover:text-accent-dark">{{ f.value }}</a>
          <template v-else>{{ f.value }}</template>
          <span v-if="f.note" class="ms-1.5 text-[10px] font-bold px-1.5 py-0.5 rounded-full" style="background:#fffbeb;color:#b45309">{{ f.note }}</span>
        </dd>
      </div>
    </dl>

    <!-- Nothing is known yet. One sentence beats a column of dashes: the dashes
         read as missing data, and the accountant cannot tell "not shipped yet"
         from "we failed to load the carrier". -->
    <div v-else class="text-[11.5px] text-ink-muted py-1">{{ empty }}</div>

    <slot />
  </div>
</template>

<script setup>
import { computed } from "vue";
import Icon from "@/components/Icon.vue";

// A card of label/value facts that renders only the facts it actually has.
//
// Every detail page used to print each field unconditionally, so a normal order
// showed six dashes and two zeroes out of ten rows. Pass the whole list; rows
// whose value is empty, "—" or undefined are dropped, and if none survive the
// card says so in words instead.
const props = defineProps({
  title: { type: String, required: true },
  icon: { type: String, default: "doc" },
  tint: { type: String, default: "#faf6f4" },
  color: { type: String, default: "#0b5c4f" },
  facts: { type: Array, default: () => [] },
  empty: { type: String, default: "Nothing recorded yet." },
});

const BLANK = ["", "—", "-", "null", "undefined", "NaN"];
const has = (v) => v !== null && v !== undefined && !BLANK.includes(String(v).trim());

const shown = computed(() => (props.facts || []).filter((f) => f && has(f.value)));
</script>
