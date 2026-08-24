"""Cost cutover — bring the whole catalogue to corrected cost in light steps.

The correction is deliberately split so no single action is heavy and the team
can watch each one land:

  1. FORWARD (today-dated): reprice every on-hand bin to its corrected landed
     cost in one cutover Stock Reconciliation. Fixes the BALANCE SHEET now.
     Nothing after it reposts, so it is cheap. -> cutover_forward()

  2. PER-MONTH RETRO (back-dated, one month at a time): reprice/pin the corrected
     cost inside a single month and let ERPNext repost that month's Delivery
     Notes, so that month's COGS — and its P&L — read true. Each month is ~16-22k
     ledger rows, a bounded chunk. Applied OLDEST->NEWEST: a later month re-poisons
     an earlier back-dated fix, so the plan only ever offers the next pending
     month. -> cutover_month()

  3. AUDIT (100%): the per-product verify-and-fix already stamps each Item as
     verified (valuation.fix_item_cost). The plan tracks that as the verified %.

Layer 1+2 on the modelled/benchmark cost get the books to ~85% automatically;
the audit layer walks them to 100%. This module's read-only cutover_plan lays the
whole machine out: forward status, the per-month backlog with its COGS delta, and
the verified %. The write actions are gated, audited and reversible.
"""
import json

import frappe
from frappe.utils import flt

from accounting_portal.api.permissions import assert_portal_access
from accounting_portal.api.valuation import _target, _benchmarks

_STATE_KEY = "ap_cutover_state"
_FLOOR = "2026-01-01"


def _state():
    try:
        return json.loads(frappe.db.get_default(_STATE_KEY) or "{}") or {}
    except Exception:
        return {}


@frappe.whitelist()
def cutover_plan(company=None):
    """Read-only. The full cutover laid out: forward status, per-month backlog
    with each month's COGS delta at corrected cost, and the audit verified %."""
    assert_portal_access()
    target = _target(company or "Justyol Morocco")
    if not target:
        return {}
    st = _state()

    # delivered qty & booked COGS per (month, item) — the retro backlog
    rows = frappe.db.sql(
        """SELECT DATE_FORMAT(sle.posting_date,'%%Y-%%m') mo, sle.item_code ic,
                  SUM(-sle.actual_qty) q, SUM(-sle.stock_value_difference) cogs,
                  COUNT(*) n
           FROM `tabStock Ledger Entry` sle
           WHERE sle.company=%s AND sle.is_cancelled=0
             AND sle.voucher_type='Delivery Note' AND sle.posting_date >= %s
           GROUP BY mo, sle.item_code""", (target, _FLOOR), as_dict=True)
    items = list({r.ic for r in rows})
    bench = _benchmarks(target, items) if items else {}

    months = {}
    for r in rows:
        m = months.setdefault(r.mo, {"month": r.mo, "rows": 0, "units": 0.0,
                                     "cogs_booked": 0.0, "cogs_corrected": 0.0,
                                     "priced_units": 0.0, "unpriced_units": 0.0})
        m["rows"] += int(r.n)
        m["units"] += flt(r.q)
        m["cogs_booked"] += flt(r.cogs)
        b = flt(bench.get(r.ic))
        if b > 0:
            m["cogs_corrected"] += b * flt(r.q)
            m["priced_units"] += flt(r.q)
        else:
            m["cogs_corrected"] += flt(r.cogs)   # unknown cost -> leave as booked
            m["unpriced_units"] += flt(r.q)

    done = set(st.get("months_done") or [])
    out = []
    ready_set = False
    for mo in sorted(months):
        d = months[mo]
        d["delta"] = round(d["cogs_corrected"] - d["cogs_booked"])
        for k in ("cogs_booked", "cogs_corrected", "units", "priced_units", "unpriced_units"):
            d[k] = round(d[k])
        d["status"] = "done" if mo in done else "pending"
        # oldest->newest discipline: only the first pending month is actionable
        d["ready"] = False
        if d["status"] == "pending" and not ready_set:
            d["ready"] = True
            ready_set = True
        out.append(d)

    vtot = len(items)
    vdone = frappe.db.sql(
        """SELECT COUNT(DISTINCT reference_name) FROM `tabAccounting Portal Action`
           WHERE reference_doctype='Item' AND status='Posted'
             AND IFNULL(reference_name,'')<>''""")[0][0]
    total_delta = round(sum(m["delta"] for m in out))
    return {
        "company": target,
        "forward_done": bool(st.get("forward_done")),
        "months": out,
        "months_done": sorted(done),
        "total_delta": total_delta,
        "verified": {"total": vtot, "done": int(vdone),
                     "pct": round(100.0 * int(vdone) / vtot, 1) if vtot else 0},
        "guard_on": True,
    }
