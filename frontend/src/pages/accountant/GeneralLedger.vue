<template>
  <div class="bg-white rounded-card border border-line overflow-hidden">
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
import { GL } from "@/data/accountant";
const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
</script>
