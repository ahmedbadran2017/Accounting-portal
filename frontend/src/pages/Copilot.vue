<template>
  <div class="flex rounded-[14px] border border-line overflow-hidden shadow-card bg-white" style="height:calc(100vh - 104px)">
    <!-- CFO control: findings + team tasks (docked sidebar) -->
    <div class="hidden md:flex w-[340px] lg:w-[380px] flex-shrink-0 border-e border-line flex-col min-h-0" style="background:rgba(255,255,255,.55)">
      <div class="px-4 pt-[15px] pb-3 border-b border-line-hair">
        <div class="flex items-center gap-2">
          <span class="text-[13.5px] font-bold">{{ L("CFO control","مدير الحسابات","Contrôle CFO") }}</span>
          <span v-if="live" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full text-success-dark bg-success-soft">{{ L("LIVE","مباشر","LIVE") }}</span>
        </div>
        <div class="text-[11px] text-ink-muted mt-0.5">{{ L("Issues found + tasks for the accounting team","المشاكل المكتشَفة + تاسكات للفريق","Problèmes + tâches de l'équipe") }}</div>
        <div class="flex items-center gap-1.5 mt-2.5">
          <button @click="view = 'findings'" class="text-[11px] font-bold px-2.5 py-1 rounded-full border transition inline-flex items-center gap-1" :class="view === 'findings' ? 'bg-ink text-white border-ink' : 'bg-white text-ink-3 border-line-2'">{{ L("Findings","المشاكل","Constats") }}<span class="text-[9px] px-1 rounded-full" :class="view === 'findings' ? 'bg-white/20' : 'bg-app-warm'">{{ feed.length }}</span></button>
          <button @click="view = 'tasks'; loadBoard()" class="text-[11px] font-bold px-2.5 py-1 rounded-full border transition inline-flex items-center gap-1" :class="view === 'tasks' ? 'bg-ink text-white border-ink' : 'bg-white text-ink-3 border-line-2'">{{ L("Tasks","التاسكات","Tâches") }}<span class="text-[9px] px-1 rounded-full" :class="view === 'tasks' ? 'bg-white/20' : 'bg-app-warm'">{{ (board.summary && board.summary.open) || 0 }}</span></button>
          <button @click="autoPlan" :disabled="planning || !feed.length" class="ms-auto text-[11px] font-bold px-2.5 py-1 rounded-full text-white disabled:opacity-50" style="background:linear-gradient(135deg,#7c3aed,#5b21b6)">{{ planning ? "…" : L("Auto-plan","خطّة تلقائية","Auto-plan") }}</button>
        </div>
      </div>

      <!-- Findings -->
      <div v-if="view === 'findings'" class="flex-1 overflow-y-auto min-h-0 p-3 flex flex-col gap-2.5">
        <div v-for="a in feed" :key="a.id" class="border border-line rounded-[12px] p-3 bg-white shadow-card">
          <div class="flex items-start gap-2.5">
            <span class="w-7 h-7 rounded-[8px] grid place-items-center flex-shrink-0" :style="{ background: sev(a).bg }"><Icon :name="a.icon" :size="14" :color="sev(a).fg" /></span>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-1.5 flex-wrap">
                <span class="text-[12px] font-bold">{{ a.title(locale) }}</span>
                <span class="text-[9px] font-bold px-1.5 py-0.5 rounded-badge border" :style="{ background: sev(a).bg, color: sev(a).fg, borderColor: sev(a).bd }">{{ sevLabel(a.sev, locale) }}</span>
                <span v-if="assigned[a.id]" class="text-[9px] font-bold px-1.5 py-0.5 rounded-badge bg-success-soft text-success-dark inline-flex items-center gap-0.5"><Icon name="check" :size="9" />{{ shortUser(assigned[a.id]) }}</span>
              </div>
              <div class="text-[11px] text-ink-3 mt-[3px] leading-snug">{{ a.desc(locale) }}</div>
            </div>
          </div>
          <div class="flex items-center gap-[7px] mt-2.5">
            <button class="h-7 px-2.5 rounded-[8px] bg-white border border-line-2 text-ink-2 text-[11px] font-semibold hover:bg-app-warm" @click="investigate(a)">{{ L("Investigate","تحقّق","Enquêter") }}</button>
            <div class="flex-1"></div>
            <div class="relative">
              <button class="h-7 px-2.5 rounded-[8px] bg-white border border-line-2 text-ink-2 text-[11px] font-semibold hover:bg-app-warm inline-flex items-center gap-1" :disabled="busy === a.id" @click="assignOpen = assignOpen === a.id ? '' : a.id"><Icon name="user" :size="11" />{{ busy === a.id ? "…" : L("Assign","إسناد","Assigner") }}</button>
              <div v-if="assignOpen === a.id" class="absolute end-0 bottom-8 z-20 w-48 bg-white border border-line rounded-[10px] shadow-pop py-1 max-h-52 overflow-auto">
                <button v-for="u in users" :key="u.name" @click="assign(a, u.name)" class="w-full text-start px-3 py-1.5 text-[12px] hover:bg-app-warm truncate">{{ u.full_name || u.name }}</button>
                <div v-if="!users.length" class="px-3 py-2 text-[11px] text-ink-muted">{{ L("No users","لا مستخدمين","Aucun") }}</div>
              </div>
            </div>
            <button class="h-7 px-2.5 rounded-[8px] text-[11px] font-bold" style="background:#faf6f4;border:1px solid #f3e4de;color:#0b5c4f" @click="go(a.go)">{{ a.cta(locale) }}</button>
          </div>
        </div>
        <div v-if="!feed.length" class="text-center text-[12px] text-success-dark py-10"><Icon name="check" :size="22" color="#047857" /><div class="mt-1 font-semibold">{{ L("No open findings.","لا مشاكل مفتوحة.","Aucun constat.") }}</div></div>
      </div>

      <!-- Team tasks -->
      <div v-else class="flex-1 overflow-y-auto min-h-0 p-3 flex flex-col gap-2">
        <div v-for="t in board.tasks" :key="t.task" class="border border-line rounded-[12px] p-3 bg-white">
          <div class="flex items-start gap-2">
            <span class="w-6 h-6 rounded-full grid place-items-center text-[9px] font-bold text-white flex-shrink-0" :style="{ background: avatar(t.assigned_to) }">{{ initials(t.assigned_to) }}</span>
            <div class="flex-1 min-w-0">
              <div class="text-[12px] font-bold leading-snug">{{ t.title }}</div>
              <div class="text-[10.5px] text-ink-muted mt-0.5 flex items-center gap-1.5 flex-wrap"><span>{{ shortUser(t.assigned_to) }}</span><span class="font-bold px-1.5 rounded-badge" :style="prioStyle(t.priority)">{{ t.priority }}</span><span>{{ L("due","حتى","éch.") }} {{ t.due }}</span></div>
            </div>
            <button v-if="t.status === 'Open'" class="h-7 px-2 rounded-[8px] text-[10.5px] font-bold text-success-dark bg-success-soft hover:opacity-80" @click="done(t)">{{ L("Done","تم","Fait") }}</button>
            <span v-else class="text-[10px] font-bold text-ink-muted">{{ L("Closed","مغلق","Fermé") }}</span>
          </div>
        </div>
        <div v-if="!board.tasks || !board.tasks.length" class="text-center text-[12px] text-ink-muted py-10">{{ L("No tasks yet — assign a finding or hit Auto-plan.","لا تاسكات بعد — أسند مشكلة أو استخدم الخطة التلقائية.","Aucune tâche — assignez ou Auto-plan.") }}</div>
      </div>
    </div>

    <!-- Chat -->
    <div class="flex-1 flex flex-col min-w-0 min-h-0" style="background:linear-gradient(180deg,#faf9f8,#f6f4f2)">
      <div ref="thread" class="flex-1 overflow-y-auto min-h-0 px-4 sm:px-6 py-[22px] flex flex-col gap-3.5">
        <div v-for="(m, i) in messages" :key="i" class="flex gap-[11px]" :class="m.role === 'user' ? 'justify-end' : 'items-start'">
          <span v-if="m.role !== 'user'" class="w-[30px] h-[30px] rounded-[9px] grid place-items-center text-white flex-shrink-0 self-start" style="background:linear-gradient(135deg,#a78bfa,#7c3aed)"><Icon name="shield" :size="16" color="#fff" /></span>
          <div :class="m.role === 'user' ? 'max-w-[82%]' : 'max-w-[80%]'">
            <div class="rounded-[14px] px-3.5 py-2.5 text-[13px] leading-relaxed" :class="m.role === 'user' ? 'bg-accent text-white' : 'bg-white border border-line text-ink'">{{ m.text }}</div>

            <!-- Proposed-journal action card -->
            <div v-if="m.proposal" class="mt-2.5 rounded-[12px] overflow-hidden" style="border:1px solid #e9d5ff;background:#faf7ff">
              <div class="flex items-center gap-1.5 px-3 py-2.5 border-b" style="border-color:#ede4fb"><Icon name="shield" :size="12" color="#7c3aed" /><span class="text-[11.5px] font-bold" style="color:#5b21b6">{{ m.proposal.title }}</span></div>
              <table class="w-full bg-white">
                <tbody>
                  <tr v-for="(l, k) in m.proposal.lines" :key="k" class="border-t border-line-hair">
                    <td class="px-3 py-[7px] text-[11px] text-ink-2 font-mono">{{ l.acc }}</td>
                    <td class="px-2 py-[7px] text-end text-[11px] font-semibold text-success-dark w-24">{{ l.dr || "" }}</td>
                    <td class="px-3 py-[7px] text-end text-[11px] font-semibold text-sale w-24">{{ l.cr || "" }}</td>
                  </tr>
                </tbody>
              </table>
              <div class="flex items-center gap-2.5 px-3 py-2.5 border-t" style="border-color:#ede4fb">
                <span class="flex-1 text-[10.5px]" style="color:#7c3aed">{{ m.proposal.note }}</span>
                <button v-if="!m.proposal.queued" class="h-[30px] px-3 rounded-[8px] text-white text-[11px] font-bold" style="background:linear-gradient(135deg,#7c3aed,#5b21b6)" @click="queue(m)">{{ L("Approve & queue","اعتماد وإرسال","Approuver & mettre en file") }}</button>
                <span v-else class="inline-flex items-center gap-1.5 text-[11px] font-bold px-2.5 py-[5px] rounded-[8px]" style="background:#ecfdf5;color:#047857;border:1px solid #a7f3d0"><Icon name="check" :size="12" />{{ L("Queued for checker","في طابور المراجع","En file validateur") }}</span>
              </div>
            </div>
          </div>
        </div>
        <div v-if="typing" class="flex gap-[11px] items-start">
          <span class="w-[30px] h-[30px] rounded-[9px] grid place-items-center text-white flex-shrink-0" style="background:linear-gradient(135deg,#a78bfa,#7c3aed)"><Icon name="shield" :size="16" color="#fff" /></span>
          <div class="bg-white border border-line rounded-[14px] px-4 py-3 flex gap-1">
            <span class="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse"></span>
            <span class="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" style="animation-delay:.2s"></span>
            <span class="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" style="animation-delay:.4s"></span>
          </div>
        </div>
      </div>

      <!-- Composer -->
      <div class="px-4 sm:px-5 pt-3 pb-[18px] border-t border-line" style="background:rgba(255,255,255,.7)">
        <div class="flex gap-2 mb-2.5 flex-wrap">
          <button v-for="s in suggestions" :key="s" class="px-3 py-[7px] rounded-full bg-white border border-line-2 text-ink-2 text-[11.5px] font-medium hover:bg-app-warm" @click="quick(s)">{{ s }}</button>
        </div>
        <div class="flex items-center gap-2.5 bg-white border border-line-2 rounded-[13px] ps-3.5 pe-2 py-[7px] shadow-card">
          <Icon name="shield" :size="15" color="#a8a29e" />
          <input v-model="draft" :placeholder="L('Ask your CFO…','اسأل مدير الحسابات…','Demandez au CFO…')"
                 class="flex-1 bg-transparent border-none outline-none text-[13px]" @keydown.enter="send" />
          <button class="w-[34px] h-[34px] rounded-[10px] grid place-items-center text-white flex-shrink-0" style="background:linear-gradient(135deg,#7c3aed,#5b21b6)" @click="send"><Icon name="send" :size="16" /></button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, nextTick, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { SEV_META, sevLabel, seedMessages, replyTo } from "@/data/copilot";
