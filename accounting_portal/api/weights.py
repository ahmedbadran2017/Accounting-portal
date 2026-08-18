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
    reg = _reg_all()
    out = []
    counts = {"zero": 0, "tiny": 0, "default": 0, "estimated": 0}
    for r in rows:
        est_src = reg.get(r.item_code)
        if est_src:
            counts["estimated"] += 1
        f = _flag(r.w)
        if not f:
            if est_src and flag == "estimated":
                r["flag"] = "estimated"
                r["est_src"] = est_src
                r["units_in"] = flt(r.units_in)
                r["stock_qty"] = flt(r.stock_qty)
                out.append(r)
            continue
        counts[f] += 1
        r["flag"] = f
        r["est_src"] = est_src
        r["units_in"] = flt(r.units_in)
        r["stock_qty"] = flt(r.stock_qty)
        out.append(r)
    q = (search or "").strip().lower()
    if q:
        out = [r for r in out if q in (r.item_name or "").lower()
               or q in (r.sku or "").lower() or q in r.item_code.lower()]
    if flag in ("zero", "tiny", "default", "estimated"):
        out = [r for r in out if r["flag"] == flag]
    sev = {"zero": 0, "tiny": 1, "default": 2, "estimated": 3}
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
    _reg_update(item_code, None)   # manual measurement beats any estimate
    frappe.db.commit()
    # the calibration scale is derived from the whole population — recompute
    try:
        for y in (2025, 2026, 2027):
            frappe.cache().delete_value(f"ap_hist_scales:{y}")
    except Exception:
        pass
    return {"item_code": item_code, "weight": w}


# ── The estimator: fill missing weights from the data itself ────────────────
# Ladder (validated on a 300-item holdout of trusted weights): FAMILY sibling
# median (98% within ±30%) → NAME-SIMILARITY top-5 median over the 55K-item
# trusted corpus (90% within ±30%) → KEYWORD-CLASS median. Every estimate is
# registered with its source (≈ chip in the worklist); a manual entry always
# overrides and unregisters. Estimates fix the RELATIVE split fairness — the
# channel calibration keeps the money total anchored to the real bills.

_TRUSTED_SQL = """SELECT name, item_name, variant_of, weight_per_unit w FROM `tabItem`
    WHERE weight_per_unit > 0.2 AND weight_per_unit <= 50 AND weight_per_unit != 0.5
      AND IFNULL(item_name,'') != ''"""

# keyword classes with sanity bands (kg) — fallback rung only
_CLASSES = [
    ("apparel_set", ("takım", "takim", "set", "ensemble"), (0.1, 3.0)),
    ("outerwear", ("ceket", "mont", "kaban", "jacket", "veste", "manteau", "hırka", "hirka"), (0.2, 3.5)),
    ("dress", ("elbise", "dress", "robe", "tunik"), (0.1, 2.0)),
    ("top", ("tişört", "tisort", "t-shirt", "tshirt", "gömlek", "gomlek", "chemise", "sweatshirt", "kazak", "bluz", "body"), (0.05, 1.5)),
    ("bottom", ("pantolon", "şort", "sort", "jean", "tayt", "etek", "eşofman", "esofman", "pantalon"), (0.1, 2.0)),
    ("pyjama", ("pijama", "pyjama", "gecelik"), (0.1, 1.5)),
    ("cookware", ("tencere", "tava", "çaydanlık", "caydanlik", "düdüklü", "cezve"), (0.3, 8.0)),
    ("tableware", ("tabak", "kase", "kâse", "servis", "sunum", "sahan"), (0.2, 6.0)),
    ("drinkware", ("bardak", "kupa", "mug", "fincan", "termos", "matara", "sürahi", "surahi"), (0.1, 3.0)),
    ("storage", ("kavanoz", "saklama", "kutu", "organizer", "organizatör", "sepet", "erzak"), (0.1, 5.0)),
    ("home_textile", ("battaniye", "yorgan", "nevresim", "havlu", "çarşaf", "carsaf", "yastık", "yastik", "pike"), (0.2, 6.0)),
    ("shoes", ("ayakkabı", "ayakkabi", "bot", "sandalet", "terlik", "sneaker", "chaussure"), (0.2, 2.5)),
]


def _toks(s):
    s = (s or "").lower()
    import re as _re
    s = _re.sub(r"[^a-zçğıöşü0-9\s]", " ", s)
    return set(t for t in s.split() if len(t) >= 3 and not t.isdigit())


def _med(lst):
    v = sorted(lst)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2.0


def _estimator_ctx():
    """Corpus + inverted index + family medians + class medians (built per
    request, ~2s — the waves keep each request small)."""
    trusted = frappe.db.sql(_TRUSTED_SQL, as_dict=True)
    corpus, inv, fam = [], {}, {}
    for t in trusted:
        tk = _toks(t.item_name)
        if not tk:
            continue
        corpus.append((tk, flt(t.w)))
        idx = len(corpus) - 1
        for tok in tk:
            inv.setdefault(tok, []).append(idx)
        if t.variant_of:
            fam.setdefault(t.variant_of, []).append(flt(t.w))
    fam_med = {t: _med(v) for t, v in fam.items()}
    cls_med = {}
    for cname, kws, band in _CLASSES:
        vals = []
        for tk, w in corpus:
            if tk & set(kws):
                vals.append(w)
        if len(vals) >= 15:
            m = _med(vals)
            if band[0] <= m <= band[1]:
                cls_med[cname] = (m, set(kws))
    return {"corpus": corpus, "inv": inv, "fam": fam_med, "cls": cls_med}


