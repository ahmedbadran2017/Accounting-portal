<template>
  <div v-if="o" class="space-y-3.5">
    <!-- Back + header -->
    <button class="inline-flex items-center gap-1.5 text-[12px] font-medium text-ink-3 hover:text-ink" @click="back">
      <span class="rtl:rotate-180"><Icon name="arrow" :size="15" /></span>{{ backLabel }}
    </button>

    <div class="bg-white rounded-card border border-line p-5">
      <div class="flex flex-wrap items-start gap-3">
        <span class="w-11 h-11 rounded-card grid place-items-center text-white text-[13px] font-bold flex-shrink-0"
              :style="{ background: AV[o.av] }">{{ o.initials }}</span>
        <div class="min-w-0">
          <div class="text-[17px] font-bold tracking-tight font-mono">{{ o.id }}</div>
          <div class="text-[12.5px] text-ink-3">{{ o.customer }} · {{ o.date }}</div>
        </div>
        <div class="ms-auto text-end">
          <div class="text-[22px] font-bold tnum">{{ o.value }} <span class="text-[13px] text-ink-3">MAD</span></div>
          <span class="inline-block text-[10px] font-bold px-2 py-0.5 rounded-badge border mt-1"
                :style="{ background: sm.bg, color: sm.fg, borderColor: sm.bd }">{{ stateLabel(o.state, locale) }}</span>
        </div>
      </div>

      <!-- State machine -->
      <div class="flex items-center gap-1 mt-5 overflow-x-auto pb-1">
        <template v-for="(st, i) in MACHINE" :key="st">
          <div class="flex flex-col items-center gap-1 min-w-[64px]">
            <div class="w-7 h-7 rounded-full grid place-items-center text-[11px] font-bold"
                 :class="i <= activeStep ? 'text-white' : 'text-ink-muted bg-app-warm'"
                 :style="i <= activeStep ? { background: STATE_META[st].c } : {}">
              <Icon v-if="i < activeStep" name="check" :size="14" color="#fff" />
              <span v-else>{{ i + 1 }}</span>
            </div>
            <span class="text-[10px] font-medium" :class="i <= activeStep ? 'text-ink-2' : 'text-ink-muted'">{{ stateLabel(st, locale) }}</span>
          </div>
          <div v-if="i < MACHINE.length - 1" class="h-0.5 flex-1 min-w-[16px] rounded"
               :class="i < activeStep ? 'bg-success' : 'bg-line-2'"></div>
        </template>
      </div>
    </div>

    <!-- Operational chips -->
    <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2.5">
      <div v-for="op in opChips" :key="op.label" class="bg-white rounded-card border border-line p-3">
        <div class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ op.label }}</div>
        <div class="text-[13px] font-semibold mt-1 truncate">{{ op.value }}</div>
      </div>
    </div>

    <!-- Auto-posted journal -->
    <div class="bg-white rounded-card border border-line overflow-hidden">
      <div class="px-4 py-3 border-b border-line flex items-center gap-2">
        <Icon name="ledger" :size="15" color="#a33a22" />
        <span class="text-[13px] font-bold">{{ jTitle }}</span>
      </div>
      <table v-if="journal.lines.length" class="w-full text-[12px]">
        <thead>
          <tr class="border-b border-line">
            <th class="px-4 py-2 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ accLabel }}</th>
            <th class="px-4 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ drLabel }}</th>
            <th class="px-4 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ crLabel }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(j, i) in journal.lines" :key="i" class="border-b border-line-hair">
            <td class="px-4 py-2.5 font-mono text-ink-2">{{ j.acc }}</td>
            <td class="px-4 py-2.5 text-end tnum font-semibold">{{ j.dr || "—" }}</td>
            <td class="px-4 py-2.5 text-end tnum font-semibold">{{ j.cr || "—" }}</td>
          </tr>
        </tbody>
      </table>
      <div class="px-4 py-3 text-[11px] text-ink-3 bg-app-warm/50 flex items-start gap-1.5">
        <Icon name="spark" :size="13" color="#a33a22" class="flex-shrink-0 mt-px" />{{ journal.note }}
      </div>
    </div>
  </div>

  <div v-else class="py-20 text-center text-[12px] text-ink-muted">{{ t("common.error_loading") }}</div>
</template>

<script setup>
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { findOrder, orderJournal, STATE_META, stateLabel, MACHINE, AV } from "@/data/orders";
import { useCreated } from "@/composables/useCreated";

const { t, locale } = useI18n();
const route = useRoute();
const router = useRouter();
const { findCreatedOrder } = useCreated();

const o = computed(() => findCreatedOrder(route.query.id) || findOrder(route.query.id));
const sm = computed(() => STATE_META[o.value?.state] || STATE_META.placed);
const journal = computed(() => orderJournal(o.value, locale.value));

// Active step: cancelled stalls at Placed; undelivered counts as transit.
const activeStep = computed(() => {
  if (!o.value) return 0;
  const map = { placed: 0, confirmed: 1, transit: 2, undelivered: 2, delivered: 3, settled: 4, cancelled: 0 };
  return map[o.value.state] ?? 0;
});

const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const backLabel = computed(() => L("Back to orders", "العودة للطلبات", "Retour aux commandes"));
const jTitle = computed(() => L("Auto-posted journal", "القيد المُرحَّل تلقائياً", "Écriture passée"));
const accLabel = computed(() => L("Account", "الحساب", "Compte"));
const drLabel = computed(() => L("Debit", "مدين", "Débit"));
const crLabel = computed(() => L("Credit", "دائن", "Crédit"));

const opChips = computed(() => o.value ? [
  { label: L("Confirmation", "التأكيد", "Confirmation"), value: o.value.salesStatus },
  { label: L("Logistics", "اللوجستيك", "Logistique"), value: o.value.logiStatus },
  { label: L("Tracking", "التتبّع", "Suivi"), value: o.value.trackStatus },
  { label: L("Carrier", "الناقل", "Transporteur"), value: o.value.carrier },
  { label: L("City", "المدينة", "Ville"), value: o.value.city },
] : []);

function back() { router.push({ path: "/accounting/sales/orders" }); }
</script>
