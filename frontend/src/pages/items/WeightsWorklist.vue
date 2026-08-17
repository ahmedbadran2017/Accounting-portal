<template>
  <div class="space-y-4">
    <!-- why this matters -->
    <div class="rounded-[12px] border px-4 py-3 text-[12px] flex items-start gap-3" style="background:#fffbeb;border-color:#fde68a">
      <span class="text-[16px]">⚖️</span>
      <div>
        <div class="font-bold" style="color:#92400e">{{ L("Weights are the freight SPLIT KEY","الأوزان هي مفتاح توزيع الشحن","Les poids répartissent le fret") }}</div>
        <div class="text-[11.5px] mt-px" style="color:#b45309">
          {{ L("A zero-weight item rides free while honest items overpay. Every weight fixed here immediately improves the split — and shrinks the calibration scale toward 1.","الصنف اللي وزنه صفر بيركب ببلاش وجاره بيدفع عنه. كل وزن يتصلح هنا بيظبط التوزيع فورًا — ومعامل المعايرة بيقرب لـ1 لوحده.","Un article à poids nul voyage gratuitement. Chaque poids corrigé améliore la répartition.") }}
        </div>
      </div>
      <div class="flex-1"></div>
      <div v-if="data && data.scales" class="text-end text-[11px] text-ink-muted whitespace-nowrap">
        <div>{{ L("calibration scale","معامل المعايرة","échelle") }}</div>
        <div class="tnum font-bold text-[13px]" style="color:#92400e" dir="ltr">
          ✈ ×{{ (data.scales.air || 1).toFixed(2) }} · 🚢 ×{{ (data.scales.sea || 1).toFixed(2) }}
        </div>
        <div>{{ L("goal: ×1.00","الهدف: ×1.00","objectif : ×1,00") }}</div>
      </div>
    </div>

    <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
      <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2 flex-wrap">
        <span class="text-[13px] font-bold">{{ L("Suspect weights","أوزان مشكوك فيها","Poids suspects") }}</span>
        <span v-if="data" class="text-[11px] text-ink-muted tnum">{{ data.total }}</span>
        <div class="flex-1"></div>
        <div class="flex items-center gap-1.5" v-if="data">
          <button v-for="f in flags" :key="f.k"
                  class="h-[26px] px-2.5 rounded-[8px] text-[11px] font-bold border"
                  :class="flag === f.k ? 'text-white bg-brand border-brand' : 'text-ink-3 border-line hover:bg-app-warm'"
                  @click="flag = flag === f.k ? '' : f.k; load()">
            {{ f.label }} <span class="tnum">{{ data.counts[f.k] }}</span>
          </button>
        </div>
        <input v-model="search" @keyup.enter="load" :placeholder="L('Search SKU / name…','بحث…','Recherche…')"
               class="h-[28px] w-[180px] text-[11.5px] px-2.5 rounded-[8px] border border-line" />
      </div>

      <div v-if="loading" class="py-12 text-center text-[12px] text-ink-muted">{{ L("Loading…","بيحمّل…","Chargement…") }}</div>
      <div v-else-if="err" class="py-12 text-center text-[12px] text-sale">{{ err }} <button class="underline" @click="load">{{ L("Retry","إعادة","Réessayer") }}</button></div>
      <div v-else class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead><tr style="background:#fafaf9">
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Item","الصنف","Article") }}</th>
            <th class="px-3 py-2.5 text-center text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Problem","المشكلة","Problème") }}</th>
            <th class="px-3 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Units received","وحدات مستلمة","Unités reçues") }}</th>
            <th class="px-3 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("In stock","في المخزون","En stock") }}</th>
            <th class="px-3 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Book kg","الوزن الدفتري","Poids") }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Real kg / unit","الوزن الحقيقي/وحدة","Réel kg") }}</th>
          </tr></thead>
          <tbody>
            <tr v-for="r in data.rows" :key="r.item_code" class="border-t border-line-hair" :class="saved[r.item_code] ? 'bg-emerald-50/40' : ''">
              <td class="px-4 py-2">
                <span class="flex items-center gap-2.5">
                  <img v-if="r.image" :src="r.image" class="w-8 h-8 rounded-[7px] object-cover flex-shrink-0 border border-line-hair" />
                  <span v-else class="w-8 h-8 rounded-[7px] bg-app-warm flex-shrink-0"></span>
                  <span class="min-w-0"><span class="block font-semibold truncate max-w-[280px]">{{ r.item_name }}</span>
                    <span class="block text-[10px] text-ink-muted font-mono">{{ r.sku || r.item_code }}</span></span>
                </span>
              </td>
              <td class="px-3 py-2 text-center">
                <span class="text-[10px] font-bold px-1.5 py-0.5 rounded-full" :style="flagChip(r.flag)">{{ flagLabel(r.flag) }}</span>
              </td>
              <td class="px-3 py-2 text-end tnum text-ink-3">{{ fmt(r.units_in) }}</td>
              <td class="px-3 py-2 text-end tnum text-ink-3">{{ fmt(r.stock_qty) }}</td>
              <td class="px-3 py-2 text-end tnum" :class="r.flag === 'zero' ? 'text-sale font-bold' : 'text-ink-3'">{{ r.w.toFixed(2) }}</td>
              <td class="px-4 py-2 text-end">
                <span v-if="saved[r.item_code]" class="text-[11.5px] font-bold text-emerald-700 tnum">✓ {{ saved[r.item_code].toFixed(2) }} kg</span>
                <span v-else class="inline-flex items-center gap-1.5">
                  <input v-model.number="edits[r.item_code]" type="number" step="0.01" min="0.005" max="50"
                         class="h-[26px] w-[72px] text-[11.5px] text-end px-1.5 rounded-[7px] border border-line tnum" dir="ltr" placeholder="kg" />
                  <button v-if="canWrite" class="h-[26px] px-2.5 rounded-[7px] text-[10.5px] font-bold text-white bg-brand hover:bg-brand-dark disabled:opacity-40"
                          :disabled="!(edits[r.item_code] > 0) || savingKey === r.item_code" @click="save(r)">
                    {{ savingKey === r.item_code ? "…" : L("Save","حفظ","OK") }}
                  </button>
                </span>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-if="!data.rows.length" class="py-10 text-center text-[12px] text-ink-muted">🎉 {{ L("Nothing suspect — the split key is clean.","مفيش أوزان مشكوك فيها — مفتاح التوزيع نضيف.","Rien de suspect.") }}</div>
        <div class="px-4 py-2.5 border-t border-line-hair flex items-center gap-2 text-[11.5px] text-ink-muted" v-if="data.total > pageSize">
          <button class="h-[26px] px-2.5 rounded-[7px] border border-line font-bold disabled:opacity-40" :disabled="start === 0" @click="start = Math.max(start - pageSize, 0); load()">‹</button>
          <span class="tnum">{{ start + 1 }}–{{ Math.min(start + pageSize, data.total) }} / {{ data.total }}</span>
          <button class="h-[26px] px-2.5 rounded-[7px] border border-line font-bold disabled:opacity-40" :disabled="start + pageSize >= data.total" @click="start += pageSize; load()">›</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from "vue";
