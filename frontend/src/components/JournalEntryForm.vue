<template>
  <div class="fixed inset-0 z-[100] flex items-start justify-center p-4 sm:p-8 overflow-y-auto" style="background:rgba(28,25,23,.45)" @click.self="$emit('close')">
    <div class="bg-white rounded-[18px] shadow-cardHover w-full max-w-2xl my-6 overflow-hidden">
      <div class="flex items-center gap-2.5 px-5 py-4 border-b border-line">
        <span class="w-8 h-8 rounded-[10px] grid place-items-center" style="background:#f5f3ff"><Icon name="ledger" :size="16" color="#7c3aed" /></span>
        <div class="flex-1 min-w-0">
          <div class="text-[14px] font-bold">{{ opening ? L("New opening entry", "قيد افتتاحي جديد", "Nouvelle écriture d'ouverture") : L("New journal entry", "قيد يومية جديد", "Nouvelle écriture") }}</div>
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
                  <div class="relative" v-click-outside="() => { if (openLine === i) openLine = null }">
                    <input v-model="ln.q" @focus="openLine = i" @input="openLine = i; ln.account = ''"
                           :placeholder="L('search account…','ابحث عن حساب…','rechercher…')"
                           class="w-full bg-transparent text-[12px] py-1 focus:outline-none"
                           :class="ln.account ? 'text-ink font-medium' : 'text-ink-2'" />
                    <div v-if="openLine === i" class="absolute z-30 mt-1 w-[280px] max-h-56 overflow-y-auto bg-white border border-line rounded-[12px] shadow-cardHover">
                      <button v-for="a in filteredFor(ln)" :key="a.name" type="button"
                              class="w-full flex items-center gap-2 px-3 py-1.5 text-start hover:bg-app-warm/60 text-[12px] border-t border-line-hair first:border-t-0"
                              :class="a.name === ln.account ? 'bg-accent-soft font-semibold' : ''" @click="pick(ln, a)">
                        <span class="flex-1 truncate">{{ a.name }}</span>
                        <span v-if="a.currency" class="text-[9.5px] text-ink-muted shrink-0">{{ a.currency }}</span>
                      </button>
                      <div v-if="!filteredFor(ln).length" class="px-3 py-3 text-center text-[11px] text-ink-muted">{{ L("No account matches.","لا حساب مطابق.","Aucun.") }}</div>
                    </div>
                  </div>
                  <!-- party: required for Receivable/Payable, optional otherwise -->
                  <div v-if="ln.account && (needsParty(ln) || ln.showParty)" class="mt-1 flex items-center gap-1.5">
                    <select v-model="ln.party_type" class="text-[10.5px] bg-app-warm/50 border border-line-2 rounded-chip px-1.5 py-0.5 focus:outline-none" @change="ln.party = ''; ln.pq = ''">
                      <option value="">{{ L("type","النوع","type") }}</option>
                      <option value="Customer">{{ L("Customer","عميل","Client") }}</option>
                      <option value="Supplier">{{ L("Supplier","مورّد","Fourn.") }}</option>
                      <option value="Employee">{{ L("Employee","موظف","Employé") }}</option>
                    </select>
                    <div v-if="ln.party_type" class="relative flex-1" v-click-outside="() => { if (openParty === i) openParty = null }">
                      <input v-model="ln.pq" @focus="openParty = i; loadParties(ln)" @input="openParty = i; ln.party = ''; loadParties(ln)"
                             :placeholder="L('search party…','ابحث عن الطرف…','tiers…')"
                             class="w-full text-[10.5px] bg-app-warm/50 border rounded-chip px-2 py-0.5 focus:outline-none"
                             :class="needsParty(ln) && !ln.party ? 'border-rose-300' : 'border-line-2'" />
                      <div v-if="openParty === i && (ln._parties || []).length" class="absolute z-40 mt-1 w-[240px] max-h-44 overflow-y-auto bg-white border border-line rounded-[10px] shadow-cardHover">
                        <button v-for="pt in ln._parties" :key="pt.name" type="button" class="w-full text-start px-2.5 py-1.5 hover:bg-app-warm/60 text-[11px] border-t border-line-hair first:border-t-0" @click="pickParty(ln, pt)">
                          <span class="font-medium">{{ pt.label || pt.name }}</span><span v-if="pt.label && pt.label !== pt.name" class="text-[9px] text-ink-muted ms-1">{{ pt.name }}</span>
                        </button>
                      </div>
                    </div>
                    <button v-if="!needsParty(ln)" type="button" class="text-ink-muted hover:text-sale" @click="ln.showParty = false; ln.party_type = ''; ln.party = ''"><Icon name="close" :size="11" /></button>
                  </div>
                  <button v-else-if="ln.account && !needsParty(ln)" type="button" class="mt-0.5 text-[9.5px] text-ink-muted hover:text-accent-dark" @click="ln.showParty = true">+ {{ L("party","طرف","tiers") }}</button>
                </td>
                <td class="px-2 py-1.5"><input type="number" min="0" v-model.number="ln.debit" class="w-full text-end tnum bg-transparent py-1 focus:outline-none" placeholder="0" /></td>
                <td class="px-2 py-1.5"><input type="number" min="0" v-model.number="ln.credit" class="w-full text-end tnum bg-transparent py-1 focus:outline-none" placeholder="0" /></td>
                <td class="px-2 text-center"><button v-if="lines.length > 2" class="text-ink-muted hover:text-sale" @click="lines.splice(i, 1)"><Icon name="close" :size="13" /></button></td>
              </tr>
            </tbody>
            <tfoot>
              <tr class="border-t border-line-2" style="background:#fafaf9">
                <td class="px-3 py-2"><button class="text-[11px] font-semibold text-accent hover:text-accent-dark inline-flex items-center gap-1" @click="lines.push(newLine())"><Icon name="plus" :size="12" />{{ L("Add line", "سطر", "Ligne") }}</button></td>
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

        <label v-if="!opening" class="flex items-center gap-2 text-[11.5px] text-ink-3 cursor-pointer select-none">
          <input type="checkbox" v-model="autoReverse" class="accent-emerald-700" />
          {{ L("Auto-reverse on the 1st of next month (accrual / prepaid)", "عكس تلقائي أول الشهر الجاي (استحقاق / مقدَّم)", "Contre-passer le 1er du mois suivant") }}
        </label>
        <div v-if="mixedCurrency" class="text-[11.5px] text-sale inline-flex items-center gap-1.5"><Icon name="alert" :size="13" />{{ L("Mixed currencies (" + usedCurrencies.join(", ") + ") — use one currency per entry", "عملات مختلطة (" + usedCurrencies.join("، ") + ") — استخدم عملة واحدة للقيد", "Devises mixtes — une seule par écriture") }}</div>
        <div v-if="error" class="text-[11.5px] text-sale">{{ error }}</div>
      </div>

      <div class="flex items-center justify-end gap-2 px-5 py-3.5 border-t border-line bg-app-warm/40">
        <button class="px-3.5 py-2 rounded-chip text-[12px] font-semibold text-ink-2 hover:bg-white" @click="$emit('close')">{{ L("Cancel", "إلغاء", "Annuler") }}</button>
        <button v-if="!opening" class="px-3.5 py-2 rounded-chip text-[12px] font-semibold text-accent-dark border border-line-2 hover:bg-white disabled:opacity-50" :disabled="!hasAnyLine || posting" @click="post(true)" :title="L('Save unsubmitted — finish later from Journals','احفظ بدون ترحيل — كمّله لاحقًا من القيود','Enregistrer en brouillon')">
          {{ posting === 'draft' ? L("Saving…","جارٍ…","…") : L("Save draft", "حفظ مسودة", "Brouillon") }}
        </button>
        <button class="px-4 py-2 rounded-chip text-[12px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand disabled:opacity-50" :disabled="!balanced || mixedCurrency || posting" @click="post(false)">
          {{ posting === 'post' ? L("Posting…", "جارٍ…", "…") : L("Post entry", "ترحيل القيد", "Passer") }}
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
import { newClientKey } from "@/utils/helpers";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";

