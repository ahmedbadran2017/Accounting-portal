<template>
  <div class="space-y-3.5">
    <!-- said before a single number is read -->
    <div class="rounded-[14px] px-4 py-3 border" style="background:#fef2f2;border-color:#fecaca">
      <div class="text-[12px] font-bold" style="color:#991b1b">
        {{ L("Estimated — management view only","تقديري — للقراءة الإدارية فقط","Estimé — vue de gestion") }}
      </div>
      <div class="text-[11px] mt-0.5" style="color:#b91c1c">
        {{ L("Cost of goods here is modelled, not booked. Do not use for tax filings, the bank, or an investor. Nothing on this page posts to the ledger.",
             "تكلفة البضاعة هنا محسوبة بنموذج مش مأخوذة من الدفاتر. ماتستخدمش الصفحة دي لإقرار ضريبي أو بنك أو مستثمر. مفيش أي قيد بيتسجل من هنا.",
             "Le coût des marchandises est modélisé. Ne pas utiliser pour le fisc, la banque ou un investisseur.") }}
      </div>
    </div>

    <div class="flex items-center gap-1 bg-white border border-line rounded-chip p-1 w-fit">
      <button v-for="o in scopes" :key="o.k" class="px-3 py-1.5 rounded-lg text-[12px] whitespace-nowrap"
              :class="scope === o.k ? 'text-accent-dark font-semibold bg-app-warm shadow-card' : 'text-ink-3 font-medium hover:text-ink'"
              @click="setScope(o.k)">{{ o.label }}</button>
    </div>

    <div v-if="loading" class="py-16 text-center text-[12px] text-ink-muted">{{ L("Loading…","جاري التحميل…","Chargement…") }}</div>
    <div v-else-if="err" class="py-16 text-center text-[12px]" style="color:#b91c1c">{{ err }}</div>

    <template v-else-if="d">
      <!-- headline -->
      <div class="grid gap-2.5" style="grid-template-columns:repeat(auto-fit,minmax(160px,1fr))">
        <div v-for="s in stats" :key="s.k" class="bg-white border border-line rounded-[14px] shadow-card px-4 py-3">
          <div class="text-[10px] font-bold text-ink-muted uppercase tracking-wide">{{ s.label }}</div>
          <div class="text-[19px] font-bold tnum mt-0.5" :class="s.tone" dir="ltr">{{ s.v }}</div>
          <div v-if="s.sub" class="text-[10.5px] text-ink-muted mt-0.5">{{ s.sub }}</div>
        </div>
      </div>

      <!-- how the cost was built -->
      <div class="bg-white border border-line rounded-[14px] shadow-card px-4 py-3">
        <div class="flex items-center justify-between gap-3 flex-wrap">
          <div>
            <div class="text-[12px] font-bold">{{ L("How the cost is modelled","التكلفة محسوبة إزاي","Modèle de coût") }}</div>
            <div class="text-[11px] text-ink-3 mt-1 font-mono" dir="ltr">
              ({{ L("product cost from its own supplier invoice, at that invoice's FX rate","تكلفة المنتج من فاتورته بسعر صرف يومها","coût produit à son propre taux") }})
              + ({{ L("weight","الوزن","poids") }} × {{ d.model.freight_per_kg }} MAD/kg)
              × {{ d.model.factor }}
            </div>
          </div>
          <div class="text-[10.5px] text-ink-muted text-end">
            <div>{{ L("Calibrated on","معايرة على","Calibré sur") }} <b class="text-ink">{{ d.model.sample }}</b> {{ L("items the team verified","صنف اعتمدهم التيم","articles vérifiés") }}</div>
            <div class="mt-0.5">{{ L("Priced","مسعّرة","Tarifés") }}: <b class="text-ink">{{ d.model.verified }}</b> {{ L("verified","مؤكدة","vérifiés") }} · <b class="text-ink">{{ d.model.modelled }}</b> {{ L("modelled","مقدّرة","modélisés") }}</div>
          </div>
        </div>
      </div>

      <!-- the statement -->
      <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
        <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2">
          <span class="text-[13px] font-bold">{{ L("P&L by month — estimated","قائمة الدخل الشهرية — تقديرية","Compte de résultat estimé") }}</span>
          <span class="text-[10.5px] text-ink-muted">{{ d.currency }} · {{ d.year }}</span>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-[11.5px]">
            <thead><tr style="background:#fafaf9">
              <th class="px-3 py-2 text-start text-[10px] font-bold text-ink-muted sticky start-0" style="background:#fafaf9">{{ L("Line","البند","Ligne") }}</th>
              <th v-for="m in d.months" :key="m" class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ mLabel(m) }}</th>
              <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("Total","الإجمالي","Total") }}</th>
            </tr></thead>
            <tbody>
              <tr v-for="r in rows" :key="r.k" class="border-t border-line-hair"
                  :class="r.strong ? 'font-bold' : ''" :style="r.bg ? 'background:' + r.bg : ''">
                <td class="px-3 py-2 sticky start-0" :style="'background:' + (r.bg || '#fff')">
                  {{ r.label }}
                  <span v-if="r.note" class="ms-1 text-[9.5px] font-bold px-1.5 py-0.5 rounded-full"
                        style="background:#fef3c7;color:#92400e">{{ r.note }}</span>
                </td>
                <td v-for="(v, i) in r.vals" :key="i" class="px-3 py-2 text-end tnum" dir="ltr"
                    :class="r.pct ? '' : (v < 0 ? 'text-sale' : '')">
                  {{ r.pct ? (v ? v.toFixed(1) + '%' : '—') : fmt(v) }}
                </td>
                <td class="px-3 py-2 text-end tnum font-bold" dir="ltr">
                  {{ r.pct ? (r.total ? r.total.toFixed(1) + '%' : '—') : fmt(r.total) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- the VAT nobody is paying in cash yet -->
      <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
        <div class="px-4 py-3 border-b border-line-hair">
          <div class="text-[13px] font-bold">{{ L("VAT — charged, and what actually leaves","الضريبة — المحصّل والمدفوع فعلًا","TVA — collectée et décaissée") }}</div>
          <div class="text-[10.5px] text-ink-muted mt-0.5">
            {{ L("The VAT above is collected for the state, never earned. Almost none of it is paid in cash today — an input-VAT credit built up on stock is absorbing it, and that credit is finite.",
                 "الضريبة اللي فوق محصّلة لحساب الدولة، مش إيراد. وتقريبًا مافيش منها حاجة بتتدفع كاش دلوقتي — رصيد ضريبة المشتريات المتراكم على المخزون هو اللي بيمتصّها، والرصيد ده محدود.",
                 "La TVA est collectée pour l'État ; un crédit de TVA l'absorbe aujourd'hui.") }}
          </div>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-[11.5px]">
            <thead><tr style="background:#fafaf9">
              <th class="px-3 py-2 text-start text-[10px] font-bold text-ink-muted">{{ L("Month","الشهر","Mois") }}</th>
              <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("VAT charged","الضريبة المحصّلة","TVA collectée") }}</th>
              <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("VAT on purchases","ضريبة المشتريات","TVA déductible") }}</th>
              <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("Net owed","الصافي المستحق","Net dû") }}</th>
            </tr></thead>
            <tbody>
              <tr v-for="(m, i) in d.months" :key="m" class="border-t border-line-hair hover:bg-[#fafaf9]">
                <td class="px-3 py-2 font-semibold">{{ mLabel(m) }}</td>
                <td class="px-3 py-2 text-end tnum" dir="ltr">{{ fmt(d.vat.output[i]) }}</td>
                <td class="px-3 py-2 text-end tnum text-ink-muted" dir="ltr">{{ fmt(d.vat.input[i]) }}</td>
                <td class="px-3 py-2 text-end tnum font-bold" dir="ltr">{{ fmt(d.vat.net[i]) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="px-4 py-3 border-t border-line-hair flex flex-wrap gap-x-6 gap-y-1.5 text-[11px]"
             style="background:#fffbeb">
          <div><span class="text-ink-muted">{{ L("Credit remaining","الرصيد المتبقي","Crédit restant") }}:</span>
               <b class="tnum ms-1" dir="ltr">{{ fmt(d.vat.credit_left) }}</b> {{ d.currency }}</div>
          <div><span class="text-ink-muted">{{ L("Burning","معدل الاستهلاك","Consommation") }}:</span>
               <b class="tnum ms-1" dir="ltr">{{ fmt(d.vat.monthly_burn) }}</b> / {{ L("month","شهر","mois") }}</div>
          <div v-if="d.vat.runway_months">
            <span class="text-ink-muted">{{ L("Runs out in","ينتهي خلال","Épuisé dans") }}:</span>
            <b class="ms-1" :style="d.vat.runway_months < 18 ? 'color:#b45309' : ''">{{ d.vat.runway_months }}</b>
            {{ L("months — after that it is cash","شهر — وبعدها بيبقى كاش","mois") }}
          </div>
        </div>
      </div>

      <!-- the team's queue -->
      <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
        <div class="px-4 py-3 border-b border-line-hair">
          <div class="text-[13px] font-bold">{{ L("Correction queue — books vs model","قائمة التصحيح — الدفاتر مقابل النموذج","File de correction") }}</div>
          <div class="text-[10.5px] text-ink-muted mt-0.5">
            {{ L("What the ledger charges, what the documents say it should be, and the gap the team is closing. When the gap goes to zero this page is no longer needed.",
                 "اللي الدفاتر بتحمّله، واللي المستندات بتقوله، والفرق اللي التيم بيقفله. لما الفرق يوصل صفر، الصفحة دي مابقاش ليها لزوم.",
                 "L'écart que l'équipe doit résorber.") }}
          </div>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-[11.5px]">
            <thead><tr style="background:#fafaf9">
              <th class="px-3 py-2 text-start text-[10px] font-bold text-ink-muted">{{ L("Month","الشهر","Mois") }}</th>
              <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("Booked","الدفاتر","Comptabilisé") }}</th>
              <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("Model","النموذج","Modèle") }}</th>
              <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("Gap","الفرق","Écart") }}</th>
              <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("Verified share","نسبة المؤكد","Part vérifiée") }}</th>
              <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("Units unpriced","وحدات بلا تكلفة","Non tarifées") }}</th>
            </tr></thead>
            <tbody>
              <tr v-for="(m, i) in d.months" :key="m" class="border-t border-line-hair hover:bg-[#fafaf9]">
                <td class="px-3 py-2 font-semibold">{{ mLabel(m) }}</td>
                <td class="px-3 py-2 text-end tnum" dir="ltr" :class="d.cogs_booked[i] < 0 ? 'text-sale' : ''">{{ fmt(d.cogs_booked[i]) }}</td>
                <td class="px-3 py-2 text-end tnum" dir="ltr">{{ fmt(d.cogs[i]) }}</td>
                <td class="px-3 py-2 text-end tnum font-bold" dir="ltr"
                    :style="Math.abs(d.gap[i]) > 300000 ? 'color:#b91c1c' : ''">{{ fmt(d.gap[i]) }}</td>
                <td class="px-3 py-2 text-end tnum" dir="ltr">{{ d.verified_share[i] }}%</td>
                <td class="px-3 py-2 text-end tnum" dir="ltr"
                    :class="d.uncovered_qty[i] > 500 ? 'text-sale font-semibold' : 'text-ink-muted'">{{ fmt(d.uncovered_qty[i]) }}</td>
              </tr>
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

