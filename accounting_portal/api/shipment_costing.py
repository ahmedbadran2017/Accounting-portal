"""Shipment costing — the true cost of each 2026 import shipment, line by line.

    sea:  (supplier price ₺ + Turkey costs ₺) × FX  +  Morocco costs ÷ shipment kg × item kg
    air:   supplier price ₺ × FX                   +  air tariff (MAD/kg at the date) × item kg

Why a page and not a formula in the ledger (audit 2026-11-16, see the memory
note shipment-cogs-audit-2026-11):
- The supplier price is not on the receipt. Maslak receipts carry the paper
  transfer price (USD); direct TRY receipts are at rate 0 on 495 of 2,290 lines
  and match their own bill on only half. The truth is the supplier's bill:
  Maslak's (or Justyol China's) for transfer receipts, Morocco's for direct ones.
- No TRY→MAD rate exists in the system. A month table lives here (Default
  `ap_fx_try_mad`), with a per-shipment override.
- Morocco's landed costs are not tied to shipments: 1.68M MAD sits on 153.03
  uncapitalised and the rest on 770.07.x. Customs bills carry the customs
  declaration number as bill_no — the natural key — and eight hand-made draft
  Landed Cost Vouchers already pair Jan–Feb receipts with their customs bill;
  both feed the suggestions.

Nothing here posts to the ledger. A shipment is a working record (Shipment
Costing): Draft → Review → Locked, every save logged in Accounting Portal
Action. Applying the cost to stock is a separate, later step.
"""
import json
import statistics

import frappe
from frappe.utils import flt, getdate, add_days, nowdate

from accounting_portal.api import _actions
from accounting_portal.api.permissions import (assert_portal_access, assert_can_write, resolve_companies,
                                               can_manage_users)

DT = "Shipment Costing"
_FROM = "2026-01-01"
_GROUP_COMPANIES = ("Maslak LTD", "Justyol Morocco", "Justyol China", "Justyol Holding")
_SOURCE_COMPANIES = ("Maslak LTD", "Justyol China")
_DOMESTIC_GROUPS = ("Morocco Local Suppliers", "Local")
_FX_KEY = "ap_fx_try_mad"
# TRY→MAD ran 0.19–0.22 through 2026; 0.30 (Neon, June) is a keying error and
# must not feed the month estimate.
_FX_BAND = {"TRY": (0.15, 0.26), "USD": (8.0, 12.0), "EUR": (9.0, 13.0)}
SAVE_ACTION = "Shipment costing"


def _target(company):
    cs = resolve_companies(company)
    if not cs:
        return None
    return company if (company and company in cs) else cs[0]


def _m(v, n=2):
    return flt(v, n)


# ── reference data ───────────────────────────────────────────────────────────

def _import_receipts(target, names=None):
    """2026 receipts from abroad: supplier groups other than the Moroccan local
    ones (the landed pipeline's rule — country is mis-tagged on local sellers)."""
    cond, args = "", {"c": target, "f": _FROM, "dom": _DOMESTIC_GROUPS}
    if names:
        cond = " AND pr.name IN %(n)s"
        args["n"] = tuple(names)
    return frappe.db.sql(f"""
        SELECT pr.name, pr.posting_date, pr.supplier, pr.currency, pr.conversion_rate,
               SUM(i.qty) qty, SUM(i.base_amount) booked,
               SUM(i.qty * IFNULL(it.weight_per_unit, 0)) kg,
               SUM(CASE WHEN IFNULL(it.weight_per_unit, 0) > 0 THEN 0 ELSE 1 END) no_weight
        FROM `tabPurchase Receipt` pr
        JOIN `tabPurchase Receipt Item` i ON i.parent = pr.name
        LEFT JOIN `tabItem` it ON it.name = i.item_code
        LEFT JOIN `tabSupplier` s ON s.name = pr.supplier
        WHERE pr.company = %(c)s AND pr.docstatus = 1 AND pr.is_return = 0 AND pr.posting_date >= %(f)s
          AND IFNULL(s.supplier_group, '') NOT IN %(dom)s {cond}
        GROUP BY pr.name ORDER BY pr.posting_date DESC""", args, as_dict=True)


