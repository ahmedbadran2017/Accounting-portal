"""Investor statements — capital, drawings, and the cycle they financed.

Investors funded inventory through Maslak while the goods sell in Morocco, so
neither entity's own P&L answers "what did my money earn": Maslak's result is
mostly the gap between what it paid suppliers and the paper price it invoices
Morocco at. The cycle result is therefore read across the group.

Two design decisions worth stating, because they are what make the screen
trustworthy rather than merely pretty:

* The statement shows EVERY margin layer instead of one "profit" figure. Whether
  marketing sits inside the shared result changes the answer by more than the
  whole capital base, so the agreement points at a line and the screen shows
  which line was chosen — it never picks silently.
* Capital is carried in the currency it was actually agreed in. These deals were
  struck in USD and booked in TRY; with the lira moving, the booked balance and
  the obligation drift apart, and that drift is reported rather than hidden.

Nothing here posts. Terms live in a setting so the numbers can be produced
before any agreement is formalised — and the screen says so.
"""
import json

import frappe
from frappe.utils import flt, nowdate

from accounting_portal.api.permissions import assert_portal_access, can_manage_users

_TERMS_KEY = "ap_investor_terms"

# the layers, outermost first; each one is the previous minus its own costs
_LAYERS = [
    ("gross_margin", "Gross margin", "revenue - product cost"),
    ("cm1", "After delivery & COD", "less courier and collection fees"),
    ("cm2", "After marketing", "less advertising"),
    ("cm3", "After fulfilment", "less packaging and warehouse labour"),
    ("operating", "Operating result", "less rent, software, admin, depreciation"),
]


def _terms():
    try:
        return json.loads(frappe.db.get_default(_TERMS_KEY) or "{}") or {}
    except Exception:
        return {}


def _fx(ccy, date):
    """USD per one unit of `ccy` on `date`. Only used for the trading cycle;
    an investor's own movements carry their agreed-currency amount already."""
    if ccy == "USD":
        return 1.0
    r = frappe.db.sql(
        """SELECT exchange_rate FROM `tabCurrency Exchange`
           WHERE from_currency='USD' AND to_currency=%s AND date <= %s
           ORDER BY date DESC LIMIT 1""", (ccy, date))
    rate = flt(r[0][0]) if r else 0
    return (1.0 / rate) if rate else 0.0


def _accounts():
    """Investor capital accounts: the 400.x family, plus anything the terms name."""
    rows = frappe.db.sql(
        """SELECT name, company, account_name, account_currency FROM `tabAccount`
           WHERE is_group=0 AND account_number LIKE '400.%%'
             AND account_name NOT LIKE '%%PROFIT%%' AND account_name NOT LIKE '%%Profit%%'
           ORDER BY company, name""", as_dict=True)
    out = []
    for r in rows:
        n = frappe.db.sql(
            "SELECT COUNT(*) FROM `tabGL Entry` WHERE account=%s AND is_cancelled=0", (r.name,))[0][0]
        if n:
            out.append(r)
    return out


def _profit_account(capital_account):
    """The drawings/profit current account that pairs with a capital account.
    Matched on the investor's name rather than a number, because the numbering
    of the two families does not line up."""
    nm = (frappe.db.get_value("Account", capital_account, "account_name") or "").upper()
    key = nm.replace("AS INVESTOR", "").replace("INVESTOR", "").strip()
    if not key:
        return None
    comp = frappe.db.get_value("Account", capital_account, "company")
    for a in frappe.db.sql(
            """SELECT name, account_name FROM `tabAccount`
               WHERE company=%s AND is_group=0 AND name != %s AND root_type='Liability'
                 AND (account_name LIKE '%%PROFIT%%' OR account_name LIKE '%%Profit%%')""",
            (comp, capital_account), as_dict=True):
        if key[:12] in (a.account_name or "").upper():
            return a.name
    return None


