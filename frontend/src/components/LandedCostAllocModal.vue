<template>
  <div class="fixed inset-0 z-[100] overflow-y-auto flex items-start justify-center p-4" style="background:rgba(28,25,23,.45)" @click.self="$emit('close')">
    <div class="bg-white rounded-[16px] shadow-cardHover w-full max-w-3xl my-4">
      <header class="flex items-center gap-2.5 px-5 py-3.5 border-b border-line-hair">
        <span class="w-8 h-8 rounded-[10px] grid place-items-center" style="background:#ecfdf5"><Icon name="truck" :size="16" color="#047857" /></span>
        <div class="min-w-0">
          <div class="text-[14px] font-bold">{{ L("Capitalise landed cost","ترسيم تكلفة الشحن","Capitaliser le coût de revient") }}</div>
          <div class="text-[11px] text-ink-muted truncate">{{ receipts.join(", ") }}</div>
        </div>
        <button @click="$emit('close')" class="ms-auto w-7 h-7 grid place-items-center rounded-[8px] hover:bg-app-warm text-ink-muted"><Icon name="close" :size="14" /></button>
      </header>

      <div class="p-5 space-y-3.5">
        <!-- Charges -->
        <div>
          <div class="flex items-center justify-between mb-1">
            <label class="text-[11px] font-bold text-ink-3">{{ L("Charges to add to product cost","التكاليف اللي هتدخل التكلفة","Charges à capitaliser") }}</label>
            <span class="text-[10.5px] text-ink-muted">{{ L("credited to the account it sits on","تُدائن على حسابها","compte d'origine") }}</span>
          </div>
          <div v-if="hasMatched" class="text-[10.5px] text-emerald-700 mb-1 flex items-center gap-1"><Icon name="check" :size="12" />{{ L("auto-matched to this shipment by the bill reference","اترابطت بالشحنة تلقائيًا من مرجع الفاتورة","liées automatiquement") }}</div>
          <div class="border border-line rounded-[10px] divide-y divide-line-hair">
            <div v-for="(c,idx) in charges" :key="idx" class="flex items-center gap-2 px-2.5 py-2 text-[12px]" :class="c.include ? '' : 'opacity-55'">
              <input type="checkbox" v-model="c.include" class="shrink-0" />
              <div class="flex-1 min-w-0">
                <div class="truncate">{{ c.label }}
                  <span v-if="!c.matched" class="text-[10px] text-amber-600 ms-1">· {{ c.shipment ? L('other shipment','شحنة أخرى','autre') : L('unassigned — add if it belongs','غير مربوطة — أضِفها لو تخص الشحنة','non liée') }}</span>
                </div>
                <div v-if="c.is_legacy_pl" class="text-[10px] text-amber-600">{{ L("on a P&L account","على حساب مصروف","compte P&L") }}</div>
              </div>
              <select v-model="c.category" class="h-8 border border-line-2 rounded-[8px] px-1.5 text-[11.5px] bg-white">
                <option v-for="cat in CATS" :key="cat.k" :value="cat.k">{{ cat.label() }} · {{ cat.basis }}</option>
              </select>
              <span class="tnum font-semibold w-24 text-end">{{ fmt2(c.amount) }}</span>
            </div>
            <div v-if="!charges.length" class="px-2.5 py-4 text-center text-[11.5px] text-ink-muted">{{ L("No charges in the clearing inbox yet","مفيش تكاليف في صندوق الترسيم","Aucune charge") }}</div>
          </div>
          <div class="flex justify-between mt-1 text-[11px] text-ink-3">
            <span>{{ included.length }} {{ L("selected","مختار","sélectionné") }}</span>
            <span><span class="me-2">{{ L("Total","الإجمالي","Total") }}:</span><b class="tnum">{{ fmt2(totalCharge) }}</b></span>
          </div>
        </div>

        <div v-if="loading" class="py-4 text-center text-[12px] text-ink-muted">{{ L("Computing per-product cost…","جارٍ حساب التكلفة/منتج…","Calcul…") }}</div>

        <template v-else-if="pv">
          <!-- Guardrails -->
          <div v-if="pv.blocked || (pv.legacy_pl_charges && pv.legacy_pl_charges.length)" class="text-[11.5px] rounded-[10px] px-3 py-2 space-y-1"
               :class="pv.blocked ? 'text-rose-700 bg-rose-50 border border-rose-200' : 'text-amber-700 bg-amber-50 border border-amber-200'">
            <div v-for="(f,i) in pv.fx_offenders" :key="'fx'+i" class="flex items-start gap-1.5"><Icon name="alert" :size="12" color="#e11d48" class="mt-px" />{{ L("FX out of band","سعر صرف خارج النطاق","FX hors bande") }}: {{ f.receipt }} {{ f.currency }}@{{ f.rate }}</div>
            <div v-if="pv.needs_weight" class="flex items-start gap-1.5"><Icon name="alert" :size="12" color="#e11d48" class="mt-px" />{{ L("Freight by weight but items have no weight — fill weights first.","شحن بالوزن بس الأصناف بلا وزن — املأ الأوزان الأول.","Poids manquant.") }}</div>
            <div v-if="pv.legacy_pl_charges && pv.legacy_pl_charges.length" class="flex items-start gap-1.5"><Icon name="alert" :size="12" color="#b45309" class="mt-px" />{{ L("Some charges sit on a P&L account — capitalising still works but re-point them to 153.03 to keep the P&L clean.","بعض التكاليف على حساب مصروف — يفضل تحويلها لـ153.03.","Charges sur compte P&L.") }}</div>
          </div>

          <!-- Per-basis summary -->
          <div class="flex gap-2 flex-wrap">
            <span v-for="(v,b) in pv.by_basis" :key="b" class="rounded-chip bg-slate-50 border border-line px-2.5 py-1 text-[11px]">
              <b>{{ basisLabel(b) }}</b> · {{ fmt2(v) }}
            </span>
          </div>

          <!-- Per-product table -->
          <div class="border border-line rounded-[10px] overflow-hidden">
            <table class="w-full text-[11.5px]">
              <thead class="bg-app-warm/50 text-[10px] uppercase text-ink-muted">
                <tr><th class="text-start px-2.5 py-1.5">{{ L("Product","المنتج","Produit") }}</th><th class="text-end px-2 py-1.5">{{ L("Qty","كمية","Qté") }}</th><th class="text-end px-2 py-1.5">{{ L("Old cost","تكلفة قديمة","Ancien") }}</th><th class="text-end px-2 py-1.5">+{{ L("Landed/u","واصل/قطعة","CR/u") }}</th><th class="text-end px-2.5 py-1.5">{{ L("New cost","تكلفة جديدة","Nouveau") }}</th></tr>
              </thead>
              <tbody class="divide-y divide-line-hair">
                <tr v-for="r in pv.lines.slice(0,20)" :key="r.item_code">
                  <td class="px-2.5 py-1.5 truncate max-w-[180px]">{{ r.item_code }}</td>
                  <td class="px-2 py-1.5 text-end tnum">{{ r.qty }}</td>
                  <td class="px-2 py-1.5 text-end tnum text-ink-muted">{{ fmt2(r.rate) }}</td>
                  <td class="px-2 py-1.5 text-end tnum text-emerald-700">+{{ fmt2(r.per_unit) }}</td>
                  <td class="px-2.5 py-1.5 text-end tnum font-semibold">{{ fmt2(r.new_rate) }}</td>
                </tr>
              </tbody>
            </table>
            <div v-if="pv.lines_n>20" class="px-2.5 py-1 text-[10.5px] text-ink-muted bg-app-warm/30">+{{ pv.lines_n-20 }} {{ L("more","إضافي","de plus") }}</div>
          </div>
          <div v-if="pv.later_moves_to_repost" class="text-[11px] text-ink-muted">{{ pv.later_moves_to_repost }} {{ L("later stock moves will be reposted (COGS heals automatically).","حركة مخزون لاحقة هتتعاد (الـCOGS يتصحّح تلقائيًا).","mouvements re-postés.") }}</div>
        </template>

        <div v-if="error" class="text-[11.5px] text-sale">{{ error }}</div>
      </div>

      <footer class="flex items-center gap-2 px-5 py-3.5 border-t border-line-hair bg-app-warm/30 rounded-b-[16px]">
        <button @click="$emit('close')" class="h-9 px-3.5 rounded-chip text-[12px] font-semibold text-ink-2 hover:bg-app-warm">{{ L("Cancel","إلغاء","Annuler") }}</button>
        <button @click="post" :disabled="busy || !canPost" class="ms-auto h-9 px-4 rounded-chip text-[12px] font-bold text-white bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50">
          {{ busy ? L("Posting…","جارٍ…","…") : L("Capitalise","ترسيم","Capitaliser") }}
        </button>
      </footer>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useToast } from "@/composables/useToast";
