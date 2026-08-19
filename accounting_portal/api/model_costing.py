"""Model costing — one review, one Submit, the whole variant family.

The team's real unit of work is the MODEL: one supplier price covers every
size/colour, so verifying 6.3 variants one page at a time was 6× wasted work
and 6× the audit surface. This module groups the stocked catalogue into
models (ERPNext variant families ∪ SKU-base kin, union-find so split
families merge), pools the family's purchase evidence for ONE verification,
and fans the Submit out item-by-item underneath — each variant still gets
its own retro schedule (ITS receipts, ITS dates), its own reversible reco
chain and its own Undo. The model layer is pure orchestration: zero change
to the accounting machinery.
"""
import frappe
from frappe.utils import flt

from accounting_portal.api.permissions import assert_portal_access, assert_can_write

SALES = "Justyol Morocco"


# ── model resolution ────────────────────────────────────────────────────────

def _base_of(sku):
    sku = (sku or "").strip()
    if "-" in sku:
        b = sku.split("-")[0].strip()
        if len(b) >= 4 and b != sku:
            return b
    return None


def _model_groups(codes):
    """Union-find over the stocked items: same variant_of OR same SKU base →
    one model. Returns [(members, meta)] where meta carries a stable key and
    a display name (the template's name when there is one)."""
    if not codes:
        return []
    meta = frappe.db.sql(
        """SELECT name, variant_of, custom_sku, item_name FROM `tabItem`
           WHERE name IN %s""", (tuple(codes),), as_dict=True)
    parent = {}

    def find(x):
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    by_t, by_b = {}, {}
    for m in meta:
        parent.setdefault(m.name, m.name)
        if m.variant_of:
            by_t.setdefault(m.variant_of, []).append(m.name)
        b = _base_of(m.custom_sku)
        if b:
            by_b.setdefault(b, []).append(m.name)
    # base groups are real models ONLY when the bare base exists as an item's
    # whole sku (JB8002) — a shared vendor prefix (T09ER-…) spans DIFFERENT
    # models and must never merge them
    if by_b:
        bares = set(frappe.db.sql(
            """SELECT DISTINCT custom_sku FROM `tabItem` WHERE custom_sku IN %s""",
            (tuple(by_b),), pluck=True))
        by_b = {b: grp for b, grp in by_b.items() if b in bares}
        # the BARE item itself (sku == base, dash-less → excluded from _base_of)
        # must join its group too, or it strands as its own catalogue row
        if by_b:
            for nm, bsku in frappe.db.sql(
                    """SELECT name, custom_sku FROM `tabItem`
                       WHERE custom_sku IN %s AND name IN %s""",
                    (tuple(by_b), tuple(codes))):
                by_b[bsku].append(nm)
    for grp in list(by_t.values()) + list(by_b.values()):
        for x in grp[1:]:
            union(grp[0], x)
    groups = {}
    for m in meta:
        groups.setdefault(find(m.name), []).append(m)
    out = []
    for members in groups.values():
        tpl = next((m.variant_of for m in members if m.variant_of), None)
        base = next((_base_of(m.custom_sku) for m in members if _base_of(m.custom_sku)), None)
        name = None
        if tpl:
            name = frappe.db.get_value("Item", tpl, "item_name")
        if not name:
            name = members[0].item_name
        # strip the variant suffix ("... -orange / 18 m") for a model-level label
        name = (name or "").split(" / ")[0]
        member_names = sorted(m.name for m in members)
        out.append({"members": member_names,
                    "key": member_names[0],   # any member resolves the model
                    "name": name, "base": base or (members[0].custom_sku or "")})
    return out


_SRC_PRIORITY = {"maslak_pi": 0, "local_pi": 1, "family_pi": 2, "morocco_pr": 3}


def _pick_suggested(tc, members):
    """Deterministic model cost: best SOURCE first (Maslak invoice > local >
    family > receipt), then sorted member order — the SAME figure on the
    catalogue row and inside the model file."""
    best = None
    for m in sorted(members):
        t = tc.get(m)
        if not (t and t.get("cost_mad")):
            continue
        pr = _SRC_PRIORITY.get(t.get("source"), 9)
        if best is None or pr < best[0]:
            best = (pr, m, t)
    return best


