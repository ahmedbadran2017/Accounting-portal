"""Operating vs Under-audit classification for bank/cash accounts.

Some companies (Maslak especially) accumulated dozens of bank/cash accounts that
were used incorrectly and still need an audit. Their tangled unreconciled
balances drown the few real operating accounts, so the team can't read the cash
position at a glance.

This lets the team park such accounts "under audit" so the banking cash cockpit
shows only the clean operating accounts — WITHOUT touching the GL. The balances
stay in the trial balance / balance sheet (statutory truth); only the operational
view segregates them. Fully reversible: flip the flag back and the account
returns to the operating view. No schema migration — the per-company list lives
in tabDefaultValue, so it persists across restarts and is shared across users.
"""
import json

import frappe

from accounting_portal.api.permissions import (
    assert_can_write,
    assert_portal_access,
    resolve_companies,
)


def _target(company):
    companies = resolve_companies(company)
    if not companies:
        return None
    return company if (company and company in companies) else companies[0]


def _key(company):
    return "ap_uaudit::" + (company or "")


def under_audit_set(company):
    """The set of account names the team has parked under audit for this company."""
    raw = frappe.db.get_default(_key(company))
    if not raw:
        return set()
    try:
        v = json.loads(raw)
        return set(v) if isinstance(v, list) else set()
    except Exception:
        return set()


def _save(company, names):
    frappe.db.set_default(_key(company), json.dumps(sorted(set(names))))
    # The banking cockpit caches its account list — drop it so the flag shows now.
    try:
        frappe.cache().delete_keys("ap_bankrec_acc")
    except Exception:
        pass


def _truthy(v):
    return v in (True, 1, "1", "true", "True", "yes")


@frappe.whitelist()
def list_status(company=None):
    """Read side: the under-audit account names for the company."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {"under_audit": []}
    return {"under_audit": sorted(under_audit_set(target))}


@frappe.whitelist()
def set_status(company=None, account=None, under_audit=None):
    """Park / un-park ONE account. View-only classification — no GL change, fully
    reversible. Requires write capability."""
    assert_can_write()
    target = _target(company)
    if not target or not account:
        frappe.throw("Account required")
    if frappe.db.get_value("Account", account, "company") != target:
        frappe.throw("Account belongs to another company")
    cur = under_audit_set(target)
    if _truthy(under_audit):
        cur.add(account)
    else:
        cur.discard(account)
    _save(target, cur)
    frappe.db.commit()
    return {"under_audit": sorted(cur)}


@frappe.whitelist()
def set_status_bulk(company=None, accounts=None, under_audit=None):
    """Park / un-park MANY accounts in one action (park the 30-odd messy accounts,
    or return a batch to operating once audited)."""
    assert_can_write()
    target = _target(company)
    accs = accounts if isinstance(accounts, list) else json.loads(accounts or "[]")
    accs = [a for a in accs if a]
    if not target or not accs:
        frappe.throw("No accounts selected")
    valid = set(frappe.db.sql_list(
        """SELECT name FROM `tabAccount` WHERE company=%s AND name IN %s""",
        (target, tuple(accs))))
    cur = under_audit_set(target)
    if _truthy(under_audit):
        cur |= valid
    else:
        cur -= valid
    _save(target, cur)
    frappe.db.commit()
    return {"under_audit": sorted(cur), "changed": len(valid)}
