<template>
  <div class="space-y-3.5">
    <div class="flex items-center gap-2 flex-wrap">
      <div class="flex gap-1 bg-white border border-line rounded-chip p-1 w-fit shadow-card">
        <button v-for="v in VIEWS" :key="v.k" class="px-3 py-1.5 rounded-lg text-[12px] font-semibold whitespace-nowrap inline-flex items-center gap-1.5" :class="view === v.k ? 'bg-app-warm text-accent-dark shadow-card' : 'text-ink-3 hover:text-ink'" @click="view = v.k">
          <Icon :name="v.icon" :size="13" />{{ v.label() }}
        </button>
      </div>
      <DateFilterBar v-if="['cockpit','components','accounting'].includes(view)" :df="df" class="ms-auto" />
    </div>

    <!-- ── COCKPIT ── -->
    <template v-if="view==='cockpit'">
      <TableLoading v-if="cLoad" :rows="4" />
      <template v-else>
        <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <Kpi :label="L('Headcount','عدد الموظفين','Effectif')" :value="c.headcount" icon="layers" color="#0f766e" :sub="L('active','نشط','actifs')" />
          <Kpi :label="L('Cost to company','تكلفة الشركة','Coût total')" :value="money(c.cost_to_company)" icon="wallet" color="#7c3aed" :sub="ccy + ' · +' + L('employer','صاحب العمل','employeur')" />
          <Kpi :label="L('Net paid','الصافي المدفوع','Net payé')" :value="money(c.net)" icon="check" color="#0369a1" :sub="(c.slips||0)+' '+L('slips','مسير','bulletins')" />
          <Kpi :label="L('Owed to staff','مستحق للموظفين','Dû au personnel')" :value="money(c.salary_payable)" icon="clock" :color="c.salary_payable ? '#b45309' : '#94a3b8'" :sub="L('salary payable','رواتب مستحقة','à payer')" />
        </div>

        <div v-if="c.missing_slips || c.no_structure" class="flex flex-wrap gap-2">
          <button v-if="c.missing_slips" class="inline-flex items-center gap-1.5 px-3 py-2 rounded-card border border-amber-200 bg-amber-50/70 text-[12px] font-semibold text-amber-800" @click="view='employees'">
            <Icon name="alert" :size="14" color="#b45309" />{{ c.missing_slips }} {{ L('active staff with no','موظف نشط بلا مسير','sans bulletin') }} {{ c.last_month }} {{ L('slip','','') }}
          </button>
          <span v-if="c.no_structure" class="inline-flex items-center gap-1.5 px-3 py-2 rounded-card border border-line bg-white text-[12px] font-semibold text-ink-2">
            <Icon name="alert" :size="14" color="#9a8f86" />{{ c.no_structure }} {{ L('with no salary structure','بلا هيكل راتب','sans structure') }}
          </span>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-3">
          <div class="bg-white rounded-card border border-line shadow-card px-4 py-3">
            <div class="text-[12px] font-bold mb-3 flex items-center gap-2"><Icon name="chart" :size="14" color="#0b5c4f" />{{ L('Monthly payroll','الرواتب الشهرية','Paie mensuelle') }}</div>
            <div class="flex items-end gap-2 h-28">
              <div v-for="mo in c.monthly" :key="mo.m" class="flex-1 flex flex-col items-center gap-1 min-w-0" :title="mo.m+': '+money(mo.net)">
                <div class="w-full flex-1 flex items-end"><div class="w-full rounded-t-sm bg-teal-600" :style="`height:${mBar(mo.net)}%;min-height:2px`"></div></div>
                <span class="text-[9px] text-ink-muted whitespace-nowrap">{{ mo.m.slice(5) }}</span>
              </div>
            </div>
          </div>
          <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
            <div class="px-4 py-2.5 border-b border-line-hair text-[12px] font-bold flex items-center gap-2"><Icon name="building" :size="14" color="#0b5c4f" />{{ L('By department','حسب القسم','Par service') }}</div>
            <table class="w-full text-[12px]"><tbody>
              <tr v-for="dep in c.by_department" :key="dep.dept" class="border-t border-line-hair first:border-t-0">
                <td class="px-4 py-2 truncate max-w-[180px]">{{ dep.dept }}</td>
                <td class="px-3 py-2 text-end tnum text-ink-muted">{{ dep.heads }} 👤</td>
                <td class="px-4 py-2 text-end tnum font-semibold">{{ money(dep.net) }}</td>
              </tr>
            </tbody></table>
          </div>
        </div>
      </template>
    </template>

    <!-- ── EMPLOYEES ── -->
    <div v-else-if="view==='employees'" class="bg-white rounded-card border border-line shadow-card overflow-hidden">
      <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2.5 flex-wrap">
        <Icon name="layers" :size="14" color="#0b5c4f" /><span class="text-[12px] font-bold">{{ L('Employees','الموظفون','Employés') }}</span>
        <div class="ms-auto relative">
          <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
          <input v-model.trim="empSearch" :placeholder="L('Search…','بحث…','Rechercher…')" class="w-44 sm:w-56 h-9 bg-app-warm/40 border border-line-2 rounded-[10px] ps-9 pe-3 text-[12.5px] focus:outline-none focus:border-accent/40 focus:bg-white" />
        </div>
      </div>
      <TableLoading v-if="eLoad" :rows="8" />
      <div v-else class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead><tr style="background:#fafaf9" class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">
            <th class="px-4 py-2 text-start">{{ L('Employee','الموظف','Employé') }}</th>
            <th class="px-3 py-2 text-start hidden sm:table-cell">{{ L('Department','القسم','Service') }}</th>
            <th class="px-3 py-2 text-end">{{ L('Base','الأساسي','Base') }}</th>
            <th class="px-3 py-2 text-start hidden md:table-cell">{{ L('Last slip','آخر مسير','Dernier') }}</th>
            <th class="px-4 py-2 text-end">{{ L('YTD net','صافي السنة','Net cumul') }}</th>
          </tr></thead>
          <tbody>
            <tr v-for="r in emps" :key="r.name" class="border-t border-line-hair hover:bg-app-warm/50 cursor-pointer group" @click="openEmp(r.name)">
              <td class="px-4 py-2.5"><div class="font-semibold group-hover:text-accent-dark">{{ r.nm }}</div><div class="text-[10px] text-ink-muted">{{ r.desig || r.name }}</div></td>
              <td class="px-3 py-2.5 text-ink-2 hidden sm:table-cell truncate max-w-[160px]">{{ r.dept || "—" }}</td>
              <td class="px-3 py-2.5 text-end tnum">{{ money(r.base) }}</td>
              <td class="px-3 py-2.5 text-ink-3 hidden md:table-cell whitespace-nowrap" :class="isStale(r.last_slip) ? 'text-amber-700 font-semibold' : ''">{{ r.last_slip || "—" }}</td>
              <td class="px-4 py-2.5 text-end tnum font-semibold">{{ money(r.ytd_net) }}</td>
            </tr>
            <tr v-if="!emps.length"><td colspan="5" class="px-4 py-8 text-center text-ink-muted">{{ L('No employees.','لا موظفين.','Aucun.') }}</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ── RUNS ── -->
    <div v-else-if="view==='runs'" class="bg-white rounded-card border border-line shadow-card overflow-hidden">
      <div class="px-4 py-2.5 border-b border-line-hair text-[12px] font-bold flex items-center gap-2"><Icon name="list" :size="14" color="#0b5c4f" />{{ L('Payroll runs','تشغيلات الرواتب','Exécutions') }}</div>
      <TableLoading v-if="rLoad" :rows="8" />
      <table v-else class="w-full text-[12px]">
        <thead><tr style="background:#fafaf9" class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">
          <th class="px-4 py-2 text-start">{{ L('Run','التشغيل','Exéc.') }}</th>
          <th class="px-3 py-2 text-start">{{ L('Period','الفترة','Période') }}</th>
          <th class="px-3 py-2 text-end">{{ L('Slips','مسيّرات','Bulletins') }}</th>
          <th class="px-3 py-2 text-start">{{ L('Status','الحالة','Statut') }}</th>
          <th class="px-4 py-2 text-end">{{ L('Net','الصافي','Net') }}</th>
        </tr></thead>
        <tbody>
          <tr v-for="r in runs" :key="r.name" class="border-t border-line-hair">
            <td class="px-4 py-2.5 font-mono text-[11px]">{{ r.name }}</td>
            <td class="px-3 py-2.5 text-ink-2">{{ r.month }}</td>
            <td class="px-3 py-2.5 text-end tnum">{{ r.slips }}</td>
            <td class="px-3 py-2.5"><span class="text-[10px] font-semibold px-1.5 py-0.5 rounded" :class="r.status==='Posted' ? 'bg-emerald-50 text-emerald-700' : r.status==='Cancelled' ? 'bg-rose-50 text-rose-600' : 'bg-amber-50 text-amber-700'">{{ r.status }}</span></td>
            <td class="px-4 py-2.5 text-end tnum font-semibold">{{ money(r.net) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- ── ACCOUNTING (GL reconciliation) ── -->
    <template v-else-if="view==='accounting'">
      <TableLoading v-if="gLoad" :rows="6" />
      <template v-else>
        <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <Kpi :label="L('Expected (slips)','المتوقّع (المسيّرات)','Attendu')" :value="money(gl.total_expected)" icon="scale" color="#0369a1" :sub="ccy" />
          <Kpi :label="L('Actual (GL)','الفعلي (الأستاذ)','Réel')" :value="money(gl.total_actual)" icon="check" color="#0f766e" :sub="ccy" />
          <Kpi :label="L('Variance','الفرق','Écart')" :value="money(gl.total_variance)" icon="alert" :color="Math.abs(gl.total_variance||0)>1 ? '#e11d48' : '#047857'" :sub="L('GL − slips','الأستاذ − المسيّرات','GL − paie')" />
          <Kpi :label="L('Mismatched','غير مطابقة','Non concordés')" :value="gl.mismatched || 0" icon="alert" :color="gl.mismatched ? '#b45309' : '#94a3b8'" :sub="L('accounts','حساب','comptes')" />
        </div>
        <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
          <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><Icon name="scale" :size="14" color="#0b5c4f" /><span class="text-[12px] font-bold">{{ L('Payroll → GL reconciliation','مطابقة الرواتب بالأستاذ','Rapprochement paie → GL') }}</span><span class="text-[10px] text-ink-muted">{{ L('slip totals vs the account they post to','إجمالي المسيّرات مقابل حسابها','par compte') }}</span></div>
          <div class="overflow-x-auto">
            <table class="w-full text-[12px]">
              <thead><tr style="background:#fafaf9" class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">
                <th class="px-4 py-2 text-start">{{ L('Account','الحساب','Compte') }}</th>
                <th class="px-3 py-2 text-end">{{ L('Expected','المتوقّع','Attendu') }}</th>
                <th class="px-3 py-2 text-end">{{ L('Actual','الفعلي','Réel') }}</th>
                <th class="px-4 py-2 text-end">{{ L('Variance','الفرق','Écart') }}</th>
              </tr></thead>
              <tbody>
                <tr v-for="r in gl.rows" :key="r.account" class="border-t border-line-hair" :class="r.tied ? '' : 'bg-rose-50/40'">
                  <td class="px-4 py-2.5"><span class="font-mono text-[10px] text-ink-muted">{{ r.num }}</span> {{ r.name }}</td>
                  <td class="px-3 py-2.5 text-end tnum text-ink-3">{{ money(r.expected) }}</td>
                  <td class="px-3 py-2.5 text-end tnum">{{ money(r.actual) }}</td>
                  <td class="px-4 py-2.5 text-end tnum font-bold" :class="r.tied ? 'text-success-dark' : 'text-rose-600'">{{ r.tied ? '✓' : money(r.variance) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </template>
    </template>

    <!-- ── COMPONENTS ── -->
    <template v-else-if="view==='components'">
      <TableLoading v-if="kLoad" :rows="8" />
      <div v-else class="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <div v-for="grp in [{k:'earnings',t:L('Earnings','الاستحقاقات','Gains'),c:'#0f766e'},{k:'deductions',t:L('Deductions','الخصومات','Retenues'),c:'#be123c'}]" :key="grp.k" class="bg-white rounded-card border border-line shadow-card overflow-hidden">
          <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><span class="w-2.5 h-2.5 rounded-sm" :style="`background:${grp.c}`"></span><span class="text-[12px] font-bold">{{ grp.t }}</span><span class="ms-auto tnum font-bold text-[12px]">{{ money(grp.k==='earnings' ? k.earning_total : k.deduction_total) }}</span></div>
          <table class="w-full text-[12px]"><tbody>
            <tr v-for="(cmp,i) in (k[grp.k]||[])" :key="i" class="border-t border-line-hair first:border-t-0">
              <td class="px-4 py-2"><div class="truncate max-w-[220px]">{{ cmp.component }}</div><div class="text-[10px] text-ink-muted font-mono">{{ cmp.account_short || "—" }}</div></td>
              <td class="px-4 py-2 text-end tnum font-semibold">{{ money(cmp.total) }}</td>
            </tr>
          </tbody></table>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { h } from "vue";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import DateFilterBar from "@/components/DateFilterBar.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";
import { useDateFilter } from "@/composables/useDateFilter";

const { locale } = useI18n();
const { entityId } = useUi();
const router = useRouter();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const money = (n) => { n = Number(n) || 0; const a = Math.abs(n); return (n < 0 ? "−" : "") + (a >= 1e6 ? (a / 1e6).toFixed(2) + "M" : a >= 1e3 ? Math.round(a / 1e3) + "K" : Math.round(a).toLocaleString()); };

const Kpi = (p) => h("div", { class: "bg-white rounded-card border border-line shadow-card px-4 py-3" }, [
  h("div", { class: "text-[10px] font-bold uppercase tracking-wider text-ink-muted flex items-center gap-1.5" }, [h(Icon, { name: p.icon, size: 13, color: p.color }), p.label]),
  h("div", { class: "text-[20px] font-extrabold mt-1 tnum", style: `color:${p.color}` }, p.value),
  h("div", { class: "text-[10.5px] text-ink-muted mt-0.5" }, p.sub)]);
Kpi.props = ["label", "value", "sub", "icon", "color"];

const view = ref("cockpit");
const VIEWS = [
  { k: "cockpit", icon: "chart", label: () => L("Cockpit", "اللوحة", "Cockpit") },
  { k: "employees", icon: "layers", label: () => L("Employees", "الموظفون", "Employés") },
  { k: "runs", icon: "list", label: () => L("Runs", "التشغيلات", "Exécutions") },
  { k: "components", icon: "scale", label: () => L("Components", "المكوّنات", "Composants") },
  { k: "accounting", icon: "check", label: () => L("Accounting", "المحاسبة", "Compta") },
];

const c = ref({}), cLoad = ref(true);
const emps = ref([]), eLoad = ref(true), empSearch = ref("");
const runs = ref([]), rLoad = ref(true);
const k = ref({}), kLoad = ref(true);
const gl = ref({}), gLoad = ref(true);
const ccy = computed(() => c.value.currency || "MAD");
const df = useDateFilter("payroll", () => { loadCockpit(); loadComponents(); if (view.value === "accounting") loadGL(); }, "year");

async function loadCockpit() { cLoad.value = true; try { c.value = await api.call("accounting_portal.api.payroll.payroll_cockpit", { company: currentCompany(), ...df.filterValue() }) || {}; } catch { c.value = {}; } finally { cLoad.value = false; } }
async function loadEmps() { eLoad.value = true; try { const r = await api.call("accounting_portal.api.payroll.payroll_employees", { company: currentCompany(), search: empSearch.value }); emps.value = r?.rows || []; } catch { emps.value = []; } finally { eLoad.value = false; } }
async function loadRuns() { rLoad.value = true; try { const r = await api.call("accounting_portal.api.payroll.payroll_runs", { company: currentCompany() }); runs.value = r?.runs || []; } catch { runs.value = []; } finally { rLoad.value = false; } }
async function loadComponents() { kLoad.value = true; try { k.value = await api.call("accounting_portal.api.payroll.payroll_components", { company: currentCompany(), ...df.filterValue() }) || {}; } catch { k.value = {}; } finally { kLoad.value = false; } }
async function loadGL() { gLoad.value = true; try { gl.value = await api.call("accounting_portal.api.payroll.payroll_gl_recon", { company: currentCompany(), ...df.filterValue() }) || {}; } catch { gl.value = {}; } finally { gLoad.value = false; } }

loadCockpit();
watch(view, (v) => { if (v === "employees" && !emps.value.length) loadEmps(); if (v === "runs" && !runs.value.length) loadRuns(); if (v === "components" && !k.value.earnings) loadComponents(); if (v === "accounting" && !gl.value.rows) loadGL(); });
let t; watch(empSearch, () => { clearTimeout(t); t = setTimeout(loadEmps, 300); });
watch(entityId, () => { c.value = {}; emps.value = []; runs.value = []; k.value = {}; gl.value = {}; loadCockpit(); if (view.value === "employees") loadEmps(); if (view.value === "runs") loadRuns(); if (view.value === "components") loadComponents(); if (view.value === "accounting") loadGL(); });

const maxNet = computed(() => Math.max(1, ...(c.value.monthly || []).map((m) => m.net)));
const mBar = (v) => Math.round((Number(v) || 0) / maxNet.value * 100);
const isStale = (d) => { if (!d) return true; const m = new Date(); m.setMonth(m.getMonth() - 2); return new Date(d) < m; };
function openEmp(name) { router.push({ path: "/accounting/accountant/payroll", query: { employee: name } }); }
</script>