import { useAuth } from "@/composables/useAuth";

const props = defineProps({ prefill: { type: Object, required: true } });
const emit = defineEmits(["close", "posted"]);
const { locale } = useI18n();
const toast = useToast();
const { can } = useAuth();
const canWrite = computed(() => can("post_entries"));
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt2 = (n) => Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const CATS = [
  { k: "freight", basis: "Weight", label: () => L("Freight", "شحن", "Fret") },
  { k: "handling", basis: "Weight", label: () => L("Handling", "مناولة", "Manutention") },
  { k: "haulage", basis: "Weight", label: () => L("Haulage", "نقل داخلي", "Camionnage") },
  { k: "demurrage", basis: "Weight", label: () => L("Demurrage", "أرضيات", "Surestaries") },
  { k: "forklift", basis: "Weight", label: () => L("Forklift", "رافعة", "Chariot") },
  { k: "customs", basis: "Amount", label: () => L("Customs duty", "جمارك", "Douane") },
  { k: "insurance", basis: "Amount", label: () => L("Insurance", "تأمين", "Assurance") },
  { k: "agent", basis: "Qty", label: () => L("Agent / clearance", "مخلّص", "Transitaire") },
];
const BASIS = { Weight: () => L("Weight", "وزن", "Poids"), Amount: () => L("Value", "قيمة", "Valeur"), Qty: () => L("Qty", "كمية", "Qté") };
const basisLabel = (b) => (BASIS[b] ? BASIS[b]() : b);

