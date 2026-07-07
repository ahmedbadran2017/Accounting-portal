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
            <button v-if="canWrite && pendingN" type="button" class="h-8 px-3 rounded-chip text-[11.5px] font-bold text-white bg-brand hover:bg-brand-dark disabled:opacity-50" :disabled="rematching" @click="rematch">{{ rematching ? "…" : L("Re-match", "إعادة مطابقة", "Re-lier") }}</button>
          </div>
        </div>
      </div>

      <!-- filters -->
      <div class="flex flex-wrap items-center gap-1 bg-white border border-line rounded-chip p-1 w-fit">
        <button v-for="fl in FILTERS" :key="fl.k" type="button" class="px-3 py-1.5 rounded-lg text-[12px]"
                :class="filter === fl.k ? 'text-accent-dark font-semibold bg-app-warm shadow-card' : 'text-ink-3 font-medium hover:text-ink'"
                @click="filter = fl.k">{{ fl.label() }} <span class="text-[10px] text-ink-muted">{{ fl.n() }}</span></button>
      </div>

      <!-- bulk selection bar -->
      <div v-if="sel.length" class="flex items-center gap-3 flex-wrap bg-emerald-50 border border-emerald-200 rounded-card px-4 py-2.5">
        <span class="text-[12px] font-bold text-emerald-800">{{ sel.length }} {{ L("selected","مختار","sélectionnés") }} · {{ selDir === 'mixed' ? L('mixed direction','اتجاه مختلط','mixte') : money(selTotal) }}</span>
        <button type="button" class="text-[11px] text-ink-3 hover:underline" @click="sel = []">{{ L("clear","إلغاء","effacer") }}</button>
        <button v-if="selDir !== 'mixed'" type="button" class="ms-auto h-8 px-3.5 rounded-chip text-[12px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand" @click="openBulk">{{ L(`Register ${sel.length} together`, `سجّل ${sel.length} مرة واحدة`, `Créer ${sel.length}`) }}</button>
        <span v-else class="ms-auto text-[10.5px] text-amber-700 font-semibold">{{ L("select all money-in or all money-out","اختار كلهم داخل أو كلهم خارج","une seule direction") }}</span>
      </div>

      <!-- lines, chronological -->
      <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-[12px]">
            <thead><tr style="background:#fafaf9" class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">
              <th v-if="canWrite" class="ps-4 py-2 w-8"><input type="checkbox" :checked="allPendingSel" class="accent-emerald-700" @change="toggleAllPending" /></th>
              <th class="px-4 py-2 text-start">{{ L("Date","التاريخ","Date") }}</th>
              <th class="px-3 py-2 text-start">{{ L("Description","الوصف","Description") }}</th>
              <th class="px-3 py-2 text-end">{{ L("Amount","المبلغ","Montant") }}</th>
              <th class="px-3 py-2 text-start">{{ L("Status","الحالة","Statut") }}</th>
              <th class="px-4 py-2 text-end">{{ L("Action","الإجراء","Action") }}</th>
            </tr></thead>
            <tbody>
              <tr v-for="l in visible" :key="l.i" class="border-t border-line-hair" :class="[l.status==='pending' ? 'hover:bg-amber-50/40' : 'hover:bg-app-warm/30', sel.includes(l.i) ? 'bg-emerald-50/40' : '']">
                <td v-if="canWrite" class="ps-4 py-2 w-8"><input v-if="l.status==='pending'" type="checkbox" :checked="sel.includes(l.i)" class="accent-emerald-700" @change="toggleSel(l)" /></td>
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
              <tr v-if="!visible.length"><td :colspan="canWrite ? 6 : 5" class="px-4 py-10 text-center text-ink-muted">{{ L("Nothing in this filter.","مفيش حاجة في الفلتر ده.","Rien ici.") }}</td></tr>
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
                  <td class="px-3 py-2 font-mono text-[11px]">{{ c.voucher }}<div class="text-[9.5px] text-ink-muted font-sans">{{ c.voucher_type }}<span v-if="c.cleared" class="ms-1 text-emerald-700 font-semibold">· {{ L("already reconciled","مُسوّى قبل كده","déjà rapproché") }}</span></div></td>
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

      <!-- bulk register modal: one combined journal for all selected lines -->
      <div v-if="bulk" class="fixed inset-0 z-[110] flex items-start justify-center p-4 sm:p-10 overflow-y-auto" style="background:rgba(28,25,23,.45)" @click.self="bulk=false">
        <div class="bg-white rounded-[18px] shadow-cardHover w-full max-w-lg my-8 overflow-hidden">
          <div class="flex items-center gap-2.5 px-5 py-4 border-b border-line">
            <span class="w-8 h-8 rounded-[10px] grid place-items-center" style="background:#f5f3ff"><Icon name="ledger" :size="16" color="#7c3aed" /></span>
            <div class="flex-1"><div class="text-[14px] font-bold">{{ L("Register together","تسجيل مجمّع","Enregistrer ensemble") }}</div>
              <div class="text-[11px] text-ink-muted">{{ sel.length }} {{ L("lines","سطر","lignes") }} · {{ selIsIn ? L("money in","وارد","entrée") : L("money out","صادر","sortie") }} · <b :class="selIsIn ? 'text-success-dark' : 'text-sale'">{{ money(selTotal) }}</b></div></div>
            <button class="text-ink-3 hover:text-ink" @click="bulk=false"><Icon name="close" :size="18" /></button>
          </div>
          <div class="p-5 space-y-3">
            <div class="text-[11px] text-ink-3 leading-relaxed rounded-[10px] px-3 py-2" style="background:#faf5ff">
              {{ L("Dr","مدين","Dr") }} <b>{{ selIsIn ? (d.account.split(" - ")[1] || d.account) : L("chosen account","الحساب المختار","compte") }}</b>
              / {{ L("Cr","دائن","Cr") }} <b>{{ selIsIn ? L("chosen account","الحساب المختار","compte") : (d.account.split(" - ")[1] || d.account) }}</b>
              — {{ L("one combined journal, all lines linked and reconciled.","قيد واحد مجمّع، كل السطور بتتربط وتتسوّى.","une seule écriture.") }}
            </div>
            <div class="block">
              <span class="text-[11px] font-semibold text-ink-3">{{ selIsIn ? L("Credit account (where it came from)","الحساب الدائن","Compte crédité") : L("Expense / debit account","حساب المصروف","Compte débité") }}</span>
              <input v-model.trim="bulkQuery" :placeholder="L('search account…','ابحث عن حساب…','rechercher…')" class="mt-1 w-full border border-line-2 rounded-chip px-3 py-2 text-[12px] focus:outline-none focus:border-accent/40" />
              <div class="mt-1 max-h-44 overflow-y-auto border border-line rounded-[12px]">
                <button v-for="a in bulkFiltered" :key="a.name" type="button" class="w-full flex items-center gap-2 px-3 py-2 text-start hover:bg-app-warm/60 text-[12px] border-t border-line-hair first:border-t-0"
                        :class="a.name === bulkAccount ? 'bg-accent-soft font-semibold' : ''" @click="bulkAccount = a.name">
                  <span class="flex-1 truncate">{{ a.num ? a.num + " · " : "" }}{{ a.nm }}</span>
                  <span class="text-[9.5px] text-ink-muted">{{ a.typ || a.rt }}</span>
                  <Icon v-if="a.name === bulkAccount" name="check" :size="13" color="#047857" />
                </button>
                <div v-if="!bulkFiltered.length" class="px-3 py-4 text-center text-[11px] text-ink-muted">{{ L("No account matches.","لا حساب مطابق.","Aucun.") }}</div>
              </div>
            </div>
            <div v-if="selTotal >= 10000" class="text-[11px] text-amber-700 inline-flex items-center gap-1.5"><Icon name="shield" :size="12" />{{ L("Material — goes for approval first.","مبلغ جوهري — للموافقة الأول.","Approbation requise.") }}</div>
          </div>
          <div class="flex items-center justify-end gap-2 px-5 py-3.5 border-t border-line bg-app-warm/40">
            <button class="px-3.5 py-2 rounded-chip text-[12px] font-semibold text-ink-2 hover:bg-white" @click="bulk=false">{{ L("Cancel","إلغاء","Annuler") }}</button>
            <button class="px-4 py-2 rounded-chip text-[12px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand disabled:opacity-50" :disabled="!bulkAccount || bulkBusy" @click="postBulk">{{ bulkBusy ? "…" : L("Register","سجّل","Enregistrer") }}</button>
          </div>
        </div>
      </div>

      <!-- money-IN modal: Dr this bank / Cr the picked account (carrier clearing, another account, income…) -->
      <div v-if="moneyIn" class="fixed inset-0 z-[110] flex items-start justify-center p-4 sm:p-10 overflow-y-auto" style="background:rgba(28,25,23,.45)" @click.self="moneyIn=null">
        <div class="bg-white rounded-[18px] shadow-cardHover w-full max-w-lg my-8 overflow-hidden">
          <div class="flex items-center gap-2.5 px-5 py-4 border-b border-line">
            <span class="w-8 h-8 rounded-[10px] grid place-items-center" style="background:#ecfdf5"><Icon name="cash" :size="16" color="#047857" /></span>
            <div class="flex-1"><div class="text-[14px] font-bold">{{ L("Record money in","تسجيل وارد","Encaissement") }}</div>
              <div class="text-[11px] text-ink-muted tnum">{{ moneyIn.date }} · {{ (moneyIn.description || "").slice(0,60) }} · <b class="text-success-dark">+{{ money(moneyIn.amount) }}</b></div></div>
            <button class="text-ink-3 hover:text-ink" @click="moneyIn=null"><Icon name="close" :size="18" /></button>
          </div>
          <div class="p-5 space-y-3">
            <div class="text-[11px] text-ink-3 leading-relaxed rounded-[10px] px-3 py-2" style="background:#f0fdf4">
              {{ L("Books: Dr", "القيد: مدين", "Dr") }} <b>{{ d.account.split(" - ")[1] || d.account }}</b> / {{ L("Cr the account below — carrier COD remittance → the carrier clearing account; transfer from our own account → that account; other income → an income account.", "دائن الحساب اللي تحت — تحصيل COD من الناقل ← حساب تصفية الناقل؛ تحويل من حساب بتاعنا ← الحساب ده؛ إيراد آخر ← حساب إيراد.", "Cr le compte choisi.") }}
            </div>
            <div class="block">
              <span class="text-[11px] font-semibold text-ink-3">{{ L("Credit account (where it came from)","الحساب الدائن (جاي منين)","Compte crédité") }}</span>
              <input v-model.trim="inQuery" :placeholder="L('search account…','ابحث عن حساب…','rechercher…')" class="mt-1 w-full border border-line-2 rounded-chip px-3 py-2 text-[12px] focus:outline-none focus:border-accent/40" />
              <div class="mt-1 max-h-44 overflow-y-auto border border-line rounded-[12px]">
                <button v-for="a in inFiltered" :key="a.name" type="button" class="w-full flex items-center gap-2 px-3 py-2 text-start hover:bg-app-warm/60 text-[12px] border-t border-line-hair first:border-t-0"
                        :class="a.name === inAccount ? 'bg-accent-soft font-semibold' : ''" @click="inAccount = a.name">
                  <span class="flex-1 truncate">{{ a.num ? a.num + " · " : "" }}{{ a.nm }}</span>
                  <span class="text-[9.5px] text-ink-muted">{{ a.typ || a.rt }}</span>
                  <Icon v-if="a.name === inAccount" name="check" :size="13" color="#047857" />
                </button>
                <div v-if="!inFiltered.length" class="px-3 py-4 text-center text-[11px] text-ink-muted">{{ L("No account matches.","لا حساب مطابق.","Aucun.") }}</div>
              </div>
            </div>
            <div v-if="Math.abs(moneyIn.amount) >= 10000" class="text-[11px] text-amber-700 inline-flex items-center gap-1.5"><Icon name="shield" :size="12" />{{ L("Material amount — goes for approval first.","مبلغ جوهري — هيروح للموافقة الأول.","Approbation requise.") }}</div>
          </div>
          <div class="flex items-center justify-end gap-2 px-5 py-3.5 border-t border-line bg-app-warm/40">
            <button class="px-3.5 py-2 rounded-chip text-[12px] font-semibold text-ink-2 hover:bg-white" @click="moneyIn=null">{{ L("Cancel","إلغاء","Annuler") }}</button>
            <button class="px-4 py-2 rounded-chip text-[12px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand disabled:opacity-50" :disabled="!inAccount || inBusy" @click="postIn">{{ inBusy ? "…" : L("Record","سجّل","Enregistrer") }}</button>
          </div>
        </div>
      </div>

      <NewExpenseModal v-if="registering" :prefill="regPrefill" @close="registering=false" @posted="onRegistered" />
    </template>
    <div v-else class="p-10 text-center text-ink-muted text-[12px]">{{ L("Import not found.","الاستيراد مش موجود.","Introuvable.") }}</div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
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

