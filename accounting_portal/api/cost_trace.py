"""Product Cost Trace — cross-company cost provenance for a product (SKU).

The truth anchor for a Morocco item's cost is NOT its Morocco-side purchase
document (those carry a PAPER USD transfer price booked at the wrong FX) but the
ACTUAL supplier bill in the sourcing company — Maslak (Turkey), in TRY. This
module traces a product's purchase journey across every company:

    origin supplier → PO → PR → PI (Maslak)   ← PI = the true cost
        → [paper intercompany transfer, shown but ignored]
        → PR / PI (Morocco)                    ← where FX distortion enters
        → current Morocco valuation → COGS

and surfaces WHERE the unit price diverged, so the real landed cost can be
rebuilt from source. Read-only / analysis only — the correction itself flows
through the audited Valuation Doctor (valuation.correct_valuation) for the
product-cost layer and the Landed Cockpit (153.03) for the inbound-freight
layer. Landed cost is added SEPARATELY on top of the product cost returned here.
"""
import frappe
from frappe.utils import flt, getdate

from accounting_portal.api.permissions import assert_portal_access, assert_can_write
from accounting_portal.api.landed_engine import _live_fx

SOURCING = "Maslak LTD"          # Turkey — the true-cost anchor (buys TRY)
SALES = "Justyol Morocco"        # the entity whose COGS we are fixing
TRANSFER_CUSTOMER = "Justyol Morocco"   # intercompany customer name in Maslak

# How much recent invoiced qty forms the cost basis per item (most-recent first).
_BASIS_QTY = 60


def _usd_rate(to_cur, date):
    """USD→to_cur at/just-before `date` (fallback: earliest known)."""
    r = frappe.db.sql(
        """SELECT exchange_rate FROM `tabCurrency Exchange`
           WHERE from_currency='USD' AND to_currency=%s AND date<=%s ORDER BY date DESC LIMIT 1""",
        (to_cur, date))
    if not r:
        r = frappe.db.sql(
            """SELECT exchange_rate FROM `tabCurrency Exchange`
               WHERE from_currency='USD' AND to_currency=%s ORDER BY date ASC LIMIT 1""", (to_cur,))
    return flt(r[0][0]) if r else 0.0


def _to_mad(rate_fc, currency, date, cache):
    """Convert a foreign unit rate to MAD at the correct rate for the date.

    MAD passes through. A direct rate (e.g. USD→MAD) is used when present.
    Currencies with NO direct MAD rate — notably TRY (Maslak's currency) — are
    cross-rated through USD: cur→MAD = (USD→MAD) / (USD→cur). This is what makes
    the Maslak-invoice (TRY) anchor usable, since the books hold no TRY→MAD rate.
    """
    if currency == "MAD":
        return flt(rate_fc)
    date = str(date or frappe.utils.nowdate())[:10]
    lf = flt(_live_fx(currency, date, cache))
    if lf > 0:
        return flt(rate_fc) * lf
    um, uc = _usd_rate("MAD", date), _usd_rate(currency, date)
    if um > 0 and uc > 0:
        return flt(rate_fc) * um / uc
    return 0.0


@frappe.whitelist()
def search_items(query=None, limit=25):
    """Find products by SKU / name / code for the Cost Trace picker. Ranks items
    that currently hold Morocco stock first (those are the ones worth tracing)."""
    assert_portal_access()
    q = (query or "").strip()
    if len(q) < 2:
        return []
    like = f"%{q}%"
    rows = frappe.db.sql(
        """SELECT i.name item_code, i.item_name, i.custom_sku sku,
                  IFNULL(b.qty, 0) stock_qty
           FROM `tabItem` i
           LEFT JOIN (SELECT b.item_code, SUM(b.actual_qty) qty FROM `tabBin` b
                      JOIN `tabWarehouse` w ON w.name=b.warehouse AND w.company=%s
                      GROUP BY b.item_code) b ON b.item_code = i.name
           WHERE i.disabled=0 AND (i.name LIKE %s OR i.item_name LIKE %s OR i.custom_sku LIKE %s)
           ORDER BY (IFNULL(b.qty,0) > 0) DESC, i.modified DESC
           LIMIT %s""", (SALES, like, like, like, int(limit)), as_dict=True)
    return rows


