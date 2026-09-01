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

Scope filter everywhere: items that can still cost us money — delivered in 2026
or SELLABLE on hand now (sales company). Integration-only ghosts, disabled items
and defective/rejected/scrap stock are excluded.

State per vendor is stored in the `ap_vendor_state` default:
  {supplier: {"weights": 1, "freight": 1, "costs": 1, "submitted": [item_codes]}}
"""
import json

import frappe
from frappe.utils import flt, cint

from accounting_portal.api import pricing
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
    """{item_code: {"sold": qty, "oh": qty}} — items DELIVERED in 2026 OR sellable
    on the shelf today.

    On-hand stock used to be excluded ("never sold, so zero COGS impact"). That
    held while the goal was correcting history; it inverts the moment the goal is
    that NEXT month's COGS is right, because unsold stock is exactly what next
    month sells. Measured on PROD before this change: closing every vendor under
    the old scope still left 8,319 on-hand units (1.25M MAD, 1,808 of them at a
    zero rate) that no vendor run could ever reach — Kitchen Life was finished
    and still had 1,571 unpriced units on the shelf.

    Stock that cannot be sold stays out — disabled items and the
    defective/rejected/scrap warehouses — since pricing goods that will never
    reach a customer is pure workload."""
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
               JOIN `tabItem` i ON i.name=b.item_code
               WHERE w.company=%s AND b.actual_qty>0 AND IFNULL(i.disabled,0)=0
                 AND LOWER(b.warehouse) NOT LIKE %s
                 AND LOWER(b.warehouse) NOT LIKE %s
                 AND LOWER(b.warehouse) NOT LIKE %s
               GROUP BY b.item_code""",
            (SALES, "%defect%", "%reject%", "%scrap%"), as_dict=True):
        out.setdefault(r.ic, {"sold": 0.0, "oh": 0.0})["oh"] = flt(r.q)
    out.pop(None, None)
    out.pop("", None)
    return out
    codes = list(out)
    for i in range(0, len(codes), 700):
        for r in frappe.db.sql(
                """SELECT b.item_code ic, SUM(b.actual_qty) q FROM `tabBin` b
                   JOIN `tabWarehouse` w ON w.name=b.warehouse
                   WHERE w.company=%s AND b.actual_qty>0 AND b.item_code IN %s
                   GROUP BY b.item_code""",
                (SALES, codes[i:i + 700]), as_dict=True):
            out[r.ic]["oh"] = flt(r.q)
    return out


# group companies appear as "suppliers" on internal transfer invoices — paper,
# never the true origin; excluded from attribution entirely
_INTERNAL_SUPPLIERS = ("Maslak LTD", "Justyol China", "Justyol Morocco", "Justyol Holding")


def _item_vendor_map(item_codes):
    """item -> true ORIGIN supplier. The winner is the supplier with the
    LARGEST CUMULATIVE PURCHASED QTY across all evidence (origin PIs at Maslak,
    local PIs at Morocco, receipts) — a 24K-unit origin invoice beats a 500-unit
    top-up regardless of date. Internal transfer 'suppliers' (group companies)
    are excluded. Invoices outrank receipts only as a tie-break."""
    if not item_codes:
        return {}
    codes = tuple(item_codes)
    acc = {}   # ic -> {sup: [qty, has_pi, latest_dt]}

    def _take(rows, is_pi):
        for r in rows:
            if not r.sup or r.sup in _INTERNAL_SUPPLIERS:
                continue
            d = acc.setdefault(r.ic, {})
            e = d.setdefault(r.sup, [0.0, 0, ""])
            e[0] += flt(r.q)
            e[1] = max(e[1], 1 if is_pi else 0)
            e[2] = max(e[2], str(r.dt or ""))

    _take(frappe.db.sql(
        """SELECT pii.item_code ic, pi.supplier sup, SUM(pii.qty) q, MAX(pi.posting_date) dt
           FROM `tabPurchase Invoice Item` pii
           JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
           WHERE pi.docstatus=1 AND pi.company IN %s AND pii.item_code IN %s
           GROUP BY pii.item_code, pi.supplier""", ((SALES, SOURCING), codes), as_dict=True), True)
    # receipts fill the invoice-less tail (the Town Team pattern)
    _take(frappe.db.sql(
        """SELECT pri.item_code ic, pr.supplier sup, SUM(pri.qty) q, MAX(pr.posting_date) dt
           FROM `tabPurchase Receipt Item` pri
           JOIN `tabPurchase Receipt` pr ON pr.name=pri.parent
           WHERE pr.docstatus=1 AND pri.item_code IN %s
           GROUP BY pri.item_code, pr.supplier""", (codes,), as_dict=True), False)

    overrides = _overrides()
    out = {}
    for ic, sups in acc.items():
        ranked = sorted(sups.items(), key=lambda kv: (-kv[1][0], -kv[1][1], kv[1][2]))
        win = ranked[0]
        rec = {"supplier": win[0], "source": "pi" if win[1][1] else "pr",
               "qty": round(win[1][0]),
               "cands": [[s, round(e[0]), int(e[1])] for s, e in ranked[:5]]}
        ov = overrides.get(ic)
        if ov and ov in sups:            # manual override wins (must be a real candidate)
            rec["supplier"] = ov
            rec["source"] = "manual"
        elif ov:                          # override to a supplier with no evidence: honor it too
            rec["supplier"] = ov
            rec["source"] = "manual"
        out[ic] = rec
    # overrides for items with no purchase evidence at all
    for ic, ov in overrides.items():
        if ic not in out and ic in (set(item_codes) if not isinstance(item_codes, tuple) else set(codes)):
            out[ic] = {"supplier": ov, "source": "manual", "qty": 0, "cands": []}
    return out


_OVERRIDES_KEY = "ap_vendor_overrides"


def _overrides():
    try:
        return json.loads(frappe.db.get_default(_OVERRIDES_KEY) or "{}") or {}
    except Exception:
        return {}


