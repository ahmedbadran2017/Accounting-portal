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
          <!-- what is this? a vendor's bill (PI) vs an immediate cash expense (JE) -->
          <div class="flex gap-1 bg-app-warm/60 rounded-chip p-1 w-fit">
            <button type="button" class="px-3 py-1.5 rounded-lg text-[11.5px]" :class="modeType==='bill' ? 'bg-white font-bold text-accent-dark shadow-card' : 'text-ink-3 font-medium'" @click="modeType='bill'">{{ L("Supplier bill", "فاتورة مورّد", "Facture fournisseur") }}</button>
            <button type="button" class="px-3 py-1.5 rounded-lg text-[11.5px]" :class="modeType==='cash' ? 'bg-white font-bold text-accent-dark shadow-card' : 'text-ink-3 font-medium'" @click="modeType='cash'">{{ L("Quick cash expense", "مصروف فوري", "Dépense rapide") }}</button>
          </div>
          <div class="text-[10.5px] text-ink-muted -mt-1.5">
            {{ modeType==='bill'
              ? L("Meta / TikTok ads, freight, clearance… — books a real Purchase Invoice: supplier ledger, aging and partial payments work.", "إعلانات ميتا/تيك توك، شحن، تخليص… — بتتسجل Purchase Invoice حقيقية: كشف المورّد والأعمار والدفع الجزئي شغالين.", "Vraie facture fournisseur.")
              : L("Small immediate spend with no vendor account — books a journal entry.", "مصروف صغير فوري من غير حساب مورّد — قيد يومية.", "Petite dépense immédiate.") }}
          </div>

          <!-- supplier (bill mode) — searchable combobox -->
          <div v-if="modeType==='bill'" class="block">
            <span class="text-[11px] font-semibold text-ink-3">{{ L("Supplier", "المورّد", "Fournisseur") }} <span class="text-sale">*</span></span>
            <div class="relative mt-1" v-click-outside="() => (suppOpen = false)">
              <input v-model="suppQuery" @focus="suppOpen = true" @input="onSuppInput"
                     :placeholder="L('search supplier name…','ابحث باسم المورّد…','rechercher…')"
                     class="w-full border border-line-2 rounded-chip ps-3 pe-8 py-2 text-[12px] focus:outline-none focus:border-accent/40" />
              <span class="absolute top-1/2 -translate-y-1/2 end-3 text-ink-muted pointer-events-none flex"><Icon :name="suppOpen ? 'search' : 'chev'" :size="14" /></span>
              <div v-if="suppOpen" class="absolute z-20 mt-1 w-full max-h-56 overflow-y-auto bg-white border border-line rounded-[12px] shadow-cardHover">
                <button v-for="s in filteredSuppliers" :key="s" type="button"
                        class="w-full flex items-center gap-2 px-3 py-2 text-start hover:bg-app-warm/60 text-[12px]"
                        :class="s === supplier ? 'bg-accent-soft font-semibold' : ''" @click="pickSupplier(s)">
                  <span class="flex-1 truncate">{{ s }}</span>
                  <Icon v-if="s === supplier" name="check" :size="13" color="#047857" class="shrink-0" />
                </button>
                <div v-if="!filteredSuppliers.length" class="px-3 py-4 text-center text-[11.5px] text-ink-muted">{{ L("No supplier matches.","لا مورّد مطابق.","Aucun fournisseur.") }}</div>
              </div>
            </div>
          </div>

          <!-- expense account — single searchable combobox -->
          <div class="block">
            <span class="text-[11px] font-semibold text-ink-3">{{ L("Expense account", "حساب المصروف", "Compte de charge") }}</span>
            <div class="relative mt-1" v-click-outside="() => (acctOpen = false)">
              <input v-model="acctQuery" @focus="acctOpen = true" @input="onAcctInput"
                     :placeholder="L('search by name, number or category…','ابحث بالاسم أو الرقم أو الفئة…','rechercher…')"
                     class="w-full border border-line-2 rounded-chip ps-3 pe-8 py-2 text-[12px] focus:outline-none focus:border-accent/40" />
              <span class="absolute top-1/2 -translate-y-1/2 end-3 text-ink-muted pointer-events-none flex"><Icon :name="acctOpen ? 'search' : 'chev'" :size="14" /></span>
              <div v-if="acctOpen" class="absolute z-20 mt-1 w-full max-h-60 overflow-y-auto bg-white border border-line rounded-[12px] shadow-cardHover">
                <button v-for="a in filteredAccounts" :key="a.name" type="button"
                        class="w-full flex items-center gap-2 px-3 py-2 text-start hover:bg-app-warm/60"
                        :class="a.name === expenseAccount ? 'bg-accent-soft' : ''" @click="pickAccount(a)">
                  <span class="w-1.5 h-1.5 rounded-full shrink-0" :style="`background:${catColor(a.category)}`"></span>
                  <span class="min-w-0 flex-1">
                    <span class="text-[12px] font-semibold truncate block">{{ a.nm }}</span>
                    <span class="text-[10px] text-ink-muted">{{ a.num || "—" }} · {{ a.category }}{{ a.ccy && a.ccy !== opt.currency ? " · " + a.ccy : "" }}</span>
                  </span>
                  <Icon v-if="a.name === expenseAccount" name="check" :size="13" color="#047857" class="shrink-0" />
                </button>
                <div v-if="!filteredAccounts.length" class="px-3 py-4 text-center text-[11.5px] text-ink-muted">{{ L("No account matches.","لا حساب مطابق.","Aucun compte.") }}</div>
              </div>
            </div>
            <div v-if="selectedAccount && !acctOpen" class="mt-1 flex items-center gap-1.5">
              <span class="text-[10px] font-semibold px-1.5 py-0.5 rounded-chip" :style="`background:${catColor(selectedAccount.category)}20;color:${catColor(selectedAccount.category)}`">{{ selectedAccount.category }}</span>
            </div>
          </div>

          <div class="grid grid-cols-3 gap-3">
            <label class="block col-span-2">
              <span class="text-[11px] font-semibold text-ink-3">{{ L("Amount", "المبلغ", "Montant") }}</span>
              <div class="mt-1 flex items-stretch gap-1.5">
                <input type="number" min="0" step="0.01" v-model.number="amount" class="flex-1 min-w-0 border border-line-2 rounded-chip px-3 py-2 text-[13px] tnum font-semibold text-end focus:outline-none focus:border-accent/40" placeholder="0.00" />
                <select v-model="currency" @change="onCurrency" class="w-[74px] border border-line-2 rounded-chip px-1.5 text-[12px] font-semibold focus:outline-none cursor-pointer">
                  <option v-for="c in opt.currencies || [opt.currency]" :key="c" :value="c">{{ c }}</option>
                </select>
              </div>
            </label>
            <label class="block">
              <span class="text-[11px] font-semibold text-ink-3">{{ L("Date", "التاريخ", "Date") }}</span>
              <input type="date" v-model="postingDate" @change="isFx && fetchRate()" class="mt-1 w-full border border-line-2 rounded-chip px-3 py-2 text-[12px] focus:outline-none focus:border-accent/40" />
            </label>
          </div>

          <!-- FX rate when the bill currency differs from the company's -->
          <div v-if="isFx" class="flex items-center gap-2 flex-wrap rounded-[10px] px-3 py-2 text-[11.5px]" style="background:#eff6ff">
            <span class="font-semibold text-sky-800">{{ L("Rate","السعر","Taux") }} 1 {{ currency }} =</span>
            <input type="number" min="0" step="0.0001" v-model.number="fxRate" class="w-[90px] h-7 border border-line-2 rounded-chip px-2 text-[12px] tnum text-end bg-white focus:outline-none" />
            <span class="text-sky-800">{{ opt.currency }}</span>
            <button v-if="rateSuggest" type="button" class="text-[10.5px] text-accent-dark font-semibold hover:underline" @click="fxRate = rateSuggest">{{ L("suggest","اقتراح","suggéré") }} {{ rateSuggest }}</button>
            <span class="ms-auto text-ink-3">≈ <b class="tnum">{{ money(grossBase) }}</b> {{ opt.currency }} {{ L("in the books","في الدفاتر","comptable") }}</span>
          </div>

          <!-- bill mode: supplier bill no + payment status -->
          <div v-if="modeType==='bill'" class="grid grid-cols-2 gap-3">
            <label class="block">
              <span class="text-[11px] font-semibold text-ink-3">{{ L("Supplier bill #", "رقم فاتورة المورّد", "N° facture") }} <span class="text-ink-muted font-normal">({{ L("optional", "اختياري", "opt.") }})</span></span>
              <input v-model.trim="billNo" :placeholder="L('e.g. META-2026-0492','مثال: META-2026-0492','ex. META-0492')" class="mt-1 w-full border border-line-2 rounded-chip px-3 py-2 text-[12px] focus:outline-none focus:border-accent/40" />
            </label>
            <label class="block">
              <span class="text-[11px] font-semibold text-ink-3">{{ L("Payment", "الدفع", "Paiement") }}</span>
              <div class="mt-1"><SearchSelect v-model="payNow" :items="payNowItems" :placeholder="L('Search…','ابحث…','Rechercher…')" :empty-text="L('No account','لا حساب','Aucun')" /></div>
            </label>
          </div>

          <!-- cash mode: pay from -->
          <label v-if="modeType==='cash'" class="block">
            <span class="text-[11px] font-semibold text-ink-3">{{ L("Paid from", "مدفوع من", "Payé depuis") }}</span>
            <div class="mt-1"><SearchSelect v-model="payAccount" :items="payAccountItems" :placeholder="L('Search account…','ابحث عن حساب…','Rechercher…')" :empty-text="L('No account','لا حساب','Aucun')" /></div>
          </label>

          <!-- cash mode: supplier (only meaningful for a payable/credit account) -->
          <label v-if="modeType==='cash' && isPayable" class="block">
            <span class="text-[11px] font-semibold text-ink-3">{{ L("Supplier", "المورّد", "Fournisseur") }} <span class="text-ink-muted font-normal">({{ L("optional", "اختياري", "facultatif") }})</span></span>
            <div class="mt-1"><SearchSelect v-model="party" :items="partyItems" :placeholder="L('Search supplier…','ابحث عن مورّد…','Rechercher…')" :empty-text="L('No supplier','لا مورّد','Aucun')" /></div>
          </label>

          <label class="block">
            <span class="text-[11px] font-semibold text-ink-3">{{ L("Description", "الوصف", "Description") }}</span>
            <input v-model.trim="description" :placeholder="L('e.g. June office rent','مثال: إيجار المكتب يونيو','ex. loyer juin')" class="mt-1 w-full border border-line-2 rounded-chip px-3 py-2 text-[12px] focus:outline-none focus:border-accent/40" />
          </label>

          <!-- VAT (TVA / KDV) -->
          <div class="border border-line rounded-[12px] overflow-hidden">
            <label class="flex items-center gap-2 px-3 py-2.5 cursor-pointer select-none" :class="hasTax ? 'bg-app-warm/50 border-b border-line-hair' : ''">
              <input type="checkbox" v-model="hasTax" class="accent-emerald-700" />
              <span class="text-[11.5px] font-semibold">{{ L("Bill includes VAT (TVA / KDV)", "الفاتورة شاملة ضريبة (TVA / KDV)", "Facture avec TVA") }}</span>
            </label>
            <div v-if="hasTax" class="p-3 space-y-2.5">
              <div class="grid grid-cols-2 gap-3">
                <label class="block">
                  <span class="text-[10.5px] font-semibold text-ink-3">{{ L("Input-VAT account", "حساب ضريبة المدخلات", "Compte TVA déductible") }}</span>
                  <div class="mt-1"><SearchSelect v-model="taxAccount" :items="taxItems" :placeholder="L('Search VAT account…','ابحث…','Rechercher…')" :empty-text="L('No account','لا حساب','Aucun')" /></div>
                </label>
                <label class="block">
                  <span class="text-[10.5px] font-semibold text-ink-3">{{ L("Amount entered is", "المبلغ المدخل فوق", "Montant saisi") }}</span>
                  <select v-model="amountMode" class="mt-1 w-full border border-line-2 rounded-chip px-2.5 py-2 text-[12px] focus:outline-none cursor-pointer">
                    <option value="gross">{{ L("incl. VAT (bill total)", "شامل الضريبة (إجمالي الفاتورة)", "TTC") }}</option>
                    <option value="net">{{ L("excl. VAT (net)", "غير شامل (الصافي)", "HT") }}</option>
                  </select>
                </label>
              </div>
              <div class="flex items-center gap-3 text-[11.5px]">
                <span class="text-ink-3">{{ L("Net", "الصافي", "HT") }} <b class="tnum">{{ money(netAmount) }}</b></span>
                <span class="text-ink-3">{{ L("VAT", "الضريبة", "TVA") }}
                  <input v-model.number="taxOverride" type="number" min="0" step="0.01" :placeholder="String(autoTax)" class="w-[90px] h-7 border border-line-2 rounded-chip px-2 text-[11px] tnum text-end focus:outline-none ms-1" />
                </span>
                <span class="text-ink-3">{{ L("Total", "الإجمالي", "TTC") }} <b class="tnum">{{ money(grossAmount) }}</b></span>
                <span v-if="taxPct" class="text-[10px] text-ink-muted">({{ taxPct }}%)</span>
              </div>
            </div>
          </div>

          <!-- bill attachment -->
          <div class="border border-dashed border-line-2 rounded-[12px] px-3 py-2.5">
            <div v-if="!fileUrl" class="flex items-center gap-2">
              <Icon name="doc" :size="14" color="#9a8f86" />
              <label class="text-[11.5px] font-semibold text-accent-dark cursor-pointer hover:underline">
                {{ uploading ? L("Uploading…","جارٍ الرفع…","…") : L("Attach the bill (PDF / photo)","أرفق الفاتورة (PDF / صورة)","Joindre la facture") }}
                <input type="file" accept=".pdf,.png,.jpg,.jpeg,.webp,.heic" class="hidden" @change="onFile" :disabled="uploading" />
              </label>
              <span class="text-[10px] text-ink-muted">{{ L("attached to the journal entry","بتتعلق على القيد نفسه","liée à l'écriture") }}</span>
            </div>
            <div v-else class="flex items-center gap-2">
              <Icon name="check" :size="14" color="#047857" />
              <span class="text-[11.5px] font-medium truncate flex-1">{{ fileName }}</span>
              <button type="button" class="text-[11px] text-rose-500 hover:underline" @click="fileUrl=''; fileName=''">{{ L("remove","إزالة","retirer") }}</button>
            </div>
          </div>

          <!-- live double-entry preview -->
          <div v-if="canPreview" class="border border-line rounded-[12px] overflow-hidden text-[11.5px]">
            <div class="px-3 py-1.5 bg-app-warm/50 text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Journal preview", "معاينة القيد", "Aperçu de l'écriture") }}</div>
            <div class="flex items-center justify-between px-3 py-2 border-t border-line-hair">
              <span class="truncate">{{ L("Dr", "مدين", "Dr") }} · {{ shortAcct(expenseAccount) }}</span>
              <span class="tnum font-bold text-teal-700">{{ money(netAmount) }}</span>
            </div>
            <div v-if="hasTax && taxValue > 0" class="flex items-center justify-between px-3 py-2 border-t border-line-hair">
              <span class="truncate">{{ L("Dr", "مدين", "Dr") }} · {{ shortAcct(taxAccount) || L("VAT", "الضريبة", "TVA") }}</span>
              <span class="tnum font-bold text-teal-700">{{ money(taxValue) }}</span>
            </div>
            <div class="flex items-center justify-between px-3 py-2 border-t border-line-hair">
              <span class="truncate" v-if="modeType==='bill'">{{ L("Cr", "دائن", "Cr") }} · {{ payNow ? shortAcct(payNow) : L("Creditors", "ذمم الموردين", "Fournisseurs") + " · " + supplier }}</span>
              <span class="truncate" v-else>{{ L("Cr", "دائن", "Cr") }} · {{ shortAcct(payAccount) }}{{ party ? " · " + party : "" }}</span>
              <span class="tnum font-bold text-rose-600">{{ money(grossAmount) }}</span>
            </div>
          </div>

          <div v-if="currencyWarn" class="text-[11px] text-amber-700 inline-flex items-center gap-1.5"><Icon name="alert" :size="13" />{{ L("Expense and pay accounts use different currencies — post this one in ERPNext.", "حساب المصروف والدفع بعملتين مختلفتين — رحّله من ERPNext.", "Devises différentes — passez-la dans ERPNext.") }}</div>
          <div v-else-if="grossBase >= opt.threshold" class="text-[11px] text-amber-700 inline-flex items-center gap-1.5"><Icon name="shield" :size="12" />{{ L("Material amount — needs an approver before it posts.", "مبلغ جوهري — يحتاج موافقة قبل الترحيل.", "Montant important — approbation requise.") }}</div>
          <div v-if="error" class="text-[11.5px] text-sale">{{ error }}</div>
        </div>

        <div class="flex items-center justify-end gap-2 px-5 py-3.5 border-t border-line bg-app-warm/40">
          <button class="px-3.5 py-2 rounded-chip text-[12px] font-semibold text-ink-2 hover:bg-white" @click="$emit('close')">{{ L("Cancel", "إلغاء", "Annuler") }}</button>
          <button class="px-4 py-2 rounded-chip text-[12px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand disabled:opacity-50" :disabled="!canSubmit || posting || uploading" @click="submit">
            {{ posting ? L("Saving…", "جارٍ الحفظ…", "…") : grossBase >= opt.threshold ? L("Submit for approval", "إرسال للموافقة", "Soumettre") : L("Record expense", "تسجيل المصروف", "Enregistrer") }}
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
import SearchSelect from "@/components/SearchSelect.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";
import { fmtMoney, getCsrfToken, newClientKey } from "@/utils/helpers";

