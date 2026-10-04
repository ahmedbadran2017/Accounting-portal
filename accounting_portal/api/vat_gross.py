"""Revenue at the price the customer pays — VAT included.

The ledger books a sale net: the 20% VAT goes to a 391.x liability and never
touches revenue. For this business that understates what a sale brings in. The
VAT charged is not handed over: an input-VAT credit built up on purchase invoices
absorbs almost all of it, so the price "includes everything" and only the VAT
actually paid to the state is a cost.

So every management report states revenue VAT-inclusive (a "VAT included in
sale price" line added to revenue) and carries one cost line, "VAT paid to the
state", for what really left the bank. The statutory figure is always one line
away: statutory net = net − VAT in price + VAT paid. The balance sheet and the
VAT reports stay statutory; so does the investor statement, which is on its own
agreed basis.

Both figures come from the GL so they reconcile to the same ledger the P&L
reads. Sales-invoice VAT is the credit to the output-VAT accounts posted by Sales
Invoices (returns post a debit and net off). VAT paid is a debit to those
accounts from a voucher that also moves a bank or cash account: a filing settled
against the input-VAT credit, or the one-off "VAT Return" JE that parked a
recovery in revenue, moves no cash and is not a payment.
"""
import frappe
from frappe.utils import flt

VAT_IN_PRICE = "__vat_in_price__"
VAT_PAID = "__vat_paid__"
VAT_IN_PRICE_LABEL = "VAT included in sale price"
VAT_PAID_LABEL = "VAT paid to the state"


def _output_accounts(company):
    ck = f"ap_vat_out_accts:{company}"
    hit = frappe.cache().get_value(ck)
    if hit is not None:
        return hit
    accts = [r[0] for r in frappe.db.sql(
        """SELECT DISTINCT t.account_head FROM `tabSales Taxes and Charges` t
           JOIN `tabSales Invoice` s ON s.name=t.parent
           JOIN `tabAccount` a ON a.name=t.account_head
           WHERE s.company=%s AND s.docstatus=1 AND a.root_type='Liability'""", (company,))]
    try:
        frappe.cache().set_value(ck, accts, expires_in_sec=3600)
    except Exception:
        pass
    return accts


def by_month(company, fr, to):
    """{"YYYY-MM": {"in_price": x, "paid": y}} over [fr, to]."""
    accts = _output_accounts(company)
    out = {}
    if not accts:
        return out
    for r in frappe.db.sql(
            """SELECT DATE_FORMAT(posting_date,'%%Y-%%m') ym, SUM(credit-debit) v
               FROM `tabGL Entry`
               WHERE company=%s AND is_cancelled=0 AND voucher_type='Sales Invoice'
                 AND account IN %s AND posting_date BETWEEN %s AND %s
               GROUP BY ym""", (company, tuple(accts), fr, to), as_dict=True):
        out.setdefault(r.ym, {"in_price": 0.0, "paid": 0.0})["in_price"] += flt(r.v)
    for r in frappe.db.sql(
            """SELECT DATE_FORMAT(g.posting_date,'%%Y-%%m') ym, SUM(g.debit-g.credit) v
               FROM `tabGL Entry` g
               WHERE g.company=%s AND g.is_cancelled=0 AND g.account IN %s
                 AND g.voucher_type NOT IN ('Sales Invoice','Purchase Invoice')
                 AND g.posting_date BETWEEN %s AND %s
                 AND EXISTS (SELECT 1 FROM `tabGL Entry` b JOIN `tabAccount` ba ON ba.name=b.account
                             WHERE b.voucher_no=g.voucher_no AND b.voucher_type=g.voucher_type
                               AND b.is_cancelled=0 AND ba.account_type IN ('Bank','Cash'))
               GROUP BY ym""", (company, tuple(accts), fr, to), as_dict=True):
        out.setdefault(r.ym, {"in_price": 0.0, "paid": 0.0})["paid"] += flt(r.v)
    return out


def totals(company, fr, to):
    m = by_month(company, fr, to)
    return (sum(v["in_price"] for v in m.values()), sum(v["paid"] for v in m.values()))
