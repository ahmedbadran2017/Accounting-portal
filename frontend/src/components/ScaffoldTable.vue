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
      <!-- Header -->
      <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
        <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#faf6f4"><Icon :name="cfg.icon" :size="14" color="#a33a22" /></span>
        <span class="text-[13px] font-bold">{{ title }}</span>
        <span v-if="isLive !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border"
              :style="isLive ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ isLive ? "Live" : "Sample" }}</span>
        <span class="hidden lg:inline text-[11px] text-ink-muted">{{ rows.length }} {{ L("records","سجل","enreg.") }}</span>
        <div class="relative ms-auto">
          <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
          <input v-model.trim="search" :placeholder="t('module.search')"
                 class="w-44 sm:w-64 h-9 bg-app-warm/40 border border-line-2 rounded-[10px] ps-9 pe-3 text-[12.5px] focus:outline-none focus:border-accent/40 focus:bg-white transition" />
        </div>
      </div>

      <!-- Toolbar: date presets · columns · page size -->
      <div class="flex items-center gap-2 px-4 py-2.5 border-b border-line-hair flex-wrap bg-app-warm/20">
        <template v-if="dateCol !== -1">
          <Icon name="clock" :size="13" color="#a8a29e" />
          <button v-for="p in DATE_PRESETS" :key="p.key"
                  class="text-[11px] font-semibold px-2.5 py-1 rounded-full border transition"
                  :class="datePreset === p.key ? 'bg-ink text-white border-ink' : 'bg-white text-ink-3 border-line-2 hover:bg-app-warm'"
                  @click="setPreset(p.key)">{{ p.label(L) }}</button>
          <div v-if="datePreset === 'range'" class="flex items-center gap-1">
            <input type="date" v-model="from" class="h-7 border border-line-2 rounded-chip px-2 text-[11px] focus:outline-none focus:border-accent/40" />
            <span class="text-ink-muted text-[11px]">→</span>
            <input type="date" v-model="to" class="h-7 border border-line-2 rounded-chip px-2 text-[11px] focus:outline-none focus:border-accent/40" />
          </div>
        </template>

        <!-- Faceted filters (configured column indices) -->
        <select v-for="fi in facetCols" :key="fi" :value="facetActive[fi] || ''" @change="setFacet(fi, $event.target.value)"
                class="h-[30px] border rounded-chip px-2 text-[11.5px] bg-white focus:outline-none focus:border-accent/40 cursor-pointer max-w-[150px]"
                :class="facetActive[fi] ? 'border-accent/50 text-accent-dark font-semibold' : 'border-line-2 text-ink-3'">
          <option value="">{{ L("All","الكل","Tous") }} {{ cfg.cols[fi][0] }}</option>
          <option v-for="opt in facetOptions[fi]" :key="opt" :value="opt">{{ opt }}</option>
        </select>

        <!-- Column visibility -->
        <div class="relative ms-auto" ref="colMenu">
          <button class="inline-flex items-center gap-1.5 text-[11.5px] font-semibold text-ink-2 bg-white border border-line-2 px-2.5 py-1.5 rounded-chip hover:bg-app-warm" @click="colOpen = !colOpen">
            <Icon name="layers" :size="13" />{{ L("Columns","الأعمدة","Colonnes") }}
          </button>
          <div v-if="colOpen" class="absolute end-0 mt-1 z-20 w-52 bg-white border border-line rounded-[10px] shadow-cardHover p-1.5 max-h-64 overflow-y-auto">
            <label v-for="(c, i) in cfg.cols" :key="i" class="flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-app-warm cursor-pointer text-[12px]">
              <input type="checkbox" :checked="!hidden.has(i)" @change="toggleCol(i)" class="accent-accent" />
              <span>{{ c[0] }}</span>
            </label>
          </div>
        </div>

        <!-- Page size -->
        <div class="inline-flex items-center gap-1.5 text-[11.5px] text-ink-3">
          <span class="hidden sm:inline">{{ L("Rows","صفوف","Lignes") }}</span>
          <select v-model.number="pageSize" class="h-[30px] border border-line-2 rounded-chip px-2 text-[11.5px] bg-white focus:outline-none focus:border-accent/40 cursor-pointer">
            <option v-for="n in [20, 50, 100, 500]" :key="n" :value="n">{{ n }}</option>
          </select>
        </div>
      </div>

      <!-- Table -->
      <div class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead>
            <tr style="background:#fafaf9">
              <th v-for="(c, i) in cfg.cols" v-show="!hidden.has(i)" :key="i"
                  class="px-4 py-2.5 text-[10px] font-bold uppercase tracking-wider text-ink-muted whitespace-nowrap cursor-pointer select-none hover:text-ink-2"
                  :class="c[1] === 'e' ? 'text-end' : 'text-start'" @click="toggleSort(i)">
                <span class="inline-flex items-center gap-1" :class="c[1] === 'e' ? 'flex-row-reverse' : ''">
                  {{ c[0] }}
                  <Icon v-if="sortCol === i" :name="sortDir === 1 ? 'chevDown' : 'chevDown'" :size="11" :class="sortDir === 1 ? '' : 'rotate-180'" color="#a33a22" />
                </span>
              </th>
              <th v-if="clickable" class="w-8"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, ri) in pageRows" :key="ri"
                class="group border-t border-line-hair hover:bg-app-warm/60 transition-colors"
                :class="clickable && row.open ? 'cursor-pointer' : ''" @click="onRowClick(row)">
              <td v-for="(cell, ci) in row.cells" v-show="!hidden.has(ci)" :key="ci"
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

      <div v-if="!sortedRows.length" class="py-12 text-center text-[12px] text-ink-muted">{{ search || datePreset !== 'all' ? L("No records match your filters.","لا توجد سجلات مطابقة.","Aucun enregistrement.") : t("common.error_loading") }}</div>

      <!-- Pagination footer -->
      <div v-if="sortedRows.length" class="flex items-center gap-3 px-4 py-2.5 border-t border-line-hair text-[11.5px] text-ink-3 flex-wrap">
        <span>{{ L("Showing","عرض","Affichage") }} <b class="text-ink">{{ rangeStart }}–{{ rangeEnd }}</b> {{ L("of","من","sur") }} <b class="text-ink">{{ sortedRows.length }}</b></span>
        <div class="ms-auto flex items-center gap-1">
          <button class="h-7 px-2.5 rounded-chip border border-line-2 bg-white text-ink-2 font-semibold disabled:opacity-40 hover:bg-app-warm inline-flex items-center gap-1" :disabled="page <= 1" @click="page--"><Icon name="arrow" :size="12" class="rotate-180 rtl:rotate-0" />{{ L("Prev","السابق","Préc.") }}</button>
          <span class="px-2 font-semibold text-ink">{{ page }} / {{ totalPages }}</span>
          <button class="h-7 px-2.5 rounded-chip border border-line-2 bg-white text-ink-2 font-semibold disabled:opacity-40 hover:bg-app-warm inline-flex items-center gap-1" :disabled="page >= totalPages" @click="page++">{{ L("Next","التالي","Suiv.") }}<Icon name="arrow" :size="12" class="rtl:rotate-180" /></button>
        </div>
      </div>
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
import { ref, computed, watch, onMounted, onUnmounted } from "vue";
import { useRoute } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { useUi } from "@/composables/useUi";
import { SUBTABS } from "@/data/nav";
import { scaffoldFor } from "@/data/scaffolds";
import { currentCompany } from "@/composables/useLive";
import api from "@/services/api";

