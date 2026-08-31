"""The agreed price — one record, read by everything.

This is the OPERATING CYCLE, deliberately separate from `vendor_workbench`.
The workbench is finance's correction tool: it repairs history and retires when
the repair is done. This module is procurement's permanent process: a supplier's
agreed price arrives, is reviewed, is approved, and from then on every consumer
reads it — PO, receipt, invoice, stock valuation, partner commission, site price.
Mixing the two would kill the cycle the day the correction finished.

Storage is two ERPNext price lists per supplier, no invented store:

    VP  - <supplier>   approved. buying=1, wired as Supplier.default_price_list,
                       so ERPNext itself fetches the price onto a PO. This is
                       THE agreed price; nothing else may hold one.
    VPP - <supplier>   pending. buying=0 and wired to nothing, so a submitted
                       price cannot reach a document before somebody approves it.

Approval copies a row from pending to approved with a `valid_from` date and
never edits an existing row — the price history stays readable, the same
doctrine the invoice-era engine follows.

Why the gate matters here: every zero-cost item we have been chasing reached the
storefront without anyone deciding what it cost. `publish_check` is the rule that
makes that impossible — a product may not go live without an approved price.
"""
import json

import frappe
from frappe.utils import add_days, flt, getdate, nowdate

from accounting_portal.api.permissions import assert_can_write, assert_portal_access

SALES = "Justyol Morocco"
VP_PREFIX = "VP - "
VPP_PREFIX = "VPP - "
_HDR_KEY = "ap_price_submissions"        # tiny header index; the rows live in VPP

PRICE_BOUNDS = (0.05, 100000.0)          # sane per-unit range in list currency
DEV_GUARD = 0.50                         # vs the last invoice → needs confirming
STALE_DAYS = 120                         # no update this long → back in the queue


# --------------------------------------------------------------------------
# the two lists
# --------------------------------------------------------------------------

def list_name(supplier, pending=False):
    return ((VPP_PREFIX if pending else VP_PREFIX) + supplier)[:140]


def supplier_currency(supplier):
    return (frappe.db.get_value("Supplier", supplier, "default_currency")
            or frappe.db.get_value("Company", SALES, "default_currency") or "MAD")


def ensure_list(supplier, pending=False):
    """The approved list is wired to the supplier so POs fetch from it. The
    pending list is deliberately buying=0 — a submitted price must not be
    reachable by any document until it is approved."""
    name = list_name(supplier, pending)
    if not frappe.db.exists("Price List", name):
        frappe.get_doc({"doctype": "Price List", "price_list_name": name,
                        "currency": supplier_currency(supplier),
                        "buying": 0 if pending else 1, "enabled": 1}).insert(ignore_permissions=True)
    if not pending:
        frappe.db.set_value("Supplier", supplier, "default_price_list", name)
    return name


def agreed_price(supplier, item_code, on_date=None):
    """THE read. Latest approved price effective on or before `on_date`.
    Every consumer goes through here; none of them keeps its own copy."""
    on_date = on_date or nowdate()
    r = frappe.db.sql(
        """SELECT price_list_rate FROM `tabItem Price`
           WHERE price_list=%s AND item_code=%s
             AND (valid_from IS NULL OR valid_from<=%s)
           ORDER BY IFNULL(valid_from,'1900-01-01') DESC, creation DESC LIMIT 1""",
        (list_name(supplier), item_code, on_date))
    return flt(r[0][0]) if r else 0.0


def agreed_map(on_date=None):
    """Every approved price in one query, keyed (supplier, item).

    The single-row read is fine on a document; the review lists and the daily
    checklist walk thousands of rows, and one query each turns a checklist into
    a page load nobody waits for."""
    on_date = on_date or nowdate()
    rows = frappe.db.sql(
        """SELECT ip.price_list, ip.item_code, ip.price_list_rate, ip.valid_from
           FROM `tabItem Price` ip
           WHERE ip.price_list LIKE %s
             AND (ip.valid_from IS NULL OR ip.valid_from<=%s)
           ORDER BY ip.price_list, ip.item_code,
                    IFNULL(ip.valid_from,'1900-01-01'), ip.creation""",
        (VP_PREFIX + "%", on_date), as_dict=True)
    out = {}
    for r in rows:                      # ordered ascending, so the last row wins
        out[(r.price_list[len(VP_PREFIX):], r.item_code)] = flt(r.price_list_rate)
    return out