import { useI18n } from "vue-i18n";
import api from "@/services/api";
import { useToast } from "@/composables/useToast";
import { useAuth } from "@/composables/useAuth";

const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const toast = useToast();
const { can } = useAuth();
const canWrite = computed(() => can("post_entries"));
const M = "accounting_portal.api.weights";

const data = ref(null);
const loading = ref(false);
const err = ref("");
const search = ref("");
const flag = ref("");
const start = ref(0);
const pageSize = 50;
const edits = ref({});
const saved = ref({});
const savingKey = ref("");

const flags = computed(() => [
  { k: "zero", label: L("Zero", "صفر", "Zéro") },
  { k: "tiny", label: L("≤200g", "≤200جم", "≤200g") },
  { k: "default", label: L("0.50 default", "0.50 افتراضي", "0,50 défaut") },
]);
const flagChip = (f) => ({
  zero: "background:#fef2f2;color:#b91c1c",
  tiny: "background:#fffbeb;color:#b45309",
  default: "background:#eff6ff;color:#2563eb",
}[f] || "");
const flagLabel = (f) => ({
  zero: L("weight = 0", "وزن = صفر", "poids nul"),
  tiny: L("≤ 200 g", "≤ 200 جم", "≤ 200 g"),
  default: L("0.50 default", "0.50 افتراضي", "0,50 défaut"),
}[f] || f);
const fmt = (n) => new Intl.NumberFormat().format(Math.round(n || 0));

async function load() {
  loading.value = true;
  err.value = "";
  try {
    data.value = await api.call(`${M}.weight_worklist`, {
      search: search.value || undefined, flag: flag.value || undefined,
      start: start.value, page_size: pageSize,
    }, { fresh: true });
  } catch (e) { err.value = e.message || "Failed"; }
  finally { loading.value = false; }
}
load();

async function save(r) {
  const w = edits.value[r.item_code];
  if (!(w > 0)) return;
  savingKey.value = r.item_code;
  try {
    await api.call(`${M}.set_item_weight`, { item_code: r.item_code, weight: w });
    saved.value[r.item_code] = w;
    toast.success(L(`Saved — ${w} kg`, `اتسجل — ${w} كجم`, `Enregistré — ${w} kg`));
  } catch (e) { toast.error(e.message || "Failed"); }
  finally { savingKey.value = ""; }
}
</script>
