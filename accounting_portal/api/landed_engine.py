"""Landed-cost engine (Phase 1 — analysis only, no writes).

Builds a defensible per-unit landed cost for an item from its real purchase
history, fixing the two things that wreck COGS on the live books:

  1. FX — purchase lines are booked at the conversion_rate stored on the invoice,
     which is frequently wrong (e.g. a USD bill stamped at 42.96 MAD/USD instead
     of ~9.5). We re-price every line at the Currency Exchange rate on the
     invoice's own date and show booked-vs-corrected side by side.
  2. Freight — inbound freight (sea/air) sits in P&L, never capitalised onto the
     product. We allocate it by weight at a per-kg rate (auto-suggested from the
     inbound pool ÷ imported kg, or a manual rate the user types — the way the
     team actually works). Last-mile carrier cargo (Cathadis/Aramex) is excluded;
     that is a distribution expense, not landed cost.

landed unit = product_cost(FX-corrected, weighted avg) + freight_per_kg × weight
            + other capitalisable charges.

Everything here is read/compute only. Writing the result back (valuation rate /
Landed Cost Voucher / correcting entry) is a later phase, behind the write gateway.
"""
import frappe
from frappe.utils import flt

from accounting_portal.api import _actions
from accounting_portal.api.permissions import (
    assert_portal_access, assert_super_admin, resolve_companies)

SET_COST_ACTION = "Set item cost"
BULK_COST_ACTION = "Set item costs (bulk)"

# Inbound, capitalisable freight/customs — but NOT the last-mile carriers, whose
# "cargo fee" is the cost of delivering to the end customer (a selling expense).
_INBOUND = (
    "((a.account_name LIKE '%%Freight%%' OR a.account_name LIKE '%%Sea%%' "
    "  OR a.account_name LIKE '%%Cargo%%' OR a.account_name LIKE '%%Customs%%' "
    "  OR a.account_name LIKE '%%Duty%%' OR a.account_name LIKE '%%Forwarding%%') "
    " AND a.account_name NOT LIKE '%%Cathadis%%' "
    " AND a.account_name NOT LIKE '%%Aramex%%' AND a.account_name NOT LIKE '%%Cash Plus%%')")

_WEIGHT_HI = 20.0     # kg — above this is implausible for this catalogue
_WEIGHT_LO = 0.01     # kg — below this (10 g) is suspiciously light
_FX_TOL = 0.10        # 10% gap between booked and live FX → flag


def _target(company):
    companies = resolve_companies(company)
    if not companies:
        return None
    return company if (company and company in companies) else companies[0]


def _live_fx(cur, date, cache):
    """Currency Exchange rate <cur>→MAD on/just before `date` (1.0 for MAD)."""
    if not cur or cur == "MAD":
        return 1.0
    key = (cur, str(date))
    if key in cache:
        return cache[key]
    r = frappe.db.sql(
        """SELECT exchange_rate FROM `tabCurrency Exchange`
           WHERE from_currency=%s AND to_currency='MAD' AND date<=%s
           ORDER BY date DESC LIMIT 1""", (cur, date))
    v = flt(r[0][0]) if r else 0.0
    cache[key] = v
    return v


def _suggested_freight_per_kg(target):
    pool = frappe.db.sql(
        f"""SELECT SUM(g.debit-g.credit) FROM `tabGL Entry` g JOIN `tabAccount` a ON a.name=g.account
            WHERE g.company=%s AND g.is_cancelled=0 AND {_INBOUND}""", (target,))[0][0]
    kg = frappe.db.sql(
        """SELECT SUM(pii.qty*IFNULL(it.weight_per_unit,0))
           FROM `tabPurchase Invoice Item` pii
           JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
           JOIN `tabItem` it ON it.name=pii.item_code
           WHERE pi.company=%s AND pi.docstatus=1""", (target,))[0][0]
    return round(flt(pool) / flt(kg), 2) if flt(kg) else 0.0


