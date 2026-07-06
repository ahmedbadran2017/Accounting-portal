<template>
  <div class="fixed inset-0 z-[100] flex items-start justify-center p-4 sm:p-8 overflow-y-auto" style="background:rgba(28,25,23,.45)" @click.self="$emit('close')">
    <div class="bg-white rounded-[18px] shadow-cardHover w-full max-w-2xl my-6 overflow-hidden">
      <div class="flex items-center gap-2.5 px-5 py-4 border-b border-line">
        <span class="w-8 h-8 rounded-[10px] grid place-items-center" style="background:#eff6ff"><Icon name="bank" :size="16" color="#0369a1" /></span>
        <div class="flex-1 min-w-0">
          <div class="text-[14px] font-bold">{{ L("Import bank statement", "استيراد كشف البنك", "Importer le relevé") }}</div>
          <div class="text-[11px] text-ink-muted truncate">{{ accountName }} · {{ L("upload → match → reconcile", "رفع ← مطابقة ← تسوية", "importer → rapprocher") }}</div>
        </div>
        <button class="text-ink-3 hover:text-ink" @click="$emit('close')"><Icon name="close" :size="18" /></button>
      </div>

      <div class="p-5 space-y-4">
        <!-- step 1: upload -->
        <div>
          <div class="text-[11px] font-bold uppercase tracking-wider text-ink-muted mb-1.5">{{ L("1 · Statement file", "1 · ملف الكشف", "1 · Fichier") }}</div>
          <label class="flex items-center gap-3 border border-dashed border-line-2 rounded-card px-4 py-3 cursor-pointer hover:bg-app-warm/40">
            <Icon name="doc" :size="18" color="#0369a1" />
            <span class="text-[12px] text-ink-2 flex-1 truncate">{{ fileName || L("Choose a CSV, Excel or PDF file…", "اختر ملف CSV أو Excel أو PDF…", "Choisir un fichier…") }}</span>
            <span v-if="uploading" class="text-[11px] text-ink-muted">{{ L("uploading…", "جارٍ الرفع…", "…") }}</span>
            <input type="file" accept=".csv,.xlsx,.xlsm,.pdf" class="hidden" @change="onFile" />
          </label>
          <div v-if="parseErr" class="text-[11.5px] text-sale mt-1.5">{{ parseErr }}</div>
        </div>

        <!-- step 2: parsed preview + mapping -->
        <div v-if="parsed">
          <div class="text-[11px] font-bold uppercase tracking-wider text-ink-muted mb-1.5 flex items-center gap-2">
            {{ L("2 · Parsed", "2 · المقروء", "2 · Analysé") }}
            <span class="text-[11px] font-semibold text-success-dark">{{ parsed.count }} {{ L("transactions", "حركة", "transactions") }}</span>
          </div>
          <!-- column mapping (override auto-detect) -->
          <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-2">
            <label v-for="f in MAP_FIELDS" :key="f.k" class="text-[10.5px]">
              <span class="text-ink-3 font-semibold">{{ f.label() }}</span>
              <select v-model.number="mapping[f.k]" class="mt-0.5 w-full h-8 bg-app-warm/40 border border-line-2 rounded-chip px-2 text-[11px] focus:outline-none" @change="reparse">
                <option :value="null">—</option>
                <option v-for="(h, i) in parsed.header" :key="i" :value="i">{{ h || ('col ' + (i + 1)) }}</option>
              </select>
            </label>
          </div>
          <div class="border border-line rounded-[10px] overflow-x-auto max-h-32 overflow-y-auto">
            <table class="w-full text-[10.5px]"><tbody>
              <tr v-for="(row, i) in parsed.preview" :key="i" :class="i === 0 ? 'bg-app-warm/60 font-bold' : 'border-t border-line-hair'">
                <td v-for="(c, j) in row" :key="j" class="px-2 py-1 truncate max-w-[120px]">{{ c }}</td>
              </tr>
            </tbody></table>
          </div>
        </div>

        <!-- step 3: match results -->
        <div v-if="result">
          <div class="text-[11px] font-bold uppercase tracking-wider text-ink-muted mb-1.5">{{ L("3 · Match", "3 · المطابقة", "3 · Rapprochement") }}</div>
          <div class="grid grid-cols-3 gap-2">
            <div class="rounded-card border border-emerald-200 bg-emerald-50/60 px-3 py-2.5">
              <div class="text-[10px] font-bold uppercase tracking-wider text-emerald-700">{{ L("Matched", "مطابَق", "Rapprochés") }}</div>
              <div class="text-[18px] font-extrabold tnum text-emerald-700">{{ result.matched_n }}</div>
              <div class="text-[10px] text-ink-muted tnum">{{ money(result.matched_value) }}</div>
            </div>
            <div class="rounded-card border border-amber-200 bg-amber-50/60 px-3 py-2.5">
              <div class="text-[10px] font-bold uppercase tracking-wider text-amber-700">{{ L("On bank only", "في البنك فقط", "Banque seule") }}</div>
              <div class="text-[18px] font-extrabold tnum text-amber-700">{{ result.statement_only_n }}</div>
              <div class="text-[10px] text-ink-muted">{{ L("missing in books", "ناقص بالدفاتر", "manquant") }}</div>
            </div>
            <div class="rounded-card border border-sky-200 bg-sky-50/60 px-3 py-2.5">
              <div class="text-[10px] font-bold uppercase tracking-wider text-sky-700">{{ L("In books only", "بالدفاتر فقط", "Livres seuls") }}</div>
              <div class="text-[18px] font-extrabold tnum text-sky-700">{{ result.book_only_n }}</div>
              <div class="text-[10px] text-ink-muted">{{ L("still outstanding", "لسه معلّق", "en attente") }}</div>
            </div>
          </div>
          <!-- detail toggler -->
          <div class="flex gap-1 mt-2">
            <button v-for="t in TABS" :key="t.k" class="text-[11px] font-semibold px-2.5 py-1 rounded-full border" :class="detail === t.k ? 'bg-ink text-white border-ink' : 'bg-white text-ink-3 border-line-2'" @click="detail = t.k">{{ t.label() }} ({{ t.n() }})</button>
          </div>
          <div class="border border-line rounded-[10px] mt-1.5 max-h-40 overflow-y-auto">
            <table class="w-full text-[11px]"><tbody>
              <tr v-for="(r, i) in detailRows" :key="i" class="border-t border-line-hair first:border-t-0">
                <td class="px-3 py-1.5 whitespace-nowrap text-ink-2">{{ r.date || r.dt }}</td>
                <td class="px-3 py-1.5 truncate max-w-[240px]">{{ r.description || r.party || r.voucher }}<span v-if="r.voucher" class="text-ink-muted font-mono"> · {{ r.voucher }}</span></td>
                <td class="px-3 py-1.5 text-end tnum font-semibold" :class="(r.amount ?? r.amt) < 0 ? 'text-rose-500' : ''">{{ money(r.amount ?? r.amt) }}</td>
              </tr>
              <tr v-if="!detailRows.length"><td class="px-3 py-4 text-center text-ink-muted">—</td></tr>
            </tbody></table>
          </div>
        </div>
      </div>

      <div class="flex items-center justify-between gap-2 px-5 py-3.5 border-t border-line bg-app-warm/40">
        <span class="text-[10.5px] text-ink-muted">{{ L("Reconciling only stamps a clearance date — no ledger impact, reversible.", "التسوية بتحط تاريخ مطابقة فقط — بدون أثر على الأستاذ.", "Rapprochement seul — réversible.") }}</span>
        <div class="flex items-center gap-2">
          <button class="px-3.5 py-2 rounded-chip text-[12px] font-semibold text-ink-2 hover:bg-white" @click="$emit('close')">{{ L("Cancel", "إلغاء", "Annuler") }}</button>
          <button v-if="parsed && !result" class="px-4 py-2 rounded-chip text-[12px] font-bold text-white bg-ink hover:brightness-110 disabled:opacity-50" :disabled="matching || !parsed.count" @click="doMatch">{{ matching ? "…" : L("Match", "طابِق", "Rapprocher") }}</button>
          <button v-if="result" class="px-4 py-2 rounded-chip text-[12px] font-bold text-white bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50" :disabled="reconciling || !result.matched_n" @click="doReconcile">{{ reconciling ? "…" : L("Reconcile", "سوِّ", "Rapprocher") + " " + result.matched_n }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useToast } from "@/composables/useToast";
