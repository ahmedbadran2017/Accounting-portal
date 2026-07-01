"""Items & margin, price lists, and landed-cost vouchers — live.

Stock valuation on the live books is broken (valuation_rate = 0, perpetual stock
not relieving to COGS), so unit cost falls back to last_purchase_rate. Selling
prices live in Shopify / Sales Orders, so per-item margin uses the recent average
sold rate, not a MAD selling price list (there isn't one).
"""
import frappe

from accounting_portal.api.permissions import assert_can_write, assert_portal_access, resolve_companies

# Cost: prefer a real valuation, fall back to last purchase (valuation is 0 on the
# broken books), then 0.
_COST = "COALESCE(NULLIF(i.valuation_rate,0), NULLIF(i.last_purchase_rate,0), 0)"

# Carrier COD collection fee as a fraction of the sold price — modeled (Cathedis
# doesn't post a per-item fee to the GL). Overridable per call.
_DEFAULT_COD_RATE = 0.05


@frappe.whitelist()
def item_groups():
    """Item groups for the filter (leaf groups that actually carry items)."""
    assert_portal_access()
    return [r.item_group for r in frappe.db.sql(
        """SELECT DISTINCT item_group FROM `tabItem` WHERE IFNULL(item_group,'')!=''
           ORDER BY item_group LIMIT 200""", as_dict=True)]


def _sold_rank(top=400):
    """Cached map item_code → sales rank (0 = best-seller). The group-by over all
    Sales Order Items is heavy (~3.5s), so it's cached for 30 min; used to order
    the default Items view by selling volume."""
    ck = "ap_item_sold_rank"
    cached = frappe.cache().get_value(ck)
    if cached is not None:
        return cached
    rows = frappe.db.sql(
        """SELECT item_code FROM `tabSales Order Item` WHERE docstatus=1
           GROUP BY item_code ORDER BY SUM(qty) DESC LIMIT %s""", (int(top),), as_dict=True)
    rank = {r.item_code: i for i, r in enumerate(rows)}
    frappe.cache().set_value(ck, rank, expires_in_sec=1800)
    return rank


