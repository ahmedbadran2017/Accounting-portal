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
_NO_GATE = {"Collect COD",
            # Master-data corrections (no GL posting) — already super-admin-gated and
            # reversible, so they post straight through instead of stranding a lone
            # super-admin at the propose→approve gate (proposer ≠ approver).
            "Set item cost", "Set item costs (bulk)", "Fix weight units",
            "Stamp PE carrier ref", "Create recurring draft"}

# action_type -> poster(action_doc) -> {"voucher_type", "voucher_no", "result"}
_POSTERS = {}
# action_type -> reverter(action_doc) -> dict. Restores the prior values captured
# in the action's payload (master-data writes only; not GL postings).
_REVERTERS = {}


def register_poster(action_type, fn):
    """Pillars call this (at import) to wire posting logic to an action_type."""
    _POSTERS[action_type] = fn


def register_reverter(action_type, fn):
    """Wire an undo function to an action_type (for reversible master-data writes)."""
    _REVERTERS[action_type] = fn


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
    import accounting_portal.api.landed_engine   # noqa: F401 — cost/weight posters + reverters
    import accounting_portal.api.recurring        # noqa: F401 — recurring-draft poster + reverter
    import accounting_portal.api.payroll          # noqa: F401 — payroll month-close poster + reverter
    import accounting_portal.api.expenses         # noqa: F401 — record-expense poster + reverter
    import accounting_portal.api.ledger           # noqa: F401 — disable/reclassify account posters + reverters
    import accounting_portal.api.intermediary     # noqa: F401 — create-intermediary-account poster + reverter
    import accounting_portal.api.valuation        # noqa: F401 — stock-valuation-fix poster + reverter
    import accounting_portal.api.landed_pipeline  # noqa: F401 — landed-cost-voucher poster + reverter


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
    # Per-submit nonce: the frontend mints a fresh `client_key` each time a create
    # form OPENS and sends it on every submit. Double-clicking one open form reuses
    # it (→ deduped, no double-post); a genuinely separate second identical entry
    # gets a new form-open → new key → it posts instead of silently vanishing.
    # Value-derived keys alone collided on legitimate same-day duplicates.
    ck = frappe.form_dict.get("client_key") if getattr(frappe, "form_dict", None) else None
    if ck:
        dedupe_key = f"{dedupe_key}:{ck}"
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
def self_approve_action(name, reason=None):
    """Break-glass: a Super Admin approves their OWN proposed action when no
    second approver exists (single-admin shops). Requires a reason and is
    recorded distinctly in the audit trail as a self-approval — segregation of
    duties is waived on purpose, not bypassed silently."""
    if not can_manage_users():
        frappe.throw("Only a Super Admin can self-approve", frappe.PermissionError)
    reason = (reason or "").strip()
    if len(reason) < 4:
        frappe.throw("A reason is required for a break-glass self-approval")
    doc = frappe.get_doc(APA, name)
    if doc.status == "Posted":
        return doc.as_dict()
    if doc.proposed_by != frappe.session.user:
        # not your own → the normal approval path applies
        return approve_action(name)
    doc.db_set("approved_by", frappe.session.user)
    doc.db_set("status", "Approved")
    doc.db_set("notes", ((doc.notes or "") + f" · SELF-APPROVED (break-glass): {reason}")[:280])
    return _post(doc).as_dict()


@frappe.whitelist()
def approvers_available(company=None):
    """How many OTHER admins could approve — the UI uses this to decide whether to
    offer break-glass self-approval."""
    assert_can_write()
    me = frappe.session.user
    admins = set()
    for role in ("Accounting Admin", "Accounting Super Admin", "System Manager"):
        for u in frappe.get_all("Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent"):
            if u not in ("Administrator", "Guest") and frappe.db.get_value("User", u, "enabled"):
                admins.add(u)
    others = admins - {me}
    return {"others": len(others), "am_super": bool(can_manage_users())}


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
def revert_action(name):
    """Undo a posted action by restoring the prior values captured in its payload.
    Super-admin only; only actions with a registered reverter (master-data writes
    like item cost / weight / reference stamping) can be undone."""
    if not can_manage_users():
        frappe.throw("Restricted to the Super Admin", frappe.PermissionError)
    doc = frappe.get_doc(APA, name)
    if doc.status != "Posted":
        frappe.throw("Only a posted action can be reverted")
    rev = _REVERTERS.get(doc.action_type)
    if not rev:
        _ensure_posters()
        rev = _REVERTERS.get(doc.action_type)
    if not rev:
        frappe.throw(f"Action '{doc.action_type}' can't be auto-reverted")
    out = rev(doc) or {}
    doc.db_set("status", "Reverted")
    doc.db_set("result", json.dumps({"reverted": out}, default=str)[:4000])
    frappe.db.commit()
    try:
        from accounting_portal.api import _cache
        _cache.bust_report_caches(doc.get("company"))
    except Exception:
        pass
    return doc.as_dict()


def _cancel_voucher_reverter(action):
    """Generic undo for a voucher-creating action: cancel the submitted voucher it
    produced (Frappe posts the reversing GL entries). If the voucher is linked
    downstream Frappe blocks the cancel — that error surfaces and it stays intact."""
    import re
    vt, vn = action.voucher_type, (action.voucher_no or "")
    if not vt:
        frappe.throw("This action has no voucher to cancel")
    done = []
    for c in [x.strip() for x in re.split(r"[,\s]+", vn) if x.strip()]:
        if frappe.db.exists(vt, c):
            d = frappe.get_doc(vt, c)
            if d.docstatus == 1:
                d.cancel()
                done.append(c)
    if not done:
        frappe.throw("No submitted voucher to cancel (already cancelled?)")
    return {"cancelled": done}


# Actions that create one submitted voucher → undo = cancel it (reversing GL).
_CANCEL_VOUCHER_ACTIONS = (
    "Post Correction", "Opening Entry", "Record Payment", "Create Sales Order",
    "Sales Return", "Bill Delivery Note", "Make Receipt", "Make Invoice", "Pay Bill",
    "Create Purchase Order", "Debit Note", "Group Pay", "Group Bill",
)
for _at in _CANCEL_VOUCHER_ACTIONS:
    register_reverter(_at, _cancel_voucher_reverter)


def revertable_types():
    """Action types that have a registered reverter (so the UI can show Undo)."""
    _ensure_posters()  # idempotent import — makes sure every module's reverters registered
    return set(_REVERTERS.keys())


@frappe.whitelist()
def list_actions(company=None, status=None, limit=50):
    """The audit feed for Settings → Activity."""
    assert_portal_access()
    filters = {}
    if company:
        filters["company"] = company
    if status:
        filters["status"] = status
    rows = frappe.get_all(
        APA, filters=filters,
        fields=["name", "action_type", "status", "company", "amount", "voucher_type",
                "voucher_no", "proposed_by", "approved_by", "posted_on", "creation", "notes", "_assign"],
        order_by="creation desc", limit=min(int(limit or 50), 200),
    )
    rtypes = revertable_types()
    for r in rows:
        r["revertable"] = bool(r.get("status") == "Posted" and r.get("action_type") in rtypes)
    return rows
