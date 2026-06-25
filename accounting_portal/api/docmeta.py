"""Document collaboration — activity timeline, attachments, and notes for any
portal document, so the team works entirely from the portal (never opens ERPNext).

Reuses ERPNext's native Version (field changes), Comment (notes), and File
(attachments) so everything stays consistent with the desk UI.
"""
import base64
import json

import frappe

from accounting_portal.api.permissions import assert_can_write, assert_portal_access, resolve_companies

# Doctypes the portal may read/annotate.
_DOCS = {
    "Sales Invoice", "Purchase Invoice", "Sales Order", "Purchase Order",
    "Purchase Receipt", "Delivery Note", "Payment Entry", "Journal Entry",
    "Customer", "Supplier",
}


def _check(doctype, name):
    if doctype not in _DOCS:
        frappe.throw("Document type not supported")
    if not frappe.db.exists(doctype, name):
        frappe.throw("Document not found")
    meta = frappe.get_meta(doctype)
    if meta.has_field("company"):
        company = frappe.db.get_value(doctype, name, "company")
        if company and company not in resolve_companies():
            frappe.throw("Not permitted", frappe.PermissionError)


@frappe.whitelist()
def get_activity(doctype=None, name=None):
    """Unified timeline: creation, submit/cancel, field changes (Version), and
    notes (Comment) — newest first."""
    assert_portal_access()
    _check(doctype, name)
    doc = frappe.db.get_value(
        doctype, name, ["owner", "creation", "modified", "modified_by", "docstatus"], as_dict=True)
    events = [{"type": "created", "by": doc.owner, "on": str(doc.creation)}]
    if doc.docstatus == 1:
        events.append({"type": "submitted", "by": doc.modified_by, "on": str(doc.modified)})
    elif doc.docstatus == 2:
        events.append({"type": "cancelled", "by": doc.modified_by, "on": str(doc.modified)})

    for v in frappe.db.sql(
            """SELECT owner, creation, data FROM `tabVersion`
               WHERE ref_doctype=%s AND docname=%s ORDER BY creation DESC LIMIT 40""",
            (doctype, name), as_dict=True):
        try:
            changed = json.loads(v.data).get("changed", [])
        except Exception:
            changed = []
        if changed:
            events.append({"type": "changed", "by": v.owner, "on": str(v.creation),
                           "changes": [{"field": c[0], "from": c[1], "to": c[2]} for c in changed[:6]]})

    for cm in frappe.db.sql(
            """SELECT owner, creation, content FROM `tabComment`
               WHERE reference_doctype=%s AND reference_name=%s AND comment_type='Comment'
               ORDER BY creation DESC LIMIT 40""", (doctype, name), as_dict=True):
        events.append({"type": "comment", "by": cm.owner, "on": str(cm.creation), "content": cm.content})

    events.sort(key=lambda e: e["on"], reverse=True)
    return {"events": events, "owner": doc.owner, "created": str(doc.creation),
            "modified": str(doc.modified), "modified_by": doc.modified_by}


@frappe.whitelist()
def add_note(doctype=None, name=None, content=None):
    """Post a note/comment on the document (also references can live here)."""
    assert_can_write()
    _check(doctype, name)
    if not (content or "").strip():
        frappe.throw("Note is empty")
    cm = frappe.get_doc({
        "doctype": "Comment", "comment_type": "Comment",
        "reference_doctype": doctype, "reference_name": name,
        "content": content, "comment_email": frappe.session.user,
        "comment_by": frappe.session.user,
    })
    cm.insert(ignore_permissions=True)
    return {"name": cm.name}


@frappe.whitelist()
def list_attachments(doctype=None, name=None):
    """Files attached to the document."""
    assert_portal_access()
    _check(doctype, name)
    return frappe.db.sql(
        """SELECT name, file_name, file_url, is_private, ROUND(file_size/1024) AS kb,
                  creation, owner
           FROM `tabFile` WHERE attached_to_doctype=%s AND attached_to_name=%s
           ORDER BY creation DESC""", (doctype, name), as_dict=True)


@frappe.whitelist()
def add_attachment(doctype=None, name=None, filename=None, content=None):
    """Upload a file against the document. `content` is base64 (optionally a data
    URL); stored private."""
    assert_can_write()
    _check(doctype, name)
    if not filename or not content:
        frappe.throw("File missing")
    data = content.split(",", 1)[1] if "," in content else content
    f = frappe.get_doc({
        "doctype": "File", "file_name": filename, "is_private": 1,
        "attached_to_doctype": doctype, "attached_to_name": name,
        "content": base64.b64decode(data), "decode": False,
    })
    f.insert(ignore_permissions=True)
    return {"name": f.name, "file_url": f.file_url, "file_name": f.file_name}


@frappe.whitelist()
def remove_attachment(file=None):
    """Detach (delete) a file. Only files attached to a permitted document."""
    assert_can_write()
    info = frappe.db.get_value("File", file, ["attached_to_doctype", "attached_to_name"], as_dict=True)
    if not info:
        frappe.throw("File not found")
    _check(info.attached_to_doctype, info.attached_to_name)
    frappe.delete_doc("File", file, ignore_permissions=True)
    return {"ok": True}
