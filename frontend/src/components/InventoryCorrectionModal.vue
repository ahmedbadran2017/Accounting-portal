<template>
  <div v-if="open" class="fixed inset-0 z-[110] flex items-start justify-center p-4 overflow-y-auto" style="background:rgba(28,25,23,.45)" @click.self="$emit('close')">
    <div class="bg-white rounded-[16px] shadow-cardHover w-full max-w-xl my-6">
      <div class="flex items-center gap-2.5 px-5 py-3.5 border-b border-line">
        <span class="w-8 h-8 rounded-[10px] grid place-items-center" style="background:#fef3c7"><Icon name="shield" :size="16" color="#b45309" /></span>
        <div class="text-[14px] font-bold">{{ L("Propose correcting entry","اقتراح قيد تصحيح","Proposer une écriture") }}</div>
        <button class="ms-auto h-8 w-8 grid place-items-center rounded-[8px] text-ink-3 hover:bg-app-warm" @click="$emit('close')">✕</button>
      </div>

      <div v-if="loading" class="p-8 text-center text-[12px] text-ink-muted">{{ L("Analysing the books…","تحليل الدفاتر…","Analyse…") }}</div>
      <div v-else-if="!p || !p.available" class="p-8 text-center text-[12px] text-ink-muted">{{ L("No inventory distortion detected.","لا يوجد تشوّه في المخزون.","Aucune distorsion.") }}</div>
      <div v-else class="p-5 space-y-3.5">
        <!-- Diagnosis -->
        <div class="rounded-[12px] border border-amber-200 bg-amber-50 px-4 py-3">
          <p v-if="p.stock_account" class="text-[11.5px] text-amber-800 leading-relaxed">{{ L("Stock-in-hand carries "+money(p.stock_balance)+" while “"+shortAcct(p.adjustment_account)+"” absorbs "+money(p.adjustment_balance)+". This nets the churn out: stock falls to "+money(p.stock_after)+" and the adjustment account zeroes.","المخزون يحمل "+money(p.stock_balance)+" بينما يمتص حساب التسوية "+money(p.adjustment_balance)+". هذا القيد يصفّي الفرق: المخزون ينزل إلى "+money(p.stock_after)+".","Le stock porte "+money(p.stock_balance)+"; cette écriture le ramène à "+money(p.stock_after)+".") }}</p>
          <p v-else class="text-[11.5px] text-amber-800 leading-relaxed">{{ L("“"+shortAcct(p.account)+"” holds "+money(p.balance)+" across "+(p.entries||0).toLocaleString()+" parked entries. This reclassifies the balance to COGS and zeroes the pile.","حساب التصحيح يحمل "+money(p.balance)+" عبر "+(p.entries||0).toLocaleString()+" قيد. هذا يعيد تصنيفه لتكلفة المبيعات ويصفّي الرصيد.","Le compte de correction porte "+money(p.balance)+" sur "+(p.entries||0).toLocaleString()+" écritures. Reclassé en CMV.") }}</p>
        </div>

        <!-- Credit target choice (inventory only) -->
        <div v-if="p.stock_account" class="flex items-center gap-2 flex-wrap">
          <span class="text-[11px] font-bold text-ink-3">{{ L("Offset against","المقابل","Contrepartie") }}:</span>
          <button @click="setTarget('stock')" class="text-[11px] font-semibold px-2.5 py-1 rounded-full border" :class="target==='stock' ? 'bg-ink text-white border-ink' : 'bg-white text-ink-3 border-line-2'">{{ L("Net to stock (conservative)","تصفية مقابل المخزون","Stock") }}</button>
          <button v-if="p.cogs_account" @click="setTarget('cogs')" class="text-[11px] font-semibold px-2.5 py-1 rounded-full border" :class="target==='cogs' ? 'bg-ink text-white border-ink' : 'bg-white text-ink-3 border-line-2'">{{ L("Reclass to COGS (if delivered)","ترحيل لتكلفة المبيعات","CMV") }}</button>
        </div>

        <!-- Editable lines -->
        <div class="border border-line rounded-[12px] overflow-hidden">
          <table class="w-full text-[12px]">
            <thead><tr style="background:#fafaf9">
              <th class="px-3 py-2 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Account","الحساب","Compte") }}</th>
              <th class="px-3 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Debit","مدين","Débit") }}</th>
              <th class="px-3 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Credit","دائن","Crédit") }}</th>
            </tr></thead>
            <tbody>
              <tr v-for="(ln, i) in lines" :key="i" class="border-t border-line-hair">
                <td class="px-3 py-2">
                  <select v-model="ln.account" class="w-full h-8 border border-line-2 rounded-[8px] px-1.5 text-[11.5px] bg-white focus:outline-none focus:border-accent/40">
                    <option v-for="a in accounts" :key="a.name" :value="a.name">{{ a.name }}</option>
                  </select>
                </td>
                <td class="px-3 py-2"><input v-model.number="ln.debit" type="number" min="0" class="w-28 h-8 border border-line-2 rounded-[8px] px-2 text-[11.5px] text-end tnum focus:outline-none focus:border-accent/40" /></td>
                <td class="px-3 py-2"><input v-model.number="ln.credit" type="number" min="0" class="w-28 h-8 border border-line-2 rounded-[8px] px-2 text-[11.5px] text-end tnum focus:outline-none focus:border-accent/40" /></td>
              </tr>
            </tbody>
            <tfoot>
              <tr class="border-t-2 border-line-2 font-bold" style="background:#fafaf9">
                <td class="px-3 py-2">{{ balanced ? L("Balanced","متوازن","Équilibré") : L("Out of balance","غير متوازن","Déséquilibré") }}</td>
                <td class="px-3 py-2 text-end tnum">{{ fmt(totalDr) }}</td>
                <td class="px-3 py-2 text-end tnum" :class="balanced ? '' : 'text-sale'">{{ fmt(totalCr) }}</td>
              </tr>
            </tfoot>
          </table>
        </div>

        <input v-model.trim="remark" :placeholder="L('Remark','ملاحظة','Remarque')" class="w-full h-9 border border-line-2 rounded-[9px] px-3 text-[12.5px] focus:outline-none focus:border-accent/40" />
        <div class="flex items-center gap-2 text-[10.5px] text-ink-muted"><Icon name="shield" :size="12" />{{ L("Large entries are sent for approval before they post — nothing posts directly.","القيود الكبيرة تُرسل للموافقة قبل الترحيل.","Les écritures importantes nécessitent une approbation.") }}</div>
        <div v-if="error" class="text-[11.5px] text-sale">{{ error }}</div>
        <div class="flex justify-end gap-2">
          <button class="px-3.5 py-2 rounded-chip text-[12px] font-semibold text-ink-2 hover:bg-app-warm" @click="$emit('close')">{{ L("Cancel","إلغاء","Annuler") }}</button>
          <button class="px-4 py-2 rounded-chip text-[12px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand disabled:opacity-50" :disabled="busy || !balanced || !totalDr" @click="submit">
            {{ busy ? L("Submitting…","جارٍ…","…") : L("Submit for approval","إرسال للموافقة","Soumettre") }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { fmtAmount } from "@/utils/helpers";
import { ref, computed, watch } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useToast } from "@/composables/useToast";

