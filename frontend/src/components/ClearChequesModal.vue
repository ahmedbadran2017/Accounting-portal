<template>
  <div class="fixed inset-0 z-[100] flex items-start justify-center p-4 sm:p-8 overflow-y-auto" style="background:rgba(28,25,23,.45)" @click.self="$emit('close')">
    <div class="bg-white rounded-[18px] shadow-cardHover w-full max-w-lg my-6 overflow-hidden">
      <div class="flex items-center gap-2.5 px-5 py-4 border-b border-line">
        <span class="w-8 h-8 rounded-[10px] grid place-items-center" style="background:#ecfdf5"><Icon name="check" :size="16" color="#047857" /></span>
        <div class="flex-1 min-w-0">
          <div class="text-[14px] font-bold">{{ L("Mark cleared", "تعليم كتصرّف", "Encaisser") }}</div>
          <div class="text-[11px] text-ink-muted">{{ rows.length }} {{ L("cheque(s) · set the actual bank clearing date", "شيك · حدّد تاريخ التصرّف الفعلي بالبنك", "chèque(s) · date de compensation réelle") }}</div>
        </div>
        <button class="text-ink-3 hover:text-ink" @click="$emit('close')"><Icon name="close" :size="18" /></button>
      </div>

      <!-- set-all helper -->
      <div class="px-5 py-3 border-b border-line-hair bg-app-warm/40 flex items-center gap-2 flex-wrap">
        <span class="text-[11px] font-semibold text-ink-3">{{ L("Set all to", "عيّن الكل على", "Tout mettre à") }}</span>
        <input type="date" v-model="allDate" class="h-8 border border-line-2 rounded-chip px-2.5 text-[12px] focus:outline-none focus:border-accent/40" />
        <button type="button" class="h-8 px-3 rounded-chip text-[11.5px] font-bold text-white bg-ink hover:brightness-110 disabled:opacity-40" :disabled="!allDate" @click="applyAll">{{ L("Apply", "طبّق", "Appliquer") }}</button>
        <span class="text-[10.5px] text-ink-muted ms-auto">{{ L("defaults to each cheque's date", "الافتراضي = تاريخ كل شيك", "défaut = date du chèque") }}</span>
      </div>

      <div class="max-h-[46vh] overflow-y-auto divide-y divide-line-hair">
        <div v-for="r in rows" :key="r.name" class="px-5 py-2.5 flex items-center gap-3">
          <div class="min-w-0 flex-1">
            <div class="text-[12px] font-mono font-semibold truncate">{{ r.cheque_no || r.name }}</div>
            <div class="text-[10.5px] text-ink-muted truncate">{{ r.supplier_name }} · {{ r.currency }} {{ fmt(r.amount) }}</div>
          </div>
          <input type="date" v-model="perDate[r.name]" class="h-8 border border-line-2 rounded-chip px-2.5 text-[12px] focus:outline-none focus:border-accent/40 shrink-0" />
        </div>
      </div>

      <div class="flex items-center justify-between gap-2 px-5 py-3.5 border-t border-line bg-app-warm/40">
        <span class="text-[11px] text-ink-muted">{{ L("Reconciliation only — no GL impact. Reversible.", "مطابقة فقط — لا أثر على الأستاذ. قابل للتراجع.", "Rapprochement seul — réversible.") }}</span>
        <div class="flex items-center gap-2">
          <button class="px-3.5 py-2 rounded-chip text-[12px] font-semibold text-ink-2 hover:bg-white" @click="$emit('close')">{{ L("Cancel", "إلغاء", "Annuler") }}</button>
          <button class="px-4 py-2 rounded-chip text-[12px] font-bold text-white bg-emerald-600 hover:bg-emerald-700 shadow-brand disabled:opacity-50" :disabled="!allSet || saving" @click="confirm">
            {{ saving ? L("Saving…", "جارٍ…", "…") : L("Confirm", "تأكيد", "Confirmer") }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";

const props = defineProps({ rows: { type: Array, default: () => [] } });
const emit = defineEmits(["close", "done"]);
const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const today = new Date().toISOString().slice(0, 10);

const perDate = reactive({});
// Default each cheque's clearing date to its own cheque date (best guess for the
// real bank date), falling back to today when the cheque has no date.
props.rows.forEach((r) => { perDate[r.name] = (r.due && r.due.slice(0, 10)) || today; });
const allDate = ref("");
const saving = ref(false);

const allSet = computed(() => props.rows.every((r) => perDate[r.name]));
function applyAll() { if (!allDate.value) return; props.rows.forEach((r) => { perDate[r.name] = allDate.value; }); }
async function confirm() {
  if (!allSet.value || saving.value) return;
  saving.value = true;
  const dates = {};
  props.rows.forEach((r) => { dates[r.name] = perDate[r.name]; });
  try { await emit("done", { names: props.rows.map((r) => r.name), dates }); }
  finally { saving.value = false; }
}
</script>
