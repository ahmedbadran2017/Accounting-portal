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

// Exact grouped amount — no K/M abbreviation (accounting precision).
export const fmtMAD = (n) => Number(n || 0).toLocaleString(undefined, { maximumFractionDigits: 2 });
