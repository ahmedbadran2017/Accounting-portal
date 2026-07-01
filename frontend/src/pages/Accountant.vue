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

    <JournalDetail v-if="activeSub === 'journals' && route.query.id" />
    <Journals v-else-if="activeSub === 'journals'" />
    <Remediation v-else-if="activeSub === 'triage'" />
    <ChartOfAccounts v-else-if="activeSub === 'coa'" />
    <GeneralLedger v-else-if="activeSub === 'gl'" />
    <TrialBalance v-else-if="activeSub === 'trial'" />
    <FixedAssets v-else-if="activeSub === 'assets'" />
    <FxRevaluation v-else-if="activeSub === 'fx'" />
    <OpeningEntry v-else-if="activeSub === 'opening'" />
    <PeriodClose v-else-if="activeSub === 'close'" />
    <AccountantDetail v-else-if="activeSub === 'team' && route.query.user" />
    <TeamPerformance v-else-if="activeSub === 'team'" />
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
import JournalDetail from "@/pages/accountant/JournalDetail.vue";
import Remediation from "@/pages/accountant/Remediation.vue";
import ChartOfAccounts from "@/pages/accountant/ChartOfAccounts.vue";
import GeneralLedger from "@/pages/accountant/GeneralLedger.vue";
import TrialBalance from "@/pages/accountant/TrialBalance.vue";
import FixedAssets from "@/pages/accountant/FixedAssets.vue";
import FxRevaluation from "@/pages/accountant/FxRevaluation.vue";
import OpeningEntry from "@/pages/accountant/OpeningEntry.vue";
import PeriodClose from "@/pages/accountant/PeriodClose.vue";
import TeamPerformance from "@/pages/accountant/TeamPerformance.vue";
import AccountantDetail from "@/pages/accountant/AccountantDetail.vue";
import { useUi } from "@/composables/useUi";
import { useAuth } from "@/composables/useAuth";
import { SUBTABS, defaultSub } from "@/data/nav";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const { entityId, entities } = useUi();
const { can } = useAuth();

// The Team-performance tab holds sensitive employee-evaluation data — show it to
// the Super Admin only (same gate the backend enforces). Others never see it.
const subs = computed(() => SUBTABS.accountant.filter((s) => s[0] !== "team" || can("manage_users")));
const activeSub = computed(() => route.params.sub || defaultSub("accountant"));
const entityName = computed(() => (entities.find((e) => e.id === entityId.value) || entities[0]).name);
const title = computed(() => {
  const found = subs.value.find((s) => s[0] === activeSub.value);
  return found ? t(found[1]) : t("nav.accountant");
});
function goSub(s) { router.push(`/accounting/accountant/${s}`); }
</script>
