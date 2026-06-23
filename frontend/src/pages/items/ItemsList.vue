<template>
  <div class="space-y-3.5">
    <!-- Auditor flag -->
    <div class="flex items-center gap-2.5 px-[15px] py-[13px] rounded-[13px]" style="background:#fff7ed;border:1px solid #fed7aa">
      <span class="w-[30px] h-[30px] rounded-[8px] grid place-items-center flex-shrink-0" style="background:#ffedd5"><Icon name="alert" :size="16" color="#ea580c" /></span>
      <div class="flex-1">
        <div class="text-[12.5px] font-bold" style="color:#9a3412">{{ L("True margin needs RTO allocated to SKU","الهامش الحقيقي يحتاج توزيع الإرجاع على الصنف","Marge réelle : retours à imputer au SKU") }}</div>
        <div class="text-[11.5px] mt-px" style="color:#c2410c">{{ L("Margin is now landed-cost based, but return shipping isn’t yet costed back to the item.","الهامش الآن مبني على التكلفة المحمَّلة، لكن شحن الإرجاع لا يُحمَّل بعد على الصنف.","La marge inclut le coût de revient, mais le retour n’est pas encore imputé à l’article.") }}</div>
      </div>
      <span class="inline-flex items-center gap-1 text-[10px] font-bold px-2.5 py-[3px] rounded-full flex-shrink-0" style="background:#f5f3ff;color:#7c3aed;border:1px solid #ddd6fe"><Icon name="shield" :size="11" />{{ L("Auditor","المدقّق","Auditeur") }}</span>
    </div>

    <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
      <div class="flex items-center gap-2.5 px-4 py-3.5 border-b border-line-hair">
        <span class="text-[13px] font-bold">{{ L("Items & true margin","الأصناف والهامش الحقيقي","Articles & marge réelle") }}</span>
        <span class="text-[11px] text-ink-muted">{{ L("Sell − landed cost − COD fee − RTO","البيع − التكلفة المحمَّلة − رسوم COD − الإرجاع","Vente − coût de revient − frais COD − retour") }}</span>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead>
            <tr style="background:#fafaf9">
              <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">SKU</th>
              <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Item","الصنف","Article") }}</th>
              <th class="px-3 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Sell","البيع","Vente") }}</th>
              <th class="px-3 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Cost","التكلفة","Coût") }}</th>
              <th class="px-3 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Landed","المحمَّلة","Revient") }}</th>
              <th class="px-3 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("COD fee","رسوم COD","Frais COD") }}</th>
              <th class="px-3 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">RTO</th>
              <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Margin","الهامش","Marge") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in ITEMS" :key="r.sku" class="border-t border-line-hair" :class="r.flagged ? 'bg-amber-50/30' : ''">
              <td class="px-4 py-2.5 font-mono font-bold whitespace-nowrap">{{ r.sku }}</td>
              <td class="px-4 py-2.5 text-ink-2 whitespace-nowrap">{{ r.name }}</td>
              <td class="px-3 py-2.5 text-end tnum font-semibold">{{ r.sell }}</td>
              <td class="px-3 py-2.5 text-end tnum text-ink-3">{{ r.cost }}</td>
              <td class="px-3 py-2.5 text-end tnum text-success-dark">{{ r.landed }}</td>
              <td class="px-3 py-2.5 text-end tnum text-ink-3">{{ r.codFee }}</td>
              <td class="px-3 py-2.5 text-end tnum text-ink-3">{{ r.rto }}</td>
              <td class="px-4 py-2.5 text-end whitespace-nowrap">
                <span class="text-[12.5px] font-bold" :style="{ color: r.flagged ? '#c2410c' : '#047857' }">{{ r.margin }}</span>
                <span class="text-[10.5px] text-ink-muted ms-1.5">{{ r.marginPct }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const ITEMS = [
  { sku: "JY-JKT-0301", name: "Veste en Jean", sell: "299", cost: "104.65", landed: "+11.5", codFee: "12", rto: "18%", margin: "+118", marginPct: "39%" },
  { sku: "JY-DRS-0392", name: "Robe Plissée", sell: "249", cost: "87.15", landed: "+8.4", codFee: "10", rto: "14%", margin: "+96", marginPct: "38%" },
  { sku: "JY-PNT-0145", name: "Pantalon Cargo", sell: "189", cost: "66.15", landed: "+9.2", codFee: "8", rto: "22%", margin: "+47", marginPct: "25%", flagged: true },
  { sku: "JY-SET-1205", name: "Set 12 contenants", sell: "129", cost: "45.15", landed: "+4.1", codFee: "7", rto: "12%", margin: "+58", marginPct: "45%" },
  { sku: "JY-ORG-3010", name: "Organisateur cuisine", sell: "298", cost: "104.30", landed: "+10.8", codFee: "12", rto: "9%", margin: "+142", marginPct: "48%" },
  { sku: "JY-BOX-0061", name: "Set 4 boîtes 6L", sell: "101", cost: "35.35", landed: "+3.2", codFee: "6", rto: "16%", margin: "+42", marginPct: "42%" },
];
</script>
