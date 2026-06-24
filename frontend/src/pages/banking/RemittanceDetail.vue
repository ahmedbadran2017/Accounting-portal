<template>
  <div v-if="b" class="max-w-[1100px] mx-auto space-y-3.5">
    <button class="inline-flex items-center gap-1.5 text-[12px] font-medium text-ink-3 hover:text-ink" @click="back">
      <span class="rtl:rotate-180"><Icon name="arrow" :size="15" /></span>{{ L("Back to batches","العودة للدفعات","Retour aux lots") }}
    </button>

    <!-- Header card -->
    <div class="bg-white rounded-[16px] border border-line px-5 py-[18px] shadow-card">
      <div class="flex items-start gap-3.5 flex-wrap">
        <span class="w-10 h-10 rounded-[11px] grid place-items-center flex-shrink-0" style="background:#fff4e0"><Icon name="truck" :size="20" color="#b45309" /></span>
        <div class="flex-1 min-w-[200px]">
          <div class="flex items-center gap-2.5 flex-wrap">
            <span class="text-[18px] font-bold font-mono">{{ b.id }}</span>
            <span class="inline-block text-[10px] font-bold px-2 py-0.5 rounded-badge border" :style="{ background: st.bg, color: st.fg, borderColor: st.bd }">{{ batchStatusLabel(state, locale) }}</span>
          </div>
          <div class="text-[12px] text-ink-3 mt-[5px]">{{ b.carrier }} · {{ b.date }} · {{ b.lineCount }} {{ L("orders","طلب","commandes") }} · {{ L("Ref","مرجع","Réf") }} {{ b.ref }}</div>
        </div>
        <div class="flex gap-2">
          <button v-if="state === 'draft'" class="h-[38px] px-[17px] rounded-[11px] text-white text-[13px] font-bold inline-flex items-center gap-1.5" style="background:linear-gradient(135deg,#0f766e,#0b5c4f)" @click="match">
            <Icon name="check" :size="15" />{{ L("Match batch","طابِق الدفعة","Rapprocher") }}
          </button>
          <button v-if="state === 'matched'" class="h-[38px] px-[17px] rounded-[11px] text-white text-[13px] font-bold inline-flex items-center gap-1.5" style="background:linear-gradient(135deg,#047857,#065f46)" @click="post">
            <Icon name="check" :size="15" />{{ L("Post to ledger","رحِّل للأستاذ","Passer au GL") }}
          </button>
          <span v-if="state === 'posted'" class="h-[38px] inline-flex items-center gap-1.5 text-[12.5px] font-semibold text-success-dark"><Icon name="check" :size="16" />{{ L("Posted","مُرحَّل","Passé") }}</span>
        </div>
      </div>

      <!-- Summary tiles -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-2.5 mt-[15px]">
        <div v-for="ti in tiles" :key="ti.label" class="rounded-[11px] px-[13px] py-[11px]" style="background:#fafaf9;border:1px solid #f0efed">
          <div class="text-[10.5px] text-ink-muted font-semibold">{{ ti.label }}</div>
          <div class="text-[18px] font-bold tnum mt-[3px]" :style="{ color: ti.color }">{{ ti.value }}</div>
        </div>
      </div>

      <!-- Variance warning -->
      <div v-if="b.variance" class="flex items-center gap-2.5 mt-3.5 px-3.5 py-[11px] rounded-[11px]" style="background:#fffbeb;border:1px solid #fde68a">
        <Icon name="alert" :size="15" color="#b45309" class="flex-shrink-0" />
        <span class="text-[12px] flex-1 leading-snug" style="color:#92400e">{{ varianceMsg(locale) }}</span>
        <span class="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-[3px] rounded-full flex-shrink-0" style="background:#f5f3ff;color:#7c3aed;border:1px solid #ddd6fe">
          <Icon name="shield" :size="11" />{{ L("Auditor","المدقّق","Auditeur") }}
        </span>
      </div>
    </div>

    <!-- Reconciliation lines -->
    <div class="bg-white rounded-[14px] border border-line shadow-card overflow-hidden">
      <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair">
        <span class="text-[12.5px] font-bold">{{ L("Reconciliation lines","سطور المطابقة","Lignes de rapprochement") }}</span>
        <span class="text-[11px] text-ink-muted">{{ matchedCount }} {{ L("matched","مطابق","rapprochés") }} · {{ varianceCount }} {{ L("variance","فرق","écart") }}</span>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead>
            <tr style="background:#fafaf9">
              <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Order","الطلب","Commande") }}</th>
              <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Expected","المتوقَّع","Attendu") }}</th>
              <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Collected","المُحصَّل","Collecté") }}</th>
              <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Fee","رسوم","Frais") }}</th>
              <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Variance","الفرق","Écart") }}</th>
              <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Match","المطابقة","Rappr.") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(ln, i) in lines" :key="i" class="border-t border-line-hair" :class="ln.variance ? 'bg-rose-50/30' : ''">
              <td class="px-4 py-2.5 font-mono font-semibold whitespace-nowrap">{{ ln.order }}</td>
              <td class="px-4 py-2.5 text-end tnum text-ink-3">{{ money(ln.expected) }}</td>
              <td class="px-4 py-2.5 text-end tnum font-semibold">{{ money(ln.collected) }}</td>
              <td class="px-4 py-2.5 text-end tnum text-sale">{{ ln.fee || "—" }}</td>
              <td class="px-4 py-2.5 text-end tnum font-bold" :class="ln.variance < 0 ? 'text-sale' : 'text-ink-3'">{{ ln.variance ? money(ln.variance) : "0" }}</td>
              <td class="px-4 py-2.5">
                <span class="inline-block text-[10px] font-bold px-2 py-0.5 rounded-badge border"
                      :style="{ background: LINE_MATCH[ln.match].bg, color: LINE_MATCH[ln.match].fg, borderColor: LINE_MATCH[ln.match].bd }">
                  {{ lineMatchLabel(ln.match, locale) }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
  <div v-else class="py-20 text-center text-[12px] text-ink-muted">{{ t("common.error_loading") }}</div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { findBatch, BATCH_STATUS, batchStatusLabel, money, LINE_MATCH, lineMatchLabel, reconLines, varianceMsg } from "@/data/banking";

const { t, locale } = useI18n();
const route = useRoute();
const router = useRouter();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

const b = computed(() => findBatch(route.query.id));
const state = ref(b.value?.status || "draft");
watch(b, (nb) => { state.value = nb?.status || "draft"; });

const st = computed(() => BATCH_STATUS[state.value] || BATCH_STATUS.draft);
const lines = computed(() => reconLines(b.value));
const matchedCount = computed(() => lines.value.filter((l) => l.match === "matched").length);
const varianceCount = computed(() => lines.value.filter((l) => l.variance).length);

const tiles = computed(() => b.value ? [
  { label: L("Carrier collected", "حصّله الناقل", "Collecté"), value: money(b.value.collected), color: "#1c1917" },
  { label: L("Fees", "الرسوم", "Frais"), value: "−" + money(b.value.fees), color: "#be123c" },
  { label: L("Net remitted", "الصافي المُحوَّل", "Net versé"), value: money(b.value.net), color: "#047857" },
  { label: L("Variance", "الفرق", "Écart"), value: b.value.variance ? money(b.value.variance) : "0", color: b.value.variance ? "#be123c" : "#047857" },
] : []);

function match() { state.value = "matched"; }
function post() { state.value = "posted"; }
function back() { router.push({ path: "/accounting/banking/remittance" }); }
</script>