@frappe.whitelist()
def landed_defaults(company=None):
    """Page-level context: currency, the suggested inbound freight rate, and how
    much of the catalogue actually has a purchase cost basis."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    currency = frappe.db.get_value("Company", target, "default_currency") or "MAD"
    purchased = frappe.db.sql(
        """SELECT COUNT(DISTINCT pii.item_code) FROM `tabPurchase Invoice Item` pii
           JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
           WHERE pi.company=%s AND pi.docstatus=1""", (target,))[0][0]
    catalogue = frappe.db.count("Item")
    return {
        "company": target, "currency": currency,
        "suggested_freight_per_kg": _suggested_freight_per_kg(target),
        "purchased_items": int(purchased or 0), "catalogue_items": int(catalogue or 0),
    }


def _sell_price(item_code, target):
    sp = frappe.db.sql(
        """SELECT MAX(ip.price_list_rate) FROM `tabItem Price` ip
           WHERE ip.item_code=%s AND ip.selling=1""", (item_code,))[0][0]
    if flt(sp):
        return flt(sp), "price list"
    avg = frappe.db.sql(
        """SELECT AVG(base_net_rate) FROM `tabSales Order Item`
           WHERE item_code=%s AND docstatus=1 AND base_net_rate>0""", (item_code,))[0][0]
    return flt(avg), "avg sold"


@frappe.whitelist()
def item_landed_cost(company=None, item_code=None, freight_per_kg=None, fx_mode="live"):
    """Full landed-cost breakdown for one item. fx_mode: 'live' uses the corrected
    Currency-Exchange rate per invoice date; 'book' uses what's posted in the GL."""
    assert_portal_access()
    target = _target(company)
    if not target or not item_code:
        return {}
    i = frappe.db.get_value(
        "Item", item_code,
        ["name", "item_name", "custom_sku", "image", "item_group", "stock_uom",
         "weight_per_unit", "weight_uom", "valuation_rate", "last_purchase_rate",
         "variant_of", "country_of_origin", "brand", "is_stock_item"], as_dict=True)
    if not i:
        frappe.throw("Item not found")
    weight = flt(i.weight_per_unit)
    currency = frappe.db.get_value("Company", target, "default_currency") or "MAD"

    purchases = frappe.db.sql(
        """SELECT pi.name AS doc, pi.supplier, pi.currency AS cur, pi.posting_date AS dt,
                  pi.conversion_rate AS book_fx, pii.qty,
                  pii.rate AS rate_fc, pii.base_rate AS rate_book
           FROM `tabPurchase Invoice Item` pii JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
           WHERE pii.item_code=%s AND pi.company=%s AND pi.docstatus=1
           ORDER BY pi.posting_date DESC LIMIT 20""", (item_code, target), as_dict=True)

    fxc = {}
    tot_qty = tot_book = tot_live = 0.0
    fx_flag = False
    for p in purchases:
        p["rate_fc"] = flt(p["rate_fc"]); p["rate_book"] = flt(p["rate_book"]); p["qty"] = flt(p["qty"])
        p["book_fx"] = flt(p["book_fx"])
        lf = _live_fx(p["cur"], p["dt"], fxc)
        p["live_fx"] = lf
        # Only correct when we actually have a live rate for this currency. With no
        # Currency Exchange record (lf=0 — e.g. TRY→MAD isn't maintained), keep the
        # booked rate rather than zeroing the cost; flag it as unverifiable instead.
        if p["cur"] == "MAD" or lf <= 0:
            p["rate_live"] = p["rate_book"]
            p["fx_off"] = False
            p["fx_unverified"] = p["cur"] != "MAD" and lf <= 0
        else:
            p["rate_live"] = round(p["rate_fc"] * lf, 3)
            p["fx_off"] = bool(p["book_fx"] and abs(p["book_fx"] - lf) / lf > _FX_TOL)
            p["fx_unverified"] = False
        fx_flag = fx_flag or p["fx_off"]
        tot_qty += p["qty"]; tot_book += p["rate_book"] * p["qty"]; tot_live += p["rate_live"] * p["qty"]
        p["dt"] = str(p["dt"])

    wavg_book = round(tot_book / tot_qty, 3) if tot_qty else flt(i.last_purchase_rate)
    wavg_live = round(tot_live / tot_qty, 3) if tot_qty else flt(i.last_purchase_rate)
    product_cost = wavg_live if fx_mode == "live" else wavg_book

    fpk = flt(freight_per_kg) if freight_per_kg not in (None, "") else _suggested_freight_per_kg(target)
    freight_unit = round(fpk * weight, 3)
    landed = round(product_cost + freight_unit, 3)

    sell, sell_src = _sell_price(item_code, target)
    margin = round(sell - landed, 2) if sell else 0.0

    return {
        "company": target, "currency": currency,
        "item_code": i.name, "item_name": i.item_name, "sku": i.custom_sku, "image": i.image,
        "item_group": i.item_group, "uom": i.stock_uom, "brand": i.brand,
        "variant_of": i.variant_of, "country": i.country_of_origin,
        "weight": weight, "weight_uom": i.weight_uom or "Kg",
        "valuation_rate": flt(i.valuation_rate), "last_purchase_rate": flt(i.last_purchase_rate),
        "purchases": purchases,
        "wavg_book": wavg_book, "wavg_live": wavg_live, "fx_mode": fx_mode,
        "freight_per_kg": fpk, "suggested_freight_per_kg": _suggested_freight_per_kg(target),
        "product_cost": round(product_cost, 3), "freight_unit": freight_unit, "landed": landed,
        "sell": round(sell, 2), "sell_src": sell_src,
        "margin": margin, "margin_pct": round(margin / sell * 100, 1) if sell else 0.0,
        "breakdown": [
            {"k": "product", "v": round(product_cost, 2)},
            {"k": "freight", "v": freight_unit},
        ],
        "flags": {
            "no_weight": weight <= 0,
            "weight_outlier": weight > _WEIGHT_HI or (0 < weight < _WEIGHT_LO),
            "no_purchase": not purchases,
            "fx_off": fx_flag,
            "fx_unverified": any(p.get("fx_unverified") for p in purchases),
            "no_cost": not (flt(i.valuation_rate) > 0),
            "not_stock": not int(i.is_stock_item or 0),
        },
    }


