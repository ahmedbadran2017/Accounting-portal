<template>
  <div class="space-y-3.5">
    <PageHeader :title="title" :subtitle="entityName">
      <template #actions>
        <div class="flex items-center gap-2 ms-auto">
          <button class="inline-flex items-center gap-1.5 text-[12px] font-semibold text-white bg-brand hover:bg-brand-dark px-3 py-1.5 rounded-chip shadow-brand">
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

    <SalesCollections v-if="activeSub === 'salescol'" />
    <Statements v-else-if="activeSub === 'statements'" />
    <TaxReports v-else-if="activeSub === 'taxreports'" />
    <VerifiedDD v-else-if="activeSub === 'dd'" />
    <ScaffoldTable v-else />
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import PageHeader from "@/components/PageHeader.vue";
import ScaffoldTable from "@/components/ScaffoldTable.vue";
import SalesCollections from "@/pages/reports/SalesCollections.vue";
import Statements from "@/pages/reports/Statements.vue";
import TaxReports from "@/pages/reports/TaxReports.vue";
import VerifiedDD from "@/pages/reports/VerifiedDD.vue";
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
