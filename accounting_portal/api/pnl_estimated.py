"""Estimated P&L — a management view that reads correctly while the books heal.

The books carry two faults that make a monthly margin unreadable: product cost is
polluted (FX mislabels, receipts priced above their own invoice, hand-keyed
receipts) and inbound freight lands in the month the container arrives instead of
following the goods. Fixing both takes the accounting team months of item-by-item
work. This report doesn't wait for them.

Nothing here posts. Revenue, payroll, rent and marketing come straight from the
GL; only the cost of goods is *modelled*, from the documents that are already
trustworthy — the supplier's own invoice, converted at the rate of its own date,
plus freight and customs on weight.

The model is calibrated against the items the team has already verified, so it is
unbiased in aggregate by construction, and it gets more accurate on its own as
they verify more. The gap column — booked minus modelled, per month — is their
work queue, sorted by money. When it closes, this report has done its job and
you go back to reading the books.
"""
import frappe
from frappe.utils import flt, nowdate

from accounting_portal.api.permissions import assert_portal_access, resolve_companies

SALES = "Justyol Morocco"
SOURCE = "Maslak LTD"

# Sea freight + customs per kg, derived from the 2026 inbound pot over the weight
# actually imported, and confirmed against the warehouse's own figure (26–46 MAD
# for a 2 kg unit). Air freight is deliberately NOT in here: it belongs to the
# small, fast subset that travels by air, and spreading it over bulky sea goods
# inflates them ~1.8x.
FREIGHT_PER_KG = 22.70
DEFAULT_WEIGHT = 1.019          # average unit weight, for items with none recorded
CALIB_FLOOR, CALIB_CEIL = 0.80, 1.60


def _target(company):
    cos = resolve_companies(company)
    if not cos:
        return None
    return company if (company and company in cos) else cos[0]


def _fx_table():
    """MAD-per-TRY by date, as a sorted list we can bisect — one query, not N."""
    rows = frappe.db.sql(
        """SELECT date, from_currency, to_currency, exchange_rate FROM `tabCurrency Exchange`
           WHERE from_currency='USD' AND to_currency IN ('TRY','MAD') ORDER BY date""",
        as_dict=True)
    try_r, mad_r = [], []
    for r in rows:
        (try_r if r.to_currency == "TRY" else mad_r).append((str(r.date), flt(r.exchange_rate)))

    def at(series, d):
        v = 0.0
        for dt, rate in series:
            if dt <= d:
                v = rate
            else:
                break
        return v

    cache = {}

    def mad_per_try(d):
        d = str(d)[:10]
        if d not in cache:
            t, m = at(try_r, d), at(mad_r, d)
            cache[d] = (m / t) if t else 0.0
        return cache[d]

    return mad_per_try


def _verified(company):
    """Costs an accountant reviewed and applied — treated as fact, never modelled."""
    out = {}
    for a in frappe.db.sql(
            """SELECT reference_name AS ic, payload FROM `tabAccounting Portal Action`
               WHERE reference_doctype='Item' AND status='Posted'
                 AND IFNULL(reference_name,'')<>''
                 AND IFNULL(payload,'') LIKE '%%"rows"%%'""", as_dict=True):
        try:
            rows = (frappe.parse_json(a.payload) or {}).get("rows") or []
        except Exception:
            continue
        if a.ic and rows and flt(rows[0].get("rate")) > 0:
            out[a.ic] = flt(rows[0].get("rate"))
    return out


