"""Group P&L + intercompany mirror matrix — the Holding as a READING LENS.

The Holding entity has ZERO GL rows: the group view is computed, not booked.
Design (audited 2026-08): matched-elimination consolidation is NOT computable
today — the IC mirror rate is ~4% (Maslak invoiced Morocco 11 times in 2026;
Morocco recorded 4). So:

  • Group P&L eliminates by POLICY (role-based), not by matching:
      sales entity (Morocco)  → external revenue + its CORRECTED COGS family
                                (already anchored on Maslak's real purchase
                                invoices = the group's true cost)
      sourcing entity (Maslak)→ OPEX only; its revenue is 100% intercompany
                                paper and its cost lines are the IC leg —
                                both dropped, both DISCLOSED
      dormant/holding         → OPEX only (China ~40K, Holding zero)
  • The IC matrix is the DISCOVERY tool: seller-side vs buyer-side documents
    per pair per month + the unpaired IC balances — the gap column is the
    settlement work queue. The consolidated BALANCE SHEET waits for it.

FX: monthly average of the Currency Exchange records (cross-rated through
USD when no direct rate exists). Rates used are returned with the figures.
"""
import frappe
from frappe.utils import flt, nowdate

from accounting_portal.api.permissions import assert_portal_access

ROLES = {          # ap_group_roles config overrides
    "Justyol Morocco": "sales",
    "Maslak LTD": "sourcing",
    "Justyol China": "dormant",
    "Justyol Holding": "holding",
}
_IC_KEYWORDS = ("morocco", "maslak", "china", "holding", "istanbul",
                "intercompan", "internal invoic")
_COGS_NAMES = ("71.801", "71.002.", "71.999")


def _roles():
    try:
        v = frappe.parse_json(frappe.db.get_default("ap_group_roles") or "{}") or {}
        return {**ROLES, **v}
    except Exception:
        return dict(ROLES)


def _ccy_of(company):
    return frappe.db.get_value("Company", company, "default_currency") or "MAD"


def _usd_month_avg(to_ccy, year):
    """{month: avg USD→ccy rate} with forward-fill from the last known rate."""
    rows = frappe.db.sql(
        """SELECT MONTH(date) m, AVG(exchange_rate) r FROM `tabCurrency Exchange`
           WHERE from_currency='USD' AND to_currency=%s AND YEAR(date)=%s
           GROUP BY MONTH(date)""", (to_ccy, year), as_dict=True)
    got = {int(x.m): flt(x.r) for x in rows}
    last = flt(frappe.db.sql(
        """SELECT exchange_rate FROM `tabCurrency Exchange`
           WHERE from_currency='USD' AND to_currency=%s AND date < %s
           ORDER BY date DESC LIMIT 1""", (to_ccy, f"{year}-01-01"))
        and frappe.db.sql(
        """SELECT exchange_rate FROM `tabCurrency Exchange`
           WHERE from_currency='USD' AND to_currency=%s AND date < %s
           ORDER BY date DESC LIMIT 1""", (to_ccy, f"{year}-01-01"))[0][0] or 0)
    out = {}
    for m in range(1, 13):
        if got.get(m):
            last = got[m]
        out[m] = last
    return out


def _month_rates(currencies, pres, year):
    """{ccy: {month: rate ccy→pres}} — cross through USD."""
    usd_to = {c: _usd_month_avg(c, year) for c in set(list(currencies) + [pres]) if c != "USD"}
    out = {}
    for c in currencies:
        out[c] = {}
        for m in range(1, 13):
            if c == pres:
                out[c][m] = 1.0
                continue
            u_p = 1.0 if pres == "USD" else flt(usd_to.get(pres, {}).get(m))
            u_c = 1.0 if c == "USD" else flt(usd_to.get(c, {}).get(m))
            out[c][m] = (u_p / u_c) if (u_p and u_c) else 0.0
    return out


def _is_cogs_row(at, name):
    n = str(name)
    if n.startswith(("770.07", "770.0.7")) and not n.startswith("770.07.004"):
        return True   # legacy inbound freight + its 71.004 offset live with COGS
    return at in ("Cost of Goods Sold", "Stock Adjustment") or n.startswith(_COGS_NAMES)