def _channel_mode(supplier):
    try:
        ch = json.loads(frappe.db.get_default("ap_freight_channels") or "{}")
    except Exception:
        ch = {}
    if supplier in (ch.get("air") or []) or supplier == "Justyol China":
        return "Air"
    return "Sea"


def _fx_table():
    try:
        return json.loads(frappe.db.get_default(_FX_KEY) or "{}")
    except Exception:
        return {}


def _fx_estimate(target, month):
    """Median TRY rate on that month's TRY receipts, inside the sane band."""
    lo, hi = _FX_BAND["TRY"]
    rates = frappe.db.sql_list(
        """SELECT conversion_rate FROM `tabPurchase Receipt` WHERE company=%s AND docstatus=1
           AND currency='TRY' AND posting_date BETWEEN %s AND LAST_DAY(%s) AND conversion_rate BETWEEN %s AND %s""",
        (target, month + "-01", month + "-01", lo, hi))
    return _m(statistics.median(rates), 4) if rates else None


def _fx_for(target, date, override=None):
    if flt(override):
        return flt(override), "override"
    month = str(date)[:7]
    t = _fx_table()
    if flt(t.get(month)):
        return flt(t[month]), "table"
    est = _fx_estimate(target, month)
    return (est, "estimate") if est else (0.0, "missing")


def _air_rates():
    try:
        from accounting_portal.api.landed_prep import get_air_rates
        return get_air_rates()
    except Exception:
        return []


def _air_rate_at(rates, date):
    val = 0.0
    for r in rates:
        if str(r.get("from") or "")[:10] <= str(date)[:10]:
            val = flt(r.get("rate"))
    return val


def _taken(invoice_items, exclude=None):
    """How much of each bill line other shipments already took."""
    if not invoice_items:
        return {}
    rows = frappe.db.sql(
        """SELECT c.invoice_item, SUM(c.amount) FROM `tabShipment Costing Charge` c
           WHERE c.invoice_item IN %(i)s AND c.parent != %(x)s GROUP BY c.invoice_item""",
        {"i": tuple(invoice_items), "x": exclude or ""})
    return {r[0]: flt(r[1]) for r in rows}


# ── the calculation ──────────────────────────────────────────────────────────

def _items(receipts):
    return frappe.db.sql(
        """SELECT i.item_code, COALESCE(MAX(it.item_name), MAX(i.item_name)) item_name, MAX(it.custom_sku) sku, SUM(i.qty) qty, SUM(i.base_amount) booked,
                  MAX(IFNULL(it.weight_per_unit, 0)) weight, MAX(i.rate) pr_rate,
                  MAX(pr.currency) pr_currency, MAX(pr.conversion_rate) pr_cr, MIN(pr.posting_date) d,
                  MAX(pr.supplier) supplier, MAX(it.image) image
           FROM `tabPurchase Receipt Item` i JOIN `tabPurchase Receipt` pr ON pr.name = i.parent
           LEFT JOIN `tabItem` it ON it.name = i.item_code
           WHERE i.parent IN %s GROUP BY i.item_code ORDER BY SUM(i.qty) DESC""",
        (tuple(receipts),), as_dict=True)


def _source_price(it):
    """The supplier's own price for this item, never the receipt's.

    Transfer receipts (Maslak LTD / Justyol China as supplier): the latest bill
    in those companies from a real (non-group) supplier, on or before the
    receipt; direct receipts: Morocco's latest bill from the same supplier.
    Fallback: the receipt rate, flagged. Returns (rate, currency, source, flag)."""
    if it.supplier in _GROUP_COMPANIES:
        r = frappe.db.sql(
            """SELECT pii.rate, pi.currency, pi.name, pi.supplier FROM `tabPurchase Invoice Item` pii
               JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
               WHERE pi.company IN %s AND pi.docstatus=1 AND pi.is_return=0 AND pi.supplier NOT IN %s
                 AND pii.item_code=%s AND pii.rate > 0
               ORDER BY (pi.posting_date <= %s) DESC, pi.posting_date DESC LIMIT 1""",
            (_SOURCE_COMPANIES, _GROUP_COMPANIES, it.item_code, it.d))
    else:
        r = frappe.db.sql(
            """SELECT pii.rate, pi.currency, pi.name, pi.supplier FROM `tabPurchase Invoice Item` pii
               JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
               WHERE pi.company='Justyol Morocco' AND pi.docstatus=1 AND pi.is_return=0 AND pi.supplier=%s
                 AND pii.item_code=%s AND pii.rate > 0
               ORDER BY ABS(DATEDIFF(pi.posting_date, %s)) LIMIT 1""",
            (it.supplier, it.item_code, it.d))
    if r:
        return flt(r[0][0]), r[0][1], f"{r[0][2]} · {r[0][3]}", None
    if flt(it.pr_rate):
        return flt(it.pr_rate), it.pr_currency, "receipt", "from_receipt"
    return 0.0, it.pr_currency, None, "missing"