const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const A = "accounting_portal.api.pnl_estimated";

const loading = ref(true);
const err = ref("");
const d = ref(null);
const scope = ref("company");
const scopes = computed(() => [
  { k: "company", label: L("Morocco only", "المغرب فقط", "Maroc seul") },
  { k: "group", label: L("Group · USD", "المجموعة · دولار", "Groupe · USD") },
]);

const fmt = (n) => (n === null || n === undefined ? "—"
  : new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(n));

const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const mLabel = (m) => MON[parseInt(String(m).slice(5, 7), 10) - 1] || m;

const stats = computed(() => {
  const t = d.value && d.value.totals;
  if (!t) return [];
  return [
    { k: "billed", label: L("Billed (incl. VAT)", "المحصّل (شامل الضريبة)", "Facturé TTC"),
      v: fmt(t.revenue_gross),
      sub: fmt(t.revenue) + " " + L("net of VAT", "بعد الضريبة", "HT"), tone: "" },
    { k: "gm", label: L("Gross margin", "الهامش المجمل", "Marge brute"),
      v: t.gross_pct + "%", sub: fmt(t.gross), tone: "" },
    { k: "net", label: L("Net result", "النتيجة", "Résultat"), v: fmt(t.net),
      sub: t.net_pct + "% " + L("of revenue", "من الإيراد", "du revenu"),
      tone: t.net < 0 ? "text-sale" : "" },
    { k: "gap", label: L("Correction gap", "فجوة التصحيح", "Écart"), v: fmt(t.gap),
      sub: L("books minus model", "الدفاتر ناقص النموذج", "livres - modèle"),
      tone: Math.abs(t.gap) > 500000 ? "text-sale" : "" },
  ];
});

