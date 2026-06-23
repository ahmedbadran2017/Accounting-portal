<template>
  <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
    <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair">
      <span class="w-7 h-7 rounded-[8px] grid place-items-center" style="background:#ecfdf5"><Icon name="bank" :size="14" color="#047857" /></span>
      <div class="flex-1">
        <div class="text-[13px] font-bold">{{ L("Bank reconciliation","المطابقة البنكية","Rapprochement bancaire") }} · {{ BANK_REC.bank }}</div>
        <div class="text-[11px] text-ink-muted">{{ L("Feed imported · matched to the ledger","الكشف مُستورد · مطابق للأستاذ","Relevé importé · rapproché au GL") }} · {{ BANK_REC.matchedPct }} {{ L("tied","مطابق","rapproché") }} · {{ BANK_REC.unmatched }} {{ L("need review","تحتاج مراجعة","à revoir") }}</div>
      </div>
      <button class="inline-flex items-center gap-1.5 h-8 px-3 rounded-[9px] bg-white border border-line-2 text-ink-2 text-[11.5px] font-semibold hover:bg-app-warm">
        <Icon name="plus" :size="13" />{{ L("Import feed","استيراد كشف","Importer relevé") }}
      </button>
    </div>
    <div class="overflow-x-auto">
      <table class="w-full text-[12px]">
        <thead>
          <tr style="background:#fafaf9">
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Date","التاريخ","Date") }}</th>
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Description","الوصف","Description") }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Amount","المبلغ","Montant") }}</th>
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("To account","إلى حساب","Vers compte") }}</th>
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Status","الحالة","Statut") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(r, i) in BANK_REC.rows" :key="i" class="border-t border-line-hair" :class="r.status === 'unmatched' ? 'bg-amber-50/30' : ''">
            <td class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ r.date }}</td>
            <td class="px-4 py-2.5 font-medium">{{ r.desc }}</td>
            <td class="px-4 py-2.5 text-end tnum font-bold whitespace-nowrap" :style="{ color: r.amount.startsWith('+') ? '#047857' : '#be123c' }">{{ r.amount }}</td>
            <td class="px-4 py-2.5 text-ink-3 font-mono whitespace-nowrap">{{ r.to }}</td>
            <td class="px-4 py-2.5">
              <span class="inline-block text-[10px] font-bold px-2 py-0.5 rounded-badge border" :style="{ background: REC_STATUS[r.status].bg, color: REC_STATUS[r.status].fg, borderColor: REC_STATUS[r.status].bd }">{{ recStatusLabel(r.status, locale) }}</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { BANK_REC, REC_STATUS, recStatusLabel } from "@/data/banking";
const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
</script>
