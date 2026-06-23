<template>
  <div class="fixed inset-0 z-[100] flex items-start justify-center p-4 sm:p-8 overflow-y-auto" style="background:rgba(28,25,23,.45)" @click.self="$emit('close')">
    <div class="bg-white rounded-[18px] shadow-cardHover w-full max-w-2xl my-6 overflow-hidden">
      <div class="flex items-center gap-2.5 px-5 py-4 border-b border-line">
        <span class="w-8 h-8 rounded-[10px] grid place-items-center" style="background:#f5f3ff"><Icon name="ledger" :size="16" color="#7c3aed" /></span>
        <div class="flex-1 min-w-0">
          <div class="text-[14px] font-bold">{{ L("New journal entry", "قيد يومية جديد", "Nouvelle écriture") }}</div>
          <div class="text-[11px] text-ink-muted">{{ entityName }} · {{ L("posts to ERPNext via the audit gateway", "يُرحّل لـ ERPNext عبر بوابة التدقيق", "passe via la passerelle d'audit") }}</div>
        </div>
        <button class="text-ink-3 hover:text-ink" @click="$emit('close')"><Icon name="close" :size="18" /></button>
      </div>

      <div class="p-5 space-y-3.5">
        <div class="grid grid-cols-2 gap-3">
          <label class="block">
            <span class="text-[11px] font-semibold text-ink-3">{{ L("Date", "التاريخ", "Date") }}</span>
            <input type="date" v-model="postingDate" class="mt-1 w-full border border-line-2 rounded-chip px-3 py-2 text-[12px] focus:outline-none focus:border-accent/40" />
          </label>
          <label class="block">
            <span class="text-[11px] font-semibold text-ink-3">{{ L("Memo", "ملاحظة", "Mémo") }}</span>
            <input v-model="remark" :placeholder="L('e.g. June accrual', 'مثال: استحقاق يونيو', 'ex. régul. juin')" class="mt-1 w-full border border-line-2 rounded-chip px-3 py-2 text-[12px] focus:outline-none focus:border-accent/40" />
          </label>
        </div>

        <div class="border border-line rounded-[12px] overflow-hidden">
          <table class="w-full text-[12px]">
            <thead>
              <tr style="background:#fafaf9">
                <th class="px-3 py-2 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Account", "الحساب", "Compte") }}</th>
                <th class="px-3 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted w-28">{{ L("Debit", "مدين", "Débit") }}</th>
                <th class="px-3 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted w-28">{{ L("Credit", "دائن", "Crédit") }}</th>
                <th class="w-8"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(ln, i) in lines" :key="i" class="border-t border-line-hair">
                <td class="px-2 py-1.5">
                  <select v-model="ln.account" class="w-full bg-transparent text-[12px] py-1 focus:outline-none cursor-pointer">
                    <option value="">—</option>
                    <option v-for="a in accounts" :key="a.name" :value="a.name">{{ a.name }}{{ a.currency ? " · " + a.currency : "" }}</option>
                  </select>
                </td>
                <td class="px-2 py-1.5"><input type="number" min="0" v-model.number="ln.debit" class="w-full text-end tnum bg-transparent py-1 focus:outline-none" placeholder="0" /></td>
                <td class="px-2 py-1.5"><input type="number" min="0" v-model.number="ln.credit" class="w-full text-end tnum bg-transparent py-1 focus:outline-none" placeholder="0" /></td>
                <td class="px-2 text-center"><button v-if="lines.length > 2" class="text-ink-muted hover:text-sale" @click="lines.splice(i, 1)"><Icon name="close" :size="13" /></button></td>
              </tr>
            </tbody>
            <tfoot>
              <tr class="border-t border-line-2" style="background:#fafaf9">
                <td class="px-3 py-2"><button class="text-[11px] font-semibold text-accent hover:text-accent-dark inline-flex items-center gap-1" @click="lines.push({ account: '', debit: null, credit: null })"><Icon name="plus" :size="12" />{{ L("Add line", "سطر", "Ligne") }}</button></td>
                <td class="px-3 py-2 text-end tnum font-bold">{{ fmt(totalDr) }}</td>
                <td class="px-3 py-2 text-end tnum font-bold">{{ fmt(totalCr) }}</td>
                <td></td>
              </tr>
            </tfoot>
          </table>
        </div>

        <div class="flex items-center justify-between text-[12px]">
          <span class="inline-flex items-center gap-1.5 font-semibold" :class="balanced ? 'text-success-dark' : 'text-sale'">
            <Icon :name="balanced ? 'check' : 'alert'" :size="14" />
            {{ balanced ? L("Balanced", "متوازن", "Équilibrée") : L("Out by " + fmt(Math.abs(totalDr - totalCr)), "فرق " + fmt(Math.abs(totalDr - totalCr)), "Écart " + fmt(Math.abs(totalDr - totalCr))) }}
          </span>
          <span v-if="totalDr >= 10000" class="text-[11px] text-amber-700 inline-flex items-center gap-1"><Icon name="shield" :size="12" />{{ L("needs an approver", "يحتاج موافِق", "approbation requise") }}</span>
        </div>

        <div v-if="mixedCurrency" class="text-[11.5px] text-sale inline-flex items-center gap-1.5"><Icon name="alert" :size="13" />{{ L("Mixed currencies (" + usedCurrencies.join(", ") + ") — use one currency per entry", "عملات مختلطة (" + usedCurrencies.join("، ") + ") — استخدم عملة واحدة للقيد", "Devises mixtes — une seule par écriture") }}</div>
        <div v-if="error" class="text-[11.5px] text-sale">{{ error }}</div>
      </div>

      <div class="flex items-center justify-end gap-2 px-5 py-3.5 border-t border-line bg-app-warm/40">
        <button class="px-3.5 py-2 rounded-chip text-[12px] font-semibold text-ink-2 hover:bg-white" @click="$emit('close')">{{ L("Cancel", "إلغاء", "Annuler") }}</button>
        <button class="px-4 py-2 rounded-chip text-[12px] font-bold text-white bg-accent hover:bg-accent-dark shadow-prim disabled:opacity-50" :disabled="!balanced || mixedCurrency || posting" @click="post">
          {{ posting ? L("Posting…", "جارٍ…", "…") : L("Post entry", "ترحيل القيد", "Passer") }}
        </button>
      </div>
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

