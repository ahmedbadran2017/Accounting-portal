"""Product Cost Trace — cross-company cost provenance for a product (SKU).

The truth anchor for a Morocco item's cost is NOT its Morocco-side purchase
document (those carry a PAPER USD transfer price booked at the wrong FX) but the
ACTUAL supplier bill in the sourcing company — Maslak (Turkey), in TRY. This
module traces a product's purchase journey across every company:

    origin supplier → PO → PR → PI (Maslak)   ← PI = the true cost
        → [paper intercompany transfer, shown but ignored]
        → PR / PI (Morocco)                    ← where FX distortion enters
        → current Morocco valuation → COGS

and surfaces WHERE the unit price diverged, so the real landed cost can be
rebuilt from source. Read-only / analysis only — the correction itself flows
through the audited Valuation Doctor (valuation.correct_valuation) for the
product-cost layer and the Landed Cockpit (153.03) for the inbound-freight
layer. Landed cost is added SEPARATELY on top of the product cost returned here.
"""
import frappe
from frappe.utils import flt, getdate

from accounting_portal.api.permissions import assert_portal_access
from accounting_portal.api.landed_engine import _live_fx

SOURCING = "Maslak LTD"          # Turkey — the true-cost anchor (buys TRY)
SALES = "Justyol Morocco"        # the entity whose COGS we are fixing
TRANSFER_CUSTOMER = "Justyol Morocco"   # intercompany customer name in Maslak

# How much recent invoiced qty forms the cost basis per item (most-recent first).
_BASIS_QTY = 60


def _usd_rate(to_cur, date):
    """USD→to_cur at/just-before `date` (fallback: earliest known)."""
    r = frappe.db.sql(
        """SELECT exchange_rate FROM `tabCurrency Exchange`
           WHERE from_currency='USD' AND to_currency=%s AND date<=%s ORDER BY date DESC LIMIT 1""",
        (to_cur, date))
    if not r:
        r = frappe.db.sql(
            """SELECT exchange_rate FROM `tabCurrency Exchange`
               WHERE from_currency='USD' AND to_currency=%s ORDER BY date ASC LIMIT 1""", (to_cur,))
    return flt(r[0][0]) if r else 0.0


def _to_mad(rate_fc, currency, date, cache):
    """Convert a foreign unit rate to MAD at the correct rate for the date.

    MAD passes through. A direct rate (e.g. USD→MAD) is used when present.
    Currencies with NO direct MAD rate — notably TRY (Maslak's currency) — are
    cross-rated through USD: cur→MAD = (USD→MAD) / (USD→cur). This is what makes
    the Maslak-invoice (TRY) anchor usable, since the books hold no TRY→MAD rate.
    """
    if currency == "MAD":
        return flt(rate_fc)
    date = str(date or frappe.utils.nowdate())[:10]
    lf = flt(_live_fx(currency, date, cache))
    if lf > 0:
        return flt(rate_fc) * lf
    um, uc = _usd_rate("MAD", date), _usd_rate(currency, date)
    if um > 0 and uc > 0:
        return flt(rate_fc) * um / uc
    return 0.0


@frappe.whitelist()
def search_items(query=None, limit=25):
    """Find products by SKU / name / code for the Cost Trace picker. Ranks items
    that currently hold Morocco stock first (those are the ones worth tracing)."""
    assert_portal_access()
    q = (query or "").strip()
    if len(q) < 2:
        return []
    like = f"%{q}%"
    rows = frappe.db.sql(
        """SELECT i.name item_code, i.item_name, i.custom_sku sku,
                  IFNULL(b.qty, 0) stock_qty
           FROM `tabItem` i
           LEFT JOIN (SELECT b.item_code, SUM(b.actual_qty) qty FROM `tabBin` b
                      JOIN `tabWarehouse` w ON w.name=b.warehouse AND w.company=%s
                      GROUP BY b.item_code) b ON b.item_code = i.name
           WHERE i.disabled=0 AND (i.name LIKE %s OR i.item_name LIKE %s OR i.custom_sku LIKE %s)
           ORDER BY (IFNULL(b.qty,0) > 0) DESC, i.modified DESC
           LIMIT %s""", (SALES, like, like, like, int(limit)), as_dict=True)
    return rows


