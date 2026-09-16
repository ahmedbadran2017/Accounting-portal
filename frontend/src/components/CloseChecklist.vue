<template>
  <div class="flex flex-col gap-2.5">
    <button v-for="c in items" :key="c.key" type="button" @click="$emit('open', c.link)"
            class="flex items-center gap-2.5 px-3 py-2.5 border rounded-[11px] text-start hover:shadow-card transition-all"
            :style="{ borderColor: tone(c).bd, background: c.state === 'done' ? '#fdfdfc' : tone(c).bg + '55' }">
      <span class="w-[24px] h-[24px] rounded-[7px] grid place-items-center flex-shrink-0" :style="{ background: tone(c).bg }">
        <Icon :name="tone(c).icon" :size="13" :color="tone(c).fg" />
      </span>
      <div class="flex-1 min-w-0">
        <div class="text-[12px] font-semibold">{{ L(c.en, c.ar, c.fr) }}</div>
        <div v-if="detail(c)" class="text-[10.5px] text-ink-muted tnum" dir="ltr">{{ detail(c) }}</div>
      </div>
      <StatusPill :label="stateLabel(c)" :tone="tone(c).pill" :small="true" />
      <Icon name="arrow" :size="12" color="#cfc9c4" class="rtl:rotate-180 flex-shrink-0" />
    </button>

    <div v-if="!items.length" class="py-8 text-center text-[12px] text-ink-muted">
      {{ empty || L("Nothing to check here.", "لا يوجد ما يُفحص.", "Rien à vérifier.") }}
    </div>
  </div>
</template>

<script setup>
// The checklist shared by the day scope and the month scope.
//
// These were two components with the same button, the same three states, the
// same tones and the same `go(c.link)` — one scoped to a day and one to a
// month. Written twice, they had already drifted: one rendered its state as an
// emoji and the other as an icon, and they disagreed about when to show the
// figure under the label.
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import StatusPill from "@/components/StatusPill.vue";

const props = defineProps({
  items: { type: Array, default: () => [] },
  empty: { type: String, default: "" },
  currency: { type: String, default: "MAD" },
});
defineEmits(["open"]);

const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const num = (n) => Number(n || 0).toLocaleString("en-US", { maximumFractionDigits: 2 });

const TONES = {
  done:    { bg: "#ecfdf5", fg: "#047857", bd: "#a7f3d0", icon: "check", pill: "good" },
  blocked: { bg: "#fef2f2", fg: "#be123c", bd: "#fecaca", icon: "alert", pill: "bad" },
  pending: { bg: "#fffbeb", fg: "#b45309", bd: "#fde68a", icon: "clock", pill: "warn" },
};
const tone = (c) => TONES[c.state] || TONES.pending;

function stateLabel(c) {
  if (c.state === "done") return L("Done", "تمام", "Fait");
  if (c.state === "blocked") return L("Fix now", "اتصرف فورًا", "À corriger");
  return L("To finish", "متبقي", "À finir");
}

// Show the figure whenever there is one to act on. The month version hid it on
// anything already done, the day version showed it for one special key — so the
// same item read differently depending on which screen you were standing on.
function detail(c) {
  const bits = [];
  if (c.value !== undefined && c.value !== null && c.value !== "") bits.push(`${c.value}${c.unit ? " " + c.unit : ""}`);
  if (c.hint_amount) bits.push(`${num(c.hint_amount)} ${props.currency}`);
  return c.state === "done" && !bits.length ? "" : bits.join(" · ");
}
</script>