const props = defineProps({ prefill: { type: Object, default: null } });
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
const acctQuery = ref("");
const acctOpen = ref(false);
const expenseAccount = ref("");
const amount = ref(null);
const postingDate = ref(new Date().toISOString().slice(0, 10));
const payAccount = ref("");
const party = ref("");
const description = ref("");
const clientKey = newClientKey();
const posting = ref(false);
const error = ref("");

// multi-currency: bill entered in `currency`, converted to base for the books
const currency = ref("");
const fxRate = ref(1);
const rateSuggest = ref(0);
const isFx = computed(() => currency.value && currency.value !== opt.value.currency);
async function fetchRate() {
  if (!isFx.value) { rateSuggest.value = 0; return; }
  try {
    const r = await api.call("accounting_portal.api.expenses.exchange_rate",
      { company: currentCompany(), from_currency: currency.value, date: postingDate.value });
    rateSuggest.value = Number(r?.rate) || 0;
    if (rateSuggest.value > 0) fxRate.value = rateSuggest.value;
  } catch { rateSuggest.value = 0; }
}
function onCurrency() { if (isFx.value) fetchRate(); else fxRate.value = 1; }
const effRate = computed(() => (isFx.value ? Number(fxRate.value) || 0 : 1));

// bill (Purchase Invoice) vs quick cash expense (Journal Entry)
const modeType = ref("bill");
const supplier = ref("");
const suppQuery = ref("");
const suppOpen = ref(false);
const filteredSuppliers = computed(() => {
  const list = opt.value.suppliers || [];
  const q = suppQuery.value.trim().toLowerCase();
  // Empty query, or the query still equals the picked supplier → show all.
  if (!q || q === supplier.value.toLowerCase()) return list.slice(0, 300);
  return list.filter((s) => s.toLowerCase().includes(q)).slice(0, 300);
});
function onSuppInput() { suppOpen.value = true; if (supplier.value) supplier.value = ""; }
function pickSupplier(s) { supplier.value = s; suppQuery.value = s; suppOpen.value = false; }
const billNo = ref("");
const payNow = ref(""); // "" = unpaid → To Pay; else the Bank/Cash account it was paid from
const cashBankAccounts = computed(() => (opt.value.pay_accounts || []).filter((a) => a.typ !== "Payable"));

