<template>
  <div class="space-y-3.5">
    <button type="button" class="inline-flex items-center gap-1.5 h-8 px-3 rounded-chip border border-line-2 bg-white text-[12px] font-semibold text-ink-2 hover:bg-app-warm" @click="back">
      <Icon name="arrow" :size="13" class="rotate-180" />{{ L("Back","رجوع","Retour") }}
    </button>
    <TableLoading v-if="loading" :rows="4" />
    <div v-else-if="!d.slip" class="bg-white rounded-card border border-line shadow-card px-4 py-14 text-center text-[12px] text-ink-muted">{{ L("Slip not found.","المسير غير موجود.","Introuvable.") }}</div>
    <template v-else>
      <div class="bg-white rounded-card border border-line shadow-card px-4 py-3.5 flex items-center gap-3 flex-wrap">
        <div>
          <div class="text-[14px] font-extrabold">{{ s.employee_name }}</div>
          <div class="text-[11px] text-ink-muted font-mono">{{ s.name }} · {{ s.start_date }} → {{ s.end_date }}</div>
        </div>
        <div class="ms-auto text-end">
          <div class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Net pay","الصافي","Net") }}</div>
          <div class="text-[22px] font-extrabold tnum" style="color:#0f766e">{{ money(s.net_pay) }} <span class="text-[12px] text-ink-muted font-bold">{{ ccy }}</span></div>
        </div>
      </div>
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
          <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><span class="w-2.5 h-2.5 rounded-sm bg-teal-600"></span><span class="text-[12px] font-bold">{{ L("Earnings","الاستحقاقات","Gains") }}</span><span class="ms-auto tnum font-bold">{{ money(s.gross_pay) }}</span></div>
          <table class="w-full text-[12px]"><tbody>
            <tr v-for="(r,i) in d.earnings" :key="i" class="border-t border-line-hair first:border-t-0"><td class="px-4 py-2">{{ r.component }}</td><td class="px-4 py-2 text-end tnum font-semibold">{{ money(r.amount) }}</td></tr>
          </tbody></table>
        </div>
        <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
          <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><span class="w-2.5 h-2.5 rounded-sm bg-rose-600"></span><span class="text-[12px] font-bold">{{ L("Deductions","الخصومات","Retenues") }}</span><span class="ms-auto tnum font-bold text-rose-600">−{{ money(s.total_deduction) }}</span></div>
          <table class="w-full text-[12px]"><tbody>
            <tr v-for="(r,i) in d.deductions" :key="i" class="border-t border-line-hair first:border-t-0"><td class="px-4 py-2">{{ r.component }}</td><td class="px-4 py-2 text-end tnum font-semibold text-rose-600">−{{ money(r.amount) }}</td></tr>
            <tr v-if="!d.deductions.length"><td colspan="2" class="px-4 py-4 text-center text-ink-muted">{{ L("None","لا شيء","Aucune") }}</td></tr>
          </tbody></table>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";

const { locale } = useI18n();
const { entityId } = useUi();
const route = useRoute();
const router = useRouter();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const money = (n) => Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const d = ref({ earnings: [], deductions: [] });
const loading = ref(true);
const slip = computed(() => route.query.slip);
const s = computed(() => d.value.slip || {});
const ccy = computed(() => d.value.currency || "MAD");

async function load() {
  if (!slip.value) return;
  loading.value = true;
  try { d.value = await api.call("accounting_portal.api.payroll.salary_slip_detail", { company: currentCompany(), slip: slip.value }) || { earnings: [], deductions: [] }; }
  catch { d.value = { earnings: [], deductions: [] }; }
  finally { loading.value = false; }
}
load();
watch(slip, load);
watch(entityId, () => router.push({ path: "/accounting/payroll" }));
function back() { router.back(); }
</script>
