<template>
  <!-- Holding shows a genuine group rollup, not the Morocco COD cockpit. -->
  <Consolidated v-if="entityId === 'group'" />

  <div v-else class="space-y-3.5">
    <!-- Entity banner (non-Morocco) — shown first to set context -->
    <div v-if="vm.entityBanner" class="rounded-[14px] p-4 border" style="background:#fffbeb;border-color:#fde68a">
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

    <!-- Auditor digest banner -->
    <div class="rounded-[18px] px-5 py-[18px] text-white relative overflow-hidden"
         style="background:linear-gradient(115deg,#1e1b3a 0%,#2e1065 55%,#4c1d95 100%);box-shadow:0 14px 40px -16px rgba(76,29,149,.5)">
      <div class="absolute inset-0" style="background:radial-gradient(60% 120% at 88% -10%,rgba(167,139,250,.35),transparent 60%)"></div>
      <div class="relative flex items-start gap-3.5 flex-wrap">
        <span class="w-10 h-10 rounded-[11px] grid place-items-center flex-shrink-0"
              style="background:rgba(255,255,255,.13);border:1px solid rgba(255,255,255,.18)"><Icon name="shield" :size="20" color="#fff" /></span>
        <div class="flex-1 min-w-[240px]">
          <div class="flex items-center gap-2 flex-wrap">
            <span class="text-[14.5px] font-bold">{{ t("dash.auditor_name") }}</span>
            <span class="inline-flex items-center gap-1.5 text-[10px] font-bold px-2 py-0.5 rounded-full" style="background:rgba(167,139,250,.25);color:#ddd6fe">
              <span class="w-[5px] h-[5px] rounded-full bg-violet-400 animate-pulse"></span>{{ t("dash.auditing") }}
            </span>
            <span v-if="isLive" class="inline-flex items-center gap-1.5 text-[10px] font-bold px-2 py-0.5 rounded-full" style="background:rgba(52,211,153,.22);color:#a7f3d0">
              <span class="w-[5px] h-[5px] rounded-full bg-emerald-400"></span>Live{{ asOf ? " · " + asOf : "" }}
            </span>
          </div>
          <p class="text-[13px] mt-1.5 leading-relaxed max-w-2xl" style="color:#e9e3ff">{{ vm.digest }}</p>
        </div>
        <button class="h-9 px-4 rounded-[10px] bg-white text-[12.5px] font-bold inline-flex items-center gap-1.5"
                style="color:#5b21b6;box-shadow:0 4px 14px -4px rgba(0,0,0,.4)" @click="goCopilot">
          {{ t("dash.open_auditor") }}<Icon name="arrow" :size="14" class="rtl:rotate-180" />
        </button>
      </div>
      <div class="relative flex flex-wrap gap-2.5 mt-3.5">
        <button v-for="c in vm.digestChips" :key="c.label"
                class="inline-flex items-center gap-2 px-[11px] py-[7px] rounded-[10px] text-[11.5px] font-semibold text-start"
                style="background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.14)" @click="goChip(c)">
          <span class="w-1.5 h-1.5 rounded-full flex-shrink-0" :style="{ background: c.dot }"></span>{{ c.label }}
        </button>
      </div>
    </div>

    <!-- KPI row -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <div v-for="k in vm.kpis" :key="k.label" class="yo-card bg-white rounded-[14px] border border-line p-4 shadow-card">
        <div class="flex items-center justify-between">
          <span class="text-[11.5px] font-semibold text-ink-3">{{ k.label }}</span>
          <span class="w-7 h-7 rounded-[8px] grid place-items-center" :style="{ background: k.ibg }"><Icon :name="k.icon" :size="15" :color="k.ic" /></span>
        </div>
        <div class="text-[24px] font-bold tracking-tight tnum mt-2">
          {{ k.value }}<span class="text-[13px] text-ink-muted font-semibold ms-0.5">{{ k.unit }}</span>
        </div>
        <div class="text-[10.5px] text-ink-muted mt-1.5">{{ k.sub }}</div>
      </div>
    </div>

    <!-- Cash flow + Collection by channel -->
    <div class="grid lg:grid-cols-[1.5fr_1fr] gap-3.5">
      <!-- Cash flow chart -->
      <div class="bg-white rounded-[14px] border border-line p-[17px] shadow-card">
        <div class="flex items-baseline justify-between gap-2.5 flex-wrap">
          <div>
            <div class="text-[13.5px] font-bold">{{ vm.cashflow.title }}</div>
            <div class="text-[11px] text-ink-muted">{{ vm.cashflow.sub }}</div>
          </div>
          <div class="flex items-center gap-3 text-[11px] text-ink-2">
            <span class="inline-flex items-center gap-1.5"><span class="w-[9px] h-[9px] rounded-[3px]" style="background:#10b981"></span>{{ vm.cashflow.inLbl }}</span>
            <span class="inline-flex items-center gap-1.5"><span class="w-[9px] h-[9px] rounded-[3px]" style="background:#f59e0b"></span>{{ vm.cashflow.outLbl }}</span>
          </div>
        </div>
        <div class="flex items-end gap-[3px] h-20 mt-[18px]">
          <div v-for="d in vm.cashflow.days" :key="d.d" class="flex-1 flex flex-col justify-end gap-[2px] h-full" :title="d.title">
            <div class="rounded-t-[2px] origin-bottom animate-barGrow" :style="{ height: d.inH + 'px', background: 'linear-gradient(180deg,#34d399,#059669)' }"></div>
            <div class="rounded-b-[2px] origin-bottom animate-barGrow" :style="{ height: d.outH + 'px', background: 'linear-gradient(180deg,#fcd34d,#f59e0b)' }"></div>
          </div>
        </div>
        <div class="flex gap-6 mt-3.5 pt-3 border-t border-line-hair">
          <div>
            <div class="text-[10px] font-semibold text-ink-muted">{{ vm.cashflow.inLbl }}</div>
            <div class="text-[18px] font-bold text-success-dark tnum mt-px">{{ vm.cashflow.totalIn }}<span class="text-[11px] text-ink-muted ms-0.5">MAD</span></div>
          </div>
          <div>
            <div class="text-[10px] font-semibold text-ink-muted">{{ vm.cashflow.outLbl }}</div>
            <div class="text-[18px] font-bold text-amber-700 tnum mt-px">{{ vm.cashflow.totalOut }}</div>
          </div>
          <div>
            <div class="text-[10px] font-semibold text-ink-muted">{{ t("dash.net") }}</div>
            <div class="text-[18px] font-bold text-info tnum mt-px">{{ vm.cashflow.net }}</div>
          </div>
        </div>
      </div>

      <!-- Collection by channel -->
      <div class="bg-white rounded-[14px] border border-line p-[17px] shadow-card">
        <div class="text-[13.5px] font-bold">{{ vm.channelMeta.title }}</div>
        <div class="text-[11px] text-ink-muted">{{ vm.channelMeta.sub }}</div>
        <div class="flex flex-col gap-3 mt-[15px]">
          <div v-for="c in vm.channels" :key="c.name">
            <div class="flex items-center justify-between mb-1">
              <span class="inline-flex items-center gap-1.5 text-[12px] font-semibold text-ink-2 truncate">
                {{ c.name }}<Icon v-if="c.warn" name="alert" :size="12" color="#d97706" />
              </span>
              <span class="text-[11.5px] font-bold text-ink tnum">{{ c.share }}%</span>
            </div>
            <div class="h-[7px] rounded-[5px] bg-line-hair overflow-hidden">
              <div class="h-full rounded-[5px] animate-barGrow origin-left" :style="{ width: Math.max(c.share, 2.5) + '%', background: c.bar }"></div>
            </div>
            <div class="text-[10px] text-ink-muted mt-[3px] font-mono tnum">{{ c.sub }} · {{ c.amount }} MAD</div>
          </div>
        </div>
        <div class="flex gap-2 mt-3.5 px-3 py-2.5 rounded-[10px]" style="background:#fffbeb;border:1px solid #fde68a">
          <Icon name="alert" :size="13" color="#b45309" class="flex-shrink-0 mt-px" />
          <span class="text-[11px] leading-snug" style="color:#92400e">{{ vm.channelMeta.warn }}</span>
        </div>
      </div>
    </div>

    <!-- Working capital -->
    <div class="grid sm:grid-cols-2 gap-3.5">
      <div class="bg-white rounded-[14px] border border-line p-[17px] shadow-card">
        <div class="flex items-center gap-2">
          <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#fff1f2"><Icon name="wallet" :size="14" color="#be123c" /></span>
          <span class="text-[13px] font-bold">{{ vm.arap.arLabel }}</span>
          <span class="text-[10.5px] text-ink-muted ms-auto">{{ vm.arap.arRows }} {{ t("dash.lines") }}</span>
        </div>
        <div class="text-[26px] font-bold text-sale tnum mt-2.5 tracking-tight">{{ vm.arap.arVal }}<span class="text-[12px] text-ink-muted ms-1">MAD</span></div>
        <div class="flex gap-2 mt-2.5 px-3 py-2.5 rounded-[10px]" style="background:#fef2f2;border:1px solid #fecaca">
          <Icon name="alert" :size="13" color="#be123c" class="flex-shrink-0 mt-px" />
          <span class="text-[11px] leading-snug" style="color:#991b1b">{{ vm.arap.arNote }}</span>
        </div>
      </div>
      <div class="bg-white rounded-[14px] border border-line p-[17px] shadow-card">
        <div class="flex items-center gap-2">
          <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#fff4e0"><Icon name="bank" :size="14" color="#b45309" /></span>
          <span class="text-[13px] font-bold">{{ vm.arap.apLabel }}</span>
          <span class="text-[10.5px] text-ink-muted ms-auto">{{ vm.arap.apRows }} {{ t("dash.lines") }}</span>
        </div>
        <div class="text-[26px] font-bold text-ink tnum mt-2.5 tracking-tight">{{ vm.arap.apVal }}<span class="text-[12px] text-ink-muted ms-1">MAD</span></div>
        <div class="text-[11.5px] text-ink-3 mt-3.5 leading-snug">{{ vm.arap.apNote }}</div>
      </div>
    </div>

    <!-- Anomalies feed -->
    <div class="bg-white rounded-[14px] border border-line p-[17px] shadow-card">
      <div class="flex items-center gap-2.5">
        <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#f5f3ff"><Icon name="shield" :size="14" color="#7c3aed" /></span>
        <div class="flex-1">
          <div class="text-[13.5px] font-bold">{{ t("dash.flagged_title") }}</div>
          <div class="text-[11px] text-ink-muted">{{ t("dash.flagged_sub") }}</div>
        </div>
        <button class="text-[11px] font-semibold text-accent-dark hover:underline" @click="goCopilot">{{ t("dash.view_all") }} →</button>
      </div>
      <div class="flex flex-col gap-2 mt-3">
        <button v-for="a in anomalies" :key="a.id"
                class="yo-row flex items-center gap-3 px-3 py-[11px] rounded-[11px] border border-line text-start w-full hover:bg-app-warm/60"
                style="background:#fdfcfb" @click="go(a.go)">
          <span class="w-[30px] h-[30px] rounded-[8px] grid place-items-center flex-shrink-0" :style="{ background: sev(a).bg }"><Icon :name="a.icon" :size="15" :color="sev(a).fg" /></span>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <span class="text-[12.5px] font-bold">{{ a.title(locale) }}</span>
              <span class="text-[9px] font-bold px-1.5 py-0.5 rounded-badge border" :style="{ background: sev(a).bg, color: sev(a).fg, borderColor: sev(a).bd }">{{ sevLabel(a.sev, locale) }}</span>
            </div>
            <div class="text-[11.5px] text-ink-3 mt-0.5 truncate">{{ a.desc(locale) }}</div>
          </div>
          <span v-if="a.amount" class="text-[12px] font-bold tnum flex-shrink-0" :class="a.amount.includes('-') ? 'text-sale' : ''">{{ a.amount }}</span>
          <Icon name="chev" :size="15" color="#cfc9c4" class="rtl:rotate-180 flex-shrink-0" />
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import Consolidated from "@/pages/Consolidated.vue";
import { useUi } from "@/composables/useUi";
import { buildDashVM } from "@/data/dashboard";
import { ANOMALIES, SEV_META, sevLabel } from "@/data/copilot";
import { useDashboard, overlayCockpit } from "@/composables/useDashboard";

const { t, locale } = useI18n();
const router = useRouter();
const { entityId } = useUi();
const { loadCockpit } = useDashboard();

// CFO cockpit from live ERPNext (KPIs, digest, working capital all computed
// from real figures); reloads when the entity changes.
const cockpit = ref(null);
const isLive = ref(null);
async function load() { cockpit.value = await loadCockpit(); isLive.value = !!(cockpit.value && cockpit.value.company); }
watch(entityId, load, { immediate: true });

const vm = computed(() => overlayCockpit(buildDashVM(locale.value, entityId.value), cockpit.value, locale.value));
const asOf = computed(() => cockpit.value?.as_of || "");
const anomalies = ANOMALIES.slice(0, 4);
const sev = (a) => SEV_META[a.sev] || SEV_META.low;

function go(g) {
  if (!g) return;
  router.push(g.sub ? `/accounting/${g.module}/${g.sub}` : `/accounting/${g.module}`);
}
const goChip = (c) => go(c.go);
const goCopilot = () => router.push("/accounting/copilot");
</script>
