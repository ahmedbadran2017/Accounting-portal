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
from frappe.utils import flt, nowdate, now_datetime

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
           ORDER BY posting_date DESC, posting_time DESC, creation DESC LIMIT 1""", (item_code, warehouse, date))
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
    # atomic like the bulk poster: the gateway commits Failed markers, so a
    # mid-submit exception must not leak a draft/half-submitted reconciliation
    frappe.db.savepoint("valfix_atomic")
    try:
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
    except Exception:
        frappe.db.rollback(save_point="valfix_atomic")
        raise
    return {"voucher_type": "Stock Reconciliation", "voucher_no": doc.name,
            "result": f"{p['item_code']} @ {p['warehouse']} → {p['rate']}"}


def _sync_bin_from_ledger(item_code, warehouse):
    """Refresh the Bin cache from the last ACTIVE ledger entry. Cancelling a
    today-dated reco leaves no later SLEs to trigger a repost, so ERPNext can
    leave Bin.valuation_rate stale (seen on DEV) — this closes that gap."""
    last = frappe.db.sql(
        """SELECT qty_after_transaction q, valuation_rate vr, stock_value sv
           FROM `tabStock Ledger Entry`
           WHERE item_code=%s AND warehouse=%s AND is_cancelled=0
           ORDER BY posting_date DESC, posting_time DESC, creation DESC LIMIT 1""",
        (item_code, warehouse), as_dict=True)
    name = frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse})
    if not (last and name):
        return
    b = frappe.get_doc("Bin", name)
    l = last[0]
    b.db_set("actual_qty", flt(l.q))
    b.db_set("valuation_rate", flt(l.vr))
    b.db_set("stock_value", flt(l.sv))


def _valfix_reverter(action):
    # a retro fix posts a CHAIN of recos (anchor + one pin per poisoned date);
    # revert must cancel every link, newest first, then the anchor voucher
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    cancelled, pin_bins = 0, set()
    for nm in reversed(p.get("posted_pins") or []):
        if frappe.db.exists("Stock Reconciliation", nm):
            d = frappe.get_doc("Stock Reconciliation", nm)
            for it in d.items:
                pin_bins.add((it.item_code, it.warehouse))
            if d.docstatus == 1:
                d.cancel()
                cancelled += 1
    if action.voucher_no and frappe.db.exists("Stock Reconciliation", action.voucher_no):
        doc = frappe.get_doc("Stock Reconciliation", action.voucher_no)
        rows = [(r.item_code, r.warehouse) for r in doc.items]
        if doc.docstatus == 1:
            doc.cancel()
        for item_code, warehouse in rows:
            pin_bins.add((item_code, warehouse))
    for item_code, warehouse in pin_bins:
        _sync_bin_from_ledger(item_code, warehouse)
    pending = frappe.db.count("Repost Item Valuation", {"docstatus": 1, "status": "Queued"})
    return {"voucher_type": "Stock Reconciliation", "voucher_no": action.voucher_no,
            "result": "cancelled" + (f" (+{cancelled} retro pin(s))" if cancelled else "")
                      + (f" — {pending} repost(s) queued: run the drain" if pending else "")}


_actions.register_poster(FIX_ACTION, _valfix_poster)
_actions.register_reverter(FIX_ACTION, _valfix_reverter)


REVAL_ACTION = "Revalue inventory (bulk)"


def _reval_rows(target, bins, date):
    """Resolve the requested bins to reconciliation rows at the FULL rate —
    product benchmark + frozen landed layer, the SAME basis the single-item fix
    applies (two paths at different rates would see-saw the same bins). Skips
    bins with no benchmark, no stock on that date, or already at the right
    rate. Carries each bin's qty AS OF `date`."""
    from accounting_portal.api.landed_prep import _landed_units_bulk
    item_codes = list({b["item_code"] for b in bins})
    bench = _benchmarks(target, item_codes)
    landed = _landed_units_bulk(item_codes)
    rows, impact = [], 0.0
    for b in bins:
        ic, wh = b.get("item_code"), b.get("warehouse")
        bm = bench.get(ic)
        if not bm or bm <= 0:
            continue
        bm = round(flt(bm) + flt(landed.get(ic)), 2)
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
    if effective_date and str(effective_date)[:10] < nowdate():
        frappe.throw("Back-dated bulk revaluation is disabled: a single back-dated reco "
                     "does not stick (later wrong-rate entries re-poison the average) — "
                     "use the per-item fix with Retro instead, which pins every polluted day")
    target = _target(company)
    bins = json.loads(bins) if isinstance(bins, str) else (bins or [])
    if not (target and bins):
        frappe.throw("company and bins are required")
    from accounting_portal.api.landed_prep import get_basis
    if not get_basis():
        frappe.throw("Landed basis is not frozen yet — bulk revaluation applies the FULL "
                     "(product + landed) rate; freeze the basis first")
    # default TODAY (cutover regime) — a back-dated default invited double
    # correction with the monthly true-ups (audit P1-1)
    date = str(effective_date or nowdate())[:10]
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
    # Re-resolve EVERYTHING at post time, not just qty: a stored payload can be
    # stale (a Failed action retried under the same dedupe key replays its old
    # rows), so re-filter bins that ERPNext would reject — disabled warehouses
    # and actively-reserved stock — instead of trusting the captured list.
    release_whs = set(p.get("release_whs") or [])
    rsv_cache = {}
    items, any_change = [], False
    for r in p["rows"]:
        q, vr = _state_asof(r["item_code"], r["warehouse"], date)
        if q <= 0:
            continue
        if frappe.db.get_value("Warehouse", r["warehouse"], "disabled"):
            continue
        if r["item_code"] not in rsv_cache:
            rsv_cache[r["item_code"]] = _reserved_by_wh(r["item_code"])
        if flt(rsv_cache[r["item_code"]].get(r["warehouse"])) and r["warehouse"] not in release_whs:
            continue
        if abs(flt(r["rate"]) - vr) >= 0.005:
            any_change = True
        items.append({"item_code": r["item_code"], "warehouse": r["warehouse"],
                      "qty": q, "valuation_rate": flt(r["rate"])})
    if not items:
        frappe.throw("No postable bins — everything is empty on the effective date, reserved, or in a disabled warehouse")
    # ERPNext refuses a reconciliation where NO row changes anything ("None of
    # the items have any change…"). A book that already sits at the target rate
    # is a SUCCESS, not an error — skip the anchor doc, still walk the pin
    # chain (interim eras may deviate), and post nothing if the chain is clean.
    base_ic, base_rate = items[0]["item_code"], flt(items[0]["valuation_rate"])
    # ATOMIC: the gateway's Failed handler commits after marking the action, so a
    # mid-submit failure here must leave NOTHING behind (the DEV test leaked a
    # draft and a half-submitted reco). Savepoint + rollback = all-or-nothing —
    # including the temporary reservation release below.
    frappe.db.savepoint("reval_atomic")
    try:
        # temp-release reservations on the bins marked for release; they are
        # re-created right after the reco posts. If ANYTHING fails, the
        # rollback restores the original reservations untouched.
        released_sos = []
        item_codes = {i["item_code"] for i in items}
        pin_whs = {wh for pin in (p.get("retro_pins") or []) for wh in pin["whs"]}
        for ic in item_codes:
            whs = [i["warehouse"] for i in items
                   if i["item_code"] == ic and i["warehouse"] in release_whs]
            # retro-pin warehouses marked for release are cycled too, even when
            # the anchor rows don't touch them
            whs += [w for w in pin_whs if w in release_whs and w not in whs]
            if whs:
                released_sos += _release_reservations(ic, whs)
        doc = None
        if any_change:
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
        # retro chain: re-pin the rate at the end of every poisoned day after
        # the anchor (deviant manual receipts / FX receipts / old-rate returns
        # re-drag the average — the canary proved one anchor is not enough)
        posted_pins = []
        # re-resolve the PIN PLAN too (same doctrine as the rows above): a
        # Failed action retried later must pin pollution that arrived since
        # the plan was captured, not replay the stale list. Schedule mode
        # (retro_sched) rebuilds the whole time-phased plan.
        if p.get("retro_pins") or p.get("retro_sched"):
            rs = p.get("retro_sched") or {}
            sched = []
            if flt(rs.get("product")) > 0:
                from accounting_portal.api.shipment_costing import retro_schedule
                try:
                    sched = retro_schedule(base_ic, flt(rs["product"]),
                                           year=rs.get("year"))
                except Exception:
                    sched = []
            final_rate = flt(sched[-1]["rate"]) if sched else base_rate
            p["retro_pins"] = _pins_from_sched(
                company, base_ic, date, final_rate, sched)
        for pin in (p.get("retro_pins") or []):
            pin_items, pin_change = [], False
            for wh in pin["whs"]:
                q_pin, vr_pin = _state_asof(base_ic, wh, pin["date"])
                if q_pin <= 0 or frappe.db.get_value("Warehouse", wh, "disabled"):
                    continue
                pr = flt(pin.get("rate") or base_rate)
                if abs(pr - vr_pin) >= 0.005:
                    pin_change = True
                pin_items.append({"item_code": base_ic, "warehouse": wh,
                                  "qty": q_pin, "valuation_rate": pr})
            if not pin_items or not pin_change:
                continue
            pd_doc = frappe.get_doc({
                "doctype": "Stock Reconciliation", "company": company,
                "purpose": "Stock Reconciliation",
                "posting_date": pin["date"], "posting_time": "23:59:00", "set_posting_time": 1,
                "expense_account": frappe.get_cached_value("Company", company, "stock_adjustment_account"),
                "cost_center": frappe.get_cached_value("Company", company, "cost_center"),
                "items": pin_items,
            })
            pd_doc.insert(ignore_permissions=True)
            pd_doc.submit()
            posted_pins.append(pd_doc.name)
        if posted_pins:
            p["posted_pins"] = posted_pins
            action.db_set("payload", json.dumps(p), update_modified=False)
        _restore_reservations(sorted(set(released_sos)))
    except Exception:
        frappe.db.rollback(save_point="reval_atomic")
        raise
    if not doc and not posted_pins:
        return {"voucher_type": None, "voucher_no": None,
                "result": f"book already at the target rate @ {date} — nothing to post ({len(items)} bin(s) verified)"}
    return {"voucher_type": "Stock Reconciliation",
            "voucher_no": doc.name if doc else posted_pins[0],
            "result": (f"revalued {len(items)} bins @ {date}" if doc
                       else f"anchor already correct @ {date}")
                      + (f" + {len(posted_pins)} retro pin(s)" if posted_pins else "")
                      + (f" (reservations cycled on {len(release_whs)} bin(s))" if release_whs else "")}


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
        """SELECT b.warehouse, b.actual_qty qty, b.valuation_rate vr,
                  IFNULL(w.disabled,0) wh_disabled
           FROM `tabBin` b JOIN `tabWarehouse` w ON w.name=b.warehouse
           WHERE w.company=%s AND b.item_code=%s AND b.actual_qty>0
           ORDER BY b.stock_value DESC""", (target, item_code), as_dict=True)


