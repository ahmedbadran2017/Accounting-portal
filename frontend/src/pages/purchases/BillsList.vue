<template>
  <div class="space-y-3.5">
    <div class="flex items-center gap-2">
      <div class="relative flex-1 max-w-xs">
        <span class="absolute inset-block-0 flex items-center ps-2.5 text-ink-muted"><Icon name="search" :size="15" /></span>
        <input v-model.trim="search" :placeholder="t('module.search')"
               class="w-full bg-white border border-line-2 rounded-chip ps-8 pe-3 py-1.5 text-[12px] focus:outline-none focus:border-accent/40" />
      </div>
      <button class="inline-flex items-center gap-1.5 text-[12px] font-semibold text-white bg-accent hover:bg-accent-dark px-3 py-1.5 rounded-chip shadow-prim ms-auto">
        <Icon name="plus" :size="14" />{{ t("module.new") }}
      </button>
    </div>

    <div class="bg-white rounded-card border border-line overflow-hidden">
      <table class="w-full text-[12px]">
        <thead>
          <tr class="border-b border-line">
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Bill","الفاتورة","Facture") }}</th>
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Vendor","المورّد","Fournisseur") }}</th>
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("3-way match","المطابقة","Rappr.") }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Amount","المبلغ","Montant") }}</th>
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Status","الحالة","Statut") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="b in rows" :key="b.id" class="border-b border-line-hair hover:bg-app-warm/70 cursor-pointer" @click="open(b.id)">
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
import { ref, computed } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { BILLS, MATCH_META, BILL_STATUS, matchLabel, billStatusLabel } from "@/data/purchases";

const { t, locale } = useI18n();
const router = useRouter();
const search = ref("");
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

const rows = computed(() => {
  const q = search.value.toLowerCase();
  return q ? BILLS.filter((b) => (b.id + b.vendor).toLowerCase().includes(q)) : BILLS;
});
function open(id) { router.push({ path: "/accounting/purchases/bills", query: { id } }); }
</script>
