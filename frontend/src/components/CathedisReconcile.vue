<template>
  <div class="fixed inset-0 z-[100] flex items-start justify-center p-4 sm:p-8 overflow-y-auto" style="background:rgba(28,25,23,.45)" @click.self="$emit('close')">
    <div class="bg-white rounded-[18px] shadow-cardHover w-full max-w-3xl my-6 overflow-hidden">
      <div class="flex items-center gap-2.5 px-5 py-4 border-b border-line">
        <span class="w-8 h-8 rounded-[10px] grid place-items-center" style="background:#f5f3ff"><Icon name="coins" :size="16" color="#7c3aed" /></span>
        <div class="flex-1 min-w-0">
          <div class="text-[14px] font-bold">{{ L("Reconcile Cathedis remittance","مطابقة تحويل كاتدييس","Rapprochement Cathedis") }}</div>
          <div class="text-[11px] text-ink-muted">{{ L("Upload the daily file — matched orders move Delivered → Collected","ارفع الملف اليومي — المطابق ينتقل من مُسلّم لمحصّل","Le fichier déplace Livrées → Encaissées") }}</div>
        </div>
        <button class="text-ink-3 hover:text-ink" @click="$emit('close')"><Icon name="close" :size="18" /></button>
      </div>

      <div class="p-5 space-y-3.5">
        <!-- Upload -->
        <label v-if="!preview" class="block border-2 border-dashed border-line-2 rounded-[14px] px-5 py-8 text-center cursor-pointer hover:border-accent/40 hover:bg-app-warm/30 transition">
          <input type="file" accept="application/pdf,.pdf" class="hidden" @change="onFile" />
          <Icon name="doc" :size="26" color="#a8a29e" class="mx-auto" />
          <div class="text-[13px] font-semibold mt-2">{{ parsing ? L("Reading the file…","جارٍ قراءة الملف…","Lecture…") : L("Drop the Cathedis PDF here, or click to choose","اسحب ملف كاتدييس PDF أو اضغط للاختيار","Déposez le PDF Cathedis") }}</div>
          <div class="text-[11px] text-ink-muted mt-1">“Retour de fonds … .pdf”</div>
        </label>

        <div v-if="error" class="text-[11.5px] text-sale bg-sale/5 border border-sale/20 rounded-chip px-3 py-2">{{ error }}</div>

        <!-- Preview -->
        <template v-if="preview">
          <div class="flex items-center gap-2 flex-wrap">
            <span class="text-[12px] font-bold font-mono px-2 py-1 rounded-chip bg-app-warm">{{ preview.reference || "—" }}</span>
            <span class="text-[11px] text-ink-muted">{{ preview.filename }}</span>
            <button class="ms-auto text-[11px] font-semibold text-accent hover:text-accent-dark" @click="reset">{{ L("Choose another file","اختر ملف آخر","Autre fichier") }}</button>
          </div>

          <!-- Tie-out -->
          <div class="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
            <div v-for="t in tiles" :key="t.label" class="rounded-[11px] px-3 py-2.5 border" :style="t.style">
              <div class="text-[10px] font-bold uppercase tracking-wider opacity-70">{{ t.label }}</div>
              <div class="text-[16px] font-extrabold tnum mt-0.5">{{ t.value }}</div>
            </div>
          </div>
          <div v-if="preview.totals.by_method" class="flex items-center gap-1.5 flex-wrap text-[10.5px]">
            <span class="text-ink-muted font-semibold uppercase tracking-wider me-1">{{ L("Matched by method","المطابق حسب الدفع","Par paiement") }}</span>
            <span class="font-bold px-2 py-0.5 rounded-full" style="background:#ecfdf5;color:#047857">{{ preview.totals.by_method.cod }} COD</span>
            <span v-if="preview.totals.by_method.card" class="font-bold px-2 py-0.5 rounded-full" style="background:#f5f3ff;color:#7c3aed">{{ preview.totals.by_method.card }} {{ L("Card","كارت","Carte") }}</span>
            <span v-if="preview.totals.by_method.bank" class="font-bold px-2 py-0.5 rounded-full" style="background:#eff6ff;color:#0369a1">{{ preview.totals.by_method.bank }} {{ L("Bank","بنك","Banque") }}</span>
          </div>
          <div v-if="grossTie" class="text-[11px] text-ink-3 flex items-center gap-1.5">
            <Icon name="check" :size="13" :color="grossTie.ok ? '#16a34a' : '#d97706'" />
            {{ L("File Total livré","Total livré بالملف","Total livré") }}: <b>{{ fmt(grossTie.printed) }}</b> · {{ L("parsed Montant","مجموع Montant","Montant lu") }}: <b>{{ fmt(grossTie.parsed) }}</b>
            <span :style="{ color: grossTie.ok ? '#16a34a' : '#d97706' }">{{ grossTie.ok ? L("✓ ties out","✓ متطابق","✓ concorde") : L("⚠ lines missing","⚠ سطور ناقصة","⚠ lignes manquantes") }}</span>
          </div>
          <div v-if="preview.totals.printed && preview.totals.printed.net" class="text-[11px] text-ink-3 flex items-center gap-1.5">
            <Icon name="check" :size="13" :color="tieOk ? '#16a34a' : '#d97706'" />
            {{ L("File net","صافي الملف","Net fichier") }}: <b>{{ fmt(preview.totals.printed.net) }}</b> · {{ L("matched net","صافي المطابق","Net rapproché") }}: <b>{{ fmt(preview.totals.net_remitted) }}</b>
            <span :style="{ color: tieOk ? '#16a34a' : '#d97706' }">{{ tieOk ? L("✓ ties out","✓ متطابق","✓ concorde") : L("⚠ review remainder","⚠ راجع الباقي","⚠ écart") }}</span>
          </div>

          <!-- category tabs -->
          <div class="flex items-center gap-1 border-b border-line-hair">
            <button v-for="c in cats" :key="c.key" class="px-3 py-2 text-[12px] font-semibold border-b-2 -mb-px transition"
                    :class="cat === c.key ? 'border-accent text-accent-dark' : 'border-transparent text-ink-3 hover:text-ink'" @click="cat = c.key">
              {{ c.label() }} <span class="text-[10px] px-1.5 py-0.5 rounded-full" :style="c.badge">{{ (preview[c.key] || []).length }}</span>
            </button>
          </div>
          <p v-if="cat === 'variance' && (preview.variance || []).length" class="text-[11px] text-ink-3 -mb-1">
            {{ L("File cash ≠ expected. Usually card/bank paid (already settled) or partial — tick the ones you confirm to also collect.","الكاش في الملف ≠ المتوقّع. غالبًا مدفوع كارت/بنك أو جزئي — علّم اللي تأكّده عشان يتحصّل برضه.","Encaisse ≠ attendu. Cochez celles à encaisser.") }}
          </p>
          <div class="border border-line rounded-[10px] overflow-hidden max-h-[280px] overflow-y-auto">
            <table class="w-full text-[12px]">
              <thead class="sticky top-0"><tr style="background:#fafaf9">
                <th v-if="cat === 'variance'" class="px-2 py-2 w-9 text-center"><input type="checkbox" :checked="allVarSelected" @change="toggleAllVar" class="accent-accent" /></th>
                <th class="px-3 py-2 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Order","الطلب","Cmd") }}</th>
                <th class="px-3 py-2 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Customer","العميل","Client") }}</th>
                <th class="px-3 py-2 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Method","الدفع","Paiement") }}</th>
                <th class="px-3 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Expected","المتوقّع","Attendu") }}</th>
                <th class="px-3 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("File cash","كاش الملف","Encaisse") }}</th>
              </tr></thead>
              <tbody>
                <tr v-for="(r, i) in (preview[cat] || []).slice(0, 300)" :key="i" class="border-t border-line-hair"
                    :class="cat === 'variance' && selectedVar.has(r.order) ? 'bg-violet-50' : ''">
                  <td v-if="cat === 'variance'" class="px-2 py-1.5 text-center"><input type="checkbox" :checked="selectedVar.has(r.order)" :disabled="!r.order" @change="toggleVar(r.order)" class="accent-accent" /></td>
                  <td class="px-3 py-1.5 font-mono font-semibold">{{ r.order || ("#" + r.cmd) }}</td>
                  <td class="px-3 py-1.5 truncate max-w-[150px]">{{ r.customer || "—" }}</td>
                  <td class="px-3 py-1.5"><span v-if="r.method" class="text-[10px] font-bold px-1.5 py-0.5 rounded-full" :style="methodStyle(r.method)">{{ r.method }}</span><span v-else class="text-ink-muted">—</span></td>
                  <td class="px-3 py-1.5 text-end tnum text-ink-3">{{ r.expected != null ? fmt(r.expected) : "—" }}</td>
                  <td class="px-3 py-1.5 text-end tnum" :class="cat === 'variance' ? 'font-semibold' : ''">{{ fmt(r.amount) }}</td>
                </tr>
                <tr v-if="!(preview[cat] || []).length"><td :colspan="cat === 'variance' ? 6 : 5" class="px-3 py-6 text-center text-ink-muted text-[12px]">{{ L("None","لا شيء","Aucun") }}</td></tr>
              </tbody>
            </table>
          </div>
        </template>
      </div>

      <div v-if="preview" class="flex items-center justify-end gap-2 px-5 py-3.5 border-t border-line bg-app-warm/40">
        <span class="me-auto text-[11.5px] text-ink-3">{{ L("Will mark","سيُعلّم","Marquera") }} <b>{{ willMark }}</b> {{ L("orders Collected","طلب كمحصّل","encaissées") }}<span v-if="selectedVar.size" class="text-violet-600"> ({{ preview.totals.matched }} + {{ selectedVar.size }} {{ L("confirmed","مؤكّد","confirmées") }})</span></span>
        <button class="px-3.5 py-2 rounded-chip text-[12px] font-semibold text-ink-2 hover:bg-white" @click="$emit('close')">{{ L("Cancel","إلغاء","Annuler") }}</button>
        <button class="px-4 py-2 rounded-chip text-[12px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand disabled:opacity-50" :disabled="!willMark || applying" @click="apply">
          {{ applying ? L("Applying…","جارٍ…","…") : L("Mark Collected","تعليم كمحصّل","Marquer encaissées") }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useToast } from "@/composables/useToast";

