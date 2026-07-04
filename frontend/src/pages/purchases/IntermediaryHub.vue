<template>
  <div class="space-y-3.5">
    <div class="flex items-center gap-2 flex-wrap">
      <span class="text-[11px] text-ink-muted">{{ L("Pay a foreign supplier via a Moroccan intermediary — funded in MAD, settled in the supplier's currency.", "ادفع لمورّد أجنبي عبر وسيط مغربي — تموّله بالدرهم، ويسدّد بعملة المورّد.", "Payer un fournisseur étranger via un intermédiaire.") }}</span>
      <button v-if="canWrite" type="button" class="ms-auto inline-flex items-center gap-1.5 h-9 px-3.5 rounded-chip text-[12.5px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand" @click="openFund()">
        <Icon name="plus" :size="14" />{{ L("Fund intermediary", "تمويل وسيط", "Financer") }}
      </button>
    </div>

    <!-- intermediary balances -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
      <div v-for="a in d.accounts" :key="a.name" class="bg-white rounded-card border shadow-card px-4 py-3.5" :class="a.flag==='negative' ? 'border-rose-200' : a.flag==='cash_type' ? 'border-amber-200' : 'border-line'">
        <div class="flex items-center gap-2">
          <span class="text-[12px] font-bold truncate flex-1">{{ a.nm }}</span>
          <span class="text-[9px] font-mono text-ink-muted">{{ a.num }}</span>
        </div>
        <div class="text-[20px] font-extrabold tnum mt-1.5" :class="a.bal < 0 ? 'text-rose-600' : ''">{{ money(a.bal) }} <span class="text-[10px] text-ink-muted">{{ ccy }}</span></div>
        <div class="text-[10.5px] text-ink-muted mt-0.5"><span class="text-teal-700">+{{ money(a.funded) }}</span> {{ L("funded","مُموّل","financé") }} · <span class="text-rose-500">−{{ money(a.settled) }}</span> {{ L("settled","سُدّد","réglé") }} · {{ a.n }} {{ L("txn","حركة","écr.") }}</div>
        <div v-if="a.flag==='negative'" class="mt-1.5 text-[10px] font-semibold text-rose-600 inline-flex items-center gap-1"><Icon name="alert" :size="11" />{{ L("Negative — payments booked without funding/clearing","سالب — دفعات بدون تمويل/تقفيل","Négatif") }}</div>
        <div v-else-if="a.flag==='cash_type'" class="mt-1.5 text-[10px] font-semibold text-amber-700 inline-flex items-center gap-1"><Icon name="alert" :size="11" />{{ L("Typed Bank/Cash — should be a receivable","مصنّف بنك/كاش — المفروض ذمم مدينة","Type banque") }}</div>
      </div>
      <div v-if="!loading && !d.accounts.length" class="text-[12px] text-ink-muted py-6 col-span-full">{{ L("No intermediary accounts found.","لا حسابات وسطاء.","Aucun.") }}</div>
    </div>

    <!-- open foreign-currency bills to settle -->
    <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
      <div class="px-4 py-2.5 border-b border-line-hair text-[12px] font-bold flex items-center gap-2">
        <Icon name="cart" :size="14" color="#0b5c4f" />{{ L("Open foreign-currency bills","فواتير مفتوحة بعملة أجنبية","Factures en devise") }}
        <span class="text-[10px] text-ink-muted">{{ opt.bills ? opt.bills.length : 0 }}</span>
      </div>
      <TableLoading v-if="loading" :rows="6" />
      <div v-else class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead><tr style="background:#fafaf9" class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">
            <th class="px-4 py-2 text-start">{{ L("Bill","الفاتورة","Facture") }}</th>
            <th class="px-3 py-2 text-start">{{ L("Supplier","المورّد","Fournisseur") }}</th>
            <th class="px-3 py-2 text-start">{{ L("Date","التاريخ","Date") }}</th>
            <th class="px-4 py-2 text-end">{{ L("Outstanding","المتبقّي","Restant") }}</th>
            <th class="px-4 py-2 text-end">{{ L("Settle","سدّد","Régler") }}</th>
          </tr></thead>
          <tbody>
            <tr v-for="b in (opt.bills || [])" :key="b.name" class="border-t border-line-hair hover:bg-app-warm/40">
              <td class="px-4 py-2.5 font-mono text-[11px]">{{ b.name }}</td>
              <td class="px-3 py-2.5 truncate max-w-[200px]">{{ b.supplier_name }}</td>
              <td class="px-3 py-2.5 text-ink-3 whitespace-nowrap">{{ b.posting_date }}</td>
              <td class="px-4 py-2.5 text-end tnum font-semibold">{{ money(b.outstanding_amount) }} <span class="text-[9px] text-ink-muted">{{ b.currency }}</span></td>
              <td class="px-4 py-2.5 text-end whitespace-nowrap">
                <div v-if="canWrite" class="inline-flex items-center gap-1.5">
                  <select v-model="settleWith[b.name]" class="h-7 bg-app-warm/40 border border-line-2 rounded-chip px-2 text-[11px] focus:outline-none max-w-[150px]">
                    <option value="">{{ L("via…","عبر…","via…") }}</option>
                    <option v-for="i in opt.intermediaries || []" :key="i.name" :value="i.name">{{ i.nm }}</option>
                  </select>
                  <button type="button" :disabled="!settleWith[b.name] || busy===b.name" class="h-7 px-2.5 rounded-chip text-[11px] font-bold text-white bg-emerald-600 hover:bg-emerald-700 disabled:opacity-40" @click="settle(b)">{{ busy===b.name ? '…' : L('Settle','سدّد','Régler') }}</button>
                </div>
              </td>
            </tr>
            <tr v-if="!(opt.bills||[]).length"><td colspan="5" class="px-4 py-8 text-center text-ink-muted">{{ L("No open foreign-currency bills.","لا فواتير مفتوحة بعملة أجنبية.","Aucune.") }}</td></tr>
          </tbody>
        </table>
      </div>
      <div class="px-4 py-2 border-t border-line-hair text-[10.5px] text-ink-muted flex items-center gap-1.5">
        <Icon name="alert" :size="11" color="#9a8f86" />{{ L("Settling pays the bill FROM the intermediary account — ERPNext books the FX gain/loss. Audited & reversible.","التسديد بيدفع الفاتورة من حساب الوسيط — ERPNext بيحسب فرق العملة. مدقّق وقابل للتراجع.","Réversible & audité.") }}
      </div>
    </div>

    <!-- fund modal -->
    <div v-if="funding" class="fixed inset-0 z-[100] flex items-start justify-center p-4 sm:p-8 overflow-y-auto" style="background:rgba(28,25,23,.45)" @click.self="funding=false">
      <div class="bg-white rounded-[18px] shadow-cardHover w-full max-w-md my-8 overflow-hidden">
        <div class="flex items-center gap-2.5 px-5 py-4 border-b border-line">
          <span class="w-8 h-8 rounded-[10px] grid place-items-center" style="background:#eff6ff"><Icon name="bank" :size="16" color="#0369a1" /></span>
          <div class="flex-1"><div class="text-[14px] font-bold">{{ L("Fund intermediary","تمويل وسيط","Financer") }}</div><div class="text-[11px] text-ink-muted">{{ L("bank → intermediary (MAD)","بنك ← وسيط (درهم)","banque → intermédiaire") }}</div></div>
          <button class="text-ink-3 hover:text-ink" @click="funding=false"><Icon name="close" :size="18" /></button>
        </div>
        <div class="p-5 space-y-3.5">
          <label class="block">
            <span class="text-[11px] font-semibold text-ink-3 flex items-center">{{ L("Intermediary","الوسيط","Intermédiaire") }}
              <button type="button" class="ms-auto text-[10.5px] font-bold text-brand hover:underline" @click="creating = !creating">{{ creating ? L("Pick existing","اختر موجود","Choisir") : L("+ New intermediary","+ وسيط جديد","+ Nouveau") }}</button></span>
            <select v-if="!creating" v-model="fund.intermediary" class="mt-1 w-full border border-line-2 rounded-chip px-3 py-2 text-[12px] focus:outline-none"><option value="">—</option><option v-for="i in opt.intermediaries || []" :key="i.name" :value="i.name">{{ i.nm }}</option></select>
          </label>
          <div v-if="creating" class="rounded-[12px] border border-line-2 bg-app-warm/40 p-3 space-y-2.5">
            <div class="text-[10.5px] text-ink-muted">{{ L("One clean account per intermediary — created under “Due From Intermediaries” and reused for every transfer.","حساب واحد نضيف لكل وسيط — بيتعمل تحت «Due From Intermediaries» ويتعاد استخدامه في كل تحويلة.","Un compte propre par intermédiaire, réutilisé.") }}</div>
            <div class="flex items-center gap-2">
              <input v-model.trim="newAcct.name" class="flex-1 border border-line-2 rounded-chip px-3 py-2 text-[12px] bg-white focus:outline-none" :placeholder="L('e.g. Due from Hassan Exchange','مثال: Due from Hassan Exchange','ex. Due from Hassan')" @keyup.enter="doCreateAcct" />
              <select v-model="newAcct.currency" class="w-[76px] border border-line-2 rounded-chip px-2 py-2 text-[12px] bg-white focus:outline-none">
                <option v-for="c in ['MAD','USD','TRY','EUR']" :key="c" :value="c">{{ c }}</option>
              </select>
              <button type="button" class="h-[34px] px-3 rounded-chip text-[11.5px] font-bold text-white bg-brand hover:bg-brand-dark disabled:opacity-50" :disabled="!newAcct.name || acctBusy" @click="doCreateAcct">{{ acctBusy ? '…' : L("Create","إنشاء","Créer") }}</button>
            </div>
            <div v-if="acctErr" class="text-[11px] text-sale">{{ acctErr }}</div>
          </div>
          <label class="block"><span class="text-[11px] font-semibold text-ink-3">{{ L("From bank","من بنك","Banque") }}</span>
            <select v-model="fund.bank" class="mt-1 w-full border border-line-2 rounded-chip px-3 py-2 text-[12px] focus:outline-none"><option value="">—</option><option v-for="b in opt.banks || []" :key="b.name" :value="b.name">{{ b.nm }}</option></select></label>
          <div class="grid grid-cols-2 gap-3">
            <label class="block"><span class="text-[11px] font-semibold text-ink-3">{{ L("Amount","المبلغ","Montant") }} ({{ ccy }})</span><input type="number" min="0" step="0.01" v-model.number="fund.amount" class="mt-1 w-full border border-line-2 rounded-chip px-3 py-2 text-[13px] tnum text-end font-semibold focus:outline-none" placeholder="0.00" /></label>
            <label class="block"><span class="text-[11px] font-semibold text-ink-3">{{ L("Date","التاريخ","Date") }}</span><input type="date" v-model="fund.date" class="mt-1 w-full border border-line-2 rounded-chip px-3 py-2 text-[12px] focus:outline-none" /></label>
          </div>
          <div v-if="fundErr" class="text-[11.5px] text-sale">{{ fundErr }}</div>
        </div>
        <div class="flex items-center justify-end gap-2 px-5 py-3.5 border-t border-line bg-app-warm/40">
          <button class="px-3.5 py-2 rounded-chip text-[12px] font-semibold text-ink-2 hover:bg-white" @click="funding=false">{{ L("Cancel","إلغاء","Annuler") }}</button>
          <button class="px-4 py-2 rounded-chip text-[12px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand disabled:opacity-50" :disabled="!fund.intermediary || !fund.bank || !(fund.amount>0) || fundBusy" @click="doFund">{{ fundBusy ? '…' : L('Fund','موّل','Financer') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch } from "vue";
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

const d = ref({ accounts: [] });
const opt = ref({ intermediaries: [], banks: [], bills: [] });
const loading = ref(true);
const busy = ref("");
const settleWith = reactive({});
const ccy = computed(() => d.value.currency || "MAD");

async function load() {
  loading.value = true;
  try {
    d.value = await api.call("accounting_portal.api.intermediary.intermediary_review", { company: currentCompany() }, { fresh: true }) || { accounts: [] };
    opt.value = await api.call("accounting_portal.api.intermediary.intermediary_options", { company: currentCompany() }, { fresh: true }) || { intermediaries: [], banks: [], bills: [] };
  } catch { d.value = { accounts: [] }; }
  finally { loading.value = false; }
}
load();
watch(entityId, load);

async function settle(b) {
  const inter = settleWith[b.name];
  if (!inter || busy.value) return;
  if (!window.confirm(L(`Settle ${b.name} (${money(b.outstanding_amount)} ${b.currency}) from the intermediary?`, `سدّد ${b.name} من حساب الوسيط؟`, `Régler ${b.name} ?`))) return;
  busy.value = b.name;
  try {
    const res = await api.call("accounting_portal.api.intermediary.settle_via_intermediary", { company: currentCompany(), invoice: b.name, intermediary: inter });
    if (res && res.status === "Proposed") toast.success(L("Sent for approval", "أُرسل للموافقة", "Envoyé"));
    else toast.success(L("Settled", "تم التسديد", "Réglé"));
    load();
  } catch (e) { toast.error(String(e?.message || e).slice(0, 180)); }
  finally { busy.value = ""; }
}

const funding = ref(false), fundBusy = ref(false), fundErr = ref("");
const fund = reactive({ intermediary: "", bank: "", amount: null, date: new Date().toISOString().slice(0, 10) });
function openFund() { fund.intermediary = ""; fund.bank = ""; fund.amount = null; fundErr.value = ""; creating.value = false; funding.value = true; }

const creating = ref(false), acctBusy = ref(false), acctErr = ref("");
const newAcct = reactive({ name: "", currency: "MAD" });
async function doCreateAcct() {
  if (!newAcct.name || acctBusy.value) return;
  acctBusy.value = true; acctErr.value = "";
  try {
    const res = await api.call("accounting_portal.api.intermediary.create_intermediary_account",
      { company: currentCompany(), account_name: newAcct.name, currency: newAcct.currency });
    toast.success(L("Account created", "تم إنشاء الحساب", "Compte créé"));
    creating.value = false; newAcct.name = "";
    await load();
    if (res && res.voucher_no) fund.intermediary = res.voucher_no;
  } catch (e) { acctErr.value = String(e?.message || e).slice(0, 200); }
  finally { acctBusy.value = false; }
}
async function doFund() {
  if (fundBusy.value) return;
  fundBusy.value = true; fundErr.value = "";
  try {
    const res = await api.call("accounting_portal.api.intermediary.fund_intermediary", { company: currentCompany(), intermediary: fund.intermediary, bank: fund.bank, amount: Number(fund.amount), posting_date: fund.date });
    if (res && res.status === "Proposed") toast.success(L("Sent for approval", "أُرسل للموافقة", "Envoyé"));
    else toast.success(L("Funded", "تم التمويل", "Financé"));
    funding.value = false; load();
  } catch (e) { fundErr.value = String(e?.message || e).slice(0, 200); }
  finally { fundBusy.value = false; }
}
</script>