@frappe.whitelist()
def list_items(company=None, search=None, group=None, limit=60, cod_rate=None):
    """Items with cost, stock, recent sold price and TRUE margin.

    True margin = avg sold − cost − landed/unit − COD fee, then discounted by the
    real RTO (return) rate. Landed/unit and RTO are real (from LCV allocations and
    returned orders); the COD fee is a modeled % of the sold price.
    """
    assert_portal_access()
    cod_rate = float(cod_rate) if cod_rate not in (None, "") else _DEFAULT_COD_RATE
    limit = min(int(limit or 60), 200)
    ck = f"ap_items:{search or ''}:{group or ''}:{limit}:{cod_rate}"
    cached_hit = frappe.cache().get_value(ck)
    if cached_hit is not None:
        return cached_hit
    _cols = f"""i.name AS item_code, i.item_name, i.custom_sku AS sku, i.image,
                i.item_group, {_COST} AS cost, i.stock_uom"""
    # Default view (no filter): show best-sellers first so the margin table is
    # meaningful up top. Filtered/search: most-recent first.
    rank = _sold_rank() if not (search or group) else None
    if rank:
        ranked = sorted(rank.keys(), key=lambda k: rank[k])[:limit]
        rows = frappe.db.sql(
            f"SELECT {_cols} FROM `tabItem` i WHERE i.disabled=0 AND i.name IN %(codes)s",
            {"codes": tuple(ranked)}, as_dict=True) if ranked else []
        rows.sort(key=lambda r: rank.get(r["item_code"], 1 << 30))
    else:
        conds = ["i.disabled=0"]
        params = {"limit": limit}
        if search:
            conds.append("(i.name LIKE %(s)s OR i.item_name LIKE %(s)s OR IFNULL(i.custom_sku,'') LIKE %(s)s)")
            params["s"] = f"%{search}%"
        if group:
            conds.append("i.item_group=%(g)s"); params["g"] = group
        rows = frappe.db.sql(
            f"SELECT {_cols} FROM `tabItem` i WHERE {' AND '.join(conds)} "
            f"ORDER BY i.modified DESC LIMIT %(limit)s", params, as_dict=True)
    codes = [r["item_code"] for r in rows]
    sold, stock, landed, returned = {}, {}, {}, {}
    if codes:
        for r in frappe.db.sql(
                """SELECT soi.item_code, AVG(soi.base_net_rate) AS avg_sold, SUM(soi.qty) AS qty_sold
                   FROM `tabSales Order Item` soi WHERE soi.item_code IN %(c)s AND soi.docstatus=1
                   GROUP BY soi.item_code""", {"c": codes}, as_dict=True):
            sold[r.item_code] = r
        for r in frappe.db.sql(
                """SELECT item_code, SUM(actual_qty) AS qty FROM `tabStock Ledger Entry`
                   WHERE item_code IN %(c)s AND is_cancelled=0 GROUP BY item_code""",
                {"c": codes}, as_dict=True):
            stock[r.item_code] = r.qty
        # Real landed cost per unit — applicable charges ÷ qty from LCV allocations.
        for r in frappe.db.sql(
                """SELECT item_code, SUM(applicable_charges) AS chg, SUM(qty) AS qty
                   FROM `tabLanded Cost Item` WHERE item_code IN %(c)s GROUP BY item_code HAVING qty>0""",
                {"c": codes}, as_dict=True):
            landed[r.item_code] = float(r.chg or 0) / float(r.qty)
        # Real RTO rate — qty on returned/exception orders ÷ total ordered qty.
        for r in frappe.db.sql(
                """SELECT soi.item_code, SUM(soi.qty) AS ret_qty
                   FROM `tabSales Order Item` soi JOIN `tabSales Order` so ON so.name=soi.parent
                   WHERE soi.item_code IN %(c)s AND so.docstatus=1
                     AND (so.custom_sales_status='Returned' OR so.custom_logistics_status='Returned'
                          OR so.custom_track_shipment_status IN ('Delivery Exception','Failed Attempt'))
                   GROUP BY soi.item_code""", {"c": codes}, as_dict=True):
            returned[r.item_code] = float(r.ret_qty or 0)
    for r in rows:
        s = sold.get(r["item_code"])
        r["avg_sold"] = round(float(s.avg_sold), 2) if (s and s.avg_sold) else 0
        r["qty_sold"] = float(s.qty_sold) if (s and s.qty_sold) else 0
        r["stock_qty"] = round(float(stock.get(r["item_code"], 0)), 1)
        r["cost"] = round(float(r["cost"]), 2)
        r["landed"] = round(landed.get(r["item_code"], 0), 2)
        r["cod_fee"] = round(r["avg_sold"] * cod_rate, 2) if r["avg_sold"] else 0
        r["rto_pct"] = round(returned.get(r["item_code"], 0) / r["qty_sold"] * 100, 1) if r["qty_sold"] else 0
        # Gross (sell − cost) and true (− landed − COD, discounted by RTO).
        r["margin"] = round(r["avg_sold"] - r["cost"], 2) if r["avg_sold"] else 0
        r["margin_pct"] = round(r["margin"] / r["avg_sold"] * 100, 1) if r["avg_sold"] else 0
        base = r["avg_sold"] - r["cost"] - r["landed"] - r["cod_fee"] if r["avg_sold"] else 0
        r["true_margin"] = round(base * (1 - r["rto_pct"] / 100), 2) if r["avg_sold"] else 0
        r["true_margin_pct"] = round(r["true_margin"] / r["avg_sold"] * 100, 1) if r["avg_sold"] else 0
    try:
        frappe.cache().set_value(ck, rows, expires_in_sec=600)
    except Exception:
        pass
    return rows


