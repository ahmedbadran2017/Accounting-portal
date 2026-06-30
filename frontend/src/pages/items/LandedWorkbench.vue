<template>
  <div class="space-y-3.5">
    <!-- Items / Health view toggle -->
    <div class="flex gap-1 bg-white border border-line rounded-chip p-1 w-fit shadow-card">
      <button v-for="v in VIEWS" :key="v.k" class="px-3.5 py-1.5 rounded-lg text-[12px] font-semibold whitespace-nowrap inline-flex items-center gap-1.5" :class="view === v.k ? 'bg-app-warm text-accent-dark shadow-card' : 'text-ink-3 hover:text-ink'" @click="view = v.k">
        <Icon :name="v.icon" :size="13" />{{ v.label() }}
      </button>
    </div>

    <CostingHealth v-if="view === 'health'" />
    <template v-else>
    <!-- context strip -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <div class="bg-white rounded-card border border-line shadow-card px-4 py-3">
        <div class="text-[10px] font-bold uppercase tracking-wider text-ink-muted flex items-center gap-1.5"><Icon name="wallet" :size="13" color="#0f766e" />{{ L("With a cost basis","لها أساس تكلفة","Base de coût") }}</div>
        <div class="text-[20px] font-extrabold mt-1 tnum">{{ (def.purchased_items||0).toLocaleString() }}</div>
        <div class="text-[10.5px] text-ink-muted mt-0.5">{{ L("of","من","sur") }} {{ (def.catalogue_items||0).toLocaleString() }} {{ L("SKUs","صنف","SKU") }}</div>
      </div>
      <div class="bg-white rounded-card border border-line shadow-card px-4 py-3">
        <div class="text-[10px] font-bold uppercase tracking-wider text-ink-muted flex items-center gap-1.5"><Icon name="truck" :size="13" color="#0369a1" />{{ L("Inbound freight","شحن داخل","Fret entrant") }}</div>
        <div class="text-[20px] font-extrabold mt-1 tnum" style="color:#0369a1">{{ (def.suggested_freight_per_kg||0).toLocaleString() }}</div>
        <div class="text-[10.5px] text-ink-muted mt-0.5">{{ ccy }} / {{ L("kg suggested","كجم مقترح","kg") }}</div>
      </div>
      <div class="col-span-2 bg-white rounded-card border border-line shadow-card px-4 py-3 flex items-center">
        <div class="text-[11.5px] text-ink-2 leading-relaxed">
          <Icon name="alert" :size="13" color="#b45309" class="inline" />
          {{ L("Costs are re-priced at the correct exchange rate per purchase date, then inbound freight is allocated by weight. Click any item to open its cost card.","التكلفة بتتسعّر بسعر الصرف الصح بتاريخ الشراء، وبعدين الشحن الداخل يتوزّع بالوزن. اضغط أي صنف لكارت التكلفة.","Recalculé au bon taux de change puis fret réparti au poids.") }}
        </div>
      </div>
    </div>

    <!-- scope + search -->
    <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
      <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
        <div class="flex gap-1 bg-app-warm/60 rounded-chip p-0.5">
          <button v-for="sc in SCOPES" :key="sc.k" class="px-2.5 py-1 rounded-lg text-[11.5px] font-semibold whitespace-nowrap" :class="scope === sc.k ? 'bg-white shadow-card text-accent-dark' : 'text-ink-3 hover:text-ink'" @click="setScope(sc.k)">{{ sc.label() }}</button>
        </div>
        <span class="hidden lg:inline text-[11px] text-ink-muted">{{ (st.total.value || 0).toLocaleString() }} {{ L("items","صنف","articles") }}</span>
        <div class="ms-auto relative">
          <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
          <input v-model.trim="st.search.value" :placeholder="L('SKU / name…','SKU / اسم…','SKU / nom…')" class="w-44 sm:w-60 h-9 bg-app-warm/40 border border-line-2 rounded-[10px] ps-9 pe-3 text-[12.5px] focus:outline-none focus:border-accent/40 focus:bg-white" />
        </div>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead><tr style="background:#fafaf9" class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">
            <th class="px-4 py-2 text-start">{{ L("Item","الصنف","Article") }}</th>
            <th class="px-3 py-2 text-end cursor-pointer" @click="st.setSort('weight')">{{ L("Weight","الوزن","Poids") }}</th>
            <th class="px-3 py-2 text-start hidden sm:table-cell">{{ L("Last buy","آخر شراء","Dernier achat") }}</th>
            <th v-if="scope==='purchased'" class="px-3 py-2 text-end cursor-pointer" @click="st.setSort('value')">{{ L("Spent","المصروف","Dépensé") }}</th>
            <th v-else class="px-3 py-2 text-end">{{ L("Booked cost","التكلفة المسجّلة","Coût") }}</th>
            <th class="px-4 py-2 text-end"></th>
          </tr></thead>
          <tbody>
            <tr v-for="r in st.rows.value" :key="r.item_code" class="border-t border-line-hair hover:bg-app-warm/50 cursor-pointer group" @click="open(r.item_code)">
              <td class="px-4 py-2">
                <div class="flex items-center gap-2.5 min-w-0">
                  <img v-if="r.image" :src="r.image" class="w-8 h-8 rounded-lg object-cover bg-app-warm shrink-0" loading="lazy" />
                  <span v-else class="w-8 h-8 rounded-lg bg-app-warm grid place-items-center shrink-0"><Icon name="grid" :size="13" color="#9a8f86" /></span>
                  <div class="min-w-0">
                    <div class="truncate font-medium group-hover:text-accent-dark max-w-[260px]">{{ r.item_name || r.item_code }}</div>
                    <div class="text-[10.5px] text-ink-muted font-mono">{{ r.sku || r.item_code }}</div>
                  </div>
                </div>
              </td>
              <td class="px-3 py-2 text-end tnum whitespace-nowrap">
                <span v-if="r.no_weight" class="inline-flex items-center gap-1 text-rose-600 font-semibold"><Icon name="alert" :size="11" />{{ L("none","لا","—") }}</span>
                <span v-else :class="r.weight_outlier ? 'text-amber-700 font-semibold' : 'text-ink-2'">{{ r.weight }}<span class="text-[10px] text-ink-muted"> kg</span><Icon v-if="r.weight_outlier" name="alert" :size="10" color="#b45309" class="inline ms-0.5" /></span>
              </td>
              <td class="px-3 py-2 text-ink-3 hidden sm:table-cell whitespace-nowrap">
                <template v-if="scope==='purchased'">{{ r.last_rate_fc }} {{ r.cur }} · {{ r.last_dt }}</template>
                <template v-else>{{ r.last_rate_fc || "—" }}</template>
              </td>
              <td v-if="scope==='purchased'" class="px-3 py-2 text-end tnum font-semibold whitespace-nowrap">{{ money(r.spent) }}</td>
              <td v-else class="px-3 py-2 text-end tnum whitespace-nowrap" :class="Number(r.cost)>0 ? '' : 'text-ink-muted'">{{ Number(r.cost)>0 ? money(r.cost) : "—" }}</td>
              <td class="px-4 py-2 text-end w-px"><Icon name="arrow" :size="13" color="#cbd5e1" class="opacity-0 group-hover:opacity-100 transition-opacity" /></td>
            </tr>
          </tbody>
        </table>
      </div>
      <TableLoading v-if="st.loading.value" :rows="8" />
      <div v-else-if="!st.rows.value.length" class="py-10 text-center text-[12px] text-ink-muted">{{ L("No items.","لا أصناف.","Aucun.") }}</div>
      <ServerPager :t="st" />
    </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import ServerPager from "@/components/ServerPager.vue";
