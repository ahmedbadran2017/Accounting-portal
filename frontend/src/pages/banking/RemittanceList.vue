<template>
  <div class="space-y-3.5">
    <div class="bg-white rounded-card border border-line overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead>
            <tr class="border-b border-line">
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
            <tr v-for="b in BATCHES" :key="b.id" class="border-b border-line-hair hover:bg-app-warm/70 cursor-pointer" @click="open(b.id)">
              <td class="px-4 py-2.5 font-mono font-semibold whitespace-nowrap">{{ b.id }}</td>
              <td class="px-4 py-2.5">{{ b.carrier }}</td>
              <td class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ b.date }}</td>
              <td class="px-4 py-2.5 text-end tnum">{{ money(b.collected) }}</td>
              <td class="px-4 py-2.5 text-end tnum text-sale">{{ money(b.fees) }}</td>
              <td class="px-4 py-2.5 text-end tnum font-semibold" :class="b.variance < 0 ? 'text-sale' : 'text-ink-3'">
                {{ b.variance ? money(b.variance) : "0" }}
              </td>
              <td class="px-4 py-2.5">
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
import { BATCHES, BATCH_STATUS, batchStatusLabel, money } from "@/data/banking";

const { locale } = useI18n();
const router = useRouter();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
function open(id) { router.push({ path: "/accounting/banking/remittance", query: { id } }); }
</script>
