<template>
  <div class="fixed inset-0 z-[100] flex items-center justify-center p-4" style="background:rgba(28,25,23,.45)" @click.self="$emit('close')">
    <div class="bg-white rounded-[16px] shadow-cardHover w-full max-w-lg max-h-[88vh] flex flex-col overflow-hidden">
      <header class="flex items-center gap-2.5 px-5 py-3.5 border-b border-line-hair">
        <span class="w-8 h-8 rounded-[10px] grid place-items-center" style="background:#eef2ff"><Icon name="scale" :size="16" color="#4338ca" /></span>
        <div class="min-w-0">
          <div class="text-[14px] font-bold">{{ L("Monthly settlement","تسوية شهرية","Règlement mensuel") }}</div>
          <div class="text-[11px] text-ink-muted">{{ L("Sweep sibling account balances into one, dated month-end.","دمج أرصدة الحسابات الشقيقة في حساب واحد بتاريخ نهاية الشهر.","Regrouper les comptes frères.") }}</div>
        </div>
        <button @click="$emit('close')" class="ms-auto w-7 h-7 grid place-items-center rounded-[8px] hover:bg-app-warm text-ink-muted"><Icon name="close" :size="14" /></button>
      </header>

      <div class="p-5 overflow-auto space-y-3.5 flex-1 min-h-0">
        <!-- survivor + date -->
        <div class="grid sm:grid-cols-2 gap-3">
          <div>
            <label class="text-[11px] font-bold text-ink-3">{{ L("Keep balance in (survivor)","الحساب الناجي","Compte survivant") }}</label>
            <div class="mt-1"><SearchSelect v-model="survivor" :items="survivorItems" :placeholder="L('Search account…','ابحث عن حساب…','Rechercher…')" :empty-text="L('No account','لا حساب','Aucun compte')" /></div>
          </div>
          <div>
            <label class="text-[11px] font-bold text-ink-3">{{ L("Settlement date","تاريخ التسوية","Date") }}</label>
            <input type="date" v-model="asOf" class="w-full h-9 mt-1 border border-line-2 rounded-[9px] px-2 text-[12.5px] focus:outline-none focus:border-accent/40" />
          </div>
        </div>

        <div v-if="loading" class="py-8 text-center text-[12px] text-ink-muted">{{ L("Loading balances…","جارٍ تحميل الأرصدة…","Chargement…") }}</div>

        <template v-else-if="data && survivor">
          <div v-if="!data.settleable" class="text-[11.5px] text-amber-700 bg-amber-50 border border-amber-200 rounded-[10px] px-3 py-2 flex items-start gap-1.5">
            <Icon name="alert" :size="13" color="#b45309" class="mt-px flex-shrink-0" />
            {{ L("The survivor isn't in the base currency — settlement supports base-currency accounts only.","الحساب الناجي مش بالعملة الأساسية — التسوية تدعم حسابات العملة الأساسية فقط.","Compte non en devise de base.") }}
          </div>

          <template v-else>
            <div class="text-[11px] font-bold uppercase tracking-wide text-ink-muted">{{ L("Sibling accounts to sweep","الحسابات الشقيقة","Comptes à regrouper") }}</div>
            <div v-if="!data.siblings.length" class="text-[12px] text-ink-muted py-3 text-center">{{ L("No sibling accounts under the same group.","لا حسابات شقيقة تحت نفس المجموعة.","Aucun compte frère.") }}</div>
            <div v-else class="rounded-[10px] border border-line-hair overflow-hidden">
              <table class="w-full text-[12px]">
                <tr v-for="s in data.siblings" :key="s.name" class="border-b border-line-hair last:border-0" :class="s.balance ? '' : 'opacity-50'">
                  <td class="ps-3 py-2 w-8"><input type="checkbox" :value="s.name" v-model="selected" :disabled="!s.balance || !s.same_ccy" class="accent-indigo-600 w-4 h-4 align-middle" /></td>
                  <td class="px-2 py-2">
                    <div class="font-semibold truncate max-w-[240px]">{{ s.account_name }}</div>
                    <div class="text-[10px] text-ink-muted font-mono">{{ s.name.split(' - ')[0] }}<span v-if="!s.same_ccy" class="text-amber-700"> · {{ s.ccy }}</span></div>
                  </td>
                  <td class="px-3 py-2 text-end tnum font-semibold" :class="s.balance < 0 ? 'text-sale' : ''">{{ fmt2(s.balance) }}</td>
                </tr>
              </table>
            </div>

            <!-- preview -->
            <div v-if="selected.length" class="rounded-[10px] bg-indigo-50/60 border border-indigo-100 px-3 py-2.5 text-[12px] space-y-1">
              <div class="flex justify-between"><span class="text-ink-3">{{ L("Survivor now","الناجي الآن","Actuel") }}</span><span class="tnum font-semibold" :class="data.survivor.balance<0?'text-sale':''">{{ fmt2(data.survivor.balance) }}</span></div>
              <div class="flex justify-between"><span class="text-ink-3">{{ L("Sweeping in","المُحوّل","Transféré") }}</span><span class="tnum font-semibold text-indigo-700">{{ fmt2(sweptTotal) }}</span></div>
              <div class="flex justify-between border-t border-indigo-200 pt-1 mt-1"><span class="font-bold">{{ L("Survivor after","الناجي بعد","Après") }}</span><span class="tnum font-extrabold" :class="survivorAfter<0?'text-sale':''">{{ fmt2(survivorAfter) }} {{ data.base_ccy }}</span></div>
              <div class="text-[11px] text-ink-muted pt-0.5">{{ selected.length }} {{ L("account(s) → 0","حساب → صفر","comptes → 0") }}</div>
            </div>
          </template>
        </template>

        <input v-model.trim="remark" :placeholder="L('Note (optional)','ملاحظة (اختياري)','Note (facultatif)')" class="w-full h-9 border border-line-2 rounded-[9px] px-2 text-[12.5px] focus:outline-none focus:border-accent/40" />
        <div v-if="error" class="text-[11.5px] text-sale">{{ error }}</div>
      </div>

      <footer class="flex items-center gap-2 px-5 py-3.5 border-t border-line-hair bg-app-warm/30">
        <button @click="$emit('close')" class="h-9 px-3.5 rounded-chip text-[12px] font-semibold text-ink-2 hover:bg-app-warm">{{ L("Cancel","إلغاء","Annuler") }}</button>
        <button @click="post" :disabled="busy || !canPost" class="ms-auto h-9 px-4 rounded-chip text-[12px] font-bold text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50">
          {{ busy ? L("Posting…","جارٍ…","…") : L("Post settlement","ترحيل التسوية","Passer") }}
        </button>
      </footer>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import SearchSelect from "@/components/SearchSelect.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useToast } from "@/composables/useToast";

