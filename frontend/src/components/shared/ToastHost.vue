<template>
  <div class="fixed bottom-4 inset-x-0 z-50 flex flex-col items-center gap-2 pointer-events-none px-4">
    <transition-group name="toast">
      <div
        v-for="t in toasts"
        :key="t.id"
        class="pointer-events-auto max-w-sm w-full rounded-lg shadow-lg px-4 py-3 text-sm font-medium flex items-start gap-3"
        :class="cls(t.type)"
      >
        <span class="flex-1">{{ t.message }}</span>
        <button class="opacity-60 hover:opacity-100" @click="dismiss(t.id)">✕</button>
      </div>
    </transition-group>
  </div>
</template>

<script setup>
import { useToast } from "@/composables/useToast";
const { toasts, dismiss } = useToast();
function cls(type) {
  return {
    success: "bg-emerald-600 text-white",
    error: "bg-rose-600 text-white",
    info: "bg-slate-800 text-white",
  }[type] || "bg-slate-800 text-white";
}
</script>

<style scoped>
.toast-enter-active, .toast-leave-active { transition: all 0.25s ease; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateY(8px); }
</style>
