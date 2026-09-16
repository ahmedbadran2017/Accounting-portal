<template>
  <div class="space-y-3">
  <FiscalYearBar />
  <div class="bg-white rounded-[14px] border border-line shadow-card overflow-hidden">
    <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
      <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#f5f3ff"><Icon name="ledger" :size="14" color="#7c3aed" /></span>
      <span class="text-[13px] font-bold">{{ L("General ledger","الأستاذ العام","Grand livre") }}</span>
      <span v-if="d.total" class="text-[11px] text-ink-muted tnum">{{ d.total.toLocaleString() }} {{ L("entries","قيد","écritures") }}</span>
      <span v-if="loadError" class="text-[10px] font-bold px-1.5 py-0.5 rounded-full border" style="background:#fef2f2;color:#b91c1c;border-color:#fecaca">{{ L("Load failed","فشل التحميل","Échec") }}</span>
      <button @click="exportCsv" :disabled="!rows.length" class="ms-auto h-7 px-2.5 rounded-chip text-[11px] font-semibold text-ink-2 border border-line-2 bg-white hover:bg-app-warm inline-flex items-center gap-1 disabled:opacity-40">CSV <span class="opacity-60">({{ L("page","الصفحة","page") }})</span></button>
      <a :href="excelUrl" :class="d.total ? '' : 'pointer-events-none opacity-40'" class="h-7 px-2.5 rounded-chip text-[11px] font-bold text-white bg-ink inline-flex items-center gap-1" :title="L('Excel of the whole filtered set (up to 50,000 rows)','Excel للمجموعة المفلترة كلها (حتى 50,000 صف)','Excel de tout le filtre')"><Icon name="download" :size="12" color="#fff" />Excel <span class="opacity-70 tnum">({{ (d.total || 0).toLocaleString() }})</span></a>
    </div>

    <!-- Filters -->
    <div class="flex items-center gap-2 px-4 py-2.5 border-b border-line-hair flex-wrap bg-app-warm/20">
      <div class="min-w-[260px] flex-1 max-w-[420px]">
        <SearchSelect v-model="acctSel" :items="acctItems" :placeholder="L('Account… (all)','الحساب… (الكل)','Compte… (tous)')" inputClass="h-8 text-[12px] bg-white" />
      </div>
      <input v-model.trim="party" @keyup.enter="apply" :placeholder="L('Party…','الطرف…','Tiers…')" class="w-36 h-8 bg-white border border-line-2 rounded-[8px] px-2.5 text-[12px] focus:outline-none focus:border-accent/40" />
      <input v-model.trim="voucher" @keyup.enter="apply" :placeholder="L('Voucher…','السند…','Pièce…')" class="w-36 h-8 bg-white border border-line-2 rounded-[8px] px-2.5 text-[12px] focus:outline-none focus:border-accent/40" />
      <input v-model="fromDate" type="date" class="h-8 bg-white border border-line-2 rounded-[8px] px-2 text-[12px] focus:outline-none focus:border-accent/40" />
      <span class="text-ink-muted text-[11px]">→</span>
      <input v-model="toDate" type="date" class="h-8 bg-white border border-line-2 rounded-[8px] px-2 text-[12px] focus:outline-none focus:border-accent/40" />
      <label class="inline-flex items-center gap-1.5 text-[11.5px] text-ink-3"><input type="checkbox" v-model="includeCancelled" @change="apply" /> {{ L("Cancelled too","مع الملغي","Annulées aussi") }}</label>
      <label class="inline-flex items-center gap-1.5 text-[11.5px] text-ink-3" :title="L('One line per document instead of per GL row','سطر لكل مستند بدل كل قيد','Une ligne par document')"><input type="checkbox" v-model="groupVoucher" @change="apply" /> {{ L("Group by voucher","تجميع بالسند","Par pièce") }}</label>
      <button @click="apply" class="h-8 px-3 rounded-[8px] text-[11.5px] font-bold text-white bg-brand hover:bg-brand-dark">{{ L("Apply","تطبيق","Appliquer") }}</button>
      <button v-if="party||voucher||fromDate||toDate||acct" @click="resetFilters" class="h-8 px-2.5 rounded-[8px] text-[11.5px] font-semibold text-ink-3 border border-line-2 hover:bg-app-warm">{{ L("Clear","مسح","Effacer") }}</button>
    </div>

    <!-- Totals of the WHOLE filtered set (server-side), not of this page -->
    <div v-if="!loading && d.total" class="flex items-center gap-4 px-4 py-2 border-b border-line-hair text-[11.5px] tnum flex-wrap bg-app-warm/10">
      <span v-if="acct" class="text-ink-3">{{ L("Opening","افتتاحي","Ouverture") }} <b class="text-ink">{{ money(d.opening) }}</b></span>
      <span class="text-ink-3">{{ L("Debit","مدين","Débit") }} <b class="text-ink">{{ money(d.total_dr) }}</b></span>
      <span class="text-ink-3">{{ L("Credit","دائن","Crédit") }} <b class="text-ink">{{ money(d.total_cr) }}</b></span>
      <span v-if="acct" class="text-ink-3">{{ L("Closing","ختامي","Clôture") }} <b class="text-ink">{{ money(d.closing) }}</b></span>
      <span class="text-ink-muted">{{ d.currency }}</span>
      <span v-if="d.include_cancelled" class="text-[10px] font-bold px-1.5 py-0.5 rounded-full" style="background:#fef2f2;color:#b91c1c">{{ L("includes cancelled","يشمل الملغي","annulées incluses") }}</span>
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
            <th v-if="acct && !d.grouped" class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Balance","الرصيد","Solde") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(g, i) in rows" :key="i" class="border-b border-line-hair hover:bg-app-warm/60 cursor-pointer" :class="g.is_cancelled ? 'opacity-60 line-through' : ''" @click="openVoucher(g)">
            <td class="px-4 py-2.5 whitespace-nowrap text-ink-3">{{ g.date }}</td>
            <td class="px-4 py-2.5 font-mono whitespace-nowrap hover:text-accent-dark">{{ g.ref }}<span class="block text-[10px] text-ink-muted font-sans">{{ g.voucher_type }}</span></td>
            <td class="px-4 py-2.5 font-mono text-ink-2">{{ g.account }}</td>
            <td class="px-4 py-2.5 text-ink-muted whitespace-nowrap">{{ g.party || "—" }}</td>
            <td class="px-4 py-2.5 text-end tnum font-semibold">{{ g.dr ? money(g.dr) : "—" }}<span v-if="g.account_currency && g.account_currency !== d.currency && g.dr_acc" class="block text-[10px] text-ink-muted font-normal">{{ money(g.dr_acc) }} {{ g.account_currency }}</span></td>
            <td class="px-4 py-2.5 text-end tnum font-semibold">{{ g.cr ? money(g.cr) : "—" }}<span v-if="g.account_currency && g.account_currency !== d.currency && g.cr_acc" class="block text-[10px] text-ink-muted font-normal">{{ money(g.cr_acc) }} {{ g.account_currency }}</span></td>
            <td v-if="acct && !d.grouped" class="px-4 py-2.5 text-end tnum text-ink-3">{{ money(g.balance) }}</td>
          </tr>
          <tr v-if="!rows.length"><td :colspan="acct && !d.grouped ? 7 : 6" class="px-4 py-10 text-center text-ink-muted text-[12px]">{{ loadError || L("No entries for these filters.","لا قيود.","Aucune écriture.") }}</td></tr>
        </tbody>
      </table>
    </div>

    <!-- Server pager -->
    <div v-if="d.total > pageSize || pageSize !== 100" class="flex items-center justify-between px-4 py-3 border-t border-line-hair text-[12px] flex-wrap gap-2">
      <span class="text-ink-muted">{{ L("Showing","عرض","Affichage") }} <b class="tnum">{{ d.total ? start + 1 : 0 }}–{{ Math.min(start + pageSize, d.total) }}</b> {{ L("of","من","sur") }} <b class="tnum">{{ (d.total || 0).toLocaleString() }}</b></span>
      <div class="flex items-center gap-1.5">
        <select v-model.number="pageSize" @change="start = 0; load()" class="h-8 rounded-[8px] border border-line-2 px-1.5 text-[11.5px] bg-white"><option :value="50">50</option><option :value="100">100</option><option :value="200">200</option><option :value="500">500</option></select>
        <button class="h-8 px-3 rounded-[8px] text-[11.5px] font-semibold border border-line-2 disabled:opacity-40" :disabled="start <= 0 || loading" @click="start = Math.max(0, start - pageSize); load()">{{ L("Prev","السابق","Préc.") }}</button>
        <span class="text-ink-3 px-1 tnum">{{ Math.floor(start / pageSize) + 1 }} / {{ Math.max(1, Math.ceil((d.total || 0) / pageSize)) }}</span>
        <button class="h-8 px-3 rounded-[8px] text-[11.5px] font-semibold border border-line-2 disabled:opacity-40" :disabled="start + pageSize >= (d.total || 0) || loading" @click="start += pageSize; load()">{{ L("Next","التالي","Suiv.") }}</button>
      </div>
    </div>
  </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from "vue";