def _reserved_by_wh(item_code):
    """Active stock reservations per warehouse for this item. ERPNext blocks a
    Stock Reconciliation on a reserved bin ('units are reserved… please
    un-reserve') — so the fix must SKIP those bins and catch them later once
    the reservation ships or is released."""
    try:
        rows = frappe.db.sql(
            """SELECT warehouse, SUM(reserved_qty - IFNULL(delivered_qty,0)) q
               FROM `tabStock Reservation Entry`
               WHERE item_code=%s AND docstatus=1
                 AND status NOT IN ('Delivered','Cancelled')
               GROUP BY warehouse HAVING q>0""", (item_code,), as_dict=True)
        return {r.warehouse: flt(r.q) for r in rows}
    except Exception:
        return {}   # site without the reservation doctype


def _active_sres(item_code, warehouse):
    """Active Stock Reservation Entries blocking a reco on this bin."""
    try:
        return frappe.get_all(
            "Stock Reservation Entry",
            filters={"item_code": item_code, "warehouse": warehouse, "docstatus": 1,
                     "status": ["not in", ["Delivered", "Cancelled"]]},
            fields=["name", "voucher_type", "voucher_no"])
    except Exception:
        return []


def _release_reservations(item_code, warehouses):
    """Cancel the bins' active reservations so the reco can post. Returns the
    affected Sales Orders for restoration. Runs INSIDE the poster's savepoint —
    a failure anywhere rolls the cancellations back too."""
    sos = set()
    for wh in warehouses:
        for sre in _active_sres(item_code, wh):
            doc = frappe.get_doc("Stock Reservation Entry", sre.name)
            doc.cancel()
            if sre.voucher_type == "Sales Order" and sre.voucher_no:
                sos.add(sre.voucher_no)
    return sorted(sos)


