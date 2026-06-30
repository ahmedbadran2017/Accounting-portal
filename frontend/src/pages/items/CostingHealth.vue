<template>
  <div class="space-y-3.5">
    <TableLoading v-if="loading" :rows="6" />
    <template v-else>
      <!-- top stat cards -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div class="bg-white rounded-card border border-line shadow-card px-4 py-3">
          <div class="text-[10px] font-bold uppercase tracking-wider text-ink-muted flex items-center gap-1.5"><Icon name="wallet" :size="13" color="#0f766e" />{{ L("Costed","متكلّفة","Coûtés") }}</div>
          <div class="text-[20px] font-extrabold mt-1 tnum">{{ (cov.costed||0).toLocaleString() }}</div>
          <div class="text-[10.5px] text-ink-muted mt-0.5">{{ L("of","من","sur") }} {{ (cov.catalogue||0).toLocaleString() }} · {{ pct(cov.costed,cov.catalogue) }}%</div>
        </div>
        <button type="button" class="text-start bg-white rounded-card border shadow-card px-4 py-3 transition hover:ring-2 hover:ring-rose-400/20" :class="w.missing ? 'border-rose-200' : 'border-line'" @click="emit('drill','noweight')">
          <div class="text-[10px] font-bold uppercase tracking-wider flex items-center gap-1.5" :class="w.missing ? 'text-rose-600' : 'text-ink-muted'"><Icon name="scale" :size="13" :color="w.missing ? '#e11d48' : '#94a3b8'" />{{ L("Missing weight","وزن ناقص","Poids manquant") }}</div>
          <div class="text-[20px] font-extrabold mt-1 tnum" :class="w.missing ? 'text-rose-600' : ''">{{ (w.missing||0).toLocaleString() }}</div>
          <div class="text-[10.5px] text-ink-muted mt-0.5">{{ pct(w.missing,w.total) }}% · <span class="text-amber-700 font-semibold underline cursor-pointer" @click.stop="emit('drill','outliers')">{{ (w.heavy||0)+(w.light||0) }} {{ L("outliers","شاذة","aberrants") }}</span></div>
        </button>
        <div class="bg-white rounded-card border shadow-card px-4 py-3" :class="fx.overstatement>0 ? 'border-amber-200' : 'border-line'">
          <div class="text-[10px] font-bold uppercase tracking-wider flex items-center gap-1.5" :class="fx.overstatement>0 ? 'text-amber-700' : 'text-ink-muted'"><Icon name="alert" :size="13" :color="fx.overstatement>0 ? '#b45309' : '#94a3b8'" />{{ L("FX overstatement","تضخّم الصرف","Surévaluation FX") }}</div>
          <div class="text-[20px] font-extrabold mt-1 tnum" :class="fx.overstatement>0 ? 'text-amber-700' : ''">{{ money(fx.overstatement) }}</div>
          <div class="text-[10.5px] text-ink-muted mt-0.5">{{ (fx.wrong||[]).length }} {{ L("bad invoices","فاتورة غلط","factures") }} · {{ ccy }}</div>
        </div>
        <div class="bg-white rounded-card border border-line shadow-card px-4 py-3">
          <div class="text-[10px] font-bold uppercase tracking-wider text-ink-muted flex items-center gap-1.5"><Icon name="truck" :size="13" color="#0369a1" />{{ L("Freight in P&L","شحن بالمصروفات","Fret en charges") }}</div>
          <div class="text-[20px] font-extrabold mt-1 tnum" style="color:#0369a1">{{ money(fr.pool) }}</div>
          <div class="text-[10.5px] text-ink-muted mt-0.5">{{ L("not capitalised","غير مرسمَل","non capitalisé") }} · {{ fr.suggested_per_kg }}/kg</div>
        </div>
      </div>

      <!-- FX anomalies -->
      <div v-if="(fx.wrong||[]).length || (fx.unverified||[]).length" class="bg-white rounded-card border border-line shadow-card overflow-hidden">
        <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><Icon name="alert" :size="14" color="#b45309" /><span class="text-[12px] font-bold">{{ L("Exchange-rate anomalies","شذوذ سعر الصرف","Anomalies de change") }}</span></div>
        <table v-if="(fx.wrong||[]).length" class="w-full text-[12px]">
          <thead><tr style="background:#fafaf9" class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">
            <th class="px-4 py-2 text-start">{{ L("Invoice","الفاتورة","Facture") }}</th>
            <th class="px-3 py-2 text-end">{{ L("Booked FX","صرف مسجّل","FX livre") }}</th>
            <th class="px-3 py-2 text-end">{{ L("Live FX","صرف حيّ","FX réel") }}</th>
            <th class="px-3 py-2 text-end">{{ L("Booked","مسجّل","Livre") }}</th>
            <th class="px-3 py-2 text-end">{{ L("Corrected","مصحّح","Corrigé") }}</th>
            <th class="px-4 py-2 text-end">{{ L("Overstated","تضخّم","Surévalué") }}</th>
          </tr></thead>
          <tbody>
            <tr v-for="r in fx.wrong" :key="r.doc" class="border-t border-line-hair hover:bg-app-warm/40">
              <td class="px-4 py-2 font-mono text-[11px]">{{ r.doc }}<div class="text-[10px] text-ink-muted">{{ r.cur }} · {{ r.date }}</div></td>
              <td class="px-3 py-2 text-end tnum text-rose-600 font-semibold">{{ r.book_fx }}</td>
              <td class="px-3 py-2 text-end tnum text-success-dark font-bold">{{ r.live_fx }}</td>
              <td class="px-3 py-2 text-end tnum line-through text-ink-muted">{{ money(r.booked) }}</td>
              <td class="px-3 py-2 text-end tnum">{{ money(r.corrected) }}</td>
              <td class="px-4 py-2 text-end tnum font-bold text-amber-700">{{ money(r.overstatement) }}</td>
            </tr>
          </tbody>
        </table>
        <div v-if="(fx.unverified||[]).length" class="px-4 py-2.5 text-[11px] text-ink-2 border-t border-line-hair bg-app-warm/30">
          <Icon name="alert" :size="11" color="#9a8f86" class="inline" />
          {{ (fx.unverified||[]).length }} {{ L("foreign invoice(s) can't be verified — no exchange rate on file for","فاتورة أجنبية مش متأكّد منها — لا سعر صرف مسجّل لـ","facture(s) non vérifiables —") }} {{ unverifiedCurrencies }}.
          <button type="button" class="font-semibold text-accent-dark hover:underline" @click="router.push('/accounting/settings/currencies')">{{ L("Add the rates →","أضف الأسعار ←","Ajouter les taux →") }}</button>
        </div>
      </div>

      <!-- weight + coverage -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
          <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><Icon name="scale" :size="14" color="#0b5c4f" /><span class="text-[12px] font-bold">{{ L("Weight gaps by group","فجوات الوزن بالمجموعة","Poids par groupe") }}</span></div>
          <table class="w-full text-[12px]">
            <tbody>
              <tr v-for="g in (w.worst_groups||[])" :key="g.group" class="border-t border-line-hair first:border-t-0 hover:bg-app-warm/40 cursor-pointer" @click="emit('drill','noweight')">
                <td class="px-4 py-2 truncate max-w-[220px]">{{ g.group }}</td>
                <td class="px-3 py-2 text-end tnum text-ink-muted">{{ g.items.toLocaleString() }}</td>
                <td class="px-4 py-2 text-end tnum font-bold text-rose-600">{{ g.missing.toLocaleString() }} {{ L("missing","ناقص","manquant") }}</td>
              </tr>
              <tr v-if="!(w.worst_groups||[]).length"><td class="px-4 py-6 text-center text-ink-muted">{{ L("All weights present.","كل الأوزان موجودة.","Complet.") }}</td></tr>
            </tbody>
          </table>
        </div>
        <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
          <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><Icon name="truck" :size="14" color="#0b5c4f" /><span class="text-[12px] font-bold">{{ L("Inbound freight pool","تجمّع الشحن الداخل","Pool de fret") }}</span></div>
          <table class="w-full text-[12px]">
            <tbody>
              <tr v-for="a in (fr.accounts||[])" :key="a.nm" class="border-t border-line-hair first:border-t-0">
                <td class="px-4 py-2 truncate max-w-[240px]">{{ a.nm }}</td>
                <td class="px-4 py-2 text-end tnum font-semibold">{{ money(a.bal) }}</td>
              </tr>
            </tbody>
          </table>
          <div class="px-4 py-2 border-t border-line-hair text-[10.5px] text-ink-muted">{{ L("Sitting in P&L — should be capitalised onto product cost by weight (Phase 3).","قاعد في الأرباح والخسائر — المفروض يترسمَل على تكلفة المنتج بالوزن (مرحلة 3).","À capitaliser au poids (phase 3).") }}</div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";

const emit = defineEmits(["drill"]);
const router = useRouter();
const { locale } = useI18n();
const { entityId } = useUi();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const money = (n) => { n = Number(n) || 0; const a = Math.abs(n); return (n < 0 ? "−" : "") + (a >= 1e6 ? (a / 1e6).toFixed(2) + "M" : a >= 1e3 ? Math.round(a / 1e3) + "K" : Math.round(a)).toLocaleString(); };
const pct = (a, b) => (Number(b) ? Math.round(Number(a) / Number(b) * 100) : 0);

const data = ref({});
const loading = ref(true);
const ccy = computed(() => data.value.currency || "MAD");
const w = computed(() => data.value.weight || {});
const cov = computed(() => data.value.coverage || {});
const fx = computed(() => data.value.fx || {});
const fr = computed(() => data.value.freight || {});
const unverifiedCurrencies = computed(() => {
  const s = new Set((fx.value.unverified || []).map((x) => x.cur));
  return [...s].join(", ");
});

async function load() {
  loading.value = true;
  try { data.value = await api.call("accounting_portal.api.landed_engine.costing_health", { company: currentCompany() }) || {}; }
  catch { data.value = {}; }
  finally { loading.value = false; }
}
load();
watch(entityId, load);
</script>
