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
