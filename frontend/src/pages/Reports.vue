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


    <GroupPnl v-if="activeSub === 'grouppnl'" />
    <Matching v-else-if="activeSub === 'matching'" />
    <SalesCollections v-else-if="activeSub === 'salescol'" />
    <ReceivablesPayables v-else-if="activeSub === 'arap'" />
    <CashForecast v-else-if="activeSub === 'forecast'" />
    <MissingDocs v-else-if="activeSub === 'missingdocs'" />
    <Statements v-else-if="activeSub === 'statements'" />
    <Investors v-else-if="activeSub === 'investors'" />
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
import GroupPnl from "@/pages/reports/GroupPnl.vue";
import SalesCollections from "@/pages/reports/SalesCollections.vue";
import ReceivablesPayables from "@/pages/reports/ReceivablesPayables.vue";
import CashForecast from "@/pages/reports/CashForecast.vue";
import MissingDocs from "@/pages/reports/MissingDocs.vue";
import Matching from "@/pages/reports/Matching.vue";
import Statements from "@/pages/reports/Statements.vue";
import Investors from "@/pages/reports/Investors.vue";
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
