<template>
  <div class="space-y-3.5">
    <!-- what this screen is -->
    <div class="rounded-[14px] px-4 py-3 border" style="background:#eff6ff;border-color:#bfdbfe">
      <div class="text-[12px] font-bold" style="color:#1e40af">
        {{ L("Vendor workbench — fix cost at the source, vendor by vendor",
             "ورشة الموردين — صلّح التكلفة من المنبع، مورّد بمورّد",
             "Atelier fournisseurs — corriger le coût à la source") }}
      </div>
      <div class="text-[11px] mt-0.5" style="color:#1d4ed8">
        {{ L("Only products with real movement (delivered 2026 or on-hand). Four steps per vendor: weights → freight share → purchase costs → submit the retro fix in light batches. Local vendors skip weights & freight.",
             "منتجات عليها حركة فعلية بس (اتسلّمت 2026 أو على المخزون). أربع خطوات لكل مورّد: أوزان ← نصيب الشحن ← تكاليف الشراء ← Submit تصحيح رجعي على دفعات خفيفة. المحلي بيتخطى الوزن والشحن.",
             "Produits avec mouvement réel uniquement. Quatre étapes par fournisseur.") }}
      </div>
    </div>

    <div v-if="loading" class="py-16 text-center text-[12px] text-ink-muted">{{ L("Loading…","جاري التحميل…","Chargement…") }}</div>
    <div v-else-if="err" class="py-16 text-center text-[12px]" style="color:#b91c1c">{{ err }}</div>

    <!-- ======================= VENDOR LIST ======================= -->
    <template v-else-if="!sel">
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div class="bg-white border border-line rounded-[14px] shadow-card px-4 py-3">
          <div class="lab">{{ L("Vendors","الموردين","Fournisseurs") }}</div>
          <div class="big tnum" dir="ltr">{{ d.totals?.vendors || 0 }}</div>
        </div>
        <div class="bg-white border border-line rounded-[14px] shadow-card px-4 py-3">
          <div class="lab">{{ L("Moved items","أصناف متحركة","Articles") }}</div>
          <div class="big tnum" dir="ltr">{{ n(d.totals?.items) }}</div>
        </div>
        <div class="bg-white border border-line rounded-[14px] shadow-card px-4 py-3">
          <div class="lab">{{ L("Units sold 2026","وحدات مبيعة","Unités vendues") }}</div>
          <div class="big tnum" dir="ltr">{{ n(d.totals?.sold) }}</div>
        </div>
        <div class="bg-white border border-line rounded-[14px] shadow-card px-4 py-3">
          <div class="lab">{{ L("Unassigned items","بدون مورّد","Sans fournisseur") }}</div>
          <div class="big tnum" :style="d.unassigned?.items ? 'color:#b45309' : ''" dir="ltr">{{ n(d.unassigned?.items) }}</div>
          <div class="text-[10.5px] text-ink-muted tnum" dir="ltr">{{ n(d.unassigned?.sold) }} {{ L("sold","مبيعة","vendues") }}</div>
        </div>
      </div>

      <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-[11.5px]">
            <thead><tr style="background:#fafaf9">
              <th class="px-3 py-2 text-start th">{{ L("Vendor","المورّد","Fournisseur") }}</th>
              <th class="px-3 py-2 text-center th">{{ L("Channel","القناة","Canal") }}</th>
              <th class="px-3 py-2 text-end th">{{ L("Items","أصناف","Articles") }}</th>
              <th class="px-3 py-2 text-end th">{{ L("Sold","مبيعات","Vendu") }}</th>
              <th class="px-3 py-2 text-end th">{{ L("On hand","مخزون","Stock") }}</th>
              <th class="px-3 py-2 text-center th">{{ L("Weights","أوزان","Poids") }}</th>
              <th class="px-3 py-2 text-center th">{{ L("Costs","تكاليف","Coûts") }}</th>
              <th class="px-3 py-2 text-center th">{{ L("Steps","الخطوات","Étapes") }}</th>
            </tr></thead>
            <tbody>
              <tr v-for="v in d.vendors" :key="v.supplier"
                  class="border-t border-line-hair hover:bg-app-warm/50 cursor-pointer" @click="open(v.supplier)">
                <td class="px-3 py-2 font-bold">{{ v.supplier }}
                  <span v-if="v.local" class="text-[9.5px] font-bold px-1.5 py-0.5 rounded-full ms-1" style="background:#ecfdf5;color:#047857">{{ L("local","محلي","local") }}</span>
                </td>
                <td class="px-3 py-2 text-center">
                  <span class="text-[10px] font-bold px-2 py-0.5 rounded-full" :style="chanStyle(v.channel)">{{ v.channel || "—" }}</span>
                </td>
                <td class="px-3 py-2 text-end tnum" dir="ltr">{{ n(v.items) }}</td>
                <td class="px-3 py-2 text-end tnum font-bold" dir="ltr">{{ n(v.sold) }}</td>
                <td class="px-3 py-2 text-end tnum text-ink-muted" dir="ltr">{{ n(v.oh) }}</td>
                <td class="px-3 py-2 text-center tnum" dir="ltr">
                  <span v-if="v.local" class="text-ink-muted">—</span>
                  <span v-else :style="v.weights_missing ? 'color:#b45309;font-weight:700' : 'color:#047857'">{{ v.weights_ok }}/{{ v.items }}</span>
                </td>
                <td class="px-3 py-2 text-center tnum" dir="ltr">
                  <span :style="v.cost_missing ? 'color:#b45309;font-weight:700' : 'color:#047857'">{{ v.cost_ok }}/{{ v.items }}</span>
                </td>
                <td class="px-3 py-2 text-center">
                  <span class="inline-flex gap-1">
                    <i class="dot" :class="v.state.weights ? 'on' : ''" :title="L('weights','أوزان','poids')"></i>
                    <i class="dot" :class="v.state.freight ? 'on' : ''" :title="L('freight','شحن','fret')"></i>
                    <i class="dot" :class="v.state.costs ? 'on' : ''" :title="L('costs','تكاليف','coûts')"></i>
                    <i class="dot" :class="v.state.submitted >= v.items && v.items ? 'on' : (v.state.submitted ? 'half' : '')" :title="L('submitted','مُرحّل','soumis')"></i>
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>

    <!-- ======================= VENDOR DETAIL ======================= -->
    <template v-else>
      <div class="flex items-center gap-2 flex-wrap">
        <button class="h-[30px] px-3 rounded-[8px] border border-line text-[12px] bg-white" @click="sel=null; det=null">← {{ L("All vendors","كل الموردين","Tous") }}</button>
        <div class="text-[15px] font-extrabold">{{ det?.supplier }}</div>
        <span v-if="det?.local" class="text-[10px] font-bold px-2 py-0.5 rounded-full" style="background:#ecfdf5;color:#047857">{{ L("local — no weights/freight needed","محلي — بدون وزن/شحن","local") }}</span>
        <span v-else class="text-[10px] font-bold px-2 py-0.5 rounded-full" :style="chanStyle(det?.channel)">{{ det?.channel || "?" }}</span>
        <span class="text-[11px] text-ink-muted tnum" dir="ltr">{{ n(det?.summary?.items) }} {{ L("items","صنف","art.") }} · {{ n(det?.summary?.sold) }} {{ L("sold","مبيعة","vendues") }}</span>
      </div>

      <div v-if="dloading" class="py-14 text-center text-[12px] text-ink-muted">{{ L("Loading…","جاري التحميل…","Chargement…") }}</div>
      <template v-else-if="det">
        <!-- step chips -->
        <div class="flex gap-2 flex-wrap">
          <button v-for="s in stepsFor(det)" :key="s.id" class="px-3 h-[34px] rounded-[10px] text-[12px] font-bold border inline-flex items-center gap-2"
                  :class="step===s.id ? 'bg-accent text-white border-accent' : 'bg-white border-line text-ink-muted'"
                  @click="step=s.id">
            <span class="w-5 h-5 rounded-full grid place-items-center text-[10.5px]"
                  :style="s.done ? 'background:#059669;color:#fff' : (step===s.id ? 'background:rgba(255,255,255,.25)' : 'background:#f1f5f9')">{{ s.done ? "✓" : s.n }}</span>
            {{ s.label }}
          </button>
        </div>

        <!-- STEP 1: weights -->
        <div v-if="step==='weights'" class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
          <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2 flex-wrap">
            <div class="text-[12.5px] font-bold">{{ L("Unit weights (kg)","أوزان الوحدة (كجم)","Poids unitaires") }}</div>
            <span class="text-[10.5px] text-ink-muted">{{ det.summary.weights_missing }} {{ L("missing","ناقص","manquants") }}</span>
            <div class="ms-auto flex gap-2">
              <button class="h-[28px] px-3 rounded-[8px] text-[11px] font-bold border border-line bg-white" @click="fillFamily">{{ L("Inherit within family","توريث داخل العائلة","Hériter famille") }}</button>
              <button class="h-[28px] px-3 rounded-[8px] text-[11px] font-bold text-white bg-accent disabled:opacity-50" :disabled="!dirtyW.length || saving" @click="saveWeights">
                {{ saving ? "…" : L("Save "+dirtyW.length,"حفظ "+dirtyW.length,"Enregistrer") }}
              </button>
              <button class="h-[28px] px-3 rounded-[8px] text-[11px] font-bold border" :class="det.state.weights ? 'border-emerald-300 text-emerald-700 bg-emerald-50' : 'border-line bg-white'" @click="markStep('weights')">
                {{ det.state.weights ? L("Reviewed ✓","تمت المراجعة ✓","Revu ✓") : L("Mark reviewed","علّم كمُراجع","Marquer revu") }}
              </button>
            </div>
          </div>
          <div class="overflow-x-auto" style="max-height:480px;overflow-y:auto">
            <table class="w-full text-[11.5px]">
              <thead><tr style="background:#fafaf9;position:sticky;top:0">
                <th class="px-3 py-2 text-start th">SKU</th>
                <th class="px-3 py-2 text-start th">{{ L("Product","المنتج","Produit") }}</th>
                <th class="px-3 py-2 text-end th">{{ L("Sold","مبيعات","Vendu") }}</th>
                <th class="px-3 py-2 text-end th">{{ L("On hand","مخزون","Stock") }}</th>
                <th class="px-3 py-2 text-end th">{{ L("Weight kg","الوزن كجم","Poids kg") }}</th>
              </tr></thead>
              <tbody>
                <tr v-for="it in det.items" :key="it.item_code" class="border-t border-line-hair" :class="!wval(it) ? 'bg-amber-50/40' : ''">
                  <td class="px-3 py-1.5 tnum text-[10.5px]" dir="ltr">{{ it.sku || it.item_code }}</td>
                  <td class="px-3 py-1.5">{{ (it.item_name || '').slice(0, 44) }}</td>
                  <td class="px-3 py-1.5 text-end tnum" dir="ltr">{{ n(it.sold) }}</td>
                  <td class="px-3 py-1.5 text-end tnum text-ink-muted" dir="ltr">{{ n(it.oh) }}</td>
                  <td class="px-3 py-1.5 text-end">
                    <span class="inline-flex items-center gap-1.5">
                      <input type="number" step="0.001" min="0" class="w-[84px] h-[26px] px-2 rounded-[7px] border text-end tnum text-[11.5px]"
                             :class="wDirty[it.item_code] !== undefined ? 'border-accent bg-blue-50/40' : 'border-line'"
                             :value="wval(it)" @input="e => setW(it, e.target.value)"
                             @keyup.enter="saveOne(it)" dir="ltr" />
                      <button v-if="wDirty[it.item_code] !== undefined && parseFloat(wDirty[it.item_code]) > 0"
                              class="h-[26px] px-2 rounded-[7px] text-[10.5px] font-bold text-white bg-accent disabled:opacity-50"
                              :disabled="savingOne === it.item_code" @click="saveOne(it)">
                        {{ savingOne === it.item_code ? "…" : L("Save","حفظ","OK") }}
                      </button>
                      <span v-else-if="justSaved === it.item_code" class="text-[11px] font-bold" style="color:#047857">✓</span>
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- STEP 2: freight -->
        <div v-else-if="step==='freight'" class="bg-white border border-line rounded-[14px] shadow-card px-4 py-4 space-y-3">
          <div class="text-[12.5px] font-bold">{{ L("Vendor's slice of the 770 freight pool","نصيب المورّد من بول شحن 770","Part du pool fret 770") }}</div>
          <div v-if="fr" class="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <div class="rounded-[12px] border border-line px-3 py-2.5"><div class="lab">{{ L("Pool (net, 2026)","البول (صافي)","Pool") }}</div><div class="big tnum" dir="ltr">{{ n(fr.pool_mad) }} <span class="text-[10px]">MAD</span></div></div>
            <div class="rounded-[12px] border border-line px-3 py-2.5"><div class="lab">{{ L("Vendor kg-share","حصة الوزن","Part kg") }}</div><div class="big tnum" dir="ltr">{{ fr.share_pct }}%</div><div class="text-[10px] text-ink-muted tnum" dir="ltr">{{ n(fr.vendor_kg) }} / {{ n(fr.total_kg) }} kg</div></div>
            <div class="rounded-[12px] border px-3 py-2.5" style="border-color:#bfdbfe;background:#eff6ff"><div class="lab" style="color:#1e40af">{{ L("Vendor freight","شحن المورّد","Fret") }}</div><div class="big tnum" style="color:#1e40af" dir="ltr">{{ n(fr.vendor_freight_mad) }} <span class="text-[10px]">MAD</span></div></div>
            <div class="rounded-[12px] border border-line px-3 py-2.5"><div class="lab">{{ L("Items w/o weight","بدون وزن","Sans poids") }}</div><div class="big tnum" :style="fr.items_without_weight ? 'color:#b45309' : 'color:#047857'" dir="ltr">{{ fr.items_without_weight }}</div></div>
          </div>
          <p class="text-[11px] text-ink-muted">{{ L("Allocation is pro-rata by weight from ONE global pool — the sum across all vendors always equals the actual bills. Fix weights first for a fair share.","التوزيع بالوزن من بول واحد — مجموع الموردين دايمًا = الفواتير الفعلية. صلّح الأوزان الأول عشان الحصة تبقى عادلة.","Allocation pro-rata au poids depuis un pool global.") }}</p>
          <button class="h-[30px] px-3 rounded-[8px] text-[11.5px] font-bold border" :class="det.state.freight ? 'border-emerald-300 text-emerald-700 bg-emerald-50' : 'border-line bg-white'" @click="markStep('freight')">
            {{ det.state.freight ? L("Reviewed ✓","تمت المراجعة ✓","Revu ✓") : L("Mark reviewed","علّم كمُراجع","Marquer revu") }}
          </button>
        </div>

        <!-- STEP 3: costs -->
        <div v-else-if="step==='costs'" class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
          <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2">
            <div class="text-[12.5px] font-bold">{{ L("Purchase-cost evidence","دليل تكلفة الشراء","Coûts d'achat") }}</div>
            <span class="text-[10.5px] text-ink-muted">{{ det.summary.cost_missing }} {{ L("without evidence","بدون دليل","sans preuve") }}</span>
            <button class="ms-auto h-[28px] px-3 rounded-[8px] text-[11px] font-bold border" :class="det.state.costs ? 'border-emerald-300 text-emerald-700 bg-emerald-50' : 'border-line bg-white'" @click="markStep('costs')">
              {{ det.state.costs ? L("Reviewed ✓","تمت المراجعة ✓","Revu ✓") : L("Mark reviewed","علّم كمُراجع","Marquer revu") }}
            </button>
          </div>
          <div class="overflow-x-auto" style="max-height:480px;overflow-y:auto">
            <table class="w-full text-[11.5px]">
              <thead><tr style="background:#fafaf9;position:sticky;top:0">
                <th class="px-3 py-2 text-start th">SKU</th>
                <th class="px-3 py-2 text-start th">{{ L("Product","المنتج","Produit") }}</th>
                <th class="px-3 py-2 text-end th">{{ L("Bought","مشترى","Acheté") }}</th>
                <th class="px-3 py-2 text-end th">{{ L("Book rate","سعر الدفتر","Taux livre") }}</th>
                <th class="px-3 py-2 text-end th">{{ L("Evidence cost","التكلفة الموثّقة","Coût prouvé") }}</th>
                <th class="px-3 py-2 text-end th">{{ L("Distortion","التشوّه","Écart") }}</th>
              </tr></thead>
              <tbody>
                <tr v-for="it in det.items" :key="it.item_code" class="border-t border-line-hair" :class="!it.bench ? 'bg-amber-50/40' : ''">
                  <td class="px-3 py-1.5 tnum text-[10.5px]" dir="ltr">{{ it.sku || it.item_code }}</td>
                  <td class="px-3 py-1.5">{{ (it.item_name || '').slice(0, 40) }}</td>
                  <td class="px-3 py-1.5 text-end tnum" dir="ltr">{{ n(it.bought) }} <span class="text-[9px] text-ink-muted">{{ it.last_doc }}</span></td>
                  <td class="px-3 py-1.5 text-end tnum" dir="ltr">{{ it.book_rate ?? "—" }}</td>
                  <td class="px-3 py-1.5 text-end tnum font-bold" dir="ltr">{{ it.bench ?? "—" }}</td>
                  <td class="px-3 py-1.5 text-end tnum" dir="ltr"
                      :style="dist(it) > 30 ? 'color:#b91c1c;font-weight:700' : dist(it) > 10 ? 'color:#b45309' : 'color:#047857'">
                    {{ it.bench && it.book_rate ? dist(it) + "%" : "—" }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- STEP 4: submit -->
        <div v-else-if="step==='submit'" class="space-y-3">
          <div class="bg-white border border-line rounded-[14px] shadow-card px-4 py-4">
            <div class="flex items-center gap-2 flex-wrap">
              <div class="text-[12.5px] font-bold">{{ L("Submit retro correction","ترحيل التصحيح الرجعي","Soumettre la correction") }}</div>
              <span class="text-[10.5px] text-ink-muted tnum" dir="ltr">{{ det.state.submitted.length }}/{{ det.summary.items }} {{ L("submitted","مُرحّل","soumis") }}</span>
              <button class="ms-auto h-[30px] px-3 rounded-[8px] text-[11.5px] font-bold border border-line bg-white" :disabled="pvLoading" @click="loadPreview">
                {{ pvLoading ? "…" : L("Dry-run preview","معاينة بدون ترحيل","Aperçu à blanc") }}
              </button>
            </div>
            <div v-if="pv" class="grid grid-cols-3 gap-3 mt-3">
              <div class="rounded-[12px] border px-3 py-2.5" style="border-color:#a7f3d0;background:#ecfdf5"><div class="lab" style="color:#047857">{{ L("Ready (retro OK)","جاهز (رترو سليم)","Prêt") }}</div><div class="big tnum" style="color:#047857" dir="ltr">{{ pv.ready }}</div></div>
              <div class="rounded-[12px] border px-3 py-2.5" style="border-color:#fde68a;background:#fffbeb"><div class="lab" style="color:#b45309">{{ L("Anchor = today","الأنكور = النهاردة","Ancre = auj.") }}</div><div class="big tnum" style="color:#b45309" dir="ltr">{{ pv.anchor_today }}</div></div>
              <div class="rounded-[12px] border px-3 py-2.5" style="border-color:#fecaca;background:#fef2f2"><div class="lab" style="color:#b91c1c">{{ L("No cost evidence","بدون دليل تكلفة","Sans coût") }}</div><div class="big tnum" style="color:#b91c1c" dir="ltr">{{ pv.no_cost }}</div></div>
            </div>
            <div v-if="pv" class="mt-3 flex items-center gap-2 flex-wrap">
              <button class="h-[34px] px-4 rounded-[9px] text-[12px] font-bold text-white bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50"
                      :disabled="submitting || !readyQueue.length" @click="runBatch">
                {{ submitting ? L("Posting batch…","جاري ترحيل الدفعة…","Envoi…")
                  : L("Submit next batch ("+Math.min(15, readyQueue.length)+" of "+readyQueue.length+")","رحّل الدفعة الجاية ("+Math.min(15, readyQueue.length)+" من "+readyQueue.length+")","Soumettre le lot") }}
              </button>
              <span class="text-[10.5px] text-ink-muted">{{ L("Light batches (≤15 items) — gated, audited, reversible; oldest anchors heal the full year.","دفعات خفيفة (≤15 صنف) — gated ومسجّلة وقابلة للعكس.","Lots légers, audités, réversibles.") }}</span>
            </div>
            <div v-if="lastResults.length" class="mt-3 rounded-[10px] border border-line overflow-hidden">
              <div class="px-3 py-2 text-[11px] font-bold" style="background:#fafaf9">{{ L("Last batch results","نتيجة آخر دفعة","Derniers résultats") }}</div>
              <div class="max-h-[180px] overflow-y-auto">
                <div v-for="r in lastResults" :key="r.item_code" class="px-3 py-1.5 text-[10.5px] border-t border-line-hair flex justify-between gap-2">
                  <span class="tnum" dir="ltr">{{ r.item_code }}</span>
                  <span :style="String(r.result).startsWith('error') ? 'color:#b91c1c' : String(r.result).startsWith('skipped') ? 'color:#b45309' : 'color:#047857'">{{ r.result }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from "vue";
import { useI18n } from "vue-i18n";
import api from "@/services/api";
import { useUi } from "@/composables/useUi";

const { locale } = useI18n();
const { entityId } = useUi();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const n = (x) => (x === null || x === undefined ? "—" : Math.round(x).toLocaleString("en-US"));

const loading = ref(true); const err = ref("");
const d = ref({ vendors: [], totals: {}, unassigned: {} });
const sel = ref(null); const det = ref(null); const dloading = ref(false);
const step = ref("weights");
const wDirty = ref({}); const saving = ref(false);
const fr = ref(null);
const pv = ref(null); const pvLoading = ref(false);
const submitting = ref(false); const lastResults = ref([]);

function chanStyle(c) {
  const m = { sea: "background:#e0f2fe;color:#0369a1", air: "background:#fef3c7;color:#b45309",
              china: "background:#fce7f3;color:#be185d", local: "background:#ecfdf5;color:#047857" };
  return m[c] || "background:#f1f5f9;color:#64748b";
}
function stepsFor(dv) {
  const s = [];
  if (!dv.local) {
    s.push({ id: "weights", n: 1, label: L("Weights","الأوزان","Poids"), done: !!dv.state.weights });
    s.push({ id: "freight", n: 2, label: L("Freight","الشحن","Fret"), done: !!dv.state.freight });
  }
  s.push({ id: "costs", n: s.length + 1, label: L("Costs","التكاليف","Coûts"), done: !!dv.state.costs });
  s.push({ id: "submit", n: s.length + 1, label: "Submit", done: dv.state.submitted.length >= dv.summary.items && dv.summary.items > 0 });
  return s;
}
function wval(it) {
  return wDirty.value[it.item_code] !== undefined ? wDirty.value[it.item_code] : (it.weight_kg || "");
}
function setW(it, v) { wDirty.value = { ...wDirty.value, [it.item_code]: v }; }
const dirtyW = computed(() =>
  Object.entries(wDirty.value)
    .filter(([, v]) => parseFloat(v) > 0)
    .map(([item_code, weight_kg]) => ({ item_code, weight_kg: parseFloat(weight_kg) })));
function dist(it) {
  if (!it.bench || !it.book_rate) return 0;
  return Math.round(100 * Math.abs(it.book_rate - it.bench) / it.bench);
}
// family inheritance: the base segment of the SKU shares one weight
function skuBase(s) { return (s || "").split("-")[0].trim().toLowerCase(); }
function fillFamily() {
  const byBase = {};
  for (const it of det.value.items) {
    const w = parseFloat(wval(it));
    const b = skuBase(it.sku);
    if (b && w > 0 && !byBase[b]) byBase[b] = w;
  }
  const patch = { ...wDirty.value };
  let filled = 0;
  for (const it of det.value.items) {
    if (parseFloat(wval(it)) > 0) continue;
    const b = skuBase(it.sku);
    if (b && byBase[b]) { patch[it.item_code] = byBase[b]; filled++; }
  }
  wDirty.value = patch;
}
const readyQueue = computed(() => {
  if (!pv.value) return [];
  const done = new Set(det.value?.state?.submitted || []);
  return pv.value.rows.filter(r => r.rate && r.retro_ok && !done.has(r.item_code)).map(r => r.item_code);
});

async function load() {
  loading.value = true; err.value = "";
  try { d.value = await api.call("accounting_portal.api.vendor_workbench.list_vendors", {}, { fresh: true }); }
  catch (e) { err.value = (e && e.message) || String(e); }
  finally { loading.value = false; }
}
async function open(sup) {
  sel.value = sup; det.value = null; dloading.value = true;
  wDirty.value = {}; fr.value = null; pv.value = null; lastResults.value = [];
  try {
    det.value = await api.call("accounting_portal.api.vendor_workbench.vendor_detail", { supplier: sup }, { fresh: true });
    step.value = det.value.local ? "costs" : "weights";
    if (!det.value.local) {
      fr.value = await api.call("accounting_portal.api.vendor_workbench.freight_summary", { supplier: sup }, { fresh: true });
    }
  } catch (e) { err.value = (e && e.message) || String(e); }
  finally { dloading.value = false; }
}
async function saveWeights() {
  saving.value = true;
  try {
    await api.call("accounting_portal.api.vendor_workbench.save_weights",
      { supplier: sel.value, rows: JSON.stringify(dirtyW.value) });
    await open(sel.value);
  } catch (e) { alert((e && e.message) || e); }
  finally { saving.value = false; }
}
const savingOne = ref(null); const justSaved = ref(null);
async function saveOne(it) {
  const w = parseFloat(wDirty.value[it.item_code]);
  if (!(w > 0)) return;
  savingOne.value = it.item_code;
  try {
    await api.call("accounting_portal.api.vendor_workbench.save_weights",
      { supplier: sel.value, rows: JSON.stringify([{ item_code: it.item_code, weight_kg: w }]) });
    it.weight_kg = w;                                  // reflect in-place, no full reload
    const d2 = { ...wDirty.value }; delete d2[it.item_code]; wDirty.value = d2;
    det.value.summary.weights_ok = det.value.items.filter(x => x.weight_kg > 0).length;
    det.value.summary.weights_missing = det.value.items.length - det.value.summary.weights_ok;
    justSaved.value = it.item_code;
    setTimeout(() => { if (justSaved.value === it.item_code) justSaved.value = null; }, 2000);
  } catch (e) { alert((e && e.message) || e); }
  finally { savingOne.value = null; }
}
async function markStep(s) {
  const cur = det.value.state[s] ? 0 : 1;
  await api.call("accounting_portal.api.vendor_workbench.set_step", { supplier: sel.value, step: s, done: cur });
  det.value.state[s] = cur;
}
async function loadPreview() {
  pvLoading.value = true;
  try {
    const items = det.value.items.map(i => i.item_code);
    pv.value = await api.call("accounting_portal.api.vendor_workbench.submit_preview",
      { supplier: sel.value, items: JSON.stringify(items) }, { fresh: true });
  } catch (e) { alert((e && e.message) || e); }
  finally { pvLoading.value = false; }
}
async function runBatch() {
  const batch = readyQueue.value.slice(0, 15);
  if (!batch.length) return;
  submitting.value = true;
  try {
    const r = await api.call("accounting_portal.api.vendor_workbench.submit_batch",
      { supplier: sel.value, items: JSON.stringify(batch) });
    lastResults.value = r.results || [];
    det.value.state.submitted = [...new Set([...(det.value.state.submitted || []), ...batch])];
  } catch (e) { alert((e && e.message) || e); }
  finally { submitting.value = false; }
}
onMounted(load);
watch(entityId, load);
</script>

<style scoped>
.lab{font-size:10px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#9a8f86}
.big{font-size:18px;font-weight:800}
.th{font-size:10px;font-weight:700;color:#9a8f86}
.tnum{font-variant-numeric:tabular-nums}
.dot{width:9px;height:9px;border-radius:99px;background:#e2e8f0;display:inline-block}
.dot.on{background:#059669}
.dot.half{background:#f59e0b}
</style>
