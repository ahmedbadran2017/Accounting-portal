<template>
  <div class="space-y-3.5">
    <DateFilterBar :df="df" />

    <!-- Headline cards -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <button type="button" class="text-start rounded-card transition focus:outline-none" :class="mode === 'deposits' && !carrier ? 'ring-2 ring-teal-500/50' : 'hover:ring-2 hover:ring-teal-500/20'" @click="setMode('deposits', null)">
        <StatCard :label="L('Collected by carriers','حصّلته الشحن','Encaissé transporteurs')" :value="money(s.total_collected)" :sub="ccy + ' · ' + (s.deposits || 0).toLocaleString() + ' ' + L('deposits','إيداع','dépôts')" icon="truck" color="#0f766e" glow="#5dcaa5" tint="#e1f5ee" valueColor="#0f766e" />
      </button>
      <button type="button" class="text-start rounded-card transition focus:outline-none" :class="mode === 'sweeps' && !carrier ? 'ring-2 ring-sky-500/50' : 'hover:ring-2 hover:ring-sky-500/20'" @click="setMode('sweeps', null)">
        <StatCard :label="L('Swept to your bank','نزل بنككم','Versé en banque')" :value="money(swept)" :sub="ccy + ' · ' + L('view transfers','اعرض التحويلات','voir virements')" icon="bank" color="#0369a1" glow="#85b7eb" tint="#eff6ff" valueColor="#0369a1" />
      </button>
      <StatCard :label="L('Still with carriers','لسه مع الشحن','Encore chez transp.')" :value="money(s.total_held)" :sub="L('not yet remitted','لم تُحوَّل بعد','non versé')" icon="clock" color="#b45309" glow="#f59e0b" tint="#fffbeb" :valueColor="s.total_held ? '#b45309' : undefined" />
      <StatCard :label="L('Carriers','شركات الشحن','Transporteurs')" :value="(s.by_carrier || []).length.toLocaleString()" :sub="topCarrier" icon="layers" color="#7c3aed" glow="#a78bfa" tint="#f5f3ff" />
    </div>

    <!-- Per-carrier breakdown -->
    <div class="bg-white rounded-card border border-line overflow-hidden shadow-card">
      <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2">
        <Icon name="truck" :size="14" color="#0b5c4f" /><span class="text-[12px] font-bold">{{ L("By carrier","حسب الناقل","Par transporteur") }}</span>
        <span v-if="loadingSum" class="text-[10px] text-ink-muted">…</span>
      </div>
      <table class="w-full text-[12px]">
        <thead><tr style="background:#fafaf9">
          <th class="px-4 py-2 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Carrier","الناقل","Transporteur") }}</th>
          <th class="px-4 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Collected","حصّل","Encaissé") }}</th>
          <th class="px-4 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Swept to bank","نزل البنك","Versé") }}</th>
          <th class="px-4 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Still held","لسه معاه","Retenu") }}</th>
          <th class="px-4 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Last","آخر","Dernier") }}</th>
        </tr></thead>
        <tbody>
          <tr v-for="c in (s.by_carrier || [])" :key="c.carrier" class="border-t border-line-hair hover:bg-app-warm/60" :class="carrier === c.carrier ? 'bg-accent/5' : ''">
            <td class="px-4 py-2.5 font-semibold">{{ carrierLabel(c.carrier) }}<Icon v-if="carrier === c.carrier" name="check" :size="11" color="#0b5c4f" class="inline ms-1" /></td>
            <td class="px-4 py-2.5 text-end tnum font-bold text-success-dark cursor-pointer hover:underline" :title="L('View deposits','اعرض الإيداعات','Voir dépôts')" @click="setMode('deposits', c.carrier)">{{ fmt(c.collected) }}</td>
            <td class="px-4 py-2.5 text-end tnum cursor-pointer hover:underline" :class="mode === 'sweeps' && carrier === c.carrier ? 'text-sky-700 font-semibold' : 'text-ink-2'" :title="L('View transfers to bank','اعرض التحويلات للبنك','Voir virements')" @click="setMode('sweeps', c.carrier)">{{ fmt(c.swept) }}</td>
            <td class="px-4 py-2.5 text-end tnum" :class="c.held > 0 ? 'text-amber-700 font-semibold' : 'text-ink-muted'">{{ fmt(c.held) }}</td>
            <td class="px-4 py-2.5 text-end text-ink-3 text-[11px] whitespace-nowrap">{{ c.last_date || "—" }}</td>
          </tr>
          <tr v-if="!loadingSum && !(s.by_carrier || []).length"><td colspan="5" class="px-4 py-8 text-center text-ink-muted text-[12px]">{{ L("No carrier settlements in this period.","لا تحصيلات شحن في هذه الفترة.","Aucun règlement.") }}</td></tr>
        </tbody>
      </table>
    </div>

    <!-- Transactions feed (deposits OR sweeps, by mode) -->
    <div class="bg-white rounded-card border border-line overflow-hidden shadow-card">
      <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
        <Icon :name="isSweeps ? 'bank' : 'coins'" :size="14" :color="isSweeps ? '#0369a1' : '#0b5c4f'" />
        <span class="text-[12px] font-bold">{{ isSweeps ? L("Swept to your bank","تحويلات لبنككم","Versés en banque") : L("Carrier deposits","إيداعات الشحن","Dépôts transporteur") }}</span>
        <span v-if="carrier" class="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-chip bg-app-warm text-ink-2">{{ carrierLabel(carrier) }}<button class="opacity-70 hover:opacity-100" @click="setMode(mode, null)"><Icon name="close" :size="11" /></button></span>
        <span class="hidden lg:inline text-[11px] text-ink-muted">{{ (st.total.value || 0).toLocaleString() }} {{ isSweeps ? L("transfers","تحويل","virements") : L("deposits","إيداع","dépôts") }}</span>
        <div class="ms-auto relative">
          <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
          <input v-model.trim="st.search.value" :placeholder="isSweeps ? L('Search voucher…','بحث بالقيد…','Rechercher écriture…') : L('Search ref / customer…','بحث…','Rechercher…')" class="w-44 sm:w-56 h-9 bg-app-warm/40 border border-line-2 rounded-[10px] ps-9 pe-3 text-[12.5px] focus:outline-none focus:border-accent/40 focus:bg-white" />
        </div>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead><tr style="background:#fafaf9">
            <th class="px-4 py-2 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted cursor-pointer" @click="st.setSort('date')">{{ L("Date","التاريخ","Date") }}</th>
            <th class="px-4 py-2 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ isSweeps ? L("Voucher","القيد","Écriture") : L("Payment","الدفعة","Paiement") }}</th>
            <th class="px-4 py-2 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ isSweeps ? L("From carrier","من الناقل","Du transp.") : L("Carrier","الناقل","Transporteur") }}</th>
            <th class="px-4 py-2 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ isSweeps ? L("To bank","إلى البنك","Vers banque") : L("Reference","المرجع","Référence") }}</th>
            <th class="px-4 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted cursor-pointer" @click="st.setSort('amount')">{{ L("Amount","المبلغ","Montant") }}</th>
          </tr></thead>
          <tbody>
            <tr v-for="r in st.rows.value" :key="r.name" class="border-t border-line-hair hover:bg-app-warm/50 cursor-pointer" @click="open(r.name)">
              <td class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ r.date }}</td>
              <td class="px-4 py-2.5 font-mono font-semibold">{{ r.name }}</td>
              <td class="px-4 py-2.5 text-ink-2">{{ carrierLabel(r.carrier) }}</td>
              <td class="px-4 py-2.5 font-mono text-ink-3 text-[11px]">{{ isSweeps ? (r.bank || "—") : r.reference }}</td>
              <td class="px-4 py-2.5 text-end tnum font-bold" :class="isSweeps ? 'text-sky-700' : 'text-success-dark'">{{ fmt2(r.amount) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <TableLoading v-if="st.loading.value" :rows="6" />
      <div v-else-if="!st.rows.value.length" class="py-10 text-center text-[12px] text-ink-muted">{{ isSweeps ? L("No transfers.","لا تحويلات.","Aucun virement.") : L("No deposits.","لا إيداعات.","Aucun dépôt.") }}</div>
      <ServerPager :t="st" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import StatCard from "@/components/StatCard.vue";
import ServerPager from "@/components/ServerPager.vue";
import TableLoading from "@/components/TableLoading.vue";
import DateFilterBar from "@/components/DateFilterBar.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useServerTable } from "@/composables/useServerTable";
import { useDateFilter } from "@/composables/useDateFilter";
import { useUi } from "@/composables/useUi";

const { locale } = useI18n();
const { entityId } = useUi();
const router = useRouter();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US");
const fmt2 = (n) => Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const money = (n) => { n = Number(n) || 0; const a = Math.abs(n); return a >= 1e6 ? (n / 1e6).toFixed(2) + "M" : a >= 1e3 ? Math.round(n / 1e3) + "K" : Math.round(n).toLocaleString(); };
const carrierLabel = (c) => String(c || "").replace(/ Transactions?$/i, "").trim() || c;

const s = ref({});
const loadingSum = ref(true);
const carrier = ref(null);
const mode = ref("deposits"); // 'deposits' = COD into carrier accounts · 'sweeps' = carrier → your bank
const ccy = computed(() => s.value.currency || "MAD");
const isSweeps = computed(() => mode.value === "sweeps");
const swept = computed(() => (s.value.total_collected || 0) - (s.value.total_held || 0));
const topCarrier = computed(() => { const c = (s.value.by_carrier || [])[0]; return c ? carrierLabel(c.carrier) : ""; });

const df = useDateFilter("carriersettle", () => { loadSummary(); st.setFilters(filtersNow()); });
function filtersNow() { return { ...df.filterValue(), carrier: carrier.value || undefined }; }

async function loadSummary() {
  loadingSum.value = true;
  try { s.value = await api.call("accounting_portal.api.cod.carrier_settlements", { company: currentCompany(), ...df.filterValue() }) || {}; }
  catch { s.value = {}; }
  finally { loadingSum.value = false; }
}

const st = useServerTable(
  (params) => api.call(
    mode.value === "sweeps"
      ? "accounting_portal.api.cod.list_carrier_sweeps"
      : "accounting_portal.api.cod.list_carrier_deposits",
    { company: currentCompany(), ...params }),
  { pageSize: 25, sortField: "date", sortDir: "desc", filters: filtersNow() },
);
loadSummary();
st.load();
watch(entityId, () => { carrier.value = null; mode.value = "deposits"; loadSummary(); st.page.value = 1; st.setFilters(filtersNow()); });

function toggleCarrier(c) { carrier.value = carrier.value === c ? null : c; st.page.value = 1; st.setFilters(filtersNow()); }
function setMode(m, c) {
  // c === undefined keeps the current carrier scope; null clears it; a value sets it.
  if (c !== undefined) carrier.value = c;
  mode.value = m;
  st.page.value = 1;
  st.setFilters(filtersNow());
}
function open(name) {
  // Sweeps are Journal Entries; deposits are Payment Entries.
  if (mode.value === "sweeps") router.push({ path: "/accounting/journals", query: { id: name } });
  else router.push({ path: "/accounting/sales/payments", query: { id: name } });
}
</script>