import { getCsrfToken } from "@/utils/helpers";
import { fmtAmount } from "@/utils/helpers";

const props = defineProps({ account: { type: String, required: true }, accountName: { type: String, default: "" } });
const emit = defineEmits(["close", "done"]);
const { locale } = useI18n();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const money = (n) => fmtAmount(n);

const MAP_FIELDS = [
  { k: "date", label: () => L("Date col", "عمود التاريخ", "Date") },
  { k: "amount", label: () => L("Amount col", "عمود المبلغ", "Montant") },
  { k: "debit", label: () => L("Debit col", "عمود المدين", "Débit") },
  { k: "credit", label: () => L("Credit col", "عمود الدائن", "Crédit") },
];
const TABS = [
  { k: "matched", label: () => L("Matched", "مطابَق", "OK"), n: () => result.value?.matched_n || 0 },
  { k: "statement_only", label: () => L("Bank only", "بنك فقط", "Banque"), n: () => result.value?.statement_only_n || 0 },
  { k: "book_only", label: () => L("Books only", "دفاتر فقط", "Livres"), n: () => result.value?.book_only_n || 0 },
];

const fileUrl = ref(""), fileName = ref(""), uploading = ref(false), parseErr = ref("");
const parsed = ref(null), mapping = reactive({ date: null, amount: null, debit: null, credit: null, desc: null });
const result = ref(null), matching = ref(false), reconciling = ref(false), detail = ref("statement_only");

