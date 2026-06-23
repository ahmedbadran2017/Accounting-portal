"""Accountant write operations — the team works the books from the portal.

Every posting goes through the _actions write gateway, so it inherits the same
controls as everything else: capability check, idempotency, an audit record, and
a propose→approve→post gate for material entries. This module owns the Journal
Entry operation (the accountant's core tool: corrections, accruals,
reclassifications); other documents (Payment Entry, Sales Invoice…) follow.
"""
import json

import frappe
from frappe.utils import flt, nowdate

from accounting_portal.api import _actions
from accounting_portal.api.permissions import assert_can_write, assert_portal_access, resolve_companies

JE_ACTION = "Post Correction"


@frappe.whitelist()
def account_options(company=None):
    """Postable (non-group) accounts for the company — the JE form's picker."""
    assert_portal_access()
    companies = resolve_companies(company)
    if not companies:
        return []
    target = company if (company and company in companies) else companies[0]
    return frappe.db.sql(
        """SELECT name, account_name, IFNULL(account_type, '') AS type
           FROM `tabAccount` WHERE company=%s AND is_group=0 AND disabled=0
           ORDER BY name""",
        (target,), as_dict=True)


def _je_poster(action):
    """Create + submit a balanced Journal Entry from the action payload."""
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    je = frappe.get_doc({
        "doctype": "Journal Entry",
        "company": action.company,
        "posting_date": p.get("posting_date") or nowdate(),
        "voucher_type": "Journal Entry",
        # Allow lines on accounts whose currency differs from the company default
        # (the books carry USD/TRY accounts); same-currency lines just use rate 1.
        "multi_currency": 1,
        "user_remark": p.get("remark") or "Posted via Accounting Portal",
        "accounts": [
            {
                "account": ln["account"],
                "debit_in_account_currency": flt(ln.get("debit")),
                "credit_in_account_currency": flt(ln.get("credit")),
                "party_type": ln.get("party_type") or None,
                "party": ln.get("party") or None,
            }
            for ln in (p.get("lines") or [])
        ],
    })
    je.insert(ignore_permissions=True)
    je.submit()
    return {"voucher_type": "Journal Entry", "voucher_no": je.name, "result": "submitted"}


_actions.register_poster(JE_ACTION, _je_poster)


@frappe.whitelist()
def create_journal_entry(company=None, posting_date=None, lines=None, remark=None, dedupe_key=None):
    """Post a balanced Journal Entry through the write gateway.

    `lines`: [{account, debit, credit, party_type?, party?}, …] — debits must
    equal credits. Material entries (≥ the gateway threshold) are recorded as
    Proposed and require an approver before they post.
    """
    assert_can_write()
    companies = resolve_companies(company)
    if not companies:
        frappe.throw("No company in scope")
    target = company if (company and company in companies) else companies[0]

    if isinstance(lines, str):
        lines = json.loads(lines)
    lines = lines or []
    if len(lines) < 2:
        frappe.throw("A journal entry needs at least two lines")

    dr = sum(flt(ln.get("debit")) for ln in lines)
    cr = sum(flt(ln.get("credit")) for ln in lines)
    if round(dr - cr, 2) != 0:
        frappe.throw(f"Debits ({dr:,.2f}) and credits ({cr:,.2f}) must balance")
    if dr <= 0:
        frappe.throw("Journal entry has no amount")

    posting_date = posting_date or nowdate()
    key = dedupe_key or f"je:{target}:{posting_date}:{round(dr, 2)}:{(remark or '')[:40]}"
    payload = {"posting_date": posting_date, "lines": lines, "remark": remark}
    return _actions.execute(JE_ACTION, target, key, payload=payload, amount=dr, notes=remark)