const emit = defineEmits(["close", "applied"]);
const { locale } = useI18n();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US", { maximumFractionDigits: 2 });

const parsing = ref(false);
const applying = ref(false);
const error = ref("");
const preview = ref(null);
const cat = ref("matched");

const cats = [
  { key: "matched", label: () => L("Matched", "مطابق", "Rapprochées"), badge: "background:#ecfdf5;color:#047857" },
  { key: "variance", label: () => L("Variance", "فروق", "Écarts"), badge: "background:#fffbeb;color:#b45309" },
  { key: "already_collected", label: () => L("Already collected", "محصّلة سابقًا", "Déjà"), badge: "background:#eff6ff;color:#0369a1" },
  { key: "not_found", label: () => L("Not found", "غير موجود", "Introuvable"), badge: "background:#fef2f2;color:#b91c1c" },
];

const tiles = computed(() => {
  const t = preview.value.totals;
  return [
    { label: L("Lines", "سطور", "Lignes"), value: t.lines, style: "background:#fafaf9;border-color:#f0efed;color:#1c1917" },
    { label: L("Matched", "مطابق", "Rapprochées"), value: t.matched, style: "background:#ecfdf5;border-color:#a7f3d0;color:#047857" },
    { label: L("Gross COD", "إجمالي COD", "Total COD"), value: fmt(t.gross_cod), style: "background:#e1f5ee;border-color:#9fe1cb;color:#0f6e56" },
    { label: L("To collect", "للتحصيل", "À encaisser"), value: fmt(t.matched_value), style: "background:#f5f3ff;border-color:#ddd6fe;color:#7c3aed" },
  ];
});
// Gross COD (sum of every Montant) must tie to the file's printed "Total livré".
const grossTie = computed(() => {
  const t = preview.value.totals, d = (t.printed || {}).delivered;
  if (!d) return null;
  return { printed: d, parsed: t.gross_cod, ok: Math.abs(d - t.gross_cod) < 1 };
});
const tieOk = computed(() => {
  const p = preview.value.totals.printed;
  return p && p.net && Math.abs(p.net - preview.value.totals.net_remitted) < 1;
});