const route = useRoute();
const { t, locale } = useI18n();
const { entityId, entities } = useUi();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

const module = computed(() => route.params.module);
const sub = computed(() => route.params.sub);
const cfg = computed(() => scaffoldFor(module.value, sub.value));
const title = computed(() => {
  const s = (SUBTABS[module.value] || []).find((x) => x[0] === sub.value);
  return s ? t(s[1]) : t("nav." + module.value);
});

const rows = ref([]);
const isLive = ref(null);
const insightCards = ref([]);
const search = ref("");
const hidden = ref(new Set());
const sortCol = ref(-1);
const sortDir = ref(1);
const page = ref(1);
const pageSize = ref(50);
const datePreset = ref("all");
const from = ref("");
const to = ref("");
const colOpen = ref(false);
const colMenu = ref(null);
const facetActive = ref({}); // { colIndex: value }

// Facet column indices come from the scaffold config (cfg.facets = [idx,...]).
const facetCols = computed(() => (cfg.value && cfg.value.facets) || []);
const facetOptions = computed(() => {
  const out = {};
  for (const i of facetCols.value) {
    const seen = new Set();
    for (const r of rows.value) { const v = String(r.cells[i] ?? "").trim(); if (v && v !== "—") seen.add(v); }
    out[i] = [...seen].sort((a, b) => a.localeCompare(b)).slice(0, 60);
  }
  return out;
});
function setFacet(i, v) { facetActive.value = { ...facetActive.value, [i]: v || undefined }; page.value = 1; }

const clickable = computed(() => !!(cfg.value && cfg.value.live && cfg.value.live.open));

const DATE_PRESETS = [
  { key: "all", label: (L) => L("All", "الكل", "Tout") },
  { key: "today", label: (L) => L("Today", "اليوم", "Auj.") },
  { key: "yesterday", label: (L) => L("Yesterday", "أمس", "Hier") },
  { key: "7d", label: (L) => L("7 days", "7 أيام", "7 j") },
  { key: "30d", label: (L) => L("30 days", "30 يوم", "30 j") },
  { key: "month", label: (L) => L("This month", "هذا الشهر", "Ce mois") },
  { key: "range", label: (L) => L("Range", "نطاق", "Plage") },
];