@frappe.whitelist()
def set_vendor_override(item_code=None, supplier=None):
    """Manually pin an item to its true vendor (empty supplier clears the pin).
    The pin wins over the volume rule everywhere in the workbench."""
    assert_can_write()
    if not item_code:
        frappe.throw("item_code required")
    ov = _overrides()
    if supplier:
        if not frappe.db.exists("Supplier", supplier):
            frappe.throw(f"unknown supplier: {supplier}")
        ov[item_code] = supplier
    else:
        ov.pop(item_code, None)
    frappe.db.set_default(_OVERRIDES_KEY, json.dumps(ov))
    return {"ok": 1, "item_code": item_code, "supplier": supplier or None}


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
        # Empty is a legitimate state (every item re-pinned to another vendor,
        # or the vendor left the 2026-delivered universe). Return the SAME
        # shape as a full payload — a partial one made the UI crash mid-render
        # and freeze on "Loading…" with no error.
        st0 = (_state().get(supplier)) or {}
        grp0 = frappe.db.get_value("Supplier", supplier, "supplier_group") or ""
        return {"supplier": supplier, "group": grp0,
                "local": grp0 in _LOCAL_GROUPS,
                "channel": _channels().get(supplier) or "",
                "items": [],
                "summary": {"items": 0, "sold": 0, "oh": 0, "weights_ok": 0,
                            "weights_missing": 0, "cost_ok": 0, "cost_missing": 0},
                "state": {"weights": 0, "freight": 0, "prices": 0, "costs": 0,
                          "submitted": st0.get("submitted") or []}}

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
    # CFO doctrine — no averages: evidence shown per item is the LATEST invoice
    # era's product price (the last invoice governs until the next one)
    _pr = _pricing(supplier, mine)
    bench = {ic: p["latest"] for ic, p in _pr.items()}
    cost_ovs = _cost_overrides()
    # half-invoice detector: invoiced vs received qty (non-internal docs only)
    inv_q, rec_q = {}, {}
    for i in range(0, len(mine), 700):
        for r in frappe.db.sql(
                """SELECT pii.item_code ic, SUM(pii.qty) q
                   FROM `tabPurchase Invoice Item` pii
                   JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
                   WHERE pi.docstatus=1 AND pi.company IN %s AND pii.item_code IN %s
                     AND pi.supplier NOT IN %s
                   GROUP BY pii.item_code""",
                ((SALES, SOURCING), mine[i:i + 700], _INTERNAL_SUPPLIERS), as_dict=True):
            inv_q[r.ic] = flt(r.q)
        for r in frappe.db.sql(
                """SELECT pri.item_code ic, SUM(pri.qty) q
                   FROM `tabPurchase Receipt Item` pri
                   JOIN `tabPurchase Receipt` pr ON pr.name=pri.parent
                   WHERE pr.docstatus=1 AND pri.item_code IN %s
                     AND pr.supplier NOT IN %s
                   GROUP BY pri.item_code""",
                (mine[i:i + 700], _INTERNAL_SUPPLIERS), as_dict=True):
            rec_q[r.ic] = flt(r.q)

    ovs = _overrides()
    items = []
    for ic in mine:
        m = meta.get(ic) or {}
        h = hist.get(ic) or {}
        vm = vmap.get(ic) or {}
        cands = vm.get("cands") or []
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
            "cost_override": (cost_ovs.get(ic) or {}).get("rate"),
            "partial_invoice": 1 if (rec_q.get(ic) and inv_q.get(ic, 0) < rec_q[ic] * 0.95) else 0,
            "inv_cov": round(100.0 * inv_q.get(ic, 0) / rec_q[ic], 0) if rec_q.get(ic) else None,
            "multi": cands if len(cands) > 1 else [],
            "pinned": 1 if ic in ovs else 0,
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
                      "prices": 1 if st.get("prices") else 0,
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


_RATES_KEY = "ap_freight_rates"          # {"sea": 22.7, "air": ..., "china": ...} MAD/kg
_DEFAULT_RATES = {"sea": 22.7, "air": 213.86, "china": 22.7}


def _rates():
    try:
        cfg = json.loads(frappe.db.get_default(_RATES_KEY) or "{}") or {}
    except Exception:
        cfg = {}
    out = dict(_DEFAULT_RATES)
    out.update({k: flt(v) for k, v in cfg.items() if flt(v) > 0})
    return out


_RATE_SCHED_KEY = "ap_freight_rate_scheds"   # {"air":[{"date","rate"},...], ...}


def _rate_scheds():
    """Dated channel rates (era pricing): each point opens an era at its
    MAD/kg from that date on. The AIR schedule falls back to the official
    tariff bands already maintained in the Landed Cockpit
    (landed_prep.get_air_rates — 110 from 2026-01-01, 126 from 2026-04-23)
    so there is ONE source of truth; an explicit workbench entry overrides."""
    try:
        cfg = json.loads(frappe.db.get_default(_RATE_SCHED_KEY) or "{}") or {}
    except Exception:
        cfg = {}
    out = {}
    for ch, pts in cfg.items():
        clean = sorted(
            [{"date": str(p.get("date"))[:10], "rate": flt(p.get("rate"))}
             for p in (pts or []) if flt(p.get("rate")) > 0 and p.get("date")],
            key=lambda p: p["date"])
        if clean:
            out[ch] = clean
    if "air" not in out:
        try:
            from accounting_portal.api.landed_prep import get_air_rates
            bands = [{"date": str(b.get("from"))[:10], "rate": flt(b.get("rate"))}
                     for b in (get_air_rates(2026) or []) if flt(b.get("rate")) > 0]
            if bands:
                out["air"] = sorted(bands, key=lambda p: p["date"])
        except Exception:
            pass
    return out


def _rate_for(supplier, date=None):
    """MAD/kg for this vendor at `date` (default: today/latest).
    Precedence: vendor override (scalar) > channel DATED schedule (era rate
    at the date — the air 100/110/120 pattern) > channel scalar. 0 for local."""
    grp = frappe.db.get_value("Supplier", supplier, "supplier_group") or ""
    if grp in _LOCAL_GROUPS:
        return 0.0, "local"
    ch = _channels().get(supplier) or "sea"
    rates = _rates()
    ov = flt(rates.get(f"vendor::{supplier}"))
    if ov > 0:
        return ov, ch
    sched = _rate_scheds().get(ch)
    if sched:
        d = str(date or frappe.utils.nowdate())[:10]
        r = sched[0]["rate"]
        for p in sched:
            if p["date"] <= d:
                r = p["rate"]
            else:
                break
        return flt(r), ch
    return flt(rates.get(ch) or rates["sea"]), ch


@frappe.whitelist()
def set_rate_sched(channel=None, sched=None):
    """Save the DATED rate schedule for a channel (era pricing). sched =
    [{date, rate}]; empty list clears it (falls back to the scalar rate)."""
    assert_can_write()
    if channel not in ("sea", "air", "china"):
        frappe.throw("channel must be sea/air/china")
    pts = frappe.parse_json(sched or "[]")
    clean = []
    for p in pts:
        d = str(p.get("date") or "")[:10]
        r = flt(p.get("rate"))
        if len(d) == 10 and r > 0:
            clean.append({"date": d, "rate": round(r, 2)})
    try:
        cfg = json.loads(frappe.db.get_default(_RATE_SCHED_KEY) or "{}") or {}
    except Exception:
        cfg = {}
    if clean:
        cfg[channel] = sorted(clean, key=lambda p: p["date"])
    else:
        cfg.pop(channel, None)
    frappe.db.set_default(_RATE_SCHED_KEY, json.dumps(cfg))
    return {"ok": 1, "channel": channel, "sched": cfg.get(channel) or []}


@frappe.whitelist()
def set_channel(supplier=None, channel=None):
    """Assign the vendor's freight channel (sea/air/china/local) — updates the
    shared ap_freight_channels classification used everywhere."""
    assert_can_write()
    if not supplier or channel not in ("sea", "air", "china", "local"):
        frappe.throw("supplier and a valid channel (sea/air/china/local) required")
    try:
        cfg = json.loads(frappe.db.get_default(_CHANNELS_KEY) or "{}") or {}
    except Exception:
        cfg = {}
    for ch in list(cfg):
        cfg[ch] = [s for s in (cfg[ch] or []) if s != supplier]
    cfg.setdefault(channel, []).append(supplier)
    frappe.db.set_default(_CHANNELS_KEY, json.dumps(cfg))
    return {"ok": 1, "supplier": supplier, "channel": channel}


@frappe.whitelist()
def set_rate(channel=None, rate=None, supplier=None):
    """Set the MAD/kg freight rate. With `supplier`: a vendor-specific override
    (rate<=0 clears it, falling back to the channel rate). Without: the shared
    channel rate itself."""
    assert_can_write()
    try:
        cfg = json.loads(frappe.db.get_default(_RATES_KEY) or "{}") or {}
    except Exception:
        cfg = {}
    r = flt(rate)
    if supplier:
        key = f"vendor::{supplier}"
        if r > 0:
            cfg[key] = r
        else:
            cfg.pop(key, None)
    else:
        if channel not in ("sea", "air", "china"):
            frappe.throw("channel must be sea/air/china")
        if r <= 0:
            frappe.throw("a positive MAD/kg rate is required")
        cfg[channel] = r
    frappe.db.set_default(_RATES_KEY, json.dumps(cfg))
    return {"ok": 1, "rates": cfg}


