<template>
  <div class="space-y-3.5">
    <PageHeader :title="title" :subtitle="entityName">
      <template #actions>
        <div class="flex items-center gap-2 ms-auto">
          <button class="inline-flex items-center gap-1.5 text-[12px] font-medium text-ink-2 bg-white border border-line-2 px-2.5 py-1.5 rounded-chip hover:bg-app-warm">
            <Icon name="filter" :size="14" />{{ t("module.filters") }}
          </button>
          <button class="inline-flex items-center gap-1.5 text-[12px] font-semibold text-white bg-accent hover:bg-accent-dark px-3 py-1.5 rounded-chip shadow-prim">
            <Icon name="plus" :size="14" />{{ t("module.new") }}
          </button>
        </div>
      </template>
    </PageHeader>

    <div class="flex flex-wrap gap-1 bg-white border border-line rounded-chip p-1 w-fit max-w-full overflow-x-auto">
      <button v-for="s in subs" :key="s[0]" class="px-3 py-1.5 rounded-lg text-[12px] whitespace-nowrap"
              :class="activeSub === s[0] ? 'text-accent-dark font-semibold bg-app-warm shadow-card' : 'text-ink-3 font-medium hover:text-ink'"
              @click="goSub(s[0])">{{ t(s[1]) }}</button>
    </div>

    <Statements v-if="activeSub === 'statements'" />
    <div v-else class="bg-white rounded-card border border-line">
      <div class="flex flex-col items-center justify-center text-center py-20 px-6">
        <div class="w-12 h-12 rounded-card grid place-items-center mb-4" style="background:#fbf2ee"><Icon name="spark" :size="22" color="#a33a22" /></div>
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
import PageHeader from "@/components/PageHeader.vue";
import Statements from "@/pages/reports/Statements.vue";
import { useUi } from "@/composables/useUi";
import { SUBTABS, defaultSub } from "@/data/nav";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const { entityId, entities } = useUi();

const subs = SUBTABS.reports;
const activeSub = computed(() => route.params.sub || defaultSub("reports"));
const entityName = computed(() => (entities.find((e) => e.id === entityId.value) || entities[0]).name);
const title = computed(() => {
  const found = subs.find((s) => s[0] === activeSub.value);
  return found ? t(found[1]) : t("nav.reports");
});
function goSub(s) { router.push(`/accounting/reports/${s}`); }
</script>
