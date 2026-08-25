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
    """{item_code: {"sold": qty, "oh": qty}} — items DELIVERED in 2026 only.

    Deliberately excludes never-sold stock (new selections still in transit /
    at the Istanbul hub, 10-per-variant): they have zero COGS impact, and the
    new receiving process prices them correctly on arrival — correcting them
    here would only inflate the team's workload. On-hand qty is kept as an
    info column for the items that DID sell."""
    out = {}
    for r in frappe.db.sql(
            """SELECT dni.item_code ic, SUM(dni.qty) q FROM `tabDelivery Note Item` dni
               JOIN `tabDelivery Note` dn ON dn.name=dni.parent
               WHERE dn.docstatus=1 AND dn.company=%s AND dn.posting_date>='2026-01-01'
               GROUP BY dni.item_code""", (SALES,), as_dict=True):
        out.setdefault(r.ic, {"sold": 0.0, "oh": 0.0})["sold"] = flt(r.q)
    if not out:
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
    # half-invoice roll-up for the banner (official + non-official halves)
    q_o = sum(m["qty"] for m in moves if m.get("cc") == "off" and not m["internal"])
    v_o = sum(m["qty"] * (m["mad"] or 0) for m in moves if m.get("cc") == "off" and not m["internal"])
    q_n = sum(m["qty"] for m in moves if m.get("cc") == "non")
    v_n = sum(m["qty"] * (m["mad"] or 0) for m in moves if m.get("cc") == "non")
    half = None
    if q_o > 0 and q_n > 0:
        half = {"off_qty": round(q_o), "off_rate": round(v_o / q_o, 2),
                "non_qty": round(q_n), "non_rate": round(v_n / q_n, 2),
                "combined": round((v_o + v_n) / max(q_o, q_n), 2),
                "physical_qty": round(max(q_o, q_n))}
    return {"item_code": item_code, "moves": moves[:60],
            "invoiced_qty": inv_q, "received_qty": rec_q, "coverage_pct": cov,
            "partial_invoice": bool(rec_q and inv_q < rec_q * 0.95),
            "half_invoice": half,
            "bench": tc, "override": ov}


def _invoice_sched(supplier, items):
    """Per item: the TIME-PHASED rate schedule from its own invoices.

    Bought 100 in March at price A, 200 in August at price B → March-July
    deliveries cost the March average, August-on cost the running average
    including B (each invoice date opens a new era at the moving qty-weighted
    invoice average AS OF that date, at that date's FX). The constant freight
    layer (channel-rate × weight) rides on every era. Feeds fix_item_cost's
    retro_sched so the retro heals each month at ITS OWN price."""
    if not items:
        return {}
    from accounting_portal.api.cost_trace import _fx_series, _to_mad_fast
    fx = _fx_series()
    rate_kg, _ch = _rate_for(supplier)
    w = {}
    for i in range(0, len(items), 700):
        for r in frappe.db.sql(
                "SELECT name, IFNULL(weight_per_unit,0) x FROM `tabItem` WHERE name IN %s",
                (items[i:i + 700],), as_dict=True):
            w[r.name] = flt(r.x)
    lines = {}
    half = set()      # half-invoice items: official+non-official halves are
                      # time-shifted, so era pricing would mislead → uniform
    seen_cc = {}
    for i in range(0, len(items), 700):
        chunk = tuple(items[i:i + 700])
        for r in frappe.db.sql(
                """SELECT pii.item_code ic, pii.base_rate rate, pi.posting_date d
                   , pii.qty, IFNULL(pii.cost_center, IFNULL(pi.cost_center,'')) cc
                   FROM `tabPurchase Invoice Item` pii
                   JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
                   WHERE pi.docstatus=1 AND pi.company=%s AND pii.item_code IN %s
                     AND pii.qty>0 ORDER BY pi.posting_date""", (SOURCING, chunk), as_dict=True):
            mad = _to_mad_fast(flt(r.rate), "TRY", r.d, fx)
            if mad > 0:
                lines.setdefault(r.ic, []).append((str(r.d), flt(r.qty), mad))
                kinds = seen_cc.setdefault(r.ic, set())
                kinds.add("non" if "non-official" in (r.cc or "").lower() else "off")
                if len(kinds) > 1:
                    half.add(r.ic)
        for r in frappe.db.sql(
                """SELECT pii.item_code ic, pii.base_rate rate, pi.posting_date d
                   , pii.qty FROM `tabPurchase Invoice Item` pii
                   JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
                   WHERE pi.docstatus=1 AND pi.company=%s AND pii.item_code IN %s
                     AND pii.qty>0 AND pi.supplier NOT IN %s
                   ORDER BY pi.posting_date""",
                (SALES, chunk, _INTERNAL_SUPPLIERS), as_dict=True):
            if flt(r.rate) > 0:
                lines.setdefault(r.ic, []).append((str(r.d), flt(r.qty), flt(r.rate)))
    # freight is era-priced too (the air 100/110/120 pattern): a dated channel
    # schedule opens freight eras BETWEEN invoices as well — each breakpoint
    # (invoice date OR rate-change date) gets product-avg-as-of + that era's
    # freight × weight. A vendor scalar override keeps freight constant.
    vendor_scalar = flt(_rates().get(f"vendor::{supplier}")) > 0
    fr_sched = [] if vendor_scalar else (_rate_scheds().get(_ch) or [])

    def fr_rate_at(d):
        if not fr_sched:
            return rate_kg
        r = fr_sched[0]["rate"]
        for p in fr_sched:
            if p["date"] <= d:
                r = p["rate"]
            else:
                break
        return flt(r)

    out = {}
    for ic, ls in lines.items():
        if ic in half:
            continue          # uniform retro at the combined benchmark
        ls.sort(key=lambda x: x[0])
        wkg = w.get(ic, 0.0)
        first = ls[0][0]
        bps = sorted({d for d, _q, _m in ls}
                     | {p["date"] for p in fr_sched if p["date"] > first})
        pts, q, v, i = [], 0.0, 0.0, 0
        for d in bps:
            while i < len(ls) and ls[i][0] <= d:
                q += ls[i][1]; v += ls[i][2] * ls[i][1]; i += 1
            if q <= 0:
                continue
            era = round(v / q + fr_rate_at(d) * wkg, 2)
            if pts and pts[-1]["date"] == d:
                pts[-1]["rate"] = era
            else:
                pts.append({"date": d, "rate": era})
        if pts:
            out[ic] = pts
    return out


