<template>
  <div class="fixed inset-0 z-[100] flex items-start justify-center p-4 sm:p-8 overflow-y-auto" style="background:rgba(28,25,23,.45)" @click.self="$emit('close')">
    <div class="bg-white rounded-[18px] shadow-cardHover w-full max-w-xl my-8 overflow-hidden">
      <div class="flex items-center gap-2.5 px-5 py-4 border-b border-line">
        <span class="w-8 h-8 rounded-[10px] grid place-items-center" style="background:#ecfdf5"><Icon name="coins" :size="16" color="#0f766e" /></span>
        <div class="flex-1 min-w-0">
          <div class="text-[14px] font-bold">{{ L("Manual salary", "راتب يدوي", "Salaire manuel") }}</div>
          <div class="text-[11px] text-ink-muted">{{ L("One employee, any month — including leavers and past years", "موظف واحد، أي شهر — حتى اللي ساب والسنين اللي فاتت", "Un salarié, n'importe quel mois — y compris sortis et années passées") }}</div>
        </div>
        <button class="text-ink-3 hover:text-ink" @click="$emit('close')"><Icon name="close" :size="18" /></button>
      </div>

      <div v-if="loadingOpt" class="p-8 text-center text-[12px] text-ink-muted">{{ L("Loading…", "جارٍ التحميل…", "Chargement…") }}</div>
      <div v-else class="p-5 space-y-4">
        <div class="grid grid-cols-1 sm:grid-cols-[1fr_150px] gap-3">
          <label class="block">
            <span class="text-[11px] font-semibold text-ink-3">{{ L("Employee", "الموظف", "Salarié") }}</span>
            <SearchSelect v-model="employee" :items="empItems" :placeholder="L('Search a name…', 'ابحث بالاسم…', 'Rechercher…')" class="mt-1" />
          </label>
          <label class="block">
            <span class="text-[11px] font-semibold text-ink-3">{{ L("Payroll month", "شهر الراتب", "Mois de paie") }}</span>
            <input id="ms-month" type="month" v-model="month" class="fld fld-md mt-1 w-full" />
          </label>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-3 gap-2">
          <button v-for="m in MODES" :key="m.k" type="button"
                  class="text-start rounded-[12px] border px-3 py-2.5 transition-colors"
                  :class="mode === m.k ? 'border-accent bg-accent-soft' : 'border-line hover:bg-app-warm/60'" @click="mode = m.k">
            <div class="text-[12.5px] font-bold flex items-center gap-1.5"><Icon :name="m.icon" :size="13" />{{ m.title() }}</div>
            <div class="text-[11px] text-ink-muted mt-0.5 leading-snug">{{ m.sub() }}</div>
          </button>
        </div>

        <!-- what already exists for this person and month -->
        <div v-if="ctxLoad" class="text-[12px] text-ink-muted">{{ L("Reading the month…", "بقرا الشهر…", "Lecture du mois…") }}</div>
        <div v-else-if="ctx" class="rounded-[12px] border border-line-hair bg-app-warm/40 px-3.5 py-2.5 space-y-1.5 text-[12.5px]">
          <div class="flex items-center justify-between gap-2 flex-wrap">
            <span class="font-semibold">{{ ctx.nm }}
              <span class="ms-1 text-[11px] font-bold px-2 py-0.5 rounded-chip" :class="ctx.status === 'Active' ? 'bg-emerald-50 text-emerald-700' : 'bg-stone-100 text-ink-3'">{{ statusLabel(ctx.status) }}</span>
              <span v-if="ctx.relieved" class="ms-1 text-[11px] text-ink-muted">{{ L("left", "ساب", "sorti le") }} {{ ctx.relieved }}</span>
            </span>
            <span class="text-ink-muted">{{ L("Balance", "رصيده", "Solde") }}
              <b class="tnum" :class="ctx.ledger.balance < -0.005 ? 'text-rose-700' : ''" dir="ltr">{{ money(ctx.ledger.balance) }}</b></span>
          </div>
          <div class="flex gap-4 flex-wrap text-ink-3">
            <span>{{ L("Slip", "القسيمة", "Bulletin") }}:
              <b v-if="ctx.slips.length" class="text-ink" dir="ltr">{{ ctx.slips[0].name }} · {{ money(ctx.slips[0].net_pay) }}{{ ctx.slips[0].docstatus === 0 ? ' (' + L('draft', 'مسودة', 'brouillon') + ')' : '' }}</b>
              <b v-else class="text-ink">{{ L("none", "مفيش", "aucun") }}</b></span>
            <span>{{ L("Booked", "متسجل مستحق", "Comptabilisé") }}: <b class="text-ink tnum" dir="ltr">{{ money(ctx.ledger.booked) }}</b></span>
            <span>{{ L("Paid", "مدفوع", "Payé") }}: <b class="text-ink tnum" dir="ltr">{{ money(ctx.ledger.paid) }}</b></span>
          </div>
          <div v-if="ctx.closed" class="text-rose-700 font-semibold flex items-center gap-1.5"><Icon name="lock" :size="13" />{{ L("This month is closed — reopen it on Month close first.", "الشهر ده مقفول — افتحه من إقفال الشهر الأول.", "Mois clôturé — rouvrez-le d'abord.") }}</div>
          <div class="text-[11px] text-ink-muted">{{ L("Payments are matched to the month by their description; a transfer whose text names no month does not show here.", "الدفعات بتتربط بالشهر من وصفها؛ التحويل اللي وصفه مافيهوش الشهر مش هيظهر هنا.", "Les paiements sont rattachés au mois par leur libellé ; un virement sans mois n'apparaît pas ici.") }}</div>
        </div>

        <!-- slip -->
        <template v-if="mode === 'slip' && ctx">
          <div v-if="ctx.slips.length" class="rounded-[10px] border border-amber-200 bg-amber-50 px-3 py-2 text-[12.5px] text-amber-800">
            {{ L("This month already has a slip. For anything on top of it use “Manual amount”.", "الشهر ده عليه قسيمة بالفعل. أي حاجة زيادة استخدم «مبلغ يدوي».", "Ce mois a déjà un bulletin. Pour un complément, utilisez « Montant manuel ».") }}
          </div>
          <div v-else-if="ctx.preview && !ctx.preview.ok" class="rounded-[10px] border border-amber-200 bg-amber-50 px-3 py-2 text-[12.5px] text-amber-800 space-y-1.5">
            <div>{{ L("HRMS will not build a slip here:", "HRMS مش هيعمل قسيمة هنا:", "HRMS ne peut pas créer de bulletin :") }} <span class="font-mono text-[11.5px]">{{ ctx.preview.error }}</span></div>
            <button class="font-semibold underline" @click="mode = 'amount'">{{ L("Use a manual amount instead", "استخدم مبلغ يدوي بدلها", "Utiliser un montant manuel") }}</button>
          </div>
          <div v-else-if="ctx.preview" class="border border-line-hair rounded-[10px] overflow-hidden">
            <table class="w-full text-[12.5px]">
              <tbody>
                <tr v-for="(r, i) in ctx.preview.earnings" :key="'e' + i" class="border-t border-line-hair first:border-t-0">
                  <td class="px-3 py-1.5 truncate">{{ r.comp }}</td><td class="px-3 py-1.5 text-end tnum" dir="ltr">{{ money(r.amount) }}</td>
                </tr>
                <tr v-for="(r, i) in ctx.preview.deductions" :key="'d' + i" class="border-t border-line-hair text-rose-700">
                  <td class="px-3 py-1.5 truncate">{{ r.comp }}</td><td class="px-3 py-1.5 text-end tnum" dir="ltr">−{{ money(r.amount) }}</td>
                </tr>
                <tr class="border-t border-line bg-app-warm/40 font-bold">
                  <td class="px-3 py-1.5">{{ L("Net", "الصافي", "Net") }} · <span class="font-normal text-ink-muted">{{ ctx.preview.structure }} · {{ ctx.preview.payment_days }}/{{ ctx.preview.working_days }} {{ L("days", "يوم", "j") }}</span></td>
                  <td class="px-3 py-1.5 text-end tnum" dir="ltr">{{ money(ctx.preview.net) }}</td>
                </tr>
              </tbody>
            </table>
            <div class="px-3 py-1.5 text-[11px] text-ink-muted border-t border-line-hair">{{ L("Adjustments keyed for this month are included. Posts the accrual dated", "البنود المتسجلة للشهر داخلة. الاستحقاق بيتسجل بتاريخ", "Ajustements du mois inclus. Comptabilisé au") }} {{ ctx.end }}.</div>
          </div>
        </template>

        <!-- amount -->
        <template v-if="mode === 'amount'">
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <label class="block sm:col-span-2">
              <span class="text-[11px] font-semibold text-ink-3">{{ L("What it is", "النوع", "Nature") }}</span>
              <select id="ms-comp" v-model="component" class="fld fld-md mt-1 w-full cursor-pointer">
                <option v-for="c in opt.components" :key="c" :value="c">{{ c }}</option>
              </select>
            </label>
            <label class="block">
              <span class="text-[11px] font-semibold text-ink-3">{{ L("Amount", "المبلغ", "Montant") }} ({{ opt.currency }})</span>
              <input id="ms-amount" type="number" min="0" step="0.01" v-model.number="amount" class="fld fld-md mt-1 w-full tnum text-end" placeholder="0.00" />
            </label>
            <label class="block">
              <span class="text-[11px] font-semibold text-ink-3">{{ L("Booking date", "تاريخ القيد", "Date d'écriture") }}</span>
              <input id="ms-date" type="date" v-model="postingDate" class="fld fld-md mt-1 w-full" />
            </label>
          </div>
          <div class="text-[11px] text-ink-muted">{{ L("Books the salary as owed to the employee: expense of the chosen kind, credit on payroll payable.", "بيسجل الراتب كمستحق للموظف: مصروف من النوع المختار، ودائن على حساب الرواتب المستحقة.", "Comptabilise le salaire dû : charge de la nature choisie, crédit sur salaires à payer.") }}</div>
        </template>

        <!-- payment -->
        <template v-if="mode === 'payment'">
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <label class="block">
              <span class="text-[11px] font-semibold text-ink-3">{{ L("Amount paid", "المبلغ المدفوع", "Montant versé") }} ({{ opt.currency }})</span>
              <input id="ms-pay-amount" type="number" min="0" step="0.01" v-model.number="amount" class="fld fld-md mt-1 w-full tnum text-end" placeholder="0.00" />
            </label>
            <label class="block">
              <span class="text-[11px] font-semibold text-ink-3">{{ L("Date it left", "تاريخ التحويل", "Date du versement") }}</span>
              <input id="ms-pay-date" type="date" v-model="postingDate" class="fld fld-md mt-1 w-full" />
            </label>
            <label class="block">
              <span class="text-[11px] font-semibold text-ink-3">{{ L("Paid from", "مدفوع من", "Payé depuis") }}</span>
              <select id="ms-account" v-model="account" class="fld fld-md mt-1 w-full cursor-pointer">
                <option value="">—</option>
                <optgroup :label="L('Bank', 'بنك', 'Banque')"><option v-for="a in banks" :key="a.name" :value="a.name">{{ a.name }}</option></optgroup>
                <optgroup :label="L('Cash', 'خزنة', 'Caisse')"><option v-for="a in cashes" :key="a.name" :value="a.name">{{ a.name }}</option></optgroup>
              </select>
            </label>
            <label class="block">
              <span class="text-[11px] font-semibold text-ink-3">{{ L("Bank reference", "رقم المرجع", "Référence bancaire") }}</span>
              <input id="ms-ref" type="text" v-model="reference" class="fld fld-md mt-1 w-full" />
            </label>
          </div>
          <div v-if="ctx && suggested > 0.005" class="text-[11.5px] text-ink-3">
            {{ L("Still open for this month:", "الباقي للشهر ده:", "Reste à payer ce mois :") }}
            <button class="font-semibold underline tnum" dir="ltr" @click="amount = suggested">{{ money(suggested) }}</button>
          </div>
        </template>

        <label class="block">
          <span class="text-[11px] font-semibold text-ink-3">{{ L("Note", "ملاحظة", "Commentaire") }} <span class="text-ink-muted font-normal">({{ L("optional", "اختياري", "facultatif") }})</span></span>
          <input id="ms-notes" type="text" v-model="notes" class="fld fld-md mt-1 w-full" :placeholder="L('e.g. final settlement, from the reconciliation sheet', 'مثلاً تسوية نهاية خدمة، من شيت المطابقة', 'ex. STC, d\'après le rapprochement')" />
        </label>

        <div v-if="ctx && effect !== null" class="flex items-center justify-between text-[12.5px] rounded-[10px] border border-line-hair px-3 py-2">
          <span class="text-ink-3">{{ L("Employee balance", "رصيد الموظف", "Solde du salarié") }}</span>
          <span class="tnum font-semibold" dir="ltr">{{ money(ctx.ledger.balance) }} → <span :class="after < -0.005 ? 'text-rose-700' : 'text-emerald-700'">{{ money(after) }}</span></span>
        </div>
        <div v-if="error" class="text-[12px] text-sale">{{ error }}</div>
      </div>

      <div v-if="!loadingOpt" class="flex items-center justify-end gap-2 px-5 py-3.5 border-t border-line bg-app-warm/40">
        <button class="px-3.5 py-2 rounded-chip text-[12px] font-semibold text-ink-2 hover:bg-white" @click="$emit('close')">{{ L("Cancel", "إلغاء", "Annuler") }}</button>
        <UiButton variant="primary" size="md" :disabled="!ready || saving" :busy="saving" @click="submit">{{ submitLabel }}</UiButton>
      </div>
    </div>
  </div>