// ---- bulk selection (register a batch of same-direction lines at once) ----
const sel = ref([]);
const visiblePending = computed(() => visible.value.filter((l) => l.status === "pending"));
const allPendingSel = computed(() => visiblePending.value.length > 0 && visiblePending.value.every((l) => sel.value.includes(l.i)));
const selRows = computed(() => lines.value.filter((l) => sel.value.includes(l.i)));
const selDir = computed(() => {
  const dirs = new Set(selRows.value.map((l) => (l.amount >= 0 ? "in" : "out")));
  return dirs.size > 1 ? "mixed" : [...dirs][0] || "";
});
const selIsIn = computed(() => selDir.value === "in");
const selTotal = computed(() => selRows.value.reduce((s, l) => s + Math.abs(Number(l.amount) || 0), 0));
function toggleSel(l) {
  const i = sel.value.indexOf(l.i);
  i >= 0 ? sel.value.splice(i, 1) : sel.value.push(l.i);
}
function toggleAllPending() {
  sel.value = allPendingSel.value ? [] : visiblePending.value.map((l) => l.i);
}
// keep selection sane when the filter changes
watch(filter, () => { sel.value = []; });

const bulk = ref(false), bulkQuery = ref(""), bulkAccount = ref(""), bulkBusy = ref(false);
const bulkFiltered = computed(() => {
  const q = bulkQuery.value.trim().toLowerCase();
  const list = inOptions.value;
  if (!q) return list.slice(0, 60);
  return list.filter((a) => (a.nm || "").toLowerCase().includes(q) || (a.num || "").toLowerCase().includes(q)).slice(0, 60);
});
async function openBulk() {
  if (selDir.value === "mixed" || !sel.value.length) return;
  bulkAccount.value = ""; bulkQuery.value = "";
  if (!inOptions.value.length) {
    try { inOptions.value = await api.call("accounting_portal.api.bank_workbench.in_account_options", { company: currentCompany() }) || []; }
    catch { inOptions.value = []; }
  }
  bulk.value = true;
}
async function postBulk() {
  if (!bulkAccount.value || bulkBusy.value) return;
  bulkBusy.value = true;
  try {
    const res = await api.call("accounting_portal.api.bank_workbench.bulk_register",
      { company: currentCompany(), name: d.value.name, idxs: sel.value, account: bulkAccount.value });
    if (res?.proposed) {
      toast.success(L("Sent for approval — link the lines after it posts", "اتبعت للموافقة — اربط السطور بعد الترحيل", "Envoyé"));
    } else {
      toast.success(L(`${res.n} registered as ${res.voucher}`, `اتسجل ${res.n} في ${res.voucher}`, `${res.n} enregistrés`));
    }
    bulk.value = false; sel.value = [];
    await load();
  } catch (e) { toast.error(String(e?.message || e).slice(0, 180)); }
  finally { bulkBusy.value = false; }
}

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

