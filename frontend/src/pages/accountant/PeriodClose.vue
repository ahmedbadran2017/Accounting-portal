<template>
  <div class="grid lg:grid-cols-[1.3fr_1fr] gap-3.5">
    <!-- Checklist -->
    <div class="bg-white border border-line rounded-[14px] p-4 shadow-card">
      <div class="text-[13px] font-bold">{{ L("Period-close checklist","قائمة إقفال الفترة","Liste de clôture") }}</div>
      <div class="text-[11px] text-ink-muted mb-3">{{ L("June 2026 · everything must tie before locking","يونيو ٢٠٢٦ · كل شيء يجب أن يتطابق قبل الإقفال","Juin 2026 · tout doit concorder avant verrouillage") }}</div>
      <div class="flex flex-col gap-2.5">
        <div v-for="c in checklist" :key="c.key" class="flex items-center gap-2.5 px-3 py-2.5 border border-line rounded-[11px]" style="background:#fdfcfb">
          <span class="w-[22px] h-[22px] rounded-[7px] grid place-items-center flex-shrink-0" :style="{ background: meta(c).bg }"><Icon :name="meta(c).icon" :size="12" :color="meta(c).fg" /></span>
          <span class="flex-1 text-[12px] font-medium">{{ L(c.en, c.ar, c.fr) }}</span>
          <span class="text-[10px] font-bold px-2 py-0.5 rounded-badge border" :style="{ background: meta(c).bg, color: meta(c).fg, borderColor: meta(c).bd }">{{ statusLabel(c) }}</span>
        </div>
      </div>
    </div>

    <div class="flex flex-col gap-3.5">
      <!-- FX revaluation -->
      <div class="bg-white border border-line rounded-[14px] p-4 shadow-card">
        <div class="flex items-center justify-between">
          <span class="text-[13px] font-bold">{{ L("FX revaluation","تسوية العملة","Réévaluation change") }}</span>
          <span class="text-[10.5px] text-ink-muted">30 Jun 2026</span>
        </div>
        <div class="flex flex-col gap-px mt-2.5">
          <div v-for="f in fx" :key="f.pair" class="flex items-center justify-between py-1.5 border-t border-line-hair">
            <span class="text-[12px] font-semibold text-ink-2">{{ f.pair }}</span>
            <span class="flex gap-3.5">
              <span class="text-[11.5px] tnum">{{ f.rate }}</span>
              <span class="text-[11px] tnum w-12 text-end" :style="{ color: f.delta.startsWith('-') ? '#be123c' : '#047857' }">{{ f.delta }}</span>
            </span>
          </div>
        </div>
      </div>

      <!-- Lock period -->
      <div class="rounded-[14px] p-4 text-white" style="background:linear-gradient(135deg,#1c1917,#292524);box-shadow:0 8px 24px -14px rgba(28,25,23,.6)">
        <div class="flex items-center gap-2.5">
          <span class="w-[30px] h-[30px] rounded-[8px] grid place-items-center" style="background:rgba(255,255,255,.1)"><Icon name="lock" :size="16" color="#fbbf24" /></span>
          <div class="flex-1">
            <div class="text-[12.5px] font-bold">{{ L("Period lock","قفل الفترة","Verrouillage") }}</div>
            <div class="text-[10.5px] text-ink-muted">{{ L("Stops back-dated postings","يمنع القيود بأثر رجعي","Bloque les écritures antidatées") }}</div>
          </div>
        </div>
        <div class="flex items-center gap-2.5 mt-3 px-3 py-2.5 rounded-[10px]" style="background:rgba(255,255,255,.06)">
          <span class="w-[7px] h-[7px] rounded-full" style="background:#fbbf24"></span>
          <span class="flex-1 text-[11.5px]" style="color:#e7e5e4">01–30 Jun 2026</span>
          <span class="text-[10.5px] font-bold" style="color:#fbbf24">{{ L("Open","مفتوحة","Ouverte") }}</span>
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

const META = {
  done: { bg: "#ecfdf5", fg: "#047857", bd: "#a7f3d0", icon: "check" },
  pending: { bg: "#fffbeb", fg: "#b45309", bd: "#fde68a", icon: "clock" },
  blocked: { bg: "#fef2f2", fg: "#dc2626", bd: "#fecaca", icon: "alert" },
};
const meta = (c) => META[c.state] || META.pending;
const statusLabel = (c) => ({
  done: L("Done", "تم", "Fait"), pending: L("Pending", "معلّق", "En attente"), blocked: L("1 blocked", "١ محظور", "1 bloquée"),
}[c.state]);

const checklist = [
  { key: "bank", en: "Bank reconciliation", ar: "المطابقة البنكية", fr: "Rapprochement bancaire", state: "done" },
  { key: "cod", en: "COD remittance matched", ar: "تطابق تحصيل COD", fr: "Encaissement COD rapproché", state: "done" },
  { key: "dep", en: "Depreciation posted", ar: "ترحيل الإهلاك", fr: "Amortissement passé", state: "pending" },
  { key: "fx", en: "FX revaluation", ar: "تسوية العملة", fr: "Réévaluation change", state: "pending" },
  { key: "mc", en: "Maker-checker queue cleared", ar: "تصفية طابور الاعتماد", fr: "File maker-checker vidée", state: "blocked" },
];
const fx = [
  { pair: "USD/MAD", rate: "9.94", delta: "+0.12" },
  { pair: "TRY/MAD", rate: "0.262", delta: "-0.004" },
  { pair: "CNY/MAD", rate: "1.371", delta: "+0.02" },
  { pair: "EUR/MAD", rate: "10.78", delta: "+0.05" },
];
</script>
