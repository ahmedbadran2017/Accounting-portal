"""Multi-entity consolidation — roll the 4 companies up into one group view.

Each company keeps its own currency (MAD/USD/TRY); figures are translated to the
group reporting currency (USD, the Holding currency) at the latest Currency
Exchange rate. P&L is fiscal-year-to-date; balance-sheet figures are as-of.
Intercompany balances are surfaced (the TR/CN→MA sourcing flows) so the team can
see what would eliminate.
"""
import frappe
from frappe.utils import flt, getdate, nowdate

from accounting_portal.api.permissions import assert_portal_access, resolve_companies

GROUP_CCY = "USD"


def _fy_start():
    return getdate(nowdate()).replace(month=1, day=1).isoformat()


def _fx_to_usd(ccy):
    """Latest rate to translate `ccy` into USD. Prefers an explicit USD→ccy rate
    (inverted), then a direct ccy→USD rate; 1.0 as a last resort (flagged)."""
    if not ccy or ccy == "USD":
        return 1.0, True
    r = frappe.db.sql(
        """SELECT exchange_rate FROM `tabCurrency Exchange` WHERE from_currency='USD'
           AND to_currency=%s AND IFNULL(exchange_rate,0)>0 ORDER BY date DESC LIMIT 1""", (ccy,))
    if r and r[0][0]:
        return round(1.0 / flt(r[0][0]), 6), True
    r = frappe.db.sql(
        """SELECT exchange_rate FROM `tabCurrency Exchange` WHERE from_currency=%s
           AND to_currency='USD' AND IFNULL(exchange_rate,0)>0 ORDER BY date DESC LIMIT 1""", (ccy,))
    if r and r[0][0]:
        return round(flt(r[0][0]), 6), True
    return 1.0, False  # no rate found — translated at 1.0, flagged


def _company_figures(company, fy):
    """P&L (FY-to-date) + balance-sheet (as-of) in the company's own currency."""
    pl = frappe.db.sql(
        """SELECT
             ROUND(SUM(CASE WHEN a.root_type='Income'  THEN g.credit-g.debit ELSE 0 END)) income,
             ROUND(SUM(CASE WHEN a.root_type='Expense' THEN g.debit-g.credit ELSE 0 END)) expense
           FROM `tabGL Entry` g JOIN `tabAccount` a ON a.name=g.account
           WHERE g.company=%s AND g.is_cancelled=0 AND g.posting_date>=%s""", (company, fy), as_dict=True)[0]
    bs = frappe.db.sql(
        """SELECT
             ROUND(SUM(CASE WHEN a.root_type='Asset'     THEN g.debit-g.credit ELSE 0 END)) assets,
             ROUND(SUM(CASE WHEN a.root_type='Liability' THEN g.credit-g.debit ELSE 0 END)) liabilities,
             ROUND(SUM(CASE WHEN a.account_type IN ('Bank','Cash') THEN g.debit-g.credit ELSE 0 END)) cash
           FROM `tabGL Entry` g JOIN `tabAccount` a ON a.name=g.account
           WHERE g.company=%s AND g.is_cancelled=0""", (company,), as_dict=True)[0]
    inter = flt(frappe.db.sql(
        """SELECT ROUND(SUM(g.debit-g.credit)) FROM `tabGL Entry` g JOIN `tabAccount` a ON a.name=g.account
           WHERE g.company=%s AND g.is_cancelled=0
             AND (a.account_name LIKE '%%Internal%%' OR a.account_name LIKE '%%Intercompany%%'
                  OR a.account_name LIKE '%%Inter Company%%')""", (company,))[0][0] or 0)
    return {
        "income": flt(pl.income), "expense": flt(pl.expense), "net": flt(pl.income) - flt(pl.expense),
        "assets": flt(bs.assets), "liabilities": flt(bs.liabilities), "cash": flt(bs.cash),
        "intercompany": inter,
    }


@frappe.whitelist()
def consolidated_financials(base=None):
    """Group rollup: each entity translated to the reporting currency + the
    consolidated totals + the FX rates used."""
    assert_portal_access()
    base = base or GROUP_CCY
    companies = resolve_companies() or [c.name for c in frappe.get_all("Company", fields=["name"])]
    fy = _fy_start()
    rows, totals = [], {"income": 0, "expense": 0, "net": 0, "assets": 0, "liabilities": 0, "cash": 0, "intercompany": 0}
    rates, missing = {}, []
    for nm in companies:
        ccy = frappe.db.get_value("Company", nm, "default_currency") or "USD"
        rate, ok = _fx_to_usd(ccy)
        if not ok:
            missing.append(ccy)
        rates[ccy] = rate
        own = _company_figures(nm, fy)
        conv = {k: round(v * rate) for k, v in own.items()}
        for k in totals:
            totals[k] += conv[k]
        rows.append({
            "company": nm, "abbr": frappe.db.get_value("Company", nm, "abbr"),
            "currency": ccy, "rate": rate, "own": own, "base": conv,
        })
    rows.sort(key=lambda r: -abs(r["base"]["assets"]))
    for k in totals:
        totals[k] = round(totals[k])
    return {
        "base": base, "fy_start": fy, "as_of": nowdate(),
        "rows": rows, "totals": totals, "rates": rates,
        "rate_warnings": sorted(set(missing)),
        "entities": len(rows),
    }