def _is_ic_name(name):
    n = (name or "").lower()
    return next((True for k in _IC_KEYWORDS if k in n), False)


@frappe.whitelist()
def group_pnl(year=None, ccy="MAD"):
    """The group's policy-eliminated P&L by month, with full disclosure of
    what was eliminated per entity and any policy anomalies."""
    assert_portal_access()
    y = int(year or nowdate()[:4])
    roles = _roles()
    companies = list(roles)
    ccys = {co: _ccy_of(co) for co in companies}
    rates = _month_rates(set(ccys.values()), ccy, y)
    months = list(range(1, 13))
    out_m = {m: {"revenue": 0.0, "cogs": 0.0, "opex": 0.0} for m in months}
    opex_by_co = {co: 0.0 for co in companies}
    eliminated = {co: {"revenue": 0.0, "ic_cost": 0.0} for co in companies}
    anomalies = []
    for co in companies:
        role = roles.get(co, "dormant")
        rows = frappe.db.sql(
            """SELECT a.name, a.root_type rt, IFNULL(a.account_type,'') at,
                      MONTH(g.posting_date) m, SUM(g.credit-g.debit) cr
               FROM `tabGL Entry` g JOIN `tabAccount` a ON a.name=g.account
               WHERE g.company=%s AND g.is_cancelled=0
                 AND a.root_type IN ('Income','Expense')
                 AND YEAR(g.posting_date)=%s
               GROUP BY a.name, MONTH(g.posting_date)""", (co, y), as_dict=True)
        fx = rates.get(ccys[co], {})
        for r in rows:
            m = int(r.m)
            v = flt(r.cr) * flt(fx.get(m))
            if r.rt == "Income":
                if role == "sales":
                    out_m[m]["revenue"] += v
                else:
                    eliminated[co]["revenue"] += v
                    if abs(v) > 5000 and not _is_ic_name(r.name):
                        anomalies.append({"company": co, "account": r.name, "month": m,
                                          "amount": round(v),
                                          "note": "revenue on a non-sales entity — external? check"})
            else:
                d = -v   # expense as positive debit
                if role == "sales" and _is_cogs_row(r.at, r.name):
                    out_m[m]["cogs"] += d
                elif role != "sales" and (_is_cogs_row(r.at, r.name) or _is_ic_name(r.name)):
                    eliminated[co]["ic_cost"] += d
                else:
                    out_m[m]["opex"] += d
                    opex_by_co[co] += d
    rows_out = []
    for m in months:
        rev, cg, op = out_m[m]["revenue"], out_m[m]["cogs"], out_m[m]["opex"]
        if not (rev or cg or op):
            continue
        rows_out.append({"month": f"{y}-{m:02d}", "revenue": round(rev), "cogs": round(cg),
                         "gross": round(rev - cg),
                         "gm_pct": round(100 * (rev - cg) / rev, 1) if rev else 0,
                         "opex": round(op), "net": round(rev - cg - op)})
    tot = {k: sum(r[k] for r in rows_out) for k in ("revenue", "cogs", "gross", "opex", "net")}
    tot["gm_pct"] = round(100 * tot["gross"] / tot["revenue"], 1) if tot["revenue"] else 0
    return {"year": y, "ccy": ccy, "roles": roles, "rows": rows_out, "total": tot,
            "opex_by_company": {k: round(v) for k, v in opex_by_co.items()},
            "eliminated": {k: {kk: round(vv) for kk, vv in v.items()}
                           for k, v in eliminated.items() if any(v.values())},
            "anomalies": anomalies[:20]}


_PARTY_PAT = {"Justyol Morocco": "%morocco%", "Maslak LTD": "%maslak%",
              "Justyol China": "%china%", "Justyol Holding": "%holding%"}


