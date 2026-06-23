"""Accountant endpoints — General Ledger, Trial Balance, Chart of Accounts.

All live ERPNext, entity-scoped, filtering is_cancelled = 0. Balances use the
net sum(debit - credit) convention; the trial balance presents each account's
net on the debit or credit side.
"""
import frappe
from frappe.utils import flt

from accounting_portal.api.permissions import assert_portal_access, resolve_companies


def _target(company):
    companies = resolve_companies(company)
    if not companies:
        return None
    return company if (company and company in companies) else companies[0]


@frappe.whitelist()
def general_ledger(company=None, account=None, limit=100):
    """Recent GL entries for one company (newest first)."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return []
    limit = min(int(limit or 100), 500)
    conds = ["gl.company = %(company)s", "gl.is_cancelled = 0"]
    params = {"company": target, "limit": limit}
    if account:
        conds.append("gl.account = %(account)s")
        params["account"] = account
    return frappe.db.sql(
        f"""
        SELECT gl.posting_date AS date, gl.voucher_type, gl.voucher_no AS ref,
               gl.account, gl.party, gl.debit AS dr, gl.credit AS cr, gl.remarks
        FROM `tabGL Entry` gl
        WHERE {' AND '.join(conds)}
        ORDER BY gl.posting_date DESC, gl.creation DESC
        LIMIT %(limit)s
        """,
        params, as_dict=True,
    )


@frappe.whitelist()
def trial_balance(company=None):
    """Net trial balance per account for one company (non-zero balances only).

    Flags anomalies the auditor cares about: an asset/expense carrying a credit
    balance, or a liability/income carrying a debit balance (a sign the account
    is mis-stated), and any single balance above an outsized threshold.
    """
    assert_portal_access()
    target = _target(company)
    if not target:
        return {"rows": [], "total_dr": 0, "total_cr": 0}
    rows = frappe.db.sql(
        """
        SELECT acc.account_number AS code, acc.account_name AS name,
               acc.root_type, acc.account_type,
               SUM(gl.debit - gl.credit) AS bal
        FROM `tabGL Entry` gl
        JOIN `tabAccount` acc ON acc.name = gl.account
        WHERE gl.is_cancelled = 0 AND gl.company = %s
        GROUP BY gl.account
        HAVING ABS(SUM(gl.debit - gl.credit)) > 0.005
        ORDER BY acc.lft
        """,
        (target,), as_dict=True,
    )
    out, total_dr, total_cr = [], 0.0, 0.0
    for r in rows:
        bal = flt(r.bal)
        dr = bal if bal > 0 else 0.0
        cr = -bal if bal < 0 else 0.0
        total_dr += dr
        total_cr += cr
        debit_nature = r.root_type in ("Asset", "Expense")
        anomaly = (debit_nature and bal < 0) or (not debit_nature and bal > 0) or abs(bal) >= 50_000_000
        out.append({"code": r.code, "name": r.name, "root_type": r.root_type,
                    "dr": dr, "cr": cr, "anomaly": bool(anomaly)})
    return {"rows": out, "total_dr": total_dr, "total_cr": total_cr}


@frappe.whitelist()
def chart_of_accounts(company=None):
    """Accounts grouped by root_type with their net balances (non-zero)."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return []
    rows = frappe.db.sql(
        """
        SELECT acc.account_number AS code, acc.account_name AS name,
               acc.root_type, acc.account_type,
               SUM(gl.debit - gl.credit) AS bal
        FROM `tabGL Entry` gl
        JOIN `tabAccount` acc ON acc.name = gl.account
        WHERE gl.is_cancelled = 0 AND gl.company = %s
        GROUP BY gl.account
        HAVING ABS(SUM(gl.debit - gl.credit)) > 0.005
        ORDER BY acc.root_type, acc.lft
        """,
        (target,), as_dict=True,
    )
    for r in rows:
        r["bal"] = flt(r.bal)
        debit_nature = r.root_type in ("Asset", "Expense")
        r["anomaly"] = bool((debit_nature and r["bal"] < 0) or abs(r["bal"]) >= 50_000_000)
    return rows


@frappe.whitelist()
def pending_journals(company=None, limit=50):
    """Draft (docstatus = 0) Journal Entries for one company — the maker-checker
    queue. Submitted entries are already posted; cancelled are excluded."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return []
    limit = min(int(limit or 50), 200)
    return frappe.db.sql(
        """
        SELECT je.name AS ref, je.total_debit AS amount, je.posting_date AS date,
               je.title, je.user_remark AS remark, je.voucher_type
        FROM `tabJournal Entry` je
        WHERE je.company = %s AND je.docstatus = 0
        ORDER BY je.modified DESC
        LIMIT %s
        """,
        (target, limit), as_dict=True,
    )
