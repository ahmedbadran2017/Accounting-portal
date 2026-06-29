import { ref, watch } from "vue";

// A ref whose value is mirrored to localStorage, so a filter the user picks
// (date preset, period, custom range…) survives navigating away and back, or a
// full page reload — instead of resetting to the default every time. Same idea
// as the persisted entity (`ap_entity`).
// The stored value is only used if it has the SAME shape as the default — so a
// corrupted or old-format value (e.g. a string where an object is expected) can
// never reach a computed and crash the page. Falls back to the default otherwise.
function shapeOk(v, d) {
  if (d === null || d === undefined) return true; // no shape constraint
  if (v === null || v === undefined) return false; // don't accept null over a real default
  if (Array.isArray(d) !== Array.isArray(v)) return false;
  return typeof v === typeof d;
}

export function usePersistedRef(key, def) {
  let initial = def;
  try {
    const raw = localStorage.getItem(key);
    if (raw !== null && raw !== undefined) {
      const parsed = JSON.parse(raw);
      if (shapeOk(parsed, def)) initial = parsed;
    }
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
