<template>
  <div class="space-y-3.5">
    <PageHeader :title="title" :subtitle="entityName">
      <template #actions>
        <div class="flex items-center gap-2 ms-auto">
        </div>
      </template>
    </PageHeader>

    <!-- The sub-tab pill row that used to sit here rendered the same array the
         sidebar renders, with the same labels, so every destination in the
         portal was drawn twice on screen — and the active one a third time as
         the page title. The sidebar holds more of them legibly, shows which
         module they belong to, and is the navigation on mobile already. -->


    <JournalDetail v-if="activeSub === 'journals' && route.query.id" />
    <!-- One screen, two scopes. `daily` is no longer in the navigation but the
         URL still resolves here, so old links and bookmarks keep working. -->
    <PeriodClose v-else-if="activeSub === 'daily'" key="daily" scope="day" />
    <Journals v-else-if="activeSub === 'journals'" />
    <Remediation v-else-if="activeSub === 'triage'" />
    <ChartOfAccounts v-else-if="activeSub === 'coa'" />
    <CoaAudit v-else-if="activeSub === 'coaaudit'" />
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
import CoaAudit from "@/pages/accountant/CoaAudit.vue";
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
