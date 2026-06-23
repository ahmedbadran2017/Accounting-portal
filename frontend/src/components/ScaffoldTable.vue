<template>
  <div v-if="cfg" class="space-y-3.5">
    <!-- Insights strip (live summary) -->
    <div v-if="insightCards.length" class="grid grid-cols-2 sm:grid-cols-4 gap-3">
      <div v-for="m in insightCards" :key="m.label" class="relative bg-white border border-line rounded-[14px] p-3.5 shadow-card overflow-hidden">
        <div class="absolute -top-8 -end-8 w-20 h-20 rounded-full blur-2xl pointer-events-none" :style="{ background: m.glow, opacity: .07 }"></div>
        <div class="relative text-[9.5px] text-ink-muted font-bold uppercase tracking-wider">{{ m.label }}</div>
        <div class="relative text-[19px] font-extrabold tnum mt-1 tracking-tight" :style="{ color: m.color }">{{ m.value }}</div>
        <div class="relative text-[10px] text-ink-3 mt-0.5">{{ m.sub }}</div>
      </div>
    </div>

    <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
      <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair">
        <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#faf6f4"><Icon :name="cfg.icon" :size="14" color="#a33a22" /></span>
        <span class="text-[13px] font-bold">{{ title }}</span>
        <span v-if="isLive !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border"
              :style="isLive ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ isLive ? "Live" : "Sample" }}</span>
        <span class="hidden sm:inline text-[11px] text-ink-muted">{{ entityName }}</span>
        <div class="relative ms-auto">
          <span class="absolute inset-block-0 flex items-center ps-2.5 text-ink-muted"><Icon name="search" :size="14" /></span>
          <input v-model.trim="search" :placeholder="t('module.search')"
                 class="w-40 sm:w-52 bg-app-warm/50 border border-line-2 rounded-chip ps-8 pe-3 py-1.5 text-[12px] focus:outline-none focus:border-accent/40" />
        </div>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead>
            <tr style="background:#fafaf9">
              <th v-for="(c, i) in cfg.cols" :key="i"
                  class="px-4 py-2.5 text-[10px] font-bold uppercase tracking-wider text-ink-muted whitespace-nowrap"
                  :class="c[1] === 'e' ? 'text-end' : 'text-start'">{{ c[0] }}</th>
              <th v-if="clickable" class="w-8"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, ri) in filteredRows" :key="ri"
                class="group border-t border-line-hair hover:bg-app-warm/60 transition-colors"
                :class="clickable && row.open ? 'cursor-pointer' : ''" @click="onRowClick(row)">
              <td v-for="(cell, ci) in row.cells" :key="ci"
                  class="px-4 py-2.5 whitespace-nowrap"
                  :class="[cfg.cols[ci] && cfg.cols[ci][1] === 'e' ? 'text-end tnum' : '', ci === 0 ? 'font-semibold font-mono' : 'text-ink-2', String(cell).startsWith('-') ? 'text-sale' : '']">
                {{ cell }}
              </td>
              <td v-if="clickable" class="px-3 text-end">
                <Icon v-if="row.open" name="arrow" :size="13" color="#c4492a" class="opacity-0 group-hover:opacity-100 transition-opacity rtl:rotate-180" />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="!filteredRows.length" class="py-12 text-center text-[12px] text-ink-muted">{{ t("common.error_loading") }}</div>
    </div>
  </div>

  <div v-else class="bg-white rounded-card border border-line">
    <div class="flex flex-col items-center justify-center text-center py-20 px-6">
      <div class="w-12 h-12 rounded-card grid place-items-center mb-4" style="background:#fbf2ee"><Icon name="spark" :size="22" color="#a33a22" /></div>
      <h3 class="text-[14px] font-bold">{{ title }} · {{ t("module.placeholder_title") }}</h3>
      <p class="text-[12px] text-ink-3 mt-1.5 max-w-md leading-relaxed">{{ t("module.placeholder_body") }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useRoute } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { useUi } from "@/composables/useUi";
import { SUBTABS } from "@/data/nav";
import { scaffoldFor } from "@/data/scaffolds";
import { currentCompany } from "@/composables/useLive";
import api from "@/services/api";

const route = useRoute();
const { t } = useI18n();
const { entityId, entities } = useUi();

const module = computed(() => route.params.module);
const sub = computed(() => route.params.sub);
const cfg = computed(() => scaffoldFor(module.value, sub.value));
const entityName = computed(() => (entities.find((e) => e.id === entityId.value) || entities[0]).name);
const title = computed(() => {
  const s = (SUBTABS[module.value] || []).find((x) => x[0] === sub.value);
  return s ? t(s[1]) : t("nav." + module.value);
});

// rows = [{ cells:[...], open: url|null }]; live tabs fetch + map, others use sample.
const rows = ref([]);
const isLive = ref(null);
const insightCards = ref([]);
const search = ref("");

const clickable = computed(() => !!(cfg.value && cfg.value.live && cfg.value.live.open));
const filteredRows = computed(() => {
  const q = search.value.toLowerCase();
  if (!q) return rows.value;
  return rows.value.filter((r) => r.cells.join(" ").toLowerCase().includes(q));
});

function pack(cells, raw) {
  const open = raw && cfg.value.live && cfg.value.live.open ? cfg.value.live.open(raw) : null;
  return { cells, open };
}

async function load() {
  const c = cfg.value;
  search.value = "";
  insightCards.value = [];
  if (!c) { rows.value = []; isLive.value = null; return; }

  if (c.live) {
    try {
      const data = await api.call(c.live.method, { company: currentCompany(), limit: 100 });
      const raw = Array.isArray(data) ? data : [];
      rows.value = raw.map((r) => pack(c.live.map(r), r));
      isLive.value = true;
    } catch {
      rows.value = c.rows.map((cells) => ({ cells, open: null }));
      isLive.value = false;
    }
  } else {
    rows.value = c.rows.map((cells) => ({ cells, open: null }));
    isLive.value = null;
  }

  if (c.insights) {
    let s = c.insights.sample;
    try { s = await api.call(c.insights.method, { company: currentCompany() }); } catch { /* sample */ }
    insightCards.value = s ? c.insights.cards(s) : [];
  }
}

function onRowClick(row) {
  if (row.open) window.open(row.open, "_blank", "noopener");
}

watch([() => route.params.sub, () => route.params.module, entityId], load, { immediate: true });
</script>
