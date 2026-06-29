import { ref, watch } from "vue";

// A ref whose value is mirrored to localStorage, so a filter the user picks
// (date preset, period, custom range…) survives navigating away and back, or a
// full page reload — instead of resetting to the default every time. Same idea
// as the persisted entity (`ap_entity`).
export function usePersistedRef(key, def) {
  let initial = def;
  try {
    const raw = localStorage.getItem(key);
    if (raw !== null && raw !== undefined) initial = JSON.parse(raw);
  } catch {
    /* corrupt value — fall back to the default */
  }
  const r = ref(initial);
  watch(
    r,
    (v) => {
      try {
        if (v === null || v === undefined || v === "") localStorage.removeItem(key);
        else localStorage.setItem(key, JSON.stringify(v));
      } catch {
        /* storage full / unavailable — ignore */
      }
    },
    { deep: true },
  );
  return r;
}
