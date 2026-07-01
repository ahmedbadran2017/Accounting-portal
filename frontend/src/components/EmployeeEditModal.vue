<template>
  <div class="fixed inset-0 z-[100] flex items-start justify-center p-4 sm:p-8 overflow-y-auto" style="background:rgba(28,25,23,.45)" @click.self="$emit('close')">
    <div class="bg-white rounded-[18px] shadow-cardHover w-full max-w-lg my-6 overflow-hidden">
      <div class="flex items-center gap-2.5 px-5 py-4 border-b border-line">
        <span class="w-8 h-8 rounded-[10px] grid place-items-center" style="background:#ecfdf5"><Icon name="user" :size="16" color="#0f766e" /></span>
        <div class="flex-1 min-w-0">
          <div class="text-[14px] font-bold">{{ employee ? L("Edit employee", "تعديل الموظف", "Modifier l'employé") : L("New employee", "موظف جديد", "Nouvel employé") }}</div>
          <div class="text-[11px] text-ink-muted truncate">{{ employee || entityName }}</div>
        </div>
        <button class="text-ink-3 hover:text-ink" @click="$emit('close')"><Icon name="close" :size="18" /></button>
      </div>

      <div v-if="loading" class="p-8 text-center text-[12px] text-ink-muted">{{ L("Loading…", "جارٍ التحميل…", "…") }}</div>
      <template v-else>
        <div class="p-5 space-y-3 max-h-[62vh] overflow-y-auto">
          <div class="grid grid-cols-2 gap-3">
            <Field :label="L('First name','الاسم الأول','Prénom')"><input v-model.trim="f.first_name" class="fi" /></Field>
            <Field :label="L('Last name','اسم العائلة','Nom')"><input v-model.trim="f.last_name" class="fi" /></Field>
          </div>
          <Field v-if="employee" :label="L('Full name','الاسم الكامل','Nom complet')"><input v-model.trim="f.employee_name" class="fi" /></Field>
          <div class="grid grid-cols-2 gap-3">
            <Field :label="L('Gender','النوع','Genre')"><select v-model="f.gender" class="fi"><option value="">—</option><option v-for="g in opt.genders" :key="g" :value="g">{{ g }}</option></select></Field>
            <Field :label="L('Date of birth','تاريخ الميلاد','Naissance')"><input type="date" v-model="f.date_of_birth" class="fi" /></Field>
          </div>
          <div class="grid grid-cols-2 gap-3">
            <Field :label="L('Joined','تاريخ التعيين','Embauche')"><input type="date" v-model="f.date_of_joining" class="fi" /></Field>
            <Field v-if="employee" :label="L('Status','الحالة','Statut')"><select v-model="f.status" class="fi"><option v-for="s in opt.statuses" :key="s" :value="s">{{ s }}</option></select></Field>
          </div>
          <Field v-if="employee && (f.status==='Left' || f.status==='Suspended')" :label="L('Relieving date','تاريخ ترك العمل','Date de départ')"><input type="date" v-model="f.relieving_date" class="fi" /></Field>
          <div class="grid grid-cols-2 gap-3">
            <Field :label="L('Department','القسم','Service')"><select v-model="f.department" class="fi"><option value="">—</option><option v-for="d in opt.departments" :key="d" :value="d">{{ d }}</option></select></Field>
            <Field :label="L('Designation','المسمى','Poste')"><select v-model="f.designation" class="fi"><option value="">—</option><option v-for="d in opt.designations" :key="d" :value="d">{{ d }}</option></select></Field>
          </div>
          <Field :label="L('Employment type','نوع التوظيف','Type')"><select v-model="f.employment_type" class="fi"><option value="">—</option><option v-for="t in opt.employment_types" :key="t" :value="t">{{ t }}</option></select></Field>
          <div class="grid grid-cols-2 gap-3">
            <Field :label="L('Phone','الهاتف','Téléphone')"><input v-model.trim="f.cell_number" class="fi" /></Field>
            <Field :label="L('Company email','إيميل الشركة','Email pro')"><input v-model.trim="f.company_email" class="fi" /></Field>
          </div>
          <div class="text-[10px] font-bold uppercase tracking-wider text-ink-muted pt-1">{{ L("Bank", "البنك", "Banque") }}</div>
          <div class="grid grid-cols-2 gap-3">
            <Field :label="L('Bank name','اسم البنك','Banque')"><input v-model.trim="f.bank_name" class="fi" /></Field>
            <Field :label="L('Account no','رقم الحساب','N° compte')"><input v-model.trim="f.bank_ac_no" class="fi" /></Field>
          </div>
          <Field :label="L('IBAN','IBAN','IBAN')"><input v-model.trim="f.iban" class="fi" /></Field>
          <div v-if="err" class="text-[11.5px] text-sale">{{ err }}</div>
        </div>
        <div class="flex items-center justify-end gap-2 px-5 py-3.5 border-t border-line bg-app-warm/40">
          <button class="px-3.5 py-2 rounded-chip text-[12px] font-semibold text-ink-2 hover:bg-white" @click="$emit('close')">{{ L("Cancel", "إلغاء", "Annuler") }}</button>
          <button class="px-4 py-2 rounded-chip text-[12px] font-bold text-white bg-emerald-600 hover:bg-emerald-700 shadow-brand disabled:opacity-50" :disabled="!valid || saving" @click="save">
            {{ saving ? "…" : employee ? L("Save", "حفظ", "Enregistrer") : L("Create", "إنشاء", "Créer") }}
          </button>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, h } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";
