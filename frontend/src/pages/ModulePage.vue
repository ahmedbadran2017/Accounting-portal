<template>
  <div class="space-y-3.5">
    <!-- Title + toolbar -->
    <div class="flex flex-wrap items-center gap-3">
      <div class="min-w-0">
        <h2 class="text-[17px] font-bold tracking-tight">{{ title }}</h2>
        <div class="text-[11.5px] text-ink-muted">{{ entityName }}</div>
      </div>
      <div class="flex items-center gap-2 ms-auto">
        <div class="relative hidden sm:block">
          <span class="absolute inset-block-0 flex items-center ps-2.5 text-ink-muted"><Icon name="search" :size="15" /></span>
          <input :placeholder="t('module.search')"
                 class="w-48 bg-white border border-line-2 rounded-chip ps-8 pe-3 py-1.5 text-[12px] focus:outline-none focus:border-accent/40" />
        </div>
        <button class="inline-flex items-center gap-1.5 text-[12px] font-semibold text-white bg-brand hover:bg-brand-dark px-3 py-1.5 rounded-chip shadow-brand">
          <Icon name="plus" :size="14" />{{ t("module.new") }}
        </button>
      </div>
    </div>

    <!-- Sub-tab pills (mirrors the sidebar tree for quick switching) -->
    <div v-if="subs.length" class="flex flex-wrap gap-1 bg-white border border-line rounded-chip p-1 w-fit max-w-full overflow-x-auto">
      <button v-for="s in subs" :key="s[0]"
              class="px-3 py-1.5 rounded-lg text-[12px] whitespace-nowrap"
              :class="activeSub === s[0] ? 'text-accent-dark font-semibold bg-app-warm shadow-card' : 'text-ink-3 font-medium hover:text-ink'"
              @click="goSub(s[0])">{{ t(s[1]) }}</button>
    </div>

    <!-- Placeholder body -->
    <div class="bg-white rounded-card border border-line">
      <div class="flex flex-col items-center justify-center text-center py-20 px-6">
        <div class="w-12 h-12 rounded-card grid place-items-center mb-4" style="background:#e7f4f1">
          <Icon name="spark" :size="22" color="#0b5c4f" />
        </div>
        <h3 class="text-[14px] font-bold">{{ title }} · {{ t("module.placeholder_title") }}</h3>
        <p class="text-[12px] text-ink-3 mt-1.5 max-w-md leading-relaxed">{{ t("module.placeholder_body") }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { useUi } from "@/composables/useUi";
import { SUBTABS, defaultSub } from "@/data/nav";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const { entityId, entities } = useUi();

const module = computed(() => route.params.module);
const subs = computed(() => SUBTABS[module.value] || []);
const activeSub = computed(() => route.params.sub || defaultSub(module.value));
const entityName = computed(() => (entities.find((e) => e.id === entityId.value) || entities[0]).name);

const title = computed(() => {
  const sub = activeSub.value;
  const found = subs.value.find((s) => s[0] === sub);
  return found ? t(found[1]) : t("nav." + module.value);
});

function goSub(s) { router.push(`/accounting/${module.value}/${s}`); }
</script>
