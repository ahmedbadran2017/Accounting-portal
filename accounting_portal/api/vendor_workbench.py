"""Vendor Workbench — the vendor-centric cost-correction cockpit.

The vendor is the natural unit of truth: one supplier -> one freight channel
(sea/air/local), one catalogue file, one price list. This workbench walks each
vendor through four steps, then submits the retro correction for all of that
vendor's MOVED products at once:

  1. WEIGHTS  — review/enter unit weights for the vendor's moved items
                (imported vendors only; local vendors skip this step).
  2. FREIGHT  — the vendor's slice of the 770 legacy freight POOL, allocated
                pro-rata by weight so the sum across vendors always equals the
                actual bills. Review-and-confirm, nothing invented per vendor.
  3. COSTS    — review each product's purchase cost (supplier invoice anchored,
                via cost_trace) and fill the gaps.
  4. SUBMIT   — gated: run the existing fix_item_cost(retro) machinery for the
                vendor's items in light batches (the UI sends chunks), with a
                dry-run preview of anchors first so silent retro-degradation
                (anchor day closed at zero) is visible BEFORE posting.

Scope filter everywhere: items with REAL movement only (delivered in 2026 or
on-hand now, sales company) — integration-only ghosts are excluded.

State per vendor is stored in the `ap_vendor_state` default:
  {supplier: {"weights": 1, "freight": 1, "costs": 1, "submitted": [item_codes]}}
"""
import json

import frappe
from frappe.utils import flt

from accounting_portal.api.permissions import assert_portal_access, assert_can_write

SALES = "Justyol Morocco"
SOURCING = "Maslak LTD"
_LOCAL_GROUPS = ("Morocco Local Suppliers", "Local")
_STATE_KEY = "ap_vendor_state"
_CHANNELS_KEY = "ap_freight_channels"

# component/packaging codes ride with their parent product, never alone
_COMPONENT_RE = r"-(box|holder|spoon|tape|bag|label|sticker|carton|cover|packag)"


def _state():
    try:
        return json.loads(frappe.db.get_default(_STATE_KEY) or "{}") or {}
    except Exception:
        return {}


def _save_state(st):
    frappe.db.set_default(_STATE_KEY, json.dumps(st))


def _channels():
    """supplier -> channel (sea/air/china/local) from the stored classification."""
    try:
        cfg = json.loads(frappe.db.get_default(_CHANNELS_KEY) or "{}") or {}
    except Exception:
        cfg = {}
    out = {}
    for ch, sups in cfg.items():
        for s in sups or []:
            out[s] = ch
    return out


def _moved_universe():
    """{item_code: {"sold": qty, "oh": qty}} — delivered 2026 or on-hand now."""
    out = {}
    for r in frappe.db.sql(
            """SELECT dni.item_code ic, SUM(dni.qty) q FROM `tabDelivery Note Item` dni
               JOIN `tabDelivery Note` dn ON dn.name=dni.parent
               WHERE dn.docstatus=1 AND dn.company=%s AND dn.posting_date>='2026-01-01'
               GROUP BY dni.item_code""", (SALES,), as_dict=True):
        out.setdefault(r.ic, {"sold": 0.0, "oh": 0.0})["sold"] = flt(r.q)
    for r in frappe.db.sql(
            """SELECT b.item_code ic, SUM(b.actual_qty) q FROM `tabBin` b
               JOIN `tabWarehouse` w ON w.name=b.warehouse
               WHERE w.company=%s AND b.actual_qty>0 GROUP BY b.item_code""",
            (SALES,), as_dict=True):
        out.setdefault(r.ic, {"sold": 0.0, "oh": 0.0})["oh"] = flt(r.q)
    return out


