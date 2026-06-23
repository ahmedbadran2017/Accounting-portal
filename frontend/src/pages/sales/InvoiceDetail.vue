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
        </div>
        <span class="ms-auto inline-block text-[11px] font-bold px-2.5 py-1 rounded-badge border h-fit"
              :style="{ background: st.bg, color: st.fg, borderColor: st.bd }">{{ invStatusLabel(inv.status, locale) }}</span>
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
            <tr v-for="(ln, i) in inv.lines" :key="i" class="border-b border-line-hair">
              <td class="px-4 py-2.5">{{ ln.name }}</td>
              <td class="px-4 py-2.5 text-end tnum">{{ ln.qty }}</td>
              <td class="px-4 py-2.5 text-end tnum">{{ ln.rate }}</td>
              <td class="px-4 py-2.5 text-end tnum font-semibold">{{ ln.amount }}</td>
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
      </div>
    </div>

    <!-- Posted journal -->
    <div class="bg-white rounded-card border border-line overflow-hidden">
      <div class="px-4 py-3 border-b border-line flex items-center gap-2"><Icon name="ledger" :size="15" color="#a33a22" /><span class="text-[13px] font-bold">{{ L("Posted journal","القيد المُرحَّل","Écriture passée") }}</span></div>
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
  </div>
  <div v-else class="py-20 text-center text-[12px] text-ink-muted">{{ t("common.error_loading") }}</div>
</template>

<script setup>
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { findInvoice, INV_STATUS, invStatusLabel, invoiceJournal, fmt2 } from "@/data/invoices";

const { t, locale } = useI18n();
const route = useRoute();
const router = useRouter();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

const inv = computed(() => findInvoice(route.query.id));
const st = computed(() => INV_STATUS[inv.value?.status] || INV_STATUS.paid);
const paid = computed(() => inv.value?.status === "paid");
const journal = computed(() => invoiceJournal(inv.value));
function back() { router.push({ path: "/accounting/sales/invoices" }); }
</script>
