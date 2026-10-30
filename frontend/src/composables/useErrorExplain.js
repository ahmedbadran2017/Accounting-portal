// The one explanation popup on screen (see components/shared/ErrorExplainer.vue
// and api/error_explain.py). The API client fills it when a write fails; the
// toast queue stays quiet while it is open so the same failure is not shown twice.
import { ref } from "vue";

export const explainCurrent = ref(null);

export function showExplain(x) {
  explainCurrent.value = x;
}

export function closeExplain() {
  explainCurrent.value = null;
}
