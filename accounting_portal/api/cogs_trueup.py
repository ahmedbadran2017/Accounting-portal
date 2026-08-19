"""Monthly COGS true-up (B6) — make the LEDGER's monthly COGS equal the true
cost, retroactively, without touching the stock ledger.

For each month: booked COGS (GL, 71.801) vs TRUE COGS (units delivered × full
true cost = Maslak-anchored product cost + frozen landed layer). The delta is
posted as a plain month-end Journal Entry between 71.801 and 71.004:

    overstated month:  Cr 71.801 / Dr 71.004   (reduce COGS)
    understated month: Dr 71.801 / Cr 71.004   (zero-cost deliveries)

GL-only → no stock ledger, no repost, fully reversible (cancel the JE).
Net P&L impact of each JE is ZERO (both accounts live in the cost block) — it
moves cost between "COGS" and the labeled correction bucket so the monthly
71.801 line reads true. 71.004's accumulated balance is extinguished later in
the intercompany/GRNI cleanup (E5).

Discipline (build-first plan): requires the frozen landed basis, so the
true-cost basis used here matches what the catalogue crawl applies.
"""
import calendar
import json

import frappe
from frappe.utils import flt, nowdate

from accounting_portal.api import _actions
from accounting_portal.api.permissions import (
    assert_can_write, assert_portal_access, resolve_companies)

SALES = "Justyol Morocco"
TRUEUP_ACTION = "Monthly COGS true-up"
# booked COGS families: 71.801 (the proper DN cost account) + 71.002.5 (the
# mistyped internal-invoicing account that 33k 2026 DN rows ALSO cost into —
# 1.9M MAD; leaving it out understated booked COGS and would have made the
# true-up double-count that slice)
COGS_LIKES = ("71.801%", "71.002.5%", "71.999%")
COGS_LIKE = "71.801%"          # the true-up JE still POSTS to 71.801 only
BUCKET_LIKE = "71.004%"        # the labeled correction bucket (Stock Adjustment)


def _target(company):
    companies = resolve_companies(company)
    if not companies:
        return None
    return company if (company and company in companies) else companies[0]


def _accounts(target):
    # order_by makes the pick deterministic when several 71.x leaves match —
    # otherwise the correcting JE could land in a different sibling per call
    cogs = frappe.db.get_value(
        "Account", {"company": target, "name": ["like", COGS_LIKE], "is_group": 0, "disabled": 0},
        order_by="name asc")
    bucket = frappe.db.get_value(
        "Account", {"company": target, "name": ["like", BUCKET_LIKE], "is_group": 0, "disabled": 0},
        order_by="name asc")
    if not (cogs and bucket):
        frappe.throw("COGS (71.801) / correction bucket (71.004) account not found")
    return cogs, bucket


def _true_month_costs(target, year):
    """{month: {"true": Σ qty×(product+landed), "qty": all units, "priced_qty"}}
    computed off the same engines the crawl uses."""
    from accounting_portal.api.cost_trace import _true_cost_bulk, _fx_series
    from accounting_portal.api.landed_prep import get_basis, _landed_units_bulk
    basis = get_basis(year=year)
    rows = frappe.db.sql(
        """SELECT MONTH(dn.posting_date) m, dni.item_code ic, SUM(dni.qty) q
           FROM `tabDelivery Note Item` dni JOIN `tabDelivery Note` dn ON dn.name=dni.parent
           WHERE dn.company=%s AND dn.docstatus=1 AND YEAR(dn.posting_date)=%s
           GROUP BY m, dni.item_code""", (target, int(year)), as_dict=True)
    items = list({r.ic for r in rows})
    tc = _true_cost_bulk(items, _fx_series()) if items else {}
    landed = _landed_units_bulk(items, year=year) if items else {}
    # ONE truth: an item the team already FIXED is priced at its APPLIED rate
    # (what the stock ledger actually carries), not the engine estimate —
    # otherwise the true-up would restate months to a basis contradicting
    # the inventory the fixes just built
    from accounting_portal.api.cost_trace import _fixed_items, _fix_is_current
    fixedmap = _fixed_items()
    basis_on = (basis or {}).get("on")
    out = {}
    for r in rows:
        d = out.setdefault(int(r.m), {"true": 0.0, "qty": 0.0, "priced_qty": 0.0})
        q = flt(r.q)
        d["qty"] += q
        fx = fixedmap.get(r.ic)
        if fx and _fix_is_current(fx["stamp"], basis_on) and flt(fx["rate"]) > 0:
            d["true"] += q * flt(fx["rate"])
            d["priced_qty"] += q
            continue
        t = tc.get(r.ic)
        if t:
            full = flt(t["cost_mad"]) + flt(landed.get(r.ic))
            d["true"] += q * full
            d["priced_qty"] += q
    return out, bool(basis)


