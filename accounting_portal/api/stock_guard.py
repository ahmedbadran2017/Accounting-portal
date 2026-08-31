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
from frappe.utils import cint, flt

from accounting_portal.api.permissions import assert_portal_access, can_manage_users

SALES = "Justyol Morocco"


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


# ---------------------------------------------------------------------------
# FLOOR 3 — a Purchase Receipt may not bring stock in at no cost
#
# Stock Entry has been guarded since August and it worked: manual receipts at a
# zero rate fell from 366 in January to a handful. The receipts kept coming in
# through the other door. Measured on PROD: 218 of 541 receipt lines in the last
# 30 days carry a zero rate — 40% — and 41 of the 114 brand-new products
# received in that window arrived costing nothing.
#
# DEFAULT OFF, deliberately. Switching it on today would refuse four receipts in
# ten and stop the warehouse, because the agreed prices that would fill the rate
# do not exist yet. The order is: get prices onto suppliers (Items → Agreed
# prices), watch "live with no agreed price" fall, then turn this on. The same
# sequencing the publish gate needs.
#     ap_pr_zero_rate_guard   "1" enables (default off)
# ---------------------------------------------------------------------------

PR_GUARD_KEY = "ap_pr_zero_rate_guard"


def _pr_guard_on():
    return str(frappe.db.get_default(PR_GUARD_KEY) or "0") == "1"


@frappe.whitelist()
def pr_zero_guard_settings():
    assert_portal_access()
    zero = frappe.db.sql(
        """SELECT COUNT(*) FROM `tabPurchase Receipt Item` pri
           JOIN `tabPurchase Receipt` pr ON pr.name=pri.parent
           WHERE pr.company=%s AND pr.docstatus=1 AND pri.qty>0
             AND IFNULL(pri.base_rate,0)<=0
             AND pr.posting_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)""", (SALES,))[0][0]
    total = frappe.db.sql(
        """SELECT COUNT(*) FROM `tabPurchase Receipt Item` pri
           JOIN `tabPurchase Receipt` pr ON pr.name=pri.parent
           WHERE pr.company=%s AND pr.docstatus=1 AND pri.qty>0
             AND pr.posting_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)""", (SALES,))[0][0]
    return {"enabled": _pr_guard_on(),
            "would_block_30d": zero, "lines_30d": total,
            "would_block_pct": round(zero / total * 100, 1) if total else 0,
            "can_toggle": can_manage_users()}


@frappe.whitelist()
def set_pr_zero_guard(on=None):
    """Super Admin only — this one can stop receiving, so it is not a casual switch."""
    assert_portal_access()
    if not can_manage_users():
        frappe.throw("Only a Super Admin can change this guard", frappe.PermissionError)
    frappe.db.set_default(PR_GUARD_KEY, "1" if cint(on) else "0")
    frappe.db.commit()
    return pr_zero_guard_settings()


def validate_purchase_receipt(doc, method=None):
    """Refuse stock arriving at no cost.

    A receipt at zero does not merely lose one product's cost: it drags the
    moving average down for every unit of that item, so later sales book a
    margin that was never earned. The rate exists — the vendor invoiced it —
    it just was not carried onto the document.
    """
    if not _pr_guard_on() or doc.company != SALES or getattr(doc, "is_return", 0):
        return
    zero = [d for d in (doc.items or []) if flt(d.qty) > 0 and flt(d.base_rate) <= 0]
    if not zero:
        return
    from accounting_portal.api import pricing
    lines, fixable = [], []
    for d in zero[:6]:
        agreed = pricing.agreed_price(doc.supplier, d.item_code) if doc.supplier else 0
        if agreed:
            fixable.append(f"{d.item_code} → {agreed}")
        lines.append(f"{d.item_code} (row {d.idx})")
    msg = ("Stock cannot be received at a zero rate: " + ", ".join(lines) +
           ". A zero receipt drags the item's moving average down, so every later "
           "sale from it books a margin that was never earned.<br><br>")
    if fixable:
        msg += ("An agreed price already exists for: <b>" + ", ".join(fixable) +
                "</b> — put it on the line, or raise the receipt from its Purchase "
                "Order so the rate is fetched for you.")
    else:
        msg += ("No agreed price exists for these yet. Enter one in "
                "<b>Items → Agreed prices</b> first — a product should not enter "
                "stock before somebody has decided what it cost.")
    frappe.throw(msg, title="Receipt has no cost")
