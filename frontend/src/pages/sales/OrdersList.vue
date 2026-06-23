<template>
  <div class="space-y-3.5">
    <!-- State-machine strip (connected, click to filter) -->
    <div class="bg-white border border-line rounded-[14px] p-3.5 shadow-card overflow-x-auto">
      <div class="flex items-center gap-1 min-w-[680px]">
        <template v-for="(st, i) in MACHINE" :key="st">
          <button class="flex flex-col items-start flex-1 px-3 py-1.5 rounded-lg"
                  :class="filterState === st ? 'bg-app-warm' : 'hover:bg-app-warm/60'"
                  @click="filterState = filterState === st ? null : st">
            <span class="text-[18px] font-bold tnum leading-none" :style="{ color: filterState === st ? STATE_META[st].fg : '#1c1917' }">{{ machineCounts[st].toLocaleString() }}</span>
            <span class="text-[10.5px] font-semibold mt-[3px]" :class="filterState === st ? 'text-accent-dark' : 'text-ink-3'">{{ stateLabel(st, locale) }}</span>
          </button>
          <Icon v-if="i < MACHINE.length - 1" name="chev" :size="15" color="#d6d3d1" class="flex-shrink-0 rtl:rotate-180" />
        </template>
      </div>
    </div>

    <!-- Toolbar -->
    <div class="flex items-center gap-2">
      <div class="relative flex-1 max-w-xs">
        <span class="absolute inset-block-0 flex items-center ps-2.5 text-ink-muted"><Icon name="search" :size="15" /></span>
        <input v-model.trim="search" :placeholder="t('module.search')"
               class="w-full bg-white border border-line-2 rounded-chip ps-8 pe-3 py-1.5 text-[12px] focus:outline-none focus:border-accent/40" />
      </div>
      <span v-if="filterState" class="inline-flex items-center gap-1 text-[11px] font-semibold px-2.5 py-1 rounded-chip"
            :style="{ background: STATE_META[filterState].bg, color: STATE_META[filterState].fg }">
        {{ stateLabel(filterState, locale) }}
        <button class="opacity-70 hover:opacity-100" @click="filterState = null"><Icon name="close" :size="12" /></button>
      </span>
      <button class="inline-flex items-center gap-1.5 text-[12px] font-semibold text-white bg-accent hover:bg-accent-dark px-3 py-1.5 rounded-chip shadow-prim ms-auto">
        <Icon name="plus" :size="14" />{{ t("module.new") }}
      </button>
    </div>

    <!-- Table -->
    <div class="bg-white rounded-card border border-line overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead>
            <tr class="border-b border-line">
              <th v-for="c in cols" :key="c.key"
                  class="px-4 py-2.5 text-[10px] font-bold uppercase tracking-wider text-ink-muted whitespace-nowrap select-none cursor-pointer"
                  :class="c.end ? 'text-end' : 'text-start'"
                  @click="toggleSort(c.key)">
                {{ c.label }}<span v-if="sort.key === c.key" class="ms-0.5">{{ sort.dir > 0 ? "↑" : "↓" }}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="o in rows" :key="o.id"
                class="border-b border-line-hair hover:bg-app-warm/70 cursor-pointer"
                @click="open(o.id)">
              <td class="px-4 py-2.5 font-mono font-semibold text-ink whitespace-nowrap">{{ o.id }}</td>
              <td class="px-4 py-2.5">
                <span class="flex items-center gap-2">
                  <span class="w-6 h-6 rounded-full grid place-items-center text-white text-[9px] font-bold flex-shrink-0"
                        :style="{ background: AV[o.av] }">{{ o.initials }}</span>
                  <span class="truncate max-w-[160px]">{{ o.customer }}</span>
                </span>
              </td>
              <td class="px-4 py-2.5 text-ink-2 whitespace-nowrap">{{ o.city }}</td>
              <td class="px-4 py-2.5 text-ink-2 whitespace-nowrap">{{ o.carrier }}</td>
              <td class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ o.trackStatus }}</td>
              <td class="px-4 py-2.5">
                <span class="inline-block text-[10px] font-bold px-2 py-0.5 rounded-badge border"
                      :style="{ background: STATE_META[o.state].bg, color: STATE_META[o.state].fg, borderColor: STATE_META[o.state].bd }">
                  {{ stateLabel(o.state, locale) }}
                </span>
              </td>
              <td class="px-4 py-2.5">
                <span class="inline-block text-[10px] font-bold px-2 py-0.5 rounded-badge border"
                      :style="postingInfo(o.state, locale).posted ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#f5f5f4;color:#a8a29e;border-color:#e7e5e4'">
                  {{ postingInfo(o.state, locale).label }}
                </span>
              </td>
              <td class="px-4 py-2.5 text-end font-bold tnum whitespace-nowrap">{{ o.value }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="!rows.length" class="py-14 text-center text-[12px] text-ink-muted">{{ t("common.error_loading") }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { ORDERS, STATE_META, stateLabel, MACHINE, machineCounts, AV, postingInfo } from "@/data/orders";
import { useCreated } from "@/composables/useCreated";

const { t, locale } = useI18n();
const router = useRouter();
const { createdOrders } = useCreated();

const search = ref("");
const filterState = ref(null);
const sort = ref({ key: null, dir: 1 });

const cols = computed(() => [
  { key: "id", label: lbl("Order", "الطلب", "Commande") },
  { key: "customer", label: lbl("Customer", "العميل", "Client") },
  { key: "city", label: lbl("City", "المدينة", "Ville") },
  { key: "carrier", label: lbl("Carrier", "الناقل", "Transporteur") },
  { key: "trackStatus", label: lbl("Shipment", "الشحن", "Expédition") },
  { key: "state", label: lbl("State", "الحالة", "État") },
  { key: "posting", label: lbl("Posting", "الترحيل", "Passation") },
  { key: "value", label: lbl("Value", "القيمة", "Valeur"), end: true },
]);
function lbl(en, ar, fr) { return locale.value === "ar" ? ar : locale.value === "fr" ? fr : en; }

function toggleSort(key) {
  sort.value = sort.value.key === key ? { key, dir: -sort.value.dir } : { key, dir: 1 };
}

const rows = computed(() => {
  let r = [...createdOrders, ...ORDERS];
  const q = search.value.toLowerCase();
  if (q) r = r.filter((o) => (o.id + o.customer + o.city + o.carrier).toLowerCase().includes(q));
  if (filterState.value) r = r.filter((o) => o.state === filterState.value);
  if (sort.value.key) {
    const k = sort.value.key, d = sort.value.dir;
    r.sort((a, b) => {
      const av = a[k], bv = b[k];
      if (typeof av === "number" && typeof bv === "number") return (av - bv) * d;
      return String(av).localeCompare(String(bv)) * d;
    });
  }
  return r;
});

function open(id) { router.push({ path: "/accounting/sales/orders", query: { id } }); }
</script>