const props = defineProps({ opening: { type: Boolean, default: false } });
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

const clientKey = newClientKey();
const autoReverse = ref(false);
const postingDate = ref(new Date().toISOString().slice(0, 10));
const remark = ref("");
const newLine = () => ({ account: "", q: "", debit: null, credit: null, party_type: "", party: "", pq: "", showParty: false, _parties: [] });
const lines = ref([newLine(), newLine()]);
const accounts = ref([]);
const posting = ref(false);
const error = ref("");
const openLine = ref(null);
const openParty = ref(null);

// Searchable account picker per line. With thousands of accounts a plain
// <select> is unusable — filter by name/number as the user types.
function filteredFor(ln) {
  const q = (ln.q || "").trim().toLowerCase();
  if (!q || q === ln.account.toLowerCase()) return accounts.value.slice(0, 80);
  return accounts.value.filter((a) => a.name.toLowerCase().includes(q)).slice(0, 80);
}
const typeMap = computed(() => Object.fromEntries(accounts.value.map((a) => [a.name, a.type])));
// Receivable/Payable accounts require a party in ERPNext — auto-set its type.
function needsParty(ln) { return ["Receivable", "Payable"].includes(typeMap.value[ln.account]); }
function pick(ln, a) {
  ln.account = a.name; ln.q = a.name; openLine.value = null;
  if (a.type === "Receivable" && !ln.party_type) ln.party_type = "Customer";
  else if (a.type === "Payable" && !ln.party_type) ln.party_type = "Supplier";
}
let ptTimer = null;
function loadParties(ln) {
  clearTimeout(ptTimer);
  ptTimer = setTimeout(async () => {
    if (!ln.party_type) { ln._parties = []; return; }
    try {
      ln._parties = await api.call("accounting_portal.api.accountant.party_options",
        { party_type: ln.party_type, q: ln.pq || undefined }) || [];
    } catch { ln._parties = []; }
  }, 250);
}
function pickParty(ln, pt) { ln.party = pt.name; ln.pq = pt.label || pt.name; openParty.value = null; }

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
const hasAnyLine = computed(() => lines.value.some((l) => l.account && ((Number(l.debit) || 0) > 0 || (Number(l.credit) || 0) > 0)));