@frappe.whitelist()
def import_weights(supplier=None, csv_text=None):
    """Bulk weight import from a team-filled sheet (CSV text — Excel 'Save as
    CSV'). Flexible: separator ; , or tab; decimal comma accepted; rows are
    resolved by item_code first, then by SKU (globally unique custom_sku).
    Returns a full report — nothing silently dropped."""
    assert_can_write()
    text = (csv_text or "").strip()
    if not text:
        frappe.throw("empty file")
    lines = [l for l in text.replace("\r\n", "\n").replace("\r", "\n").split("\n") if l.strip()]
    sep = ";" if lines[0].count(";") >= lines[0].count(",") else ","
    if "\t" in lines[0] and lines[0].count("\t") > lines[0].count(sep):
        sep = "\t"
    hdr = [c.strip().strip('"').lower() for c in lines[0].split(sep)]

    def _col(*names):
        for nm in names:
            for i, h in enumerate(hdr):
                if nm in h:
                    return i
        return None
    ci = _col("item_code", "item code", "code")
    cs = _col("sku")
    cw = _col("weight", "وزن", "kg", "poids")
    if cw is None:
        frappe.throw("no weight column found (expect a header containing 'weight'/'kg')")
    saved, unmatched, invalid = [], [], []
    for ln in lines[1:]:
        parts = [c.strip().strip('"') for c in ln.split(sep)]
        if len(parts) <= cw:
            continue
        raw_w = parts[cw].replace(",", ".").replace(" ", "")
        try:
            w = float(raw_w) if raw_w else 0.0
        except Exception:
            w = 0.0
        code = parts[ci].strip() if ci is not None and len(parts) > ci else ""
        sku = parts[cs].strip() if cs is not None and len(parts) > cs else ""
        if w <= 0:
            continue                        # blank/zero = not filled, skip silently
        if not (0.005 <= w <= 50):
            invalid.append({"row": code or sku, "weight": w})
            continue
        ic = None
        if code and frappe.db.exists("Item", code):
            ic = code
        elif sku:
            ic = frappe.db.get_value("Item", {"custom_sku": sku}, "name")
        if not ic:
            unmatched.append(code or sku or ln[:30])
            continue
        frappe.db.set_value("Item", ic, {"weight_per_unit": w, "weight_uom": "Kg"})
        saved.append(ic)
    frappe.db.commit()
    return {"saved": len(saved), "unmatched": unmatched[:50],
            "unmatched_n": len(unmatched), "invalid": invalid[:20],
            "invalid_n": len(invalid)}


@frappe.whitelist()
def freight_summary(supplier=None):
    """Step 2 read: the vendor's pro-rata slice of the 2026 770 freight pool.

    Timing matters (a large share of goods SHIPPED IN 2025): the 2026 pool is
    allocated over units RECEIVED IN 2026 only — clearing stays honest (the sum
    over vendors equals the 2026 bills). 2025 freight was expensed in the
    closed 2025 P&L and is shown as context, never re-allocated. The COSTING
    side is separate: every imported unit carries channel-rate × weight in the
    submit, whatever year it shipped."""
    assert_portal_access()
    if not supplier:
        frappe.throw("supplier required")
    rate_kg, chan = _rate_for(supplier)

    def _pool(year):
        return round(flt(frappe.db.sql(
            """SELECT SUM(g.debit-g.credit)
               FROM `tabGL Entry` g JOIN `tabAccount` a ON a.name=g.account
               WHERE g.company=%s AND g.is_cancelled=0
                 AND (a.account_number LIKE '770.07%%' OR a.account_number LIKE '770.0.7%%')
                 AND a.account_number NOT LIKE '770.07.004%%'
                 AND YEAR(g.posting_date)=%s""", (SALES, year))[0][0] or 0))
    pool26, pool25 = _pool(2026), _pool(2025)

    # weighted units RECEIVED in 2026 into the sales company. Kitchen-Life
    # lesson: goods arrive via the INTERNAL transfer, so the receipt's own
    # supplier says "Maslak LTD" — each unit must be credited to its TRUE
    # origin vendor via the same attribution map used everywhere else.
    recv = frappe.db.sql(
        """SELECT pri.item_code ic, SUM(pri.qty) q
           FROM `tabPurchase Receipt Item` pri
           JOIN `tabPurchase Receipt` pr ON pr.name=pri.parent
           WHERE pr.docstatus=1 AND pr.company=%s AND YEAR(pr.posting_date)=2026
           GROUP BY pri.item_code""", (SALES,), as_dict=True)
    codes = list({r.ic for r in recv})
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
    for r in recv:
        vend = vmap.get(r.ic, {}).get("supplier")
        if not vend or sup_groups.get(vend, "") in _LOCAL_GROUPS:
            continue                      # local goods carry no import freight
        kg = w.get(r.ic, 0.0) * flt(r.q)
        tot_kg += kg
        if vend == supplier:
            my_kg += kg
            my_units += flt(r.q)
            if w.get(r.ic, 0.0) <= 0:
                my_nw += 1
    share = (my_kg / tot_kg) if tot_kg else 0.0
    rates_cfg = _rates()
    chan_rate = flt(rates_cfg.get(chan) or 0)
    ch_sched = _rate_scheds().get(chan) or []
    src = ("vendor" if flt(rates_cfg.get(f"vendor::{supplier}")) > 0
           else ("schedule" if ch_sched else "channel"))
    return {"supplier": supplier, "channel": chan, "rate_kg": rate_kg,
            "channel_rate": chan_rate, "rate_sched": ch_sched,
            "rate_source": src,
            "pool_mad": pool26, "pool_2025_mad": pool25,
            "vendor_kg": round(my_kg, 1), "total_kg": round(tot_kg, 1),
            "share_pct": round(100 * share, 2),
            "vendor_freight_mad": round(pool26 * share),
            "vendor_units": round(my_units), "items_without_weight": my_nw,
            "note": "2026 pool over 2026-received units — sum over vendors == 2026 bills; "
                    "2025 freight sits in the closed 2025 P&L (context only)"}


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


_COST_OV_KEY = "ap_cost_overrides"     # {item: {"rate": MAD, "note": str}}


def _cost_overrides():
    try:
        return json.loads(frappe.db.get_default(_COST_OV_KEY) or "{}") or {}
    except Exception:
        return {}


@frappe.whitelist()
def set_cost_override(item_code=None, rate=None, note=None):
    """Reviewer's verified PRODUCT cost for an item (MAD) — wins over the
    invoice benchmark in submit. rate<=0 clears it. A note is mandatory:
    an override without its why is unauditable."""
    assert_can_write()
    if not item_code:
        frappe.throw("item_code required")
    ov = _cost_overrides()
    r = flt(rate)
    if r > 0:
        if not (note or "").strip():
            frappe.throw("a note explaining the override is required")
        ov[item_code] = {"rate": round(r, 2), "note": note.strip()}
    else:
        ov.pop(item_code, None)
    frappe.db.set_default(_COST_OV_KEY, json.dumps(ov))
    return {"ok": 1, "item_code": item_code, "override": ov.get(item_code)}


