<template>
  <div class="bg-white rounded-[14px] border border-line shadow-card overflow-hidden">
    <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair">
      <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#fff4e0"><Icon name="doc" :size="14" color="#b45309" /></span>
      <span class="text-[13px] font-bold">{{ L("Bills","الفواتير","Factures") }}</span>
      <span v-if="isLive !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border"
            :style="isLive ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ isLive ? "Live" : "Sample" }}</span>
      <span class="text-[11px] text-ink-muted">{{ L("Purchase Invoice · 3-way match vs PO + Goods Receipt","فاتورة شراء · مطابقة ثلاثية","Facture d’achat · rappr. 3 voies") }}</span>
    </div>
    <div class="overflow-x-auto">
      <table class="w-full text-[12px]">
        <thead>
          <tr style="background:#fafaf9">
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Bill","الفاتورة","Facture") }}</th>
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Vendor","المورّد","Fournisseur") }}</th>
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("3-way match","المطابقة","Rappr.") }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Amount","المبلغ","Montant") }}</th>
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Status","الحالة","Statut") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="b in rows" :key="b.id" class="border-t border-line-hair hover:bg-app-warm/70 cursor-pointer" @click="open(b.id)">
            <td class="px-4 py-2.5 font-mono font-semibold whitespace-nowrap">{{ b.id }}</td>
            <td class="px-4 py-2.5">{{ b.vendor }}</td>
            <td class="px-4 py-2.5">
              <span class="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-badge border"
                    :style="{ background: MATCH_META[b.match].bg, color: MATCH_META[b.match].c, borderColor: MATCH_META[b.match].bd }">
                <Icon :name="b.match === 'ok' ? 'check' : 'alert'" :size="11" />{{ matchLabel(b.match, locale) }}
              </span>
            </td>
            <td class="px-4 py-2.5 text-end font-bold tnum whitespace-nowrap" :class="b.amount.includes('-') ? 'text-sale' : ''">{{ b.amount }}</td>
            <td class="px-4 py-2.5">
              <span class="inline-block text-[10px] font-bold px-2 py-0.5 rounded-badge border"
                    :style="{ background: BILL_STATUS[b.status].bg, color: BILL_STATUS[b.status].fg, borderColor: BILL_STATUS[b.status].bd }">
                {{ billStatusLabel(b.status, locale) }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { BILLS, MATCH_META, BILL_STATUS, matchLabel, billStatusLabel } from "@/data/purchases";
import { liveOrSample, currentCompany } from "@/composables/useLive";

const { locale } = useI18n();
const router = useRouter();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

// Live ERPNext bills (fallback to the June sample).
const rows = ref(BILLS);
const isLive = ref(null);
onMounted(async () => {
  const res = await liveOrSample(
    "accounting_portal.api.purchases.list_bills", { company: currentCompany(), limit: 100 }, () => BILLS,
    (data) => data.map((r) => ({
      id: r.name, vendor: r.supplier, match: r.match,
      amount: `${r.currency} ${Number(r.amount).toLocaleString()}`, status: r.status_norm,
    })),
  );
  rows.value = res.data;
  isLive.value = res.live;
});

function open(id) { router.push({ path: "/accounting/purchases/bills", query: { id } }); }
</script>
