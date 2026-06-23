<template>
  <div class="grid sm:grid-cols-2 gap-3.5">
    <div v-for="v in VENDORS" :key="v.id" class="yo-card bg-white rounded-card border border-line p-4">
      <div class="flex items-center gap-2.5 mb-3">
        <span class="w-9 h-9 rounded-lg grid place-items-center text-white text-[11px] font-bold" :style="{ background: v.badge }">{{ v.code }}</span>
        <div class="min-w-0">
          <div class="text-[13.5px] font-bold truncate flex items-center gap-1.5">
            {{ v.name }}
            <span v-if="v.interco" class="text-[9px] font-bold px-1.5 py-0.5 rounded-badge" style="background:#faf5ff;color:#7c3aed;border:1px solid #e9d5ff">{{ L("Intercompany","بين الشركات","Intra-groupe") }}</span>
          </div>
          <div class="text-[11px] text-ink-muted">{{ v.place }} · {{ v.terms(locale) }}</div>
        </div>
      </div>
      <div class="flex items-end justify-between pt-3 border-t border-line">
        <div>
          <div class="text-[10px] text-ink-muted uppercase tracking-wide">{{ L("Open payable","مستحق مفتوح","Dû ouvert") }}</div>
          <div class="text-[11px] text-ink-3">{{ v.note(locale) }}</div>
        </div>
        <div class="text-[19px] font-bold tnum">{{ v.payable }} <span class="text-[12px] text-ink-3">{{ v.ccy }}</span></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useI18n } from "vue-i18n";
import { VENDORS } from "@/data/purchases";
const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
</script>