@frappe.whitelist()
def ic_matrix(year=None):
    """The intercompany MIRROR matrix: for every pair, the seller's invoices
    vs the buyer's recorded purchases (by month, local currencies), and every
    IC-flagged balance account — the gaps are the settlement work queue."""
    assert_portal_access()
    y = int(year or nowdate()[:4])
    companies = list(_roles())
    pairs = []
    for seller in companies:
        for buyer in companies:
            if seller == buyer:
                continue
            si = frappe.db.sql(
                """SELECT MONTH(posting_date) m, COUNT(*) n, ROUND(SUM(base_grand_total)) x
                   FROM `tabSales Invoice`
                   WHERE company=%s AND docstatus=1 AND YEAR(posting_date)=%s
                     AND LOWER(customer) LIKE %s
                   GROUP BY MONTH(posting_date)""",
                (seller, y, _PARTY_PAT[buyer]), as_dict=True)
            pi = frappe.db.sql(
                """SELECT MONTH(posting_date) m, COUNT(*) n, ROUND(SUM(base_grand_total)) x
                   FROM `tabPurchase Invoice`
                   WHERE company=%s AND docstatus=1 AND YEAR(posting_date)=%s
                     AND LOWER(supplier) LIKE %s
                   GROUP BY MONTH(posting_date)""",
                (buyer, y, _PARTY_PAT[seller]), as_dict=True)
            if not si and not pi:
                continue
            sm = {int(r.m): r for r in si}
            pm = {int(r.m): r for r in pi}
            months = []
            for m in sorted(set(sm) | set(pm)):
                months.append({"month": f"{y}-{m:02d}",
                               "seller_n": sm.get(m, {}).get("n", 0) if m in sm else 0,
                               "seller_amt": flt(sm[m].x) if m in sm else 0,
                               "buyer_n": pm.get(m, {}).get("n", 0) if m in pm else 0,
                               "buyer_amt": flt(pm[m].x) if m in pm else 0})
            pairs.append({
                "seller": seller, "buyer": buyer,
                "seller_ccy": _ccy_of(seller), "buyer_ccy": _ccy_of(buyer),
                "seller_total": sum(x["seller_amt"] for x in months),
                "seller_docs": sum(x["seller_n"] for x in months),
                "buyer_total": sum(x["buyer_amt"] for x in months),
                "buyer_docs": sum(x["buyer_n"] for x in months),
                "months": months})
    balances = []
    cond = " OR ".join(["LOWER(a.account_name) LIKE %s"] * len(_IC_KEYWORDS))
    kws = [f"%{k}%" for k in _IC_KEYWORDS]
    for co in companies:
        rows = frappe.db.sql(
            f"""SELECT a.name, a.root_type rt, ROUND(SUM(g.debit-g.credit)) x
                FROM `tabGL Entry` g JOIN `tabAccount` a ON a.name=g.account
                WHERE g.company=%s AND g.is_cancelled=0 AND ({cond})
                  AND a.root_type IN ('Asset','Liability')
                GROUP BY a.name HAVING ABS(SUM(g.debit-g.credit)) > 50000
                ORDER BY ABS(SUM(g.debit-g.credit)) DESC LIMIT 12""",
            tuple([co] + kws), as_dict=True)
        for r in rows:
            balances.append({"company": co, "ccy": _ccy_of(co), "account": r.name,
                             "root_type": r.rt, "balance": flt(r.x)})
    return {"year": y, "pairs": pairs, "balances": balances}


