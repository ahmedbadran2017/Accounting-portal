<template>
  <div class="bg-white rounded-[14px] border border-line shadow-card overflow-hidden">
    <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
      <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#f5f3ff"><Icon name="ledger" :size="14" color="#7c3aed" /></span>
      <span class="text-[13px] font-bold">{{ L("General ledger","الأستاذ العام","Grand livre") }}</span>
      <span v-if="acct" class="inline-flex items-center gap-1.5 text-[11px] font-bold px-2 py-0.5 rounded-chip bg-app-warm text-ink-2"><span class="font-mono">{{ acct }}</span><button class="text-ink-muted hover:text-sale" @click="clearAcct">✕</button></span>
      <span v-if="isLive !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="isLive ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ isLive ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échant.") }}</span>
      <button @click="exportCsv" class="ms-auto h-7 px-2.5 rounded-chip text-[11px] font-bold text-white bg-ink inline-flex items-center gap-1"><Icon name="doc" :size="12" color="#fff" />CSV</button>
    </div>

    <!-- Filters -->
    <div class="flex items-center gap-2 px-4 py-2.5 border-b border-line-hair flex-wrap bg-app-warm/20">
      <input v-model.trim="party" @keyup.enter="load" :placeholder="L('Party…','الطرف…','Tiers…')" class="w-32 h-8 bg-white border border-line-2 rounded-[8px] px-2.5 text-[12px] focus:outline-none focus:border-accent/40" />
      <input v-model.trim="voucher" @keyup.enter="load" :placeholder="L('Voucher…','السند…','Pièce…')" class="w-32 h-8 bg-white border border-line-2 rounded-[8px] px-2.5 text-[12px] focus:outline-none focus:border-accent/40" />
      <input v-model="fromDate" type="date" class="h-8 bg-white border border-line-2 rounded-[8px] px-2 text-[12px] focus:outline-none focus:border-accent/40" />
      <span class="text-ink-muted text-[11px]">→</span>
      <input v-model="toDate" type="date" class="h-8 bg-white border border-line-2 rounded-[8px] px-2 text-[12px] focus:outline-none focus:border-accent/40" />
      <button @click="load" class="h-8 px-3 rounded-[8px] text-[11.5px] font-bold text-white bg-brand hover:bg-brand-dark">{{ L("Apply","تطبيق","Appliquer") }}</button>
      <button v-if="party||voucher||fromDate||toDate" @click="resetFilters" class="h-8 px-2.5 rounded-[8px] text-[11.5px] font-semibold text-ink-3 border border-line-2 hover:bg-app-warm">{{ L("Clear","مسح","Effacer") }}</button>
      <span v-if="acct" class="ms-auto text-[11px] text-ink-muted tnum">{{ L("Opening","افتتاحي","Ouverture") }}: {{ money(d.opening) }} · {{ L("Dr","مدين","Dt") }} {{ money(d.total_dr) }} · {{ L("Cr","دائن","Ct") }} {{ money(d.total_cr) }}</span>
    </div>

    <div class="overflow-x-auto">
      <TableLoading v-if="loading" :rows="10" />
      <table v-else class="w-full text-[12px]">
        <thead>
          <tr class="border-b border-line">
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Date","التاريخ","Date") }}</th>
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Voucher","السند","Pièce") }}</th>
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Account","الحساب","Compte") }}</th>
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Party","الطرف","Tiers") }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Debit","مدين","Débit") }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Credit","دائن","Crédit") }}</th>
            <th v-if="acct" class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Balance","الرصيد","Solde") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(g, i) in pagedRows" :key="i" class="border-b border-line-hair hover:bg-app-warm/60 cursor-pointer" @click="openVoucher(g)">
            <td class="px-4 py-2.5 whitespace-nowrap text-ink-3">{{ g.date }}</td>
            <td class="px-4 py-2.5 font-mono whitespace-nowrap hover:text-accent-dark">{{ g.ref }}</td>
            <td class="px-4 py-2.5 font-mono text-ink-2">{{ g.account }}</td>
            <td class="px-4 py-2.5 text-ink-muted whitespace-nowrap">{{ g.party || "—" }}</td>
            <td class="px-4 py-2.5 text-end tnum font-semibold">{{ g.dr ? money(g.dr) : "—" }}</td>
            <td class="px-4 py-2.5 text-end tnum font-semibold">{{ g.cr ? money(g.cr) : "—" }}</td>
            <td v-if="acct" class="px-4 py-2.5 text-end tnum text-ink-3">{{ money(g.balance) }}</td>
          </tr>
          <tr v-if="!rows.length"><td :colspan="acct ? 7 : 6" class="px-4 py-10 text-center text-ink-muted text-[12px]">{{ L("No entries for these filters.","لا قيود.","Aucune écriture.") }}</td></tr>
        </tbody>
      </table>
    </div>

    <!-- Client pager over the loaded rows (running balance is server-computed) -->
    <div v-if="rows.length > pageSize" class="flex items-center justify-between px-4 py-3 border-t border-line-hair text-[12px]">
      <span class="text-ink-muted">{{ L("Showing","عرض","Affichage") }} <b>{{ (page - 1) * pageSize + 1 }}–{{ Math.min(page * pageSize, rows.length) }}</b> {{ L("of","من","sur") }} <b>{{ rows.length.toLocaleString() }}</b></span>
      <div class="flex items-center gap-1.5">
        <button class="h-8 px-3 rounded-[8px] text-[11.5px] font-semibold border border-line-2 disabled:opacity-40" :disabled="page <= 1" @click="page--">{{ L("Prev","السابق","Préc.") }}</button>
        <span class="text-ink-3 px-1">{{ page }} / {{ totalPages }}</span>
        <button class="h-8 px-3 rounded-[8px] text-[11.5px] font-semibold border border-line-2 disabled:opacity-40" :disabled="page >= totalPages" @click="page++">{{ L("Next","التالي","Suiv.") }}</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { usePersistedRef } from "@/composables/usePersistedRef";

