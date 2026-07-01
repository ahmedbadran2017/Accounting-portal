"""Expense cockpit — separates cost-of-sales from operating expenses and buckets
every expense-account posting into a clear category (Payroll, Marketing, Rent &
Office, Freight & Logistics, Taxes, Financial…).

Justyol books *everything* (inventory purchases, salaries, rent, ads, freight)
into flat expense accounts via Purchase Invoices/JEs, so this reads the GL by
account, classifies each account by its number prefix + name keywords, and rolls
up by category. Read-only, entity-scoped, cached. The classification map is a
plain constant here (Phase 1); making it user-editable is a later phase.
"""
import json

import frappe
from frappe.utils import flt, nowdate, add_days

from accounting_portal.api import _actions, _paginate
from accounting_portal.api.permissions import (
    assert_portal_access, assert_can_write, resolve_companies)

EXPENSE_ACTION = "Record expense"


def _target(company):
    companies = resolve_companies(company)
    if not companies:
        return None
    return company if (company and company in companies) else companies[0]


def _ccy(target):
    return frappe.db.get_value("Company", target, "default_currency") or "MAD"


def _m(v):
    return flt(v, 2)


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


# ─────────────────────────────────────────────────────────────────────────────
# Expense TRANSACTIONS — the filterable ledger accountants work from
# ─────────────────────────────────────────────────────────────────────────────

def _expense_accounts(target):
    """All leaf expense accounts for the company (name, number, name, category)."""
    rows = frappe.db.sql(
        """SELECT name, account_number num, account_name nm, account_currency ccy FROM `tabAccount`
           WHERE company=%s AND root_type='Expense' AND is_group=0 AND disabled=0
           ORDER BY account_number, account_name""",
        (target,), as_dict=True)
    for r in rows:
        r["category"] = _classify(r.num, r.nm)
    return rows


def _accounts_in_category(target, category):
    return [a["name"] for a in _expense_accounts(target) if a["category"] == category]


def _accounts_in_group(target, group):
    return [a["name"] for a in _expense_accounts(target) if _GROUP.get(a["category"]) == group]


@frappe.whitelist()
def expense_transactions(company=None, from_date=None, to_date=None, group="opex",
                         category=None, account=None, search=None, min_amount=None,
                         start=0, page_size=25):
    """Individual expense postings (one row per GL line on an expense account),
    filterable by period, group (opex / cost_of_sales / all), category, account,
    free text, and minimum amount. Defaults to operating expenses — the noise of
    auto COGS / round-off postings from invoices is excluded unless asked for."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {"rows": [], "total": 0}
    if not (from_date and to_date):
        from_date, to_date = add_days(nowdate(), -365), nowdate()
    conds = ["g.company=%(c)s", "g.is_cancelled=0", "a.root_type='Expense'",
             "g.posting_date BETWEEN %(fd)s AND %(td)s", "(g.debit-g.credit)!=0"]
    params = {"c": target, "fd": from_date, "td": to_date}
    empty = {"company": target, "currency": _ccy(target), "rows": [], "total": 0,
             "start": 0, "page_size": min(max(1, int(page_size or 25)), 100)}
    if account:
        conds.append("a.name=%(acct)s"); params["acct"] = account
    elif category and category != "all":
        accts = _accounts_in_category(target, category)
        if not accts:
            return empty
        conds.append("a.name IN %(accts)s"); params["accts"] = tuple(accts)
    elif group and group != "all":
        accts = _accounts_in_group(target, group)
        if not accts:
            return empty
        conds.append("a.name IN %(accts)s"); params["accts"] = tuple(accts)
        # Default operating-expense view: hide the auto cost/round-off postings that
        # invoices, delivery notes and stock entries generate — accountants manage
        # real opex (rent, marketing, office…) booked via Purchase Invoices / JEs.
        if group == "opex":
            conds.append("g.voucher_type NOT IN ('Sales Invoice','Delivery Note','Stock Entry','Purchase Receipt','POS Invoice')")
    if search:
        conds.append("(g.voucher_no LIKE %(s)s OR a.account_name LIKE %(s)s "
                     "OR IFNULL(g.remarks,'') LIKE %(s)s OR IFNULL(g.party,'') LIKE %(s)s)")
        params["s"] = f"%{search}%"
    if min_amount:
        conds.append("ABS(g.debit-g.credit) >= %(minamt)s"); params["minamt"] = flt(min_amount)

    rows, total, st, ps = _paginate.page_query(
        from_sql="`tabGL Entry` g JOIN `tabAccount` a ON a.name=g.account",
        where=" AND ".join(conds), params=params,
        fields="g.name id, g.posting_date, g.voucher_type, g.voucher_no, "
               "a.account_number num, a.account_name nm, g.party, g.remarks, "
               "(g.debit-g.credit) amount",
        order_by="g.posting_date DESC, g.creation DESC",
        start=start, page_size=page_size)
    for r in rows:
        r["posting_date"] = str(r["posting_date"] or "")[:10]
        r["amount"] = _m(r["amount"])
        r["category"] = _classify(r["num"], r["nm"])
        r["remarks"] = (r["remarks"] or "")[:120]
    return {"company": target, "currency": _ccy(target), "rows": rows,
            "total": total, "start": st, "page_size": ps}


# ─────────────────────────────────────────────────────────────────────────────
# CREATE expense — accountants record an operating expense without opening ERPNext
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def expense_form_options(company=None):
    """Everything the New-expense form needs: expense accounts (with category),
    pay-from accounts (bank / cash / payable), suppliers, and defaults."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    pay = frappe.db.sql(
        """SELECT name, account_name nm, IFNULL(account_type,'') typ, account_currency ccy
           FROM `tabAccount` WHERE company=%s AND is_group=0 AND disabled=0
             AND account_type IN ('Bank','Cash','Payable') ORDER BY account_type, name""",
        (target,), as_dict=True)
    suppliers = [r.name for r in frappe.db.sql(
        "SELECT name FROM `tabSupplier` WHERE disabled=0 ORDER BY name LIMIT 200", as_dict=True)]
    return {
        "company": target, "currency": _ccy(target),
        "expense_accounts": _expense_accounts(target),
        "pay_accounts": pay, "suppliers": suppliers,
        "default_pay": next((p.name for p in pay if p.typ == "Cash"),
                            next((p.name for p in pay if p.typ == "Bank"), pay[0].name if pay else None)),
        "categories": _ORDER, "cat_color": _COLOR,
        "threshold": _actions.MATERIAL_THRESHOLD,
    }