def _last_invoice_rate(supplier, item_code):
    """What the vendor actually billed — the benchmark a submission is judged on."""
    r = frappe.db.sql(
        """SELECT pii.base_net_rate FROM `tabPurchase Invoice Item` pii
           JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
           WHERE pi.supplier=%s AND pii.item_code=%s AND pi.docstatus=1
             AND IFNULL(pi.is_return,0)=0 AND pii.qty>0
           ORDER BY pi.posting_date DESC LIMIT 1""", (supplier, item_code))
    return flt(r[0][0]) if r else 0.0


def _last_receipt_rate(supplier, item_code):
    """Fallback benchmark. Eleven local vendors have receipts and no invoice at
    all, so an invoice-only view leaves the team staring at empty rows."""
    r = frappe.db.sql(
        """SELECT pri.base_net_rate FROM `tabPurchase Receipt Item` pri
           JOIN `tabPurchase Receipt` pr ON pr.name=pri.parent
           WHERE pr.supplier=%s AND pri.item_code=%s AND pr.docstatus=1
             AND IFNULL(pr.is_return,0)=0 AND pri.qty>0 AND IFNULL(pri.base_net_rate,0)>0
           ORDER BY pr.posting_date DESC LIMIT 1""", (supplier, item_code))
    return flt(r[0][0]) if r else 0.0


def benchmark(supplier, item_code):
    """(rate, source) — invoice first, then what was actually paid on a receipt."""
    v = _last_invoice_rate(supplier, item_code)
    if v > 0:
        return v, "invoice"
    v = _last_receipt_rate(supplier, item_code)
    return (v, "receipt") if v > 0 else (0.0, "none")


# --------------------------------------------------------------------------
# the ONE writer — no other code may create an approved price row
# --------------------------------------------------------------------------

def write_agreed(supplier, rows, confirm=False, bench_fn=None):
    """The single place an approved price is ever written.

    Both doors call this: procurement approving a submission, and the team
    editing the grid. A second writer is how two "agreed" prices for the same
    item come to exist, which is the whole problem this module removes.

    Append-only: the open row is closed at the day before the new one starts, so
    "what did we agree on 12 June" stays answerable. A same-day correction
    replaces rather than stacks. Backdating behind the latest row is refused —
    it would silently rewrite a period that documents were already priced from.

    `bench_fn(item_code) -> rate in list currency` supplies the comparison the
    deviation guard uses; callers differ (last invoice, or the era engine), the
    guard itself must not.
    """
    ccy = supplier_currency(supplier)
    today = nowdate()
    bench_fn = bench_fn or (lambda ic: benchmark(supplier, ic)[0])
    saved, flagged, invalid = [], [], []
    pl = None
    for r in rows or []:
        ic = (r or {}).get("item_code")
        rate = flt((r or {}).get("rate", (r or {}).get("price")))
        vfrom = str((r or {}).get("valid_from") or today)[:10]
        if not ic or not frappe.db.exists("Item", ic):
            invalid.append({"row": ic, "why": "unknown item"})
            continue
        if not (PRICE_BOUNDS[0] <= rate <= PRICE_BOUNDS[1]):
            invalid.append({"row": ic, "why": f"rate {rate} out of bounds"})
            continue
        b = flt(bench_fn(ic))
        if b > 0 and not confirm and abs(rate - b) / b > DEV_GUARD:
            flagged.append({"item_code": ic, "rate": rate, "benchmark": round(b, 2),
                            "dev_pct": round(100.0 * (rate - b) / b)})
            continue
        pl = pl or ensure_list(supplier)
        latest = frappe.db.sql(
            """SELECT name, valid_from FROM `tabItem Price`
               WHERE price_list=%s AND item_code=%s
               ORDER BY valid_from DESC, creation DESC LIMIT 1""", (pl, ic))
        if latest:
            prev_name, prev_from = latest[0][0], str(latest[0][1] or "")[:10]
            if prev_from and vfrom < prev_from:
                invalid.append({"row": ic, "why": f"backdated ({vfrom} < {prev_from})"})
                continue
            if prev_from == vfrom:
                frappe.db.set_value("Item Price", prev_name, "price_list_rate", rate)
                saved.append(ic)
                continue
            frappe.db.set_value("Item Price", prev_name, "valid_upto", add_days(vfrom, -1))
        frappe.get_doc({"doctype": "Item Price", "price_list": pl, "item_code": ic,
                        "price_list_rate": rate, "currency": ccy, "buying": 1,
                        "supplier": supplier, "valid_from": vfrom}
                       ).insert(ignore_permissions=True)
        saved.append(ic)
    frappe.db.commit()
    return {"saved": saved, "flagged": flagged, "invalid": invalid,
            "price_list": pl or list_name(supplier)}