@frappe.whitelist()
def item_options(search=None, limit=15):
    """Item search for pickers — by SKU, code or name."""
    assert_portal_access()
    like = f"%{(search or '').strip()}%"
    return frappe.db.sql(
        """SELECT name AS item_code, item_name, custom_sku AS sku FROM `tabItem`
           WHERE disabled=0 AND (name LIKE %s OR item_name LIKE %s OR IFNULL(custom_sku,'') LIKE %s)
           ORDER BY modified DESC LIMIT %s""",
        (like, like, like, min(int(limit or 15), 30)), as_dict=True)


@frappe.whitelist()
def set_item_price(item_code=None, price_list=None, rate=None):
    """Create or update an Item Price (e.g. set a Morocco MAD selling price).
    Master data — gated by write capability, not the GL approval flow."""
    assert_can_write()
    if not (item_code and price_list):
        frappe.throw("Item and price list are required")
    if not frappe.db.exists("Item", item_code):
        frappe.throw("Item not found")
    pl = frappe.db.get_value("Price List", price_list, ["name", "selling", "buying"], as_dict=True)
    if not pl:
        frappe.throw("Price list not found")
    rate = frappe.utils.flt(rate)
    if rate <= 0:
        frappe.throw("Rate must be positive")
    existing = frappe.db.get_value("Item Price", {"item_code": item_code, "price_list": price_list}, "name")
    if existing:
        doc = frappe.get_doc("Item Price", existing)
        doc.price_list_rate = rate
        doc.save(ignore_permissions=True)
        return {"name": doc.name, "updated": True, "rate": rate}
    doc = frappe.get_doc({
        "doctype": "Item Price", "item_code": item_code, "price_list": price_list,
        "price_list_rate": rate, "selling": pl.selling, "buying": pl.buying,
    })
    doc.insert(ignore_permissions=True)
    return {"name": doc.name, "updated": False, "rate": rate}


@frappe.whitelist()
def get_item(item_code=None):
    """One item: cost, stock, prices across every price list, recent purchases,
    recent sales, and landed cost applied to it."""
    assert_portal_access()
    i = frappe.db.get_value(
        "Item", item_code,
        ["name", "item_name", "custom_sku", "image", "item_group", "stock_uom",
         "valuation_rate", "last_purchase_rate", "standard_rate", "brand"], as_dict=True)
    if not i:
        frappe.throw("Item not found")
    cost = float(i.valuation_rate or 0) or float(i.last_purchase_rate or 0)
    prices = frappe.db.sql(
        """SELECT ip.price_list, pl.currency, ip.price_list_rate AS rate, ip.selling, ip.buying
           FROM `tabItem Price` ip JOIN `tabPrice List` pl ON pl.name=ip.price_list
           WHERE ip.item_code=%s ORDER BY ip.selling DESC, ip.price_list""", (item_code,), as_dict=True)
    stock = frappe.db.sql(
        """SELECT warehouse, SUM(actual_qty) AS qty, SUM(stock_value_difference) AS val
           FROM `tabStock Ledger Entry` WHERE item_code=%s AND is_cancelled=0
           GROUP BY warehouse HAVING qty<>0""", (item_code,), as_dict=True)
    purchases = frappe.db.sql(
        """SELECT poi.parent AS doc, po.supplier, poi.qty, poi.base_rate AS rate, po.transaction_date AS date
           FROM `tabPurchase Order Item` poi JOIN `tabPurchase Order` po ON po.name=poi.parent
           WHERE poi.item_code=%s AND po.docstatus=1 ORDER BY po.transaction_date DESC LIMIT 5""",
        (item_code,), as_dict=True)
    sales = frappe.db.sql(
        """SELECT AVG(base_net_rate) AS avg_rate, SUM(qty) AS qty, COUNT(DISTINCT parent) AS orders
           FROM `tabSales Order Item` WHERE item_code=%s AND docstatus=1""", (item_code,), as_dict=True)[0]
    landed = frappe.db.sql(
        """SELECT parent AS voucher, applicable_charges AS charge, qty
           FROM `tabLanded Cost Item` WHERE item_code=%s ORDER BY creation DESC LIMIT 5""",
        (item_code,), as_dict=True)
    avg_sold = round(float(sales.avg_rate), 2) if sales.avg_rate else 0
    return {
        "item_code": i.name, "item_name": i.item_name, "sku": i.custom_sku, "image": i.image,
        "item_group": i.item_group, "uom": i.stock_uom, "brand": i.brand,
        "cost": round(cost, 2), "valuation_broken": not (i.valuation_rate and float(i.valuation_rate) > 0),
        "avg_sold": avg_sold, "qty_sold": float(sales.qty or 0), "orders": sales.orders or 0,
        "margin": round(avg_sold - cost, 2) if avg_sold else 0,
        "margin_pct": round((avg_sold - cost) / avg_sold * 100, 1) if avg_sold else 0,
        "prices": prices, "stock": stock, "purchases": purchases, "landed": landed,
    }