def _invoice_costs(company, mad_per_try):
    """Weighted-average purchase cost per item, from its OWN supplier invoice.

    Maslak lines are TRY and are converted at the rate of the invoice's own date —
    not today's — because the lira moved 15% across this year and a single rate
    would quietly re-price January.
    """
    rows = frappe.db.sql(
        """SELECT i.item_code AS ic, p.posting_date AS d, i.qty AS q,
                  i.base_rate AS r, p.company AS co
           FROM `tabPurchase Invoice Item` i JOIN `tabPurchase Invoice` p ON p.name=i.parent
           WHERE p.docstatus=1 AND i.base_rate>0 AND i.qty>0
             AND p.company IN (%s, %s)""", (SOURCE, company), as_dict=True)
    acc = {}
    for r in rows:
        rate = flt(r.r) * (mad_per_try(r.d) if r.co == SOURCE else 1.0)
        if rate <= 0:
            continue
        if not r.ic:
            continue
        a = acc.setdefault(r.ic, [0.0, 0.0, False])
        a[0] += rate * flt(r.q)
        a[1] += flt(r.q)
        if r.co == SOURCE:
            a[2] = True
    return {ic: (v[0] / v[1], v[2]) for ic, v in acc.items() if v[1] > 0}


def _weights(items):
    """Unit weight, falling back to the family average, then the catalogue average."""
    if not items:
        return {}
    out, need = {}, []
    for chunk in [items[i:i + 500] for i in range(0, len(items), 500)]:
        ph = ", ".join(["%s"] * len(chunk))
        for r in frappe.db.sql(
                "SELECT name, weight_per_unit AS w, variant_of AS v FROM `tabItem` "
                "WHERE name IN (" + ph + ")", tuple(chunk), as_dict=True):
            if 0.005 <= flt(r.w) <= 50:
                out[r.name] = flt(r.w)
            elif r.v:
                need.append((r.name, r.v))
    fams = list({v for _, v in need})
    fam = {}
    for chunk in [fams[i:i + 300] for i in range(0, len(fams), 300)]:
        ph = ", ".join(["%s"] * len(chunk))
        for r in frappe.db.sql(
                "SELECT variant_of AS v, AVG(weight_per_unit) AS w FROM `tabItem` "
                "WHERE variant_of IN (" + ph + ") AND weight_per_unit BETWEEN 0.005 AND 50 "
                "GROUP BY variant_of", tuple(chunk), as_dict=True):
            fam[r.v] = flt(r.w)
    for ic, v in need:
        out[ic] = fam.get(v) or DEFAULT_WEIGHT
    return out


def _unit_costs(company):
    """Modelled landed cost per item + the calibration factor, cached together.

    Returns (costs, meta) where costs maps item -> {"cost", "tier"}:
        tier 0  the team verified it — used raw, the model never touches it
        tier 1  its own supplier invoice
        tier 2  a sibling in the same family had one
    """
    ck = "ap_pnlest:costs:" + company
    hit = frappe.cache().get_value(ck)
    if hit is not None:
        return hit["costs"], hit["meta"]

    mad_per_try = _fx_table()
    verified = _verified(company)
    inv = _invoice_costs(company, mad_per_try)
    items = sorted({k for k in list(inv.keys()) + list(verified.keys()) if k})
    wt = _weights(items)

    def modelled(ic):
        prod, imported = inv[ic]
        return prod + (wt.get(ic, DEFAULT_WEIGHT) * FREIGHT_PER_KG if imported else 0.0)

    # Calibrate on the overlap: items the team verified that also have their own
    # invoice. The residual is systematic (the model reads ~17% light), so one
    # factor removes the bias; per-item scatter stays, aggregate goes to zero.
    num = den = 0.0
    sample = 0
    for ic, truth in verified.items():
        if ic in inv:
            num += truth
            den += modelled(ic)
            sample += 1
    factor = (num / den) if (den > 0 and sample >= 30) else 1.0
    factor = max(CALIB_FLOOR, min(CALIB_CEIL, factor))

    costs = {}
    for ic, rate in verified.items():
        costs[ic] = {"cost": rate, "tier": 0}
    for ic in inv:
        if ic not in costs:
            costs[ic] = {"cost": modelled(ic) * factor, "tier": 1}

    # tier 2 — a sibling carried an invoice, so the family price is a fair stand-in
    fam_rows = frappe.db.sql(
        """SELECT it.variant_of AS v, it.name AS ic FROM `tabItem` it
           WHERE IFNULL(it.variant_of,'')<>'' AND it.disabled=0""", as_dict=True)
    by_fam, orphans = {}, []
    for r in fam_rows:
        if not r.ic or not r.v:
            continue
        if r.ic in costs:
            by_fam.setdefault(r.v, []).append(costs[r.ic]["cost"])
        else:
            orphans.append((r.ic, r.v))
    for ic, v in orphans:
        peers = by_fam.get(v)
        if peers:
            costs[ic] = {"cost": sum(peers) / len(peers), "tier": 2}

    meta = {"factor": round(factor, 4), "sample": sample,
            "verified": len(verified), "modelled": len(costs) - len(verified),
            "freight_per_kg": FREIGHT_PER_KG}
    try:
        frappe.cache().set_value(ck, {"costs": costs, "meta": meta}, expires_in_sec=1800)
    except Exception:
        pass
    return costs, meta