@frappe.whitelist()
def investor_list():
    """Every investor with money in the group, newest movement first."""
    assert_portal_access()
    terms = _terms()
    out = []
    for a in _accounts():
        ccy = a.account_currency or frappe.db.get_value("Company", a.company, "default_currency")
        bal = flt(frappe.db.sql(
            """SELECT SUM(credit)-SUM(debit) FROM `tabGL Entry`
               WHERE account=%s AND is_cancelled=0""", (a.name,))[0][0])
        pa = _profit_account(a.name)
        drawn = flt(frappe.db.sql(
            """SELECT SUM(debit)-SUM(credit) FROM `tabGL Entry`
               WHERE account=%s AND is_cancelled=0""", (pa,))[0][0]) if pa else 0.0
        last = frappe.db.sql(
            "SELECT MAX(posting_date) FROM `tabGL Entry` WHERE account=%s AND is_cancelled=0", (a.name,))[0][0]
        t = terms.get(a.name) or {}
        out.append({
            "account": a.name, "company": a.company, "name": a.account_name,
            "currency": ccy, "capital": round(bal, 2), "drawn": round(drawn, 2),
            "profit_account": pa, "last_movement": str(last or "")[:10],
            "share_pct": t.get("share_pct"), "basis": t.get("basis"),
            "start": t.get("start"), "deal_currency": t.get("deal_currency"),
            "shares_losses": t.get("shares_losses"),
            "configured": bool(t.get("share_pct")),
        })
    out.sort(key=lambda r: -abs(r["capital"]))
    return {"investors": out, "layers": [{"key": k, "label": l, "hint": h} for k, l, h in _LAYERS]}


def _cycle(date_from, date_to):
    """The trading cycle across the group, layer by layer, in USD.

    Internal invoicing cancels when the entities are summed, so what remains is
    external revenue less what the group really paid third parties.
    """
    SALES, SRC = "Justyol Morocco", "Maslak LTD"
    mad = _fx("MAD", date_to) or 0.105
    try_ = _fx("TRY", date_to) or 0.021

    def gl(company, like, rate, credit_side=False):
        col = "SUM(credit)-SUM(debit)" if credit_side else "SUM(debit)-SUM(credit)"
        v = flt(frappe.db.sql(
            f"""SELECT {col} FROM `tabGL Entry`
                WHERE company=%s AND is_cancelled=0 AND account LIKE %s
                  AND posting_date BETWEEN %s AND %s""",
            (company, like, date_from, date_to))[0][0])
        return v * rate

    # revenue: Morocco's external sales (Maslak sells only to Morocco)
    revenue = gl(SALES, "600.%", mad, credit_side=True)
    # product cost from the stock ledger, not the COGS accounts: those carry the
    # correction entries, which would net the cost away to nothing
    def stock_out(company, rate):
        out = flt(frappe.db.sql(
            """SELECT -SUM(stock_value_difference) FROM `tabStock Ledger Entry`
               WHERE company=%s AND is_cancelled=0 AND voucher_type='Delivery Note'
                 AND actual_qty < 0 AND posting_date BETWEEN %s AND %s""",
            (company, date_from, date_to))[0][0])
        back = flt(frappe.db.sql(
            """SELECT SUM(stock_value_difference) FROM `tabStock Ledger Entry`
               WHERE company=%s AND is_cancelled=0 AND voucher_type='Delivery Note'
                 AND actual_qty > 0 AND posting_date BETWEEN %s AND %s""",
            (company, date_from, date_to))[0][0])
        return (out - back) * rate

    product = stock_out(SALES, mad)
    # the sourcing entity's shortfall IS the rest of the true product cost: what
    # it paid suppliers beyond the paper price it charged Morocco
    src_exp = gl(SRC, "7%", try_)
    src_internal = gl(SRC, "600.801%", try_, credit_side=True)
    src_gap = max(src_exp - src_internal, 0)

    courier = gl(SALES, "770.07.004%", mad)
    ads = gl(SALES, "760.%", mad) + gl(SRC, "760.%", try_)
    fulfil = gl(SALES, "71.005%", mad)
    payroll = gl(SALES, "720.%", mad) + gl(SRC, "720.%", try_)
    rent = gl(SALES, "770.001%", mad) + gl(SRC, "770.001%", try_)
    soft = gl(SALES, "770.012%", mad) + gl(SRC, "770.012%", try_)

    gm = revenue - product - src_gap
    cm1 = gm - courier
    cm2 = cm1 - ads
    cm3 = cm2 - fulfil
    op = cm3 - payroll - rent - soft
    return {
        "from": date_from, "to": date_to, "currency": "USD",
        "revenue": round(revenue), "product_cost": round(product + src_gap),
        "courier": round(courier), "marketing": round(ads), "fulfilment": round(fulfil),
        "payroll": round(payroll), "rent": round(rent), "software": round(soft),
        "gross_margin": round(gm), "cm1": round(cm1), "cm2": round(cm2),
        "cm3": round(cm3), "operating": round(op),
        "gm_pct": round(100.0 * gm / revenue, 1) if revenue else None,
        "rates": {"MAD": round(mad, 5), "TRY": round(try_, 5)},
    }