# --------------------------------------------------------------------------
# submission headers (tiny — the rows themselves live in the pending list)
# --------------------------------------------------------------------------

def _headers():
    try:
        return json.loads(frappe.db.get_default(_HDR_KEY) or "{}") or {}
    except Exception:
        return {}


def _save_headers(h):
    frappe.db.set_default(_HDR_KEY, json.dumps(h))


# --------------------------------------------------------------------------
# ① intake — one document, whichever door it came through
# --------------------------------------------------------------------------

@frappe.whitelist()
def submit_prices(supplier=None, rows=None, source="team"):
    """Both doors land here: a sheet the buyer uploads, and the supplier typing
    in his own portal. Same queue, same review, same approval — two paths that
    each wrote their own prices is exactly how a catalogue drifts."""
    assert_can_write()
    if not supplier:
        frappe.throw("supplier required")
    if isinstance(rows, str):
        rows = json.loads(rows or "[]")
    rows = rows or []
    if source not in ("team", "sheet", "supplier"):
        frappe.throw("source must be team, sheet or supplier")

    pend = ensure_list(supplier, pending=True)
    ccy = supplier_currency(supplier)
    accepted, rejected = 0, []
    for r in rows:
        item = (r or {}).get("item_code")
        rate = flt((r or {}).get("price"))
        if not item or not frappe.db.exists("Item", item):
            rejected.append({"item_code": item, "why": "unknown item"})
            continue
        if not (PRICE_BOUNDS[0] <= rate <= PRICE_BOUNDS[1]):
            rejected.append({"item_code": item, "why": f"out of bounds ({rate})"})
            continue
        frappe.db.sql("DELETE FROM `tabItem Price` WHERE price_list=%s AND item_code=%s",
                      (pend, item))
        frappe.get_doc({"doctype": "Item Price", "price_list": pend, "item_code": item,
                        "price_list_rate": rate, "currency": ccy, "buying": 1,
                        "supplier": supplier,
                        "valid_from": (r or {}).get("valid_from") or nowdate()}
                       ).insert(ignore_permissions=True)
        accepted += 1

    h = _headers()
    h[supplier] = {"source": source, "by": frappe.session.user, "on": nowdate(),
                   "rows": accepted, "status": "pending"}
    _save_headers(h)
    frappe.db.commit()
    return {"supplier": supplier, "accepted": accepted, "rejected": rejected,
            "pending_list": pend}


# --------------------------------------------------------------------------
# ② review — the queue procurement works from
# --------------------------------------------------------------------------

@frappe.whitelist()
def queue():
    """Suppliers with something waiting, worst deviation first — a vendor whose
    prices moved 3x deserves attention before one that moved 2%."""
    assert_portal_access()
    h = _headers()
    out = []
    for sup, hdr in h.items():
        if (hdr or {}).get("status") != "pending":
            continue
        pend = list_name(sup, pending=True)
        if not frappe.db.exists("Price List", pend):
            continue
        rows = frappe.db.sql(
            """SELECT item_code, price_list_rate FROM `tabItem Price` WHERE price_list=%s""",
            (pend,), as_dict=True)
        worst, flagged = 0.0, 0
        # the queue only needs to rank suppliers; the full line-by-line check is
        # review()'s job, so a large submission is sampled rather than walked
        for r in rows[:400]:
            b, _ = benchmark(sup, r.item_code)
            if b > 0:
                dev = abs(flt(r.price_list_rate) - b) / b
                worst = max(worst, dev)
                if dev > DEV_GUARD:
                    flagged += 1
        out.append({"supplier": sup, "rows": len(rows), "flagged": flagged,
                    "worst_dev_pct": round(worst * 100, 1),
                    "source": hdr.get("source"), "by": hdr.get("by"), "on": hdr.get("on")})
    out.sort(key=lambda x: (-x["flagged"], -x["worst_dev_pct"]))
    return {"pending": out, "count": len(out)}