def _item_vendor_map(item_codes):
    """item -> (supplier, evidence) resolved from purchase docs, best first:
    Morocco PI > Maslak PI > Purchase Receipt (any company). On conflict the
    supplier with the LATEST document wins; count kept for the UI."""
    if not item_codes:
        return {}
    codes = tuple(item_codes)
    best = {}   # ic -> (posting_date, supplier, source)

    def _take(rows, source):
        for r in rows:
            cur = best.get(r.ic)
            if cur is None or (r.dt and str(r.dt) > str(cur[0])):
                best[r.ic] = (r.dt, r.sup, source)

    _take(frappe.db.sql(
        """SELECT pii.item_code ic, pi.supplier sup, MAX(pi.posting_date) dt
           FROM `tabPurchase Invoice Item` pii
           JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
           WHERE pi.docstatus=1 AND pi.company=%s AND pii.item_code IN %s
           GROUP BY pii.item_code, pi.supplier""", (SALES, codes), as_dict=True), "pi_local")
    _take(frappe.db.sql(
        """SELECT pii.item_code ic, pi.supplier sup, MAX(pi.posting_date) dt
           FROM `tabPurchase Invoice Item` pii
           JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
           WHERE pi.docstatus=1 AND pi.company=%s AND pii.item_code IN %s
           GROUP BY pii.item_code, pi.supplier""", (SOURCING, codes), as_dict=True), "pi_maslak")
    # receipts fill the invoice-less tail (the Town Team pattern)
    _take(frappe.db.sql(
        """SELECT pri.item_code ic, pr.supplier sup, MAX(pr.posting_date) dt
           FROM `tabPurchase Receipt Item` pri
           JOIN `tabPurchase Receipt` pr ON pr.name=pri.parent
           WHERE pr.docstatus=1 AND pri.item_code IN %s
           GROUP BY pri.item_code, pr.supplier""", (codes,), as_dict=True), "pr")
    return {ic: {"supplier": v[1], "source": v[2]} for ic, v in best.items() if v[1]}


@frappe.whitelist()
def list_vendors():
    """Every vendor owning moved items, with readiness counters per step."""
    assert_portal_access()
    uni = _moved_universe()
    codes = list(uni)
    vmap = _item_vendor_map(codes)

    # weights + cost flags in bulk
    meta = {}
    for i in range(0, len(codes), 700):
        for r in frappe.db.sql(
                """SELECT name, IFNULL(weight_per_unit,0) w FROM `tabItem`
                   WHERE name IN %s""", (codes[i:i + 700],), as_dict=True):
            meta[r.name] = flt(r.w)
    # cost basis: any submitted PI line (either company)
    haspi = set()
    for i in range(0, len(codes), 700):
        for r in frappe.db.sql(
                """SELECT DISTINCT pii.item_code ic FROM `tabPurchase Invoice Item` pii
                   JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
                   WHERE pi.docstatus=1 AND pi.company IN %s AND pii.item_code IN %s""",
                ((SALES, SOURCING), codes[i:i + 700]), as_dict=True):
            haspi.add(r.ic)

    sup_groups = dict(frappe.db.sql(
        "SELECT name, IFNULL(supplier_group,'') FROM `tabSupplier`"))
    chan = _channels()
    st = _state()

    vendors = {}
    unassigned = {"supplier": None, "items": 0, "sold": 0.0, "oh": 0.0}
    for ic, m in uni.items():
        v = vmap.get(ic, {}).get("supplier")
        if not v:
            unassigned["items"] += 1
            unassigned["sold"] += m["sold"]
            unassigned["oh"] += m["oh"]
            continue
        d = vendors.setdefault(v, {
            "supplier": v,
            "group": sup_groups.get(v, ""),
            "local": sup_groups.get(v, "") in _LOCAL_GROUPS,
            "channel": chan.get(v) or ("local" if sup_groups.get(v, "") in _LOCAL_GROUPS else ""),
            "items": 0, "sold": 0.0, "oh": 0.0,
            "weights_ok": 0, "weights_missing": 0,
            "cost_ok": 0, "cost_missing": 0,
        })
        d["items"] += 1
        d["sold"] += m["sold"]
        d["oh"] += m["oh"]
        if flt(meta.get(ic)) > 0:
            d["weights_ok"] += 1
        else:
            d["weights_missing"] += 1
        if ic in haspi:
            d["cost_ok"] += 1
        else:
            d["cost_missing"] += 1

    out = []
    for v, d in vendors.items():
        s = st.get(v) or {}
        d["sold"] = round(d["sold"])
        d["oh"] = round(d["oh"])
        d["state"] = {
            "weights": 1 if (s.get("weights") or d["local"]) else 0,
            "freight": 1 if (s.get("freight") or d["local"]) else 0,
            "costs": 1 if s.get("costs") else 0,
            "submitted": len(s.get("submitted") or []),
        }
        out.append(d)
    out.sort(key=lambda x: -x["sold"])
    unassigned["sold"] = round(unassigned["sold"])
    unassigned["oh"] = round(unassigned["oh"])
    return {"vendors": out, "unassigned": unassigned,
            "totals": {"vendors": len(out),
                       "items": sum(v["items"] for v in out),
                       "sold": sum(v["sold"] for v in out)}}


