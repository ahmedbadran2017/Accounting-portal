import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";

// Dashboard cockpit — a CFO daily view built from live ERPNext figures
// (get_cod_cockpit). KPIs, the auditor digest and the working-capital block are
// all computed from real numbers; the sample VM is only a fallback shape.

const pick = (l, en, ar, fr) => (l === "ar" ? ar : l === "fr" ? fr : en);

function vu(n) {
  // → { value, unit } for the big KPI number (carries a − for negatives).
  const a = Math.abs(Number(n) || 0), s = n < 0 ? "−" : "";
  if (a >= 1e6) return { value: s + (a / 1e6).toFixed(2), unit: "M" };
  if (a >= 1e3) return { value: s + Math.round(a / 1e3), unit: "K" };
  return { value: s + Math.round(a), unit: "" };
}
function compact(n) {
  const a = Math.abs(Number(n) || 0), s = n < 0 ? "−" : "";
  if (a >= 1e6) return s + (a / 1e6).toFixed(2) + "M";
  if (a >= 1e3) return s + Math.round(a / 1e3) + "K";
  return s + Math.round(a);
}

// A 100×26 SVG polyline for a KPI sparkline, normalised from a number series.
export function sparkPts(arr) {
  const a = arr && arr.length > 1 ? arr : [0, 0];
  const min = Math.min(...a), max = Math.max(...a), range = max - min || 1;
  const w = 100, h = 26, pad = 3;
  return a.map((v, i) => `${((i / (a.length - 1)) * w).toFixed(1)},${(h - pad - ((v - min) / range) * (h - 2 * pad)).toFixed(1)}`).join(" ");
}

function cfoKpis(d, l) {
  const cohPos = d.cash_on_hand >= 0, netPos = d.net_cash >= 0;
  const coh = vu(d.cash_on_hand), col = vu(d.cash_collected_mtd), net = vu(Math.abs(d.net_cash)), pay = vu(d.payable);
  // Real daily series → sparklines.
  const flow = d.cash_flow || [];
  const inS = flow.map((r) => Number(r.in) || 0);
  const outS = flow.map((r) => Number(r.out) || 0);
  const netS = flow.map((r) => (Number(r.in) || 0) - (Number(r.out) || 0));
  let acc = 0; const cumS = netS.map((v) => (acc += v));
  return [
    {
      label: pick(l, "Cash on hand", "النقدية الفعلية", "Trésorerie"),
      value: coh.value, unit: coh.unit, up: cohPos, icon: "coins",
      ic: cohPos ? "#047857" : "#be123c", ibg: cohPos ? "#ecfdf5" : "#fff1f2", spark: sparkPts(cumS),
      sub: pick(l, `Bank ${compact(d.bank_balance)} · Cash ${compact(d.cash_balance)}`,
        `بنك ${compact(d.bank_balance)} · كاش ${compact(d.cash_balance)}`,
        `Banque ${compact(d.bank_balance)} · Caisse ${compact(d.cash_balance)}`),
    },
    {
      label: pick(l, "Collected (MTD)", "محصّل (الشهر)", "Encaissé (mois)"),
      value: col.value, unit: col.unit, up: true, icon: "wallet", ic: "#0369a1", ibg: "#eff6ff", spark: sparkPts(inS),
      sub: pick(l, "COD via Cathadis", "COD عبر Cathadis", "COD via Cathadis"),
    },
    {
      label: pick(l, "Net cash (MTD)", "صافي النقد (الشهر)", "Flux net (mois)"),
      value: (netPos ? "+" : "−") + net.value, unit: net.unit, up: netPos, icon: "trend",
      ic: netPos ? "#047857" : "#be123c", ibg: netPos ? "#ecfdf5" : "#fff1f2", spark: sparkPts(netS),
      sub: pick(l, "collected − paid", "محصّل − مدفوع", "encaissé − décaissé"),
    },
    {
      label: pick(l, "Payables (AP)", "دائنون (AP)", "Dettes (AP)"),
      value: pay.value, unit: pay.unit, up: false, icon: "receipt", ic: "#be123c", ibg: "#fff1f2", spark: sparkPts(outS),
      sub: pick(l, "owed to suppliers", "مستحق للموردين", "dû aux fournisseurs"),
    },
  ];
}

