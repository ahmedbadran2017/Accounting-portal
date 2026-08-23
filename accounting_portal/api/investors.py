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
    ("gross_margin", "Gross margin on the goods", "revenue less what the goods cost"),
    ("cm1", "After delivering them", "less courier to the customer"),
    ("cm2", "After selling them", "less advertising"),
    ("operating", "Profit on the goods", "less the running costs the goods needed"),
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


def _deal_amount(base, row, foreign, ccy, date, out=False):
    """The movement's value in the currency the deal was struck in.

    Every line here should already carry it — ERPNext stores the account-currency
    amount when the account is foreign — and that recorded figure is authoritative
    because it is what the parties transacted at, not what a rate table says today.
    Only when it is absent (a line posted without one, or a capital account kept in
    the books' own currency while the deal was agreed in another) does this fall
    back to the rate of that date, and the row is marked so the screen can show it
    as an estimate rather than passing it off as recorded fact.
    """
    if foreign:
        rec = (flt(row.dac) - flt(row.cac)) if out else (flt(row.cac) - flt(row.dac))
        if abs(rec) > 0.005:
            return rec, False
    else:
        return base, False
    rate = _fx(ccy, date)
    return (base * rate, True) if rate else (0.0, True)

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


def _capital_snapshot():
    """The counted stock the capital share is struck on.

    Deliberately not read from the stock ledger. That ledger carries a million
    phantom units in a Turkish rejects warehouse from one mistyped receipt, and its
    quantities disagree with the system's own bin balances by over a million units.
    A stock somebody counted and valued does not have that problem, so the share is
    struck on a snapshot the finance team enters each cycle: a date, the counted
    value in USD, and the investor capital standing against it.
    """
    d = frappe.parse_json(frappe.db.get_default("ap_investor_capital") or "{}") or {}
    return {
        "date": d.get("date") or "2025-12-31",
        "stock_usd": flt(d.get("stock_usd") or 493279),
        "source": d.get("source") or "STOCK VALUATION 2025.xlsx, each location in its own currency",
        "detail": d.get("detail") or [
            {"location": "Justyol Morocco", "skus": 2314, "units": 36761, "native": "3,112,348 MAD", "usd": 342016},
            {"location": "Maslak, Turkey", "skus": 134, "units": 2025, "native": "440,430 TRY", "usd": 10303},
            {"location": "Justyol China", "skus": 1039, "units": 15388, "native": "54,466 USD", "usd": 54466},
            {"location": "In transit", "skus": 181, "units": 19625, "native": "3,697,511 TRY", "usd": 86494},
        ],
    }


# A cost is charged to the goods when handling or selling them required it. It
# stays with the company when the group would not have carried it buying through
# an agent - which is the whole of the Turkish sourcing operation: an agent at 5%
# of goods value would cost about 45,000 a year against the 328,000 that entity
# actually costs. Building it is an investment in the group, not a cost of a cycle.
_GOODS_SHARE = [
    ("Morocco payroll", "Justyol Morocco", ["720.%"], 0.87,
     "26 of 30 heads are warehouse, customer service or procurement"),
    ("Morocco warehouses", "Justyol Morocco", ["770.001%"], 1.0, "where the goods sit"),
    ("Store software", None, ["770.012.005%", "770.012.004%", "760.01.009%"], 1.0,
     "Shopify, Aftership, cloud - there is no store without them"),
    ("Morocco utilities & supplies", "Justyol Morocco",
     ["770.01%", "770.03%"], 0.5, "the warehouse half"),
]


