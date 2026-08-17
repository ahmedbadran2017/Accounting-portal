<template>
  <!-- The PR cost-verification file — lives in Cost Trace. Freight is
       assembled first in Purchases → Shipments; this sheet opens AFTER the
       landed is in (source=bills) and the team verifies the product cost of
       every line against the supplier invoice, then saves the draft. -->
  <div v-if="s" class="space-y-3">
    <div class="bg-white rounded-card border border-line shadow-card p-4">
      <div class="flex items-center gap-3 flex-wrap">
        <span class="text-[15px] font-bold font-mono" dir="ltr">{{ s.pr }}</span>
        <span class="text-[12px] text-ink-muted">{{ s.dt }} · {{ s.supplier }}</span>
        <span class="text-[12px]">{{ s.channel === "air" ? "🛫" : "🚢" }} {{ fmt0(s.kg) }}kg · {{ fmt0(s.qty) }} {{ L("units","قطعة","unités") }}</span>
        <span class="flex-1"></span>
        <span class="text-[12px] tnum"><b>{{ L("Freight","الشحن","Fret") }}:</b> {{ fmt0(s.freight.landed) }}
          <span class="text-[10px] font-bold px-1.5 py-0.5 rounded-full ms-1"
                :style="s.freight.source==='bills' ? 'background:#ecfdf5;color:#047857' : 'background:#fffbeb;color:#b45309'">
            {{ s.freight.source==='bills' ? L("actual","فعلي","réel") : L("not assembled","مش متجمّع","non assemblé") }}</span>
          <span class="text-[10.5px] text-ink-muted"> @{{ s.freight.rate_kg }}/kg</span>
        </span>
      </div>
      <div class="flex gap-1.5 flex-wrap mt-1.5" v-if="s.freight.bills?.length">
        <span v-for="b in s.freight.bills" :key="b.voucher" class="inline-flex items-center gap-1 text-[10px] border rounded-[6px] px-1.5 py-0.5" style="background:#f0fdf4;border-color:#bbf7d0">
          <span class="font-mono" dir="ltr">{{ b.voucher }}</span><span class="tnum font-semibold">{{ fmt0(b.share) }}</span>
          <span v-if="b.n_prs > 1" class="text-ink-muted">÷{{ b.n_prs }}</span>
        </span>
      </div>
    </div>

    <!-- gate: verify AFTER the landed is assembled -->
    <div v-if="!freightReady" class="rounded-[10px] border border-amber-200 bg-amber-50 text-amber-800 px-4 py-3 text-[12px]">
      🔒 {{ L("Assemble this shipment's freight first (attach its bills in Purchases → Shipments) — verification opens once the landed cost is actual, so the Full column is real.",
              "اجمعوا شحن الشحنة دي الأول (إرفاق فواتيرها من المشتريات → الشحنات) — التحقق بيفتح لما الـlanded يبقى فعلي، علشان عمود «الكاملة» يكون حقيقي.",
              "Assembler d'abord le fret (Achats → Expéditions).") }}
      <router-link to="/accounting/purchases/shipments" class="font-bold underline ms-1">{{ L("Open Shipments","افتح الشحنات","Ouvrir") }} →</router-link>
    </div>

    <div class="bg-white rounded-card border border-line shadow-card overflow-hidden" :style="freightReady ? '' : 'opacity:.55'">
      <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2 flex-wrap">
        <span class="text-[12px] font-bold">📦 {{ L("Product costs — verify each line against the supplier invoice","تكلفة البضاعة — اتحققوا من كل سطر مع فاتورة المورد","Coûts produits") }}</span>
        <span class="text-[11px] text-ink-muted flex-1">{{ verifiedCount }}/{{ s.lines.length }} {{ L("verified","متحقق","vérifié") }}</span>
        <button v-if="canWrite && freightReady" class="h-[26px] px-2.5 rounded-[7px] text-[10.5px] font-bold border border-line text-ink-2 hover:bg-app-warm"
                @click="useSuggestedAll">{{ L("Use suggested for empty lines","استخدام المقترح للفاضي","Suggestions") }}</button>
      </div>
      <div class="max-h-[440px] overflow-y-auto">
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
                <div class="text-[10px] text-ink-muted truncate max-w-[260px]">{{ l.sku || l.item_name }}</div>
              </td>
              <td class="px-3 py-1.5 text-end tnum">{{ fmt0(l.qty) }}</td>
              <td class="px-3 py-1.5 text-end tnum text-ink-muted">{{ l.book_rate }}</td>
              <td class="px-3 py-1.5 text-end tnum">
                <button v-if="l.suggested" class="hover:underline decoration-dotted" :title="l.source" :disabled="!freightReady" @click="edits[l.item_code] = l.suggested">{{ l.suggested }}</button>
                <span v-else class="text-ink-3">—</span>
              </td>
              <td class="px-2 py-1 text-end">
                <input type="number" step="0.01" min="0" v-model.number="edits[l.item_code]" :disabled="!canWrite || !freightReady"
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
        <input v-model="note" :disabled="!freightReady" :placeholder="L('Note (which invoice was checked…)','ملاحظة (اتراجعت على أنهي فاتورة…)','Note…')"
               class="h-[30px] px-2.5 text-[11.5px] border border-line rounded-[8px] outline-none flex-1 min-w-[200px]" />
        <span class="text-[11px] text-ink-muted" v-if="s.sheet.on" dir="ltr">💾 {{ s.sheet.by }} · {{ s.sheet.on }}</span>
        <button v-if="canWrite" class="h-[32px] px-4 rounded-[8px] text-[12px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand disabled:opacity-50"
                :disabled="busy || !freightReady" @click="saveSheet">💾 {{ L("Save draft","حفظ المسودة","Enregistrer") }}</button>
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

const props = defineProps({ pr: { type: String, required: true }, year: { type: [Number, String], default: null } });
const emit = defineEmits(["saved"]);
const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt0 = (n) => Number(n || 0).toLocaleString("en-US", { maximumFractionDigits: 0 });
const { can } = useAuth();
const canWrite = computed(() => can("post_entries"));
const toast = useToast();

const SC = "accounting_portal.api.shipment_costing";
const s = ref(null);
const edits = reactive({});
const note = ref("");
const busy = ref(false);

const freightReady = computed(() => s.value?.freight?.source === "bills");
const verifiedCount = computed(() => (s.value?.lines || []).filter((l) => edits[l.item_code] > 0).length);

async function load() {
  s.value = null;
  try {
    const r = await api.call(`${SC}.get_sheet`, { pr: props.pr, year: props.year || undefined }, { fresh: true });
    Object.keys(edits).forEach((k) => delete edits[k]);
    for (const l of r.lines) if (l.verified > 0) edits[l.item_code] = l.verified;
    note.value = r.sheet?.note || "";
    s.value = r;
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
</script>