@frappe.whitelist()
def costing_health(company=None):
    """Read-only costing data-quality cockpit: weight gaps, FX anomalies (with the
    COGS overstatement they cause), catalogue coverage, and the un-capitalised
    inbound freight pool. Surfaces exactly what corrupts COGS before any fix."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    currency = frappe.db.get_value("Company", target, "default_currency") or "MAD"

    w = frappe.db.sql(
        """SELECT COUNT(*) n, SUM(IFNULL(weight_per_unit,0)=0) missing,
                  SUM(weight_per_unit>%s) heavy, SUM(weight_per_unit>0 AND weight_per_unit<%s) light
           FROM `tabItem` WHERE is_stock_item=1""", (_WEIGHT_HI, _WEIGHT_LO), as_dict=True)[0]
    worst_groups = frappe.db.sql(
        """SELECT item_group g, COUNT(*) n, SUM(IFNULL(weight_per_unit,0)=0) missing
           FROM `tabItem` WHERE is_stock_item=1 GROUP BY item_group
           HAVING missing>0 ORDER BY missing DESC LIMIT 6""", as_dict=True)

    purchased = frappe.db.sql(
        """SELECT COUNT(DISTINCT pii.item_code) FROM `tabPurchase Invoice Item` pii
           JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
           WHERE pi.company=%s AND pi.docstatus=1""", (target,))[0][0]
    catalogue = frappe.db.count("Item", {"is_stock_item": 1})
    costed = frappe.db.count("Item", {"is_stock_item": 1, "valuation_rate": [">", 0]})

    # FX anomalies — only the foreign invoices, re-priced at the live rate.
    fxc = {}
    foreign = frappe.db.sql(
        """SELECT pi.name doc, pi.currency cur, pi.posting_date dt, pi.conversion_rate book_fx,
                  ROUND(SUM(pii.base_amount)) booked, SUM(pii.amount) amt_fc
           FROM `tabPurchase Invoice Item` pii JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
           WHERE pi.company=%s AND pi.docstatus=1 AND pi.currency!='MAD'
           GROUP BY pi.name ORDER BY pi.posting_date DESC""", (target,), as_dict=True)
    wrong, unverified, overstate = [], [], 0.0
    for r in foreign:
        lf = _live_fx(r["cur"], r["dt"], fxc)
        if lf <= 0:
            unverified.append({"doc": r["doc"], "cur": r["cur"], "booked": flt(r["booked"])})
            continue
        corrected = flt(r["amt_fc"]) * lf
        if flt(r["book_fx"]) and abs(flt(r["book_fx"]) - lf) / lf > _FX_TOL:
            over = flt(r["booked"]) - corrected
            overstate += over
            wrong.append({"doc": r["doc"], "cur": r["cur"], "book_fx": round(flt(r["book_fx"]), 3),
                          "live_fx": lf, "booked": round(flt(r["booked"])), "corrected": round(corrected),
                          "overstatement": round(over), "date": str(r["dt"])})
    wrong.sort(key=lambda x: -x["overstatement"])

    pool = frappe.db.sql(
        f"""SELECT a.account_name nm, ROUND(SUM(g.debit-g.credit)) bal FROM `tabGL Entry` g
            JOIN `tabAccount` a ON a.name=g.account
            WHERE g.company=%s AND g.is_cancelled=0 AND {_INBOUND}
            GROUP BY a.account_name HAVING ABS(SUM(g.debit-g.credit))>0
            ORDER BY ABS(SUM(g.debit-g.credit)) DESC LIMIT 10""", (target,), as_dict=True)
    for p in pool:
        p["bal"] = flt(p["bal"])

    return {
        "company": target, "currency": currency,
        "weight": {"total": int(w.n or 0), "missing": int(w.missing or 0),
                   "heavy": int(w.heavy or 0), "light": int(w.light or 0),
                   "worst_groups": [{"group": g.g, "items": g.n, "missing": int(g.missing or 0)} for g in worst_groups]},
        "coverage": {"catalogue": int(catalogue or 0), "purchased": int(purchased or 0), "costed": int(costed or 0)},
        "fx": {"foreign_invoices": len(foreign), "wrong": wrong, "unverified": unverified,
               "overstatement": round(overstate)},
        "freight": {"accounts": pool, "pool": round(sum(p["bal"] for p in pool)),
                    "suggested_per_kg": _suggested_freight_per_kg(target)},
    }


@frappe.whitelist()
def landed_workbench_list(company=None, search=None, scope="purchased",
                          from_date=None, to_date=None,
                          start=0, page_size=25, sort_field="value", sort_dir="desc"):
    """Items to cost, server-paginated. scope: 'purchased' (has a PI line — the real
    cost basis), 'noweight' (zero weight), 'outliers' (implausible weight), 'all'.
    from_date/to_date scope to items sold in that range (the cohort workflow)."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {"rows": [], "total": 0}
    from accounting_portal.api import _paginate
    start = int(start or 0); page_size = min(int(page_size or 25), 100)

    if scope == "purchased":
        # one row per *stock* item that has been bought, with its latest purchase line.
        # Service/freight lines (e.g. a logistics invoice) are excluded — their
        # lump-sum "unit cost" is not a product cost and would mislead.
        conds = ["pi.company=%(c)s", "pi.docstatus=1", "i.is_stock_item=1"]
        params = {"c": target}
        if search:
            conds.append("(pii.item_code LIKE %(s)s OR i.item_name LIKE %(s)s OR IFNULL(i.custom_sku,'') LIKE %(s)s)")
            params["s"] = f"%{search}%"
        sort = {"value": "spent", "weight": "i.weight_per_unit", "code": "pii.item_code"}
        col = sort.get(sort_field, "spent")
        d = "ASC" if str(sort_dir).lower() == "asc" else "DESC"
        rows, total, s, ps = _paginate.page_query(
            "`tabPurchase Invoice Item` pii "
            "JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent "
            "LEFT JOIN `tabItem` i ON i.name=pii.item_code",
            " AND ".join(conds), params,
            "pii.item_code AS item_code, MAX(i.item_name) AS item_name, MAX(i.custom_sku) AS sku, "
            "MAX(i.image) AS image, MAX(i.weight_per_unit) AS weight, "
            "SUM(pii.qty) AS qty, ROUND(SUM(pii.base_amount)) AS spent, "
            "SUBSTRING_INDEX(GROUP_CONCAT(pi.currency ORDER BY pi.posting_date DESC),',',1) AS cur, "
            "ROUND(SUBSTRING_INDEX(GROUP_CONCAT(pii.rate ORDER BY pi.posting_date DESC),',',1),3) AS last_rate_fc, "
            "MAX(pi.posting_date) AS last_dt",
            f"{col} {d}", start, page_size, group_by="pii.item_code")
        for r in rows:
            w = flt(r.get("weight"))
            r["weight"] = w
            r["no_weight"] = w <= 0
            r["weight_outlier"] = w > _WEIGHT_HI or (0 < w < _WEIGHT_LO)
            r["last_dt"] = str(r.get("last_dt") or "")[:10]
        return {"rows": rows, "total": total, "start": s, "page_size": ps}

    # scope = noweight / outliers / all : straight off the Item master, optionally
    # scoped to items active (sold) in a date range — the cohort-by-period workflow.
    conds = ["i.is_stock_item=1"]
    params = {}
    if scope == "noweight":
        conds.append("IFNULL(i.weight_per_unit,0)=0")
    elif scope == "outliers":
        conds.append("(i.weight_per_unit>%(hi)s OR (i.weight_per_unit>0 AND i.weight_per_unit<%(lo)s))")
        params["hi"] = _WEIGHT_HI; params["lo"] = _WEIGHT_LO
    if from_date or to_date:
        dc = ["soi.item_code=i.name", "so.company=%(c)s", "so.docstatus=1"]
        params["c"] = target
        if from_date:
            dc.append("so.transaction_date>=%(fd)s"); params["fd"] = from_date
        if to_date:
            dc.append("so.transaction_date<=%(td)s"); params["td"] = to_date
        conds.append("EXISTS(SELECT 1 FROM `tabSales Order Item` soi "
                     "JOIN `tabSales Order` so ON so.name=soi.parent WHERE " + " AND ".join(dc) + ")")
    if search:
        conds.append("(i.name LIKE %(s)s OR i.item_name LIKE %(s)s OR IFNULL(i.custom_sku,'') LIKE %(s)s)")
        params["s"] = f"%{search}%"
    d = "ASC" if str(sort_dir).lower() == "asc" else "DESC"
    rows, total, s, ps = _paginate.page_query(
        "`tabItem` i", " AND ".join(conds), params,
        "i.name AS item_code, i.item_name, i.custom_sku AS sku, i.image, "
        "i.weight_per_unit AS weight, i.valuation_rate AS cost, i.last_purchase_rate AS last_rate_fc",
        f"i.weight_per_unit {d}", start, page_size)
    for r in rows:
        w = flt(r.get("weight"))
        r["weight"] = w
        r["no_weight"] = w <= 0
        r["weight_outlier"] = w > _WEIGHT_HI or (0 < w < _WEIGHT_LO)
    return {"rows": rows, "total": total, "start": s, "page_size": ps}