const props = defineProps({ open: Boolean, kind: { type: String, default: "inventory" } });
const emit = defineEmits(["close", "done"]);
const ENDPOINT = { inventory: "propose_inventory_correction", correction: "propose_correction_pile" };
const { locale } = useI18n();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const money = (n) => fmtAmount(n);
const shortAcct = (a) => String(a || "").split(" - ").slice(0, 2).join(" ");

const p = ref(null);
const accounts = ref([]);
const lines = ref([]);
const remark = ref("");
const target = ref("stock");
const loading = ref(false);
const busy = ref(false);
const error = ref("");

const totalDr = computed(() => lines.value.reduce((s, l) => s + (Number(l.debit) || 0), 0));
const totalCr = computed(() => lines.value.reduce((s, l) => s + (Number(l.credit) || 0), 0));
const balanced = computed(() => totalDr.value > 0 && Math.round((totalDr.value - totalCr.value) * 100) === 0);

async function loadAll() {
  loading.value = true; error.value = "";
  try {
    p.value = await api.call(`accounting_portal.api.accountant.${ENDPOINT[props.kind] || ENDPOINT.inventory}`, { company: currentCompany() });
    accounts.value = await api.call("accounting_portal.api.accountant.account_options", { company: currentCompany() });
    if (p.value && p.value.available) {
      lines.value = p.value.lines.map((l) => ({ account: l.account, debit: l.debit, credit: l.credit }));
      remark.value = p.value.remark || "";
      target.value = "stock";
    }
  } catch (e) { error.value = String((e && e.message) || "Failed").slice(0, 140); }
  finally { loading.value = false; }
}
watch(() => props.open, (o) => { if (o) loadAll(); });

function setTarget(t) {
  target.value = t;
  if (!p.value) return;
  // Line 0 = Dr Stock-Adjustment (fixed); line 1 = the credit target.
  lines.value[1].account = t === "cogs" ? p.value.cogs_account : p.value.stock_account;
}

async function submit() {
  error.value = ""; busy.value = true;
  try {
    const res = await api.call("accounting_portal.api.accountant.create_journal_entry", {
      company: currentCompany(), lines: JSON.stringify(lines.value), remark: remark.value || undefined,
    });
    if (res && res.status === "Posted") toast.success(L(`Posted ${res.voucher_no || ""}`, `تم الترحيل ${res.voucher_no || ""}`, `Passé ${res.voucher_no || ""}`));
    else toast.info(L("Sent for approval", "أُرسل للموافقة", "Envoyé pour approbation"));
    emit("done"); emit("close");
  } catch (e) { error.value = String((e && e.message) || L("Failed", "فشل", "Échec")).slice(0, 160); }
  finally { busy.value = false; }
}
</script>