import { routeForDoc } from "@/utils/helpers";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import FiscalYearBar from "@/components/FiscalYearBar.vue";
import SearchSelect from "@/components/SearchSelect.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { usePersistedRef } from "@/composables/usePersistedRef";
import { useFiscalYear } from "@/composables/useFiscalYear";
import { useUi } from "@/composables/useUi";

const route = useRoute();
const router = useRouter();
const { locale } = useI18n();
const { entityId } = useUi();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const money = (n) => Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

// The account lives in the URL so drill-ins from the trial balance / CoA and
// bookmarks keep working; the picker just writes it there.
const acct = computed(() => route.query.account || "");
const acctSel = computed({
  get: () => acct.value,
  set: (v) => { start.value = 0; router.replace({ path: route.path, query: { ...route.query, account: v || undefined } }); },
});
const accounts = ref([]);
const acctItems = computed(() => [{ value: "", label: L("All accounts", "كل الحسابات", "Tous les comptes") }, ...accounts.value.map((a) => ({ value: a.name, label: a.name }))]);
async function loadAccounts() {
  try { accounts.value = (await api.call("accounting_portal.api.accountant.account_options", { company: currentCompany() })) || []; } catch { accounts.value = []; }
}

const d = ref({ rows: [], opening: 0, total: 0, total_dr: 0, total_cr: 0, closing: null, currency: "" });
const rows = computed(() => d.value.rows || []);
const start = ref(0);
const pageSize = usePersistedRef("ap_gl_ps", 100);
const loading = ref(true);
const loadError = ref("");
const party = usePersistedRef("ap_gl_party", "");
const voucher = usePersistedRef("ap_gl_voucher", "");
const fromDate = usePersistedRef("ap_gl_from", "");
const toDate = usePersistedRef("ap_gl_to", "");
const includeCancelled = ref(false);
// Their saved Desk report was always "Group by Voucher (Consolidated)".
const groupVoucher = usePersistedRef("ap_gl_grp", false);

