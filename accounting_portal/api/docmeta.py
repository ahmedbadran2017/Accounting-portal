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
    "Customer", "Supplier", "Item", "Landed Cost Voucher",
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


# Document kinds the team chases for a missing source document — only the ones a
# human actually attaches a file to. Sales Invoices AND COD receipts are excluded:
# both are bulk auto-generated (Shopify invoices, ~48k carrier-collection receipts)
# with no paper to chase.
_MISSING = {
    "bills": ("Purchase Invoice", "supplier", "grand_total", "docstatus=1"),
    "payments": ("Payment Entry", "party", "paid_amount", "docstatus=1 AND payment_type='Pay'"),
    "journals": ("Journal Entry", "NULL", "total_debit", "docstatus=1 AND voucher_type IN ('Journal Entry','Bank Entry')"),
}


@frappe.whitelist()
def missing_documents(company=None, kind="bills", search=None, limit=200):
    """Documents with NO file attached — the team's 'upload the source doc' queue.
    kind: bills | payments | receipts | journals. Returns rows + per-kind counts."""
    assert_portal_access()
    if kind not in _MISSING:
        frappe.throw("Unknown kind")
    companies = resolve_companies(company)
    if not companies:
        return {"rows": [], "counts": {}}
    target = company if (company and company in companies) else companies[0]

    def _count(k):
        dt, _pf, _af, cond = _MISSING[k]
        return frappe.db.sql(
            f"""SELECT COUNT(*) FROM `tab{dt}` d WHERE d.company=%s AND {cond}
                AND NOT EXISTS (SELECT 1 FROM `tabFile` f
                    WHERE f.attached_to_doctype=%s AND f.attached_to_name=d.name)""",
            (target, dt))[0][0]

    dt, pf, af, cond = _MISSING[kind]
    party_sel = f"d.{pf} AS party" if pf != "NULL" else "'' AS party"
    conds = [f"d.company=%(c)s", cond,
             "NOT EXISTS (SELECT 1 FROM `tabFile` f WHERE f.attached_to_doctype=%(dt)s AND f.attached_to_name=d.name)"]
    params = {"c": target, "dt": dt, "limit": min(int(limit or 200), 500)}
    if search:
        like = f"%{search}%"
        conds.append(f"(d.name LIKE %(s)s OR {('d.'+pf+' LIKE %(s)s') if pf!='NULL' else '0'})")
        params["s"] = like
    rows = frappe.db.sql(
        f"""SELECT d.name, {party_sel}, d.posting_date AS date, ROUND(d.{af}) AS amount
            FROM `tab{dt}` d WHERE {' AND '.join(conds)}
            ORDER BY d.posting_date DESC LIMIT %(limit)s""", params, as_dict=True)
    counts = {k: _count(k) for k in _MISSING}
    routes = {"bills": "purchases/bills", "payments": "purchases/payments",
              "receipts": "sales/payments", "journals": "accountant/journals"}
    return {"kind": kind, "doctype": dt, "rows": rows, "counts": counts, "route": routes.get(kind)}


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


# ── Tags ──
@frappe.whitelist()
def get_tags(doctype=None, name=None):
    assert_portal_access()
    _check(doctype, name)
    tags = frappe.db.get_value(doctype, name, "_user_tags") or ""
    return [t for t in tags.split(",") if t]


@frappe.whitelist()
def add_tag(doctype=None, name=None, tag=None):
    assert_can_write()
    _check(doctype, name)
    if not (tag or "").strip():
        frappe.throw("Empty tag")
    frappe.get_doc(doctype, name).add_tag(tag.strip())
    return {"tags": get_tags(doctype, name)}


@frappe.whitelist()
def remove_tag(doctype=None, name=None, tag=None):
    assert_can_write()
    _check(doctype, name)
    frappe.get_doc(doctype, name).remove_tag(tag)
    return {"tags": get_tags(doctype, name)}


