<template>
  <div class="space-y-3.5">
    <!-- Tiles -->
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
      <div v-for="ti in tiles" :key="ti.label" class="bg-white rounded-card border border-line p-3">
        <div class="text-[10px] text-ink-muted uppercase tracking-wide">{{ ti.label }}</div>
        <div class="text-[18px] font-bold tnum mt-0.5" :style="{ color: ti.color }">{{ ti.value }}</div>
      </div>
    </div>

    <div class="bg-white rounded-card border border-line overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead>
            <tr class="border-b border-line">
              <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Invoice","الفاتورة","Facture") }}</th>
              <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Customer","العميل","Client") }}</th>
              <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Net","الصافي","HT") }}</th>
              <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("VAT 20%","ضريبة","TVA") }}</th>
              <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Gross","الإجمالي","TTC") }}</th>
              <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Status","الحالة","Statut") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="inv in INVOICES" :key="inv.id" class="border-b border-line-hair hover:bg-app-warm/70 cursor-pointer" @click="open(inv.id)">
              <td class="px-4 py-2.5 font-mono font-semibold whitespace-nowrap">{{ inv.id }}</td>
              <td class="px-4 py-2.5 truncate max-w-[160px]">{{ inv.customer }}</td>
              <td class="px-4 py-2.5 text-end tnum">{{ fmt2(inv.net) }}</td>
              <td class="px-4 py-2.5 text-end tnum text-ink-3">{{ fmt2(inv.vat) }}</td>
              <td class="px-4 py-2.5 text-end tnum font-bold">{{ fmt2(inv.gross) }}</td>
              <td class="px-4 py-2.5">
                <span class="inline-block text-[10px] font-bold px-2 py-0.5 rounded-badge border"
                      :style="{ background: INV_STATUS[inv.status].bg, color: INV_STATUS[inv.status].fg, borderColor: INV_STATUS[inv.status].bd }">
                  {{ invStatusLabel(inv.status, locale) }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { INVOICES, INV_STATUS, invStatusLabel, invoiceTiles, fmt2 } from "@/data/invoices";

const { locale } = useI18n();
const router = useRouter();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const tiles = computed(() => invoiceTiles(locale.value));
function open(id) { router.push({ path: "/accounting/sales/invoices", query: { id } }); }
</script>