def _restore_reservations(sales_orders):
    """Re-reserve for the affected Sales Orders via ERPNext's own API — it
    reserves each SO item's remaining undelivered qty against available stock,
    reproducing what was released."""
    if not sales_orders:
        return
    from erpnext.stock.doctype.stock_reservation_entry.stock_reservation_entry import (
        create_stock_reservation_entries_for_so_items)
    for so in sales_orders:
        try:
            doc = frappe.get_doc("Sales Order", so)
            if doc.docstatus == 1:
                create_stock_reservation_entries_for_so_items(doc, notify=False)
        except Exception:
            # restoration must never kill the posted fix — log, don't fail
            frappe.log_error(f"re-reservation failed for {so}", "valuation fix")


def _fixed_action(item_code):
    """The LATEST posted fix action for this product, if any (drives the ✓
    badge) — ordered so a re-fix after a basis change shows the new voucher."""
    return frappe.db.get_value(
        "Accounting Portal Action",
        {"action_type": REVAL_ACTION, "status": "Posted",
         "reference_doctype": "Item", "reference_name": item_code},
        ["name", "voucher_no", "posted_on"], as_dict=True,
        order_by="posted_on desc")


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
        # LOCAL supplier invoices (MAD) — the domestic product's truth
        ev = frappe.db.sql(
            """SELECT pi.name doc, pi.posting_date dt, pi.supplier, 'MAD' cur,
                      ROUND(pii.qty,0) qty, ROUND(pii.base_rate,2) rate
               FROM `tabPurchase Invoice Item` pii
               JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
               JOIN `tabSupplier` s ON s.name=pi.supplier
               WHERE pi.company=%s AND pi.docstatus=1 AND pii.item_code=%s AND pii.qty>0
                 AND IFNULL(s.supplier_group,'') IN ('Morocco Local Suppliers', 'Local')
               ORDER BY pi.posting_date DESC LIMIT 5""", (target, item_code), as_dict=True)
    if not ev:
        ev = frappe.db.sql(
            """SELECT pr.name doc, pr.posting_date dt, pr.supplier, pr.currency cur,
                      ROUND(pri.qty,0) qty, ROUND(pri.rate,2) rate
               FROM `tabPurchase Receipt Item` pri JOIN `tabPurchase Receipt` pr ON pr.name=pri.parent
               WHERE pr.company=%s AND pr.docstatus=1 AND pri.item_code=%s AND pri.qty>0
               ORDER BY pr.posting_date DESC LIMIT 5""", (target, item_code), as_dict=True)
    if not ev:
        # FAMILY evidence — a variant's invoice usually lives on a sibling
        # size/colour or the template (one code per model, one price across
        # variants). Show WHICH member each line came from (`via`).
        from accounting_portal.api.cost_trace import _family_members
        _, members = _family_members(item_code)
        if members:
            fam = tuple(members)
            ev = frappe.db.sql(
                """SELECT pi.name doc, pi.posting_date dt, pi.supplier, 'TRY' cur,
                          ROUND(pii.qty,0) qty, ROUND(pii.base_rate,2) rate, pii.item_code via_item
                   FROM `tabPurchase Invoice Item` pii JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
                   WHERE pi.company=%s AND pi.docstatus=1 AND pii.item_code IN %s AND pii.qty>0
                   ORDER BY pi.posting_date DESC LIMIT 5""", (SOURCING, fam), as_dict=True)
            if not ev:
                ev = frappe.db.sql(
                    """SELECT pi.name doc, pi.posting_date dt, pi.supplier, 'MAD' cur,
                              ROUND(pii.qty,0) qty, ROUND(pii.base_rate,2) rate, pii.item_code via_item
                       FROM `tabPurchase Invoice Item` pii
                       JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
                       JOIN `tabSupplier` sp ON sp.name=pi.supplier
                       WHERE pi.company=%s AND pi.docstatus=1 AND pii.item_code IN %s AND pii.qty>0
                         AND IFNULL(sp.supplier_group,'') IN ('Morocco Local Suppliers', 'Local')
                       ORDER BY pi.posting_date DESC LIMIT 5""", (target, fam), as_dict=True)
            if not ev:
                ev = frappe.db.sql(
                    """SELECT pr.name doc, pr.posting_date dt, pr.supplier, pr.currency cur,
                              ROUND(pri.qty,0) qty, ROUND(pri.rate,2) rate, pri.item_code via_item
                       FROM `tabPurchase Receipt Item` pri JOIN `tabPurchase Receipt` pr ON pr.name=pri.parent
                       WHERE pr.company=%s AND pr.docstatus=1 AND pri.item_code IN %s AND pri.qty>0
                       ORDER BY pr.posting_date DESC LIMIT 5""", (target, fam), as_dict=True)
            for e in ev:
                e["via"] = frappe.db.get_value("Item", e.pop("via_item"), "custom_sku") or ""
    for e in ev:
        e["rate_mad"] = round(_to_mad_fast(e["rate"], e["cur"], e["dt"], fx), 2)
        e["dt"] = str(e["dt"] or "")
    # landed layer (B5): frozen basis × item weight — added ON TOP of product cost
    from accounting_portal.api.landed_prep import get_basis, landed_unit
    basis = get_basis()
    landed = landed_unit(item_code) if basis else 0.0
    # per-bin dry-run at the FULL rate (product + landed); None-safe when unpriced.
    # Reserved/disabled bins are marked skipped — ERPNext blocks recos on them.
    product = flt(tc.get("cost_mad")) if tc.get("cost_mad") else 0
    rate = round(product + landed, 2) if product > 0 else 0
    reserved = _reserved_by_wh(item_code)
    bins, writedown, skipped = [], 0.0, 0
    for b in _fix_bins(target, item_code):
        rsv = flt(reserved.get(b.warehouse))
        # reserved bins are no longer skipped — the fix cycles their
        # reservations (release → reco → re-reserve, atomic). Only a disabled
        # warehouse still blocks.
        blocked = bool(b.wh_disabled)
        delta = round((rate - flt(b.vr)) * flt(b.qty), 2) if (rate > 0 and not blocked) else None
        if delta is not None:
            writedown += delta
        if blocked:
            skipped += 1
        bins.append({"warehouse": b.warehouse, "qty": round(flt(b.qty)),
                     "old_rate": round(flt(b.vr), 2), "new_rate": rate or None,
                     "delta": delta, "reserved": round(rsv) or None,
                     "cycle": bool(rsv) and not blocked,
                     "disabled": int(b.wh_disabled or 0) or None})
    w = flt(frappe.db.get_value("Item", item_code, "weight_per_unit"))
    trk = frappe.db.get_value("Item", item_code, ["has_batch_no", "has_serial_no"], as_dict=True) or {}
    return {"item_code": item_code, "true_cost": tc, "evidence": ev,
            "batch_tracked": bool(trk.get("has_batch_no") or trk.get("has_serial_no")),
            "bins": bins, "net_change": round(writedown, 2), "skipped_reserved": skipped,
            # rate_kg = this item's EFFECTIVE rate (its receipts' air/sea mix), not a global
            "landed": {"frozen": bool(basis), "weight": w, "unit": landed,
                       "rate_kg": round(landed / w, 2) if w > 0 else 0},
            "fixed": _fixed_action(item_code)}