@frappe.whitelist()
def set_item_cost(company=None, item_code=None, cost=None, dry_run=1):
    """Write a computed landed cost back as the item's valuation_rate (the standard
    cost reference). Super-admin only; routed through the write gateway for the
    audit trail; reversible (the prior value is captured). Master-data only — it
    does NOT post a GL correction for historical stock; that is a later phase that
    needs the target accounts confirmed."""
    assert_super_admin()
    target = _target(company)
    if not target or not item_code:
        frappe.throw("Item required")
    if not frappe.db.exists("Item", item_code):
        frappe.throw("Item not found")
    cost = flt(cost)
    if cost <= 0:
        frappe.throw("Cost must be positive")
    old = flt(frappe.db.get_value("Item", item_code, "valuation_rate"))
    preview = {"item_code": item_code, "old": old, "new": round(cost, 2)}
    if int(dry_run or 0):
        return {"dry_run": True, **preview}
    key = f"set_cost:{target}:{item_code}:{round(cost, 2)}"
    res = _actions.execute(
        SET_COST_ACTION, target, key,
        payload={"item_code": item_code, "cost": round(cost, 4), "old": old},
        amount=cost, notes=f"Set {item_code} valuation_rate {old:g} -> {cost:g}")
    return {"dry_run": False, **preview, "result": res}


