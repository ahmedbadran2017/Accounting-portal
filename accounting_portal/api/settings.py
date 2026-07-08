"""Settings reference data — companies, currencies/FX, and tax templates — live
from ERPNext so the Settings screens stop showing hardcoded tables."""
import frappe
from frappe.utils import flt, nowdate

from accounting_portal.api.permissions import (
    assert_can_write, assert_portal_access, can_manage_users,
)


def _assert_admin():
    if not (can_manage_users() or "Accounting Admin" in frappe.get_roles()):
        frappe.throw("Only an admin can do this", frappe.PermissionError)


@frappe.whitelist()
def settings_reference():
    """Live reference data for the Settings screens."""
    assert_portal_access()
    companies = frappe.db.sql(
        """SELECT name, abbr, default_currency AS ccy, country FROM `tabCompany` ORDER BY name""",
        as_dict=True)
    # Latest exchange rate per currency pair.
    fx = frappe.db.sql(
        """SELECT ce.from_currency AS frm, ce.to_currency AS too, ce.exchange_rate AS rate, ce.date
           FROM `tabCurrency Exchange` ce
           JOIN (SELECT from_currency, to_currency, MAX(date) d FROM `tabCurrency Exchange`
                 GROUP BY from_currency, to_currency) m
             ON m.from_currency=ce.from_currency AND m.to_currency=ce.to_currency AND m.d=ce.date
           ORDER BY ce.from_currency, ce.to_currency""", as_dict=True)
    taxes = frappe.db.sql(
        """SELECT t.name, t.company, MAX(td.rate) AS rate
           FROM `tabSales Taxes and Charges Template` t
           JOIN `tabSales Taxes and Charges` td ON td.parent=t.name
           GROUP BY t.name ORDER BY MAX(td.rate) DESC""", as_dict=True)
    return {"companies": companies, "fx": fx, "taxes": taxes}


@frappe.whitelist()
def set_exchange_rate(from_currency=None, to_currency=None, rate=None, date=None):
    """Create or update a Currency Exchange rate so FX can be maintained from the
    portal. Frappe auto-fetches the rate for a posting date, so this is what drives
    multi-currency postings. Upserts the (pair, date) record."""
    assert_can_write()
    if not (from_currency and to_currency and rate):
        frappe.throw("From, to and rate are required")
    if from_currency == to_currency:
        frappe.throw("Currencies must differ")
    date = date or nowdate()
    name = frappe.db.get_value(
        "Currency Exchange",
        {"from_currency": from_currency, "to_currency": to_currency, "date": date}, "name")
    if name:
        ce = frappe.get_doc("Currency Exchange", name)
        ce.exchange_rate = flt(rate)
        ce.save(ignore_permissions=True)
    else:
        ce = frappe.get_doc({
            "doctype": "Currency Exchange", "from_currency": from_currency,
            "to_currency": to_currency, "date": date, "exchange_rate": flt(rate),
            "for_buying": 1, "for_selling": 1,
        })
        ce.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"name": ce.name, "from_currency": from_currency, "to_currency": to_currency,
            "rate": flt(rate), "date": str(date)}


# Far-past sentinel meaning "not locked". ERPNext's check_freezing_date crashes on
# a NULL/empty acc_frozen_upto, so we never clear it — we set it to this instead.
_UNLOCK = "1900-01-01"


@frappe.whitelist()
def get_period_lock():
    """The current global posting-lock date (Accounts Frozen Upto). Returns null
    when effectively unlocked (the sentinel or earlier)."""
    assert_portal_access()
    d = frappe.db.get_single_value("Accounts Settings", "acc_frozen_upto")
    locked = d and str(d) > _UNLOCK
    return {"acc_frozen_upto": str(d) if locked else None}


@frappe.whitelist()
def set_period_lock(date=None):
    """Lock the books up to a date (Accounts Settings.acc_frozen_upto) so no one can
    post or edit entries on/before it. Global across all companies — admin only.
    Pass an empty date to UNLOCK (sets the far-past sentinel, never NULL)."""
    _assert_admin()
    frappe.db.set_single_value("Accounts Settings", "acc_frozen_upto", date or _UNLOCK)
    frappe.db.commit()
    d = frappe.db.get_single_value("Accounts Settings", "acc_frozen_upto")
    locked = d and str(d) > _UNLOCK
    return {"acc_frozen_upto": str(d) if locked else None}


@frappe.whitelist()
def fiscal_years_for_close(company=None):
    """Fiscal years + whether each already has a Period Closing Voucher for this
    company (so the UI shows what's still open to close)."""
    assert_portal_access()
    from accounting_portal.api.permissions import resolve_companies
    comps = resolve_companies(company)
    target = company if (company and company in comps) else (comps[0] if comps else None)
    rows = frappe.db.sql(
        """SELECT name, year_start_date sd, year_end_date ed FROM `tabFiscal Year`
           WHERE disabled=0 ORDER BY year_start_date DESC LIMIT 8""", as_dict=True)
    for r in rows:
        r["sd"], r["ed"] = str(r["sd"]), str(r["ed"])
        r["closed"] = bool(frappe.db.exists("Period Closing Voucher",
                       {"company": target, "fiscal_year": r["name"], "docstatus": 1}))
    return {"company": target, "years": rows}


@frappe.whitelist()
def close_fiscal_year(company=None, fiscal_year=None, closing_account=None):
    """Year-end close: post a Period Closing Voucher that rolls the year's P&L
    (income - expense) into the closing/retained-earnings equity account, zeroing
    income & expense for the new year. Admin only; audited; reversible (cancel the
    PCV)."""
    _assert_admin()
    from accounting_portal.api.permissions import resolve_companies
    from accounting_portal.api import _actions
    comps = resolve_companies(company)
    target = company if (company and company in comps) else (comps[0] if comps else None)
    if not (target and fiscal_year):
        frappe.throw("company and fiscal_year are required")
    if not frappe.db.exists("Fiscal Year", fiscal_year):
        frappe.throw("Unknown fiscal year")
    if frappe.db.exists("Period Closing Voucher", {"company": target, "fiscal_year": fiscal_year, "docstatus": 1}):
        frappe.throw(f"{fiscal_year} is already closed for {target}")
    acct = closing_account or frappe.db.get_value(
        "Account", {"company": target, "root_type": "Equity",
                    "account_name": ["like", "%Retained Earnings%"], "is_group": 0}, "name")
    if not acct:
        frappe.throw("Pick the closing (retained earnings) equity account")
    ye = frappe.db.get_value("Fiscal Year", fiscal_year, "year_end_date")
    return _actions.execute(
        "Close fiscal year", target, f"yearclose:{target}:{fiscal_year}",
        payload={"fiscal_year": fiscal_year, "closing_account": acct, "posting_date": str(ye)},
        amount=0, notes=f"Year-end close {fiscal_year}")


def _year_close_poster(action):
    import json
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    pcv = frappe.get_doc({
        "doctype": "Period Closing Voucher", "company": action.company,
        "fiscal_year": p["fiscal_year"], "posting_date": p["posting_date"],
        "closing_account_head": p["closing_account"],
        "remarks": f"Year-end close via Accounting Portal ({p['fiscal_year']})",
    })
    pcv.insert(ignore_permissions=True)
    pcv.submit()
    return {"voucher_type": "Period Closing Voucher", "voucher_no": pcv.name, "result": "closed"}


from accounting_portal.api import _actions as _acts  # noqa: E402
_acts.register_poster("Close fiscal year", _year_close_poster)
_acts.register_reverter("Close fiscal year", _acts._cancel_voucher_reverter)
_acts._NO_GATE.add("Close fiscal year")