def _estimate_one(name_toks, variant_of, ctx):
    """(weight, source) via the ladder — None when no rung fires."""
    w = ctx["fam"].get(variant_of) if variant_of else None
    if w and 0.02 <= w <= 20:
        return round(w, 3), "family"
    if name_toks:
        counts = {}
        for tok in name_toks:
            for j in ctx["inv"].get(tok, ()):
                counts[j] = counts.get(j, 0) + 1
        scored = []
        for j, inter in counts.items():
            if inter >= 2:
                tk2, w2 = ctx["corpus"][j]
                scored.append((inter / len(name_toks | tk2), w2))
        scored.sort(reverse=True)
        if len(scored) >= 3 and scored[0][0] >= 0.25:
            w = _med([x[1] for x in scored[:5]])
            if 0.02 <= w <= 15:
                return round(w, 3), "similar"
        for cname, (m, kws) in ctx["cls"].items():
            if name_toks & kws:
                return round(m, 3), "class"
    return None, None


def _suspects():
    return frappe.db.sql(
        """SELECT DISTINCT i.name, i.item_name, i.custom_sku sku, i.variant_of,
                  IFNULL(i.weight_per_unit,0) w
           FROM `tabPurchase Receipt Item` pri
           JOIN `tabPurchase Receipt` pr ON pr.name=pri.parent
           JOIN `tabItem` i ON i.name=pri.item_code
           LEFT JOIN `tabSupplier` s ON s.name=pr.supplier
           WHERE pr.company=%s AND pr.docstatus=1 AND i.is_stock_item=1
             AND IFNULL(s.supplier_group,'') NOT IN %s
             AND (IFNULL(i.weight_per_unit,0) <= 0.2 OR i.weight_per_unit = 0.5)
           ORDER BY i.name""", (SALES, _DOMESTIC_GROUPS), as_dict=True)


# estimate registry — chunked config keys (defvalue is TEXT-bounded)
def _reg_key(item_code):
    return f"ap_west_{sum(ord(c) for c in item_code) % 4}"


def _reg_all():
    out = {}
    for i in range(4):
        try:
            out.update(frappe.parse_json(frappe.db.get_default(f"ap_west_{i}") or "{}") or {})
        except Exception:
            pass
    return out


def _reg_update(item_code, src):
    """src=None removes (manual measurement overrides the estimate)."""
    import json as _json
    k = _reg_key(item_code)
    try:
        m = frappe.parse_json(frappe.db.get_default(k) or "{}") or {}
    except Exception:
        m = {}
    if src is None:
        m.pop(item_code, None)
    else:
        m[item_code] = src[0]   # f / s / c — compact
    frappe.db.set_default(k, _json.dumps(m))


@frappe.whitelist()
def estimate_weights(start=0, page_size=400):
    """Preview a wave of estimates for the suspect items (read-only)."""
    assert_portal_access()
    start, page_size = int(start or 0), min(int(page_size or 400), 500)
    sus = _suspects()
    wave = sus[start:start + page_size]
    ctx = _estimator_ctx()
    rows = []
    for x in wave:
        w, src = _estimate_one(_toks(x.item_name), x.variant_of, ctx)
        rows.append({"item_code": x.name, "sku": x.sku, "item_name": x.item_name,
                     "current": flt(x.w), "est": w, "src": src})
    return {"total": len(sus), "start": start, "rows": rows}


@frappe.whitelist()
def apply_weight_estimates(items=None):
    """Apply estimates for the given item codes — recomputed SERVER-side (the
    client's preview numbers are never trusted). Master-data only, no GL.
    Registered with source; busts the calibration cache."""
    assert_can_write()
    codes = frappe.parse_json(items or "[]") or []
    if not codes:
        frappe.throw("items required")
    codes = codes[:500]
    meta = frappe.db.sql(
        """SELECT name, item_name, variant_of, IFNULL(weight_per_unit,0) w,
                  IFNULL(weight_uom,'') uom
           FROM `tabItem` WHERE name IN %s""", (tuple(codes),), as_dict=True)
    ctx = _estimator_ctx()
    applied, skipped = [], []
    for x in meta:
        # never overwrite a weight that already looks measured
        if flt(x.w) > 0.2 and flt(x.w) != 0.5:
            skipped.append({"item_code": x.name, "reason": "already has a real weight"})
            continue
        w, src = _estimate_one(_toks(x.item_name), x.variant_of, ctx)
        if not w:
            skipped.append({"item_code": x.name, "reason": "no confident estimate"})
            continue
        frappe.db.set_value("Item", x.name, "weight_per_unit", w,
                            update_modified=False)
        if not x.uom:
            frappe.db.set_value("Item", x.name, "weight_uom", "Kg", update_modified=False)
        _reg_update(x.name, src)
        applied.append({"item_code": x.name, "w": w, "src": src})
    frappe.db.commit()
    try:
        for y in (2025, 2026, 2027):
            frappe.cache().delete_value(f"ap_hist_scales:{y}")
        frappe.cache().delete_value("ap_model_catalogue")
    except Exception:
        pass
    return {"applied": applied, "skipped": skipped}
