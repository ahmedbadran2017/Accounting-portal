"""Valuation Doctor — find and fix wrong stock valuation, retroactively.

ERPNext values stock per item × warehouse (moving average). One wrong incoming
rate (an FX-inflated purchase, a rate typo, a zero-rate receipt) contaminates
the average and every later Delivery Note books wrong COGS from it.

This module benchmarks every bin against the FX-corrected landed cost
(corrected product cost + freight/kg × weight — same engine as the Costing
screen) and flags deviation IN EITHER DIRECTION: the books here are mostly
OVER-valued (the FX bug booked USD@~43 instead of ~9.5), so write-downs are
the common fix — but too-low bins (below product cost) are flagged too.

Fixing posts a back-dated Stock Reconciliation at the correct rate; ERPNext's
Repost Item Valuation then recomputes the moving average through every later
stock ledger entry — Delivery Notes included — and re-posts their GL, so COGS
heals retroactively. Policy agreed with the CFO: corrections never post before
2026-01-01 (fix-forward for older errors; original date within 2026).

Known gotcha: back-dated reposts can sit "Queued" — repost_queue/kick_repost
expose and push them from the portal.
"""
import json

import frappe
from frappe.utils import flt, nowdate

from accounting_portal.api.permissions import assert_portal_access, assert_can_write, resolve_companies
from accounting_portal.api import _actions
from accounting_portal.api.landed_engine import _live_fx, _freight_stats

FIX_ACTION = "Correct stock valuation"
_POLICY_FLOOR = "2026-01-01"   # never restate closed years — fix-forward
_DEV_FLAG = 0.30               # |deviation| ≥ 30% vs benchmark → flagged


def _target(company):
    companies = resolve_companies(company)
    if not companies:
        return None
    return company if (company and company in companies) else companies[0]


def _benchmarks(target, item_codes):
    """FX-corrected weighted-avg purchase cost per item (batch version of the
    Costing screen's math), + freight/kg × weight → landed benchmark."""
    if not item_codes:
        return {}
    lines = frappe.db.sql(
        """SELECT pii.item_code item, pi.currency cur, pi.posting_date dt,
                  pii.qty, pii.rate rate_fc, pii.base_rate rate_book
           FROM `tabPurchase Invoice Item` pii
           JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
           WHERE pi.company=%s AND pi.docstatus=1 AND pii.item_code IN %s
           ORDER BY pi.posting_date DESC""", (target, tuple(item_codes)), as_dict=True)
    fxc, agg = {}, {}
    for p in lines:
        a = agg.setdefault(p.item, [0.0, 0.0])   # qty, corrected value
        if a[0] >= 60:  # recent-enough basis per item
            continue
        lf = _live_fx(p.cur, p.dt, fxc)
        rate = flt(p.rate_book) if (p.cur == "MAD" or lf <= 0) else flt(p.rate_fc) * lf
        a[0] += flt(p.qty)
        a[1] += rate * flt(p.qty)
    fs = _freight_stats(target)
    fpk = fs["rate"]
    weights = dict(frappe.db.sql(
        "SELECT name, IFNULL(weight_per_unit,0) FROM `tabItem` WHERE name IN %s", (tuple(item_codes),)))
    out = {}
    for item, (q, v) in agg.items():
        if q <= 0:
            continue
        product = v / q
        out[item] = round(product + fpk * flt(weights.get(item)), 2)
    return out


