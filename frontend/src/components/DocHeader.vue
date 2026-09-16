<template>
  <div class="bg-white rounded-[16px] border border-line px-5 py-[18px] shadow-card">
    <div class="flex items-start gap-3.5 flex-wrap">
      <div class="flex-1 min-w-[200px]">
        <div class="flex items-center gap-2.5 flex-wrap">
          <span class="text-[19px] font-bold font-mono">{{ id }}</span>
          <StatusPill v-if="status" :label="status" :tone="tone" />
          <StatusPill v-for="p in pills" :key="p.label" :label="p.label" :tone="p.tone || 'neutral'" :small="true" />
        </div>
        <!-- Identity line: who and when. Everything else belongs to a card
             below — repeating it here is what made these pages feel crowded. -->
        <div v-if="party || date || meta" class="flex items-center gap-3 mt-[7px] text-[12px] text-ink-3 flex-wrap">
          <span v-if="party" class="inline-flex items-center gap-1.5">
            <span v-if="initials" class="w-6 h-6 rounded-full grid place-items-center text-white text-[9px] font-bold" :style="{ background: avatar }">{{ initials }}</span>{{ party }}
          </span>
          <span v-if="date">{{ date }}</span>
          <span v-if="meta" class="text-ink-muted">{{ meta }}</span>
        </div>
      </div>

      <!-- The one number the reader came for. Nothing else on the page is
           allowed to be larger than this. -->
      <div v-if="amount !== null && amount !== undefined && amount !== ''" class="text-end">
        <div class="text-[10.5px] text-ink-muted font-semibold">{{ amountLabel }}</div>
        <div class="text-[24px] font-bold tnum leading-tight" :class="amountTone">
          {{ amount }} <span class="text-[13px] text-ink-3 font-normal">{{ currency }}</span>
        </div>
        <div v-if="secondary" class="text-[11.5px] text-ink-3 mt-0.5 tnum">{{ secondaryLabel }} {{ secondary }}</div>
      </div>
    </div>

    <div v-if="$slots.default" class="flex justify-end flex-wrap gap-2 mt-3 pt-3 border-t border-line-hair">
      <slot />
    </div>
  </div>
</template>

<script setup>
// One header for every document screen.
//
// Before this each of the twelve detail pages built its own, at its own type
// sizes, and the audit found the result: on the vendor and customer pages the
// largest number was a row count, on the invoice it was the document id, and
// the figure the accountant actually opened the page for — the outstanding
// balance — was not rendered as a field at all.
//
// The contract is: id, who, when, status, and THE number. Anything else goes in
// a FactCard underneath.
import StatusPill from "@/components/StatusPill.vue";

defineProps({
  id: { type: String, required: true },
  party: { type: String, default: "" },
  initials: { type: String, default: "" },
  avatar: { type: String, default: "#0b5c4f" },
  date: { type: String, default: "" },
  meta: { type: String, default: "" },
  status: { type: String, default: "" },
  tone: { type: String, default: "neutral" },
  pills: { type: Array, default: () => [] },
  amount: { type: [String, Number], default: null },
  amountLabel: { type: String, default: "" },
  amountTone: { type: String, default: "" },
  currency: { type: String, default: "" },
  secondary: { type: [String, Number], default: "" },
  secondaryLabel: { type: String, default: "" },
});
</script>
