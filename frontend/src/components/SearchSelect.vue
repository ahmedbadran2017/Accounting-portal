<template>
  <div class="relative" v-click-outside="close">
    <input
      :value="display" @focus="onFocus" @input="onInput" @keydown.esc="close"
      :placeholder="placeholder" :disabled="disabled"
      class="w-full border border-line-2 rounded-[9px] ps-2.5 pe-8 focus:outline-none focus:border-accent/40 disabled:opacity-60 disabled:bg-app-warm/40"
      :class="inputClass" />
    <span class="absolute top-1/2 -translate-y-1/2 end-2.5 text-ink-muted pointer-events-none flex"><Icon :name="open ? 'search' : 'chevDown'" :size="14" /></span>
    <div v-if="open" class="absolute z-30 mt-1 w-full max-h-56 overflow-y-auto bg-white border border-line rounded-[10px] shadow-cardHover">
      <button v-for="o in filtered" :key="o.value" type="button"
        class="w-full text-start px-3 py-1.5 hover:bg-app-warm/60 border-t border-line-hair first:border-t-0 disabled:opacity-40 disabled:cursor-not-allowed"
        :class="o.value === modelValue ? 'bg-accent-soft' : ''" :disabled="o.disabled" @click="pick(o)">
        <div class="truncate text-[12.5px]" :class="o.value === modelValue ? 'font-semibold' : ''">{{ o.label }}</div>
        <div v-if="o.sub" class="text-[10px] text-ink-muted font-mono truncate">{{ o.sub }}</div>
      </button>
      <div v-if="!filtered.length" class="px-3 py-3 text-center text-[11px] text-ink-muted">{{ emptyText }}</div>
    </div>
  </div>
</template>

<script setup>
/**
 * Reusable searchable dropdown. Pass `items` as [{ value, label, sub?, disabled? }].
 * Behaves like a native <select> (v-model) but with type-to-filter — for pickers
 * with many options (accounts, suppliers, employees…). Small enum selects
 * (currency, status, mode) should stay native <select>.
 */
import { ref, computed } from "vue";
import Icon from "@/components/Icon.vue";

const props = defineProps({
  modelValue: { type: [String, Number], default: "" },
  items: { type: Array, default: () => [] },
  placeholder: { type: String, default: "Select…" },
  emptyText: { type: String, default: "No match" },
  disabled: { type: Boolean, default: false },
  limit: { type: Number, default: 100 },
  inputClass: { type: String, default: "h-9 text-[12.5px] bg-white" },
});
const emit = defineEmits(["update:modelValue"]);

const open = ref(false);
const typing = ref(false);
const query = ref("");

const sel = computed(() => props.items.find((o) => o.value === props.modelValue) || null);
const display = computed(() => (typing.value ? query.value : (sel.value ? sel.value.label : "")));
const filtered = computed(() => {
  const q = query.value.trim().toLowerCase();
  if (!typing.value || !q) return props.items.slice(0, props.limit);
  return props.items
    .filter((o) => String(o.label || "").toLowerCase().includes(q) || String(o.sub || "").toLowerCase().includes(q))
    .slice(0, props.limit);
});

function onFocus() { open.value = true; typing.value = true; query.value = ""; }
function onInput(e) { open.value = true; typing.value = true; query.value = e.target.value; }
function pick(o) { if (o.disabled) return; emit("update:modelValue", o.value); typing.value = false; query.value = ""; open.value = false; }
function close() { open.value = false; typing.value = false; query.value = ""; }
</script>