const props = defineProps({ accounts: { type: Array, default: () => [] } });
const emit = defineEmits(["close", "posted"]);
const { locale } = useI18n();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt2 = (n) => Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function lastPrevMonthEnd() {
  const now = new Date();
  const d = new Date(now.getFullYear(), now.getMonth(), 0); // day 0 → last day of previous month
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

const survivor = ref("");
const survivorItems = computed(() => (props.accounts || []).map((a) => ({ value: a.name, label: a.account_name || a.name, sub: a.name.split(" - ")[0] + (a.ccy ? " · " + a.ccy : "") })));
const asOf = ref(lastPrevMonthEnd());
const data = ref(null);
const selected = ref([]);
const remark = ref("");
const loading = ref(false);
const busy = ref(false);
const error = ref("");

const sweptTotal = computed(() => (data.value?.siblings || []).filter((s) => selected.value.includes(s.name)).reduce((t, s) => t + Number(s.balance || 0), 0));
const survivorAfter = computed(() => Number(data.value?.survivor?.balance || 0) + sweptTotal.value);
const canPost = computed(() => !!(survivor.value && data.value?.settleable && selected.value.length));

let seq = 0;
async function loadSiblings() {
  if (!survivor.value) { data.value = null; selected.value = []; return; }
  loading.value = true; error.value = "";
  const my = ++seq;
  try {
    const r = await api.call("accounting_portal.api.settlement.settlement_siblings", { company: currentCompany(), survivor: survivor.value, as_of: asOf.value });
    if (my !== seq) return;
    data.value = r;
    // default-tick siblings that have a non-zero balance in the base currency
    selected.value = (r.siblings || []).filter((s) => s.balance && s.same_ccy).map((s) => s.name);
  } catch (e) { if (my === seq) { error.value = String(e?.message || e).slice(0, 160); data.value = null; } }
  finally { if (my === seq) loading.value = false; }
}
watch([survivor, asOf], loadSiblings);
onMounted(() => { if (props.accounts.length === 1) survivor.value = props.accounts[0].name; });

async function post() {
  if (!canPost.value || busy.value) return;
  busy.value = true; error.value = "";
  try {
    const r = await api.call("accounting_portal.api.settlement.post_monthly_settlement", {
      company: currentCompany(), survivor: survivor.value, sources: selected.value, as_of: asOf.value, remark: remark.value || undefined,
    });
    if (r && r.status === "Posted") toast.success(L(`Settled — ${r.voucher_no || ""}`, `تمت التسوية — ${r.voucher_no || ""}`, `Réglé — ${r.voucher_no || ""}`));
    else toast.info(L("Recorded — awaiting an approver", "سُجّل — بانتظار موافِق", "Enregistré — en attente"));
    emit("posted"); emit("close");
  } catch (e) { error.value = String(e?.message || e).slice(0, 200); }
  finally { busy.value = false; }
}
</script>
