<template>
  <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
    <!-- Document actions: submit / cancel / amend / assign -->
    <DocActions :doctype="doctype" :name="name" @changed="onChanged" @open="goto" />
    <!-- Toolbar: tags + print + edit -->
    <div class="flex items-center gap-2 px-3 py-2.5 border-b border-line-hair flex-wrap">
      <Icon name="filter" :size="13" color="#a8a29e" />
      <span v-for="tg in tags" :key="tg" class="inline-flex items-center gap-1 text-[10.5px] font-semibold px-2 py-0.5 rounded-full bg-accent-soft text-accent-dark">{{ tg }}<button @click="removeTag(tg)" class="hover:text-sale"><Icon name="x" :size="10" /></button></span>
      <input v-model.trim="newTag" @keyup.enter="addTag" :placeholder="L('+ tag', '+ وسم', '+ tag')" class="w-20 h-6 text-[11px] bg-transparent border-b border-dashed border-line-2 focus:outline-none focus:border-accent/40" />
      <div class="ms-auto flex items-center gap-1.5">
        <button @click="openEdit" class="inline-flex items-center gap-1 h-7 px-2.5 rounded-chip text-[11px] font-semibold text-ink-2 bg-white border border-line-2 hover:bg-app-warm"><Icon name="gear" :size="12" />{{ L("Edit", "تعديل", "Modifier") }}</button>
        <button v-if="canEmail" @click="openEmail" class="inline-flex items-center gap-1 h-7 px-2.5 rounded-chip text-[11px] font-semibold text-ink-2 bg-white border border-line-2 hover:bg-app-warm"><Icon name="send" :size="12" />{{ L("Email", "إيميل", "E-mail") }}</button>
        <a :href="printUrl" target="_blank" rel="noopener" class="inline-flex items-center gap-1 h-7 px-2.5 rounded-chip text-[11px] font-semibold text-white bg-ink hover:opacity-90"><Icon name="doc" :size="12" color="#fff" />{{ L("Print / PDF", "طباعة", "PDF") }}</a>
      </div>
    </div>

    <!-- Tabs -->
    <div class="flex items-center gap-1 px-3 pt-2.5 border-b border-line-hair">
      <button v-for="t in tabs" :key="t.key" @click="tab = t.key"
              class="px-3 py-2 text-[12px] font-semibold rounded-t-[8px] -mb-px border-b-2 transition"
              :class="tab === t.key ? 'border-accent text-accent-dark' : 'border-transparent text-ink-3 hover:text-ink'">
        {{ t.label() }}<span v-if="t.n" class="ms-1 text-[10px] text-ink-muted">{{ t.n }}</span>
      </button>
    </div>

    <!-- Activity -->
    <div v-if="tab === 'activity'" class="p-4">
      <div v-if="loadingAct" class="py-4"><TableLoading :rows="3" /></div>
      <div v-else-if="!events.length" class="py-6 text-center text-[12px] text-ink-muted">{{ L("No activity yet.", "لا نشاط بعد.", "Aucune activité.") }}</div>
      <div v-else class="space-y-3">
        <div v-for="(e, i) in events" :key="i" class="flex gap-2.5">
          <span class="w-7 h-7 rounded-full grid place-items-center flex-shrink-0 mt-0.5" :style="{ background: EV[e.type].bg }"><Icon :name="EV[e.type].icon" :size="13" :color="EV[e.type].fg" /></span>
          <div class="flex-1 min-w-0">
            <div class="text-[12px]">
              <span class="font-semibold">{{ shortUser(e.by) }}</span>
              <span class="text-ink-3"> {{ EV[e.type].verb() }}</span>
            </div>
            <div v-if="e.type === 'comment'" class="text-[12px] text-ink-2 bg-app-warm/50 rounded-[8px] px-2.5 py-1.5 mt-1 whitespace-pre-wrap">{{ e.content }}</div>
            <div v-else-if="e.type === 'changed'" class="text-[11px] text-ink-muted mt-0.5">
              <span v-for="(c, j) in e.changes" :key="j" class="me-2"><b>{{ c.field }}</b>: {{ trunc(c.from) }} → {{ trunc(c.to) }}</span>
            </div>
            <div class="text-[10.5px] text-ink-muted mt-0.5">{{ fmtDate(e.on) }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Attachments -->
    <div v-else-if="tab === 'attachments'" class="p-4">
      <div class="flex items-center gap-2 mb-3">
        <label class="inline-flex items-center gap-1.5 h-8 px-3 rounded-chip text-[12px] font-bold text-white bg-accent hover:bg-accent-dark cursor-pointer" :class="uploading ? 'opacity-60 pointer-events-none' : ''">
          <Icon name="plus" :size="13" color="#fff" />{{ uploading ? L("Uploading…", "جارٍ الرفع…", "…") : L("Upload file", "ارفع ملف", "Téléverser") }}
          <input type="file" class="hidden" @change="onFile" />
        </label>
        <span class="text-[11px] text-ink-muted">{{ files.length }} {{ L("files", "ملف", "fichiers") }}</span>
      </div>
      <div v-if="loadingFiles" class="py-3"><TableLoading :rows="2" /></div>
      <div v-else-if="!files.length" class="py-5 text-center text-[12px] text-ink-muted">{{ L("No attachments.", "لا مرفقات.", "Aucune pièce jointe.") }}</div>
      <div v-else class="space-y-1.5">
        <div v-for="f in files" :key="f.name" class="flex items-center gap-2.5 px-2.5 py-2 rounded-[9px] border border-line-2 hover:bg-app-warm/40">
          <Icon name="doc" :size="15" color="#0b5c4f" class="flex-shrink-0" />
          <a :href="fileHref(f)" target="_blank" rel="noopener" class="flex-1 min-w-0 text-[12px] font-medium truncate hover:text-accent-dark">{{ f.file_name }}</a>
          <span class="text-[10.5px] text-ink-muted whitespace-nowrap">{{ f.kb }} KB</span>
          <button @click="remove(f)" class="text-ink-muted hover:text-sale flex-shrink-0"><Icon name="x" :size="13" /></button>
        </div>
      </div>
    </div>

    <!-- Notes -->
    <div v-else class="p-4">
      <textarea v-model="note" :placeholder="L('Add a note or reference…', 'أضف ملاحظة أو مرجعًا…', 'Ajouter une note…')" rows="3"
                class="w-full border border-line-2 rounded-[10px] px-3 py-2 text-[12.5px] focus:outline-none focus:border-accent/40 resize-y"></textarea>
      <div class="flex justify-end mt-2">
        <button @click="postNote" :disabled="posting || !note.trim()" class="inline-flex items-center gap-1.5 h-9 px-4 rounded-[9px] text-[12px] font-bold text-white bg-accent hover:bg-accent-dark disabled:opacity-50">
          <Icon name="check" :size="13" color="#fff" />{{ posting ? L("Posting…", "جارٍ…", "…") : L("Post note", "أضف", "Publier") }}
        </button>
      </div>
      <div v-if="notes.length" class="mt-3 space-y-2">
        <div v-for="(e, i) in notes" :key="i" class="bg-app-warm/50 rounded-[9px] px-2.5 py-2">
          <div class="text-[12px] text-ink-2 whitespace-pre-wrap">{{ e.content }}</div>
          <div class="text-[10.5px] text-ink-muted mt-0.5">{{ shortUser(e.by) }} · {{ fmtDate(e.on) }}</div>
        </div>
      </div>
    </div>

    <!-- Edit modal -->
    <div v-if="editOpen" class="fixed inset-0 z-50 grid place-items-center bg-black/30 p-4" @click.self="editOpen = false">
      <div class="bg-white rounded-card shadow-xl w-full max-w-sm p-5 space-y-3">
        <div class="text-[14px] font-bold">{{ L("Edit document", "تعديل المستند", "Modifier") }}</div>
        <div v-if="!editFields.length" class="text-[12px] text-ink-muted py-4 text-center">{{ L("No editable fields here.", "لا حقول قابلة للتعديل.", "Aucun champ modifiable.") }}</div>
        <div v-for="f in editFields" :key="f.field">
          <label class="text-[11px] font-bold text-ink-3">{{ f.label }}</label>
          <input v-model="f.value" :type="f.type === 'Date' ? 'date' : 'text'" class="w-full h-9 mt-1 border border-line-2 rounded-[9px] px-2 text-[12.5px] focus:outline-none focus:border-accent/40" />
        </div>
        <div class="flex gap-2 justify-end pt-1">
          <button @click="editOpen = false" class="h-9 px-3 rounded-[9px] text-[12px] font-semibold text-ink-3 hover:bg-app-warm">{{ L("Cancel", "إلغاء", "Annuler") }}</button>
          <button v-if="editFields.length" @click="saveEdit" :disabled="savingEdit" class="h-9 px-4 rounded-[9px] text-[12px] font-bold text-white bg-accent disabled:opacity-50">{{ savingEdit ? L("Saving…", "حفظ…", "…") : L("Save", "حفظ", "Enregistrer") }}</button>
        </div>
      </div>
    </div>

    <!-- Email modal -->
    <div v-if="emailOpen" class="fixed inset-0 z-50 grid place-items-center bg-black/30 p-4" @click.self="emailOpen = false">
      <div class="bg-white rounded-card shadow-xl w-full max-w-sm p-5 space-y-3">
        <div class="flex items-center gap-2"><span class="w-8 h-8 rounded-[9px] grid place-items-center" style="background:#eff6ff"><Icon name="send" :size="15" color="#0369a1" /></span><div class="text-[14px] font-bold">{{ L("Email document", "إرسال بالإيميل", "Envoyer par e-mail") }}</div></div>
        <div><label class="text-[11px] font-bold text-ink-3">{{ L("To", "إلى", "À") }}</label><input v-model.trim="em.recipients" :placeholder="L('email@…  (comma-separated)', 'بريد إلكتروني', 'email@…')" class="w-full h-9 mt-1 border border-line-2 rounded-[9px] px-2 text-[12.5px] focus:outline-none focus:border-accent/40" /></div>
        <div><label class="text-[11px] font-bold text-ink-3">{{ L("Subject", "الموضوع", "Objet") }}</label><input v-model.trim="em.subject" class="w-full h-9 mt-1 border border-line-2 rounded-[9px] px-2 text-[12.5px] focus:outline-none focus:border-accent/40" /></div>
        <div><label class="text-[11px] font-bold text-ink-3">{{ L("Message", "الرسالة", "Message") }}</label><textarea v-model="em.message" rows="3" class="w-full mt-1 border border-line-2 rounded-[9px] px-2 py-1.5 text-[12.5px] focus:outline-none focus:border-accent/40 resize-y"></textarea></div>
        <p class="text-[10px] text-ink-muted">{{ L("The document PDF is attached automatically.", "ملف PDF يُرفق تلقائيًا.", "Le PDF est joint automatiquement.") }}</p>
        <div class="flex gap-2 justify-end pt-1">
          <button @click="emailOpen = false" class="h-9 px-3 rounded-[9px] text-[12px] font-semibold text-ink-3 hover:bg-app-warm">{{ L("Cancel", "إلغاء", "Annuler") }}</button>
          <button @click="sendEmail" :disabled="sending || !em.recipients" class="h-9 px-4 rounded-[9px] text-[12px] font-bold text-white bg-accent disabled:opacity-50">{{ sending ? L("Sending…", "إرسال…", "…") : L("Send", "إرسال", "Envoyer") }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import DocActions from "@/components/DocActions.vue";
import api from "@/services/api";
import { useToast } from "@/composables/useToast";

const props = defineProps({ doctype: { type: String, required: true }, name: { type: String, required: true } });
const emit = defineEmits(["changed"]);
const route = useRoute();
const router = useRouter();
const { locale } = useI18n();
const toast = useToast();
// Refresh the activity timeline + tell the parent detail page to reload its data.
function onChanged() { loadActivity(); emit("changed"); }
// Navigate to a related document (e.g. the new draft created by Amend).
function goto(name) { router.replace({ path: route.path, query: { ...route.query, id: name } }); }
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

const EV = {
  created: { icon: "plus", bg: "#eff6ff", fg: "#0369a1", verb: () => L("created this", "أنشأ هذا", "a créé") },
  submitted: { icon: "check", bg: "#ecfdf5", fg: "#047857", verb: () => L("submitted", "رحّل", "a soumis") },
  cancelled: { icon: "x", bg: "#fef2f2", fg: "#be123c", verb: () => L("cancelled", "ألغى", "a annulé") },
  changed: { icon: "refresh", bg: "#fffbeb", fg: "#b45309", verb: () => L("edited", "عدّل", "a modifié") },
  comment: { icon: "send", bg: "#f5f3ff", fg: "#6d28d9", verb: () => L("noted", "علّق", "a noté") },
};
const shortUser = (u) => String(u || "").split("@")[0];
const trunc = (v) => { const s = String(v ?? ""); return s.length > 24 ? s.slice(0, 24) + "…" : (s || "∅"); };
const fmtDate = (s) => String(s || "").slice(0, 16).replace("T", " ");

const tab = ref("activity");
const events = ref([]);
const files = ref([]);
const loadingAct = ref(false);
const loadingFiles = ref(false);
const uploading = ref(false);
const posting = ref(false);
const note = ref("");
const notes = computed(() => events.value.filter((e) => e.type === "comment"));
const tabs = computed(() => [
  { key: "activity", label: () => L("Activity", "النشاط", "Activité"), n: events.value.length },
  { key: "attachments", label: () => L("Attachments", "المرفقات", "Pièces jointes"), n: files.value.length },
  { key: "notes", label: () => L("Notes", "الملاحظات", "Notes"), n: notes.value.length },
]);

async function loadActivity() {
  loadingAct.value = true;
  try { events.value = (await api.call("accounting_portal.api.docmeta.get_activity", { doctype: props.doctype, name: props.name })).events || []; }
  catch { events.value = []; }
  finally { loadingAct.value = false; }
}
async function loadFiles() {
  loadingFiles.value = true;
  try { files.value = await api.call("accounting_portal.api.docmeta.list_attachments", { doctype: props.doctype, name: props.name }) || []; }
  catch { files.value = []; }
  finally { loadingFiles.value = false; }
}
function fileHref(f) { return f.file_url; }

function onFile(e) {
  const file = e.target.files[0]; if (!file) return;
  if (file.size > 10 * 1024 * 1024) { toast.error(L("Max 10 MB", "الحد 10 ميجا", "Max 10 Mo")); return; }
  uploading.value = true;
  const reader = new FileReader();
  reader.onload = async () => {
    try { await api.call("accounting_portal.api.docmeta.add_attachment", { doctype: props.doctype, name: props.name, filename: file.name, content: reader.result }); toast.success(L("Uploaded", "تم الرفع", "Téléversé")); loadFiles(); }
    catch (err) { toast.error(String((err && err.message) || L("Upload failed", "فشل الرفع", "Échec")).slice(0, 140)); }
    finally { uploading.value = false; e.target.value = ""; }
  };
  reader.readAsDataURL(file);
}
async function remove(f) {
  if (!window.confirm(L(`Delete ${f.file_name}?`, `حذف ${f.file_name}؟`, `Supprimer ${f.file_name} ?`))) return;
  try { await api.call("accounting_portal.api.docmeta.remove_attachment", { file: f.name }); loadFiles(); }
  catch (e) { toast.error(L("Failed", "فشل", "Échec")); }
}
async function postNote() {
  posting.value = true;
  try { await api.call("accounting_portal.api.docmeta.add_note", { doctype: props.doctype, name: props.name, content: note.value }); note.value = ""; toast.success(L("Note added", "تمت الإضافة", "Note ajoutée")); loadActivity(); }
  catch (e) { toast.error(L("Failed", "فشل", "Échec")); }
  finally { posting.value = false; }
}

// ── Tags ──
const tags = ref([]);
const newTag = ref("");
async function loadTags() {
  try { tags.value = await api.call("accounting_portal.api.docmeta.get_tags", { doctype: props.doctype, name: props.name }) || []; }
  catch { tags.value = []; }
}
async function addTag() {
  if (!newTag.value.trim()) return;
  try { tags.value = (await api.call("accounting_portal.api.docmeta.add_tag", { doctype: props.doctype, name: props.name, tag: newTag.value })).tags || tags.value; newTag.value = ""; }
  catch (e) { toast.error(L("Failed", "فشل", "Échec")); }
}
async function removeTag(tg) {
  try { tags.value = (await api.call("accounting_portal.api.docmeta.remove_tag", { doctype: props.doctype, name: props.name, tag: tg })).tags || []; }
  catch (e) { toast.error(L("Failed", "فشل", "Échec")); }
}

// ── Print / PDF (Frappe's native renderer) ──
const printUrl = computed(() => `/api/method/frappe.utils.print_format.download_pdf?doctype=${encodeURIComponent(props.doctype)}&name=${encodeURIComponent(props.name)}&no_letterhead=0`);

// ── Edit fields ──
const editOpen = ref(false);
const editFields = ref([]);
const savingEdit = ref(false);
async function openEdit() {
  editOpen.value = true; editFields.value = [];
  try { editFields.value = (await api.call("accounting_portal.api.docmeta.editable_fields", { doctype: props.doctype, name: props.name })).fields || []; }
  catch { editFields.value = []; }
}
async function saveEdit() {
  savingEdit.value = true;
  try {
    const fields = {}; editFields.value.forEach((f) => { fields[f.field] = f.value; });
    await api.call("accounting_portal.api.docmeta.update_doc_fields", { doctype: props.doctype, name: props.name, fields });
    editOpen.value = false; toast.success(L("Saved", "تم الحفظ", "Enregistré")); loadActivity();
  } catch (e) { toast.error(String((e && e.message) || L("Save failed", "فشل الحفظ", "Échec")).slice(0, 140)); }
  finally { savingEdit.value = false; }
}

// ── Email ──
const canEmail = computed(() => !["Customer", "Supplier"].includes(props.doctype));
const emailOpen = ref(false);
const sending = ref(false);
const em = ref({ recipients: "", subject: "", message: "" });
async function openEmail() {
  em.value = { recipients: "", subject: `${props.doctype} ${props.name}`, message: L(`Please find attached ${props.doctype} ${props.name}.`, `مرفق ${props.doctype} ${props.name}.`, `Veuillez trouver ci-joint ${props.doctype} ${props.name}.`) };
  emailOpen.value = true;
  try { const r = await api.call("accounting_portal.api.docmeta.default_recipient", { doctype: props.doctype, name: props.name }); if (r && r.email) em.value.recipients = r.email; } catch { /* keep blank */ }
}
async function sendEmail() {
  sending.value = true;
  try {
    await api.call("accounting_portal.api.docmeta.email_document", { doctype: props.doctype, name: props.name, recipients: em.value.recipients, subject: em.value.subject, message: em.value.message });
    emailOpen.value = false; toast.success(L("Email sent", "تم الإرسال", "E-mail envoyé")); loadActivity();
  } catch (e) { toast.error(String((e && e.message) || L("Send failed", "فشل الإرسال", "Échec")).slice(0, 160)); }
  finally { sending.value = false; }
}

watch(() => [props.doctype, props.name], () => { if (props.name) { loadActivity(); loadFiles(); loadTags(); } }, { immediate: true });
</script>