_CATEGORY = [
    # Checked against the account NAME first, because the chart puts several costs in
    # the wrong branch: Google Cloud sits under 760.01.009, a marketing number, and
    # ERPNext development under 770.05, professional fees. Reading the number alone
    # reports cloud infrastructure as advertising and understates software by half.
    ("Software & cloud", ("cloud", "hosting", "erpnext", "shopify", "saas", "subscription",
                          "zoho", "openai", "chatgpt", "anthropic", "aftership", "manus")),
    ("Travel", ("airplane", "ticket", "travel")),
    ("Food & staff welfare", ("food", "catering", "hospitality")),
]
_BY_NUMBER = (
    ("770.07.004", "Courier to customer"), ("770.07.008", "Courier to customer"),
    ("760.", "Advertising"), ("720.", "Payroll"), ("770.001", "Rent & office"),
    ("770.012", "Software & cloud"), ("770.05", "Professional fees"),
    ("770.06", "Travel"), ("770.09", "Taxes & duties"), ("78.", "Bank charges & FX"),
    ("770.01", "Utilities & supplies"), ("770.03", "Utilities & supplies"),
    ("770.08", "Utilities & supplies"), ("708.", "Food & staff welfare"),
)


def _category(number, name):
    """Group an expense account by what it IS, name before number."""
    n = (name or "").lower()
    for label, words in _CATEGORY:
        for w in words:
            if w in n:
                return label
    num = str(number or "")
    for prefix, label in _BY_NUMBER:
        if num.startswith(prefix):
            return label
    return "Other"


def _months(year):
    y = int(year)
    last = int(nowdate()[5:7]) if y == int(nowdate()[:4]) else 12
    return [f"{y}-{m:02d}" for m in range(1, last + 1)]


def _is_inbound_landed(name):
    n = str(name)
    return (n.startswith(("770.07", "770.0.7")) and not n.startswith(("770.07.004", "770.07.008")))


def _is_product_cost(name, at):
    return str(name).startswith("71.") or at in ("Cost of Goods Sold", "Stock Adjustment")


