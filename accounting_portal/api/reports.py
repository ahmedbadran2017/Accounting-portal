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