def _booked_by_month(target, year):
    return {int(m): flt(v) for m, v in frappe.db.sql(
        """SELECT MONTH(posting_date), SUM(debit-credit) FROM `tabGL Entry`
           WHERE company=%s AND (account LIKE %s OR account LIKE %s OR account LIKE %s)
             AND is_cancelled=0 AND YEAR(posting_date)=%s
           GROUP BY MONTH(posting_date)""",
        (target, COGS_LIKES[0], COGS_LIKES[1], COGS_LIKES[2], int(year)))}


def _posted_trueups(target, year, basis_on=None):
    """{month: {name, voucher_no, stale_basis}} for already-posted true-up
    actions. `stale_basis` flags a month posted under a basis that was later
    unfrozen/refrozen — its figures no longer match the current basis."""
    rows = frappe.get_all(
        "Accounting Portal Action",
        filters={"action_type": TRUEUP_ACTION, "status": "Posted", "company": target,
                 "reference_doctype": "Fiscal Year", "reference_name": str(year)},
        fields=["name", "voucher_no", "dedupe_key", "payload"])
    out = {}
    for r in rows:
        try:
            m = int(r.dedupe_key.split(":")[2].split("-")[1])   # cogstrueup:<co>:<YYYY-MM>
            stamped = None
            try:
                stamped = (json.loads(r.payload or "{}") or {}).get("basis_on")
            except Exception:
                pass
            out[m] = {"name": r.name, "voucher_no": r.voucher_no,
                      "stale_basis": bool(basis_on and stamped and stamped != basis_on)}
        except Exception:
            continue
    return out


@frappe.whitelist()
def monthly_review(company=None, year=None):
    """The month-by-month table: booked vs true COGS, delta, coverage, status."""
    assert_portal_access()
    target = _target(company) or SALES
    year = int(year) if year else int(nowdate()[:4])
    true_m, basis_frozen = _true_month_costs(target, year)
    booked = _booked_by_month(target, year)
    from accounting_portal.api.landed_prep import get_basis
    posted = _posted_trueups(target, year, basis_on=(get_basis(year=year) or {}).get("on"))
    today = nowdate()
    cur_y, cur_m = int(today[:4]), int(today[5:7])
    months = sorted(set(list(true_m.keys()) + list(booked.keys())))
    rows = []
    for m in months:
        t = true_m.get(m, {})
        b = flt(booked.get(m, 0))
        tr = round(flt(t.get("true", 0)), 2)
        cov = round(100 * flt(t.get("priced_qty", 0)) / max(flt(t.get("qty", 1)), 1), 1)
        po = posted.get(m)
        # a RETRO repost restates booked COGS underneath a standing true-up JE —
        # the month is then corrected twice. A posted month whose LIVE residual
        # delta is still material is exactly that case: flag it for
        # revert-and-repost instead of letting the double-count sit silently.
        if po and abs(b - tr) > max(500, abs(tr) * 0.02):
            po = dict(po)
            po["stale_amount"] = round(b - tr)
        rows.append({
            "month": f"{year}-{m:02d}", "booked": round(b), "true": round(tr),
            "delta": round(b - tr), "coverage_pct": cov,
            "open_month": (year == cur_y and m >= cur_m),
            "posted": po,
        })
    return {"company": target, "year": year, "basis_frozen": basis_frozen, "rows": rows}


_COVERAGE_FLOOR = 95.0   # % of delivered units that must carry a true cost


def _month_figures(target, year, month):
    """(booked, true, delta, coverage_pct, basis) for one month — shared by the
    proposal AND the poster, so the posted JE always carries post-time figures."""
    from accounting_portal.api.landed_prep import get_basis
    basis = get_basis(year=year)
    if not basis:
        frappe.throw("Landed basis is not frozen — freeze it in the Landed Cockpit first "
                     "so every month is trued-up on the same final basis")
    true_m, _ = _true_month_costs(target, year)
    t = true_m.get(month, {})
    booked = flt(_booked_by_month(target, year).get(month, 0))
    tr = flt(t.get("true", 0))
    cov = round(100 * flt(t.get("priced_qty", 0)) / max(flt(t.get("qty", 1)), 1), 1)
    return booked, tr, round(booked - tr, 2), cov, basis