@frappe.whitelist()
def valuation_review(company=None, limit=250):
    """Every stocked bin vs its landed benchmark, worst distortion first."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    bins = frappe.db.sql(
        """SELECT b.item_code, b.warehouse, b.actual_qty qty, b.valuation_rate vr,
                  b.stock_value, i.item_name, i.custom_sku sku, i.image
           FROM `tabBin` b
           JOIN `tabWarehouse` w ON w.name=b.warehouse AND w.company=%s
           JOIN `tabItem` i ON i.name=b.item_code
           WHERE b.actual_qty > 0
           ORDER BY b.stock_value DESC LIMIT %s""", (target, int(limit)), as_dict=True)
    bench = _benchmarks(target, list({b.item_code for b in bins}))
    rows, tot_over, tot_under = [], 0.0, 0.0
    for b in bins:
        bm = bench.get(b.item_code)
        b["qty"], b["vr"], b["stock_value"] = flt(b.qty), flt(b.vr), flt(b.stock_value)
        b["benchmark"] = bm
        if not bm:
            b["flag"], b["distortion"] = "no_basis", 0.0
            if b["vr"] <= 0:
                b["flag"] = "zero_rate"
            rows.append(b)
            continue
        dev = (b["vr"] - bm) / bm if bm else 0
        b["dev_pct"] = round(dev * 100, 1)
        b["distortion"] = round((b["vr"] - bm) * b["qty"])
        b["flag"] = ("overvalued" if dev >= _DEV_FLAG else
                     "undervalued" if dev <= -_DEV_FLAG else
                     "zero_rate" if b["vr"] <= 0 else "ok")
        if b["flag"] == "overvalued":
            tot_over += b["distortion"]
        elif b["flag"] in ("undervalued", "zero_rate"):
            tot_under += b["distortion"]
        rows.append(b)
    rows.sort(key=lambda r: -abs(r.get("distortion") or 0))
    flagged = [r for r in rows if r["flag"] not in ("ok", "no_basis")]
    return {"company": target, "rows": rows,
            "freight": _freight_stats(target),
            "summary": {"bins": len(rows), "flagged": len(flagged),
                        "overvalued_mad": round(tot_over), "undervalued_mad": round(tot_under),
                        "policy_floor": _POLICY_FLOOR}}


@frappe.whitelist()
def correct_valuation(company=None, item_code=None, warehouse=None, correct_rate=None,
                      effective_date=None, notes=None):
    """Set a bin's valuation to the correct rate via a back-dated Stock
    Reconciliation. ERPNext reposts every later SLE (Delivery Notes included)
    and their GL — the retroactive fix. Gated (propose→approve when material),
    audited, revertible (revert = cancel the reconciliation)."""
    assert_can_write()
    target = _target(company)
    rate = flt(correct_rate)
    if not (target and item_code and warehouse):
        frappe.throw("company, item_code and warehouse are required")
    if rate <= 0:
        frappe.throw("Correct rate must be > 0")
    if frappe.db.get_value("Warehouse", warehouse, "company") != target:
        frappe.throw(f"{warehouse} is not a {target} warehouse")
    b = frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse},
                            ["actual_qty", "valuation_rate"], as_dict=True)
    if not b or flt(b.actual_qty) <= 0:
        frappe.throw("No stock in this warehouse for this item")
    date = str(effective_date or nowdate())[:10]
    if date < _POLICY_FLOOR:
        date = _POLICY_FLOOR  # fix-forward policy: never restate closed years
    if date > nowdate():
        frappe.throw("Effective date cannot be in the future")
    impact = abs(rate - flt(b.valuation_rate)) * flt(b.actual_qty)
    return _actions.execute(
        FIX_ACTION, target, f"valfix:{target}:{item_code}:{warehouse}:{rate}:{date}",
        payload={"item_code": item_code, "warehouse": warehouse, "qty": flt(b.actual_qty),
                 "old_rate": flt(b.valuation_rate), "rate": rate, "date": date},
        amount=impact,
        notes=notes or f"Valuation {item_code} @ {warehouse}: {flt(b.valuation_rate):,.2f} → {rate:,.2f} ({date})")


def _valfix_poster(action):
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    company = action.company
    doc = frappe.get_doc({
        "doctype": "Stock Reconciliation", "company": company,
        "purpose": "Stock Reconciliation",
        "posting_date": p["date"], "posting_time": "23:59:00", "set_posting_time": 1,
        "expense_account": frappe.get_cached_value("Company", company, "stock_adjustment_account"),
        "cost_center": frappe.get_cached_value("Company", company, "cost_center"),
        "items": [{"item_code": p["item_code"], "warehouse": p["warehouse"],
                   "qty": flt(p["qty"]), "valuation_rate": flt(p["rate"])}],
    })
    doc.insert(ignore_permissions=True)
    doc.submit()
    return {"voucher_type": "Stock Reconciliation", "voucher_no": doc.name,
            "result": f"{p['item_code']} @ {p['warehouse']} → {p['rate']}"}


def _valfix_reverter(action):
    if action.voucher_no and frappe.db.exists("Stock Reconciliation", action.voucher_no):
        doc = frappe.get_doc("Stock Reconciliation", action.voucher_no)
        if doc.docstatus == 1:
            doc.cancel()
    return {"voucher_type": "Stock Reconciliation", "voucher_no": action.voucher_no, "result": "cancelled"}


_actions.register_poster(FIX_ACTION, _valfix_poster)
_actions.register_reverter(FIX_ACTION, _valfix_reverter)


@frappe.whitelist()
def repost_queue(company=None):
    """Repost Item Valuation jobs — the engine that heals history. Back-dated
    ones can sit Queued (known gotcha); kick_repost pushes them."""
    assert_portal_access()
    target = _target(company)
    rows = frappe.db.sql(
        """SELECT name, status, item_code, warehouse, posting_date, voucher_type, voucher_no,
                  modified
           FROM `tabRepost Item Valuation`
           WHERE company=%s AND status != 'Completed'
           ORDER BY modified DESC LIMIT 50""", (target,), as_dict=True)
    counts = dict(frappe.db.sql(
        "SELECT status, COUNT(*) FROM `tabRepost Item Valuation` WHERE company=%s GROUP BY status", (target,)))
    for r in rows:
        r["posting_date"] = str(r["posting_date"] or "")[:10]
        r["modified"] = str(r["modified"] or "")[:16]
    return {"rows": rows, "counts": {k: int(v) for k, v in counts.items()}}


@frappe.whitelist()
def kick_repost(name=None):
    """Re-enqueue a Queued/Failed repost job (long queue)."""
    assert_can_write()
    doc = frappe.get_doc("Repost Item Valuation", name)
    if doc.status not in ("Queued", "Failed"):
        frappe.throw(f"Job is {doc.status} — nothing to kick")
    from erpnext.stock.doctype.repost_item_valuation.repost_item_valuation import repost
    frappe.enqueue(repost, doc=doc, queue="long", timeout=3600,
                   job_name=f"portal_repost_{doc.name}", enqueue_after_commit=True)
    return {"status": "enqueued", "name": doc.name}