def _resolve_family(item_code):
    """Seed item → the model's full member list. Expands variant families and
    bare-base kin to a FIXED POINT so it always covers the same set the
    catalogue's union-find shows — chained families (variant of A, kin of B,
    B's own sibs…) never leave the Submit short of the displayed ✓ n/N."""
    from accounting_portal.api.cost_trace import _family_members
    members = {item_code}
    for _hop in range(5):
        before = len(members)
        # variant expansion for every member
        meta = frappe.db.sql(
            """SELECT name, variant_of, has_variants FROM `tabItem` WHERE name IN %s""",
            (tuple(members),), as_dict=True)
        tpls = {m.name for m in meta if m.has_variants} | {m.variant_of for m in meta if m.variant_of}
        if tpls:
            members |= set(frappe.db.sql(
                "SELECT name FROM `tabItem` WHERE variant_of IN %s", (tuple(tpls),), pluck=True))
            members |= tpls
        # kin expansion from every member added so far (bounded population)
        for m in list(members):
            _, mem = _family_members(m)
            members |= set(mem)
        if len(members) == before:
            break
    return sorted(members)


# ── read side ───────────────────────────────────────────────────────────────

def _month_sales(month):
    """{item: {"qty", "booked"}} — Delivery-Note outflows of one sales month.
    `month` = "2026-01". Reads LIVE SLE (repost-corrected)."""
    try:
        y, m = str(month).split("-")
        y, m = int(y), int(m)
    except Exception:
        return {}
    rows = frappe.db.sql(
        """SELECT item_code, SUM(-actual_qty) q, SUM(-stock_value_difference) v
           FROM `tabStock Ledger Entry`
           WHERE company=%s AND is_cancelled=0 AND voucher_type='Delivery Note'
             AND actual_qty < 0 AND YEAR(posting_date)=%s AND MONTH(posting_date)=%s
           GROUP BY item_code""", (SALES, y, m), as_dict=True)
    return {r.item_code: {"qty": flt(r.q), "booked": flt(r.v)} for r in rows}


@frappe.whitelist()
def model_catalogue(search=None, fix_status=None, start=0, page_size=50, month=None):
    """The catalogue grouped by MODEL: one row per family with pooled cost
    evidence, aggregate stock and the fix progress (✓ n/N). With `month`
    ("2026-01"): only models SOLD in that month, ranked by that month's
    estimated report impact — the month-workbench lens."""
    assert_portal_access()
    from accounting_portal.api.cost_trace import _true_cost_bulk, _fx_series
    from accounting_portal.api.shipment_costing import _fixed_map
    stocked = frappe.db.sql(
        """SELECT b.item_code, SUM(b.actual_qty) q, SUM(b.stock_value) sv
           FROM `tabBin` b JOIN `tabWarehouse` w ON w.name=b.warehouse
           WHERE w.company=%s AND b.actual_qty>0 GROUP BY b.item_code""",
        (SALES,), as_dict=True)
    qty = {s.item_code: flt(s.q) for s in stocked}
    val = {s.item_code: flt(s.sv) for s in stocked}
    codes = list(qty)
    ck = f"ap_model_catalogue:{month or 'all'}"
    cached = frappe.cache().get_value(ck)
    if cached is not None:
        return _slice_catalogue(cached, search, fix_status, start, page_size)
    msales = _month_sales(month) if month else {}
    tc = _true_cost_bulk(codes, _fx_series())
    fixed = _fixed_map()
    rows = []
    for g in _model_groups(codes):
        mem = g["members"]
        pick = _pick_suggested(tc, mem)
        t = pick[2] if pick else None
        n_fixed = sum(1 for m in mem if m in fixed)
        mq = sum(qty.get(m, 0) for m in mem)
        mv = sum(val.get(m, 0) for m in mem)
        book_rates = [round(val[m] / qty[m], 2) for m in mem if qty.get(m)]
        month_qty = month_booked = 0.0
        if month:
            for m2 in mem:
                ms = msales.get(m2)
                if ms:
                    month_qty += ms["qty"]
                    month_booked += ms["booked"]
            if month_qty <= 0:
                continue   # month lens: only models that hit this month's report
        rows.append({
            "key": g["key"], "name": g["name"], "base": g["base"],
            "n_variants": len(mem), "qty": round(mq), "value": round(mv),
            "true_cost": (t or {}).get("cost_mad"), "source": (t or {}).get("source") or "unpriced",
            "book_min": min(book_rates) if book_rates else 0,
            "book_max": max(book_rates) if book_rates else 0,
            "n_fixed": n_fixed,
            "status": ("fixed" if n_fixed >= len(mem) else
                       "partial" if n_fixed else
                       "ready" if t else "unpriced"),
            "month_qty": round(month_qty),
            "month_booked": round(month_booked),
            # estimated correction on THIS month's report: sold units × the gap
            # between the suggested true product cost and the avg booked rate
            "month_impact": round(abs(month_qty * flt((t or {}).get("cost_mad") or 0)
                                      - month_booked)) if (month and t) else 0,
        })
    sev = {"ready": 0, "partial": 1, "unpriced": 2, "fixed": 3}
    if month:
        rows.sort(key=lambda r: (sev[r["status"]], -r["month_impact"], -r["month_booked"]))
    else:
        rows.sort(key=lambda r: (sev[r["status"]], -r["value"]))
    try:
        frappe.cache().set_value(ck, rows, expires_in_sec=300)
    except Exception:
        pass
    return _slice_catalogue(rows, search, fix_status, start, page_size)