def _holding_whs(target, item_code, date):
    """Enabled warehouses that held this item at the END of `date`."""
    whs = [w[0] for w in frappe.db.sql(
        """SELECT DISTINCT sle.warehouse FROM `tabStock Ledger Entry` sle
           JOIN `tabWarehouse` w ON w.name=sle.warehouse
           WHERE sle.company=%s AND sle.item_code=%s AND sle.is_cancelled=0
             AND sle.posting_date <= %s AND IFNULL(w.disabled,0)=0""",
        (target, item_code, date))]
    return [wh for wh in whs if _qty_asof(item_code, wh, date) > 0]


def _pins_from_sched(target, item_code, anchor, final_rate, sched):
    """Merge the SCHEDULE pins (each era's simulated average at its receipt
    date) with the POISON pins (deviant incomings, judged against their ERA's
    rate). Schedule pins cover every holding warehouse; a poison date already
    covered by a schedule pin is skipped."""
    pins, seen = [], set()
    for pnt in (sched[1:] if sched else []):
        whs = _holding_whs(target, item_code, pnt["date"])
        if whs:
            pins.append({"date": pnt["date"], "whs": whs, "rate": pnt["rate"]})
            seen.add(pnt["date"])
    for pp in _retro_pins(target, item_code, anchor, final_rate, sched=sched):
        if pp["date"] not in seen:
            pins.append(pp)
    pins.sort(key=lambda x: x["date"])
    return pins


