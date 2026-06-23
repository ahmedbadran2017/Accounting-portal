<template>
  <div class="space-y-3.5">
    <!-- Group digest banner -->
    <div class="rounded-card p-5 text-white" style="background:linear-gradient(115deg,#1e1b3a,#3b2566 55%,#6d28d9)">
      <div class="flex items-center gap-2 mb-2.5">
        <Icon name="layers" :size="17" color="#e9d5ff" />
        <span class="text-[13px] font-bold">{{ L("Consolidated · Justyol Holding", "موحَّد · Justyol Holding", "Consolidé · Justyol Holding") }}</span>
        <span class="inline-flex items-center gap-1.5 text-[11px] font-semibold bg-white/15 px-2.5 py-1 rounded-full ms-1">USD</span>
      </div>
      <p class="text-[13px] leading-relaxed text-violet-50/95 max-w-4xl">{{ vm.digest }}</p>
    </div>

    <!-- Group KPI row -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
      <div v-for="k in vm.kpis" :key="k.label" class="yo-card bg-white rounded-card border border-line p-4">
        <div class="flex items-start justify-between mb-3">
          <span class="w-8 h-8 rounded-[9px] grid place-items-center" :style="{ background: k.ibg }">
            <Icon :name="k.icon" :size="15" :color="k.ic" />
          </span>
        </div>
        <div class="text-[22px] font-bold tracking-tight tnum">{{ k.value }}</div>
        <div class="text-[11.5px] text-ink-3 mt-0.5">{{ k.label }}</div>
        <div class="text-[10.5px] text-ink-muted mt-1.5">{{ k.sub }}</div>
      </div>
    </div>

    <!-- Per-entity contribution -->
    <div class="grid lg:grid-cols-3 gap-3.5">
      <div v-for="e in vm.rows" :key="e.id" class="bg-white rounded-card border border-line p-4">
        <div class="flex items-center gap-2.5 mb-3">
          <span class="w-8 h-8 rounded-lg grid place-items-center text-white text-[10px] font-bold" :style="{ background: e.badge }">{{ e.code }}</span>
          <div class="min-w-0">
            <div class="text-[13px] font-bold truncate flex items-center gap-1.5">
              {{ e.name }}
              <span v-if="e.interco" class="text-[9px] font-bold px-1.5 py-0.5 rounded-badge"
                    style="background:#faf5ff;color:#7c3aed;border:1px solid #e9d5ff">{{ L("Intercompany", "بين الشركات", "Intra-groupe") }}</span>
            </div>
            <div class="text-[10.5px] text-ink-muted">{{ e.role }} · {{ e.ccy }}</div>
          </div>
        </div>
        <div class="grid grid-cols-2 gap-2 text-start">
          <div class="rounded-lg bg-app-warm/60 p-2.5">
            <div class="text-[10px] text-ink-muted">{{ L("Payables", "دائنون", "Dettes") }}</div>
            <div class="text-[15px] font-bold tnum">{{ e.payUsdLabel }}</div>
            <div class="text-[10px] text-ink-muted tnum">{{ e.payLabel }}</div>
          </div>
          <div class="rounded-lg bg-app-warm/60 p-2.5">
            <div class="text-[10px] text-ink-muted">{{ L("Cash", "نقد", "Trésorerie") }}</div>
            <div class="text-[15px] font-bold tnum">{{ e.cashUsdLabel }}</div>
            <div v-if="e.spendLabel" class="text-[10px] text-ink-muted tnum">{{ L("Spend YTD", "الإنفاق", "Dépense") }} {{ e.spendLabel }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Group payables by entity -->
    <div class="bg-white rounded-card border border-line p-4">
      <div class="text-[13px] font-bold">{{ L("Group payables by entity", "دائنو المجموعة حسب الكيان", "Dettes du groupe par entité") }}</div>
      <div class="text-[11px] text-ink-muted mb-3">{{ L("USD base · total", "أساس الدولار · الإجمالي", "Base USD · total") }} {{ vm.groupPayLabel }}</div>
      <div class="flex h-3 rounded-full overflow-hidden bg-app-warm">
        <div v-for="e in vm.rows" :key="e.id" class="h-full" :style="{ width: e.payShare + '%', background: e.badge }" :title="`${e.name} · ${e.payUsdLabel}`"></div>
      </div>
      <div class="flex flex-wrap gap-x-5 gap-y-1 mt-3">
        <div v-for="e in vm.rows" :key="e.id" class="flex items-center gap-1.5 text-[11px]">
          <span class="w-2.5 h-2.5 rounded-sm" :style="{ background: e.badge }"></span>
          <span class="font-medium">{{ e.name }}</span>
          <span class="text-ink-muted tnum">{{ e.payUsdLabel }} · {{ Math.round(e.payShare) }}%</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { buildConsolVM } from "@/data/consolidated";

const { locale } = useI18n();
const vm = computed(() => buildConsolVM(locale.value));
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
</script>