def _to_mad(rate, ccy, fx_try, pr_ccy, pr_cr, date):
    if ccy in (None, "", "MAD"):
        return rate, None
    if ccy == "TRY":
        return (rate * fx_try, None) if fx_try else (0.0, "fx_missing")
    lo, hi = _FX_BAND.get(ccy, (0, 1e9))
    if pr_ccy == ccy and lo <= flt(pr_cr) <= hi:
        return rate * flt(pr_cr), None
    r = frappe.db.sql("""SELECT exchange_rate FROM `tabCurrency Exchange` WHERE from_currency=%s AND to_currency='MAD'
                         ORDER BY ABS(DATEDIFF(date, %s)) LIMIT 1""", (ccy, date))
    if r and lo <= flt(r[0][0]) <= hi:
        return rate * flt(r[0][0]), None
    return 0.0, "fx_missing"


def _compute(target, s):
    """`s`: dict with receipts, mode, fx_rate, tr_basis, charges[]. Pure read."""
    receipts = [r for r in (s.get("receipts") or []) if r]
    if not receipts:
        return {"items": [], "totals": {}}
    heads = _import_receipts(target, receipts)
    first = min((h.posting_date for h in heads), default=getdate(nowdate()))
    fx, fx_src = _fx_for(target, first, s.get("fx_rate"))
    mode = s.get("mode") or "Sea"
    air = mode == "Air"
    air_rate = _air_rate_at(_air_rates(), first) if air else 0.0
    charges = s.get("charges") or []
    ma_total = sum(flt(c.get("amount")) for c in charges if c.get("side") == "Morocco")
    tr_try = sum(flt(c.get("amount")) for c in charges if c.get("side") == "Turkey")
    tr_mad = tr_try * fx if fx else 0.0

    rows = []
    for it in _items(receipts):
        rate, ccy, src, flag = _source_price(it)
        mad, fxflag = _to_mad(rate, ccy, fx, it.pr_currency, it.pr_cr, first)
        rows.append(dict(item_code=it.item_code, item_name=it.item_name, sku=it.sku or it.item_code, image=it.image, qty=flt(it.qty), weight=flt(it.weight),
                         price=_m(rate, 4), currency=ccy or "MAD", source=src, flag=flag or fxflag,
                         price_mad=mad, booked_unit=flt(it.booked) / flt(it.qty) if flt(it.qty) else 0))
    kg = sum(r["qty"] * r["weight"] for r in rows if r["weight"])
    value = sum(r["qty"] * r["price_mad"] for r in rows)
    basis = s.get("tr_basis") or "Weight"
    ma_per_kg = air_rate if air else (ma_total / kg if kg else 0.0)
    total = 0.0
    for r in rows:
        if basis == "Value":
            tr_u = tr_mad * r["price_mad"] / value if value else 0.0
        else:
            tr_u = tr_mad * r["weight"] / kg if kg and r["weight"] else 0.0
        ma_u = ma_per_kg * r["weight"]
        final = r["price_mad"] + tr_u + ma_u
        r.update(tr_unit=_m(tr_u), after_turkey=_m(r["price_mad"] + tr_u), ma_unit=_m(ma_u), final=_m(final),
                 price_mad=_m(r["price_mad"]), booked_unit=_m(r["booked_unit"]),
                 no_weight=not r["weight"])
        total += final * r["qty"]
    product_try = sum(r["qty"] * r["price"] for r in rows if r["currency"] == "TRY")
    product_mad = sum(r["qty"] * r["price_mad"] for r in rows)
    booked = sum(flt(h.booked) for h in heads)
    issues = {
        "no_weight": sum(1 for r in rows if r["no_weight"]),
        "no_price": sum(1 for r in rows if r["flag"] == "missing"),
        "price_from_receipt": sum(1 for r in rows if r["flag"] == "from_receipt"),
        "fx_missing": (not fx) or any(r["flag"] == "fx_missing" for r in rows),
        "no_morocco_costs": (not air) and not ma_total,
    }
    return {
        "mode": mode, "fx": fx, "fx_source": fx_src, "air_rate": air_rate,
        "receipts": [{"name": h.name, "date": str(h.posting_date), "supplier": h.supplier, "kg": _m(h.kg, 1),
                      "qty": flt(h.qty), "currency": h.currency, "conversion_rate": flt(h.conversion_rate)}
                     for h in heads],
        "items": rows,
        "totals": {"kg": _m(kg, 1), "units": sum(r["qty"] for r in rows), "product_try": _m(product_try),
                   "product_mad": _m(product_mad), "turkey_try": _m(tr_try), "turkey_mad": _m(tr_mad),
                   "after_turkey": _m(product_mad + tr_mad), "morocco": _m(air_rate * kg if air else ma_total),
                   "morocco_per_kg": _m(ma_per_kg), "total": _m(total), "booked": _m(booked),
                   "diff": _m(total - booked)},
        "issues": issues,
        "complete": not any(issues.values()),
    }


