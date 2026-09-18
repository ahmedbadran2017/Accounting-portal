<template>
  <transition name="fade">
    <div v-if="t.selected.value.size" class="fixed bottom-5 inset-x-0 z-40 flex flex-col items-center justify-end px-4 pointer-events-none">
      <div class="pointer-events-auto bg-ink text-white rounded-[14px] shadow-xl flex items-center gap-2.5 ps-4 pe-2 py-2 max-w-full flex-wrap">
        <span class="text-[13px] font-bold whitespace-nowrap">{{ t.selected.value.size }} {{ L("selected", "محدد", "sél.") }}</span>
        <span v-if="note" class="text-[11px] text-white/60 truncate max-w-[200px]">· {{ note }}</span>
        <button @click="t.clearSelection()" class="text-[11px] text-white/60 hover:text-white px-1.5">{{ L("clear", "مسح", "effacer") }}</button>
        <span class="w-px h-5 bg-white/15"></span>
        <button @click="t.exportSelectedCSV(filename)" class="inline-flex items-center gap-1.5 h-8 px-3 rounded-[10px] text-[12px] font-semibold bg-white/10 hover:bg-white/20 transition">
          <Icon name="download" :size="13" color="#fff" />{{ L("Export", "تصدير", "Exporter") }}
        </button>
        <button v-for="a in actions" :key="a.key" @click="start(a)" :disabled="busy || (a.disabled && a.disabled(t.selectedRows.value))"
                class="inline-flex items-center gap-1.5 h-8 px-3.5 rounded-[10px] text-[12px] font-bold text-white disabled:opacity-40 transition hover:brightness-110"
                :style="{ background: a.color || '#0f766e' }">
          <Icon v-if="!(busy && running === a.key)" :name="a.icon || 'check'" :size="13" color="#fff" />
          <span v-if="busy && running === a.key" class="w-3 h-3 rounded-full border-2 border-white/40 border-t-white animate-spin"></span>
          {{ a.label }}
        </button>
      </div>

      <!-- Some actions need one value before they run — who to assign to, which
           tag to add. The bar asks for it here rather than sending the caller
           off to a modal, so the selection stays visible while you answer. -->
      <div v-if="asking" class="pointer-events-auto absolute bottom-[58px] w-[280px] bg-white rounded-[14px] border border-line shadow-pop p-3 space-y-2.5">
        <div class="text-[12px] font-bold">{{ asking.prompt.label }}</div>
        <select v-if="asking.prompt.kind === 'user'" v-model="answer" class="fld fld-md w-full">
          <option value="">{{ L("Choose…", "اختر…", "Choisir…") }}</option>
          <option v-for="o in promptOptions" :key="o.name" :value="o.name">{{ o.full_name || o.name }}</option>
        </select>
        <input v-else v-model="answer" :placeholder="asking.prompt.placeholder || ''"
               class="fld fld-md w-full" />
        <div class="flex justify-end gap-2">
          <button class="h-8 px-3 rounded-chip text-[12px] font-semibold text-ink-3 hover:bg-app-warm" @click="cancelAsk">{{ L("Back", "رجوع", "Retour") }}</button>
          <UiButton variant="secondary" size="sm" :disabled="!answer || busy" @click="confirmAsk">{{ asking.label }}</UiButton>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import UiButton from "@/components/UiButton.vue";

const props = defineProps({
  t: { type: Object, required: true },
  actions: { type: Array, default: () => [] }, // {key,label,icon,color,run(rows),disabled(rows),confirm}
  filename: { type: String, default: "selection" },
  note: { type: String, default: "" },
});

const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const busy = ref(false);
const running = ref("");

const asking = ref(null);
const answer = ref("");
const promptOptions = ref([]);

async function start(a) {
  if (busy.value) return;
  if (!a.prompt) return run(a);
  asking.value = a; answer.value = ""; promptOptions.value = [];
  if (a.prompt.options) {
    try { promptOptions.value = await a.prompt.options() || []; } catch { promptOptions.value = []; }
  }
}
function cancelAsk() { asking.value = null; answer.value = ""; }
async function confirmAsk() {
  const a = asking.value;
  asking.value = null;
  await run(a, answer.value);
  answer.value = "";
}

async function run(a, arg) {
  if (busy.value) return;
  const rows = props.t.selectedRows.value;
  if (a.confirm && !window.confirm(a.confirm(rows))) return;
  busy.value = true; running.value = a.key;
  try { await a.run(rows, arg); }
  finally { busy.value = false; running.value = ""; }
}
</script>
