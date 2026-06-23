<template>
  <!-- A real list view for the generic sub-tabs (config in data/scaffolds.js);
       falls back to the "pending build" placeholder when there's no config. -->
  <div v-if="cfg" class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
    <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair">
      <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#faf6f4"><Icon :name="cfg.icon" :size="14" color="#a33a22" /></span>
      <span class="text-[13px] font-bold">{{ title }}</span>
      <span class="text-[11px] text-ink-muted">{{ entityName }}</span>
    </div>
    <div class="overflow-x-auto">
      <table class="w-full text-[12px]">
        <thead>
          <tr style="background:#fafaf9">
            <th v-for="(c, i) in cfg.cols" :key="i"
                class="px-4 py-2.5 text-[10px] font-bold uppercase tracking-wider text-ink-muted whitespace-nowrap"
                :class="c[1] === 'e' ? 'text-end' : 'text-start'">{{ c[0] }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, ri) in cfg.rows" :key="ri" class="border-t border-line-hair hover:bg-app-warm/60">
            <td v-for="(cell, ci) in row" :key="ci"
                class="px-4 py-2.5 whitespace-nowrap"
                :class="[cfg.cols[ci] && cfg.cols[ci][1] === 'e' ? 'text-end tnum' : '', ci === 0 ? 'font-semibold font-mono' : 'text-ink-2', String(cell).startsWith('-') ? 'text-sale' : '']">
              {{ cell }}
            </td>
          </tr>
        </tbody>
      </table>
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
import { computed } from "vue";
import { useRoute } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { useUi } from "@/composables/useUi";
import { SUBTABS } from "@/data/nav";
import { scaffoldFor } from "@/data/scaffolds";

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
</script>
