<template>
  <div v-if="x" class="fixed inset-0 z-[60] grid place-items-center bg-ink/30 px-4 py-6 overflow-y-auto" @click.self="close">
    <div class="bg-white rounded-card border border-line shadow-pop w-full max-w-[560px] p-5" role="alertdialog" aria-modal="true" :aria-label="t(x.title)">
      <div class="flex items-start gap-3">
        <div class="w-9 h-9 rounded-full grid place-items-center flex-none"
             :class="x.severity === 'danger' ? 'bg-rose-50 text-rose-700' : 'bg-amber-50 text-amber-700'">
          <Icon :name="x.icon || 'alert'" :size="18" />
        </div>
        <div class="flex-1 min-w-0">
          <div class="text-[15px] font-bold leading-snug">{{ t(x.title) }}</div>
          <div class="text-[13px] text-ink-3 mt-1 leading-relaxed">{{ t(x.body) }}</div>
        </div>
        <button class="text-ink-muted hover:text-ink-2 p-1 -m-1" :aria-label="L('Close', 'إغلاق', 'Fermer')" @click="close"><Icon name="x" :size="16" /></button>
      </div>

      <div v-for="(f, i) in (x.facts || [])" :key="'f' + i"
           class="mt-3 bg-app-warm/60 rounded-[10px] px-3 py-2 flex items-center justify-between gap-2 flex-wrap text-[13px]">
        <span class="flex items-center gap-1.5 min-w-0">
          <Icon name="check-circle" :size="14" class="text-emerald-600 flex-none" />
          <span class="text-ink-3">{{ t(f.label) }}</span>
          <button v-if="f.doc" class="font-mono text-[12px] underline decoration-dotted truncate" @click="open(f.doc)">{{ f.value }}</button>
          <span v-else class="font-mono text-[12px] truncate">{{ f.value }}</span>
        </span>
        <span v-if="f.amount" class="font-semibold tnum" dir="ltr">{{ f.amount }}</span>
      </div>

      <div v-if="x.lines && x.lines.rows && x.lines.rows.length" class="mt-3 border border-line-hair rounded-[10px] overflow-hidden">
        <table class="w-full text-[12.5px] table-fixed">
          <thead>
            <tr class="text-ink-muted bg-app-warm/40">
              <th v-for="c in x.lines.columns" :key="c.key" class="px-2.5 py-1.5 font-semibold"
                  :class="[c.num ? 'text-end' : 'text-start', c.key === 'idx' ? 'w-[46px]' : c.key === 'order' ? 'w-[96px]' : c.key === 'amount' ? 'w-[110px]' : '']">{{ t(c.label) }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(r, i) in x.lines.rows" :key="i" class="border-t border-line-hair">
              <td v-for="c in x.lines.columns" :key="c.key" class="px-2.5 py-1.5 truncate"
                  :class="c.num ? 'text-end tnum' : 'text-start'" :dir="c.num ? 'ltr' : null">{{ r[c.key] }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="x.note" class="mt-3 rounded-[10px] border border-amber-200 bg-amber-50 px-3 py-2 text-[12.5px] text-amber-800 flex gap-2">
        <Icon name="info" :size="14" class="flex-none mt-0.5" /><span>{{ t(x.note) }}</span>
      </div>

      <template v-if="(x.actions || []).length">
        <div class="text-[12.5px] font-semibold mt-4 mb-2">{{ L("What do you want to do?", "عايز تعمل إيه؟", "Que voulez-vous faire ?") }}</div>
        <div class="flex flex-col gap-2">
          <UiButton v-for="(a, i) in x.actions" :key="'a' + i" :variant="a.primary ? 'primary' : 'secondary'" size="md"
                    class="w-full !justify-start text-start" :busy="busy === i" :disabled="busy !== null"
                    @click="act(a, i)">{{ t(a.label) }}</UiButton>
        </div>
      </template>
      <div v-else class="flex justify-end mt-4">
        <UiButton variant="secondary" size="md" @click="close">{{ L("Got it", "تمام", "Compris") }}</UiButton>
      </div>
      <div v-if="actErr" class="mt-2 text-[12px] text-rose-700">{{ actErr }}</div>

      <details v-if="x.technical" class="mt-3 text-[11.5px] text-ink-muted">
        <summary class="cursor-pointer select-none">{{ L("Technical detail", "التفاصيل التقنية", "Détail technique") }}</summary>
        <div class="font-mono mt-1.5 break-words" dir="ltr">{{ x.technical }}</div>
      </details>
    </div>
  </div>
</template>

<script setup>
// The popup for a failed write: what happened, the documents behind it, and
// ready-made fixes. Content comes from api/error_explain.py in all three
// languages; this component only picks the reader's.
import { ref, computed } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import Icon from "@/components/Icon.vue";
import UiButton from "@/components/UiButton.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useToast } from "@/composables/useToast";
import { explainCurrent, closeExplain } from "@/composables/useErrorExplain";
import { routeForDoc } from "@/utils/helpers";

const { locale } = useI18n();
const router = useRouter();
const toast = useToast();
const x = computed(() => explainCurrent.value);
const busy = ref(null);
const actErr = ref("");
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const t = (o) => (o ? (o[locale.value] || o.en || "") : "");

function close() {
  if (busy.value !== null) return;
  actErr.value = "";
  closeExplain();
}

function open(d) {
  const r = routeForDoc(d.doctype, d.name);
  closeExplain();
  if (r) router.push(r);
}

const ENDPOINT = {
  remove_lines: "remove_lines",
  delete_drafts: "delete_drafts",
  unlink_closed: "unlink_closed",
  clear_price_list: "clear_price_list",
  realloc_payment: "realloc_payment",
};

async function act(a, i) {
  if (a.kind === "open") return open({ doctype: a.doctype, name: a.name });
  const fn = ENDPOINT[a.kind];
  if (!fn) return;
  busy.value = i;
  actErr.value = "";
  try {
    await api.call(`accounting_portal.api.error_explain.${fn}`, {
      doctype: a.doctype, name: a.name, rows: a.rows, names: a.names, company: currentCompany(),
    });
    toast.success(L("Done", "تم", "Fait"));
    // The fix saved the document on the server; reload so every open screen
    // (the draft editor included) shows it as it now stands.
    closeExplain();
    setTimeout(() => window.location.reload(), 400);
  } catch (err) {
    actErr.value = String((err && err.message) || L("Failed", "فشل", "Échec")).slice(0, 200);
  } finally {
    busy.value = null;
  }
}
</script>