@frappe.whitelist()
def post_trueup(company=None, year=None, month=None, note=None):
    """Post ONE month's true-up JE (gated, audited, reversible). Figures are
    recomputed INSIDE the poster at post time; blocks open/current months, low
    true-cost coverage, an unfrozen basis, or an already-posted month."""
    assert_can_write()
    target = _target(company) or SALES
    year, month = (int(year) if year else int(nowdate()[:4])), int(month)
    if not (1 <= month <= 12):
        frappe.throw("month 1–12 required")
    if year < 2026:
        frappe.throw("Policy floor: closed years are never restated (fix-forward) — true-ups post 2026 onward")
    today = nowdate()
    if (year, month) >= (int(today[:4]), int(today[5:7])):
        frappe.throw(f"{year}-{month:02d} is still open — a true-up now would go stale with every "
                     "delivery; post it after month-end")
    if month in _posted_trueups(target, year):
        frappe.throw(f"{year}-{month:02d} already has a posted true-up — revert it first to re-post")
    booked, tr, delta, cov, basis = _month_figures(target, year, month)
    if cov < _COVERAGE_FLOOR:
        frappe.throw(f"Only {cov}% of {year}-{month:02d} delivered units carry a true cost "
                     f"(floor {_COVERAGE_FLOOR}%) — unpriced items would be trued-up to ZERO cost, "
                     "over-reducing COGS. Price them (Verify & Fix / manual) first")
    if abs(delta) < 1:
        frappe.throw("Nothing to true-up — booked equals true for this month")
    last_day = calendar.monthrange(year, month)[1]
    posting_date = f"{year}-{month:02d}-{last_day:02d}"
    cogs, bucket = _accounts(target)
    return _actions.execute(
        TRUEUP_ACTION, target, f"cogstrueup:{target}:{year}-{month:02d}",
        payload={"posting_date": posting_date, "delta": delta,
                 "cogs_account": cogs, "bucket_account": bucket,
                 "booked": booked, "true": round(tr, 2), "coverage_pct": cov,
                 "basis_on": basis.get("on")},
        amount=abs(delta),
        reference_doctype="Fiscal Year", reference_name=str(year),
        notes=(note or f"COGS true-up {year}-{month:02d}: booked {booked:,.0f} → true {tr:,.0f} (Δ {delta:,.0f})"))


def _trueup_poster(action):
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    # Re-resolve figures at POST time (approval can lag the proposal by days;
    # a Failed retry must not replay stale numbers). Payload keeps the
    # proposal-time figures for the audit trail only.
    y, m = int(p["posting_date"][:4]), int(p["posting_date"][5:7])
    booked, tr, delta, cov, _basis = _month_figures(action.company, y, m)
    if cov < _COVERAGE_FLOOR:
        frappe.throw(f"Coverage dropped to {cov}% since the proposal — re-propose after pricing")
    if abs(delta) < 1:
        frappe.throw("Booked already equals true for this month — nothing to post")
    p["booked"], p["true"], p["delta"] = booked, round(tr, 2), delta
    # P&L accounts require a cost center on JE lines in most configs
    cc = frappe.get_cached_value("Company", action.company, "cost_center")
    # overstated (delta>0): Cr COGS / Dr bucket · understated: mirror
    cogs_leg = {"account": p["cogs_account"], "cost_center": cc,
                ("credit_in_account_currency" if delta > 0 else "debit_in_account_currency"): abs(delta)}
    bucket_leg = {"account": p["bucket_account"], "cost_center": cc,
                  ("debit_in_account_currency" if delta > 0 else "credit_in_account_currency"): abs(delta)}
    frappe.db.savepoint("trueup_atomic")
    try:
        je = frappe.get_doc({
            "doctype": "Journal Entry", "company": action.company,
            "voucher_type": "Journal Entry", "posting_date": p["posting_date"],
            "user_remark": (f"Monthly COGS true-up — booked {flt(p['booked']):,.0f} vs true "
                            f"{flt(p['true']):,.0f}; ledger COGS re-stated to true full cost "
                            f"(product + landed). Net P&L impact zero (cost-block reclass)."),
            "accounts": [cogs_leg, bucket_leg],
        })
        je.insert(ignore_permissions=True)
        je.submit()
    except Exception:
        frappe.db.rollback(save_point="trueup_atomic")
        raise
    return {"voucher_type": "Journal Entry", "voucher_no": je.name,
            "result": f"COGS {'-' if delta > 0 else '+'}{abs(delta):,.0f} @ {p['posting_date']}"}


def _trueup_reverter(action):
    if action.voucher_no and frappe.db.exists("Journal Entry", action.voucher_no):
        doc = frappe.get_doc("Journal Entry", action.voucher_no)
        if doc.docstatus == 1:
            doc.cancel()
    return {"voucher_type": "Journal Entry", "voucher_no": action.voucher_no, "result": "cancelled"}


_actions.register_poster(TRUEUP_ACTION, _trueup_poster)
_actions.register_reverter(TRUEUP_ACTION, _trueup_reverter)