@frappe.whitelist()
def review(supplier=None):
    """Line by line: what is agreed now, what is proposed, and what the vendor
    actually billed. The third column is what stops a plausible-looking price
    from walking in."""
    assert_portal_access()
    if not supplier:
        frappe.throw("supplier required")
    pend = list_name(supplier, pending=True)
    rows = frappe.db.sql(
        """SELECT ip.item_code, ip.price_list_rate rate, ip.valid_from
           FROM `tabItem Price` ip WHERE ip.price_list=%s ORDER BY ip.item_code""",
        (pend,), as_dict=True) if frappe.db.exists("Price List", pend) else []
    out = []
    for r in rows:
        cur = agreed_price(supplier, r.item_code)
        b, bsrc = benchmark(supplier, r.item_code)
        dev = (abs(flt(r.rate) - b) / b * 100) if b > 0 else None
        out.append({
            "item_code": r.item_code,
            "item_name": frappe.db.get_value("Item", r.item_code, "item_name"),
            "proposed": flt(r.rate), "current_agreed": cur,
            "benchmark": b, "benchmark_source": bsrc,
            "dev_pct": round(dev, 1) if dev is not None else None,
            "flagged": bool(dev is not None and dev > DEV_GUARD * 100),
            "valid_from": str(r.valid_from) if r.valid_from else nowdate(),
        })
    hdr = _headers().get(supplier) or {}
    return {"supplier": supplier, "currency": supplier_currency(supplier),
            "items": out, "header": hdr,
            "flagged": sum(1 for x in out if x["flagged"])}


# --------------------------------------------------------------------------
# ③ approve — one row into the approved list, history never edited
# --------------------------------------------------------------------------

@frappe.whitelist()
def approve(supplier=None, item_codes=None, confirm_flagged=0):
    """Copy pending → approved with an effective date. A new price is a NEW row:
    the old one keeps its dates, so 'what did we agree in June' stays answerable.
    Rows past the deviation guard need `confirm_flagged` — the guard the old
    buying lists never had, which is how a 356-billion rate got in."""
    assert_can_write()
    if not supplier:
        frappe.throw("supplier required")
    if isinstance(item_codes, str):
        item_codes = json.loads(item_codes or "[]")
    pend = list_name(supplier, pending=True)

    rows = frappe.db.sql(
        """SELECT item_code, price_list_rate rate, valid_from FROM `tabItem Price`
           WHERE price_list=%s""", (pend,), as_dict=True)
    if item_codes:
        wanted = set(item_codes)
        rows = [r for r in rows if r.item_code in wanted]

    res = write_agreed(supplier, [{"item_code": r.item_code, "rate": flt(r.rate),
                                   "valid_from": r.valid_from} for r in rows],
                       confirm=bool(int(confirm_flagged or 0)))
    done, blocked = res["saved"], res["flagged"] + res["invalid"]
    if done:
        ph = ",".join(["%s"] * len(done))
        frappe.db.sql(f"""DELETE FROM `tabItem Price` WHERE price_list=%s
                          AND item_code IN ({ph})""", tuple([pend] + list(done)))

    left = frappe.db.count("Item Price", {"price_list": pend})
    h = _headers()
    if supplier in h:
        h[supplier]["status"] = "pending" if left else "approved"
        h[supplier]["approved_by"] = frappe.session.user
        h[supplier]["approved_on"] = nowdate()
        _save_headers(h)
    frappe.db.commit()
    return {"supplier": supplier, "approved": len(done), "blocked": blocked,
            "still_pending": left}


