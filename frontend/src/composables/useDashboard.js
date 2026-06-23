import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";

// Dashboard cockpit: overlays the live get_cod_cockpit figures onto the sample
// VM (kpis / cash-flow / channels / working-capital). The Auditor narration +
// anomalies stay sample until Phase 4 (the live controls engine).

function vu(n) {
  // → { value, unit } for the big-number KPI display.
  const a = Math.abs(Number(n) || 0), sign = n < 0 ? "−" : "";
  if (a >= 1e6) return { value: sign + (a / 1e6).toFixed(2), unit: "M" };
  if (a >= 1e3) return { value: sign + Math.round(a / 1e3), unit: "K" };
  return { value: sign + Math.round(a), unit: "" };
}
const flat = (n) => { const f = vu(n); return f.value + f.unit; };

/** Merge live cockpit data into the sample VM. Defensive: any bad field → keep sample. */
export function overlayCockpit(base, d) {
  if (!d || !d.company) return base;
  try {
    const kpis = base.kpis.map((x) => ({ ...x }));
    let f;
    f = vu(d.cash_collected_mtd); kpis[0].value = f.value; kpis[0].unit = f.unit;
    f = vu(d.paid_out_mtd); kpis[1].value = f.value; kpis[1].unit = f.unit;
    f = vu(d.net_cash); kpis[2].value = (d.net_cash >= 0 ? "+" : "−") + f.value.replace("−", ""); kpis[2].unit = f.unit;
    f = vu(d.payable); kpis[3].value = f.value; kpis[3].unit = f.unit;

    const flow = d.cash_flow || [];
    const cmax = Math.max(1, ...flow.map((r) => Math.max(Number(r.in) || 0, Number(r.out) || 0)));
    const cashflow = {
      ...base.cashflow,
      totalIn: flat(d.cash_collected_mtd), totalOut: flat(d.paid_out_mtd),
      net: (d.net_cash >= 0 ? "+" : "−") + flat(Math.abs(d.net_cash)),
      days: flow.map((r) => ({
        d: r.day,
        inH: Math.round((Number(r.in) || 0) / cmax * 60) + 2,
        outH: Math.round((Number(r.out) || 0) / cmax * 60) + 2,
        title: `${r.day} · +${Math.round((Number(r.in) || 0) / 1000)}k / −${Math.round((Number(r.out) || 0) / 1000)}k`,
      })),
    };

    const channels = (d.channels || []).slice(0, 5).map((c) => ({
      name: c.account, sub: "",
      amount: Math.round(Number(c.cash_in) || 0).toLocaleString("en-US"),
      share: c.share,
      bar: c.is_clearing ? "linear-gradient(90deg,#fcd34d,#d97706)" : "linear-gradient(90deg,#6ee7b7,#059669)",
      warn: !!c.is_clearing,
    }));

    const arap = {
      ...base.arap,
      arVal: (d.receivable < 0 ? "−" : "") + flat(Math.abs(d.receivable)),
      apVal: flat(d.payable),
    };

    return { ...base, kpis, cashflow, channels: channels.length ? channels : base.channels, arap };
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
