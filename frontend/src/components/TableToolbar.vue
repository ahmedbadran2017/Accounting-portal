<template>
  <div class="flex items-center gap-2 px-4 py-2.5 border-b border-line-hair flex-wrap bg-app-warm/20">
    <template v-if="t.hasDate">
      <Icon name="clock" :size="13" color="#a8a29e" />
      <button v-for="p in PRESETS" :key="p.key"
              class="text-[11px] font-semibold px-2.5 py-1 rounded-full border transition"
              :class="t.datePreset.value === p.key ? 'bg-ink text-white border-ink' : 'bg-white text-ink-3 border-line-2 hover:bg-app-warm'"
              @click="t.setPreset(p.key)">{{ p.label(L) }}</button>
      <div v-if="t.datePreset.value === 'range'" class="flex items-center gap-1">
        <input type="date" v-model="t.from.value" class="h-7 border border-line-2 rounded-chip px-2 text-[11px] focus:outline-none focus:border-accent/40" />
        <span class="text-ink-muted text-[11px]">→</span>
        <input type="date" v-model="t.to.value" class="h-7 border border-line-2 rounded-chip px-2 text-[11px] focus:outline-none focus:border-accent/40" />
      </div>
    </template>

    <!-- Faceted filters (carrier / city / status …) -->
    <select v-for="f in t.facets" :key="f.key" :value="t.facetActive.value[f.key] || ''" @change="t.setFacet(f.key, $event.target.value)"
            class="h-[30px] border rounded-chip px-2 text-[11.5px] bg-white focus:outline-none focus:border-accent/40 cursor-pointer max-w-[140px]"
            :class="t.facetActive.value[f.key] ? 'border-accent/50 text-accent-dark font-semibold' : 'border-line-2 text-ink-3'">
      <option value="">{{ L("All","الكل","Tous") }} {{ f.label }}</option>
      <option v-for="opt in t.facetOptions.value[f.key]" :key="opt" :value="opt">{{ f.format ? f.format(opt) : opt }}</option>
    </select>

    <button class="ms-auto inline-flex items-center gap-1.5 text-[11.5px] font-semibold text-ink-2 bg-white border border-line-2 px-2.5 py-1.5 rounded-chip hover:bg-app-warm" @click="t.exportCSV(filename)" :title="L('Export current view to CSV','تصدير العرض الحالي CSV','Exporter en CSV')">
      <Icon name="doc" :size="13" />{{ L("Export","تصدير","Exporter") }}
    </button>
    <div class="relative" ref="menu">
      <button class="inline-flex items-center gap-1.5 text-[11.5px] font-semibold text-ink-2 bg-white border border-line-2 px-2.5 py-1.5 rounded-chip hover:bg-app-warm" @click="open = !open">
        <Icon name="layers" :size="13" />{{ L("Columns","الأعمدة","Colonnes") }}
      </button>
      <div v-if="open" class="absolute end-0 mt-1 z-20 w-52 bg-white border border-line rounded-[10px] shadow-cardHover p-1.5 max-h-64 overflow-y-auto">
        <label v-for="c in t.cols" :key="c.key" class="flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-app-warm cursor-pointer text-[12px]">
          <input type="checkbox" :checked="!t.hidden.value.has(c.key)" @change="t.toggleCol(c.key)" class="accent-accent" />
          <span>{{ c.label }}</span>
        </label>
      </div>
    </div>

    <div class="inline-flex items-center gap-1.5 text-[11.5px] text-ink-3">
      <span class="hidden sm:inline">{{ L("Rows","صفوف","Lignes") }}</span>
      <select v-model.number="t.pageSize.value" class="h-[30px] border border-line-2 rounded-chip px-2 text-[11.5px] bg-white focus:outline-none focus:border-accent/40 cursor-pointer">
        <option v-for="n in [20, 50, 100, 500]" :key="n" :value="n">{{ n }}</option>
      </select>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";

const props = defineProps({ t: { type: Object, required: true }, filename: { type: String, default: "export" } });
const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

const PRESETS = [
  { key: "all", label: (L) => L("All", "الكل", "Tout") },
  { key: "today", label: (L) => L("Today", "اليوم", "Auj.") },
  { key: "yesterday", label: (L) => L("Yesterday", "أمس", "Hier") },
  { key: "7d", label: (L) => L("7 days", "7 أيام", "7 j") },
  { key: "30d", label: (L) => L("30 days", "30 يوم", "30 j") },
  { key: "month", label: (L) => L("This month", "هذا الشهر", "Ce mois") },
  { key: "range", label: (L) => L("Range", "نطاق", "Plage") },
];

const open = ref(false);
const menu = ref(null);
function onDoc(e) { if (menu.value && !menu.value.contains(e.target)) open.value = false; }
onMounted(() => document.addEventListener("click", onDoc));
onUnmounted(() => document.removeEventListener("click", onDoc));
</script>
