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
from accounting_portal.api.landed_engine import _freight_stats

FIX_ACTION = "Correct stock valuation"
_POLICY_FLOOR = "2026-01-01"   # never restate closed years — fix-forward
_DEV_FLAG = 0.30               # |deviation| ≥ 30% vs benchmark → flagged


def _target(company):
    companies = resolve_companies(company)
    if not companies:
        return None
    return company if (company and company in companies) else companies[0]


def _benchmarks(target, item_codes):
    """TRUE product cost per item (MAD), anchored on the sourcing company's ACTUAL
    supplier invoice (Maslak, TRY) via cost_trace._true_cost_bulk — NOT the
    Morocco-side purchase docs, which carry a paper USD transfer price at the
    wrong FX. Falls back to a Morocco direct receipt (FX-corrected) when no
    Maslak invoice exists.

    PRODUCT COST ONLY — inbound landed freight/customs is a SEPARATE layer,
    capitalized on top via the Landed Cockpit (153.03). Keeping freight out of
    this benchmark is deliberate: it prevents double-counting when the two
    correction passes (valuation fix here + landed capitalization there) run.
    """
    if not item_codes:
        return {}
    from accounting_portal.api.cost_trace import _true_cost_bulk, _fx_series
    tc = _true_cost_bulk(list(item_codes), _fx_series())
    return {item: round(flt(t["cost_mad"]), 2)
            for item, t in tc.items() if t and flt(t.get("cost_mad")) > 0}


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
def zero_cogs_review(company=None):
    """The zero-COGS queue: bins holding stock at a ZERO/negative valuation.
    Every delivery from them books COGS = 0 → 100% fake margin. These bins have
    stock_value = 0 so the distortion view (sorted by stock value) never surfaces
    them — this is their dedicated queue, ranked by the COGS they already missed
    in 2026 (units delivered × benchmark)."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    bins = frappe.db.sql(
        """SELECT b.item_code, b.warehouse, b.actual_qty qty, b.valuation_rate vr,
                  i.item_name, i.custom_sku sku, i.image
           FROM `tabBin` b
           JOIN `tabWarehouse` w ON w.name=b.warehouse AND w.company=%s
           JOIN `tabItem` i ON i.name=b.item_code
           WHERE b.actual_qty > 0 AND IFNULL(b.valuation_rate, 0) <= 0""", (target,), as_dict=True)
    if not bins:
        return {"company": target, "rows": [],
                "summary": {"bins": 0, "sellers": 0, "missed_cogs": 0, "stock_units_zero": 0}}
    items = list({b.item_code for b in bins})
    sold = dict(frappe.db.sql(
        """SELECT dni.item_code, SUM(dni.qty) FROM `tabDelivery Note Item` dni
           JOIN `tabDelivery Note` dn ON dn.name=dni.parent
           WHERE dn.docstatus=1 AND dn.company=%s AND dn.posting_date >= '2026-01-01'
             AND dni.item_code IN %s GROUP BY dni.item_code""", (target, tuple(items))))
    bench = _benchmarks(target, items)
    rows = []
    for b in bins:
        bm = bench.get(b.item_code)
        s = flt(sold.get(b.item_code))
        b["qty"], b["vr"] = flt(b.qty), flt(b.vr)
        b["sold_2026"] = s
        b["benchmark"] = bm
        b["missed_cogs"] = round(s * bm) if bm else None
        b["flag"] = "zero_rate" if bm else "no_basis"
        rows.append(b)
    rows.sort(key=lambda r: (-(r["missed_cogs"] or 0), -r["qty"]))
    sellers = [r for r in rows if r["sold_2026"] > 0]
    return {"company": target, "rows": rows[:300],
            "summary": {"bins": len(rows), "sellers": len(sellers),
                        "missed_cogs": round(sum(r["missed_cogs"] or 0 for r in sellers)),
                        "stock_units_zero": round(sum(r["qty"] for r in rows))}}


def _qty_asof(item_code, warehouse, date):
    """Stock on hand at the END of `date` — a back-dated reconciliation must carry
    the quantity of THAT day, not today's, or it rewrites quantity history."""
    r = frappe.db.sql(
        """SELECT qty_after_transaction FROM `tabStock Ledger Entry`
           WHERE item_code=%s AND warehouse=%s AND is_cancelled=0 AND posting_date <= %s
           ORDER BY posting_date DESC, creation DESC LIMIT 1""", (item_code, warehouse, date))
    return flt(r[0][0]) if r else 0.0


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
    qty_then = _qty_asof(item_code, warehouse, date)
    if qty_then <= 0:
        frappe.throw(f"No stock in {warehouse} on {date} — pick a later effective date")
    impact = abs(rate - flt(b.valuation_rate)) * qty_then
    return _actions.execute(
        FIX_ACTION, target, f"valfix:{target}:{item_code}:{warehouse}:{rate}:{date}",
        payload={"item_code": item_code, "warehouse": warehouse, "qty": qty_then,
                 "old_rate": flt(b.valuation_rate), "rate": rate, "date": date},
        amount=impact,
        notes=notes or f"Valuation {item_code} @ {warehouse}: {flt(b.valuation_rate):,.2f} → {rate:,.2f} ({date})")


