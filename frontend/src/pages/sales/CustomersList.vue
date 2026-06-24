<template>
  <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
    <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
      <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#faf6f4"><Icon name="users" :size="14" color="#a33a22" /></span>
      <span class="text-[13px] font-bold">{{ L("Customers","العملاء","Clients") }}</span>
      <span v-if="live !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border"
            :style="live ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">
        {{ live ? L("Live","مباشر","En direct") : L("Sample","عيّنة","Échantillon") }}
      </span>
      <span class="text-[11px] text-ink-muted flex-1">{{ L("LTV & delivery health · computed from invoices","القيمة العمرية وصحة التسليم · محسوبة من الفواتير","LTV & livraison · calculé depuis les factures") }}</span>
      <div class="relative w-[200px]">
        <span class="absolute top-1/2 -translate-y-1/2 start-2.5 text-ink-muted pointer-events-none flex"><Icon name="search" :size="14" /></span>
        <input v-model.trim="search" :placeholder="L('Search name…','بحث بالاسم…','Rechercher…')" class="w-full h-8 ps-[30px] pe-2.5 rounded-[9px] border border-line-2 bg-app-warm2 text-[12px] focus:outline-none focus:border-accent/40" />
      </div>
    </div>

    <!-- Tag filter -->
    <div class="flex items-center gap-1.5 px-4 py-2.5 border-b border-line-hair flex-wrap">
      <span class="text-[10px] font-bold uppercase tracking-wider text-ink-muted me-1">{{ L("Filter","تصفية","Filtrer") }}</span>
      <button class="text-[11px] font-semibold px-2.5 py-1 rounded-full border transition"
              :class="activeTag === null ? 'bg-ink text-white border-ink' : 'bg-white text-ink-3 border-line-2 hover:bg-app-warm'"
              @click="activeTag = null">{{ L("All","الكل","Tous") }} <span class="opacity-60">{{ rows.length }}</span></button>
      <button v-for="key in TAG_ORDER" :key="key"
              class="text-[11px] font-semibold px-2.5 py-1 rounded-full border transition inline-flex items-center gap-1.5"
              :class="activeTag === key ? 'border-transparent' : 'bg-white border-line-2 hover:bg-app-warm'"
              :style="activeTag === key ? `background:${TAG_META[key].fg};color:#fff` : `color:${TAG_META[key].fg}`"
              @click="activeTag = activeTag === key ? null : key">
        <span class="w-1.5 h-1.5 rounded-full" :style="{ background: activeTag === key ? '#fff' : TAG_META[key].fg }"></span>{{ TAG_META[key].label(L) }} <span class="opacity-60">{{ tagCount(key) }}</span>
      </button>
    </div>
    <div class="overflow-x-auto">
      <table class="w-full text-[12px]">
        <thead>
          <tr style="background:#fafaf9">
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Customer","العميل","Client") }}</th>
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("City","المدينة","Ville") }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Orders","الطلبات","Commandes") }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Delivery","التسليم","Livraison") }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">RTO</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">LTV</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Credit","رصيد دائن","Crédit") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(c, i) in filtered" :key="c.name" class="border-t border-line-hair hover:bg-app-warm/70 cursor-pointer" @click="open(c.name)">
            <td class="px-4 py-2.5">
              <span class="flex items-center gap-2.5">
                <span class="w-7 h-7 rounded-full grid place-items-center text-white text-[10px] font-bold flex-shrink-0" :style="{ background: AV[c.av] || AV[avKeys[i % avKeys.length]] }">{{ initials(c.customer_name || c.name) }}</span>
                <span class="min-w-0">
                  <span class="font-semibold whitespace-nowrap">{{ c.customer_name || c.name }}</span>
                  <span v-if="c.tags && c.tags.length" class="flex items-center gap-1 mt-0.5">
                    <span v-for="tg in c.tags" :key="tg" class="text-[9px] font-bold px-1.5 py-px rounded-full border leading-tight"
                          :style="`background:${TAG_META[tg].bg};color:${TAG_META[tg].fg};border-color:${TAG_META[tg].bd}`">{{ TAG_META[tg].label(L) }}</span>
                  </span>
                </span>
              </span>
            </td>
            <td class="px-4 py-2.5 text-ink-2 whitespace-nowrap">{{ c.city }}</td>
            <td class="px-4 py-2.5 text-end tnum font-semibold">{{ c.orders }}</td>
            <td class="px-4 py-2.5 text-end tnum font-bold" :style="{ color: deliveryColor(c.delivery) }">{{ c.delivery }}</td>
            <td class="px-4 py-2.5 text-end tnum" :style="{ color: rtoColor(c.rto) }">{{ c.rto }}</td>
            <td class="px-4 py-2.5 text-end tnum font-semibold whitespace-nowrap">{{ c.ltv }}</td>
            <td class="px-4 py-2.5 text-end tnum font-semibold whitespace-nowrap" style="color:#7c3aed">{{ c.credit }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { initials, deliveryColor, rtoColor } from "@/data/customers";
import { AV } from "@/data/orders";
import { useCustomers } from "@/composables/useCustomers";

const { locale } = useI18n();
const router = useRouter();
const { loadList, live } = useCustomers();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const search = ref("");
const rows = ref([]);
const activeTag = ref(null);
const avKeys = ["rose", "sky", "amber", "emerald", "violet", "accent"];

const TAG_ORDER = ["vip", "loyal", "returning", "new", "risk"];
const TAG_META = {
  vip: { label: (L) => L("VIP", "مميّز", "VIP"), bg: "#f5f3ff", fg: "#7c3aed", bd: "#ddd6fe" },
  loyal: { label: (L) => L("Loyal", "وفيّ", "Fidèle"), bg: "#ecfdf5", fg: "#047857", bd: "#a7f3d0" },
  returning: { label: (L) => L("Returning", "متكرّر", "Récurrent"), bg: "#eff6ff", fg: "#0369a1", bd: "#bae6fd" },
  new: { label: (L) => L("New", "جديد", "Nouveau"), bg: "#f5f5f4", fg: "#57534e", bd: "#e7e5e4" },
  risk: { label: (L) => L("At risk", "محفوف بالمخاطر", "À risque"), bg: "#fef2f2", fg: "#b91c1c", bd: "#fecaca" },
};

const filtered = computed(() => (activeTag.value ? rows.value.filter((c) => (c.tags || []).includes(activeTag.value)) : rows.value));
const tagCount = (key) => rows.value.filter((c) => (c.tags || []).includes(key)).length;

async function reload() { rows.value = await loadList(search.value); }
let timer;
watch(search, () => { clearTimeout(timer); timer = setTimeout(reload, 300); });
onMounted(reload);

function open(name) { router.push({ path: "/accounting/sales/customers", query: { id: name } }); }
</script>