// VAT (TVA / KDV)
const hasTax = ref(false);
const taxAccount = ref("");
const amountMode = ref("gross"); // what the user typed in Amount: bill total or net
const taxOverride = ref(null);   // manual tax when the split isn't a clean %

const taxPct = computed(() => {
  const v = (opt.value.vat_accounts || []).find((x) => x.name === taxAccount.value);
  return v && v.pct ? Number(v.pct) : 0;
});
const autoTax = computed(() => {
  const a = Number(amount.value) || 0;
  if (!hasTax.value || !a || !taxPct.value) return 0;
  const r = taxPct.value / 100;
  return +(amountMode.value === "gross" ? a - a / (1 + r) : a * r).toFixed(2);
});
const taxValue = computed(() => (hasTax.value ? (Number(taxOverride.value) > 0 ? +Number(taxOverride.value).toFixed(2) : autoTax.value) : 0));
const netAmount = computed(() => {
  const a = Number(amount.value) || 0;
  if (!hasTax.value) return a;
  return +(amountMode.value === "gross" ? a - taxValue.value : a).toFixed(2);
});
const grossAmount = computed(() => +(netAmount.value + taxValue.value).toFixed(2));
const grossBase = computed(() => +(grossAmount.value * effRate.value).toFixed(2));

// bill attachment
const fileUrl = ref(""), fileName = ref(""), uploading = ref(false);
async function onFile(e) {
  const f = e.target.files[0];
  if (!f) return;
  uploading.value = true; error.value = "";
  try {
    const fd = new FormData();
    fd.append("file", f); fd.append("is_private", 1); fd.append("folder", "Home");
    const res = await fetch("/api/method/upload_file", { method: "POST", headers: { "X-Frappe-CSRF-Token": getCsrfToken() }, body: fd });
    const body = await res.json();
    if (!res.ok) throw new Error("Upload failed");
    fileUrl.value = body.message.file_url;
    fileName.value = f.name;
  } catch (err) { error.value = String(err?.message || err).slice(0, 160); }
  finally { uploading.value = false; e.target.value = ""; }
}

