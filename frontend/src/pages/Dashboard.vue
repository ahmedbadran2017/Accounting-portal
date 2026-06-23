<template>
  <!-- Holding shows a genuine group rollup, not the Morocco COD cockpit. -->
  <Consolidated v-if="entityId === 'group'" />

  <div v-else class="space-y-3.5">
    <!-- Auditor digest banner -->
    <div class="rounded-card p-5 text-white relative overflow-hidden"
         style="background:linear-gradient(115deg,#1e1b3a,#2e1065 55%,#4c1d95)">
      <div class="flex items-center gap-2 mb-2.5">
        <span class="inline-flex items-center gap-1.5 text-[11px] font-semibold bg-white/15 px-2.5 py-1 rounded-full">
          <span class="w-1.5 h-1.5 rounded-full bg-violet-300 animate-pulse"></span>{{ t("dash.auditing") }}
        </span>
      </div>
      <p class="text-[13.5px] leading-relaxed text-violet-50/95 max-w-4xl">{{ vm.digest }}</p>
      <div class="flex flex-wrap items-center gap-2 mt-3.5">
        <button v-for="c in vm.digestChips" :key="c.label"
                class="inline-flex items-center gap-1.5 text-[11.5px] font-medium bg-white/10 hover:bg-white/20 px-2.5 py-1.5 rounded-chip"
                @click="goChip(c)">
          <span class="w-1.5 h-1.5 rounded-full" :style="{ background: c.dot }"></span>{{ c.label }}
        </button>
        <button class="inline-flex items-center gap-1.5 text-[11.5px] font-semibold bg-white text-violet-900 px-3 py-1.5 rounded-chip ms-auto"
                @click="goCopilot">
          {{ t("dash.open_auditor") }} <Icon name="chev" :size="14" />
        </button>
      </div>
    </div>

    <!-- Entity banner (non-Morocco) -->
    <div v-if="vm.entityBanner" class="rounded-card p-4 border" style="background:#fffbeb;border-color:#fde68a">
      <div class="flex flex-wrap items-center gap-x-6 gap-y-2">
        <div class="min-w-0">
          <div class="text-[13px] font-bold text-amber-900">{{ vm.entityBanner.name }} · {{ vm.entityBanner.ccy }}</div>
          <div class="text-[11.5px] text-amber-800/80 max-w-xl">{{ vm.entityBanner.role }}</div>
        </div>
        <div class="flex items-center gap-5 ms-auto">
          <div v-for="f in vm.entityBanner.figs" :key="f.label" class="leading-tight">
            <div class="text-[10px] text-amber-700/80 uppercase tracking-wide">{{ f.label }}</div>
            <div class="text-[14px] font-bold text-amber-900 tnum">{{ f.value }}</div>
          </div>
        </div>
      </div>
      <div class="text-[11px] text-amber-800/70 mt-2 pt-2 border-t border-amber-200">{{ vm.entityBanner.note }}</div>
    </div>

    <!-- KPI row -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
      <div v-for="k in vm.kpis" :key="k.label" class="yo-card bg-white rounded-card border border-line p-4">
        <div class="flex items-start justify-between mb-3">
          <span class="w-8 h-8 rounded-[9px] grid place-items-center" :style="{ background: k.ibg }">
            <Icon :name="k.icon" :size="15" :color="k.ic" />
          </span>
        </div>
        <div class="text-[22px] font-bold tracking-tight tnum">
          {{ k.value }}<span class="text-[13px] text-ink-3 font-semibold ms-0.5">{{ k.unit }}</span>
        </div>
        <div class="text-[11.5px] text-ink-3 mt-0.5">{{ k.label }}</div>
        <div class="text-[10.5px] text-ink-muted mt-1.5">{{ k.sub }}</div>
      </div>
    </div>

    <!-- Cash flow + Collection by channel -->
    <div class="grid lg:grid-cols-3 gap-3.5">
      <!-- Cash flow chart -->
      <div class="lg:col-span-2 bg-white rounded-card border border-line p-4">
        <div class="flex items-start justify-between mb-3">
          <div>
            <div class="text-[13px] font-bold">{{ vm.cashflow.title }}</div>
            <div class="text-[11px] text-ink-muted">{{ vm.cashflow.sub }}</div>
          </div>
          <div class="flex items-center gap-3 text-[10.5px]">
            <span class="inline-flex items-center gap-1.5"><span class="w-2 h-2 rounded-sm" style="background:#059669"></span>{{ vm.cashflow.inLbl }}</span>
            <span class="inline-flex items-center gap-1.5"><span class="w-2 h-2 rounded-sm" style="background:#f59e0b"></span>{{ vm.cashflow.outLbl }}</span>
          </div>
        </div>
        <div class="flex items-end gap-[5px] h-[84px] mb-2">
          <div v-for="d in vm.cashflow.days" :key="d.d" class="flex-1 flex items-end justify-center gap-[2px]" :title="d.title">
            <div class="w-1/2 rounded-t-[2px] origin-bottom animate-barGrow" :style="{ height: d.inH + 'px', background: 'linear-gradient(180deg,#34d399,#059669)' }"></div>
            <div class="w-1/2 rounded-t-[2px] origin-bottom animate-barGrow" :style="{ height: d.outH + 'px', background: 'linear-gradient(180deg,#fcd34d,#f59e0b)' }"></div>
          </div>
        </div>
        <div class="flex items-center justify-between pt-2.5 border-t border-line text-[11.5px]">
          <span class="text-success-dark font-semibold tnum">+ {{ vm.cashflow.totalIn }}</span>
          <span class="text-amber-600 font-semibold tnum">− {{ vm.cashflow.totalOut }}</span>
          <span class="font-bold tnum">{{ t("dash.net") }} {{ vm.cashflow.net }}</span>
        </div>
      </div>

      <!-- Collection by channel -->
      <div class="bg-white rounded-card border border-line p-4">
        <div class="text-[13px] font-bold">{{ vm.channelMeta.title }}</div>
        <div class="text-[11px] text-ink-muted mb-3">{{ vm.channelMeta.sub }}</div>
        <div class="space-y-3">
          <div v-for="c in vm.channels" :key="c.name">
            <div class="flex items-center justify-between text-[11.5px] mb-1">
              <span class="font-medium truncate flex items-center gap-1">
                <Icon v-if="c.warn" name="alert" :size="12" color="#b45309" />{{ c.name }}
              </span>
              <span class="text-ink-3 tnum">{{ c.share }}%</span>
            </div>
            <div class="h-2 rounded-full bg-app-warm overflow-hidden">
              <div class="h-full rounded-full animate-barGrow origin-left" :style="{ width: Math.max(c.share, 2.5) + '%', background: c.bar }"></div>
            </div>
            <div class="text-[10px] text-ink-muted mt-0.5 tnum">{{ c.sub }} · {{ c.amount }}</div>
          </div>
        </div>
        <div class="mt-3 pt-2.5 border-t border-line text-[10.5px] text-amber-700 leading-snug flex gap-1.5">
          <Icon name="alert" :size="13" color="#b45309" class="flex-shrink-0 mt-px" />{{ vm.channelMeta.warn }}
        </div>
      </div>
    </div>

    <!-- Working capital -->
    <div class="bg-white rounded-card border border-line p-4">
      <div class="flex items-center justify-between mb-3">
        <div>
          <div class="text-[13px] font-bold">{{ vm.arap.title }}</div>
          <div class="text-[11px] text-ink-muted">{{ vm.arap.sub }}</div>
        </div>
      </div>
      <div class="grid sm:grid-cols-2 gap-3.5">
        <div class="rounded-card border border-rose-100 bg-rose-50/40 p-4">
          <div class="flex items-center justify-between">
            <span class="text-[11.5px] font-semibold text-ink-2">{{ vm.arap.arLabel }}</span>
            <span class="text-[10px] text-ink-muted tnum">{{ vm.arap.arRows }} rows</span>
          </div>
          <div class="text-[24px] font-bold text-sale tnum mt-1">{{ vm.arap.arVal }}</div>
          <div class="text-[10.5px] text-rose-700/80 mt-1.5 leading-snug">{{ vm.arap.arNote }}</div>
        </div>
        <div class="rounded-card border border-line-2 bg-app-warm/50 p-4">
          <div class="flex items-center justify-between">
            <span class="text-[11.5px] font-semibold text-ink-2">{{ vm.arap.apLabel }}</span>
            <span class="text-[10px] text-ink-muted tnum">{{ vm.arap.apRows }} rows</span>
          </div>
          <div class="text-[24px] font-bold text-ink tnum mt-1">{{ vm.arap.apVal }}</div>
          <div class="text-[10.5px] text-ink-3 mt-1.5 leading-snug">{{ vm.arap.apNote }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import Consolidated from "@/pages/Consolidated.vue";
import { useUi } from "@/composables/useUi";
import { buildDashVM } from "@/data/dashboard";

const { t, locale } = useI18n();
const router = useRouter();
const { entityId } = useUi();

const vm = computed(() => buildDashVM(locale.value, entityId.value));

function go(g) {
  if (!g) return;
  router.push(g.sub ? `/accounting/${g.module}/${g.sub}` : `/accounting/${g.module}`);
}
const goChip = (c) => go(c.go);
const goCopilot = () => router.push("/accounting/copilot");
</script>