@frappe.whitelist()
def true_cost(item_code=None):
    """The product's TRUE unit cost in MAD, anchored on Maslak's actual supplier
    invoices (TRY) converted at the correct FX. Product cost ONLY — inbound landed
    freight/customs is added separately via the Landed Cockpit. Returns the cost,
    the basis, and the source ('maslak_pi' | 'morocco_pr' | 'orphan')."""
    assert_portal_access()
    if not item_code:
        frappe.throw("item_code required")
    cache = {}
    # 1) preferred anchor — Maslak purchase INVOICES (actual bill), most recent
    pi = frappe.db.sql(
        """SELECT pii.base_rate rate_try, pi.posting_date dt, pii.qty
           FROM `tabPurchase Invoice Item` pii JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
           WHERE pi.company=%s AND pi.docstatus=1 AND pii.item_code=%s AND pii.qty>0
           ORDER BY pi.posting_date DESC""", (SOURCING, item_code), as_dict=True)
    if pi:
        q = v = 0.0
        for r in pi:
            if q >= _BASIS_QTY:
                break
            mad = _to_mad(r.rate_try, "TRY", r.dt, cache)
            q += flt(r.qty); v += mad * flt(r.qty)
        # require a POSITIVE converted value — q>0 with v==0 means every line failed
        # to convert (no FX rate for its currency); don't report that as a 0 cost.
        if q > 0 and v > 0:
            return {"item_code": item_code, "cost_mad": round(v / q, 2),
                    "source": "maslak_pi", "basis_qty": round(q),
                    "note": "Maslak supplier invoice (TRY) @ correct FX — product cost only"}
    # 2) fallback — Morocco direct purchase receipts, FX-corrected
    mo = frappe.db.sql(
        """SELECT pri.rate rate_fc, pr.currency cur, pr.posting_date dt, pri.qty
           FROM `tabPurchase Receipt Item` pri JOIN `tabPurchase Receipt` pr ON pr.name=pri.parent
           WHERE pr.company=%s AND pr.docstatus=1 AND pri.item_code=%s AND pri.qty>0
           ORDER BY pr.posting_date DESC""", (SALES, item_code), as_dict=True)
    if mo:
        q = v = 0.0
        for r in mo:
            if q >= _BASIS_QTY:
                break
            mad = _to_mad(r.rate_fc, r.cur, r.dt, cache)
            q += flt(r.qty); v += mad * flt(r.qty)
        if q > 0 and v > 0:
            return {"item_code": item_code, "cost_mad": round(v / q, 2),
                    "source": "morocco_pr", "basis_qty": round(q),
                    "note": "Morocco direct receipt, FX-corrected — no Maslak invoice"}
        if q > 0:  # had receipts but no line could be FX-converted
            return {"item_code": item_code, "cost_mad": None, "source": "fx_unavailable",
                    "basis_qty": round(q),
                    "note": "Purchase docs exist but their currency has no usable FX rate — needs a rate"}
    # 3) orphan — no cost source anywhere
    return {"item_code": item_code, "cost_mad": None, "source": "orphan", "basis_qty": 0,
            "note": "No Maslak invoice and no Morocco receipt — needs estimated/manual cost"}


# ── Bulk true-cost engine (Phase 2) — computes the whole catalogue at once ──

def _fx_series():
    """Pre-load USD→X rate history so per-item conversion needs no extra queries.
    Returns {currency: [(date_str, usd_to_ccy), …] sorted ascending}."""
    rows = frappe.db.sql(
        """SELECT to_currency cur, date, exchange_rate rate FROM `tabCurrency Exchange`
           WHERE from_currency='USD' ORDER BY date""", as_dict=True)
    s = {}
    for r in rows:
        s.setdefault(r.cur, []).append((str(r.date), flt(r.rate)))
    return s


def _asof(series, cur, date):
    """USD→cur at/just-before `date` (fallback: earliest)."""
    lst = series.get(cur)
    if not lst:
        return 0.0
    val = None
    for d, rate in lst:
        if d <= date:
            val = rate
        else:
            break
    return flt(val if val is not None else lst[0][1])


def _to_mad_fast(rate_fc, currency, date, fx):
    """Same conversion as _to_mad but off the pre-loaded FX series (no queries)."""
    if currency == "MAD":
        return flt(rate_fc)
    date = str(date or frappe.utils.nowdate())[:10]
    um = _asof(fx, "MAD", date)
    if currency == "USD":
        return flt(rate_fc) * um
    uc = _asof(fx, currency, date)
    return flt(rate_fc) * um / uc if (um > 0 and uc > 0) else 0.0


