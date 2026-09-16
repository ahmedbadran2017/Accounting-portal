"""Every "Create →" and status action the ERPNext Desk offers on a document,
exposed once, generically, for the portal's document toolbar.

The Desk form of a Sales Order offers Sales Invoice / Delivery Note / Payment;
a Purchase Receipt offers Purchase Invoice / Return / Landed Cost Voucher; a
Journal Entry offers Reverse; and so on. Rather than re-implementing each flow
in the portal, this module calls ERPNext's own mapper functions (the same ones
the Desk buttons call) and saves the result as a DRAFT the team then reviews,
edits (DraftEditor) and submits from the portal. Drafts post nothing, so
creation is audited but not gated; submit carries the gate.

Status actions (Close / Reopen / Hold / Release) call ERPNext's whitelisted
status functions the same way.
"""
import json

import frappe
from frappe.utils import flt, now_datetime

from accounting_portal.api import _actions
from accounting_portal.api.permissions import assert_can_write, assert_portal_access, resolve_companies

FLOW_ACTION = "Create from document"
STATUS_ACTION = "Set document status"

_SO = "erpnext.selling.doctype.sales_order.sales_order."
_SI = "erpnext.accounts.doctype.sales_invoice.sales_invoice."
_DN = "erpnext.stock.doctype.delivery_note.delivery_note."
_PO = "erpnext.buying.doctype.purchase_order.purchase_order."
_PR = "erpnext.stock.doctype.purchase_receipt.purchase_receipt."
_PI = "erpnext.accounts.doctype.purchase_invoice.purchase_invoice."
_JE = "erpnext.accounts.doctype.journal_entry.journal_entry."
_PE = "erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry"
_EA = "hrms.hr.doctype.employee_advance.employee_advance."

_open = lambda d: d.docstatus == 1 and d.get("status") not in ("Closed", "On Hold", "Cancelled")  # noqa: E731

# key → (target doctype, label, mapper path or special tag, availability rule)
_CREATES = {
    "Sales Order": [
        ("sales_invoice", "Sales Invoice", "Sales invoice", _SO + "make_sales_invoice",
         lambda d: _open(d) and flt(d.per_billed) < 100),
        ("delivery_note", "Delivery Note", "Delivery note", _SO + "make_delivery_note",
         lambda d: _open(d) and flt(d.per_delivered) < 100),
        ("payment", "Payment Entry", "Payment (advance)", "PAYMENT",
         lambda d: _open(d) and flt(d.advance_paid) < flt(d.rounded_total or d.grand_total)),
    ],
    "Sales Invoice": [
        ("payment", "Payment Entry", "Payment", "PAYMENT",
         lambda d: d.docstatus == 1 and not d.is_return and flt(d.outstanding_amount) > 0),
        ("credit_note", "Sales Invoice", "Credit note (return)", _SI + "make_sales_return",
         lambda d: d.docstatus == 1 and not d.is_return),
        ("delivery_note", "Delivery Note", "Delivery note", _SI + "make_delivery_note",
         lambda d: d.docstatus == 1 and not d.is_return and not d.update_stock),
    ],
    "Delivery Note": [
        ("sales_invoice", "Sales Invoice", "Sales invoice", _DN + "make_sales_invoice",
         lambda d: _open(d) and not d.is_return and flt(d.per_billed) < 100),
        ("sales_return", "Delivery Note", "Sales return", _DN + "make_sales_return",
         lambda d: d.docstatus == 1 and not d.is_return),
    ],
    "Purchase Order": [
        ("purchase_receipt", "Purchase Receipt", "Purchase receipt", _PO + "make_purchase_receipt",
         lambda d: _open(d) and flt(d.per_received) < 100),
        ("purchase_invoice", "Purchase Invoice", "Purchase invoice", _PO + "make_purchase_invoice",
         lambda d: _open(d) and flt(d.per_billed) < 100),
        ("payment", "Payment Entry", "Payment (advance)", "PAYMENT",
         lambda d: _open(d) and flt(d.advance_paid) < flt(d.rounded_total or d.grand_total)),
    ],
    "Purchase Receipt": [
        ("purchase_invoice", "Purchase Invoice", "Purchase invoice", _PR + "make_purchase_invoice",
         lambda d: _open(d) and not d.is_return and flt(d.per_billed) < 100),
        ("purchase_return", "Purchase Receipt", "Purchase return", _PR + "make_purchase_return",
         lambda d: d.docstatus == 1 and not d.is_return),
        ("lcv", "Landed Cost Voucher", "Landed cost voucher", "LCV",
         lambda d: d.docstatus == 1 and not d.is_return),
    ],
    "Purchase Invoice": [
        ("payment", "Payment Entry", "Payment", "PAYMENT",
         lambda d: d.docstatus == 1 and not d.is_return and flt(d.outstanding_amount) > 0),
        ("debit_note", "Purchase Invoice", "Debit note (return)", _PI + "make_debit_note",
         lambda d: d.docstatus == 1 and not d.is_return),
        ("lcv", "Landed Cost Voucher", "Landed cost voucher", "LCV",
         lambda d: d.docstatus == 1 and not d.is_return and d.update_stock),
    ],
    "Journal Entry": [
        ("reverse", "Journal Entry", "Reverse entry", _JE + "make_reverse_journal_entry",
         lambda d: d.docstatus == 1),
    ],
    "Employee Advance": [
        ("pay", "Payment Entry", "Pay advance", "EA_PAY",
         lambda d: d.docstatus == 1 and flt(d.paid_amount) < flt(d.advance_amount)),
        ("return", "Journal Entry", "Return unclaimed balance", "EA_RETURN",
         lambda d: d.docstatus == 1 and flt(d.paid_amount) - flt(d.claimed_amount) - flt(d.return_amount) > 0),
    ],
}

