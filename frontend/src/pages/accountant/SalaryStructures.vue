<template>
  <div class="space-y-3.5">
    <div class="flex items-center gap-2 flex-wrap">
      <span class="text-[13px] font-bold">{{ L("Salary structures", "هياكل المرتبات", "Structures salariales") }}</span>
      <span class="text-[11px] text-ink-muted">{{ L("fixed-amount earnings and deductions; assign one to each employee", "استحقاقات وخصومات بمبالغ ثابتة؛ اربط واحدة بكل موظف", "gains et retenues à montant fixe") }}</span>
      <button v-if="canWrite" type="button" class="ms-auto inline-flex items-center gap-1.5 h-9 px-3.5 rounded-chip text-[13px] font-semibold text-white bg-brand hover:bg-brand-dark shadow-brand" @click="openNew()"><Icon name="plus" :size="14" />{{ L("New structure", "هيكل جديد", "Nouvelle structure") }}</button>
    </div>

    <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
      <TableLoading v-if="loading" :rows="6" />
      <div v-else-if="!rows.length" class="px-4 py-10 text-center text-[12px] text-ink-muted">{{ L("No salary structures.", "لا هياكل.", "Aucune structure.") }}</div>
      <table v-else class="w-full text-[12px]">
        <thead><tr class="text-[11px] font-bold uppercase tracking-wider text-ink-muted" style="background:#fafaf9">
          <th class="px-4 py-2 text-start">{{ L("Structure", "الهيكل", "Structure") }}</th>
          <th class="px-2 py-2 text-end">{{ L("Earnings", "الاستحقاقات", "Gains") }}</th>
          <th class="px-2 py-2 text-end">{{ L("Deductions", "الخصومات", "Retenues") }}</th>
          <th class="px-2 py-2 text-end">{{ L("Assigned", "مربوط", "Assignés") }}</th>
          <th class="px-2 py-2 text-start">{{ L("State", "الحالة", "État") }}</th>
          <th class="px-3 py-2"></th>
        </tr></thead>
        <tbody>
          <tr v-for="r in rows" :key="r.name" class="border-t border-line-hair hover:bg-app-warm/40">
            <td class="px-4 py-2"><span class="font-semibold">{{ r.name }}</span><span class="block text-[11px] text-ink-muted">{{ r.currency }} · {{ r.payroll_frequency }} · {{ r.modified }}</span></td>
            <td class="px-2 py-2 text-end tnum text-teal-700">{{ money(r.earn) }}</td>
            <td class="px-2 py-2 text-end tnum text-rose-600">{{ money(r.ded) }}</td>
            <td class="px-2 py-2 text-end tnum">{{ r.assigned }}</td>
            <td class="px-2 py-2"><span class="text-[11px] font-semibold px-1.5 py-0.5 rounded" :class="r.docstatus === 0 ? 'bg-amber-50 text-amber-700' : r.is_active === 'Yes' ? 'bg-emerald-50 text-emerald-700' : 'bg-app-warm text-ink-muted'">{{ r.docstatus === 0 ? L("Draft", "مسودة", "Brouillon") : r.is_active === 'Yes' ? L("Active", "نشط", "Actif") : L("Inactive", "غير نشط", "Inactif") }}</span></td>
            <td class="px-3 py-2 text-end whitespace-nowrap">
              <button type="button" class="text-[11px] font-bold px-2 py-0.5 rounded border border-line-2 hover:bg-app-warm" @click="openEdit(r)">{{ r.docstatus === 0 ? L("Edit", "تعديل", "Modifier") : L("Copy as new", "نسخ كجديد", "Copier") }}</button>
              <button v-if="canWrite && r.docstatus === 1" type="button" class="ms-1 text-[11px] font-bold px-2 py-0.5 rounded border border-line-2 hover:bg-app-warm" :disabled="busy" @click="toggleActive(r)">{{ r.is_active === 'Yes' ? L("Deactivate", "تعطيل", "Désactiver") : L("Activate", "تفعيل", "Activer") }}</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div class="px-4 py-2 border-t border-line-hair text-[11px] text-ink-muted">{{ L("A submitted structure cannot change in ERPNext: copy it as a new one with the new amounts, then re-assign the employee.", "الهيكل المرحّل مش بيتعدل في ERPNext: انسخه كهيكل جديد بالمبالغ الجديدة واربط الموظف عليه.", "Une structure soumise ne se modifie pas : copiez-la puis réassignez.") }}</div>
    </div>

    <!-- editor -->
    <div v-if="edOpen" class="fixed inset-0 z-50 grid place-items-center bg-ink/30 p-4" @click.self="edOpen = false">
      <div class="bg-white rounded-card shadow-pop w-full max-w-2xl max-h-[92vh] flex flex-col">
        <div class="px-5 py-3 border-b border-line-hair text-[14px] font-bold">{{ ed.name ? L("Edit draft structure", "تعديل مسودة الهيكل", "Modifier") : L("New salary structure", "هيكل مرتب جديد", "Nouvelle structure") }}</div>
        <div class="flex-1 overflow-auto px-5 py-4 space-y-3">
          <div class="grid gap-2 sm:grid-cols-3">
            <div class="sm:col-span-3"><label class="block text-[11px] font-bold text-ink-3 mb-1">{{ L("Name", "الاسم", "Nom") }} *</label><input v-model.trim="ed.structure_name" :disabled="!!ed.name" class="h-9 w-full rounded-[9px] border border-line-2 px-2.5 text-[13px] bg-white disabled:bg-app-warm" /></div>
            <div><label class="block text-[11px] font-bold text-ink-3 mb-1">{{ L("Currency", "العملة", "Devise") }}</label><input v-model.trim="ed.currency" dir="ltr" class="h-9 w-full rounded-[9px] border border-line-2 px-2.5 text-[13px] bg-white" /></div>
            <div><label class="block text-[11px] font-bold text-ink-3 mb-1">{{ L("Frequency", "الدورية", "Fréquence") }}</label><select v-model="ed.payroll_frequency" class="h-9 w-full rounded-[9px] border border-line-2 px-2 text-[13px] bg-white"><option v-for="f in (opts.frequencies || ['Monthly'])" :key="f" :value="f">{{ f }}</option></select></div>
            <div><label class="block text-[11px] font-bold text-ink-3 mb-1">{{ L("Paid via", "طريقة الدفع", "Mode") }}</label><select v-model="ed.mode_of_payment" class="h-9 w-full rounded-[9px] border border-line-2 px-2 text-[13px] bg-white"><option value="">—</option><option v-for="m in (opts.modes || [])" :key="m" :value="m">{{ m }}</option></select></div>
          </div>
          <div v-for="grp in ['earnings','deductions']" :key="grp" class="border border-line rounded-[12px] overflow-hidden">
            <div class="px-3 py-2 border-b border-line-hair flex items-center gap-2 text-[12px] font-bold"><span class="w-2.5 h-2.5 rounded-sm" :style="`background:${grp === 'earnings' ? '#0f766e' : '#be123c'}`"></span>{{ grp === 'earnings' ? L("Earnings", "الاستحقاقات", "Gains") : L("Deductions", "الخصومات", "Retenues") }}<span class="ms-auto tnum">{{ money(sum(ed[grp])) }}</span></div>
            <div v-for="(row, i) in ed[grp]" :key="i" class="flex items-center gap-2 px-3 py-1.5 border-b border-line-hair/60">
              <SearchSelect v-model="row.salary_component" :items="compItems(grp)" :placeholder="L('Component…','المكوّن…','Composant…')" inputClass="h-8 text-[12px] bg-white min-w-[260px]" />
              <input type="number" step="any" min="0" v-model="row.amount" dir="ltr" class="h-8 w-32 rounded-[8px] border border-line-2 px-2 text-[12px] text-end tnum bg-white" />
              <button type="button" class="text-ink-muted hover:text-sale" @click="ed[grp].splice(i, 1)"><Icon name="close" :size="13" /></button>
            </div>
            <div class="px-3 py-1.5"><button type="button" class="text-[12px] font-semibold text-accent hover:text-accent-dark inline-flex items-center gap-1" @click="ed[grp].push({ salary_component: '', amount: '' })"><Icon name="plus" :size="12" />{{ L("Add line", "إضافة سطر", "Ajouter") }}</button></div>
          </div>
          <div class="text-[12px] font-bold text-end">{{ L("Net", "الصافي", "Net") }}: <span class="tnum">{{ money(sum(ed.earnings) - sum(ed.deductions)) }}</span> {{ ed.currency }}</div>
          <label class="inline-flex items-center gap-2 text-[12px]"><input type="checkbox" v-model="ed.submit" /> {{ L("Submit now (ready to assign)", "رحّله الآن (جاهز للربط)", "Soumettre maintenant") }}</label>
          <p v-if="edErr" class="text-[12px] text-sale">{{ edErr }}</p>
        </div>
        <div class="px-5 py-3 border-t border-line-hair flex justify-end gap-2">
          <button class="h-9 px-3.5 rounded-chip text-[12px] font-semibold text-ink-2 hover:bg-app-warm" @click="edOpen = false">{{ L("Cancel", "إلغاء", "Annuler") }}</button>
          <button class="h-9 px-4 rounded-chip text-[12px] font-semibold text-white bg-brand hover:bg-brand-dark shadow-brand disabled:opacity-50" :disabled="busy || (!ed.name && !ed.structure_name)" @click="save">{{ busy ? "…" : L("Save", "حفظ", "Enregistrer") }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import SearchSelect from "@/components/SearchSelect.vue";
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
const money = (n) => fmtAmount(n || 0);
const canWrite = computed(() => can("post_entries"));
const sum = (rows) => (rows || []).reduce((s, r) => s + (Number(r.amount) || 0), 0);

const rows = ref([]); const loading = ref(true); const busy = ref(false);
const opts = ref({ components: [], modes: [], frequencies: [] });
const compItems = (grp) => opts.value.components.filter((c) => (grp === "earnings" ? c.type === "Earning" : c.type === "Deduction")).map((c) => ({ value: c.value, label: c.value }));

async function load() {
  loading.value = true;
  try { rows.value = (await api.call("accounting_portal.api.payroll.list_salary_structures", { company: currentCompany() }, { fresh: true }))?.rows || []; }
  catch { rows.value = []; } finally { loading.value = false; }
}
async function loadOpts() { try { opts.value = (await api.call("accounting_portal.api.payroll.structure_options", { company: currentCompany() })) || opts.value; } catch { /* */ } }

const edOpen = ref(false); const edErr = ref("");
const ed = reactive({ name: "", structure_name: "", currency: "", payroll_frequency: "Monthly", mode_of_payment: "", payment_account: "", earnings: [], deductions: [], submit: true });
function openNew() {
  Object.assign(ed, { name: "", structure_name: "", currency: opts.value.currency || "", payroll_frequency: "Monthly", mode_of_payment: "", payment_account: "", earnings: [{ salary_component: "", amount: "" }], deductions: [], submit: true });
  edErr.value = ""; edOpen.value = true;
}
async function openEdit(r) {
  try {
    const s = await api.call("accounting_portal.api.payroll.get_salary_structure", { name: r.name }, { fresh: true });
    Object.assign(ed, { name: r.docstatus === 0 ? s.name : "", structure_name: r.docstatus === 0 ? s.name : s.name + " (new)", currency: s.currency, payroll_frequency: s.payroll_frequency, mode_of_payment: s.mode_of_payment || "", payment_account: s.payment_account || "",
      earnings: s.earnings.map((x) => ({ ...x })), deductions: s.deductions.map((x) => ({ ...x })), submit: true });
    edErr.value = ""; edOpen.value = true;
  } catch (e) { toast.error(String(e?.message || e).slice(0, 160)); }
}
async function save() {
  busy.value = true; edErr.value = "";
  try {
    const r = await api.call("accounting_portal.api.payroll.save_salary_structure", { company: currentCompany(), name: ed.name || null, structure_name: ed.structure_name, currency: ed.currency, payroll_frequency: ed.payroll_frequency, earnings: ed.earnings, deductions: ed.deductions, mode_of_payment: ed.mode_of_payment, payment_account: ed.payment_account, submit: ed.submit ? 1 : 0 });
    let res = r && r.result; res = typeof res === "string" ? JSON.parse(res) : res;
    toast.success((res?.docstatus === 1 ? L("Structure submitted", "تم ترحيل الهيكل", "Structure soumise") : L("Draft saved", "تم حفظ المسودة", "Brouillon enregistré")) + (res?.structure ? " · " + res.structure : ""));
    edOpen.value = false; load();
  } catch (e) { edErr.value = String(e?.message || e).slice(0, 220); }
  finally { busy.value = false; }
}
async function toggleActive(r) {
  busy.value = true;
  try { await api.call("accounting_portal.api.payroll.set_structure_active", { company: currentCompany(), name: r.name, active: r.is_active === "Yes" ? 0 : 1 }); load(); }
  catch (e) { toast.error(String(e?.message || e).slice(0, 160)); } finally { busy.value = false; }
}
onMounted(() => { load(); loadOpts(); });
watch(entityId, () => { load(); loadOpts(); });
</script>
