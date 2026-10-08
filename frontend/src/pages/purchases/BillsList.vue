<template>
  <div class="space-y-3">
    <DateFilterBar :df="df" />
    <div class="bg-white rounded-[14px] border border-line shadow-card overflow-hidden">
    <!-- Header -->
    <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
      <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#fff4e0"><Icon name="doc" :size="14" color="#b45309" /></span>
      <span class="text-[13px] font-bold">{{ L("Bills","الفواتير","Factures") }}</span>
      <LiveBadge :live="isLive" />
      <span class="hidden lg:inline text-[11px] text-ink-muted">{{ L("Purchase Invoice · 3-way match vs PO + Goods Receipt","فاتورة شراء · مطابقة ثلاثية","Facture d’achat · rappr. 3 voies") }}</span>
      <div class="relative ms-auto">
        <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
        <input v-model.trim="st.search.value" :placeholder="L('Search bill / vendor…','بحث…','Rechercher…')" class="fld fld-md fld-sunk w-44 sm:w-64" />
      </div>
      <UiButton v-if="canWrite" variant="secondary" size="sm" icon="refresh" @click="openCn">
        {{ L("New credit note", "إشعار دائن جديد", "Nouvel avoir") }}
      </UiButton>
    </div>

    <!-- Supplier credit note: pick the bill it reduces, then finish the draft. -->
    <div v-if="cnOpen" class="fixed inset-0 z-50 grid place-items-center bg-ink/30 px-4" @click.self="cnOpen = false">
      <div class="bg-white rounded-card shadow-pop w-full max-w-lg p-5">
        <div class="text-[14px] font-bold">{{ L("New supplier credit note", "إشعار دائن جديد من مورّد", "Nouvel avoir fournisseur") }}</div>
        <div class="text-[12px] text-ink-3 mt-1">{{ L("Choose the bill the supplier is crediting. A draft opens with its lines — keep what is credited, then submit.",
          "اختار الفاتورة اللي المورّد عامل عليها الإشعار. هتتفتح مسودة فيها سطورها، سيب اللي عليه الإشعار وبعدين رحّل.",
          "Choisissez la facture créditée. Un brouillon s'ouvre avec ses lignes.") }}</div>
        <input id="cn-bill-search" v-model.trim="cnQ" autofocus :placeholder="L('Supplier, bill no. or PUR-INV…','المورّد أو رقم الفاتورة…','Fournisseur, n° facture…')" class="fld fld-md fld-sunk w-full mt-3" />
        <div class="mt-2 max-h-[320px] overflow-y-auto border border-line-hair rounded-[10px]">
          <div v-if="cnLoading" class="py-6 text-center text-[12px] text-ink-muted">{{ L("Loading…", "جارٍ التحميل…", "Chargement…") }}</div>
          <div v-else-if="cnError" class="py-6 text-center text-[12px] text-sale">{{ L("Load failed", "فشل التحميل", "Échec du chargement") }}</div>
          <div v-else-if="!cnRows.length" class="py-6 text-center text-[12px] text-ink-muted">{{ L("No posted bill matches.", "مفيش فاتورة مرحّلة مطابقة.", "Aucune facture.") }}</div>
          <button v-for="r in cnRows" :key="r.name" type="button" :disabled="cnBusy"
                  class="w-full flex items-center gap-3 px-3 py-2 text-start text-[12px] border-b border-line-hair last:border-0 hover:bg-app-warm disabled:opacity-50"
                  @click="pickCn(r.name)">
            <span class="font-mono font-semibold whitespace-nowrap">{{ r.name }}</span>
            <span class="truncate flex-1">{{ r.supplier }}<span v-if="r.bill_no" class="text-ink-muted"> · {{ r.bill_no }}</span></span>
            <span class="text-ink-3 whitespace-nowrap">{{ r.date }}</span>
            <span class="font-semibold tnum whitespace-nowrap">{{ r.currency }} {{ fmt(r.amount) }}</span>
          </button>
        </div>
        <div class="flex justify-end mt-3">
          <UiButton variant="quiet" size="md" @click="cnOpen = false">{{ L("Cancel", "إلغاء", "Annuler") }}</UiButton>
        </div>
      </div>
    </div>

    <div class="overflow-x-auto">
      <table class="w-full text-[12px]">
        <thead>
          <tr style="background:#fafaf9">
            <th class="w-8 px-3"><input type="checkbox" :checked="st.allSelected.value" @change="st.toggleAll()" /></th>
            <th v-for="c in cols" :key="c.key"
                class="px-4 py-2.5 text-[11px] font-bold uppercase tracking-wider text-ink-muted whitespace-nowrap select-none"
                :class="[c.align === 'e' ? 'text-end' : 'text-start', c.sort ? 'cursor-pointer hover:text-ink-2' : '']" @click="c.sort && st.setSort(c.sort)">
              <span class="inline-flex items-center gap-1" :class="c.align === 'e' ? 'flex-row-reverse' : ''">{{ c.label }}
                <Icon v-if="c.sort && st.sortField.value === c.sort" name="chevDown" :size="11" :class="st.sortDir.value === 'asc' ? 'rotate-180' : ''" color="#0b5c4f" /></span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="b in displayRows" :key="b.id" class="border-t border-line-hair hover:bg-app-warm/70 cursor-pointer" @click="open(b.id)">
            <td class="px-3 py-2" @click.stop><input type="checkbox" :checked="st.selected.value.has(b.id)" @change="st.toggle(b.id)" /></td>
            <td class="px-4 py-2.5 font-mono font-semibold whitespace-nowrap">{{ b.id }}</td>
            <td class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ b.date || "—" }}</td>
            <td class="px-4 py-2.5 truncate max-w-[200px]">{{ b.vendor }}</td>
            <td class="px-4 py-2.5">
              <span class="inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded-badge border"
                    :style="{ background: MATCH_META[b.match].bg, color: MATCH_META[b.match].c, borderColor: MATCH_META[b.match].bd }">
                <Icon :name="b.match === 'ok' ? 'check' : 'alert'" :size="11" />{{ matchLabel(b.match, locale) }}
              </span>
            </td>
            <td class="px-4 py-2.5 text-end font-bold tnum whitespace-nowrap" :class="b.amount < 0 ? 'text-sale' : ''">{{ b.currency }} {{ fmt(b.amount) }}</td>
            <td class="px-4 py-2.5">
              <span class="inline-block text-[11px] font-bold px-2 py-0.5 rounded-badge border"
                    :style="{ background: BILL_STATUS[b.status].bg, color: BILL_STATUS[b.status].fg, borderColor: BILL_STATUS[b.status].bd }">
                {{ billStatusLabel(b.status, locale) }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <TableLoading v-if="st.loading.value" />
    <div v-else-if="!displayRows.length" class="py-12 text-center text-[12px] text-ink-muted">{{ L("No bills match your filters.","لا توجد فواتير مطابقة.","Aucune facture.") }}</div>
    <ListToolbar v-model:status="listStatus" v-model:pageSize="listPageSize" v-model:owner="listOwner" owner-doctype="Purchase Invoice" :total="st.total.value" export-key="bills" :export-filters="exportFilters" :extra-statuses="extraStatuses" />
    <ServerPager :t="st" />
    <BulkBar :t="st" :actions="bulkActions" filename="bills" />
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import LiveBadge from "@/components/LiveBadge.vue";
import TableLoading from "@/components/TableLoading.vue";
import ServerPager from "@/components/ServerPager.vue";
import ListToolbar from "@/components/ListToolbar.vue";
import BulkBar from "@/components/BulkBar.vue";
import { useBulkDocs } from "@/composables/useBulkDocs";
import { MATCH_META, BILL_STATUS, matchLabel, billStatusLabel } from "@/data/purchases";
import { currentCompany } from "@/composables/useLive";
import { useServerTable } from "@/composables/useServerTable";
import { usePersistedRef } from "@/composables/usePersistedRef";
import { useDateFilter } from "@/composables/useDateFilter";
import DateFilterBar from "@/components/DateFilterBar.vue";
import { useUi } from "@/composables/useUi";
import api from "@/services/api";
import UiButton from "@/components/UiButton.vue";
import { useAuth } from "@/composables/useAuth";
import { useToast } from "@/composables/useToast";
import { openCreditNoteDraft } from "@/composables/useCreditNote";

const { locale } = useI18n();
const route = useRoute();
const router = useRouter();
const { entityId } = useUi();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US", { maximumFractionDigits: 2 });

const cols = [
  { key: "id", label: L("Bill", "الفاتورة", "Facture"), align: "s", sort: "id" },
  { key: "date", label: L("Date", "التاريخ", "Date"), align: "s", sort: "date" },
  { key: "vendor", label: L("Vendor", "المورّد", "Fournisseur"), align: "s", sort: "supplier" },
  { key: "match", label: L("3-way match", "المطابقة", "Rappr."), align: "s" },
  { key: "amount", label: L("Amount", "المبلغ", "Montant"), align: "e", sort: "amount" },
  { key: "status", label: L("Status", "الحالة", "Statut"), align: "s" },
];

const isLive = ref(null);
const df = useDateFilter("bills", (f) => st.setFilters(f));
const { actions: bulkActions } = useBulkDocs("Purchase Invoice", () => st);
const st = useServerTable(
  (params) => api.call("accounting_portal.api.purchases.list_bills", { company: currentCompany(), ...params }).then((r) => { isLive.value = true; return r; }),
  { pageSize: 25, sortField: "date", sortDir: "desc", filters: df.filterValue() , storeKey: "bills" },
);
// Status chips + page size + full-list Excel (ListToolbar).
const listStatus = usePersistedRef("ap_ls_bills", "open");
const listPageSize = usePersistedRef("ap_lps_bills", 25);
const listOwner = usePersistedRef("ap_lo_bills", "");
const extraStatuses = [{ k: "overdue", label: () => L("Overdue","المتأخر","En retard") }, { k: "paid", label: () => L("Paid","المدفوع","Payées") }];
const exportFilters = computed(() => ({ ...st.filters.value, search: st.search.value || undefined, status: listStatus.value, owner: listOwner.value || undefined }));
let _lsFirst = true;
watch([listStatus, listPageSize, listOwner], () => {
  st.pageSize.value = listPageSize.value;
  // First run seeds the filter before the page's own initial load, so opening
  // the list costs one request, not two.
  if (_lsFirst) { _lsFirst = false; st.filters.value = { ...st.filters.value, status: listStatus.value, owner: listOwner.value || undefined }; return; }
  st.setFilters({ status: listStatus.value, owner: listOwner.value || undefined });
}, { immediate: true });

// Arriving from a supplier page (?supplier=…) narrows the list to that supplier.
watch(() => route.query.supplier, (v) => { if (v) st.search.value = String(v); }, { immediate: true });

st.load();
watch(entityId, () => { st.page.value = 1; st.load(); });

const displayRows = computed(() => (st.rows.value || []).map((r) => ({
  id: r.name, date: String(r.date || ""), vendor: r.supplier, match: r.match,
  amount: Number(r.amount) || 0, currency: r.currency || "MAD", status: r.status_norm,
})));

function open(id) { router.push({ path: "/accounting/purchases/bills", query: { id } }); }

// ── New supplier credit note ──
const { can } = useAuth();
const toast = useToast();
const canWrite = computed(() => can("post_entries"));
const cnOpen = ref(false), cnQ = ref(""), cnRows = ref([]), cnLoading = ref(false), cnError = ref(false), cnBusy = ref(false);
let _cnT, _cnSeq = 0;
async function loadCn() {
  const seq = ++_cnSeq;
  cnLoading.value = true; cnError.value = false;
  try {
    const r = await api.call("accounting_portal.api.purchases.list_bills",
      { company: currentCompany(), status: "returnable", search: cnQ.value || undefined, page_size: 15 });
    if (seq === _cnSeq) cnRows.value = ((r && r.rows) || []).map((x) => ({ ...x, date: String(x.date || "") }));
  } catch { if (seq === _cnSeq) { cnRows.value = []; cnError.value = true; } }
  finally { if (seq === _cnSeq) cnLoading.value = false; }
}
function openCn() { cnOpen.value = true; cnQ.value = st.search.value || ""; loadCn(); }
watch(cnQ, () => { if (!cnOpen.value) return; clearTimeout(_cnT); _cnT = setTimeout(loadCn, 300); });
async function pickCn(bill) {
  cnBusy.value = true;
  try {
    const nd = await openCreditNoteDraft(bill);
    cnOpen.value = false;
    router.push({ path: "/accounting/purchases/bills", query: { id: nd, edit: "1" } });
  } catch (err) { toast.error(String((err && err.message) || L("Failed", "فشل", "Échec")).slice(0, 160)); }
  finally { cnBusy.value = false; }
}
</script>
