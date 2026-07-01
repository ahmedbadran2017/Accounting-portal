<template>
  <div class="space-y-3.5">
    <button type="button" class="inline-flex items-center gap-1.5 h-8 px-3 rounded-chip border border-line-2 bg-white text-[12px] font-semibold text-ink-2 hover:bg-app-warm" @click="back">
      <Icon name="arrow" :size="13" class="rotate-180" />{{ L("Payroll", "الرواتب", "Paie") }}
    </button>

    <TableLoading v-if="loading" :rows="4" />
    <div v-else-if="!d.run" class="bg-white rounded-card border border-line shadow-card px-4 py-14 text-center text-[12px] text-ink-muted">{{ L("Run not found.", "التشغيل غير موجود.", "Introuvable.") }}</div>

    <template v-else>
      <div class="bg-white rounded-card border border-line shadow-card px-4 py-3.5 flex items-center gap-3 flex-wrap">
        <span class="w-10 h-10 rounded-[12px] grid place-items-center text-white shrink-0" style="background:#0b5c4f"><Icon name="list" :size="18" /></span>
        <div class="min-w-0">
          <div class="text-[15px] font-extrabold font-mono">{{ d.run.name }}</div>
          <div class="text-[11.5px] text-ink-muted">{{ d.run.start_date }} → {{ d.run.end_date }} · {{ d.run.payroll_frequency }}</div>
        </div>
        <span class="ms-auto text-[10px] font-bold px-2 py-1 rounded-chip" :class="d.run.status==='Posted' ? 'bg-emerald-50 text-emerald-700' : d.run.status==='Cancelled' ? 'bg-rose-50 text-rose-600' : 'bg-amber-50 text-amber-700'">{{ d.run.status }}</span>
      </div>

      <div class="grid grid-cols-3 gap-3">
        <Kpi :label="L('Slips','المسيّرات','Bulletins')" :value="String(d.slips.length)" color="#0f766e" :sub="d.submitted + ' ' + L('posted','مُرحّل','postés') + (d.drafts ? ' · ' + d.drafts + ' ' + L('draft','مسودّة','brouillon') : '')" />
        <Kpi :label="L('Gross','الإجمالي','Brut')" :value="money(d.gross)" color="#0369a1" :sub="ccy" />
        <Kpi :label="L('Net','الصافي','Net')" :value="money(d.net)" color="#7c3aed" :sub="ccy" />
      </div>

      <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
        <div class="px-4 py-2.5 border-b border-line-hair text-[12px] font-bold flex items-center gap-2"><Icon name="users" :size="14" color="#0b5c4f" />{{ L("Slips in this run","مسيّرات هذا التشغيل","Bulletins") }}</div>
        <table class="w-full text-[12px]">
          <thead><tr style="background:#fafaf9" class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">
            <th class="px-4 py-2 text-start">{{ L("Employee","الموظف","Employé") }}</th>
            <th class="px-3 py-2 text-end">{{ L("Gross","الإجمالي","Brut") }}</th>
            <th class="px-3 py-2 text-end">{{ L("Deductions","الخصومات","Retenues") }}</th>
            <th class="px-4 py-2 text-end">{{ L("Net","الصافي","Net") }}</th>
          </tr></thead>
          <tbody>
            <tr v-for="s in d.slips" :key="s.name" class="border-t border-line-hair hover:bg-app-warm/40 cursor-pointer group" @click="openSlip(s.name)">
              <td class="px-4 py-2.5"><div class="font-semibold group-hover:text-accent-dark">{{ s.employee_name }}</div><div class="text-[10px] text-ink-muted font-mono">{{ s.name }}</div></td>
              <td class="px-3 py-2.5 text-end tnum text-ink-3">{{ money(s.gross) }}</td>
              <td class="px-3 py-2.5 text-end tnum text-rose-500">−{{ money(s.ded) }}</td>
              <td class="px-4 py-2.5 text-end tnum font-bold">{{ money(s.net) }}</td>
            </tr>
            <tr v-if="!d.slips.length"><td colspan="4" class="px-4 py-8 text-center text-ink-muted">{{ L("No slips.","لا مسيّرات.","Aucun.") }}</td></tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, h } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";
import { fmtAmount } from "@/utils/helpers";

const { locale } = useI18n();
const { entityId } = useUi();
const route = useRoute();
const router = useRouter();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const money = (n) => fmtAmount(n);
const Kpi = (p) => h("div", { class: "bg-white rounded-card border border-line shadow-card px-4 py-3" }, [
  h("div", { class: "text-[10px] font-bold uppercase tracking-wider text-ink-muted" }, p.label),
  h("div", { class: "text-[19px] font-extrabold mt-1 tnum", style: `color:${p.color}` }, p.value),
  p.sub ? h("div", { class: "text-[10px] text-ink-muted mt-0.5" }, p.sub) : null]);
Kpi.props = ["label", "value", "color", "sub"];

const d = ref({ run: null, slips: [] });
const loading = ref(true);
const ccy = computed(() => d.value.currency || "MAD");
const run = computed(() => route.query.run);

async function load() {
  if (!run.value) return;
  loading.value = true;
  try { d.value = await api.call("accounting_portal.api.payroll.payroll_run_detail", { company: currentCompany(), run: run.value }) || { run: null, slips: [] }; }
  catch { d.value = { run: null, slips: [] }; }
  finally { loading.value = false; }
}
load();
watch(run, load);
watch(entityId, () => router.push({ path: "/accounting/payroll" }));
function back() { if (window.history.length > 1) router.back(); else router.push({ path: "/accounting/payroll" }); }
function openSlip(name) { router.push({ path: "/accounting/payroll", query: { slip: name } }); }
</script>
