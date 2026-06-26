"""Settings reference data — companies, currencies/FX, and tax templates — live
from ERPNext so the Settings screens stop showing hardcoded tables."""
import frappe

from accounting_portal.api.permissions import assert_portal_access


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
