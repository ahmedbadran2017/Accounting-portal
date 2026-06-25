<template>
  <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
    <!-- Header -->
    <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
      <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#faf6f4"><Icon name="ledger" :size="14" color="#0b5c4f" /></span>
      <span class="text-[13px] font-bold">{{ L("Journals", "القيود", "Écritures") }}</span>
      <span v-if="isLive !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="isLive ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ isLive ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échant.") }}</span>
      <span class="hidden lg:inline text-[11px] text-ink-muted">{{ rows.length }} {{ L("entries", "قيد", "écritures") }}</span>
      <div class="relative ms-auto">
        <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
        <input v-model.trim="tt.search.value" :placeholder="L('Journal / remark / type…', 'قيد / بيان…', 'Écriture / libellé…')" class="w-44 sm:w-56 h-9 bg-app-warm/40 border border-line-2 rounded-[10px] ps-9 pe-3 text-[12.5px] focus:outline-none focus:border-accent/40 focus:bg-white" />
      </div>
      <button class="inline-flex items-center gap-1.5 h-[33px] px-3 rounded-[9px] text-white text-[12px] font-bold" style="background:linear-gradient(135deg,#0f766e,#0b5c4f)" @click="showForm = true">
        <Icon name="plus" :size="13" />{{ L("New JE", "قيد جديد", "Nouvelle écriture") }}
      </button>
    </div>

    <TableToolbar :t="tt" filename="journals" />
    <div v-if="loading" class="px-1"><TableLoading :rows="6" /></div>
    <div v-else class="overflow-x-auto">
      <table class="w-full text-[12px]">
        <thead>
          <tr style="background:#fafaf9">
            <th class="px-3 py-2.5 w-9"><input type="checkbox" :checked="tt.allFilteredSelected.value" @change="tt.toggleAllFiltered()" class="accent-accent w-3.5 h-3.5 align-middle" /></th>
            <th v-for="c in cols" v-show="!tt.hidden.value.has(c.key)" :key="c.key"
                class="px-4 py-2.5 text-[10px] font-bold uppercase tracking-wider text-ink-muted whitespace-nowrap cursor-pointer select-none hover:text-ink-2"
                :class="c.align === 'e' ? 'text-end' : 'text-start'" @click="tt.toggleSort(c.key)">
              <span class="inline-flex items-center gap-1" :class="c.align === 'e' ? 'flex-row-reverse' : ''">{{ c.label }}
                <Icon v-if="tt.sortKey.value === c.key" name="chevDown" :size="11" :class="tt.sortDir.value === 1 ? '' : 'rotate-180'" color="#0b5c4f" /></span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="j in tt.pageRows.value" :key="j.name" class="border-t border-line-hair hover:bg-app-warm/70 cursor-pointer" :class="tt.isSelected(j) ? 'bg-accent/5' : ''" @click="open(j.name)">
            <td class="px-3 py-2.5 w-9" @click.stop><input type="checkbox" :checked="tt.isSelected(j)" @change="tt.toggleRow(j)" class="accent-accent w-3.5 h-3.5 align-middle" /></td>
            <td v-show="!tt.hidden.value.has('name')" class="px-4 py-2.5 font-mono font-semibold whitespace-nowrap">{{ j.name }}</td>
            <td v-show="!tt.hidden.value.has('date')" class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ j.date }}</td>
            <td v-show="!tt.hidden.value.has('type')" class="px-4 py-2.5 text-ink-2 whitespace-nowrap">{{ j.type }}</td>
            <td v-show="!tt.hidden.value.has('remark')" class="px-4 py-2.5 text-ink-3 truncate max-w-[260px]">{{ j.remark || "—" }}</td>
            <td v-show="!tt.hidden.value.has('amount')" class="px-4 py-2.5 text-end font-bold tnum whitespace-nowrap">{{ fmt(j.amount) }}</td>
            <td v-show="!tt.hidden.value.has('status')" class="px-4 py-2.5">
              <span class="inline-block text-[10px] font-bold px-2 py-0.5 rounded-badge border" :style="statusStyle(j.status)">{{ statusLabel(j.status) }}</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="!loading && !tt.sorted.value.length" class="py-12 text-center text-[12px] text-ink-muted">{{ L("No journals match your filters.", "لا قيود مطابقة.", "Aucune écriture.") }}</div>
    <TablePager :t="tt" />

    <BulkBar :t="tt" filename="journals-selected" :actions="bulkActions" />
  </div>

  <JournalEntryForm v-if="showForm" @close="showForm = false" @posted="onPosted" />
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableToolbar from "@/components/TableToolbar.vue";
import TablePager from "@/components/TablePager.vue";
import TableLoading from "@/components/TableLoading.vue";
import BulkBar from "@/components/BulkBar.vue";
import JournalEntryForm from "@/components/JournalEntryForm.vue";
import { useToast } from "@/composables/useToast";
import { liveOrSample, currentCompany } from "@/composables/useLive";
import { useTableTools } from "@/composables/useTableTools";
import { useBulkDocActions } from "@/composables/useBulkActions";

const { locale } = useI18n();
const router = useRouter();
const toast = useToast();
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
  { key: "name", label: L("Journal", "القيد", "Écriture"), align: "s" },
  { key: "date", label: L("Date", "التاريخ", "Date"), align: "s" },
  { key: "type", label: L("Type", "النوع", "Type"), align: "s" },
  { key: "remark", label: L("Remark", "البيان", "Libellé"), align: "s" },
  { key: "amount", label: L("Amount", "المبلغ", "Montant"), align: "e" },
  { key: "status", label: L("Status", "الحالة", "Statut"), align: "s" },
];

const SAMPLE = [
  { name: "ACC-JV-2026-04920", date: "2026-06-23", type: "Journal Entry", remark: "Posted via Accounting Portal", amount: 100, status: "submitted" },
  { name: "ACC-JV-2026-04880", date: "2026-06-06", type: "Depreciation Entry", remark: "", amount: 85.67, status: "submitted" },
];
const rows = ref([]);
const isLive = ref(null);
const loading = ref(true);
const showForm = ref(false);
const tt = useTableTools(rows, cols, { keyField: "name", dateKey: "date", defaultSort: "date", defaultDir: -1, facets: [{ key: "type", label: L("type", "نوع", "type") }, { key: "status", label: L("status", "حالة", "statut") }] });

async function load() {
  loading.value = true;
  try {
    const res = await liveOrSample(
      "accounting_portal.api.accountant.list_journals", { company: currentCompany(), limit: 500 }, () => SAMPLE,
      (data) => data.map((r) => ({ name: r.name, date: String(r.date || ""), type: r.type || "Journal Entry", remark: r.remark || "", amount: Number(r.amount) || 0, status: r.status || "submitted" })),
    );
    rows.value = res.data;
    isLive.value = res.live;
  } finally { loading.value = false; }
}
onMounted(load);
const bulkActions = useBulkDocActions("Journal Entry", { keyField: "name", onDone: () => { tt.clearSelection(); load(); }, L });

function onPosted(res) {
  if (res && res.status === "Posted") toast.success(L(`Journal ${res.voucher_no || ""} posted`, `قيد ${res.voucher_no || ""} رُحّل`, `Écriture ${res.voucher_no || ""} passée`));
  else toast.info(L("Entry recorded — awaiting an approver", "القيد سُجّل — بانتظار موافِق", "Écriture enregistrée — en attente"));
  load();
}
</script>
