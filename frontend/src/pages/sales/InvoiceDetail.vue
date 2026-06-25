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
          <button v-if="inv.gross > 0" class="inline-flex items-center gap-1.5 text-[11.5px] font-semibold text-sale border border-sale/30 bg-sale/5 hover:bg-sale/10 px-2.5 py-1 rounded-chip" @click="showRefund = true">
            <Icon name="refresh" :size="13" />{{ L("Refund","استرداد","Remboursement") }}
          </button>
        </div>
      </div>
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
        <div v-if="refundError" class="text-[11.5px] text-sale mb-2">{{ refundError }}</div>
        <div class="flex justify-end gap-2">
          <button class="px-3.5 py-2 rounded-chip text-[12px] font-semibold text-ink-2 hover:bg-app-warm" @click="showRefund = false">{{ L("Cancel","إلغاء","Annuler") }}</button>
          <button class="px-4 py-2 rounded-chip text-[12px] font-bold text-white bg-sale hover:opacity-90 disabled:opacity-50" :disabled="busy" @click="createReturn">
            {{ busy ? L("Creating…","جارٍ…","…") : L("Create credit note","إنشاء","Créer") }}
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
  <div v-else class="py-20 text-center text-[12px] text-ink-muted">{{ t("common.error_loading") }}</div>
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
async function load() { vm.value = await loadDetail(route.query.id); }

async function createReturn() {
  busy.value = true; refundError.value = "";
  try {
    const res = await api.call("accounting_portal.api.sales.create_sales_return", { company: currentCompany(), invoice: inv.value.id, reason: reason.value || undefined });
    showRefund.value = false; reason.value = "";
    if (res && res.status === "Posted") toast.success(L(`Credit note ${res.voucher_no || ""} created`, `إشعار دائن ${res.voucher_no || ""} أُنشئ`, `Note de crédit ${res.voucher_no || ""} créée`));
    else toast.info(L("Recorded — awaiting an approver", "سُجّل — بانتظار موافِق", "Enregistré — en attente"));
    load();
  } catch (e) { refundError.value = (e && e.message) || L("Failed to create credit note.", "فشل الإنشاء.", "Échec."); }
  finally { busy.value = false; }
}
watch(() => route.query.id, load, { immediate: true });

const inv = computed(() => vm.value?.inv || null);
const st = computed(() => INV_STATUS[inv.value?.status] || INV_STATUS.paid);
const paid = computed(() => !!vm.value?.paid);
const journal = computed(() => vm.value?.journal || []);
const related = computed(() => vm.value?.related || { orders: [], deliveries: [], payments: [] });
function openDoc(sub, id) { router.push({ path: `/accounting/sales/${sub}`, query: { id } }); }
function back() { router.push({ path: "/accounting/sales/invoices" }); }
</script>
