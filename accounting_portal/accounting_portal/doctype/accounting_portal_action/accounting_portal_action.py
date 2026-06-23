"""Accounting Portal Action — the audit record for every write the portal makes.

One row per action (match a remittance, post a correction, clear GRNI…). Carries
the idempotency key, the approval chain, and a link to the resulting GL voucher.
The lifecycle (Proposed → Approved → Posted) is driven by accounting_portal.api._actions.
"""
import frappe
from frappe.model.document import Document


class AccountingPortalAction(Document):
    pass