onMounted(async () => {
  try {
    opt.value = await api.call("accounting_portal.api.expenses.expense_form_options", { company: currentCompany() }) || opt.value;
    payAccount.value = opt.value.default_pay || (opt.value.pay_accounts[0] && opt.value.pay_accounts[0].name) || "";
    currency.value = opt.value.currency;
    // Prefill from a recurring expense (supplier · account · typical amount).
    const p = props.prefill;
    if (p) {
      if (p.expense_account) {
        expenseAccount.value = p.expense_account;
        const a = (opt.value.expense_accounts || []).find((x) => x.name === p.expense_account);
        if (a) acctQuery.value = acctLabel(a);
      }
      if (p.amount) amount.value = Number(p.amount);
      if (p.description) description.value = p.description;
      if (p.posting_date) postingDate.value = String(p.posting_date).slice(0, 10);
      // Explicit mode from Duplicate (bill vs cash); otherwise a party implies bill.
      if (p.mode === "cash" || p.mode === "bill") modeType.value = p.mode;
      // Bank-workbench prefill: the line's bank account pays in both modes.
      if (p.pay_account && (opt.value.pay_accounts || []).some((a) => a.name === p.pay_account)) payAccount.value = p.pay_account;
      if (p.paid_from && (opt.value.pay_accounts || []).some((a) => a.name === p.paid_from && a.typ !== "Payable")) payNow.value = p.paid_from;
      // Duplicate carrying VAT — re-open the tax section pre-filled.
      if (p.tax_amount && p.tax_account) {
        hasTax.value = true;
        taxAccount.value = p.tax_account;
        amountMode.value = "net";       // amount above is the net expense
        taxOverride.value = Number(p.tax_amount);
      }
      // A recurring vendor (Meta / TikTok / carrier…) lands straight in
      // supplier-bill mode with the supplier picked; party kept for cash mode.
      if (p.party) {
        if (p.mode !== "cash") modeType.value = "bill";
        if (!(opt.value.suppliers || []).includes(p.party)) (opt.value.suppliers = opt.value.suppliers || []).unshift(p.party);
        supplier.value = p.party;
        suppQuery.value = p.party;
        party.value = p.party;
      }
    }
  } catch (e) { error.value = (e && e.message) || "Failed to load"; }
  finally { optLoad.value = false; }
});