def _doc_rates(months):
    """Monthly FX taken from the documents the books actually posted, not a table.

    The `Currency Exchange` table holds three USD/MAD records for the whole of 2026
    and stops in March, so anything derived from it silently re-prices half the year
    at a stale rate. Every payment and every foreign purchase, on the other hand,
    carries the rate the business really transacted at. Those are averaged per month
    and carried forward into the gaps, which keeps the series continuous without
    inventing a number.
    """
    usdmad, madtry = {}, {}
    for m in months:
        um = frappe.db.sql(
            """SELECT AVG(r) FROM (
                 SELECT source_exchange_rate r FROM `tabPayment Entry`
                   WHERE company=%s AND docstatus=1 AND paid_from_account_currency='USD'
                     AND source_exchange_rate BETWEEN 7 AND 13
                     AND DATE_FORMAT(posting_date,'%%Y-%%m')=%s
                 UNION ALL SELECT conversion_rate FROM `tabPurchase Receipt`
                   WHERE company=%s AND docstatus=1 AND currency='USD'
                     AND conversion_rate BETWEEN 7 AND 13
                     AND DATE_FORMAT(posting_date,'%%Y-%%m')=%s
                 UNION ALL SELECT conversion_rate FROM `tabPurchase Invoice`
                   WHERE company=%s AND docstatus=1 AND currency='USD'
                     AND conversion_rate BETWEEN 7 AND 13
                     AND DATE_FORMAT(posting_date,'%%Y-%%m')=%s) x""",
            (SALES, m, SALES, m, SALES, m))[0][0]
        mt = frappe.db.sql(
            """SELECT AVG(r) FROM (
                 SELECT conversion_rate r FROM `tabPurchase Receipt`
                   WHERE company=%s AND docstatus=1 AND currency='TRY'
                     AND conversion_rate BETWEEN 0.15 AND 0.30
                     AND DATE_FORMAT(posting_date,'%%Y-%%m')=%s
                 UNION ALL SELECT conversion_rate FROM `tabPurchase Invoice`
                   WHERE company=%s AND docstatus=1 AND currency='TRY'
                     AND conversion_rate BETWEEN 0.15 AND 0.30
                     AND DATE_FORMAT(posting_date,'%%Y-%%m')=%s
                 UNION ALL SELECT source_exchange_rate FROM `tabPayment Entry`
                   WHERE company=%s AND docstatus=1 AND paid_from_account_currency='TRY'
                     AND source_exchange_rate BETWEEN 0.15 AND 0.30
                     AND DATE_FORMAT(posting_date,'%%Y-%%m')=%s) x""",
            (SALES, m, SALES, m, SALES, m))[0][0]
        usdmad[m] = flt(um)
        madtry[m] = flt(mt)

    def fill(d):
        last = 0.0
        for m in months:                      # carry forward
            if d[m]:
                last = d[m]
            else:
                d[m] = last
        nxt = 0.0
        for m in reversed(months):            # and back, for a gap at the start
            if d[m]:
                nxt = d[m]
            else:
                d[m] = nxt
        return d

    return fill(usdmad), fill(madtry)


_RATE_CACHE = {}


def _usd_at(ccy, month, rates=None):
    """USD per unit of a local currency, from the month's own documents."""
    if ccy == "USD":
        return 1.0
    if rates is None:
        rates = _RATE_CACHE.get("r")
    if not rates:
        return 0.0
    usdmad, madtry = rates
    um = usdmad.get(month) or 0.0
    if ccy == "MAD":
        return (1.0 / um) if um else 0.0
    if ccy == "TRY":
        mt = madtry.get(month) or 0.0
        return (mt / um) if (um and mt) else 0.0
    return 0.0


def _sibling_opex(company, months, exclude):
    """Operating cost the group carries in the other entities, by category, in USD.

    Morocco is the only company that sells to a customer, so reading its P&L alone
    hides everything the group spends elsewhere on the same trade — most of the
    Turkish payroll, the Istanbul office, and a quarter of the ad spend. These land
    in the SAME categories as Morocco's own costs rather than a single lump, because
    "advertising" is a question about the group, not about one entity.

    Product cost is deliberately not taken from here: the model already values goods
    at what Maslak paid a third party, so adding Maslak's own cost of sales would
    count the same goods twice, and its sales to Morocco are internal, never revenue.
    """
    n = len(months)
    cats, by_co = {}, {}
    for co in frappe.get_all("Company", pluck="name"):
        if co == exclude:
            continue
        ccy = frappe.db.get_value("Company", co, "default_currency") or "USD"
        rows = frappe.db.sql(
            """SELECT a.name AS acc, a.account_name AS an,
                      DATE_FORMAT(g.posting_date,'%%Y-%%m') AS ym,
                      SUM(g.debit-g.credit) AS v
               FROM `tabGL Entry` g JOIN `tabAccount` a ON a.name=g.account
               WHERE g.company=%s AND g.is_cancelled=0 AND a.root_type='Expense'
                 AND a.name NOT LIKE '71.%%'
                 AND NOT (a.name LIKE '770.07%%' AND a.name NOT LIKE '770.07.004%%'
                          AND a.name NOT LIKE '770.07.008%%')
                 AND g.posting_date BETWEEN %s AND %s
               GROUP BY a.name, ym""",
            (co, months[0] + "-01", months[-1] + "-31"), as_dict=True)
        total = [0.0] * n
        for r in rows:
            if r["ym"] not in months:
                continue
            i = months.index(r["ym"])
            v = flt(r["v"]) * _usd_at(ccy, r["ym"])
            key = _category(r["acc"], r["an"])
            c = cats.setdefault(key, [0.0] * n)
            c[i] += v
            total[i] += v
        if max(abs(x) for x in total) > 1:
            by_co[co] = {"company": co, "currency": ccy,
                         "monthly": [round(x) for x in total], "total": round(sum(total))}
    return cats, list(by_co.values())


