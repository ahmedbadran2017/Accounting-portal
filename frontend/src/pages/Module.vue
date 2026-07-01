<template>
  <div v-if="err" class="bg-white border border-line rounded-card shadow-card p-8 text-center max-w-lg mx-auto mt-10">
    <div class="w-12 h-12 rounded-full grid place-items-center mx-auto" style="background:#fef2f2"><Icon name="alert" :size="22" color="#b91c1c" /></div>
    <div class="text-[15px] font-bold mt-3">{{ L("This page hit an error", "حصل خطأ في الصفحة", "Erreur sur cette page") }}</div>
    <div class="text-[12px] text-ink-3 mt-1.5">{{ L("It's been logged. Try reloading — if it persists, resetting saved filters usually fixes it.", "تم تسجيله. جرّب إعادة التحميل — لو استمر، إعادة ضبط الفلاتر المحفوظة بتحلّه غالبًا.", "Réessayez de recharger.") }}</div>
    <div v-if="errMsg" class="text-[10.5px] text-ink-muted font-mono mt-2 bg-app-warm rounded-chip px-3 py-2 break-words">{{ errMsg }}</div>
    <div class="flex items-center justify-center gap-2 mt-4">
      <button class="h-9 px-4 rounded-chip text-[12px] font-bold text-white bg-ink" @click="retry">{{ L("Reload page", "إعادة التحميل", "Recharger") }}</button>
      <button class="h-9 px-4 rounded-chip text-[12px] font-semibold text-ink-2 bg-white border border-line-2 hover:bg-app-warm" @click="resetFilters">{{ L("Reset saved filters", "إعادة ضبط الفلاتر", "Réinitialiser les filtres") }}</button>
    </div>
  </div>
  <component v-else :is="view" />
</template>

<script setup>
import { computed, ref, onErrorCaptured, watch, defineAsyncComponent } from "vue";
import { useRoute } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
// Dashboard is the landing page → keep it eager (in app.js) for instant first
// paint. Every other module is a lazy chunk, loaded only when navigated to.
import Dashboard from "@/pages/Dashboard.vue";
const lazy = (loader) => defineAsyncComponent(loader);
const Copilot = lazy(() => import("@/pages/Copilot.vue"));
const MyWork = lazy(() => import("@/pages/MyWork.vue"));
const Sales = lazy(() => import("@/pages/Sales.vue"));
const Purchases = lazy(() => import("@/pages/Purchases.vue"));
const Banking = lazy(() => import("@/pages/Banking.vue"));
const Accountant = lazy(() => import("@/pages/Accountant.vue"));
const Items = lazy(() => import("@/pages/Items.vue"));
const Reports = lazy(() => import("@/pages/Reports.vue"));
const Settings = lazy(() => import("@/pages/Settings.vue"));
const ExpenseCenter = lazy(() => import("@/pages/accountant/ExpenseCenter.vue"));
const Payroll = lazy(() => import("@/pages/accountant/Payroll.vue"));
const EmployeePayroll = lazy(() => import("@/pages/accountant/EmployeePayroll.vue"));
const SlipDetail = lazy(() => import("@/pages/accountant/SlipDetail.vue"));
const RunDetail = lazy(() => import("@/pages/accountant/RunDetail.vue"));
const ModulePage = lazy(() => import("@/pages/ModulePage.vue"));

// Single dynamic child of AppLayout: dispatch on the :module route param so we
// don't enumerate a route per module. Dashboard and Copilot are bespoke; every
// other module renders the generic sub-tabbed ModulePage.
const route = useRoute();
const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const view = computed(() => {
  const m = route.params.module;
  if (m === "dashboard") return Dashboard;
  if (m === "copilot") return Copilot;
  if (m === "mywork") return MyWork;
  if (m === "sales") return Sales;
  if (m === "purchases") return Purchases;
  if (m === "banking") return Banking;
  if (m === "accountant") return Accountant;
  if (m === "items") return Items;
  if (m === "reports") return Reports;
  if (m === "settings") return Settings;
  if (m === "expenses") return ExpenseCenter;
  if (m === "payroll") {
    if (route.query.slip) return SlipDetail;
    if (route.query.employee) return EmployeePayroll;
    if (route.query.run) return RunDetail;
    return Payroll;
  }
  return ModulePage;
});

// Error boundary: a single page's crash shows a recoverable message instead of a
// blank white screen, and never takes down the shell/nav.
const err = ref(false);
const errMsg = ref("");
onErrorCaptured((e) => {
  err.value = true;
  errMsg.value = String((e && e.message) || e).slice(0, 200);
  // eslint-disable-next-line no-console
  console.error("[Module] page error:", e);
  return false; // stop it propagating past the boundary
});
// Clear the error when navigating to a different module/sub.
watch(() => [route.params.module, route.params.sub], () => { err.value = false; errMsg.value = ""; });
function retry() { window.location.reload(); }
function resetFilters() {
  try {
    Object.keys(localStorage).filter((k) => k.startsWith("ap_tt_") || k.startsWith("ap_dash_") || k.startsWith("ap_stmt_") || k.startsWith("ap_gl_")).forEach((k) => localStorage.removeItem(k));
  } catch { /* ignore */ }
  window.location.reload();
}
</script>
