<template>
  <component :is="view" />
</template>

<script setup>
import { computed } from "vue";
import { useRoute } from "vue-router";
import Dashboard from "@/pages/Dashboard.vue";
import Copilot from "@/pages/Copilot.vue";
import Sales from "@/pages/Sales.vue";
import Purchases from "@/pages/Purchases.vue";
import Banking from "@/pages/Banking.vue";
import Accountant from "@/pages/Accountant.vue";
import Items from "@/pages/Items.vue";
import Reports from "@/pages/Reports.vue";
import Settings from "@/pages/Settings.vue";
import ModulePage from "@/pages/ModulePage.vue";

// Single dynamic child of AppLayout: dispatch on the :module route param so we
// don't enumerate a route per module. Dashboard and Copilot are bespoke; every
// other module renders the generic sub-tabbed ModulePage.
const route = useRoute();
const view = computed(() => {
  const m = route.params.module;
  if (m === "dashboard") return Dashboard;
  if (m === "copilot") return Copilot;
  if (m === "sales") return Sales;
  if (m === "purchases") return Purchases;
  if (m === "banking") return Banking;
  if (m === "accountant") return Accountant;
  if (m === "items") return Items;
  if (m === "reports") return Reports;
  if (m === "settings") return Settings;
  return ModulePage;
});
</script>
