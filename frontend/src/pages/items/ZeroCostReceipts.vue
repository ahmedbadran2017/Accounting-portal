<template>
  <div class="space-y-3.5">
    <!-- what this queue is, and that the leak is already stopped -->
    <div class="rounded-[14px] px-4 py-3 border" style="background:#f0fdf4;border-color:#bbf7d0">
      <div class="text-[12px] font-bold" style="color:#166534">
        {{ L("The leak is already stopped — this is the clean-up of what got in before",
             "النزيف اتقفل خلاص — دي مراجعة اللي دخل قبل كده",
             "La fuite est déjà stoppée — nettoyage de l'existant") }}
      </div>
      <div class="text-[11px] mt-0.5" style="color:#15803d">
        {{ L("Warehouse staff keyed Material Receipts and left the rate at zero, so goods entered stock at nil value — diluting the moving average and understating COGS on every sale that drew from them. The entry guard now blocks new ones. Below, each item is priced at the same modelled landed cost the P&L uses. Nothing is posted from this screen.",
             "موظفو المخزن كانوا بيسجلوا استلامات ويسيبوا السعر صفر، فالبضاعة دخلت المخزون بقيمة صفر — بتخفّض متوسط التكلفة وبتقلّل الـCOGS في كل بيعة سحبت منها. الحارس دلوقتي بيمنع الجديد. تحت، كل صنف متسعّر بتكلفة النموذج نفسها اللي بيستخدمها الـP&L. مفيش أي ترحيل من الشاشة دي.",
             "Le personnel de l'entrepôt a saisi des réceptions à taux nul. Le garde bloque désormais les nouvelles. Rien n'est comptabilisé ici.") }}
      </div>
    </div>

    <div v-if="loading" class="py-16 text-center text-[12px] text-ink-muted">{{ L("Loading…","جاري التحميل…","Chargement…") }}</div>
    <div v-else-if="err" class="py-16 text-center text-[12px]" style="color:#b91c1c">{{ err }}</div>

    <template v-else>
      <!-- the size of the hole -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div class="bg-white border border-line rounded-[14px] shadow-card px-4 py-3">
          <div class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Still on hand","لسه في المخزن","Encore en stock") }}</div>
          <div class="text-[18px] font-extrabold tnum" style="color:#047857" dir="ltr">{{ money(s.onhand_value) }}</div>
          <div class="text-[10.5px] text-ink-muted tnum" dir="ltr">{{ n(s.onhand_units) }} {{ L("units","قطعة","u") }} · {{ L("cheap reprice","إعادة تسعير سهلة","reprix simple") }}</div>
        </div>
        <div class="bg-white border border-line rounded-[14px] shadow-card px-4 py-3">
          <div class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Already sold","اتباع خلاص","Déjà vendu") }}</div>
          <div class="text-[18px] font-extrabold tnum" style="color:#b45309" dir="ltr">{{ money(s.sold_value) }}</div>
          <div class="text-[10.5px] text-ink-muted tnum" dir="ltr">{{ n(s.sold_units) }} {{ L("units","قطعة","u") }} · {{ L("historical COGS","COGS تاريخية","COGS histor.") }}</div>
        </div>
        <div class="bg-white border border-line rounded-[14px] shadow-card px-4 py-3">
          <div class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Total not booked","إجمالي غير محسوب","Total non comptab.") }}</div>
          <div class="text-[18px] font-extrabold tnum" dir="ltr">{{ money(s.total_value) }}</div>
          <div class="text-[10.5px] text-ink-muted tnum" dir="ltr">{{ n(s.total_units) }} {{ L("units","قطعة","u") }}</div>
        </div>
        <div class="bg-white border border-line rounded-[14px] shadow-card px-4 py-3">
          <div class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Items with no cost","أصناف بلا تكلفة","Sans coût") }}</div>
          <div class="text-[18px] font-extrabold tnum" :style="s.no_cost_items ? 'color:#b91c1c' : ''" dir="ltr">{{ n(s.no_cost_items) }}</div>
          <div class="text-[10.5px] text-ink-muted">{{ L("need a manual price","محتاجة تسعير يدوي","prix manuel requis") }}</div>
        </div>
      </div>

      <!-- the queue -->
      <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
        <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2 flex-wrap">
          <span class="text-[13px] font-bold">{{ L("Zero-cost receipts by item","الاستلامات الصفرية حسب الصنف","Réceptions par article") }}</span>
          <span class="text-[10.5px] text-ink-muted">{{ n(d.rows.length) }} {{ L("items","صنف","articles") }}</span>
          <div class="flex-1"></div>
          <label class="flex items-center gap-1.5 text-[11px] text-ink-muted cursor-pointer">
            <input type="checkbox" v-model="hidePriced" class="accent-emerald-600" />
            {{ L("only items needing a price","اللي محتاج تسعير بس","à tarifer") }}
          </label>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-[11.5px]">
            <thead><tr style="background:#fafaf9">
              <th class="px-3 py-2 text-start text-[10px] font-bold text-ink-muted">{{ L("Item","الصنف","Article") }}</th>
              <th class="px-3 py-2 text-center text-[10px] font-bold text-ink-muted">{{ L("Receipts","استلامات","Réceptions") }}</th>
              <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("Zero qty","كمية بصفر","Qté nulle") }}</th>
              <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("On hand","في المخزن","En stock") }}</th>
              <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("Sold","مباع","Vendu") }}</th>
              <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("Model rate","سعر النموذج","Coût modèle") }}</th>
              <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("On-hand value","قيمة المخزون","Valeur stock") }}</th>
              <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("Sold value","قيمة المباع","Valeur vendu") }}</th>
            </tr></thead>
            <tbody>
              <tr v-for="r in shown" :key="r.item_code" class="border-t border-line-hair hover:bg-[#fafaf9]">
                <td class="px-3 py-2">
                  <div class="font-bold truncate max-w-[240px]">{{ r.item_name || r.item_code }}</div>
                  <div class="text-[9.5px] text-ink-muted tnum" dir="ltr">{{ r.item_code }} · {{ r.first_date }}→{{ r.last_date }}</div>
                </td>
                <td class="px-3 py-2 text-center tnum" dir="ltr">{{ r.docs }}<span class="text-ink-muted">/{{ r.lines }}</span></td>
                <td class="px-3 py-2 text-end tnum" dir="ltr">{{ n(r.zero_qty) }}</td>
                <td class="px-3 py-2 text-end tnum" dir="ltr">{{ n(r.on_hand) }}</td>
                <td class="px-3 py-2 text-end tnum text-ink-muted" dir="ltr">{{ n(r.sold) }}</td>
                <td class="px-3 py-2 text-end tnum" dir="ltr">
                  <span v-if="r.model_rate">{{ money(r.model_rate) }}</span>
                  <span v-else class="text-[9.5px] font-bold px-1.5 py-0.5 rounded-full" style="background:#fef2f2;color:#b91c1c">{{ L("no cost","بلا تكلفة","sans coût") }}</span>
                </td>
                <td class="px-3 py-2 text-end tnum font-bold" :style="r.onhand_value ? 'color:#047857' : ''" dir="ltr">{{ r.onhand_value ? money(r.onhand_value) : "—" }}</td>
                <td class="px-3 py-2 text-end tnum" :style="r.sold_value ? 'color:#b45309' : ''" dir="ltr">{{ r.sold_value ? money(r.sold_value) : "—" }}</td>
              </tr>
              <tr v-if="!shown.length"><td colspan="8" class="px-3 py-8 text-center text-ink-muted">—</td></tr>
            </tbody>
          </table>
        </div>
        <div class="px-4 py-2.5 border-t border-line-hair text-[10.5px] text-ink-muted">
          {{ L("Priced against the modelled landed cost — verified against " + (s.model_verified||0) + " team-checked items, calibration " + (s.model_factor||1) + ". The reprice itself runs through the Valuation Doctor once this list is agreed.",
               "متسعّر بتكلفة النموذج — معايَر على " + (s.model_verified||0) + " صنف متحقق منها، معامل " + (s.model_factor||1) + ". إعادة التسعير نفسها بتتم من خلال Valuation Doctor بعد الاتفاق على القايمة.",
               "Évalué au coût modélisé.") }}
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from "vue";
import { useI18n } from "vue-i18n";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { fmtAmount } from "@/utils/helpers";

const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const money = (x) => fmtAmount(x);
const n = (x) => (x === null || x === undefined ? "—" : Math.round(x).toLocaleString("en-US"));

const loading = ref(true);
const err = ref("");
const d = ref({ rows: [] });
const s = ref({});
const hidePriced = ref(false);

const shown = computed(() =>
  hidePriced.value ? d.value.rows.filter((r) => r.flag === "no_cost") : d.value.rows);

async function load() {
  loading.value = true; err.value = "";
  try {
    const r = await api.call("accounting_portal.api.valuation.zero_cost_receipts_review",
      { company: currentCompany.value }, { fresh: true });
    d.value = r || { rows: [] };
    s.value = (r && r.summary) || {};
  } catch (e) {
    err.value = (e && e.message) || String(e);
  } finally {
    loading.value = false;
  }
}
onMounted(load);
watch(currentCompany, load);
</script>