const emit = defineEmits(["close", "posted"]);
const { locale } = useI18n();
const { entityId, entities } = useUi();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const entityName = computed(() => (entities.find((e) => e.id === entityId.value) || entities[0]).name);
const fmt = (n) => Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const SAMPLE_ACCOUNTS = [
  { name: "71.999 - Correction Need Income - JM" }, { name: "120.01 - Debtors - JM" },
  { name: "100.002.002 - Petty cash - JM" }, { name: "600.002 - Good Sales at Morocco - JM" },
  { name: "320.01 - Creditors - JM" }, { name: "191.020 - VAT %20 - JM" },
];

const postingDate = ref(new Date().toISOString().slice(0, 10));
const remark = ref("");
const lines = ref([{ account: "", debit: null, credit: null }, { account: "", debit: null, credit: null }]);
const accounts = ref([]);
const posting = ref(false);
const error = ref("");

onMounted(async () => {
  try {
    const a = await api.call("accounting_portal.api.accountant.account_options", { company: currentCompany() });
    accounts.value = Array.isArray(a) && a.length ? a : SAMPLE_ACCOUNTS;
  } catch { accounts.value = SAMPLE_ACCOUNTS; }
});

const totalDr = computed(() => lines.value.reduce((s, l) => s + (Number(l.debit) || 0), 0));
const totalCr = computed(() => lines.value.reduce((s, l) => s + (Number(l.credit) || 0), 0));
const balanced = computed(() => totalDr.value > 0 && Math.round((totalDr.value - totalCr.value) * 100) === 0);
const curMap = computed(() => Object.fromEntries(accounts.value.map((a) => [a.name, a.currency])));
const usedCurrencies = computed(() => [...new Set(lines.value.filter((l) => l.account).map((l) => curMap.value[l.account]).filter(Boolean))]);
const mixedCurrency = computed(() => usedCurrencies.value.length > 1);

async function post() {
  error.value = "";
  const clean = lines.value.filter((l) => l.account && ((Number(l.debit) || 0) > 0 || (Number(l.credit) || 0) > 0));
  if (clean.length < 2) { error.value = L("Add at least two complete lines.", "أضف سطرين مكتملين على الأقل.", "Ajoutez au moins deux lignes."); return; }
  posting.value = true;
  try {
    const res = await api.call("accounting_portal.api.accountant.create_journal_entry", {
      company: currentCompany(), posting_date: postingDate.value,
      lines: clean.map((l) => ({ account: l.account, debit: Number(l.debit) || 0, credit: Number(l.credit) || 0 })),
      remark: remark.value,
    });
    emit("posted", res);
    emit("close");
  } catch (e) {
    error.value = (e && e.message) || L("Failed to post.", "فشل الترحيل.", "Échec de la passation.");
  } finally {
    posting.value = false;
  }
}
</script>