const route = useRoute();
const router = useRouter();
const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const money = (n) => Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const acct = computed(() => route.query.account || "");
const d = ref({ rows: [], opening: 0, total_dr: 0, total_cr: 0 });
const rows = computed(() => d.value.rows || []);
const pageSize = 100;
const page = ref(1);
const totalPages = computed(() => Math.max(1, Math.ceil(rows.value.length / pageSize)));
const pagedRows = computed(() => rows.value.slice((page.value - 1) * pageSize, page.value * pageSize));
const isLive = ref(null);
const loading = ref(true);
const party = usePersistedRef("ap_gl_party", "");
const voucher = usePersistedRef("ap_gl_voucher", "");
const fromDate = usePersistedRef("ap_gl_from", "");
const toDate = usePersistedRef("ap_gl_to", "");

async function load() {
  loading.value = true;
  try {
    d.value = await api.call("accounting_portal.api.ledger.general_ledger", {
      company: currentCompany(), account: acct.value || undefined,
      party: party.value || undefined, voucher_no: voucher.value || undefined,
      from_date: fromDate.value || undefined, to_date: toDate.value || undefined,
      limit: acct.value ? 1000 : 200,
    });
    page.value = 1;
    isLive.value = true;
  } catch { d.value = { rows: [], opening: 0 }; isLive.value = false; }
  finally { loading.value = false; }
}
onMounted(load);
watch(() => route.query.account, load);
function clearAcct() { router.replace({ path: "/accounting/accountant/gl", query: {} }); }
function resetFilters() { party.value = ""; voucher.value = ""; fromDate.value = ""; toDate.value = ""; load(); }

const VTYPE_ROUTE = {
  "Sales Invoice": "sales/invoices", "Sales Order": "sales/orders", "Delivery Note": "sales/challans",
  "Purchase Invoice": "purchases/bills", "Payment Entry": "purchases/payments", "Journal Entry": "accountant/journals",
};
function openVoucher(g) {
  const r = VTYPE_ROUTE[g.voucher_type];
  if (r && g.ref) router.push({ path: `/accounting/${r}`, query: { id: g.ref } });
}

function exportCsv() {
  const head = ["Date", "Voucher Type", "Voucher", "Account", "Party", "Debit", "Credit", acct.value ? "Balance" : ""].filter(Boolean);
  const lines = rows.value.map((g) => [g.date, g.voucher_type, g.ref, g.account, g.party || "", g.dr || 0, g.cr || 0, acct.value ? g.balance : ""]
    .filter((_, i) => acct.value || i < 7).map((v) => `"${String(v).replace(/"/g, '""')}"`).join(","));
  const csv = [head.join(","), ...lines].join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `general-ledger${acct.value ? "-" + acct.value.split(" ")[0] : ""}.csv`;
  a.click(); URL.revokeObjectURL(a.href);
}
</script>
