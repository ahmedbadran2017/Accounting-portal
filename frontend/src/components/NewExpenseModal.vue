<template>
  <div class="fixed inset-0 z-[100] flex items-start justify-center p-4 sm:p-8 overflow-y-auto" style="background:rgba(28,25,23,.45)" @click.self="$emit('close')">
    <div class="bg-white rounded-[18px] shadow-cardHover w-full max-w-xl my-6 overflow-hidden">
      <div class="flex items-center gap-2.5 px-5 py-4 border-b border-line">
        <span class="w-8 h-8 rounded-[10px] grid place-items-center" style="background:#fff7ed"><Icon name="wallet" :size="16" color="#b45309" /></span>
        <div class="flex-1 min-w-0">
          <div class="text-[14px] font-bold">{{ L("Record an expense", "تسجيل مصروف", "Enregistrer une dépense") }}</div>
          <div class="text-[11px] text-ink-muted">{{ entityName }} · {{ L("posts to ERPNext via the audit gateway", "يُرحّل لـ ERPNext عبر بوابة التدقيق", "via la passerelle d'audit") }}</div>
        </div>
        <button class="text-ink-3 hover:text-ink" @click="$emit('close')"><Icon name="close" :size="18" /></button>
      </div>

      <div v-if="optLoad" class="p-8 text-center text-ink-muted text-[12px]">{{ L("Loading…", "جارٍ التحميل…", "…") }}</div>
      <template v-else>
        <div class="p-5 space-y-3.5">
          <!-- expense account -->
          <label class="block">
            <span class="text-[11px] font-semibold text-ink-3">{{ L("Expense account", "حساب المصروف", "Compte de charge") }}</span>
            <input v-model.trim="acctFilter" :placeholder="L('filter accounts…','تصفية الحسابات…','filtrer…')" class="mt-1 w-full border border-line-2 rounded-chip px-3 py-1.5 text-[11.5px] focus:outline-none focus:border-accent/40" />
            <select v-model="expenseAccount" size="1" class="mt-1.5 w-full border border-line-2 rounded-chip px-3 py-2 text-[12px] focus:outline-none focus:border-accent/40 cursor-pointer">
              <option value="">—</option>
              <option v-for="a in filteredAccounts" :key="a.name" :value="a.name">{{ a.num ? a.num + " · " : "" }}{{ a.nm }}{{ a.ccy && a.ccy !== opt.currency ? " · " + a.ccy : "" }}</option>
            </select>
            <div v-if="selectedAccount" class="mt-1 flex items-center gap-1.5">
              <span class="text-[10px] font-semibold px-1.5 py-0.5 rounded-chip" :style="`background:${catColor(selectedAccount.category)}20;color:${catColor(selectedAccount.category)}`">{{ selectedAccount.category }}</span>
            </div>
          </label>

          <div class="grid grid-cols-2 gap-3">
            <label class="block">
              <span class="text-[11px] font-semibold text-ink-3">{{ L("Amount", "المبلغ", "Montant") }} ({{ opt.currency }})</span>
              <input type="number" min="0" step="0.01" v-model.number="amount" class="mt-1 w-full border border-line-2 rounded-chip px-3 py-2 text-[13px] tnum font-semibold text-end focus:outline-none focus:border-accent/40" placeholder="0.00" />
            </label>
            <label class="block">
              <span class="text-[11px] font-semibold text-ink-3">{{ L("Date", "التاريخ", "Date") }}</span>
              <input type="date" v-model="postingDate" class="mt-1 w-full border border-line-2 rounded-chip px-3 py-2 text-[12px] focus:outline-none focus:border-accent/40" />
            </label>
          </div>

          <!-- pay from -->
          <label class="block">
            <span class="text-[11px] font-semibold text-ink-3">{{ L("Paid from", "مدفوع من", "Payé depuis") }}</span>
            <select v-model="payAccount" class="mt-1 w-full border border-line-2 rounded-chip px-3 py-2 text-[12px] focus:outline-none focus:border-accent/40 cursor-pointer">
              <option v-for="a in opt.pay_accounts" :key="a.name" :value="a.name">{{ payLabel(a) }}</option>
            </select>
          </label>

          <!-- supplier (only meaningful for a payable/credit account) -->
          <label v-if="isPayable" class="block">
            <span class="text-[11px] font-semibold text-ink-3">{{ L("Supplier", "المورّد", "Fournisseur") }} <span class="text-ink-muted font-normal">({{ L("optional", "اختياري", "facultatif") }})</span></span>
            <select v-model="party" class="mt-1 w-full border border-line-2 rounded-chip px-3 py-2 text-[12px] focus:outline-none focus:border-accent/40 cursor-pointer">
              <option value="">—</option>
              <option v-for="s in opt.suppliers" :key="s" :value="s">{{ s }}</option>
            </select>
          </label>

          <label class="block">
            <span class="text-[11px] font-semibold text-ink-3">{{ L("Description", "الوصف", "Description") }}</span>
            <input v-model.trim="description" :placeholder="L('e.g. June office rent','مثال: إيجار المكتب يونيو','ex. loyer juin')" class="mt-1 w-full border border-line-2 rounded-chip px-3 py-2 text-[12px] focus:outline-none focus:border-accent/40" />
          </label>

          <!-- live double-entry preview -->
          <div v-if="canPreview" class="border border-line rounded-[12px] overflow-hidden text-[11.5px]">
            <div class="px-3 py-1.5 bg-app-warm/50 text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Journal preview", "معاينة القيد", "Aperçu de l'écriture") }}</div>
            <div class="flex items-center justify-between px-3 py-2 border-t border-line-hair">
              <span class="truncate">{{ L("Dr", "مدين", "Dr") }} · {{ shortAcct(expenseAccount) }}</span>
              <span class="tnum font-bold text-teal-700">{{ money(amount) }}</span>
            </div>
            <div class="flex items-center justify-between px-3 py-2 border-t border-line-hair">
              <span class="truncate">{{ L("Cr", "دائن", "Cr") }} · {{ shortAcct(payAccount) }}{{ party ? " · " + party : "" }}</span>
              <span class="tnum font-bold text-rose-600">{{ money(amount) }}</span>
            </div>
          </div>

          <div v-if="currencyWarn" class="text-[11px] text-amber-700 inline-flex items-center gap-1.5"><Icon name="alert" :size="13" />{{ L("Expense and pay accounts use different currencies — post this one in ERPNext.", "حساب المصروف والدفع بعملتين مختلفتين — رحّله من ERPNext.", "Devises différentes — passez-la dans ERPNext.") }}</div>
          <div v-else-if="amount >= opt.threshold" class="text-[11px] text-amber-700 inline-flex items-center gap-1.5"><Icon name="shield" :size="12" />{{ L("Material amount — needs an approver before it posts.", "مبلغ جوهري — يحتاج موافقة قبل الترحيل.", "Montant important — approbation requise.") }}</div>
          <div v-if="error" class="text-[11.5px] text-sale">{{ error }}</div>
        </div>

        <div class="flex items-center justify-end gap-2 px-5 py-3.5 border-t border-line bg-app-warm/40">
          <button class="px-3.5 py-2 rounded-chip text-[12px] font-semibold text-ink-2 hover:bg-white" @click="$emit('close')">{{ L("Cancel", "إلغاء", "Annuler") }}</button>
          <button class="px-4 py-2 rounded-chip text-[12px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand disabled:opacity-50" :disabled="!canSubmit || posting" @click="submit">
            {{ posting ? L("Saving…", "جارٍ الحفظ…", "…") : amount >= opt.threshold ? L("Submit for approval", "إرسال للموافقة", "Soumettre") : L("Record expense", "تسجيل المصروف", "Enregistrer") }}
          </button>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";
