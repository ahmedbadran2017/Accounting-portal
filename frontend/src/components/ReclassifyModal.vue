<template>
  <div class="fixed inset-0 z-[100] overflow-y-auto flex items-start justify-center p-4" style="background:rgba(28,25,23,.45)" @click.self="$emit('close')">
    <div class="bg-white rounded-[16px] shadow-cardHover w-full max-w-lg my-4">
      <header class="flex items-center gap-2.5 px-5 py-3.5 border-b border-line-hair">
        <span class="w-8 h-8 rounded-[10px] grid place-items-center" style="background:#eef2ff"><Icon name="refresh" :size="16" color="#4338ca" /></span>
        <div class="min-w-0">
          <div class="text-[14px] font-bold">{{ L("Reclassify balance","إعادة تصنيف رصيد","Reclasser un solde") }}</div>
          <div class="text-[11px] text-ink-muted">{{ L("Move an account's whole balance into another — one dated journal, source docs untouched.","نقل رصيد حساب بالكامل لحساب آخر — قيد واحد، من غير المساس بالمستندات.","Déplacer un solde vers un autre compte.") }}</div>
        </div>
        <button @click="$emit('close')" class="ms-auto w-7 h-7 grid place-items-center rounded-[8px] hover:bg-app-warm text-ink-muted"><Icon name="close" :size="14" /></button>
      </header>

      <div class="p-5 space-y-3.5">
        <div>
          <label class="text-[11px] font-bold text-ink-3">{{ L("From (empties to zero)","من (يتصفّر)","Depuis") }}</label>
          <div class="mt-1"><SearchSelect v-model="fromAccount" :items="accountItems" :placeholder="L('Search account…','ابحث عن حساب…','Rechercher…')" :empty-text="L('No account','لا حساب','Aucun')" /></div>
        </div>
        <div>
          <label class="text-[11px] font-bold text-ink-3">{{ L("To (receives the balance)","إلى (يستقبل الرصيد)","Vers") }}</label>
          <div class="mt-1"><SearchSelect v-model="toAccount" :items="accountItems" :placeholder="L('Search account…','ابحث عن حساب…','Rechercher…')" :empty-text="L('No account','لا حساب','Aucun')" /></div>
        </div>
        <div>
          <label class="text-[11px] font-bold text-ink-3">{{ L("Date","التاريخ","Date") }}</label>
          <input type="date" v-model="asOf" class="w-full h-9 mt-1 border border-line-2 rounded-[9px] px-2 text-[12.5px] focus:outline-none focus:border-accent/40" />
        </div>

        <div v-if="loading" class="py-4 text-center text-[12px] text-ink-muted">{{ L("Loading balances…","جارٍ التحميل…","Chargement…") }}</div>

        <template v-else-if="pv && fromAccount && toAccount">
          <div v-if="pv.problems && pv.problems.length" class="text-[11.5px] text-amber-700 bg-amber-50 border border-amber-200 rounded-[10px] px-3 py-2 space-y-0.5">
            <div v-for="(p,i) in pv.problems" :key="i" class="flex items-start gap-1.5"><Icon name="alert" :size="12" color="#b45309" class="mt-px flex-shrink-0" />{{ p }}</div>
          </div>
          <div v-else class="rounded-[10px] bg-indigo-50/60 border border-indigo-100 px-3 py-2.5 text-[12px] space-y-1">
            <div class="flex justify-between"><span class="text-ink-3">{{ pv.from.label }} <span class="text-ink-muted">({{ L("now","الآن","actuel") }})</span></span><span class="tnum font-semibold" :class="pv.from.balance<0?'text-sale':''">{{ fmt2(pv.from.balance) }} {{ pv.ccy }}</span></div>
            <div class="flex justify-between"><span class="text-ink-3">{{ L("Moves to","ينتقل إلى","Vers") }} {{ pv.to.label }}</span><span class="tnum font-semibold text-indigo-700">{{ fmt2(pv.move) }}</span></div>
            <div class="flex justify-between border-t border-indigo-200 pt-1 mt-1"><span class="font-bold">{{ pv.from.label }} → 0 · {{ pv.to.label }} {{ L("after","بعد","après") }}</span><span class="tnum font-extrabold" :class="pv.to.after<0?'text-sale':''">{{ fmt2(pv.to.after) }}</span></div>
          </div>
        </template>

        <input v-model.trim="remark" :placeholder="L('Note (optional)','ملاحظة (اختياري)','Note (facultatif)')" class="w-full h-9 border border-line-2 rounded-[9px] px-2 text-[12.5px] focus:outline-none focus:border-accent/40" />
        <div v-if="error" class="text-[11.5px] text-sale">{{ error }}</div>
      </div>

      <footer class="flex items-center gap-2 px-5 py-3.5 border-t border-line-hair bg-app-warm/30 rounded-b-[16px]">
        <button @click="$emit('close')" class="h-9 px-3.5 rounded-chip text-[12px] font-semibold text-ink-2 hover:bg-app-warm">{{ L("Cancel","إلغاء","Annuler") }}</button>
        <button @click="post" :disabled="busy || !(pv && pv.ok)" class="ms-auto h-9 px-4 rounded-chip text-[12px] font-bold text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50">
          {{ busy ? L("Posting…","جارٍ…","…") : L("Post reclass","ترحيل إعادة التصنيف","Passer") }}
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

const emit = defineEmits(["close", "posted"]);
const { locale } = useI18n();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt2 = (n) => Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const accounts = ref([]);
const accountItems = computed(() => accounts.value.map((a) => ({ value: a.name, label: a.account_name || a.name, sub: (a.name.includes(" - ") ? a.name.split(" - ")[0] : "") + (a.currency ? " · " + a.currency : "") })));
const fromAccount = ref("");
const toAccount = ref("");
const asOf = ref(new Date().toISOString().slice(0, 10));
const pv = ref(null);
const remark = ref("");
const loading = ref(false);
const busy = ref(false);
const error = ref("");

onMounted(async () => {
  try { accounts.value = await api.call("accounting_portal.api.accountant.account_options", { company: currentCompany() }) || []; } catch { accounts.value = []; }
});

let seq = 0;
async function loadPreview() {
  if (!fromAccount.value || !toAccount.value) { pv.value = null; return; }
  loading.value = true; error.value = "";
  const my = ++seq;
  try {
    const r = await api.call("accounting_portal.api.reclass.reclass_preview", { company: currentCompany(), from_account: fromAccount.value, to_account: toAccount.value, as_of: asOf.value });
    if (my === seq) pv.value = r;
  } catch (e) { if (my === seq) { error.value = String(e?.message || e).slice(0, 160); pv.value = null; } }
  finally { if (my === seq) loading.value = false; }
}
watch([fromAccount, toAccount, asOf], loadPreview);

async function post() {
  if (busy.value || !(pv.value && pv.value.ok)) return;
  busy.value = true; error.value = "";
  try {
    const r = await api.call("accounting_portal.api.reclass.post_reclass", { company: currentCompany(), from_account: fromAccount.value, to_account: toAccount.value, as_of: asOf.value, remark: remark.value || undefined });
    if (r && r.status === "Posted") toast.success(L(`Reclassified — ${r.voucher_no || ""}`, `تمت إعادة التصنيف — ${r.voucher_no || ""}`, `Reclassé — ${r.voucher_no || ""}`));
    else toast.info(L("Recorded — awaiting an approver", "سُجّل — بانتظار موافِق", "Enregistré — en attente"));
    emit("posted"); emit("close");
  } catch (e) { error.value = String(e?.message || e).slice(0, 200); }
  finally { busy.value = false; }
}
</script>
