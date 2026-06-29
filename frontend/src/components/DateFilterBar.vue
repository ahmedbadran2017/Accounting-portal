<template>
  <div class="flex items-center gap-1.5 flex-wrap">
    <Icon name="clock" :size="13" color="#a8a29e" />
    <button v-for="p in df.PRESETS" :key="p.key" @click="df.setPreset(p.key)"
            class="text-[11px] font-semibold px-2.5 py-1 rounded-full border transition"
            :class="df.preset.value === p.key ? 'bg-ink text-white border-ink' : 'bg-white text-ink-3 border-line-2 hover:bg-app-warm'">{{ p.label() }}</button>
    <template v-if="df.preset.value === 'range'">
      <input type="date" v-model="df.from.value" @change="df.applyRange()" class="h-7 border border-line-2 rounded-chip px-2 text-[11px] focus:outline-none focus:border-accent/40" />
      <span class="text-ink-muted text-[11px]">→</span>
      <input type="date" v-model="df.to.value" @change="df.applyRange()" class="h-7 border border-line-2 rounded-chip px-2 text-[11px] focus:outline-none focus:border-accent/40" />
    </template>
  </div>
</template>

<script setup>
import Icon from "@/components/Icon.vue";
defineProps({ df: { type: Object, required: true } });
</script>
