<template>
  <div class="grid gap-3.5 lg:grid-cols-2">
    <!-- ── Attendance punches ── -->
    <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
      <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2 flex-wrap">
        <Icon name="clock" :size="14" color="#0b5c4f" /><span class="text-[12px] font-bold">{{ L("Attendance punches", "بصمات الحضور", "Pointages") }}</span>
        <input type="date" v-model="ci.from" @change="loadCheckins" class="h-7 rounded-[8px] border border-line-2 px-1.5 text-[11px] bg-white" />
        <span class="text-[11px] text-ink-muted">→</span>
        <input type="date" v-model="ci.to" @change="loadCheckins" class="h-7 rounded-[8px] border border-line-2 px-1.5 text-[11px] bg-white" />
        <span class="text-[11px] text-ink-muted ms-auto tnum">{{ ci.rows.length }}</span>
      </div>
      <div v-if="canWrite" class="px-4 py-2.5 border-b border-line-hair bg-app-warm/30 grid gap-2 sm:grid-cols-[1fr_auto_auto_auto] items-end">
        <div><label class="block text-[11px] font-bold text-ink-3 mb-0.5">{{ L("Employee", "الموظف", "Employé") }}</label><SearchSelect v-model="ciForm.employee" :items="empItems" :placeholder="L('Select…','اختر…','Choisir…')" inputClass="h-8 text-[12px] bg-white" /></div>
        <div><label class="block text-[11px] font-bold text-ink-3 mb-0.5">{{ L("Type", "النوع", "Type") }}</label>
          <select v-model="ciForm.log_type" class="h-8 rounded-[8px] border border-line-2 px-1.5 text-[12px] bg-white"><option value="IN">IN</option><option value="OUT">OUT</option></select></div>
        <div><label class="block text-[11px] font-bold text-ink-3 mb-0.5">{{ L("Time", "الوقت", "Heure") }}</label><input type="datetime-local" v-model="ciForm.time" class="h-8 rounded-[8px] border border-line-2 px-1.5 text-[12px] bg-white" /></div>
        <button type="button" :disabled="busy || !ciForm.employee || !ciForm.time" class="h-8 px-3 rounded-chip text-[12px] font-semibold text-white bg-brand hover:bg-brand-dark disabled:opacity-50" @click="addCheckin">{{ L("Add", "إضافة", "Ajouter") }}</button>
      </div>
      <TableLoading v-if="ci.loading" :rows="5" />
      <div v-else-if="!ci.rows.length" class="px-4 py-8 text-center text-[12px] text-ink-muted">{{ L("No punches in this range.", "لا بصمات في هذه الفترة.", "Aucun pointage.") }}</div>
      <div v-else class="max-h-[420px] overflow-auto">
        <table class="w-full text-[12px]">
          <tbody>
            <tr v-for="r in ci.rows" :key="r.name" class="border-t border-line-hair">
              <td class="px-4 py-1.5 font-semibold truncate max-w-[200px]">{{ r.nm }}</td>
              <td class="px-2 py-1.5"><span class="text-[11px] font-bold px-1.5 py-0.5 rounded" :class="r.log_type === 'IN' ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'">{{ r.log_type }}</span></td>
              <td class="px-2 py-1.5 tnum text-ink-2 whitespace-nowrap"><bdi dir="ltr">{{ r.time }}</bdi></td>
              <td class="px-2 py-1.5 text-[11px] text-ink-muted">{{ r.device === 'portal' ? L("portal", "بورتال", "portail") : (r.device || "") }}</td>
              <td class="px-3 py-1.5 text-end"><button v-if="canWrite && r.deletable" type="button" class="text-ink-muted hover:text-sale" @click="delCheckin(r)"><Icon name="close" :size="12" /></button></td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="px-4 py-2 border-t border-line-hair text-[11px] text-ink-muted">{{ L("Punches feed HR attendance; a portal-entered punch can be removed until attendance uses it.", "البصمات بتغذّي الحضور؛ البصمة المدخلة من البورتال تتحذف لحد ما الحضور يستخدمها.", "Les pointages alimentent la présence.") }}</div>
    </div>

    <!-- ── Employee advances ── -->
    <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
      <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2 flex-wrap">
        <Icon name="wallet" :size="14" color="#0b5c4f" /><span class="text-[12px] font-bold">{{ L("Employee advances", "سلف الموظفين", "Avances aux employés") }}</span>
        <span class="text-[11px] text-ink-muted">{{ L("open", "مفتوح", "en cours") }} <b class="tnum">{{ money(adv.open_total) }}</b> {{ adv.currency || "" }}</span>
        <button v-if="canWrite" type="button" class="ms-auto inline-flex items-center gap-1 h-8 px-3 rounded-chip text-[12px] font-semibold text-white bg-brand hover:bg-brand-dark" @click="advOpen = !advOpen"><Icon name="plus" :size="12" />{{ L("New advance", "سلفة جديدة", "Nouvelle avance") }}</button>
      </div>
      <div v-if="advOpen" class="px-4 py-3 border-b border-line-hair bg-app-warm/30 grid gap-2 sm:grid-cols-2">
        <div class="sm:col-span-2"><label class="block text-[11px] font-bold text-ink-3 mb-0.5">{{ L("Employee", "الموظف", "Employé") }}</label><SearchSelect v-model="advForm.employee" :items="empItems" :placeholder="L('Select…','اختر…','Choisir…')" inputClass="h-8 text-[12px] bg-white" /></div>
        <div><label class="block text-[11px] font-bold text-ink-3 mb-0.5">{{ L("Amount", "المبلغ", "Montant") }}</label><input type="number" step="any" min="0" v-model="advForm.amount" dir="ltr" class="h-8 w-full rounded-[8px] border border-line-2 px-2 text-[12px] tnum bg-white" /></div>
        <div><label class="block text-[11px] font-bold text-ink-3 mb-0.5">{{ L("Date", "التاريخ", "Date") }}</label><input type="date" v-model="advForm.posting_date" class="h-8 w-full rounded-[8px] border border-line-2 px-2 text-[12px] bg-white" /></div>
        <div class="sm:col-span-2"><label class="block text-[11px] font-bold text-ink-3 mb-0.5">{{ L("Purpose", "الغرض", "Objet") }}</label><input v-model.trim="advForm.purpose" class="h-8 w-full rounded-[8px] border border-line-2 px-2 text-[12px] bg-white" /></div>
        <div><label class="block text-[11px] font-bold text-ink-3 mb-0.5">{{ L("Paid via", "طريقة الدفع", "Mode") }}</label>
          <select v-model="advForm.mode_of_payment" class="h-8 w-full rounded-[8px] border border-line-2 px-1.5 text-[12px] bg-white"><option value="">—</option><option v-for="m in advOpts.modes" :key="m.value" :value="m.value">{{ m.label }}</option></select></div>
        <div><label class="block text-[11px] font-bold text-ink-3 mb-0.5">{{ L("Advance account", "حساب السلف", "Compte d'avance") }}</label>
          <select v-model="advForm.advance_account" class="h-8 w-full rounded-[8px] border border-line-2 px-1.5 text-[12px] bg-white"><option value="">{{ L("company default", "افتراضي الشركة", "défaut") }}</option><option v-for="a in advOpts.accounts" :key="a.value" :value="a.value">{{ a.label }}</option></select></div>
        <label class="sm:col-span-2 inline-flex items-center gap-2 text-[12px]"><input type="checkbox" v-model="advForm.repay" /> {{ L("Repay unclaimed balance from salary", "خصم الباقي من المرتب", "Rembourser sur salaire") }}</label>
        <div class="sm:col-span-2 flex items-center gap-2">
          <span v-if="advErr" class="text-[12px] text-sale">{{ advErr }}</span>
          <button type="button" :disabled="busy || !advForm.employee || !advForm.amount || !advForm.purpose" class="ms-auto h-8 px-4 rounded-chip text-[12px] font-semibold text-white bg-brand hover:bg-brand-dark disabled:opacity-50" @click="createAdvance">{{ busy ? "…" : L("Book advance", "تسجيل السلفة", "Enregistrer") }}</button>
        </div>
      </div>
      <TableLoading v-if="adv.loading" :rows="5" />
      <div v-else-if="!adv.rows.length" class="px-4 py-8 text-center text-[12px] text-ink-muted">{{ L("No employee advances.", "لا سلف.", "Aucune avance.") }}</div>
      <div v-else class="max-h-[420px] overflow-auto">
        <table class="w-full text-[12px]">
          <thead><tr class="text-[11px] font-bold uppercase tracking-wider text-ink-muted" style="background:#fafaf9">
            <th class="px-4 py-2 text-start">{{ L("Employee", "الموظف", "Employé") }}</th><th class="px-2 py-2 text-start">{{ L("Date", "التاريخ", "Date") }}</th>
            <th class="px-2 py-2 text-end">{{ L("Amount", "المبلغ", "Montant") }}</th><th class="px-2 py-2 text-end">{{ L("Open", "الباقي", "Solde") }}</th><th class="px-3 py-2 text-end">{{ L("Status", "الحالة", "Statut") }}</th>
          </tr></thead>
          <tbody>
            <tr v-for="r in adv.rows" :key="r.name" class="border-t border-line-hair">
              <td class="px-4 py-1.5"><span class="font-semibold">{{ r.nm }}</span><span class="block text-[11px] text-ink-muted truncate max-w-[220px]">{{ r.purpose }}</span></td>
              <td class="px-2 py-1.5 tnum text-ink-2 whitespace-nowrap">{{ r.posting_date }}</td>
              <td class="px-2 py-1.5 text-end tnum">{{ money(r.advance_amount) }}</td>
              <td class="px-2 py-1.5 text-end tnum" :class="r.open > 0 ? 'text-amber-700 font-semibold' : 'text-ink-muted'">{{ money(r.open) }}</td>
              <td class="px-3 py-1.5 text-end whitespace-nowrap">
                <span class="text-[11px] font-semibold px-1.5 py-0.5 rounded" :class="r.docstatus === 0 ? 'bg-amber-50 text-amber-700' : r.status === 'Claimed' || r.status === 'Returned' ? 'bg-emerald-50 text-emerald-700' : 'bg-app-warm text-ink-3'">{{ r.docstatus === 0 ? L("Draft", "مسودة", "Brouillon") : r.status }}</span>
                <button v-if="canWrite && r.docstatus === 1 && r.paid_amount < r.advance_amount" type="button" :disabled="busy" class="ms-1 text-[11px] font-bold px-1.5 py-0.5 rounded border border-line-2 hover:bg-app-warm" @click="advFlow(r, 'pay')">{{ L("Pay", "صرف", "Payer") }}</button>
                <button v-if="canWrite && r.docstatus === 1 && r.paid_amount > 0 && r.open > 0" type="button" :disabled="busy" class="ms-1 text-[11px] font-bold px-1.5 py-0.5 rounded border border-line-2 hover:bg-app-warm" @click="advFlow(r, 'return')">{{ L("Return", "رد", "Retour") }}</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="px-4 py-2 border-t border-line-hair text-[11px] text-ink-muted">{{ L("An advance posts on submit and is reversible from Settings → Activity. Recovery runs through the salary slip when 'repay from salary' is on.", "السلفة بتترحّل عند التسجيل ويمكن عكسها من الإعدادات ← النشاط. الاسترداد بيتم من المرتب لو فعّلت الخصم.", "L'avance est comptabilisée à la validation.") }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
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
const busy = ref(false);

const pad = (n) => String(n).padStart(2, "0");
const today = new Date();
const iso = (dt) => `${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())}`;
const nowLocal = () => `${iso(today)}T${pad(today.getHours())}:${pad(today.getMinutes())}`;

const emps = ref([]);
const empItems = computed(() => emps.value.map((e) => ({ value: e.name, label: e.nm })));
async function loadEmps() {
  try { const r = await api.call("accounting_portal.api.payroll.payroll_employees", { company: currentCompany(), status: "Active" }); emps.value = r?.rows || []; } catch { emps.value = []; }
}

// ── check-ins ──
const ci = reactive({ from: iso(new Date(today.getFullYear(), today.getMonth(), 1)), to: iso(today), rows: [], loading: true });
const ciForm = reactive({ employee: "", log_type: "IN", time: nowLocal() });
async function loadCheckins() {
  ci.loading = true;
  try { ci.rows = (await api.call("accounting_portal.api.payroll.list_checkins", { company: currentCompany(), from_date: ci.from, to_date: ci.to }, { fresh: true }))?.rows || []; }
  catch { ci.rows = []; } finally { ci.loading = false; }
}
async function addCheckin() {
  busy.value = true;
  try {
    await api.call("accounting_portal.api.payroll.add_checkin", { company: currentCompany(), employee: ciForm.employee, log_type: ciForm.log_type, time: ciForm.time });
    toast.success(L("Punch recorded", "تم تسجيل البصمة", "Pointage enregistré"));
    ciForm.log_type = ciForm.log_type === "IN" ? "OUT" : "IN";
    loadCheckins();
  } catch (e) { toast.error(String(e?.message || e).slice(0, 160)); }
  finally { busy.value = false; }
}
async function delCheckin(r) {
  try { await api.call("accounting_portal.api.payroll.delete_checkin", { name: r.name }); loadCheckins(); }
  catch (e) { toast.error(String(e?.message || e).slice(0, 160)); }
}

// ── advances ──
const adv = reactive({ rows: [], open_total: 0, currency: "", loading: true });
const advOpts = reactive({ accounts: [], modes: [] });
const advOpen = ref(false);
const advErr = ref("");
const advForm = reactive({ employee: "", amount: "", posting_date: iso(today), purpose: "", mode_of_payment: "", advance_account: "", repay: true });
async function loadAdvances() {
  adv.loading = true;
  try { Object.assign(adv, (await api.call("accounting_portal.api.payroll.list_employee_advances", { company: currentCompany() }, { fresh: true })) || { rows: [] }); }
  catch { adv.rows = []; } finally { adv.loading = false; }
}
async function loadAdvOpts() {
  try { Object.assign(advOpts, (await api.call("accounting_portal.api.payroll.advance_options", { company: currentCompany() })) || {}); } catch { /* */ }
}
async function createAdvance() {
  busy.value = true; advErr.value = "";
  try {
    const r = await api.call("accounting_portal.api.payroll.create_employee_advance", {
      company: currentCompany(), employee: advForm.employee, amount: advForm.amount, purpose: advForm.purpose,
      posting_date: advForm.posting_date, mode_of_payment: advForm.mode_of_payment, advance_account: advForm.advance_account,
      repay_from_salary: advForm.repay ? 1 : 0 });
    toast.success(r?.status && r.status !== "Posted" ? L("Queued for approval", "بانتظار الموافقة", "En attente d'approbation") : L("Advance booked", "تم تسجيل السلفة", "Avance enregistrée"));
    advOpen.value = false; Object.assign(advForm, { employee: "", amount: "", purpose: "" });
    loadAdvances();
  } catch (e) { advErr.value = String(e?.message || e).slice(0, 200); }
  finally { busy.value = false; }
}

// Pay (→ Payment Entry draft) / Return (→ Journal Entry draft) through docflow, then open the draft.
const router = useRouter();
async function advFlow(r, key) {
  busy.value = true;
  try {
    const res0 = await api.call("accounting_portal.api.docflow.create", { doctype: "Employee Advance", name: r.name, key, company: currentCompany() });
    let res = res0 && res0.result; res = typeof res === "string" ? JSON.parse(res) : res;
    toast.success((key === "pay" ? L("Payment draft created", "تم إنشاء مسودة الدفع", "Brouillon de paiement créé") : L("Return entry drafted", "تم إنشاء قيد الرد", "Écriture de retour créée")) + (res?.new_doc ? " · " + res.new_doc : ""));
    if (res?.new_doc) router.push({ path: key === "pay" ? "/accounting/purchases/payments" : "/accounting/accountant/journals", query: { id: res.new_doc } });
  } catch (e) { toast.error(String(e?.message || e).slice(0, 200)); }
  finally { busy.value = false; }
}

function loadAll() { loadEmps(); loadCheckins(); loadAdvances(); loadAdvOpts(); }
onMounted(loadAll);
watch(entityId, loadAll);
</script>