# key → (label, callable(name, doc)) ; availability rule
_STATUSES = {
    "Sales Order": [
        ("close", "Close", lambda d: d.docstatus == 1 and d.status not in ("Closed",)),
        ("reopen", "Reopen", lambda d: d.docstatus == 1 and d.status in ("Closed", "On Hold")),
        ("hold", "Put on hold", lambda d: d.docstatus == 1 and d.status not in ("Closed", "On Hold", "Completed")),
    ],
    "Purchase Order": [
        ("close", "Close", lambda d: d.docstatus == 1 and d.status not in ("Closed",)),
        ("reopen", "Reopen", lambda d: d.docstatus == 1 and d.status in ("Closed", "On Hold")),
        ("hold", "Put on hold", lambda d: d.docstatus == 1 and d.status not in ("Closed", "On Hold", "Completed")),
    ],
    "Delivery Note": [
        ("close", "Close", lambda d: d.docstatus == 1 and d.status != "Closed"),
        ("reopen", "Reopen", lambda d: d.docstatus == 1 and d.status == "Closed"),
    ],
    "Purchase Receipt": [
        ("close", "Close", lambda d: d.docstatus == 1 and d.status != "Closed"),
        ("reopen", "Reopen", lambda d: d.docstatus == 1 and d.status == "Closed"),
    ],
    "Purchase Invoice": [
        ("hold", "Hold payment", lambda d: d.docstatus == 1 and not d.on_hold and flt(d.outstanding_amount) > 0),
        ("unhold", "Release hold", lambda d: d.docstatus == 1 and bool(d.on_hold)),
    ],
}

_FIELDS = ["name", "company", "docstatus", "status", "per_billed", "per_delivered", "per_received",
           "is_return", "update_stock", "outstanding_amount", "advance_paid", "rounded_total", "grand_total",
           "on_hold", "paid_amount", "claimed_amount", "return_amount", "advance_amount", "employee",
           "advance_account", "mode_of_payment", "currency", "exchange_rate"]


def _head(doctype, name):
    meta = frappe.get_meta(doctype)
    flds = [f for f in _FIELDS if f == "name" or meta.has_field(f) or f in ("docstatus",)]
    d = frappe.db.get_value(doctype, name, flds, as_dict=True)
    if not d:
        frappe.throw("Document not found")
    for f in _FIELDS:
        d.setdefault(f, None)
    return d


@frappe.whitelist()
def options(doctype=None, name=None):
    """What can be created from / done to this document right now."""
    assert_portal_access()
    if doctype not in _CREATES and doctype not in _STATUSES:
        return {"creates": [], "statuses": []}
    if not name or not frappe.db.exists(doctype, name):
        return {"creates": [], "statuses": []}
    d = _head(doctype, name)
    if d.company not in resolve_companies():
        return {"creates": [], "statuses": []}
    creates = [{"key": k, "target": t, "label": lbl} for k, t, lbl, _fn, rule in _CREATES.get(doctype, []) if _safe(rule, d)]
    statuses = [{"key": k, "label": lbl} for k, lbl, rule in _STATUSES.get(doctype, []) if _safe(rule, d)]
    return {"creates": creates, "statuses": statuses, "status": d.status, "docstatus": d.docstatus}


def _safe(rule, d):
    try:
        return bool(rule(d))
    except Exception:
        return False


def _as_doc(res):
    if res is None:
        frappe.throw("ERPNext returned nothing for this action")
    if isinstance(res, dict) and not hasattr(res, "insert"):
        res = frappe.get_doc(res)
    return res