// Detect the date column from the headers (label contains date/posting/تاريخ).
const dateCol = computed(() => {
  if (!cfg.value) return -1;
  return cfg.value.cols.findIndex((c) => /date|posting|تاريخ/i.test(c[0]));
});

function parseDate(v) {
  if (!v) return null;
  const s = String(v).trim();
  let m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (m) return new Date(+m[1], +m[2] - 1, +m[3]);
  m = s.match(/^(\d{2})-(\d{2})-(\d{4})/);
  if (m) return new Date(+m[3], +m[2] - 1, +m[1]);
  const d = new Date(s);
  return isNaN(d) ? null : d;
}

function presetBounds(key) {
  const now = new Date();
  const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const today = startOfDay(now);
  if (key === "today") return [today, now];
  if (key === "yesterday") { const y = new Date(today); y.setDate(y.getDate() - 1); return [y, today]; }
  if (key === "7d") { const s = new Date(today); s.setDate(s.getDate() - 7); return [s, now]; }
  if (key === "30d") { const s = new Date(today); s.setDate(s.getDate() - 30); return [s, now]; }
  if (key === "month") return [new Date(now.getFullYear(), now.getMonth(), 1), now];
  if (key === "range") return [from.value ? new Date(from.value) : null, to.value ? new Date(to.value + "T23:59:59") : null];
  return [null, null];
}

const facetFiltered = computed(() => {
  const active = Object.entries(facetActive.value).filter(([, v]) => v);
  if (!active.length) return rows.value;
  return rows.value.filter((r) => active.every(([i, v]) => String(r.cells[+i] ?? "").trim() === v));
});
const dateFiltered = computed(() => {
  if (dateCol.value === -1 || datePreset.value === "all") return facetFiltered.value;
  const [lo, hi] = presetBounds(datePreset.value);
  if (!lo && !hi) return facetFiltered.value;
  return facetFiltered.value.filter((r) => {
    const d = parseDate(r.cells[dateCol.value]);
    if (!d) return false;
    if (lo && d < lo) return false;
    if (hi && d > hi) return false;
    return true;
  });
});

const searched = computed(() => {
  const q = search.value.toLowerCase();
  if (!q) return dateFiltered.value;
  return dateFiltered.value.filter((r) => r.cells.join(" ").toLowerCase().includes(q));
});

function cellSortVal(cell) {
  const s = String(cell).replace(/[, ]/g, "");
  const n = parseFloat(s.replace(/[^\d.-]/g, ""));
  return /^-?[\d.,\s]+%?$/.test(String(cell).trim()) && !isNaN(n) ? n : String(cell).toLowerCase();
}
const sortedRows = computed(() => {
  if (sortCol.value === -1) return searched.value;
  const i = sortCol.value, dir = sortDir.value;
  return [...searched.value].sort((a, b) => {
    const va = cellSortVal(a.cells[i]), vb = cellSortVal(b.cells[i]);
    if (va < vb) return -dir;
    if (va > vb) return dir;
    return 0;
  });
});

const totalPages = computed(() => Math.max(1, Math.ceil(sortedRows.value.length / pageSize.value)));
const pageRows = computed(() => sortedRows.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value));
const rangeStart = computed(() => sortedRows.value.length ? (page.value - 1) * pageSize.value + 1 : 0);
const rangeEnd = computed(() => Math.min(page.value * pageSize.value, sortedRows.value.length));

function setPreset(k) { datePreset.value = k; page.value = 1; }
function toggleCol(i) { const h = new Set(hidden.value); h.has(i) ? h.delete(i) : h.add(i); hidden.value = h; }
function toggleSort(i) {
  if (sortCol.value === i) { sortDir.value === 1 ? (sortDir.value = -1) : (sortCol.value = -1); }
  else { sortCol.value = i; sortDir.value = 1; }
}
// Reset to page 1 whenever the result set shrinks/changes.
watch([search, datePreset, from, to, pageSize, sortedRows], () => { if (page.value > totalPages.value) page.value = 1; });

function pack(cells, raw) {
  const open = raw && cfg.value.live && cfg.value.live.open ? cfg.value.live.open(raw) : null;
  return { cells, open };
}

async function load() {
  const c = cfg.value;
  search.value = ""; insightCards.value = []; hidden.value = new Set();
  sortCol.value = -1; page.value = 1; datePreset.value = "all"; facetActive.value = {};
  if (!c) { rows.value = []; isLive.value = null; return; }

  if (c.live) {
    try {
      const data = await api.call(c.live.method, { company: currentCompany(), limit: 500 });
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
function onDocClick(e) { if (colMenu.value && !colMenu.value.contains(e.target)) colOpen.value = false; }
onMounted(() => document.addEventListener("click", onDocClick));
onUnmounted(() => document.removeEventListener("click", onDocClick));

watch([() => route.params.sub, () => route.params.module, entityId], load, { immediate: true });
</script>
