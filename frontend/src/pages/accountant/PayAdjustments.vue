<template>
  <div class="space-y-3.5">
    <!-- header: month + add -->
    <div class="flex items-center gap-2 flex-wrap">
      <div class="bg-white border border-line rounded-chip px-3 py-1.5 shadow-card flex items-center gap-2">
        <Icon name="coins" :size="14" color="#0b5c4f" />
        <select v-model="month" class="text-[13px] font-bold bg-transparent focus:outline-none cursor-pointer" @change="load">
          <option v-for="m in months" :key="m" :value="m">{{ m }}</option>
        </select>
      </div>
      <span class="text-[11px] text-ink-muted hidden sm:inline">{{ L("bonuses & deductions reviewed before the slip is generated", "حوافز وخصومات تُراجَع قبل إنشاء المسيّر", "revus avant génération") }}</span>
      <button v-if="canWrite" type="button" class="ms-auto inline-flex items-center gap-1.5 h-9 px-3.5 rounded-chip text-[12.5px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand" @click="openAdd()">
        <Icon name="plus" :size="14" />{{ L("Add adjustment", "إضافة", "Ajouter") }}
      </button>
    </div>

    <!-- totals -->
    <div class="grid grid-cols-3 gap-3">
      <Kpi :label="L('Bonuses','الحوافز','Primes')" :value="'+' + money(d.earn_total)" color="#0f766e" :sub="ccy" />
      <Kpi :label="L('Deductions','الخصومات','Retenues')" :value="'−' + money(d.ded_total)" color="#be123c" :sub="ccy" />
      <Kpi :label="L('Net effect','الأثر الصافي','Effet net')" :value="money((d.earn_total||0) - (d.ded_total||0))" color="#7c3aed" :sub="ccy" />
    </div>

    <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
      <div class="px-4 py-2.5 border-b border-line-hair text-[12px] font-bold flex items-center gap-2"><Icon name="users" :size="14" color="#0b5c4f" />{{ L("By employee","حسب الموظف","Par employé") }}<span class="text-[10px] text-ink-muted font-normal">{{ d.count || 0 }} {{ L("entries","بند","lignes") }}</span></div>
      <TableLoading v-if="loading" :rows="6" />
      <div v-else-if="!(d.employees||[]).length" class="px-4 py-10 text-center text-[12px] text-ink-muted">{{ L("No adjustments for this month yet.","لا حوافز أو خصومات لهذا الشهر.","Aucun ajustement.") }}</div>
      <div v-else class="divide-y divide-line-hair">
        <div v-for="e in d.employees" :key="e.employee">
          <button type="button" class="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-app-warm/40 text-start" @click="toggle(e.employee)">
            <Icon name="arrow" :size="12" color="#cbd5e1" class="transition-transform shrink-0" :class="open[e.employee] ? 'rotate-90' : ''" />
            <span class="text-[12.5px] font-semibold flex-1 truncate">{{ e.nm }}</span>
            <span v-if="e.earn" class="text-[11.5px] tnum font-semibold text-teal-700">+{{ money(e.earn) }}</span>
            <span v-if="e.ded" class="text-[11.5px] tnum font-semibold text-rose-600">−{{ money(e.ded) }}</span>
            <span class="text-[12px] tnum font-bold w-24 text-end" :class="e.net < 0 ? 'text-rose-600' : 'text-teal-700'">{{ e.net >= 0 ? '+' : '' }}{{ money(e.net) }}</span>
          </button>
          <div v-if="open[e.employee]" class="bg-app-warm/30 px-4 pb-2">
            <div v-for="it in e.items" :key="it.name" class="flex items-center gap-2 py-1.5 text-[11.5px] border-b border-line-hair/50 last:border-b-0">
              <span class="w-2 h-2 rounded-sm shrink-0" :style="`background:${it.type==='Earning' ? '#0f766e' : '#be123c'}`"></span>
              <span class="flex-1 truncate">{{ it.comp }}</span>
              <span class="tnum font-semibold" :class="it.type==='Earning' ? 'text-teal-700' : 'text-rose-600'">{{ it.type==='Earning' ? '+' : '−' }}{{ money(it.amount) }}</span>
              <button v-if="canWrite" type="button" class="text-ink-muted hover:text-sale p-0.5" :disabled="busy===it.name" @click="remove(it)"><Icon :name="busy===it.name ? 'clock' : 'close'" :size="13" /></button>
            </div>
            <button v-if="canWrite" type="button" class="mt-1 text-[11px] font-semibold text-accent hover:text-accent-dark inline-flex items-center gap-1" @click="openAdd(e)"><Icon name="plus" :size="11" />{{ L("Add for","إضافة لـ","Ajouter pour") }} {{ e.nm }}</button>
          </div>
        </div>
      </div>
      <div class="px-4 py-2 border-t border-line-hair text-[10.5px] text-ink-muted flex items-center gap-1.5">
        <Icon name="alert" :size="11" color="#9a8f86" />{{ L("These apply automatically when you Generate the month's slips.","بتتطبّق تلقائيًا لما تعمل Generate لمسيّرات الشهر.","Appliqués à la génération.") }}
      </div>
    </div>

    <!-- add modal -->
    <div v-if="adding" class="fixed inset-0 z-[100] flex items-start justify-center p-4 sm:p-8 overflow-y-auto" style="background:rgba(28,25,23,.45)" @click.self="adding=false">
      <div class="bg-white rounded-[18px] shadow-cardHover w-full max-w-md my-8 overflow-hidden">
        <div class="flex items-center gap-2.5 px-5 py-4 border-b border-line">
          <span class="w-8 h-8 rounded-[10px] grid place-items-center" style="background:#fff7ed"><Icon name="coins" :size="16" color="#b45309" /></span>
          <div class="flex-1"><div class="text-[14px] font-bold">{{ L("Add adjustment","إضافة حافز/خصم","Ajouter") }}</div><div class="text-[11px] text-ink-muted">{{ month }}</div></div>
          <button class="text-ink-3 hover:text-ink" @click="adding=false"><Icon name="close" :size="18" /></button>
        </div>
        <div class="p-5 space-y-3.5">
          <label class="block">
            <span class="text-[11px] font-semibold text-ink-3">{{ L("Employee","الموظف","Employé") }}</span>
            <select v-model="form.employee" class="mt-1 w-full border border-line-2 rounded-chip px-3 py-2 text-[12px] focus:outline-none focus:border-accent/40 cursor-pointer">
              <option value="">—</option>
              <option v-for="e in emps" :key="e.name" :value="e.name">{{ e.nm }}</option>
            </select>
          </label>
          <label class="block">
            <span class="text-[11px] font-semibold text-ink-3">{{ L("Type","النوع","Type") }}</span>
            <div class="mt-1 flex gap-1 bg-app-warm/50 rounded-chip p-0.5">
              <button type="button" class="flex-1 py-1.5 rounded-lg text-[12px] font-semibold" :class="form.kind==='earn' ? 'bg-white text-teal-700 shadow-card' : 'text-ink-3'" @click="setKind('earn')">{{ L("Bonus","حافز","Prime") }}</button>
              <button type="button" class="flex-1 py-1.5 rounded-lg text-[12px] font-semibold" :class="form.kind==='ded' ? 'bg-white text-rose-600 shadow-card' : 'text-ink-3'" @click="setKind('ded')">{{ L("Deduction","خصم","Retenue") }}</button>
            </div>
          </label>
          <label class="block">
            <span class="text-[11px] font-semibold text-ink-3">{{ L("Component","المكوّن","Composant") }}</span>
            <select v-model="form.component" class="mt-1 w-full border border-line-2 rounded-chip px-3 py-2 text-[12px] focus:outline-none focus:border-accent/40 cursor-pointer">
              <option value="">—</option>
              <option v-for="c in (form.kind==='earn' ? comp.earnings : comp.deductions) || []" :key="c" :value="c">{{ c }}</option>
            </select>
          </label>
          <label class="block">
            <span class="text-[11px] font-semibold text-ink-3">{{ L("Amount","المبلغ","Montant") }} ({{ ccy }})</span>
            <input type="number" min="0" step="0.01" v-model.number="form.amount" class="mt-1 w-full border border-line-2 rounded-chip px-3 py-2 text-[13px] tnum text-end font-semibold focus:outline-none focus:border-accent/40" placeholder="0.00" />
          </label>
          <div v-if="err" class="text-[11.5px] text-sale">{{ err }}</div>
        </div>
        <div class="flex items-center justify-end gap-2 px-5 py-3.5 border-t border-line bg-app-warm/40">
          <button class="px-3.5 py-2 rounded-chip text-[12px] font-semibold text-ink-2 hover:bg-white" @click="adding=false">{{ L("Cancel","إلغاء","Annuler") }}</button>
          <button class="px-4 py-2 rounded-chip text-[12px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand disabled:opacity-50" :disabled="!form.employee || !form.component || !(form.amount>0) || saving" @click="save">{{ saving ? "…" : L("Add","إضافة","Ajouter") }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, h, watch } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";