import { loadControls, feedFrom } from "@/composables/useAuditor";
import { usePersistedRef } from "@/composables/usePersistedRef";
import { useUi } from "@/composables/useUi";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useToast } from "@/composables/useToast";

const { locale } = useI18n();
const router = useRouter();
const { entityId } = useUi();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

const messages = reactive(seedMessages(locale.value));
const draft = ref("");
const typing = ref(false);
const thread = ref(null);
const sev = (a) => SEV_META[a.sev] || SEV_META.low;

const feed = ref([]);
const live = ref(false);
async function loadFeed() {
  const r = await loadControls();
  live.value = r.live;
  feed.value = feedFrom(r.data && r.data.findings);
}

// ── CFO task board ──
const view = usePersistedRef("ap_copilot_view", "findings");
const users = ref([]);
const board = ref({ tasks: [], summary: {} });
const assigned = reactive({});
const assignOpen = ref("");
const busy = ref("");
const planning = ref(false);
async function loadUsers() { try { users.value = await api.call("accounting_portal.api.docops.assignable_users", {}) || []; } catch { /* */ } }
async function loadBoard() {
  try { board.value = await api.call("accounting_portal.api.auditor.remediation_board", { company: currentCompany() }); (board.value.tasks || []).forEach((t) => { if (t.finding_id) assigned[t.finding_id] = t.assigned_to; }); } catch { /* */ }
}
async function assign(a, user) {
  busy.value = a.id; assignOpen.value = "";
  try {
    await api.call("accounting_portal.api.auditor.assign_finding", { company: currentCompany(), finding_id: a.id, to_user: user });
    assigned[a.id] = user; toast.success(L("Task assigned", "تم إسناد التاسك", "Tâche assignée")); loadBoard();
  } catch (e) { toast.error(String((e && e.message) || L("Failed", "فشل", "Échec")).slice(0, 140)); }
  finally { busy.value = ""; }
}
async function autoPlan() {
  planning.value = true;
  try {
    const r = await api.call("accounting_portal.api.auditor.auto_plan", { company: currentCompany() });
    toast.success(L(`Planned ${r.created} task(s)`, `تم إنشاء ${r.created} تاسك`, `${r.created} tâche(s)`));
    await loadBoard(); view.value = "tasks";
  } catch (e) { toast.error(String((e && e.message) || L("Failed", "فشل", "Échec")).slice(0, 140)); }
  finally { planning.value = false; }
}
async function done(t) {
  try { await api.call("accounting_portal.api.auditor.close_task", { task: t.task }); t.status = "Closed"; if (board.value.summary) board.value.summary.open = Math.max(0, (board.value.summary.open || 1) - 1); toast.success(L("Marked done", "تم", "Fait")); }
  catch (e) { toast.error(String((e && e.message) || L("Failed", "فشل", "Échec")).slice(0, 140)); }
}
const PAL = ["#7c3aed", "#0369a1", "#047857", "#b45309", "#be123c", "#0891b2"];
const avatar = (u) => { let h = 0; for (const ch of String(u || "?")) h = (h * 31 + ch.charCodeAt(0)) % PAL.length; return PAL[h]; };
const initials = (u) => { const s = String(u || "?").split("@")[0].replace(/[._-]/g, " ").trim().split(/\s+/); return ((s[0] || "")[0] + (s[1] ? s[1][0] : "")).toUpperCase().slice(0, 2) || "?"; };
const shortUser = (u) => (u ? String(u).split("@")[0] : "—");
const prioStyle = (p) => ({ High: "background:#fef2f2;color:#b91c1c", Medium: "background:#fffbeb;color:#b45309", Low: "background:#f5f5f4;color:#57534e" }[p] || "");

