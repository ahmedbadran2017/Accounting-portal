"""Generic bulk actions (Submit / Cancel) for the portal tables.

Every table's BulkBar can submit or cancel the selected documents in one audited,
gated operation. Hard delete is intentionally NOT offered — deleting a GL-posted
document corrupts the ledger. Only an allow-listed set of doctypes is accepted,
the company scope is enforced per row, and the whole batch is routed through the
write gateway (one Accounting Portal Action, material-amount approval gate).
"""
import json

import frappe

from accounting_portal.api._actions import digest as _digest
from frappe.utils import flt

from accounting_portal.api import _actions
from accounting_portal.api.permissions import assert_can_write, resolve_companies

SUBMIT_ACTION = "Bulk Submit"
CANCEL_ACTION = "Bulk Cancel"

# Doctype -> the column holding its headline amount (for the approval gate).
_ALLOWED = {
    "Sales Order": "grand_total", "Sales Invoice": "grand_total",
    "Purchase Order": "grand_total", "Purchase Receipt": "grand_total",
    "Purchase Invoice": "grand_total", "Delivery Note": "grand_total",
    "Payment Entry": "paid_amount", "Journal Entry": "total_debit",
    # payroll bonuses/deductions — amended on the Desk 34× in a quarter (date/amount)
    "Additional Salary": "amount",
}


def _bulk_poster(action):
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    dt, names, op = p["doctype"], p["names"], p["op"]
    done, failed = [], []
    for n in names:
        try:
            d = frappe.get_doc(dt, n)
            d.flags.ignore_permissions = True
            if op == "submit" and d.docstatus == 0:
                d.submit()
            elif op == "cancel" and d.docstatus == 1:
                d.cancel()
            else:
                failed.append({"name": n, "error": "wrong state"}); continue
            done.append(n)
        except Exception as e:
            failed.append({"name": n, "error": str(e)[:140]})
    return {"voucher_type": dt, "voucher_no": (done[0] if done else None),
            "result": {"op": op, "doctype": dt, "done": done, "failed": failed,
                       "ok": len(done), "fail": len(failed)}}


_actions.register_poster(SUBMIT_ACTION, _bulk_poster)
_actions.register_poster(CANCEL_ACTION, _bulk_poster)


def _run(op, doctype, names, company):
    assert_can_write()
    if doctype not in _ALLOWED:
        frappe.throw(f"Bulk actions are not allowed for {doctype}")
    names = names if isinstance(names, list) else json.loads(names or "[]")
    names = [n for n in names if n][:200]
    if not names:
        frappe.throw("No rows selected")
    companies = resolve_companies(company)
    target = company if (company and company in companies) else (companies[0] if companies else None)
    amt_field = _ALLOWED[doctype]
    rows = frappe.db.sql(
        f"SELECT name, company, docstatus, IFNULL({amt_field},0) AS amt "
        f"FROM `tab{doctype}` WHERE name IN %(n)s", {"n": tuple(names)}, as_dict=True)
    found = {r.name for r in rows}
    missing = [n for n in names if n not in found]
    if missing:
        frappe.throw(f"Not found: {', '.join(missing[:5])}")
    want = 0 if op == "submit" else 1
    for r in rows:
        if target and r.company != target:
            frappe.throw(f"{r.name} belongs to another company")
        if r.docstatus != want:
            frappe.throw(f"{r.name} is not {'a draft' if op == 'submit' else 'submitted'}")
    total = sum(flt(r.amt) for r in rows)
    action_type = SUBMIT_ACTION if op == "submit" else CANCEL_ACTION
    key = f"bulk:{op}:{doctype}:" + _digest("".join(sorted(names)), 16)
    return _actions.execute(
        action_type, target or rows[0].company, key,
        payload={"doctype": doctype, "names": sorted(names), "op": op},
        amount=total, reference_doctype=doctype, reference_name=sorted(names)[0],
        notes=f"Bulk {op} · {len(names)} {doctype}")


@frappe.whitelist()
def bulk_submit(doctype=None, names=None, company=None):
    """Submit the selected draft documents (one audited, gated batch)."""
    return _run("submit", doctype, names, company)


@frappe.whitelist()
def bulk_cancel(doctype=None, names=None, company=None):
    """Cancel the selected submitted documents — reverses their GL. Gated by the
    batch total like any material posting."""
    return _run("cancel", doctype, names, company)


# ── Bulk delete of drafts (the Desk list's Delete on a selection) ───────────────

DELETE_ACTION = "Bulk Delete Drafts"


def _bulk_delete_poster(action):
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    dt, names = p["doctype"], p["names"]
    done, failed = [], []
    for n in names:
        try:
            if frappe.db.get_value(dt, n, "docstatus") != 0:
                failed.append({"name": n, "error": "not a draft"}); continue
            frappe.delete_doc(dt, n, ignore_permissions=True)
            done.append(n)
        except Exception as e:
            failed.append({"name": n, "error": str(e)[:140]})
    return {"voucher_type": dt, "voucher_no": None,
            "result": {"op": "delete", "doctype": dt, "done": done, "failed": failed, "ok": len(done), "fail": len(failed)}}


_actions.register_poster(DELETE_ACTION, _bulk_delete_poster)
_actions._NO_GATE.add(DELETE_ACTION)


@frappe.whitelist()
def bulk_delete(doctype=None, names=None, company=None):
    """Delete up to 200 DRAFTS of one doctype in one audited action. Submitted or
    cancelled rows are refused (cancel them instead)."""
    assert_can_write()
    if doctype not in _ALLOWED:
        frappe.throw(f"Bulk actions are not allowed for {doctype}")
    names = names if isinstance(names, list) else json.loads(names or "[]")
    names = [n for n in names if n][:200]
    if not names:
        frappe.throw("No rows selected")
    companies = resolve_companies(company)
    rows = frappe.db.sql(f"SELECT name, company, docstatus FROM `tab{doctype}` WHERE name IN %(n)s",
                         {"n": tuple(names)}, as_dict=True)
    for r in rows:
        if r.company not in companies:
            frappe.throw(f"{r.name} belongs to another company")
        if r.docstatus != 0:
            frappe.throw(f"{r.name} is not a draft")
    target = rows[0].company if rows else (companies[0] if companies else None)
    key = f"bulk-delete:{doctype}:{_digest(','.join(sorted(names)), 12)}"
    return _actions.execute(DELETE_ACTION, target, key, payload={"doctype": doctype, "names": names, "op": "delete"},
                            amount=0, notes=f"Delete {len(names)} draft {doctype}(s)")
