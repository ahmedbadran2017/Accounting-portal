"""FX guard — blocks purchase documents booked at an implausible exchange rate.

THE root-cause fix for the cost disease: Morocco receipts were saved with
conversion_rate ≈ 43 (the USD→TRY figure) instead of ≈ 9.5 (USD→MAD), inflating
inventory ~4.5× and poisoning the moving average — after which every downstream
correction is expensive. This hook rejects the bad document AT ENTRY, with a
clear message, before it can touch the stock ledger.

Wired via hooks.doc_events on Purchase Receipt + Purchase Invoice (both feed
valuation). The reference rate comes from the books' own Currency Exchange
records (direct pair, else cross-rated through USD — same mechanic as
cost_trace); if the books hold no reference for a pair the guard stays silent
rather than block legitimate work on a hunch.

Runtime-togglable (no redeploy): Super Admin can flip `ap_fx_guard` off /
adjust `ap_fx_guard_tolerance` — mirrors the approval-gate toggle pattern.
"""
import frappe
from frappe.utils import flt

from accounting_portal.api.permissions import assert_portal_access, can_manage_users

_DEFAULT_TOLERANCE = 0.40   # ±40% around the reference — catches ≥ ~1.7× errors


def _enabled():
    v = frappe.db.get_default("ap_fx_guard")
    if v in (None, ""):
        return True   # secure by default
    return str(v) == "1"


def _tolerance():
    v = frappe.db.get_default("ap_fx_guard_tolerance")
    try:
        t = float(v)
        return t if 0.05 <= t <= 2 else _DEFAULT_TOLERANCE
    except (TypeError, ValueError):
        return _DEFAULT_TOLERANCE


def _ce_rate(from_cur, to_cur, date):
    """Latest Currency Exchange at/just-before date (fallback earliest)."""
    r = frappe.db.sql(
        """SELECT exchange_rate FROM `tabCurrency Exchange`
           WHERE from_currency=%s AND to_currency=%s AND date<=%s
           ORDER BY date DESC LIMIT 1""", (from_cur, to_cur, date))
    if not r:
        r = frappe.db.sql(
            """SELECT exchange_rate FROM `tabCurrency Exchange`
               WHERE from_currency=%s AND to_currency=%s ORDER BY date ASC LIMIT 1""",
            (from_cur, to_cur))
    return flt(r[0][0]) if r else 0.0


def _reference_rate(doc_cur, comp_cur, date):
    """doc_cur→comp_cur: direct record, else cross-rated through USD."""
    direct = _ce_rate(doc_cur, comp_cur, date)
    if direct > 0:
        return direct
    to_comp = _ce_rate("USD", comp_cur, date)
    to_doc = _ce_rate("USD", doc_cur, date)
    if to_comp > 0 and to_doc > 0:
        return to_comp / to_doc
    return 0.0


def validate_fx(doc, method=None):
    """doc_events validate for Purchase Receipt / Purchase Invoice."""
    if not _enabled():
        return
    comp_cur = frappe.get_cached_value("Company", doc.company, "default_currency")
    if not doc.currency or doc.currency == comp_cur:
        return
    used = flt(doc.conversion_rate)
    if used <= 0:
        return   # ERPNext's own validation handles missing rates
    date = str(doc.get("posting_date") or frappe.utils.nowdate())[:10]
    ref = _reference_rate(doc.currency, comp_cur, date)
    if ref <= 0:
        return   # no basis to judge — do not block
    tol = _tolerance()
    lo, hi = ref * (1 - tol), ref * (1 + tol)
    if lo <= used <= hi:
        return
    frappe.throw(
        f"Exchange rate looks wrong: this {doc.doctype} converts {doc.currency}→{comp_cur} "
        f"at <b>{used:,.4f}</b>, but the reference rate for {date} is <b>{ref:,.4f}</b> "
        f"(allowed {lo:,.2f}–{hi:,.2f}). A wrong rate here permanently poisons inventory "
        f"cost and COGS.<br>Fix the document's exchange rate; if the rate is genuinely "
        f"correct, update the Currency Exchange record for {doc.currency}→{comp_cur} "
        f"(or a Super Admin can adjust the FX-guard in the portal).",
        title="FX guard: implausible exchange rate")


@frappe.whitelist()
def fx_guard_settings():
    """Read the guard state for the Settings screen."""
    assert_portal_access()
    return {"enabled": _enabled(), "tolerance": _tolerance()}


@frappe.whitelist()
def set_fx_guard(on=None, tolerance=None):
    """Toggle/tune the guard. Super Admin only; persisted; no redeploy."""
    if not can_manage_users():
        frappe.throw("Restricted to the Super Admin", frappe.PermissionError)
    if on is not None:
        frappe.db.set_default("ap_fx_guard", "1" if str(on) in ("1", "true", "True", "yes", "on") else "0")
    if tolerance not in (None, ""):
        t = flt(tolerance)
        if not (0.05 <= t <= 2):
            frappe.throw("Tolerance must be between 0.05 and 2")
        frappe.db.set_default("ap_fx_guard_tolerance", str(t))
    frappe.db.commit()
    return fx_guard_settings()
