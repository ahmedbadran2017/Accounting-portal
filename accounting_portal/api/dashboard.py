"""Dashboard endpoints — live multi-company accounting KPIs.

Reads straight from ERPNext's GL Entry + Account tables. All queries filter
`is_cancelled = 0` (cancelled entries must never count) and scope to the
companies the user is allowed to see.

Balances use the accounting convention sum(debit - credit):
  • Asset / Expense accounts carry a debit (positive) balance
  • Liability / Income / Equity carry a credit (negative) balance
So Payables (a liability) are reported as a positive "amount owed" by negating.
"""
import frappe
from frappe.utils import flt, getdate, nowdate

from accounting_portal.api.permissions import assert_portal_access, allowed_companies


def _company_filter(companies):
    """Build a safe SQL IN-list for the given company names."""
    if not companies:
        return "1=0", []
    placeholders = ", ".join(["%s"] * len(companies))
    return f"gl.company IN ({placeholders})", list(companies)


@frappe.whitelist()
def get_overview():
    """Per-company snapshot: receivables, payables, cash & bank, and a
    fiscal-year-to-date P&L (income, expense, net).

    Returns:
        {
          "as_of": "2026-06-23",
          "companies": [
            {"company", "currency", "receivable", "payable",
             "cash_bank", "income_ytd", "expense_ytd", "net_ytd"},
            ...
          ],
          "totals": { ... summed across companies (note: mixed-currency) ... }
        }
    """
    assert_portal_access()
    companies = allowed_companies()
    if not companies:
        return {"as_of": nowdate(), "companies": [], "totals": {}}

    where, params = _company_filter(companies)
    fy_start = _fiscal_year_start()

    # Balance-sheet style figures (all-time, by account_type).
    bs = frappe.db.sql(
        f"""
        SELECT gl.company AS company, acc.account_type AS account_type,
               SUM(gl.debit - gl.credit) AS bal
        FROM `tabGL Entry` gl
        JOIN `tabAccount` acc ON acc.name = gl.account
        WHERE gl.is_cancelled = 0
          AND {where}
          AND acc.account_type IN ('Receivable', 'Payable', 'Cash', 'Bank')
        GROUP BY gl.company, acc.account_type
        """,
        params,
        as_dict=True,
    )

    # P&L figures, fiscal-year-to-date, by root_type.
    pl = frappe.db.sql(
        f"""
        SELECT gl.company AS company, acc.root_type AS root_type,
               SUM(gl.credit - gl.debit) AS amt
        FROM `tabGL Entry` gl
        JOIN `tabAccount` acc ON acc.name = gl.account
        WHERE gl.is_cancelled = 0
          AND {where}
          AND gl.posting_date >= %s
          AND acc.root_type IN ('Income', 'Expense')
        GROUP BY gl.company, acc.root_type
        """,
        params + [fy_start],
        as_dict=True,
    )

    by_company = {c: {
        "company": c,
        "currency": frappe.db.get_value("Company", c, "default_currency"),
        "receivable": 0.0, "payable": 0.0, "cash_bank": 0.0,
        "income_ytd": 0.0, "expense_ytd": 0.0, "net_ytd": 0.0,
    } for c in companies}

    for r in bs:
        row = by_company.get(r.company)
        if not row:
            continue
        bal = flt(r.bal)
        if r.account_type == "Receivable":
            row["receivable"] += bal
        elif r.account_type == "Payable":
            row["payable"] += -bal          # liability → report as positive owed
        elif r.account_type in ("Cash", "Bank"):
            row["cash_bank"] += bal

    for r in pl:
        row = by_company.get(r.company)
        if not row:
            continue
        amt = flt(r.amt)
        if r.root_type == "Income":
            row["income_ytd"] += amt        # credit-positive
        elif r.root_type == "Expense":
            row["expense_ytd"] += -amt       # expenses are debit-positive

    for row in by_company.values():
        row["net_ytd"] = row["income_ytd"] - row["expense_ytd"]

    companies_out = [by_company[c] for c in companies]
    totals = {
        "receivable": sum(r["receivable"] for r in companies_out),
        "payable": sum(r["payable"] for r in companies_out),
        "cash_bank": sum(r["cash_bank"] for r in companies_out),
        "income_ytd": sum(r["income_ytd"] for r in companies_out),
        "expense_ytd": sum(r["expense_ytd"] for r in companies_out),
        "net_ytd": sum(r["net_ytd"] for r in companies_out),
    }
    return {"as_of": nowdate(), "fy_start": fy_start,
            "companies": companies_out, "totals": totals}


@frappe.whitelist()
def get_recent_entries(limit=20, company=None):
    """Most recent GL entries across allowed companies (audit feed)."""
    assert_portal_access()
    companies = allowed_companies()
    if company:
        companies = [c for c in companies if c == company]
    if not companies:
        return []
    where, params = _company_filter(companies)
    limit = min(int(limit or 20), 100)
    rows = frappe.db.sql(
        f"""
        SELECT gl.posting_date, gl.company, gl.account, gl.voucher_type,
               gl.voucher_no, gl.debit, gl.credit, gl.party_type, gl.party,
               gl.remarks
        FROM `tabGL Entry` gl
        WHERE gl.is_cancelled = 0 AND {where}
        ORDER BY gl.posting_date DESC, gl.creation DESC
        LIMIT %s
        """,
        params + [limit],
        as_dict=True,
    )
    return rows


def _fiscal_year_start():
    """Start date of the fiscal year containing today. Falls back to Jan 1."""
    try:
        fy = frappe.db.sql(
            """SELECT year_start_date FROM `tabFiscal Year`
               WHERE %s BETWEEN year_start_date AND year_end_date
               ORDER BY year_start_date DESC LIMIT 1""",
            (nowdate(),),
        )
        if fy:
            return str(fy[0][0])
    except Exception:
        pass
    return f"{getdate(nowdate()).year}-01-01"
