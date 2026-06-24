<template>
  <div class="space-y-3">
    <div class="flex items-center gap-2">
      <span class="inline-flex items-center gap-1.5 text-[10.5px] font-bold uppercase tracking-wider px-2 py-1 rounded-chip"
            :class="live ? 'text-success-dark bg-success-soft' : 'text-amber-700 bg-amber-50'">
        <span class="w-1.5 h-1.5 rounded-full" :class="live ? 'bg-success' : 'bg-amber-500'"></span>{{ live ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échantillon") }}
      </span>
      <span class="text-[11px] text-ink-muted">{{ L("Every write the team makes from the portal — who, what, when, and the posted voucher.","كل عملية كتابة يقوم بها الفريق من البورتال — من، وماذا، ومتى، والمستند المُرحّل.","Chaque écriture passée depuis le portail — qui, quoi, quand.") }}</span>
    </div>

    <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
      <table class="w-full text-[12px]">
        <thead><tr style="background:#fafaf9">
          <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Action","الإجراء","Action") }}</th>
          <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Status","الحالة","Statut") }}</th>
          <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Amount","المبلغ","Montant") }}</th>
          <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Voucher","المستند","Pièce") }}</th>
          <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("By","بواسطة","Par") }}</th>
          <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("When","متى","Quand") }}</th>
        </tr></thead>
        <tbody>
          <tr v-for="a in rows" :key="a.name" class="border-t border-line-hair hover:bg-app-warm/40">
            <td class="px-4 py-2.5"><div class="font-semibold">{{ a.action_type }}</div><div v-if="a.notes" class="text-[10.5px] text-ink-muted truncate max-w-[220px]">{{ a.notes }}</div></td>
            <td class="px-4 py-2.5"><span class="inline-flex items-center gap-1 text-[10.5px] font-bold px-2 py-0.5 rounded-badge border" :style="badge(a.status)">{{ a.status }}</span></td>
            <td class="px-4 py-2.5 text-end tnum font-semibold">{{ a.amount ? money0(a.amount) : "—" }}</td>
            <td class="px-4 py-2.5 font-mono text-[11px] text-ink-2">{{ a.voucher_no || "—" }}</td>
            <td class="px-4 py-2.5 text-ink-3">{{ shortUser(a.proposed_by) }}<span v-if="a.approved_by" class="text-ink-muted"> → {{ shortUser(a.approved_by) }}</span></td>
            <td class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ when(a.posted_on || a.creation) }}</td>
          </tr>
          <tr v-if="!rows.length"><td colspan="6" class="px-4 py-10 text-center text-ink-muted text-[12px]">{{ L("No portal actions yet.","لا توجد إجراءات بعد.","Aucune action pour l'instant.") }}</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useUi } from "@/composables/useUi";
import { liveOrSample, currentCompany } from "@/composables/useLive";
import { money0 } from "@/composables/useReports";

const { locale } = useI18n();
const { entityId } = useUi();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

const SAMPLE = [
  { name: "a1", action_type: "Post Correction", status: "Posted", amount: 4200, voucher_no: "ACC-JV-2026-04920", proposed_by: "demo@justyol.com", approved_by: null, posted_on: "2026-06-23 14:12:00", notes: "June accrual reclass" },
  { name: "a2", action_type: "Record Payment", status: "Posted", amount: 298, voucher_no: "PAY-22475", proposed_by: "collections@justyol.com", approved_by: null, posted_on: "2026-06-23 11:40:00", notes: "Receive 298 from Omniya" },
  { name: "a3", action_type: "Post Correction", status: "Proposed", amount: 185000, voucher_no: null, proposed_by: "demo@justyol.com", approved_by: null, posted_on: null, notes: "Correction-Need reclass — needs approver" },
  { name: "a4", action_type: "Record Payment", status: "Approved", amount: 12500, voucher_no: "PAY-22468", proposed_by: "collections@justyol.com", approved_by: "cfo@justyol.com", posted_on: "2026-06-22 18:03:00", notes: "Carrier remittance batch" },
];

const live = ref(false);
const rows = ref([]);
async function load() {
  const r = await liveOrSample("accounting_portal.api._actions.list_actions", { company: currentCompany(), limit: 100 }, () => SAMPLE);
  live.value = r.live;
  rows.value = Array.isArray(r.data) ? r.data : SAMPLE;
}
onMounted(load);
watch(entityId, load);

const PALETTE = {
  Posted: "background:#ecfdf5;color:#047857;border-color:#a7f3d0",
  Approved: "background:#eff6ff;color:#0369a1;border-color:#bae6fd",
  Proposed: "background:#fffbeb;color:#b45309;border-color:#fde68a",
  Rejected: "background:#fef2f2;color:#b91c1c;border-color:#fecaca",
  Failed: "background:#fef2f2;color:#b91c1c;border-color:#fecaca",
};
const badge = (s) => PALETTE[s] || "background:#f5f5f4;color:#57534e;border-color:#e7e5e4";
const shortUser = (u) => (u ? String(u).split("@")[0] : "—");
function when(d) {
  if (!d) return "—";
  return String(d).slice(0, 16).replace("T", " ");
}
</script>
