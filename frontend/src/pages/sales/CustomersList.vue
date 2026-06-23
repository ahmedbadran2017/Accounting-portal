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
      <div class="relative w-[190px]">
        <span class="absolute inset-block-0 flex items-center ps-2.5 text-ink-muted pointer-events-none"><Icon name="search" :size="14" /></span>
        <input v-model.trim="search" :placeholder="L('Search…','بحث…','Rechercher…')" class="w-full h-8 ps-8 pe-2.5 rounded-[9px] border border-line-2 bg-app-warm2 text-[12px] focus:outline-none focus:border-accent/40" />
      </div>
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
          <tr v-for="(c, i) in rows" :key="c.name" class="border-t border-line-hair hover:bg-app-warm/70 cursor-pointer" @click="open(c.name)">
            <td class="px-4 py-2.5">
              <span class="flex items-center gap-2.5">
                <span class="w-7 h-7 rounded-full grid place-items-center text-white text-[10px] font-bold flex-shrink-0" :style="{ background: AV[c.av] || AV[avKeys[i % avKeys.length]] }">{{ initials(c.customer_name || c.name) }}</span>
                <span class="font-semibold whitespace-nowrap">{{ c.customer_name || c.name }}</span>
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
import { ref, watch, onMounted } from "vue";
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
const avKeys = ["rose", "sky", "amber", "emerald", "violet", "accent"];

async function reload() { rows.value = await loadList(search.value); }
let timer;
watch(search, () => { clearTimeout(timer); timer = setTimeout(reload, 300); });
onMounted(reload);

function open(name) { router.push({ path: "/accounting/sales/customers", query: { id: name } }); }
</script>
