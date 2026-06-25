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

    <VendorDetail v-if="activeSub === 'vendors' && route.query.id" />
    <VendorsList v-else-if="activeSub === 'vendors'" />
    <PurchaseDocDetail v-else-if="['tobuy','received','billed','topay','paid'].includes(activeSub) && route.query.id" />
    <PurchaseBucket v-else-if="['tobuy','received','billed','topay','paid'].includes(activeSub)" />
    <BillDetail v-else-if="activeSub === 'bills' && route.query.id" />
    <BillsList v-else-if="activeSub === 'bills'" />
    <PaymentMadeDetail v-else-if="activeSub === 'payments' && route.query.id" />
    <PaymentsMade v-else-if="activeSub === 'payments'" />
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
import VendorsList from "@/pages/purchases/VendorsList.vue";
import VendorDetail from "@/pages/purchases/VendorDetail.vue";
import PurchaseBucket from "@/pages/purchases/PurchaseBucket.vue";
import PurchaseDocDetail from "@/pages/purchases/PurchaseDocDetail.vue";
import BillsList from "@/pages/purchases/BillsList.vue";
import BillDetail from "@/pages/purchases/BillDetail.vue";
import PaymentsMade from "@/pages/purchases/PaymentsMade.vue";
import PaymentMadeDetail from "@/pages/purchases/PaymentMadeDetail.vue";
import { useUi } from "@/composables/useUi";
import { SUBTABS, defaultSub } from "@/data/nav";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const { entityId, entities } = useUi();

const subs = SUBTABS.purchases;
const activeSub = computed(() => route.params.sub || defaultSub("purchases"));
const entityName = computed(() => (entities.find((e) => e.id === entityId.value) || entities[0]).name);
const title = computed(() => {
  const found = subs.find((s) => s[0] === activeSub.value);
  return found ? t(found[1]) : t("nav.purchases");
});
function goSub(s) { router.push(`/accounting/purchases/${s}`); }
</script>