def _doc_payload(doc):
    return {
        "name": doc.name, "status": doc.status, "mode": doc.mode, "fx_rate": flt(doc.fx_rate) or None,
        "customs_declaration": doc.customs_declaration or "", "bill_of_lading": doc.bill_of_lading or "",
        "tr_basis": doc.tr_basis or "Weight", "sent_by": doc.sent_by, "locked_by": doc.locked_by,
        "receipts": [r.purchase_receipt for r in doc.receipts],
        "charges": [{"side": c.side, "purchase_invoice": c.purchase_invoice, "invoice_item": c.invoice_item,
                     "source_company": c.source_company, "account": c.account, "description": c.description,
                     "full_amount": flt(c.full_amount), "amount": flt(c.amount), "is_manual": c.is_manual,
                     "attachment": c.attachment} for c in doc.charges],
    }


def _shipment_of(receipt):
    return frappe.db.get_value("Shipment Costing Receipt", {"purchase_receipt": receipt}, "parent")


# ── endpoints: read ──────────────────────────────────────────────────────────

@frappe.whitelist()
def shipments_overview(company=None, mode=None):
    """The column: every 2026 import receipt, grouped into its saved shipment
    or standing alone, with a one-word state, plus the page's headline numbers."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    recs = _import_receipts(target)
    by_doc = {}
    for r in frappe.db.sql("""SELECT r.purchase_receipt, r.parent FROM `tabShipment Costing Receipt` r
                              JOIN `tabShipment Costing` s ON s.name = r.parent WHERE s.company=%s""", (target,)):
        by_doc[r[0]] = r[1]
    docs = {d.name: d for d in frappe.get_all(DT, filters={"company": target},
                                                fields=["name", "mode", "status", "customs_declaration"])}
    charges = {}
    for c in frappe.db.sql("""SELECT parent, side, SUM(amount) FROM `tabShipment Costing Charge`
                              WHERE parent IN %s GROUP BY parent, side""", (tuple(docs) or ("",),)):
        charges.setdefault(c[0], {})[c[1]] = flt(c[2])
    rows, seen = [], set()
    for r in recs:
        key = by_doc.get(r.name) or r.name
        if key in seen:
            continue
        seen.add(key)
        d = docs.get(key)
        group = [x for x in recs if (by_doc.get(x.name) or x.name) == key]
        kg = sum(flt(x.kg) for x in group)
        ch = charges.get(key, {})
        m = (d.mode if d else _channel_mode(r.supplier))
        if mode and m != mode:
            continue
        ma = ch.get("Morocco", 0)
        if m == "Air":
            state = "air"
        elif ma and ch.get("Turkey"):
            state = "complete"
        elif ma:
            state = "partial"
        else:
            state = "no_costs"
        rows.append({
            "key": key, "saved": bool(d), "status": d.status if d else None, "mode": m,
            "customs_declaration": d.customs_declaration if d else None,
            "receipts": [x.name for x in group], "date": str(min(x.posting_date for x in group)),
            "supplier": r.supplier, "kg": _m(kg, 1), "units": sum(flt(x.qty) for x in group),
            "no_weight": sum(int(x.no_weight or 0) for x in group),
            "morocco": _m(ma), "per_kg": _m(ma / kg) if ma and kg else None, "state": state,
        })
    clearing = flt(frappe.db.sql("""SELECT SUM(debit-credit) FROM `tabGL Entry` WHERE company=%s AND is_cancelled=0
                                    AND account LIKE '153.03%%'""", (target,))[0][0])
    return {
        "company": target,
        "kpi": {"receipts": len(recs), "kg": _m(sum(flt(r.kg) for r in recs), 0),
                "units": sum(flt(r.qty) for r in recs), "clearing_153": _m(clearing),
                "complete": sum(1 for x in rows if x["state"] == "complete"), "shipments": len(rows),
                "no_weight_lines": sum(int(r.no_weight or 0) for r in recs)},
        "rows": rows,
    }


@frappe.whitelist()
def get_shipment(company=None, key=None):
    """One shipment: a saved Shipment Costing by name, or a lone receipt by its
    name (not yet saved). Returns the editable payload and its calculation."""
    assert_portal_access()
    target = _target(company)
    if not (target and key):
        return {}
    if frappe.db.exists(DT, key):
        doc = frappe.get_doc(DT, key)
        if doc.company != target:
            frappe.throw("Not permitted", frappe.PermissionError)
        payload = _doc_payload(doc)
    else:
        if _shipment_of(key):
            return get_shipment(company, _shipment_of(key))
        h = _import_receipts(target, [key])
        if not h:
            frappe.throw("Not an import receipt of this company")
        payload = {"name": None, "status": "Draft", "mode": _channel_mode(h[0].supplier), "fx_rate": None,
                   "customs_declaration": "", "bill_of_lading": "", "tr_basis": "Weight",
                   "receipts": [key], "charges": []}
    return {"shipment": payload, "calc": _compute(target, payload), "history": _history(payload.get("name"))}


@frappe.whitelist()
def preview(company=None, shipment=None):
    """Recalculate an unsaved edit — the page calls this as fields change."""
    assert_portal_access()
    target = _target(company)
    s = json.loads(shipment) if isinstance(shipment, str) else (shipment or {})
    return _compute(target, s)


@frappe.whitelist()
def charge_candidates(company=None, shipment=None, side="Morocco"):
    """Bill lines that may belong to this shipment, best first.

    Morocco: inbound lines (153.03, 770.07.x except outbound Cathedis .004 and
    local delivery .008, and the malformed 770.0.7.002) 45 days before to 60
    after the shipment. Turkey: Maslak's 770.07.x export costs 75 days before
    to 10 after (Trendyol .001 and local .008 excluded). Each line shows what
    other shipments already took. Suggested first: customs bill whose number is
    the declaration, or an amount a draft Landed Cost Voucher already put on
    one of these receipts."""
    assert_portal_access()
    target = _target(company)
    s = json.loads(shipment) if isinstance(shipment, str) else (shipment or {})
    receipts = [r for r in (s.get("receipts") or []) if r]
    if not receipts:
        return []
    d0 = min(getdate(x) for x in frappe.db.sql_list(
        "SELECT posting_date FROM `tabPurchase Receipt` WHERE name IN %s", (tuple(receipts),)))
    if side == "Turkey":
        co, lo, hi = "Maslak LTD", add_days(d0, -75), add_days(d0, 10)
        acc = """(pii.expense_account LIKE '770.07%%' AND pii.expense_account NOT LIKE '770.07.001%%'
                  AND pii.expense_account NOT LIKE '770.07.008%%')"""
    else:
        co, lo, hi = target, add_days(d0, -45), add_days(d0, 60)
        acc = """(pii.expense_account LIKE '153.03%%' OR pii.expense_account LIKE '770.0.7%%'
                  OR (pii.expense_account LIKE '770.07%%' AND pii.expense_account NOT LIKE '770.07.004%%'
                      AND pii.expense_account NOT LIKE '770.07.008%%'))"""
    rows = frappe.db.sql(f"""
        SELECT pii.name line, pi.name bill, pi.supplier, pi.posting_date, pi.bill_no, pii.expense_account account,
               LEFT(IFNULL(pii.item_name, pii.description), 60) what, pii.base_amount amount
        FROM `tabPurchase Invoice Item` pii JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
        WHERE pi.company=%(co)s AND pi.docstatus=1 AND pi.is_return=0 AND pi.posting_date BETWEEN %(lo)s AND %(hi)s
          AND {acc} AND pii.base_amount > 0""", {"co": co, "lo": lo, "hi": hi}, as_dict=True)
    taken = _taken([r.line for r in rows], s.get("name"))
    lcv_amounts = set()
    if side == "Morocco":
        for a in frappe.db.sql_list(
                """SELECT ROUND(t.amount) FROM `tabLanded Cost Taxes and Charges` t
                   JOIN `tabLanded Cost Purchase Receipt` r ON r.parent = t.parent
                   JOIN `tabLanded Cost Voucher` l ON l.name = t.parent
                   WHERE l.docstatus < 2 AND r.receipt_document IN %s""", (tuple(receipts),)):
            lcv_amounts.add(flt(a))
    dec = (s.get("customs_declaration") or "").strip()
    out = []
    for r in rows:
        left = flt(r.amount) - taken.get(r.line, 0)
        if left <= 0.5:
            continue
        why = None
        if dec and (r.bill_no or "").strip() == dec:
            why = "declaration"
        elif round(flt(r.amount)) in lcv_amounts:
            why = "draft_lcv"
        out.append({"line": r.line, "bill": r.bill, "supplier": r.supplier, "date": str(r.posting_date),
                    "bill_no": r.bill_no, "account": r.account, "what": r.what, "full": _m(r.amount),
                    "left": _m(left), "taken": _m(taken.get(r.line, 0)), "suggested": why,
                    "days": abs((getdate(r.posting_date) - d0).days), "company": co})
    out.sort(key=lambda x: (0 if x["suggested"] else 1, x["days"]))
    return out[:60]


@frappe.whitelist()
def merge_candidates(company=None, shipment=None):
    """Import receipts within three weeks that are in no other shipment."""
    assert_portal_access()
    target = _target(company)
    s = json.loads(shipment) if isinstance(shipment, str) else (shipment or {})
    mine = set(s.get("receipts") or [])
    if not mine:
        return []
    d0 = min(getdate(x) for x in frappe.db.sql_list(
        "SELECT posting_date FROM `tabPurchase Receipt` WHERE name IN %s", (tuple(mine),)))
    out = []
    for r in _import_receipts(target):
        if r.name in mine or abs((getdate(r.posting_date) - d0).days) > 21:
            continue
        other = _shipment_of(r.name)
        if other and other != s.get("name"):
            continue
        out.append({"name": r.name, "date": str(r.posting_date), "supplier": r.supplier, "kg": _m(r.kg, 1)})
    return out


def _history(name):
    if not name:
        return []
    return [{"who": a.owner, "when": str(a.creation)[:16], "what": a.notes}
            for a in frappe.get_all("Accounting Portal Action",
                                    filters={"reference_doctype": DT, "reference_name": name},
                                    fields=["owner", "creation", "notes"], order_by="creation desc", limit=30)]


@frappe.whitelist()
def fx_table(company=None, year="2026"):
    """Month → TRY→MAD: what was entered, else the receipts' estimate."""
    assert_portal_access()
    target = _target(company)
    t = _fx_table()
    return [{"month": f"{year}-{m:02d}", "rate": flt(t.get(f"{year}-{m:02d}")) or None,
             "estimate": _fx_estimate(target, f"{year}-{m:02d}")} for m in range(1, 13)]