def _true_cost_bulk(item_codes, fx):
    """True MAD cost for many items at once. Maslak PI first, then Morocco PR.
    Returns {item_code: {"cost_mad", "source", "basis_qty"}}."""
    if not item_codes:
        return {}
    codes = tuple(item_codes)
    out = {}

    def _agg(rows, is_try, source):
        by = {}
        for r in rows:
            by.setdefault(r.item_code, []).append(r)
        for item, lines in by.items():
            if item in out:
                continue
            q = v = 0.0
            for r in lines:              # already ordered newest-first
                if q >= _BASIS_QTY:
                    break
                cur = "TRY" if is_try else r.cur
                m = _to_mad_fast(r.rate, cur, r.dt, fx)
                q += flt(r.qty); v += m * flt(r.qty)
            if q > 0 and v > 0:
                out[item] = {"cost_mad": round(v / q, 2), "source": source, "basis_qty": round(q)}

    pi = frappe.db.sql(
        """SELECT pii.item_code, pii.base_rate rate, pi.posting_date dt, pii.qty
           FROM `tabPurchase Invoice Item` pii JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
           WHERE pi.company=%s AND pi.docstatus=1 AND pii.item_code IN %s AND pii.qty>0
           ORDER BY pi.posting_date DESC""", (SOURCING, codes), as_dict=True)
    _agg(pi, True, "maslak_pi")

    missing = [c for c in item_codes if c not in out]
    if missing:
        pr = frappe.db.sql(
            """SELECT pri.item_code, pri.rate, pr.currency cur, pr.posting_date dt, pri.qty
               FROM `tabPurchase Receipt Item` pri JOIN `tabPurchase Receipt` pr ON pr.name=pri.parent
               WHERE pr.company=%s AND pr.docstatus=1 AND pri.item_code IN %s AND pri.qty>0
               ORDER BY pr.posting_date DESC""", (SALES, tuple(missing)), as_dict=True)
        _agg(pr, False, "morocco_pr")
    return out


def _item_procurement(item_codes):
    """Per item → its procurement footprint: primary (most-recent) supplier, and
    the set of (supplier, month) pairs it was purchased in — from Maslak invoices
    AND Morocco receipts. Powers the supplier / month audit filters."""
    if not item_codes:
        return {}
    codes = tuple(item_codes)
    rows = frappe.db.sql(
        """SELECT item_code, supplier, mo FROM (
             SELECT pii.item_code, pi.supplier, DATE_FORMAT(pi.posting_date,'%%Y-%%m') mo, pi.posting_date dt
             FROM `tabPurchase Invoice Item` pii JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
             WHERE pi.company=%s AND pi.docstatus=1 AND pii.item_code IN %s
             UNION ALL
             SELECT pri.item_code, pr.supplier, DATE_FORMAT(pr.posting_date,'%%Y-%%m') mo, pr.posting_date dt
             FROM `tabPurchase Receipt Item` pri JOIN `tabPurchase Receipt` pr ON pr.name=pri.parent
             WHERE pr.company=%s AND pr.docstatus=1 AND pri.item_code IN %s
           ) u ORDER BY dt DESC""", (SOURCING, codes, SALES, codes), as_dict=True)
    out = {}
    for r in rows:
        d = out.setdefault(r.item_code, {"supplier": r.supplier, "pairs": set(), "months": set()})
        d["pairs"].add((r.supplier, r.mo))
        d["months"].add(r.mo)
    return out


@frappe.whitelist()
def cost_filters(company=None):
    """Distinct suppliers (with item counts) and months for the audit filters —
    scoped to items currently in Morocco stock."""
    assert_portal_access()
    stocked = frappe.db.sql(
        """SELECT DISTINCT b.item_code FROM `tabBin` b JOIN `tabWarehouse` w ON w.name=b.warehouse
           WHERE w.company=%s AND b.actual_qty>0""", (SALES,), pluck=True)
    proc = _item_procurement(stocked)
    sup_count, months = {}, set()
    for it, d in proc.items():
        months |= d["months"]
        for s in {p[0] for p in d["pairs"]}:
            sup_count[s] = sup_count.get(s, 0) + 1
    suppliers = sorted(({"supplier": s, "items": n} for s, n in sup_count.items()),
                       key=lambda x: -x["items"])
    return {"suppliers": suppliers, "months": sorted(months, reverse=True)}


