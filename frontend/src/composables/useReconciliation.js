import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";

// COD reconciliation (Pillar 1) read bridge — live ERPNext with graceful nulls.
export function useReconciliation() {
  async function summary() {
    try {
      return await api.call("accounting_portal.api.reconciliation.cod_summary", { company: currentCompany() });
    } catch {
      return null;
    }
  }
  async function unmatchedPayments(limit = 50) {
    try {
      const rows = await api.call("accounting_portal.api.reconciliation.unmatched_payments", { company: currentCompany(), limit });
      return { live: true, rows: Array.isArray(rows) ? rows : [] };
    } catch {
      return { live: false, rows: [] };
    }
  }
  async function candidates(payment) {
    try {
      return await api.call("accounting_portal.api.reconciliation.match_candidates", { payment });
    } catch {
      return null;
    }
  }
  return { summary, unmatchedPayments, candidates };
}

export const fmtMAD = (n) => {
  const a = Math.abs(Number(n) || 0), s = n < 0 ? "−" : "";
  if (a >= 1e6) return s + (a / 1e6).toFixed(2) + "M";
  if (a >= 1e3) return s + Math.round(a / 1e3) + "K";
  return s + Math.round(a);
};
