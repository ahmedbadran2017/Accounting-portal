<template>
  <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
    <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2 flex-wrap">
      <span class="text-[13px] font-bold">③ {{ L("Catalogue — by model","③ الكتالوج — بالموديل","③ Catalogue par modèle") }}</span>
      <span v-if="data" class="text-[11px] text-ink-muted tnum">{{ data.total }} {{ L("models","موديل","modèles") }}</span>
      <div class="flex-1"></div>
      <select v-model="supFilter" @change="start = 0; load()" class="h-[28px] text-[11.5px] px-2 rounded-[8px] border border-line max-w-[170px]">
        <option value="">{{ L("All suppliers","كل الموردين","Fournisseurs") }}</option>
        <option v-for="sp in filters.suppliers" :key="sp.supplier" :value="sp.supplier">{{ shortSup(sp.supplier) }} ({{ sp.items }})</option>
      </select>
      <select v-model="moFilter" @change="start = 0; load()" class="h-[28px] text-[11.5px] px-2 rounded-[8px] border border-line">
        <option value="">{{ L("All months","كل الشهور","Mois") }}</option>
        <option v-for="mo in filters.months" :key="mo" :value="mo">{{ mo }}</option>
      </select>
      <select v-model="srcFilter" @change="start = 0; load()" class="h-[28px] text-[11.5px] px-2 rounded-[8px] border border-line">
        <option value="">{{ L("All sources","كل المصادر","Toutes") }}</option>
        <option value="maslak_pi">{{ L("Maslak-sourced","مصدر Maslak","Maslak") }}</option>
        <option value="local_pi">{{ L("Local suppliers","موردين محليين","Locaux") }}</option>
        <option value="family_pi">{{ L("Family evidence","دليل العائلة","Famille") }}</option>
        <option value="morocco_pr">{{ L("Morocco-direct","مغرب مباشر","Maroc") }}</option>
      </select>
      <div class="flex items-center gap-1.5" v-if="data">
        <button v-for="f in statuses" :key="f.k"
                class="h-[26px] px-2.5 rounded-[8px] text-[11px] font-bold border"
                :class="stFilter === f.k ? 'text-white bg-brand border-brand' : 'text-ink-3 border-line hover:bg-app-warm'"
                @click="stFilter = stFilter === f.k ? '' : f.k; start = 0; load()">
          {{ f.label }} <span class="tnum">{{ data.counts[f.k] || 0 }}</span>
        </button>
      </div>
      <input v-model="search" @keyup.enter="start = 0; load()" :placeholder="L('Search model…','بحث…','Recherche…')"
             class="h-[28px] w-[170px] text-[11.5px] px-2.5 rounded-[8px] border border-line" />
    </div>
    <div v-if="loading" class="py-12 text-center text-[12px] text-ink-muted">{{ L("Grouping the catalogue…","بيجمع الكتالوج…","Chargement…") }}</div>
    <div v-else-if="err" class="py-12 text-center text-[12px] text-sale">{{ err }} <button class="underline" @click="load">{{ L("Retry","إعادة","Réessayer") }}</button></div>
    <div v-else-if="data" class="overflow-x-auto">
      <table class="w-full text-[12px]">
        <thead><tr style="background:#fafaf9">
          <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Model","الموديل","Modèle") }}</th>
          <th class="px-3 py-2.5 text-center text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Variants","الأصناف","Var.") }}</th>
          <th class="px-3 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Stock","المخزون","Stock") }}</th>
          <th class="px-3 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ month ? L("Month impact","أثر الشهر","Impact mois") : L("Value","القيمة","Valeur") }}</th>
          <th class="px-3 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Book range","مدى الدفاتر","Livre") }}</th>
          <th class="px-3 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("True","الحقيقي","Vrai") }}</th>
          <th class="px-4 py-2.5 text-center text-[10px] font-bold uppercase tracking-wider text-ink-muted">✓</th>
        </tr></thead>
        <tbody>
          <tr v-for="r in data.rows" :key="r.key" class="border-t border-line-hair hover:bg-app-warm/60 cursor-pointer" @click="$emit('open', r.key)">
            <td class="px-4 py-2.5"><span class="font-semibold truncate block max-w-[280px]">{{ r.name }}</span><span class="text-[10px] text-ink-muted font-mono">{{ r.base }}</span></td>
            <td class="px-3 py-2.5 text-center"><span class="text-[10.5px] font-bold px-1.5 py-0.5 rounded-full bg-app-warm text-ink-2">×{{ r.n_variants }}</span></td>
            <td class="px-3 py-2.5 text-end tnum text-ink-3">{{ fmt(r.qty) }}</td>
            <td class="px-3 py-2.5 text-end tnum" :class="month && r.month_impact ? 'font-bold text-amber-700' : ''">{{ month ? fmt(r.month_impact) : fmt(r.value) }}</td>
            <td class="px-3 py-2.5 text-end tnum text-ink-3" dir="ltr">{{ r.book_min === r.book_max ? fmt2(r.book_min) : fmt2(r.book_min) + "–" + fmt2(r.book_max) }}</td>
            <td class="px-3 py-2.5 text-end tnum font-semibold" :class="r.true_cost != null ? 'text-emerald-700' : 'text-amber-600'">{{ r.true_cost != null ? fmt2(r.true_cost) : "—" }}</td>
            <td class="px-4 py-2.5 text-center">
              <span class="text-[10.5px] font-bold tnum" :class="r.n_fixed >= r.n_variants ? 'text-emerald-700' : r.n_fixed ? 'text-amber-600' : 'text-ink-3'">
                {{ r.n_fixed }}/{{ r.n_variants }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="!data.rows.length" class="py-10 text-center text-[12px] text-ink-muted">{{ L("No models.","لا موديلات.","Aucun.") }}</div>
      <div class="px-4 py-2.5 border-t border-line-hair flex items-center gap-2 text-[11.5px] text-ink-muted" v-if="data.total > pageSize">
        <button class="h-[26px] px-2.5 rounded-[7px] border border-line font-bold disabled:opacity-40" :disabled="start === 0" @click="start = Math.max(start - pageSize, 0); load()">‹</button>
        <span class="tnum">{{ start + 1 }}–{{ Math.min(start + pageSize, data.total) }} / {{ data.total }}</span>
        <button class="h-[26px] px-2.5 rounded-[7px] border border-line font-bold disabled:opacity-40" :disabled="start + pageSize >= data.total" @click="start += pageSize; load()">›</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useI18n } from "vue-i18n";
