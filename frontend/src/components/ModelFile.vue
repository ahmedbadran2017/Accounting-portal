<template>
  <div class="space-y-4">
    <div v-if="loading" class="py-12 text-center text-[12px] text-ink-muted">{{ L("Loading model…","بيحمّل الموديل…","Chargement…") }}</div>
    <div v-else-if="err" class="py-12 text-center text-[12px] text-sale">{{ err }} <button class="underline" @click="load">{{ L("Retry","إعادة","Réessayer") }}</button></div>

    <template v-else-if="d">
      <!-- model header -->
      <div class="bg-white border border-line rounded-[14px] shadow-card px-5 py-4 flex items-center gap-4 flex-wrap">
        <div class="min-w-0 flex-1">
          <div class="text-[15px] font-bold truncate">{{ modelName }}</div>
          <div class="text-[11px] text-ink-muted mt-0.5">
            {{ d.model.n_stocked }} {{ L("variant(s) in stock","variant في المخزون","variantes en stock") }}
            · {{ L("one price for the whole model","سعر واحد للموديل كله","un prix pour le modèle") }}
          </div>
        </div>
        <div class="text-end">
          <div class="text-[10.5px] text-ink-muted font-semibold">{{ L("Suggested (family evidence)","المقترح (دليل العائلة)","Suggéré") }}</div>
          <div class="text-[18px] font-bold tnum" :class="d.model.suggested ? 'text-emerald-700' : 'text-amber-600'">
            {{ d.model.suggested != null ? fmtNum(d.model.suggested, 2) : L("no source","بلا مصدر","—") }}
          </div>
          <div v-if="d.model.basis_qty" class="text-[10px] text-ink-3 tnum">{{ L("basis","أساس","base") }} {{ d.model.basis_qty }}u</div>
        </div>
      </div>

      <!-- ① pooled evidence + one verified cost -->
      <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
        <div class="px-4 py-3 border-b border-line-hair"><span class="text-[13px] font-bold">① {{ L("Product cost — one verification for the family","تكلفة المنتج — تحقق واحد للعيلة كلها","① Coût produit") }}</span></div>
        <div class="p-4 space-y-3">
          <table v-if="d.evidence.length" class="w-full text-[11.5px]">
            <thead><tr style="background:#fafaf9">
              <th class="px-3 py-1.5 text-start text-[10px] font-bold text-ink-muted">{{ L("Document","المستند","Document") }}</th>
              <th class="px-3 py-1.5 text-start text-[10px] font-bold text-ink-muted">{{ L("Supplier","المورّد","Fournisseur") }}</th>
              <th class="px-3 py-1.5 text-end text-[10px] font-bold text-ink-muted">{{ L("Qty","كمية","Qté") }}</th>
              <th class="px-3 py-1.5 text-end text-[10px] font-bold text-ink-muted">{{ L("Rate","السعر","Taux") }}</th>
              <th class="px-3 py-1.5 text-end text-[10px] font-bold text-ink-muted">→ MAD</th>
            </tr></thead>
            <tbody>
              <tr v-for="e in d.evidence" :key="e.doc + (e.via || '')" class="border-t border-line-hair">
                <td class="px-3 py-1.5 font-mono text-[10.5px]" dir="ltr">{{ e.doc }}<span class="text-ink-muted font-sans"> · {{ e.dt }}</span><span v-if="e.via" class="font-sans text-[10px] text-violet-700"> 👪 {{ e.via }}</span></td>
                <td class="px-3 py-1.5 truncate max-w-[150px]">{{ e.supplier }}</td>
                <td class="px-3 py-1.5 text-end tnum">{{ fmtNum(e.qty) }}</td>
                <td class="px-3 py-1.5 text-end tnum">{{ fmtNum(e.rate, 2) }} {{ e.cur }}</td>
                <td class="px-3 py-1.5 text-end tnum font-bold" :class="e.rate_mad >= 0.5 ? 'text-emerald-700' : 'text-sale'">{{ fmtNum(e.rate_mad, 2) }}</td>
              </tr>
            </tbody>
          </table>
          <div v-else class="text-[11px] text-amber-700">{{ L("No purchase documents anywhere in the family — enter the cost manually (note required).","مفيش مستندات في العيلة كلها — أدخلوا التكلفة يدويًا (الملاحظة إجبارية).","Aucun document — saisir manuellement.") }}</div>
          <div class="flex items-center gap-2 flex-wrap pt-1 border-t border-line-hair">
            <label class="text-[11.5px] text-ink-2 font-semibold">{{ L("Verified cost (MAD/unit)","التكلفة المعتمدة (درهم/وحدة)","Coût vérifié") }}</label>
            <input v-model.number="rate" type="number" step="0.01" min="0" class="h-[30px] w-[110px] text-[12px] text-end px-2 rounded-[8px] border border-line tnum" dir="ltr" />
            <input v-model="note" :placeholder="L('Note (required if you change the figure)','ملاحظة (إجبارية لو غيرتوا الرقم)','Note')"
                   class="h-[30px] flex-1 min-w-[220px] text-[12px] px-2.5 rounded-[8px] border border-line" />
          </div>
        </div>
      </div>

      <!-- ③ variants -->
      <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
        <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2">
          <span class="text-[13px] font-bold">③ {{ L("Variants — what one Submit will do","الـvariants — اللي الاعتماد الواحد هيعمله","③ Variantes") }}</span>
          <span v-if="d.waiting_prs.length" class="text-[10.5px] font-bold px-2 py-0.5 rounded-full" style="background:#fffbeb;color:#b45309">
            ⏳ {{ d.waiting_prs.length }} {{ L("shipment(s) missing freight","شحنة ناقصها شحن","expéditions sans fret") }}
          </span>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-[11.5px]">
            <thead><tr style="background:#fafaf9">
              <th class="px-3 py-2 text-center text-[10px] font-bold text-ink-muted">{{ L("Apply","تطبيق","OK") }}</th>
              <th class="px-4 py-2 text-start text-[10px] font-bold text-ink-muted">{{ L("Variant","الصنف","Variante") }}</th>
              <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("Qty","كمية","Qté") }}</th>
              <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("Book","الدفاتر","Livre") }}</th>
              <th class="px-3 py-2 text-center text-[10px] font-bold text-ink-muted">{{ L("Status","الحالة","Statut") }}</th>
              <th class="px-3 py-2 text-center text-[10px] font-bold text-ink-muted"></th>
            </tr></thead>
            <tbody>
              <tr v-for="v in d.variants" :key="v.item_code" class="border-t border-line-hair" :class="results[v.item_code] === 'ok' ? 'bg-emerald-50/40' : ''">
                <td class="px-3 py-1.5 text-center">
                  <input type="checkbox" :checked="!excluded.has(v.item_code)" :disabled="v.fixed || v.batch_tracked || posting"
                         @change="toggleExclude(v.item_code)" />
                </td>
                <td class="px-4 py-1.5"><span class="font-semibold">{{ v.sku || v.item_code }}</span><span class="text-[10px] text-ink-muted"> · {{ v.item_name }}</span></td>
                <td class="px-3 py-1.5 text-end tnum">{{ fmtNum(v.qty) }}</td>
                <td class="px-3 py-1.5 text-end tnum">{{ fmtNum(v.book_rate, 2) }}</td>
                <td class="px-3 py-1.5 text-center">
                  <span v-if="v.fixed" class="text-[10px] font-bold px-1.5 py-0.5 rounded-full" style="background:#ecfdf5;color:#047857">✓ {{ L("fixed","متظبط","corrigé") }}</span>
                  <span v-else-if="v.batch_tracked" class="text-[10px] font-bold px-1.5 py-0.5 rounded-full" style="background:#faf5ff;color:#7c3aed" :title="L('batch/serial tracked — manual path','بتتبع باتشات — مسار يدوي','suivi par lot')">🧬</span>
                  <span v-else-if="v.waiting.length" class="text-[10px] font-bold px-1.5 py-0.5 rounded-full" style="background:#fffbeb;color:#b45309" :title="v.waiting.join(', ')">⏳ {{ L("freight","شحن","fret") }}</span>
                  <span v-else class="text-[10px] font-bold px-1.5 py-0.5 rounded-full" style="background:#eff6ff;color:#2563eb">{{ L("ready","جاهز","prêt") }}</span>
                </td>
                <td class="px-3 py-1.5 text-center text-[12px]">
                  <span v-if="results[v.item_code] === 'ok'" class="text-emerald-700 font-bold">✓</span>
                  <span v-else-if="results[v.item_code]" class="text-sale font-bold" :title="results[v.item_code]">✕</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- ④ submit -->
      <div v-if="canWrite" class="bg-white border rounded-[14px] shadow-card px-4 py-3.5 flex items-center gap-3 flex-wrap" :style="canSubmit ? 'border-color:#a7f3d0' : 'border-color:#e7e5e4'">
        <div class="flex-1 min-w-[260px]">
          <div class="text-[12px] font-bold">④ {{ L("Submit — the whole model, retroactively","الاعتماد — الموديل كله بأثر رجعي","④ Soumettre") }}</div>
          <div class="text-[11px] text-ink-muted mt-0.5">{{ L("Each variant posts its OWN retro schedule (its receipts, its dates) at this one product cost — one undoable action per variant.","كل variant بياخد جدوله الزمني الخاص (استلاماته وتواريخه) بنفس تكلفة المنتج — وUndo مستقل لكل واحد.","Chaque variante a son propre plan rétro.") }}</div>
        </div>
        <template v-if="posting">
          <div class="flex-1 h-[8px] rounded-full overflow-hidden min-w-[140px]" style="background:#f5f5f4">
            <div class="h-full rounded-full transition-all" style="background:#059669" :style="{ width: (progress / Math.max(targetCount, 1) * 100) + '%' }"></div>
          </div>
          <span class="text-[11.5px] tnum text-ink-muted">{{ progress }} / {{ targetCount }}</span>
        </template>
        <template v-else>
          <span v-if="finished" class="text-[12px] font-bold text-emerald-700">✓ {{ posted }} {{ L("posted","اترحّل","comptabilisés") }}<span v-if="failed" class="text-sale"> · {{ failed }} {{ L("failed","فشل","échoués") }}</span></span>
          <span v-if="draining" class="text-[11px] text-ink-muted">⏳ {{ L("reposting old moves…","بيعاد حساب الحركات القديمة…","recalcul…") }}</span>
          <button class="h-[34px] px-5 rounded-[10px] text-[12.5px] font-bold text-white bg-brand hover:bg-brand-dark disabled:opacity-40"
                  :disabled="!canSubmit" @click="runSubmit">
            {{ L("Submit","اعتماد","Soumettre") }} {{ targetCount }}
          </button>
        </template>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed } from "vue";