def _slice_catalogue(rows, search, fix_status, start, page_size):
    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1   # BEFORE filters
    q = (search or "").strip().lower()
    if q:
        rows = [r for r in rows if q in (r["name"] or "").lower() or q in (r["base"] or "").lower()]
    if fix_status in ("fixed", "partial", "ready", "unpriced"):
        rows = [r for r in rows if r["status"] == fix_status]
    start, page_size = int(start or 0), min(int(page_size or 50), 200)
    return {"total": len(rows), "counts": counts,
            "rows": rows[start:start + page_size]}


@frappe.whitelist()
def model_detail(item_code=None):
    """The model file: pooled evidence + every stocked variant's state + the
    union of freight waits — everything ONE review needs before ONE submit."""
    assert_portal_access()
    if not item_code:
        frappe.throw("item_code required")
    from accounting_portal.api.cost_trace import _true_cost_bulk, _fx_series
    from accounting_portal.api.shipment_costing import _fixed_map, _pr_lines
    from accounting_portal.api.landed_prep import shipment_review
    from accounting_portal.api.valuation import item_fix_preview
    members = _resolve_family(item_code)
    stocked = frappe.db.sql(
        """SELECT b.item_code, SUM(b.actual_qty) q, SUM(b.stock_value) sv
           FROM `tabBin` b JOIN `tabWarehouse` w ON w.name=b.warehouse
           WHERE w.company=%s AND b.actual_qty>0 AND b.item_code IN %s
           GROUP BY b.item_code""", (SALES, tuple(members)), as_dict=True)
    smap = {s.item_code: s for s in stocked}
    tc = _true_cost_bulk(members, _fx_series())
    fixed = _fixed_map()
    meta = {m.name: m for m in frappe.db.sql(
        """SELECT name, item_name, custom_sku, IFNULL(has_batch_no,0)+IFNULL(has_serial_no,0) trk,
                  IFNULL(weight_per_unit,0) w
           FROM `tabItem` WHERE name IN %s""", (tuple(members),), as_dict=True)}
    # evidence: preview the member the SUGGESTED figure actually comes from
    # (deterministic pick) — never the arbitrary clicked seed, whose own
    # paper-price docs could contradict the family figure shown beside them
    pick = _pick_suggested(tc, members)
    ev_seed = pick[1] if pick else item_code
    ev = []
    try:
        ev = (item_fix_preview(company=SALES, item_code=ev_seed) or {}).get("evidence") or []
    except Exception:
        pass
    # freight picture: which member sits in which shipment, what still waits
    sr = shipment_review()
    costed = {r["name"] for r in sr["receipts"] if r["source"] in ("bills", "rate")}
    lines_all = _pr_lines([r["name"] for r in sr["receipts"]])
    item_prs = {}
    for prn, lns in lines_all.items():
        for l in lns:
            if l.ic in smap:
                item_prs.setdefault(l.ic, set()).add(prn)
    t = pick[2] if pick else None
    # live landed per stocked member — powers the per-variant impact preview
    from accounting_portal.api.shipment_costing import _live_landed
    live = _live_landed(set(smap), sr["receipts"], year=sr["year"]) if smap else {}
    variants, waiting_prs, fam_prs = [], set(), set()
    for m in sorted(smap, key=lambda x: (meta.get(x) and meta[x].custom_sku) or x):
        s = smap[m]
        waits = sorted(p for p in item_prs.get(m, ()) if p not in costed)
        waiting_prs |= set(waits)
        fam_prs |= set(item_prs.get(m, ()))
        w = flt(meta[m].w) if m in meta else 0
        variants.append({
            "item_code": m, "sku": meta[m].custom_sku if m in meta else m,
            "item_name": meta[m].item_name if m in meta else "",
            "qty": flt(s.q), "book_rate": round(flt(s.sv) / flt(s.q), 2) if flt(s.q) else 0,
            "fixed": m in fixed,
            "batch_tracked": bool(m in meta and meta[m].trk),
            "n_shipments": len(item_prs.get(m, ())),
            "waiting": waits,
            "weight": w,
            "weight_suspect": bool(w <= 0.2 or w == 0.5),
            "landed_unit": round(flt(live.get(m)), 2),
        })
    # the FAMILY's shipments — same picture the SKU page shows, one row per PR,
    # with which variants ride in it and the same channel/rate actions
    from accounting_portal.api.landed_prep import get_air_rates, _air_rate_at, get_basis
    bands = get_air_rates(sr["year"])
    sku_of = {m: (meta[m].custom_sku if m in meta else m) for m in smap}
    receipts = []
    for r in sr["receipts"]:
        if r["name"] not in fam_prs:
            continue
        mems = sorted(sku_of[m] for m in smap if r["name"] in item_prs.get(m, ()))
        receipts.append({
            "pr": r["name"], "dt": r["dt"], "channel": r["channel"],
            "channel_confirmed": bool(r.get("channel_confirmed")),
            "pr_qty": r["qty"], "source": r["source"], "rate_kg": r["rate_kg"],
            "band_rate": _air_rate_at(bands, r["dt"]) if r["channel"] == "air" else 0,
            "members": mems,
        })
    receipts.sort(key=lambda x: x["dt"], reverse=True)
    return {
        "model": {"seed": item_code, "n_members": len(members),
                  "n_stocked": len(variants),
                  "suggested": (t or {}).get("cost_mad"),
                  "source": (t or {}).get("source"),
                  "basis_qty": (t or {}).get("basis_qty")},
        "evidence": ev, "variants": variants,
        "receipts": receipts, "year": sr["year"],
        "frozen": bool(get_basis(year=sr["year"])),
        "waiting_prs": sorted(waiting_prs),
    }


