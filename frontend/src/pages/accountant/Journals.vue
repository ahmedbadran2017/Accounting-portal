<template>
  <div class="space-y-3">
    <DateFilterBar :df="df" />
    <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
    <!-- Header -->
    <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
      <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#faf6f4"><Icon name="ledger" :size="14" color="#0b5c4f" /></span>
      <span class="text-[13px] font-bold">{{ L("Journals", "القيود", "Écritures") }}</span>
      <LiveBadge :live="isLive" />
      <span class="hidden lg:inline text-[11px] text-ink-muted">{{ (st.total.value || 0).toLocaleString() }} {{ L("entries", "قيد", "écritures") }}</span>
      <div class="relative ms-auto">
        <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
        <input v-model.trim="st.search.value" :placeholder="L('Journal / remark / type…', 'قيد / بيان…', 'Écriture / libellé…')" class="fld fld-md fld-sunk w-44 sm:w-56" />
      </div>
      <UiButton variant="secondary" size="sm" icon="refresh" v-if="canWrite" @click="showReclass = true"> {{ L("Reclassify", "إعادة تصنيف", "Reclasser") }}
      </UiButton>
      <UiButton variant="create" size="sm" icon="plus" @click="showForm = true"> {{ L("New JE", "قيد جديد", "Nouvelle écriture") }}
      </UiButton>
    </div>

    <div v-if="st.loading.value" class="px-1"><TableLoading :rows="6" /></div>
    <div v-else class="overflow-x-auto">
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
          <tr v-for="j in displayRows" :key="j.name" class="border-t border-line-hair hover:bg-app-warm/70 cursor-pointer" @click="open(j.name)">
            <td class="px-3 py-2" @click.stop><input type="checkbox" :checked="st.selected.value.has(j.name)" @change="st.toggle(j.name)" /></td>
            <td class="px-4 py-2.5 font-mono font-semibold whitespace-nowrap">{{ j.name }}</td>
            <td class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ j.date }}</td>
            <td class="px-4 py-2.5 text-ink-2 whitespace-nowrap">{{ j.type }}</td>
            <td class="px-4 py-2.5 text-ink-3 truncate max-w-[260px]">{{ j.remark || "—" }}</td>
            <td class="px-4 py-2.5 text-end font-bold tnum whitespace-nowrap">{{ fmt(j.amount) }}</td>
            <td class="px-4 py-2.5">
              <span class="inline-block text-[11px] font-bold px-2 py-0.5 rounded-badge border" :style="statusStyle(j.status)">{{ statusLabel(j.status) }}</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="!st.loading.value && !displayRows.length" class="py-12 text-center text-[12px] text-ink-muted">{{ L("No journals match your filters.", "لا قيود مطابقة.", "Aucune écriture.") }}</div>
    <ListToolbar v-model:status="listStatus" v-model:pageSize="listPageSize" v-model:owner="listOwner" owner-doctype="Journal Entry" :total="st.total.value" export-key="journals" :export-filters="exportFilters" :extra-statuses="extraStatuses" />
    <ServerPager :t="st" />
    <BulkBar :t="st" :actions="bulkActions" filename="journals" />
    </div>
    <JournalEntryForm v-if="showForm" @close="showForm = false" @posted="onPosted" />
    <ReclassifyModal v-if="showReclass" @close="showReclass = false" @posted="onPosted" />
  </div>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import LiveBadge from "@/components/LiveBadge.vue";
import TableLoading from "@/components/TableLoading.vue";
import ServerPager from "@/components/ServerPager.vue";
import ListToolbar from "@/components/ListToolbar.vue";
import BulkBar from "@/components/BulkBar.vue";
import { useBulkDocs } from "@/composables/useBulkDocs";
import JournalEntryForm from "@/components/JournalEntryForm.vue";
import ReclassifyModal from "@/components/ReclassifyModal.vue";
import { useAuth } from "@/composables/useAuth";
import { useToast } from "@/composables/useToast";
import { currentCompany } from "@/composables/useLive";
import { useServerTable } from "@/composables/useServerTable";
import { usePersistedRef } from "@/composables/usePersistedRef";
import { useDateFilter } from "@/composables/useDateFilter";
import DateFilterBar from "@/components/DateFilterBar.vue";
import { useUi } from "@/composables/useUi";
import api from "@/services/api";
import UiButton from "@/components/UiButton.vue";

