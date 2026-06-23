<template>
  <div v-if="b" class="space-y-3.5">
    <button class="inline-flex items-center gap-1.5 text-[12px] font-medium text-ink-3 hover:text-ink" @click="back">
      <span class="rtl:rotate-180"><Icon name="arrow" :size="15" /></span>{{ L("Back to bills","العودة للفواتير","Retour aux factures") }}
    </button>

    <div class="bg-white rounded-card border border-line p-5">
      <div class="flex flex-wrap items-start gap-3">
        <div class="min-w-0">
          <div class="text-[17px] font-bold tracking-tight font-mono">{{ b.id }}</div>
          <div class="text-[12.5px] text-ink-3">{{ b.vendor }}</div>
        </div>
        <div class="ms-auto text-end">
          <div class="text-[22px] font-bold tnum" :class="b.amount.includes('-') ? 'text-sale' : ''">{{ b.amount }}</div>
          <span class="inline-block text-[10px] font-bold px-2 py-0.5 rounded-badge border mt-1"
                :style="{ background: BILL_STATUS[b.status].bg, color: BILL_STATUS[b.status].fg, borderColor: BILL_STATUS[b.status].bd }">
            {{ billStatusLabel(b.status, locale) }}
          </span>
        </div>
      </div>
    </div>

    <!-- 3-way match panel -->
    <div class="bg-white rounded-card border border-line p-4">
      <div class="text-[13px] font-bold mb-3">{{ L("3-way match","المطابقة الثلاثية","Rapprochement 3 voies") }}</div>
      <div class="grid grid-cols-3 gap-2.5">
        <div v-for="leg in legs" :key="leg.key" class="rounded-card border p-3 text-center"
             :style="{ borderColor: leg.ok ? '#a7f3d0' : '#fecaca', background: leg.ok ? '#ecfdf5' : '#fef2f2' }">
          <Icon :name="leg.ok ? 'check' : 'alert'" :size="18" :color="leg.ok ? '#047857' : '#be123c'" />
          <div class="text-[11.5px] font-semibold mt-1.5">{{ leg.label }}</div>
          <div class="text-[10px] mt-0.5" :style="{ color: leg.ok ? '#047857' : '#be123c' }">{{ leg.state }}</div>
        </div>
      </div>
      <div class="mt-3 pt-2.5 border-t border-line text-[11px]" :class="matched ? 'text-success-dark' : 'text-sale'">
        {{ matched
          ? L("PO, Goods Receipt and Invoice agree — cleared to pay.","أمر الشراء وسند الاستلام والفاتورة متطابقة — جاهزة للدفع.","BC, réception et facture concordent — bon à payer.")
          : L("Quantity / price mismatch vs PO + Goods Receipt — held for review.","فرق كمية/سعر مقابل أمر الشراء والاستلام — موقوفة للمراجعة.","Écart quantité/prix vs BC + réception — en attente.") }}
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
import { findBill, BILL_STATUS, billStatusLabel } from "@/data/purchases";

const { t, locale } = useI18n();
const route = useRoute();
const router = useRouter();

const b = computed(() => findBill(route.query.id));
const matched = computed(() => b.value?.match === "ok");
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

const legs = computed(() => {
  const ok = matched.value;
  return [
    { key: "po", label: L("Purchase order", "أمر الشراء", "Bon de commande"), ok: true, state: L("Linked", "مرتبط", "Lié") },
    { key: "grn", label: L("Goods receipt", "سند الاستلام", "Réception"), ok: ok, state: ok ? L("Received", "مستلَم", "Reçu") : L("Qty short", "نقص كمية", "Qté manquante") },
    { key: "inv", label: L("Invoice", "الفاتورة", "Facture"), ok: ok, state: ok ? L("Matched", "مطابقة", "Rapprochée") : L("Price gap", "فرق سعر", "Écart prix") },
  ];
});

// Bill posts to Creditors. Returns reverse it (negative amount).
const journal = computed(() => {
  if (!b.value) return [];
  const isReturn = b.value.amount.includes("-");
  const amt = b.value.amount.replace(/[^0-9.\-]/g, "");
  if (isReturn) return [
    { acc: "320.01 Creditors", dr: amt.replace("-", ""), cr: "" },
    { acc: "71.801 Cost of Goods Sold / Stock", dr: "", cr: amt.replace("-", "") },
  ];
  return [
    { acc: "153.01 Stock in Hand / Expense", dr: amt, cr: "" },
    { acc: "320.01 Creditors", dr: "", cr: amt },
  ];
});

function back() { router.push({ path: "/accounting/purchases/bills" }); }
</script>
