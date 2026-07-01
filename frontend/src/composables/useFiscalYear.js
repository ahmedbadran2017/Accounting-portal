import { ref, computed } from "vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { usePersistedRef } from "@/composables/usePersistedRef";

// Shared fiscal-year filter for the banking screens. Bank balances are cumulative
// (they carry forward across years), so instead of one running mess this exposes,
// per year: opening (carried forward) → in/out (this year) → closing. Selecting a
// year lets you isolate where a problem started without breaking the balance chain.
// Module-level state → one selection shared across every banking screen.

const years = ref([]);           // [{name, start, end}]
const current = ref(null);
const loaded = ref(false);
// "all" = all-time (no period); otherwise a Fiscal Year name.
const selected = usePersistedRef("ap_fiscal_year", "all");

export function useFiscalYear() {
  async function loadYears() {
    if (loaded.value) return;
    loaded.value = true;
    try {
      const r = await api.call("accounting_portal.api.reconciliation.fiscal_years", { company: currentCompany() });
      years.value = r?.years || [];
      current.value = r?.current || null;
      // Default to the current fiscal year the first time (nothing persisted yet).
      if (selected.value === "all" && !localStorageHas("ap_fiscal_year") && current.value) selected.value = current.value;
    } catch { years.value = []; }
  }
  const fy = computed(() => {
    if (selected.value === "all") return { name: "all", from: null, to: null };
    const y = years.value.find((x) => x.name === selected.value);
    return y ? { name: y.name, from: y.start, to: y.end } : { name: "all", from: null, to: null };
  });
  const filterValue = () => (fy.value.from ? { from_date: fy.value.from, to_date: fy.value.to } : {});
  return { years, current, selected, fy, filterValue, loadYears };
}

function localStorageHas(k) { try { return localStorage.getItem(k) !== null; } catch { return false; } }
