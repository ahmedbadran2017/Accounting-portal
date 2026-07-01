"""Expense cockpit — separates cost-of-sales from operating expenses and buckets
every expense-account posting into a clear category (Payroll, Marketing, Rent &
Office, Freight & Logistics, Taxes, Financial…).

Justyol books *everything* (inventory purchases, salaries, rent, ads, freight)
into flat expense accounts via Purchase Invoices/JEs, so this reads the GL by
account, classifies each account by its number prefix + name keywords, and rolls
up by category. Read-only, entity-scoped, cached. The classification map is a
plain constant here (Phase 1); making it user-editable is a later phase.
"""
import frappe
from frappe.utils import flt

from accounting_portal.api.permissions import assert_portal_access, resolve_companies


def _target(company):
    companies = resolve_companies(company)
    if not companies:
        return None
    return company if (company and company in companies) else companies[0]


# (category, group, color, number-prefixes, name-keywords). First match wins, so
# order matters — e.g. Taxes before Rent so "Tax Office …" isn't caught by "office".
_CATEGORIES = [
    ("COGS", "cost_of_sales", "#0f766e", ("71",),
     ("cost of goods", "stock", "correction need", "packaging")),
    ("Freight & Logistics", "cost_of_sales", "#0369a1", ("770.07", "770.04", "770.0.7"),
     ("freight", "cargo", "shipping", "sea ", "air freight", "customs", "clearance",
      "forwarding", "warehouse fee", "inspection", "logistic", "delivery cost", "shipment")),
    ("Payroll", "opex", "#7c3aed", ("72",),
     ("salary", "wage", "employee", "social security", "commission", "payroll",
      "bonus", "overtime", "leave encashment", "unemployment", "absence")),
    ("Marketing", "opex", "#db2777", ("76",),
     ("facebook", "instagram", "instigram", "marketing", "digital", "ads", "publicit")),
    ("Taxes", "opex", "#0891b2", ("770.09",), ("tax", "stopaj", "damga", "vat")),
    ("Financial", "opex", "#4f46e5", ("78",),
     ("bank charge", "exchange rate", "round off", "commission bancaire")),
    ("Rent, Office & Utilities", "opex", "#b45309", ("770.001", "770.01", "770.03", "770.08"),
     ("rent", "office", "warehouse", "maintenance", "internet", "orange", "electric",
      "janitor", "cleaning", "supplies", "utilit", "phone", "recruitment", "accountant")),
    ("Other", "opex", "#78716c", (), ()),
]
_GROUP = {c[0]: c[1] for c in _CATEGORIES}
_COLOR = {c[0]: c[2] for c in _CATEGORIES}
_ORDER = [c[0] for c in _CATEGORIES]


def _classify(num, name):
    n = (num or "").strip()
    s = (name or "").lower()
    for cat, _grp, _col, prefixes, keywords in _CATEGORIES:
        if cat == "Other":
            continue
        for p in prefixes:
            if n.startswith(p):
                return cat
        for k in keywords:
            if k in s:
                return cat
    return "Other"


@frappe.whitelist()
def expense_cockpit(company=None, from_date=None, to_date=None):
    """All expense-account activity, classified into categories and split into
    cost-of-sales vs operating expenses. Period-filtered."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    if not (from_date and to_date):
        from frappe.utils import add_days, nowdate
        from_date, to_date = add_days(nowdate(), -365), nowdate()
    currency = frappe.db.get_value("Company", target, "default_currency") or "MAD"
    ck = f"ap_expense_cockpit:{target}:{from_date}:{to_date}"
    cached = frappe.cache().get_value(ck)
    if cached is not None:
        return cached

    params = {"c": target, "fd": from_date, "td": to_date}
    rows = frappe.db.sql(
        """SELECT a.account_number num, a.account_name nm,
                  ROUND(SUM(g.debit - g.credit)) bal
           FROM `tabAccount` a JOIN `tabGL Entry` g ON g.account = a.name
           WHERE g.company = %(c)s AND g.is_cancelled = 0 AND a.root_type = 'Expense'
             AND g.posting_date BETWEEN %(fd)s AND %(td)s
           GROUP BY a.name HAVING ABS(SUM(g.debit - g.credit)) > 0""", params, as_dict=True)

    cats, by_account = {}, {}
    for r in rows:
        cat = _classify(r.num, r.nm)
        bal = flt(r.bal)
        cats[cat] = cats.get(cat, 0.0) + bal
        by_account.setdefault(cat, []).append({"num": r.num, "name": r.nm, "amount": bal})

    categories = []
    for cat in _ORDER:
        if cat in cats:
            categories.append({"cat": cat, "group": _GROUP[cat], "color": _COLOR[cat],
                               "amount": round(cats[cat]), "accounts": len(by_account.get(cat, []))})
    categories.sort(key=lambda x: -abs(x["amount"]))
    for cat in by_account:
        by_account[cat].sort(key=lambda x: -abs(x["amount"]))
        by_account[cat] = by_account[cat][:15]

    groups = {"cost_of_sales": round(sum(v for k, v in cats.items() if _GROUP[k] == "cost_of_sales")),
              "opex": round(sum(v for k, v in cats.items() if _GROUP[k] == "opex"))}

    # monthly trend by category
    mrows = frappe.db.sql(
        """SELECT DATE_FORMAT(g.posting_date, '%%Y-%%m') m, a.account_number num,
                  a.account_name nm, ROUND(SUM(g.debit - g.credit)) bal
           FROM `tabAccount` a JOIN `tabGL Entry` g ON g.account = a.name
           WHERE g.company = %(c)s AND g.is_cancelled = 0 AND a.root_type = 'Expense'
             AND g.posting_date BETWEEN %(fd)s AND %(td)s
           GROUP BY m, a.name""", params, as_dict=True)
    monthly = {}
    for r in mrows:
        cat = _classify(r.num, r.nm)
        mm = monthly.setdefault(r.m, {})
        mm[cat] = mm.get(cat, 0.0) + flt(r.bal)
    months = [{"m": m, **{k: round(v) for k, v in monthly[m].items()}} for m in sorted(monthly)][-12:]

    out = {
        "company": target, "currency": currency, "from_date": str(from_date), "to_date": str(to_date),
        "categories": categories, "groups": groups,
        "total": round(sum(cats.values())),
        "by_account": by_account, "months": months,
        "cat_order": _ORDER, "cat_color": _COLOR,
    }
    frappe.cache().set_value(ck, out, expires_in_sec=300)
    return out
