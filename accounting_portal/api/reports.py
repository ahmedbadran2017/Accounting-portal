"""Financial reports — P&L, balance sheet, AR/AP aging, VAT.

All read-only, entity-scoped, and validated against the live books. Heavy GL
aggregates are bounded by company + period. Account-level rows are returned so
the team sees exactly where each number comes from (and the auditor's anomalies,
like the stock-adjustment pile in the P&L, stay visible rather than hidden).
"""
import frappe
from frappe.utils import flt, nowdate

from accounting_portal.api.permissions import assert_portal_access, resolve_companies


def _target(company):
    companies = resolve_companies(company)
    if not companies:
        return None
    return company if (company and company in companies) else companies[0]


def _year_bounds(year=None):
    y = int(year or nowdate()[:4])
    return f"{y}-01-01", f"{y}-12-31"


@frappe.whitelist()
def pnl(company=None, from_date=None, to_date=None):
    """Profit & loss — income and expense accounts grouped, with net result."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    if not (from_date and to_date):
        from_date, to_date = _year_bounds()

    rows = frappe.db.sql(
        """SELECT a.name, a.account_name, a.root_type,
                  ROUND(SUM(gle.credit - gle.debit)) AS credit_net,
                  ROUND(SUM(gle.debit - gle.credit)) AS debit_net
           FROM `tabGL Entry` gle JOIN `tabAccount` a ON a.name = gle.account
           WHERE gle.company=%s AND gle.is_cancelled=0
             AND a.root_type IN ('Income','Expense')
             AND gle.posting_date BETWEEN %s AND %s
           GROUP BY a.name HAVING SUM(ABS(gle.debit)) + SUM(ABS(gle.credit)) > 0
           ORDER BY ABS(SUM(gle.debit - gle.credit)) DESC""",
        (target, from_date, to_date), as_dict=True)

    income = [{"account": r.name, "name": r.account_name, "amount": flt(r.credit_net)}
              for r in rows if r.root_type == "Income"]
    expense = [{"account": r.name, "name": r.account_name, "amount": flt(r.debit_net)}
               for r in rows if r.root_type == "Expense"]
    income_total = sum(r["amount"] for r in income)
    expense_total = sum(r["amount"] for r in expense)

    # Flag a single expense account that dominates the statement (the broken
    # Stock-Adjustment pile) so the P&L isn't silently read as a real loss.
    anomaly = None
    if expense and expense_total and expense[0]["amount"] > 0.4 * expense_total and expense[0]["amount"] > 1_000_000:
        anomaly = {"account": expense[0]["account"], "name": expense[0]["name"], "amount": expense[0]["amount"]}

    return {
        "from_date": from_date, "to_date": to_date, "company": target,
        "income": income[:20], "expense": expense[:20],
        "income_total": income_total, "expense_total": expense_total,
        "net": income_total - expense_total, "anomaly": anomaly,
    }


@frappe.whitelist()
def balance_sheet(company=None, as_on=None):
    """Balance sheet — asset / liability / equity balances as of a date."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    as_on = as_on or nowdate()
    rows = frappe.db.sql(
        """SELECT a.root_type,
                  ROUND(SUM(gle.debit - gle.credit)) AS debit_net,
                  ROUND(SUM(gle.credit - gle.debit)) AS credit_net
           FROM `tabGL Entry` gle JOIN `tabAccount` a ON a.name = gle.account
           WHERE gle.company=%s AND gle.is_cancelled=0
             AND a.root_type IN ('Asset','Liability','Equity')
             AND gle.posting_date <= %s
           GROUP BY a.root_type""",
        (target, as_on), as_dict=True)
    out = {"assets": 0.0, "liabilities": 0.0, "equity": 0.0}
    for r in rows:
        if r.root_type == "Asset":
            out["assets"] = flt(r.debit_net)
        elif r.root_type == "Liability":
            out["liabilities"] = flt(r.credit_net)
        elif r.root_type == "Equity":
            out["equity"] = flt(r.credit_net)
    out["as_on"] = as_on
    out["check"] = round(out["assets"] - out["liabilities"] - out["equity"], 0)
    return out


