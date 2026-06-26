<template>
  <div class="bg-white rounded-card border border-line overflow-hidden shadow-card">
    <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
      <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#eff6ff"><Icon name="truck" :size="14" color="#0369a1" /></span>
      <span class="text-[13px] font-bold">{{ L("Landed-cost vouchers","سندات التكلفة المحمَّلة","Bons de coût de revient") }}</span>
      <span v-if="isLive !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="isLive ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ isLive ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échant.") }}</span>
      <span class="hidden lg:inline text-[11px] text-ink-muted">{{ L("freight, customs, duties capitalised into inventory","شحن وجمارك ورسوم تُرسمل في المخزون","frais capitalisés dans le stock") }}</span>
    </div>
    <TableLoading v-if="loading" :rows="6" />
    <div v-else class="overflow-x-auto">
      <table class="w-full text-[12px]">
        <thead><tr style="background:#fafaf9">
          <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Voucher","السند","Bon") }}</th>
          <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Freight","الشحن","Fret") }}</th>
          <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Customs","الجمارك","Douane") }}</th>
          <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Duties","الرسوم","Droits") }}</th>
          <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Total","الإجمالي","Total") }}</th>
          <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Basis","الأساس","Base") }}</th>
          <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Status","الحالة","Statut") }}</th>
        </tr></thead>
        <tbody>
          <tr v-for="r in rows" :key="r.name" class="border-t border-line-hair hover:bg-app-warm/50 cursor-pointer" @click="open(r.name)">
            <td class="px-4 py-2.5 font-mono text-[11.5px] font-semibold">{{ r.name }}<div v-if="r.shipment && r.shipment !== '—'" class="text-[10px] text-ink-muted font-sans">{{ r.shipment }}</div></td>
            <td class="px-4 py-2.5 text-end tnum">{{ r.freight ? fmt(r.freight) : "—" }}</td>
            <td class="px-4 py-2.5 text-end tnum">{{ r.customs ? fmt(r.customs) : "—" }}</td>
            <td class="px-4 py-2.5 text-end tnum">{{ r.duties ? fmt(r.duties) : "—" }}</td>
            <td class="px-4 py-2.5 text-end tnum font-bold">{{ fmt(r.total) }}</td>
            <td class="px-4 py-2.5 text-ink-3">{{ L("By","حسب","Par") }} {{ r.basis }}</td>
            <td class="px-4 py-2.5"><span class="text-[10.5px] font-bold px-2 py-0.5 rounded-badge" :style="statusBadge(r.status)">{{ r.status }}</span></td>
          </tr>
          <tr v-if="!rows.length"><td colspan="7" class="px-4 py-12 text-center text-ink-muted text-[12px]">{{ L("No landed-cost vouchers.","لا سندات.","Aucun bon.") }}</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";

const { locale } = useI18n();
const { entityId } = useUi();
const router = useRouter();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US");

const rows = ref([]);
const isLive = ref(null);
const loading = ref(true);
const SAMPLE = [{ name: "LCV-0042", shipment: "Maslak — denim", freight: 18400, customs: 9200, duties: 22600, total: 53300, basis: "Value", status: "Posted" }];
async function load() {
  loading.value = true;
  try { rows.value = await api.call("accounting_portal.api.items.list_landed_costs", { company: currentCompany() }); isLive.value = true; }
  catch { rows.value = SAMPLE; isLive.value = false; }
  finally { loading.value = false; }
}
onMounted(load);
watch(entityId, load);
function open(name) { router.push({ path: "/accounting/items/landed", query: { id: name } }); }
function statusBadge(s) {
  if (s === "Posted") return "background:#ecfdf5;color:#047857";
  if (s === "Cancelled") return "background:#fef2f2;color:#b91c1c";
  return "background:#fffbeb;color:#b45309";
}
</script>