def _state_asof(item_code, warehouse, date):
    """(qty, valuation_rate) at the END of `date` — the back-dated reco must
    carry that day's quantity, and the old rate prices the impact estimate."""
    r = frappe.db.sql(
        """SELECT qty_after_transaction q, valuation_rate vr
           FROM `tabStock Ledger Entry`
           WHERE item_code=%s AND warehouse=%s AND is_cancelled=0 AND posting_date <= %s
           ORDER BY posting_date DESC, posting_time DESC, creation DESC LIMIT 1""",
        (item_code, warehouse, date), as_dict=True)
    return (flt(r[0].q), flt(r[0].vr)) if r else (0.0, 0.0)


def _retro_pins(target, item_code, anchor, rate, tolerance=0.02, sched=None):
    """The chain that makes retro actually stick (canary lesson): one anchor
    reco is NOT enough — every later wrong-rate incoming (manual receipt, FX
    receipt, sales return at an old rate) re-poisons the moving average. So the
    fix pins the rate again at the END of every day a deviant incoming landed:
    [{date, whs}] for every (date, warehouse) with an incoming whose rate is
    off by more than `tolerance` from the verified cost."""
    rows = frappe.db.sql(
        """SELECT sle.posting_date d, sle.warehouse wh, sle.incoming_rate r
           FROM `tabStock Ledger Entry` sle
           JOIN `tabWarehouse` w ON w.name=sle.warehouse
           WHERE sle.company=%s AND sle.item_code=%s AND sle.is_cancelled=0
             AND sle.actual_qty>0 AND sle.posting_date > %s
             AND IFNULL(w.disabled,0)=0""", (target, item_code, anchor), as_dict=True)
    def rate_at(d):
        # era rate: the last schedule point at/before this date (time-phased
        # retro) — falls back to the single final rate (uniform retro)
        era = rate
        for pnt in (sched or []):
            if pnt["date"] <= d:
                era = flt(pnt["rate"])
            else:
                break
        return era
    by_date = {}
    for x in rows:
        era = rate_at(str(x.d))
        if era > 0 and abs(flt(x.r) - era) / era > tolerance:
            by_date.setdefault(str(x.d), set()).add(x.wh)
    return [{"date": d, "whs": sorted(by_date[d]), "rate": round(rate_at(d), 2)}
            for d in sorted(by_date)]


