"""Weight hygiene worklist — fix the split key, one item at a time.

Freight is distributed over BOOK weights (the relative split key under the
bill-anchored calibration). The book is filthy: ~29% of imported items weigh
ZERO (they ride free while honest items overpay), hundreds more carry absurd
entries (a kids' 2-piece set at 190g, 96 items parked on the 0.50 default).
Every weight fixed here immediately improves the fairness of the freight
split — and shrinks the calibration scale toward 1 (it recomputes live).

Fixing a weight edits the ITEM MASTER only (no GL, no repost) — the effect
flows into the NEXT landed computation/apply naturally.
"""
import frappe
from frappe.utils import flt

from accounting_portal.api.permissions import assert_portal_access, assert_can_write

SALES = "Justyol Morocco"
_DOMESTIC_GROUPS = ("Morocco Local Suppliers", "Local")

# sanity band for a COD-parcel product's unit weight
_MIN_KG, _MAX_KG = 0.005, 50.0


def _flag(w):
    w = flt(w)
    if w <= 0:
        return "zero"
    if w == 0.5:
        return "default"
    if w <= 0.2:
        return "tiny"
    return None


@frappe.whitelist()
def weight_worklist(search=None, flag=None, start=0, page_size=50):
    """Imported items with suspect weights, ranked by DAMAGE: units received
    through import shipments (the more units, the more the bad weight skews
    everyone's freight split). flag: zero | tiny | default | all."""
    assert_portal_access()
    rows = frappe.db.sql(
        """SELECT i.name item_code, i.item_name, i.custom_sku sku, i.image,
                  i.item_group, IFNULL(i.weight_per_unit,0) w,
                  SUM(pri.qty) units_in,
                  IFNULL(b.qty, 0) stock_qty
           FROM `tabPurchase Receipt Item` pri
           JOIN `tabPurchase Receipt` pr ON pr.name=pri.parent
           JOIN `tabItem` i ON i.name=pri.item_code
           LEFT JOIN `tabSupplier` s ON s.name=pr.supplier
           LEFT JOIN (SELECT b.item_code, SUM(b.actual_qty) qty FROM `tabBin` b
                      JOIN `tabWarehouse` w2 ON w2.name=b.warehouse AND w2.company=%s
                      GROUP BY b.item_code) b ON b.item_code = i.name
           WHERE pr.company=%s AND pr.docstatus=1 AND i.is_stock_item=1
             AND IFNULL(s.supplier_group,'') NOT IN %s
           GROUP BY i.name""",
        (SALES, SALES, _DOMESTIC_GROUPS), as_dict=True)
    out = []
    counts = {"zero": 0, "tiny": 0, "default": 0}
    for r in rows:
        f = _flag(r.w)
        if not f:
            continue
        counts[f] += 1
        r["flag"] = f
        r["units_in"] = flt(r.units_in)
        r["stock_qty"] = flt(r.stock_qty)
        out.append(r)
    q = (search or "").strip().lower()
    if q:
        out = [r for r in out if q in (r.item_name or "").lower()
               or q in (r.sku or "").lower() or q in r.item_code.lower()]
    if flag in ("zero", "tiny", "default"):
        out = [r for r in out if r["flag"] == flag]
    sev = {"zero": 0, "tiny": 1, "default": 2}
    out.sort(key=lambda r: (sev[r["flag"]], -r["units_in"]))
    start, page_size = int(start or 0), min(int(page_size or 50), 200)
    # live calibration scales — the motivation meter (they shrink toward 1)
    scales = {}
    try:
        from accounting_portal.api.landed_prep import _hist_scales, _year
        scales = _hist_scales(_year(None))
    except Exception:
        pass
    return {"total": len(out), "counts": counts,
            "rows": out[start:start + page_size],
            "scales": {k: v.get("scale") for k, v in scales.items()}}


@frappe.whitelist()
def set_item_weight(item_code=None, weight=None):
    """Fix one item's unit weight (master data only — no GL). Sane band
    enforced; sets weight_uom to Kg when empty; busts the calibration cache
    so the scales reflect the fix immediately."""
    assert_can_write()
    if not item_code or not frappe.db.exists("Item", item_code):
        frappe.throw("item_code required")
    w = flt(weight)
    if not (_MIN_KG <= w <= _MAX_KG):
        frappe.throw(f"Weight must be between {_MIN_KG} and {_MAX_KG} kg — got {w}")
    doc = frappe.get_doc("Item", item_code)
    doc.db_set("weight_per_unit", w)
    if not doc.weight_uom:
        doc.db_set("weight_uom", "Kg")
    frappe.db.commit()
    # the calibration scale is derived from the whole population — recompute
    try:
        for y in (2025, 2026, 2027):
            frappe.cache().delete_value(f"ap_hist_scales:{y}")
    except Exception:
        pass
    return {"item_code": item_code, "weight": w}