@frappe.whitelist()
def pnl_estimated(company=None, year=None, scope=None):
    """Monthly P&L with a modelled cost of goods. Read-only; posts nothing.

    scope="group" adds the operating cost the other entities carry and restates
    everything in USD, which is the only level the result means anything at:
    Morocco sells, Maslak sources and pays a large share of the overhead.
    """
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    group = str(scope or "") == "group"
    y = int(year or nowdate()[:4])
    ck = f"ap_pnlest:{target}:{y}:{scope or ''}"
    hit = frappe.cache().get_value(ck)
    if hit is not None:
        return hit

    months = _months(y)
    idx = {m: i for i, m in enumerate(months)}
    n = len(months)
    fr, to = f"{y}-01-01", f"{y}-12-31"
    ccy = frappe.db.get_value("Company", target, "default_currency") or "MAD"

    costs, meta = _unit_costs(target)

    # ── revenue and operating costs, straight from the GL ──────────────────────
    rows = frappe.db.sql(
        """SELECT a.name, a.account_name AS an, a.root_type AS rt,
                  IFNULL(a.account_type,'') AS at,
                  DATE_FORMAT(g.posting_date,'%%Y-%%m') AS ym,
                  ROUND(SUM(g.credit-g.debit)) AS net
           FROM `tabGL Entry` g JOIN `tabAccount` a ON a.name=g.account
           WHERE g.company=%s AND g.is_cancelled=0 AND a.root_type IN ('Income','Expense')
             AND g.posting_date BETWEEN %s AND %s
           GROUP BY a.name, ym""", (target, fr, to), as_dict=True)

    revenue = [0.0] * n
    booked_cogs = [0.0] * n      # what the books charge, for the gap column
    opex_accts = {}
    for r in rows:
        i = idx.get(r["ym"])
        if i is None:
            continue
        if r["rt"] == "Income":
            revenue[i] += flt(r["net"])
            continue
        amt = -flt(r["net"])                      # expense positive
        if _is_product_cost(r["name"], r["at"]) or _is_inbound_landed(r["name"]):
            booked_cogs[i] += amt                 # replaced by the model, not shown
            continue
        a = opex_accts.setdefault(r["name"], {"account": r["name"], "name": r["an"],
                                              "monthly": [0.0] * n, "total": 0.0})
        a["monthly"][i] += amt
        a["total"] += amt

    # ── modelled cost of goods: units that actually shipped × their unit cost ──
    units = frappe.db.sql(
        """SELECT sle.item_code AS ic, DATE_FORMAT(sle.posting_date,'%%Y-%%m') AS ym,
                  SUM(-sle.actual_qty) AS q
           FROM `tabStock Ledger Entry` sle
           WHERE sle.company=%s AND sle.is_cancelled=0 AND sle.voucher_type='Delivery Note'
             AND sle.posting_date BETWEEN %s AND %s
           GROUP BY sle.item_code, ym""", (target, fr, to), as_dict=True)

    model_cogs = [0.0] * n
    tier_val = {0: [0.0] * n, 1: [0.0] * n, 2: [0.0] * n}
    uncovered_qty = [0.0] * n
    for r in units:
        i = idx.get(r["ym"])
        if i is None:
            continue
        q = flt(r["q"])
        c = costs.get(r["ic"])
        if not c:
            uncovered_qty[i] += q
            continue
        v = q * c["cost"]
        model_cogs[i] += v
        tier_val[c["tier"]][i] += v

    # ── the money before tax, and where the tax actually goes ─────────────────
    vat = _vat(target, idx, n, fr, to)

    # ── accrue the recurring costs that simply stopped being billed ────────────
    accruals = _accruals(target, months, opex_accts)

    # Revenue is stated VAT-inclusive on purpose. The VAT charged is not being handed
    # over: an input-VAT credit built up on earlier stock absorbs almost all of it, so
    # only what is genuinely settled in cash is treated as a cost. This is a management
    # view — a statutory statement from the same ledger shows revenue net and a smaller
    # profit, and the two have to be reconciled before either goes outside.
    revenue_net = list(revenue)
    for i in range(n):
        revenue[i] += vat["output"][i]
    opex_accts["__vat__"] = {"account": "__vat__", "name": "VAT settled with the state",
                             "monthly": [flt(v) for v in vat["settled"]],
                             "total": float(sum(vat["settled"]))}

    opex = [0.0] * n
    for a in opex_accts.values():
        for i in range(n):
            opex[i] += a["monthly"][i]
    accrual_total = [sum(x["monthly"][i] for x in accruals) for i in range(n)]

    gross = [revenue[i] - model_cogs[i] for i in range(n)]
    net = [gross[i] - opex[i] - accrual_total[i] for i in range(n)]
    gap = [booked_cogs[i] - model_cogs[i] for i in range(n)]

    # ── restate to USD and fold in the other entities, before anything is grouped ──
    siblings, fxr, sib_cats = [], [1.0] * n, {}
    if group:
        _RATE_CACHE["r"] = _doc_rates(months)
        sib_cats, siblings = _sibling_opex(target, months, target)
        fxr = [_usd_at(ccy, m) for m in months]
        for i in range(n):
            k = fxr[i]
            revenue[i] *= k
            revenue_net[i] *= k
            model_cogs[i] *= k
            booked_cogs[i] *= k
            opex[i] *= k
            accrual_total[i] *= k
            for a in opex_accts.values():
                a["monthly"][i] *= k
            for s2 in vat.values():
                if isinstance(s2, list):
                    s2[i] = round(s2[i] * k)
            opex[i] += sum(c[i] for c in sib_cats.values())
        for a in opex_accts.values():
            a["total"] = sum(a["monthly"])
        for x in accruals:
            x["monthly"] = [round(x["monthly"][i] * fxr[i]) for i in range(n)]
            x["total"] = sum(x["monthly"])
            x["run_rate"] = round(flt(x["run_rate"]) * (fxr[-1] or 1.0))
        for s2 in ("credit_left", "monthly_burn"):
            vat[s2] = round(flt(vat[s2]) * (fxr[-1] or 1.0))
        gross = [revenue[i] - model_cogs[i] for i in range(n)]
        net = [gross[i] - opex[i] - accrual_total[i] for i in range(n)]
        gap = [booked_cogs[i] - model_cogs[i] for i in range(n)]
        ccy = "USD"

    def cov(i):
        tot = sum(tier_val[t][i] for t in (0, 1, 2))
        return round(100.0 * tier_val[0][i] / tot, 1) if tot else 0.0

    # ── one line per idea, not per account: cloud infrastructure filed under a
    #    marketing number reads as advertising until it is grouped by what it is ──
    cats = {}
    for key, arr in sib_cats.items():
        cats[key] = {"account": key, "name": key, "monthly": list(arr),
                     "total": sum(arr), "accounts": [], "cross_entity": True}
    for a in opex_accts.values():
        key = ("VAT settled with the state" if a["account"] == "__vat__"
               else _category(a["account"], a["name"]))
        c = cats.setdefault(key, {"account": key, "name": key,
                                  "monthly": [0.0] * n, "total": 0.0, "accounts": []})
        for i in range(n):
            c["monthly"][i] += a["monthly"][i]
        c["total"] += a["total"]
        c["accounts"].append({"account": a["account"], "name": a["name"],
                              "total": round(a["total"])})
    ol = sorted(cats.values(), key=lambda a: -abs(a["total"]))
    for a in ol:
        a["monthly"] = [round(x) for x in a["monthly"]]
        a["total"] = round(a["total"])
        a["accounts"].sort(key=lambda x: -abs(x["total"]))

    result = {
        "company": target, "currency": ccy, "year": y, "months": months,
        "estimated": True, "scope": "group" if group else "company",
        "siblings": siblings,
        "fx": ({"usd_per_mad": [round(1.0 / v, 4) if v else 0 for v in
                                [_RATE_CACHE["r"][0][m] for m in months]],
                "mad_per_try": [round(_RATE_CACHE["r"][1][m], 4) for m in months],
                "source": "documents posted in each month, not the Currency Exchange table"}
               if group else None),
        "model": meta,
        "vat": vat,
        "revenue": [round(x) for x in revenue],
        "revenue_net": [round(x) for x in revenue_net],
        "vat_included": True,
        "cogs": [round(x) for x in model_cogs],
        "cogs_booked": [round(x) for x in booked_cogs],
        "gap": [round(x) for x in gap],
        "gross": [round(x) for x in gross],
        "opex": [round(x) for x in opex],
        "opex_accounts": ol,
        "accruals": accruals,
        "accrual_total": [round(x) for x in accrual_total],
        "net": [round(x) for x in net],
        "verified_share": [cov(i) for i in range(n)],
        "uncovered_qty": [round(x) for x in uncovered_qty],
        "totals": {
            "revenue": round(sum(revenue)), "cogs": round(sum(model_cogs)),
            "cogs_booked": round(sum(booked_cogs)), "gap": round(sum(gap)),
            "gross": round(sum(gross)), "opex": round(sum(opex)),
            "accruals": round(sum(accrual_total)), "net": round(sum(net)),
            "revenue_net": round(sum(revenue_net)),
            "vat_output": round(sum(vat["output"])),
            "vat_settled": round(sum(vat["settled"])),
            "vat_kept": round(sum(vat["output"]) - sum(vat["settled"])),
            "vat_input": round(sum(vat["input"])),
            "vat_net": round(sum(vat["net"])),
            "gross_pct": round(100.0 * sum(gross) / sum(revenue), 1) if sum(revenue) else 0.0,
            "net_pct": round(100.0 * sum(net) / sum(revenue), 1) if sum(revenue) else 0.0,
        },
    }
    try:
        frappe.cache().set_value(ck, result, expires_in_sec=600)
    except Exception:
        pass
    return result