# ── endpoints: write ─────────────────────────────────────────────────────────

def _describe(before, after):
    """One plain line per change, for the shipment's history."""
    out = []
    labels = {"mode": "mode", "fx_rate": "FX", "customs_declaration": "declaration",
              "bill_of_lading": "B/L", "tr_basis": "Turkey basis"}
    for k, lab in labels.items():
        if (before.get(k) or "") != (after.get(k) or ""):
            out.append(f"{lab}: {before.get(k) or '—'} → {after.get(k) or '—'}")
    b, a = set(before.get("receipts") or []), set(after.get("receipts") or [])
    out += [f"+ {r}" for r in sorted(a - b)] + [f"− {r}" for r in sorted(b - a)]
    key = lambda c: c.get("invoice_item") or ("manual:" + (c.get("description") or "") + c.get("side", ""))
    bc = {key(c): c for c in before.get("charges") or []}
    ac = {key(c): c for c in after.get("charges") or []}
    for k, c in ac.items():
        if k not in bc:
            out.append(f"link {c.get('purchase_invoice') or c.get('description') or 'manual'} {c.get('side')} {flt(c.get('amount')):,.2f}")
        elif flt(bc[k].get("amount")) != flt(c.get("amount")):
            out.append(f"{c.get('purchase_invoice') or 'manual'}: {flt(bc[k].get('amount')):,.2f} → {flt(c.get('amount')):,.2f}")
    for k, c in bc.items():
        if k not in ac:
            out.append(f"unlink {c.get('purchase_invoice') or c.get('description') or 'manual'}")
    return "; ".join(out)[:900] or "saved"


