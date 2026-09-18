<template>
  <component :is="tag" v-bind="$attrs" :class="cls" :disabled="tag === 'button' ? (disabled || busy) : null">
    <span v-if="busy" class="w-3.5 h-3.5 rounded-full border-2 border-white/40 border-t-white animate-spin flex-shrink-0"
          :class="variant === 'secondary' || variant === 'quiet' ? 'border-ink-muted/40 border-t-ink-2' : ''"></span>
    <Icon v-else-if="icon" :name="icon" :size="size === 'sm' ? 13 : 14" :color="iconColor" class="flex-shrink-0" />
    <slot />
  </component>
</template>

<script setup>
// One button, four meanings.
//
// The audit counted six different backgrounds doing the job of "the main action
// on this screen" across 166 buttons — terracotta 102, ink 30, teal 13, emerald
// 13, red 7, success 1 — at three heights in near-equal use (h-7 70, h-8 65,
// h-9 60). A row could hold a terracotta button beside a green one beside a dark
// one, all claiming to be the important one, none of them the same height.
//
// The rule now:
//   primary    teal      the action this screen exists for — one per surface
//   create     terracotta  only ever "make a new thing"
//   secondary  outlined   everything else that acts
//   quiet      bare       navigation and dismissal
//   danger     red        cancels, deletes, reverses a posting
//
// Two sizes: sm for toolbars and table rows, md for anything a decision is made
// in. Never three.
import { computed, useAttrs } from "vue";
import Icon from "@/components/Icon.vue";

defineOptions({ inheritAttrs: false });
const props = defineProps({
  variant: { type: String, default: "secondary" },  // primary | create | secondary | quiet | danger
  size: { type: String, default: "md" },            // sm | md
  icon: { type: String, default: "" },
  busy: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  block: { type: Boolean, default: false },
});
const attrs = useAttrs();
const tag = computed(() => (attrs.href ? "a" : "button"));

const SIZE = {
  sm: "h-8 px-3 text-[12px] gap-1.5 rounded-[9px]",
  md: "h-9 px-4 text-[13px] gap-2 rounded-[10px]",
};
const VARIANT = {
  primary: "text-white bg-accent hover:bg-accent-dark shadow-prim",
  create: "text-white bg-brand hover:bg-brand-dark shadow-brand",
  secondary: "text-ink-2 bg-white border border-line-2 hover:bg-app-warm hover:border-ink-muted/40",
  quiet: "text-ink-3 hover:text-ink hover:bg-app-warm",
  danger: "text-sale bg-sale/5 border border-sale/25 hover:bg-sale/10",
};
const ICON_COLOR = { primary: "#fff", create: "#fff", secondary: "#57534e", quiet: "#78716c", danger: "#c4301c" };

const iconColor = computed(() => ICON_COLOR[props.variant] || "#57534e");
const cls = computed(() => [
  "inline-flex items-center justify-center font-semibold whitespace-nowrap select-none",
  "transition-colors duration-150",
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/35 focus-visible:ring-offset-1",
  "disabled:opacity-45 disabled:pointer-events-none",
  SIZE[props.size] || SIZE.md,
  VARIANT[props.variant] || VARIANT.secondary,
  props.block ? "w-full" : "",
  attrs.class || "",
].join(" "));
</script>