@frappe.whitelist()
def vendor_detail(supplier=None):
    """The vendor's moved items with purchase history, weight, cost evidence
    and current book valuation — everything the four steps need."""
    assert_portal_access()
    if not supplier:
        frappe.throw("supplier required")
    uni = _moved_universe()
    codes = list(uni)
    vmap = _item_vendor_map(codes)
    mine = [ic for ic in codes if vmap.get(ic, {}).get("supplier") == supplier]
    if not mine:
        return {"supplier": supplier, "items": [], "summary": {}}

    grp = frappe.db.get_value("Supplier", supplier, "supplier_group") or ""
    local = grp in _LOCAL_GROUPS

    # item master
    meta = {}
    for i in range(0, len(mine), 700):
        for r in frappe.db.sql(
                """SELECT name, item_name, custom_sku sku, IFNULL(weight_per_unit,0) w, image
                   FROM `tabItem` WHERE name IN %s""", (mine[i:i + 700],), as_dict=True):
            meta[r.name] = r
    # purchased history from THIS vendor (qty + latest rate/ccy), PI first then PR
    hist = {}
    for r in frappe.db.sql(
            """SELECT pii.item_code ic, SUM(pii.qty) q, MAX(pi.posting_date) dt
               FROM `tabPurchase Invoice Item` pii
               JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
               WHERE pi.docstatus=1 AND pi.supplier=%s AND pii.item_code IN %s
               GROUP BY pii.item_code""", (supplier, tuple(mine)), as_dict=True):
        hist[r.ic] = {"bought": flt(r.q), "last": str(r.dt or ""), "doc": "PI"}
    for r in frappe.db.sql(
            """SELECT pri.item_code ic, SUM(pri.qty) q, MAX(pr.posting_date) dt
               FROM `tabPurchase Receipt Item` pri
               JOIN `tabPurchase Receipt` pr ON pr.name=pri.parent
               WHERE pr.docstatus=1 AND pr.supplier=%s AND pri.item_code IN %s
               GROUP BY pri.item_code""", (supplier, tuple(mine)), as_dict=True):
        h = hist.setdefault(r.ic, {"bought": 0.0, "last": "", "doc": "PR"})
        if h["doc"] == "PR":
            h["bought"] = max(h["bought"], flt(r.q))
            h["last"] = max(h["last"], str(r.dt or ""))
    # current book rate per item (on-hand weighted)
    book = dict(frappe.db.sql(
        """SELECT b.item_code, SUM(b.stock_value)/NULLIF(SUM(b.actual_qty),0)
           FROM `tabBin` b JOIN `tabWarehouse` w ON w.name=b.warehouse
           WHERE w.company=%s AND b.item_code IN %s GROUP BY b.item_code""",
        (SALES, tuple(mine))))
    # evidence-based product cost (supplier invoice anchored)
    from accounting_portal.api.valuation import _benchmarks
    bench = _benchmarks(SALES, mine)

    items = []
    for ic in mine:
        m = meta.get(ic) or {}
        h = hist.get(ic) or {}
        items.append({
            "item_code": ic,
            "item_name": m.get("item_name"),
            "sku": m.get("sku"),
            "image": m.get("image"),
            "weight_kg": round(flt(m.get("w")), 3),
            "bought": round(flt(h.get("bought"))),
            "last_doc": h.get("doc"), "last_date": h.get("last"),
            "sold": round(uni[ic]["sold"]),
            "oh": round(uni[ic]["oh"]),
            "book_rate": round(flt(book.get(ic)), 2) if book.get(ic) else None,
            "bench": bench.get(ic),
        })
    items.sort(key=lambda x: -x["sold"])
    st = (_state().get(supplier)) or {}
    n_w = sum(1 for x in items if x["weight_kg"] > 0)
    n_c = sum(1 for x in items if x["bench"])
    return {"supplier": supplier, "group": grp, "local": local,
            "channel": _channels().get(supplier) or ("local" if local else ""),
            "items": items,
            "summary": {"items": len(items),
                        "sold": sum(x["sold"] for x in items),
                        "oh": sum(x["oh"] for x in items),
                        "weights_ok": n_w, "weights_missing": len(items) - n_w,
                        "cost_ok": n_c, "cost_missing": len(items) - n_c},
            "state": {"weights": 1 if (st.get("weights") or local) else 0,
                      "freight": 1 if (st.get("freight") or local) else 0,
                      "costs": 1 if st.get("costs") else 0,
                      "submitted": st.get("submitted") or []}}


