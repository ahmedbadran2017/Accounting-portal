<template>
  <div class="bg-white rounded-[14px] border border-line shadow-card overflow-hidden">
    <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair">
      <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#f5f3ff"><Icon name="ledger" :size="14" color="#7c3aed" /></span>
      <span class="text-[13px] font-bold">{{ L("General ledger","الأستاذ العام","Grand livre") }}</span>
      <span class="text-[11px] text-ink-muted">{{ L("Every posting, reconciled to source","كل قيد، مطابق للمصدر","Chaque écriture, rapprochée à la source") }}</span>
    </div>
    <div class="overflow-x-auto">
      <table class="w-full text-[12px]">
        <thead>
          <tr class="border-b border-line">
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Date","التاريخ","Date") }}</th>
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Voucher","السند","Pièce") }}</th>
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Account","الحساب","Compte") }}</th>
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Dimension","البُعد","Dimension") }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Debit","مدين","Débit") }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Credit","دائن","Crédit") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(g, i) in GL" :key="i" class="border-b border-line-hair hover:bg-app-warm/60">
            <td class="px-4 py-2.5 whitespace-nowrap text-ink-3">{{ g.date }}</td>
            <td class="px-4 py-2.5 font-mono whitespace-nowrap">{{ g.ref }}</td>
            <td class="px-4 py-2.5 font-mono text-ink-2">{{ g.account }}</td>
            <td class="px-4 py-2.5 text-ink-muted whitespace-nowrap">{{ g.dim }}</td>
            <td class="px-4 py-2.5 text-end tnum font-semibold">{{ g.dr || "—" }}</td>
            <td class="px-4 py-2.5 text-end tnum font-semibold">{{ g.cr || "—" }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { GL } from "@/data/accountant";
const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
</script>
