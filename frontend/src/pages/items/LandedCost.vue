<template>
  <div class="space-y-3.5">
    <!-- Vouchers -->
    <div class="bg-white rounded-card border border-line overflow-hidden">
      <div class="px-4 py-3 border-b border-line flex items-center gap-2">
        <span class="w-6 h-6 rounded-lg grid place-items-center" style="background:#eff6ff"><Icon name="truck" :size="14" color="#0369a1" /></span>
        <span class="text-[13px] font-bold">{{ vm.title }}</span>
        <span class="text-[11px] text-ink-muted">· {{ vm.sub }}</span>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead>
            <tr class="border-b border-line">
              <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ vm.cols.voucher }}</th>
              <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ vm.cols.shipment }}</th>
              <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ vm.cols.freight }}</th>
              <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ vm.cols.customs }}</th>
              <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ vm.cols.duties }}</th>
              <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ vm.cols.total }}</th>
              <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ vm.cols.basis }}</th>
              <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ vm.cols.status }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="v in vm.vouchers" :key="v.id" class="border-b border-line-hair hover:bg-app-warm/60">
              <td class="px-4 py-2.5 font-mono font-semibold whitespace-nowrap">{{ v.id }}</td>
              <td class="px-4 py-2.5 whitespace-nowrap">{{ v.ship }}</td>
              <td class="px-4 py-2.5 text-end tnum">{{ v.freight }}</td>
              <td class="px-4 py-2.5 text-end tnum">{{ v.customs }}</td>
              <td class="px-4 py-2.5 text-end tnum">{{ v.duties }}</td>
              <td class="px-4 py-2.5 text-end tnum font-bold">{{ v.total }}</td>
              <td class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ v.basis }}</td>
              <td class="px-4 py-2.5">
                <span class="inline-block text-[10px] font-bold px-2 py-0.5 rounded-badge border"
                      :style="{ background: LCV_STATUS[v.status].bg, color: LCV_STATUS[v.status].fg, borderColor: LCV_STATUS[v.status].bd }">
                  {{ lcvStatusLabel(v.status, locale) }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="grid lg:grid-cols-2 gap-3.5">
      <!-- Allocation -->
      <div class="bg-white rounded-card border border-line overflow-hidden">
        <div class="px-4 py-3 border-b border-line text-[13px] font-bold">{{ vm.allocTitle }}</div>
        <table class="w-full text-[12px]">
          <thead>
            <tr class="border-b border-line">
              <th class="px-4 py-2 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ vm.cols.item }}</th>
              <th class="px-4 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ vm.cols.receipt }}</th>
              <th class="px-4 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ vm.cols.allocated }}</th>
              <th class="px-4 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ vm.cols.perUnit }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="a in vm.alloc" :key="a.item" class="border-b border-line-hair" :class="a.flagged ? 'bg-emerald-50/40' : ''">
              <td class="px-4 py-2 font-mono text-[11px]">{{ a.item }}<Icon v-if="a.flagged" name="check" :size="11" color="#047857" class="ms-1 inline" /></td>
              <td class="px-4 py-2 text-end tnum text-ink-3">{{ a.basis }}</td>
              <td class="px-4 py-2 text-end tnum font-semibold text-success-dark">{{ a.rate }}</td>
              <td class="px-4 py-2 text-end tnum font-semibold">{{ a.sku }}</td>
            </tr>
          </tbody>
        </table>
        <div class="px-4 py-2.5 bg-emerald-50 border-t border-emerald-100 text-[11px] text-emerald-800 flex items-start gap-1.5">
          <Icon name="check" :size="13" color="#047857" class="flex-shrink-0 mt-px" /><span><b>{{ vm.flagTitle }}</b> — {{ vm.flagDesc }}</span>
        </div>
      </div>

      <!-- Capitalisation journal -->
      <div class="bg-white rounded-card border border-line overflow-hidden">
        <div class="px-4 py-3 border-b border-line flex items-center gap-2"><Icon name="ledger" :size="15" color="#a33a22" /><span class="text-[13px] font-bold">{{ vm.journalTitle }}</span></div>
        <table class="w-full text-[12px]">
          <tbody>
            <tr v-for="(j, i) in vm.journal" :key="i" class="border-b border-line-hair">
              <td class="px-4 py-2.5 font-mono text-ink-2 text-[11px]">{{ j.acc }}</td>
              <td class="px-4 py-2.5 text-end tnum font-semibold">{{ j.dr || "—" }}</td>
              <td class="px-4 py-2.5 text-end tnum font-semibold">{{ j.cr || "—" }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { landedVM, LCV_STATUS, lcvStatusLabel } from "@/data/landed";

const { locale } = useI18n();
const vm = computed(() => landedVM(locale.value));
</script>
