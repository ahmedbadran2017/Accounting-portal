<template>
  <div class="flex flex-wrap items-center gap-3">
    <div class="min-w-0">
      <h2 class="text-[17px] font-bold tracking-tight">{{ title }}</h2>
      <div class="text-[11.5px] text-ink-muted">{{ subtitle }}</div>
    </div>
    <slot name="actions" />
  </div>
</template>

<script setup>
defineProps({ title: String, subtitle: String });
</script>
