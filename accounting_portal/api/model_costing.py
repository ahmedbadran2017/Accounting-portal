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

@frappe.whitelist()
def model_catalogue(search=None, fix_status=None, start=0, page_size=50):
    """The catalogue grouped by MODEL: one row per family with pooled cost
    evidence, aggregate stock and the fix progress (✓ n/N)."""
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
    ck = "ap_model_catalogue"
    cached = frappe.cache().get_value(ck)
    if cached is not None:
        return _slice_catalogue(cached, search, fix_status, start, page_size)
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
        })
    sev = {"ready": 0, "partial": 1, "unpriced": 2, "fixed": 3}
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
    variants, waiting_prs = [], set()
    for m in sorted(smap, key=lambda x: (meta.get(x) and meta[x].custom_sku) or x):
        s = smap[m]
        waits = sorted(p for p in item_prs.get(m, ()) if p not in costed)
        waiting_prs |= set(waits)
        variants.append({
            "item_code": m, "sku": meta[m].custom_sku if m in meta else m,
            "item_name": meta[m].item_name if m in meta else "",
            "qty": flt(s.q), "book_rate": round(flt(s.sv) / flt(s.q), 2) if flt(s.q) else 0,
            "fixed": m in fixed,
            "batch_tracked": bool(m in meta and meta[m].trk),
            "n_shipments": len(item_prs.get(m, ())),
            "waiting": waits,
        })
    return {
        "model": {"seed": item_code, "n_members": len(members),
                  "n_stocked": len(variants),
                  "suggested": (t or {}).get("cost_mad"),
                  "source": (t or {}).get("source"),
                  "basis_qty": (t or {}).get("basis_qty")},
        "evidence": ev, "variants": variants,
        "waiting_prs": sorted(waiting_prs),
    }


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
        frappe.cache().delete_value("ap_model_catalogue")   # the ✓ n/N moved
    except Exception:
        pass
    return {"posted": done, "skipped": skipped, "proposed": proposed,
            "remaining": max(len(todo_all) - len(done) - len(skipped) - len(proposed), 0)}