def _full_rates(supplier, items):
    """{item: {product, freight, rate, weight_kg}} — product benchmark plus the
    channel freight layer (rate/kg × unit weight). Local vendors: freight 0.
    Every imported unit carries freight in its COST whatever year it shipped —
    separate from the 2026 pool-clearing view."""
    from accounting_portal.api.valuation import _benchmarks
    rate_kg, _ch = _rate_for(supplier)
    bench = _benchmarks(SALES, items) if items else {}
    for ic, ov in _cost_overrides().items():        # reviewer's verified cost wins
        if ic in (items or []):
            bench[ic] = flt(ov.get("rate"))
    w = {}
    if items:
        for i in range(0, len(items), 700):
            for r in frappe.db.sql(
                    "SELECT name, IFNULL(weight_per_unit,0) x FROM `tabItem` WHERE name IN %s",
                    (items[i:i + 700],), as_dict=True):
                w[r.name] = flt(r.x)
    out = {}
    for ic in items:
        b = flt(bench.get(ic))
        if b <= 0:
            out[ic] = {"product": None, "freight": 0, "rate": None, "weight_kg": w.get(ic, 0)}
            continue
        fr = round(rate_kg * w.get(ic, 0.0), 2)
        out[ic] = {"product": b, "freight": fr, "rate": round(b + fr, 2),
                   "weight_kg": w.get(ic, 0)}
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
    from accounting_portal.api.valuation import fix_item_cost
    rates = _full_rates(supplier, items)
    scheds = _invoice_sched(supplier, items)
    cost_ovs = _cost_overrides()
    rate_kg, chan = _rate_for(supplier)
    st = _state()
    v = st.setdefault(supplier, {})
    done = v.setdefault("submitted", [])
    results = []
    for ic in items:
        rr = rates.get(ic) or {}
        if not rr.get("rate"):
            results.append({"item_code": ic, "result": "skipped — no cost evidence"})
            continue
        if rate_kg > 0 and flt(rr.get("weight_kg")) <= 0:
            results.append({"item_code": ic, "result": "skipped — no weight (freight layer unknown)"})
            continue
        split = (f"vendor workbench — {supplier} [{chan}]: "
                 f"product {rr['product']} + freight {rr['freight']} "
                 f"({rate_kg}/kg × {rr['weight_kg']}kg)")
        # invoice-era schedule: each month heals at ITS era's invoice average.
        # A manual cost override is a single verified truth → uniform retro.
        sched = None if ic in cost_ovs else (scheds.get(ic) or None)
        if sched:
            split += f" — {len(sched)} invoice era(s)"
        try:
            r = fix_item_cost(company=SALES, item_code=ic, rate=rr["rate"], full_rate=1,
                              retro=1, retro_product=rr["product"],
                              retro_sched=json.dumps(sched) if sched else None,
                              note=(note + " — " if note else "") + split)
            results.append({"item_code": ic, "result": (r or {}).get("result") or "ok"})
            if ic not in done:
                done.append(ic)
        except Exception as e:
            results.append({"item_code": ic, "result": f"error: {e}"})
    _save_state(st)
    return {"supplier": supplier, "results": results,
            "submitted_total": len(done)}
