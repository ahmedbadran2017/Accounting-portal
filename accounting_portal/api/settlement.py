"""Monthly settlement — sweep sibling sub-account balances into one survivor.

A single real account (e.g. a Kuveyttürk credit card) got booked across several
GL codes over time; individually each shows a large balance, together they net to
the truth. This posts ONE month-end Journal Entry that zeroes each selected
sibling and moves its balance into a chosen survivor account, so the running
balance lives in one place.

Recurring by design: run it at each month-end (dated the last day of the month).
Single-currency only (survivor + sources all in the company base currency) so the
entry is exact and needs no FX. Gated, audited, reversible (cancel the JE).
"""
import json

import frappe
from frappe.utils import flt, nowdate

from accounting_portal.api import _actions
from accounting_portal.api.permissions import (
    assert_can_write, assert_portal_access, resolve_companies,
)

SETTLE_ACTION = "Monthly settlement"


def _target(company):
    cs = resolve_companies(company)
    if not cs:
        return None
    return company if (company and company in cs) else cs[0]


def _bal(account, as_of):
    """Account-currency balance up to and including `as_of`."""
    return flt(frappe.db.sql(
        """SELECT COALESCE(SUM(debit_in_account_currency - credit_in_account_currency), 0)
           FROM `tabGL Entry` WHERE account=%s AND is_cancelled=0 AND posting_date<=%s""",
        (account, as_of))[0][0])


@frappe.whitelist()
def settlement_siblings(company=None, survivor=None, as_of=None):
    """The sibling leaf accounts (same parent group) that could be swept into the
    survivor, with each balance as of `as_of`. The UI previews and lets the
    accountant tick which to include."""
    assert_portal_access()
    target = _target(company)
    if not target or not survivor:
        return {"survivor": None, "siblings": []}
    surv = frappe.db.get_value(
        "Account", survivor,
        ["parent_account", "account_currency", "is_group", "company", "account_name"], as_dict=True)
    if not surv or surv.company != target or surv.is_group:
        frappe.throw("Pick a valid (non-group) account")
    as_of = str(as_of or nowdate())[:10]
    base = frappe.db.get_value("Company", target, "default_currency")
    rows = frappe.db.sql(
        """SELECT name, account_name, account_currency ccy, disabled, account_type
           FROM `tabAccount`
           WHERE company=%s AND parent_account=%s AND is_group=0 AND name!=%s
           ORDER BY account_name""",
        (target, surv.parent_account, survivor), as_dict=True)
    sibs = []
    for r in rows:
        b = _bal(r.name, as_of)
        sibs.append({"name": r.name, "account_name": r.account_name, "ccy": r.ccy,
                     "balance": round(b, 2), "disabled": int(r.disabled or 0),
                     "same_ccy": r.ccy == surv.account_currency and surv.account_currency == base})
    sibs.sort(key=lambda x: -abs(x["balance"]))
    return {
        "survivor": {"name": survivor, "account_name": surv.account_name,
                     "ccy": surv.account_currency, "balance": round(_bal(survivor, as_of), 2)},
        "base_ccy": base, "as_of": as_of,
        "settleable": surv.account_currency == base,   # survivor must be base-currency
        "siblings": sibs,
    }


def _settle_poster(action):
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    survivor, as_of, sources = p["survivor"], p["as_of"], p["sources"]
    je = frappe.new_doc("Journal Entry")
    je.company = action.company
    je.posting_date = as_of
    je.voucher_type = "Journal Entry"
    je.user_remark = p.get("remark") or f"Monthly settlement into {survivor.split(' - ')[0]} @ {as_of}"
    total = 0.0
    for s in sources:
        b = flt(s["balance"])
        if not b:
            continue
        # Zero the sibling: post the opposite side of its balance.
        je.append("accounts", {
            "account": s["name"],
            "debit_in_account_currency": (-b if b < 0 else 0.0),
            "credit_in_account_currency": (b if b > 0 else 0.0)})
        total += b
    if not je.get("accounts"):
        frappe.throw("Nothing to settle — the selected accounts are already zero at that date")
    # The survivor absorbs the net (skip if the siblings already offset each other).
    if abs(round(total, 2)) > 0.004:
        je.append("accounts", {
            "account": survivor,
            "debit_in_account_currency": (total if total > 0 else 0.0),
            "credit_in_account_currency": (-total if total < 0 else 0.0)})
    je.flags.ignore_permissions = True
    je.insert()
    je.submit()
    return {"voucher_type": "Journal Entry", "voucher_no": je.name,
            "result": {"swept": len([s for s in sources if flt(s["balance"])]),
                       "net_into_survivor": round(total, 2)}}


_actions.register_poster(SETTLE_ACTION, _settle_poster)
_actions.register_reverter(SETTLE_ACTION, _actions._cancel_voucher_reverter)


@frappe.whitelist()
def post_monthly_settlement(company=None, survivor=None, sources=None, as_of=None, remark=None):
    """Sweep the selected sibling balances into `survivor` with one month-end JE.
    Balances are recomputed server-side as of `as_of` (never trust the client)."""
    assert_can_write()
    target = _target(company)
    if not target or not survivor:
        frappe.throw("Pick the surviving account")
    srcs = sources if isinstance(sources, list) else json.loads(sources or "[]")
    srcs = [s for s in srcs if s]
    if not srcs:
        frappe.throw("Pick at least one account to settle")
    as_of = str(as_of or nowdate())[:10]
    base = frappe.db.get_value("Company", target, "default_currency")
    surv = frappe.db.get_value("Account", survivor, ["account_currency", "company", "is_group"], as_dict=True)
    if not surv or surv.company != target or surv.is_group:
        frappe.throw("Invalid survivor account")
    if surv.account_currency != base:
        frappe.throw("Settlement supports base-currency accounts only")
    clean, net = [], 0.0
    for name in srcs:
        info = frappe.db.get_value("Account", name, ["account_currency", "company", "is_group"], as_dict=True)
        if not info or info.company != target or info.is_group:
            frappe.throw(f"Invalid account: {name}")
        if info.account_currency != base:
            frappe.throw(f"{name} isn't in the base currency — can't settle it here")
        if name == survivor:
            continue
        b = _bal(name, as_of)
        if b:
            clean.append({"name": name, "balance": round(b, 2)})
            net += b
    if not clean:
        frappe.throw("Nothing to settle — the selected accounts are already zero at that date")
    key = f"settle:{target}:{survivor}:{as_of}"
    return _actions.execute(
        SETTLE_ACTION, target, key,
        payload={"survivor": survivor, "sources": clean, "as_of": as_of, "remark": remark},
        amount=abs(round(net, 2)),
        notes=f"Monthly settlement → {survivor.split(' - ')[0]} @ {as_of} ({len(clean)} accounts)")
