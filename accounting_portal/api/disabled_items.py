"""Billing goods that already arrived, after their item was disabled.

The catalogue cleanup of 2026-04-20 disabled items with no stock and no sales.
Right for the catalogue, wrong for receipts still waiting for their bill:
ERPNext refuses every purchase line whose item is disabled ("Item
47022928494846 is disabled") — on the bill made from the receipt, on its
amendment, on a draft saved later, on submit. `purchases._make_invoice_poster`
worked around it for one button only; amending the cancelled PUR-INV-06530
then failed four times on the same three items.

Disabled means "don't start new buying or selling of this", not "don't pay for
what already came in". So, for the length of one save, the items on lines that
continue an earlier purchase document (a bill line from a receipt or order, a
receipt line from an order) are re-enabled, and disabled again right after the
save. A line typed by hand gets no such pass. If the save fails, the transaction
rolls back and the items were never changed.
"""
import frappe

_FLAG = "portal_reenabled_items"


def _continued_lines(doc):
    codes = set()
    for r in doc.get("items") or []:
        if not r.get("item_code"):
            continue
        if doc.doctype == "Purchase Invoice":
            linked = r.get("purchase_receipt") or r.get("purchase_order")
        else:
            linked = r.get("purchase_order")
        if linked:
            codes.add(r.item_code)
    return codes


def allow_disabled_on_continued_lines(doc, method=None):
    """before_validate on Purchase Invoice / Purchase Receipt."""
    codes = _continued_lines(doc)
    if not codes:
        return
    disabled = frappe.get_all("Item", filters={"name": ["in", list(codes)], "disabled": 1}, pluck="name")
    if not disabled:
        return
    for it in disabled:
        frappe.db.set_value("Item", it, "disabled", 0, update_modified=False)
    doc.flags[_FLAG] = (doc.flags.get(_FLAG) or []) + disabled


def _disable_again(doc):
    for it in doc.flags.pop(_FLAG, None) or []:
        frappe.db.set_value("Item", it, "disabled", 1, update_modified=False)


def restore_after_save(doc, method=None):
    """on_update. On a submit, on_submit still has to post stock and GL with the
    item enabled, so the restore waits for it there."""
    if getattr(doc, "_action", None) != "submit":
        _disable_again(doc)


def restore_after_submit(doc, method=None):
    """on_submit."""
    _disable_again(doc)