def _retro_anchor(target, item_code):
    """The earliest date a retro fix may take effect: the item's first receipt
    in the company, clamped to the policy floor (closed years never restate).
    Falls back to today when there is no history to heal."""
    r = frappe.db.sql(
        """SELECT MIN(posting_date) FROM `tabStock Ledger Entry`
           WHERE company=%s AND item_code=%s AND is_cancelled=0 AND actual_qty>0""",
        (target, item_code))
    first = str(r[0][0]) if r and r[0][0] else None
    if not first:
        # reco-born items (opening dumps) have no receipt SLE — anchor on the
        # first moment the item actually held stock instead
        r = frappe.db.sql(
            """SELECT MIN(posting_date) FROM `tabStock Ledger Entry`
               WHERE company=%s AND item_code=%s AND is_cancelled=0
                 AND qty_after_transaction > 0""", (target, item_code))
        first = str(r[0][0]) if r and r[0][0] else None
    if not first:
        return nowdate()
    anchor = max(first, _POLICY_FLOOR)
    # the LM2C3110 case: first receipt was pre-2026 but the stock ran dry
    # before the floor — anchoring at the floor finds nothing to fix. Fall
    # FORWARD to the first incoming on/after the floor instead.
    if anchor == _POLICY_FLOOR and first < _POLICY_FLOOR:
        # SUM(actual_qty) lies here: a zeroing Stock Reconciliation carries
        # actual_qty=0 while resetting the balance — so ask the ledger which
        # warehouses actually HELD stock at the floor instead
        if not _holding_whs(target, item_code, _POLICY_FLOOR):
            nxt = frappe.db.sql(
                """SELECT MIN(posting_date) FROM `tabStock Ledger Entry`
                   WHERE company=%s AND item_code=%s AND is_cancelled=0
                     AND actual_qty>0 AND posting_date >= %s""",
                (target, item_code, _POLICY_FLOOR))
            anchor = str(nxt[0][0]) if nxt and nxt[0][0] else nowdate()
    return anchor if anchor < nowdate() else nowdate()


