<template>
  <div class="space-y-3.5">
    <button type="button" class="inline-flex items-center gap-1.5 text-[12px] font-semibold text-ink-3 hover:text-ink" @click="$emit('back')">
      <Icon name="arrow" :size="13" class="rotate-180 rtl:rotate-0" />{{ L("Back to reconciliation", "رجوع للتسوية", "Retour") }}
    </button>

    <div v-if="loading" class="p-10 text-center text-ink-muted text-[12px]">{{ L("Loading…","جارٍ التحميل…","…") }}</div>
    <template v-else-if="d.name">
      <!-- header -->
      <div class="bg-white rounded-card border border-line shadow-card p-4">
        <div class="flex items-center gap-3 flex-wrap">
          <span class="w-10 h-10 rounded-[12px] grid place-items-center" style="background:#eff6ff"><Icon name="doc" :size="18" color="#0369a1" /></span>
          <div class="flex-1 min-w-0">
            <div class="text-[14px] font-bold truncate">{{ d.file_name }} <span class="text-[10px] font-mono text-ink-muted">{{ d.name }}</span></div>
            <div class="text-[11px] text-ink-muted">{{ d.account }} · {{ d.from_date }} → {{ d.to_date }} · {{ L("by","بواسطة","par") }} {{ d.owner }}</div>
          </div>
          <div class="flex items-center gap-2 flex-wrap text-[11px] font-semibold">
            <span class="px-2.5 py-1 rounded-chip bg-app-warm text-ink-2">{{ d.n_total }} {{ L("lines","سطر","lignes") }}</span>
            <span class="px-2.5 py-1 rounded-chip" style="background:#ecfdf5;color:#047857">✓ {{ d.n_matched }}</span>
            <span class="px-2.5 py-1 rounded-chip" style="background:#eff6ff;color:#0369a1">➕ {{ d.n_created }}</span>
            <span class="px-2.5 py-1 rounded-chip" style="background:#f5f5f4;color:#78716c">👁 {{ d.n_ignored }}</span>
            <span class="px-2.5 py-1 rounded-chip font-bold" :class="pendingN ? 'bg-amber-50 text-amber-800' : 'bg-emerald-50 text-emerald-700'">{{ pendingN ? pendingN + " " + L("pending","متبقي","restants") : L("Done 🎉","خلصت 🎉","Terminé") }}</span>
          </div>
        </div>
      </div>

      <!-- filters -->
      <div class="flex flex-wrap items-center gap-1 bg-white border border-line rounded-chip p-1 w-fit">
        <button v-for="fl in FILTERS" :key="fl.k" type="button" class="px-3 py-1.5 rounded-lg text-[12px]"
                :class="filter === fl.k ? 'text-accent-dark font-semibold bg-app-warm shadow-card' : 'text-ink-3 font-medium hover:text-ink'"
                @click="filter = fl.k">{{ fl.label() }} <span class="text-[10px] text-ink-muted">{{ fl.n() }}</span></button>
      </div>

      <!-- lines, chronological -->
      <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-[12px]">
            <thead><tr style="background:#fafaf9" class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">
              <th class="px-4 py-2 text-start">{{ L("Date","التاريخ","Date") }}</th>
              <th class="px-3 py-2 text-start">{{ L("Description","الوصف","Description") }}</th>
              <th class="px-3 py-2 text-end">{{ L("Amount","المبلغ","Montant") }}</th>
              <th class="px-3 py-2 text-start">{{ L("Status","الحالة","Statut") }}</th>
              <th class="px-4 py-2 text-end">{{ L("Action","الإجراء","Action") }}</th>
            </tr></thead>
            <tbody>
              <tr v-for="l in visible" :key="l.i" class="border-t border-line-hair" :class="l.status==='pending' ? 'hover:bg-amber-50/40' : 'hover:bg-app-warm/30'">
                <td class="px-4 py-2 whitespace-nowrap text-ink-3">{{ l.date }}</td>
                <td class="px-3 py-2 max-w-[340px]"><div class="truncate" :title="l.description">{{ l.description || "—" }}</div>
                  <div v-if="l.reason" class="text-[10px] text-ink-muted">{{ L("reason","السبب","raison") }}: {{ l.reason }}</div>
                </td>
                <td class="px-3 py-2 text-end tnum font-semibold whitespace-nowrap" :class="l.amount < 0 ? 'text-sale' : 'text-success-dark'">{{ l.amount < 0 ? "−" : "+" }}{{ money(Math.abs(l.amount)) }}</td>
                <td class="px-3 py-2 whitespace-nowrap">
                  <span v-if="l.status==='matched'" class="text-[10.5px] font-semibold px-2 py-0.5 rounded-chip" style="background:#ecfdf5;color:#047857">✓ {{ l.voucher }}</span>
                  <span v-else-if="l.status==='created'" class="text-[10.5px] font-semibold px-2 py-0.5 rounded-chip" style="background:#eff6ff;color:#0369a1">➕ {{ l.voucher }}</span>
                  <span v-else-if="l.status==='ignored'" class="text-[10.5px] font-semibold px-2 py-0.5 rounded-chip" style="background:#f5f5f4;color:#78716c">👁 {{ L("ignored","متجاهَل","ignoré") }}</span>
                  <span v-else class="text-[10.5px] font-semibold px-2 py-0.5 rounded-chip bg-amber-50 text-amber-800">{{ L("missing in books","ناقص في الدفاتر","manquant") }}</span>
                  <div v-if="l.by && l.by!=='auto'" class="text-[9.5px] text-ink-muted mt-0.5">{{ l.by.split("@")[0] }} · {{ l.at }}</div>
                </td>
                <td class="px-4 py-2 text-end whitespace-nowrap">
                  <div v-if="canWrite && l.status==='pending'" class="inline-flex items-center gap-1.5">
                    <button type="button" class="h-7 px-2.5 rounded-chip text-[11px] font-bold text-white bg-brand hover:bg-brand-dark" @click="openRegister(l)">{{ L("Register","سجّل","Créer") }}</button>
                    <button type="button" class="h-7 px-2.5 rounded-chip text-[11px] font-semibold text-accent-dark border border-line-2 hover:bg-app-warm" @click="openMatch(l)">{{ L("Match","اربط","Lier") }}</button>
                    <button type="button" class="h-7 px-2 rounded-chip text-[11px] text-ink-3 hover:bg-app-warm" @click="ignore(l)">{{ L("Ignore","تجاهل","Ignorer") }}</button>
                  </div>
                  <button v-else-if="canWrite && l.status!=='pending'" type="button" class="text-[10.5px] text-ink-muted hover:text-sale hover:underline" @click="reset(l)">{{ L("undo","تراجع","annuler") }}</button>
                </td>
              </tr>
              <tr v-if="!visible.length"><td colspan="5" class="px-4 py-10 text-center text-ink-muted">{{ L("Nothing in this filter.","مفيش حاجة في الفلتر ده.","Rien ici.") }}</td></tr>
            </tbody>
          </table>
        </div>
        <div class="px-4 py-2 border-t border-line-hair text-[10.5px] text-ink-muted flex items-center gap-1.5">
          <Icon name="alert" :size="11" color="#9a8f86" />{{ L("Register opens the expense form (supplier bill or quick cash) prefilled from the line; Match links an existing uncleared entry and marks it reconciled at the line's date.","«سجّل» بيفتح فورم المصروفات (فاتورة مورّد أو مصروف فوري) متعبي من السطر؛ «اربط» بيوصل قيد موجود ويعلّمه مُسوّى بتاريخ السطر.","Créer / Lier / Ignorer.") }}
        </div>
      </div>

      <!-- match modal -->
      <div v-if="matching" class="fixed inset-0 z-[110] flex items-start justify-center p-4 sm:p-10 overflow-y-auto" style="background:rgba(28,25,23,.45)" @click.self="matching=null">
        <div class="bg-white rounded-[18px] shadow-cardHover w-full max-w-2xl my-8 overflow-hidden">
          <div class="flex items-center gap-2.5 px-5 py-4 border-b border-line">
            <span class="w-8 h-8 rounded-[10px] grid place-items-center" style="background:#ecfdf5"><Icon name="check" :size="16" color="#047857" /></span>
            <div class="flex-1"><div class="text-[14px] font-bold">{{ L("Match to a book entry","اربط بقيد في الدفاتر","Lier à une écriture") }}</div>
              <div class="text-[11px] text-ink-muted tnum">{{ matching.date }} · {{ matching.description?.slice(0,60) }} · <b :class="matching.amount<0 ? 'text-sale' : 'text-success-dark'">{{ money(matching.amount) }}</b></div></div>
            <button class="text-ink-3 hover:text-ink" @click="matching=null"><Icon name="close" :size="18" /></button>
          </div>
          <div class="p-4">
            <div v-if="candBusy" class="py-8 text-center text-ink-muted text-[12px]">{{ L("Searching…","جارٍ البحث…","…") }}</div>
            <table v-else-if="cands.length" class="w-full text-[12px]">
              <tbody>
                <tr v-for="c in cands" :key="c.voucher" class="border-t border-line-hair hover:bg-app-warm/40">
                  <td class="px-3 py-2 font-mono text-[11px]">{{ c.voucher }}<div class="text-[9.5px] text-ink-muted font-sans">{{ c.voucher_type }}</div></td>
                  <td class="px-3 py-2 text-ink-3 whitespace-nowrap">{{ c.date }}</td>
                  <td class="px-3 py-2 truncate max-w-[180px] text-[11px]">{{ c.party || c.ref }}</td>
                  <td class="px-3 py-2 text-end tnum font-semibold" :class="c.amount<0 ? 'text-sale' : 'text-success-dark'">{{ money(c.amount) }}</td>
                  <td class="px-3 py-2 text-end"><button type="button" class="h-7 px-3 rounded-chip text-[11px] font-bold text-white bg-emerald-600 hover:bg-emerald-700" @click="doMatch(c)">{{ L("Link","اربط","Lier") }}</button></td>
                </tr>
              </tbody>
            </table>
            <div v-else class="py-8 text-center text-[12px] text-ink-muted">{{ L("No close uncleared entry — use Register to create it.","مفيش قيد قريب غير مُسوّى — استخدم «سجّل» لإنشائه.","Aucune correspondance.") }}</div>
          </div>
        </div>
      </div>

      <NewExpenseModal v-if="registering" :prefill="regPrefill" @close="registering=false" @posted="onRegistered" />
    </template>
    <div v-else class="p-10 text-center text-ink-muted text-[12px]">{{ L("Import not found.","الاستيراد مش موجود.","Introuvable.") }}</div>
  </div>
