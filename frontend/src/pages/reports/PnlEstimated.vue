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

const fmt = (n) => (n === null || n === undefined ? "—"
  : new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(n));

const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const mLabel = (m) => MON[parseInt(String(m).slice(5, 7), 10) - 1] || m;

const stats = computed(() => {
  const t = d.value && d.value.totals;
  if (!t) return [];
  return [
    { k: "rev", label: L("Revenue", "الإيراد", "Revenu"), v: fmt(t.revenue), sub: d.value.currency, tone: "" },
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
    { k: "rev", label: L("Revenue", "الإيراد", "Revenu"), vals: x.revenue, total: sum(x.revenue), strong: true },
    { k: "cogs", label: L("Cost of goods (modelled)", "تكلفة البضاعة (نموذج)", "Coût des marchandises (modèle)"),
      vals: x.cogs.map((v) => -v), total: -sum(x.cogs), note: L("estimated", "تقديري", "estimé") },
    { k: "gross", label: L("Gross profit", "الربح المجمل", "Marge brute"),
      vals: x.gross, total: sum(x.gross), strong: true, bg: "#f5f5f4" },
    { k: "gm", label: L("Gross margin %", "نسبة الهامش المجمل", "Marge %"),
      vals: pct(x.gross, x.revenue), total: x.totals.gross_pct, pct: true, bg: "#f5f5f4" },
    { k: "opex", label: L("Operating expenses", "المصاريف التشغيلية", "Charges d'exploitation"),
      vals: x.opex.map((v) => -v), total: -sum(x.opex) },
  ];
  (x.accruals || []).forEach((a, j) => out.push({
    k: "acc" + j, label: "  " + L("accrued", "استحقاق", "provision") + " · " + a.label,
    vals: a.monthly.map((v) => -v), total: -a.total, note: L("not billed", "غير مفوترة", "non facturé"),
  }));
  out.push({ k: "net", label: L("Net result", "النتيجة", "Résultat"),
             vals: x.net, total: x.totals.net, strong: true, bg: "#f5f5f4" });
  return out.map((r) => ({ ...r, vals: r.vals.slice(0, n) }));
});

onMounted(async () => {
  try {
    d.value = await api.call(A + ".pnl_estimated", {});
  } catch (e) {
    err.value = (e && e.message) || "Failed to load";
  } finally {
    loading.value = false;
  }
});
</script>