async function load() {
  loading.value = true; loadError.value = "";
  try {
    d.value = await api.call("accounting_portal.api.ledger.general_ledger", {
      company: currentCompany(), account: acct.value || undefined,
      party: party.value || undefined, voucher_no: voucher.value || undefined,
      from_date: fromDate.value || undefined, to_date: toDate.value || undefined,
      start: start.value, page_size: pageSize.value, include_cancelled: includeCancelled.value ? 1 : 0,
      group_by: groupVoucher.value ? "voucher" : undefined,
    }, { fresh: true }) || { rows: [], total: 0 };
  } catch (e) { d.value = { rows: [], opening: 0, total: 0 }; loadError.value = String(e?.message || e).slice(0, 160); }
  finally { loading.value = false; }
}
function apply() { start.value = 0; load(); }
const fyc = useFiscalYear();
// A fiscal-year pick sets the ledger's date window (opening is computed before it).
watch(fyc.selected, () => {
  const f = fyc.fy.value;
  fromDate.value = f.from || "";
  toDate.value = f.to || "";
  apply();
});
onMounted(() => {
  // Deep links: ?voucher=… (from the shipment pipeline) and ?account=… (drill-ins).
  if (route.query.voucher) voucher.value = String(route.query.voucher);
  if (route.query.party) party.value = String(route.query.party);
  loadAccounts(); load();
});
watch(() => route.query.account, () => { start.value = 0; load(); });
watch(entityId, () => { start.value = 0; loadAccounts(); load(); });
function resetFilters() {
  party.value = ""; voucher.value = ""; fromDate.value = ""; toDate.value = ""; includeCancelled.value = false; start.value = 0;
  if (acct.value) router.replace({ path: route.path, query: {} }); else load();
}

function openVoucher(g) {
  const to = routeForDoc(g.voucher_type, g.ref, g.party_type);
  if (to) router.push(to);
}

// Server-built .xlsx of the WHOLE filtered set (the CSV button is this page only).
const excelUrl = computed(() => {
  const q = new URLSearchParams({ company: currentCompany(), account: acct.value || "", party: party.value || "", voucher_no: voucher.value || "",
    from_date: fromDate.value || "", to_date: toDate.value || "", include_cancelled: includeCancelled.value ? "1" : "0",
    group_by: groupVoucher.value ? "voucher" : "" });
  return `/api/method/accounting_portal.api.export.gl_xlsx?${q.toString()}`;
});

function exportCsv() {
  const head = ["Date", "Voucher Type", "Voucher", "Account", "Party", "Debit", "Credit", "Account currency", "Debit (acc ccy)", "Credit (acc ccy)", "Cost center", "Remarks", acct.value ? "Balance" : ""].filter(Boolean);
  const lines = rows.value.map((g) => [g.date, g.voucher_type, g.ref, g.account, g.party || "", g.dr || 0, g.cr || 0, g.account_currency || "", g.dr_acc || 0, g.cr_acc || 0, g.cost_center || "", (g.remarks || "").replace(/\s+/g, " "), acct.value ? g.balance : ""]
    .filter((_, i) => acct.value || i < 12).map((v) => `"${String(v).replace(/"/g, '""')}"`).join(","));
  const csv = [head.join(","), ...lines].join("\n");
  const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8;" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `general-ledger${acct.value ? "-" + acct.value.split(" ")[0] : ""}-p${Math.floor(start.value / pageSize.value) + 1}.csv`;
  a.click(); URL.revokeObjectURL(a.href);
}
</script>
