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
    frappe.cache().set_value(ck, out, expires_in_sec=600)
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


@frappe.whitelist()
def duplicate_source(company=None, source_type=None, source_name=None):
    """Read an existing bill / expense and return values to pre-fill the New-
    expense form — the portal's 'Duplicate', so a recurring vendor bill or a
    repeated cash expense is re-entered in one click (nothing is posted here)."""
    assert_portal_access()
    target = _target(company)
    if not (target and source_type and source_name):
        frappe.throw("source_type and source_name are required")
    if source_type == "Purchase Invoice":
        pi = frappe.db.get_value("Purchase Invoice", source_name,
                                 ["company", "supplier", "total_taxes_and_charges", "remarks"], as_dict=True)
        if not pi or pi.company != target:
            frappe.throw("Bill not in this company")
        item = frappe.db.sql(
            """SELECT expense_account, description, base_net_amount amt
               FROM `tabPurchase Invoice Item` WHERE parent=%s ORDER BY base_net_amount DESC LIMIT 1""",
            (source_name,), as_dict=True)
        net = frappe.db.get_value("Purchase Invoice", source_name, "base_net_total")
        tax = frappe.db.sql(
            """SELECT account_head, base_tax_amount FROM `tabPurchase Taxes and Charges`
               WHERE parent=%s AND base_tax_amount>0 ORDER BY base_tax_amount DESC LIMIT 1""",
            (source_name,), as_dict=True)
        return {"mode": "bill", "party": pi.supplier,
                "expense_account": item[0].expense_account if item else None,
                "amount": flt(net) or (flt(item[0].amt) if item else 0),
                "tax_amount": flt(tax[0].base_tax_amount) if tax else 0,
                "tax_account": tax[0].account_head if tax else None,
                "description": (item[0].description if item else None) or pi.remarks}
    if source_type == "Journal Entry":
        je = frappe.db.get_value("Journal Entry", source_name, ["company", "user_remark"], as_dict=True)
        if not je or je.company != target:
            frappe.throw("Entry not in this company")
        rows = frappe.db.sql(
            """SELECT jea.account, jea.debit, jea.credit, a.root_type, a.account_type
               FROM `tabJournal Entry Account` jea JOIN `tabAccount` a ON a.name=jea.account
               WHERE jea.parent=%s""", (source_name,), as_dict=True)
        exp = next((r for r in rows if r.root_type == "Expense" and flt(r.debit) > 0), None)
        pay = next((r for r in rows if r.account_type in ("Bank", "Cash") and flt(r.credit) > 0), None)
        return {"mode": "cash", "expense_account": exp.account if exp else None,
                "amount": flt(exp.debit) if exp else 0,
                "pay_account": pay.account if pay else None,
                "description": je.user_remark}
    frappe.throw(f"Cannot duplicate a {source_type}")


def _fx_rate(from_ccy, to_ccy, date):
    """Currency-exchange rate from_ccy → to_ccy on/just before `date` (1.0 if same
    currency). Tries the direct pair, then the inverse (1/rate)."""
    if not from_ccy or from_ccy == to_ccy:
        return 1.0
    r = frappe.db.sql(
        """SELECT exchange_rate FROM `tabCurrency Exchange`
           WHERE from_currency=%s AND to_currency=%s AND date<=%s
           ORDER BY date DESC LIMIT 1""", (from_ccy, to_ccy, date))
    if r and flt(r[0][0]):
        return flt(r[0][0])
    inv = frappe.db.sql(
        """SELECT exchange_rate FROM `tabCurrency Exchange`
           WHERE from_currency=%s AND to_currency=%s AND date<=%s
           ORDER BY date DESC LIMIT 1""", (to_ccy, from_ccy, date))
    if inv and flt(inv[0][0]):
        return round(1.0 / flt(inv[0][0]), 9)
    return 0.0