import { useToast } from "@/composables/useToast";

const props = defineProps({ employee: { type: String, default: null } });
const emit = defineEmits(["close", "done"]);
const { locale } = useI18n();
const { entityId, entities } = useUi();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const entityName = computed(() => (entities.find((e) => e.id === entityId.value) || entities[0]).name);

const Field = (p, { slots }) => h("label", { class: "block" }, [
  h("span", { class: "text-[11px] font-semibold text-ink-3" }, p.label), slots.default && slots.default()]);
Field.props = ["label"];

const opt = ref({ departments: [], designations: [], employment_types: [], genders: [], statuses: ["Active", "Inactive", "Suspended", "Left"] });
const loading = ref(true), saving = ref(false), err = ref("");
const EDITABLE = ["employee_name", "first_name", "last_name", "gender", "date_of_birth", "date_of_joining", "status", "department", "designation", "employment_type", "cell_number", "company_email", "bank_name", "bank_ac_no", "iban", "relieving_date"];
const f = reactive(Object.fromEntries(EDITABLE.map((k) => [k, ""])));
f.status = "Active";

const valid = computed(() => f.first_name && f.gender && f.date_of_birth && f.date_of_joining);

onMounted(async () => {
  try {
    opt.value = await api.call("accounting_portal.api.payroll.employee_form_options", { company: currentCompany() }) || opt.value;
    if (props.employee) {
      const p = await api.call("accounting_portal.api.payroll.employee_profile", { company: currentCompany(), employee: props.employee });
      EDITABLE.forEach((k) => { if (p && p[k] != null) f[k] = p[k]; });
    }
  } catch (e) { err.value = String(e?.message || e).slice(0, 160); }
  finally { loading.value = false; }
});

async function save() {
  if (!valid.value || saving.value) return;
  saving.value = true; err.value = "";
  try {
    if (props.employee) {
      const fields = {};
      EDITABLE.forEach((k) => { fields[k] = f[k] || null; });
      await api.call("accounting_portal.api.payroll.update_employee", { company: currentCompany(), employee: props.employee, fields });
      toast.success(L("Saved", "تم الحفظ", "Enregistré"));
    } else {
      await api.call("accounting_portal.api.payroll.create_employee", {
        company: currentCompany(), first_name: f.first_name, last_name: f.last_name, gender: f.gender,
        date_of_birth: f.date_of_birth, date_of_joining: f.date_of_joining, department: f.department || undefined,
        designation: f.designation || undefined, employment_type: f.employment_type || undefined,
        cell_number: f.cell_number || undefined, company_email: f.company_email || undefined,
        bank_name: f.bank_name || undefined, bank_ac_no: f.bank_ac_no || undefined, iban: f.iban || undefined,
      });
      toast.success(L("Employee created", "تم إنشاء الموظف", "Employé créé"));
    }
    emit("done"); emit("close");
  } catch (e) { err.value = String(e?.message || e).slice(0, 200); }
  finally { saving.value = false; }
}
</script>

<style scoped>
.fi { margin-top: 4px; width: 100%; border: 1px solid var(--line-2, #e7e5e4); border-radius: 999px; padding: 8px 12px; font-size: 12px; outline: none; }
.fi:focus { border-color: rgba(15, 118, 110, .4); }
</style>
