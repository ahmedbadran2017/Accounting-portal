<template>
  <div class="space-y-3.5">
    <!-- what this is, in one breath -->
    <div class="rounded-[14px] px-4 py-3 border border-line bg-white shadow-card">
      <div class="text-[13px] font-bold">{{ L("The group's result for the period, from the ledger", "نتيجة المجموعة للفترة — من الدفاتر مباشرة", "Résultat du groupe sur la période") }}</div>
      <div class="text-[11.5px] text-ink-2 mt-0.5 leading-relaxed">
        {{ L("Sales − (opening stock + purchases − closing stock) − expenses. Goods enter at what the group paid outside; sales and receipts between Morocco, Türkiye and China are left out. No sale is priced one by one, so the only judgement here is the value of the stock.",
             "المبيعات − (مخزون أول المدة + المشتريات − مخزون آخر المدة) − المصروفات. البضاعة داخلة بالسعر اللي المجموعة دفعته لموردين من بره، والتعاملات بين المغرب وتركيا والصين مستبعدة. مفيش تسعير لكل بيعة، فالحاجة الوحيدة اللي محتاجة تأكيد هي قيمة المخزون.",
             "Ventes − (stock initial + achats − stock final) − charges. Les flux intragroupe sont exclus.") }}
      </div>
    </div>

    <!-- controls -->
    <div class="flex items-center gap-2 flex-wrap">
      <select id="cp-year" v-model.number="year" @change="load()" class="fld fld-sm" :aria-label="L('Year','السنة','Année')">
        <option v-for="y in years" :key="y" :value="y">{{ y }}</option>
      </select>
      <select id="cp-from" v-model.number="fromM" @change="load()" class="fld fld-sm" :aria-label="L('From','من','Du')">
        <option v-for="m in 12" :key="m" :value="m">{{ monthName(m) }}</option>
      </select>
      <span class="text-[12px] text-ink-muted">→</span>
      <select id="cp-to" v-model.number="toM" @change="load()" class="fld fld-sm" :aria-label="L('To','إلى','Au')">
        <option v-for="m in 12" :key="m" :value="m" :disabled="m < fromM">{{ monthName(m) }}</option>
      </select>
      <div class="flex rounded-[8px] border border-line overflow-hidden">
        <button v-for="v in [1, 0]" :key="v" @click="vat = v; load()" class="h-[30px] px-3 text-[12px] font-bold"
                :class="vat === v ? 'bg-accent text-white' : 'bg-white text-ink-muted'">
          {{ v ? L("Incl. VAT", "شامل الضريبة", "TTC") : L("Excl. VAT", "بدون الضريبة", "HT") }}
        </button>
      </div>
      <div class="flex rounded-[8px] border border-line overflow-hidden">
        <button v-for="c in ['MAD', 'USD']" :key="c" @click="ccy = c" class="h-[30px] px-3 text-[12px] font-bold"
                :class="ccy === c ? 'bg-accent text-white' : 'bg-white text-ink-muted'">{{ c }}</button>
      </div>
      <button class="ms-auto text-[11.5px] font-semibold text-accent hover:underline" @click="load(true)">{{ L("Refresh", "تحديث", "Actualiser") }}</button>
    </div>

    <div v-if="loading" class="py-16 text-center text-[12px] text-ink-muted">{{ L("Reading the ledger…", "جاري قراءة الدفاتر…", "Lecture du grand livre…") }}</div>
    <div v-else-if="err" class="py-16 text-center text-[12px]" style="color:#b91c1c">{{ err }}</div>

    <template v-else-if="d">
      <!-- headline -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div class="kpi"><div class="lab">{{ L("Sales", "المبيعات", "Ventes") }}</div><div class="big tnum" dir="ltr">{{ m(d.sales.total) }}</div>
          <div class="sub tnum" dir="ltr">{{ m(d.sales.total / d.months) }} {{ L("a month", "في الشهر", "/ mois") }}</div></div>
        <div class="kpi"><div class="lab">{{ L("Gross margin", "هامش الربح الإجمالي", "Marge brute") }}</div><div class="big tnum" dir="ltr">{{ pct(d.gross, d.sales.total) }}</div>
          <div class="sub tnum" dir="ltr">{{ m(d.gross) }}</div></div>
        <div class="kpi"><div class="lab">{{ L("Expenses", "المصروفات", "Charges") }}</div><div class="big tnum" dir="ltr">{{ m(d.expenses_total) }}</div>
          <div class="sub tnum" dir="ltr">{{ m(d.expenses_total / d.months) }} {{ L("a month", "في الشهر", "/ mois") }}</div></div>
        <div class="kpi"><div class="lab">{{ L("Net result", "صافي النتيجة", "Résultat net") }}</div>
          <div class="big tnum" :style="d.net < 0 ? 'color:#b91c1c' : 'color:#047857'" dir="ltr">{{ m(d.net) }}</div>
          <div class="sub tnum" dir="ltr">{{ m(d.net / d.months) }} {{ L("a month", "في الشهر", "/ mois") }}</div></div>
      </div>

      <div class="grid lg:grid-cols-[1.35fr_1fr] gap-3.5 items-start">
        <!-- the statement -->
        <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
          <div class="px-4 py-3 border-b border-line-hair flex items-baseline gap-2">
            <span class="text-[13px] font-bold">{{ L("Statement", "القائمة", "Compte de résultat") }}</span>
            <span class="text-[11px] text-ink-muted">{{ monthName(d.from_month) }}–{{ monthName(d.to_month) }} {{ d.year }} · {{ ccy }} · {{ d.vat ? L("incl. VAT", "شامل الضريبة", "TTC") : L("excl. VAT", "بدون الضريبة", "HT") }}</span>
          </div>
          <table class="w-full text-[12.5px]">
            <tbody>
              <tr class="sec"><td colspan="2">{{ L("Sales", "المبيعات", "Ventes") }}</td></tr>
              <tr><td class="lbl">{{ L("Sales net of VAT", "المبيعات بدون الضريبة", "Ventes HT") }}</td><td class="num">{{ m(d.sales.net) }}</td></tr>
              <tr v-if="d.vat"><td class="lbl">{{ L("VAT collected from customers", "الضريبة المحصّلة من العملاء", "TVA collectée") }}</td><td class="num">{{ m(d.sales.vat) }}</td></tr>
              <tr class="tot"><td>{{ L("Total sales", "إجمالي المبيعات", "Total ventes") }}</td><td class="num">{{ m(d.sales.total) }}</td></tr>

              <tr class="sec"><td colspan="2">{{ L("Cost of what was sold", "تكلفة اللي اتباع", "Coût des ventes") }}</td></tr>
              <tr class="clickable" @click="open.stock = !open.stock"><td class="lbl">{{ open.stock ? "▾" : "▸" }} {{ L("Opening stock", "مخزون أول المدة", "Stock initial") }}</td><td class="num">{{ m(d.stock.open) }}</td></tr>
              <tr class="clickable" @click="open.buy = !open.buy"><td class="lbl">{{ open.buy ? "▾" : "▸" }} + {{ L("Purchases", "المشتريات", "Achats") }}</td><td class="num">{{ m(d.purchases.total) }}</td></tr>
              <template v-if="open.buy">
                <tr v-for="g in d.purchases.goods" :key="g.key" class="sub-row"><td class="lbl">{{ g.label }}</td><td class="num">{{ m(g.amount) }}</td></tr>
                <tr v-for="f in d.purchases.freight" :key="f.key" class="sub-row"><td class="lbl">{{ f.label }}</td><td class="num">{{ m(f.amount) }}</td></tr>
                <tr v-if="d.vat" class="sub-row"><td class="lbl">{{ L("VAT paid to suppliers", "الضريبة المدفوعة للموردين", "TVA payée aux fournisseurs") }}</td><td class="num">{{ m(d.purchases.vat_in) }}</td></tr>
              </template>
              <tr class="clickable" @click="open.stock = !open.stock"><td class="lbl">{{ open.stock ? "▾" : "▸" }} − {{ L("Closing stock", "مخزون آخر المدة", "Stock final") }}</td><td class="num">{{ m(-d.stock.close) }}</td></tr>
              <template v-if="open.stock">
                <tr v-for="s in d.stock.lines" :key="s.key" class="sub-row">
                  <td class="lbl">{{ s.label }} <span class="text-ink-muted" dir="ltr">({{ s.currency }} {{ n(s.open_own) }} → {{ n(s.close_own) }})</span></td>
                  <td class="num">{{ m(s.close - s.open) }}</td>
                </tr>
              </template>
              <tr class="tot"><td>{{ L("Cost of goods sold", "تكلفة البضاعة المباعة", "Coût des marchandises vendues") }} <span class="pc">{{ pct(d.cogs, d.sales.total) }}</span></td><td class="num">{{ m(d.cogs) }}</td></tr>
              <tr class="grand"><td>{{ L("Gross profit", "مجمل الربح", "Marge brute") }} <span class="pc">{{ pct(d.gross, d.sales.total) }}</span></td><td class="num" :class="d.gross < 0 ? 'neg' : ''">{{ m(d.gross) }}</td></tr>

              <tr class="sec"><td colspan="2">{{ L("Expenses", "المصروفات", "Charges") }}</td></tr>
              <tr v-for="x in d.expenses" :key="x.key">
                <td class="lbl">{{ x.label }}
                  <span v-if="x.turkiye" class="text-[10.5px] text-ink-muted" dir="ltr">· {{ L("MA", "المغرب", "MA") }} {{ m(x.morocco) }} · {{ L("TR", "تركيا", "TR") }} {{ m(x.turkiye) }}</span></td>
                <td class="num">{{ m(-x.amount) }}</td>
              </tr>
              <tr v-if="d.other_income"><td class="lbl">{{ L("Sub-lease income", "إيراد تأجير من الباطن", "Sous-location") }}</td><td class="num">{{ m(d.other_income) }}</td></tr>
              <tr class="grand"><td>{{ L("Operating result", "نتيجة النشاط", "Résultat d'exploitation") }}</td><td class="num" :class="d.operating < 0 ? 'neg' : ''">{{ m(d.operating) }}</td></tr>
              <tr v-for="b in d.below" :key="b.key"><td class="lbl">{{ b.label }}</td><td class="num">{{ m(b.amount) }}</td></tr>
              <tr class="grand"><td>{{ L("Net result", "صافي النتيجة", "Résultat net") }}</td><td class="num" :class="d.net < 0 ? 'neg' : ''">{{ m(d.net) }}</td></tr>
            </tbody>
          </table>
        </div>

        <div class="space-y-3.5">
          <!-- the ladder: where it turns -->
          <div class="bg-white border border-line rounded-[14px] shadow-card p-4">
            <div class="text-[13px] font-bold mb-1">{{ L("Where the result turns", "النتيجة بتتقلب فين", "Où le résultat bascule") }}</div>
            <div class="text-[11px] text-ink-muted mb-3">{{ L("Each step adds one group of costs.", "كل خطوة بتضيف مجموعة تكاليف.", "Chaque étape ajoute un groupe de coûts.") }}</div>
            <div v-for="s in d.ladder" :key="s.key" class="flex items-center gap-3 py-1.5 border-b border-line-hair last:border-0">
              <div class="flex-1 text-[12px]">{{ s.label }}</div>
              <div class="w-28 h-2 rounded-full bg-app-warm relative overflow-hidden">
                <div class="absolute top-0 h-2 rounded-full" :style="barStyle(s.amount)"></div>
              </div>
              <div class="w-24 text-end text-[12px] font-semibold tnum" :class="s.amount < 0 ? 'neg' : ''" dir="ltr">{{ m(s.amount) }}</div>
            </div>
          </div>

          <!-- how far to trust it -->
          <div class="bg-white border border-line rounded-[14px] shadow-card p-4">
            <div class="text-[13px] font-bold mb-2">{{ L("How far to trust these figures", "الأرقام دي موثوقة لأي درجة", "Fiabilité") }}</div>
            <div v-for="(f, i) in d.flags" :key="i" class="flex gap-2 text-[11.5px] leading-relaxed py-1">
              <span class="mt-[5px] w-2 h-2 rounded-full shrink-0" :style="f.level === 'warn' ? 'background:#b45309' : 'background:#64748b'"></span>
              <span>{{ f.text }}</span>
            </div>
          </div>

          <!-- what is left out -->
          <div class="bg-white border border-line rounded-[14px] shadow-card p-4">
            <div class="text-[13px] font-bold mb-2">{{ L("Left out on purpose", "مستبعد عن قصد", "Exclu volontairement") }}</div>
            <div class="text-[11.5px] space-y-1">
              <div class="flex justify-between gap-3"><span>{{ L("Sales between group companies (Türkiye → Morocco)", "مبيعات بين شركات المجموعة (تركيا ← المغرب)", "Ventes intragroupe") }}</span><span class="tnum" dir="ltr">{{ m(d.excluded.intercompany_revenue) }}</span></div>
              <div class="flex justify-between gap-3"><span>{{ L("Cost of goods as booked (replaced by the stock movement)", "تكلفة البضاعة المسجّلة (بدلها حركة المخزون)", "Coût comptabilisé (remplacé)") }}</span><span class="tnum" dir="ltr">{{ m(d.excluded.booked_cost_of_goods) }}</span></div>
              <div v-if="d.excluded.nonsale_vat_recovery" class="flex justify-between gap-3"><span>{{ L("VAT recovery booked as sales", "استرداد ضريبة متسجّل كمبيعات", "Récupération TVA en ventes") }}</span><span class="tnum" dir="ltr">{{ m(d.excluded.nonsale_vat_recovery) }}</span></div>
              <div v-if="d.excluded.owner_private" class="flex justify-between gap-3"><span>{{ L("Owner's private items / “no effect” invoices", "مصاريف شخصية للمالك / فواتير «بدون أثر»", "Privé / sans effet") }}</span><span class="tnum" dir="ltr">{{ m(d.excluded.owner_private) }}</span></div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