@frappe.whitelist()
def exchange_rate(company=None, from_currency=None, date=None):
    """FX rate from `from_currency` to the company's base currency on `date`.
    Feeds the expense form's rate field when a foreign-currency bill is entered."""
    assert_portal_access()
    target = _target(company)
    base = _ccy(target)
    return {"from": from_currency, "to": base,
            "rate": _fx_rate(from_currency, base, date or nowdate())}


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
        "SELECT name FROM `tabSupplier` WHERE disabled=0 ORDER BY name LIMIT 1000", as_dict=True)]
    # Input-VAT (recoverable) accounts — TVA in Morocco / İndirilecek KDV in Maslak
    # live under 191.x: Tax-type on the ASSET side (391.x is the output side).
    import re as _re
    vat = frappe.db.sql(
        """SELECT name, account_name nm, account_number num FROM `tabAccount`
           WHERE company=%s AND is_group=0 AND disabled=0
             AND account_type='Tax' AND root_type='Asset' ORDER BY name""", (target,), as_dict=True)
    for v in vat:
        m = _re.search(r"%\s*(\d+)", v.nm or "")
        v["pct"] = int(m.group(1)) if m else None
    # currencies the team actually transacts in — base first, then the ones seen
    # on accounts, then the usual foreign ones.
    seen = [r[0] for r in frappe.db.sql(
        "SELECT DISTINCT account_currency FROM `tabAccount` WHERE company=%s AND account_currency IS NOT NULL AND account_currency != ''", (target,))]
    base = _ccy(target)
    currencies = [base] + [c for c in (seen + ["USD", "EUR", "TRY", "MAD"]) if c and c != base]
    currencies = list(dict.fromkeys(currencies))  # dedupe, keep order
    return {
        "company": target, "currency": base, "currencies": currencies,
        "expense_accounts": _expense_accounts(target),
        "pay_accounts": pay, "suppliers": suppliers, "vat_accounts": vat,
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
    if p.get("attachment"):
        # The bill's scan was uploaded to the portal's private files — pin it to the JE.
        frappe.get_doc({"doctype": "File", "file_url": p["attachment"],
                        "file_name": p.get("attachment_name") or p["attachment"].rsplit("/", 1)[-1],
                        "attached_to_doctype": "Journal Entry", "attached_to_name": je.name,
                        "is_private": 1}).insert(ignore_permissions=True)
    return {"voucher_type": "Journal Entry", "voucher_no": je.name, "result": "expense submitted"}


@frappe.whitelist()
def create_expense(company=None, expense_account=None, amount=None, posting_date=None,
                   pay_account=None, party=None, description=None, dry_run=0,
                   tax_amount=0, tax_account=None, attachment=None, attachment_name=None,
                   currency=None, exchange_rate=None):
    """Record an operating expense as a balanced Journal Entry (Dr expense account,
    Cr the bank/cash/payable it's paid from). Goes through the write gateway →
    audited, idempotent, gated for material amounts, and reversible (cancels the JE).

    VAT-bearing bills (TVA Morocco / KDV Maslak): `amount` is the NET expense and
    `tax_amount` posts as a second debit on the input-VAT asset account (191.x) —
    Dr expense net / Dr VAT / Cr pay gross, so the recoverable tax never inflates
    the expense and offsets output VAT at return time. `attachment` (a portal
    file_url) is attached to the Journal Entry when it posts."""
    assert_can_write()
    target = _target(company)
    amt = _m(amount)
    tax = _m(tax_amount)
    if not (target and expense_account and pay_account):
        frappe.throw("company, expense_account and pay_account are required")
    if amt <= 0:
        frappe.throw("Amount must be greater than zero")
    if tax < 0:
        frappe.throw("Tax cannot be negative")
    if tax > 0 and not tax_account:
        frappe.throw("Pick the input-VAT account for the tax portion")
    check = [expense_account, pay_account] + ([tax_account] if tax > 0 else [])
    for a in check:
        if not frappe.db.exists("Account", {"name": a, "company": target, "is_group": 0}):
            frappe.throw(f"Account not found in {target}: {a}")
    pd = posting_date or nowdate()
    pay_type = frappe.db.get_value("Account", pay_account, "account_type")
    party = party or None
    party_type = "Supplier" if (party and pay_type == "Payable") else None
    # Foreign-currency cash expense: convert to base so the JE (and the gate) are
    # in the company's currency. amount/tax entered in `currency`.
    base = _ccy(target)
    ccy = (currency or base).strip()
    rate = flt(exchange_rate) if exchange_rate not in (None, "") else _fx_rate(ccy, base, str(pd)[:10])
    if ccy != base and rate <= 0:
        frappe.throw(f"No exchange rate for {ccy}→{base} on {pd} — enter one")
    rate = 1.0 if ccy == base else rate
    amt_b = round(amt * rate, 2)
    tax_b = round(tax * rate, 2)
    gross = round(amt_b + tax_b, 2)
    lines = [{"account": expense_account, "debit": amt_b, "credit": 0}]
    if tax > 0:
        lines.append({"account": tax_account, "debit": tax_b, "credit": 0})
    lines.append({"account": pay_account, "debit": 0, "credit": gross,
                  "party_type": party_type, "party": party if party_type else None})
    if int(dry_run or 0):
        return {"preview": True, "lines": lines, "amount": gross, "posting_date": str(pd),
                "gated": gross >= _actions.MATERIAL_THRESHOLD}
    key = "expense:" + frappe.generate_hash(
        f"{target}|{expense_account}|{pay_account}|{amt}|{tax}|{ccy}|{pd}|{description or ''}|{party or ''}", 14)
    remark = (description or "Operating expense") + (f" ({amt + tax:,.0f} {ccy} @ {rate})" if ccy != base else "")
    return _actions.execute(
        EXPENSE_ACTION, target, key,
        payload={"posting_date": str(pd), "remark": remark, "lines": lines,
                 "attachment": attachment or None, "attachment_name": attachment_name or None},
        amount=gross, notes=description or "Operating expense")


BILL_ACTION = "Record supplier bill"


@frappe.whitelist()
def create_supplier_bill(company=None, supplier=None, expense_account=None, amount=None,
                         posting_date=None, bill_no=None, description=None,
                         tax_amount=0, tax_account=None, paid_from=None,
                         attachment=None, attachment_name=None,
                         currency=None, exchange_rate=None):
    """A recurring vendor's expense bill (Meta / TikTok ads, freight, clearance…)
    recorded as a real Purchase Invoice — supplier ledger, AP aging, statements
    and partial payments all work, unlike a bare journal. Service line (no stock
    item) debits the expense account; VAT debits the 191.x input account.
    `paid_from` (a Bank/Cash account) marks it paid immediately; empty = it lands
    in Purchases → To Pay. Gated, audited, revert = cancel the invoice."""
    assert_can_write()
    target = _target(company)
    amt = _m(amount)
    tax = _m(tax_amount)
    if not (target and supplier and expense_account):
        frappe.throw("company, supplier and expense_account are required")
    if amt <= 0:
        frappe.throw("Amount must be greater than zero")
    if tax > 0 and not tax_account:
        frappe.throw("Pick the input-VAT account for the tax portion")
    if not frappe.db.exists("Supplier", supplier):
        frappe.throw(f"Supplier not found: {supplier}")
    for a in [expense_account] + ([tax_account] if tax > 0 else []) + ([paid_from] if paid_from else []):
        if not frappe.db.exists("Account", {"name": a, "company": target, "is_group": 0}):
            frappe.throw(f"Account not found in {target}: {a}")
    if paid_from and frappe.db.get_value("Account", paid_from, "account_type") not in ("Bank", "Cash"):
        frappe.throw("paid_from must be a Bank or Cash account")
    pd = str(posting_date or nowdate())[:10]
    # Multi-currency: amount/tax are in `currency`; rate converts to base for the
    # GL and the materiality gate. Default currency = base (rate 1).
    base = _ccy(target)
    ccy = (currency or base).strip()
    rate = flt(exchange_rate) if exchange_rate not in (None, "") else _fx_rate(ccy, base, pd)
    if ccy != base and rate <= 0:
        frappe.throw(f"No exchange rate for {ccy}→{base} on {pd} — enter one")
    if ccy == base:
        rate = 1.0
    gross = round(amt + tax, 2)           # in the bill currency
    gross_base = round(gross * rate, 2)   # what hits the books / the gate
    key = "suppbill:" + frappe.generate_hash(
        f"{target}|{supplier}|{expense_account}|{amt}|{tax}|{ccy}|{pd}|{bill_no or ''}", 14)
    return _actions.execute(
        BILL_ACTION, target, key,
        payload={"supplier": supplier, "expense_account": expense_account, "net": amt,
                 "tax": tax, "tax_account": tax_account, "posting_date": pd,
                 "bill_no": bill_no or None, "description": description or None,
                 "paid_from": paid_from or None, "currency": ccy, "rate": rate,
                 "attachment": attachment or None, "attachment_name": attachment_name or None},
        amount=gross_base,
        notes=(description or f"Supplier bill — {supplier}") + (f" · {bill_no}" if bill_no else "")
              + (f" · {gross:,.0f} {ccy}" if ccy != base else ""))


def _bill_poster(action):
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    pi = frappe.new_doc("Purchase Invoice")
    pi.company = action.company
    pi.supplier = p["supplier"]
    pi.posting_date = p["posting_date"]
    pi.set_posting_time = 1
    base = frappe.get_cached_value("Company", action.company, "default_currency")
    ccy = p.get("currency") or base
    if ccy and ccy != base:
        pi.currency = ccy
        pi.conversion_rate = flt(p.get("rate")) or 1.0
    if p.get("bill_no"):
        pi.bill_no = p["bill_no"]
        pi.bill_date = p["posting_date"]
    pi.append("items", {
        "item_name": (p.get("description") or p["expense_account"].split(" - ")[-2 if " - " in p["expense_account"] else 0])[:140],
        "description": p.get("description") or "Expense bill via Accounting Portal",
        "qty": 1, "rate": flt(p["net"]),
        "expense_account": p["expense_account"],
        "cost_center": frappe.get_cached_value("Company", action.company, "cost_center"),
    })
    if flt(p.get("tax")) > 0:
        pi.append("taxes", {"charge_type": "Actual", "add_deduct_tax": "Add", "category": "Total",
                            "account_head": p["tax_account"], "tax_amount": flt(p["tax"]),
                            "description": "Input VAT"})
    if p.get("paid_from"):
        pi.is_paid = 1
        pi.cash_bank_account = p["paid_from"]
        pi.paid_amount = round(flt(p["net"]) + flt(p.get("tax")), 2)
    pi.insert(ignore_permissions=True)
    pi.submit()
    if p.get("attachment"):
        frappe.get_doc({"doctype": "File", "file_url": p["attachment"],
                        "file_name": p.get("attachment_name") or p["attachment"].rsplit("/", 1)[-1],
                        "attached_to_doctype": "Purchase Invoice", "attached_to_name": pi.name,
                        "is_private": 1}).insert(ignore_permissions=True)
    return {"voucher_type": "Purchase Invoice", "voucher_no": pi.name,
            "result": f"{p['supplier']} · {pi.grand_total}"}


def _register():
    _actions.register_poster(EXPENSE_ACTION, _expense_poster)
    _actions.register_reverter(EXPENSE_ACTION, _actions._cancel_voucher_reverter)
    _actions.register_poster(BILL_ACTION, _bill_poster)
    _actions.register_reverter(BILL_ACTION, _actions._cancel_voucher_reverter)


_register()
