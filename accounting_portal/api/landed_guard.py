"""Landed-account guard — new freight bills belong on 153.03, not P&L.

The forward doctrine (Landed Cockpit): an inbound-freight/customs bill debits
153.03 (Expenses Included In Valuation, balance sheet) and is capitalized into
stock per shipment — 153.03 trends to zero and the P&L is never touched. The
habit it replaces: 131 new PIs hit the 770.07 P&L family in the last 30 days,
each one needing retro correction later. This guard breaks the habit at entry.

Runtime-togglable (mirrors fx_guard / stock_guard):
    ap_freight_153_guard      "0" disables (default on)
    ap_freight_redirect       JSON list of blocked account prefixes
                              (default ["770.07"])
"""
import frappe

from accounting_portal.api.permissions import assert_portal_access, can_manage_users

SALES = "Justyol Morocco"


def _enabled():
    v = frappe.db.get_default("ap_freight_153_guard")
    if v in (None, ""):
        return True
    return str(v) == "1"


def _patterns():
    # "770.0.7" is the malformed twin of 770.07 (a real account carrying 288K of
    # sea freight) — it does NOT match the 770.07 prefix, so name it explicitly
    default = ["770.07", "770.0.7"]
    try:
        p = frappe.parse_json(frappe.db.get_default("ap_freight_redirect") or "[]") or []
        return [str(x) for x in p] or default
    except Exception:
        return default


def validate_landed_account(doc, method=None):
    """doc_events validate for Purchase Invoice."""
    if not _enabled() or doc.company != SALES:
        return
    pats = tuple(_patterns())
    # freight arrives BOTH ways: as an item line (expense_account) and as a
    # charge row (account_head) — guarding only the items let charge-row
    # freight through untouched
    bad = [(d.expense_account or "") for d in (doc.items or [])
           if (d.expense_account or "").startswith(pats)]
    bad += [(t.account_head or "") for t in (doc.taxes or [])
            if (t.account_head or "").startswith(pats)]
    if not bad:
        return
    clearing = frappe.db.get_value("Company", SALES, "expenses_included_in_valuation") \
        or "153.03 - Expenses Included In Valuation"
    accs = ", ".join(sorted(set(bad))[:3])
    frappe.throw(
        f"New freight/import bills must NOT hit the P&L family ({accs}). "
        f"Book them to <b>{clearing}</b> — in the portal's New-expense screen tick "
        "<b>Freight bill (landed)</b> and the account is set automatically; the bill "
        "then appears in Purchases → Shipments for allocation to its shipment. "
        "(A Super Admin can temporarily disable this guard if truly needed.)",
        title="Freight goes to 153.03")


@frappe.whitelist()
def freight_guard_settings():
    assert_portal_access()
    return {"enabled": _enabled(), "patterns": _patterns()}


@frappe.whitelist()
def set_freight_guard(on=None):
    if not can_manage_users():
        frappe.throw("Restricted to the Super Admin", frappe.PermissionError)
    if on is not None:
        frappe.db.set_default("ap_freight_153_guard",
                              "1" if str(on) in ("1", "true", "True", "yes", "on") else "0")
    frappe.db.commit()
    return freight_guard_settings()