@frappe.whitelist()
def cost_overview(company=None):
    """Catalogue-wide KPI: current book value vs true value of stock on hand,
    the total overvaluation, and the breakdown by cost source."""
    assert_portal_access()
    fx = _fx_series()
    bins = frappe.db.sql(
        """SELECT b.item_code, SUM(b.actual_qty) qty, SUM(b.stock_value) sv
           FROM `tabBin` b JOIN `tabWarehouse` w ON w.name=b.warehouse
           WHERE w.company=%s AND b.actual_qty>0 GROUP BY b.item_code""", (SALES,), as_dict=True)
    tc = _true_cost_bulk([b.item_code for b in bins], fx)
    n = {"maslak_pi": 0, "morocco_pr": 0, "unpriced": 0}
    cur_val = true_val = over = 0.0
    priced_qty = 0.0
    for b in bins:
        cur_val += flt(b.sv)
        t = tc.get(b.item_code)
        if t:
            n[t["source"]] += 1
            tv = flt(t["cost_mad"]) * flt(b.qty)
            true_val += tv; over += flt(b.sv) - tv; priced_qty += flt(b.qty)
        else:
            n["unpriced"] += 1
    return {
        "company": SALES, "items": len(bins),
        "current_value": round(cur_val), "true_value_priced": round(true_val),
        "overvaluation": round(over),
        "maslak_pi": n["maslak_pi"], "morocco_pr": n["morocco_pr"], "unpriced": n["unpriced"],
    }


@frappe.whitelist()
def cost_table(company=None, start=0, page_size=50, source=None, search=None,
               supplier=None, month=None):
    """The bulk true-cost worklist: every stocked item with its true cost, current
    valuation, distortion, and its supplier — the feed for the valuation
    correction and the SKU-by-SKU audit. Filters: `source`
    (maslak_pi|morocco_pr|unpriced), `supplier`, `month` (YYYY-MM, honours the
    chosen supplier), free-text `search`. Sorted by absolute overvaluation."""
    assert_portal_access()
    fx = _fx_series()
    conds = ["w.company=%(c)s", "b.actual_qty>0"]
    params = {"c": SALES}
    if search:
        conds.append("(b.item_code LIKE %(s)s OR i.item_name LIKE %(s)s OR i.custom_sku LIKE %(s)s)")
        params["s"] = f"%{search}%"
    bins = frappe.db.sql(
        f"""SELECT b.item_code, SUM(b.actual_qty) qty, SUM(b.stock_value) sv,
                   MAX(i.item_name) item_name, MAX(i.custom_sku) sku
            FROM `tabBin` b JOIN `tabWarehouse` w ON w.name=b.warehouse
            JOIN `tabItem` i ON i.name=b.item_code
            WHERE {' AND '.join(conds)} GROUP BY b.item_code""", params, as_dict=True)
    item_codes = [b.item_code for b in bins]
    tc = _true_cost_bulk(item_codes, fx)
    proc = _item_procurement(item_codes)   # supplier + (supplier,month) pairs per item
    rows = []
    for b in bins:
        # supplier / month audit filter
        if supplier or month:
            d = proc.get(b.item_code)
            pairs = d["pairs"] if d else set()
            if supplier and month:
                if (supplier, month) not in pairs:
                    continue
            elif supplier:
                if supplier not in {p[0] for p in pairs}:
                    continue
            elif month:
                if month not in {p[1] for p in pairs}:
                    continue
        t = tc.get(b.item_code)
        cur_rate = round(flt(b.sv) / flt(b.qty), 2) if flt(b.qty) else 0
        src = t["source"] if t else "unpriced"
        cost = flt(t["cost_mad"]) if t else None
        over = round((flt(b.sv) - cost * flt(b.qty))) if cost is not None else None
        dev = round((cur_rate - cost) / cost * 100, 1) if (cost and cost > 0) else None
        rows.append({"item_code": b.item_code, "sku": b.sku, "item_name": b.item_name,
                     "qty": round(flt(b.qty)), "current_rate": cur_rate, "true_cost": cost,
                     "source": src, "overvaluation": over, "dev_pct": dev,
                     "supplier": (proc.get(b.item_code) or {}).get("supplier")})
    if source in ("maslak_pi", "morocco_pr", "unpriced"):
        rows = [r for r in rows if r["source"] == source]
    rows.sort(key=lambda r: -abs(r["overvaluation"] or 0))
    total = len(rows)
    start, page_size = int(start or 0), min(int(page_size or 50), 500)
    return {"rows": rows[start:start + page_size], "total": total}


def _current_valuation(item_code):
    """Weighted-average current Morocco valuation across all its bins."""
    row = frappe.db.sql(
        """SELECT SUM(b.stock_value) sv, SUM(b.actual_qty) q
           FROM `tabBin` b JOIN `tabWarehouse` w ON w.name=b.warehouse
           WHERE w.company=%s AND b.item_code=%s AND b.actual_qty>0""",
        (SALES, item_code), as_dict=True)
    r = row[0] if row else None
    if r and flt(r.q) > 0:
        return round(flt(r.sv) / flt(r.q), 2), round(flt(r.q))
    return None, 0


