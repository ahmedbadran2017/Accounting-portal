<template>
  <div class="flex items-center gap-2 px-4 py-2 border-b border-line-hair flex-wrap bg-app-warm/20">
    <!-- Status chips: the one thing every Desk list had and no portal list did -->
    <div v-if="statuses.length" class="flex items-center gap-1 flex-wrap">
      <button v-for="s in statuses" :key="s.k" type="button"
              class="h-7 px-2.5 rounded-chip text-[12px] font-semibold border transition"
              :class="status === s.k ? 'text-white bg-ink border-ink' : 'text-ink-3 bg-white border-line-2 hover:bg-app-warm'"
              @click="$emit('update:status', s.k)">{{ s.label() }}</button>
    </div>

    <span class="ms-auto flex items-center gap-2">
      <span v-if="total != null" class="text-[12px] text-ink-muted tnum">{{ total.toLocaleString() }} {{ L("rows", "صف", "lignes") }}</span>
      <select :value="pageSize" @change="$emit('update:pageSize', Number($event.target.value))"
              class="fld fld-xs" :title="L('Rows per page','صفوف في الصفحة','Lignes par page')">
        <option :value="25">25</option><option :value="50">50</option><option :value="100">100</option><option :value="200">200</option>
      </select>
      <a v-if="exportKey" :href="excelUrl" class="h-7 px-2.5 rounded-chip text-[11px] font-bold text-white inline-flex items-center gap-1" style="background:#1d6f42"
         :title="L('Excel of the whole filtered list','Excel للقائمة المفلترة كلها','Excel de toute la liste filtrée')">
        <Icon name="download" :size="12" color="#fff" />Excel
      </a>
    </span>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { currentCompany } from "@/composables/useLive";

const props = defineProps({
  status: { type: String, default: "open" },
  pageSize: { type: Number, default: 25 },
  total: { type: Number, default: null },
  // Which list to export (key in api/export._LIST_EXPORTS) + the filters on screen.
  exportKey: { type: String, default: "" },
  exportFilters: { type: Object, default: () => ({}) },
  // Extra business states beyond draft/submitted/cancelled, e.g. overdue for bills.
  extraStatuses: { type: Array, default: () => [] },
});
defineEmits(["update:status", "update:pageSize"]);
const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

const statuses = computed(() => [
  { k: "open", label: () => L("Open", "المفتوح", "Ouverts") },
  { k: "draft", label: () => L("Drafts", "المسودات", "Brouillons") },
  { k: "submitted", label: () => L("Submitted", "المُرحّل", "Soumis") },
  ...props.extraStatuses,
  { k: "cancelled", label: () => L("Cancelled", "الملغي", "Annulés") },
  { k: "all", label: () => L("All", "الكل", "Tous") },
]);

const excelUrl = computed(() => {
  const q = new URLSearchParams({ key: props.exportKey, company: currentCompany() });
  for (const [k, v] of Object.entries(props.exportFilters || {})) {
    if (v !== undefined && v !== null && v !== "") q.set(k, String(v));
  }
  return `/api/method/accounting_portal.api.export.list_xlsx?${q.toString()}`;
});
</script>