import { useAuth } from "@/composables/useAuth";
import { useToast } from "@/composables/useToast";
import { fmtAmount } from "@/utils/helpers";

const { locale } = useI18n();
const { entityId } = useUi();
const { can } = useAuth();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const money = (n) => fmtAmount(n);
const canWrite = computed(() => can("post_entries"));
const Kpi = (p) => h("div", { class: "bg-white rounded-card border border-line shadow-card px-4 py-3" }, [
  h("div", { class: "text-[10px] font-bold uppercase tracking-wider text-ink-muted" }, p.label),
  h("div", { class: "text-[18px] font-extrabold mt-1 tnum", style: `color:${p.color}` }, p.value),
  h("div", { class: "text-[10px] text-ink-muted mt-0.5" }, p.sub)]);
Kpi.props = ["label", "value", "color", "sub"];

const now = new Date();
const curMonth = now.toISOString().slice(0, 7);
const months = computed(() => {
  const out = [];
  const dt = new Date(now.getFullYear(), now.getMonth(), 1);
  for (let i = 0; i < 14; i++) { out.push(dt.toISOString().slice(0, 7)); dt.setMonth(dt.getMonth() - 1); }
  return out;
});
const month = ref(curMonth);
const d = ref({ employees: [] });
const loading = ref(true);
const open = reactive({});
const busy = ref("");
const emps = ref([]);
const comp = ref({ earnings: [], deductions: [] });
const ccy = computed(() => d.value.currency || "MAD");

