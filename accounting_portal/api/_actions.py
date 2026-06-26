"""Write gateway + audit trail for the Accounting Portal.

Every write the portal makes to ERPNext goes through this module so it inherits
one consistent set of controls:
  • capability check (permissions.can_write)
  • idempotency — a unique dedupe_key means a retry never double-posts
  • a full audit record (Accounting Portal Action: who/when/what + voucher link)
  • a propose → approve → post gate for MATERIAL entries (proposer ≠ approver)

Pillars (reconciliation, remediation, …) don't post GL directly: they register
a poster fn per action_type and describe each action as (action_type, payload).
The gateway runs the poster, links the resulting voucher, and stamps the audit.
"""
import json

import frappe
from frappe.utils import flt, now_datetime

from accounting_portal.api.permissions import (
    assert_can_write, assert_portal_access, can_manage_users,
)

APA = "Accounting Portal Action"

# Actions at/above this MAD-equivalent magnitude need a distinct approver before
# they post. Smaller actions post straight through (still fully audited).
MATERIAL_THRESHOLD = 10000.0

# Operational, non-GL actions that only tag/flip status (no journal posting) are
# exempt from the approval gate regardless of magnitude — a daily Cathedis
# remittance is large by nature but doesn't post to the ledger, so making the
# accountant chase an approver for every batch is wrong. Still fully audited.
_NO_GATE = {"Collect COD"}

# action_type -> poster(action_doc) -> {"voucher_type", "voucher_no", "result"}
_POSTERS = {}


def register_poster(action_type, fn):
    """Pillars call this (at import) to wire posting logic to an action_type."""
    _POSTERS[action_type] = fn


def _ensure_posters():
    """Lazily import modules that register posters, so posting works even in a
    fresh request that never imported them (e.g. a standalone approve_action)."""
    import accounting_portal.api.accountant  # noqa: F401 — Journal Entry poster
    import accounting_portal.api.payments     # noqa: F401 — Payment Entry poster
    import accounting_portal.api.sales        # noqa: F401 — Sales Order poster
    import accounting_portal.api.cod          # noqa: F401 — Collect COD poster
    import accounting_portal.api.purchases    # noqa: F401 — Receipt/Invoice/Pay posters
    import accounting_portal.api.bulk         # noqa: F401 — Bulk Submit/Cancel posters
    import accounting_portal.api.docops       # noqa: F401 — Amend Document poster
    import accounting_portal.api.reconciliation  # noqa: F401 — Clear Bank Entry poster


def _existing(dedupe_key):
    name = frappe.db.get_value(APA, {"dedupe_key": dedupe_key}, "name")
    return frappe.get_doc(APA, name) if name else None


def _post(doc):
    """Run the registered poster, link the voucher, mark Posted. Internal."""
    poster = _POSTERS.get(doc.action_type)
    if not poster:
        _ensure_posters()
        poster = _POSTERS.get(doc.action_type)
    if not poster:
        frappe.throw(f"No poster registered for action '{doc.action_type}'")
    try:
        out = poster(doc) or {}
    except Exception:
        doc.db_set("status", "Failed")
        doc.db_set("result", frappe.get_traceback()[:4000])
        frappe.db.commit()
        raise
    doc.db_set("voucher_type", out.get("voucher_type"))
    doc.db_set("voucher_no", out.get("voucher_no"))
    doc.db_set("result", json.dumps(out.get("result", out), default=str)[:4000])
    doc.db_set("posted_on", now_datetime())
    doc.db_set("status", "Posted")
    frappe.db.commit()
    # A posting changes the GL → drop the cached report aggregates for this company
    # so the next page load reflects it (cockpit busts itself separately).
    try:
        from accounting_portal.api import _cache
        _cache.bust_report_caches(doc.get("company"))
    except Exception:
        pass
    return doc


def execute(action_type, company, dedupe_key, payload=None, amount=0,
            reference_doctype=None, reference_name=None, notes=None):
    """The one entry point pillars call. Idempotent + audited.

    - dedupe_key already Posted/Rejected → returns it (never double-posts).
    - material (amount ≥ threshold) and not yet Approved → records a Proposed
      action and returns it WITHOUT posting (awaits approve_action()).
    - otherwise posts immediately via the registered poster, fully audited.
    """
    assert_can_write()
    existing = _existing(dedupe_key)
    if existing and existing.status in ("Posted", "Rejected"):
        return existing.as_dict()

    doc = existing or frappe.get_doc({
        "doctype": APA, "action_type": action_type, "company": company,
        "dedupe_key": dedupe_key, "amount": flt(amount),
        "reference_doctype": reference_doctype, "reference_name": reference_name,
        "payload": json.dumps(payload or {}, default=str), "notes": notes,
        "proposed_by": frappe.session.user, "status": "Proposed",
    })
    if not existing:
        doc.insert(ignore_permissions=True)
        frappe.db.commit()

    if flt(amount) >= MATERIAL_THRESHOLD and action_type not in _NO_GATE and doc.status != "Approved":
        return doc.as_dict()  # awaits an approver
    return _post(doc).as_dict()


@frappe.whitelist()
def approve_action(name):
    """Approve a proposed material action and post it. The approver must differ
    from the proposer (segregation of duties) and be an admin."""
    if not (can_manage_users() or "Accounting Admin" in frappe.get_roles()):
        frappe.throw("Only an admin can approve actions", frappe.PermissionError)
    doc = frappe.get_doc(APA, name)
    if doc.status == "Posted":
        return doc.as_dict()
    if doc.proposed_by == frappe.session.user:
        frappe.throw("An action must be approved by someone other than its proposer", frappe.PermissionError)
    doc.db_set("approved_by", frappe.session.user)
    doc.db_set("status", "Approved")
    return _post(doc).as_dict()


@frappe.whitelist()
def reject_action(name, reason=None):
    assert_can_write()
    doc = frappe.get_doc(APA, name)
    if doc.status == "Posted":
        frappe.throw("Cannot reject a posted action")
    doc.db_set("status", "Rejected")
    if reason:
        doc.db_set("notes", reason)
    frappe.db.commit()
    return doc.as_dict()


@frappe.whitelist()
def list_actions(company=None, status=None, limit=50):
    """The audit feed for Settings → Activity."""
    assert_portal_access()
    filters = {}
    if company:
        filters["company"] = company
    if status:
        filters["status"] = status
    return frappe.get_all(
        APA, filters=filters,
        fields=["name", "action_type", "status", "company", "amount", "voucher_type",
                "voucher_no", "proposed_by", "approved_by", "posted_on", "creation", "notes", "_assign"],
        order_by="creation desc", limit=min(int(limit or 50), 200),
    )