def _flow_poster(action):
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    doctype, name, key = p["doctype"], p["name"], p["key"]
    spec = next((s for s in _CREATES.get(doctype, []) if s[0] == key), None)
    if not spec:
        frappe.throw("Unknown action")
    _k, target, _lbl, fn, _rule = spec
    d = _head(doctype, name)
    frappe.flags.ignore_permissions = True
    try:
        if fn == "PAYMENT":
            new = frappe.get_attr(_PE)(doctype, name)
        elif fn == "LCV":
            new = frappe.get_attr(_PR + "make_lcv")(doctype, name)
        elif fn == "EA_PAY":
            new = _as_doc(frappe.get_attr(_EA + "make_bank_entry")(doctype, name))
        elif fn == "EA_RETURN":
            amt = flt(d.paid_amount) - flt(d.claimed_amount) - flt(d.return_amount)
            new = _as_doc(frappe.get_attr(_EA + "make_return_entry")(
                d.employee, d.company, name, amt, d.advance_account, d.mode_of_payment,
                d.currency, d.exchange_rate or 1))
        else:
            new = frappe.get_attr(fn)(name)
    finally:
        frappe.flags.ignore_permissions = False
    new = _as_doc(new)
    new.flags.ignore_permissions = True
    if not (new.get("name") and frappe.db.exists(new.doctype, new.name)):
        new.insert()
    return {"voucher_type": new.doctype, "voucher_no": new.name,
            "result": {"new_doc": new.name, "doctype": new.doctype, "from": name,
                       "payment_type": new.get("payment_type"), "docstatus": new.docstatus}}


def _status_poster(action):
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    doctype, name, key = p["doctype"], p["name"], p["key"]
    frappe.flags.ignore_permissions = True
    try:
        if doctype == "Sales Order":
            frappe.get_attr(_SO + "update_status")({"close": "Closed", "reopen": "Draft", "hold": "On Hold"}[key], name)
        elif doctype == "Purchase Order":
            frappe.get_attr(_PO + "update_status")({"close": "Closed", "reopen": "Draft", "hold": "On Hold"}[key], name)
        elif doctype == "Delivery Note":
            frappe.get_attr(_DN + "update_delivery_note_status")(name, {"close": "Closed", "reopen": "Submitted"}[key])
        elif doctype == "Purchase Receipt":
            frappe.get_attr(_PR + "update_purchase_receipt_status")(name, {"close": "Closed", "reopen": "Submitted"}[key])
        elif doctype == "Purchase Invoice":
            if key == "hold":
                frappe.get_attr(_PI + "block_invoice")(name, p.get("comment") or "Held from portal", p.get("release_date") or None)
            else:
                frappe.get_attr(_PI + "unblock_invoice")(name)
        else:
            frappe.throw("Unknown status action")
    finally:
        frappe.flags.ignore_permissions = False
    return {"voucher_type": doctype, "voucher_no": name,
            "result": {"status": frappe.db.get_value(doctype, name, "status"), "key": key}}


_actions.register_poster(FLOW_ACTION, _flow_poster)
_actions.register_poster(STATUS_ACTION, _status_poster)
_actions._NO_GATE.add(FLOW_ACTION)      # creates a DRAFT; submit is gated separately
_actions._NO_GATE.add(STATUS_ACTION)


@frappe.whitelist()
def create(doctype=None, name=None, key=None, company=None):
    """Create the linked document as a draft (ERPNext's own mapper), audited."""
    assert_can_write()
    if doctype not in _CREATES or not name or not key:
        frappe.throw("Unknown action")
    d = _head(doctype, name)
    if d.company not in resolve_companies(company):
        frappe.throw("Not permitted", frappe.PermissionError)
    spec = next((s for s in _CREATES[doctype] if s[0] == key), None)
    if not spec or not _safe(spec[4], d):
        frappe.throw("That action is not available for this document right now")
    # A second partial invoice/receipt from the same order is legitimate → unique key per call.
    dk = f"flow:{doctype}:{name}:{key}:{str(now_datetime())[:19]}"
    return _actions.execute(FLOW_ACTION, d.company, dk, payload={"doctype": doctype, "name": name, "key": key},
                            amount=0, reference_doctype=doctype, reference_name=name,
                            notes=f"{spec[2]} from {doctype} {name}")


@frappe.whitelist()
def set_status(doctype=None, name=None, key=None, company=None, comment=None, release_date=None):
    """Close / reopen / hold / release, audited."""
    assert_can_write()
    if doctype not in _STATUSES or not name or not key:
        frappe.throw("Unknown action")
    d = _head(doctype, name)
    if d.company not in resolve_companies(company):
        frappe.throw("Not permitted", frappe.PermissionError)
    spec = next((s for s in _STATUSES[doctype] if s[0] == key), None)
    if not spec or not _safe(spec[2], d):
        frappe.throw("That action is not available for this document right now")
    dk = f"status:{doctype}:{name}:{key}:{str(now_datetime())[:19]}"
    return _actions.execute(STATUS_ACTION, d.company, dk,
                            payload={"doctype": doctype, "name": name, "key": key, "comment": comment, "release_date": release_date},
                            amount=0, reference_doctype=doctype, reference_name=name,
                            notes=f"{spec[1]} {doctype} {name}")
