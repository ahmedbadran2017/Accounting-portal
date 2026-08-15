<template>
  <div class="space-y-3.5">
    <!-- Headline -->
    <div class="flex items-center gap-2 flex-wrap">
      <span class="text-[13px] font-bold">{{ L("Product cost trace","تتبّع تكلفة المنتج","Traçage coût produit") }}</span>
      <span class="text-[11px] text-ink-muted flex-1">{{ L("The true cost of a product, from its source supplier through every company to Morocco — where the price diverged.","التكلفة الحقيقية للمنتج، من المورّد الأصلي عبر كل الشركات للمغرب — والفرق حصل فين.","Le vrai coût d'un produit, de la source jusqu'au Maroc.") }}</span>
    </div>

    <!-- Search -->
    <div class="bg-white border border-line rounded-[12px] shadow-card p-3 relative">
      <div class="flex items-center gap-2">
        <Icon name="search" :size="16" color="#9a8f88" />
        <input v-model="q" @input="onSearch" @focus="onSearch"
               :placeholder="L('Search SKU / name / code…','بحث SKU / اسم / كود…','Rechercher…')"
               class="flex-1 h-[30px] text-[13px] outline-none bg-transparent" />
        <span v-if="loading" class="text-[11px] text-ink-muted">{{ L("…","…","…") }}</span>
      </div>
      <div v-if="results.length && showResults" class="absolute z-20 left-3 right-3 top-[52px] bg-white border border-line rounded-[10px] shadow-cardHover max-h-[320px] overflow-y-auto">
        <button v-for="r in results" :key="r.item_code" class="w-full text-start px-3 py-2 hover:bg-app-warm border-b border-line-hair last:border-0 flex items-center gap-2"
                @click="pick(r.item_code)">
          <div class="flex-1 min-w-0">
            <div class="text-[12px] font-semibold truncate">{{ r.sku || r.item_code }}</div>
            <div class="text-[10.5px] text-ink-muted truncate">{{ r.item_name }}</div>
          </div>
          <span v-if="r.stock_qty > 0" class="text-[10px] font-bold text-emerald-700 whitespace-nowrap">{{ fmtNum(r.stock_qty) }} {{ L("in stock","بالمخزن","stock") }}</span>
        </button>
      </div>
    </div>

    <div v-if="err" class="rounded-[10px] border border-amber-200 bg-amber-50 text-amber-800 px-4 py-3 text-[12px]">{{ err }}</div>

    <!-- Catalogue overview + worklist (shown when no single item is picked) -->
    <template v-if="!trace">
      <div v-if="ov" class="grid grid-cols-2 lg:grid-cols-4 gap-2.5">
        <div class="bg-white rounded-[12px] border border-line p-3.5 shadow-card">
          <div class="text-[10.5px] text-ink-muted font-semibold">{{ L("Current book value","القيمة الحالية","Valeur actuelle") }}</div>
          <div class="text-[18px] font-bold tnum mt-[3px]">{{ fmtNum(ov.current_value) }}</div>
          <div class="text-[10px] text-ink-3">{{ fmtNum(ov.items) }} {{ L("stocked items","صنف بالمخزن","articles") }}</div>
        </div>
        <div class="bg-white rounded-[12px] border border-line p-3.5 shadow-card">
          <div class="text-[10.5px] text-ink-muted font-semibold">{{ L("True value (priced)","القيمة الحقيقية","Valeur vraie") }}</div>
          <div class="text-[18px] font-bold tnum mt-[3px] text-emerald-700">{{ fmtNum(ov.true_value_priced) }}</div>
          <div class="text-[10px] text-ink-3">{{ fmtNum(ov.maslak_pi + ov.morocco_pr) }} {{ L("priced","مسعّر","tarifés") }}</div>
        </div>
        <div class="bg-white rounded-[12px] border p-3.5 shadow-card" style="border-color:#fecaca">
          <div class="text-[10.5px] text-ink-muted font-semibold">{{ L("Overvaluation","التشوّه","Survalorisation") }}</div>
          <div class="text-[18px] font-bold tnum mt-[3px]" style="color:#b91c1c">{{ fmtNum(ov.overvaluation) }}</div>
          <div class="text-[10px] text-ink-3">{{ L("to remove from stock","يتشال من المخزون","à retirer") }}</div>
        </div>
        <div class="bg-white rounded-[12px] border p-3.5 shadow-card" style="border-color:#fde68a">
          <div class="text-[10.5px] text-ink-muted font-semibold">{{ L("Unpriced (no source)","بلا مصدر","sans source") }}</div>
          <div class="text-[18px] font-bold tnum mt-[3px]" style="color:#b45309">{{ fmtNum(ov.unpriced) }}</div>
          <div class="text-[10px] text-ink-3">{{ L("need manual cost","محتاجة تسعير يدوي","coût manuel") }}</div>
        </div>
      </div>

      <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
        <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2 flex-wrap">
          <span class="text-[13px] font-bold">{{ L("Catalogue — true cost vs book","الكتالوج — الحقيقة مقابل الدفاتر","Catalogue") }}</span>
          <div class="flex-1"></div>
          <!-- supplier → month audit filter -->
          <select v-model="supFilter" class="h-[28px] text-[11.5px] px-2 rounded-[8px] border border-line max-w-[180px]">
            <option value="">{{ L("All suppliers","كل الموردين","Fournisseurs") }}</option>
            <option v-for="s in filters.suppliers" :key="s.supplier" :value="s.supplier">{{ shortSup(s.supplier) }} ({{ s.items }})</option>
          </select>
          <select v-model="moFilter" class="h-[28px] text-[11.5px] px-2 rounded-[8px] border border-line">
            <option value="">{{ L("All months","كل الشهور","Mois") }}</option>
            <option v-for="m in filters.months" :key="m" :value="m">{{ m }}</option>
          </select>
          <select v-model="srcFilter" class="h-[28px] text-[11.5px] px-2 rounded-[8px] border border-line">
            <option value="">{{ L("All sources","كل المصادر","Toutes") }}</option>
            <option value="maslak_pi">{{ L("Maslak-sourced","مصدر Maslak","Maslak") }}</option>
            <option value="morocco_pr">{{ L("Morocco-direct","مغرب مباشر","Maroc") }}</option>
            <option value="unpriced">{{ L("Unpriced","بلا سعر","Sans prix") }}</option>
          </select>
        </div>
        <div v-if="ct.error.value" class="py-8 text-center text-[12px] text-sale">{{ ct.error.value }}</div>
        <div v-else class="overflow-x-auto">
          <table class="w-full text-[12px]">
            <thead>
              <tr style="background:#fafaf9">
                <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Product","المنتج","Produit") }}</th>
                <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Supplier","المورّد","Fournisseur") }}</th>
                <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Source","المصدر","Source") }}</th>
                <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Qty","كمية","Qté") }}</th>
                <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Book","الدفاتر","Livre") }}</th>
                <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("True","الحقيقي","Vrai") }}</th>
                <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Overvaluation","التشوّه","Survalo.") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in ct.rows.value" :key="r.item_code" class="border-t border-line-hair hover:bg-app-warm/60 cursor-pointer" @click="pick(r.item_code)">
                <td class="px-4 py-2.5 truncate max-w-[220px]"><span class="font-semibold">{{ r.sku || r.item_code }}</span><div class="text-[10px] text-ink-muted truncate">{{ r.item_name }}</div></td>
                <td class="px-4 py-2.5 text-ink-3 truncate max-w-[130px] text-[11px]">{{ shortSup(r.supplier) || "—" }}</td>
                <td class="px-4 py-2.5"><span class="text-[10px] font-bold px-1.5 py-0.5 rounded-full" :style="srcChip(r.source)">{{ srcShort(r.source) }}</span></td>
                <td class="px-4 py-2.5 text-end tnum text-ink-3">{{ fmtNum(r.qty) }}</td>
                <td class="px-4 py-2.5 text-end tnum">{{ fmtNum(r.current_rate, 1) }}</td>
                <td class="px-4 py-2.5 text-end tnum font-semibold text-emerald-700">{{ r.true_cost != null ? fmtNum(r.true_cost, 1) : "—" }}</td>
                <td class="px-4 py-2.5 text-end tnum font-bold" :style="{ color: (r.overvaluation || 0) > 0 ? '#b91c1c' : '#78716c' }">{{ r.overvaluation != null ? fmtNum(r.overvaluation) : "—" }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="!ct.loading.value && !ct.rows.value.length && !ct.error.value" class="py-10 text-center text-[12px] text-ink-muted">{{ L("No items.","لا أصناف.","Aucun.") }}</div>
        <ServerPager :t="ct" />
      </div>
    </template>

    <!-- Trace result -->
    <div v-if="trace" class="space-y-3">
      <button class="text-[11.5px] font-semibold text-brand hover:underline inline-flex items-center gap-1" @click="trace = null; q = ''">
        <Icon name="arrow" :size="12" class="rtl:rotate-180" />{{ L("Back to catalogue","رجوع للكتالوج","Retour") }}
      </button>
      <!-- Product header + KPIs -->
      <div class="bg-white border border-line rounded-[14px] shadow-card p-4">
        <div class="flex items-start gap-3 flex-wrap">
          <div class="flex-1 min-w-[200px]">
            <div class="text-[14px] font-bold">{{ trace.sku || trace.item_code }}</div>
            <div class="text-[11.5px] text-ink-muted">{{ trace.item_name }}</div>
            <div class="text-[10.5px] text-ink-3 mt-0.5">{{ trace.item_code }} · {{ trace.uom }} · {{ trace.weight_per_unit }}kg</div>
          </div>
          <div class="grid grid-cols-3 gap-2.5">
            <div class="text-center px-3">
              <div class="text-[10px] text-ink-muted font-semibold">{{ L("True cost","التكلفة الحقيقية","Vrai coût") }}</div>
              <div class="text-[18px] font-bold tnum text-emerald-700">{{ trace.true_cost.cost_mad != null ? fmtNum(trace.true_cost.cost_mad) : "—" }}</div>
              <div class="text-[9.5px]" :class="srcColor">{{ srcLabel }}</div>
            </div>
            <div class="text-center px-3">
              <div class="text-[10px] text-ink-muted font-semibold">{{ L("Current book","الدفاتر الحالية","Livre actuel") }}</div>
              <div class="text-[18px] font-bold tnum">{{ trace.current_valuation_mad != null ? fmtNum(trace.current_valuation_mad) : "—" }}</div>
              <div class="text-[9.5px] text-ink-3">{{ fmtNum(trace.current_qty) }} {{ L("units","وحدة","u.") }}</div>
            </div>
            <div class="text-center px-3">
              <div class="text-[10px] text-ink-muted font-semibold">{{ L("Distortion","التشوّه","Distorsion") }}</div>
              <div class="text-[18px] font-bold tnum" :style="{ color: distColor }">{{ trace.distortion_pct != null ? (trace.distortion_pct > 0 ? "+" : "") + fmtNum(trace.distortion_pct) + "%" : "—" }}</div>
              <div class="text-[9.5px] text-ink-3">{{ L("vs true cost","مقابل الحقيقة","vs vrai") }}</div>
            </div>
          </div>
        </div>
        <div class="text-[10.5px] text-ink-muted mt-2.5 pt-2.5 border-t border-line-hair">
          ⓘ {{ L("Product cost only — inbound landed freight/customs is added on top separately (Landed Cockpit).","تكلفة المنتج فقط — الشحن/الجمارك الوارد يُضاف فوقها منفصلًا (Landed Cockpit).","Coût produit uniquement — le fret entrant s'ajoute séparément.") }}
        </div>
      </div>

      <!-- The cost ladder -->
      <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
        <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2">
          <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#eef6ff"><Icon name="layers" :size="14" color="#2563eb" /></span>
          <span class="text-[13px] font-bold">{{ L("Cost ladder — source → Morocco","سلّم التكلفة — المصدر → المغرب","Échelle du coût") }}</span>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-[12px]">
            <thead>
              <tr style="background:#fafaf9">
                <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Stage","المرحلة","Étape") }}</th>
                <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Company","الشركة","Société") }}</th>
                <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Document","المستند","Document") }}</th>
                <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Rate","السعر","Taux") }}</th>
                <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("→ MAD","→ MAD","→ MAD") }}</th>
                <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Δ vs true","Δ الحقيقة","Δ") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(h, i) in trace.ladder" :key="i" class="border-t border-line-hair" :style="rowStyle(h)">
                <td class="px-4 py-2.5 font-semibold whitespace-nowrap">{{ stageLabel(h.stage) }}</td>
                <td class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ h.company }}</td>
                <td class="px-4 py-2.5 font-mono text-[11px] whitespace-nowrap">{{ h.name }}<div class="text-[10px] text-ink-muted font-sans">{{ h.date }}</div></td>
                <td class="px-4 py-2.5 text-end tnum whitespace-nowrap">{{ fmtNum(h.rate, 2) }} {{ h.currency }}<span v-if="h.conversion_rate" class="text-[10px] text-ink-muted"> @{{ h.conversion_rate }}</span></td>
                <td class="px-4 py-2.5 text-end tnum font-bold">{{ fmtNum(h.rate_mad, 2) }}</td>
                <td class="px-4 py-2.5 text-end tnum">
                  <span v-if="h.dev_pct != null" :style="{ color: devColor(h) }" class="font-semibold">{{ h.dev_pct > 0 ? "+" : "" }}{{ fmtNum(h.dev_pct) }}%</span>
                  <span v-else class="text-ink-muted">—</span>
                  <span class="ms-1.5 text-[13px]">{{ flagIcon(h.flag) }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="!trace.ladder.length" class="py-10 text-center text-[12px] text-ink-muted">{{ L("No purchase documents found for this product.","لا مستندات شراء لهذا المنتج.","Aucun document d'achat.") }}</div>
      </div>
    </div>

    <div v-else-if="!loading && !err" class="py-16 text-center text-[12px] text-ink-muted">
      {{ L("Search for a product to trace its cost across companies.","ابحث عن منتج لتتبّع تكلفته عبر الشركات.","Recherchez un produit.") }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import ServerPager from "@/components/ServerPager.vue";
import { useServerTable } from "@/composables/useServerTable";
import api from "@/services/api";
import { useToast } from "@/composables/useToast";

const { locale } = useI18n();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmtNum = (n, d = 0) => {
  const v = Number(n);
  if (!isFinite(v)) return "—";
  return v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
};
const M = "accounting_portal.api.cost_trace";

const q = ref("");
const results = ref([]);
const showResults = ref(false);
const trace = ref(null);
const loading = ref(false);
const err = ref("");

let t = null;
function onSearch() {
  showResults.value = true;
  clearTimeout(t);
  const term = q.value.trim();
  if (term.length < 2) { results.value = []; return; }
  t = setTimeout(async () => {
    try { results.value = await api.call(`${M}.search_items`, { query: term }); }
    catch (e) { results.value = []; }
  }, 250);
}

async function pick(itemCode) {
  showResults.value = false;
  loading.value = true;
  err.value = "";
  trace.value = null;
  try {
    trace.value = await api.call(`${M}.trace_item`, { item_code: itemCode });
    q.value = trace.value.sku || itemCode;
  } catch (e) {
    err.value = e.message || "Failed to load trace";
  } finally {
    loading.value = false;
  }
}

// ── Catalogue overview + worklist table ──
const ov = ref(null);
const srcFilter = ref("");
const supFilter = ref("");
const moFilter = ref("");
const filters = ref({ suppliers: [], months: [] });
api.call(`${M}.cost_overview`, {}).then((r) => { ov.value = r; }).catch(() => {});
api.call(`${M}.cost_filters`, {}).then((r) => { filters.value = r; }).catch(() => {});
const ct = useServerTable(
  (params) => api.call(`${M}.cost_table`, {
    source: srcFilter.value || undefined,
    supplier: supFilter.value || undefined,
    month: moFilter.value || undefined,
    ...params,
  }),
  { pageSize: 50 });
ct.load();
watch([srcFilter, supFilter, moFilter], () => { ct.page.value = 1; ct.load(); });
// a Turkish supplier name can be very long — trim for chips/cells
const shortSup = (s) => (s ? String(s).replace(/\s*(T[İI]C\.?|SAN\.?|LTD\.?|Ş[Tt][İI]\.?|A\.?Ş\.?|İMALAT).*$/i, "").trim().slice(0, 22) || String(s).slice(0, 22) : "");

const SRC = {
  maslak_pi: [L("Maslak", "Maslak", "Maslak"), "background:#ecfdf5;color:#047857"],
  morocco_pr: [L("Morocco", "مغرب", "Maroc"), "background:#eff6ff;color:#2563eb"],
  unpriced: [L("unpriced", "بلا سعر", "sans prix"), "background:#fffbeb;color:#b45309"],
};
const srcShort = (s) => (SRC[s] ? SRC[s][0] : s);
const srcChip = (s) => (SRC[s] ? SRC[s][1] : "");

const srcLabel = computed(() => ({
  maslak_pi: L("Maslak invoice", "فاتورة Maslak", "Facture Maslak"),
  morocco_pr: L("Morocco receipt", "استلام المغرب", "Réception Maroc"),
  orphan: L("no source", "بلا مصدر", "sans source"),
  fx_unavailable: L("no FX rate", "بلا سعر صرف", "sans taux"),
}[trace.value?.true_cost?.source] || ""));
const srcColor = computed(() => (
  trace.value?.true_cost?.source === "maslak_pi" ? "text-emerald-700"
    : ["orphan", "fx_unavailable"].includes(trace.value?.true_cost?.source) ? "text-amber-600" : "text-ink-3"));
const distColor = computed(() => {
  const d = trace.value?.distortion_pct;
  if (d == null) return "#78716c";
  return Math.abs(d) < 15 ? "#047857" : Math.abs(d) < 60 ? "#b45309" : "#b91c1c";
});

const stageLabels = {
  source_po: L("① PO (source)", "① أمر شراء", "① Commande"),
  source_pr: L("② Receipt (source)", "② استلام (مصدر)", "② Réception"),
  source_pi: L("③ Invoice (source) ⭐", "③ فاتورة (مصدر) ⭐", "③ Facture ⭐"),
  transfer_paper: L("④ Transfer (paper)", "④ تحويل (ورقي)", "④ Transfert"),
  dest_pr: L("⑤ Receipt (Morocco)", "⑤ استلام (المغرب)", "⑤ Réception Maroc"),
};
const stageLabel = (s) => stageLabels[s] || s;
const flagIcon = (f) => ({ ok: "✅", inflated: "🔴", low: "🔵", no_basis: "⚪" }[f] || "");
const devColor = (h) => (h.flag === "inflated" ? "#b91c1c" : h.flag === "low" ? "#2563eb" : "#047857");
function rowStyle(h) {
  if (h.stage === "source_pi") return { background: "#f0fdf4" };
  if (h.stage === "transfer_paper") return { background: "#fffbeb" };
  return {};
}
</script>
