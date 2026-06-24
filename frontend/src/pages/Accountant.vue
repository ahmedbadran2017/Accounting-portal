<template>
  <div class="space-y-3.5">
    <PageHeader :title="title" :subtitle="entityName">
      <template #actions>
        <div class="flex items-center gap-2 ms-auto">
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

    <Journals v-if="activeSub === 'journals'" />
    <ChartOfAccounts v-else-if="activeSub === 'coa'" />
    <GeneralLedger v-else-if="activeSub === 'gl'" />
    <TrialBalance v-else-if="activeSub === 'trial'" />
    <FixedAssets v-else-if="activeSub === 'assets'" />
    <PeriodClose v-else-if="activeSub === 'close'" />
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
import Journals from "@/pages/accountant/Journals.vue";
import ChartOfAccounts from "@/pages/accountant/ChartOfAccounts.vue";
import GeneralLedger from "@/pages/accountant/GeneralLedger.vue";
import TrialBalance from "@/pages/accountant/TrialBalance.vue";
import FixedAssets from "@/pages/accountant/FixedAssets.vue";
import PeriodClose from "@/pages/accountant/PeriodClose.vue";
import { useUi } from "@/composables/useUi";
import { SUBTABS, defaultSub } from "@/data/nav";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const { entityId, entities } = useUi();

const subs = SUBTABS.accountant;
const activeSub = computed(() => route.params.sub || defaultSub("accountant"));
const entityName = computed(() => (entities.find((e) => e.id === entityId.value) || entities[0]).name);
const title = computed(() => {
  const found = subs.find((s) => s[0] === activeSub.value);
  return found ? t(found[1]) : t("nav.accountant");
});
function goSub(s) { router.push(`/accounting/accountant/${s}`); }
</script>