# ── Edit a small allow-list of safe fields, from the portal ──
_EDITABLE = {
    "Sales Invoice": ["due_date", "remarks", "po_no"],
    "Purchase Invoice": ["due_date", "remarks", "bill_no", "bill_date"],
    "Sales Order": ["po_no"],
    "Purchase Order": ["schedule_date"],
    "Payment Entry": ["reference_no", "reference_date", "remarks"],
    "Journal Entry": ["user_remark", "cheque_no", "cheque_date"],
    "Customer": ["customer_name", "email_id", "mobile_no"],
    "Supplier": ["supplier_name", "email_id", "mobile_no"],
}


@frappe.whitelist()
def editable_fields(doctype=None, name=None):
    """Which fields the portal may edit on this doctype + their current values."""
    assert_portal_access()
    _check(doctype, name)
    flds = [f for f in _EDITABLE.get(doctype, []) if frappe.get_meta(doctype).has_field(f)]
    if not flds:
        return {"fields": []}
    cur = frappe.db.get_value(doctype, name, flds, as_dict=True) or {}
    meta = frappe.get_meta(doctype)
    out = []
    for f in flds:
        df = meta.get_field(f)
        out.append({"field": f, "label": df.label if df else f, "type": (df.fieldtype if df else "Data"),
                    "value": (str(cur.get(f)) if cur.get(f) is not None else "")})
    return {"fields": out}


@frappe.whitelist()
def update_doc_fields(doctype=None, name=None, fields=None):
    """Save edits to the allow-listed fields. For submitted docs only fields that
    are editable-after-submit will save; the rest are rejected by ERPNext."""
    assert_can_write()
    _check(doctype, name)
    allowed = set(_EDITABLE.get(doctype, []))
    data = fields if isinstance(fields, dict) else json.loads(fields or "{}")
    bad = [k for k in data if k not in allowed]
    if bad:
        frappe.throw(f"Not editable: {', '.join(bad)}")
    if not data:
        frappe.throw("Nothing to update")
    doc = frappe.get_doc(doctype, name)
    doc.flags.ignore_permissions = True
    for k, v in data.items():
        doc.set(k, v or None)
    doc.save()
    return {"ok": True}


@frappe.whitelist()
def default_recipient(doctype=None, name=None):
    """Best-guess email to send this document to — the party's contact email."""
    assert_portal_access()
    _check(doctype, name)
    party_field = {"Sales Invoice": "customer", "Sales Order": "customer",
                   "Purchase Invoice": "supplier", "Purchase Order": "supplier",
                   "Customer": None, "Supplier": None}.get(doctype)
    party_type = "Customer" if doctype in ("Sales Invoice", "Sales Order", "Customer") else "Supplier"
    party = name if doctype in ("Customer", "Supplier") else (
        frappe.db.get_value(doctype, name, party_field) if party_field else None)
    if not party:
        return {"email": ""}
    email = frappe.db.get_value(party_type, party, "email_id") or ""
    if not email:
        email = frappe.db.sql(
            """SELECT c.email_id FROM `tabContact` c JOIN `tabDynamic Link` dl ON dl.parent=c.name
               WHERE dl.link_doctype=%s AND dl.link_name=%s AND IFNULL(c.email_id,'')!='' LIMIT 1""",
            (party_type, party))
        email = email[0][0] if email else ""
    return {"email": email}


@frappe.whitelist()
def email_document(doctype=None, name=None, recipients=None, subject=None, message=None):
    """Email the document (as a PDF) to the recipients via the configured outgoing
    account. Outward-facing — the UI collects + confirms the recipients."""
    assert_can_write()
    _check(doctype, name)
    to = [r.strip() for r in (recipients or "").replace(";", ",").split(",") if r.strip()]
    if not to:
        frappe.throw("No recipients")
    frappe.sendmail(
        recipients=to,
        subject=subject or f"{doctype} {name}",
        message=message or f"Please find attached {doctype} {name}.",
        attachments=[frappe.attach_print(doctype, name)],
        reference_doctype=doctype, reference_name=name,
    )
    frappe.get_doc({
        "doctype": "Comment", "comment_type": "Comment",
        "reference_doctype": doctype, "reference_name": name,
        "content": f"📧 Emailed to {', '.join(to)}",
        "comment_email": frappe.session.user, "comment_by": frappe.session.user,
    }).insert(ignore_permissions=True)
    return {"ok": True, "sent_to": to}
