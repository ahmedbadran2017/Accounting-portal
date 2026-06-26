<template>
  <div class="space-y-3.5">
    <div class="flex items-center gap-2 flex-wrap">
      <span class="text-[13px] font-bold">{{ L("Remediation","المعالجة","Remédiation") }}</span>
      <span v-if="isLive !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="isLive ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ isLive ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échant.") }}</span>
      <span class="text-[11px] text-ink-muted">{{ L("propose correcting entries for the auditor's findings — review & approve before they post","اقترح قيود تصحيح لملاحظات المدقّق — مراجعة وموافقة قبل الترحيل","proposez des écritures correctives — révision avant passage") }}</span>
    </div>

    <div class="grid lg:grid-cols-2 gap-3.5">
      <div v-for="fx in fixable" :key="fx.id" class="bg-white rounded-card border shadow-card p-4" :style="{ borderColor: fx.bd }">
        <div class="flex items-start gap-2.5">
          <span class="w-9 h-9 rounded-[10px] grid place-items-center flex-shrink-0" :style="{ background: fx.tint }"><Icon name="shield" :size="17" :color="fx.ic" /></span>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 flex-wrap"><span class="text-[13px] font-bold">{{ fx.title }}</span><span class="text-[9px] font-bold px-1.5 py-0.5 rounded-badge" :style="{ background: fx.tint, color: fx.ic }">{{ fx.sevLabel }}</span></div>
            <div class="text-[11.5px] text-ink-3 mt-1 leading-relaxed">{{ fx.detail }}</div>
          </div>
        </div>
        <div class="flex items-center justify-between mt-3 pt-3 border-t border-line-hair">
          <div><div class="text-[10px] text-ink-muted uppercase tracking-wide font-bold">{{ L("Balance","الرصيد","Solde") }}</div><div class="text-[16px] font-extrabold tnum" :class="fx.amount < 0 ? 'text-sale' : ''">{{ money(fx.amount) }}</div></div>
          <button class="h-9 px-3.5 rounded-[10px] bg-brand hover:bg-brand-dark text-white text-[12px] font-bold inline-flex items-center gap-1.5 shadow-brand" @click="openFix(fx.kind)">
            <Icon name="shield" :size="14" color="#fff" />{{ L("Propose correcting entry","اقترح قيد تصحيح","Proposer") }}
          </button>
        </div>
      </div>
      <div v-if="!fixable.length && isLive" class="lg:col-span-2 bg-white rounded-card border border-line shadow-card py-12 text-center text-[12px] text-success-dark"><Icon name="check" :size="20" color="#047857" class="mb-1" /><div>{{ L("Nothing to remediate — no correctable findings.","لا شيء للمعالجة.","Rien à corriger.") }}</div></div>
    </div>

    <p class="text-[10.5px] text-ink-muted">{{ L("Each proposal is balanced and editable. Material entries are recorded Proposed and need an approver — nothing posts directly.","كل اقتراح متوازن وقابل للتعديل. القيود الكبيرة تُسجَّل كمقترحة وتحتاج موافقة.","Chaque proposition est équilibrée; les écritures importantes nécessitent une approbation.") }}</p>

    <InventoryCorrectionModal :open="showFix" :kind="fixKind" @close="showFix = false" @done="load" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import InventoryCorrectionModal from "@/components/InventoryCorrectionModal.vue";
import { loadControls } from "@/composables/useAuditor";
import { useUi } from "@/composables/useUi";

const { locale } = useI18n();
const { entityId } = useUi();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const money = (n) => { n = Number(n) || 0; const a = Math.abs(n); return (n < 0 ? "−" : "") + (a >= 1e6 ? (a / 1e6).toFixed(2) + "M" : a >= 1e3 ? Math.round(a / 1e3) + "K" : Math.round(a).toLocaleString()); };

const findings = ref([]);
const isLive = ref(null);
async function load() {
  const r = await loadControls();
  isLive.value = r.live;
  findings.value = (r.data && r.data.findings) || [];
}
onMounted(load);
watch(entityId, load);

// Findings that have a generator-backed fix.
const FIX = {
  stock_cogs: { kind: "inventory", tint: "#fef3c7", ic: "#b45309", bd: "#fde68a" },
  correction_pile: { kind: "correction", tint: "#faf5ff", ic: "#7c3aed", bd: "#e9d5ff" },
};
const SEV = { high: { en: "High", ar: "مرتفع", fr: "Élevé" }, medium: { en: "Medium", ar: "متوسط", fr: "Moyen" }, low: { en: "Low", ar: "منخفض", fr: "Faible" } };
const fixable = computed(() => findings.value.filter((f) => FIX[f.id]).map((f) => ({
  id: f.id, kind: FIX[f.id].kind, ...FIX[f.id], title: f.title, detail: f.detail, amount: f.amount,
  sevLabel: (SEV[f.severity] || SEV.high)[locale.value] || (SEV[f.severity] || SEV.high).en,
})));

const showFix = ref(false);
const fixKind = ref("inventory");
function openFix(kind) { fixKind.value = kind; showFix.value = true; }
</script>