@frappe.whitelist()
def true_cost(item_code=None):
    """The product's TRUE unit cost in MAD, anchored on Maslak's actual supplier
    invoices (TRY) converted at the correct FX. Product cost ONLY — inbound landed
    freight/customs is added separately via the Landed Cockpit. Returns the cost,
    the basis, and the source ('maslak_pi' | 'morocco_pr' | 'orphan')."""
    assert_portal_access()
    if not item_code:
        frappe.throw("item_code required")
    cache = {}
    # 1) preferred anchor — Maslak purchase INVOICES (actual bill), most recent
    pi = frappe.db.sql(
        """SELECT pii.base_rate rate_try, pi.posting_date dt, pii.qty
           FROM `tabPurchase Invoice Item` pii JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
           WHERE pi.company=%s AND pi.docstatus=1 AND pii.item_code=%s AND pii.qty>0
           ORDER BY pi.posting_date DESC""", (SOURCING, item_code), as_dict=True)
    if pi:
        q = v = 0.0
        for r in pi:
            if q >= _BASIS_QTY:
                break
            mad = _to_mad(r.rate_try, "TRY", r.dt, cache)
            q += flt(r.qty); v += mad * flt(r.qty)
        # require a POSITIVE converted value — q>0 with v==0 means every line failed
        # to convert (no FX rate for its currency); don't report that as a 0 cost.
        if q > 0 and v > 0:
            return {"item_code": item_code, "cost_mad": round(v / q, 2),
                    "source": "maslak_pi", "basis_qty": round(q),
                    "note": "Maslak supplier invoice (TRY) @ correct FX — product cost only"}
    # 1b) LOCAL supplier invoices (MAD) — domestic products' truth: no FX, no landed
    lpi = frappe.db.sql(
        """SELECT pii.base_rate rate_mad, pi.posting_date dt, pii.qty
           FROM `tabPurchase Invoice Item` pii
           JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
           JOIN `tabSupplier` s ON s.name=pi.supplier
           WHERE pi.company=%s AND pi.docstatus=1 AND pii.item_code=%s AND pii.qty>0
             AND IFNULL(s.supplier_group,'') IN ('Morocco Local Suppliers', 'Local')
           ORDER BY pi.posting_date DESC""", (SALES, item_code), as_dict=True)
    if lpi:
        q = v = 0.0
        for r in lpi:
            if q >= _BASIS_QTY:
                break
            q += flt(r.qty); v += flt(r.rate_mad) * flt(r.qty)
        if q > 0 and v > 0:
            return {"item_code": item_code, "cost_mad": round(v / q, 2),
                    "source": "local_pi", "basis_qty": round(q),
                    "note": "Local supplier invoice (MAD) — domestic product, no landed layer"}
    # 2) fallback — Morocco direct purchase receipts, FX-corrected
    mo = frappe.db.sql(
        """SELECT pri.rate rate_fc, pr.currency cur, pr.posting_date dt, pri.qty
           FROM `tabPurchase Receipt Item` pri JOIN `tabPurchase Receipt` pr ON pr.name=pri.parent
           WHERE pr.company=%s AND pr.docstatus=1 AND pri.item_code=%s AND pri.qty>0
           ORDER BY pr.posting_date DESC""", (SALES, item_code), as_dict=True)
    if mo:
        q = v = 0.0
        for r in mo:
            if q >= _BASIS_QTY:
                break
            mad = _to_mad(r.rate_fc, r.cur, r.dt, cache)
            q += flt(r.qty); v += mad * flt(r.qty)
        if q > 0 and v > 0:
            return {"item_code": item_code, "cost_mad": round(v / q, 2),
                    "source": "morocco_pr", "basis_qty": round(q),
                    "note": "Morocco direct receipt, FX-corrected — no Maslak invoice"}
        if q > 0:  # had receipts but no line could be FX-converted
            return {"item_code": item_code, "cost_mad": None, "source": "fx_unavailable",
                    "basis_qty": round(q),
                    "note": "Purchase docs exist but their currency has no usable FX rate — needs a rate"}
    # 3) FAMILY INHERITANCE — a variant whose own code never hit a purchase
    # document inherits the model's evidence (invoice on a sibling size/colour
    # or on the template). Same source ladder, scoped to the family.
    template, members = _family_members(item_code)
    if members:
        fam = tuple(members)
        for sql, params, is_try, lbl in (
            ("""SELECT pii.item_code ic, pii.base_rate rate, 'TRY' cur, pi.posting_date dt, pii.qty
                FROM `tabPurchase Invoice Item` pii JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
                WHERE pi.company=%s AND pi.docstatus=1 AND pii.item_code IN %s AND pii.qty>0
                ORDER BY pi.posting_date DESC""", (SOURCING, fam), True, "Maslak invoice"),
            ("""SELECT pii.item_code ic, pii.base_rate rate, 'MAD' cur, pi.posting_date dt, pii.qty
                FROM `tabPurchase Invoice Item` pii
                JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
                JOIN `tabSupplier` sp ON sp.name=pi.supplier
                WHERE pi.company=%s AND pi.docstatus=1 AND pii.item_code IN %s AND pii.qty>0
                  AND IFNULL(sp.supplier_group,'') IN ('Morocco Local Suppliers', 'Local')
                ORDER BY pi.posting_date DESC""", (SALES, fam), False, "local invoice"),
            ("""SELECT pri.item_code ic, pri.rate, pr.currency cur, pr.posting_date dt, pri.qty
                FROM `tabPurchase Receipt Item` pri JOIN `tabPurchase Receipt` pr ON pr.name=pri.parent
                WHERE pr.company=%s AND pr.docstatus=1 AND pri.item_code IN %s AND pri.qty>0
                ORDER BY pr.posting_date DESC""", (SALES, fam), False, "Morocco receipt"),
        ):
            rows = frappe.db.sql(sql, params, as_dict=True)
            if not rows:
                continue
            q = v = 0.0
            ev_item = rows[0].ic
            for r in rows:
                if q >= _BASIS_QTY:
                    break
                cur = "TRY" if is_try else r.cur
                mad = _to_mad(r.rate, cur, r.dt, cache)
                q += flt(r.qty); v += mad * flt(r.qty)
            if q > 0 and v > 0:
                ev_sku = frappe.db.get_value("Item", ev_item, "custom_sku") or ev_item
                return {"item_code": item_code, "cost_mad": round(v / q, 2),
                        "source": "family_pi", "basis_qty": round(q),
                        "evidence_item": ev_item,
                        "note": f"Family evidence — {lbl} on {ev_sku} (same model, one price across variants)"}
    # 3) orphan — no cost source anywhere
    return {"item_code": item_code, "cost_mad": None, "source": "orphan", "basis_qty": 0,
            "note": "No Maslak invoice and no Morocco receipt — needs estimated/manual cost"}


