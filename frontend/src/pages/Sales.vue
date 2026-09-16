<template>
  <div class="space-y-3.5">
    <!-- Header -->
    <PageHeader :title="title" :subtitle="entityName">
      <template #actions>
        <div v-if="showNew" class="flex items-center gap-2 ms-auto">
          <button class="inline-flex items-center gap-1.5 text-[12px] font-semibold text-white bg-brand hover:bg-brand-dark px-3 py-1.5 rounded-chip shadow-brand" @click="onNew">
            <Icon name="plus" :size="14" />{{ newLabel }}
          </button>
        </div>
      </template>
    </PageHeader>

    <PaymentEntryForm v-if="showPayment" @close="showPayment = false" @posted="onPaid" />
    <SalesOrderForm v-if="showOrder" @close="showOrder = false" @posted="onOrdered" />

        <!-- The sub-tab pill row that used to sit here rendered the same array the
         sidebar renders, with the same labels, so every destination in the
         portal was drawn twice on screen — and the active one a third time as
         the page title. The sidebar holds more of them legibly, shows which
         module they belong to, and is the navigation on mobile already. -->


    <!-- Body -->
    <OrderDetail v-if="activeSub === 'orders' && route.query.id" />
    <OrdersList v-else-if="activeSub === 'orders'" @new="showOrder = true" />
    <CodBucket v-else-if="['todeliver','delivered','collected','toreturn','returned'].includes(activeSub)" />
    <ChallanDetail v-else-if="activeSub === 'challans' && route.query.id" />
    <ChallansList v-else-if="activeSub === 'challans'" />
    <ToBillQueue v-else-if="activeSub === 'tobill'" />
    <CreditsList v-else-if="activeSub === 'credits'" />
    <InvoiceDetail v-else-if="activeSub === 'invoices' && route.query.id" />
    <InvoicesList v-else-if="activeSub === 'invoices'" />
    <CustomerDetail v-else-if="activeSub === 'customers' && route.query.id" />
    <CustomersList v-else-if="activeSub === 'customers'" />
    <ReceiptDetail v-else-if="activeSub === 'payments' && route.query.id" />
    <PaymentsList v-else-if="activeSub === 'payments'" />
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
import PaymentsList from "@/pages/sales/PaymentsList.vue";
import ReceiptDetail from "@/pages/sales/ReceiptDetail.vue";
import ChallansList from "@/pages/sales/ChallansList.vue";
import ChallanDetail from "@/pages/sales/ChallanDetail.vue";
import CreditsList from "@/pages/sales/CreditsList.vue";
import ToBillQueue from "@/pages/sales/ToBillQueue.vue";
import { useUi } from "@/composables/useUi";
import { SUBTABS, defaultSub, tabsFor } from "@/data/nav";

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

const subs = tabsFor("sales");
const activeSub = computed(() => route.params.sub || defaultSub("sales"));
const entityName = computed(() => (entities.find((e) => e.id === entityId.value) || entities[0]).name);
const title = computed(() => {
  // The title must name every sub, including the pipeline stages that are
  // no longer drawn as tabs — otherwise standing on "Delivered" shows the
  // module name and the page stops saying where you are.
  const found = (SUBTABS.sales || []).find((s) => s[0] === activeSub.value);
  return found ? t(found[1]) : t("nav.sales");
});

function goSub(s) { router.push(`/accounting/sales/${s}`); }
</script>