@frappe.whitelist()
def reject(supplier=None, item_codes=None, reason=None):
    """Drop pending rows. The approved list is untouched — a rejected price never
    existed as far as any document is concerned."""
    assert_can_write()
    if not supplier:
        frappe.throw("supplier required")
    if isinstance(item_codes, str):
        item_codes = json.loads(item_codes or "[]")
    pend = list_name(supplier, pending=True)
    if item_codes:
        ph = ",".join(["%s"] * len(item_codes))
        frappe.db.sql(f"""DELETE FROM `tabItem Price` WHERE price_list=%s
                          AND item_code IN ({ph})""", tuple([pend] + list(item_codes)))
    else:
        frappe.db.sql("DELETE FROM `tabItem Price` WHERE price_list=%s", (pend,))
    left = frappe.db.count("Item Price", {"price_list": pend})
    h = _headers()
    if supplier in h:
        h[supplier]["status"] = "pending" if left else "rejected"
        h[supplier]["rejected_reason"] = reason or ""
        h[supplier]["rejected_by"] = frappe.session.user
        _save_headers(h)
    frappe.db.commit()
    return {"supplier": supplier, "still_pending": left}


# --------------------------------------------------------------------------
# seeding — so a first-time vendor is a review, not a thousand blank boxes
# --------------------------------------------------------------------------

@frappe.whitelist()
def seed_proposal(supplier=None, only_missing=1):
    """Propose the benchmark as the agreed price for everything that has none.

    Town Team has 1,113 items and no purchase invoice at all: asking the team to
    type 1,113 prices from nothing is how a rollout dies. The receipts already
    carry what was actually paid, so the team reviews a filled grid instead."""
    assert_can_write()
    if not supplier:
        frappe.throw("supplier required")
    items = [r[0] for r in frappe.db.sql(
        """SELECT DISTINCT pri.item_code FROM `tabPurchase Receipt Item` pri
           JOIN `tabPurchase Receipt` pr ON pr.name=pri.parent
           WHERE pr.supplier=%s AND pr.docstatus=1 AND pri.item_code IS NOT NULL
           UNION
           SELECT DISTINCT pii.item_code FROM `tabPurchase Invoice Item` pii
           JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
           WHERE pi.supplier=%s AND pi.docstatus=1 AND pii.item_code IS NOT NULL""",
        (supplier, supplier))]
    rows, skipped = [], {"has_agreed": 0, "no_benchmark": 0}
    for ic in items:
        if int(only_missing or 0) and agreed_price(supplier, ic) > 0:
            skipped["has_agreed"] += 1
            continue
        b, src = benchmark(supplier, ic)
        if not (PRICE_BOUNDS[0] <= b <= PRICE_BOUNDS[1]):
            skipped["no_benchmark"] += 1
            continue
        rows.append({"item_code": ic, "price": b, "from": src})
    return {"supplier": supplier, "items": len(items), "proposed": rows,
            "skipped": skipped}


# --------------------------------------------------------------------------
# ④ the gate — nothing goes live without a price somebody agreed to
# --------------------------------------------------------------------------

@frappe.whitelist()
def publish_check(item_code=None, supplier=None):
    """Called before a product is published for sale. This single rule is what
    would have prevented every zero-cost item in the book: 481 items on the shelf
    at a zero rate, 315 units received at zero in August alone, 274 of Beauty
    Mall's units — all of them reached the storefront with nobody having decided
    what they cost."""
    assert_portal_access()
    if not item_code:
        frappe.throw("item_code required")
    supplier = supplier or frappe.db.get_value("Item", item_code, "default_supplier")
    if not supplier:
        return {"ok": False, "reason": "no supplier attributed to this item",
                "item_code": item_code}
    price = agreed_price(supplier, item_code)
    return {"ok": price > 0, "item_code": item_code, "supplier": supplier,
            "agreed_price": price,
            "reason": "" if price > 0 else "no approved agreed price for this item"}


@frappe.whitelist()
def unpriced_live_items(limit=200):
    """Everything already on sale that never passed the gate — the backlog the
    rule stops growing but does not clear."""
    assert_portal_access()
    rows = frappe.db.sql(
        """SELECT b.item_code, i.item_name, i.default_supplier sup,
                  SUM(b.actual_qty) qty, SUM(b.stock_value) val
           FROM `tabBin` b
           JOIN `tabWarehouse` w ON w.name=b.warehouse
           JOIN `tabItem` i ON i.name=b.item_code
           WHERE w.company=%s AND b.actual_qty>0 AND IFNULL(i.disabled,0)=0
           GROUP BY b.item_code, i.item_name, i.default_supplier
           ORDER BY SUM(b.actual_qty) DESC LIMIT %s""",
        (SALES, int(limit)), as_dict=True)
    amap = agreed_map()
    out = []
    for r in rows:
        if r.sup and amap.get((r.sup, r.item_code), 0) > 0:
            continue
        out.append({"item_code": r.item_code, "item_name": r.item_name,
                    "supplier": r.sup or "", "qty": flt(r.qty),
                    "stock_value": flt(r.val),
                    "zero_rate": flt(r.val) <= 0})
    return {"items": out, "count": len(out),
            "units": sum(x["qty"] for x in out)}