@frappe.whitelist()
def save_shipment(company=None, shipment=None):
    """Create or update a shipment while it is a draft. A receipt belongs to one
    shipment; a bill line can be split across shipments but never over-taken."""
    assert_can_write()
    target = _target(company)
    s = json.loads(shipment) if isinstance(shipment, str) else (shipment or {})
    receipts = list(dict.fromkeys(r for r in (s.get("receipts") or []) if r))
    if not receipts:
        frappe.throw("A shipment needs at least one receipt")
    if len(_import_receipts(target, receipts)) != len(receipts):
        frappe.throw("Every receipt must be a 2026 import receipt of this company")
    name = s.get("name")
    if name:
        doc = frappe.get_doc(DT, name)
        if doc.company != target:
            frappe.throw("Not permitted", frappe.PermissionError)
        if doc.status != "Draft":
            frappe.throw(f"{name} is {doc.status}. Send it back to draft before editing.")
        before = _doc_payload(doc)
    else:
        doc = frappe.new_doc(DT)
        doc.company = target
        before = {}
    for r in receipts:
        other = _shipment_of(r)
        if other and other != name:
            frappe.throw(f"{r} is already in shipment {other}")
    charges = s.get("charges") or []
    lines = [c.get("invoice_item") for c in charges if c.get("invoice_item")]
    taken = _taken(lines, name)
    for c in charges:
        if flt(c.get("amount")) <= 0:
            frappe.throw("A linked amount must be above zero")
        if c.get("invoice_item"):
            full = flt(frappe.db.get_value("Purchase Invoice Item", c["invoice_item"], "base_amount"))
            if flt(c["amount"]) > full - taken.get(c["invoice_item"], 0) + 0.5:
                frappe.throw(f"{c.get('purchase_invoice')}: {flt(c['amount']):,.2f} is more than what is left "
                             f"on the line ({full - taken.get(c['invoice_item'], 0):,.2f})")
    doc.mode = s.get("mode") if s.get("mode") in ("Sea", "Air") else "Sea"
    doc.fx_rate = flt(s.get("fx_rate")) or None
    doc.customs_declaration = (s.get("customs_declaration") or "").strip()
    doc.bill_of_lading = (s.get("bill_of_lading") or "").strip()
    doc.tr_basis = s.get("tr_basis") if s.get("tr_basis") in ("Weight", "Value") else "Weight"
    doc.set("receipts", [{"purchase_receipt": r} for r in receipts])
    rows = []
    for c in charges:
        line = c.get("invoice_item")
        meta = frappe.db.get_value("Purchase Invoice Item", line, ["parent", "expense_account", "base_amount"],
                                   as_dict=True) if line else None
        rows.append({"side": c.get("side") if c.get("side") in ("Morocco", "Turkey") else "Morocco",
                     "purchase_invoice": meta.parent if meta else None, "invoice_item": line,
                     "source_company": frappe.db.get_value("Purchase Invoice", meta.parent, "company") if meta else None,
                     "account": meta.expense_account if meta else None,
                     "description": (c.get("description") or "")[:140], "full_amount": flt(meta.base_amount) if meta else 0,
                     "amount": flt(c.get("amount")), "is_manual": 0 if meta else 1, "attachment": c.get("attachment")})
    doc.set("charges", rows)
    doc.flags.ignore_permissions = True
    doc.save()
    after = _doc_payload(doc)
    _actions.record(SAVE_ACTION, target, reference_doctype=DT, reference_name=doc.name,
                    voucher_type=DT, voucher_no=doc.name, amount=0,
                    payload=json.dumps({"before": before, "after": after}, default=str)[:60000],
                    result=json.dumps({"saved": doc.name}), notes=_describe(before, after))
    return get_shipment(target, doc.name)


