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
          <div class="border border-line rounded-[10px] overflow-hidden max-h-[280px] overflow-y-auto">
            <table class="w-full text-[12px]">
              <thead class="sticky top-0"><tr style="background:#fafaf9">
                <th class="px-3 py-2 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Order","الطلب","Cmd") }}</th>
                <th class="px-3 py-2 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Customer","العميل","Client") }}</th>
                <th class="px-3 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("File amt","مبلغ الملف","Montant") }}</th>
                <th class="px-3 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Order amt","مبلغ الطلب","Cmde") }}</th>
              </tr></thead>
              <tbody>
                <tr v-for="(r, i) in (preview[cat] || []).slice(0, 300)" :key="i" class="border-t border-line-hair">
                  <td class="px-3 py-1.5 font-mono font-semibold">{{ r.order || ("#" + r.cmd) }}</td>
                  <td class="px-3 py-1.5 truncate max-w-[200px]">{{ r.customer || "—" }}</td>
                  <td class="px-3 py-1.5 text-end tnum">{{ fmt(r.amount) }}</td>
                  <td class="px-3 py-1.5 text-end tnum" :class="cat === 'variance' ? 'text-sale font-semibold' : 'text-ink-3'">{{ r.grand_total != null ? fmt(r.grand_total) : "—" }}</td>
                </tr>
                <tr v-if="!(preview[cat] || []).length"><td colspan="4" class="px-3 py-6 text-center text-ink-muted text-[12px]">{{ L("None","لا شيء","Aucun") }}</td></tr>
              </tbody>
            </table>
          </div>
        </template>
      </div>

      <div v-if="preview" class="flex items-center justify-end gap-2 px-5 py-3.5 border-t border-line bg-app-warm/40">
        <span class="me-auto text-[11.5px] text-ink-3">{{ L("Will mark","سيُعلّم","Marquera") }} <b>{{ preview.totals.matched }}</b> {{ L("orders Collected","طلب كمحصّل","encaissées") }}</span>
        <button class="px-3.5 py-2 rounded-chip text-[12px] font-semibold text-ink-2 hover:bg-white" @click="$emit('close')">{{ L("Cancel","إلغاء","Annuler") }}</button>
        <button class="px-4 py-2 rounded-chip text-[12px] font-bold text-white bg-accent hover:bg-accent-dark shadow-prim disabled:opacity-50" :disabled="!preview.totals.matched || applying" @click="apply">
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
    { label: L("COD value", "قيمة COD", "Valeur"), value: fmt(t.matched_value), style: "background:#fafaf9;border-color:#f0efed;color:#1c1917" },
    { label: L("To collect", "للتحصيل", "À encaisser"), value: t.matched + t.variance, style: "background:#f5f3ff;border-color:#ddd6fe;color:#7c3aed" },
  ];
});
const tieOk = computed(() => {
  const p = preview.value.totals.printed;
  return p && p.net && Math.abs(p.net - preview.value.totals.net_remitted) < 1;
});

function reset() { preview.value = null; error.value = ""; cat.value = "matched"; }
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
  if (!preview.value || !preview.value.totals.matched) return;
  applying.value = true; error.value = "";
  try {
    const orders = preview.value.matched.map((r) => r.order);
    const res = await api.call("accounting_portal.api.cod.apply_remittance", {
      company: currentCompany(), reference: preview.value.reference,
      orders, amount: preview.value.totals.matched_value,
    });
    if (res && res.status === "Posted") toast.success(L(`${orders.length} orders marked Collected`, `${orders.length} طلب اتعلّم محصّل`, `${orders.length} encaissées`));
    else toast.info(L("Recorded — awaiting an approver", "سُجّل — بانتظار موافِق", "Enregistré — en attente"));
    emit("applied");
  } catch (err) {
    error.value = (err && err.message) || L("Failed to apply.", "فشل التطبيق.", "Échec.");
  } finally { applying.value = false; }
}
</script>