const rows = computed(() => {
  const x = d.value;
  if (!x) return [];
  const n = x.months.length;
  const pct = (a, b) => a.map((v, i) => (b[i] ? (100 * v) / b[i] : 0));
  const sum = (a) => a.reduce((s, v) => s + v, 0);
  const out = [
    { k: "gross_billed", label: L("Billed to customers (incl. VAT)", "المحصّل من العملاء (شامل الضريبة)", "Facturé TTC"),
      vals: x.revenue_gross, total: sum(x.revenue_gross), strong: true },
    { k: "vat", label: "  " + L("VAT charged — collected for the state", "الضريبة المحصّلة — مستحقة للدولة", "TVA collectée"),
      vals: x.vat.output.map((v) => -v), total: -sum(x.vat.output) },
    { k: "rev", label: L("Revenue (net of VAT)", "الإيراد (بعد الضريبة)", "Revenu HT"),
      vals: x.revenue, total: sum(x.revenue), strong: true, bg: "#f5f5f4" },
    { k: "cogs", label: L("Cost of goods (modelled)", "تكلفة البضاعة (نموذج)", "Coût des marchandises (modèle)"),
      vals: x.cogs.map((v) => -v), total: -sum(x.cogs), note: L("estimated", "تقديري", "estimé") },
    { k: "gross", label: L("Gross profit", "الربح المجمل", "Marge brute"),
      vals: x.gross, total: sum(x.gross), strong: true, bg: "#f5f5f4" },
    { k: "gm", label: L("Gross margin %", "نسبة الهامش المجمل", "Marge %"),
      vals: pct(x.gross, x.revenue), total: x.totals.gross_pct, pct: true, bg: "#f5f5f4" },
    { k: "opex", label: L("Operating expenses", "المصاريف التشغيلية", "Charges d'exploitation"),
      vals: x.opex.map((v) => -v), total: -sum(x.opex) },
  ];
  (x.siblings || []).forEach((s2, j) => out.push({
    k: "sib" + j, label: "  " + L("opex carried by", "مصاريف تتحملها", "charges portées par") + " " + s2.company,
    vals: s2.monthly.map((v) => -v), total: -s2.total,
    note: L("other entity", "كيان آخر", "autre entité"),
  }));
  (x.accruals || []).forEach((a, j) => out.push({
    k: "acc" + j, label: "  " + L("accrued", "استحقاق", "provision") + " · " + a.label,
    vals: a.monthly.map((v) => -v), total: -a.total, note: L("not billed", "غير مفوترة", "non facturé"),
  }));
  out.push({ k: "net", label: L("Net result", "النتيجة", "Résultat"),
             vals: x.net, total: x.totals.net, strong: true, bg: "#f5f5f4" });
  return out.map((r) => ({ ...r, vals: r.vals.slice(0, n) }));
});

async function load() {
  loading.value = true;
  err.value = "";
  try {
    d.value = await api.call(A + ".pnl_estimated", { scope: scope.value });
  } catch (e) {
    err.value = (e && e.message) || "Failed to load";
  } finally {
    loading.value = false;
  }
}
function setScope(k) {
  if (scope.value === k) return;
  scope.value = k;
  load();
}
onMounted(load);
</script>
