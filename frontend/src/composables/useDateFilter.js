import { useI18n } from "vue-i18n";
import { usePersistedRef } from "@/composables/usePersistedRef";

// Shared date-range filter for the paginated lists. Presets are persisted per
// page (storeKey) and resolved to { from_date, to_date } passed server-side.
// onApply(filterValue) is called whenever the selection changes — typically
// `(f) => st.setFilters(f)` to drive a useServerTable.
export function useDateFilter(storeKey, onApply, defaultPreset = "all") {
  const { locale } = useI18n();
  const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
  const PRESETS = [
    { key: "all", label: () => L("All time", "كل الوقت", "Tout") },
    { key: "today", label: () => L("Today", "اليوم", "Auj.") },
    { key: "yesterday", label: () => L("Yesterday", "أمس", "Hier") },
    { key: "month", label: () => L("This month", "هذا الشهر", "Ce mois") },
    { key: "lastmonth", label: () => L("Last month", "الشهر الماضي", "Mois dern.") },
    { key: "quarter", label: () => L("This quarter", "هذا الربع", "Trimestre") },
    { key: "year", label: () => L("This year", "هذه السنة", "Année") },
    { key: "range", label: () => L("Range", "نطاق", "Plage") },
  ];
  const preset = usePersistedRef(`ap_${storeKey}_preset`, defaultPreset);
  const from = usePersistedRef(`ap_${storeKey}_from`, "");
  const to = usePersistedRef(`ap_${storeKey}_to`, "");

  function bounds(k) {
    const iso = (d) => d.toISOString().slice(0, 10);
    const now = new Date(), y = now.getFullYear(), m = now.getMonth();
    if (k === "today") return [iso(now), iso(now)];
    if (k === "yesterday") { const yd = new Date(y, m, now.getDate() - 1); return [iso(yd), iso(yd)]; }
    if (k === "month") return [iso(new Date(y, m, 1)), iso(now)];
    if (k === "lastmonth") return [iso(new Date(y, m - 1, 1)), iso(new Date(y, m, 0))];
    if (k === "quarter") { const q = Math.floor(m / 3) * 3; return [iso(new Date(y, q, 1)), iso(now)]; }
    if (k === "year") return [iso(new Date(y, 0, 1)), iso(now)];
    if (k === "range") return [from.value || null, to.value || null];
    return [null, null];
  }
  function filterValue() { const [fd, td] = bounds(preset.value); return { from_date: fd || undefined, to_date: td || undefined }; }
  function setPreset(k) { preset.value = k; if (k !== "range") onApply(filterValue()); }
  function applyRange() { if (from.value && to.value) onApply(filterValue()); }

  return { PRESETS, preset, from, to, bounds, filterValue, setPreset, applyRange };
}