</template>

<script setup>
import { ref, computed } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import NewExpenseModal from "@/components/NewExpenseModal.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useAuth } from "@/composables/useAuth";
import { useToast } from "@/composables/useToast";
import { fmtAmount } from "@/utils/helpers";

const props = defineProps({ importName: { type: String, required: true } });
defineEmits(["back"]);
const { locale } = useI18n();
const { can } = useAuth();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const money = (n) => fmtAmount(n);
const canWrite = computed(() => can("post_entries"));

const d = ref({});
const loading = ref(true);
const filter = ref("pending");
const matching = ref(null), cands = ref([]), candBusy = ref(false);
const registering = ref(false), regPrefill = ref(null), regLine = ref(null);

const lines = computed(() => d.value.lines || []);
const pendingN = computed(() => lines.value.filter((l) => l.status === "pending").length);
const FILTERS = [
  { k: "all", label: () => L("All", "الكل", "Tout"), n: () => lines.value.length },
  { k: "pending", label: () => L("Missing", "الناقص", "Manquant"), n: () => pendingN.value },
  { k: "matched", label: () => L("Matched", "متطابق", "Lié"), n: () => lines.value.filter((l) => l.status === "matched").length },
  { k: "created", label: () => L("Created", "اتسجل", "Créé"), n: () => lines.value.filter((l) => l.status === "created").length },
  { k: "ignored", label: () => L("Ignored", "متجاهَل", "Ignoré"), n: () => lines.value.filter((l) => l.status === "ignored").length },
];
const visible = computed(() => (filter.value === "all" ? lines.value : lines.value.filter((l) => l.status === filter.value)));