function cfoDigest(d, l) {
  const coh = compact(d.cash_on_hand), col = compact(d.cash_collected_mtd), paid = compact(d.paid_out_mtd);
  const net = (d.net_cash >= 0 ? "+" : "−") + compact(Math.abs(d.net_cash));
  const ar = compact(d.receivable), ap = compact(d.payable);
  const clearing = (d.channels || []).find((c) => c.is_clearing);
  const share = clearing ? clearing.share : null;
  const overdraft = d.cash_balance < 0;
  return pick(l,
    `Cash on hand ${coh} MAD${overdraft ? ` — a ${compact(Math.abs(d.cash_balance))} cash overdraft offsets the bank` : ""}. This month: ${col} collected vs ${paid} paid → net ${net}. Receivables ${ar} (COD over-collection, unmatched to invoices)${share ? `; ${share}% of collection routes through one Cathadis clearing account` : ""}. Payables ${ap}.`,
    `النقدية الفعلية ${coh} درهم${overdraft ? ` — سحب كاش ${compact(Math.abs(d.cash_balance))} يقابل رصيد البنك` : ""}. هذا الشهر: ${col} محصّل مقابل ${paid} مدفوع → صافي ${net}. المدينون ${ar} (تحصيل COD زائد غير مطابق للفواتير)${share ? `؛ ${share}% من التحصيل عبر حساب مقاصّة Cathadis واحد` : ""}. الدائنون ${ap}.`,
    `Trésorerie ${coh} MAD. Ce mois : ${col} encaissé vs ${paid} payé → net ${net}. Créances ${ar} (sur-encaissement COD non lettré). Dettes ${ap}.`);
}

function cfoChips(d, l) {
  const netPos = d.net_cash >= 0;
  const clearing = (d.channels || []).find((c) => c.is_clearing);
  const chips = [
    { label: pick(l, `Net cash ${netPos ? "+" : "−"}${compact(Math.abs(d.net_cash))}`, `صافي ${netPos ? "+" : "−"}${compact(Math.abs(d.net_cash))}`, `Net ${netPos ? "+" : "−"}${compact(Math.abs(d.net_cash))}`), dot: netPos ? "#34d399" : "#f87171", go: { module: "banking" } },
  ];
  if (clearing) chips.push({ label: pick(l, `${clearing.share}% via Cathadis`, `${clearing.share}% عبر Cathadis`, `${clearing.share}% via Cathadis`), dot: "#fbbf24", go: { module: "banking", sub: "variance" } });
  if (d.receivable < 0) chips.push({ label: pick(l, `Debtors ${compact(d.receivable)}`, `مدينون ${compact(d.receivable)}`, `Créances ${compact(d.receivable)}`), dot: "#f87171", go: { module: "banking", sub: "variance" } });
  return chips;
}

/** Build the CFO view-model from live cockpit data; fall back to the sample VM. */
export function overlayCockpit(base, d, l = "en") {
  if (!d || !d.company) return base;
  try {
    const flow = d.cash_flow || [];
    const cmax = Math.max(1, ...flow.map((r) => Math.max(Number(r.in) || 0, Number(r.out) || 0)));
    const cashflow = {
      ...base.cashflow,
      totalIn: compact(d.cash_collected_mtd), totalOut: compact(d.paid_out_mtd),
      net: (d.net_cash >= 0 ? "+" : "−") + compact(Math.abs(d.net_cash)),
      days: flow.map((r) => ({
        d: r.day,
        inH: Math.round((Number(r.in) || 0) / cmax * 60) + 2,
        outH: Math.round((Number(r.out) || 0) / cmax * 60) + 2,
        title: `${r.day} · +${Math.round((Number(r.in) || 0) / 1000)}k / −${Math.round((Number(r.out) || 0) / 1000)}k`,
      })),
    };
    const channels = (d.channels || []).slice(0, 5).map((c) => ({
      name: c.account, sub: "", amount: Math.round(Number(c.cash_in) || 0).toLocaleString("en-US"),
      share: c.share,
      bar: c.is_clearing ? "linear-gradient(90deg,#fcd34d,#d97706)" : "linear-gradient(90deg,#6ee7b7,#059669)",
      warn: !!c.is_clearing,
    }));
    const arap = {
      ...base.arap,
      arVal: compact(d.receivable), apVal: compact(d.payable),
    };
    return {
      ...base,
      digest: cfoDigest(d, l), digestChips: cfoChips(d, l), kpis: cfoKpis(d, l),
      cashflow, channels: channels.length ? channels : base.channels, arap,
    };
  } catch {
    return base;
  }
}

export function useDashboard() {
  async function loadCockpit() {
    try {
      const d = await api.call("accounting_portal.api.dashboard.get_cod_cockpit", { company: currentCompany() });
      return d && d.company ? d : null;
    } catch {
      return null;
    }
  }
  return { loadCockpit };
}