const acctLabel = (a) => (a.num ? a.num + " · " : "") + a.nm;
const selectedAccount = computed(() => (opt.value.expense_accounts || []).find((a) => a.name === expenseAccount.value) || null);
const filteredAccounts = computed(() => {
  const list = opt.value.expense_accounts || [];
  const q = acctQuery.value.trim().toLowerCase();
  // When the query is empty, or still shows the picked account's label, show all.
  if (!q || (selectedAccount.value && q === acctLabel(selectedAccount.value).toLowerCase())) return list.slice(0, 500);
  return list.filter((a) => (a.num || "").toLowerCase().includes(q) || (a.nm || "").toLowerCase().includes(q) || (a.category || "").toLowerCase().includes(q)).slice(0, 500);
});
function onAcctInput() { acctOpen.value = true; if (expenseAccount.value) expenseAccount.value = ""; }
function pickAccount(a) { expenseAccount.value = a.name; acctQuery.value = acctLabel(a); acctOpen.value = false; }
const payMap = computed(() => Object.fromEntries((opt.value.pay_accounts || []).map((a) => [a.name, a])));
const isPayable = computed(() => payMap.value[payAccount.value]?.typ === "Payable");
const canPreview = computed(() =>
  expenseAccount.value && Number(amount.value) > 0 &&
  (modeType.value === "bill" ? !!supplier.value : !!payAccount.value));