# ── Price lists ──
@frappe.whitelist()
def list_price_lists():
    """Price lists with currency, buy/sell flags and how many items are priced."""
    assert_portal_access()
    counts = {r.price_list: r.n for r in frappe.db.sql(
        "SELECT price_list, COUNT(*) n FROM `tabItem Price` GROUP BY price_list", as_dict=True)}
    upd = {r.price_list: r.upd for r in frappe.db.sql(
        "SELECT price_list, MAX(modified) upd FROM `tabItem Price` GROUP BY price_list", as_dict=True)}
    out = []
    for pl in frappe.db.sql(
            "SELECT name, currency, selling, buying FROM `tabPrice List` WHERE enabled=1 ORDER BY name", as_dict=True):
        out.append({"name": pl.name, "currency": pl.currency, "selling": pl.selling, "buying": pl.buying,
                    "items": counts.get(pl.name, 0), "updated": str(upd.get(pl.name) or "")[:10]})
    out.sort(key=lambda x: -x["items"])
    return out


@frappe.whitelist()
def get_price_list(name=None, search=None, limit=100):
    """Items priced in one price list."""
    assert_portal_access()
    pl = frappe.db.get_value("Price List", name, ["name", "currency", "selling", "buying"], as_dict=True)
    if not pl:
        frappe.throw("Price list not found")
    limit = min(int(limit or 100), 500)
    conds = ["ip.price_list=%(pl)s"]
    params = {"pl": name, "limit": limit}
    if search:
        conds.append("(ip.item_code LIKE %(s)s OR i.item_name LIKE %(s)s OR IFNULL(i.custom_sku,'') LIKE %(s)s)")
        params["s"] = f"%{search}%"
    rows = frappe.db.sql(
        f"""SELECT ip.item_code, i.item_name, i.custom_sku AS sku, i.image,
                   ip.price_list_rate AS rate
            FROM `tabItem Price` ip LEFT JOIN `tabItem` i ON i.name=ip.item_code
            WHERE {' AND '.join(conds)} ORDER BY ip.modified DESC LIMIT %(limit)s""", params, as_dict=True)
    total = frappe.db.count("Item Price", {"price_list": name})
    return {"name": pl.name, "currency": pl.currency, "selling": pl.selling, "buying": pl.buying,
            "total": total, "rows": rows}


# ── Landed cost vouchers ──
def _classify(desc):
    """Bucket a charge by its description — handles EN, FR and AR labels."""
    d = (desc or "").lower()
    # Customs first ("رسوم الجمارك" = customs duties → customs).
    if any(k in d for k in ("custom", "clearance", "douane", "جمرك", "جمارك", "مخلص", "تخليص")):
        return "customs"
    if any(k in d for k in ("freight", "shipping", "cargo", "sea", "air", "fret", "نقل", "شحن")):
        return "freight"
    if any(k in d for k in ("duty", "duties", "tariff", "droit", "رسوم", "ضريب")):
        return "duties"
    if any(k in d for k in ("insur", "assur", "تأمين")):
        return "insurance"
    return "other"