import { useI18n } from "vue-i18n";
import api from "@/services/api";
import { useToast } from "@/composables/useToast";
import { useAuth } from "@/composables/useAuth";

const props = defineProps({ seed: { type: String, required: true } });
const emit = defineEmits(["applied"]);
const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const toast = useToast();
const { can } = useAuth();
const canWrite = computed(() => can("post_entries"));
const M = "accounting_portal.api.model_costing";
const fmtNum = (n, d = 0) => new Intl.NumberFormat(undefined, { maximumFractionDigits: d }).format(n || 0);

const d = ref(null);
const loading = ref(false);
const err = ref("");
const rate = ref(null);
const note = ref("");
const excluded = ref(new Set());
const results = ref({});
const posting = ref(false);
const finished = ref(false);
const draining = ref(false);
const posted = ref(0);
const failed = ref(0);
const progress = ref(0);

const modelName = computed(() => {
  const n = d.value?.variants?.[0]?.item_name || props.seed;
  return n.split(" / ")[0];
});
const targetCount = computed(() =>
  (d.value?.variants || []).filter((v) => !v.fixed && !v.batch_tracked && !excluded.value.has(v.item_code)).length);
const canSubmit = computed(() => rate.value > 0 && targetCount.value > 0 && !posting.value);

function toggleExclude(ic) {
  const s = new Set(excluded.value);
  s.has(ic) ? s.delete(ic) : s.add(ic);
  excluded.value = s;
}

