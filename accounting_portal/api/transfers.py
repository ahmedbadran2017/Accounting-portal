"""Bank transfers to confirm — the orders logistics may not prepare yet.

A customer who pays by bank transfer ("Virement bancaire") has paid before the
parcel leaves — but only accounting can say the money actually arrived. Until
then logistics holds the order out of picking (logistics_portal.api.picking.
_TRANSFER_HELD), because the Cathedis label is printed for grand_total minus
advance_paid: a transfer that is not on the books makes the courier collect
the price again. That happened on #246427 and #247117 (July), where the
transfer was posted weeks after delivery and Cathedis remitted the same money.

This is accounting's side of that gate: the waiting orders, and one action
that records the transfer as an advance Payment Entry on the order. The
moment it posts, advance_paid covers the total, logistics releases the order
by itself, and its label reads 0.

The held condition must match logistics_portal's _TRANSFER_HELD exactly:
payment_type is a transfer and advance_paid is short of the total by 1 MAD or
more (transfers are posted in whole dirhams: 186 for a 186.10 order).
"""
import frappe
from frappe.utils import flt, nowdate

from accounting_portal.api import _paginate
from accounting_portal.api.permissions import assert_portal_access, resolve_companies

TRANSFER_TYPES = ("Virement bancaire", "Bank Transfer")
# Where accounting already posts transfers (all of 2026's are on it).
DEFAULT_ACCOUNT = "108.021.007 - Deposite Transactions - JM"
_HELD = "COALESCE(so.advance_paid, 0) + 1 < so.grand_total"


def _target(company):
    companies = resolve_companies(company)
    if not companies:
        return None
    return company if (company and company in companies) else companies[0]


def _where(search):
    w = f"""so.company = %(c)s AND so.docstatus = 1
            AND so.payment_type IN %(t)s AND {_HELD}
            AND COALESCE(so.custom_sales_status, '') NOT IN ('Cancelled')
            AND IFNULL(so.custom_logistics_status, 'Pending') IN ('', 'Pending')
            AND so.status NOT IN ('Closed', 'Completed')
            AND so.creation >= DATE_SUB(NOW(), INTERVAL 90 DAY)"""
    if search:
        w += " AND (so.name LIKE %(q)s OR so.customer_name LIKE %(q)s OR so.custom_customer_phone LIKE %(q)s)"
    return w


@frappe.whitelist()
def awaiting(company=None, search=None, start=0, page_size=25):
    """Transfer orders whose money is not posted yet, oldest first."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {"rows": [], "total": 0, "summary": {}}
    search = (search or "").strip()
    params = {"c": target, "t": TRANSFER_TYPES, "q": f"%{search}%"}
    rows, total, st_, ps = _paginate.page_query(
        "`tabSales Order` so", _where(search), params,
        """so.name, so.customer, so.customer_name, so.custom_customer_phone AS phone,
           so.grand_total AS total, COALESCE(so.advance_paid, 0) AS paid,
           so.custom_sales_status AS sales_status, so.creation,
           DATEDIFF(NOW(), so.creation) AS age""",
        "so.creation ASC", start, page_size)
    s = frappe.db.sql(
        f"""SELECT COUNT(*) n, COALESCE(SUM(so.grand_total - COALESCE(so.advance_paid, 0)), 0) v
            FROM `tabSales Order` so WHERE {_where('')}""", {"c": target, "t": TRANSFER_TYPES})[0]
    for r in rows:
        r["due"] = round(flt(r.total) - flt(r.paid), 2)
        r["creation"] = str(r.creation)[:16]
    return {"rows": rows, "total": total, "start": st_, "page_size": ps,
            "summary": {"count": int(s[0] or 0), "value": round(flt(s[1]), 2),
                        "default_account": DEFAULT_ACCOUNT
                        if frappe.db.exists("Account", {"name": DEFAULT_ACCOUNT, "company": target})
                        else ""}}


@frappe.whitelist()
def confirm(company=None, sales_order=None, amount=None, account=None,
            reference_no=None, posting_date=None):
    """The transfer is on the bank statement: post it as an advance on the order.
    Goes through the portal's write gateway (audit, dedupe, approval above the
    material threshold) like every other receipt."""
    from accounting_portal.api.payments import create_payment_entry
    target = _target(company)
    if not target:
        frappe.throw("No company in scope")
    so = frappe.db.get_value(
        "Sales Order", sales_order,
        ["name", "company", "docstatus", "customer", "payment_type", "grand_total",
         "advance_paid", "custom_sales_status"], as_dict=True)
    if not so or so.company != target or so.docstatus != 1:
        frappe.throw("Order not found in this company")
    if so.payment_type not in TRANSFER_TYPES:
        frappe.throw("This order is not paid by bank transfer")
    if so.custom_sales_status == "Cancelled":
        frappe.throw("This order is cancelled — nothing to confirm")
    due = round(flt(so.grand_total) - flt(so.advance_paid), 2)
    if due < 1:
        frappe.throw("The transfer is already recorded on this order")
    amt = flt(amount) if amount not in (None, "") else due
    if amt <= 0 or amt > due + 0.01:
        frappe.throw(f"Amount must be between 0 and the {due:,.2f} still due")
    account = account or DEFAULT_ACCOUNT
    res = create_payment_entry(
        company=target, party=so.customer, amount=amt, account=account,
        reference_no=(reference_no or "").strip() or f"VIR-{so.name.lstrip('#')}",
        posting_date=posting_date or nowdate(), payment_type="Receive", party_type="Customer",
        references=[{"doctype": "Sales Order", "name": so.name, "amount": amt}],
        dedupe_key=f"transfer:{so.name}:{round(amt, 2)}")
    status = (res or {}).get("status") if isinstance(res, dict) else None
    try:
        frappe.get_doc({
            "doctype": "Comment", "comment_type": "Comment",
            "reference_doctype": "Sales Order", "reference_name": so.name,
            "content": (f"Bank transfer of {amt:,.2f} MAD confirmed by {frappe.session.user} "
                        + ("— released to logistics." if status == "Posted"
                           else f"— payment {status or 'recorded'}, awaiting approval.")),
        }).insert(ignore_permissions=True)
    except Exception:
        pass
    return res