# ── Bulk true-cost engine (Phase 2) — computes the whole catalogue at once ──

def _fx_series():
    """Pre-load USD→X rate history so per-item conversion needs no extra queries.
    Returns {currency: [(date_str, usd_to_ccy), …] sorted ascending}."""
    rows = frappe.db.sql(
        """SELECT to_currency cur, date, exchange_rate rate FROM `tabCurrency Exchange`
           WHERE from_currency='USD' ORDER BY date""", as_dict=True)
    s = {}
    for r in rows:
        s.setdefault(r.cur, []).append((str(r.date), flt(r.rate)))
    return s


def _asof(series, cur, date):
    """USD→cur at/just-before `date` (fallback: earliest)."""
    lst = series.get(cur)
    if not lst:
        return 0.0
    val = None
    for d, rate in lst:
        if d <= date:
            val = rate
        else:
            break
    return flt(val if val is not None else lst[0][1])


def _to_mad_fast(rate_fc, currency, date, fx):
    """Same conversion as _to_mad but off the pre-loaded FX series (no queries)."""
    if currency == "MAD":
        return flt(rate_fc)
    date = str(date or frappe.utils.nowdate())[:10]
    um = _asof(fx, "MAD", date)
    if currency == "USD":
        return flt(rate_fc) * um
    uc = _asof(fx, currency, date)
    return flt(rate_fc) * um / uc if (um > 0 and uc > 0) else 0.0


def _family_members(item_code):
    """For an ERPNext variant: (template, [other member codes incl. the
    template]) — the model's whole family. None for non-variants. The purchase
    invoice usually carries ONE code per model while stock is per size/colour,
    and the model's price is the same across variants — so family evidence is
    valid evidence."""
    t = frappe.db.get_value("Item", item_code, "variant_of")
    if not t:
        return None, []
    sibs = [r[0] for r in frappe.db.sql(
        "SELECT name FROM `tabItem` WHERE variant_of=%s AND name!=%s", (t, item_code))]
    return t, sibs + [t]


def _true_cost_bulk(item_codes, fx):
    """True MAD cost for many items at once. Maslak PI first, then Morocco PR.
    Returns {item_code: {"cost_mad", "source", "basis_qty"}}."""
    if not item_codes:
        return {}
    codes = tuple(item_codes)
    out = {}

    def _agg(rows, is_try, source):
        by = {}
        for r in rows:
            by.setdefault(r.item_code, []).append(r)
        for item, lines in by.items():
            if item in out:
                continue
            q = v = 0.0
            for r in lines:              # already ordered newest-first
                if q >= _BASIS_QTY:
                    break
                cur = "TRY" if is_try else r.cur
                m = _to_mad_fast(r.rate, cur, r.dt, fx)
                q += flt(r.qty); v += m * flt(r.qty)
            if q > 0 and v > 0:
                out[item] = {"cost_mad": round(v / q, 2), "source": source, "basis_qty": round(q)}

    pi = frappe.db.sql(
        """SELECT pii.item_code, pii.base_rate rate, pi.posting_date dt, pii.qty
           FROM `tabPurchase Invoice Item` pii JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
           WHERE pi.company=%s AND pi.docstatus=1 AND pii.item_code IN %s AND pii.qty>0
           ORDER BY pi.posting_date DESC""", (SOURCING, codes), as_dict=True)
    _agg(pi, True, "maslak_pi")

    # LOCAL products (bought inside Morocco): the truth is the local supplier's
    # PURCHASE INVOICE in MAD — no FX, no landed. Fix = match the receipt to
    # the invoice value.
    missing = [c for c in item_codes if c not in out]
    if missing:
        lpi = frappe.db.sql(
            """SELECT pii.item_code, pii.base_rate rate, 'MAD' cur, pi.posting_date dt, pii.qty
               FROM `tabPurchase Invoice Item` pii
               JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
               JOIN `tabSupplier` s ON s.name=pi.supplier
               WHERE pi.company=%s AND pi.docstatus=1 AND pii.item_code IN %s AND pii.qty>0
                 AND IFNULL(s.supplier_group,'') IN ('Morocco Local Suppliers', 'Local')
               ORDER BY pi.posting_date DESC""", (SALES, tuple(missing)), as_dict=True)
        _agg(lpi, False, "local_pi")

    missing = [c for c in item_codes if c not in out]
    if missing:
        pr = frappe.db.sql(
            """SELECT pri.item_code, pri.rate, pr.currency cur, pr.posting_date dt, pri.qty
               FROM `tabPurchase Receipt Item` pri JOIN `tabPurchase Receipt` pr ON pr.name=pri.parent
               WHERE pr.company=%s AND pr.docstatus=1 AND pri.item_code IN %s AND pri.qty>0
               ORDER BY pr.posting_date DESC""", (SALES, tuple(missing)), as_dict=True)
        _agg(pr, False, "morocco_pr")

    # ── FAMILY INHERITANCE — variants whose own code never hit a purchase
    # document inherit the model's evidence (the invoice carries ONE code per
    # model; the price is the same across sizes/colours). Pooled per template,
    # same source ladder, newest-first. ~60% of the "unpriced" catalogue.
    missing = [c for c in item_codes if c not in out]
    if missing:
        vmap = dict(frappe.db.sql(
            """SELECT name, variant_of FROM `tabItem`
               WHERE name IN %s AND IFNULL(variant_of,'') != ''""", (tuple(missing),)))
        if vmap:
            templates = tuple(set(vmap.values()))
            fam_of = {t: t for t in templates}
            for n, t in frappe.db.sql(
                    "SELECT name, variant_of FROM `tabItem` WHERE variant_of IN %s", (templates,)):
                fam_of[n] = t
            member_codes = tuple(fam_of.keys())
            fam_out = {}

            def _fam_agg(rows, is_try):
                by = {}
                for r in rows:
                    t = fam_of.get(r.item_code)
                    if t:
                        by.setdefault(t, []).append(r)
                for t, lines in by.items():
                    if t in fam_out:
                        continue
                    q = v = 0.0
                    ev_item = lines[0].item_code
                    for r in lines:
                        if q >= _BASIS_QTY:
                            break
                        cur = "TRY" if is_try else r.cur
                        m = _to_mad_fast(r.rate, cur, r.dt, fx)
                        q += flt(r.qty); v += m * flt(r.qty)
                    if q > 0 and v > 0:
                        fam_out[t] = {"cost_mad": round(v / q, 2), "source": "family_pi",
                                      "basis_qty": round(q), "evidence_item": ev_item}

            _fam_agg(frappe.db.sql(
                """SELECT pii.item_code, pii.base_rate rate, 'TRY' cur, pi.posting_date dt, pii.qty
                   FROM `tabPurchase Invoice Item` pii JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
                   WHERE pi.company=%s AND pi.docstatus=1 AND pii.item_code IN %s AND pii.qty>0
                   ORDER BY pi.posting_date DESC""", (SOURCING, member_codes), as_dict=True), True)
            _fam_agg(frappe.db.sql(
                """SELECT pii.item_code, pii.base_rate rate, 'MAD' cur, pi.posting_date dt, pii.qty
                   FROM `tabPurchase Invoice Item` pii
                   JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
                   JOIN `tabSupplier` sp ON sp.name=pi.supplier
                   WHERE pi.company=%s AND pi.docstatus=1 AND pii.item_code IN %s AND pii.qty>0
                     AND IFNULL(sp.supplier_group,'') IN ('Morocco Local Suppliers', 'Local')
                   ORDER BY pi.posting_date DESC""", (SALES, member_codes), as_dict=True), False)
            _fam_agg(frappe.db.sql(
                """SELECT pri.item_code, pri.rate, pr.currency cur, pr.posting_date dt, pri.qty
                   FROM `tabPurchase Receipt Item` pri JOIN `tabPurchase Receipt` pr ON pr.name=pri.parent
                   WHERE pr.company=%s AND pr.docstatus=1 AND pri.item_code IN %s AND pri.qty>0
                   ORDER BY pr.posting_date DESC""", (SALES, member_codes), as_dict=True), False)

            for c in missing:
                f = fam_out.get(vmap.get(c))
                if f and c not in out:
                    out[c] = dict(f)
    return out