</template>

<script setup>
// Book one employee's salary outside the monthly run: a slip for a month that was
// missed, a figure with no structure behind it (final settlement, old salary), or
// a transfer that was made and never recorded. api/payroll.py → manual_salary.
import { ref, computed, watch, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import SearchSelect from "@/components/SearchSelect.vue";
import UiButton from "@/components/UiButton.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useToast } from "@/composables/useToast";
import { fmtMoney } from "@/utils/helpers";

const props = defineProps({ employee: { type: String, default: "" }, month: { type: String, default: "" } });
const emit = defineEmits(["close", "done"]);
const { locale } = useI18n();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const money = (n) => fmtMoney(n);

const MODES = [
  { k: "slip", icon: "list", title: () => L("Salary slip", "قسيمة راتب", "Bulletin"),
    sub: () => L("From the salary structure, for a month that was missed", "من هيكل الراتب، لشهر اتنسى", "Depuis la structure, pour un mois oublié") },
  { k: "amount", icon: "coins", title: () => L("Manual amount", "مبلغ يدوي", "Montant manuel"),
    sub: () => L("Final settlement, bonus, old salary with no structure", "تسوية نهاية خدمة، بريمة، راتب قديم", "STC, prime, ancien salaire sans structure") },
  { k: "payment", icon: "bank", title: () => L("Payment already made", "تحويل اتعمل", "Versement déjà fait"),
    sub: () => L("Record a transfer on its real date", "سجّل تحويل بتاريخه الحقيقي", "Enregistrer un virement à sa vraie date") },
];

const opt = ref({ employees: [], components: [], accounts: [] });
const loadingOpt = ref(true);
const employee = ref(props.employee);
const month = ref(props.month || new Date().toISOString().slice(0, 7));
const mode = ref("slip");
const component = ref("");
const amount = ref(null);
const postingDate = ref("");
const account = ref("");
const reference = ref("");
const notes = ref("");
const ctx = ref(null), ctxLoad = ref(false);
const saving = ref(false);
const error = ref("");
// One key per opened form: a double click is deduped, a second real entry is not.
const clientKey = Math.random().toString(36).slice(2) + Date.now().toString(36);

const STATUS = { Active: ["Active", "نشط", "Actif"], Left: ["Left", "ساب", "Sorti"], Inactive: ["Inactive", "غير نشط", "Inactif"], Suspended: ["Suspended", "موقوف", "Suspendu"] };
const statusLabel = (s) => (STATUS[s] ? L(...STATUS[s]) : s);
const empItems = computed(() => (opt.value.employees || []).map((e) => ({
  value: e.name, label: e.nm, sub: `${e.name} · ${statusLabel(e.status)}${e.relieved ? " · " + e.relieved : ""}`,
})));
const banks = computed(() => (opt.value.accounts || []).filter((a) => a.kind === "Bank"));
const cashes = computed(() => (opt.value.accounts || []).filter((a) => a.kind === "Cash"));

const suggested = computed(() => {
  if (!ctx.value) return 0;
  const owed = (ctx.value.slips[0]?.docstatus === 1 ? ctx.value.slips[0].net_pay : ctx.value.ledger.booked) - ctx.value.ledger.paid;
  return Math.round(owed * 100) / 100;
});
const effect = computed(() => {
  if (!ctx.value) return null;
  if (mode.value === "slip") return ctx.value.preview?.ok && !ctx.value.slips.length ? ctx.value.preview.net : null;
  const a = Number(amount.value) || 0;
  if (!a) return null;
  return mode.value === "amount" ? a : -a;
});
const after = computed(() => (ctx.value ? ctx.value.ledger.balance + (effect.value || 0) : 0));

const ready = computed(() => {
  if (!employee.value || !/^\d{4}-\d{2}$/.test(month.value) || !ctx.value || ctx.value.closed) return false;
  if (mode.value === "slip") return !ctx.value.slips.length && !!ctx.value.preview?.ok;
  if (!(Number(amount.value) > 0) || !postingDate.value) return false;
  if (mode.value === "amount") return !!component.value;
  return !!account.value;
});
const submitLabel = computed(() => (saving.value ? L("Saving…", "جارٍ الحفظ…", "Enregistrement…")
  : mode.value === "slip" ? L("Create and post the slip", "اعمل القسيمة وسجّلها", "Créer et comptabiliser")
  : mode.value === "amount" ? L("Book the salary", "سجّل الراتب", "Comptabiliser")
  : L("Record the payment", "سجّل التحويل", "Enregistrer le versement")));

function monthEnd(m) {
  const [y, mo] = m.split("-").map(Number);
  return new Date(Date.UTC(y, mo, 0)).toISOString().slice(0, 10);
}
function resetDate() {
  if (!/^\d{4}-\d{2}$/.test(month.value)) return;
  postingDate.value = mode.value === "payment" ? "" : monthEnd(month.value);
}

let seq = 0;
async function loadCtx() {
  ctx.value = null; error.value = "";
  if (!employee.value || !/^\d{4}-\d{2}$/.test(month.value)) return;
  const my = ++seq;
  ctxLoad.value = true;
  try {
    const r = await api.call("accounting_portal.api.payroll.manual_salary_context",
      { company: currentCompany(), employee: employee.value, month: month.value }, { fresh: true });
    if (my === seq) ctx.value = r || null;
  } catch (e) { if (my === seq) error.value = String(e?.message || e).slice(0, 200); }
  finally { if (my === seq) ctxLoad.value = false; }
}
watch([employee, month], () => { resetDate(); loadCtx(); });
watch(mode, resetDate);

onMounted(async () => {
  try {
    opt.value = await api.call("accounting_portal.api.payroll.manual_salary_options", { company: currentCompany() }) || opt.value;
    component.value = opt.value.default_component && opt.value.components.includes(opt.value.default_component)
      ? opt.value.default_component : (opt.value.components[0] || "");
  } catch (e) { error.value = String(e?.message || e).slice(0, 200); }
  finally { loadingOpt.value = false; }
  resetDate();
  loadCtx();
});

async function submit() {
  if (!ready.value || saving.value) return;
  saving.value = true; error.value = "";
  try {
    const res = await api.call("accounting_portal.api.payroll.manual_salary", {
      company: currentCompany(), client_key: clientKey, employee: employee.value, month: month.value, mode: mode.value,
      amount: mode.value === "slip" ? undefined : Number(amount.value),
      salary_component: mode.value === "amount" ? component.value : undefined,
      posting_date: mode.value === "slip" ? undefined : postingDate.value,
      account: mode.value === "payment" ? account.value : undefined,
      reference: mode.value === "payment" ? reference.value : undefined,
      notes: notes.value || undefined,
    });
    if (res && res.status === "Proposed") toast.success(L("Sent for approval", "اتبعت للموافقة", "Envoyé pour approbation"));
    else toast.success(L("Saved", "اتسجل", "Enregistré") + (res?.voucher_no ? " · " + res.voucher_no : ""));
    emit("done", res);
    emit("close");
  } catch (e) {
    if (!e?.explained) error.value = String(e?.message || e).slice(0, 240);
  } finally { saving.value = false; }
}
</script>
