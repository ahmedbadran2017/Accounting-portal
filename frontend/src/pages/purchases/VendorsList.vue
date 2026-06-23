<template>
  <div class="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
    <button v-for="v in VENDORS" :key="v.id" class="yo-card text-start bg-white border border-line rounded-[14px] p-4 shadow-card w-full">
      <div class="flex items-center gap-2.5">
        <span class="w-[30px] h-[30px] rounded-[8px] grid place-items-center text-white text-[9.5px] font-bold flex-shrink-0" :style="{ background: v.badge }">{{ v.code }}</span>
        <div class="flex-1 min-w-0">
          <div class="text-[12.5px] font-bold truncate">{{ v.name }}</div>
          <div class="text-[10.5px] text-ink-muted">{{ v.place }}</div>
        </div>
        <Icon name="chev" :size="14" color="#bcb6b0" class="rtl:rotate-180 flex-shrink-0" />
      </div>
      <div class="text-[20px] font-bold tnum mt-2.5">{{ v.payable }}<span class="text-[11px] text-ink-muted ms-0.5">{{ v.ccy }}</span></div>
      <div class="text-[10.5px] text-ink-muted mt-0.5">{{ v.note(locale) }}</div>
    </button>
  </div>
</template>

<script setup>
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { VENDORS } from "@/data/purchases";
const { locale } = useI18n();
</script>