@frappe.whitelist()
def item_cost_detail(item_code=None):
    """The full purchase story of one product — every invoice and receipt
    across both companies, MAD-converted at document-date FX, with invoice
    coverage (the 'half-invoice' detector) and the benchmark's basis."""
    assert_portal_access()
    if not item_code:
        frappe.throw("item_code required")
    from accounting_portal.api.cost_trace import _fx_series, _to_mad_fast, true_cost
    fx = _fx_series()
    # INVOICES ONLY in the story (CFO policy — receipts are noise, not evidence);
    # internal transfer invoices shown dimmed for context.
    moves = []
    for co, lbl in ((SOURCING, "maslak"), (SALES, "morocco")):
        for r in frappe.db.sql(
                """SELECT pi.name doc, pi.supplier sup, pi.posting_date d, pi.currency ccy,
                          pii.qty, pii.rate, pii.base_rate,
                          IFNULL(pii.purchase_receipt,'') linked_pr,
                          IFNULL(pii.cost_center, IFNULL(pi.cost_center,'')) cc
                   FROM `tabPurchase Invoice Item` pii
                   JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
                   WHERE pi.docstatus=1 AND pi.company=%s AND pii.item_code=%s AND pii.qty>0
                   ORDER BY pi.posting_date DESC""", (co, item_code), as_dict=True):
            internal = r.sup in _INTERNAL_SUPPLIERS
            mad = (flt(r.base_rate) if co == SALES
                   else _to_mad_fast(flt(r.base_rate), "TRY", r.d, fx))
            moves.append({"kind": "PI", "company": lbl, "doc": r.doc, "supplier": r.sup,
                          "date": str(r.d), "qty": round(flt(r.qty)),
                          "rate": flt(r.rate), "ccy": r.ccy,
                          "mad": round(mad, 2) if mad else None,
                          "linked_pr": r.linked_pr or None,
                          "cc": ("non" if "non-official" in (r.cc or "").lower()
                                 else ("off" if r.cc else None)),
                          "excluded": 1 if f"{r.doc}::{item_code}" in _price_exclusions() else 0,
                          "internal": 1 if internal else 0})
    moves.sort(key=lambda m: m["date"], reverse=True)
    # invoice coverage vs origin receipts — the 'half-invoice' detector
    # (receipt QTY only feeds this counter; receipt RATES never touch anything).
    inv_q = sum(m["qty"] for m in moves if not m["internal"])
    rec_q = flt(frappe.db.sql(
        """SELECT SUM(pri.qty) FROM `tabPurchase Receipt Item` pri
           JOIN `tabPurchase Receipt` pr ON pr.name=pri.parent
           WHERE pr.docstatus=1 AND pri.item_code=%s
             AND pr.supplier NOT IN %s""",
        (item_code, _INTERNAL_SUPPLIERS))[0][0] or 0)
    cov = round(100.0 * inv_q / rec_q, 1) if rec_q else None
    tc = true_cost(item_code=item_code)
    ov = _cost_overrides().get(item_code)
    # era timeline (no-averages doctrine): each invoice's own price + its
    # era freight — what the retro will actually apply, period by period
    sup = (_item_vendor_map([item_code]).get(item_code) or {}).get("supplier")
    eras = []
    if sup:
        p = _pricing(sup, [item_code]).get(item_code)
        if p:
            eras = p["eras"]
    # channel split roll-up (informational): the two cost centres are two
    # PAYMENT CHANNELS at the same full unit price — never halves of one
    # price, so the combined cost is plain qty-weighted, nothing is summed.
    q_o = sum(m["qty"] for m in moves if m.get("cc") == "off" and not m["internal"])
    v_o = sum(m["qty"] * (m["mad"] or 0) for m in moves if m.get("cc") == "off" and not m["internal"])
    q_n = sum(m["qty"] for m in moves if m.get("cc") == "non")
    v_n = sum(m["qty"] * (m["mad"] or 0) for m in moves if m.get("cc") == "non")
    half = None
    if q_o > 0 and q_n > 0:
        half = {"off_qty": round(q_o), "off_rate": round(v_o / q_o, 2),
                "non_qty": round(q_n), "non_rate": round(v_n / q_n, 2),
                "combined": round((v_o + v_n) / (q_o + q_n), 2),
                "physical_qty": round(q_o + q_n)}
    return {"item_code": item_code, "moves": moves[:60],
            "invoiced_qty": inv_q, "received_qty": rec_q, "coverage_pct": cov,
            "partial_invoice": bool(rec_q and inv_q < rec_q * 0.95),
            "half_invoice": half, "eras": eras,
            "bench": tc, "override": ov}


_PRICE_EXCL_KEY = "ap_price_exclusions"     # ["<PI_NAME>::<item_code>", ...]


def _price_exclusions():
    try:
        return set(json.loads(frappe.db.get_default(_PRICE_EXCL_KEY) or "[]"))
    except Exception:
        return set()


@frappe.whitelist()
def set_price_exclusion(item_code=None, doc=None, excluded=1):
    """Per-period control: knock a WRONG invoice line out of the pricing
    timeline (a qty-1 manual entry must not hijack the model's era). The
    invoice itself is untouched accounting-wise — it just stops feeding the
    price. excluded=0 restores it."""
    assert_can_write()
    if not (item_code and doc):
        frappe.throw("item_code and doc required")
    key = f"{doc}::{item_code}"
    ex = _price_exclusions()
    if str(excluded) in ("1", "true", "True"):
        ex.add(key)
    else:
        ex.discard(key)
    frappe.db.set_default(_PRICE_EXCL_KEY, json.dumps(sorted(ex)))
    return {"ok": 1, "key": key, "excluded": key in ex}


