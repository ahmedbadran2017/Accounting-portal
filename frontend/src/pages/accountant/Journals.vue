<template>
  <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
    <!-- Header -->
    <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
      <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#faf6f4"><Icon name="ledger" :size="14" color="#0b5c4f" /></span>
      <span class="text-[13px] font-bold">{{ L("Journals", "القيود", "Écritures") }}</span>
      <span v-if="isLive !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="isLive ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ isLive ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échant.") }}</span>
      <span class="hidden lg:inline text-[11px] text-ink-muted">{{ (st.total.value || 0).toLocaleString() }} {{ L("entries", "قيد", "écritures") }}</span>
      <div class="relative ms-auto">
        <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
        <input v-model.trim="st.search.value" :placeholder="L('Journal / remark / type…', 'قيد / بيان…', 'Écriture / libellé…')" class="w-44 sm:w-56 h-9 bg-app-warm/40 border border-line-2 rounded-[10px] ps-9 pe-3 text-[12.5px] focus:outline-none focus:border-accent/40 focus:bg-white" />
      </div>
      <button class="inline-flex items-center gap-1.5 h-[33px] px-3 rounded-[9px] text-white text-[12px] font-bold" style="background:linear-gradient(135deg,#0f766e,#0b5c4f)" @click="showForm = true">
        <Icon name="plus" :size="13" />{{ L("New JE", "قيد جديد", "Nouvelle écriture") }}
      </button>
    </div>

    <div v-if="st.loading.value" class="px-1"><TableLoading :rows="6" /></div>
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
          <tr v-for="j in displayRows" :key="j.name" class="border-t border-line-hair hover:bg-app-warm/70 cursor-pointer" @click="open(j.name)">
            <td class="px-4 py-2.5 font-mono font-semibold whitespace-nowrap">{{ j.name }}</td>
            <td class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ j.date }}</td>
            <td class="px-4 py-2.5 text-ink-2 whitespace-nowrap">{{ j.type }}</td>
            <td class="px-4 py-2.5 text-ink-3 truncate max-w-[260px]">{{ j.remark || "—" }}</td>
            <td class="px-4 py-2.5 text-end font-bold tnum whitespace-nowrap">{{ fmt(j.amount) }}</td>
            <td class="px-4 py-2.5">
              <span class="inline-block text-[10px] font-bold px-2 py-0.5 rounded-badge border" :style="statusStyle(j.status)">{{ statusLabel(j.status) }}</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="!st.loading.value && !displayRows.length" class="py-12 text-center text-[12px] text-ink-muted">{{ L("No journals match your filters.", "لا قيود مطابقة.", "Aucune écriture.") }}</div>
    <ServerPager :t="st" />
  </div>

  <JournalEntryForm v-if="showForm" @close="showForm = false" @posted="onPosted" />
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import ServerPager from "@/components/ServerPager.vue";
import JournalEntryForm from "@/components/JournalEntryForm.vue";
import { useToast } from "@/composables/useToast";
import { currentCompany } from "@/composables/useLive";
import { useServerTable } from "@/composables/useServerTable";
import { useUi } from "@/composables/useUi";
import api from "@/services/api";

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

const isLive = ref(null);
const showForm = ref(false);
const st = useServerTable(
  (params) => api.call("accounting_portal.api.accountant.list_journals", { company: currentCompany(), ...params }).then((r) => { isLive.value = true; return r; }),
  { pageSize: 25, sortField: "date", sortDir: "desc" },
);
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
