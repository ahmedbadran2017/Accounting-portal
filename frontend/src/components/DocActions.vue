<template>
  <div v-if="state.exists || flow.creates.length" class="flex items-center gap-2 px-3 py-2.5 border-b border-line-hair flex-wrap bg-app-warm/30">
    <!-- docstatus pill -->
    <span class="inline-flex items-center gap-1.5 text-[11px] font-bold px-2 py-0.5 rounded-full" :style="pill.style">
      <span class="w-1.5 h-1.5 rounded-full" :style="{ background: pill.dot }"></span>{{ pill.label }}
    </span>
    <span v-if="state.amended_to" class="text-[11px] text-ink-muted">{{ L("amended →","عُدّل →","amendé →") }} <button class="font-mono text-accent-dark hover:underline" @click="emit('open', state.amended_to)">{{ state.amended_to }}</button></span>

    <!-- assignees -->
    <div class="flex items-center gap-1">
      <span v-for="u in assignList" :key="u" :title="u" class="w-6 h-6 rounded-full grid place-items-center text-[11px] font-bold text-white" :style="{ background: avatarColor(u) }">{{ initials(u) }}</span>
      <div class="relative">
        <button @click="assignOpen = !assignOpen; if (assignOpen) loadUsers();" class="w-6 h-6 rounded-full grid place-items-center border border-dashed border-line-2 text-ink-muted hover:bg-white" :title="L('Assign','إسناد','Assigner')"><Icon name="plus" :size="11" /></button>
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
      <!-- Create → : every linked document the Desk offers, as a portal draft -->
      <div v-if="flow.creates.length" class="relative">
        <UiButton variant="create" size="sm" icon="plus" :disabled="busy" @click="createOpen = !createOpen">{{ L("Create","إنشاء","Créer") }} ▾</UiButton>
        <div v-if="createOpen" class="absolute z-20 mt-1 end-0 w-56 bg-white border border-line rounded-[10px] shadow-pop py-1">
          <button v-for="c in flow.creates" :key="c.key" @click="createFrom(c)" class="w-full text-start px-3 py-1.5 text-[12px] hover:bg-app-warm flex items-center gap-2">
            <Icon name="doc" :size="12" color="#0b5c4f" /><span>{{ flowLabel(c) }}</span>
          </button>
        </div>
      </div>
      <UiButton v-for="s in flow.statuses" :key="s.key" variant="secondary" size="sm"
                :icon="s.key === 'close' || s.key === 'hold' ? 'lock' : 'refresh'"
                :disabled="busy" @click="setStatus(s)">{{ statusLabel(s) }}</UiButton>
      <UiButton v-if="state.docstatus === 1 && GL_DOCTYPES.includes(props.doctype)" variant="secondary" size="sm" icon="ledger" :title="L('Rebuild this document\'s ledger entries from the document','إعادة بناء قيود هذا المستند من المستند نفسه','Reconstruire les écritures')" :disabled="busy" @click="confirm = 'repost'">{{ L("Repost ledger","إعادة ترحيل القيود","Reposter") }}</UiButton>
      <UiButton v-if="state.exists" variant="secondary" size="sm" icon="copy" :title="L('Copy into a new draft','نسخ كمسودة جديدة','Copier en brouillon')" :disabled="busy" @click="run('duplicate')">{{ L("Duplicate","نسخ","Dupliquer") }}</UiButton>
      <UiButton v-if="state.exists && state.docstatus === 0" variant="danger" size="sm" icon="close" :disabled="busy" @click="confirm = 'delete'">{{ L("Delete draft","حذف المسودة","Supprimer") }}</UiButton>
      <UiButton v-if="state.can_submit" variant="primary" size="sm" icon="check" :disabled="busy" @click="run('submit')">{{ L("Submit","ترحيل","Soumettre") }}</UiButton>
      <UiButton v-if="state.can_cancel" variant="danger" size="sm" icon="x" :disabled="busy" @click="confirm = 'cancel'">{{ L("Cancel doc","إلغاء المستند","Annuler") }}</UiButton>
      <UiButton v-if="state.can_amend" variant="secondary" size="sm" icon="refresh" :disabled="busy" @click="confirm = 'amend'">{{ L("Amend","تعديل ونسخ","Amender") }}</UiButton>
      <!-- the single most common amendment on the Desk (JE ×221, PE ×160 in a quarter): one click -->
      <UiButton v-if="state.can_amend && REDATE_OK.includes(props.doctype)" variant="secondary" size="sm" icon="clock" :disabled="busy" @click="newDate = ''; confirm = 'redate'">{{ L("Change date","تغيير التاريخ","Changer la date") }}</UiButton>
    </div>

    <!-- confirm dialog -->
    <div v-if="confirm" class="fixed inset-0 z-50 grid place-items-center bg-ink/30 px-4" @click.self="confirm = ''">
      <div class="bg-white rounded-card shadow-pop w-full max-w-sm p-5">
        <div class="text-[14px] font-bold">{{ confirm === 'cancel' ? L("Cancel this document?","إلغاء هذا المستند؟","Annuler ?") : confirm === 'delete' ? L("Delete this draft?","حذف هذه المسودة؟","Supprimer ce brouillon ?") : confirm === 'repost' ? L("Repost this document's ledger?","إعادة ترحيل قيود هذا المستند؟","Reposter les écritures ?") : confirm === 'redate' ? L("Move this document to another date","نقل المستند لتاريخ آخر","Changer la date") : L("Amend this document?","تعديل ونسخ؟","Amender ?") }}</div>
        <div class="text-[12px] text-ink-3 mt-1.5">
          {{ confirm === 'cancel'
            ? L("This reverses its ledger entries. It can be reopened by amending.","سيعكس قيوده. يمكن إعادته بالتعديل.","Annule ses écritures.")
            : confirm === 'delete'
            ? L("The draft is removed for good. Nothing was posted, so nothing reverses.","المسودة هتتحذف نهائيًا. مفيش حاجة اترحّلت فمفيش حاجة تتعكس.","Le brouillon est supprimé définitivement.")
            : confirm === 'repost'
            ? L("ERPNext deletes and rebuilds this voucher's GL entries from the document as it stands now (Repost Accounting Ledger). Use after an after-submit account change.","ERPNext بيمسح قيود المستند ويعيد بناءها من المستند بوضعه الحالي (Repost Accounting Ledger). استخدمه بعد تغيير حساب بعد الترحيل.","Reconstruit les écritures du document.")
            : confirm === 'redate'
            ? L("Cancels it, re-creates it as an amendment with the new date and submits — same lines, same amounts. Posts above 10,000 need approval.","يلغيه وينشئه من جديد كتعديل بالتاريخ الجديد ويرحّله، بنفس السطور والمبالغ. ما فوق 10٬000 يحتاج موافقة.","Annule, recrée avec la nouvelle date et soumet.")
            : L("Cancels this document and opens an editable copy (a new draft linked to it). Posts above 10,000 need approval.","يلغي المستند ويفتح نسخة قابلة للتعديل. ما فوق 10٬000 يحتاج موافقة.","Annule et ouvre une copie modifiable.") }}
        </div>
        <div v-if="confirm === 'redate'" class="mt-3">
          <label class="block text-[11px] font-bold text-ink-3 mb-1">{{ L("New posting date","التاريخ الجديد","Nouvelle date") }}</label>
          <input type="date" v-model="newDate" class="h-9 w-full rounded-[9px] border border-line-2 px-2.5 text-[13px] bg-white focus:outline-none focus:border-accent/40" />
        </div>
        <div class="flex justify-end gap-2 mt-4">
          <UiButton variant="quiet" @click="confirm = ''">{{ L("Back","رجوع","Retour") }}</UiButton>
          <UiButton :variant="confirm === 'cancel' || confirm === 'delete' ? 'danger' : 'primary'" :busy="busy"
                    :disabled="busy || (confirm === 'redate' && !newDate)" @click="run(confirm)">{{ busy ? L("Working…","جارٍ…","…") : L("Confirm","تأكيد","Confirmer") }}</UiButton>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import Icon from "@/components/Icon.vue";