import { fmtMoney } from "@/utils/helpers";

const emit = defineEmits(["close", "posted"]);
const { locale } = useI18n();
const { entityId, entities } = useUi();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const entityName = computed(() => (entities.find((e) => e.id === entityId.value) || entities[0]).name);
const money = (n) => fmtMoney(n, "", 2);

const CAT_COLOR = { COGS: "#0f766e", "Freight & Logistics": "#0369a1", Payroll: "#7c3aed", Marketing: "#db2777", Taxes: "#0891b2", Financial: "#4f46e5", "Rent, Office & Utilities": "#b45309", Other: "#78716c" };
const catColor = (c) => (opt.value.cat_color && opt.value.cat_color[c]) || CAT_COLOR[c] || "#78716c";

const opt = ref({ expense_accounts: [], pay_accounts: [], suppliers: [], currency: "MAD", threshold: 10000 });
const optLoad = ref(true);
const acctFilter = ref("");
const expenseAccount = ref("");
const amount = ref(null);
const postingDate = ref(new Date().toISOString().slice(0, 10));
const payAccount = ref("");
const party = ref("");
const description = ref("");
const posting = ref(false);
const error = ref("");

onMounted(async () => {
  try {
    opt.value = await api.call("accounting_portal.api.expenses.expense_form_options", { company: currentCompany() }) || opt.value;
    payAccount.value = opt.value.default_pay || (opt.value.pay_accounts[0] && opt.value.pay_accounts[0].name) || "";
  } catch (e) { error.value = (e && e.message) || "Failed to load"; }
  finally { optLoad.value = false; }
});

