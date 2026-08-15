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
