<template>
  <div class="space-y-3.5">
    <!-- Verified metric cards -->
    <div class="grid grid-cols-2 lg:grid-cols-3 gap-3">
      <div v-for="m in metrics" :key="m.key" class="yo-card bg-white border border-line rounded-[14px] p-4 shadow-card">
        <div class="flex items-center justify-between">
          <span class="text-[11.5px] font-semibold text-ink-3">{{ L(m.en, m.ar, m.fr) }}</span>
          <span class="inline-flex items-center gap-1 text-[9px] font-bold px-1.5 py-0.5 rounded-full" style="background:#ecfdf5;color:#047857;border:1px solid #a7f3d0"><Icon name="check" :size="10" />{{ L("Tied","مطابق","Rapproché") }}</span>
        </div>
        <div class="text-[23px] font-bold tnum mt-2">{{ m.value }}</div>
        <div class="text-[10.5px] text-ink-muted mt-[3px]">{{ L(m.tieEn, m.tieAr, m.tieFr) }}</div>
      </div>
    </div>

    <div class="grid lg:grid-cols-[1fr_1.2fr] gap-3.5">
      <!-- Unit economics -->
      <div class="bg-white border border-line rounded-[14px] p-4 shadow-card">
        <div class="text-[13px] font-bold">{{ L("Unit economics","اقتصاديات الوحدة","Économie unitaire") }}</div>
        <div class="text-[11px] text-ink-muted">{{ L("Per delivered COD order","لكل طلب COD مُسلَّم","Par commande COD livrée") }}</div>
        <div class="flex flex-col mt-3">
          <div v-for="u in unit" :key="u.key" class="flex items-center justify-between py-2.5 border-t border-line-hair">
            <span class="text-[12px] text-ink-2">{{ L(u.en, u.ar, u.fr) }}</span>
            <span class="text-[13px] font-bold tnum">{{ u.value }}</span>
          </div>
        </div>
      </div>

      <!-- Ops ↔ Finance reconciliation -->
      <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
        <div class="flex items-center gap-2.5 px-4 py-3.5 border-b border-line-hair">
          <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#f5f3ff"><Icon name="shield" :size="14" color="#7c3aed" /></span>
          <div class="flex-1">
            <div class="text-[13px] font-bold">{{ L("Ops ↔ Finance reconciliation","تطابق التشغيل ↔ المالية","Rappr. Ops ↔ Finance") }}</div>
            <div class="text-[11px] text-ink-muted">{{ L("Storefront metrics tied to the ledger","مؤشرات المتجر مطابقة للأستاذ","Indicateurs storefront ↔ GL") }}</div>
          </div>
        </div>
        <div class="flex flex-col">
          <div v-for="r in recon" :key="r.key" class="flex items-center gap-3 px-4 py-[11px] border-t border-line-hair">
            <div class="flex-1 min-w-0">
              <div class="text-[12px] font-semibold">{{ L(r.en, r.ar, r.fr) }}</div>
              <div class="text-[10.5px] text-ink-muted">{{ r.ops }} ↔ {{ r.fin }}</div>
            </div>
            <span class="text-[10px] font-bold px-2 py-0.5 rounded-badge border" :style="r.state === 'diverge' ? 'background:#fffbeb;color:#b45309;border-color:#fde68a' : 'background:#ecfdf5;color:#047857;border-color:#a7f3d0'">
              {{ r.state === 'diverge' ? L("Diverges","تباين","Diverge") : L("Tied","مطابق","Rapproché") }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

const metrics = [
  { key: "rev", en: "Net revenue (June)", ar: "إيراد صافٍ (يونيو)", fr: "Revenu net (juin)", value: "933K", tieEn: "tied to Sales Invoice", tieAr: "مطابق لفواتير البيع", tieFr: "lié aux factures" },
  { key: "cod", en: "Collected (COD)", ar: "المُحصَّل (COD)", fr: "Encaissé (COD)", value: "1.15M", tieEn: "tied to Payment Entry", tieAr: "مطابق لقيود الدفع", tieFr: "lié aux paiements" },
  { key: "deliv", en: "Delivery rate", ar: "نسبة التسليم", fr: "Taux de livraison", value: "74.9%", tieEn: "Delivery Note / Orders", tieAr: "سندات التسليم / الطلبات", tieFr: "Bons / commandes" },
  { key: "repeat", en: "Repeat rate", ar: "نسبة التكرار", fr: "Taux de réachat", value: "17.9%", tieEn: "2,310 / 12,917 customers", tieAr: "٢٬٣١٠ / ١٢٬٩١٧ عميل", tieFr: "2 310 / 12 917 clients" },
  { key: "margin", en: "Gross margin", ar: "الهامش الإجمالي", fr: "Marge brute", value: "37%", tieEn: "landed-cost based", tieAr: "على التكلفة المحمَّلة", tieFr: "base coût de revient" },
  { key: "ap", en: "Payables (open)", ar: "دائنون (مفتوح)", fr: "Dettes (ouvertes)", value: "3.60M", tieEn: "89 suppliers", tieAr: "٨٩ مورّد", tieFr: "89 fournisseurs" },
];
const unit = [
  { key: "aov", en: "AOV (gross)", ar: "متوسط قيمة الطلب", fr: "Panier moyen (TTC)", value: "128 MAD" },
  { key: "cogs", en: "COGS / order", ar: "تكلفة / طلب", fr: "COGS / commande", value: "45 MAD" },
  { key: "fee", en: "COD fee / order", ar: "رسوم COD / طلب", fr: "Frais COD / commande", value: "9 MAD" },
  { key: "contrib", en: "Contribution / delivered", ar: "مساهمة / مُسلَّم", fr: "Contribution / livrée", value: "62 MAD" },
];
const recon = [
  { key: "rev", en: "Revenue", ar: "الإيراد", fr: "Revenu", ops: "Shopify 6,106", fin: "ERPNext 6,038", state: "tied" },
  { key: "cash", en: "Cash collected", ar: "النقد المُحصَّل", fr: "Cash encaissé", ops: "1.15M", fin: "1.15M", state: "tied" },
  { key: "orders", en: "Orders", ar: "الطلبات", fr: "Commandes", ops: "7,697", fin: "7,697", state: "tied" },
  { key: "margin", en: "Margin", ar: "الهامش", fr: "Marge", ops: "0 (storefront)", fin: "37% (GL)", state: "diverge" },
];
</script>