@frappe.whitelist()
def set_status(company=None, name=None, status=None, comment=None):
    """Draft → Review → Locked, and back to Draft. The person who locks is not
    the one who sent it for review (a user manager may)."""
    assert_can_write()
    target = _target(company)
    doc = frappe.get_doc(DT, name)
    if doc.company != target:
        frappe.throw("Not permitted", frappe.PermissionError)
    me = frappe.session.user
    allowed = {("Draft", "Review"), ("Review", "Draft"), ("Review", "Locked"), ("Locked", "Draft")}
    if (doc.status, status) not in allowed:
        frappe.throw(f"Cannot go from {doc.status} to {status}")
    if status == "Locked" and doc.sent_by == me and not can_manage_users():
        frappe.throw("Someone other than the person who sent it for review has to lock it.")
    old = doc.status
    doc.status = status
    if status == "Review":
        doc.sent_by = me
    if status == "Locked":
        doc.locked_by = me
    doc.flags.ignore_permissions = True
    doc.save()
    _actions.record(SAVE_ACTION, target, reference_doctype=DT, reference_name=doc.name,
                    voucher_type=DT, voucher_no=doc.name, amount=0,
                    payload=json.dumps({"from": old, "to": status, "comment": comment}),
                    result=json.dumps({"status": status}),
                    notes=f"{old} → {status}" + (f" — {comment}" if comment else ""))
    return get_shipment(target, doc.name)