def _item_procurement(item_codes):
    """Per item → its procurement footprint: primary (most-recent) supplier, and
    the set of (supplier, month) pairs it was purchased in — from Maslak invoices
    AND Morocco receipts. Powers the supplier / month audit filters."""
    if not item_codes:
        return {}
    codes = tuple(item_codes)
    # rank 0 = Maslak invoice (the real manufacturer) so it wins the "primary"
    # supplier over rank 1 = Morocco receipt (often the "Maslak LTD" intercompany
    # transfer, which is not a useful supplier name for the audit).
    rows = frappe.db.sql(
        """SELECT item_code, supplier, mo FROM (
             SELECT pii.item_code, pi.supplier, DATE_FORMAT(pi.posting_date,'%%Y-%%m') mo, pi.posting_date dt, 0 rk
             FROM `tabPurchase Invoice Item` pii JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
             WHERE pi.company=%s AND pi.docstatus=1 AND pii.item_code IN %s
             UNION ALL
             SELECT pri.item_code, pr.supplier, DATE_FORMAT(pr.posting_date,'%%Y-%%m') mo, pr.posting_date dt, 1 rk
             FROM `tabPurchase Receipt Item` pri JOIN `tabPurchase Receipt` pr ON pr.name=pri.parent
             WHERE pr.company=%s AND pr.docstatus=1 AND pri.item_code IN %s
           ) u ORDER BY rk, dt DESC""", (SOURCING, codes, SALES, codes), as_dict=True)
    out = {}
    for r in rows:
        d = out.setdefault(r.item_code, {"supplier": r.supplier, "pairs": set(), "months": set()})
        d["pairs"].add((r.supplier, r.mo))
        d["months"].add(r.mo)
    return out


@frappe.whitelist()
def cost_filters(company=None):
    """Distinct suppliers (with item counts) and months for the audit filters —
    scoped to items currently in Morocco stock."""
    assert_portal_access()
    stocked = frappe.db.sql(
        """SELECT DISTINCT b.item_code FROM `tabBin` b JOIN `tabWarehouse` w ON w.name=b.warehouse
           WHERE w.company=%s AND b.actual_qty>0""", (SALES,), pluck=True)
    proc = _item_procurement(stocked)
    sup_count, months = {}, set()
    for it, d in proc.items():
        months |= d["months"]
        for s in {p[0] for p in d["pairs"]}:
            sup_count[s] = sup_count.get(s, 0) + 1
    suppliers = sorted(({"supplier": s, "items": n} for s, n in sup_count.items()),
                       key=lambda x: -x["items"])
    return {"suppliers": suppliers, "months": sorted(months, reverse=True)}


