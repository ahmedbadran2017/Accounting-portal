<template>
  <div v-if="inv" class="space-y-3.5">
    <button class="inline-flex items-center gap-1.5 text-[12px] font-medium text-ink-3 hover:text-ink" @click="back">
      <span class="rtl:rotate-180"><Icon name="arrow" :size="15" /></span>{{ L("Back to invoices","العودة للفواتير","Retour aux factures") }}
    </button>

    <!-- Header -->
    <div class="bg-white rounded-card border border-line p-5">
      <div class="flex flex-wrap items-start gap-3">
        <div class="min-w-0">
          <div class="text-[17px] font-bold tracking-tight font-mono">{{ inv.id }}</div>
          <div class="text-[12.5px] text-ink-3">{{ L("Bill to","الفاتورة إلى","Facturé à") }}: {{ inv.customer }} · {{ inv.date }}</div>
          <div v-if="inv.phone || inv.city" class="text-[11.5px] text-ink-muted mt-0.5 flex items-center gap-2.5">
            <span v-if="inv.phone" class="inline-flex items-center gap-1"><Icon name="user" :size="11" />{{ inv.phone }}</span>
            <span v-if="inv.city" class="inline-flex items-center gap-1"><Icon name="building" :size="11" />{{ inv.city }}</span>
          </div>
        </div>
        <div class="ms-auto flex items-center gap-2 h-fit">
          <span class="inline-block text-[11px] font-bold px-2.5 py-1 rounded-badge border"
                :style="{ background: st.bg, color: st.fg, borderColor: st.bd }">{{ invStatusLabel(inv.status, locale) }}</span>
          <button v-if="canPay" class="inline-flex items-center gap-1.5 text-[11.5px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand px-2.5 py-1 rounded-chip" @click="openPay">
            <Icon name="coins" :size="13" color="#fff" />{{ L("Record payment","تسجيل دفعة","Encaisser") }}
          </button>
          <button v-if="canRefund" class="inline-flex items-center gap-1.5 text-[11.5px] font-semibold text-sale border border-sale/30 bg-sale/5 hover:bg-sale/10 px-2.5 py-1 rounded-chip" @click="openRefund">
            <Icon name="refresh" :size="13" />{{ L("Credit note","إشعار دائن","Note de crédit") }}
          </button>
          <button v-if="canPay" class="inline-flex items-center gap-1.5 text-[11.5px] font-semibold text-ink-2 border border-line-2 hover:bg-app-warm px-2.5 py-1 rounded-chip" @click="refundCash" :disabled="busy">
            <Icon name="cash" :size="13" />{{ L("Refund cash","استرداد نقدي","Rembourser") }}
          </button>
          <button v-if="inv && inv.outstanding > 0 && inv.outstanding <= 200" class="inline-flex items-center gap-1.5 text-[11.5px] font-semibold text-ink-3 border border-line-2 hover:bg-app-warm px-2.5 py-1 rounded-chip" @click="writeOff" :disabled="busy">
            {{ L("Write off","شطب","Passer en perte") }} {{ fmt2(inv.outstanding) }}
          </button>
        </div>
      </div>
    </div>

    <!-- Existing credit note banner -->
    <div v-if="inv && inv.credit_note" class="flex items-center gap-2 flex-wrap px-4 py-2.5 rounded-card border" style="background:#fef2f2;border-color:#fecaca">
      <Icon name="refresh" :size="15" color="#be123c" />
      <span class="text-[12px] text-ink-2">{{ L("Credited by","مُقابَل بإشعار دائن","Crédité par") }}
        <button class="font-mono font-bold text-sale hover:underline" @click="openDoc('invoices', inv.credit_note.name)">{{ inv.credit_note.name }}</button>
        · <span class="tnum">{{ fmt2(inv.credit_note.grand_total) }}</span></span>
      <span v-if="Number(inv.credit_note.outstanding_amount) < 0" class="ms-auto text-[11px] font-semibold text-amber-700">{{ L("refund due","استرداد مستحق","à rembourser") }} {{ fmt2(Math.abs(inv.credit_note.outstanding_amount)) }}</span>
      <span v-else class="ms-auto text-[11px] font-semibold text-success-dark">{{ L("refunded ✓","تم الاسترداد ✓","remboursé ✓") }}</span>
    </div>

    <!-- Refund / credit note -->
    <div v-if="showRefund" class="fixed inset-0 z-[100] flex items-center justify-center p-4" style="background:rgba(28,25,23,.45)" @click.self="showRefund = false">
      <div class="bg-white rounded-[16px] shadow-cardHover w-full max-w-md p-5">
        <div class="flex items-center gap-2.5 mb-1.5">
          <span class="w-8 h-8 rounded-[10px] grid place-items-center" style="background:#fef2f2"><Icon name="refresh" :size="16" color="#be123c" /></span>
          <div class="text-[14px] font-bold">{{ L("Create credit note","إنشاء إشعار دائن","Note de crédit") }}</div>
        </div>
        <p class="text-[12px] text-ink-3 mb-3">{{ L("Reverses the invoice — credits the customer's debtor and reverses the revenue.","يعكس الفاتورة — يقفل مديونية العميل ويعكس الإيراد.","Annule la facture — crédite le débiteur.") }} <b class="font-mono">{{ inv.id }}</b></p>
        <textarea v-model="reason" rows="2" :placeholder="L('Reason (optional)','السبب (اختياري)','Motif (facultatif)')" class="w-full border border-line-2 rounded-[10px] px-3 py-2 text-[12.5px] focus:outline-none focus:border-accent/40 mb-3"></textarea>
        <label class="flex items-center gap-2 mb-2 text-[12.5px] cursor-pointer">
          <input type="checkbox" v-model="alsoRefund" class="accent-sale w-4 h-4" />
          <span>{{ L("Also refund the cash to the customer","استرداد الكاش للعميل أيضًا","Rembourser aussi le client") }}</span>
        </label>
        <div v-if="alsoRefund" class="mb-3">
          <label class="text-[11px] font-bold text-ink-3">{{ L("Refund from","الاسترداد من","Rembourser depuis") }}</label>
          <select v-model="refundAccount" class="w-full h-9 mt-1 border border-line-2 rounded-[9px] px-2 text-[12.5px] bg-white focus:outline-none focus:border-accent/40">
            <option value="">{{ L("Select bank/cash account","اختر حساب بنك/كاش","Sélectionner un compte") }}</option>
            <option v-for="a in accounts" :key="a.name" :value="a.name">{{ a.account_name }} ({{ a.account_type }})</option>
          </select>
        </div>
        <div v-if="refundError" class="text-[11.5px] text-sale mb-2">{{ refundError }}</div>
        <div class="flex justify-end gap-2">
          <button class="px-3.5 py-2 rounded-chip text-[12px] font-semibold text-ink-2 hover:bg-app-warm" @click="showRefund = false">{{ L("Cancel","إلغاء","Annuler") }}</button>
          <button class="px-4 py-2 rounded-chip text-[12px] font-bold text-white bg-sale hover:opacity-90 disabled:opacity-50" :disabled="busy" @click="createReturn">
            {{ busy ? L("Creating…","جارٍ…","…") : L("Create credit note","إنشاء","Créer") }}
          </button>
        </div>
      </div>
    </div>

    <!-- Record payment -->
    <div v-if="showPay" class="fixed inset-0 z-[100] flex items-center justify-center p-4" style="background:rgba(28,25,23,.45)" @click.self="showPay = false">
      <div class="bg-white rounded-[16px] shadow-cardHover w-full max-w-md p-5">
        <div class="flex items-center gap-2.5 mb-1.5">
          <span class="w-8 h-8 rounded-[10px] grid place-items-center" style="background:#ecfdf5"><Icon name="coins" :size="16" color="#047857" /></span>
          <div class="text-[14px] font-bold">{{ L("Record payment","تسجيل دفعة","Encaisser") }}</div>
        </div>
        <p class="text-[12px] text-ink-3 mb-3">{{ L("Collect against","تحصيل مقابل","Encaisser pour") }} <b class="font-mono">{{ inv.id }}</b> · {{ L("outstanding","المتبقّي","restant") }} <b class="tnum">{{ fmt2(inv.outstanding) }}</b></p>
        <div class="space-y-2.5">
          <div><label class="text-[11px] font-bold text-ink-3">{{ L("Amount","المبلغ","Montant") }}</label><input v-model.number="pay.amount" type="number" min="0" :max="inv.outstanding" class="w-full h-9 mt-1 border border-line-2 rounded-[9px] px-2 text-[12.5px] focus:outline-none focus:border-accent/40" /></div>
          <div><label class="text-[11px] font-bold text-ink-3">{{ L("Deposit to","الإيداع في","Déposer sur") }}</label>
            <select v-model="pay.account" class="w-full h-9 mt-1 border border-line-2 rounded-[9px] px-2 text-[12.5px] bg-white focus:outline-none focus:border-accent/40">
              <option v-for="a in accounts" :key="a.name" :value="a.name">{{ a.account_name }} ({{ a.account_type }})</option>
            </select></div>
          <div class="grid grid-cols-2 gap-2">
            <div><label class="text-[11px] font-bold text-ink-3">{{ L("Reference","المرجع","Référence") }}</label><input v-model.trim="pay.reference_no" class="w-full h-9 mt-1 border border-line-2 rounded-[9px] px-2 text-[12.5px] focus:outline-none focus:border-accent/40" :placeholder="L('e.g. COD batch','مثال: تحصيل','réf')" /></div>
            <div><label class="text-[11px] font-bold text-ink-3">{{ L("Date","التاريخ","Date") }}</label><input v-model="pay.posting_date" type="date" class="w-full h-9 mt-1 border border-line-2 rounded-[9px] px-2 text-[12.5px] focus:outline-none focus:border-accent/40" /></div>
          </div>
        </div>
        <div v-if="payError" class="text-[11.5px] text-sale mt-2">{{ payError }}</div>
        <div class="flex justify-end gap-2 mt-4">
          <button class="px-3.5 py-2 rounded-chip text-[12px] font-semibold text-ink-2 hover:bg-app-warm" @click="showPay = false">{{ L("Cancel","إلغاء","Annuler") }}</button>
          <button class="px-4 py-2 rounded-chip text-[12px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand disabled:opacity-50" :disabled="busy || !pay.amount || !pay.account" @click="submitPay">
            {{ busy ? L("Recording…","جارٍ…","…") : L("Record payment","تسجيل","Encaisser") }}
          </button>
        </div>
      </div>
    </div>

    <div class="grid lg:grid-cols-3 gap-3.5">
      <!-- Lines + totals -->
      <div class="lg:col-span-2 bg-white rounded-card border border-line overflow-hidden">
        <table class="w-full text-[12px]">
          <thead>
            <tr class="border-b border-line">
              <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Item","الصنف","Article") }}</th>
              <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Qty","الكمية","Qté") }}</th>
              <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Rate","السعر","PU") }}</th>
              <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Amount","المبلغ","Montant") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(ln, i) in inv.lines" :key="i" class="border-b border-line-hair hover:bg-app-warm/40">
              <td class="px-4 py-3">
                <div class="flex items-center gap-3">
                  <img v-if="ln.image" :src="ln.image" :alt="ln.name" loading="lazy"
                       class="w-12 h-12 rounded-[10px] object-cover border border-line bg-app-warm flex-shrink-0"
                       @error="$event.target.style.display='none'" />
                  <span v-else class="w-12 h-12 rounded-[10px] grid place-items-center bg-app-warm border border-line flex-shrink-0"><Icon name="box" :size="17" color="#a8a29e" /></span>
                  <span class="text-[12px] leading-snug">{{ ln.name }}</span>
                </div>
              </td>
              <td class="px-4 py-3 text-end tnum align-middle">{{ ln.qty }}</td>
              <td class="px-4 py-3 text-end tnum align-middle">{{ ln.rate }}</td>
              <td class="px-4 py-3 text-end tnum font-semibold align-middle">{{ ln.amount }}</td>
            </tr>
          </tbody>
          <tfoot class="text-[12px]">
            <tr><td colspan="2"></td><td class="px-4 py-1.5 text-end text-ink-3">{{ L("Subtotal (ex-VAT)","المجموع قبل الضريبة","Sous-total HT") }}</td><td class="px-4 py-1.5 text-end tnum">{{ fmt2(inv.net) }}</td></tr>
            <tr><td colspan="2"></td><td class="px-4 py-1.5 text-end text-ink-3">{{ L("VAT 20%","ضريبة 20%","TVA 20%") }}</td><td class="px-4 py-1.5 text-end tnum">{{ fmt2(inv.vat) }}</td></tr>
            <tr class="border-t border-line-2"><td colspan="2"></td><td class="px-4 py-2 text-end font-bold">{{ L("Total","الإجمالي","Total") }}</td><td class="px-4 py-2 text-end tnum font-bold text-[14px]">{{ fmt2(inv.gross) }}</td></tr>
          </tfoot>
        </table>
      </div>

      <!-- Payment status -->
      <div class="bg-white rounded-card border border-line p-4">
        <div class="text-[13px] font-bold mb-2">{{ L("Payment","الدفع","Paiement") }}</div>
        <div class="rounded-card p-3 border" :style="paid ? 'background:#ecfdf5;border-color:#a7f3d0' : 'background:#fffbeb;border-color:#fde68a'">
          <div class="flex items-center gap-1.5 text-[12.5px] font-semibold" :style="{ color: paid ? '#047857' : '#b45309' }">
            <Icon :name="paid ? 'check' : 'clock'" :size="15" />
            {{ paid ? L("Payment received","تم استلام الدفعة","Paiement reçu") : L("Awaiting COD collection","بانتظار تحصيل الدفع","En attente d’encaissement") }}
          </div>
          <div class="text-[11px] text-ink-3 mt-1">
            {{ paid ? `${L("via","عبر","via")} ${inv.track} · ${inv.pay}` : L("Delivered, cash not yet remitted","مُسلَّم، النقد لم يُحوَّل بعد","Livré, cash non encore versé") }}
          </div>
        </div>

        <!-- Related documents -->
        <div class="mt-3 pt-3 border-t border-line-hair">
          <div class="text-[11px] font-bold uppercase tracking-wider text-ink-muted mb-2">{{ L("Related","مرتبط","Lié") }}</div>
          <div v-if="related.orders.length || related.deliveries.length || related.payments.length" class="flex flex-wrap gap-1.5">
            <button v-for="o in related.orders" :key="o" @click="openDoc('orders', o)" class="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-1 rounded-chip border border-line-2 bg-app-warm hover:bg-white"><Icon name="receipt" :size="11" color="#0b5c4f" />{{ o }}</button>
            <button v-for="dn in related.deliveries" :key="dn" @click="openDoc('challans', dn)" class="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-1 rounded-chip border border-line-2 bg-app-warm hover:bg-white"><Icon name="truck" :size="11" color="#c2410c" />{{ dn }}</button>
            <button v-for="pe in related.payments" :key="pe" @click="openDoc('payments', pe)" class="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-1 rounded-chip border border-line-2 bg-app-warm hover:bg-white"><Icon name="coins" :size="11" color="#047857" />{{ pe }}</button>
          </div>
          <div v-else class="text-[11px] text-ink-muted">{{ L("No linked documents.","لا مستندات مرتبطة.","Aucun document lié.") }}</div>
        </div>
      </div>
    </div>

    <!-- Posted journal -->
    <div class="bg-white rounded-card border border-line overflow-hidden">
      <div class="px-4 py-3 border-b border-line flex items-center gap-2"><Icon name="ledger" :size="15" color="#0b5c4f" /><span class="text-[13px] font-bold">{{ L("Posted journal","القيد المُرحَّل","Écriture passée") }}</span></div>
      <table class="w-full text-[12px]">
        <tbody>
          <tr v-for="(j, i) in journal" :key="i" class="border-b border-line-hair">
            <td class="px-4 py-2.5 font-mono text-ink-2">{{ j.acc }}</td>
            <td class="px-4 py-2.5 text-end tnum font-semibold">{{ j.dr || "—" }}</td>
            <td class="px-4 py-2.5 text-end tnum font-semibold">{{ j.cr || "—" }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <DocHub v-if="route.query.id" :doctype="DOCTYPE" :name="route.query.id" class="mt-1" />
  </div>
  <div v-else-if="loading" class="py-20 text-center text-[12px] text-ink-muted">{{ t("common.loading") }}</div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import DocHub from "@/components/DocHub.vue";
import { INV_STATUS, invStatusLabel, fmt2 } from "@/data/invoices";
import { useInvoices } from "@/composables/useInvoices";
import api from "@/services/api";
import { useToast } from "@/composables/useToast";
import { currentCompany } from "@/composables/useLive";

const { t, locale } = useI18n();
const route = useRoute();
const router = useRouter();
const { loadDetail } = useInvoices();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const DOCTYPE = "Sales Invoice";

const vm = ref(null);
const showRefund = ref(false);
const reason = ref("");
const busy = ref(false);
const refundError = ref("");
const loading = ref(true);
async function load() {
  loading.value = true;
  vm.value = await loadDetail(route.query.id);
  loading.value = false;
  if (route.query.id && !vm.value) router.replace("/accounting/sales/invoices");
}

const alsoRefund = ref(false);
const refundAccount = ref("");
async function openRefund() {
  refundError.value = ""; reason.value = "";
  alsoRefund.value = !!paid.value;   // a paid invoice → the customer is owed the cash back
  refundAccount.value = "";
  showRefund.value = true;
  if (!accounts.value.length) {
    try { accounts.value = await api.call("accounting_portal.api.payments.deposit_accounts", { company: currentCompany() }); } catch { accounts.value = []; }
  }
  if (accounts.value.length) refundAccount.value = accounts.value[0].name;
}
async function createReturn() {
  if (alsoRefund.value && !refundAccount.value) { refundError.value = L("Pick a bank/cash account for the refund.", "اختر حساب بنك/كاش للاسترداد.", "Choisissez un compte."); return; }
  busy.value = true; refundError.value = "";
  try {
    const res = await api.call("accounting_portal.api.sales.create_sales_return", { company: currentCompany(), invoice: inv.value.id, reason: reason.value || undefined, refund_account: alsoRefund.value ? refundAccount.value : undefined });
    showRefund.value = false; reason.value = "";
    if (res && res.status === "Posted") toast.success(L(`Credit note ${res.voucher_no || ""} created`, `إشعار دائن ${res.voucher_no || ""} أُنشئ`, `Note de crédit ${res.voucher_no || ""} créée`));
    else toast.info(L("Recorded — awaiting an approver", "سُجّل — بانتظار موافِق", "Enregistré — en attente"));
    if (res && res.refund_error) toast.error(L("Credit note posted, but the refund failed: ", "أُنشئ الإشعار لكن فشل الاسترداد: ", "Note créée, remboursement échoué : ") + String(res.refund_error).slice(0, 120));
    else if (res && res.refund) toast.success(L("Cash refunded to the customer", "تم استرداد الكاش للعميل", "Client remboursé"));
    load();
  } catch (e) { refundError.value = (e && e.message) || L("Failed to create credit note.", "فشل الإنشاء.", "Échec."); }
  finally { busy.value = false; }
}
async function refundCash() {
  const i = inv.value; if (!i || busy.value) return;
  const amt = Number(window.prompt(L(`Refund how much cash to the customer? (outstanding/credit ${fmt2(i.outstanding)})`, `كام تسترد كاش للعميل؟ (${fmt2(i.outstanding)})`, `Montant à rembourser ?`), String(Math.abs(i.outstanding))));
  if (!(amt > 0)) return;
  if (!accounts.value.length) { try { accounts.value = await api.call("accounting_portal.api.payments.deposit_accounts", { company: currentCompany() }) || []; } catch { /* */ } }
  const acct = accounts.value[0]?.name;
  if (!acct) { toast.error(L("No bank/cash account", "لا حساب بنك/كاش", "Aucun compte")); return; }
  busy.value = true;
  try {
    const res = await api.call("accounting_portal.api.payments.create_payment_entry", {
      company: currentCompany(), party: i.customer || i.party, party_type: "Customer",
      payment_type: "Pay", amount: amt, account: acct, posting_date: new Date().toISOString().slice(0, 10),
    });
    if (res && res.status === "Proposed") toast.info(L("Sent for approval", "أُرسل للموافقة", "Envoyé"));
    else toast.success(L("Cash refunded", "تم الاسترداد النقدي", "Remboursé"));
    load();
  } catch (e) { toast.error(String(e?.message || e).slice(0, 160)); }
  finally { busy.value = false; }
}
async function writeOff() {
  const i = inv.value; if (!i || busy.value) return;
  const reasonTxt = window.prompt(L(`Write off ${fmt2(i.outstanding)}? Reason:`, `شطب ${fmt2(i.outstanding)}؟ السبب:`, `Passer en perte ${fmt2(i.outstanding)} ? Motif:`), L("Rounding / bad debt", "تقريب / دين معدوم", "Arrondi"));
  if (reasonTxt === null) return;
  busy.value = true;
  try {
    await api.call("accounting_portal.api.payments.write_off_invoice", {
      company: currentCompany(), invoice: i.id, doctype: "Sales Invoice", reason: reasonTxt || undefined });
    toast.success(L("Written off", "تم الشطب", "Passé en perte"));
    load();
  } catch (e) { toast.error(String(e?.message || e).slice(0, 160)); }
  finally { busy.value = false; }
}
watch(() => route.query.id, load, { immediate: true });

const inv = computed(() => vm.value?.inv || null);
const st = computed(() => INV_STATUS[inv.value?.status] || INV_STATUS.paid);
// Only a posted, non-return, non-draft invoice can be credited.
const canRefund = computed(() => {
  const i = inv.value;
  return !!i && Number(i.gross) > 0 && !i.is_return && !i.credit_note && !["draft", "cancelled", "return"].includes(i.status);
});
const paid = computed(() => !!vm.value?.paid);
const journal = computed(() => vm.value?.journal || []);
const related = computed(() => vm.value?.related || { orders: [], deliveries: [], payments: [] });
function openDoc(sub, id) { router.push({ path: `/accounting/sales/${sub}`, query: { id } }); }
function back() { router.push({ path: "/accounting/sales/invoices" }); }

// ── Record payment (collect against this invoice; partial allowed) ──
const canPay = computed(() => {
  const i = inv.value;
  return !!i && !i.is_return && Number(i.outstanding) > 0 && !["draft", "cancelled", "return"].includes(i.status);
});
const showPay = ref(false);
const payError = ref("");
const accounts = ref([]);
const pay = ref({ amount: 0, account: "", reference_no: "", posting_date: "" });
async function openPay() {
  payError.value = "";
  pay.value = { amount: Number(inv.value.outstanding) || 0, account: "", reference_no: "", posting_date: new Date().toISOString().slice(0, 10) };
  showPay.value = true;
  if (!accounts.value.length) {
    try { accounts.value = await api.call("accounting_portal.api.payments.deposit_accounts", { company: currentCompany() }); } catch { accounts.value = []; }
  }
  if (accounts.value.length && !pay.value.account) pay.value.account = accounts.value[0].name;
}
async function submitPay() {
  payError.value = "";
  const amt = Number(pay.value.amount) || 0;
  if (amt <= 0 || amt > Number(inv.value.outstanding) + 0.01) { payError.value = L("Amount must be between 0 and the outstanding balance.", "المبلغ يجب أن يكون بين 0 والمتبقّي.", "Montant invalide."); return; }
  busy.value = true;
  try {
    const res = await api.call("accounting_portal.api.payments.create_payment_entry", {
      company: currentCompany(), party: inv.value.customer, amount: amt, account: pay.value.account,
      reference_no: pay.value.reference_no || undefined, posting_date: pay.value.posting_date || undefined,
      payment_type: "Receive", references: JSON.stringify([{ name: inv.value.id, amount: amt }]),
    });
    showPay.value = false;
    if (res && res.status === "Posted") toast.success(L(`Payment ${res.voucher_no || ""} recorded`, `سُجّلت الدفعة ${res.voucher_no || ""}`, `Paiement ${res.voucher_no || ""} enregistré`));
    else toast.info(L("Recorded — awaiting an approver", "سُجّل — بانتظار موافِق", "Enregistré — en attente"));
    load();
  } catch (e) { payError.value = String((e && e.message) || L("Failed to record payment.", "فشل التسجيل.", "Échec.")).slice(0, 160); }
  finally { busy.value = false; }
}
</script>