// The owner's reading of the period: what came in, what is left, what was spent.
// Built because three screens disagreed — see api/clear_pnl.py for why.
import { ref, reactive, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import api from "@/services/api";

const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const now = new Date();
const years = [now.getFullYear(), now.getFullYear() - 1];
const year = ref(now.getFullYear());
const fromM = ref(1);
const toM = ref(Math.max(1, now.getMonth()));      // last complete month
const vat = ref(1);
const ccy = ref("MAD");
const loading = ref(true);
const err = ref("");
const d = ref(null);
const open = reactive({ buy: true, stock: false });

const MONTHS = { en: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
                 ar: ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"],
                 fr: ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."] };
const monthName = (i) => (MONTHS[locale.value] || MONTHS.en)[i - 1];

const n = (v) => Math.round(v || 0).toLocaleString("en-US");
function m(v) {
  const x = ccy.value === "USD" ? (v || 0) * (d.value?.usd_rate || 0.105263) : (v || 0);
  const s = Math.abs(x) >= 1e6 ? (Math.abs(x) / 1e6).toFixed(2) + "M" : Math.round(Math.abs(x)).toLocaleString("en-US");
  return (x < 0 ? "(" : "") + (ccy.value === "USD" ? "$" : "") + s + (x < 0 ? ")" : "");
}
const pct = (a, b) => (b ? (100 * a / b).toFixed(1) + "%" : "—");
function barStyle(v) {
  const max = Math.max(...(d.value?.ladder || []).map((s) => Math.abs(s.amount)), 1);
  const w = Math.min(50, 50 * Math.abs(v) / max);
  return v >= 0 ? `left:50%;width:${w}%;background:#0f6e66` : `right:50%;width:${w}%;background:#b4322a`;
}

async function load(fresh = false) {
  if (toM.value < fromM.value) toM.value = fromM.value;
  loading.value = true; err.value = "";
  try {
    d.value = await api.call("accounting_portal.api.clear_pnl.clear_pnl",
      { year: year.value, from_month: fromM.value, to_month: toM.value, vat: vat.value, fresh: fresh ? 1 : 0 }, { fresh: true });
  } catch (e) { err.value = (e && e.message) || String(e); }
  finally { loading.value = false; }
}
onMounted(() => load());
</script>

<style scoped>
.kpi{background:#fff;border:1px solid var(--tw-border, #e8e2da);border-radius:14px;padding:12px 16px;box-shadow:0 1px 2px rgba(0,0,0,.04)}
.lab{font-size:10px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#9a8f86}
.big{font-size:19px;font-weight:800;margin-top:2px}
.sub{font-size:11px;color:#8a8178}
.tnum,.num{font-variant-numeric:tabular-nums}
td{padding:6px 16px;border-bottom:1px solid #f1ede7}
td.num{text-align:end;white-space:nowrap;direction:ltr}
td.lbl{color:#3d3a36}
tr.sec td{background:#faf8f5;font-size:10.5px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#8a8178;padding-top:9px}
tr.sub-row td{font-size:11.5px;color:#6b665f;padding-top:4px;padding-bottom:4px}
tr.sub-row td.lbl{padding-inline-start:32px}
tr.tot td{font-weight:700;border-top:1px solid #d9d2c7}
tr.grand td{font-weight:800;font-size:13.5px;border-top:1.5px solid #1d2433;border-bottom:1.5px solid #1d2433}
tr.clickable{cursor:pointer} tr.clickable:hover td{background:#fbfaf7}
.pc{font-size:11px;font-weight:600;color:#8a8178;margin-inline-start:6px}
.neg{color:#b91c1c}
</style>
