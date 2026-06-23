<template>
  <div class="space-y-3.5">
    <!-- Bank accounts -->
    <div class="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
      <div v-for="acc in BANK_ACCOUNTS" :key="acc.no" class="yo-card bg-white border border-line rounded-[14px] p-4 shadow-card">
        <div class="flex items-center gap-2.5">
          <span class="w-[30px] h-[30px] rounded-[8px] grid place-items-center" :style="{ background: acc.bg }"><Icon name="bank" :size="15" :color="acc.color" /></span>
          <div class="flex-1 min-w-0">
            <div class="text-[12.5px] font-bold truncate">{{ acc.name }}</div>
            <div class="text-[10.5px] text-ink-muted">{{ acc.no }}</div>
          </div>
        </div>
        <div class="text-[20px] font-bold tnum mt-2.5">{{ acc.balance }}<span class="text-[11px] text-ink-muted ms-0.5">{{ acc.ccy }}</span></div>
      </div>
    </div>

    <!-- COD remittance batches -->
    <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
      <div class="flex items-center gap-2.5 px-[18px] py-[15px] border-b border-line-hair">
        <span class="w-7 h-7 rounded-[8px] grid place-items-center" style="background:#fff4e0"><Icon name="truck" :size="15" color="#b45309" /></span>
        <div class="flex-1">
          <div class="text-[13.5px] font-bold">{{ L("COD remittance batches","دفعات تحصيل COD","Lots d’encaissement COD") }}</div>
          <div class="text-[11px] text-ink-muted">{{ L("Carrier statements → payment entries","كشوف الناقلين → قيود الدفع","Relevés transporteurs → écritures") }}</div>
        </div>
        <button class="inline-flex items-center gap-1.5 h-8 px-3 rounded-[9px] bg-white border border-line-2 text-ink-2 text-[11.5px] font-semibold hover:bg-app-warm">
          <Icon name="plus" :size="13" />{{ L("Import statement","استيراد كشف","Importer relevé") }}
        </button>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead>
            <tr style="background:#fafaf9">
              <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Batch","الدفعة","Lot") }}</th>
              <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Carrier","الناقل","Transporteur") }}</th>
              <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Date","التاريخ","Date") }}</th>
              <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Collected","المُحصَّل","Collecté") }}</th>
              <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Fees","الرسوم","Frais") }}</th>
              <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Variance","الفرق","Écart") }}</th>
              <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Status","الحالة","Statut") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="b in BATCHES" :key="b.id" class="border-t border-line-hair hover:bg-app-warm/70 cursor-pointer" @click="open(b.id)">
              <td class="px-4 py-3 font-mono font-semibold whitespace-nowrap">{{ b.id }}</td>
              <td class="px-4 py-3 font-semibold">{{ b.carrier }}</td>
              <td class="px-4 py-3 text-ink-3 whitespace-nowrap">{{ b.date }}</td>
              <td class="px-4 py-3 text-end tnum">{{ money(b.collected) }}</td>
              <td class="px-4 py-3 text-end tnum text-sale">{{ money(b.fees) }}</td>
              <td class="px-4 py-3 text-end tnum font-bold" :class="b.variance < 0 ? 'text-sale' : 'text-ink-3'">{{ b.variance ? money(b.variance) : "0" }}</td>
              <td class="px-4 py-3">
                <span class="inline-block text-[10px] font-bold px-2 py-0.5 rounded-badge border"
                      :style="{ background: BATCH_STATUS[b.status].bg, color: BATCH_STATUS[b.status].fg, borderColor: BATCH_STATUS[b.status].bd }">
                  {{ batchStatusLabel(b.status, locale) }}
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
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { BATCHES, BATCH_STATUS, batchStatusLabel, money, BANK_ACCOUNTS } from "@/data/banking";

const { locale } = useI18n();
const router = useRouter();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
function open(id) { router.push({ path: "/accounting/banking/remittance", query: { id } }); }
</script>