def _pricing(supplier, items):
    """CFO pricing doctrine — NO averages. Each invoice OPENS AN ERA at ITS
    OWN unit price for its own period (until the next invoice):

      bought 100 in March @A, 200 in August @B → March-July deliveries cost A,
      August-on cost B. Nothing is blended across eras.

    Half-invoice handling is PAIRED, not averaged: an official invoice's full
    price = its own rate + the qty-weighted rate of the NON-OFFICIAL tranches
    within ±90 days (the two halves of the same physical purchase); with no
    nearby tranche, the overall non-official rate of the timeline fills in.

    One price per MODEL: when the item belongs to a family (template or
    sku-base), the timeline is the FAMILY's pooled invoices, so every variant
    shares the same eras. Freight rides on each era at ITS date's channel
    rate × weight (the 110→126 air bands).

    Returns {item: {"eras":[{date, product, freight, rate}], "latest": product,
                     "rate": full, "half": 0/1}}"""
    if not items:
        return {}
    from accounting_portal.api.cost_trace import _fx_series, _to_mad_fast
    fx = _fx_series()
    rate_kg_today, _ch = _rate_for(supplier)
    vendor_scalar = flt(_rates().get(f"vendor::{supplier}")) > 0
    fr_sched = [] if vendor_scalar else (_rate_scheds().get(_ch) or [])

    def fr_rate_at(d):
        if not fr_sched:
            return rate_kg_today
        r = fr_sched[0]["rate"]
        for p in fr_sched:
            if p["date"] <= d:
                r = p["rate"]
            else:
                break
        return flt(r)

    w = {}
    for i in range(0, len(items), 700):
        for r in frappe.db.sql(
                "SELECT name, IFNULL(weight_per_unit,0) x FROM `tabItem` WHERE name IN %s",
                (items[i:i + 700],), as_dict=True):
            w[r.name] = flt(r.x)

    # ---- family grouping: every variant shares the model's timeline ----
    meta = {}
    for i in range(0, len(items), 700):
        for r in frappe.db.sql(
                "SELECT name, variant_of, custom_sku FROM `tabItem` WHERE name IN %s",
                (items[i:i + 700],), as_dict=True):
            meta[r.name] = r
    fam_of = {}
    bases = set()
    for ic in items:
        m = meta.get(ic)
        if m and m.variant_of:
            fam_of[ic] = "tpl::" + m.variant_of
        else:
            sku = ((m.custom_sku if m else "") or "").strip()
            b = sku.split("-")[0].strip() if "-" in sku else ""
            if len(b) >= 4 and b != sku:
                fam_of[ic] = "base::" + b
                bases.add(b)
            else:
                fam_of[ic] = "solo::" + ic
    members = {}
    tpls = {k[5:] for k in fam_of.values() if k.startswith("tpl::")}
    if tpls:
        for r in frappe.db.sql(
                "SELECT name, variant_of FROM `tabItem` WHERE variant_of IN %s",
                (tuple(tpls),), as_dict=True):
            members.setdefault("tpl::" + r.variant_of, set()).add(r.name)
    for b in bases:
        kin = frappe.db.sql(
            "SELECT name FROM `tabItem` WHERE custom_sku=%s OR custom_sku LIKE %s LIMIT 200",
            (b, b + "-%"), pluck=True)
        members["base::" + b] = set(kin or [])
    for ic in items:
        members.setdefault(fam_of[ic], set()).add(ic)

    all_codes = tuple({m for s in members.values() for m in s})
    fam_by_code = {}
    for f, ms in members.items():
        for m in ms:
            fam_by_code.setdefault(m, f)

    # ---- pooled invoice lines per family (Maslak w/ cc + Morocco full) ----
    # per-period control: lines the reviewer EXCLUDED (ap_price_exclusions,
    # key "<PI>::<item>") never feed the timeline — a qty-1 manual entry must
    # not hijack the model's current era
    excl = _price_exclusions()
    lines = {}   # fam -> [(date, qty, mad, kind)]
    for i in range(0, len(all_codes), 700):
        chunk = tuple(all_codes[i:i + 700])
        for r in frappe.db.sql(
                """SELECT pii.item_code ic, pi.name doc, pii.base_rate rate, pi.posting_date d, pii.qty,
                          IFNULL(pii.cost_center, IFNULL(pi.cost_center,'')) cc
                   FROM `tabPurchase Invoice Item` pii
                   JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
                   WHERE pi.docstatus=1 AND pi.company=%s AND pii.item_code IN %s AND pii.qty>0
                """, (SOURCING, chunk), as_dict=True):
            f = fam_by_code.get(r.ic)
            if not f or f"{r.doc}::{r.ic}" in excl:
                continue
            mad = _to_mad_fast(flt(r.rate), "TRY", r.d, fx)
            if mad > 0:
                kind = "non" if "non-official" in (r.cc or "").lower() else "off"
                lines.setdefault(f, []).append((str(r.d), flt(r.qty), mad, kind))
        for r in frappe.db.sql(
                """SELECT pii.item_code ic, pi.name doc, pii.base_rate rate, pi.posting_date d, pii.qty
                   FROM `tabPurchase Invoice Item` pii
                   JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
                   WHERE pi.docstatus=1 AND pi.company=%s AND pii.item_code IN %s AND pii.qty>0
                     AND pi.supplier NOT IN %s""",
                (SALES, chunk, _INTERNAL_SUPPLIERS), as_dict=True):
            f = fam_by_code.get(r.ic)
            if f and flt(r.rate) > 0 and f"{r.doc}::{r.ic}" not in excl:
                lines.setdefault(f, []).append((str(r.d), flt(r.qty), flt(r.rate), "full"))

    # ---- eras per family: each opener priced at ITS OWN rate ----
    def _fam_eras(ls):
        """Every purchase line opens an era at ITS OWN price — official or
        non-official alike.

        There is NO price-splitting between the two cost centres. Verified on
        PROD (2026-08-28): only 0.11% of item+day combos are billed in both
        centres, the median non/official RATE ratio is 1.00 (85% within ±15%),
        and quantities do not mirror. The two centres are two PAYMENT
        CHANNELS for separate purchases at the same full unit price — what is
        under-declared is quantity, never the rate. The earlier pairing model
        (own + paired_non) therefore DOUBLED the cost wherever it fired
        (TOMMYLIFE tracksuit: 471 MAD vs a true 229, against a 274 MAD selling
        price). Same-day lines merge qty-weighted; that is the only averaging
        allowed, and it is within one invoice day."""
        ls.sort(key=lambda x: x[0])
        by_day = {}
        for d, q, m, k in ls:
            e = by_day.setdefault(d, [0.0, 0.0])
            e[0] += q
            e[1] += m * q
        eras = []
        for d in sorted(by_day):
            q, v = by_day[d]
            if q > 0 and v > 0:
                eras.append({"date": d, "product": round(v / q, 2)})
        return eras, 0

    fam_eras = {}
    for f, ls in lines.items():
        fam_eras[f] = _fam_eras(ls)

    out = {}
    for ic in items:
        f = fam_of.get(ic)
        eras, half = fam_eras.get(f, ([], 0))
        if not eras:
            continue
        wkg = w.get(ic, 0.0)
        first = eras[0]["date"]
        bps = sorted({e["date"] for e in eras}
                     | {p["date"] for p in fr_sched if p["date"] > first})
        full_eras = []
        cur = eras[0]["product"]
        ei = 0
        for d in bps:
            while ei < len(eras) and eras[ei]["date"] <= d:
                cur = eras[ei]["product"]; ei += 1
            fr = round(fr_rate_at(d) * wkg, 2)
            full_eras.append({"date": d, "product": cur, "freight": fr,
                              "rate": round(cur + fr, 2)})
        out[ic] = {"eras": full_eras, "latest": full_eras[-1]["product"],
                   "rate": full_eras[-1]["rate"], "half": half,
                   "weight_kg": wkg}
    return out


def _invoice_sched(supplier, items):
    """Submit schedule = the era timeline from _pricing (CFO doctrine: each
    invoice opens an era at ITS OWN price; freight era-priced too). Items with
    a manual cost override get NO schedule (uniform verified truth)."""
    pr = _pricing(supplier, items)
    ovs = _cost_overrides()
    out = {}
    for ic, p in pr.items():
        if ic in ovs:
            continue
        out[ic] = [{"date": e["date"], "rate": e["rate"]} for e in p["eras"]]
    return out

def _full_rates(supplier, items):
    """{item: {product, freight, rate, weight_kg, eras}} — the LATEST invoice
    era's price (CFO doctrine: no averages — the last invoice governs until the
    next one), plus that era's freight. A manual override wins as a single
    uniform truth. Local vendors: freight 0."""
    rate_kg, _ch = _rate_for(supplier)
    pr = _pricing(supplier, items) if items else {}
    ovs = _cost_overrides()
    w = {}
    if items:
        for i in range(0, len(items), 700):
            for r in frappe.db.sql(
                    "SELECT name, IFNULL(weight_per_unit,0) x FROM `tabItem` WHERE name IN %s",
                    (items[i:i + 700],), as_dict=True):
                w[r.name] = flt(r.x)
    out = {}
    for ic in items:
        ov = flt((ovs.get(ic) or {}).get("rate"))
        p = pr.get(ic)
        if ov > 0:
            fr = round(rate_kg * w.get(ic, 0.0), 2)
            out[ic] = {"product": ov, "freight": fr, "rate": round(ov + fr, 2),
                       "weight_kg": w.get(ic, 0), "eras": 0}
        elif p:
            out[ic] = {"product": p["latest"], "freight": p["eras"][-1]["freight"],
                       "rate": p["rate"], "weight_kg": p["weight_kg"],
                       "eras": len(p["eras"])}
        else:
            out[ic] = {"product": None, "freight": 0, "rate": None,
                       "weight_kg": w.get(ic, 0), "eras": 0}
    return out


