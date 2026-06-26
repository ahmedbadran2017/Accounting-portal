<template>
  <div v-if="state.exists" class="flex items-center gap-2 px-3 py-2.5 border-b border-line-hair flex-wrap bg-app-warm/30">
    <!-- docstatus pill -->
    <span class="inline-flex items-center gap-1.5 text-[10.5px] font-bold px-2 py-0.5 rounded-full" :style="pill.style">
      <span class="w-1.5 h-1.5 rounded-full" :style="{ background: pill.dot }"></span>{{ pill.label }}
    </span>
    <span v-if="state.amended_to" class="text-[10.5px] text-ink-muted">{{ L("amended →","عُدّل →","amendé →") }} <button class="font-mono text-accent-dark hover:underline" @click="emit('open', state.amended_to)">{{ state.amended_to }}</button></span>

    <!-- assignees -->
    <div class="flex items-center gap-1">
      <span v-for="u in assignList" :key="u" :title="u" class="w-6 h-6 rounded-full grid place-items-center text-[9px] font-bold text-white" :style="{ background: avatarColor(u) }">{{ initials(u) }}</span>
      <div class="relative">
        <button @click="assignOpen = !assignOpen" class="w-6 h-6 rounded-full grid place-items-center border border-dashed border-line-2 text-ink-muted hover:bg-white" :title="L('Assign','إسناد','Assigner')"><Icon name="plus" :size="11" /></button>
        <div v-if="assignOpen" class="absolute z-20 mt-1 start-0 w-52 bg-white border border-line rounded-[10px] shadow-pop py-1 max-h-60 overflow-auto">
          <button v-for="u in users" :key="u.name" @click="assign(u.name)" class="w-full text-start px-3 py-1.5 text-[12px] hover:bg-app-warm flex items-center justify-between">
            <span class="truncate">{{ u.full_name || u.name }}</span>
            <Icon v-if="assignList.includes(u.name)" name="check" :size="12" color="#047857" />
          </button>
          <div v-if="!users.length" class="px-3 py-2 text-[11px] text-ink-muted">{{ L("No users","لا مستخدمين","Aucun") }}</div>
        </div>
      </div>
    </div>

    <div class="ms-auto flex items-center gap-1.5">
      <button v-if="state.can_submit" :disabled="busy" @click="run('submit')" class="inline-flex items-center gap-1 h-7 px-2.5 rounded-chip text-[11px] font-bold text-white bg-success-dark hover:opacity-90 disabled:opacity-50"><Icon name="check" :size="12" color="#fff" />{{ L("Submit","ترحيل","Soumettre") }}</button>
      <button v-if="state.can_cancel" :disabled="busy" @click="confirm = 'cancel'" class="inline-flex items-center gap-1 h-7 px-2.5 rounded-chip text-[11px] font-semibold text-sale border border-sale/30 bg-sale/5 hover:bg-sale/10 disabled:opacity-50"><Icon name="x" :size="12" />{{ L("Cancel doc","إلغاء المستند","Annuler") }}</button>
      <button v-if="state.can_amend" :disabled="busy" @click="confirm = 'amend'" class="inline-flex items-center gap-1 h-7 px-2.5 rounded-chip text-[11px] font-semibold text-ink-2 bg-white border border-line-2 hover:bg-app-warm disabled:opacity-50"><Icon name="refresh" :size="12" />{{ L("Amend","تعديل ونسخ","Amender") }}</button>
    </div>

    <!-- confirm dialog -->
    <div v-if="confirm" class="fixed inset-0 z-50 grid place-items-center bg-ink/30 px-4" @click.self="confirm = ''">
      <div class="bg-white rounded-card shadow-pop w-full max-w-sm p-5">
        <div class="text-[14px] font-bold">{{ confirm === 'cancel' ? L("Cancel this document?","إلغاء هذا المستند؟","Annuler ?") : L("Amend this document?","تعديل ونسخ؟","Amender ?") }}</div>
        <div class="text-[12px] text-ink-3 mt-1.5">
          {{ confirm === 'cancel'
            ? L("This reverses its ledger entries. It can be reopened by amending.","سيعكس قيوده. يمكن إعادته بالتعديل.","Annule ses écritures.")
            : L("Cancels this document and opens an editable copy (a new draft linked to it). Posts above 10,000 need approval.","يلغي المستند ويفتح نسخة قابلة للتعديل. ما فوق 10٬000 يحتاج موافقة.","Annule et ouvre une copie modifiable.") }}
        </div>
        <div class="flex justify-end gap-2 mt-4">
          <button class="px-3.5 py-2 rounded-chip text-[12px] font-semibold text-ink-2 hover:bg-app-warm" @click="confirm = ''">{{ L("Back","رجوع","Retour") }}</button>
          <button class="px-4 py-2 rounded-chip text-[12px] font-bold text-white disabled:opacity-50" :class="confirm === 'cancel' ? 'bg-sale' : 'bg-ink'" :disabled="busy" @click="run(confirm)">{{ busy ? L("Working…","جارٍ…","…") : L("Confirm","تأكيد","Confirmer") }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useToast } from "@/composables/useToast";

