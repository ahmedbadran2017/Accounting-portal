<template>
  <div class="space-y-3.5">
    <div class="flex items-center gap-2 flex-wrap">
      <span class="text-[15px] font-bold">{{ L("My work","مهامي","Mon travail") }}</span>
      <span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-app-warm text-ink-2">{{ open.length }} {{ L("open","مفتوح","ouvert") }}</span>
      <span class="text-[11px] text-ink-muted">{{ L("tasks assigned to you by the CFO / auditor","مهام مُسنَدة إليك من المدير/المدقّق","tâches qui vous sont assignées") }}</span>
      <button class="ms-auto text-[11px] font-semibold text-ink-3 hover:text-ink inline-flex items-center gap-1" @click="load"><Icon name="refresh" :size="13" />{{ L("Refresh","تحديث","Rafraîchir") }}</button>
    </div>

    <div v-if="loading"><TableLoading :rows="5" /></div>
    <div v-else-if="!open.length" class="bg-white border border-line rounded-card shadow-card py-16 text-center">
      <Icon name="check" :size="26" color="#047857" />
      <div class="text-[13px] font-bold text-success-dark mt-1.5">{{ L("All clear — no open tasks.","تمام — لا مهام مفتوحة.","Rien à faire.") }}</div>
    </div>

    <div v-else class="space-y-2.5">
      <div v-for="t in open" :key="t.task" class="bg-white border border-line rounded-[14px] p-4 shadow-card flex items-start gap-3">
        <span class="w-8 h-8 rounded-[10px] grid place-items-center flex-shrink-0" :style="prioBg(t.priority)"><Icon :name="t.is_audit ? 'shield' : 'doc'" :size="15" :color="prioFg(t.priority)" /></span>
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-1.5 flex-wrap">
            <span class="text-[13px] font-bold">{{ t.title }}</span>
            <span class="text-[9px] font-bold px-1.5 py-0.5 rounded-badge" :style="prioChip(t.priority)">{{ t.priority }}</span>
            <span v-if="t.is_audit" class="text-[9px] font-bold px-1.5 py-0.5 rounded-badge bg-violet-50 text-violet-700">{{ L("Audit","تدقيق","Audit") }}</span>
            <span v-if="overdue(t.due)" class="text-[9px] font-bold px-1.5 py-0.5 rounded-badge bg-rose-50 text-rose-600">{{ L("Overdue","متأخّر","En retard") }}</span>
          </div>
          <div v-if="t.detail" class="text-[11.5px] text-ink-3 mt-1 leading-snug">{{ t.detail }}</div>
          <div class="text-[10.5px] text-ink-muted mt-1.5">{{ L("Due","الاستحقاق","Échéance") }} {{ t.due || "—" }}</div>
        </div>
        <div class="flex flex-col items-end gap-1.5 flex-shrink-0">
          <button v-if="t.reference_type && t.reference_name" class="h-7 px-2.5 rounded-[8px] text-[11px] font-semibold text-ink-2 bg-white border border-line-2 hover:bg-app-warm" @click="openRef(t)">{{ L("Open","فتح","Ouvrir") }}</button>
          <button v-else-if="t.is_audit" class="h-7 px-2.5 rounded-[8px] text-[11px] font-semibold text-ink-2 bg-white border border-line-2 hover:bg-app-warm" @click="go('/accounting/copilot')">{{ L("View","عرض","Voir") }}</button>
          <button class="h-7 px-2.5 rounded-[8px] text-[11px] font-bold text-success-dark bg-success-soft hover:opacity-80 disabled:opacity-50" :disabled="busy === t.task" @click="done(t)">{{ busy === t.task ? "…" : L("Done","تم","Fait") }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";
import { useToast } from "@/composables/useToast";

const { locale } = useI18n();
const router = useRouter();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

const tasks = ref([]);
const loading = ref(true);
const busy = ref("");
const open = computed(() => tasks.value);
const today = new Date().toISOString().slice(0, 10);

async function load() {
  loading.value = true;
  try { const r = await api.call("accounting_portal.api.docops.my_work", {}); tasks.value = r.tasks || []; }
  catch { tasks.value = []; }
  finally { loading.value = false; }
}
onMounted(load);

async function done(t) {
  busy.value = t.task;
  try {
    await api.call("accounting_portal.api.auditor.close_task", { task: t.task });
    tasks.value = tasks.value.filter((x) => x.task !== t.task);
    toast.success(L("Marked done", "تم", "Fait"));
  } catch (e) { toast.error(String((e && e.message) || L("Failed", "فشل", "Échec")).slice(0, 140)); }
  finally { busy.value = ""; }
}
const REF_ROUTE = { "Sales Invoice": "sales/invoices", "Sales Order": "sales/orders", "Purchase Invoice": "purchases/bills", "Payment Entry": "purchases/payments", "Journal Entry": "accountant/journals", "Delivery Note": "sales/challans", "Purchase Order": "purchases/tobuy" };
function openRef(t) { const r = REF_ROUTE[t.reference_type]; if (r) router.push({ path: `/accounting/${r}`, query: { id: t.reference_name } }); }
function go(p) { router.push(p); }
const overdue = (d) => d && String(d) < today;
const prioBg = (p) => ({ High: "background:#fef2f2", Medium: "background:#fffbeb", Low: "background:#f5f5f4" }[p] || "background:#f5f5f4");
const prioFg = (p) => ({ High: "#b91c1c", Medium: "#b45309", Low: "#57534e" }[p] || "#57534e");
const prioChip = (p) => ({ High: "background:#fef2f2;color:#b91c1c", Medium: "background:#fffbeb;color:#b45309", Low: "background:#f5f5f4;color:#57534e" }[p] || "");
</script>
