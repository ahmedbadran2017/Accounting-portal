<template>
  <div v-if="b" class="space-y-3.5">
    <button class="inline-flex items-center gap-1.5 text-[12px] font-medium text-ink-3 hover:text-ink" @click="back">
      <span class="rtl:rotate-180"><Icon name="arrow" :size="15" /></span>{{ L("Back to remittance","العودة للتحصيل","Retour aux encaissements") }}
    </button>

    <!-- Header -->
    <div class="bg-white rounded-card border border-line p-5">
      <div class="flex flex-wrap items-start gap-3">
        <span class="w-11 h-11 rounded-card grid place-items-center" style="background:#fff7ed"><Icon name="truck" :size="20" color="#c2410c" /></span>
        <div class="min-w-0">
          <div class="text-[17px] font-bold tracking-tight font-mono">{{ b.id }}</div>
          <div class="text-[12.5px] text-ink-3">{{ b.carrier }} · {{ b.date }} · {{ b.ref }} · {{ b.lineCount }} {{ L("orders","طلب","commandes") }}</div>
        </div>
        <span class="ms-auto inline-block text-[10px] font-bold px-2 py-0.5 rounded-badge border h-fit"
              :style="{ background: st.bg, color: st.fg, borderColor: st.bd }">{{ batchStatusLabel(state, locale) }}</span>
      </div>
    </div>

    <!-- Reconciliation figures -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
      <div class="bg-white rounded-card border border-line p-4">
        <div class="text-[10px] text-ink-muted uppercase tracking-wide">{{ L("Carrier collected","حصّله الناقل","Collecté transporteur") }}</div>
        <div class="text-[19px] font-bold tnum mt-1">{{ money(b.collected) }}</div>
      </div>
      <div class="bg-white rounded-card border border-line p-4">
        <div class="text-[10px] text-ink-muted uppercase tracking-wide">{{ L("Fees","الرسوم","Frais") }}</div>
        <div class="text-[19px] font-bold tnum text-sale mt-1">−{{ money(b.fees) }}</div>
      </div>
      <div class="bg-white rounded-card border border-line p-4">
        <div class="text-[10px] text-ink-muted uppercase tracking-wide">{{ L("Net remitted","الصافي المُحوَّل","Net versé") }}</div>
        <div class="text-[19px] font-bold tnum text-success-dark mt-1">{{ money(b.net) }}</div>
      </div>
      <div class="rounded-card border p-4" :style="varStyle">
        <div class="text-[10px] uppercase tracking-wide" :style="{ color: varColor }">{{ L("Variance","الفرق","Écart") }}</div>
        <div class="text-[19px] font-bold tnum mt-1" :style="{ color: varColor }">{{ b.variance ? money(b.variance) : "0" }}</div>
      </div>
    </div>

    <!-- Match flow -->
    <div class="bg-white rounded-card border border-line p-4">
      <div class="text-[13px] font-bold mb-3">{{ L("Reconciliation","المطابقة","Rapprochement") }}</div>
      <div class="flex items-center gap-2 text-[12px]">
        <div class="flex-1 rounded-lg bg-app-warm/60 p-3 text-center">
          <div class="text-[10px] text-ink-muted">{{ L("Expected (orders)","المتوقَّع (طلبات)","Attendu (commandes)") }}</div>
          <!-- variance = collected − expected ⇒ expected = collected − variance -->
          <div class="text-[15px] font-bold tnum">{{ money(b.collected - b.variance) }}</div>
        </div>
        <Icon name="arrow" :size="18" color="#a8a29e" class="rtl:rotate-180" />
        <div class="flex-1 rounded-lg bg-app-warm/60 p-3 text-center">
          <div class="text-[10px] text-ink-muted">{{ L("Carrier collected","حصّله الناقل","Collecté") }}</div>
          <div class="text-[15px] font-bold tnum">{{ money(b.collected) }}</div>
        </div>
        <Icon name="arrow" :size="18" color="#a8a29e" class="rtl:rotate-180" />
        <div class="flex-1 rounded-lg p-3 text-center" :style="varStyle">
          <div class="text-[10px]" :style="{ color: varColor }">{{ b.variance ? L("Variance → queue","فرق ← الطابور","Écart → file") : L("Balanced","متوازن","Équilibré") }}</div>
          <div class="text-[15px] font-bold tnum" :style="{ color: varColor }">{{ b.variance ? money(b.variance) : "✓" }}</div>
        </div>
      </div>

      <div v-if="b.variance" class="mt-3 text-[11px] text-amber-700 flex items-start gap-1.5">
        <Icon name="alert" :size="13" color="#b45309" class="flex-shrink-0 mt-px" />
        {{ L("Collected is short of what the orders expected — post the matched portion and send the variance to the variance queue for investigation.",
              "المُحصَّل أقل مما تتوقعه الطلبات — رحِّل الجزء المطابق وأرسل الفرق لطابور الفروق للمراجعة.",
              "Le collecté est inférieur à l’attendu — passez la partie rapprochée et envoyez l’écart à la file des écarts.") }}
      </div>

      <div class="flex items-center gap-2 mt-4 pt-3 border-t border-line">
        <button v-if="state === 'draft'" class="inline-flex items-center gap-1.5 text-[12px] font-semibold text-white bg-accent hover:bg-accent-dark px-3 py-2 rounded-chip shadow-prim" @click="match">
          <Icon name="check" :size="14" />{{ L("Match batch","طابِق الدفعة","Rapprocher") }}
        </button>
        <button v-if="state === 'matched'" class="inline-flex items-center gap-1.5 text-[12px] font-semibold text-white bg-success-dark hover:opacity-90 px-3 py-2 rounded-chip" @click="post">
          <Icon name="ledger" :size="14" />{{ L("Post to ledger","رحِّل للأستاذ","Passer au grand livre") }}
        </button>
        <span v-if="state === 'posted'" class="inline-flex items-center gap-1.5 text-[12px] font-semibold text-success-dark">
          <Icon name="check" :size="15" />{{ L("Posted to ledger","مُرحَّل للأستاذ","Passé au grand livre") }}
        </span>
      </div>
    </div>

    <!-- Posted journal (shown once posted) -->
    <div v-if="state === 'posted'" class="bg-white rounded-card border border-line overflow-hidden animate-fadeIn">
      <div class="px-4 py-3 border-b border-line flex items-center gap-2"><Icon name="ledger" :size="15" color="#a33a22" /><span class="text-[13px] font-bold">{{ L("Posted journal","القيد المُرحَّل","Écriture passée") }}</span></div>
      <table class="w-full text-[12px]">
        <tbody>
          <tr v-for="(j, i) in journal" :key="i" class="border-b border-line-hair">
            <td class="px-4 py-2.5 font-mono text-ink-2">{{ j.acc }}</td>
            <td class="px-4 py-2.5 text-end tnum font-semibold">{{ j.dr || "—" }}</td>
            <td class="px-4 py-2.5 text-end tnum font-semibold">{{ j.cr || "—" }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
  <div v-else class="py-20 text-center text-[12px] text-ink-muted">{{ t("common.error_loading") }}</div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { findBatch, BATCH_STATUS, batchStatusLabel, money } from "@/data/banking";

const { t, locale } = useI18n();
const route = useRoute();
const router = useRouter();

const b = computed(() => findBatch(route.query.id));
// Local reconciliation state machine (draft → matched → posted), seeded from data.
const state = ref(b.value?.status || "draft");
watch(b, (nb) => { state.value = nb?.status || "draft"; });

const st = computed(() => BATCH_STATUS[state.value] || BATCH_STATUS.draft);
const varColor = computed(() => (b.value?.variance ? "#be123c" : "#047857"));
const varStyle = computed(() => (b.value?.variance ? { background: "#fef2f2", borderColor: "#fecaca" } : { background: "#ecfdf5", borderColor: "#a7f3d0" }));
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

const journal = computed(() => {
  if (!b.value) return [];
  return [
    { acc: "102.02.01.01 BMCE Bank", dr: money(b.value.net), cr: "" },
    { acc: "108.021.003 COD fees", dr: money(b.value.fees), cr: "" },
    { acc: "108.021.003 Carrier clearing", dr: "", cr: money(b.value.collected) },
  ];
});

function match() { state.value = "matched"; }
function post() { state.value = "posted"; }
function back() { router.push({ path: "/accounting/banking/remittance" }); }
</script>
