"""Reclassify one account's whole balance into another via a single Journal Entry.

For correcting mis-classified balances without touching source documents — e.g.
customer shipping fees credited to a freight EXPENSE account instead of a shipping
REVENUE account. Zeroes the "from" account and moves its net balance to the "to"
account, dated as chosen. Single-currency (both accounts same currency) so the
entry is exact. Gated, audited, reversible (cancel the JE).
"""
import json

import frappe
from frappe.utils import flt, nowdate

from accounting_portal.api import _actions
from accounting_portal.api.permissions import (
    assert_can_write, assert_portal_access, resolve_companies,
)

RECLASS_ACTION = "Reclassify balance"


def _target(company):
    cs = resolve_companies(company)
    if not cs:
        return None
    return company if (company and company in cs) else cs[0]


def _bal(account, as_of):
    """Net balance (debit - credit) in account currency, up to and incl. as_of."""
    return flt(frappe.db.sql(
        """SELECT COALESCE(SUM(debit_in_account_currency - credit_in_account_currency), 0)
           FROM `tabGL Entry` WHERE account=%s AND is_cancelled=0 AND posting_date<=%s""",
        (account, as_of))[0][0])


def _acc(name):
    return frappe.db.get_value(
        "Account", name,
        ["company", "is_group", "account_currency", "account_type", "account_name", "root_type"],
        as_dict=True)


@frappe.whitelist()
def reclass_preview(company=None, from_account=None, to_account=None, as_of=None):
    """Preview: the from-account balance to move, the to-account before/after, and
    any blockers — so the accountant sees exactly what will post."""
    assert_portal_access()
    target = _target(company)
    if not target or not from_account or not to_account:
        return {}
    as_of = str(as_of or nowdate())[:10]
    fa, ta = _acc(from_account), _acc(to_account)
    problems = []
    for lbl, acc in (("from", fa), ("to", ta)):
        if not acc or acc.company != target:
            problems.append(f"{lbl} account is not in this company")
        elif acc.is_group:
            problems.append(f"{lbl} account is a group")
        elif acc.account_type in ("Receivable", "Payable"):
            problems.append(f"{lbl} is a party account — reconcile per party, not a balance reclass")
    if fa and ta and fa.account_currency != ta.account_currency:
        problems.append("both accounts must be the same currency")
    if from_account == to_account:
        problems.append("from and to must differ")
    fb = _bal(from_account, as_of) if (fa and not fa.is_group) else 0.0
    tb = _bal(to_account, as_of) if (ta and not ta.is_group) else 0.0
    return {
        "as_of": as_of,
        "ccy": fa.account_currency if fa else None,
        "from": {"name": from_account, "label": (fa.account_name if fa else ""),
                 "type": (fa.account_type if fa else ""), "root": (fa.root_type if fa else ""),
                 "balance": round(fb, 2)},
        "to": {"name": to_account, "label": (ta.account_name if ta else ""),
               "type": (ta.account_type if ta else ""), "root": (ta.root_type if ta else ""),
               "balance": round(tb, 2), "after": round(tb + fb, 2)},
        "move": round(fb, 2),
        "ok": (not problems) and abs(round(fb, 2)) > 0.004,
        "problems": problems,
    }


def _reclass_poster(action):
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    frm, to, as_of, amt = p["from_account"], p["to_account"], p["as_of"], flt(p["amount"])
    je = frappe.new_doc("Journal Entry")
    je.company = action.company
    je.posting_date = as_of
    je.voucher_type = "Journal Entry"
    je.user_remark = p.get("remark") or f"Reclassify {frm.split(' - ')[0]} → {to.split(' - ')[0]} @ {as_of}"
    # Zero the source (post the opposite of its balance); the target absorbs it.
    je.append("accounts", {"account": frm,
                           "debit_in_account_currency": (-amt if amt < 0 else 0.0),
                           "credit_in_account_currency": (amt if amt > 0 else 0.0)})
    je.append("accounts", {"account": to,
                           "debit_in_account_currency": (amt if amt > 0 else 0.0),
                           "credit_in_account_currency": (-amt if amt < 0 else 0.0)})
    je.flags.ignore_permissions = True
    je.insert()
    je.submit()
    return {"voucher_type": "Journal Entry", "voucher_no": je.name,
            "result": {"moved": round(amt, 2), "from": frm, "to": to}}


_actions.register_poster(RECLASS_ACTION, _reclass_poster)
_actions.register_reverter(RECLASS_ACTION, _actions._cancel_voucher_reverter)


@frappe.whitelist()
def post_reclass(company=None, from_account=None, to_account=None, as_of=None, remark=None):
    """Move the whole balance of `from_account` into `to_account` with one JE.
    Balance is recomputed server-side as of `as_of` (never trust the client)."""
    assert_can_write()
    target = _target(company)
    if not target:
        frappe.throw("No company in scope")
    as_of = str(as_of or nowdate())[:10]
    fa, ta = _acc(from_account), _acc(to_account)
    if not fa or fa.company != target or fa.is_group:
        frappe.throw("Invalid source account")
    if not ta or ta.company != target or ta.is_group:
        frappe.throw("Invalid target account")
    if from_account == to_account:
        frappe.throw("Source and target must differ")
    if fa.account_type in ("Receivable", "Payable") or ta.account_type in ("Receivable", "Payable"):
        frappe.throw("Party accounts (Receivable/Payable) need per-party reconciliation, not a balance reclass")
    if fa.account_currency != ta.account_currency:
        frappe.throw("Both accounts must be in the same currency")
    amt = round(_bal(from_account, as_of), 2)
    if abs(amt) < 0.005:
        frappe.throw("The source account is already zero at that date")
    key = f"reclass:{target}:{from_account}:{to_account}:{as_of}"
    return _actions.execute(
        RECLASS_ACTION, target, key,
        payload={"from_account": from_account, "to_account": to_account, "as_of": as_of,
                 "amount": amt, "remark": remark},
        amount=abs(amt),
        notes=f"Reclass {from_account.split(' - ')[0]} → {to_account.split(' - ')[0]} ({abs(amt):,.0f})")