@frappe.whitelist()
def submit_preview(supplier=None, items=None):
    """Step 4 dry-run: for each item the FULL rate (product + freight layer)
    and the retro anchor date — silent degradation (anchor at today) and
    missing weights are visible BEFORE anything posts."""
    assert_portal_access()
    if not supplier:
        frappe.throw("supplier required")
    items = frappe.parse_json(items or "[]")
    from accounting_portal.api.valuation import _retro_anchor
    rates = _full_rates(supplier, items)
    scheds = _invoice_sched(supplier, items)
    rate_kg, chan = _rate_for(supplier)
    out = []
    for ic in items:
        rr = rates.get(ic) or {}
        eras = len(scheds.get(ic) or [])
        anchor = None
        try:
            anchor = _retro_anchor(SALES, ic)
        except Exception:
            anchor = None
        out.append({"item_code": ic, "rate": rr.get("rate"),
                    "product": rr.get("product"), "freight": rr.get("freight"),
                    "weight_kg": rr.get("weight_kg"), "eras": eras,
                    "anchor": str(anchor) if anchor else None,
                    "retro_ok": bool(anchor and str(anchor) < frappe.utils.nowdate()),
                    "no_cost": not rr.get("rate"),
                    "no_weight": rate_kg > 0 and flt(rr.get("weight_kg")) <= 0})
    return {"supplier": supplier, "channel": chan, "rate_kg": rate_kg, "rows": out,
            "ready": sum(1 for r in out if r["rate"] and r["retro_ok"]),
            "no_cost": sum(1 for r in out if r["no_cost"]),
            "no_weight": sum(1 for r in out if r["no_weight"]),
            "anchor_today": sum(1 for r in out if r["rate"] and not r["retro_ok"])}


_RUN_STALE_SECONDS = 1200  # one item can legitimately take minutes (160+ retro pins)


def _run_is_stale(run):
    """A run whose driver died (closed tab, killed worker) stays 'running'
    forever — nothing calls finish_run. Six vendors were found wedged this way
    on 2026-09-01 (one since two days prior). A run with no heartbeat for 10
    minutes is dead: real runs write an item every few seconds."""
    if (run or {}).get("state") != "running":
        return False
    last = run.get("updated") or run.get("started")
    if not last:
        return True
    try:
        return frappe.utils.time_diff_in_seconds(frappe.utils.now(), last) > _RUN_STALE_SECONDS
    except Exception:
        return True


def _record_run(supplier, ic, msg, ok, total=None):
    """Persist one item's outcome immediately: re-read state (other tabs/jobs may
    have touched it), append the result, bump the counter, commit. Progress is
    therefore never lost to a timeout, a reload or a dead worker."""
    st = _state()
    v = st.setdefault(supplier, {})
    d = v.setdefault("submitted", [])
    if ok and ic not in d:
        d.append(ic)
    r = v.setdefault("run", {"state": "running", "total": total or 0,
                             "done": 0, "results": []})
    if total:
        r["total"] = total
    r["state"] = "running"
    r["updated"] = frappe.utils.now()
    r["done"] = flt(r.get("done")) + 1
    r.setdefault("results", []).append({"item_code": ic, "result": msg})
    r["results"] = r["results"][-40:]
    _save_state(st)
    frappe.db.commit()
    return r


def _submit_one_item(supplier, ic, note=None, total=None):
    """The unit of work: price the item, apply the retro fix, record the result.
    Used by both the background batch and the per-item endpoint."""
    from accounting_portal.api.valuation import fix_item_cost
    rates = _full_rates(supplier, [ic])
    scheds = _invoice_sched(supplier, [ic])
    cost_ovs = _cost_overrides()
    rate_kg, chan = _rate_for(supplier)
    rr = rates.get(ic) or {}
    if not rr.get("rate"):
        _record_run(supplier, ic, "skipped — no cost evidence", False, total)
        return {"item_code": ic, "ok": 0, "result": "skipped — no cost evidence"}
    if rate_kg > 0 and flt(rr.get("weight_kg")) <= 0:
        _record_run(supplier, ic, "skipped — no weight (freight layer unknown)", False, total)
        return {"item_code": ic, "ok": 0, "result": "skipped — no weight"}
    split = (f"vendor workbench — {supplier} [{chan}]: "
             f"product {rr['product']} + freight {rr['freight']} "
             f"({rate_kg}/kg × {rr['weight_kg']}kg)")
    sched = None if ic in cost_ovs else (scheds.get(ic) or None)
    if sched:
        split += f" — {len(sched)} invoice era(s)"
    try:
        r = fix_item_cost(company=SALES, item_code=ic, rate=rr["rate"], full_rate=1,
                          retro=1, retro_product=rr["product"],
                          retro_sched=json.dumps(sched) if sched else None,
                          note=(note + " — " if note else "") + split)
        msg = (r or {}).get("result") or "ok"
        _record_run(supplier, ic, msg, True, total)
        return {"item_code": ic, "ok": 1, "result": msg}
    except Exception as e:
        frappe.db.rollback()
        msg = f"error: {e}"
        _record_run(supplier, ic, msg, False, total)
        return {"item_code": ic, "ok": 0, "result": msg}


@frappe.whitelist()
def submit_one(supplier=None, item_code=None, note=None, total=None):
    """Post ONE item's retro fix inside this request — no background worker
    involved. The UI walks the batch item by item: each request is short, a
    timeout costs at most one item (the fix is atomic and rolls back), and the
    progress is already committed. This is the path that keeps working when the
    long-queue worker is down."""
    assert_can_write()
    if not supplier or not item_code:
        frappe.throw("supplier and item_code required")
    return _submit_one_item(supplier, item_code, note, cint(total) or None)


@frappe.whitelist()
def start_run(supplier=None, total=0):
    """Reset the progress counter before a UI-driven item-by-item run."""
    assert_can_write()
    st = _state()
    v = st.setdefault(supplier, {})
    v["run"] = {"state": "running", "total": cint(total), "done": 0,
                "started": frappe.utils.now(), "results": []}
    _save_state(st)
    return {"ok": 1}


@frappe.whitelist()
def finish_run(supplier=None):
    """Close the progress counter when the UI-driven run ends."""
    assert_can_write()
    st = _state()
    r = (st.setdefault(supplier, {}).setdefault("run", {}))
    r["state"] = "done"
    r["finished"] = frappe.utils.now()
    _save_state(st)
    return {"ok": 1}


@frappe.whitelist()
def submit_batch(supplier=None, items=None, note=None):
    """Step 4 write: run fix_item_cost(retro) for a batch of the vendor's items.

    ONE item can post 160+ retro pins and take minutes, so a synchronous batch
    blew past the HTTP timeout (Kitchen Life canary died on item 2 of 15, its
    action left hanging in Proposed with the work half done and no progress
    recorded). The batch therefore runs as a BACKGROUND JOB that saves state
    after EVERY item — a timeout, a reload or a closed tab can no longer lose
    or repeat work — and the UI polls submit_progress()."""
    assert_can_write()
    if not supplier:
        frappe.throw("supplier required")
    items = frappe.parse_json(items or "[]")
    if not items:
        frappe.throw("no items in batch")
    if len(items) > 25:
        frappe.throw("batch too large — send at most 25 items per submit")
    st = _state()
    v = st.setdefault(supplier, {})
    run = v.get("run") or {}
    if run.get("state") == "running" and not _run_is_stale(run):
        return {"supplier": supplier, "queued": 0, "already_running": 1,
                "done": run.get("done"), "total": run.get("total")}
    done = v.setdefault("submitted", [])
    todo = [ic for ic in items if ic not in done]
    v["run"] = {"state": "running", "total": len(todo), "done": 0, "mode": "batch",
                "started": frappe.utils.now(), "updated": frappe.utils.now(),
                "results": []}
    _save_state(st)
    frappe.enqueue("accounting_portal.api.vendor_workbench._run_submit",
                   queue="long", timeout=7200, supplier=supplier,
                   items=todo, note=note, user=frappe.session.user)
    return {"supplier": supplier, "queued": len(todo), "total": len(todo)}