const suggestions = [
  L("What should we fix first?", "ما الأولوية للإصلاح؟", "Que corriger d'abord ?"),
  L("Give me a remediation plan", "أعطني خطة معالجة", "Donne un plan de correction"),
  L("Who should own each issue?", "من يتولّى كل مشكلة؟", "Qui gère chaque problème ?"),
];

function scrollEnd() { nextTick(() => { if (thread.value) thread.value.scrollTop = thread.value.scrollHeight; }); }

async function send() {
  const text = draft.value.trim();
  if (!text) return;
  messages.push({ role: "user", text });
  draft.value = "";
  scrollEnd();
  typing.value = true;
  try {
    const r = await api.call("accounting_portal.api.auditor.ask_auditor", { question: text, company: currentCompany() });
    messages.push({ role: "ai", text: r.answer, source: r.source });
  } catch {
    messages.push(replyTo(text, locale.value)); // offline fallback
  } finally {
    typing.value = false;
    scrollEnd();
  }
}
function quick(s) { draft.value = s; send(); }
function investigate(a) { draft.value = `${L("Investigate", "تحقّق من", "Enquêter sur")} ${a.ref} — ${a.title(locale.value)}`; send(); }
function queue(m) { m.proposal.queued = true; }
function go(g) { if (g) router.push(g.sub ? `/accounting/${g.module}/${g.sub}` : `/accounting/${g.module}`); }

onMounted(() => { scrollEnd(); loadFeed(); loadUsers(); loadBoard(); });
</script>