def _quality_flags():
    """What is known to be wrong with the inputs, and which way it pushes the
    result — so a provisional number is never mistaken for a settled one."""
    SALES = "Justyol Morocco"
    y0 = f"{nowdate()[:4]}-01-01"
    out = []
    z = frappe.db.sql(
        """SELECT COUNT(*) FROM `tabStock Ledger Entry`
           WHERE company=%s AND is_cancelled=0 AND voucher_type='Delivery Note'
             AND actual_qty<0 AND IFNULL(stock_value_difference,0)=0
             AND posting_date >= %s""", (SALES, y0))[0][0]
    if z:
        out.append({"issue": f"{z:,} sale lines shipped at zero cost",
                    "effect": "profit overstated", "severity": "high"})
    grni = flt(frappe.db.sql(
        """SELECT SUM(credit)-SUM(debit) FROM `tabGL Entry`
           WHERE company=%s AND account LIKE '321.01%%' AND is_cancelled=0""", (SALES,))[0][0])
    if abs(grni) > 250_000:
        out.append({"issue": f"{grni:,.0f} MAD received but not billed",
                    "effect": "cost understated", "severity": "medium"})
    try:
        from accounting_portal.api.auditor import _missing_recurring
        for f in _missing_recurring(SALES, "MAD"):
            out.append({"issue": f["title"], "effect": "cost understated" if "no bill" in f["title"]
                        else "cost in the wrong month", "severity": f["severity"]})
    except Exception:
        pass
    return out


