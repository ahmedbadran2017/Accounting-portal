import { liveOrSample, currentCompany } from "@/composables/useLive";

const fmt0 = (n) => Math.round(Number(n || 0)).toLocaleString("en-US");
export const money0 = fmt0;

// ---- Sample fallbacks (representative of the live Justyol Morocco books) ----
const SAMPLE_PNL = {
  income: [{ name: "Good Sales at Morocco", amount: 7600000 }, { name: "Shipping income", amount: 210535 }],
  expense: [{ name: "Stock Adjustment", amount: 663000000, account: "71.004 - Stock Adjustment - JM" }, { name: "Last-mile delivery", amount: 540000 }, { name: "Ad spend (Meta)", amount: 167790 }],
  income_total: 7810535, expense_total: 663707790, net: -655897255,
  anomaly: { name: "Stock Adjustment", amount: 663000000, account: "71.004 - Stock Adjustment - JM" },
};
const SAMPLE_BS = { assets: 690000000, liabilities: 12500000, equity: 677500000, check: 0 };
const SAMPLE_AR = { cur: 0, d1_30: 1020, d31_60: 637, d61_90: 0, d90p: 112146, total: 113803, n: 265 };
const SAMPLE_AP = { cur: 281488, d1_30: 208475, d31_60: 900000, d61_90: 771337, d90p: 4809725, total: 6971024, n: 306 };
const SAMPLE_VAT = {
  output: [{ name: "VAT DANIŞ %20", amount: 1514530 }],
  input: [{ name: "VAT %20 (MAD)", amount: -145281 }, { name: "VAT %20", amount: -80109 }, { name: "VAT %10 (MAD)", amount: -48065 }],
  output_total: 1514530, input_total: 273455, net_payable: 1241075,
};

export async function loadPnl() {
  return liveOrSample("accounting_portal.api.reports.pnl", { company: currentCompany() }, () => SAMPLE_PNL);
}
export async function loadBalanceSheet() {
  return liveOrSample("accounting_portal.api.reports.balance_sheet", { company: currentCompany() }, () => SAMPLE_BS);
}
export async function loadArAging() {
  return liveOrSample("accounting_portal.api.reports.ar_aging", { company: currentCompany() }, () => SAMPLE_AR);
}
export async function loadApAging() {
  return liveOrSample("accounting_portal.api.reports.ap_aging", { company: currentCompany() }, () => SAMPLE_AP);
}
export async function loadVat() {
  return liveOrSample("accounting_portal.api.reports.vat_summary", { company: currentCompany() }, () => SAMPLE_VAT);
}

export function agingBuckets(a, L) {
  return [
    { k: L("Current", "جاري", "Courant"), v: a.cur || 0, tone: "ok" },
    { k: "1–30", v: a.d1_30 || 0, tone: "ok" },
    { k: "31–60", v: a.d31_60 || 0, tone: "warn" },
    { k: "61–90", v: a.d61_90 || 0, tone: "warn" },
    { k: "90+", v: a.d90p || 0, tone: "bad" },
  ];
}