def _set_cost_poster(action):
    """Set Item.valuation_rate to the proposed cost (master data)."""
    import json
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    item_code, cost = p.get("item_code"), flt(p.get("cost"))
    if item_code and cost > 0:
        frappe.db.set_value("Item", item_code, {"valuation_rate": cost}, update_modified=True)
    return {"voucher_type": "Item", "voucher_no": item_code, "result": "cost set"}


_actions.register_poster(SET_COST_ACTION, _set_cost_poster)


def _bulk_corrected_costs(target, include_freight):
    """For every purchased item, the FX-corrected weighted-average unit cost (plus
    optional freight/kg). Used by the bulk write-back."""
    lines = frappe.db.sql(
        """SELECT pii.item_code ic, pi.currency cur, pi.posting_date dt,
                  pii.qty, pii.rate rate_fc, pii.base_rate rate_book
           FROM `tabPurchase Invoice Item` pii
           JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
           JOIN `tabItem` it ON it.name=pii.item_code AND it.is_stock_item=1
           WHERE pi.company=%s AND pi.docstatus=1 AND IFNULL(pii.item_code,'')!=''""",
        (target,), as_dict=True)
    fxc, agg = {}, {}
    for ln in lines:
        lf = _live_fx(ln.cur, ln.dt, fxc)
        rate = flt(ln.rate_fc) * lf if (ln.cur != "MAD" and lf > 0) else flt(ln.rate_book)
        a = agg.setdefault(ln.ic, [0.0, 0.0])
        a[0] += flt(ln.qty); a[1] += rate * flt(ln.qty)
    fpk = _suggested_freight_per_kg(target) if int(include_freight or 0) else 0.0
    weights = {}
    if agg and fpk:
        for r in frappe.db.sql(
                "SELECT name, weight_per_unit w FROM `tabItem` WHERE name IN %(it)s",
                {"it": tuple(agg.keys())}, as_dict=True):
            weights[r.name] = flt(r.w)
    out = []
    for ic, (q, c) in agg.items():
        if q <= 0:
            continue
        cost = c / q + (fpk * weights.get(ic, 0.0) if fpk else 0.0)
        if cost > 0:
            out.append({"item": ic, "cost": round(cost, 4)})
    return out


