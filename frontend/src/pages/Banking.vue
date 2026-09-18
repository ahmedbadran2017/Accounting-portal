<template>
  <div class="space-y-3.5">
    <PageHeader :title="title" :subtitle="entityName">
      <template #actions>
        <div class="flex items-center gap-2 ms-auto">
          <UiButton variant="create" size="sm" icon="plus" v-if="canWrite" @click="showTransfer = true"> {{ L("New transfer","تحويل جديد","Virement") }}
          </UiButton>
        </div>
      </template>
    </PageHeader>

    <TransferModal v-if="showTransfer" @close="showTransfer = false" @posted="onTransfer" />

    <!-- The sub-tab pill row that used to sit here rendered the same array the
         sidebar renders, with the same labels, so every destination in the
         portal was drawn twice on screen — and the active one a third time as
         the page title. The sidebar holds more of them legibly, shows which
         module they belong to, and is the navigation on mobile already. -->


    <FiscalYearBar v-if="['accounts','bankrec'].includes(activeSub)" />

    <BankAccountDetail v-if="activeSub === 'accounts' && route.query.id" />
    <BankAccounts v-else-if="activeSub === 'accounts'" />
    <BankTransactions v-else-if="activeSub === 'transactions'" />
    <RemittanceDetail v-else-if="activeSub === 'remittance' && route.query.id" />
    <RemittanceList v-else-if="activeSub === 'remittance'" />
    <VarianceQueue v-else-if="activeSub === 'variance'" />
    <CathedisClose v-else-if="activeSub === 'codclose'" />
    <CarrierSettlements v-else-if="activeSub === 'settlements'" />
    <CarrierAging v-else-if="activeSub === 'aging'" />
    <BankRec v-else-if="activeSub === 'bankrec'" />
    <CashBankReview v-else-if="activeSub === 'cleanup'" />
    <ScaffoldTable v-else />
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import PageHeader from "@/components/PageHeader.vue";
import ScaffoldTable from "@/components/ScaffoldTable.vue";
import FiscalYearBar from "@/components/FiscalYearBar.vue";
import CashBankReview from "@/pages/banking/CashBankReview.vue";
import BankAccounts from "@/pages/banking/BankAccounts.vue";
import BankAccountDetail from "@/pages/banking/BankAccountDetail.vue";
import BankTransactions from "@/pages/banking/BankTransactions.vue";
import RemittanceList from "@/pages/banking/RemittanceList.vue";
import RemittanceDetail from "@/pages/banking/RemittanceDetail.vue";
import VarianceQueue from "@/pages/banking/VarianceQueue.vue";
import CathedisClose from "@/pages/banking/CathedisClose.vue";
import CarrierAging from "@/pages/banking/CarrierAging.vue";
import CarrierSettlements from "@/pages/banking/CarrierSettlements.vue";
import BankRec from "@/pages/banking/BankRec.vue";
import TransferModal from "@/components/TransferModal.vue";
import { useUi } from "@/composables/useUi";
import { useAuth } from "@/composables/useAuth";
import { SUBTABS, defaultSub } from "@/data/nav";
import UiButton from "@/components/UiButton.vue";

const { t, locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const route = useRoute();
const router = useRouter();
const { entityId, entities } = useUi();
const { can } = useAuth();
const canWrite = computed(() => can("post_entries"));
const showTransfer = ref(false);
function onTransfer() { router.replace({ query: { ...route.query, _r: Date.now() } }); }

const subs = SUBTABS.banking;
const activeSub = computed(() => route.params.sub || defaultSub("banking"));
const entityName = computed(() => (entities.find((e) => e.id === entityId.value) || entities[0]).name);
const title = computed(() => {
  const found = subs.find((s) => s[0] === activeSub.value);
  return found ? t(found[1]) : t("nav.banking");
});
function goSub(s) { router.push(`/accounting/banking/${s}`); }
</script>