@frappe.whitelist()
def save_weights(supplier=None, rows=None):
    """Step 1 write: set weight_per_unit for the vendor's items (item master
    only — no GL, no repost). rows = [{item_code, weight_kg}]."""
    assert_can_write()
    if not supplier:
        frappe.throw("supplier required")
    rows = frappe.parse_json(rows or "[]")
    done, skipped = 0, []
    for r in rows:
        ic = (r.get("item_code") or "").strip()
        w = flt(r.get("weight_kg"))
        if not ic or w <= 0 or w > 50:
            skipped.append(ic or "?")
            continue
        frappe.db.set_value("Item", ic, {"weight_per_unit": w, "weight_uom": "Kg"})
        done += 1
    frappe.db.commit()
    return {"saved": done, "skipped": skipped}


@frappe.whitelist()
def freight_summary(supplier=None):
    """Step 2 read: the vendor's pro-rata slice of the 770 freight pool.
    Pool stays GLOBAL per channel (sum over vendors == actual bills)."""
    assert_portal_access()
    if not supplier:
        frappe.throw("supplier required")
    chan = _channels().get(supplier) or ""
    # channel pools: net (ex-VAT) 2026 balances on legacy 770 freight accounts,
    # split by the forwarder classification agreed earlier
    pool = frappe.db.sql(
        """SELECT a.account_number an, SUM(g.debit-g.credit) x
           FROM `tabGL Entry` g JOIN `tabAccount` a ON a.name=g.account
           WHERE g.company=%s AND g.is_cancelled=0
             AND (a.account_number LIKE '770.07%%' OR a.account_number LIKE '770.0.7%%')
             AND a.account_number NOT LIKE '770.07.004%%'
             AND YEAR(g.posting_date)=2026
           GROUP BY a.account_number""", (SALES,), as_dict=True)
    total_pool = round(sum(flt(r.x) for r in pool))
    # vendor's weighted units vs all-imported weighted units (weight × sold+oh)
    uni = _moved_universe()
    codes = list(uni)
    vmap = _item_vendor_map(codes)
    sup_groups = dict(frappe.db.sql(
        "SELECT name, IFNULL(supplier_group,'') FROM `tabSupplier`"))
    w = {}
    for i in range(0, len(codes), 700):
        for r in frappe.db.sql(
                "SELECT name, IFNULL(weight_per_unit,0) x FROM `tabItem` WHERE name IN %s",
                (codes[i:i + 700],), as_dict=True):
            w[r.name] = flt(r.x)
    tot_kg = my_kg = 0.0
    my_units = my_nw = 0
    for ic, m in uni.items():
        sup = vmap.get(ic, {}).get("supplier")
        if not sup or sup_groups.get(sup, "") in _LOCAL_GROUPS:
            continue
        units = m["sold"] + m["oh"]
        kg = w.get(ic, 0.0) * units
        tot_kg += kg
        if sup == supplier:
            my_kg += kg
            my_units += units
            if w.get(ic, 0.0) <= 0:
                my_nw += 1
    share = (my_kg / tot_kg) if tot_kg else 0.0
    return {"supplier": supplier, "channel": chan,
            "pool_mad": total_pool,
            "vendor_kg": round(my_kg, 1), "total_kg": round(tot_kg, 1),
            "share_pct": round(100 * share, 2),
            "vendor_freight_mad": round(total_pool * share),
            "vendor_units": round(my_units), "items_without_weight": my_nw,
            "note": "pool allocation — sum over vendors always equals the actual 770 bills"}