const filteredAccounts = computed(() => {
  const q = acctFilter.value.toLowerCase();
  const list = opt.value.expense_accounts || [];
  if (!q) return list.slice(0, 400);
  return list.filter((a) => (a.num || "").toLowerCase().includes(q) || (a.nm || "").toLowerCase().includes(q) || (a.category || "").toLowerCase().includes(q)).slice(0, 400);
});
const selectedAccount = computed(() => (opt.value.expense_accounts || []).find((a) => a.name === expenseAccount.value) || null);
const payMap = computed(() => Object.fromEntries((opt.value.pay_accounts || []).map((a) => [a.name, a])));
const isPayable = computed(() => payMap.value[payAccount.value]?.typ === "Payable");
const canPreview = computed(() => expenseAccount.value && payAccount.value && Number(amount.value) > 0);
const currencyWarn = computed(() => {
  const ea = selectedAccount.value, pa = payMap.value[payAccount.value];
  const eccy = (ea && ea.ccy) || opt.value.currency;
  const pccy = (pa && pa.ccy) || opt.value.currency;
  return ea && pa && eccy !== pccy;
});
const canSubmit = computed(() => canPreview.value && !currencyWarn.value);

function payLabel(a) {
  const t = a.typ === "Bank" ? L("Bank", "بنك", "Banque") : a.typ === "Cash" ? L("Cash", "نقدية", "Caisse") : L("Payable", "ذمم دائنة", "À payer");
  return `${a.nm} · ${t}`;
}
function shortAcct(name) { const a = (opt.value.expense_accounts || []).concat(opt.value.pay_accounts || []).find((x) => x.name === name); return a ? (a.num ? a.num + " " : "") + a.nm : name; }

async function submit() {
  error.value = "";
  if (!canSubmit.value) return;
  posting.value = true;
  try {
    const res = await api.call("accounting_portal.api.expenses.create_expense", {
      company: currentCompany(), expense_account: expenseAccount.value,
      amount: Number(amount.value), posting_date: postingDate.value,
      pay_account: payAccount.value, party: (isPayable.value && party.value) || undefined,
      description: description.value || undefined,
    });
    emit("posted", res);
    emit("close");
  } catch (e) {
    error.value = (e && e.message) || L("Failed to save.", "فشل الحفظ.", "Échec.");
  } finally { posting.value = false; }
}
</script>
