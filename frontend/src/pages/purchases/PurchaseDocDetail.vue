<template>
  <div class="space-y-3.5">
    <button class="inline-flex items-center gap-1.5 text-[12px] font-semibold text-ink-3 hover:text-ink" @click="back">
      <Icon name="arrow" :size="14" class="rotate-180" />{{ backLabel }}
    </button>

    <div v-if="loading" class="bg-white rounded-card border border-line shadow-card"><TableLoading :rows="4" /></div>
    <div v-else-if="!d" class="bg-white rounded-card border border-line shadow-card py-16 text-center text-[12px] text-ink-muted">{{ L("Document not found.","المستند غير موجود.","Introuvable.") }}</div>

    <template v-else>
      <!-- Header -->
      <div class="bg-white rounded-card border border-line shadow-card p-5">
        <div class="flex items-start gap-3 flex-wrap">
          <span class="w-11 h-11 rounded-[12px] grid place-items-center flex-shrink-0" :style="{ background: tint }"><Icon :name="icon" :size="20" :color="color" /></span>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="text-[16px] font-bold font-mono">{{ h.name }}</span>
              <span class="text-[10px] font-bold px-2 py-0.5 rounded-full" :style="{ background: tint, color }">{{ DT_LABEL() }}</span>
              <span v-if="h.status" class="text-[10px] font-bold px-2 py-0.5 rounded-full" style="background:#f1efe8;color:#5f5e5a">{{ h.status }}</span>
            </div>
            <div class="text-[13px] text-ink-2 mt-0.5">{{ h.supplier_name }}</div>
            <div class="text-[11px] text-ink-muted mt-0.5">{{ h.date }}<span v-if="h.due"> · {{ L("due","استحقاق","éch.") }} {{ h.due }}</span></div>
          </div>
          <div class="text-end">
            <div class="text-[24px] font-extrabold tnum">{{ fmt(h.grand) }}<span class="text-[12px] text-ink-muted ms-1">{{ h.currency }}</span></div>
            <div v-if="h.outstanding > 0" class="text-[11px] font-bold text-sale mt-0.5">{{ fmt(h.outstanding) }} {{ L("owed","مستحق","dû") }}</div>
            <div v-else-if="h.doctype === 'Purchase Order'" class="text-[11px] text-ink-muted mt-0.5">{{ Math.round(h.per_received) }}% {{ L("received","مُستلم","reçu") }}</div>
            <div v-else-if="h.doctype === 'Purchase Receipt'" class="text-[11px] text-ink-muted mt-0.5">{{ Math.round(h.per_billed) }}% {{ L("billed","متفوتر","facturé") }}</div>
          </div>
        </div>
        <!-- action -->
        <div v-if="canAct" class="flex items-center gap-2.5 flex-wrap mt-4 pt-3 border-t border-line-hair">
          <button @click="primaryAction" :disabled="posting"
                  class="inline-flex items-center gap-2 h-9 px-4 rounded-[10px] text-[12.5px] font-bold text-white shadow-card disabled:opacity-50 hover:brightness-110 transition"
                  :style="{ background: actionMeta.color }">
            <Icon :name="actionMeta.icon" :size="15" color="#fff" />{{ posting ? L("Working…", "جارٍ…", "…") : actionMeta.label }}
          </button>
          <span class="text-[11px] text-ink-muted">{{ actionMeta.hint }}</span>
        </div>

        <!-- connections -->
        <div v-if="hasConn" class="flex items-center gap-1.5 flex-wrap mt-4 pt-3 border-t border-line-hair">
          <span class="text-[10px] font-bold uppercase tracking-wider text-ink-muted me-1">{{ L("Connections","الروابط","Liens") }}</span>
          <button v-for="o in d.connections.orders" :key="o" @click="open('tobuy', o)" class="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-1 rounded-chip border border-line-2 bg-app-warm hover:bg-white"><Icon name="cart" :size="11" color="#0369a1" />{{ o }}</button>
          <button v-for="r in d.connections.receipts" :key="r" @click="open('received', r)" class="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-1 rounded-chip border border-line-2 bg-app-warm hover:bg-white"><Icon name="box" :size="11" color="#b45309" />{{ r }}</button>
          <button v-for="i in d.connections.invoices" :key="i" @click="open('topay', i)" class="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-1 rounded-chip border border-line-2 bg-app-warm hover:bg-white"><Icon name="doc" :size="11" color="#0891b2" />{{ i }}</button>
          <span v-for="p in d.connections.payments" :key="p" class="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-1 rounded-chip border border-line-2 bg-app-warm"><Icon name="coins" :size="11" color="#047857" />{{ p }}</span>
        </div>
      </div>

      <div class="grid lg:grid-cols-3 gap-3.5">
        <!-- Lines -->
        <div class="lg:col-span-2 bg-white rounded-card border border-line shadow-card overflow-hidden">
          <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><Icon name="list" :size="14" color="#0b5c4f" /><span class="text-[12px] font-bold">{{ L("Items","الأصناف","Articles") }}</span><span class="text-[10px] text-ink-muted">{{ d.items.length }}</span></div>
          <div class="overflow-x-auto">
            <table class="w-full text-[12px]">
              <thead><tr style="background:#fafaf9">
                <th class="px-4 py-2 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Item","الصنف","Article") }}</th>
                <th class="px-4 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Qty","الكمية","Qté") }}</th>
                <th class="px-4 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Rate","السعر","PU") }}</th>
                <th class="px-4 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Amount","المبلغ","Montant") }}</th>
              </tr></thead>
              <tbody>
                <tr v-for="(it, i) in d.items" :key="i" class="border-t border-line-hair">
                  <td class="px-4 py-2.5">
                    <div class="flex items-center gap-2.5">
                      <img v-if="it.image" :src="it.image" loading="lazy" @error="$event.target.style.display='none'" class="w-9 h-9 rounded-[8px] object-cover border border-line-2 bg-app-warm flex-shrink-0" />
                      <span v-else class="w-9 h-9 rounded-[8px] bg-app-warm grid place-items-center flex-shrink-0"><Icon name="box" :size="14" color="#a8a29e" /></span>
                      <div class="min-w-0">
                        <div class="font-medium truncate max-w-[230px]">{{ it.item_name }}</div>
                        <div class="text-[10px] text-ink-muted">
                          <span v-if="it.sku" class="font-mono font-semibold text-accent-dark">{{ it.sku }}</span><span v-if="it.sku" class="mx-1">·</span><span class="font-mono">{{ it.item_code }}</span>
                        </div>
                      </div>
                    </div>
                  </td>
                  <td class="px-4 py-2.5 text-end tnum">{{ it.qty }}</td>
                  <td class="px-4 py-2.5 text-end tnum text-ink-3">{{ fmt(it.rate) }}</td>
                  <td class="px-4 py-2.5 text-end tnum font-semibold">{{ fmt(it.amount) }}</td>
                </tr>
              </tbody>
              <tfoot>
                <tr class="border-t-2 border-line-2 font-bold"><td class="px-4 py-2.5" colspan="3">{{ L("Net","الصافي","HT") }}</td><td class="px-4 py-2.5 text-end tnum">{{ fmt(h.net) }}</td></tr>
                <tr v-if="h.tax" class="border-t border-line-hair"><td class="px-4 py-2 text-ink-3" colspan="3">{{ L("Tax","الضريبة","Taxe") }}</td><td class="px-4 py-2 text-end tnum text-ink-3">{{ fmt(h.tax) }}</td></tr>
                <tr class="border-t border-line-hair font-bold"><td class="px-4 py-2.5" colspan="3">{{ L("Total","الإجمالي","Total") }}</td><td class="px-4 py-2.5 text-end tnum">{{ fmt(h.grand) }}</td></tr>
              </tfoot>
            </table>
          </div>
        </div>

        <!-- GL -->
        <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
          <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><Icon name="ledger" :size="14" color="#0b5c4f" /><span class="text-[12px] font-bold">{{ L("Journal impact","الأثر المحاسبي","Impact GL") }}</span></div>
          <table v-if="d.gl.length" class="w-full text-[12px]">
            <thead><tr style="background:#fafaf9"><th class="px-3 py-2 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Account","الحساب","Compte") }}</th><th class="px-3 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Dr","مدين","D") }}</th><th class="px-3 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Cr","دائن","C") }}</th></tr></thead>
            <tbody>
              <tr v-for="(g, i) in d.gl" :key="i" class="border-t border-line-hair">
                <td class="px-3 py-2"><div class="truncate max-w-[150px]">{{ g.name }}</div></td>
                <td class="px-3 py-2 text-end tnum" :class="g.dr ? 'font-semibold' : 'text-ink-muted'">{{ g.dr ? fmt(g.dr) : "—" }}</td>
                <td class="px-3 py-2 text-end tnum" :class="g.cr ? 'font-semibold' : 'text-ink-muted'">{{ g.cr ? fmt(g.cr) : "—" }}</td>
              </tr>
            </tbody>
          </table>
          <div v-else class="py-8 text-center text-[11px] text-ink-muted">{{ L("No journal yet.","لا قيد بعد.","Aucune écriture.") }}</div>
        </div>
      </div>

      <DocHub v-if="d" :doctype="doctype" :name="route.query.id" class="mt-1" />
    </template>

    <!-- Pay dialog -->
    <div v-if="payOpen" class="fixed inset-0 z-50 grid place-items-center bg-black/30 p-4" @click.self="payOpen = false">
      <div class="bg-white rounded-card shadow-xl w-full max-w-sm p-5 space-y-3.5">
        <div class="flex items-center gap-2">
          <span class="w-8 h-8 rounded-[9px] grid place-items-center" style="background:#ecfdf5"><Icon name="wallet" :size="16" color="#047857" /></span>
          <div>
            <div class="text-[14px] font-bold">{{ L("Record payment", "تسجيل دفعة", "Enregistrer paiement") }}</div>
            <div class="text-[11px] text-ink-muted">{{ h.name }} · {{ fmt(h.outstanding) }} {{ h.currency }}</div>
          </div>
        </div>
        <div>
          <label class="text-[11px] font-bold text-ink-3">{{ L("Method", "الطريقة", "Méthode") }}</label>
          <select v-model="payMode" class="w-full h-9 mt-1 border border-line-2 rounded-[9px] px-2 text-[12.5px] bg-white focus:outline-none focus:border-accent/40">
            <option value="">{{ L("Select…", "اختر…", "Choisir…") }}</option>
            <option v-for="m in modes" :key="m.mode" :value="m.mode">{{ m.mode }}</option>
          </select>
        </div>
        <div>
          <label class="text-[11px] font-bold text-ink-3 flex items-center justify-between">{{ L("Amount", "المبلغ", "Montant") }}
            <button type="button" class="text-[10px] text-accent-dark font-semibold hover:underline" @click="payAmount = h.outstanding">{{ L("full","الكامل","total") }} {{ fmt(h.outstanding) }}</button>
          </label>
          <input type="number" min="0" step="0.01" :max="h.outstanding" v-model.number="payAmount" class="w-full h-9 mt-1 border border-line-2 rounded-[9px] px-2 text-[13px] tnum text-end font-semibold focus:outline-none focus:border-accent/40" :placeholder="String(h.outstanding)" />
          <div v-if="payAmount > 0 && payAmount < h.outstanding" class="text-[10.5px] text-amber-700 mt-0.5">{{ L("Partial — ","جزئي — ","Partiel — ") }}{{ fmt(h.outstanding - payAmount) }} {{ L("stays outstanding","يبقى مستحقًا","restant") }}</div>
        </div>
        <div class="grid grid-cols-2 gap-2">
          <div>
            <label class="text-[11px] font-bold text-ink-3">{{ L("Reference No", "رقم المرجع", "Référence") }}</label>
            <input v-model.trim="payRef" :placeholder="L('Cheque / txn no', 'شيك / معاملة', 'Chèque / réf')" class="w-full h-9 mt-1 border border-line-2 rounded-[9px] px-2 text-[12.5px] focus:outline-none focus:border-accent/40" />
          </div>
          <div>
            <label class="text-[11px] font-bold text-ink-3">{{ L("Date", "التاريخ", "Date") }}</label>
            <input type="date" v-model="payDate" class="w-full h-9 mt-1 border border-line-2 rounded-[9px] px-2 text-[12.5px] focus:outline-none focus:border-accent/40" />
          </div>
        </div>
        <p class="text-[10.5px] text-ink-muted">{{ L("Bank / cheque methods require a reference.", "طرق البنك/الشيك تتطلب مرجعًا.", "Les méthodes banque/chèque exigent une référence.") }}</p>
        <div class="flex gap-2 justify-end pt-1">
          <button @click="payOpen = false" class="h-9 px-3 rounded-[9px] text-[12px] font-semibold text-ink-3 hover:bg-app-warm">{{ L("Cancel", "إلغاء", "Annuler") }}</button>
          <button @click="confirmPay" :disabled="posting || !payMode" class="h-9 px-4 rounded-[9px] text-[12px] font-bold text-white disabled:opacity-50" style="background:#047857">{{ posting ? L("Paying…", "جارٍ…", "…") : L("Pay", "دفع", "Payer") }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import DocHub from "@/components/DocHub.vue";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useToast } from "@/composables/useToast";

