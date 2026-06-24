<template>
  <div class="py-10 px-6 space-y-2.5">
    <div v-for="n in rows" :key="n" class="flex items-center gap-4 animate-pulse" :style="{ opacity: Math.max(0.25, 1 - (n - 1) * 0.12) }">
      <div class="h-3 rounded-full bg-app-warm flex-1" style="max-width:120px"></div>
      <div class="h-3 rounded-full bg-app-warm flex-1" style="max-width:90px"></div>
      <div class="h-3 rounded-full bg-app-warm flex-1"></div>
      <div class="h-3 rounded-full bg-app-warm flex-1" style="max-width:80px"></div>
      <div class="h-3 rounded-full bg-app-warm" style="width:60px"></div>
    </div>
  </div>
</template>

<script setup>
defineProps({ rows: { type: Number, default: 6 } });
</script>
