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
                  <td class="px-4 py-2.5"><div class="font-medium truncate max-w-[260px]">{{ it.item_name }}</div><div class="text-[10px] text-ink-muted font-mono">{{ it.item_code }}</div></td>
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
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";

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

watch(() => route.query.id, async (id) => {
  if (!id) return;
  loading.value = true; d.value = null;
  try { d.value = await api.call("accounting_portal.api.purchases.get_purchase_doc", { name: id, doctype: doctype.value, company: currentCompany() }); }
  catch { d.value = null; }
  finally { loading.value = false; }
}, { immediate: true });
</script>
