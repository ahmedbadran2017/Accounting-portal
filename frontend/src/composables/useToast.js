import { ref } from "vue";
import { explainCurrent } from "@/composables/useErrorExplain";

// Minimal global toast queue. Components render <ToastHost/> once at the root.
const toasts = ref([]);
let _id = 0;

function push(message, type = "info", timeout = 4000) {
  const id = ++_id;
  toasts.value.push({ id, message, type });
  if (timeout) setTimeout(() => dismiss(id), timeout);
  return id;
}

function dismiss(id) {
  toasts.value = toasts.value.filter((t) => t.id !== id);
}

export function useToast() {
  return {
    toasts,
    success: (m, t) => push(m, "success", t),
    // While the explanation popup is open it already says what failed.
    error: (m, t) => (explainCurrent.value ? null : push(m, "error", t)),
    info: (m, t) => push(m, "info", t),
    dismiss,
  };
}