const props = defineProps({ doctype: { type: String, required: true }, name: { type: String, required: true } });
const emit = defineEmits(["changed", "open"]);
const { locale } = useI18n();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

const state = reactive({ exists: false, docstatus: 0, can_submit: false, can_cancel: false, can_amend: false, amended_to: null });
const assignList = ref([]);
const users = ref([]);
const busy = ref(false);
const confirm = ref("");
const assignOpen = ref(false);

async function loadState() {
  try {
    const s = await api.call("accounting_portal.api.docops.doc_state", { doctype: props.doctype, name: props.name });
    Object.assign(state, s);
  } catch { state.exists = false; }
  try { assignList.value = await api.call("accounting_portal.api.docops.assignees", { doctype: props.doctype, name: props.name }) || []; } catch { /* */ }
}
async function loadUsers() { try { users.value = await api.call("accounting_portal.api.docops.assignable_users", {}) || []; } catch { /* */ } }
onMounted(() => { loadState(); loadUsers(); });
watch(() => props.name, loadState);

const pill = computed(() => {
  if (state.docstatus === 1) return { label: L("Submitted", "مُرحّل", "Soumis"), style: "background:#ecfdf5;color:#047857", dot: "#047857" };
  if (state.docstatus === 2) return { label: L("Cancelled", "ملغى", "Annulé"), style: "background:#fef2f2;color:#b91c1c", dot: "#b91c1c" };
  return { label: L("Draft", "مسودة", "Brouillon"), style: "background:#fffbeb;color:#b45309", dot: "#b45309" };
});

async function run(op) {
  busy.value = true;
  try {
    const fn = { submit: "doc_submit", cancel: "doc_cancel", amend: "doc_amend" }[op];
    const r = await api.call(`accounting_portal.api.docops.${fn}`, { doctype: props.doctype, name: props.name, company: currentCompany() });
    if (r && r.status && r.status !== "Posted") {
      toast.success(L("Queued for approval (over 10,000)", "بانتظار الموافقة (فوق 10٬000)", "En attente d'approbation"));
    } else if (op === "amend") {
      let res = r && r.result; res = typeof res === "string" ? JSON.parse(res) : res;
      const nd = res && res.new_draft;
      toast.success(L("Amended — editable draft created", "تم — أنشئت مسودة", "Amendé — brouillon créé"));
      if (nd) emit("open", nd);
    } else {
      toast.success(op === "submit" ? L("Submitted", "تم الترحيل", "Soumis") : L("Cancelled", "تم الإلغاء", "Annulé"));
    }
    confirm.value = "";
    await loadState();
    emit("changed");
  } catch (err) { toast.error(String((err && err.message) || L("Failed", "فشل", "Échec")).slice(0, 160)); }
  finally { busy.value = false; }
}

async function assign(user) {
  try {
    const has = assignList.value.includes(user);
    assignList.value = await api.call(`accounting_portal.api.docops.${has ? "unassign_doc" : "assign_doc"}`,
      { doctype: props.doctype, name: props.name, [has ? "from_user" : "to_user"]: user });
    toast.success(has ? L("Unassigned", "أُلغي الإسناد", "Retiré") : L("Assigned", "تم الإسناد", "Assigné"));
  } catch (err) { toast.error(String((err && err.message) || L("Failed", "فشل", "Échec")).slice(0, 140)); }
  assignOpen.value = false;
}

const PAL = ["#7c3aed", "#0369a1", "#047857", "#b45309", "#be123c", "#0891b2"];
function avatarColor(u) { let h = 0; for (const ch of String(u)) h = (h * 31 + ch.charCodeAt(0)) % PAL.length; return PAL[h]; }
function initials(u) { const s = String(u).split("@")[0].replace(/[._-]/g, " ").trim().split(/\s+/); return ((s[0] || "")[0] || "" + (s[1] ? s[1][0] : "")).toUpperCase().slice(0, 2) || "?"; }
</script>