const currencyWarn = computed(() => {
  if (modeType.value === "bill") return false; // PI handles its own currency
  const ea = selectedAccount.value, pa = payMap.value[payAccount.value];
  const eccy = (ea && ea.ccy) || opt.value.currency;
  const pccy = (pa && pa.ccy) || opt.value.currency;
  return ea && pa && eccy !== pccy;
});
const canSubmit = computed(() =>
  expenseAccount.value && Number(amount.value) > 0 &&
  (!hasTax.value || (taxAccount.value && netAmount.value > 0)) &&
  (!isFx.value || effRate.value > 0) &&
  (modeType.value === "bill"
    ? !!supplier.value
    : (payAccount.value && !currencyWarn.value)));

function payLabel(a) {
  const t = a.typ === "Bank" ? L("Bank", "بنك", "Banque") : a.typ === "Cash" ? L("Cash", "نقدية", "Caisse") : L("Payable", "ذمم دائنة", "À payer");
  return `${a.nm} · ${t}`;
}
function shortAcct(name) { const a = (opt.value.expense_accounts || []).concat(opt.value.pay_accounts || []).find((x) => x.name === name); return a ? (a.num ? a.num + " " : "") + a.nm : name; }

// Searchable-picker option lists (keep the empty sentinels the selects had).
const payNowItems = computed(() => [{ value: "", label: L("Not paid yet → To Pay", "لسه ماتدفعتش ← To Pay", "Impayée → À payer") }, ...cashBankAccounts.value.map((a) => ({ value: a.name, label: a.nm, sub: a.num || "" }))]);
const payAccountItems = computed(() => (opt.value.pay_accounts || []).map((a) => ({ value: a.name, label: payLabel(a), sub: a.num || "" })));
const partyItems = computed(() => [{ value: "", label: "—" }, ...(opt.value.suppliers || []).map((s) => ({ value: s, label: s }))]);
const taxItems = computed(() => [{ value: "", label: "—" }, ...(opt.value.vat_accounts || []).map((v) => ({ value: v.name, label: v.nm, sub: v.num || "" }))]);

async function submit() {
  error.value = "";
  if (!canSubmit.value) return;
  posting.value = true;
  try {
    const common = {
      company: currentCompany(), client_key: clientKey, expense_account: expenseAccount.value,
      amount: netAmount.value, posting_date: postingDate.value,
      description: description.value || undefined,
      tax_amount: taxValue.value || undefined,
      tax_account: (hasTax.value && taxAccount.value) || undefined,
      attachment: fileUrl.value || undefined,
      attachment_name: fileName.value || undefined,
      currency: isFx.value ? currency.value : undefined,
      exchange_rate: isFx.value ? effRate.value : undefined,
    };
    const res = modeType.value === "bill"
      ? await api.call("accounting_portal.api.expenses.create_supplier_bill", {
          ...common, supplier: supplier.value, bill_no: billNo.value || undefined,
          paid_from: payNow.value || undefined,
        })
      : await api.call("accounting_portal.api.expenses.create_expense", {
          ...common, pay_account: payAccount.value,
          party: (isPayable.value && party.value) || undefined,
        });
    emit("posted", res);
    emit("close");
  } catch (e) {
    error.value = (e && e.message) || L("Failed to save.", "فشل الحفظ.", "Échec.");
  } finally { posting.value = false; }
}
</script>