const rematching = ref(false);
async function rematch() {
  if (rematching.value) return;
  rematching.value = true;
  try {
    const res = await api.call("accounting_portal.api.bank_workbench.rematch_import",
      { company: currentCompany(), name: d.value.name });
    toast.success(L(`${res.newly_matched} newly matched`, `اتطابق ${res.newly_matched} جديد`, `${res.newly_matched} liés`));
    await load();
  } catch (e) { toast.error(String(e?.message || e).slice(0, 180)); }
  finally { rematching.value = false; }
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

const moneyIn = ref(null), inAccount = ref(""), inQuery = ref(""), inBusy = ref(false);
const inOptions = ref([]);
const inFiltered = computed(() => {
  const q = inQuery.value.trim().toLowerCase();
  const list = inOptions.value;
  if (!q) return list.slice(0, 60);
  return list.filter((a) => (a.nm || "").toLowerCase().includes(q) || (a.num || "").toLowerCase().includes(q)).slice(0, 60);
});
async function openMoneyIn(l) {
  regLine.value = l;
  moneyIn.value = l;
  inAccount.value = ""; inQuery.value = "";
  if (!inOptions.value.length) {
    try { inOptions.value = await api.call("accounting_portal.api.bank_workbench.in_account_options", { company: currentCompany() }) || []; }
    catch { inOptions.value = []; }
  }
  // carrier remittance? default straight to the carrier clearing account
  const desc = (l.description || "").toLowerCase();
  if (/cathedis|cathadis|aramex|cash ?plus|rdf/.test(desc)) {
    const hit = inOptions.value.find((a) => /cathadis|cathedis/.test((a.nm || "").toLowerCase()))
      || inOptions.value.find((a) => /aramex/.test((a.nm || "").toLowerCase()) && /aramex/.test(desc));
    if (hit) { inAccount.value = hit.name; inQuery.value = hit.nm; }
  }
}
async function postIn() {
  const l = moneyIn.value;
  if (!inAccount.value || inBusy.value || !l) return;
  inBusy.value = true;
  try {
    const amt = Math.abs(l.amount);
    const res = await api.call("accounting_portal.api.accountant.create_journal_entry", {
      company: currentCompany(), posting_date: l.date,
      lines: [{ account: d.value.account, debit: amt, credit: 0 },
              { account: inAccount.value, debit: 0, credit: amt }],
      remark: `Bank in · ${(l.description || "").slice(0, 120)} · ${l.date}`,
      dedupe_key: "bsiin:" + d.value.name + ":" + l.i,
    });
    if (res?.status === "Proposed") {
      toast.success(L("Sent for approval — link the line after it posts", "اتبعت للموافقة — اربط السطر بعد الترحيل", "Envoyé"));
      moneyIn.value = null;
      return;
    }
    if (res?.voucher_no && await act(l, "created", { voucher: res.voucher_no, voucher_type: "Journal Entry" })) {
      toast.success(L("Recorded & linked", "اتسجل واتربط", "Enregistré"));
      moneyIn.value = null;
    }
  } catch (e) { toast.error(String(e?.message || e).slice(0, 180)); }
  finally { inBusy.value = false; }
}

function openRegister(l) {
  if (l.amount > 0) return openMoneyIn(l);
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