const toast = useToast();

const route = useRoute();
const router = useRouter();
const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const DT = { tobuy: "Purchase Order", received: "Purchase Receipt", billed: "Purchase Invoice", topay: "Purchase Invoice", paid: "Purchase Invoice" };
const sub = computed(() => route.params.sub);
const doctype = computed(() => DT[sub.value] || "Purchase Invoice");
const META = {
  "Purchase Order": { icon: "cart", color: "#0369a1", tint: "#eff6ff", label: () => L("Purchase order", "أمر شراء", "Bon de commande") },
  "Purchase Receipt": { icon: "box", color: "#b45309", tint: "#fffbeb", label: () => L("Receipt", "إيصال استلام", "Réception") },
  "Purchase Invoice": { icon: "doc", color: "#0891b2", tint: "#ecfeff", label: () => L("Purchase invoice", "فاتورة شراء", "Facture") },
};
const icon = computed(() => META[doctype.value].icon);
const color = computed(() => META[doctype.value].color);
const tint = computed(() => META[doctype.value].tint);
const DT_LABEL = () => META[doctype.value].label();
const backLabel = computed(() => L("Back", "رجوع", "Retour"));

const d = ref(null);
const loading = ref(true);
const h = computed(() => d.value?.header || {});
const hasConn = computed(() => { const c = d.value?.connections; return c && (c.orders.length || c.receipts.length || c.invoices.length || c.payments.length); });

