import { liveOrSample, currentCompany } from "@/composables/useLive";
import { ANOMALIES } from "@/data/copilot";

// Sample findings shaped like the backend run_controls() output, so the feed
// renders the same whether live or offline.
const SAMPLE_FINDINGS = {
  summary: { high: 4, medium: 2, low: 0, count: 6, exposure: 694000000 },
  findings: [
    { id: "stock_cogs", severity: "high", metric: "Stock in hand", title: "Perpetual inventory isn't relieving to COGS", detail: "Stock-in-hand carries 687,123,522 MAD while Stock Adjustment absorbs −680,873,788. Deliveries aren't posting COGS, so margin is unmeasurable.", amount: 687123522, account: "71.004 - Stock Adjustment - JM", recommendation: "Reconcile stock and post COGS on delivery.", drill: { module: "items", sub: "", label: "Inventory health" } },
    { id: "unmatched_cod", severity: "high", metric: "Debtors (net)", title: "Collected COD not applied to invoices", detail: "Debtors show a net credit of −2,851,163 MAD — carrier cash sits unallocated instead of clearing invoices.", amount: -2851163, account: "Debtors", recommendation: "Match remittances in Banking → COD reconcile.", drill: { module: "banking", sub: "", label: "COD reconcile" } },
    { id: "correction_pile", severity: "high", metric: "Correction Need", title: "“Correction Need” pile is material", detail: "Correction Need holds 3,685,385 MAD parked for correction — it distorts the P&L.", amount: 3685385, account: "71.999 - Correction Need Income Account - JM", recommendation: "Triage and reclassify.", drill: { module: "accountant", sub: "", label: "Journals" } },
    { id: "negative_cash", severity: "high", metric: "Cash on hand", title: "Cash account is overdrawn", detail: "Cash shows −845,264 MAD — impossible for physical cash; points to unrecorded receipts.", amount: -845264, account: "Cash", recommendation: "Reconcile cash movements.", drill: { module: "banking", sub: "", label: "Banking" } },
    { id: "grni_gap", severity: "medium", metric: "GRNI", title: "Goods received but not billed", detail: "GRNI stands at −4,717,445 MAD — the three-way match is incomplete.", amount: -4717445, account: "321.01 - Stock Received But Not Billed - JM", recommendation: "Match bills to receipts.", drill: { module: "purchases", sub: "", label: "Purchases" } },
    { id: "payables_load", severity: "medium", metric: "Creditors", title: "Large supplier payable outstanding", detail: "Creditors stand at −3,516,655 MAD. Review the 90+ concentration against cash.", amount: -3516655, account: "Creditors", recommendation: "Review AP aging.", drill: { module: "reports", sub: "statements", label: "AP aging" } },
  ],
};

export async function loadControls() {
  // Full audit: balance controls + entry-level forensics + report tie-outs.
  return liveOrSample("accounting_portal.api.auditor.full_findings", { company: currentCompany() }, () => SAMPLE_FINDINGS);
}

const ICON = { stock_cogs: "box", unmatched_cod: "coins", correction_pile: "ledger", negative_cash: "bank", grni_gap: "truck", payables_load: "doc" };
const CAT_ICON = { entry: "ledger", report: "scale", control: "shield", anomaly: "alert" };

// Map a backend finding into the Copilot anomaly-feed item shape.
export function toFeedItem(f) {
  return {
    id: f.id, sev: f.severity, icon: ICON[f.id] || CAT_ICON[f.category] || "alert",
    category: f.category || "control",
    title: () => f.title,
    desc: () => f.detail,
    ref: f.account || f.metric || "",
    go: f.drill || null,
    cta: () => (f.drill && f.drill.label) || "Open",
    amount: f.amount, recommendation: f.recommendation, score: f.score || 0,
  };
}

export function feedFrom(findings) {
  const arr = (findings || []).map(toFeedItem);
  return arr.length ? arr : ANOMALIES;
}