def _expense_poster(action):
    """Create + submit the expense Journal Entry (Dr expense, Cr pay account)."""
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    je = frappe.get_doc({
        "doctype": "Journal Entry",
        "company": action.company,
        "posting_date": p.get("posting_date") or nowdate(),
        "voucher_type": "Journal Entry",
        "multi_currency": 1,
        "user_remark": p.get("remark") or "Expense recorded via Accounting Portal",
        "accounts": [
            {
                "account": ln["account"],
                "debit_in_account_currency": flt(ln.get("debit")),
                "credit_in_account_currency": flt(ln.get("credit")),
                "party_type": ln.get("party_type") or None,
                "party": ln.get("party") or None,
            }
            for ln in (p.get("lines") or [])
        ],
    })
    je.insert(ignore_permissions=True)
    je.submit()
    return {"voucher_type": "Journal Entry", "voucher_no": je.name, "result": "expense submitted"}


@frappe.whitelist()
def create_expense(company=None, expense_account=None, amount=None, posting_date=None,
                   pay_account=None, party=None, description=None, dry_run=0):
    """Record an operating expense as a balanced Journal Entry (Dr expense account,
    Cr the bank/cash/payable it's paid from). Goes through the write gateway →
    audited, idempotent, gated for material amounts, and reversible (cancels the JE)."""
    assert_can_write()
    target = _target(company)
    amt = _m(amount)
    if not (target and expense_account and pay_account):
        frappe.throw("company, expense_account and pay_account are required")
    if amt <= 0:
        frappe.throw("Amount must be greater than zero")
    for a in (expense_account, pay_account):
        if not frappe.db.exists("Account", {"name": a, "company": target, "is_group": 0}):
            frappe.throw(f"Account not found in {target}: {a}")
    pd = posting_date or nowdate()
    pay_type = frappe.db.get_value("Account", pay_account, "account_type")
    party = party or None
    party_type = "Supplier" if (party and pay_type == "Payable") else None
    lines = [
        {"account": expense_account, "debit": amt, "credit": 0},
        {"account": pay_account, "debit": 0, "credit": amt,
         "party_type": party_type, "party": party if party_type else None},
    ]
    if int(dry_run or 0):
        return {"preview": True, "lines": lines, "amount": amt, "posting_date": str(pd),
                "gated": amt >= _actions.MATERIAL_THRESHOLD}
    key = "expense:" + frappe.generate_hash(
        f"{target}|{expense_account}|{pay_account}|{amt}|{pd}|{description or ''}|{party or ''}", 14)
    return _actions.execute(
        EXPENSE_ACTION, target, key,
        payload={"posting_date": str(pd), "remark": description or "Operating expense", "lines": lines},
        amount=amt, notes=description or "Operating expense")


def _register():
    _actions.register_poster(EXPENSE_ACTION, _expense_poster)
    _actions.register_reverter(EXPENSE_ACTION, _actions._cancel_voucher_reverter)


_register()