@frappe.whitelist()
def group_pnl_corrected(year=None, ccy="USD"):
    """Group P&L on the CORRECTED cost basis — the trustworthy reading lens.

    Same policy-elimination as group_pnl (sales entity carries external revenue;
    sourcing/dormant carry OPEX only, their IC revenue+cost disclosed), and the
    SAME FX. The one difference: cost of goods is the MODELLED landed cost
    (pnl_estimated._unit_costs), not the booked GL COGS. The booked figure mixes
    in 71.004 Stock-Adjustment repost noise (June reads a negative COGS, January
    a 91% margin); the modelled figure is stable month to month, so the monthly
    P&L is readable now — while the books converge to it as the cost correction
    lands. cogs_booked is returned alongside so the gap is visible.
    """
    assert_portal_access()
    from accounting_portal.api.pnl_estimated import _unit_costs
    y = int(year or nowdate()[:4])
    roles = _roles()
    companies = list(roles)
    ccys = {co: _ccy_of(co) for co in companies}
    rates = _month_rates(set(ccys.values()), ccy, y)
    months = list(range(1, 13))
    out_m = {m: {"revenue": 0.0, "cogs": 0.0, "cogs_booked": 0.0, "opex": 0.0} for m in months}
    opex_by_co = {co: 0.0 for co in companies}
    eliminated = {co: {"revenue": 0.0, "ic_cost": 0.0} for co in companies}
    sales_co = next((c for c, r in roles.items() if r == "sales"), None)

    # revenue + opex + eliminations + booked cogs (for the gap) — same as group_pnl
    for co in companies:
        role = roles.get(co, "dormant")
        fx = rates.get(ccys[co], {})
        rows = frappe.db.sql(
            """SELECT a.name, a.root_type rt, IFNULL(a.account_type,'') at,
                      MONTH(g.posting_date) m, SUM(g.credit-g.debit) cr
               FROM `tabGL Entry` g JOIN `tabAccount` a ON a.name=g.account
               WHERE g.company=%s AND g.is_cancelled=0
                 AND a.root_type IN ('Income','Expense') AND YEAR(g.posting_date)=%s
               GROUP BY a.name, MONTH(g.posting_date)""", (co, y), as_dict=True)
        for r in rows:
            m = int(r.m); v = flt(r.cr) * flt(fx.get(m))
            if r.rt == "Income":
                if role == "sales": out_m[m]["revenue"] += v
                else: eliminated[co]["revenue"] += v
            else:
                d = -v
                if role == "sales" and _is_cogs_row(r.at, r.name):
                    out_m[m]["cogs_booked"] += d      # booked, kept only for the gap
                elif role != "sales" and (_is_cogs_row(r.at, r.name) or _is_ic_name(r.name)):
                    eliminated[co]["ic_cost"] += d
                else:
                    out_m[m]["opex"] += d
                    opex_by_co[co] += d

    # corrected COGS: modelled unit cost × delivered qty, sales entity, per month
    model = {}
    if sales_co:
        costs, model = _unit_costs(sales_co)
        sccy = ccys[sales_co]; sfx = rates.get(sccy, {})
        for r in frappe.db.sql(
                """SELECT MONTH(sle.posting_date) m, sle.item_code ic, SUM(-sle.actual_qty) q
                   FROM `tabStock Ledger Entry` sle
                   WHERE sle.company=%s AND sle.is_cancelled=0 AND sle.voucher_type='Delivery Note'
                     AND YEAR(sle.posting_date)=%s GROUP BY MONTH(sle.posting_date), sle.item_code""",
                (sales_co, y), as_dict=True):
            c = costs.get(r.ic)
            if c and flt(c["cost"]) > 0:
                out_m[int(r.m)]["cogs"] += flt(r.q) * flt(c["cost"]) * flt(sfx.get(int(r.m)))

    rows_out = []
    for m in months:
        d = out_m[m]
        if not (d["revenue"] or d["cogs"] or d["opex"]):
            continue
        rows_out.append({"month": f"{y}-{m:02d}", "revenue": round(d["revenue"]),
                         "cogs": round(d["cogs"]), "cogs_booked": round(d["cogs_booked"]),
                         "gross": round(d["revenue"] - d["cogs"]),
                         "gm_pct": round(100 * (d["revenue"] - d["cogs"]) / d["revenue"], 1) if d["revenue"] else 0,
                         "opex": round(d["opex"]), "net": round(d["revenue"] - d["cogs"] - d["opex"])})
    tot = {k: sum(r[k] for r in rows_out) for k in ("revenue", "cogs", "cogs_booked", "gross", "opex", "net")}
    tot["gm_pct"] = round(100 * tot["gross"] / tot["revenue"], 1) if tot["revenue"] else 0
    return {"year": y, "ccy": ccy, "basis": "corrected", "roles": roles, "rows": rows_out, "total": tot,
            "opex_by_company": {k: round(v) for k, v in opex_by_co.items()},
            "eliminated": {k: {kk: round(vv) for kk, vv in v.items()}
                           for k, v in eliminated.items() if any(v.values())},
            "model": model}