def _landed_map(item_codes):
    """{item: landed/unit} from the FROZEN basis — {} when not frozen. v3:
    each item's weighted share of its import receipts' ACTUAL freight costs
    (bill-by-bill allocations snapshotted per PR at freeze time). Keeps every
    catalogue number consistent with the FULL rate the fix applies."""
    from accounting_portal.api.landed_prep import _landed_units_bulk
    return _landed_units_bulk(list(item_codes)) if item_codes else {}


@frappe.whitelist()
def cost_overview(company=None):
    """Catalogue-wide KPI: current book value vs true FULL value (product +
    frozen landed) of stock on hand, the total overvaluation, and the source
    breakdown. Uses the same full rate the fix applies, so fixed items read 0."""
    assert_portal_access()
    fx = _fx_series()
    bins = frappe.db.sql(
        """SELECT b.item_code, SUM(b.actual_qty) qty, SUM(b.stock_value) sv
           FROM `tabBin` b JOIN `tabWarehouse` w ON w.name=b.warehouse
           WHERE w.company=%s AND b.actual_qty>0 GROUP BY b.item_code""", (SALES,), as_dict=True)
    tc = _true_cost_bulk([b.item_code for b in bins], fx)
    landed = _landed_map([b.item_code for b in bins])
    n = {"maslak_pi": 0, "local_pi": 0, "morocco_pr": 0, "family_pi": 0, "unpriced": 0}
    cur_val = true_val = over = 0.0
    priced_qty = 0.0
    for b in bins:
        cur_val += flt(b.sv)
        t = tc.get(b.item_code)
        if t:
            n[t["source"]] += 1
            full = flt(t["cost_mad"]) + flt(landed.get(b.item_code))
            tv = full * flt(b.qty)
            true_val += tv; over += flt(b.sv) - tv; priced_qty += flt(b.qty)
        else:
            n["unpriced"] += 1
    return {
        "company": SALES, "items": len(bins),
        "current_value": round(cur_val), "true_value_priced": round(true_val),
        "overvaluation": round(over),
        "maslak_pi": n["maslak_pi"], "local_pi": n["local_pi"],
        "morocco_pr": n["morocco_pr"], "family_pi": n["family_pi"], "unpriced": n["unpriced"],
    }


def _fixed_items():
    """{item: basis_on-stamp-of-its-LATEST-posted-fix} — drives the ✓ column.
    The stamp lets the catalogue detect fixes made under a basis that was later
    unfrozen/refrozen (stale ✓): compare against the current basis' `on`."""
    rows = frappe.get_all(
        "Accounting Portal Action",
        filters={"action_type": "Revalue inventory (bulk)", "status": "Posted",
                 "reference_doctype": "Item"},
        fields=["reference_name", "payload"], order_by="posted_on asc")
    out = {}
    for r in rows:
        stamp, rate = None, None
        try:
            pl = frappe.parse_json(r.payload or "{}") or {}
            stamp = pl.get("basis_on")
            rws = pl.get("rows") or []
            if rws:
                rate = flt(rws[0].get("rate"))
        except Exception:
            pass
        # later rows overwrite → latest fix wins; rate = the APPLIED full rate,
        # the single source of truth the measurements must compare against
        out[r.reference_name] = {"stamp": stamp, "rate": rate}
    return out


def _fix_is_current(stamp, basis_on):
    """A fix counts as current if it carries no stamp (legacy) or its stamp
    matches the currently frozen basis."""
    return stamp is None or not basis_on or stamp == basis_on


