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
            <button v-for="o in related.orders" :key="o" @click="openDoc('orders', o)" class="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-1 rounded-chip border border-line-2 bg-app-warm hover:bg-white"><Icon name="receipt" :size="11" color="#a33a22" />{{ o }}</button>
            <button v-for="dn in related.deliveries" :key="dn" @click="openDoc('challans', dn)" class="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-1 rounded-chip border border-line-2 bg-app-warm hover:bg-white"><Icon name="truck" :size="11" color="#c2410c" />{{ dn }}</button>
            <button v-for="pe in related.payments" :key="pe" @click="openDoc('payments', pe)" class="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-1 rounded-chip border border-line-2 bg-app-warm hover:bg-white"><Icon name="coins" :size="11" color="#047857" />{{ pe }}</button>
          </div>
          <div v-else class="text-[11px] text-ink-muted">{{ L("No linked documents.","لا مستندات مرتبطة.","Aucun document lié.") }}</div>
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
import { ref, computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { INV_STATUS, invStatusLabel, fmt2 } from "@/data/invoices";
import { useInvoices } from "@/composables/useInvoices";

const { t, locale } = useI18n();
const route = useRoute();
const router = useRouter();
const { loadDetail } = useInvoices();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

const vm = ref(null);
async function load() { vm.value = await loadDetail(route.query.id); }
watch(() => route.query.id, load, { immediate: true });

const inv = computed(() => vm.value?.inv || null);
const st = computed(() => INV_STATUS[inv.value?.status] || INV_STATUS.paid);
const paid = computed(() => !!vm.value?.paid);
const journal = computed(() => vm.value?.journal || []);
const related = computed(() => vm.value?.related || { orders: [], deliveries: [], payments: [] });
function openDoc(sub, id) { router.push({ path: `/accounting/sales/${sub}`, query: { id } }); }
function back() { router.push({ path: "/accounting/sales/invoices" }); }
</script>