@frappe.whitelist()
def submit_all(supplier=None, items=None, note=None):
    """One click: queue EVERY remaining ready item as a single background job.
    The browser is a spectator from then on — the tab can be closed freely.
    Items are the frontend's ready queue (rate + retro OK + weight + not yet
    submitted); already-submitted codes are filtered again here anyway.

    The worker chunks itself (_SUBMIT_CHUNK per queue turn), so the reposts
    each chunk creates drain between chunks instead of piling up until the
    end. Stop via stop_run(); progress via submit_progress()."""
    assert_can_write()
    if not supplier:
        frappe.throw("supplier required")
    items = frappe.parse_json(items or "[]")
    if not items:
        frappe.throw("no items to submit")
    st = _state()
    v = st.setdefault(supplier, {})
    run = v.get("run") or {}
    if run.get("state") == "running" and not _run_is_stale(run):
        return {"supplier": supplier, "queued": 0, "already_running": 1,
                "done": run.get("done"), "total": run.get("total")}
    done = v.setdefault("submitted", [])
    todo = [ic for ic in items if ic not in done]
    if not todo:
        return {"supplier": supplier, "queued": 0, "total": 0}
    v["run"] = {"state": "running", "total": len(todo), "done": 0, "mode": "all",
                "started": frappe.utils.now(), "updated": frappe.utils.now(),
                "results": []}
    _save_state(st)
    frappe.db.commit()
    frappe.enqueue("accounting_portal.api.vendor_workbench._run_submit",
                   queue="long", timeout=7200, supplier=supplier,
                   items=todo, note=note or "vendor workbench — run all",
                   user=frappe.session.user)
    return {"supplier": supplier, "queued": len(todo), "total": len(todo)}


@frappe.whitelist()
def stop_run(supplier=None):
    """Ask the background run to stop after the item it is on. The worker
    checks this flag between items; finished work stays submitted."""
    assert_can_write()
    st = _state()
    r = st.setdefault(supplier or "", {}).setdefault("run", {})
    r["stop"] = 1
    _save_state(st)
    frappe.db.commit()
    return {"ok": 1}


def _stop_requested(supplier):
    return bool(((_state().get(supplier) or {}).get("run") or {}).get("stop"))


_NOTIFY_KEY = "ap_submit_notify"
_NOTIFY_DEFAULT = ["ahmed@justyol.com", "eman@justyol.com"]


def _notify_recipients():
    try:
        r = json.loads(frappe.db.get_default(_NOTIFY_KEY) or "[]") or []
        return r if isinstance(r, list) and r else _NOTIFY_DEFAULT
    except Exception:
        return _NOTIFY_DEFAULT


def _notify_run_finished(supplier, run):
    """Email the team when a Run-all background job ends. Best-effort: a mail
    hiccup must never mark hours of posted corrections as failed."""
    try:
        state = run.get("state") or "done"
        done = int(flt(run.get("done")))
        total = int(flt(run.get("total")))
        errors = [r for r in (run.get("results") or [])
                  if str(r.get("result", "")).startswith("error")]
        subject = "Vendor workbench — %s: %s (%d/%d)" % (
            supplier, "stopped" if state == "stopped" else "finished", done, total)
        lines = [
            "Run-all submit for <b>%s</b> %s." % (
                supplier, "was stopped on request" if state == "stopped" else "finished"),
            "Items processed this run: <b>%d / %d</b>" % (done, total),
            "Started: %s — finished: %s" % (run.get("started"), run.get("finished")),
            "Reposts still queued: %s" % frappe.db.count(
                "Repost Item Valuation", {"status": ["in", ["Queued", "In Progress"]]}),
        ]
        if errors:
            lines.append("<b>%d item(s) errored</b> — reopen the vendor to see them:" % len(errors))
            lines += ["&nbsp;&nbsp;%s: %s" % (e.get("item_code"), e.get("result"))
                      for e in errors[:10]]
        frappe.sendmail(recipients=_notify_recipients(), subject=subject,
                        message="<br>".join(lines))
    except Exception:
        frappe.log_error(title="workbench run notification",
                         message=frappe.get_traceback())


_SUBMIT_CHUNK = 10


def _run_submit(supplier=None, items=None, note=None, user=None, total=None):
    """Background worker for submit_batch/submit_all — the same per-item unit
    of work the UI can also drive directly, so all paths record progress
    identically. _record_run commits per item, so the stop flag written by
    stop_run() is visible between items.

    Cooperative chunking: process _SUBMIT_CHUNK items, then RE-ENQUEUE the
    remainder and exit. The re-enqueued job lands BEHIND the reposts this
    chunk just created (FIFO), so the single long worker alternates between
    posting corrections and draining their reposts — a multi-hour run never
    starves the repost queue, and neither starves the other."""
    if user:
        frappe.set_user(user)
    items = items or []
    total = total or len(items)
    stopped = False
    done_now = 0
    for ic in items[:_SUBMIT_CHUNK]:
        if _stop_requested(supplier):
            stopped = True
            break
        _submit_one_item(supplier, ic, note, total)
        done_now += 1
    remaining = [] if stopped else items[done_now:]
    if remaining:
        st = _state()
        r = st.setdefault(supplier, {}).setdefault("run", {})
        r["updated"] = frappe.utils.now()
        _save_state(st)
        frappe.db.commit()
        frappe.enqueue("accounting_portal.api.vendor_workbench._run_submit",
                       queue="long", timeout=7200, supplier=supplier,
                       items=remaining, note=note, user=user, total=total)
        return
    st = _state()
    r = (st.setdefault(supplier, {}).setdefault("run", {}))
    r["state"] = "stopped" if stopped else "done"
    r.pop("stop", None)
    r["finished"] = frappe.utils.now()
    _save_state(st)
    frappe.db.commit()
    if (r.get("mode") or "batch") == "all":
        _notify_run_finished(supplier, r)


@frappe.whitelist()
def submit_progress(supplier=None):
    """Poll target for the running batch: how far the worker got, what each
    item returned, and how deep the repost queue is."""
    assert_portal_access()
    v = (_state().get(supplier) or {})
    run = v.get("run") or {}
    if _run_is_stale(run):
        # self-heal on poll: flip the dead run to done so the UI offers
        # resume instead of "keep this tab open" for a loop that no longer exists
        st = _state()
        r = st.setdefault(supplier, {}).setdefault("run", {})
        r["state"] = "done"
        r["finished"] = frappe.utils.now()
        r["note"] = "auto-released: no heartbeat for %ds" % _RUN_STALE_SECONDS
        _save_state(st)
        frappe.db.commit()
        run = r
    return {"supplier": supplier,
            "state": run.get("state") or "idle",
            "mode": run.get("mode") or "batch",
            "done": int(flt(run.get("done"))), "total": int(flt(run.get("total"))),
            "results": run.get("results") or [],
            "submitted_total": len(v.get("submitted") or []),
            "reposts": frappe.db.count("Repost Item Valuation",
                                       {"status": ["in", ["Queued", "In Progress", "Failed"]]})}


# ============================== PRICE CHAIN (P1) ==============================
# The agreed-price layer: one fresh append-only buying price list per supplier
# ("VP - <name>"), never the old polluted lists. Every update is a NEW Item
# Price row with valid_from (previous row gets closed) — supplier price
# history builds up exactly like invoice eras. Creating the list also sets it
# as the supplier's default buying list, so every PO (portal or ERPNext)
# auto-fetches the latest valid price.

# The agreed price is owned by api/pricing.py (procurement's operating cycle).
# The workbench only READS it — a correction tool must never be a second place
# where a price can be defined, or the two drift apart.
_VP_PREFIX = pricing.VP_PREFIX


def _vp_name(supplier):
    return pricing.list_name(supplier)