async function post(draft = false) {
  error.value = "";
  const clean = lines.value.filter((l) => l.account && ((Number(l.debit) || 0) > 0 || (Number(l.credit) || 0) > 0));
  if (draft) {
    if (!clean.length) { error.value = L("Nothing to save yet.", "لا شيء لحفظه.", "Rien à enregistrer."); return; }
  } else {
    if (clean.length < 2) { error.value = L("Add at least two complete lines.", "أضف سطرين مكتملين على الأقل.", "Ajoutez au moins deux lignes."); return; }
    const missingParty = clean.find((l) => needsParty(l) && !l.party);
    if (missingParty) { error.value = L(`${missingParty.account} needs a party.`, `${missingParty.account} يحتاج طرفًا.`, "Tiers requis."); return; }
  }
  posting.value = draft ? "draft" : "post";
  try {
    const method = props.opening ? "create_opening_entry" : "create_journal_entry";
    const res = await api.call(`accounting_portal.api.accountant.${method}`, {
      company: currentCompany(), client_key: clientKey, posting_date: postingDate.value, draft: (draft && !props.opening) ? 1 : undefined, auto_reverse: (autoReverse.value && !props.opening && !draft) ? 1 : undefined,
      lines: clean.map((l) => ({ account: l.account, debit: Number(l.debit) || 0, credit: Number(l.credit) || 0,
        party_type: (l.party && l.party_type) || undefined, party: l.party || undefined })),
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
