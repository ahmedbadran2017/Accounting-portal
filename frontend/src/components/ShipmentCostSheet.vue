<template>
  <!-- The PR costing file (Cost Trace). Order per the human workflow:
       ① verify product costs  ② landed (air: confirm rate/kg · sea: bills)
       ③ summary  ④ Submit — applies items whose EVERY shipment is complete.
       Retroactive month restatement stays a separate step (monthly true-up). -->
  <div v-if="s" class="space-y-3.5">
    <div class="bg-white rounded-card border border-line shadow-card p-4">
      <div class="flex items-center gap-3 flex-wrap">
        <span class="text-[15px] font-bold font-mono" dir="ltr">{{ s.pr }}</span>
        <span class="text-[12px] text-ink-muted">{{ s.dt }} · {{ s.supplier }}</span>
        <span class="text-[12px]">{{ s.channel === "air" ? "🛫" : "🚢" }} {{ fmt0(s.kg) }}kg · {{ fmt0(s.qty) }} {{ L("units","قطعة","unités") }}</span>
        <span class="flex-1"></span>
        <span class="text-[11px] tnum text-ink-muted">① {{ verifiedCount }}/{{ s.lines.length }} · ② {{ freightReady ? "✓" : "…" }}</span>
      </div>
    </div>

    <!-- ① product costs -->
    <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
      <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2 flex-wrap">
        <span class="text-[12px] font-bold">① {{ L("Product costs — verify each line against the supplier invoice","تكلفة البضاعة — اتحققوا من كل سطر مع فاتورة المورد","Coûts produits") }}</span>
        <span class="text-[11px] text-ink-muted flex-1">{{ verifiedCount }}/{{ s.lines.length }} {{ L("verified","متحقق","vérifié") }}</span>
        <button v-if="canWrite" class="h-[26px] px-2.5 rounded-[7px] text-[10.5px] font-bold border border-line text-ink-2 hover:bg-app-warm"
                @click="useSuggestedAll">{{ L("Use suggested for empty lines","استخدام المقترح للفاضي","Suggestions") }}</button>
      </div>
      <div class="max-h-[420px] overflow-y-auto">
        <table class="w-full text-[11.5px]">
          <thead><tr style="background:#fafaf9" class="sticky top-0 z-[1]">
            <th class="px-3 py-1.5 text-start text-[10px] font-bold text-ink-muted">{{ L("Item","الصنف","Article") }}</th>
            <th class="px-3 py-1.5 text-end text-[10px] font-bold text-ink-muted">{{ L("Qty","كمية","Qté") }}</th>
            <th class="px-3 py-1.5 text-end text-[10px] font-bold text-ink-muted">{{ L("Booked","المسجّل","Comptab.") }}</th>
            <th class="px-3 py-1.5 text-end text-[10px] font-bold text-ink-muted">{{ L("Suggested","المقترح","Suggéré") }}</th>
            <th class="px-3 py-1.5 text-end text-[10px] font-bold text-ink-muted w-[110px]">{{ L("Verified ✎","المعتمد ✎","Vérifié ✎") }}</th>
            <th class="px-3 py-1.5 text-end text-[10px] font-bold text-ink-muted">+ {{ L("freight","شحن","fret") }}</th>
            <th class="px-3 py-1.5 text-end text-[10px] font-bold text-ink-muted">{{ L("Full","الكاملة","Total") }}</th>
          </tr></thead>
          <tbody>
            <tr v-for="l in s.lines" :key="l.item_code" class="border-t border-line-hair" :style="l.fixed ? 'background:#f0fdf4' : ''">
              <td class="px-3 py-1.5">
                <span class="font-mono text-[10.5px]" dir="ltr">{{ l.item_code }}</span>
                <span v-if="l.fixed" class="text-[9.5px] font-bold ms-1" style="color:#047857">✓ {{ L("applied","مطبَّق","appliqué") }}</span>
                <!-- cross-shipment badge: the applied cost is weighted over ALL its shipments -->
                <span v-if="l.other_prs?.length" class="text-[9.5px] font-bold px-1.5 py-0.5 rounded-full ms-1 cursor-help"
                      :style="(l.wait_freight?.length || l.wait_verify?.length) ? 'background:#fffbeb;color:#b45309' : 'background:#eef2ff;color:#4338ca'"
                      :title="L('This product also came on: ', 'المنتج ده جه كمان في: ', 'Aussi sur : ') + l.other_prs.join(', ')
                              + (l.wait_freight?.length ? ' · ' + L('freight missing: ','ناقص شحن: ','fret manquant : ') + l.wait_freight.join(', ') : '')
                              + (l.wait_verify?.length ? ' · ' + L('not verified in: ','مش متحقق في: ','non vérifié : ') + l.wait_verify.join(', ') : '')
                              + ' — ' + L('final cost = weighted average across all of them','التكلفة النهائية = متوسط مرجّح بينهم كلهم','coût final = moyenne pondérée')">
                  ×{{ l.other_prs.length + 1 }} {{ L("shipments","شحنات","exp.") }}{{ (l.wait_freight?.length || l.wait_verify?.length) ? " ⏳" : "" }}
                </span>
                <div class="text-[10px] text-ink-muted truncate max-w-[260px]">{{ l.sku || l.item_name }}</div>
              </td>
              <td class="px-3 py-1.5 text-end tnum">{{ fmt0(l.qty) }}</td>
              <td class="px-3 py-1.5 text-end tnum text-ink-muted">{{ l.book_rate }}</td>
              <td class="px-3 py-1.5 text-end tnum">
                <button v-if="l.suggested" class="hover:underline decoration-dotted" :title="l.source" @click="edits[l.item_code] = l.suggested">{{ l.suggested }}</button>
                <span v-else class="text-ink-3">—</span>
              </td>
              <td class="px-2 py-1 text-end">
                <input type="number" step="0.01" min="0" v-model.number="edits[l.item_code]" :disabled="!canWrite"
                       class="w-[92px] h-[26px] px-1.5 text-end tnum text-[11.5px] border rounded-[6px] outline-none focus:border-accent"
                       :style="edits[l.item_code] > 0 ? 'border-color:#a7f3d0;background:#f0fdf4' : 'border-color:#e7e5e4'" />
              </td>
              <td class="px-3 py-1.5 text-end tnum text-ink-muted">{{ l.landed_unit }}</td>
              <td class="px-3 py-1.5 text-end tnum font-semibold">{{ edits[l.item_code] > 0 ? (Number(edits[l.item_code]) + l.landed_unit).toFixed(2) : "—" }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="px-4 py-3 border-t border-line-hair flex items-center gap-2 flex-wrap">
        <input v-model="note" :placeholder="L('Note (which invoice was checked…)','ملاحظة (اتراجعت على أنهي فاتورة…)','Note…')"
               class="h-[30px] px-2.5 text-[11.5px] border border-line rounded-[8px] outline-none flex-1 min-w-[200px]" />
        <span class="text-[11px] text-ink-muted" v-if="s.sheet.on" dir="ltr">💾 {{ s.sheet.by }} · {{ s.sheet.on }}</span>
        <button v-if="canWrite" class="h-[30px] px-3.5 rounded-[8px] text-[11.5px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand disabled:opacity-50"
                :disabled="busy" @click="saveSheet">{{ L("Save draft","حفظ المسودة","Enregistrer") }}</button>
      </div>
    </div>

    <!-- ② landed cost -->
    <div class="bg-white rounded-card border border-line shadow-card p-4">
      <div class="flex items-center gap-2 flex-wrap mb-2">
        <span class="text-[12px] font-bold">② {{ L("Landed cost of this shipment","تكلفة شحن الشحنة","Coût du fret") }}</span>
        <FreightChip :source="s.freight.source" />
        <span class="text-[12px] tnum flex-1 text-end"><b>{{ fmt0(s.freight.landed) }}</b> <span class="text-[10.5px] text-ink-muted" dir="ltr">@{{ s.freight.rate_kg }}/kg</span></span>
      </div>

      <!-- AIR: confirm the flat rate -->
      <div v-if="s.channel === 'air'" class="flex items-center gap-2 flex-wrap">
        <span class="text-[11.5px]">🛫 {{ L("Door-to-door rate","سعر الكيلو door-to-door","Tarif au kg") }}</span>
        <input type="number" step="1" min="0" v-model.number="rateEdit" :disabled="!canWrite || s.frozen"
               class="w-[80px] h-[28px] px-2 text-end tnum text-[12px] border rounded-[7px] outline-none focus:border-accent"
               :style="s.freight.confirmed_rate ? 'border-color:#a7f3d0;background:#f0fdf4' : 'border-color:#e7e5e4'" />
        <span class="text-[11px] text-ink-muted">MAD/kg × {{ fmt0(s.kg) }}kg = <b class="tnum">{{ fmt0((rateEdit || 0) * s.kg) }}</b></span>
        <span v-if="s.freight.band_rate && !s.freight.confirmed_rate" class="text-[10.5px] text-amber-700">{{ L("prefilled from the tariff band — confirm it","متعبّي من التعريفة — أكّدوه","préremp. du barème") }}</span>
        <button v-if="canWrite && !s.frozen" class="h-[26px] px-2.5 rounded-[7px] text-[10.5px] font-bold text-white bg-brand hover:bg-brand-dark disabled:opacity-50"
                :disabled="busy || !(rateEdit > 0)" @click="confirmRate">✓ {{ L("Confirm rate","اعتماد السعر","Confirmer") }}</button>
        <button v-if="canWrite && !s.frozen && s.freight.confirmed_rate" class="h-[28px] px-2 rounded-[7px] text-[11px] border border-line text-ink-3 hover:bg-app-warm"
                :disabled="busy" @click="clearRate">✕</button>
      </div>

      <!-- SEA (or air with itemized bills): attach the actual bills -->
      <div :class="s.channel === 'air' ? 'mt-2.5 pt-2.5 border-t border-line-hair' : ''">
        <div class="text-[11px] font-bold text-ink-2 mb-1.5">
          {{ s.channel === 'sea' ? "🚢 " + L("The container's bills (freight / customs / transport / clearance)","فواتير الكونتينر (شحن / جمارك / نقل / تخليص)","Factures du conteneur") : "🧾 " + L("Or itemized bills instead of the rate","أو فواتير مفصلة بدل السعر","Ou factures détaillées") }}
        </div>
        <div class="flex gap-1.5 flex-wrap mb-1.5">
          <span v-for="b in attachedBills" :key="b.voucher" class="inline-flex items-center gap-1.5 text-[11px] border rounded-[8px] px-2 py-1" style="background:#f0fdf4;border-color:#bbf7d0">
            <span class="font-mono text-[10.5px]" dir="ltr">{{ b.voucher }}</span>
            <span class="tnum font-semibold">{{ fmt0(shareOf(b)) }}</span>
            <span v-if="b.n_prs > 1" class="text-[10px] text-ink-muted">÷{{ b.n_prs }}</span>
            <button v-if="canWrite && !s.frozen" class="text-sale" @click="toggleBill(b, false)">✕</button>
          </span>
          <span v-if="!attachedBills.length" class="text-[11px] text-ink-muted">—</span>
        </div>
        <details class="text-[11.5px]">
          <summary class="cursor-pointer text-accent-dark font-bold text-[11.5px]">{{ L("+ Attach a bill","+ إرفاق فاتورة","+ Joindre") }} ({{ shownBills.length }}/{{ availableBills.length }})</summary>
          <input v-model="billSearch" :placeholder="L('search bill / supplier / amount…','بحث فاتورة / مورّد / مبلغ…','rechercher…')"
                 class="mt-2 h-[26px] px-2.5 text-[11px] border border-line rounded-[7px] outline-none focus:border-accent w-[230px]" />
          <div class="mt-2 border border-line rounded-[8px] max-h-[200px] overflow-y-auto">
            <div v-for="b in shownBills" :key="b.voucher" class="flex items-center gap-2 px-3 py-1.5 border-b border-line-hair last:border-0 hover:bg-app-warm">
              <span class="font-mono text-[10.5px]" dir="ltr">{{ b.voucher }}</span>
              <span class="text-[10px] text-ink-muted">{{ b.dt }}</span>
              <span v-if="b.ref_match" class="text-[9.5px] font-bold px-1.5 py-0.5 rounded-full whitespace-nowrap" style="background:#ecfdf5;color:#047857"
                    :title="L('The bill mentions this shipment in its reference/remarks','الفاتورة ذاكرة الشحنة دي في مرجعها/بيانها','La facture référence cette expédition')">⭐ {{ L("ref match","مرجع مطابق","réf.") }}</span>
              <span v-else-if="b.days < 999" class="text-[10px] text-ink-3 tnum whitespace-nowrap" dir="ltr"
                    :title="L('days between bill and receipt dates','فرق الأيام بين تاريخ الفاتورة والاستلام','écart en jours')">±{{ b.days }}{{ L("d","ي","j") }}</span>
              <span class="truncate flex-1 text-[11px]">{{ b.supplier || b.account }}</span>
              <span class="tnum font-semibold">{{ fmt0(b.amount) }}</span>
              <span v-if="b.n_prs" class="text-[10px] text-ink-muted">{{ L("covers","بتغطي","couvre") }} {{ b.n_prs }}</span>
              <button v-if="canWrite && !s.frozen" class="text-[10.5px] font-bold px-2 py-0.5 rounded-[6px] border border-line hover:bg-white" @click="toggleBill(b, true)">{{ L("Attach","إرفاق","Joindre") }}</button>
            </div>
          </div>
        </details>
        <div class="text-[10px] text-ink-3 mt-1">{{ L("Missing bills? Enter them from Purchases → New bill on the freight accounts — they appear here.","فيه فواتير ناقصة؟ دخّلوها من المشتريات (فاتورة جديدة) على حسابات الشحن — هتظهر هنا.","Saisir les factures manquantes dans Achats.") }}</div>
      </div>
    </div>

    <!-- ③ summary -->
    <div class="bg-white rounded-card border border-line shadow-card p-4">
      <div class="text-[12px] font-bold mb-2">③ {{ L("Summary","الملخص","Résumé") }}</div>
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <div class="border border-line rounded-[10px] px-3 py-2"><div class="text-[10px] text-ink-muted">{{ L("Goods (verified)","البضاعة (المعتمد)","Marchandise") }}</div><div class="text-[14px] font-bold tnum">{{ fmt0(goodsValue) }}</div><div class="text-[10px] text-ink-3">{{ verifiedCount }}/{{ s.lines.length }} {{ L("lines","سطر","lignes") }}</div></div>
        <div class="border border-line rounded-[10px] px-3 py-2"><div class="text-[10px] text-ink-muted">{{ L("Freight","الشحن","Fret") }}</div><div class="text-[14px] font-bold tnum">{{ fmt0(s.freight.landed) }}</div></div>
        <div class="border border-line rounded-[10px] px-3 py-2"><div class="text-[10px] text-ink-muted">{{ L("Shipment total","إجمالي الشحنة","Total") }}</div><div class="text-[14px] font-bold tnum">{{ fmt0(goodsValue + (s.freight.landed || 0)) }}</div></div>
        <div class="border rounded-[10px] px-3 py-2" :style="isComplete ? 'border-color:#a7f3d0;background:#ecfdf5' : 'border-color:#fde68a;background:#fffbeb'"><div class="text-[10px] text-ink-muted">{{ L("Avg full cost / unit","متوسط التكلفة الكاملة/وحدة","Coût moyen/unité") }}</div><div class="text-[14px] font-bold tnum">{{ s.qty > 0 ? ((goodsValue + (s.freight.landed || 0)) / s.qty).toFixed(2) : "—" }}</div><div class="text-[10px] font-bold" :style="isComplete ? 'color:#047857' : 'color:#b45309'">{{ isComplete ? "✅ " + L("complete","مكتملة","complète") : L("finish ① + ②","كمّلوا ① و②","finir ① + ②") }}</div></div>
      </div>
    </div>

    <!-- ④ submit -->
    <div class="bg-white rounded-card border shadow-card p-4" :style="isComplete ? 'border-color:#a7f3d0' : 'border-color:#e7e5e4'">
      <div class="flex items-center gap-3 flex-wrap">
        <div class="flex-1 min-w-[260px]">
          <div class="text-[12px] font-bold">④ {{ L("Submit — apply this shipment's costs","الاعتماد النهائي — تطبيق تكلفة الشحنة","Soumettre") }}</div>
          <div class="text-[11px] text-ink-muted mt-0.5">
            <span :title="L('An item applies only when ALL its shipments are complete — its cost is the weighted average across them. Retroactive monthly restatement is a separate step (true-up card).','الصنف بيتطبق لما كل شحناته تكون مكتملة — تكلفته متوسط مرجّح بينهم. الأثر الرجعي الشهري خطوة منفصلة (كارت الـtrue-up).','Un article part quand toutes ses expéditions sont complètes ; le rétroactif est séparé.')">
              {{ L("Updates current stock — every next sale leaves at the right cost. Undoable in Activity.","بيحدّث المخزون الحالي — كل بيع جاي يخرج بالتكلفة الصح. قابل للعكس من Activity.","Met à jour le stock actuel ; réversible.") }}</span>
          </div>
        </div>
        <button v-if="canWrite" class="h-[30px] px-3 rounded-[8px] text-[11.5px] font-bold border border-line text-ink-2 hover:bg-app-warm disabled:opacity-50"
                :disabled="busy" @click="previewSubmit">{{ L("Preview","معاينة","Aperçu") }}</button>
        <button v-if="canWrite" class="h-[30px] px-3.5 rounded-[8px] text-[11.5px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand disabled:opacity-50"
                :disabled="busy || !subPrev || !readyCount"
                :title="!subPrev ? L('Loading preview…','بيحمّل المعاينة…','Aperçu…') : !readyCount ? L('Nothing ready — see the preview below','مفيش جاهز — شوف المعاينة تحت','Rien de prêt') : ''"
                @click="runSubmit">{{ L("Submit","اعتماد","Soumettre") }} ({{ readyCount }})</button>
      </div>
      <div v-if="subPrev" class="mt-2.5 border-t border-line-hair pt-2 text-[11px] space-y-1">
        <template v-if="subPrev.dry_run">
          <div><b style="color:#047857">{{ subPrev.counts.ready || 0 }} {{ L("ready","جاهز","prêts") }}</b>
            · <span style="color:#b45309">{{ subPrev.counts.waiting_freight || 0 }} {{ L("waiting other shipments' freight","مستني شحن شحنات تانية","attendent fret") }}</span>
            · <span style="color:#b45309">{{ subPrev.counts.waiting_verify || 0 }} {{ L("waiting verification elsewhere","مستني تحقق في شحنة تانية","attendent vérif.") }}</span>
            · {{ subPrev.counts.already_applied || 0 }} {{ L("already applied","متطبق قبل كدا","déjà appliqués") }}</div>
          <div v-for="r in waitingRows.slice(0, 5)" :key="r.item_code" class="text-ink-muted">
            <span class="font-mono text-[10px]" dir="ltr">{{ r.item_code }}</span> →
            {{ r.status === "waiting_freight" ? L("freight of","شحن","fret de") : L("verify in","تحقق في","vérif. dans") }}
            <span class="font-mono text-[10px]" dir="ltr">{{ (r.prs || []).join(", ") }}</span>
          </div>
          <div v-if="waitingRows.length > 5" class="text-ink-3">+{{ waitingRows.length - 5 }}</div>
        </template>
        <template v-else>
          <b style="color:#047857">✅ {{ subPrev.posted.length }} {{ L("applied — undoable in Activity","اتطبّقوا — قابلين للعكس من Activity","appliqués") }}</b>
          <span v-if="subPrev.skipped.length" class="ms-2" style="color:#b45309">⚠ {{ subPrev.skipped.length }} {{ L("skipped","اتعدّوا","ignorés") }} — {{ subPrev.skipped[0]?.reason }}</span>
        </template>
      </div>
    </div>
  </div>
  <div v-else class="text-[12px] text-ink-muted py-6 text-center">{{ L("Loading shipment…","بيحمّل الشحنة…","Chargement…") }}</div>
</template>

<script setup>
import { ref, reactive, computed, watch } from "vue";
import { useI18n } from "vue-i18n";
import api from "@/services/api";
import { useAuth } from "@/composables/useAuth";
import { useToast } from "@/composables/useToast";
import FreightChip from "@/components/FreightChip.vue";

const props = defineProps({ pr: { type: String, required: true }, year: { type: [Number, String], default: null } });
const emit = defineEmits(["saved"]);
const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt0 = (n) => Number(n || 0).toLocaleString("en-US", { maximumFractionDigits: 0 });
const { can } = useAuth();
const canWrite = computed(() => can("post_entries"));
const toast = useToast();

const SC = "accounting_portal.api.shipment_costing";
const LP = "accounting_portal.api.landed_prep";
const s = ref(null);
const edits = reactive({});
const note = ref("");
const rateEdit = ref(null);
const busy = ref(false);
const subPrev = ref(null);

const freightReady = computed(() => ["bills", "rate"].includes(s.value?.freight?.source));
const verifiedCount = computed(() => (s.value?.lines || []).filter((l) => edits[l.item_code] > 0).length);
const goodsValue = computed(() => {
  let t = 0;
  for (const l of s.value?.lines || []) if (edits[l.item_code] > 0) t += l.qty * Number(edits[l.item_code]);
  return Math.round(t);
});
const isComplete = computed(() =>
  s.value && verifiedCount.value >= s.value.lines.length && s.value.lines.length > 0 && freightReady.value);
const attachedBills = computed(() => (s.value?.picker || []).filter((b) => b.attached));
const availableBills = computed(() => (s.value?.picker || []).filter((b) => !b.attached));
const billSearch = ref("");
const shownBills = computed(() => {
  const q = billSearch.value.trim().toLowerCase();
  if (!q) return availableBills.value;
  return availableBills.value.filter((b) =>
    (b.voucher + " " + (b.supplier || "") + " " + (b.account || "") + " " + b.amount).toLowerCase().includes(q));
});
const shareOf = (b) => {
  const hit = (s.value?.freight?.bills || []).find((x) => x.voucher === b.voucher);
  return hit ? hit.share : 0;
};
const readyCount = computed(() =>
  subPrev.value?.dry_run ? (subPrev.value.counts.ready || 0) : 0);
const waitingRows = computed(() =>
  (subPrev.value?.rows || []).filter((r) => r.status.startsWith("waiting")));

async function load() {
  s.value = null;
  subPrev.value = null;
  try {
    const r = await api.call(`${SC}.get_sheet`, { pr: props.pr, year: props.year || undefined }, { fresh: true });
    Object.keys(edits).forEach((k) => delete edits[k]);
    for (const l of r.lines) if (l.verified > 0) edits[l.item_code] = l.verified;
    note.value = r.sheet?.note || "";
    rateEdit.value = r.freight.confirmed_rate || r.freight.band_rate || null;
    s.value = r;
    previewSubmit();   // pre-load the ④ preview so Submit is never a dead button
  } catch (e) { toast.error(e.message || "Failed"); }
}
watch(() => props.pr, load, { immediate: true });

function useSuggestedAll() {
  for (const l of s.value.lines)
    if (!(edits[l.item_code] > 0) && l.suggested > 0) edits[l.item_code] = l.suggested;
}

async function saveSheet() {
  busy.value = true;
  try {
    const costs = {};
    for (const l of s.value.lines) if (edits[l.item_code] > 0) costs[l.item_code] = edits[l.item_code];
    await api.call(`${SC}.save_sheet`, { pr: s.value.pr, costs: JSON.stringify(costs), note: note.value });
    toast.success(L("Draft saved", "المسودة اتحفظت", "Brouillon enregistré"));
    emit("saved");
    await load();
  } catch (e) { toast.error(e.message || "Failed"); }
  finally { busy.value = false; }
}

async function confirmRate() {
  busy.value = true;
  try {
    await api.call(`${LP}.set_pr_rate`, { pr: s.value.pr, rate: rateEdit.value, year: props.year || undefined });
    toast.success(L("Rate confirmed", "السعر اتعتمد", "Tarif confirmé"));
    emit("saved");
    await load();
  } catch (e) { toast.error(e.message || "Failed"); }
  finally { busy.value = false; }
}
async function clearRate() {
  busy.value = true;
  try {
    await api.call(`${LP}.set_pr_rate`, { pr: s.value.pr, rate: 0, year: props.year || undefined });
    emit("saved");
    await load();
  } catch (e) { toast.error(e.message || "Failed"); }
  finally { busy.value = false; }
}

async function toggleBill(b, attach) {
  busy.value = true;
  try {
    await api.call(`${SC}.attach_bill`, { pr: s.value.pr, voucher: b.voucher, attached: attach ? 1 : 0, year: props.year || undefined });
    emit("saved");
    await load();
  } catch (e) { toast.error(e.message || "Failed"); }
  finally { busy.value = false; }
}

async function previewSubmit() {
  busy.value = true;
  try { subPrev.value = await api.call(`${SC}.apply_shipment`, { pr: s.value.pr, year: props.year || undefined, dry_run: 1 }, { fresh: true }); }
  catch (e) { toast.error(e.message || "Failed"); }
  finally { busy.value = false; }
}
async function runSubmit() {
  if (!window.confirm(L(
    `Apply ${readyCount.value} item(s) at their full verified cost? Each posts a today-dated revaluation — undoable in Activity.`,
    `تطبيق ${readyCount.value} صنف بتكلفتهم الكاملة المعتمدة؟ كل صنف قيد إعادة تقييم بتاريخ النهاردة — قابل للعكس من Activity.`,
    "Appliquer ?"))) return;
  busy.value = true;
  try {
    subPrev.value = await api.call(`${SC}.apply_shipment`, { pr: s.value.pr, year: props.year || undefined, dry_run: 0 });
    emit("saved");
  } catch (e) { toast.error(e.message || "Failed"); }
  finally { busy.value = false; }
}
</script>
