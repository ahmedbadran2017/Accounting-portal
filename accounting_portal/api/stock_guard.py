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
    """doc_events validate for Stock Entry — two floors, not one.

    FLOOR 1 (everyone): a zero-rate Material Receipt is rejected. It poisons
    the moving average and every later sale books a wrong COGS.

    FLOOR 2 (added 2026-08-29): a PRICED Material Receipt is still goods
    entering the books with no purchase document — its counter-entry credits
    Stock Adjustment, i.e. NEGATIVE cost. Measured on 2026 Morocco:
    1,205 such receipts kept **2,062,010 MAD of real cost out of the P&L**
    (Jan alone −986K), which is why margins read too good. So a priced manual
    receipt now needs BOTH a manager and a written reason; everyone else is
    routed to the Purchase Receipt flow. Genuine corrections stay possible —
    they just become documented and rare instead of routine.
    """
    if not _enabled():
        return
    if (doc.stock_entry_type or doc.purpose) != "Material Receipt":
        return
    incoming = [d for d in (doc.items or []) if d.t_warehouse and not d.s_warehouse]
    if not incoming:
        return

    zero = [d for d in incoming if flt(d.basic_rate) <= 0]
    if zero:
        lines = ", ".join(f"{d.item_code} (row {d.idx})" for d in zero[:5])
        frappe.throw(
            f"Material Receipt with a ZERO rate is blocked: {lines}. "
            "A zero-rate receipt poisons the moving average — every later sale books "
            "wrong COGS.<br>Supplier goods (including fulfillment stock paid when sold) "
            "must come in as a <b>Purchase Receipt at the agreed price</b>; the supplier "
            "then invoices the sold portion against it. If this receipt is genuinely "
            "free goods, enter the fair unit value instead of zero (a Super Admin can "
            "temporarily disable this guard from the portal if truly needed).",
            title="Stock guard: zero-rate Material Receipt")

    # priced, but still no purchase document behind it
    if can_manage_users() and (doc.remarks or "").strip():
        return                      # documented manager correction — allowed
    value = sum(flt(d.basic_rate) * flt(d.qty) for d in incoming)
    frappe.throw(
        f"Stock cannot enter the books without a purchase document "
        f"({len(incoming)} line(s), {value:,.0f}).<br>"
        "A Material Receipt books the goods in and credits <b>Stock Adjustment</b> — "
        "it lands as NEGATIVE cost, so the P&L shows a margin you did not earn. "
        "2026 lost 2,062,010 MAD of real cost this way.<br><br>"
        "Use a <b>Purchase Receipt</b> against the supplier and price it from the "
        "agreed price list; the invoice then matches it. For a genuine internal "
        "correction (found stock, cycle count), a manager must enter the reason in "
        "<b>Remarks</b> before saving.",
        title="Stock guard: receipt without a purchase document")


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