@frappe.whitelist()
def cost_table(company=None, start=0, page_size=50, source=None, search=None,
               supplier=None, month=None, fix_status=None):
    """The bulk true-cost worklist: every stocked item with its true cost, current
    valuation, distortion, and its supplier — the feed for the valuation
    correction and the SKU-by-SKU audit. Filters: `source`
    (maslak_pi|morocco_pr|unpriced), `supplier`, `month` (YYYY-MM, honours the
    chosen supplier), free-text `search`. Sorted by absolute overvaluation."""
    assert_portal_access()
    fx = _fx_series()
    conds = ["w.company=%(c)s", "b.actual_qty>0"]
    params = {"c": SALES}
    if search:
        conds.append("(b.item_code LIKE %(s)s OR i.item_name LIKE %(s)s OR i.custom_sku LIKE %(s)s)")
        params["s"] = f"%{search}%"
    bins = frappe.db.sql(
        f"""SELECT b.item_code, SUM(b.actual_qty) qty, SUM(b.stock_value) sv,
                   MAX(i.item_name) item_name, MAX(i.custom_sku) sku
            FROM `tabBin` b JOIN `tabWarehouse` w ON w.name=b.warehouse
            JOIN `tabItem` i ON i.name=b.item_code
            WHERE {' AND '.join(conds)} GROUP BY b.item_code""", params, as_dict=True)
    item_codes = [b.item_code for b in bins]
    tc = _true_cost_bulk(item_codes, fx)
    proc = _item_procurement(item_codes)   # supplier + (supplier,month) pairs per item
    fixed = _fixed_items()
    from accounting_portal.api.landed_prep import get_basis
    basis_on = (get_basis() or {}).get("on")
    landed = _landed_map(item_codes)
    rows = []
    for b in bins:
        # supplier / month audit filter
        if supplier or month:
            d = proc.get(b.item_code)
            pairs = d["pairs"] if d else set()
            if supplier and month:
                if (supplier, month) not in pairs:
                    continue
            elif supplier:
                if supplier not in {p[0] for p in pairs}:
                    continue
            elif month:
                if month not in {p[1] for p in pairs}:
                    continue
        t = tc.get(b.item_code)
        cur_rate = round(flt(b.sv) / flt(b.qty), 2) if flt(b.qty) else 0
        src = t["source"] if t else "unpriced"
        has_fix = b.item_code in fixed
        is_fixed = has_fix and _fix_is_current(fixed[b.item_code]["stamp"], basis_on)
        applied = flt(fixed[b.item_code]["rate"]) if has_fix else 0
        # FULL cost (product + frozen landed) — the same rate the fix applies,
        # so a fixed item reads ~0 overvaluation instead of a phantom negative
        cost = round(flt(t["cost_mad"]) + flt(landed.get(b.item_code)), 2) if t else None
        # a FIXED item is measured against what was actually APPLIED — comparing
        # it to the engine benchmark manufactured false "repolluted" flags
        ref = applied if (is_fixed and applied > 0) else cost
        over = round((flt(b.sv) - ref * flt(b.qty))) if ref is not None else None
        dev = round((cur_rate - ref) / ref * 100, 1) if (ref and ref > 0) else None
        rows.append({"item_code": b.item_code, "sku": b.sku, "item_name": b.item_name,
                     "qty": round(flt(b.qty)), "current_rate": cur_rate, "true_cost": cost,
                     "source": src, "overvaluation": over, "dev_pct": dev,
                     "supplier": (proc.get(b.item_code) or {}).get("supplier"),
                     "fixed": is_fixed,
                     # fixed under a basis that was later refrozen — needs a re-fix
                     "stale_fix": bool(has_fix and not is_fixed),
                     # a fixed item drifting again = a NEW bad inbound — surface it
                     "repolluted": bool(is_fixed and dev is not None and abs(dev) > 15)})
    if source in ("maslak_pi", "local_pi", "morocco_pr", "family_pi", "unpriced"):
        rows = [r for r in rows if r["source"] == source]
    if fix_status == "fixed":
        rows = [r for r in rows if r["fixed"]]
    elif fix_status == "pending":
        rows = [r for r in rows if not r["fixed"]]
    rows.sort(key=lambda r: -abs(r["overvaluation"] or 0))
    total = len(rows)
    start, page_size = int(start or 0), min(int(page_size or 50), 500)
    return {"rows": rows[start:start + page_size], "total": total}


@frappe.whitelist()
def control_tower(company=None):
    """One call → the live status of the 5-step cost-correction process, so the
    Cost Trace screen renders as a guided stepper for the human team:
      ① secure the source (FX guard)   ② freeze the landed basis
      ③ the catalogue crawl (progress) ④ monthly true-ups   ⑤ closings."""
    assert_portal_access()
    from accounting_portal.api.fx_guard import _enabled as _fx_on, _tolerance as _fx_tol
    from accounting_portal.api.landed_prep import shipment_review

    # ② shipment freight progress (the team's daily work) + the basis state
    # (freeze now gates ONLY the monthly true-ups, not the item fixes)
    sr = shipment_review()
    basis = sr["frozen"]
    freight = {"costed": sum(1 for r in sr["receipts"] if r["source"] in ("bills", "rate")),
               "total": len(sr["receipts"]),
               "unallocated_bills": sr["recon"]["unallocated_count"]}

    # ③ crawl progress: fixed vs total, and the overvaluation still uncorrected
    fx = _fx_series()
    bins = frappe.db.sql(
        """SELECT b.item_code, SUM(b.actual_qty) qty, SUM(b.stock_value) sv
           FROM `tabBin` b JOIN `tabWarehouse` w ON w.name=b.warehouse
           WHERE w.company=%s AND b.actual_qty>0 GROUP BY b.item_code""", (SALES,), as_dict=True)
    tc = _true_cost_bulk([b.item_code for b in bins], fx)
    fixed = _fixed_items()
    basis_on = (basis or {}).get("on")
    landed = _landed_map([b.item_code for b in bins])
    total_over = remaining_over = 0.0
    n_fixed = 0
    for b in bins:
        fx = fixed.get(b.item_code)
        is_fixed = bool(fx) and _fix_is_current(fx["stamp"], basis_on)
        t = tc.get(b.item_code)
        if not t:
            # manually-fixed orphans (no purchase docs) still count as done —
            # otherwise the crawl can never reach 100% while orphans exist
            if is_fixed:
                n_fixed += 1
            continue
        full = (flt(fx["rate"]) if (is_fixed and fx and flt(fx["rate"]) > 0)
                else flt(t["cost_mad"]) + flt(landed.get(b.item_code)))
        over = flt(b.sv) - full * flt(b.qty)
        total_over += over
        if is_fixed:
            n_fixed += 1
        else:
            remaining_over += over

    # ④ true-ups posted (current-year months)
    from accounting_portal.api.cogs_trueup import TRUEUP_ACTION, _posted_trueups
    today = frappe.utils.nowdate()
    cur_year = int(today[:4])
    posted_months = sorted(_posted_trueups(SALES, cur_year, basis_on=basis_on).keys())
    closable_months = max(int(today[5:7]) - 1, 0)

    # ⑤ 2025 close: the dummy-customer residual is the headline signal
    dummy_bal = flt(frappe.db.sql(
        """SELECT SUM(debit-credit) FROM `tabGL Entry`
           WHERE company=%s AND account LIKE '120.01%%' AND party=%s AND is_cancelled=0""",
        (SALES, "Justyol Morocco Sales 2025"))[0][0] or 0)

    return {
        "guard": {"enabled": _fx_on(), "tolerance": _fx_tol()},
        "basis": basis,
        "freight": freight,
        "crawl": {"fixed": n_fixed, "total": len(bins),
                  "total_over": round(total_over), "remaining_over": round(remaining_over)},
        "trueup": {"posted_months": posted_months, "closable_months": closable_months,
                   "basis_frozen": bool(basis)},
        "close2025": {"dummy_balance": round(dummy_bal),
                      "done": abs(dummy_bal) < 100,
                      "plan_doc": "docs/CLOSE_2025_PLAN.md"},
    }