import UiButton from "@/components/UiButton.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useToast } from "@/composables/useToast";

const props = defineProps({ doctype: { type: String, required: true }, name: { type: String, required: true } });
const emit = defineEmits(["changed", "open", "failed"]);
const { locale } = useI18n();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

const state = reactive({ exists: false, docstatus: 0, can_submit: false, can_cancel: false, can_amend: false, amended_to: null });
const assignList = ref([]);
const users = ref([]);
const busy = ref(false);
const confirm = ref("");
const assignOpen = ref(false);
const newDate = ref("");
const REDATE_OK = ["Journal Entry", "Payment Entry", "Purchase Invoice", "Sales Invoice", "Additional Salary"];
const GL_DOCTYPES = ["Journal Entry", "Payment Entry", "Purchase Invoice", "Sales Invoice", "Delivery Note", "Purchase Receipt"];
const router = useRouter();

// ── Create-from / status actions (api/docflow) ──
const flow = reactive({ creates: [], statuses: [] });
const createOpen = ref(false);
const FLOW_LABELS = {
  sales_invoice: ["Sales invoice", "فاتورة بيع", "Facture de vente"], delivery_note: ["Delivery note", "إذن تسليم", "Bon de livraison"],
  payment: ["Payment", "دفعة", "Paiement"], credit_note: ["Credit note (return)", "إشعار دائن (مرتجع)", "Avoir (retour)"],
  sales_return: ["Sales return", "مرتجع بيع", "Retour de vente"], purchase_receipt: ["Purchase receipt", "إيصال استلام", "Réception"],
  purchase_invoice: ["Purchase invoice", "فاتورة شراء", "Facture d'achat"], purchase_return: ["Purchase return", "مرتجع شراء", "Retour d'achat"],
  lcv: ["Landed cost voucher", "قسيمة تكلفة الشحن", "Coûts d'approche"], debit_note: ["Debit note (return)", "إشعار مدين (مرتجع)", "Note de débit"],
  reverse: ["Reverse entry", "قيد عكسي", "Écriture inverse"], pay: ["Pay advance", "صرف السلفة", "Payer l'avance"], return: ["Return balance", "رد الباقي", "Retour du solde"],
};
const STATUS_LABELS = { close: ["Close", "إقفال", "Clôturer"], reopen: ["Reopen", "إعادة فتح", "Rouvrir"], hold: ["Put on hold", "تعليق", "Suspendre"], unhold: ["Release hold", "إلغاء التعليق", "Lever"] };
const flowLabel = (c) => { const l = FLOW_LABELS[c.key]; return l ? L(...l) : c.label; };
const statusLabel = (s) => { const l = STATUS_LABELS[s.key]; return l ? L(...l) : s.label; };
const ROUTE = {
  "Sales Order": "/accounting/sales/orders", "Sales Invoice": "/accounting/sales/invoices", "Delivery Note": "/accounting/sales/challans",
  "Purchase Order": "/accounting/purchases/tobuy", "Purchase Receipt": "/accounting/purchases/received", "Purchase Invoice": "/accounting/purchases/bills",
  "Journal Entry": "/accounting/accountant/journals", "Landed Cost Voucher": "/accounting/items/landed",
};
function routeFor(res) {
  if (res.doctype === "Payment Entry") return res.payment_type === "Receive" ? "/accounting/sales/payments" : "/accounting/purchases/payments";
  return ROUTE[res.doctype] || null;
}
async function loadFlow() {
  try { Object.assign(flow, (await api.call("accounting_portal.api.docflow.options", { doctype: props.doctype, name: props.name }, { fresh: true })) || { creates: [], statuses: [] }); }
  catch { flow.creates = []; flow.statuses = []; }
}
async function createFrom(c) {
  createOpen.value = false; busy.value = true;
  try {
    const r = await api.call("accounting_portal.api.docflow.create", { doctype: props.doctype, name: props.name, key: c.key, company: currentCompany() });
    let res = r && r.result; res = typeof res === "string" ? JSON.parse(res) : res;
    if (!res || !res.new_doc) { toast.success(L("Created", "تم الإنشاء", "Créé")); return; }
    toast.success(`${flowLabel(c)} · ${res.new_doc} — ${L("draft, review then submit", "مسودة، راجعها ثم رحّل", "brouillon, vérifier puis soumettre")}`);
    const path = routeFor(res);
    if (path) router.push({ path, query: { id: res.new_doc } });
    emit("changed");
  } catch (err) { toast.error(String((err && err.message) || L("Failed", "فشل", "Échec")).slice(0, 200)); }
  finally { busy.value = false; }
}
async function setStatus(s) {
  busy.value = true;
  try {
    await api.call("accounting_portal.api.docflow.set_status", { doctype: props.doctype, name: props.name, key: s.key, company: currentCompany() });
    toast.success(statusLabel(s));
    await loadState(); emit("changed");
  } catch (err) { toast.error(String((err && err.message) || L("Failed", "فشل", "Échec")).slice(0, 200)); }
  finally { busy.value = false; }
}

