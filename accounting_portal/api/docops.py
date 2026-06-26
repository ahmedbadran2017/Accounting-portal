"""Per-document actions — submit / cancel / amend — and assignment (assign-to /
ToDo), so the team works a single document to completion from the portal instead
of opening ERPNext.

Submit/cancel reuse the bulk poster (one code path, one approval gate). Amend is
ERPNext's standard "cancel → clone to a fresh draft (amended_from)" so a posted
document with a wrong line can be corrected here. Every action is routed through
the _actions maker-checker gate and fully audited.
"""
import json

import frappe
from frappe.utils import flt

from accounting_portal.api import _actions, bulk
from accounting_portal.api.permissions import (
    assert_can_write, assert_portal_access, resolve_companies,
)

AMEND_ACTION = "Amend Document"

# Title/party column per doctype, for a friendly state label.
_TITLE = {
    "Sales Invoice": "customer", "Sales Order": "customer", "Delivery Note": "customer",
    "Purchase Invoice": "supplier", "Purchase Order": "supplier", "Purchase Receipt": "supplier",
    "Payment Entry": "party", "Journal Entry": "title",
}


def _amount(doctype, name):
    field = bulk._ALLOWED.get(doctype)
    if not field:
        return 0.0
    return flt(frappe.db.get_value(doctype, name, field) or 0)


@frappe.whitelist()
def doc_state(doctype=None, name=None):
    """Docstatus + amount + amendability for one document, so DocActions can
    render the right buttons without the detail page passing anything extra."""
    assert_portal_access()
    if doctype not in bulk._ALLOWED or not name or not frappe.db.exists(doctype, name):
        return {"exists": False}
    ds = frappe.db.get_value(doctype, name, "docstatus")
    amended_to = frappe.db.get_value(doctype, {"amended_from": name}, "name")
    return {
        "exists": True, "docstatus": ds, "amount": _amount(doctype, name),
        "can_submit": ds == 0, "can_cancel": ds == 1,
        # A submitted or cancelled doc can be amended, unless already superseded.
        "can_amend": ds in (1, 2) and not amended_to,
        "amended_to": amended_to,
    }


@frappe.whitelist()
def doc_submit(doctype=None, name=None, company=None):
    """Submit one draft document (audited + gated by its own amount)."""
    return bulk._run("submit", doctype, [name], company)


@frappe.whitelist()
def doc_cancel(doctype=None, name=None, company=None):
    """Cancel one submitted document — reverses its GL (gated like any posting)."""
    return bulk._run("cancel", doctype, [name], company)


def _amend_poster(action):
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    dt, name = p["doctype"], p["name"]
    d = frappe.get_doc(dt, name)
    d.flags.ignore_permissions = True
    if d.docstatus == 1:
        d.cancel()          # amendment requires the original to be cancelled first
    elif d.docstatus != 2:
        frappe.throw("Only a submitted or cancelled document can be amended")
    new = frappe.copy_doc(d)
    new.amended_from = name
    new.flags.ignore_permissions = True
    new.insert()
    return {"voucher_type": dt, "voucher_no": new.name,
            "result": {"amended_from": name, "new_draft": new.name}}


_actions.register_poster(AMEND_ACTION, _amend_poster)


@frappe.whitelist()
def doc_amend(doctype=None, name=None, company=None):
    """Cancel the document and open a fresh editable draft linked via amended_from
    (ERPNext's amendment flow). The new draft is returned for the team to edit and
    resubmit. Gated by the document amount because it reverses posted GL."""
    assert_can_write()
    if doctype not in bulk._ALLOWED:
        frappe.throw(f"Amend is not allowed for {doctype}")
    companies = resolve_companies(company)
    target = company if (company and company in companies) else (companies[0] if companies else None)
    if target and frappe.db.get_value(doctype, name, "company") != target:
        frappe.throw(f"{name} belongs to another company")
    key = f"amend:{doctype}:{name}"
    return _actions.execute(
        AMEND_ACTION, target, key, payload={"doctype": doctype, "name": name},
        amount=_amount(doctype, name), reference_doctype=doctype, reference_name=name,
        notes=f"Amend {doctype} {name}")


# ── Assignment (assign-to / ToDo) ───────────────────────────────────────────

@frappe.whitelist()
def assignees(doctype=None, name=None):
    """Current assignees of a document (the _assign list)."""
    assert_portal_access()
    raw = frappe.db.get_value(doctype, name, "_assign") if frappe.db.exists(doctype, name) else None
    return json.loads(raw) if raw else []


@frappe.whitelist()
def assignable_users():
    """Enabled portal/system users to assign work to."""
    assert_portal_access()
    return frappe.get_all(
        "User", filters={"enabled": 1, "user_type": "System User"},
        fields=["name", "full_name"], order_by="full_name", limit=100)


@frappe.whitelist()
def assign_doc(doctype=None, name=None, to_user=None, description=None):
    """Assign a document (or an approval action) to a user — creates a ToDo."""
    assert_can_write()
    from frappe.desk.form.assign_to import add
    add({"doctype": doctype, "name": name, "assign_to": [to_user],
         "description": description or f"{doctype} {name}"})
    return assignees(doctype, name)


@frappe.whitelist()
def unassign_doc(doctype=None, name=None, from_user=None):
    """Remove an assignment."""
    assert_can_write()
    from frappe.desk.form.assign_to import remove
    remove(doctype, name, from_user)
    return assignees(doctype, name)


@frappe.whitelist()
def my_work(user=None):
    """Open tasks assigned to a user — audit/CFO tasks plus any assigned documents —
    enriched with a title, priority and due date for the personal task screen."""
    assert_portal_access()
    u = user or frappe.session.user
    rows = frappe.get_all(
        "ToDo", filters={"allocated_to": u, "status": "Open"},
        fields=["name", "reference_type", "reference_name", "description", "date", "priority"],
        order_by="date asc", limit=200)
    out = []
    for r in rows:
        d = r.get("description") or ""
        is_audit = "⟦AUDIT:" in d
        a, b = d.find("<b>"), d.find("</b>")
        title = d[a + 3:b] if (a >= 0 and b > a) else ""
        if not title:
            if r.get("reference_type") and r.get("reference_name"):
                title = f"{r['reference_type']} {r['reference_name']}"
            else:
                title = (frappe.utils.strip_html_tags(d) or "Task")[:80]
        detail = ""
        if is_audit and b > 0:
            mk = d.find("⟦AUDIT:")
            detail = frappe.utils.strip_html_tags(d[b + 4:mk] if mk > b else d[b + 4:])[:240]
        out.append({
            "task": r["name"], "title": title, "detail": detail.strip(),
            "priority": r.get("priority") or "Medium", "due": str(r.get("date") or ""),
            "is_audit": is_audit, "reference_type": r.get("reference_type"),
            "reference_name": r.get("reference_name"),
        })
    order = {"High": 0, "Medium": 1, "Low": 2}
    out.sort(key=lambda t: (order.get(t["priority"], 1), t["due"] or "9999"))
    return {"user": u, "tasks": out, "count": len(out)}


@frappe.whitelist()
def my_work_count(user=None):
    """Open-task count for the current user — powers the sidebar badge."""
    assert_portal_access()
    u = user or frappe.session.user
    return {"count": frappe.db.count("ToDo", {"allocated_to": u, "status": "Open"})}
