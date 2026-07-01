<template>
  <div class="space-y-3.5">
    <button type="button" class="inline-flex items-center gap-1.5 h-8 px-3 rounded-chip border border-line-2 bg-white text-[12px] font-semibold text-ink-2 hover:bg-app-warm" @click="back">
      <Icon name="arrow" :size="13" class="rotate-180" />{{ L("Payroll","الرواتب","Paie") }}
    </button>

    <TableLoading v-if="loading" :rows="4" />
    <div v-else-if="!d.employee" class="bg-white rounded-card border border-line shadow-card px-4 py-14 text-center text-[12px] text-ink-muted">{{ L("Employee not found.","الموظف غير موجود.","Introuvable.") }}</div>

    <template v-else>
      <div class="bg-white rounded-card border border-line shadow-card px-4 py-3.5 flex items-center gap-3.5 flex-wrap">
        <span class="w-11 h-11 rounded-full grid place-items-center text-[13px] font-bold text-white shrink-0" style="background:#0f766e">{{ initials(e.employee_name) }}</span>
        <div class="min-w-0">
          <div class="text-[15px] font-extrabold">{{ e.employee_name }}</div>
          <div class="text-[11.5px] text-ink-muted">{{ e.designation || "—" }}<span v-if="e.department"> · {{ e.department }}</span></div>
          <div class="text-[10.5px] text-ink-muted mt-0.5">{{ e.name }}<span v-if="e.date_of_joining"> · {{ L("joined","انضم","embauché") }} {{ e.date_of_joining }}</span></div>
        </div>
        <span class="ms-auto text-[10px] font-bold px-2 py-1 rounded-chip" :class="e.status==='Active' ? 'bg-emerald-50 text-emerald-700' : 'bg-app-warm text-ink-muted'">{{ e.status }}</span>
      </div>

      <div class="grid grid-cols-3 gap-3">
        <Kpi :label="L('Base salary','الراتب الأساسي','Salaire base')" :value="money(d.base)" color="#0f766e" />
        <Kpi :label="L('YTD gross','إجمالي السنة','Brut cumul')" :value="money(d.ytd.gross)" color="#0369a1" />
        <Kpi :label="L('YTD net','صافي السنة','Net cumul')" :value="money(d.ytd.net)" color="#7c3aed" :sub="(d.ytd.slips||0)+' '+L('slips','مسير','bull.')" />
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <!-- structure -->
        <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
          <div class="px-4 py-2.5 border-b border-line-hair text-[12px] font-bold flex items-center gap-2"><Icon name="scale" :size="14" color="#0b5c4f" />{{ L("Latest structure","آخر هيكل","Structure") }}</div>
          <table class="w-full text-[12px]"><tbody>
            <tr v-for="(cmp,i) in d.components" :key="i" class="border-t border-line-hair first:border-t-0">
              <td class="px-4 py-2"><span class="w-2 h-2 rounded-sm inline-block me-2" :style="`background:${cmp.type==='earning' ? '#0f766e' : '#be123c'}`"></span>{{ cmp.component }}</td>
              <td class="px-4 py-2 text-end tnum font-semibold" :class="cmp.type==='deduction' ? 'text-rose-600' : ''">{{ cmp.type==='deduction' ? '−' : '' }}{{ money(cmp.amount) }}</td>
            </tr>
            <tr v-if="!d.components.length"><td colspan="2" class="px-4 py-6 text-center text-ink-muted">{{ L("No structure.","لا هيكل.","Aucune.") }}</td></tr>
          </tbody></table>
        </div>
        <!-- slip history -->
        <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
          <div class="px-4 py-2.5 border-b border-line-hair text-[12px] font-bold flex items-center gap-2"><Icon name="list" :size="14" color="#0b5c4f" />{{ L("Slip history","سجل المسيّرات","Historique") }}</div>
          <table class="w-full text-[12px]">
            <tbody>
              <tr v-for="s in d.slips" :key="s.name" class="border-t border-line-hair first:border-t-0 hover:bg-app-warm/40 cursor-pointer group" @click="openSlip(s.name)">
                <td class="px-4 py-2 font-semibold">{{ s.month }}</td>
                <td class="px-3 py-2 text-end tnum text-ink-3">{{ money(s.gross) }}</td>
                <td class="px-3 py-2 text-end tnum text-rose-500">−{{ money(s.ded) }}</td>
                <td class="px-4 py-2 text-end tnum font-bold group-hover:text-accent-dark">{{ money(s.net) }}</td>
              </tr>
              <tr v-if="!d.slips.length"><td colspan="4" class="px-4 py-6 text-center text-ink-muted">{{ L("No slips.","لا مسيّرات.","Aucun.") }}</td></tr>
            </tbody>
          </table>
        </div>
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
import { fmtMoney } from "@/utils/helpers";

const { locale } = useI18n();
const { entityId } = useUi();
const route = useRoute();
const router = useRouter();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
// Accounting precision: exact, grouped, 2 decimals — no K/M abbreviation.
const money = (n) => fmtMoney(n);
const Kpi = (p) => h("div", { class: "bg-white rounded-card border border-line shadow-card px-4 py-3" }, [
  h("div", { class: "text-[10px] font-bold uppercase tracking-wider text-ink-muted" }, p.label),
  h("div", { class: "text-[19px] font-extrabold mt-1 tnum", style: `color:${p.color}` }, p.value),
  p.sub ? h("div", { class: "text-[10px] text-ink-muted mt-0.5" }, p.sub) : null]);
Kpi.props = ["label", "value", "color", "sub"];

const d = ref({ components: [], slips: [], ytd: {} });
const loading = ref(true);
const employee = computed(() => route.query.employee);
const e = computed(() => d.value.employee || {});

async function load() {
  if (!employee.value) return;
  loading.value = true;
  try { d.value = await api.call("accounting_portal.api.payroll.employee_payroll", { company: currentCompany(), employee: employee.value }) || { components: [], slips: [], ytd: {} }; }
  catch { d.value = { components: [], slips: [], ytd: {} }; }
  finally { loading.value = false; }
}
load();
watch(employee, load);
watch(entityId, () => router.push({ path: "/accounting/payroll" }));

function initials(n) { return String(n || "?").trim().split(/\s+/).slice(0, 2).map((w) => w[0]).join("").toUpperCase() || "?"; }
function back() { if (window.history.length > 1) router.back(); else router.push({ path: "/accounting/payroll" }); }
function openSlip(name) { router.push({ path: "/accounting/payroll", query: { slip: name } }); }
</script>