const selectedVar = ref(new Set());
const willMark = computed(() => (preview.value ? preview.value.totals.matched + selectedVar.value.size : 0));
const allVarSelected = computed(() => {
  const v = (preview.value && preview.value.variance || []).filter((r) => r.order);
  return v.length > 0 && v.every((r) => selectedVar.value.has(r.order));
});
function methodStyle(m) {
  if (m === "Card") return "background:#f5f3ff;color:#7c3aed";
  if (m === "Bank") return "background:#eff6ff;color:#0369a1";
  return "background:#ecfdf5;color:#047857"; // COD
}
function toggleVar(order) {
  if (!order) return;
  const s = new Set(selectedVar.value);
  s.has(order) ? s.delete(order) : s.add(order);
  selectedVar.value = s;
}
function toggleAllVar() {
  const v = (preview.value && preview.value.variance || []).filter((r) => r.order);
  selectedVar.value = allVarSelected.value ? new Set() : new Set(v.map((r) => r.order));
}

function reset() { preview.value = null; error.value = ""; cat.value = "matched"; selectedVar.value = new Set(); }
function onFile(e) {
  const file = e.target.files && e.target.files[0];
  if (!file) return;
  error.value = ""; parsing.value = true;
  const reader = new FileReader();
  reader.onload = async () => {
    try {
      const r = await api.call("accounting_portal.api.cod.match_remittance", { company: currentCompany(), content_b64: reader.result, filename: file.name });
      preview.value = r;
    } catch (err) {
      error.value = (err && err.message) || L("Couldn't read the file.", "تعذّر قراءة الملف.", "Échec de lecture.");
    } finally { parsing.value = false; }
  };
  reader.onerror = () => { parsing.value = false; error.value = L("Couldn't read the file.", "تعذّر قراءة الملف.", "Échec."); };
  reader.readAsDataURL(file);
}

async function apply() {
  if (!preview.value || !willMark.value) return;
  applying.value = true; error.value = "";
  try {
    const confirmedVar = (preview.value.variance || []).filter((r) => selectedVar.value.has(r.order));
    const orders = [...preview.value.matched.map((r) => r.order), ...confirmedVar.map((r) => r.order)];
    const amount = preview.value.totals.matched_value + confirmedVar.reduce((s, r) => s + (Number(r.amount) || 0), 0);
    const res = await api.call("accounting_portal.api.cod.apply_remittance", {
      company: currentCompany(), reference: preview.value.reference,
      orders, amount,
    });
    if (res && res.status === "Posted") toast.success(L(`${orders.length} orders marked Collected`, `${orders.length} طلب اتعلّم محصّل`, `${orders.length} encaissées`));
    else toast.info(L("Recorded — awaiting an approver", "سُجّل — بانتظار موافِق", "Enregistré — en attente"));
    emit("applied");
  } catch (err) {
    error.value = (err && err.message) || L("Failed to apply.", "فشل التطبيق.", "Échec.");
  } finally { applying.value = false; }
}
</script>