def _aging(doctype, company):
    return frappe.db.sql(
        f"""SELECT
              ROUND(SUM(CASE WHEN DATEDIFF(CURDATE(), IFNULL(due_date,posting_date)) <= 0 THEN outstanding_amount ELSE 0 END)) AS cur,
              ROUND(SUM(CASE WHEN DATEDIFF(CURDATE(), IFNULL(due_date,posting_date)) BETWEEN 1 AND 30 THEN outstanding_amount ELSE 0 END)) AS d1_30,
              ROUND(SUM(CASE WHEN DATEDIFF(CURDATE(), IFNULL(due_date,posting_date)) BETWEEN 31 AND 60 THEN outstanding_amount ELSE 0 END)) AS d31_60,
              ROUND(SUM(CASE WHEN DATEDIFF(CURDATE(), IFNULL(due_date,posting_date)) BETWEEN 61 AND 90 THEN outstanding_amount ELSE 0 END)) AS d61_90,
              ROUND(SUM(CASE WHEN DATEDIFF(CURDATE(), IFNULL(due_date,posting_date)) > 90 THEN outstanding_amount ELSE 0 END)) AS d90p,
              ROUND(SUM(outstanding_amount)) AS total, COUNT(*) AS n
           FROM `tab{doctype}` WHERE company=%s AND docstatus=1 AND outstanding_amount<>0""",
        (company,), as_dict=True)[0]


@frappe.whitelist()
def ar_aging(company=None):
    """Receivables aging by due date — current / 1-30 / 31-60 / 61-90 / 90+."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    out = _aging("Sales Invoice", target)
    out["company"] = target
    return out


@frappe.whitelist()
def ap_aging(company=None):
    """Payables aging by due date — current / 1-30 / 31-60 / 61-90 / 90+."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    out = _aging("Purchase Invoice", target)
    out["company"] = target
    return out


@frappe.whitelist()
def inventory_health(company=None):
    """Diagnose the stock/COGS break: stock-in-hand vs the Stock-Adjustment pile.

    Healthy books relieve stock to COGS on delivery. Here stock-in-hand is
    enormous while a Stock-Adjustment account absorbs the offset — so margin is
    unmeasurable. Returns the figures and the magnitude of the distortion.
    """
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    stock = flt(frappe.db.sql(
        """SELECT ROUND(SUM(gle.debit - gle.credit)) FROM `tabGL Entry` gle
           JOIN `tabAccount` a ON a.name=gle.account
           WHERE gle.company=%s AND gle.is_cancelled=0 AND a.account_type='Stock'""",
        (target,))[0][0] or 0)
    adj = frappe.db.sql(
        """SELECT a.name, ROUND(SUM(gle.debit - gle.credit)) AS bal FROM `tabGL Entry` gle
           JOIN `tabAccount` a ON a.name=gle.account
           WHERE gle.company=%s AND gle.is_cancelled=0 AND a.account_name LIKE '%%Stock Adjustment%%'
           GROUP BY a.name ORDER BY ABS(SUM(gle.debit - gle.credit)) DESC LIMIT 1""",
        (target,), as_dict=True)
    adj_acct = adj[0].name if adj else None
    adj_bal = flt(adj[0].bal) if adj else 0.0
    revenue = flt(frappe.db.sql(
        """SELECT ROUND(SUM(gle.credit - gle.debit)) FROM `tabGL Entry` gle
           JOIN `tabAccount` a ON a.name=gle.account
           WHERE gle.company=%s AND gle.is_cancelled=0 AND a.root_type='Income'
             AND gle.posting_date BETWEEN %s AND %s""",
        (target, *_year_bounds()))[0][0] or 0)
    return {
        "company": target, "stock_in_hand": stock, "adjustment_account": adj_acct,
        "adjustment_balance": adj_bal, "revenue": revenue,
        "distortion": abs(stock) + abs(adj_bal),
        "healthy": abs(stock) < 50_000_000,
    }