@frappe.whitelist()
def month_scoreboard(month=None):
    """The month workbench header: how many models hit this month's report,
    how many are fully fixed, and the LIVE booked-vs-true COGS line (the
    booked side is re-read from GL, so every retro apply moves it)."""
    assert_portal_access()
    if not month:
        frappe.throw("month required (YYYY-MM)")
    from accounting_portal.api.cost_trace import _true_cost_bulk, _fx_series
    from accounting_portal.api.shipment_costing import _fixed_map
    msales = _month_sales(month)
    out = {"month": month, "n_items": len(msales), "n_models": 0, "n_models_fixed": 0,
           "booked": round(sum(v["booked"] for v in msales.values())),
           "units": round(sum(v["qty"] for v in msales.values()))}
    if msales:
        fixed = _fixed_map()
        for g in _model_groups(list(msales)):
            mem = g["members"]
            out["n_models"] += 1
            if all(m in fixed or m not in msales for m in mem):
                # every member that touched this month is fixed
                if any(m in fixed for m in mem):
                    out["n_models_fixed"] += 1
    # the report line: booked (live GL) vs true (engine) for the month
    try:
        from accounting_portal.api.cogs_trueup import monthly_review
        y = int(str(month)[:4])
        for r in (monthly_review(year=y) or {}).get("rows", []):
            if r["month"] == month:
                out["report"] = {"booked": r["booked"], "true": r["true"],
                                 "delta": r["delta"], "coverage_pct": r["coverage_pct"],
                                 "posted": bool(r.get("posted"))}
                break
    except Exception:
        pass
    return out


@frappe.whitelist()
def set_family_weight(item_code=None, weight=None, only_suspect=1):
    """One measured weight for the whole family (variants of a model share
    packaging). By default only fills SUSPECT weights (zero/0.5/≤200g) —
    a deliberate different weight on one size is respected."""
    assert_can_write()
    from accounting_portal.api.weights import set_item_weight, _flag
    w = flt(weight)
    members = _resolve_family(item_code)
    stocked = frappe.db.sql(
        """SELECT DISTINCT b.item_code FROM `tabBin` b
           JOIN `tabWarehouse` wh ON wh.name=b.warehouse
           WHERE wh.company=%s AND b.actual_qty>0 AND b.item_code IN %s""",
        (SALES, tuple(members)), pluck=True)
    only = str(only_suspect) in ("1", "true", "True")
    applied, skipped = [], []
    for m in stocked:
        cur = flt(frappe.db.get_value("Item", m, "weight_per_unit"))
        if only and not _flag(cur):
            skipped.append(m)
            continue
        set_item_weight(item_code=m, weight=w)
        applied.append(m)
    return {"applied": applied, "skipped": skipped, "weight": w}