async function load() {
  loading.value = true;
  err.value = "";
  try {
    d.value = await api.call(`${M}.model_detail`, { item_code: props.seed }, { fresh: true });
    if (d.value.model.suggested && !rate.value) rate.value = d.value.model.suggested;
  } catch (e) { err.value = e.message || "Failed"; }
  finally { loading.value = false; }
}
load();

async function runSubmit() {
  if (!canSubmit.value) return;
  if (!window.confirm(L(
    `Apply ${targetCount.value} variant(s) at ${rate.value} MAD product cost, RETROACTIVELY from each one's first 2026 receipt?`,
    `تطبيق ${targetCount.value} variant بتكلفة منتج ${rate.value} درهم، بأثر رجعي من أول استلام 2026 لكل واحد؟`,
    `Appliquer ${targetCount.value} variante(s) ?`))) return;
  posting.value = true;
  finished.value = false;
  posted.value = 0; failed.value = 0; progress.value = 0;
  try {
    for (let w = 0; w < 20; w++) {
      const r = await api.call(`${M}.apply_model`, {
        item_code: props.seed, rate: rate.value, note: note.value || undefined,
        retro: 1, exclude: JSON.stringify([...excluded.value]), limit: 15,
      }, { fresh: true });
      for (const p of r.posted) { if (results.value[p.item_code] !== "ok") posted.value++; results.value[p.item_code] = "ok"; }
      for (const s of r.skipped) { if (!results.value[s.item_code]) failed.value++; results.value[s.item_code] = s.reason || "failed"; }
      progress.value = posted.value + failed.value;
      if (!r.posted.length || !r.remaining) break;
    }
    toast.success(L(`Model applied — ${posted.value} variant(s)`, `الموديل اتطبق — ${posted.value} variant`, `${posted.value} appliqués`));
  } catch (e) { toast.error(e.message || "Failed"); }
  finally {
    posting.value = false;
    finished.value = true;
    emit("applied");
    await load();
    draining.value = true;
    for (let i = 0; i < 12; i++) {
      try {
        const r = await api.call("accounting_portal.api.valuation.drain_reposts", { budget_s: 45 }, { fresh: true });
        if (!r.remaining) break;
      } catch { break; }
    }
    draining.value = false;
  }
}
</script>
