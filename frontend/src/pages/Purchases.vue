<template>
  <div class="space-y-3.5">
    <PageHeader :title="title" :subtitle="entityName">
      <template #actions>
        <div v-if="newLabel" class="flex items-center gap-2 ms-auto">
          <button class="inline-flex items-center gap-1.5 text-[12px] font-semibold text-white bg-brand hover:bg-brand-dark px-3 py-1.5 rounded-chip shadow-brand" @click="onNew">
            <Icon name="plus" :size="14" />{{ newLabel }}
          </button>
        </div>
      </template>
    </PageHeader>

    <!-- The sub-tab pill row that used to sit here rendered the same array the
         sidebar renders, with the same labels, so every destination in the
         portal was drawn twice on screen — and the active one a third time as
         the page title. The sidebar holds more of them legibly, shows which
         module they belong to, and is the navigation on mobile already. -->


    <VendorDetail v-if="activeSub === 'vendors' && route.query.id" />
    <VendorsList v-else-if="activeSub === 'vendors'" />
    <PurchaseDocDetail v-else-if="['tobuy','received','billed','topay','paid'].includes(activeSub) && route.query.id" />
    <PurchaseBucket v-else-if="['tobuy','received','billed','topay','paid'].includes(activeSub)" />
    <BillDetail v-else-if="activeSub === 'bills' && route.query.id" />
    <BillsList v-else-if="activeSub === 'bills'" />
    <PaymentMadeDetail v-else-if="activeSub === 'payments' && route.query.id" />
    <PaymentsMade v-else-if="activeSub === 'payments'" />
    <Shipments v-else-if="activeSub === 'shipments'" />
    <Cheques v-else-if="activeSub === 'cheques'" />
    <IntermediaryHub v-else-if="activeSub === 'intermediaries'" />
    <ScaffoldTable v-else />

    <PurchaseOrderForm v-if="showPo" @close="showPo = false" @created="onPoCreated" />
    <PaymentEntryForm v-if="showPayment" direction="out" @close="showPayment = false" @posted="onPaid" />
    <NewInvoiceModal v-if="showBill" kind="purchase" @close="showBill = false" @posted="onBilled" />
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import PageHeader from "@/components/PageHeader.vue";
import ScaffoldTable from "@/components/ScaffoldTable.vue";
import PurchaseOrderForm from "@/components/PurchaseOrderForm.vue";
import PaymentEntryForm from "@/components/PaymentEntryForm.vue";
import NewInvoiceModal from "@/components/NewInvoiceModal.vue";
import VendorsList from "@/pages/purchases/VendorsList.vue";
import VendorDetail from "@/pages/purchases/VendorDetail.vue";
import PurchaseBucket from "@/pages/purchases/PurchaseBucket.vue";
import PurchaseDocDetail from "@/pages/purchases/PurchaseDocDetail.vue";
import BillsList from "@/pages/purchases/BillsList.vue";
import BillDetail from "@/pages/purchases/BillDetail.vue";
import PaymentsMade from "@/pages/purchases/PaymentsMade.vue";
import PaymentMadeDetail from "@/pages/purchases/PaymentMadeDetail.vue";
import Cheques from "@/pages/purchases/Cheques.vue";
import Shipments from "@/pages/purchases/Shipments.vue";
import IntermediaryHub from "@/pages/purchases/IntermediaryHub.vue";
import { useUi } from "@/composables/useUi";
import { useToast } from "@/composables/useToast";
import { SUBTABS, defaultSub, tabsFor } from "@/data/nav";

const { t, locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const toast = useToast();
const route = useRoute();
const router = useRouter();
const { entityId, entities } = useUi();
const showPo = ref(false);
const showPayment = ref(false);
const showBill = ref(false);

// One button per module named the same thing on every tab, so "Payments made" —
// 2,129 supplier payments — offered "New PO" and no way to record a payment.
// The button names what the screen lists, like the Desk's "Add <doctype>".
const NEW = {
  tobuy:    { label: () => L("New PO", "أمر شراء", "Nouvelle CA"), open: () => (showPo.value = true) },
  payments: { label: () => L("Record payment", "تسجيل دفعة", "Enregistrer un paiement"), open: () => (showPayment.value = true) },
  bills:    { label: () => L("New bill", "فاتورة مورد", "Nouvelle facture"), open: () => (showBill.value = true) },
};
const newLabel = computed(() => (NEW[activeSub.value] ? NEW[activeSub.value].label() : ""));
function onNew() { NEW[activeSub.value]?.open(); }
function onPaid(res) {
  showPayment.value = false;
  const v = res && (res.voucher_no || res.name);
  if (res && res.status && res.status !== "Posted") toast.info(L("Recorded — awaiting an approver", "سُجّل — بانتظار موافِق", "Enregistré — en attente"));
  else if (v) router.push({ path: "/accounting/purchases/payments", query: { id: v } });
}
function onBilled(res) {
  showBill.value = false;
  const v = res && (res.voucher_no || res.name);
  if (v) router.push({ path: "/accounting/purchases/bills", query: { id: v } });
}
function onPoCreated() { if (activeSub.value === "tobuy") router.replace({ path: "/accounting/purchases/tobuy", query: { _r: Date.now() } }); }

const subs = tabsFor("purchases");
const activeSub = computed(() => route.params.sub || defaultSub("purchases"));
const entityName = computed(() => (entities.find((e) => e.id === entityId.value) || entities[0]).name);
const title = computed(() => {
  // The title must name every sub, including the pipeline stages that are
  // no longer drawn as tabs — otherwise standing on "Delivered" shows the
  // module name and the page stops saying where you are.
  const found = (SUBTABS.purchases || []).find((s) => s[0] === activeSub.value);
  return found ? t(found[1]) : t("nav.purchases");
});
function goSub(s) { router.push(`/accounting/purchases/${s}`); }
</script>