import api from "@/services/api";

const props = defineProps({ month: { type: String, default: "" } });
defineEmits(["open"]);
const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const M = "accounting_portal.api.model_costing";
const fmt = (n) => new Intl.NumberFormat("en-US").format(Math.round(n || 0));
const fmt2 = (n) => new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(n || 0);

const data = ref(null);
const loading = ref(false);
const err = ref("");
const search = ref("");
const stFilter = ref("");
const supFilter = ref("");
const moFilter = ref("");
const srcFilter = ref("");
const filters = ref({ suppliers: [], months: [] });
api.call("accounting_portal.api.cost_trace.cost_filters", {}).then((r) => { filters.value = r; }).catch(() => {});
const shortSup = (s) => (s ? String(s).replace(/\s*(T[İI]C\.?|SAN\.?|LTD\.?|Ş[Tt][İI]\.?|A\.?Ş\.?|İMALAT).*$/i, "").trim().slice(0, 22) || String(s).slice(0, 22) : "");
const start = ref(0);
const pageSize = 50;

const statuses = computed(() => [
  { k: "ready", label: L("Ready", "جاهز", "Prêt") },
  { k: "partial", label: L("Partial", "جزئي", "Partiel") },
  { k: "unpriced", label: L("Unpriced", "بلا سعر", "Sans prix") },
  { k: "fixed", label: L("Fixed ✓", "متظبط ✓", "Corrigé ✓") },
]);

async function load() {
  loading.value = true;
  err.value = "";
  try {
    data.value = await api.call(`${M}.model_catalogue`, {
      search: search.value || undefined, fix_status: stFilter.value || undefined,
      start: start.value, page_size: pageSize, month: props.month || undefined,
      supplier: supFilter.value || undefined, proc_month: moFilter.value || undefined,
      source: srcFilter.value || undefined,
    }, { fresh: true });
  } catch (e) { err.value = e.message || "Failed"; }
  finally { loading.value = false; }
}
load();
watch(() => props.month, () => { start.value = 0; load(); });
defineExpose({ load });
</script>