def _vat(company, idx, n, fr, to):
    """What the customer paid on top, and what of it actually leaves as cash.

    Revenue is booked net, so the gross a customer hands over is invisible in a
    normal P&L. Showing it costs nothing in rigour as long as the VAT is deducted
    right underneath — it is collected for the state, never earned. The part worth
    watching is the last line: almost none of it is being paid in cash, because a
    pre-existing input-VAT credit is absorbing it, and that credit is finite.
    """
    out = [0.0] * n
    inp = [0.0] * n
    for r in frappe.db.sql(
            """SELECT DATE_FORMAT(s.posting_date,'%%Y-%%m') AS ym,
                      SUM(t.base_tax_amount) AS v
               FROM `tabSales Taxes and Charges` t JOIN `tabSales Invoice` s ON s.name=t.parent
               WHERE s.company=%s AND s.docstatus=1 AND t.account_head LIKE '391.%%'
                 AND s.posting_date BETWEEN %s AND %s
               GROUP BY ym""", (company, fr, to), as_dict=True):
        i = idx.get(r["ym"])
        if i is not None:
            out[i] += flt(r["v"])
    for r in frappe.db.sql(
            """SELECT DATE_FORMAT(posting_date,'%%Y-%%m') AS ym, SUM(debit-credit) AS v
               FROM `tabGL Entry` WHERE company=%s AND is_cancelled=0
                 AND account LIKE '191.%%' AND posting_date BETWEEN %s AND %s
               GROUP BY ym""", (company, fr, to), as_dict=True):
        i = idx.get(r["ym"])
        if i is not None:
            inp[i] += flt(r["v"])
    credit = flt(frappe.db.sql(
        """SELECT SUM(debit-credit) FROM `tabGL Entry`
           WHERE company=%s AND is_cancelled=0
             AND (account LIKE '191.%%' OR account LIKE '391.1%%' OR account LIKE '391.6%%')""",
        (company,))[0][0])
    # what is actually settled with the state: a debit to the VAT liability from
    # something that is not a sales or purchase invoice — i.e. a payment or a filing
    settled = [0.0] * n
    for r in frappe.db.sql(
            """SELECT DATE_FORMAT(posting_date,'%%Y-%%m') AS ym, SUM(debit) AS v
               FROM `tabGL Entry` WHERE company=%s AND is_cancelled=0
                 AND account LIKE '391.%%'
                 AND voucher_type NOT IN ('Sales Invoice','Purchase Invoice')
                 AND posting_date BETWEEN %s AND %s
               GROUP BY ym""", (company, fr, to), as_dict=True):
        i = idx.get(r["ym"])
        if i is not None:
            settled[i] += flt(r["v"])
    net = [out[i] - inp[i] for i in range(n)]
    burn = (sum(net) / n) if n else 0.0
    return {
        "output": [round(x) for x in out],
        "input": [round(x) for x in inp],
        "net": [round(x) for x in net],
        "settled": [round(x) for x in settled],
        "kept": round(sum(out) - sum(settled)),
        "credit_left": round(credit),
        "monthly_burn": round(burn),
        "runway_months": round(credit / burn, 1) if burn > 0 else None,
    }