// 12s, not the request layer's 45s: an action bar that has not appeared after
// twelve seconds is a fault, and the accountant should be told rather than left
// looking at a document with no actions on it.
function withDeadline(p, ms = 12000) {
  return Promise.race([p, new Promise((_, reject) =>
    setTimeout(() => reject(new Error("No response after " + Math.round(ms / 1000) + "s")), ms))]);
}

async function loadState() {
  try {
    const s = await withDeadline(api.call("accounting_portal.api.docops.doc_state", { doctype: props.doctype, name: props.name }));
    Object.assign(state, s);
    emit("failed", false);
  } catch (e) {
    // The whole bar is hidden when nothing loads, which reads exactly like a
    // document that simply has no actions. Tell the parent so it can say so.
    state.exists = false;
    emit("failed", String(e?.message || e).slice(0, 160) || true);
  }
  try { assignList.value = await api.call("accounting_portal.api.docops.assignees", { doctype: props.doctype, name: props.name }) || []; } catch { /* */ }
  loadFlow();
}
async function loadUsers() { try { users.value = await api.call("accounting_portal.api.docops.assignable_users", {}) || []; } catch { /* */ } }
// loadUsers fetched every assignable user on mount for a menu almost nobody
// opens. It waits for the menu now.
onMounted(() => { loadState(); });
watch(() => props.name, loadState);