@frappe.whitelist()
def trace_item(item_code=None):
    """The full cross-company cost ladder for a product, with per-hop unit price
    (doc currency + MAD-corrected) and a divergence flag at each break point."""
    assert_portal_access()
    if not item_code:
        frappe.throw("item_code required")
    meta = frappe.db.get_value("Item", item_code,
                               ["item_name", "custom_sku", "weight_per_unit", "stock_uom"], as_dict=True) or {}
    cache = {}
    ladder = []

    def add(stage, company, doctype, name, dt, qty, rate, cur):
        ladder.append({
            "stage": stage, "company": company, "doctype": doctype, "name": name,
            "date": str(dt or ""), "qty": round(flt(qty)), "rate": round(flt(rate), 2),
            "currency": cur, "rate_mad": round(_to_mad(rate, cur, dt, cache), 2),
        })

    # ── Maslak (source): PO → PR → PI ──
    for stage, dt_field, tbl, itbl in [
        ("source_po", "transaction_date", "Purchase Order", "Purchase Order Item"),
        ("source_pr", "posting_date", "Purchase Receipt", "Purchase Receipt Item"),
        ("source_pi", "posting_date", "Purchase Invoice", "Purchase Invoice Item")]:
        rows = frappe.db.sql(
            f"""SELECT it.parent nm, p.{dt_field} dt, it.qty, it.rate, p.currency cur
                FROM `tab{itbl}` it JOIN `tab{tbl}` p ON p.name=it.parent
                WHERE p.company=%s AND p.docstatus=1 AND it.item_code=%s AND it.qty>0
                ORDER BY p.{dt_field} DESC LIMIT 1""", (SOURCING, item_code), as_dict=True)
        if rows:
            r = rows[0]
            add(stage, SOURCING, tbl, r.nm, r.dt, r.qty, r.rate, r.cur)

    # ── the paper intercompany transfer (Maslak sells to Morocco) ──
    tr = frappe.db.sql(
        """SELECT si.name nm, si.posting_date dt, sii.qty, sii.rate, si.currency cur
           FROM `tabSales Invoice Item` sii JOIN `tabSales Invoice` si ON si.name=sii.parent
           WHERE si.company=%s AND si.docstatus=1 AND si.customer=%s AND sii.item_code=%s AND sii.qty>0
           ORDER BY si.posting_date DESC LIMIT 1""", (SOURCING, TRANSFER_CUSTOMER, item_code), as_dict=True)
    if tr:
        r = tr[0]
        add("transfer_paper", SOURCING, "Sales Invoice", r.nm, r.dt, r.qty, r.rate, r.cur)

    # ── Morocco (dest): PR (where the FX distortion typically enters) ──
    mo = frappe.db.sql(
        """SELECT pr.name nm, pr.posting_date dt, pri.qty, pri.rate, pr.currency cur, pr.conversion_rate cr
           FROM `tabPurchase Receipt Item` pri JOIN `tabPurchase Receipt` pr ON pr.name=pri.parent
           WHERE pr.company=%s AND pr.docstatus=1 AND pri.item_code=%s AND pri.qty>0
           ORDER BY pr.posting_date DESC LIMIT 1""", (SALES, item_code), as_dict=True)
    if mo:
        r = mo[0]
        add("dest_pr", SALES, "Purchase Receipt", r.nm, r.dt, r.qty, r.rate, r.cur)
        ladder[-1]["conversion_rate"] = round(flt(r.cr), 3)

    # ── divergence flags: compare each hop's MAD unit rate to the true cost ──
    tc = true_cost(item_code)
    truth = flt(tc.get("cost_mad")) if tc.get("cost_mad") is not None else None
    for row in ladder:
        if truth and truth > 0 and row.get("rate_mad"):
            dev = (row["rate_mad"] - truth) / truth
            row["dev_pct"] = round(dev * 100, 1)
            row["flag"] = ("inflated" if dev > 0.15 else "low" if dev < -0.15 else "ok")
        else:
            row["dev_pct"], row["flag"] = None, "no_basis"

    cur_val, cur_qty = _current_valuation(item_code)
    distortion = None
    if truth and truth > 0 and cur_val is not None:
        distortion = round((cur_val - truth) / truth * 100, 1)

    return {
        "item_code": item_code, "item_name": meta.get("item_name"), "sku": meta.get("custom_sku"),
        "weight_per_unit": flt(meta.get("weight_per_unit")), "uom": meta.get("stock_uom"),
        "true_cost": tc, "current_valuation_mad": cur_val, "current_qty": cur_qty,
        "distortion_pct": distortion, "ladder": ladder,
        "note": "true_cost is PRODUCT cost only; inbound landed (freight/customs via 153.03) is added on top separately",
    }