_RECURRING = [
    ("760.%", "Marketing / ads"),
    ("770.07.004%", "Courier (COD delivery)"),
    ("720.%", "Payroll"),
    ("770.001%", "Rent / warehouse"),
]


def _accruals(company, months, opex_accts):
    """Fill the months a recurring stream went quiet with its own median run-rate.

    A bill that has not been entered yet is still a cost of that month; leaving the
    hole makes the month look profitable and the catch-up month look terrible. Only
    streams with a real history qualify, and the current month is never accrued —
    it is simply not finished.
    """
    out = []
    n = len(months)
    for like, label in _RECURRING:
        series = []
        for m in months:
            v = flt(frappe.db.sql(
                """SELECT SUM(debit)-SUM(credit) FROM `tabGL Entry`
                   WHERE company=%s AND is_cancelled=0 AND account LIKE %s
                     AND DATE_FORMAT(posting_date,'%%Y-%%m')=%s""",
                (company, like, m))[0][0])
            series.append(v)
        active = sorted(v for v in series[:-1] if v > 0)
        if len(active) < 4:
            continue
        run_rate = active[len(active) // 2]
        row = [0.0] * n
        hit = False
        for i in range(n - 1):                       # never accrue the running month
            if series[i] < run_rate * 0.35:
                row[i] = round(run_rate - max(series[i], 0.0))
                hit = True
        if hit:
            out.append({"label": label, "account_like": like,
                        "run_rate": round(run_rate), "monthly": row,
                        "total": round(sum(row))})
    return out


@frappe.whitelist()
def model_detail(company=None):
    """How the model is built and how far it can be trusted — shown on the report."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    costs, meta = _unit_costs(target)
    tiers = {0: 0, 1: 0, 2: 0}
    for c in costs.values():
        tiers[c["tier"]] = tiers.get(c["tier"], 0) + 1
    return {
        "company": target,
        "freight_per_kg": FREIGHT_PER_KG,
        "default_weight": DEFAULT_WEIGHT,
        "calibration": meta,
        "tiers": [
            {"tier": 0, "label": "Verified by the team", "items": tiers.get(0, 0)},
            {"tier": 1, "label": "Own supplier invoice", "items": tiers.get(1, 0)},
            {"tier": 2, "label": "Sibling in the same family", "items": tiers.get(2, 0)},
        ],
        "formula": ("(product cost from its own invoice, at that invoice's FX rate)"
                    " + (weight x %.2f MAD/kg sea freight & customs), calibrated x %.4f"
                    % (FREIGHT_PER_KG, meta.get("factor", 1.0))),
    }