@frappe.whitelist()
def set_item_costs_bulk(company=None, include_freight=0, dry_run=1):
    """Establish valuation_rate for every purchased item at once from its FX-corrected
    weighted-average purchase cost (optionally + inbound freight/kg). Super-admin only;
    one audited, reversible write-gateway action; master-data only (no GL). Most of
    these items currently have no cost at all — this gives COGS a real basis."""
    assert_super_admin()
    target = _target(company)
    if not target:
        frappe.throw("No company in scope")
    pairs = _bulk_corrected_costs(target, include_freight)
    total = round(sum(p["cost"] for p in pairs))
    # sample with current value for the preview
    sample = []
    for p in pairs[:12]:
        old = flt(frappe.db.get_value("Item", p["item"], "valuation_rate"))
        nm = frappe.db.get_value("Item", p["item"], "item_name")
        sample.append({"item": p["item"], "name": nm, "old": old, "new": p["cost"]})
    preview = {"count": len(pairs), "total": total, "include_freight": int(include_freight or 0), "sample": sample}
    if int(dry_run or 0):
        return {"dry_run": True, **preview}
    if not pairs:
        return {"dry_run": False, "count": 0}
    # capture prior valuation in one query so the action is reversible (undo)
    old_map = {r.name: flt(r.valuation_rate) for r in frappe.db.sql(
        "SELECT name, valuation_rate FROM `tabItem` WHERE name IN %(it)s",
        {"it": tuple(p["item"] for p in pairs)}, as_dict=True)}
    for p in pairs:
        p["old"] = old_map.get(p["item"], 0.0)
    key = f"bulk_cost:{target}:{len(pairs)}:{total}:{int(include_freight or 0)}"
    res = _actions.execute(
        BULK_COST_ACTION, target, key,
        payload={"pairs": pairs},
        amount=total, notes=f"Set valuation_rate on {len(pairs)} items (freight={int(include_freight or 0)})")
    return {"dry_run": False, **preview, "result": res}


def _bulk_cost_poster(action):
    import json
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    done = 0
    for it in (p.get("pairs") or []):
        ic, cost = it.get("item"), flt(it.get("cost"))
        if ic and cost > 0 and frappe.db.exists("Item", ic):
            frappe.db.set_value("Item", ic, {"valuation_rate": cost}, update_modified=True)
            done += 1
    return {"voucher_type": "Item", "voucher_no": f"{done} items costed", "result": "bulk cost set"}


def _restore_field(action, doctype, field):
    """Generic reverter: restore <field> to the 'old' captured per pair."""
    import json
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    done = 0
    for it in (p.get("pairs") or []):
        ic = it.get("item")
        if ic and "old" in it and frappe.db.exists(doctype, ic):
            frappe.db.set_value(doctype, ic, {field: flt(it.get("old"))}, update_modified=True)
            done += 1
    return {"restored": done, "field": field}