@frappe.whitelist()
def vat_summary(company=None, from_date=None, to_date=None):
    """VAT — output (collected) vs input (recoverable) vs net payable.

    Output VAT lives on liability tax accounts (39x), input VAT on asset tax
    accounts (19x). Net payable = output − input.
    """
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    if not (from_date and to_date):
        from_date, to_date = _year_bounds()
    rows = frappe.db.sql(
        """SELECT a.name, a.account_name, a.root_type,
                  ROUND(SUM(gle.credit - gle.debit)) AS net
           FROM `tabGL Entry` gle JOIN `tabAccount` a ON a.name = gle.account
           WHERE gle.company=%s AND gle.is_cancelled=0 AND a.account_type='Tax'
             AND gle.posting_date BETWEEN %s AND %s
           GROUP BY a.name HAVING SUM(ABS(gle.debit)) + SUM(ABS(gle.credit)) > 0
           ORDER BY ABS(SUM(gle.credit - gle.debit)) DESC""",
        (target, from_date, to_date), as_dict=True)
    output, inp = [], []
    for r in rows:
        item = {"account": r.name, "name": r.account_name, "amount": flt(r.net)}
        # Liability-rooted tax accounts are output VAT; assets are input VAT.
        (output if (r.root_type == "Liability" or r.net > 0) else inp).append(item)
    output_total = sum(i["amount"] for i in output)
    input_total = sum(-i["amount"] for i in inp)  # input shows as debit (negative net)
    return {
        "from_date": from_date, "to_date": to_date, "company": target,
        "output": output, "input": inp,
        "output_total": output_total, "input_total": input_total,
        "net_payable": output_total - input_total,
    }


@frappe.whitelist()
def sales_collections_cohort(company=None, from_date=None, to_date=None):
    """Sales (invoiced) and collections (reconciled COD cash) grouped by the
    ORDER month — so revenue lines up with the month its ad spend was incurred,
    not the (later) invoice month. Verified 1 invoice = 1 order for this book, so
    each invoice is attributed whole to its order's transaction month."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    if not (from_date and to_date):
        from_date, to_date = _year_bounds()
    ck = f"ap_sales_cohort:{target}:{from_date}:{to_date}"
    cached = frappe.cache().get_value(ck)
    if cached is not None:
        return cached

    params = {"c": target, "fd": from_date, "td": to_date}
    so = frappe.db.sql(
        """SELECT DATE_FORMAT(so.transaction_date,'%%Y-%%m') m,
                  COUNT(*) orders,
                  ROUND(SUM(so.grand_total)) order_value,
                  ROUND(SUM(CASE WHEN IFNULL(so.custom_reference_number,'') LIKE 'CATH%%' THEN so.grand_total ELSE 0 END)) collected,
                  ROUND(SUM(CASE WHEN IFNULL(so.custom_reference_number,'') LIKE 'CATH%%'
                                  OR so.custom_track_shipment_status='Delivered' THEN so.grand_total ELSE 0 END)) delivered
           FROM `tabSales Order` so
           WHERE so.company=%(c)s AND so.docstatus=1
             AND so.transaction_date BETWEEN %(fd)s AND %(td)s
             AND IFNULL(so.custom_sales_status,'') NOT IN ('Cancelled','Duplicated','')
           GROUP BY m""", params, as_dict=True)
    # 1 invoice = 1 order; collapse items to the invoice first to avoid multiplying
    # the header net by the line count, then attribute to the order's month.
    inv = frappe.db.sql(
        """SELECT DATE_FORMAT(so.transaction_date,'%%Y-%%m') m, ROUND(SUM(x.net)) invoiced
           FROM (SELECT si.name, si.base_net_total net, MIN(sii.sales_order) so_name
                 FROM `tabSales Invoice` si JOIN `tabSales Invoice Item` sii ON sii.parent=si.name
                 WHERE si.company=%(c)s AND si.docstatus=1 GROUP BY si.name) x
           JOIN `tabSales Order` so ON so.name=x.so_name
           WHERE so.transaction_date BETWEEN %(fd)s AND %(td)s
           GROUP BY m""", params, as_dict=True)
    inv_by = {r.m: flt(r.invoiced) for r in inv}

    months = []
    for r in so:
        invoiced, collected, delivered = inv_by.get(r.m, 0.0), flt(r.collected), flt(r.delivered)
        months.append({
            "month": r.m, "orders": r.orders or 0, "order_value": flt(r.order_value),
            "invoiced": invoiced, "delivered": delivered, "collected": collected,
            "outstanding": round(delivered - collected),
            "collection_rate": round(collected / delivered * 100, 1) if delivered else 0,
        })
    months.sort(key=lambda x: x["month"])
    t = {k: round(sum(m[k] for m in months)) for k in ("orders", "invoiced", "delivered", "collected", "outstanding")}
    t["collection_rate"] = round(t["collected"] / t["delivered"] * 100, 1) if t["delivered"] else 0
    out = {"company": target, "from_date": from_date, "to_date": to_date, "months": months, "totals": t}
    frappe.cache().set_value(ck, out, expires_in_sec=180)
    return out