# ── write side ──────────────────────────────────────────────────────────────

@frappe.whitelist()
def apply_model(item_code=None, rate=None, note=None, retro=1, exclude=None, limit=15):
    """ONE submit for the whole family: every stocked, unfixed, unexcluded
    variant gets the SAME verified product cost + ITS OWN live landed and ITS
    OWN retro schedule (its receipts, its dates) via fix_item_cost — one
    reversible action per variant. Waves of `limit`; the UI loops on
    `remaining`. Variants still waiting for freight are skipped with reasons."""
    assert_can_write()
    product = flt(rate)
    if product <= 0:
        frappe.throw("A positive verified product cost is required")
    if product < 0.5:
        frappe.throw(f"{product} MAD/unit looks like a broken FX conversion, not a price")
    exclude = set(frappe.parse_json(exclude or "[]") or [])
    retro = str(retro) in ("1", "true", "True")
    limit = min(int(limit or 15), 40)
    from accounting_portal.api.shipment_costing import _fixed_map, _pr_lines, _live_landed
    from accounting_portal.api.landed_prep import shipment_review
    from accounting_portal.api.valuation import fix_item_cost
    members = _resolve_family(item_code)
    stocked = frappe.db.sql(
        """SELECT DISTINCT b.item_code FROM `tabBin` b
           JOIN `tabWarehouse` w ON w.name=b.warehouse
           WHERE w.company=%s AND b.actual_qty>0 AND b.item_code IN %s""",
        (SALES, tuple(members)), pluck=True)
    fixed = _fixed_map()
    tracked = set(frappe.db.sql(
        """SELECT name FROM `tabItem` WHERE name IN %s
           AND (IFNULL(has_batch_no,0)=1 OR IFNULL(has_serial_no,0)=1)""",
        (tuple(stocked),), pluck=True)) if stocked else set()
    todo_all = [m for m in sorted(stocked)
                if m not in fixed and m not in exclude and m not in tracked]
    # freight completeness per member — same rule as every other apply path
    sr = shipment_review()
    costed = {r["name"] for r in sr["receipts"] if r["source"] in ("bills", "rate")}
    lines_all = _pr_lines([r["name"] for r in sr["receipts"]])
    item_prs = {}
    for prn, lns in lines_all.items():
        for l in lns:
            item_prs.setdefault(l.ic, set()).add(prn)
    live = _live_landed(set(todo_all), sr["receipts"], year=sr["year"])
    done, skipped, proposed = [], [], []
    for m in todo_all:
        if len(done) + len(proposed) >= limit:
            break
        waits = [p for p in item_prs.get(m, ()) if p not in costed]
        if waits:
            skipped.append({"item_code": m, "reason": "waiting freight: " + ", ".join(waits[:3])})
            continue
        landed = flt(live.get(m))
        full = round(product + landed, 2)
        try:
            res = fix_item_cost(
                company=SALES, item_code=m, rate=full, full_rate=1, retro=1 if retro else 0,
                retro_product=product, retro_year=sr["year"],
                note=((note or "").strip() or "Model apply")
                     + f" — family of {item_code} · product {product} + landed {landed} = {full}")
            if isinstance(res, dict) and res.get("status") and res["status"] != "Posted":
                proposed.append({"item_code": m, "status": res["status"]})
                continue
            done.append({"item_code": m, "full": full,
                         "voucher": (res or {}).get("voucher_no")})
        except Exception as e:
            skipped.append({"item_code": m, "reason": str(e)[:140]})
            continue
    try:
        frappe.cache().delete_value("ap_model_catalogue:all")   # the ✓ n/N moved
        today = frappe.utils.nowdate()
        for mm in range(1, 13):
            frappe.cache().delete_value(f"ap_model_catalogue:{today[:4]}-{mm:02d}")
    except Exception:
        pass
    return {"posted": done, "skipped": skipped, "proposed": proposed,
            "remaining": max(len(todo_all) - len(done) - len(skipped) - len(proposed), 0)}