@frappe.whitelist()
def fix_item_cost(company=None, item_code=None, rate=None, note=None, full_rate=0,
                  retro=0, retro_product=None, retro_year=None):
    """The reviewer's Fix button: revalue EVERY bin of this product in ONE
    today-dated Stock Reconciliation at the FULL rate = verified PRODUCT cost
    (`rate`, defaults to the evidence-based figure; overriding requires a note)
    + the frozen landed layer (rate/kg × item weight). Requires the landed basis
    to be frozen first — enforces the single-crawl discipline. Gated, audited,
    reversible; the action references the Item for the catalogue's ✓."""
    assert_can_write()
    target = _target(company)
    if not (target and item_code):
        frappe.throw("company and item_code required")
    trk = frappe.db.get_value("Item", item_code, ["has_batch_no", "has_serial_no"], as_dict=True)
    if trk and (trk.has_batch_no or trk.has_serial_no):
        # a plain reco row can't carry a Serial/Batch Bundle — fail with a clear
        # message instead of ERPNext's raw "Please add Serial and Batch Bundle"
        frappe.throw(f"{item_code} is batch/serial-tracked — revaluation needs a batch bundle; "
                     "handle this item via ERPNext Stock Reconciliation for now (excluded from the portal fix)")
    from accounting_portal.api.cost_trace import true_cost as _tc
    from accounting_portal.api.landed_prep import get_basis, landed_unit
    basis = get_basis()
    full_rate = str(full_rate) in ("1", "true", "True")
    if full_rate:
        # shipment-submit path: the caller already computed product + LIVE
        # landed (its shipments' actual costs) — no frozen basis needed, and
        # nothing is added on top. A note documenting the split is required.
        r = round(flt(rate), 2)
        if r <= 0:
            frappe.throw("A positive full rate is required")
        if not (note or "").strip():
            frappe.throw("A note documenting the product + landed split is required")
        product, landed = r, 0.0
        tc = _tc(item_code=item_code)
    else:
        if not basis:
            frappe.throw("Landed basis is not frozen yet — review & freeze it in the Landed Cockpit first, "
                         "so the catalogue is crawled ONCE at the full (product + landed) cost")
        tc = _tc(item_code=item_code)
        bench = flt(tc.get("cost_mad")) if tc.get("cost_mad") else 0
        product = flt(rate) if rate not in (None, "") else bench
        if product <= 0:
            frappe.throw("A positive verified product cost is required (this product has no cost source — enter it manually)")
        if bench > 0 and abs(product - bench) / bench > 0.005 and not (note or "").strip():
            frappe.throw(f"Rate {product} differs from the evidence-based cost {bench} — a note explaining the override is required")
        landed = landed_unit(item_code)
        r = round(product + landed, 2)   # the FULL applied rate
    retro = str(retro) in ("1", "true", "True")
    # time-phased schedule (each shipment prices its own era) — available when
    # the caller supplies the PRODUCT split; empty for locals/no-import items
    sched = []
    if retro and flt(retro_product) > 0:
        from accounting_portal.api.shipment_costing import retro_schedule
        try:
            sched = retro_schedule(item_code, flt(retro_product), year=retro_year)
        except Exception:
            sched = []
    if sched:
        date = max(sched[0]["date"], _POLICY_FLOOR)
        r = flt(sched[-1]["rate"])   # final-era average = the ONE-TRUTH applied rate
    else:
        date = _retro_anchor(target, item_code) if retro else nowdate()
    retro = retro and date < nowdate()   # no history → degenerates to today mode
    if not retro:
        sched = []
    anchor_rate = flt(sched[0]["rate"]) if sched else r
    reserved = _reserved_by_wh(item_code)
    rows, impact, skipped, release_whs, retro_pins = [], 0.0, [], [], []
    if retro:
        # RETRO: reco lands at the anchor date and ERPNext reposts every later
        # SLE — old COGS heals inside the stock ledger itself. Rows come from
        # the warehouses that held stock ON that date (not today's bins), at
        # that day's quantity (the poster re-resolves via _qty_asof). Current
        # rate being "already correct" is NOT a skip reason here: the whole
        # point is repricing the interim months.
        whs = [w[0] for w in frappe.db.sql(
            """SELECT DISTINCT sle.warehouse FROM `tabStock Ledger Entry` sle
               JOIN `tabWarehouse` w ON w.name=sle.warehouse
               WHERE sle.company=%s AND sle.item_code=%s AND sle.is_cancelled=0
                 AND sle.posting_date <= %s AND IFNULL(w.disabled,0)=0""",
            (target, item_code, date))]
        for wh in whs:
            q_then, vr_then = _state_asof(item_code, wh, date)
            if q_then <= 0:
                continue
            if flt(reserved.get(wh)):
                release_whs.append(wh)
            rows.append({"item_code": item_code, "warehouse": wh, "rate": anchor_rate})
            impact += abs((anchor_rate - vr_then) * q_then)
        if not rows:
            # nothing held stock on the anchor day — degrade gracefully to the
            # today-dated fix instead of failing the whole submit
            retro = False
            sched = []
            date = nowdate()
            anchor_rate = r
        retro_pins = _pins_from_sched(target, item_code, date, r, sched) if retro else []
        # pin warehouses that are reserved TODAY need the same release/re-reserve
        # cycle, or the pin reco trips ERPNext's reservation validation
        for pin in retro_pins:
            for wh in pin["whs"]:
                if flt(reserved.get(wh)) and wh not in release_whs:
                    release_whs.append(wh)
    if not retro:
        rows, release_whs, correct = [], [], []
        for b in _fix_bins(target, item_code):
            if abs(r - flt(b.vr)) < 0.01:
                correct.append({"item_code": item_code, "warehouse": b.warehouse, "rate": r})
                continue
            if flt(reserved.get(b.warehouse)):
                # reserved bins are INCLUDED: the poster releases the reservations,
                # posts the reco, then re-reserves via ERPNext's own API — atomic
                # (any failure rolls it all back). Orders reserve 24/7 here, so
                # "wait for the reservation to ship" never comes.
                release_whs.append(b.warehouse)
                rows.append({"item_code": item_code, "warehouse": b.warehouse, "rate": r})
                impact += abs((r - flt(b.vr)) * flt(b.qty))
                continue
            if b.wh_disabled:
                skipped.append(f"{b.warehouse} (disabled warehouse)")
                continue
            rows.append({"item_code": item_code, "warehouse": b.warehouse, "rate": r})
            impact += abs((r - flt(b.vr)) * flt(b.qty))
        if not rows and correct:
            # already at the target everywhere — record the verification as a
            # Posted no-op (the poster detects zero change and posts no voucher)
            # so the item earns its ✓ instead of a red error
            rows = correct
    if not rows:
        frappe.throw("Nothing fixable now — every bin is already correct or blocked by reservations: "
                     + ("; ".join(skipped) or "none"))
    # content-aware dedupe key: if the postable row-set changes (a reservation
    # cleared, a warehouse toggled), the retry gets a FRESH action instead of
    # replaying a stale Failed payload under the same key.
    wh_sig = frappe.generate_hash(",".join(sorted(x["warehouse"] for x in rows)), 8)
    # retro: the pin plan is part of the identity — new pollution since the last
    # run means a DIFFERENT fix, not a dedupe hit on the old Posted action
    if retro and retro_pins:
        wh_sig += "-" + frappe.generate_hash(json.dumps(retro_pins, sort_keys=True), 8)
    res = _actions.execute(
        REVAL_ACTION, target, f"itemfix:{item_code}:{r}:{date}:{wh_sig}",
        # basis_on stamps WHICH frozen basis this fix used — an unfreeze/refreeze
        # later marks it stale in the catalogue instead of keeping a silent ✓
        # full-rate fixes carry LIVE landed, not the frozen snapshot — stamping
        # the basis would mark them stale on every unfreeze/refreeze and make
        # the batch re-apply already-correct items forever
        payload={"date": date, "rows": rows, "release_whs": release_whs,
                 "basis_on": None if full_rate else (basis or {}).get("on"),
                 "retro_pins": retro_pins if retro else [],
                 "retro_sched": ({"product": flt(retro_product), "year": retro_year}
                                 if (retro and sched) else None)},
        amount=round(impact, 2),
        reference_doctype="Item", reference_name=item_code,
        notes=((note or f"Verified cost fix — {item_code}")
               + ("" if full_rate else f" · product {product} + landed {landed} = {r} ({tc.get('source')})")
               + ((f" · RETRO schedule from {date} ({len(sched)} era(s), final {r})" if sched
                   else f" · RETRO from {date} (reposts later SLEs)") if retro else "")
               + (f" · skipped: {'; '.join(skipped)}" if skipped else "")))
    if isinstance(res, dict):
        res["skipped_reserved"] = skipped
    return res


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


