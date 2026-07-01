<template>
  <div class="space-y-3.5">
    <!-- summary -->
    <div class="grid grid-cols-3 gap-3">
      <div class="bg-white rounded-card border shadow-card px-4 py-3" :class="d.overdue ? 'border-rose-200' : 'border-line'">
        <div class="text-[10px] font-bold uppercase tracking-wider flex items-center gap-1.5" :class="d.overdue ? 'text-rose-600' : 'text-ink-muted'"><Icon name="alert" :size="13" :color="d.overdue ? '#e11d48' : '#94a3b8'" />{{ L("Overdue","متأخّرة","En retard") }}</div>
        <div class="text-[20px] font-extrabold mt-1 tnum" :class="d.overdue ? 'text-rose-600' : ''">{{ loading ? "—" : (d.overdue || 0) }}</div>
        <div class="text-[10.5px] text-ink-muted mt-0.5">{{ L("past due, not booked","فات موعدها ولم تُسجّل","non enregistrées") }}</div>
      </div>
      <div class="bg-white rounded-card border shadow-card px-4 py-3" :class="d.due ? 'border-amber-200' : 'border-line'">
        <div class="text-[10px] font-bold uppercase tracking-wider flex items-center gap-1.5" :class="d.due ? 'text-amber-700' : 'text-ink-muted'"><Icon name="clock" :size="13" :color="d.due ? '#b45309' : '#94a3b8'" />{{ L("Due soon","مستحقة قريباً","Bientôt") }}</div>
        <div class="text-[20px] font-extrabold mt-1 tnum" :class="d.due ? 'text-amber-700' : ''">{{ loading ? "—" : (d.due || 0) }}</div>
        <div class="text-[10.5px] text-ink-muted mt-0.5">{{ L("within 7 days","خلال 7 أيام","sous 7 jours") }}</div>
      </div>
      <div class="bg-white rounded-card border border-line shadow-card px-4 py-3">
        <div class="text-[10px] font-bold uppercase tracking-wider text-ink-muted flex items-center gap-1.5"><Icon name="wallet" :size="13" color="#7c3aed" />{{ L("Monthly total","إجمالي شهري","Total mensuel") }}</div>
        <div class="text-[20px] font-extrabold mt-1 tnum" style="color:#7c3aed">{{ loading ? "—" : money(d.monthly_total) }}</div>
        <div class="text-[10.5px] text-ink-muted mt-0.5">{{ ccy }} · {{ L("recurring monthly","متكرر شهري","récurrent") }}</div>
      </div>
    </div>

    <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
      <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2">
        <Icon name="clock" :size="14" color="#0b5c4f" /><span class="text-[12px] font-bold">{{ L("Recurring expenses","المصروفات المتكرّرة","Charges récurrentes") }}</span>
        <span class="text-[10px] text-ink-muted">{{ L("detected from history · overdue first","مكتشفة من السجل · المتأخّر أولاً","détecté de l'historique") }}</span>
      </div>
      <TableLoading v-if="loading" :rows="8" />
      <div v-else-if="err" class="px-4 py-10 text-center"><Icon name="alert" :size="18" color="#e11d48" /><p class="text-[12px] text-ink-2 mt-1">{{ L("Couldn't load.","تعذّر التحميل.","Échec.") }}</p><button class="mt-2 h-8 px-3 rounded-chip border border-line-2 text-[12px] font-semibold" @click="load">{{ L("Retry","إعادة","Réessayer") }}</button></div>
      <div v-else-if="!(d.recurring||[]).length" class="px-4 py-10 text-center text-[12px] text-ink-muted">{{ L("No recurring expenses detected.","لم تُكتشف مصروفات متكرّرة.","Aucune.") }}</div>
      <div v-else class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead><tr style="background:#fafaf9" class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">
            <th class="px-4 py-2 text-start">{{ L("Expense","المصروف","Charge") }}</th>
            <th class="px-3 py-2 text-start hidden sm:table-cell">{{ L("Cadence","التكرار","Cadence") }}</th>
            <th class="px-3 py-2 text-end">{{ L("Avg / time","المتوسط","Moyenne") }}</th>
            <th class="px-3 py-2 text-start">{{ L("Next due","الاستحقاق التالي","Prochaine") }}</th>
            <th class="px-4 py-2 text-end"></th>
          </tr></thead>
          <tbody>
            <tr v-for="(r,i) in d.recurring" :key="i" class="border-t border-line-hair" :class="r.status==='overdue' ? 'bg-rose-50/40' : r.status==='due' ? 'bg-amber-50/40' : ''">
              <td class="px-4 py-2.5">
                <div class="flex items-center gap-2 min-w-0">
                  <span class="w-2 h-2 rounded-sm shrink-0" :style="`background:${r.color}`"></span>
                  <div class="min-w-0">
                    <div class="font-semibold truncate max-w-[220px]">{{ r.supplier }}</div>
                    <div class="text-[10.5px] text-ink-muted truncate max-w-[220px]">{{ r.account_name }}</div>
                  </div>
                </div>
              </td>
              <td class="px-3 py-2.5 text-ink-2 hidden sm:table-cell">{{ cadence(r.cadence) }} <span class="text-ink-muted">· {{ r.months }} {{ L("mo","شهر","mois") }}</span></td>
              <td class="px-3 py-2.5 text-end tnum font-semibold">{{ money(r.avg_amt) }}</td>
              <td class="px-3 py-2.5">
                <span class="text-[10px] font-bold px-1.5 py-0.5 rounded" :class="badge(r.status)">{{ r.next }}</span>
                <div class="text-[10px] text-ink-muted mt-0.5">{{ dueLabel(r) }}</div>
              </td>
              <td class="px-4 py-2.5 text-end whitespace-nowrap">
                <div v-if="canWrite && r.status!=='ok'" class="inline-flex items-center gap-1.5">
                  <button type="button" class="inline-flex items-center gap-1 h-7 px-2.5 rounded-chip text-[11px] font-bold text-white bg-brand hover:bg-brand-dark" @click="record(r)">
                    <Icon name="wallet" :size="12" />{{ L("Record","تسجيل","Enregistrer") }}
                  </button>
                  <button type="button" :disabled="busy===key(r)" class="inline-flex items-center gap-1 h-7 px-2.5 rounded-chip text-[11px] font-semibold text-ink-2 bg-white border border-line-2 hover:bg-app-warm disabled:opacity-60" @click="makeDraft(r)">
                    <Icon :name="busy===key(r) ? 'clock' : 'doc'" :size="12" />{{ L("Draft bill","درافت فاتورة","Brouillon") }}
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="px-4 py-2 border-t border-line-hair text-[10px] text-ink-muted flex items-center gap-1.5">
        <Icon name="alert" :size="11" color="#9a8f86" />{{ L("“Record” opens the expense form prefilled (posts a journal). “Draft bill” copies the last bill forward as an unpaid draft to review.","«تسجيل» بيفتح نموذج المصروف معبّأ (بيرحّل قيد). «درافت فاتورة» بينسخ آخر فاتورة كمسودّة غير مدفوعة للمراجعة.","« Enregistrer » ouvre le formulaire pré-rempli ; « Brouillon » copie la dernière facture.") }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { fmtAmount } from "@/utils/helpers";
import { ref, computed, watch } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";
import { useAuth } from "@/composables/useAuth";
import { useToast } from "@/composables/useToast";

const emit = defineEmits(["counts", "record"]);
const { locale } = useI18n();
const { entityId } = useUi();
const { can } = useAuth();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const money = (n) => fmtAmount(n);

const d = ref({});
const loading = ref(true);
const err = ref(false);
const busy = ref("");
const canWrite = computed(() => can("post_entries"));
const ccy = computed(() => d.value.currency || "MAD");
const key = (r) => r.supplier + "|" + r.account;

async function load() {
  loading.value = true; err.value = false;
  try { d.value = await api.call("accounting_portal.api.recurring.recurring_overview", { company: currentCompany() }) || {}; emit("counts", { due: d.value.due || 0, overdue: d.value.overdue || 0 }); }
  catch { d.value = {}; err.value = true; }
  finally { loading.value = false; }
}
load();
watch(entityId, load);

const cadence = (c) => (c === "Monthly" ? L("Monthly", "شهري", "Mensuel") : c === "Quarterly" ? L("Quarterly", "ربع سنوي", "Trim.") : L("Yearly", "سنوي", "Annuel"));
const badge = (s) => (s === "overdue" ? "bg-rose-100 text-rose-700" : s === "due" ? "bg-amber-100 text-amber-700" : "bg-app-warm text-ink-2");
function dueLabel(r) {
  const dd = r.days_until;
  if (dd < 0) return L(`${-dd}d overdue`, `متأخّر ${-dd} يوم`, `retard ${-dd}j`);
  if (dd === 0) return L("today", "اليوم", "auj.");
  return L(`in ${dd}d`, `خلال ${dd} يوم`, `dans ${dd}j`);
}
function record(r) {
  // Hand a prefilled expense up to the Expense Center's New-expense modal.
  emit("record", {
    expense_account: r.account, amount: r.avg_amt, party: r.supplier,
    description: L(`Recurring · ${r.account_name || r.supplier}`, `متكرّر · ${r.account_name || r.supplier}`, `Récurrent · ${r.account_name || r.supplier}`),
  });
}
async function makeDraft(r) {
  if (busy.value) return;
  if (!window.confirm(L(
    `Create a draft bill for ${r.supplier} (copy of the last one)? You review & submit it later.`,
    `إنشاء مسودّة فاتورة لـ ${r.supplier} (نسخة من الأخيرة)؟ تراجعها وتعتمدها لاحقاً.`,
    `Créer un brouillon pour ${r.supplier} ?`))) return;
  busy.value = key(r);
  try {
    const res = await api.call("accounting_portal.api.recurring.create_recurring_draft", { company: currentCompany(), supplier: r.supplier, expense_account: r.account, dry_run: 0 });
    const vn = res?.result?.voucher_no;
    toast.success(L(`Draft ${vn || ""} created`, `مسودّة ${vn || ""} أُنشئت`, `Brouillon ${vn || ""} créé`));
  } catch (e) {
    toast.error(L("Failed", "فشل", "Échec") + ": " + String(e?.message || e).slice(0, 120));
  } finally { busy.value = ""; }
}
</script>
