<template>
  <div class="space-y-3">
    <div class="flex items-center gap-2">
      <span class="inline-flex items-center gap-1.5 text-[10.5px] font-bold uppercase tracking-wider px-2 py-1 rounded-chip"
            :class="live ? 'text-success-dark bg-success-soft' : 'text-amber-700 bg-amber-50'">
        <span class="w-1.5 h-1.5 rounded-full" :class="live ? 'bg-success' : 'bg-amber-500'"></span>{{ live ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échantillon") }}
      </span>
      <span class="text-[11px] text-ink-muted">{{ L("Every write the team makes from the portal — who, what, when, and the posted voucher.","كل عملية كتابة يقوم بها الفريق من البورتال — من، وماذا، ومتى، والمستند المُرحّل.","Chaque écriture passée depuis le portail.") }}</span>
    </div>

    <!-- Approval gate control (Super Admin) -->
    <div v-if="canManage" class="flex items-center gap-3 px-4 py-3 rounded-card border" :style="requireApproval ? 'background:#eff6ff;border-color:#bae6fd' : 'background:#fffbeb;border-color:#fde68a'">
      <Icon name="shield" :size="16" :color="requireApproval ? '#0369a1' : '#b45309'" />
      <div class="min-w-0">
        <div class="text-[12.5px] font-bold">{{ L("Require an approver for material actions","اشتراط موافِق للعمليات الكبيرة","Approbation requise") }}</div>
        <div class="text-[11px] text-ink-muted">{{ requireApproval
          ? L(`Actions ≥ ${money0(threshold)} are held for a second approver.`, `العمليات ≥ ${money0(threshold)} تُحجز لموافِق ثانٍ.`, `Les actions ≥ ${money0(threshold)} attendent un approbateur.`)
          : L("OFF — every action posts directly (correction period). Still fully audited below.","معطّل — كل العمليات تُرحّل مباشرة (فترة التصحيح). وكلها مُسجّلة بالأسفل.","Désactivé — tout est passé directement.") }}</div>
      </div>
      <button @click="toggleApproval" :disabled="apprBusy" class="ms-auto inline-flex items-center gap-2 h-8 px-3 rounded-chip text-[12px] font-bold disabled:opacity-50"
              :class="requireApproval ? 'text-white bg-brand hover:bg-brand-dark' : 'text-amber-800 bg-amber-100 hover:bg-amber-200'">
        <span class="w-8 h-4 rounded-full relative transition-colors" :style="requireApproval ? 'background:#0b5c4f' : 'background:#d6d3d1'"><span class="absolute top-0.5 w-3 h-3 rounded-full bg-white transition-all" :style="requireApproval ? 'inset-inline-end:2px' : 'inset-inline-start:2px'"></span></span>
        {{ requireApproval ? L("On","مفعّل","Activé") : L("Off","معطّل","Désactivé") }}
      </button>
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
                <button @click="openDetail(a)" class="h-7 px-2 rounded-[8px] text-[11px] font-semibold text-ink-2 bg-white border border-line-2 hover:bg-app-warm inline-flex items-center gap-1" :title="L('View transaction details','عرض تفاصيل المعاملة','Voir les détails')"><Icon name="doc" :size="12" />{{ L("Details","تفاصيل","Détails") }}</button>
                <span v-if="a.status === 'Proposed'" class="relative">
                  <button @click="assignOpen = assignOpen === a.name ? '' : a.name" class="h-7 px-2 rounded-[8px] text-[11px] font-semibold text-ink-2 bg-white border border-line-2 hover:bg-app-warm inline-flex items-center gap-1"><Icon name="user" :size="12" />{{ L("Assign","إسناد","Assigner") }}</button>
                  <div v-if="assignOpen === a.name" class="absolute z-20 mt-1 end-0 w-52 bg-white border border-line rounded-[10px] shadow-pop py-1 max-h-60 overflow-auto text-start">
                    <button v-for="u in users" :key="u.name" @click="assign(a, u.name)" class="w-full text-start px-3 py-1.5 text-[12px] hover:bg-app-warm flex items-center justify-between"><span class="truncate">{{ u.full_name || u.name }}</span><Icon v-if="assigneesOf(a).includes(u.name)" name="check" :size="12" color="#047857" /></button>
                    <div v-if="!users.length" class="px-3 py-2 text-[11px] text-ink-muted">{{ L("No users","لا مستخدمين","Aucun") }}</div>
                  </div>
                </span>
                <button v-if="a.status === 'Proposed' && !isMine(a)" @click="approve(a)" :disabled="busy" class="h-7 px-2.5 rounded-[8px] text-[11px] font-bold text-white bg-success disabled:opacity-50">{{ L("Approve", "اعتماد", "Approuver") }}</button>
                <button v-else-if="a.status === 'Proposed' && canBreakGlass" @click="selfApprove(a)" :disabled="busy" class="h-7 px-2.5 rounded-[8px] text-[11px] font-bold text-white bg-amber-600 hover:bg-amber-700 disabled:opacity-50" :title="L('No other approver available — self-approve with a reason (logged)','لا يوجد موافِق آخر — اعتمد بنفسك بسبب مُسجّل','Auto-approuver')">{{ L("Self-approve", "اعتمد بنفسك", "Auto-approuver") }}</button>
                <span v-else-if="a.status === 'Proposed'" class="text-[10px] text-ink-muted italic px-1" :title="L('You proposed this — another approver must approve it', 'أنت اقترحته — لازم موافِق آخر', 'Un autre approbateur est requis')">{{ L("awaiting another approver", "بانتظار موافِق آخر", "en attente d'un autre approbateur") }}</span>
                <button v-if="a.status === 'Proposed'" @click="reject(a)" :disabled="busy" class="h-7 px-2.5 rounded-[8px] text-[11px] font-semibold text-ink-3 bg-white border border-line-2 hover:bg-app-warm">{{ L("Reject", "رفض", "Rejeter") }}</button>
                <button v-if="a.status === 'Posted' && a.revertable && canManage" @click="revert(a)" :disabled="busy" class="h-7 px-2.5 rounded-[8px] text-[11px] font-semibold text-ink-3 bg-white border border-line-2 hover:bg-app-warm inline-flex items-center gap-1"><Icon name="arrow" :size="11" class="rotate-180" />{{ L("Undo", "تراجع", "Annuler") }}</button>
              </span>
            </td>
          </tr>
          <tr v-if="!filtered.length"><td colspan="7" class="px-4 py-10 text-center text-ink-muted text-[12px]">{{ L("No portal actions here.","لا توجد إجراءات.","Aucune action.") }}</td></tr>
        </tbody>
      </table>
    </div>

    <!-- Review modal: the full transaction behind an action, before approving -->
    <div v-if="detailOpen" class="fixed inset-0 z-40 flex items-center justify-center p-4" @click.self="closeDetail">
      <div class="absolute inset-0 bg-black/40"></div>
      <div class="relative bg-white rounded-[16px] shadow-pop w-full max-w-lg max-h-[86vh] flex flex-col overflow-hidden">
        <header class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair">
          <span class="w-7 h-7 rounded-[9px] grid place-items-center" style="background:#eff6ff"><Icon name="doc" :size="14" color="#0369a1" /></span>
          <div class="min-w-0">
            <div class="text-[13px] font-bold truncate">{{ detail?.action_type || L("Loading…","تحميل…","…") }}</div>
            <div class="text-[10.5px] text-ink-muted">{{ L("Review before approving","راجِع قبل الاعتماد","Vérifier avant d’approuver") }}</div>
          </div>
          <span v-if="detail" class="ms-auto text-[10.5px] font-bold px-2 py-0.5 rounded-badge border" :style="badge(detail.status)">{{ detail.status }}</span>
          <button @click="closeDetail" class="w-7 h-7 grid place-items-center rounded-[8px] hover:bg-app-warm text-ink-muted"><Icon name="close" :size="14" /></button>
        </header>

        <div class="p-4 overflow-auto space-y-3">
          <div v-if="detailLoading" class="py-10 text-center text-[12px] text-ink-muted">{{ L("Loading…","جارٍ التحميل…","Chargement…") }}</div>
          <template v-else-if="detail">
            <!-- meta strip -->
            <div class="grid grid-cols-2 gap-2 text-[11.5px]">
              <div class="rounded-[10px] bg-app-warm/50 px-3 py-2"><div class="text-ink-muted text-[10px] uppercase tracking-wide font-bold">{{ L("Amount","المبلغ","Montant") }}</div><div class="font-bold tnum">{{ detail.amount ? money0(detail.amount) : "—" }}</div></div>
              <div class="rounded-[10px] bg-app-warm/50 px-3 py-2"><div class="text-ink-muted text-[10px] uppercase tracking-wide font-bold">{{ L("Company","الشركة","Société") }}</div><div class="font-semibold truncate">{{ detail.company || "—" }}</div></div>
              <div class="rounded-[10px] bg-app-warm/50 px-3 py-2"><div class="text-ink-muted text-[10px] uppercase tracking-wide font-bold">{{ L("Proposed by","اقترحه","Proposé par") }}</div><div class="font-semibold truncate">{{ shortUser(detail.proposed_by) }}</div></div>
              <div class="rounded-[10px] bg-app-warm/50 px-3 py-2"><div class="text-ink-muted text-[10px] uppercase tracking-wide font-bold">{{ L("When","متى","Quand") }}</div><div class="font-semibold">{{ when(detail.creation) }}</div></div>
            </div>

            <div v-if="detail.notes" class="text-[12px] text-ink-2 rounded-[10px] border border-line-hair px-3 py-2"><span class="text-ink-muted">{{ L("Note","ملاحظة","Note") }}: </span>{{ detail.notes }}</div>

            <!-- scalar payload fields -->
            <div v-if="scalarRows.length" class="rounded-[10px] border border-line-hair overflow-hidden">
              <div class="px-3 py-2 bg-app-warm/40 text-[10px] font-bold uppercase tracking-wide text-ink-muted">{{ L("Transaction","المعاملة","Transaction") }}</div>
              <table class="w-full text-[12px]">
                <tr v-for="r in scalarRows" :key="r.k" class="border-t border-line-hair">
                  <td class="px-3 py-1.5 text-ink-muted whitespace-nowrap align-top w-[42%]">{{ r.label }}</td>
                  <td class="px-3 py-1.5 font-medium text-end tnum break-all">{{ r.val }}</td>
                </tr>
              </table>
            </div>

            <!-- array payload blocks (e.g. correction lines) -->
            <div v-for="b in tableBlocks" :key="b.k" class="rounded-[10px] border border-line-hair overflow-hidden">
              <div class="px-3 py-2 bg-app-warm/40 text-[10px] font-bold uppercase tracking-wide text-ink-muted">{{ b.label }} · {{ b.rows.length }}</div>
              <div class="overflow-x-auto">
                <table class="w-full text-[11.5px]">
                  <thead><tr class="text-[9.5px] uppercase text-ink-muted">
                    <th v-for="c in b.cols" :key="c" class="px-3 py-1.5 text-start font-bold whitespace-nowrap">{{ klabel(c) }}</th>
                  </tr></thead>
                  <tbody>
                    <tr v-for="(row,i) in b.rows" :key="i" class="border-t border-line-hair">
                      <td v-for="c in b.cols" :key="c" class="px-3 py-1.5 whitespace-nowrap" :class="['debit','credit','amount','net','tax'].includes(c) ? 'text-end tnum' : ''">{{ fmtVal(c, row[c]) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div v-if="detail.voucher_no" class="text-[11.5px] text-ink-3">{{ L("Posted voucher","المستند المُرحّل","Pièce") }}: <span class="font-mono text-ink-2">{{ detail.voucher_no }}</span></div>
          </template>
        </div>

        <!-- in-context decision for a Proposed action -->
        <footer v-if="detail && detail.status === 'Proposed'" class="flex items-center gap-2 px-4 py-3 border-t border-line-hair bg-app-warm/30">
          <button @click="reject(detail)" :disabled="busy" class="h-8 px-3 rounded-chip text-[12px] font-semibold text-ink-3 bg-white border border-line-2 hover:bg-app-warm disabled:opacity-50">{{ L("Reject","رفض","Rejeter") }}</button>
          <button v-if="!isMine(detail)" @click="approve(detail)" :disabled="busy" class="ms-auto h-8 px-4 rounded-chip text-[12px] font-bold text-white bg-success hover:brightness-95 disabled:opacity-50">{{ L("Approve & post","اعتماد وترحيل","Approuver") }}</button>
          <button v-else-if="canBreakGlass" @click="selfApprove(detail)" :disabled="busy" class="ms-auto h-8 px-4 rounded-chip text-[12px] font-bold text-white bg-amber-600 hover:bg-amber-700 disabled:opacity-50">{{ L("Self-approve","اعتمد بنفسك","Auto-approuver") }}</button>
          <span v-else class="ms-auto text-[11px] text-ink-muted italic">{{ L("awaiting another approver","بانتظار موافِق آخر","en attente") }}</span>
        </footer>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import api from "@/services/api";
import { useUi } from "@/composables/useUi";
import { useAuth } from "@/composables/useAuth";
import { usePersistedRef } from "@/composables/usePersistedRef";
import { useToast } from "@/composables/useToast";
import { liveOrSample, currentCompany } from "@/composables/useLive";
import { money0 } from "@/composables/useReports";

const { locale } = useI18n();
const { entityId } = useUi();
const { can, user } = useAuth();
const canManage = computed(() => can("manage_users"));
// Break-glass self-approval: only when you're a super-admin AND no other approver
// exists (a genuine single-admin shop) — otherwise segregation of duties stands.
const noOtherApprover = ref(false);
const canBreakGlass = computed(() => canManage.value && noOtherApprover.value);
// Segregation of duties: you can't approve what you proposed — so hide Approve on
// your own proposals (the backend enforces it too; this stops the raw error).
const isMine = (a) => !!(a.proposed_by && user.value && a.proposed_by === user.value);
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
  // Only ever show demo rows when NOT live — never mask a real (empty/failed) audit feed.
  rows.value = r.live ? (Array.isArray(r.data) ? r.data : []) : SAMPLE;
}
const requireApproval = ref(true);
const threshold = ref(10000);
const apprBusy = ref(false);
async function loadApprovalSetting() {
  try { const r = await api.call("accounting_portal.api._actions.approval_settings", {}); requireApproval.value = !!r.require_approval; threshold.value = Number(r.threshold) || 10000; }
  catch { /* */ }
}
async function toggleApproval() {
  apprBusy.value = true;
  try {
    const r = await api.call("accounting_portal.api._actions.set_approval_required", { on: requireApproval.value ? 0 : 1 });
    requireApproval.value = !!r.require_approval;
    toast.success(requireApproval.value ? L("Approvals on", "تم تفعيل الموافقات", "Approbations activées") : L("Approvals off — direct posting", "تم إيقاف الموافقات — ترحيل مباشر", "Approbations désactivées"));
  } catch (e) { toast.error(String((e && e.message) || L("Failed", "فشل", "Échec")).slice(0, 140)); }
  finally { apprBusy.value = false; }
}
onMounted(() => { load(); loadUsers(); checkApprovers(); if (canManage.value) loadApprovalSetting(); });
async function checkApprovers() {
  try { const r = await api.call("accounting_portal.api._actions.approvers_available", {}); noOtherApprover.value = !!(r && r.am_super && r.others === 0); }
  catch { noOtherApprover.value = false; }
}
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

// ── Detail / review modal ──────────────────────────────────────────────
const detailOpen = ref(false);
const detail = ref(null);
const detailLoading = ref(false);
async function openDetail(a) {
  detailOpen.value = true; detail.value = null; detailLoading.value = true;
  if (!live.value) { detail.value = { ...a, payload: a.payload || {} }; detailLoading.value = false; return; }
  try { detail.value = await api.call("accounting_portal.api._actions.get_action", { name: a.name }); }
  catch (e) { toast.error(String((e && e.message) || L("Failed", "فشل", "Échec")).slice(0, 140)); detailOpen.value = false; }
  finally { detailLoading.value = false; }
}
function closeDetail() { detailOpen.value = false; detail.value = null; }

const KEYLBL = {
  supplier: ["Supplier", "المورّد", "Fournisseur"], customer: ["Customer", "العميل", "Client"],
  party: ["Party", "الطرف", "Tiers"], party_type: ["Party type", "نوع الطرف", "Type de tiers"],
  expense_account: ["Expense account", "حساب المصروف", "Compte de charge"],
  tax_account: ["Tax account", "حساب الضريبة", "Compte TVA"], tax: ["Tax", "الضريبة", "Taxe"],
  paid_from: ["Paid from", "مدفوع من", "Payé depuis"], pay_account: ["Pay account", "حساب الدفع", "Compte de paiement"],
  account: ["Account", "الحساب", "Compte"], from_account: ["From account", "من حساب", "Depuis"],
  to_account: ["To account", "إلى حساب", "Vers"], net: ["Net amount", "الصافي", "Net"],
  amount: ["Amount", "المبلغ", "Montant"], debit: ["Debit", "مدين", "Débit"], credit: ["Credit", "دائن", "Crédit"],
  currency: ["Currency", "العملة", "Devise"], rate: ["FX rate", "سعر الصرف", "Taux de change"],
  posting_date: ["Date", "التاريخ", "Date"], bill_no: ["Bill no.", "رقم الفاتورة", "N° facture"],
  description: ["Description", "الوصف", "Description"], reference_no: ["Reference", "المرجع", "Référence"],
  invoice: ["Invoice", "الفاتورة", "Facture"], reason: ["Reason", "السبب", "Motif"],
  attachment: ["Attachment", "المرفق", "Pièce jointe"], pay_amount: ["Pay amount", "مبلغ الدفع", "Montant payé"],
};
function klabel(k) { const m = KEYLBL[k]; return m ? L(m[0], m[1], m[2]) : String(k).replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase()); }
const NUMKEYS = new Set(["net", "tax", "amount", "debit", "credit", "gross", "pay_amount", "allocated"]);
function fmtVal(k, v) {
  if (v === null || v === undefined || v === "") return "—";
  if (v === true) return "✓"; if (v === false) return "—";
  if (typeof v === "number") return NUMKEYS.has(k) ? money0(v) : v.toLocaleString("en-US");
  return String(v);
}
const scalarRows = computed(() => {
  const p = detail.value && detail.value.payload;
  if (!p || typeof p !== "object") return [];
  return Object.entries(p)
    .filter(([, v]) => v !== null && v !== "" && v !== undefined && typeof v !== "object")
    .map(([k, v]) => ({ k, label: klabel(k), val: fmtVal(k, v) }));
});
const tableBlocks = computed(() => {
  const p = detail.value && detail.value.payload;
  if (!p || typeof p !== "object") return [];
  const out = [];
  for (const [k, v] of Object.entries(p)) {
    if (Array.isArray(v) && v.length && typeof v[0] === "object") {
      const cols = [...new Set(v.flatMap((r) => Object.keys(r)))];
      out.push({ k, label: klabel(k), cols, rows: v });
    }
  }
  return out;
});
async function approve(a) {
  busy.value = true;
  try { await api.call("accounting_portal.api._actions.approve_action", { name: a.name }); toast.success(L("Approved & posted", "تم الاعتماد والترحيل", "Approuvé & passé")); closeDetail(); load(); }
  catch (e) { toast.error(String((e && e.message) || L("Failed", "فشل", "Échec")).slice(0, 160)); }
  finally { busy.value = false; }
}
async function selfApprove(a) {
  const reason = window.prompt(L(
    "No other approver is available. Self-approve this — a reason is required and will be recorded in the audit trail:",
    "لا يوجد موافِق آخر. اعتمده بنفسك — السبب مطلوب وسيُسجَّل في سجل التدقيق:",
    "Auto-approuver — motif requis (journalisé) :"));
  if (!reason || reason.trim().length < 4) return;
  busy.value = true;
  try { await api.call("accounting_portal.api._actions.self_approve_action", { name: a.name, reason: reason.trim() }); toast.success(L("Self-approved & posted", "اعتُمد ذاتيًا وتم الترحيل", "Auto-approuvé")); closeDetail(); load(); }
  catch (e) { toast.error(String((e && e.message) || L("Failed", "فشل", "Échec")).slice(0, 160)); }
  finally { busy.value = false; }
}
async function reject(a) {
  const reason = window.prompt(L("Reason for rejection?", "سبب الرفض؟", "Motif du rejet ?")) || "";
  busy.value = true;
  try { await api.call("accounting_portal.api._actions.reject_action", { name: a.name, reason }); toast.info(L("Rejected", "تم الرفض", "Rejeté")); closeDetail(); load(); }
  catch (e) { toast.error(L("Failed", "فشل", "Échec")); }
  finally { busy.value = false; }
}
async function revert(a) {
  if (!window.confirm(L(
    `Undo "${a.action_type}"? This reverses it — cancelling the voucher it posted, or restoring the prior values.`,
    `تراجع عن "${a.action_type}"؟ هيعكسها — يلغي المستند اللي اترحّل، أو يرجّع القيم القديمة.`,
    `Annuler « ${a.action_type} » ?`))) return;
  busy.value = true;
  try { await api.call("accounting_portal.api._actions.revert_action", { name: a.name }); toast.success(L("Reverted", "تم التراجع", "Annulé")); load(); }
  catch (e) { toast.error(String((e && e.message) || L("Failed", "فشل", "Échec")).slice(0, 160)); }
  finally { busy.value = false; }
}

const PALETTE = {
  Posted: "background:#ecfdf5;color:#047857;border-color:#a7f3d0",
  Approved: "background:#eff6ff;color:#0369a1;border-color:#bae6fd",
  Proposed: "background:#fffbeb;color:#b45309;border-color:#fde68a",
  Rejected: "background:#fef2f2;color:#b91c1c;border-color:#fecaca",
  Failed: "background:#fef2f2;color:#b91c1c;border-color:#fecaca",
  Reverted: "background:#f5f3ff;color:#6d28d9;border-color:#ddd6fe",
};
const badge = (s) => PALETTE[s] || "background:#f5f5f4;color:#57534e;border-color:#e7e5e4";
const shortUser = (u) => (u ? String(u).split("@")[0] : "—");
function when(d) {
  if (!d) return "—";
  return String(d).slice(0, 16).replace("T", " ");
}
</script>
