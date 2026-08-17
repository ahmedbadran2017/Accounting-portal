"""Stock-entry guard — blocks the manual-receipt disease at entry.

The Chardon-Marie case: fulfillment/consignment goods were brought in via
manual Stock Entries (Material Receipt) at GUESSED rates or ZERO, while the
supplier invoices lived unlinked — the moving average first inflated (74 vs
real 48), then collapsed to ~5 after 120 zero-rate units. Every sale booked a
wrong COGS in one direction or the other.

The correct flow for supplier goods (including fulfillment stock paid when
sold) is a PURCHASE RECEIPT at the agreed price → invoice the sold portion
later against it. This guard enforces the floor: a Material Receipt line with
no rate is rejected with a message that points to the right flow.

Runtime-togglable without redeploy (mirrors fx_guard):
    ap_stock_guard        "0" disables (default on)
"""
import frappe
from frappe.utils import flt

from accounting_portal.api.permissions import assert_portal_access, can_manage_users


def _enabled():
    v = frappe.db.get_default("ap_stock_guard")
    if v in (None, ""):
        return True   # secure by default
    return str(v) == "1"


def validate_stock_entry(doc, method=None):
    """doc_events validate for Stock Entry."""
    if not _enabled():
        return
    if (doc.stock_entry_type or doc.purpose) != "Material Receipt":
        return
    bad = [d for d in (doc.items or [])
           if d.t_warehouse and not d.s_warehouse and flt(d.basic_rate) <= 0]
    if not bad:
        return
    lines = ", ".join(f"{d.item_code} (row {d.idx})" for d in bad[:5])
    frappe.throw(
        f"Material Receipt with a ZERO rate is blocked: {lines}. "
        "A zero-rate receipt poisons the moving average — every later sale books "
        "wrong COGS.<br>Supplier goods (including fulfillment stock paid when sold) "
        "must come in as a <b>Purchase Receipt at the agreed price</b>; the supplier "
        "then invoices the sold portion against it. If this receipt is genuinely "
        "free goods, enter the fair unit value instead of zero (a Super Admin can "
        "temporarily disable this guard from the portal if truly needed).",
        title="Stock guard: zero-rate Material Receipt")


@frappe.whitelist()
def stock_guard_settings():
    assert_portal_access()
    return {"enabled": _enabled()}


@frappe.whitelist()
def set_stock_guard(on=None):
    if not can_manage_users():
        frappe.throw("Restricted to the Super Admin", frappe.PermissionError)
    if on is not None:
        frappe.db.set_default("ap_stock_guard", "1" if str(on) in ("1", "true", "True", "yes", "on") else "0")
    frappe.db.commit()
    return stock_guard_settings()
