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

    <RemittanceDetail v-if="activeSub === 'remittance' && route.query.id" />
    <RemittanceList v-else-if="activeSub === 'remittance'" />
    <VarianceQueue v-else-if="activeSub === 'variance'" />
    <CarrierAging v-else-if="activeSub === 'aging'" />
    <BankRec v-else-if="activeSub === 'bankrec'" />
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
import RemittanceList from "@/pages/banking/RemittanceList.vue";
import RemittanceDetail from "@/pages/banking/RemittanceDetail.vue";
import VarianceQueue from "@/pages/banking/VarianceQueue.vue";
import CarrierAging from "@/pages/banking/CarrierAging.vue";
import BankRec from "@/pages/banking/BankRec.vue";
import { useUi } from "@/composables/useUi";
import { SUBTABS, defaultSub } from "@/data/nav";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const { entityId, entities } = useUi();

const subs = SUBTABS.banking;
const activeSub = computed(() => route.params.sub || defaultSub("banking"));
const entityName = computed(() => (entities.find((e) => e.id === entityId.value) || entities[0]).name);
const title = computed(() => {
  const found = subs.find((s) => s[0] === activeSub.value);
  return found ? t(found[1]) : t("nav.banking");
});
function goSub(s) { router.push(`/accounting/banking/${s}`); }
</script>