@frappe.whitelist()
def set_item_weight(company=None, item_code=None, weight=None, shipment=None):
    """Weight per unit (kg) on the item master — every costing reads it. Logged
    with the old value, against the shipment it was set from."""
    assert_can_write()
    target = _target(company)
    w = flt(weight, 4)
    if not item_code or w <= 0 or w > 500:
        frappe.throw("Weight must be between 0 and 500 kg")
    old = flt(frappe.db.get_value("Item", item_code, "weight_per_unit"))
    upd = {"weight_per_unit": w}
    if not frappe.db.get_value("Item", item_code, "weight_uom") and frappe.db.exists("UOM", "Kg"):
        upd["weight_uom"] = "Kg"
    frappe.db.set_value("Item", item_code, upd)
    _actions.record(SAVE_ACTION, target, reference_doctype=DT if shipment else "Item",
                    reference_name=shipment or item_code, voucher_type="Item", voucher_no=item_code, amount=0,
                    payload=json.dumps({"item": item_code, "before": old, "after": w}),
                    result=json.dumps({"weight": w}), notes=f"weight {item_code}: {old or '—'} → {w} kg")
    return {"item_code": item_code, "weight": w, "before": old}


@frappe.whitelist()
def set_fx(company=None, month=None, rate=None):
    """Set (or clear, with no rate) the TRY→MAD rate for a month."""
    assert_can_write()
    target = _target(company)
    if not (month and len(month) == 7):
        frappe.throw("Month must look like 2026-06")
    r = flt(rate, 6)
    lo, hi = _FX_BAND["TRY"]
    if r and not (lo <= r <= hi):
        frappe.throw(f"{r} is outside the TRY→MAD band {lo}–{hi}")
    t = _fx_table()
    old = t.get(month)
    if r:
        t[month] = r
    else:
        t.pop(month, None)
    frappe.db.set_default(_FX_KEY, json.dumps(t))
    _actions.record(SAVE_ACTION, target, reference_doctype="Company", reference_name=target, amount=0,
                    payload=json.dumps({"month": month, "before": old, "after": r or None}),
                    result=json.dumps({"ok": 1}), notes=f"TRY→MAD {month}: {old or '—'} → {r or '—'}")
    return fx_table(target, month[:4])