import TableLoading from "@/components/TableLoading.vue";
import CostingHealth from "@/pages/items/CostingHealth.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useServerTable } from "@/composables/useServerTable";
import { useUi } from "@/composables/useUi";

const { locale } = useI18n();
const { entityId } = useUi();
const router = useRouter();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const money = (n) => { n = Number(n) || 0; const a = Math.abs(n); return (a >= 1e6 ? (n / 1e6).toFixed(2) + "M" : a >= 1e3 ? Math.round(n / 1e3) + "K" : Math.round(n)).toLocaleString(); };

const def = ref({});
const ccy = computed(() => def.value.currency || "MAD");
const view = ref("items");
const VIEWS = [
  { k: "items", icon: "wallet", label: () => L("Item costs", "تكاليف الأصناف", "Coûts") },
  { k: "health", icon: "alert", label: () => L("Costing health", "صحة التكلفة", "Santé") },
];
const scope = ref("purchased");
const SCOPES = [
  { k: "purchased", label: () => L("Purchased", "المشتراة", "Achetés") },
  { k: "noweight", label: () => L("Weight issues", "مشاكل وزن", "Poids") },
  { k: "all", label: () => L("All", "الكل", "Tous") },
];

async function loadDefaults() {
  try { def.value = await api.call("accounting_portal.api.landed_engine.landed_defaults", { company: currentCompany() }) || {}; }
  catch { def.value = {}; }
}

const st = useServerTable(
  (params) => api.call("accounting_portal.api.landed_engine.landed_workbench_list", { company: currentCompany(), scope: scope.value, ...params }),
  { pageSize: 25, sortField: "value", sortDir: "desc", filters: {} },
);
loadDefaults();
st.load();
watch(entityId, () => { loadDefaults(); st.page.value = 1; st.setFilters({ _scope: scope.value }); });

function setScope(k) { if (k === scope.value) return; scope.value = k; st.page.value = 1; st.setFilters({ _scope: k }); }
function open(code) { router.push({ path: "/accounting/items/costing", query: { item: code } }); }
</script>
