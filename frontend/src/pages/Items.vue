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

    <!-- Inventory health — the auditor's #1 finding lands here -->
    <div v-if="health && !health.healthy" class="rounded-[14px] border border-amber-200 bg-amber-50 overflow-hidden shadow-card">
      <div class="px-4 py-3 flex items-start gap-3">
        <span class="w-9 h-9 rounded-[10px] grid place-items-center flex-shrink-0" style="background:#fef3c7"><Icon name="alert" :size="18" color="#b45309" /></span>
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 flex-wrap">
            <span class="text-[13.5px] font-bold text-amber-900">{{ L("Inventory health — perpetual stock isn't relieving to COGS","صحة المخزون — الجرد المستمر لا يُرحّل لتكلفة المبيعات","Santé du stock — non soldé en CMV") }}</span>
            <span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-200 text-amber-800">{{ healthLive ? L("LIVE","مباشر","LIVE") : L("SAMPLE","عيّنة","ÉCH.") }}</span>
          </div>
          <p class="text-[12px] text-amber-800 mt-1 leading-relaxed">{{ L("Stock-in-hand carries "+money0(health.stock_in_hand)+" MAD while “"+(health.adjustment_account||'Stock Adjustment')+"” absorbs "+money0(health.adjustment_balance)+". Deliveries aren't posting cost of goods sold, so per-order margin is unmeasurable and the balance sheet is overstated.","المخزون يحمل "+money0(health.stock_in_hand)+" درهم بينما يمتص حساب التسوية "+money0(health.adjustment_balance)+". التسليمات لا تُرحّل تكلفة المبيعات، فالهامش غير قابل للقياس.","Le stock porte "+money0(health.stock_in_hand)+" MAD.") }}</p>
        </div>
      </div>
      <div class="flex items-center gap-3 px-4 py-2.5 border-t border-amber-200 bg-amber-100/40">
        <div class="flex-1 grid grid-cols-3 gap-2 text-center">
          <div><div class="text-[10px] font-bold uppercase tracking-wider text-amber-700">{{ L("Stock in hand","المخزون","Stock") }}</div><div class="text-[13.5px] font-extrabold tnum text-amber-900">{{ money0(health.stock_in_hand) }}</div></div>
          <div><div class="text-[10px] font-bold uppercase tracking-wider text-amber-700">{{ L("Adjustment","التسوية","Ajustement") }}</div><div class="text-[13.5px] font-extrabold tnum text-amber-900">{{ money0(health.adjustment_balance) }}</div></div>
          <div><div class="text-[10px] font-bold uppercase tracking-wider text-amber-700">{{ L("Revenue (FY)","الإيراد","Produits") }}</div><div class="text-[13.5px] font-extrabold tnum text-amber-900">{{ money0(health.revenue) }}</div></div>
        </div>
        <button class="h-8 px-3.5 rounded-[9px] bg-amber-600 hover:bg-amber-700 text-white text-[11.5px] font-bold inline-flex items-center gap-1.5" @click="proposeFix">
          <Icon name="shield" :size="13" />{{ L("Propose correcting entry","اقترح قيد تصحيح","Proposer une écriture") }}
        </button>
      </div>
    </div>

    <ItemDetail v-if="activeSub === 'items' && route.query.id" />
    <ItemsList v-else-if="activeSub === 'items'" />
    <PriceListDetail v-else-if="activeSub === 'pricelists' && route.query.id" />
    <PriceListsList v-else-if="activeSub === 'pricelists'" />
    <LandedCostDetail v-else-if="activeSub === 'landed' && route.query.id" />
    <LandedCost v-else-if="activeSub === 'landed'" />
    <ScaffoldTable v-else />
  </div>
</template>

<script setup>
import { computed, ref, onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import PageHeader from "@/components/PageHeader.vue";
import ScaffoldTable from "@/components/ScaffoldTable.vue";
import LandedCost from "@/pages/items/LandedCost.vue";
import LandedCostDetail from "@/pages/items/LandedCostDetail.vue";
import ItemsList from "@/pages/items/ItemsList.vue";
import ItemDetail from "@/pages/items/ItemDetail.vue";
import PriceListsList from "@/pages/items/PriceListsList.vue";
import PriceListDetail from "@/pages/items/PriceListDetail.vue";
import { useUi } from "@/composables/useUi";
import { SUBTABS, defaultSub } from "@/data/nav";
import { liveOrSample, currentCompany } from "@/composables/useLive";
import { money0 } from "@/composables/useReports";

const { t, locale } = useI18n();
const route = useRoute();
const router = useRouter();
const { entityId, entities } = useUi();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

const subs = SUBTABS.items;
const activeSub = computed(() => route.params.sub || defaultSub("items"));
const entityName = computed(() => (entities.find((e) => e.id === entityId.value) || entities[0]).name);
const title = computed(() => {
  const found = subs.find((s) => s[0] === activeSub.value);
  return found ? t(found[1]) : t("nav.items");
});
function goSub(s) { router.push(`/accounting/items/${s}`); }

const SAMPLE_HEALTH = { stock_in_hand: 687123522, adjustment_account: "71.004 - Stock Adjustment - JM", adjustment_balance: -680873788, revenue: 7810535, distortion: 1368000000, healthy: false };
const health = ref(null);
const healthLive = ref(false);
async function loadHealth() {
  const r = await liveOrSample("accounting_portal.api.reports.inventory_health", { company: currentCompany() }, () => SAMPLE_HEALTH);
  healthLive.value = r.live; health.value = r.data;
}
function proposeFix() { router.push("/accounting/accountant/journals"); }
onMounted(loadHealth);
watch(entityId, loadHealth);
</script>
