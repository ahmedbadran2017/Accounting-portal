<template>
  <div class="space-y-3.5">
    <button class="inline-flex items-center gap-1.5 text-[12px] font-semibold text-ink-3 hover:text-ink" @click="back">
      <Icon name="arrow" :size="14" class="rotate-180" />{{ L("Back", "رجوع", "Retour") }}
    </button>

    <div v-if="st.loading.value && !h.account" class="bg-white rounded-card border border-line shadow-card"><TableLoading :rows="5" /></div>
    <div v-else-if="!h.account" class="bg-white rounded-card border border-line shadow-card py-16 text-center text-[12px] text-ink-muted">{{ L("Account not found.", "الحساب غير موجود.", "Introuvable.") }}</div>

    <template v-else>
      <!-- Header -->
      <div class="bg-white rounded-card border border-line shadow-card p-5">
        <div class="flex items-start gap-3 flex-wrap">
          <span class="w-11 h-11 rounded-[12px] grid place-items-center flex-shrink-0" :style="{ background: h.type === 'Cash' ? '#fffbeb' : '#eff6ff' }"><Icon :name="h.type === 'Cash' ? 'coins' : 'bank'" :size="20" :color="h.type === 'Cash' ? '#b45309' : '#0369a1'" /></span>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 flex-wrap"><span class="text-[16px] font-bold">{{ h.name }}</span><span class="text-[10px] font-bold px-2 py-0.5 rounded-full" :style="h.type === 'Cash' ? 'background:#fffbeb;color:#b45309' : 'background:#eff6ff;color:#0369a1'">{{ h.type }}</span></div>
            <div class="text-[11px] text-ink-muted mt-0.5 font-mono">{{ h.account }}</div>
          </div>
          <div class="text-end">
            <div class="text-[10.5px] text-ink-muted font-semibold uppercase tracking-wider">{{ L("Balance", "الرصيد", "Solde") }}</div>
            <div class="text-[26px] font-extrabold tnum" :class="h.balance < 0 ? 'text-sale' : ''">{{ fmt(h.balance) }}<span class="text-[12px] text-ink-muted ms-1">{{ h.currency }}</span></div>
          </div>
        </div>
        <div class="grid grid-cols-3 gap-3 mt-4 pt-3 border-t border-line-hair">
          <div><div class="text-[10px] text-ink-muted font-semibold uppercase tracking-wider">{{ L("In (30d)", "وارد (30ي)", "Entrées 30j") }}</div><div class="text-[15px] font-bold tnum text-success-dark mt-0.5">+{{ money(h.inflow) }}</div></div>
          <div><div class="text-[10px] text-ink-muted font-semibold uppercase tracking-wider">{{ L("Out (30d)", "صادر (30ي)", "Sorties 30j") }}</div><div class="text-[15px] font-bold tnum text-sale mt-0.5">−{{ money(h.outflow) }}</div></div>
          <button @click="goRec" class="text-start"><div class="text-[10px] text-ink-muted font-semibold uppercase tracking-wider">{{ L("Unreconciled", "غير مُسوّى", "Non rappr.") }}</div><div class="text-[15px] font-bold tnum mt-0.5" :class="h.uncleared_n ? 'text-brand' : 'text-ink-muted'">{{ h.uncleared_n }} <Icon v-if="h.uncleared_n" name="arrow" :size="11" color="#c2562f" class="inline rtl:rotate-180" /></div></button>
        </div>
      </div>

      <!-- Date filter (by posting date) -->
      <div class="flex items-center gap-1.5 flex-wrap">
        <Icon name="clock" :size="13" color="#a8a29e" />
        <button v-for="p in DATE_PRESETS" :key="p.key" @click="setDatePreset(p.key)" class="text-[11px] font-semibold px-2.5 py-1 rounded-full border transition" :class="datePreset === p.key ? 'bg-ink text-white border-ink' : 'bg-white text-ink-3 border-line-2 hover:bg-app-warm'">{{ p.label() }}</button>
        <template v-if="datePreset === 'range'">
          <input type="date" v-model="dateFrom" @change="applyRange" class="h-7 border border-line-2 rounded-chip px-2 text-[11px] focus:outline-none focus:border-accent/40" />
          <span class="text-ink-muted text-[11px]">→</span>
          <input type="date" v-model="dateTo" @change="applyRange" class="h-7 border border-line-2 rounded-chip px-2 text-[11px] focus:outline-none focus:border-accent/40" />
        </template>
      </div>

      <!-- Ledger -->
      <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
        <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><Icon name="ledger" :size="14" color="#0b5c4f" /><span class="text-[12px] font-bold">{{ L("Ledger", "الحركات", "Grand livre") }}</span><span class="text-[10px] text-ink-muted">{{ (st.total.value || 0).toLocaleString() }}</span></div>
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
              <tr v-for="(e, i) in st.rows.value" :key="i" class="border-t border-line-hair hover:bg-app-warm/50 cursor-pointer" @click="openVoucher(e)">
                <td class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ e.date }}</td>
                <td class="px-4 py-2.5"><div class="font-mono font-semibold">{{ e.voucher }}</div><div class="text-[10px] text-ink-muted">{{ e.type }}</div></td>
                <td class="px-4 py-2.5 text-end tnum text-success-dark">{{ e.debit ? fmt(e.debit) : "—" }}</td>
                <td class="px-4 py-2.5 text-end tnum text-sale">{{ e.credit ? fmt(e.credit) : "—" }}</td>
                <td class="px-4 py-2.5 text-end tnum font-semibold" :class="e.balance < 0 ? 'text-sale' : ''">{{ fmt(e.balance) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <TableLoading v-if="st.loading.value" :rows="4" />
        <div v-else-if="!st.rows.value.length" class="py-10 text-center text-[12px] text-ink-muted">{{ L("No movements in this period.", "لا حركات في هذه الفترة.", "Aucun mouvement.") }}</div>
        <ServerPager :t="st" />
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import ServerPager from "@/components/ServerPager.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useServerTable } from "@/composables/useServerTable";
import { usePersistedRef } from "@/composables/usePersistedRef";

const route = useRoute();
const router = useRouter();
const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const money = (n) => { n = Number(n) || 0; const a = Math.abs(n); return a >= 1e6 ? (n / 1e6).toFixed(2) + "M" : a >= 1e3 ? Math.round(n / 1e3) + "K" : Math.round(n).toLocaleString(); };

function back() { router.push("/accounting/banking/accounts"); }
function goRec() { router.push("/accounting/banking/bankrec"); }
function openVoucher(e) {
  if (e.type === "Payment Entry") router.push({ path: "/accounting/purchases/payments", query: { id: e.voucher } });
  else if (e.type === "Journal Entry") router.push({ path: "/accounting/accountant/journals", query: { id: e.voucher } });
}

// Date filter (by posting date) — persisted, applied server-side.
const DATE_PRESETS = [
  { key: "all", label: () => L("All time", "كل الوقت", "Tout") },
  { key: "month", label: () => L("This month", "هذا الشهر", "Ce mois") },
  { key: "lastmonth", label: () => L("Last month", "الشهر الماضي", "Mois dern.") },
  { key: "quarter", label: () => L("This quarter", "هذا الربع", "Trimestre") },
  { key: "year", label: () => L("This year", "هذه السنة", "Année") },
  { key: "range", label: () => L("Range", "نطاق", "Plage") },
];
const datePreset = usePersistedRef("ap_bankacct_preset", "all");
const dateFrom = usePersistedRef("ap_bankacct_from", "");
const dateTo = usePersistedRef("ap_bankacct_to", "");
function dateBounds(key) {
  const iso = (d) => d.toISOString().slice(0, 10);
  const now = new Date(), y = now.getFullYear(), m = now.getMonth();
  if (key === "month") return [iso(new Date(y, m, 1)), iso(now)];
  if (key === "lastmonth") return [iso(new Date(y, m - 1, 1)), iso(new Date(y, m, 0))];
  if (key === "quarter") { const q = Math.floor(m / 3) * 3; return [iso(new Date(y, q, 1)), iso(now)]; }
  if (key === "year") return [iso(new Date(y, 0, 1)), iso(now)];
  if (key === "range") return [dateFrom.value || null, dateTo.value || null];
  return [null, null];
}
function dateFilter() { const [fd, td] = dateBounds(datePreset.value); return { from_date: fd || undefined, to_date: td || undefined }; }

// Server-paginated ledger — running balance is computed correctly per page.
const st = useServerTable(
  (params) => api.call("accounting_portal.api.reconciliation.get_bank_account", { company: currentCompany(), account: route.query.id, ...params })
    .then((r) => ({ ...r, rows: r.ledger || [], total: r.ledger_total || 0 })),
  { pageSize: 60, sortField: "date", sortDir: "desc", filters: dateFilter() },
);
const h = computed(() => st.extra.value || {});

function setDatePreset(k) { datePreset.value = k; if (k !== "range") st.setFilters(dateFilter()); }
function applyRange() { if (dateFrom.value && dateTo.value) st.setFilters(dateFilter()); }

watch(() => [route.query.id, currentCompany()], () => { st.page.value = 1; st.load(); }, { immediate: true });
</script>