def _valfix_poster(action):
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    company = action.company
    # Re-resolve the quantity AS OF the effective date at post time (approval may
    # come days after the proposal) — a back-dated reco with today's qty would
    # rewrite quantity history and corrupt every later stock move.
    qty_then = _qty_asof(p["item_code"], p["warehouse"], p["date"])
    if qty_then <= 0:
        frappe.throw(f"No stock in {p['warehouse']} on {p['date']} — re-propose with a later date")
    doc = frappe.get_doc({
        "doctype": "Stock Reconciliation", "company": company,
        "purpose": "Stock Reconciliation",
        "posting_date": p["date"], "posting_time": "23:59:00", "set_posting_time": 1,
        "expense_account": frappe.get_cached_value("Company", company, "stock_adjustment_account"),
        "cost_center": frappe.get_cached_value("Company", company, "cost_center"),
        "items": [{"item_code": p["item_code"], "warehouse": p["warehouse"],
                   "qty": qty_then, "valuation_rate": flt(p["rate"])}],
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


REVAL_ACTION = "Revalue inventory (bulk)"


def _reval_rows(target, bins, date):
    """Resolve the requested bins to reconciliation rows at the FX-corrected
    landed benchmark, carrying each bin's qty AS OF `date`. Skips bins with no
    benchmark, no stock on that date, or already at the right rate."""
    item_codes = list({b["item_code"] for b in bins})
    bench = _benchmarks(target, item_codes)
    rows, impact = [], 0.0
    for b in bins:
        ic, wh = b.get("item_code"), b.get("warehouse")
        bm = bench.get(ic)
        if not bm or bm <= 0:
            continue
        q = _qty_asof(ic, wh, date)
        if q <= 0:
            continue
        old = flt(frappe.db.get_value("Bin", {"item_code": ic, "warehouse": wh}, "valuation_rate"))
        if abs(bm - old) < 0.01:
            continue
        delta = round((bm - old) * q, 2)
        rows.append({"item_code": ic, "warehouse": wh, "qty": q,
                     "old_rate": round(old, 2), "rate": bm, "delta": delta})
        impact += abs(delta)
    return rows, round(impact, 2)


@frappe.whitelist()
def revalue_bins(company=None, bins=None, effective_date=None, dry_run=1, notes=None):
    """The bulk revaluation loop the single-bin fix was missing: heal MANY bins to
    their FX-corrected landed benchmark in ONE back-dated Stock Reconciliation, so
    the books' inventory value (and later COGS via repost) is corrected in a single
    voucher — not item master only, and not one voucher per SKU. dry_run=1 returns
    the preview (per bin old→new, total impact) and posts nothing. Gated on the
    total absolute impact; revert cancels the reconciliation."""
    assert_can_write()
    target = _target(company)
    bins = json.loads(bins) if isinstance(bins, str) else (bins or [])
    if not (target and bins):
        frappe.throw("company and bins are required")
    date = str(effective_date or _POLICY_FLOOR)[:10]
    if date < _POLICY_FLOOR:
        date = _POLICY_FLOOR
    if date > nowdate():
        frappe.throw("Effective date cannot be in the future")
    rows, impact = _reval_rows(target, bins, date)
    if not rows:
        frappe.throw("Nothing to revalue (no benchmark, no stock on that date, or already correct)")
    if int(dry_run or 0):
        return {"dry_run": 1, "date": date, "rows": rows, "n": len(rows), "impact": impact}
    key = "reval:" + frappe.generate_hash(f"{target}:{date}:{sorted((r['item_code'], r['warehouse']) for r in rows)}:{impact}", 14)
    return _actions.execute(
        REVAL_ACTION, target, key,
        payload={"date": date, "rows": [{"item_code": r["item_code"], "warehouse": r["warehouse"], "rate": r["rate"]} for r in rows]},
        amount=impact,
        notes=notes or f"Bulk revaluation — {len(rows)} bins, impact {impact:,.0f} ({date})")


def _revalue_poster(action):
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    company = action.company
    date = p["date"]
    # Re-resolve qty AS OF the effective date at post time (approval may lag) and
    # drop any bin now empty — a back-dated reco with today's qty rewrites history.
    items = []
    for r in p["rows"]:
        q = _qty_asof(r["item_code"], r["warehouse"], date)
        if q > 0:
            items.append({"item_code": r["item_code"], "warehouse": r["warehouse"],
                          "qty": q, "valuation_rate": flt(r["rate"])})
    if not items:
        frappe.throw("No stock on the effective date for any selected bin — re-propose with a later date")
    doc = frappe.get_doc({
        "doctype": "Stock Reconciliation", "company": company,
        "purpose": "Stock Reconciliation",
        "posting_date": date, "posting_time": "23:59:00", "set_posting_time": 1,
        "expense_account": frappe.get_cached_value("Company", company, "stock_adjustment_account"),
        "cost_center": frappe.get_cached_value("Company", company, "cost_center"),
        "items": items,
    })
    doc.insert(ignore_permissions=True)
    doc.submit()
    return {"voucher_type": "Stock Reconciliation", "voucher_no": doc.name,
            "result": f"revalued {len(items)} bins @ {date}"}


_actions.register_poster(REVAL_ACTION, _revalue_poster)
_actions.register_reverter(REVAL_ACTION, _valfix_reverter)


# ── Per-product verify-and-fix (the human-in-the-loop cutover) ───────────────
# The accounting/purchasing team reviews ONE product at a time: see the source
# evidence (the actual Maslak supplier-invoice lines behind the true cost),
# confirm the figure is right, preview the per-bin impact, then click Fix —
# which posts ONE today-dated Stock Reconciliation covering every bin of the
# product. Today-dated on purpose: nothing follows it in the ledger, so there is
# no heavy back-dated repost (the failure mode of the first canary), and all
# bins move together so no old-rate stock re-contaminates the average.

def _fix_bins(target, item_code):
    return frappe.db.sql(
        """SELECT b.warehouse, b.actual_qty qty, b.valuation_rate vr
           FROM `tabBin` b JOIN `tabWarehouse` w ON w.name=b.warehouse
           WHERE w.company=%s AND b.item_code=%s AND b.actual_qty>0
           ORDER BY b.stock_value DESC""", (target, item_code), as_dict=True)


def _fixed_action(item_code):
    """The posted fix action for this product, if any (drives the ✓ badge)."""
    return frappe.db.get_value(
        "Accounting Portal Action",
        {"action_type": REVAL_ACTION, "status": "Posted",
         "reference_doctype": "Item", "reference_name": item_code},
        ["name", "voucher_no", "posted_on"], as_dict=True)


@frappe.whitelist()
def item_fix_preview(company=None, item_code=None):
    """Everything the reviewer needs to verify ONE product's cost: the true-cost
    figure + the actual purchase-document lines behind it (the evidence), the
    per-bin dry-run at that rate, and whether it was already fixed."""
    assert_portal_access()
    from accounting_portal.api.cost_trace import (
        SALES, SOURCING, _fx_series, _to_mad_fast, true_cost as _tc)
    # default to the sales entity (Morocco) — _target(None) picks the first
    # company alphabetically (China), which silently yields an empty preview
    target = _target(company or SALES)
    if not (target and item_code):
        frappe.throw("company and item_code required")
    tc = _tc(item_code=item_code)
    fx = _fx_series()
    # evidence: the most recent source lines (Maslak invoices; else Morocco receipts)
    ev = frappe.db.sql(
        """SELECT pi.name doc, pi.posting_date dt, pi.supplier, 'TRY' cur,
                  ROUND(pii.qty,0) qty, ROUND(pii.base_rate,2) rate
           FROM `tabPurchase Invoice Item` pii JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
           WHERE pi.company=%s AND pi.docstatus=1 AND pii.item_code=%s AND pii.qty>0
           ORDER BY pi.posting_date DESC LIMIT 5""", (SOURCING, item_code), as_dict=True)
    if not ev:
        ev = frappe.db.sql(
            """SELECT pr.name doc, pr.posting_date dt, pr.supplier, pr.currency cur,
                      ROUND(pri.qty,0) qty, ROUND(pri.rate,2) rate
               FROM `tabPurchase Receipt Item` pri JOIN `tabPurchase Receipt` pr ON pr.name=pri.parent
               WHERE pr.company=%s AND pr.docstatus=1 AND pri.item_code=%s AND pri.qty>0
               ORDER BY pr.posting_date DESC LIMIT 5""", (target, item_code), as_dict=True)
    for e in ev:
        e["rate_mad"] = round(_to_mad_fast(e["rate"], e["cur"], e["dt"], fx), 2)
        e["dt"] = str(e["dt"] or "")
    # per-bin dry-run at the true cost (None-safe when unpriced)
    rate = flt(tc.get("cost_mad")) if tc.get("cost_mad") else 0
    bins, writedown = [], 0.0
    for b in _fix_bins(target, item_code):
        delta = round((rate - flt(b.vr)) * flt(b.qty), 2) if rate > 0 else None
        if delta is not None:
            writedown += delta
        bins.append({"warehouse": b.warehouse, "qty": round(flt(b.qty)),
                     "old_rate": round(flt(b.vr), 2), "new_rate": rate or None, "delta": delta})
    return {"item_code": item_code, "true_cost": tc, "evidence": ev,
            "bins": bins, "net_change": round(writedown, 2),
            "fixed": _fixed_action(item_code)}


@frappe.whitelist()
def fix_item_cost(company=None, item_code=None, rate=None, note=None):
    """The reviewer's Fix button: revalue EVERY bin of this product to the
    verified rate in ONE today-dated Stock Reconciliation. `rate` defaults to
    the true-cost benchmark; overriding it (reviewer found a different verified
    figure) requires a note. Gated, audited, reversible; the action references
    the Item so the catalogue can show it as fixed."""
    assert_can_write()
    target = _target(company)
    if not (target and item_code):
        frappe.throw("company and item_code required")
    from accounting_portal.api.cost_trace import true_cost as _tc
    tc = _tc(item_code=item_code)
    bench = flt(tc.get("cost_mad")) if tc.get("cost_mad") else 0
    r = flt(rate) if rate not in (None, "") else bench
    if r <= 0:
        frappe.throw("A positive verified rate is required (this product has no cost source — enter it manually)")
    if bench > 0 and abs(r - bench) / bench > 0.005 and not (note or "").strip():
        frappe.throw(f"Rate {r} differs from the evidence-based cost {bench} — a note explaining the override is required")
    date = nowdate()   # today-dated cutover: no back-dated repost, cheap + safe
    rows, impact = [], 0.0
    for b in _fix_bins(target, item_code):
        if abs(r - flt(b.vr)) < 0.01:
            continue
        rows.append({"item_code": item_code, "warehouse": b.warehouse, "rate": r})
        impact += abs((r - flt(b.vr)) * flt(b.qty))
    if not rows:
        frappe.throw("Nothing to fix — every bin is already at this rate")
    return _actions.execute(
        REVAL_ACTION, target, f"itemfix:{item_code}:{r}:{date}",
        payload={"date": date, "rows": rows},
        amount=round(impact, 2),
        reference_doctype="Item", reference_name=item_code,
        notes=(note or f"Verified cost fix — {item_code} → {r} ({tc.get('source')})"))


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