// guess a category from the account/description text
function guessCat(txt) {
  const t = (txt || "").toLowerCase();
  if (/custom|duty|douane|جمار/.test(t)) return "customs";
  if (/insur|assur|تأمين/.test(t)) return "insurance";
  if (/agent|clear|مخلّ|transit/.test(t)) return "agent";
  if (/demurr|أرضي/.test(t)) return "demurrage";
  if (/forklift|رافع/.test(t)) return "forklift";
  if (/haul|نقل الداخل|camion/.test(t)) return "haulage";
  return "freight";
}

const receipts = computed(() => props.prefill.receipts || []);
const charges = ref((props.prefill.charges || []).map((c) => ({
  label: c.account_name || c.description || c.account || c.vn,
  amount: Number(c.amount || 0),
  expense_account: c.account,
  source: c.vn,
  is_legacy_pl: !!c.is_legacy_pl,
  shipment: c.shipment || null,
  matched: !!c.matched,          // bill remark tags this shipment → auto-attached
  include: c.include !== false,  // matched charges are on by default, suggestions off
  category: guessCat(c.account_name || c.description || c.account),
})));
// only ticked charges are previewed / posted
const included = computed(() => charges.value.filter((c) => c.include));
const suggestions = computed(() => charges.value.filter((c) => !c.matched));
const hasMatched = computed(() => charges.value.some((c) => c.matched));
const totalCharge = computed(() => included.value.reduce((s, c) => s + Number(c.amount || 0), 0));
const clearingShort = ref(props.prefill.clearing_account ? String(props.prefill.clearing_account).split(" - ")[0] : "153.03");

const pv = ref(null);
const loading = ref(false);
const busy = ref(false);
const error = ref("");
const canPost = computed(() => canWrite.value && pv.value && !pv.value.blocked && included.value.length && receipts.value.length);

function payloadCharges() {
  return included.value.map((c) => ({ expense_account: c.expense_account, description: c.label, amount: c.amount, category: c.category, source: c.source }));
}

let seq = 0;
async function loadPreview() {
  if (!receipts.value.length || !included.value.length) { pv.value = null; return; }
  loading.value = true; error.value = "";
  const my = ++seq;
  try {
    const r = await api.call("accounting_portal.api.landed_pipeline.preview_lcv",
      { company: currentCompany(), receipts: JSON.stringify(receipts.value), charges: JSON.stringify(payloadCharges()) }, { fresh: true });
    if (my === seq) pv.value = r;
  } catch (e) { if (my === seq) { error.value = String(e?.message || e).slice(0, 180); pv.value = null; } }
  finally { if (my === seq) loading.value = false; }
}
watch(charges, loadPreview, { deep: true });
onMounted(loadPreview);

async function post() {
  if (busy.value || !canPost.value) return;
  busy.value = true; error.value = "";
  try {
    const r = await api.call("accounting_portal.api.landed_pipeline.post_lcv",
      { company: currentCompany(), receipts: JSON.stringify(receipts.value), charges: JSON.stringify(payloadCharges()) });
    if (r && r.status === "Proposed") toast.info(L("Sent for approval", "اتبعت للموافقة", "Envoyé pour approbation"));
    else toast.success(L(`Capitalised — ${r?.voucher_no || ""}`, `اترسّم — ${r?.voucher_no || ""}`, `Capitalisé — ${r?.voucher_no || ""}`));
    emit("posted"); emit("close");
  } catch (e) { error.value = String(e?.message || e).slice(0, 220); }
  finally { busy.value = false; }
}
</script>
