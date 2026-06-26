<template>
  <div class="space-y-3">
    <div class="flex items-center gap-2 flex-wrap">
      <span class="text-[13px] font-bold">{{ L("Fixed assets","الأصول الثابتة","Immobilisations") }}</span>
      <span v-if="isLive !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="isLive ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ isLive ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échant.") }}</span>
      <span class="text-[11px] text-ink-muted">{{ L("register · gross cost, net book value & depreciation","السجل · التكلفة والقيمة الدفترية والإهلاك","registre") }}</span>
    </div>

    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <div v-for="m in cards" :key="m.label" class="bg-white border border-line rounded-[14px] p-4 shadow-card">
        <div class="text-[10.5px] font-semibold text-ink-3">{{ m.label }}</div>
        <div class="text-[19px] font-bold tnum mt-1.5">{{ m.value }}</div>
      </div>
    </div>

    <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
      <TableLoading v-if="loading" :rows="8" />
      <table v-else class="w-full text-[12px]">
        <thead><tr style="background:#fafaf9">
          <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Asset","الأصل","Actif") }}</th>
          <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Category","الفئة","Catégorie") }}</th>
          <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Gross","الإجمالي","Brut") }}</th>
          <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Net book value","القيمة الدفترية","VNC") }}</th>
          <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Status","الحالة","Statut") }}</th>
        </tr></thead>
        <tbody>
          <tr v-for="(a, i) in d.rows" :key="i" class="border-t border-line-hair hover:bg-app-warm/40">
            <td class="px-4 py-2.5 font-semibold truncate max-w-[260px]">{{ a.asset_name }}</td>
            <td class="px-4 py-2.5 text-ink-3 truncate max-w-[180px]">{{ a.category }}</td>
            <td class="px-4 py-2.5 text-end tnum">{{ money(a.gross) }}</td>
            <td class="px-4 py-2.5 text-end tnum font-semibold">{{ money(a.nbv) }}</td>
            <td class="px-4 py-2.5"><span class="text-[10px] font-bold px-2 py-0.5 rounded-badge" :style="statusStyle(a.status)">{{ a.status }}</span></td>
          </tr>
          <tr v-if="!d.rows.length"><td colspan="5" class="px-4 py-10 text-center text-ink-muted text-[12px]">{{ L("No assets for this entity.","لا أصول لهذه الشركة.","Aucun actif.") }}</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from "vue";
import { useI18n } from "vue-i18n";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";

const { locale } = useI18n();
const { entityId } = useUi();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const money = (n) => Number(n || 0).toLocaleString("en-US", { maximumFractionDigits: 0 });

const d = ref({ rows: [], summary: {}, currency: "MAD" });
const isLive = ref(null);
const loading = ref(true);

async function load() {
  loading.value = true;
  try { d.value = await api.call("accounting_portal.api.reports.fixed_assets", { company: currentCompany() }); isLive.value = true; }
  catch { d.value = { rows: [], summary: {}, currency: "MAD" }; isLive.value = false; }
  finally { loading.value = false; }
}
onMounted(load);
watch(entityId, load);

const cards = computed(() => {
  const s = d.value.summary || {}; const c = d.value.currency || "MAD";
  return [
    { label: L("Assets", "عدد الأصول", "Actifs"), value: s.count || 0 },
    { label: L("Gross cost", "التكلفة الإجمالية", "Coût brut"), value: money(s.gross) + " " + c },
    { label: L("Net book value", "القيمة الدفترية", "VNC"), value: money(s.nbv) + " " + c },
    { label: L("Accumulated dep.", "مجمع الإهلاك", "Amort. cumulé"), value: money(s.accumulated_dep) + " " + c },
  ];
});
function statusStyle(s) {
  if (s === "Submitted" || s === "Fully Depreciated") return "background:#ecfdf5;color:#047857";
  if (s === "Draft") return "background:#fffbeb;color:#b45309";
  if (s === "Scrapped" || s === "Sold") return "background:#fef2f2;color:#b91c1c";
  return "background:#f5f5f4;color:#57534e";
}
</script>