@frappe.whitelist()
def set_step(supplier=None, step=None, done=1):
    """Mark a vendor step reviewed (weights/freight/costs)."""
    assert_can_write()
    if not supplier or step not in ("weights", "freight", "costs"):
        frappe.throw("supplier and a valid step required")
    st = _state()
    v = st.setdefault(supplier, {})
    v[step] = 1 if str(done) in ("1", "true", "True") else 0
    _save_state(st)
    return {"ok": 1, "state": v}


@frappe.whitelist()
def submit_preview(supplier=None, items=None):
    """Step 4 dry-run: for each item show the rate that would be applied and
    the retro anchor date — so silent degradation (anchor at today) is visible
    BEFORE anything posts."""
    assert_portal_access()
    if not supplier:
        frappe.throw("supplier required")
    items = frappe.parse_json(items or "[]")
    from accounting_portal.api.valuation import _benchmarks, _retro_anchor
    bench = _benchmarks(SALES, items) if items else {}
    out = []
    for ic in items:
        b = bench.get(ic)
        anchor = None
        try:
            anchor = _retro_anchor(SALES, ic)
        except Exception:
            anchor = None
        out.append({"item_code": ic, "rate": b,
                    "anchor": str(anchor) if anchor else None,
                    "retro_ok": bool(anchor and str(anchor) < frappe.utils.nowdate()),
                    "no_cost": not b})
    return {"supplier": supplier, "rows": out,
            "ready": sum(1 for r in out if r["rate"] and r["retro_ok"]),
            "no_cost": sum(1 for r in out if r["no_cost"]),
            "anchor_today": sum(1 for r in out if r["rate"] and not r["retro_ok"])}


@frappe.whitelist()
def submit_batch(supplier=None, items=None, note=None):
    """Step 4 write: run fix_item_cost(retro) for a SMALL batch of the vendor's
    items (the UI sends chunks so each action stays light). Existing machinery:
    gating, audit stamps, retro pins, repost — all inherited."""
    assert_can_write()
    if not supplier:
        frappe.throw("supplier required")
    items = frappe.parse_json(items or "[]")
    if not items:
        frappe.throw("no items in batch")
    if len(items) > 25:
        frappe.throw("batch too large — send at most 25 items per submit")
    from accounting_portal.api.valuation import _benchmarks, fix_item_cost
    bench = _benchmarks(SALES, items)
    st = _state()
    v = st.setdefault(supplier, {})
    done = v.setdefault("submitted", [])
    results = []
    for ic in items:
        b = bench.get(ic)
        if not b:
            results.append({"item_code": ic, "result": "skipped — no cost evidence"})
            continue
        try:
            r = fix_item_cost(company=SALES, item_code=ic, rate=b, full_rate=1, retro=1,
                              note=note or f"vendor workbench submit — {supplier}")
            results.append({"item_code": ic, "result": (r or {}).get("result") or "ok"})
            if ic not in done:
                done.append(ic)
        except Exception as e:
            results.append({"item_code": ic, "result": f"error: {e}"})
    _save_state(st)
    return {"supplier": supplier, "results": results,
            "submitted_total": len(done)}