def _set_cost_reverter(action):
    import json
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    ic = p.get("item_code")
    if ic and frappe.db.exists("Item", ic):
        frappe.db.set_value("Item", ic, {"valuation_rate": flt(p.get("old"))}, update_modified=True)
        return {"restored": 1, "item": ic}
    return {"restored": 0}


_actions.register_poster(BULK_COST_ACTION, _bulk_cost_poster)
_actions.register_reverter(BULK_COST_ACTION, lambda a: _restore_field(a, "Item", "valuation_rate"))
_actions.register_reverter(SET_COST_ACTION, _set_cost_reverter)


WEIGHT_FIX_ACTION = "Fix weight units"


def _weight_unit_suspects(target, from_date=None, to_date=None):
    """Stock items whose weight is implausibly high (>_WEIGHT_HI kg) — almost always
    grams typed into the kg field. Optionally scoped to items sold in a date range.
    Returns {item, name, old, new} where new = old/1000."""
    conds = ["i.is_stock_item=1", "i.weight_per_unit>%(hi)s"]
    params = {"hi": _WEIGHT_HI}
    if from_date or to_date:
        dc = ["soi.item_code=i.name", "so.company=%(c)s", "so.docstatus=1"]
        params["c"] = target
        if from_date:
            dc.append("so.transaction_date>=%(fd)s"); params["fd"] = from_date
        if to_date:
            dc.append("so.transaction_date<=%(td)s"); params["td"] = to_date
        conds.append("EXISTS(SELECT 1 FROM `tabSales Order Item` soi "
                     "JOIN `tabSales Order` so ON so.name=soi.parent WHERE " + " AND ".join(dc) + ")")
    rows = frappe.db.sql(
        f"""SELECT i.name AS item, i.item_name AS name, i.weight_per_unit AS old
            FROM `tabItem` i WHERE {' AND '.join(conds)}
            ORDER BY i.weight_per_unit DESC""", params, as_dict=True)
    out = []
    for r in rows:
        old = flt(r["old"])
        new = round(old / 1000.0, 4)
        # only propose where the /1000 result is itself sensible (<_WEIGHT_HI)
        if 0 < new < _WEIGHT_HI:
            out.append({"item": r["item"], "name": r["name"], "old": old, "new": new})
    return out


@frappe.whitelist()
def fix_weight_units(company=None, from_date=None, to_date=None, dry_run=1):
    """Bulk-correct grams-entered-as-kg: divide weight by 1000 for stock items whose
    weight is implausibly high. Optionally scope to items sold in a date range (clean
    up cohort by cohort, e.g. one year at a time). Super-admin only; one audited,
    reversible write-gateway action; master-data only."""
    assert_super_admin()
    target = _target(company)
    if not target:
        frappe.throw("No company in scope")
    suspects = _weight_unit_suspects(target, from_date, to_date)
    preview = {"count": len(suspects), "sample": suspects[:15]}
    if int(dry_run or 0):
        return {"dry_run": True, **preview}
    if not suspects:
        return {"dry_run": False, "count": 0}
    key = f"fix_weight:{target}:{from_date or ''}:{to_date or ''}:{len(suspects)}"
    res = _actions.execute(
        WEIGHT_FIX_ACTION, target, key,
        payload={"pairs": [{"item": s["item"], "new": s["new"], "old": s["old"]} for s in suspects]},
        amount=len(suspects), notes=f"grams→kg on {len(suspects)} items ({from_date or 'all'}..{to_date or 'all'})")
    return {"dry_run": False, **preview, "result": res}


def _weight_fix_poster(action):
    import json
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    done = 0
    for it in (p.get("pairs") or []):
        ic, new = it.get("item"), flt(it.get("new"))
        if ic and new > 0 and frappe.db.exists("Item", ic):
            frappe.db.set_value("Item", ic, {"weight_per_unit": new}, update_modified=True)
            done += 1
    return {"voucher_type": "Item", "voucher_no": f"{done} weights fixed", "result": "weight units fixed"}


_actions.register_poster(WEIGHT_FIX_ACTION, _weight_fix_poster)
_actions.register_reverter(WEIGHT_FIX_ACTION, lambda a: _restore_field(a, "Item", "weight_per_unit"))