async function load() {
  loading.value = true;
  try { d.value = await api.call("accounting_portal.api.payroll.pay_adjustments", { company: currentCompany(), month: month.value }, { fresh: true }) || { employees: [] }; }
  catch { d.value = { employees: [] }; }
  finally { loading.value = false; }
}
async function loadRefs() {
  try { const r = await api.call("accounting_portal.api.payroll.payroll_employees", { company: currentCompany(), status: "Active" }); emps.value = r?.rows || []; } catch { emps.value = []; }
  try { comp.value = await api.call("accounting_portal.api.payroll.component_options", { company: currentCompany() }) || comp.value; } catch { /* ignore */ }
}
load(); loadRefs();
watch(entityId, () => { load(); loadRefs(); });

function toggle(k) { open[k] = !open[k]; }

const adding = ref(false), saving = ref(false), err = ref("");
const form = reactive({ employee: "", kind: "earn", component: "", amount: null });
function setKind(k) { form.kind = k; form.component = ""; }
function openAdd(e) { form.employee = e ? e.employee : ""; form.kind = "earn"; form.component = ""; form.amount = null; err.value = ""; adding.value = true; }
async function save() {
  if (saving.value) return;
  saving.value = true; err.value = "";
  try {
    await api.call("accounting_portal.api.payroll.add_adjustment", { company: currentCompany(), employee: form.employee, salary_component: form.component, amount: Number(form.amount), month: month.value });
    toast.success(L("Added", "تمت الإضافة", "Ajouté")); adding.value = false; load();
  } catch (e) { err.value = String(e?.message || e).slice(0, 200); }
  finally { saving.value = false; }
}
async function remove(it) {
  if (busy.value) return;
  if (!window.confirm(L(`Remove ${it.comp}?`, `حذف ${it.comp}؟`, `Supprimer ?`))) return;
  busy.value = it.name;
  try { await api.call("accounting_portal.api.payroll.remove_adjustment", { company: currentCompany(), name: it.name }); toast.success(L("Removed", "تم الحذف", "Supprimé")); load(); }
  catch (e) { toast.error(String(e?.message || e).slice(0, 160)); }
  finally { busy.value = ""; }
}
</script>