async function load() {
  loading.value = true;
  try { d.value = await api.call("accounting_portal.api.bank_workbench.get_import", { company: currentCompany(), name: props.importName }, { fresh: true }) || {}; }
  catch { d.value = {}; }
  finally { loading.value = false; }
}
load();

function applyResult(res) {
  if (!res) return;
  const i = (d.value.lines || []).findIndex((x) => x.i === res.line.i);
  if (i >= 0) d.value.lines[i] = res.line;
  Object.assign(d.value, { n_matched: res.n_matched, n_created: res.n_created, n_ignored: res.n_ignored, status: res.status });
}

async function act(l, action, extra = {}) {
  try {
    const res = await api.call("accounting_portal.api.bank_workbench.line_action",
      { company: currentCompany(), name: d.value.name, idx: l.i, action, ...extra });
    applyResult(res);
    return true;
  } catch (e) { toast.error(String(e?.message || e).slice(0, 180)); return false; }
}

async function ignore(l) {
  const reason = window.prompt(L("Why ignore this line? (bank fee, duplicate…)", "ليه بتتجاهل السطر؟ (رسوم بنكية، مكرر…)", "Raison ?"));
  if (reason === null) return;
  if (await act(l, "ignore", { reason })) toast.success(L("Ignored", "اتجاهل", "Ignoré"));
}
async function reset(l) {
  if (await act(l, "reset")) toast.success(L("Back to pending", "رجع ناقص", "Réinitialisé"));
}

