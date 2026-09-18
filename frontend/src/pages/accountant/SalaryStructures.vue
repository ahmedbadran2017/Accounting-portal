<template>
  <div class="space-y-3.5">
    <div class="flex items-center gap-2 flex-wrap">
      <span class="text-[13px] font-bold">{{ L("Salary structures", "هياكل المرتبات", "Structures salariales") }}</span>
      <span class="text-[11px] text-ink-muted">{{ L("fixed-amount earnings and deductions; assign one to each employee", "استحقاقات وخصومات بمبالغ ثابتة؛ اربط واحدة بكل موظف", "gains et retenues à montant fixe") }}</span>
      <UiButton variant="create" size="md" icon="plus" class="ms-auto" v-if="canWrite" type="button" @click="openNew()"> {{ L("New structure", "هيكل جديد", "Nouvelle structure") }}</UiButton>
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

    <!-- Who is actually on which structure. The portal could create an
         assignment and never show one, so "is this person assigned, and at what
         base" was a Desk question — and it is the question behind almost every
         payroll run that reports "No employees found". -->
    <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
      <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2">
        <Icon name="users" :size="14" color="#0b5c4f" />
        <span class="text-[12px] font-semibold">{{ L("Assignments", "الربط بالموظفين", "Affectations") }}</span>
        <span class="text-[11px] text-ink-muted">{{ L("the newest row per employee is the one payroll uses", "أحدث سطر لكل موظف هو اللي بيتحسب عليه", "la plus récente s'applique") }}</span>
      </div>

      <div v-if="unassigned.length" class="px-4 py-2.5 border-b border-line-hair text-[12px]" style="background:#fffbeb;color:#92400e">
        <b>{{ unassigned.length }}</b>
        {{ L("active employees have no structure — they are silently skipped by a payroll run.", "موظف نشط من غير هيكل — بيتسابوا من غير تنبيه لما تعمل تشغيل رواتب.", "employés actifs sans structure.") }}
        <span class="text-[11px]">{{ unassigned.map((u) => u.nm).join(" · ") }}</span>
      </div>

      <TableLoading v-if="aLoading" :rows="5" />
      <div v-else-if="!assignments.length" class="px-4 py-8 text-center text-[12px] text-ink-muted">{{ L("No assignments yet.", "مفيش ربط لسه.", "Aucune affectation.") }}</div>
      <table v-else class="w-full text-[12px]">
        <thead><tr class="text-[11px] font-bold uppercase tracking-wider text-ink-muted" style="background:#fafaf9">
          <th class="px-4 py-2 text-start">{{ L("Employee", "الموظف", "Employé") }}</th>
          <th class="px-2 py-2 text-start">{{ L("Structure", "الهيكل", "Structure") }}</th>
          <th class="px-2 py-2 text-start">{{ L("From", "من", "Depuis") }}</th>
          <th class="px-2 py-2 text-end">{{ L("Base", "الأساسي", "Base") }}</th>
        </tr></thead>
        <tbody>
          <tr v-for="a in assignments" :key="a.name" class="border-t border-line-hair"
              :class="a.current ? '' : 'text-ink-muted'">
            <td class="px-4 py-2">
              {{ a.nm }}
              <span v-if="!a.current" class="text-[10px] ms-1">{{ L("superseded", "مُستبدَل", "remplacé") }}</span>
              <span v-else-if="a.emp_status !== 'Active'" class="text-[10px] ms-1 text-tone-warn">{{ a.emp_status }}</span>
            </td>
            <td class="px-2 py-2">{{ a.salary_structure }}</td>
            <td class="px-2 py-2 tnum">{{ a.from_date }}</td>
            <td class="px-2 py-2 text-end tnum">{{ money(a.base) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- editor -->
    <div v-if="edOpen" class="fixed inset-0 z-50 grid place-items-center bg-ink/30 p-4" @click.self="edOpen = false">
      <div class="bg-white rounded-card shadow-pop w-full max-w-2xl max-h-[92vh] flex flex-col">
        <div class="px-5 py-3 border-b border-line-hair text-[14px] font-bold">{{ ed.name ? L("Edit draft structure", "تعديل مسودة الهيكل", "Modifier") : L("New salary structure", "هيكل مرتب جديد", "Nouvelle structure") }}</div>
        <div class="flex-1 overflow-auto px-5 py-4 space-y-3">
          <div class="grid gap-2 sm:grid-cols-3">
            <div class="sm:col-span-3"><label class="block text-[11px] font-bold text-ink-3 mb-1">{{ L("Name", "الاسم", "Nom") }} *</label><input v-model.trim="ed.structure_name" :disabled="!!ed.name" class="fld fld-md fld-sunk w-full" /></div>
            <div><label class="block text-[11px] font-bold text-ink-3 mb-1">{{ L("Currency", "العملة", "Devise") }}</label><input v-model.trim="ed.currency" dir="ltr" class="fld fld-md w-full" /></div>
            <div><label class="block text-[11px] font-bold text-ink-3 mb-1">{{ L("Frequency", "الدورية", "Fréquence") }}</label><select v-model="ed.payroll_frequency" class="fld fld-md w-full"><option v-for="f in (opts.frequencies || ['Monthly'])" :key="f" :value="f">{{ f }}</option></select></div>
            <div><label class="block text-[11px] font-bold text-ink-3 mb-1">{{ L("Paid via", "طريقة الدفع", "Mode") }}</label><select v-model="ed.mode_of_payment" class="fld fld-md w-full"><option value="">—</option><option v-for="m in (opts.modes || [])" :key="m" :value="m">{{ m }}</option></select></div>
          </div>
          <div v-for="grp in ['earnings','deductions']" :key="grp" class="border border-line rounded-[12px] overflow-hidden">
            <div class="px-3 py-2 border-b border-line-hair flex items-center gap-2 text-[12px] font-bold"><span class="w-2.5 h-2.5 rounded-sm" :style="`background:${grp === 'earnings' ? '#0f766e' : '#be123c'}`"></span>{{ grp === 'earnings' ? L("Earnings", "الاستحقاقات", "Gains") : L("Deductions", "الخصومات", "Retenues") }}<span class="ms-auto tnum">{{ money(sum(ed[grp])) }}</span></div>
            <div v-for="(row, i) in ed[grp]" :key="i" class="flex items-center gap-2 px-3 py-1.5 border-b border-line-hair/60">
              <SearchSelect v-model="row.salary_component" :items="compItems(grp)" :placeholder="L('Component…','المكوّن…','Composant…')" inputClass="h-8 text-[12px] bg-white min-w-[260px]" />
              <input type="number" step="any" min="0" v-model="row.amount" dir="ltr" class="fld fld-sm w-32 text-end tnum" />
              <button type="button" class="text-ink-muted hover:text-sale" @click="ed[grp].splice(i, 1)"><Icon name="close" :size="13" /></button>
            </div>
            <div class="px-3 py-1.5"><button type="button" class="text-[12px] font-semibold text-accent hover:text-accent-dark inline-flex items-center gap-1" @click="ed[grp].push({ salary_component: '', amount: '' })"><Icon name="plus" :size="12" />{{ L("Add line", "إضافة سطر", "Ajouter") }}</button></div>
          </div>
          <div class="text-[12px] font-bold text-end">{{ L("Net", "الصافي", "Net") }}: <span class="tnum">{{ money(sum(ed.earnings) - sum(ed.deductions)) }}</span> {{ ed.currency }}</div>
          <label class="inline-flex items-center gap-2 text-[12px]"><input type="checkbox" v-model="ed.submit" /> {{ L("Submit now (ready to assign)", "رحّله الآن (جاهز للربط)", "Soumettre maintenant") }}</label>
          <p v-if="edErr" class="text-[12px] text-sale">{{ edErr }}</p>
        </div>
        <div class="px-5 py-3 border-t border-line-hair flex justify-end gap-2">
          <UiButton variant="quiet" size="md" @click="edOpen = false">{{ L("Cancel", "إلغاء", "Annuler") }}</UiButton>
          <UiButton variant="primary" size="md" :disabled="busy || (!ed.name && !ed.structure_name)" @click="save">{{ busy ? "…" : L("Save", "حفظ", "Enregistrer") }}</UiButton>
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
import UiButton from "@/components/UiButton.vue";

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


const assignments = ref([]);
const unassigned = ref([]);
const aLoading = ref(true);
async function loadAssignments() {
  aLoading.value = true;
  try {
    const r = await api.call("accounting_portal.api.payroll.list_structure_assignments",
      { company: currentCompany() }, { fresh: true }) || {};
    assignments.value = r.rows || [];
    unassigned.value = r.unassigned || [];
  } catch { assignments.value = []; unassigned.value = []; }
  finally { aLoading.value = false; }
}

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
onMounted(() => { load(); loadOpts(); loadAssignments(); });
watch(entityId, () => { load(); loadOpts(); loadAssignments(); });
</script>
