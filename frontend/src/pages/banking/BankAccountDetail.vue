<template>
  <div class="space-y-3.5">
    <button class="inline-flex items-center gap-1.5 text-[12px] font-semibold text-ink-3 hover:text-ink" @click="back">
      <Icon name="arrow" :size="14" class="rotate-180" />{{ L("Back", "رجوع", "Retour") }}
    </button>

    <div v-if="loading" class="bg-white rounded-card border border-line shadow-card"><TableLoading :rows="5" /></div>
    <div v-else-if="!d" class="bg-white rounded-card border border-line shadow-card py-16 text-center text-[12px] text-ink-muted">{{ L("Account not found.", "الحساب غير موجود.", "Introuvable.") }}</div>

    <template v-else>
      <!-- Header -->
      <div class="bg-white rounded-card border border-line shadow-card p-5">
        <div class="flex items-start gap-3 flex-wrap">
          <span class="w-11 h-11 rounded-[12px] grid place-items-center flex-shrink-0" :style="{ background: d.type === 'Cash' ? '#fffbeb' : '#eff6ff' }"><Icon :name="d.type === 'Cash' ? 'coins' : 'bank'" :size="20" :color="d.type === 'Cash' ? '#b45309' : '#0369a1'" /></span>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 flex-wrap"><span class="text-[16px] font-bold">{{ d.name }}</span><span class="text-[10px] font-bold px-2 py-0.5 rounded-full" :style="d.type === 'Cash' ? 'background:#fffbeb;color:#b45309' : 'background:#eff6ff;color:#0369a1'">{{ d.type }}</span></div>
            <div class="text-[11px] text-ink-muted mt-0.5 font-mono">{{ d.account }}</div>
          </div>
          <div class="text-end">
            <div class="text-[10.5px] text-ink-muted font-semibold uppercase tracking-wider">{{ L("Balance", "الرصيد", "Solde") }}</div>
            <div class="text-[26px] font-extrabold tnum" :class="d.balance < 0 ? 'text-sale' : ''">{{ fmt(d.balance) }}<span class="text-[12px] text-ink-muted ms-1">{{ d.currency }}</span></div>
          </div>
        </div>
        <div class="grid grid-cols-3 gap-3 mt-4 pt-3 border-t border-line-hair">
          <div><div class="text-[10px] text-ink-muted font-semibold uppercase tracking-wider">{{ L("In (30d)", "وارد (30ي)", "Entrées 30j") }}</div><div class="text-[15px] font-bold tnum text-success-dark mt-0.5">+{{ money(d.inflow) }}</div></div>
          <div><div class="text-[10px] text-ink-muted font-semibold uppercase tracking-wider">{{ L("Out (30d)", "صادر (30ي)", "Sorties 30j") }}</div><div class="text-[15px] font-bold tnum text-sale mt-0.5">−{{ money(d.outflow) }}</div></div>
          <button @click="goRec" class="text-start"><div class="text-[10px] text-ink-muted font-semibold uppercase tracking-wider">{{ L("Unreconciled", "غير مُسوّى", "Non rappr.") }}</div><div class="text-[15px] font-bold tnum mt-0.5" :class="d.uncleared_n ? 'text-brand' : 'text-ink-muted'">{{ d.uncleared_n }} <Icon v-if="d.uncleared_n" name="arrow" :size="11" color="#c2562f" class="inline rtl:rotate-180" /></div></button>
        </div>
      </div>

      <!-- Ledger -->
      <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
        <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><Icon name="ledger" :size="14" color="#0b5c4f" /><span class="text-[12px] font-bold">{{ L("Recent ledger", "آخر الحركات", "Grand livre récent") }}</span><span class="text-[10px] text-ink-muted">{{ d.ledger.length }}</span></div>
        <div class="overflow-x-auto">
          <table class="w-full text-[12px]">
            <thead><tr style="background:#fafaf9">
              <th class="px-4 py-2 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Date", "التاريخ", "Date") }}</th>
              <th class="px-4 py-2 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Voucher", "المستند", "Pièce") }}</th>
              <th class="px-4 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("In", "وارد", "Entrée") }}</th>
              <th class="px-4 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Out", "صادر", "Sortie") }}</th>
              <th class="px-4 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Balance", "الرصيد", "Solde") }}</th>
            </tr></thead>
            <tbody>
              <tr v-for="(e, i) in d.ledger" :key="i" class="border-t border-line-hair hover:bg-app-warm/50 cursor-pointer" @click="openVoucher(e)">
                <td class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ e.date }}</td>
                <td class="px-4 py-2.5"><div class="font-mono font-semibold">{{ e.voucher }}</div><div class="text-[10px] text-ink-muted">{{ e.type }}</div></td>
                <td class="px-4 py-2.5 text-end tnum text-success-dark">{{ e.debit ? fmt(e.debit) : "—" }}</td>
                <td class="px-4 py-2.5 text-end tnum text-sale">{{ e.credit ? fmt(e.credit) : "—" }}</td>
                <td class="px-4 py-2.5 text-end tnum font-semibold" :class="e.balance < 0 ? 'text-sale' : ''">{{ fmt(e.balance) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";

const route = useRoute();
const router = useRouter();
const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const money = (n) => { n = Number(n) || 0; const a = Math.abs(n); return a >= 1e6 ? (n / 1e6).toFixed(2) + "M" : a >= 1e3 ? Math.round(n / 1e3) + "K" : Math.round(n).toLocaleString(); };

const d = ref(null);
const loading = ref(true);
function back() { router.push("/accounting/banking/accounts"); }
function goRec() { router.push("/accounting/banking/bankrec"); }
function openVoucher(e) {
  if (e.type === "Payment Entry") router.push({ path: "/accounting/purchases/payments", query: { id: e.voucher } });
  else if (e.type === "Journal Entry") router.push({ path: "/accounting/accountant/journals", query: { id: e.voucher } });
}
async function load() {
  const id = route.query.id;
  if (!id) { loading.value = false; return; }
  loading.value = true; d.value = null;
  try { d.value = await api.call("accounting_portal.api.reconciliation.get_bank_account", { company: currentCompany(), account: id }); }
  catch { d.value = null; }
  finally { loading.value = false; }
  if (!d.value) router.replace({ path: "/accounting/banking/accounts", query: {} });
}
watch(() => route.query.id, load, { immediate: true });
</script>