def _current_valuation(item_code):
    """Weighted-average current Morocco valuation across all its bins."""
    row = frappe.db.sql(
        """SELECT SUM(b.stock_value) sv, SUM(b.actual_qty) q
           FROM `tabBin` b JOIN `tabWarehouse` w ON w.name=b.warehouse
           WHERE w.company=%s AND b.item_code=%s AND b.actual_qty>0""",
        (SALES, item_code), as_dict=True)
    r = row[0] if row else None
    if r and flt(r.q) > 0:
        return round(flt(r.sv) / flt(r.q), 2), round(flt(r.q))
    return None, 0


@frappe.whitelist()
def trace_item(item_code=None):
    """The full cross-company cost ladder for a product, with per-hop unit price
    (doc currency + MAD-corrected) and a divergence flag at each break point."""
    assert_portal_access()
    if not item_code:
        frappe.throw("item_code required")
    meta = frappe.db.get_value("Item", item_code,
                               ["item_name", "custom_sku", "weight_per_unit", "stock_uom"], as_dict=True) or {}
    cache = {}
    ladder = []

    def add(stage, company, doctype, name, dt, qty, rate, cur):
        ladder.append({
            "stage": stage, "company": company, "doctype": doctype, "name": name,
            "date": str(dt or ""), "qty": round(flt(qty)), "rate": round(flt(rate), 2),
            "currency": cur, "rate_mad": round(_to_mad(rate, cur, dt, cache), 2),
        })

    # ── Maslak (source): PO → PR → PI ──
    for stage, dt_field, tbl, itbl in [
        ("source_po", "transaction_date", "Purchase Order", "Purchase Order Item"),
        ("source_pr", "posting_date", "Purchase Receipt", "Purchase Receipt Item"),
        ("source_pi", "posting_date", "Purchase Invoice", "Purchase Invoice Item")]:
        rows = frappe.db.sql(
            f"""SELECT it.parent nm, p.{dt_field} dt, it.qty, it.rate, p.currency cur
                FROM `tab{itbl}` it JOIN `tab{tbl}` p ON p.name=it.parent
                WHERE p.company=%s AND p.docstatus=1 AND it.item_code=%s AND it.qty>0
                ORDER BY p.{dt_field} DESC LIMIT 1""", (SOURCING, item_code), as_dict=True)
        if rows:
            r = rows[0]
            add(stage, SOURCING, tbl, r.nm, r.dt, r.qty, r.rate, r.cur)

    # ── the paper intercompany transfer (Maslak sells to Morocco) ──
    tr = frappe.db.sql(
        """SELECT si.name nm, si.posting_date dt, sii.qty, sii.rate, si.currency cur
           FROM `tabSales Invoice Item` sii JOIN `tabSales Invoice` si ON si.name=sii.parent
           WHERE si.company=%s AND si.docstatus=1 AND si.customer=%s AND sii.item_code=%s AND sii.qty>0
           ORDER BY si.posting_date DESC LIMIT 1""", (SOURCING, TRANSFER_CUSTOMER, item_code), as_dict=True)
    if tr:
        r = tr[0]
        add("transfer_paper", SOURCING, "Sales Invoice", r.nm, r.dt, r.qty, r.rate, r.cur)

    # ── Morocco (dest): PR (where the FX distortion typically enters) ──
    mo = frappe.db.sql(
        """SELECT pr.name nm, pr.posting_date dt, pri.qty, pri.rate, pr.currency cur, pr.conversion_rate cr
           FROM `tabPurchase Receipt Item` pri JOIN `tabPurchase Receipt` pr ON pr.name=pri.parent
           WHERE pr.company=%s AND pr.docstatus=1 AND pri.item_code=%s AND pri.qty>0
           ORDER BY pr.posting_date DESC LIMIT 1""", (SALES, item_code), as_dict=True)
    if mo:
        r = mo[0]
        add("dest_pr", SALES, "Purchase Receipt", r.nm, r.dt, r.qty, r.rate, r.cur)
        ladder[-1]["conversion_rate"] = round(flt(r.cr), 3)

    # ── divergence flags: compare each hop's MAD unit rate to the true cost ──
    tc = true_cost(item_code)
    truth = flt(tc.get("cost_mad")) if tc.get("cost_mad") is not None else None
    for row in ladder:
        if truth and truth > 0 and row.get("rate_mad"):
            dev = (row["rate_mad"] - truth) / truth
            row["dev_pct"] = round(dev * 100, 1)
            row["flag"] = ("inflated" if dev > 0.15 else "low" if dev < -0.15 else "ok")
        else:
            row["dev_pct"], row["flag"] = None, "no_basis"

    cur_val, cur_qty = _current_valuation(item_code)
    distortion = None
    if truth and truth > 0 and cur_val is not None:
        distortion = round((cur_val - truth) / truth * 100, 1)

    return {
        "item_code": item_code, "item_name": meta.get("item_name"), "sku": meta.get("custom_sku"),
        "weight_per_unit": flt(meta.get("weight_per_unit")), "uom": meta.get("stock_uom"),
        "true_cost": tc, "current_valuation_mad": cur_val, "current_qty": cur_qty,
        "distortion_pct": distortion, "ladder": ladder,
        "note": "true_cost is PRODUCT cost only; inbound landed (freight/customs via 153.03) is added on top separately",
    }


