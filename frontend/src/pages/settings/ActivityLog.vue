<template>
  <div class="space-y-3">
    <div class="flex items-center gap-2">
      <span class="inline-flex items-center gap-1.5 text-[10.5px] font-bold uppercase tracking-wider px-2 py-1 rounded-chip"
            :class="live ? 'text-success-dark bg-success-soft' : 'text-amber-700 bg-amber-50'">
        <span class="w-1.5 h-1.5 rounded-full" :class="live ? 'bg-success' : 'bg-amber-500'"></span>{{ live ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échantillon") }}
      </span>
      <span class="text-[11px] text-ink-muted">{{ L("Every write the team makes from the portal — who, what, when, and the posted voucher.","كل عملية كتابة يقوم بها الفريق من البورتال — من، وماذا، ومتى، والمستند المُرحّل.","Chaque écriture passée depuis le portail.") }}</span>
    </div>

    <div v-if="pending" class="flex items-center gap-2.5 px-4 py-2.5 rounded-card border" style="background:#fffbeb;border-color:#fde68a">
      <Icon name="bell" :size="15" color="#b45309" />
      <span class="text-[12px] font-bold text-ink-2">{{ pending }} {{ L("action(s) awaiting your approval", "إجراء بانتظار موافقتك", "action(s) à approuver") }}</span>
      <button @click="filter = 'Proposed'" class="ms-auto text-[11px] font-bold px-2.5 py-1 rounded-full bg-brand text-white">{{ L("Review", "راجع", "Examiner") }}</button>
    </div>

    <div class="flex items-center gap-2 flex-wrap">
      <button v-for="f in FILTERS" :key="f" class="text-[11px] font-semibold px-2.5 py-1 rounded-full border transition" :class="filter === f ? 'bg-ink text-white border-ink' : 'bg-white text-ink-3 border-line-2 hover:bg-app-warm'" @click="filter = f">{{ f || L('All', 'الكل', 'Tout') }}</button>
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
          <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted"></th>
        </tr></thead>
        <tbody>
          <tr v-for="a in filtered" :key="a.name" class="border-t border-line-hair hover:bg-app-warm/40">
            <td class="px-4 py-2.5"><div class="font-semibold">{{ a.action_type }}</div><div v-if="a.notes" class="text-[10.5px] text-ink-muted truncate max-w-[220px]">{{ a.notes }}</div></td>
            <td class="px-4 py-2.5"><span class="inline-flex items-center gap-1 text-[10.5px] font-bold px-2 py-0.5 rounded-badge border" :style="badge(a.status)">{{ a.status }}</span></td>
            <td class="px-4 py-2.5 text-end tnum font-semibold">{{ a.amount ? money0(a.amount) : "—" }}</td>
            <td class="px-4 py-2.5 font-mono text-[11px] text-ink-2">{{ a.voucher_no || "—" }}</td>
            <td class="px-4 py-2.5 text-ink-3">{{ shortUser(a.proposed_by) }}<span v-if="a.approved_by" class="text-ink-muted"> → {{ shortUser(a.approved_by) }}</span>
              <span v-if="assigneesOf(a).length" class="ms-1 inline-flex gap-0.5 align-middle"><span v-for="u in assigneesOf(a)" :key="u" :title="u" class="w-5 h-5 rounded-full grid place-items-center text-[8px] font-bold text-white" :style="{ background: avatarColor(u) }">{{ initials(u) }}</span></span>
            </td>
            <td class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ when(a.posted_on || a.creation) }}</td>
            <td class="px-4 py-2.5 text-end whitespace-nowrap">
              <span class="inline-flex gap-1.5 items-center">
                <span v-if="a.status === 'Proposed'" class="relative">
                  <button @click="assignOpen = assignOpen === a.name ? '' : a.name" class="h-7 px-2 rounded-[8px] text-[11px] font-semibold text-ink-2 bg-white border border-line-2 hover:bg-app-warm inline-flex items-center gap-1"><Icon name="user" :size="12" />{{ L("Assign","إسناد","Assigner") }}</button>
                  <div v-if="assignOpen === a.name" class="absolute z-20 mt-1 end-0 w-52 bg-white border border-line rounded-[10px] shadow-pop py-1 max-h-60 overflow-auto text-start">
                    <button v-for="u in users" :key="u.name" @click="assign(a, u.name)" class="w-full text-start px-3 py-1.5 text-[12px] hover:bg-app-warm flex items-center justify-between"><span class="truncate">{{ u.full_name || u.name }}</span><Icon v-if="assigneesOf(a).includes(u.name)" name="check" :size="12" color="#047857" /></button>
                    <div v-if="!users.length" class="px-3 py-2 text-[11px] text-ink-muted">{{ L("No users","لا مستخدمين","Aucun") }}</div>
                  </div>
                </span>
                <button v-if="a.status === 'Proposed'" @click="approve(a)" :disabled="busy" class="h-7 px-2.5 rounded-[8px] text-[11px] font-bold text-white bg-success disabled:opacity-50">{{ L("Approve", "اعتماد", "Approuver") }}</button>
                <button v-if="a.status === 'Proposed'" @click="reject(a)" :disabled="busy" class="h-7 px-2.5 rounded-[8px] text-[11px] font-semibold text-ink-3 bg-white border border-line-2 hover:bg-app-warm">{{ L("Reject", "رفض", "Rejeter") }}</button>
              </span>
            </td>
          </tr>
          <tr v-if="!filtered.length"><td colspan="7" class="px-4 py-10 text-center text-ink-muted text-[12px]">{{ L("No portal actions here.","لا توجد إجراءات.","Aucune action.") }}</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import api from "@/services/api";
