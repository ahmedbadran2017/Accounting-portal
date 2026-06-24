<template>
  <div class="space-y-3.5">
    <!-- Header -->
    <PageHeader :title="title" :subtitle="entityName">
      <template #actions>
        <div v-if="showNew" class="flex items-center gap-2 ms-auto">
          <button class="inline-flex items-center gap-1.5 text-[12px] font-semibold text-white bg-accent hover:bg-accent-dark px-3 py-1.5 rounded-chip shadow-prim" @click="onNew">
            <Icon name="plus" :size="14" />{{ newLabel }}
          </button>
        </div>
      </template>
    </PageHeader>

    <PaymentEntryForm v-if="showPayment" @close="showPayment = false" @posted="onPaid" />
    <SalesOrderForm v-if="showOrder" @close="showOrder = false" @posted="onOrdered" />

    <!-- Sub-tab pills -->
    <div class="flex flex-wrap gap-1 bg-white border border-line rounded-chip p-1 w-fit max-w-full overflow-x-auto">
      <button v-for="s in subs" :key="s[0]"
              class="px-3 py-1.5 rounded-lg text-[12px] whitespace-nowrap"
              :class="activeSub === s[0] ? 'text-accent-dark font-semibold bg-app-warm shadow-card' : 'text-ink-3 font-medium hover:text-ink'"
              @click="goSub(s[0])">{{ t(s[1]) }}</button>
    </div>

    <!-- Body -->
    <OrderDetail v-if="activeSub === 'orders' && route.query.id" />
    <OrdersList v-else-if="activeSub === 'orders'" @new="showOrder = true" />
    <CodBucket v-else-if="['todeliver','delivered','collected','returned'].includes(activeSub)" />
    <InvoiceDetail v-else-if="activeSub === 'invoices' && route.query.id" />
    <InvoicesList v-else-if="activeSub === 'invoices'" />
    <CustomerDetail v-else-if="activeSub === 'customers' && route.query.id" />
    <CustomersList v-else-if="activeSub === 'customers'" />
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
import PaymentEntryForm from "@/components/PaymentEntryForm.vue";
import SalesOrderForm from "@/components/SalesOrderForm.vue";
import CodBucket from "@/pages/sales/CodBucket.vue";
import { useToast } from "@/composables/useToast";
import OrdersList from "@/pages/sales/OrdersList.vue";
import OrderDetail from "@/pages/sales/OrderDetail.vue";
import InvoicesList from "@/pages/sales/InvoicesList.vue";
import InvoiceDetail from "@/pages/sales/InvoiceDetail.vue";
import CustomersList from "@/pages/sales/CustomersList.vue";
import CustomerDetail from "@/pages/sales/CustomerDetail.vue";
import { useUi } from "@/composables/useUi";
import { SUBTABS, defaultSub } from "@/data/nav";

const { t, locale } = useI18n();
const route = useRoute();
const router = useRouter();
const { entityId, entities } = useUi();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

const showPayment = ref(false);
const showOrder = ref(false);
const canRecordPayment = computed(() => activeSub.value === "payments");
const canCreateOrder = computed(() => activeSub.value === "orders");
// Only show "+New" where it actually does something — the COD bucket tabs use
// "Reconcile" as their action, customers/invoices have their own create paths.
const showNew = computed(() => canRecordPayment.value || canCreateOrder.value);
const newLabel = computed(() => canRecordPayment.value
  ? L("Record receipt", "تسجيل دفعة", "Encaissement")
  : canCreateOrder.value ? L("New order", "أمر جديد", "Nouvelle commande") : t("module.new"));
function onNew() {
  if (canRecordPayment.value) showPayment.value = true;
  else if (canCreateOrder.value) showOrder.value = true;
}
function onPaid(res) {
  if (res && res.status === "Posted") {
    toast.success(L(`Receipt ${res.voucher_no || ""} recorded`, `سند ${res.voucher_no || ""} سُجّل`, `Encaissement ${res.voucher_no || ""} enregistré`));
  } else {
    toast.info(L("Receipt recorded — awaiting an approver", "الدفعة سُجّلت — بانتظار موافِق", "Encaissement enregistré — en attente"));
  }
}
function onOrdered(res) {
  if (res && res.status === "Posted") {
    toast.success(L(`Order ${res.voucher_no || ""} created`, `الطلب ${res.voucher_no || ""} أُنشئ`, `Commande ${res.voucher_no || ""} créée`));
    router.push({ path: "/accounting/sales/orders", query: { id: res.voucher_no } });
  } else {
    toast.info(L("Order recorded — awaiting an approver", "الطلب سُجّل — بانتظار موافِق", "Commande enregistrée — en attente"));
  }
}

const subs = SUBTABS.sales;
const activeSub = computed(() => route.params.sub || defaultSub("sales"));
const entityName = computed(() => (entities.find((e) => e.id === entityId.value) || entities[0]).name);
const title = computed(() => {
  const found = subs.find((s) => s[0] === activeSub.value);
  return found ? t(found[1]) : t("nav.sales");
});

function goSub(s) { router.push(`/accounting/sales/${s}`); }
</script>
