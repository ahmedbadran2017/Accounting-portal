<template>
  <div class="flex flex-col items-center justify-center text-center py-16 px-6">
    <div class="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mb-4">
      <span class="text-slate-400 text-xl">∅</span>
    </div>
    <h3 class="text-sm font-semibold text-slate-700">{{ title }}</h3>
    <p v-if="body" class="text-sm text-slate-400 mt-1 max-w-sm">{{ body }}</p>
    <slot />
  </div>
</template>

<script setup>
defineProps({ title: String, body: String });
</script>