def _vp_list(supplier, create=False):
    if create:
        return pricing.ensure_list(supplier)
    name = pricing.list_name(supplier)
    return name if frappe.db.exists("Price List", name) else None


def _vp_ccy(supplier):
    pl = _vp_list(supplier)
    if pl:
        return frappe.db.get_value("Price List", pl, "currency") or "MAD"
    return pricing.supplier_currency(supplier)


@frappe.whitelist()
def vendor_prices(supplier=None):
    """Price-list step data: per item — the current agreed price (+ since),
    the full price history, and the latest invoice era in MAD so the grid can
    show 'agreed vs actually billed' side by side."""
    assert_portal_access()
    if not supplier:
        frappe.throw("supplier required")
    uni = _moved_universe()
    vmap = _item_vendor_map(list(uni))
    mine = [ic for ic in uni if vmap.get(ic, {}).get("supplier") == supplier]
    if not mine:
        return {"supplier": supplier, "items": [], "currency": _vp_ccy(supplier)}
    meta = {}
    for i in range(0, len(mine), 700):
        for r in frappe.db.sql(
                """SELECT name, item_name, custom_sku sku FROM `tabItem`
                   WHERE name IN %s""", (mine[i:i + 700],), as_dict=True):
            meta[r.name] = r
    pl = _vp_list(supplier)
    hist = {}
    if pl:
        for r in frappe.db.sql(
                """SELECT item_code, price_list_rate rate, valid_from, valid_upto
                   FROM `tabItem Price` WHERE price_list=%s
                   ORDER BY valid_from DESC, creation DESC""", (pl,), as_dict=True):
            hist.setdefault(r.item_code, []).append(
                {"rate": flt(r.rate), "from": str(r.valid_from or "")[:10],
                 "upto": str(r.valid_upto or "")[:10] or None})
    _pr = _pricing(supplier, mine)
    ccy = _vp_ccy(supplier)
    from accounting_portal.api.cost_trace import _fx_series, _to_mad_fast
    fx = _fx_series()
    today = frappe.utils.nowdate()
    items = []
    for ic in mine:
        m = meta.get(ic) or {}
        h = hist.get(ic) or []
        cur = h[0] if h else None
        bench = (_pr.get(ic) or {}).get("latest")
        agreed_mad = _to_mad_fast(cur["rate"], ccy, today, fx) if cur else None
        items.append({
            "item_code": ic, "item_name": m.get("item_name"), "sku": m.get("sku"),
            "sold": round(uni[ic]["sold"]),
            "bench": bench,                                   # latest invoice era, MAD
            "agreed": cur["rate"] if cur else None,           # list currency
            "agreed_since": cur["from"] if cur else None,
            "agreed_mad": round(agreed_mad, 2) if agreed_mad else None,
            "dev_pct": (round(100.0 * (agreed_mad - flt(bench)) / flt(bench), 0)
                        if (agreed_mad and flt(bench) > 0) else None),
            "history": h[:12],
        })
    items.sort(key=lambda x: -x["sold"])
    n = sum(1 for x in items if x["agreed"] is not None)
    return {"supplier": supplier, "currency": ccy, "price_list": pl,
            "items": items,
            "summary": {"items": len(items), "priced": n, "unpriced": len(items) - n}}


def _write_prices(supplier, rows, confirm):
    """The team door of the pricing cycle.

    The write itself lives in api/pricing.write_agreed — the one place an
    approved price is ever created. All this does is supply the workbench's own
    benchmark (the invoice-era rate, converted into the supplier's list currency
    so the guard compares like with like) and shape the reply for the grid.
    """
    from accounting_portal.api.cost_trace import _fx_series, _to_mad_fast
    fx = _fx_series()
    ccy = _vp_ccy(supplier)
    today = frappe.utils.nowdate()
    codes = [r.get("item_code") for r in rows if r.get("item_code")]
    _pr = _pricing(supplier, codes)
    per_unit_mad = _to_mad_fast(1.0, ccy, today, fx) or 1.0

    def _bench(ic):
        era_mad = flt((_pr.get(ic) or {}).get("latest") or 0)
        return era_mad / per_unit_mad if era_mad else 0.0

    res = pricing.write_agreed(supplier, rows, confirm=bool(cint(confirm)), bench_fn=_bench)
    flagged = [{"item_code": f["item_code"], "rate": f["rate"],
                "agreed_mad": round(flt(f["rate"]) * per_unit_mad, 2),
                "era_mad": round(flt((_pr.get(f["item_code"]) or {}).get("latest") or 0), 2),
                "dev_pct": f["dev_pct"]} for f in res["flagged"]]
    invalid = res["invalid"]
    return {"saved": len(res["saved"]), "flagged": flagged[:50], "flagged_n": len(flagged),
            "invalid": invalid[:20], "invalid_n": len(invalid), "currency": ccy}


@frappe.whitelist()
def save_vendor_prices(supplier=None, rows=None, confirm=0):
    """Grid write: rows=[{item_code, rate, valid_from?}]. A >±50% jump vs the
    latest invoice era comes back as `flagged` (nothing written) until the
    caller re-sends with confirm=1 — the anti-pollution firewall."""
    assert_can_write()
    if not supplier:
        frappe.throw("supplier required")
    rows = json.loads(rows) if isinstance(rows, str) else (rows or [])
    if not rows:
        frappe.throw("no rows")
    return _write_prices(supplier, rows, confirm)


@frappe.whitelist()
def import_vendor_prices(supplier=None, csv_text=None):
    """Excel round-trip like weights: columns item_code/sku + price/rate
    (+ optional valid_from). Flagged rows are skipped and reported — an
    import never overrides the firewall."""
    assert_can_write()
    text = (csv_text or "").strip()
    if not text:
        frappe.throw("empty file")
    lines = [l for l in text.replace("\r\n", "\n").replace("\r", "\n").split("\n") if l.strip()]
    sep = ";" if lines[0].count(";") >= lines[0].count(",") else ","
    if "\t" in lines[0] and lines[0].count("\t") > lines[0].count(sep):
        sep = "\t"
    hdr = [c.strip().strip('"').lower() for c in lines[0].split(sep)]

    def _col(*names):
        for nm in names:
            for i, h in enumerate(hdr):
                if nm in h:
                    return i
        return None
    ci = _col("item_code", "item code", "code")
    cs = _col("sku")
    cp = _col("price", "rate", "سعر", "prix")
    cd = _col("valid_from", "date", "تاريخ")
    if cp is None:
        frappe.throw("no price column found (expect a header containing 'price'/'rate')")
    rows, unmatched = [], []
    for ln in lines[1:]:
        parts = [c.strip().strip('"') for c in ln.split(sep)]
        if len(parts) <= cp:
            continue
        raw = parts[cp].replace(",", ".").replace(" ", "")
        try:
            rate = float(raw) if raw else 0.0
        except Exception:
            rate = 0.0
        if rate <= 0:
            continue
        code = parts[ci].strip() if ci is not None and len(parts) > ci else ""
        sku = parts[cs].strip() if cs is not None and len(parts) > cs else ""
        ic = code if (code and frappe.db.exists("Item", code)) else \
            (frappe.db.get_value("Item", {"custom_sku": sku}, "name") if sku else None)
        if not ic:
            unmatched.append(code or sku or ln[:30])
            continue
        vfrom = parts[cd].strip()[:10] if (cd is not None and len(parts) > cd and parts[cd].strip()) else None
        rows.append({"item_code": ic, "rate": rate, "valid_from": vfrom})
    rep = _write_prices(supplier, rows, confirm=0) if rows else \
        {"saved": 0, "flagged": [], "flagged_n": 0, "invalid": [], "invalid_n": 0}
    rep["unmatched"] = unmatched[:50]
    rep["unmatched_n"] = len(unmatched)
    return rep