# ── Bulk apply for LOCAL (domestic) products ────────────────────────────────
# Local items carry no landed layer: their supplier invoice (MAD) IS the full
# cost. That makes them safe to fix in bulk — unlike imports, there is no
# freight completeness to wait for. Weak evidence stays on the manual path.

_LOCAL_MIN_BASIS = 3      # < this many invoiced units → suggestion too weak
_LOCAL_MIN_RATE = 0.5     # sub-0.5 MAD "cost" = broken conversion, never real


def _local_batch_rows():
    """(ready, stats): every local-supplier item in Morocco stock, split into
    the bulk-ready set (solid invoice basis) and counted-out reasons."""
    fx = _fx_series()
    stocked = frappe.db.sql(
        """SELECT b.item_code, SUM(b.actual_qty) qty, SUM(b.stock_value) sv,
                  MAX(IFNULL(i.has_batch_no,0)+IFNULL(i.has_serial_no,0)) trk,
                  MAX(i.item_name) item_name, MAX(i.custom_sku) sku
           FROM `tabBin` b
           JOIN `tabWarehouse` w ON w.name=b.warehouse
           JOIN `tabItem` i ON i.name=b.item_code
           WHERE w.company=%s AND b.actual_qty>0
           GROUP BY b.item_code""", (SALES,), as_dict=True)
    costs = _true_cost_bulk([s.item_code for s in stocked], fx)
    fixed = _fixed_items()
    ready = []
    stats = {"local_total": 0, "already_fixed": 0, "tracked": 0,
             "weak_basis": 0, "bad_rate": 0, "ready": 0}
    for s in stocked:
        t = costs.get(s.item_code)
        if not t or t.get("source") != "local_pi":
            continue
        stats["local_total"] += 1
        if s.item_code in fixed:
            stats["already_fixed"] += 1
            continue
        if s.trk:
            stats["tracked"] += 1
            continue
        rate = flt(t.get("cost_mad"))
        if rate < _LOCAL_MIN_RATE:
            stats["bad_rate"] += 1
            continue
        if flt(t.get("basis_qty")) < _LOCAL_MIN_BASIS:
            stats["weak_basis"] += 1
            continue
        stats["ready"] += 1
        qty = flt(s.qty)
        book_rate = round(flt(s.sv) / qty, 2) if qty else 0
        ready.append({
            "item_code": s.item_code, "sku": s.sku, "item_name": s.item_name,
            "rate": rate, "basis_qty": flt(t.get("basis_qty")),
            "qty": qty, "book_rate": book_rate,
            "delta": round(rate * qty - flt(s.sv), 2),
        })
    # stable order across waves: the fixed-map grows, the sort key doesn't
    ready.sort(key=lambda r: r["item_code"])
    return ready, stats


@frappe.whitelist()
def apply_local_batch(limit=25, dry_run=1, retro=0):
    """Bulk-fix the local catalogue: each ready item gets its own reversible
    Stock Reco via fix_item_cost (full rate = invoice rate, landed 0 by
    nature). One failure never stops the wave — it lands in `skipped`."""
    assert_can_write()
    limit = min(int(limit or 25), 100)
    ready, stats = _local_batch_rows()
    if str(dry_run) in ("1", "true", "True"):
        return {"dry_run": True, "stats": stats, "rows": ready,
                "total_delta": round(sum(r["delta"] for r in ready), 2)}
    from accounting_portal.api.valuation import fix_item_cost
    done, skipped, proposed = [], [], []
    # walk the WHOLE ready list until `limit` successes — a permanently-failing
    # head (e.g. already-at-rate without retro) must not wedge every wave
    for r in ready:
        if len(done) + len(proposed) >= limit:
            break
        try:
            res = fix_item_cost(
                company=SALES, item_code=r["item_code"], rate=r["rate"], full_rate=1,
                retro=retro, retro_product=r["rate"],
                note=(f"Local bulk — supplier invoice {r['rate']} MAD/unit "
                      f"(basis {round(r['basis_qty'])}u), landed 0 (domestic)"))
            # approval gate can return a PROPOSED (unposted) action — never
            # report it as applied or the wave loop retries it forever
            if isinstance(res, dict) and res.get("status") and res["status"] != "Posted":
                proposed.append({"item_code": r["item_code"], "status": res["status"]})
                continue
            done.append({"item_code": r["item_code"], "rate": r["rate"],
                         "voucher": (res or {}).get("voucher_no")})
        except Exception as e:
            skipped.append({"item_code": r["item_code"], "reason": str(e)[:140]})
            continue
    return {"dry_run": False, "posted": done, "skipped": skipped, "proposed": proposed,
            "remaining": max(stats["ready"] - len(done) - len(proposed), 0)}