def _cycle(date_from, date_to):
    """The trading cycle on the goods, layer by layer, in USD.

    Product cost is modelled rather than booked: the booked figure carries FX
    mislabels and receipts priced above their own invoice. Rates come from the
    documents each month actually posted, not the sparse Currency Exchange table.
    """
    from accounting_portal.api.pnl_estimated import _doc_rates, _unit_costs, _usd_at, _RATE_CACHE
    SALES, SRC = "Justyol Morocco", "Maslak LTD"
    months = []
    y0, m0 = int(date_from[:4]), int(date_from[5:7])
    y1, m1 = int(date_to[:4]), int(date_to[5:7])
    while (y0, m0) <= (y1, m1):
        months.append(f"{y0}-{m0:02d}")
        m0 += 1
        if m0 > 12:
            m0 = 1
            y0 += 1
    _RATE_CACHE["r"] = _doc_rates(months)

    def usd(company, v, m):
        ccy = frappe.db.get_value("Company", company, "default_currency") or "USD"
        r = _usd_at(ccy, m)
        return v * r

    def gl(company, like, m, root=None, credit=False):
        col = "SUM(g.credit)-SUM(g.debit)" if credit else "SUM(g.debit)-SUM(g.credit)"
        q = ("SELECT " + col + " FROM `tabGL Entry` g JOIN `tabAccount` a ON a.name=g.account "
             "WHERE g.company=%s AND g.is_cancelled=0 AND a.name LIKE %s "
             "AND DATE_FORMAT(g.posting_date,'%%Y-%%m')=%s "
             "AND g.voucher_type NOT IN ('Stock Reconciliation','Stock Entry')")
        p = [company, like, m]
        if root:
            q += " AND a.root_type=%s"
            p.append(root)
        return flt(frappe.db.sql(q, tuple(p))[0][0])

    costs, meta = _unit_costs(SALES)
    revenue = product = courier = ads = 0.0
    units = uncovered = 0.0
    for m in months:
        revenue += usd(SALES, gl(SALES, "6%", m, "Income", credit=True), m)
        courier += usd(SALES, gl(SALES, "770.07.004%", m) + gl(SALES, "770.07.008%", m), m)
        ads += usd(SALES, gl(SALES, "760.%", m) - gl(SALES, "760.01.009%", m), m)
        ads += usd(SRC, gl(SRC, "760.%", m) - gl(SRC, "760.01.009%", m)
                   - gl(SRC, "760.002.001%", m), m)
        for r in frappe.db.sql(
                """SELECT sle.item_code AS ic, SUM(-sle.actual_qty) AS q
                   FROM `tabStock Ledger Entry` sle
                   WHERE sle.company=%s AND sle.is_cancelled=0
                     AND sle.voucher_type='Delivery Note'
                     AND DATE_FORMAT(sle.posting_date,'%%Y-%%m')=%s
                   GROUP BY sle.item_code""", (SALES, m), as_dict=True):
            c = costs.get(r["ic"])
            q = flt(r["q"])
            units += q
            if c:
                product += usd(SALES, q * c["cost"], m)
            else:
                uncovered += q

    # overhead, split by what it served
    goods_oh, oh_rows = 0.0, []
    for label, company, likes, share, why in _GOODS_SHARE:
        v = 0.0
        for m in months:
            for like in likes:
                if company:
                    v += usd(company, gl(company, like, m), m)
                else:
                    for co in (SALES, SRC):
                        v += usd(co, gl(co, like, m), m)
        v *= share
        goods_oh += v
        oh_rows.append({"label": label, "usd": round(v), "share_pct": round(share * 100),
                        "why": why})
    total_oh = 0.0
    for m in months:
        for co in (SALES, SRC):
            total_oh += usd(co, flt(frappe.db.sql(
                """SELECT SUM(g.debit-g.credit) FROM `tabGL Entry` g
                   JOIN `tabAccount` a ON a.name=g.account
                   WHERE g.company=%s AND g.is_cancelled=0 AND a.root_type='Expense'
                     AND a.name NOT LIKE '71.%%'
                     AND NOT ((a.name LIKE '770.07%%' OR a.name LIKE '770.0.7%%')
                              AND a.name NOT LIKE '770.07.004%%'
                              AND a.name NOT LIKE '770.07.008%%')
                     AND DATE_FORMAT(g.posting_date,'%%Y-%%m')=%s""",
                (co, m))[0][0]), m)

    gm = revenue - product
    cm1 = gm - courier
    cm2 = cm1 - ads
    on_goods = cm2 - goods_oh
    snap = _capital_snapshot()
    stock = flt(snap["stock_usd"])
    return {
        "from": date_from, "to": date_to, "currency": "USD", "months": months,
        "revenue": round(revenue), "product_cost": round(product),
        "units": round(units), "units_unpriced": round(uncovered),
        "courier": round(courier), "marketing": round(ads),
        "gross_margin": round(gm), "cm1": round(cm1), "cm2": round(cm2),
        "overhead_total": round(total_oh), "overhead_goods": round(goods_oh),
        "overhead_rows": oh_rows,
        "overhead_goods_pct": round(100.0 * goods_oh / total_oh, 1) if total_oh else None,
        "operating": round(on_goods),
        "gm_pct": round(100.0 * gm / revenue, 1) if revenue else None,
        "capital": snap,
        "model": meta,
        "stock_usd": round(stock),
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
        deal, est = _deal_amount(base, r, foreign, ccy, str(r.posting_date))
        rate = (base / deal) if deal else None        # base units per deal unit
        moves.append({"date": str(r.posting_date)[:10], "voucher": r.voucher_no,
                      "local": round(base, 2), "rate": round(rate, 4) if rate else None,
                      "deal": round(deal, 2), "estimated": est,
                      "note": (r.remarks or "")[:120]})
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
            deal, est = _deal_amount(base, r, pf, ccy, str(r.posting_date), out=True)
            rate = (base / deal) if deal else None
            draws.append({"date": str(r.posting_date)[:10], "voucher": r.voucher_no,
                          "local": round(base, 2), "deal": round(deal, 2),
                          "rate": round(rate, 4) if rate else None, "estimated": est})
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
    # The share on the goods: capital buys a proportion of the stock, that
    # proportion earns its slice of what the goods made, and the operator takes
    # half of it. Order does not matter - halving before or after the split lands
    # on the same number - so it is shown the way the deal was struck.
    goods = None
    cap_usd = cap_deal if deal_ccy == "USD" else (
        cap_deal * (_fx(deal_ccy, date_to) or 0))
    stock = flt(cyc.get("stock_usd"))
    if stock > 0 and cap_usd > 0:
        pct = cap_usd / stock
        profit = flt(cyc.get("operating"))
        op_half = flt(t.get("operator_pct") or 50) / 100.0
        his = profit * pct
        drawn_usd = drawn_deal if deal_ccy == "USD" else (
            drawn_deal * (_fx(deal_ccy, date_to) or 0))
        goods = {
            "capital_usd": round(cap_usd), "stock_usd": round(stock),
            "company_usd": round(stock - cap_usd),
            "pct": round(100.0 * pct, 1),
            "company_pct": round(100.0 * (1 - pct), 1),
            "profit": round(profit),
            "his_capital_share": round(his),
            "company_capital_share": round(profit - his),
            "his_half": round(his * (1 - op_half)),
            "operator_half": round(his * op_half),
            "drawn": round(drawn_usd),
            "outstanding": round(his * (1 - op_half) - drawn_usd),
            "operator_pct": round(op_half * 100),
            "sensitivity": [],
        }
        # The share moves with what counts as "the capital he bought into", and
        # that is a judgement, not a fact. Show the answer on each defensible
        # reading so the number is argued once rather than every cycle.
        det = cyc.get("capital", {}).get("detail") or []
        bases = [("all stock counted, everywhere", stock)]
        transit = sum(flt(d.get("usd")) for d in det
                      if "transit" in str(d.get("location", "")).lower())
        if transit:
            bases.append(("landed stock only, in-transit excluded", stock - transit))
        mor = sum(flt(d.get("usd")) for d in det
                  if "morocco" in str(d.get("location", "")).lower())
        if mor:
            bases.append(("stock in the selling country only", mor))
        for lbl, base in bases:
            if base <= 0:
                continue
            p2 = min(cap_usd / base, 1.0)
            goods["sensitivity"].append({
                "label": lbl, "base_usd": round(base), "pct": round(100.0 * p2, 1),
                "amount": round(profit * p2 * (1 - op_half)),
                "chosen": abs(base - stock) < 1,
            })

    return {
        "account": account, "name": acc.account_name, "company": acc.company,
        "goods": goods,
        "currency": ccy, "deal_currency": deal_ccy,
        "capital_local": round(cap_local, 2), "capital_deal": round(cap_deal, 2),
        "owed_in_base": round(owed_in_base, 2) if owed_in_base is not None else None,
        "fx_gap": round(fx_gap, 2) if fx_gap is not None else None,
        "fx_gap_note": ("carrying value in the books vs the same obligation at today's rate — "
                        "an exchange-rate revaluation that has not been run"),
        "drawn_local": round(drawn_local, 2), "drawn_deal": round(drawn_deal, 2),
        "moves": moves, "draws": draws, "profit_account": pa,
        "terms": t, "cycle": cyc, "share": share,
        "capital_basis": cyc.get("capital"),
        "overhead_rows": cyc.get("overhead_rows"),
        "model": cyc.get("model"),
        "layers": [{"key": k, "label": l, "hint": h, "value": cyc.get(k)} for k, l, h in _LAYERS],
        "quality": _quality_flags(),
        "provisional": True,
    }


@frappe.whitelist()
def set_investor_terms(account=None, share_pct=None, basis=None, start=None,
                       deal_currency=None, shares_losses=None, operator_pct=None):
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
        "operator_pct": flt(operator_pct) if operator_pct not in (None, "") else 50,
    }
    frappe.db.set_default(_TERMS_KEY, json.dumps(t))
    frappe.db.commit()
    return t[account]


@frappe.whitelist()
def set_capital_snapshot(date=None, stock_usd=None, source=None, detail=None):
    """Record the counted stock the capital share is struck on.

    Entered rather than read, because the counted figure is the trustworthy one:
    each location valued in its own currency by the people who held it, against a
    ledger that still carries a million phantom units from one mistyped receipt.
    """
    if not can_manage_users():
        frappe.throw("Restricted to the Super Admin", frappe.PermissionError)
    if not flt(stock_usd):
        frappe.throw("stock_usd required")
    if isinstance(detail, str):
        detail = frappe.parse_json(detail or "[]")
    frappe.db.set_default("ap_investor_capital", json.dumps({
        "date": date or nowdate(), "stock_usd": flt(stock_usd),
        "source": source or "counted stock", "detail": detail or [],
    }))
    frappe.db.commit()
    return _capital_snapshot()