import { useUi } from "@/composables/useUi";
import { usePersistedRef } from "@/composables/usePersistedRef";
import { useToast } from "@/composables/useToast";
import { liveOrSample, currentCompany } from "@/composables/useLive";
import { money0 } from "@/composables/useReports";

const { locale } = useI18n();
const { entityId } = useUi();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const FILTERS = ["", "Proposed", "Posted", "Rejected"];
const filter = usePersistedRef("ap_activity_filter", "");
const busy = ref(false);
const users = ref([]);
const assignOpen = ref("");

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
onMounted(() => { load(); loadUsers(); });
watch(entityId, load);
async function loadUsers() { try { users.value = await api.call("accounting_portal.api.docops.assignable_users", {}) || []; } catch { /* */ } }
function assigneesOf(a) { try { return a._assign ? JSON.parse(a._assign) : []; } catch { return []; } }
async function assign(a, user) {
  try {
    const has = assigneesOf(a).includes(user);
    const list = await api.call(`accounting_portal.api.docops.${has ? "unassign_doc" : "assign_doc"}`,
      { doctype: "Accounting Portal Action", name: a.name, [has ? "from_user" : "to_user"]: user });
    a._assign = JSON.stringify(list || []);
    toast.success(has ? L("Unassigned", "أُلغي الإسناد", "Retiré") : L("Assigned", "تم الإسناد", "Assigné"));
  } catch (e) { toast.error(String((e && e.message) || L("Failed", "فشل", "Échec")).slice(0, 140)); }
  assignOpen.value = "";
}
const PAL = ["#7c3aed", "#0369a1", "#047857", "#b45309", "#be123c", "#0891b2"];
function avatarColor(u) { let h = 0; for (const ch of String(u)) h = (h * 31 + ch.charCodeAt(0)) % PAL.length; return PAL[h]; }
function initials(u) { const s = String(u).split("@")[0].replace(/[._-]/g, " ").trim().split(/\s+/); return ((s[0] || "")[0] + (s[1] ? s[1][0] : "")).toUpperCase().slice(0, 2) || "?"; }

const filtered = computed(() => (filter.value ? rows.value.filter((r) => r.status === filter.value) : rows.value));
const pending = computed(() => rows.value.filter((r) => r.status === "Proposed").length);
async function approve(a) {
  busy.value = true;
  try { await api.call("accounting_portal.api._actions.approve_action", { name: a.name }); toast.success(L("Approved & posted", "تم الاعتماد والترحيل", "Approuvé & passé")); load(); }
  catch (e) { toast.error(String((e && e.message) || L("Failed", "فشل", "Échec")).slice(0, 160)); }
  finally { busy.value = false; }
}
async function reject(a) {
  const reason = window.prompt(L("Reason for rejection?", "سبب الرفض؟", "Motif du rejet ?")) || "";
  busy.value = true;
  try { await api.call("accounting_portal.api._actions.reject_action", { name: a.name, reason }); toast.info(L("Rejected", "تم الرفض", "Rejeté")); load(); }
  catch (e) { toast.error(L("Failed", "فشل", "Échec")); }
  finally { busy.value = false; }
}

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
