<template>
  <div class="space-y-3.5">
    <!-- what this lens is -->
    <div class="rounded-[14px] px-4 py-3 border" style="background:#eff6ff;border-color:#bfdbfe">
      <div class="text-[12px] font-bold" style="color:#1e40af">
        {{ L("Group P&L on the corrected cost basis","قائمة دخل المجموعة على أساس التكلفة المصحّحة","P&L groupe — coût corrigé") }}
      </div>
      <div class="text-[11px] mt-0.5" style="color:#1d4ed8">
        {{ L("The Holding is a reading lens (no GL rows of its own). Cost of goods is the modelled landed cost, so every month reads true — the booked figure folds in stock-adjustment repost noise and swings wildly. The books converge to this as the cost correction lands.",
             "الهولدينج عدسة قراءة (مالوش قيود). تكلفة البضاعة محسوبة، فكل شهر يقرأ صح — الرقم المرحّل بيخلط ضوضاء تسويات المخزون ويتأرجح. الدفاتر بتتقارب مع اكتمال التصحيح.",
             "Le Holding est une lentille de lecture ; coût modélisé.") }}
      </div>
    </div>

    <div class="flex items-center gap-2 flex-wrap">
      <select v-model.number="year" @change="load" class="h-[30px] px-2 rounded-[8px] border border-line text-[12px] bg-white">
        <option v-for="y in years" :key="y" :value="y">{{ y }}</option>
      </select>
      <div class="flex rounded-[8px] border border-line overflow-hidden">
        <button v-for="c in ['USD','MAD']" :key="c" @click="ccy=c;load()"
                class="h-[30px] px-3 text-[12px] font-bold" :class="ccy===c ? 'bg-accent text-white' : 'bg-white text-ink-muted'">{{ c }}</button>
      </div>
      <span v-if="d.model" class="text-[10.5px] text-ink-muted">{{ L("model","النموذج","modèle") }}: {{ d.model.verified }} {{ L("verified","متحقق","vérifiés") }} · ×{{ d.model.factor }}</span>
    </div>

    <div v-if="loading" class="py-16 text-center text-[12px] text-ink-muted">{{ L("Loading…","جاري التحميل…","Chargement…") }}</div>
    <div v-else-if="err" class="py-16 text-center text-[12px]" style="color:#b91c1c">{{ err }}</div>

    <template v-else>
      <!-- totals -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div class="bg-white border border-line rounded-[14px] shadow-card px-4 py-3">
          <div class="lab">{{ L("Revenue","الإيراد","Revenu") }}</div>
          <div class="big tnum" dir="ltr">{{ money(t.revenue) }}</div>
        </div>
        <div class="bg-white border border-line rounded-[14px] shadow-card px-4 py-3">
          <div class="lab">{{ L("Gross margin","مجمل الربح","Marge brute") }}</div>
          <div class="big tnum" dir="ltr">{{ money(t.gross) }}</div>
          <div class="text-[10.5px] text-ink-muted tnum" dir="ltr">{{ t.gm_pct }}%</div>
        </div>
        <div class="bg-white border border-line rounded-[14px] shadow-card px-4 py-3">
          <div class="lab">{{ L("Operating costs","المصاريف","Charges") }}</div>
          <div class="big tnum" dir="ltr">{{ money(t.opex) }}</div>
        </div>
        <div class="bg-white border border-line rounded-[14px] shadow-card px-4 py-3">
          <div class="lab">{{ L("Net","الصافي","Net") }}</div>
          <div class="big tnum" :style="t.net<0 ? 'color:#b91c1c' : 'color:#047857'" dir="ltr">{{ money(t.net) }}</div>
        </div>
      </div>

      <!-- monthly statement -->
      <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
        <div class="px-4 py-3 border-b border-line-hair text-[13px] font-bold">
          {{ L("Month by month","شهر بشهر","Mois par mois") }}
          <span class="text-[10.5px] font-normal text-ink-muted">— {{ d.ccy }}</span>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-[11.5px]">
            <thead><tr style="background:#fafaf9">
              <th class="px-3 py-2 text-start th">{{ L("Month","الشهر","Mois") }}</th>
              <th class="px-3 py-2 text-end th">{{ L("Revenue","إيراد","Revenu") }}</th>
              <th class="px-3 py-2 text-end th">{{ L("COGS","التكلفة","CMV") }}</th>
              <th class="px-3 py-2 text-end th">{{ L("GM %","هامش%","MB%") }}</th>
              <th class="px-3 py-2 text-end th">{{ L("Opex","مصاريف","Charges") }}</th>
              <th class="px-3 py-2 text-end th">{{ L("Net","صافي","Net") }}</th>
              <th class="px-3 py-2 text-end th" :title="L('booked COGS for comparison','التكلفة المرحّلة للمقارنة','CMV comptable')">{{ L("vs booked","مقابل المرحّل","vs compt.") }}</th>
            </tr></thead>
            <tbody>
              <tr v-for="r in d.rows" :key="r.month" class="border-t border-line-hair">
                <td class="px-3 py-2 font-bold tnum" dir="ltr">{{ r.month }}</td>
                <td class="px-3 py-2 text-end tnum" dir="ltr">{{ money(r.revenue) }}</td>
                <td class="px-3 py-2 text-end tnum" dir="ltr">{{ money(r.cogs) }}</td>
                <td class="px-3 py-2 text-end tnum font-bold" :style="r.gm_pct<20 ? 'color:#b45309' : 'color:#047857'" dir="ltr">{{ r.gm_pct }}%</td>
                <td class="px-3 py-2 text-end tnum text-ink-muted" dir="ltr">{{ money(r.opex) }}</td>
                <td class="px-3 py-2 text-end tnum font-bold" :style="r.net<0 ? 'color:#b91c1c' : 'color:#047857'" dir="ltr">{{ money(r.net) }}</td>
                <td class="px-3 py-2 text-end tnum text-[10px]" style="color:#9a8f86" dir="ltr">
                  {{ money(r.cogs_booked) }}
                  <span v-if="r.cogs_booked" :style="Math.abs(r.cogs_booked-r.cogs) > r.cogs*0.15 ? 'color:#b45309' : ''"> ({{ pct(r.cogs_booked, r.revenue) }}%)</span>
                </td>
              </tr>
              <tr class="border-t border-line" style="background:#fafaf9">
                <td class="px-3 py-2 font-extrabold">{{ L("Total","الإجمالي","Total") }}</td>
                <td class="px-3 py-2 text-end tnum font-extrabold" dir="ltr">{{ money(t.revenue) }}</td>
                <td class="px-3 py-2 text-end tnum font-extrabold" dir="ltr">{{ money(t.cogs) }}</td>
                <td class="px-3 py-2 text-end tnum font-extrabold" dir="ltr">{{ t.gm_pct }}%</td>
                <td class="px-3 py-2 text-end tnum font-extrabold" dir="ltr">{{ money(t.opex) }}</td>
                <td class="px-3 py-2 text-end tnum font-extrabold" :style="t.net<0 ? 'color:#b91c1c' : 'color:#047857'" dir="ltr">{{ money(t.net) }}</td>
                <td class="px-3 py-2 text-end tnum text-[10px]" style="color:#9a8f86" dir="ltr">{{ money(t.cogs_booked) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- opex by company + eliminations -->
      <div class="grid lg:grid-cols-2 gap-3">
        <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
          <div class="px-4 py-2.5 border-b border-line-hair text-[12px] font-bold">{{ L("Operating costs by entity","المصاريف حسب الكيان","Charges par entité") }}</div>
          <table class="w-full text-[11.5px]">
            <tbody>
              <tr v-for="(v,co) in d.opex_by_company" :key="co" class="border-t border-line-hair">
                <td class="px-4 py-1.5">{{ co }} <span class="text-[10px] text-ink-muted">({{ d.roles[co] }})</span></td>
                <td class="px-4 py-1.5 text-end tnum" dir="ltr">{{ money(v) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="bg-white border rounded-[14px] shadow-card overflow-hidden" style="border-color:#fde68a">
          <div class="px-4 py-2.5 border-b text-[12px] font-bold" style="border-color:#fde68a;background:#fffbeb">
            {{ L("Eliminated (intercompany, disclosed)","المُقصى (بين الشركات، مُفصح)","Éliminé (intragroupe)") }}
          </div>
          <table class="w-full text-[11.5px]">
            <tbody>
              <tr v-for="(v,co) in d.eliminated" :key="co" class="border-t border-line-hair">
                <td class="px-4 py-1.5">{{ co }}</td>
                <td class="px-4 py-1.5 text-end tnum text-ink-muted" dir="ltr">
                  {{ L("rev","إيراد","rev") }} {{ money(v.revenue) }} · {{ L("cost","تكلفة","coût") }} {{ money(v.ic_cost) }}
                </td>
              </tr>
              <tr v-if="!d.eliminated || !Object.keys(d.eliminated).length"><td class="px-4 py-4 text-center text-ink-muted">—</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import api from "@/services/api";
import { fmtAmount } from "@/utils/helpers";

const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const money = (n) => fmtAmount(n);
const pct = (a, b) => (b ? Math.round(100 * (b - a) / b) : 0);

const now = new Date().getFullYear();
const years = [now, now - 1];
const year = ref(now);
const ccy = ref("USD");
const loading = ref(true);
const err = ref("");
const d = ref({ rows: [], total: {}, opex_by_company: {}, eliminated: {}, roles: {} });
const t = computed(() => d.value.total || {});

async function load() {
  loading.value = true; err.value = "";
  try {
    d.value = await api.call("accounting_portal.api.group_pnl.group_pnl_corrected",
      { year: year.value, ccy: ccy.value }, { fresh: true });
  } catch (e) { err.value = (e && e.message) || String(e); }
  finally { loading.value = false; }
}
onMounted(load);
</script>

<style scoped>
.lab{font-size:10px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#9a8f86}
.big{font-size:18px;font-weight:800}
.th{font-size:10px;font-weight:700;color:#9a8f86}
.tnum{font-variant-numeric:tabular-nums}
</style>
