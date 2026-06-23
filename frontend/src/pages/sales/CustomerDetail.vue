<template>
  <div v-if="d" class="max-w-[1080px] mx-auto space-y-3.5">
    <button class="inline-flex items-center gap-1.5 text-[12px] font-medium text-ink-3 hover:text-ink" @click="back">
      <span class="rtl:rotate-180"><Icon name="arrow" :size="15" /></span>{{ L("Back to customers","العودة للعملاء","Retour aux clients") }}
    </button>

    <!-- Header card -->
    <div class="bg-white rounded-[16px] border border-line px-5 py-[18px] shadow-card">
      <div class="flex items-center gap-3.5 flex-wrap">
        <span class="w-12 h-12 rounded-full grid place-items-center text-white text-[16px] font-bold flex-shrink-0" :style="{ background: AV[d.av] }">{{ initials(d.name) }}</span>
        <div class="flex-1 min-w-[180px]">
          <div class="text-[18px] font-bold">{{ d.name }}</div>
          <div class="text-[12px] text-ink-3 mt-0.5">{{ d.city }} · {{ d.phone }} · {{ d.sinceLabel }} {{ d.since }}</div>
        </div>
        <div class="text-end">
          <div class="text-[10.5px] text-ink-muted font-semibold">{{ d.creditLabel }}</div>
          <div class="text-[20px] font-bold tnum" style="color:#7c3aed">{{ d.credit }} <span class="text-[11px] text-ink-muted">MAD</span></div>
        </div>
      </div>
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-2.5 mt-[15px]">
        <div v-for="s in d.stats" :key="s.label" class="rounded-[11px] px-[13px] py-[11px]" style="background:#fafaf9;border:1px solid #f0efed">
          <div class="text-[10.5px] text-ink-muted font-semibold">{{ s.label }}</div>
          <div class="text-[18px] font-bold tnum mt-[3px]">{{ s.value }}</div>
        </div>
      </div>
    </div>

    <!-- Connections -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-2.5">
      <button v-for="cn in d.connections" :key="cn.label" class="yo-card bg-white border border-line rounded-[12px] p-3.5 shadow-card text-start" @click="go(cn.go)">
        <div class="flex items-center justify-between">
          <span class="text-[10.5px] text-ink-muted font-semibold">{{ cn.label }}</span>
          <Icon name="chevDown" :size="14" color="#cbb5ad" class="-rotate-90 rtl:rotate-90" />
        </div>
        <div class="text-[20px] font-bold tnum mt-[3px]">{{ cn.value }}</div>
      </button>
    </div>

    <div class="grid lg:grid-cols-2 gap-3.5">
      <!-- Contact & segment -->
      <div class="bg-white border border-line rounded-[14px] p-4 shadow-card">
        <div class="text-[13px] font-bold mb-3">{{ d.contactTitle }}</div>
        <div class="flex flex-col gap-2.5">
          <div v-for="ct in d.contact" :key="ct.k" class="flex items-baseline justify-between gap-3">
            <span class="text-[11.5px] text-ink-muted font-semibold flex-shrink-0">{{ ct.k }}</span>
            <span class="text-[12px] font-medium text-end">{{ ct.v }}</span>
          </div>
        </div>
      </div>

      <!-- Recent activity -->
      <div class="bg-white border border-line rounded-[14px] p-4 shadow-card">
        <div class="text-[13px] font-bold mb-3.5">{{ d.activityTitle }}</div>
        <div class="flex flex-col gap-3.5">
          <div v-for="(ac, i) in d.activity" :key="i" class="flex items-start gap-2.5">
            <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center flex-shrink-0" :style="{ background: ac.iconBg }"><Icon :name="ac.icon" :size="13" :color="ac.iconColor" /></span>
            <div class="flex-1 min-w-0">
              <div class="text-[12px] font-semibold">{{ ac.title }}</div>
              <div class="text-[11px] text-ink-muted">{{ ac.meta }}</div>
            </div>
            <span class="text-[10.5px] text-ink-muted flex-shrink-0">{{ ac.time }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Customer ledger -->
    <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
      <div class="px-4 py-3 border-b border-line-hair text-[13px] font-bold">{{ d.ledgerTitle }}</div>
      <div class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead>
            <tr style="background:#fafaf9">
              <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Date","التاريخ","Date") }}</th>
              <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Document","المستند","Document") }}</th>
              <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Type","النوع","Type") }}</th>
              <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Debit","مدين","Débit") }}</th>
              <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Credit","دائن","Crédit") }}</th>
              <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Balance","الرصيد","Solde") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(l, i) in d.ledger" :key="i" class="border-t border-line-hair">
              <td class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ l.date }}</td>
              <td class="px-4 py-2.5 font-mono font-semibold whitespace-nowrap">{{ l.doc }}</td>
              <td class="px-4 py-2.5 text-ink-3">{{ l.type }}</td>
              <td class="px-4 py-2.5 text-end tnum text-success-dark">{{ l.dr || "—" }}</td>
              <td class="px-4 py-2.5 text-end tnum text-sale">{{ l.cr || "—" }}</td>
              <td class="px-4 py-2.5 text-end tnum font-bold">{{ l.bal }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
  <div v-else class="py-20 text-center text-[12px] text-ink-muted">{{ t("common.error_loading") }}</div>
</template>

<script setup>
import { ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { initials } from "@/data/customers";
import { AV } from "@/data/orders";
import { useCustomers } from "@/composables/useCustomers";

const { t, locale } = useI18n();
const route = useRoute();
const router = useRouter();
const { loadDetail } = useCustomers();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

const d = ref(null);
async function load() { d.value = route.query.id ? await loadDetail(route.query.id, locale.value) : null; }
watch(() => [route.query.id, locale.value], load, { immediate: true });

function go(g) { if (g) router.push(g.sub ? `/accounting/${g.module}/${g.sub}` : `/accounting/${g.module}`); }
function back() { router.push({ path: "/accounting/sales/customers" }); }
</script>