async function openMatch(l) {
  matching.value = l; cands.value = []; candBusy.value = true;
  try { cands.value = await api.call("accounting_portal.api.bank_workbench.match_candidates", { company: currentCompany(), name: d.value.name, idx: l.i }, { fresh: true }) || []; }
  catch (e) { toast.error(String(e?.message || e).slice(0, 160)); }
  finally { candBusy.value = false; }
}
async function doMatch(c) {
  const l = matching.value;
  if (await act(l, "match", { voucher: c.voucher, voucher_type: c.voucher_type })) {
    toast.success(L("Linked & reconciled", "اتربط واتسوّى", "Lié"));
    matching.value = null;
  }
}

function openRegister(l) {
  regLine.value = l;
  // money OUT: an expense/bill paid from this bank; the modal's bill/cash switch
  // covers supplier vs quick cash. Prefill everything from the line.
  regPrefill.value = {
    amount: Math.abs(l.amount),
    description: `${l.description || "Bank line"} · ${l.date}`.slice(0, 140),
    posting_date: l.date,
    pay_account: d.value.account,   // quick-cash mode: credit this bank
    paid_from: d.value.account,     // bill mode: paid from this bank
  };
  registering.value = true;
}
async function onRegistered(res) {
  registering.value = false;
  const l = regLine.value;
  if (!l) return;
  const vno = res?.voucher_no, vt = res?.voucher_type;
  if (res?.status === "Proposed") {
    toast.success(L("Sent for approval — link the line after it posts", "اتبعت للموافقة — اربط السطر بعد الترحيل", "Envoyé"));
    return;
  }
  if (vno && vt) {
    if (await act(l, "created", { voucher: vno, voucher_type: vt }))
      toast.success(L("Created & linked", "اتسجل واتربط", "Créé"));
  }
}
</script>