@frappe.whitelist()
def investor_statement(account=None, date_from=None, date_to=None):
    """One investor: what they put in, what they took out, and the cycle result
    their money financed — with the share computed only if terms are set."""
    assert_portal_access()
    if not account:
        frappe.throw("account required")
    acc = frappe.db.get_value("Account", account,
                              ["account_name", "company", "account_currency"], as_dict=True)
    if not acc:
        frappe.throw("Unknown account")
    ccy = acc.account_currency or frappe.db.get_value("Company", acc.company, "default_currency")
    t = _terms().get(account) or {}
    deal_ccy = t.get("deal_currency") or "USD"
    date_from = date_from or t.get("start") or f"{nowdate()[:4]}-01-01"
    date_to = date_to or nowdate()

    # When the account is held in the currency the deal was struck in, ERPNext
    # already stores that amount per line — read it rather than reconstructing it
    # from a rate table, which is both wrong at the edges and unnecessary.
    foreign = ccy != frappe.db.get_value("Company", acc.company, "default_currency")
    moves = []
    for r in frappe.db.sql(
            """SELECT posting_date, voucher_type, voucher_no, debit, credit,
                      debit_in_account_currency dac, credit_in_account_currency cac, remarks
               FROM `tabGL Entry` WHERE account=%s AND is_cancelled=0
               ORDER BY posting_date, creation""", (account,), as_dict=True):
        base = flt(r.credit) - flt(r.debit)           # credit = money in
        deal = (flt(r.cac) - flt(r.dac)) if foreign else base
        rate = (base / deal) if deal else None        # base units per deal unit
        moves.append({"date": str(r.posting_date)[:10], "voucher": r.voucher_no,
                      "local": round(base, 2), "rate": round(rate, 4) if rate else None,
                      "deal": round(deal, 2), "note": (r.remarks or "")[:120]})
    cap_local = sum(m["local"] for m in moves)
    cap_deal = sum(m["deal"] or 0 for m in moves)

    pa = _profit_account(account)
    draws = []
    if pa:
        pf = frappe.db.get_value("Account", pa, "account_currency") != \
            frappe.db.get_value("Company", acc.company, "default_currency")
        for r in frappe.db.sql(
                """SELECT posting_date, voucher_no, debit, credit,
                          debit_in_account_currency dac, credit_in_account_currency cac
                   FROM `tabGL Entry` WHERE account=%s AND is_cancelled=0
                   ORDER BY posting_date, creation""", (pa,), as_dict=True):
            base = flt(r.debit) - flt(r.credit)       # debit = drawn out
            deal = (flt(r.dac) - flt(r.cac)) if pf else base
            draws.append({"date": str(r.posting_date)[:10], "voucher": r.voucher_no,
                          "local": round(base, 2), "deal": round(deal, 2)})
    drawn_local = sum(d["local"] for d in draws)
    drawn_deal = sum(d["deal"] or 0 for d in draws)

    # The obligation itself is clear — it is recorded in its own currency. What
    # drifts is the base-currency carrying value, because nobody has run an
    # exchange-rate revaluation since the contributions were made. Report that
    # drift as what it is: an unrecorded FX movement, in base currency.
    base_rate = 1.0 / _fx(ccy, date_to) if _fx(ccy, date_to) else None   # base per deal unit
    owed_in_base = cap_deal * base_rate if base_rate else None
    fx_gap = (owed_in_base - cap_local) if owed_in_base is not None else None

    cyc = _cycle(date_from, date_to)
    share = None
    if t.get("share_pct") and t.get("basis") in dict((k, l) for k, l, _ in _LAYERS):
        base = flt(cyc.get(t["basis"]))
        if base < 0 and not t.get("shares_losses"):
            share = {"basis_value": base, "amount": 0,
                     "note": "the cycle is negative and the terms do not share losses"}
        else:
            share = {"basis_value": base, "amount": round(base * flt(t["share_pct"]) / 100.0)}
    return {
        "account": account, "name": acc.account_name, "company": acc.company,
        "currency": ccy, "deal_currency": deal_ccy,
        "capital_local": round(cap_local, 2), "capital_deal": round(cap_deal, 2),
        "owed_in_base": round(owed_in_base, 2) if owed_in_base is not None else None,
        "fx_gap": round(fx_gap, 2) if fx_gap is not None else None,
        "fx_gap_note": ("carrying value in the books vs the same obligation at today's rate — "
                        "an exchange-rate revaluation that has not been run"),
        "drawn_local": round(drawn_local, 2), "drawn_deal": round(drawn_deal, 2),
        "moves": moves, "draws": draws, "profit_account": pa,
        "terms": t, "cycle": cyc, "share": share,
        "layers": [{"key": k, "label": l, "hint": h, "value": cyc.get(k)} for k, l, h in _LAYERS],
        "quality": _quality_flags(),
        "provisional": True,
    }


@frappe.whitelist()
def set_investor_terms(account=None, share_pct=None, basis=None, start=None,
                       deal_currency=None, shares_losses=None):
    """Record what was agreed. Restricted, and deliberately explicit about loss
    sharing — silence on that point is where these arrangements go wrong."""
    if not can_manage_users():
        frappe.throw("Restricted to the Super Admin", frappe.PermissionError)
    if not account:
        frappe.throw("account required")
    valid = [k for k, _, _ in _LAYERS]
    if basis and basis not in valid:
        frappe.throw(f"basis must be one of: {', '.join(valid)}")
    t = _terms()
    t[account] = {
        "share_pct": flt(share_pct) or None,
        "basis": basis or None,
        "start": start or None,
        "deal_currency": (deal_currency or "USD").upper(),
        "shares_losses": str(shares_losses) in ("1", "true", "True", "yes"),
    }
    frappe.db.set_default(_TERMS_KEY, json.dumps(t))
    frappe.db.commit()
    return t[account]