const detailRows = computed(() => {
  if (!result.value) return [];
  if (detail.value === "matched") return result.value.matched.map((m) => m.statement);
  return result.value[detail.value] || [];
});

async function onFile(e) {
  const f = e.target.files[0];
  if (!f) return;
  fileName.value = f.name; parseErr.value = ""; parsed.value = null; result.value = null;
  uploading.value = true;
  try {
    const fd = new FormData();
    fd.append("file", f); fd.append("is_private", 1); fd.append("folder", "Home");
    const res = await fetch("/api/method/upload_file", { method: "POST", headers: { "X-Frappe-CSRF-Token": getCsrfToken() }, body: fd });
    const body = await res.json();
    if (!res.ok) throw new Error(body?._server_messages || "Upload failed");
    fileUrl.value = body.message.file_url;
    await reparse();
  } catch (err) { parseErr.value = String(err?.message || err).slice(0, 200); }
  finally { uploading.value = false; }
}

async function reparse() {
  if (!fileUrl.value) return;
  parseErr.value = "";
  try {
    // First parse: no mapping → backend auto-detects. Re-parse after the user
    // touched a select: send the FULL mapping (nulls included) so "—" clears a
    // column instead of the auto-detect re-filling it.
    const userMapping = parsed.value ? { ...mapping } : undefined;
    parsed.value = await api.call("accounting_portal.api.bank_import.parse_statement", { file_url: fileUrl.value, mapping: userMapping }, { fresh: true });
    if (parsed.value.columns) Object.assign(mapping, { date: parsed.value.columns.date, amount: parsed.value.columns.amount, debit: parsed.value.columns.debit, credit: parsed.value.columns.credit, desc: parsed.value.columns.desc });
    result.value = null;
  } catch (err) { parseErr.value = String(err?.message || err).slice(0, 200); parsed.value = null; }
}

async function doMatch() {
  if (!parsed.value?.transactions?.length) return;
  matching.value = true;
  try {
    result.value = await api.call("accounting_portal.api.bank_import.match_statement", { company: currentCompany(), account: props.account, transactions: parsed.value.transactions }, { fresh: true });
    detail.value = result.value.statement_only_n ? "statement_only" : "matched";
  } catch (err) { toast.error(String(err?.message || err).slice(0, 200)); }
  finally { matching.value = false; }
}

async function doReconcile() {
  if (!result.value?.matched_n) return;
  if (!window.confirm(L(`Reconcile ${result.value.matched_n} matched entr(ies)?`, `تسوية ${result.value.matched_n} قيد مطابَق؟`, `Rapprocher ${result.value.matched_n} ?`))) return;
  reconciling.value = true;
  try {
    const entries = result.value.matched.map((m) => ({ doctype: m.book.doctype, name: m.book.voucher }));
    await api.call("accounting_portal.api.reconciliation.mark_bank_cleared", { company: currentCompany(), entries });
    toast.success(L(`${entries.length} reconciled`, `تمت تسوية ${entries.length}`, `${entries.length} rapprochés`));
    emit("done"); emit("close");
  } catch (err) { toast.error(String(err?.message || err).slice(0, 200)); }
  finally { reconciling.value = false; }
}
</script>
