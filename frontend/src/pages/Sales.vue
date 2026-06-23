<template>
  <div class="space-y-3.5">
    <!-- Header -->
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

    <!-- Sub-tab pills -->
    <div class="flex flex-wrap gap-1 bg-white border border-line rounded-chip p-1 w-fit max-w-full overflow-x-auto">
      <button v-for="s in subs" :key="s[0]"
              class="px-3 py-1.5 rounded-lg text-[12px] whitespace-nowrap"
              :class="activeSub === s[0] ? 'text-accent-dark font-semibold bg-app-warm shadow-card' : 'text-ink-3 font-medium hover:text-ink'"
              @click="goSub(s[0])">{{ t(s[1]) }}</button>
    </div>

    <!-- Body -->
    <OrderDetail v-if="activeSub === 'orders' && route.query.id" />
    <OrdersList v-else-if="activeSub === 'orders'" />
    <InvoiceDetail v-else-if="activeSub === 'invoices' && route.query.id" />
    <InvoicesList v-else-if="activeSub === 'invoices'" />
    <CustomerDetail v-else-if="activeSub === 'customers' && route.query.id" />
    <CustomersList v-else-if="activeSub === 'customers'" />
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
import OrdersList from "@/pages/sales/OrdersList.vue";
import OrderDetail from "@/pages/sales/OrderDetail.vue";
import InvoicesList from "@/pages/sales/InvoicesList.vue";
import InvoiceDetail from "@/pages/sales/InvoiceDetail.vue";
import CustomersList from "@/pages/sales/CustomersList.vue";
import CustomerDetail from "@/pages/sales/CustomerDetail.vue";
import { useUi } from "@/composables/useUi";
import { SUBTABS, defaultSub } from "@/data/nav";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const { entityId, entities } = useUi();

const subs = SUBTABS.sales;
const activeSub = computed(() => route.params.sub || defaultSub("sales"));
const entityName = computed(() => (entities.find((e) => e.id === entityId.value) || entities[0]).name);
const title = computed(() => {
  const found = subs.find((s) => s[0] === activeSub.value);
  return found ? t(found[1]) : t("nav.sales");
});

function goSub(s) { router.push(`/accounting/sales/${s}`); }
</script>
