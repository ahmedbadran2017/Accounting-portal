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
    ap_freight_outbound       JSON list of prefixes INSIDE those that are
                              outbound delivery, not inbound freight
"""
import frappe

from accounting_portal.api.permissions import assert_portal_access, can_manage_users

SALES = "Justyol Morocco"


def _enabled():
    v = frappe.db.get_default("ap_freight_153_guard")
    if v in (None, ""):
        return True
    return str(v) == "1"


# Delivery TO the customer lives inside the same 770.07 parent as inbound
# freight, and it is not a landed cost: you cannot capitalise the cost of
# shipping goods you no longer hold into the value of stock. Cathedis last-mile
# alone is 972,950 in 2026, and the guard was pushing it at 153.03, where it
# would have inflated inventory and never cleared. These stay in the P&L, below
# gross margin, as the selling expense they are.
_OUTBOUND = ["770.07.0001",   # Trendyol fees
             "770.07.001",    # Trendyol cargo / penalty / subscription
             "770.07.004",    # Cathedis last-mile (+ .001 extra charges)
             "770.07.005",    # Aramex courier
             "770.07.008"]    # local delivery to the customer


def _outbound():
    try:
        p = frappe.parse_json(frappe.db.get_default("ap_freight_outbound") or "[]") or []
        return [str(x) for x in p] or list(_OUTBOUND)
    except Exception:
        return list(_OUTBOUND)


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
    out = tuple(_outbound())

    def _blocked(acc):
        acc = acc or ""
        return acc.startswith(pats) and not acc.startswith(out)

    # freight arrives BOTH ways: as an item line (expense_account) and as a
    # charge row (account_head) — guarding only the items let charge-row
    # freight through untouched
    def _bad_of(d):
        if not d:
            return set()
        return {a for a in ([r.get("expense_account") for r in (d.get("items") or [])]
                            + [r.get("account_head") for r in (d.get("taxes") or [])]) if _blocked(a)}

    bad = sorted(_bad_of(doc))
    if not bad:
        return

    # The rule is about freight being booked to the P&L, not about the document
    # being touched. A bill written in June already sits on 770.07; refusing
    # every save of it locks the accountant out of the only route ERPNext gives
    # her to correct it — cancel and amend — and out of Change date too. The
    # guard fired on the copy, which of course still carried the old account.
    #
    # So compare with where the document came from. If nothing blocked is NEW,
    # this is an existing bill being handled rather than fresh freight going to
    # the wrong place: say so and let it through.
    prior = set()
    # A duplicate is new, has no `amended_from`, and no pre-save copy — so every
    # blocked account on it reads as brand-new freight and the copy is refused.
    # It is not new freight; it is the same bill again. The duplicating action
    # stamps its source here so the guard can compare against it.
    src = doc.flags.get("ap_copied_from") if doc.flags else None
    if src and frappe.db.exists(doc.doctype, src):
        prior = _bad_of(frappe.get_doc(doc.doctype, src))
    elif doc.get("amended_from"):
        prior = _bad_of(frappe.get_doc(doc.doctype, doc.amended_from))
    elif not doc.is_new():
        before = doc.get_doc_before_save()
        if before:
            prior = _bad_of(before)
        else:
            # Frappe does not always hand back the pre-save copy. Read the stored
            # accounts rather than fall through to a throw: an existing bill would
            # otherwise be locked by the accident of a missing cache entry.
            prior = {r[0] for r in frappe.db.sql(
                """SELECT expense_account FROM `tabPurchase Invoice Item` WHERE parent=%(n)s
                   UNION SELECT account_head FROM `tabPurchase Taxes and Charges` WHERE parent=%(n)s""",
                {"n": doc.name}) if _blocked(r[0])}
    if prior and not (set(bad) - prior):
        frappe.msgprint(
            f"This bill still sits on {', '.join(bad[:2])}. It is not being blocked — it was "
            "already there — but freight belongs on the landed-cost clearing account, so this "
            "is the moment to move it.",
            title="Freight still in the P&L", indicator="orange")
        return
    clearing = frappe.db.get_value("Company", SALES, "expenses_included_in_valuation") \
        or "153.03 - Expenses Included In Valuation"
    accs = ", ".join(bad[:3])
    frappe.throw(
        f"New freight/import bills must NOT hit the P&L family ({accs}). "
        f"Book them to <b>{clearing}</b> — in the portal's New-expense screen tick "
        "<b>Freight bill (landed)</b> and the account is set automatically; the bill "
        "then appears in Purchases → Shipments for allocation to its shipment.<br><br>"
        "<i>Delivery to the customer — Cathedis, Aramex, local last-mile — is NOT "
        "affected by this rule: it is a selling expense and belongs in the P&L.</i> "
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
