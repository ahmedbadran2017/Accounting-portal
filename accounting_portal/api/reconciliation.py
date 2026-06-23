"""COD Cash Reconciliation — Pillar 1 (read engine).

The −2.85M debtor credit balance on Justyol Morocco is over-collection: COD cash
(via Cathadis) credits debtors faster than Sales Invoices debit them. Validated
on the live instance: 1,079 Payment Entries hold ~3.51M unallocated while only
265 invoices (~114k) are open. Reconciliation = allocate unallocated receipts to
open invoices (same party); the residual is collected-without-invoice and is
flagged. The allocation WRITE is posted through accounting_portal.api._actions
(idempotent + audited) — added as the next slice; this module is the read side.
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
def cod_summary(company=None):
    """The reconciliation headline: net debtor, unallocated receipts, open
    invoices, and how much is collected-without-invoice (the real gap)."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    net_debtor = flt(frappe.db.sql(
        "SELECT COALESCE(SUM(debit-credit),0) FROM `tabGL Entry` WHERE company=%s AND is_cancelled=0 AND party_type='Customer'",
        (target,))[0][0])
    ua = frappe.db.sql(
        "SELECT COALESCE(SUM(unallocated_amount),0), COUNT(*) FROM `tabPayment Entry` WHERE company=%s AND docstatus=1 AND payment_type='Receive' AND unallocated_amount>0",
        (target,))[0]
    oi = frappe.db.sql(
        "SELECT COALESCE(SUM(outstanding_amount),0), COUNT(*) FROM `tabSales Invoice` WHERE company=%s AND docstatus=1 AND outstanding_amount>0",
        (target,))[0]
    unalloc, outstanding = flt(ua[0]), flt(oi[0])
    return {
        "company": target,
        "net_debtor": net_debtor,
        "unallocated_amount": unalloc, "unallocated_count": ua[1],
        "outstanding_amount": outstanding, "outstanding_count": oi[1],
        # Best case the matching could clear; the rest is cash with no open invoice.
        "matchable": min(unalloc, outstanding),
        "collected_no_invoice": max(0.0, unalloc - outstanding),
    }


@frappe.whitelist()
def list_accounts(company=None):
    """Bank & Cash accounts with live balances — the Banking → Accounts tab.
    A negative Cash balance (overdraft) is a control flag worth seeing here."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return []
    return frappe.db.sql(
        """
        SELECT a.name AS account, a.account_type AS type, a.account_currency AS ccy,
               ROUND(SUM(gl.debit - gl.credit)) AS balance
        FROM `tabAccount` a
        JOIN `tabGL Entry` gl ON gl.account = a.name AND gl.is_cancelled = 0
        WHERE a.company = %s AND a.account_type IN ('Bank', 'Cash')
        GROUP BY a.name, a.account_type, a.account_currency
        ORDER BY ABS(SUM(gl.debit - gl.credit)) DESC
        """,
        (target,), as_dict=True)


@frappe.whitelist()
def unmatched_payments(company=None, limit=50):
    """COD receipts holding unallocated cash (the queue to reconcile), biggest first."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return []
    return frappe.db.sql(
        """
        SELECT name, party AS customer, posting_date AS date, mode_of_payment AS mode,
               paid_amount, unallocated_amount, reference_no
        FROM `tabPayment Entry`
        WHERE company=%s AND docstatus=1 AND payment_type='Receive' AND unallocated_amount>0
        ORDER BY unallocated_amount DESC LIMIT %s
        """,
        (target, min(int(limit or 50), 200)), as_dict=True)


@frappe.whitelist()
def open_invoices(company=None, limit=50):
    """Sales invoices still carrying an outstanding balance, biggest first."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return []
    return frappe.db.sql(
        """
        SELECT name, customer, posting_date AS date, grand_total, outstanding_amount, status
        FROM `tabSales Invoice`
        WHERE company=%s AND docstatus=1 AND outstanding_amount>0
        ORDER BY outstanding_amount DESC LIMIT %s
        """,
        (target, min(int(limit or 50), 200)), as_dict=True)


@frappe.whitelist()
def match_candidates(payment, limit=10):
    """Open invoices for a receipt's customer, ranked by closeness to the
    unallocated amount — the suggestions a reconcile action would draw from."""
    assert_portal_access()
    pe = frappe.db.get_value(
        "Payment Entry", payment, ["party", "unallocated_amount", "company"], as_dict=True)
    if not pe:
        frappe.throw("Payment not found")
    candidates = frappe.db.sql(
        """
        SELECT name, posting_date AS date, grand_total, outstanding_amount
        FROM `tabSales Invoice`
        WHERE company=%s AND customer=%s AND docstatus=1 AND outstanding_amount>0
        ORDER BY ABS(outstanding_amount - %s) ASC LIMIT %s
        """,
        (pe.company, pe.party, flt(pe.unallocated_amount), min(int(limit or 10), 50)), as_dict=True)
    return {
        "payment": payment, "customer": pe.party,
        "unallocated": flt(pe.unallocated_amount), "candidates": candidates,
    }
