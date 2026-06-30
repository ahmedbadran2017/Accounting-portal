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

from accounting_portal.api.permissions import assert_portal_access, resolve_companies

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
         "variant_of", "country_of_origin", "brand"], as_dict=True)
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
        p["live_fx"] = _live_fx(p["cur"], p["dt"], fxc)
        p["rate_live"] = round(p["rate_fc"] * p["live_fx"], 3) if p["cur"] != "MAD" else p["rate_fc"]
        p["fx_off"] = bool(p["live_fx"] and p["book_fx"] and abs(p["book_fx"] - p["live_fx"]) / p["live_fx"] > _FX_TOL)
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
            "no_cost": not (flt(i.valuation_rate) > 0),
        },
    }


@frappe.whitelist()
def landed_workbench_list(company=None, search=None, scope="purchased",
                          start=0, page_size=25, sort_field="value", sort_dir="desc"):
    """Items to cost, server-paginated. scope: 'purchased' (has a PI line — the
    real cost basis), 'noweight' (missing/implausible weight), 'all'."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {"rows": [], "total": 0}
    from accounting_portal.api import _paginate
    start = int(start or 0); page_size = min(int(page_size or 25), 100)

    if scope == "purchased":
        # one row per item that has been bought, with its latest purchase line.
        conds = ["pi.company=%(c)s", "pi.docstatus=1"]
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

    # scope = noweight / all : straight off the Item master
    conds = ["i.is_stock_item=1"]
    params = {}
    if scope == "noweight":
        conds.append("(IFNULL(i.weight_per_unit,0)=0 OR i.weight_per_unit>%(hi)s OR (i.weight_per_unit>0 AND i.weight_per_unit<%(lo)s))")
        params["hi"] = _WEIGHT_HI; params["lo"] = _WEIGHT_LO
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
