<template>
  <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
    <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair">
      <span class="text-[13px] font-bold">{{ L("Fixed assets","الأصول الثابتة","Immobilisations") }}</span>
      <span class="text-[11px] text-ink-muted">{{ L("Cost · depreciation method · net book value","التكلفة · طريقة الإهلاك · القيمة الدفترية","Coût · amortissement · VNC") }}</span>
    </div>
    <div class="overflow-x-auto">
      <table class="w-full text-[12px]">
        <thead>
          <tr style="background:#fafaf9">
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Asset","الأصل","Actif") }}</th>
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Category","الفئة","Catégorie") }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Cost","التكلفة","Coût") }}</th>
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Method","الطريقة","Méthode") }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Accum. dep.","مجمع الإهلاك","Amort. cumulé") }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">NBV</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in ASSETS" :key="r.name" class="border-t border-line-hair hover:bg-app-warm/60">
            <td class="px-4 py-3 font-semibold whitespace-nowrap">{{ r.name }}</td>
            <td class="px-4 py-3 text-ink-3">{{ L(r.cat, r.catAr, r.catFr) }}</td>
            <td class="px-4 py-3 text-end tnum font-semibold">{{ r.cost }}</td>
            <td class="px-4 py-3 text-ink-3 whitespace-nowrap">{{ r.method }}</td>
            <td class="px-4 py-3 text-end tnum text-sale">{{ r.accum }}</td>
            <td class="px-4 py-3 text-end tnum font-bold text-success-dark">{{ r.nbv }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { useI18n } from "vue-i18n";
const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const ASSETS = [
  { name: "VW ID.4", cat: "Vehicles", catAr: "مركبات", catFr: "Véhicules", cost: "520,000", method: "Straight-line · 5y", accum: "-104,000", nbv: "416,000" },
  { name: "Warehouse racking", cat: "Equipment", catAr: "معدات", catFr: "Équipement", cost: "180,000", method: "Straight-line · 8y", accum: "-33,750", nbv: "146,250" },
  { name: "MacBooks (12)", cat: "IT", catAr: "تقنية", catFr: "Informatique", cost: "288,000", method: "Straight-line · 3y", accum: "-160,000", nbv: "128,000" },
];
</script>