@frappe.whitelist()
def drain_reposts(budget_s=45, names=None):
    """Process queued repost jobs SYNCHRONOUSLY, oldest first, inside a strict
    time budget — the reliable half of the retro engine when the long-queue
    workers sit on jobs (the known Queued gotcha). Each job commits its own
    progress via ERPNext's repost(), so hitting the budget leaves a clean,
    resumable queue. Writers only (a retro apply leaves its jobs here — the
    applier must be able to drain them, or GL lags stock until someone does)."""
    assert_can_write()
    import time
    from erpnext.stock.doctype.repost_item_valuation.repost_item_valuation import repost
    budget = min(flt(budget_s) or 45, 280)   # stay under the gunicorn timeout
    if names and isinstance(names, str):
        names = json.loads(names)
    todo = names or [r.name for r in frappe.get_all(
        "Repost Item Valuation", filters={"docstatus": 1, "status": "Queued"},
        order_by="creation asc", limit_page_length=20, fields=["name"])]
    start, processed, failed = time.monotonic(), [], 0
    for nm in todo:
        if time.monotonic() - start > budget:
            break
        # row-lock the status so two concurrent drains (or a drain racing the
        # background worker) can never run the SAME job twice — interleaved
        # recomputation of one item's SLE chain commits conflicting valuations
        st = frappe.db.get_value("Repost Item Valuation", nm, ["status", "modified"],
                                 as_dict=True, for_update=True)
        stale = st and st.status == "In Progress" and \
            (now_datetime() - st.modified).total_seconds() > 1800
        if not st or (st.status != "Queued" and not stale):
            frappe.db.commit()   # release the row lock
            continue
        doc = frappe.get_doc("Repost Item Valuation", nm)
        try:
            repost(doc)   # In Progress → Completed/Failed; commits internally
        except Exception:
            frappe.log_error(title=f"drain_reposts: {nm}")
        st2 = frappe.db.get_value("Repost Item Valuation", nm, "status")
        if st2 == "Failed":
            failed += 1
        processed.append({"name": nm, "status": st2})
    remaining = frappe.db.count("Repost Item Valuation", {"docstatus": 1, "status": "Queued"})
    backfilled = 0
    if not remaining:
        # queue drained → close the OTHER leak found in the live audit: a sale
        # of zero-valued stock posts NO GL at all; when a later fix reprices its
        # SLE inline (same-day future-SLE processing skips GL regeneration) the
        # ledger moves but the GL never does. Sweep and regenerate.
        try:
            backfilled = backfill_stock_gl()["backfilled"]
        except Exception:
            pass   # the sweep is hygiene, never fail the drain over it
    if processed:
        # the GL just changed historically (reposted vouchers) — stale report
        # caches would show pre-repost numbers for up to their TTL
        try:
            from accounting_portal.api._cache import bust_report_caches
            bust_report_caches(_target(None))
        except Exception:
            pass
    return {"processed": processed, "remaining": remaining,
            "failed": failed, "gl_backfilled": backfilled}


@frappe.whitelist()
def backfill_stock_gl(company=None, days=60):
    """Find stock vouchers whose SLE value no longer matches their stock-account
    GL (the zero-value-sale-repriced-later leak — 12 live DNs found in 30 days)
    and regenerate their GL via ERPNext's own repost_gle_for_stock_vouchers."""
    assert_can_write()
    target = _target(company)
    since = frappe.utils.add_days(nowdate(), -int(days))
    rows = frappe.db.sql("""
        SELECT v, vt, SUM(gl) gl, SUM(sle) sle, MIN(d) d FROM (
          SELECT voucher_no v, voucher_type vt, SUM(debit)-SUM(credit) gl, 0 sle,
                 MIN(posting_date) d
          FROM `tabGL Entry`
          WHERE company=%(c)s AND is_cancelled=0 AND posting_date >= %(s)s
            AND account IN (SELECT name FROM `tabAccount`
                            WHERE company=%(c)s AND account_type='Stock')
          GROUP BY voucher_no, voucher_type
          UNION ALL
          SELECT voucher_no v, voucher_type vt, 0 gl, SUM(stock_value_difference) sle,
                 MIN(posting_date) d
          FROM `tabStock Ledger Entry`
          WHERE company=%(c)s AND is_cancelled=0 AND posting_date >= %(s)s
          GROUP BY voucher_no, voucher_type) t
        GROUP BY v, vt HAVING ABS(SUM(gl)-SUM(sle)) > 0.01
        ORDER BY MIN(d) LIMIT 200""", {"c": target, "s": since}, as_dict=True)
    if not rows:
        return {"backfilled": 0, "vouchers": []}
    from erpnext.accounts.utils import repost_gle_for_stock_vouchers
    repost_gle_for_stock_vouchers([(r.vt, r.v) for r in rows], str(rows[0].d))
    frappe.db.commit()
    try:
        from accounting_portal.api._cache import bust_report_caches
        bust_report_caches(target)
    except Exception:
        pass
    return {"backfilled": len(rows), "vouchers": [r.v for r in rows]}
