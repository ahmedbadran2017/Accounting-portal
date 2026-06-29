<template>
  <div class="bg-white rounded-card border border-line overflow-hidden shadow-card">
    <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
      <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#ecfdf5"><Icon name="wallet" :size="14" color="#047857" /></span>
      <span class="text-[13px] font-bold">{{ L("Payments made", "المدفوعات", "Paiements émis") }}</span>
      <span v-if="live !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="live ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ live ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échant.") }}</span>
      <span class="hidden lg:inline text-[11px] text-ink-muted">{{ (st.total.value || 0).toLocaleString() }} {{ L("records", "سجل", "enreg.") }}</span>
      <div class="relative ms-auto">
        <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
        <input v-model.trim="st.search.value" :placeholder="L('Payment / vendor / ref…', 'دفعة / مورّد / مرجع…', 'Paiement / fournisseur…')" class="w-44 sm:w-56 h-9 bg-app-warm/40 border border-line-2 rounded-[10px] ps-9 pe-3 text-[12.5px] focus:outline-none focus:border-accent/40 focus:bg-white" />
      </div>
    </div>

    <div v-if="adv.count" class="flex items-center gap-2 px-4 py-2.5 border-b border-line-hair flex-wrap" style="background:#fffbeb66">
      <span class="w-1.5 h-1.5 rounded-full bg-brand"></span>
      <span class="text-[11.5px] text-ink-2"><b>{{ adv.count }}</b> {{ L("advances", "دفعة مقدّمة", "avances") }} · <b class="text-sale tnum">{{ fmt(adv.total) }} MAD</b> {{ L("paid but not matched to any bill", "مدفوعة بلا مطابقة لفواتير", "non affecté à une facture") }}</span>
      <button @click="toggleAdvances" class="ms-auto text-[11px] font-bold px-2.5 py-1 rounded-full border transition" :class="advancesOnly ? 'bg-brand text-white border-brand' : 'bg-white text-brand border-brand/40 hover:bg-brand/5'">{{ advancesOnly ? L("Showing advances", "عرض المقدّمات", "Avances") : L("Show advances only", "اعرض المقدّمات فقط", "Voir les avances") }}</button>
    </div>

    <div class="flex items-center gap-2 px-4 py-2.5 border-b border-line-hair flex-wrap bg-app-warm/20">
      <Icon name="clock" :size="13" color="#a8a29e" />
      <button v-for="p in DATE_PRESETS" :key="p.key" class="text-[11px] font-semibold px-2.5 py-1 rounded-full border transition"
              :class="datePreset === p.key ? 'bg-ink text-white border-ink' : 'bg-white text-ink-3 border-line-2 hover:bg-app-warm'" @click="setPreset(p.key)">{{ p.label() }}</button>
      <span v-if="st.loading.value" class="ms-2 text-[11px] text-ink-muted inline-flex items-center gap-1.5"><span class="w-1.5 h-1.5 rounded-full bg-accent animate-pulse"></span>{{ L("loading…", "تحميل…", "…") }}</span>
    </div>

    <div v-if="st.loading.value" class="px-1"><TableLoading :rows="5" /></div>
    <div v-else class="overflow-x-auto">
      <table class="w-full text-[12px]">
        <thead>
          <tr style="background:#fafaf9">
            <th v-for="c in cols" :key="c.key"
                class="px-4 py-2.5 text-[10px] font-bold uppercase tracking-wider text-ink-muted whitespace-nowrap select-none"
                :class="[c.align === 'e' ? 'text-end' : 'text-start', c.sort ? 'cursor-pointer hover:text-ink-2' : '']" @click="c.sort && st.setSort(c.sort)">
              <span class="inline-flex items-center gap-1" :class="c.align === 'e' ? 'flex-row-reverse' : ''">{{ c.label }}
                <Icon v-if="c.sort && st.sortField.value === c.sort" name="chevDown" :size="11" :class="st.sortDir.value === 'asc' ? 'rotate-180' : ''" color="#0b5c4f" /></span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="o in displayRows" :key="o.name" class="border-t border-line-hair hover:bg-app-warm/70 cursor-pointer" @click="open(o.name)">
            <td class="px-4 py-2.5 font-mono font-semibold whitespace-nowrap">{{ o.name }}</td>
            <td class="px-4 py-2.5 truncate max-w-[220px]">{{ o.party_name }}</td>
            <td class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ o.date }}</td>
            <td class="px-4 py-2.5 whitespace-nowrap">
              <span class="text-[10px] font-bold px-2 py-0.5 rounded-full" :style="methodStyle(o.method)">{{ o.method }}</span>
              <span v-if="o.unallocated > 0" class="ms-1.5 text-[10px] font-bold px-1.5 py-0.5 rounded-full" style="background:#fffbeb;color:#b45309">{{ L("advance", "مقدّم", "avance") }} {{ fmt(o.unallocated) }}</span>
              <span v-else-if="o.n_bills > 1" class="ms-1.5 text-[10px] text-ink-muted">· {{ o.n_bills }} {{ L("bills", "فاتورة", "factures") }}</span>
            </td>
            <td class="px-4 py-2.5 text-end font-bold tnum whitespace-nowrap">{{ o.currency }} {{ fmt(o.amount) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="!st.loading.value && !displayRows.length" class="py-12 text-center text-[12px] text-ink-muted">{{ L("No payments in this period.", "لا مدفوعات في هذه الفترة.", "Aucun paiement.") }}</div>
    <ServerPager :t="st" />
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import ServerPager from "@/components/ServerPager.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";
import { useServerTable } from "@/composables/useServerTable";

const router = useRouter();
const { locale } = useI18n();
const { entityId } = useUi();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
function methodStyle(m) {
  m = (m || "").toLowerCase();
  if (/cheque|chèque|شيك/.test(m)) return "background:#fffbeb;color:#b45309";
  if (/bmce|bank|wire|virement|transfer|kuveyt|حوالة|تحويل/.test(m)) return "background:#eff6ff;color:#0369a1";
  if (/cash|كاش|espèce/.test(m)) return "background:#ecfdf5;color:#047857";
  return "background:#f5f3ff;color:#6d28d9";
}

const DATE_PRESETS = [
  { key: "all", label: () => L("All", "الكل", "Tout") },
  { key: "7d", label: () => L("7 days", "7 أيام", "7 j") },
  { key: "30d", label: () => L("30 days", "30 يوم", "30 j") },
  { key: "month", label: () => L("This month", "هذا الشهر", "Ce mois") },
];
const cols = [
  { key: "name", label: L("Payment", "الدفعة", "Paiement"), align: "s", sort: "id" },
  { key: "party_name", label: L("Vendor", "المورّد", "Fournisseur"), align: "s", sort: "party" },
  { key: "date", label: L("Date", "التاريخ", "Date"), align: "s", sort: "date" },
  { key: "method", label: L("Method", "الطريقة", "Méthode"), align: "s" },
  { key: "amount", label: L("Amount", "المبلغ", "Montant"), align: "e", sort: "amount" },
];

const live = ref(null);
const datePreset = ref("month");
const advancesOnly = ref(false);
const adv = ref({ count: 0, total: 0 });

function bounds() {
  const iso = (d) => d.toISOString().slice(0, 10);
  const now = new Date(); const t = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  if (datePreset.value === "7d") { const s = new Date(t); s.setDate(s.getDate() - 7); return [iso(s), iso(now)]; }
  if (datePreset.value === "30d") { const s = new Date(t); s.setDate(s.getDate() - 30); return [iso(s), iso(now)]; }
  if (datePreset.value === "month") return [iso(new Date(now.getFullYear(), now.getMonth(), 1)), iso(now)];
  return [null, null];
}
const [fd0, td0] = bounds();
const st = useServerTable(
  (params) => api.call("accounting_portal.api.payments.list_payments_made", { company: currentCompany(), ...params }).then((r) => { live.value = true; return r; }),
  { pageSize: 25, sortField: "date", sortDir: "desc", filters: { from_date: fd0 || undefined, to_date: td0 || undefined } },
);
// initial load is triggered by the immediate entityId watch below (loadAdv + setFilters)

const displayRows = computed(() => (st.rows.value || []).map((r) => ({
  name: r.name, party_name: r.party_name, date: String(r.date || ""), method: r.method,
  amount: Number(r.amount) || 0, currency: r.currency || "MAD", unallocated: Number(r.unallocated) || 0, n_bills: r.n_bills,
})));

function setPreset(k) { datePreset.value = k; const [fd, td] = bounds(); st.setFilters({ from_date: fd || undefined, to_date: td || undefined }); }
function toggleAdvances() {
  advancesOnly.value = !advancesOnly.value;
  if (advancesOnly.value) datePreset.value = "all";
  const [fd, td] = bounds();
  st.setFilters({ advances_only: advancesOnly.value ? 1 : undefined, from_date: fd || undefined, to_date: td || undefined });
}
function open(name) { router.push({ path: "/accounting/purchases/payments", query: { id: name } }); }

async function loadAdv() {
  try { adv.value = await api.call("accounting_portal.api.payments.payments_advances_summary", { company: currentCompany() }) || { count: 0, total: 0 }; }
  catch { adv.value = { count: 0, total: 0 }; }
}
watch(entityId, () => { advancesOnly.value = false; datePreset.value = "month"; const [fd, td] = bounds(); loadAdv(); st.page.value = 1; st.setFilters({ advances_only: undefined, from_date: fd || undefined, to_date: td || undefined }); }, { immediate: true });
</script>