function back() { router.push(`/accounting/purchases/${sub.value}`); }
function open(targetSub, id) { router.push({ path: `/accounting/purchases/${targetSub}`, query: { id } }); }

async function load() {
  const id = route.query.id;
  if (!id) { loading.value = false; return; }
  loading.value = true; d.value = null;
  try { d.value = await api.call("accounting_portal.api.purchases.get_purchase_doc", { name: id, doctype: doctype.value, company: currentCompany() }); }
  catch { d.value = null; }
  finally { loading.value = false; }
  // Stale / wrong-doctype id (e.g. switched buckets while a detail was open):
  // fall back to the bucket list instead of sticking on the skeleton.
  if (!d.value) router.replace({ path: `/accounting/purchases/${sub.value}`, query: {} });
}
// Watch the sub too: switching buckets keeps the same ?id but changes the
// doctype, so we must re-evaluate (and self-heal) rather than show a stuck page.
watch([() => route.query.id, () => route.params.sub], load, { immediate: true });

// ── Pipeline actions ──
const posting = ref(false);
const payOpen = ref(false);
const payMode = ref("");
const payRef = ref("");
const payDate = ref(new Date().toISOString().slice(0, 10));
const payAmount = ref(0);
const modes = ref([]);

const canAct = computed(() => {
  if (!d.value) return false;
  const dt = h.value.doctype;
  if (dt === "Purchase Order") return h.value.per_received < 100;
  if (dt === "Purchase Receipt") return h.value.per_billed < 100;
  if (dt === "Purchase Invoice") return h.value.outstanding > 0;
  return false;
});
const actionMeta = computed(() => {
  const dt = h.value.doctype;
  if (dt === "Purchase Order") return { label: L("Make receipt", "إنشاء استلام", "Créer réception"), icon: "box", color: "#b45309", hint: L("Dr Stock · Cr GRNI", "مدين مخزون · دائن GRNI", "Dr Stock · Cr GRNI") };
  if (dt === "Purchase Receipt") return { label: L("Make invoice", "إنشاء فاتورة", "Créer facture"), icon: "doc", color: "#0891b2", hint: L("clears GRNI → Creditors", "يقفل GRNI", "solde GRNI → Fournisseurs") };
  return { label: L("Record payment", "تسجيل دفعة", "Enregistrer paiement"), icon: "wallet", color: "#047857", hint: L("Dr Creditors · Cr Bank", "مدين موردين · دائن بنك", "Dr Fournisseurs · Cr Banque") };
});