const { locale } = useI18n();
const router = useRouter();
const toast = useToast();
const { entityId } = useUi();
function open(name) { router.push({ path: "/accounting/accountant/journals", query: { id: name } }); }
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const STATUS = {
  draft: { bg: "#fffbeb", fg: "#b45309", bd: "#fde68a", l: () => L("Draft", "مسودة", "Brouillon") },
  submitted: { bg: "#ecfdf5", fg: "#047857", bd: "#a7f3d0", l: () => L("Submitted", "مُرحّل", "Soumis") },
  cancelled: { bg: "#fef2f2", fg: "#be123c", bd: "#fecaca", l: () => L("Cancelled", "ملغى", "Annulé") },
};
const statusStyle = (s) => { const m = STATUS[s] || STATUS.submitted; return { background: m.bg, color: m.fg, borderColor: m.bd }; };
const statusLabel = (s) => (STATUS[s] || STATUS.submitted).l();

const cols = [
  { key: "name", label: L("Journal", "القيد", "Écriture"), align: "s", sort: "id" },
  { key: "date", label: L("Date", "التاريخ", "Date"), align: "s", sort: "date" },
  { key: "type", label: L("Type", "النوع", "Type"), align: "s", sort: "type" },
  { key: "remark", label: L("Remark", "البيان", "Libellé"), align: "s" },
  { key: "amount", label: L("Amount", "المبلغ", "Montant"), align: "e", sort: "amount" },
  { key: "status", label: L("Status", "الحالة", "Statut"), align: "s" },
];

const { can } = useAuth();
const canWrite = computed(() => can("post_entries"));
const isLive = ref(null);
const showForm = ref(false);
const showReclass = ref(false);
const df = useDateFilter("journals", (f) => st.setFilters(f));
const { actions: bulkActions } = useBulkDocs("Journal Entry", () => st);
const st = useServerTable(
  (params) => api.call("accounting_portal.api.accountant.list_journals", { company: currentCompany(), ...params }).then((r) => { isLive.value = true; return r; }),
  { pageSize: 25, sortField: "date", sortDir: "desc", filters: df.filterValue() , storeKey: "journals" },
);
// Status chips + page size + full-list Excel (ListToolbar).
const listStatus = usePersistedRef("ap_ls_journals", "open");
const listPageSize = usePersistedRef("ap_lps_journals", 25);
const listOwner = usePersistedRef("ap_lo_journals", "");
const extraStatuses = [];
const exportFilters = computed(() => ({ ...st.filters.value, search: st.search.value || undefined, status: listStatus.value, owner: listOwner.value || undefined }));
let _lsFirst = true;
watch([listStatus, listPageSize, listOwner], () => {
  st.pageSize.value = listPageSize.value;
  // First run seeds the filter before the page's own initial load, so opening
  // the list costs one request, not two.
  if (_lsFirst) { _lsFirst = false; st.filters.value = { ...st.filters.value, status: listStatus.value, owner: listOwner.value || undefined }; return; }
  st.setFilters({ status: listStatus.value, owner: listOwner.value || undefined });
}, { immediate: true });

st.load();
watch(entityId, () => { st.page.value = 1; st.load(); });

const displayRows = computed(() => (st.rows.value || []).map((r) => ({
  name: r.name, date: String(r.date || ""), type: r.type || "Journal Entry",
  remark: r.remark || "", amount: Number(r.amount) || 0, status: r.status || "submitted",
})));

function onPosted(res) {
  if (res && res.status === "Posted") toast.success(L(`Journal ${res.voucher_no || ""} posted`, `قيد ${res.voucher_no || ""} رُحّل`, `Écriture ${res.voucher_no || ""} passée`));
  else toast.info(L("Entry recorded — awaiting an approver", "القيد سُجّل — بانتظار موافِق", "Écriture enregistrée — en attente"));
  st.load();
}
</script>