const pill = computed(() => {
  if (state.docstatus === 1) return { label: L("Submitted", "مُرحّل", "Soumis"), style: "background:#ecfdf5;color:#047857", dot: "#047857" };
  if (state.docstatus === 2) return { label: L("Cancelled", "ملغى", "Annulé"), style: "background:#fef2f2;color:#b91c1c", dot: "#b91c1c" };
  return { label: L("Draft", "مسودة", "Brouillon"), style: "background:#fffbeb;color:#b45309", dot: "#b45309" };
});

async function run(op) {
  busy.value = true;
  try {
    const fn = { submit: "doc_submit", cancel: "doc_cancel", amend: "doc_amend", duplicate: "doc_duplicate", delete: "doc_delete" }[op];
    const r = op === "redate"
      ? await api.call("accounting_portal.api.docedit.redate", { doctype: props.doctype, name: props.name, posting_date: newDate.value, company: currentCompany() })
      : op === "repost"
      ? await api.call("accounting_portal.api.docedit.repost_ledger", { doctype: props.doctype, name: props.name, company: currentCompany() })
      : await api.call(`accounting_portal.api.docops.${fn}`, { doctype: props.doctype, name: props.name, company: currentCompany() });
    if (op === "repost") {
      toast.success(L("Ledger repost queued", "تم طلب إعادة الترحيل", "Repost lancé") + (r?.repost ? " · " + r.repost : ""));
      confirm.value = ""; emit("changed"); return;
    }
    if (r && r.status && r.status !== "Posted") {
      toast.success(L("Queued for approval (over 10,000)", "بانتظار الموافقة (فوق 10٬000)", "En attente d'approbation"));
    } else if (op === "amend" || op === "redate" || op === "duplicate") {
      let res = r && r.result; res = typeof res === "string" ? JSON.parse(res) : res;
      const nd = res && (res.new_draft || res.new_doc);
      toast.success(op === "redate" ? L("Redated and submitted", "تم النقل والترحيل", "Redaté et soumis")
        : op === "duplicate" ? L("Copied — new draft opened", "تم النسخ، اتفتحت مسودة جديدة", "Copié — nouveau brouillon")
        : L("Amended — editable draft created", "تم — أنشئت مسودة", "Amendé — brouillon créé"));
      if (nd) emit("open", nd);
    } else if (op === "delete") {
      toast.success(L("Draft deleted", "تم حذف المسودة", "Brouillon supprimé"));
      confirm.value = "";
      router.replace({ path: router.currentRoute.value.path, query: {} });
      emit("changed");
      return;
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