# --------------------------------------------------------------------------
# ⑤ maintenance — the triggers that keep the cycle turning by itself
# --------------------------------------------------------------------------

@frappe.whitelist()
def stale_prices(days=None):
    """A price nobody has confirmed in months is a guess. Suppliers surface here
    so the cycle does not depend on somebody remembering to ask."""
    assert_portal_access()
    days = int(days or STALE_DAYS)
    cutoff = add_days(nowdate(), -days)
    out = []
    for pl in frappe.get_all("Price List", filters={"name": ["like", VP_PREFIX + "%"]},
                             fields=["name"]):
        sup = pl.name[len(VP_PREFIX):]
        last = frappe.db.sql("""SELECT MAX(IFNULL(valid_from, DATE(creation)))
                                FROM `tabItem Price` WHERE price_list=%s""", (pl.name,))[0][0]
        if last and str(last) < cutoff:
            out.append({"supplier": sup, "last_update": str(last),
                        "days": (getdate(nowdate()) - getdate(last)).days,
                        "items": frappe.db.count("Item Price", {"price_list": pl.name})})
    out.sort(key=lambda x: -x["days"])
    return {"stale": out, "count": len(out), "threshold_days": days}


@frappe.whitelist()
def billed_above_agreed(since=None, limit=100):
    """The invoice is still the judge. When a vendor bills above what we agreed,
    procurement should hear about it while the invoice is fresh, not at year end."""
    assert_portal_access()
    since = since or add_days(nowdate(), -90)
    rows = frappe.db.sql(
        """SELECT pi.supplier, pi.name inv, pi.posting_date, pii.item_code,
                  pii.qty, pii.base_net_rate rate
           FROM `tabPurchase Invoice Item` pii
           JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
           WHERE pi.company=%s AND pi.docstatus=1 AND IFNULL(pi.is_return,0)=0
             AND pi.posting_date>=%s AND pii.qty>0
           ORDER BY pi.posting_date DESC LIMIT 2000""",
        (SALES, since), as_dict=True)
    amap = agreed_map()
    out = []
    for r in rows:
        agreed = amap.get((r.supplier, r.item_code), 0.0)
        if agreed > 0 and flt(r.rate) > agreed * 1.001:
            out.append({"supplier": r.supplier, "invoice": r.inv,
                        "date": str(r.posting_date), "item_code": r.item_code,
                        "agreed": agreed, "billed": flt(r.rate),
                        "over_pct": round((flt(r.rate) - agreed) / agreed * 100, 1),
                        "overcharge": round((flt(r.rate) - agreed) * flt(r.qty), 2)})
        if len(out) >= int(limit):
            break
    out.sort(key=lambda x: -x["overcharge"])
    return {"cases": out, "count": len(out),
            "total_overcharge": round(sum(x["overcharge"] for x in out), 2)}


@frappe.whitelist()
def cycle_health():
    """One call for the daily checklist: what the cycle is waiting on today."""
    assert_portal_access()
    q = queue()
    up = unpriced_live_items(limit=500)
    st = stale_prices()
    ba = billed_above_agreed()
    return {
        "pending_submissions": q["count"],
        "flagged_rows": sum(x["flagged"] for x in q["pending"]),
        "unpriced_live": up["count"], "unpriced_units": up["units"],
        "stale_suppliers": st["count"],
        "billed_above_agreed": ba["count"], "overcharge": ba["total_overcharge"],
        "lists_wired": frappe.db.count("Price List", {"name": ["like", VP_PREFIX + "%"]}),
        "suppliers_wired": frappe.db.count("Supplier",
                                           {"default_price_list": ["like", VP_PREFIX + "%"]}),
    }