@frappe.whitelist()
def list_landed_costs(company=None, limit=100):
    """Landed-cost vouchers with the freight/customs/duties split and status."""
    assert_portal_access()
    companies = resolve_companies(company)
    if not companies:
        return []
    limit = min(int(limit or 100), 300)
    rows = frappe.db.sql(
        """SELECT name, docstatus, posting_date AS date, total_taxes_and_charges AS total,
                  distribute_charges_based_on AS basis
           FROM `tabLanded Cost Voucher` WHERE company=%s
           ORDER BY modified DESC LIMIT %s""", (companies[0], limit), as_dict=True)
    for r in rows:
        split = {"freight": 0, "customs": 0, "duties": 0, "insurance": 0, "other": 0}
        for t in frappe.db.sql(
                "SELECT description, base_amount FROM `tabLanded Cost Taxes and Charges` WHERE parent=%s",
                (r["name"],), as_dict=True):
            split[_classify(t.description)] += float(t.base_amount or 0)
        r["freight"] = round(split["freight"]); r["customs"] = round(split["customs"]); r["duties"] = round(split["duties"])
        r["status"] = "Posted" if r["docstatus"] == 1 else ("Cancelled" if r["docstatus"] == 2 else "Draft")
        r["shipment"] = frappe.db.get_value(
            "Landed Cost Purchase Receipt", {"parent": r["name"]}, "receipt_document") or "—"
    return rows


@frappe.whitelist()
def get_landed_cost(name=None):
    """One landed-cost voucher: charges, linked receipts, per-item allocation, and
    the inventory capitalisation journal (GL)."""
    assert_portal_access()
    lcv = frappe.db.get_value(
        "Landed Cost Voucher", name,
        ["name", "company", "docstatus", "posting_date", "total_taxes_and_charges",
         "distribute_charges_based_on"], as_dict=True)
    if not lcv:
        frappe.throw("Voucher not found")
    if lcv.company not in resolve_companies():
        frappe.throw("Not permitted", frappe.PermissionError)
    charges = frappe.db.sql(
        """SELECT expense_account AS account, description, base_amount AS amount
           FROM `tabLanded Cost Taxes and Charges` WHERE parent=%s ORDER BY base_amount DESC""", (name,), as_dict=True)
    for c in charges:
        c["kind"] = _classify(c.description or c.account)
    receipts = frappe.db.sql(
        """SELECT receipt_document AS doc, supplier, posting_date AS date, grand_total
           FROM `tabLanded Cost Purchase Receipt` WHERE parent=%s""", (name,), as_dict=True)
    items = frappe.db.sql(
        """SELECT lci.item_code, i.item_name, i.image, lci.qty, lci.amount AS receipt_value,
                  lci.applicable_charges AS allocated
           FROM `tabLanded Cost Item` lci LEFT JOIN `tabItem` i ON i.name=lci.item_code
           WHERE lci.parent=%s ORDER BY lci.applicable_charges DESC""", (name,), as_dict=True)
    total_val = sum(float(r.receipt_value or 0) for r in items) or 0
    for r in items:
        r["share"] = round(float(r.receipt_value or 0) / total_val * 100, 1) if total_val else 0
        r["per_unit"] = round(float(r.allocated or 0) / float(r.qty), 2) if r.qty else 0
    journal = frappe.db.sql(
        """SELECT account AS acc, debit AS dr, credit AS cr FROM `tabGL Entry`
           WHERE voucher_no=%s AND is_cancelled=0 ORDER BY debit DESC""", (name,), as_dict=True)
    return {
        "name": lcv.name, "company": lcv.company, "posting_date": lcv.posting_date,
        "status": "Posted" if lcv.docstatus == 1 else ("Cancelled" if lcv.docstatus == 2 else "Draft"),
        "basis": lcv.distribute_charges_based_on, "total": float(lcv.total_taxes_and_charges or 0),
        "charges": charges, "receipts": receipts, "items": items, "journal": journal,
    }