function errMsg(e) { return (e && (e.message || e._server_messages || e.exc)) ? String(e.message || e).slice(0, 160) : L("Action failed", "فشل الإجراء", "Échec"); }
function handleRes(res) {
  if (res && res.status === "Proposed") toast.info(L("Sent for approval (material amount)", "أُرسل للموافقة (مبلغ كبير)", "Envoyé pour approbation"));
  else { toast.success(L("Done", "تم", "Fait") + (res && res.voucher_no ? " · " + res.voucher_no : "")); load(); }
}

async function primaryAction() {
  const dt = h.value.doctype;
  if (dt === "Purchase Invoice") { await openPay(); return; }
  posting.value = true;
  try {
    const fn = dt === "Purchase Order" ? "make_receipt" : "make_invoice_from_receipt";
    const arg = dt === "Purchase Order" ? { purchase_order: h.value.name } : { purchase_receipt: h.value.name };
    handleRes(await api.call(`accounting_portal.api.purchases.${fn}`, { company: currentCompany(), ...arg }));
  } catch (e) { toast.error(errMsg(e)); } finally { posting.value = false; }
}

async function openPay() {
  payRef.value = ""; payMode.value = "";
  payAmount.value = h.value.outstanding;
  payDate.value = new Date().toISOString().slice(0, 10);
  payOpen.value = true;
  if (!modes.value.length) {
    try { modes.value = await api.call("accounting_portal.api.purchases.payment_modes", { company: currentCompany() }); }
    catch { modes.value = []; }
  }
}
async function confirmPay() {
  posting.value = true;
  try {
    const m = modes.value.find((x) => x.mode === payMode.value);
    const res = await api.call("accounting_portal.api.purchases.pay_bill", {
      company: currentCompany(), invoice: h.value.name, mode: payMode.value,
      paid_from: (m && m.account) || undefined, reference_no: payRef.value || undefined, reference_date: payDate.value || undefined,
      pay_amount: (payAmount.value > 0 && payAmount.value < h.value.outstanding) ? payAmount.value : undefined,
    });
    payOpen.value = false; handleRes(res);
  } catch (e) { toast.error(errMsg(e)); } finally { posting.value = false; }
}
</script>
