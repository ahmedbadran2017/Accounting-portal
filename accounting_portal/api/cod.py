"""COD operational pipeline + Cathedis remittance reconciliation.

The accounting-relevant lifecycle of a confirmed COD order:

    To Deliver  → handed to the carrier (invoiced / in transit), not delivered
    Delivered   → carrier confirms delivery (custom_track_shipment_status)
    Collected   → carrier remitted the cash; we stamp the remittance reference
                  (custom_reference_number = "CATH…") — this is the existing
                  field/marker, so Collected is simply "has a CATH reference"
    Returned    → carrier returned / failed delivery

The Cathedis daily "Retour de fonds" file lists delivered orders by N° CMD
(= the Sales Order name, e.g. #218556). Reconciliation = match each line to its
order, then stamp the remittance reference + mark Fully Received, which moves the
order from Delivered to Collected. Scoped to the current fiscal year (2026+);
older orders stay in the plain Sales-orders history.
"""
import base64
import io
import re

import frappe
from frappe.utils import flt, getdate, nowdate

from accounting_portal.api import _actions
from accounting_portal.api.permissions import assert_can_write, assert_portal_access, resolve_companies

COLLECT_ACTION = "Collect COD"
RETURN_TRACK = ("Return", "Returned", "Return Issued", "Delivery Exception", "Failed Attempt")
TRANSIT_TRACK = ("In Transit", "Out For Delivery", "Picked up", "Pending")
BUCKETS = ("todeliver", "delivered", "collected", "toreturn", "returned")


def _fy_start():
    return getdate(nowdate()).replace(month=1, day=1).isoformat()


def _target(company):
    companies = resolve_companies(company)
    if not companies:
        return None
    return company if (company and company in companies) else companies[0]


# ── bucket classifier (must agree with the SQL conditions below) ──
# To Return = carrier flagged it back (track) but the goods haven't physically
# returned. Returned = a submitted return Delivery Note exists (goods back in the
# warehouse, inventory restocked) — the authoritative physical-return signal.
def cod_bucket(ref, track, has_return_dn=False):
    if (ref or "").upper().startswith("CATH"):
        return "collected"
    if has_return_dn:
        return "returned"
    track = (track or "").strip()
    if track in RETURN_TRACK:
        return "toreturn"
    if track == "Delivered":
        return "delivered"
    return "todeliver"


_RETURNISH = "('Return','Returned','Return Issued','Delivery Exception','Failed Attempt')"
_TRANSIT = "('In Transit','Out For Delivery','Picked up')"
_NOTCATH = "IFNULL(so.custom_reference_number,'') NOT LIKE 'CATH%%'"
# Flags orders that have a submitted return Delivery Note (goods physically back).
_RET_JOIN = (
    "LEFT JOIN (SELECT DISTINCT dni.against_sales_order so "
    "FROM `tabDelivery Note Item` dni JOIN `tabDelivery Note` dn ON dn.name=dni.parent "
    "WHERE dn.is_return=1 AND dn.docstatus=1 AND dn.company=%(c)s "
    "AND IFNULL(dni.against_sales_order,'')!='') ret ON ret.so=so.name")
_COND = {
    "collected": "IFNULL(so.custom_reference_number,'') LIKE 'CATH%%'",
    "returned": f"{_NOTCATH} AND ret.so IS NOT NULL",
    "toreturn": f"{_NOTCATH} AND ret.so IS NULL AND so.custom_track_shipment_status IN {_RETURNISH}",
    "delivered": f"{_NOTCATH} AND ret.so IS NULL AND so.custom_track_shipment_status='Delivered'",
    "todeliver": f"{_NOTCATH} AND ret.so IS NULL "
                 f"AND so.custom_track_shipment_status NOT IN {_RETURNISH} "
                 f"AND so.custom_track_shipment_status!='Delivered' "
                 f"AND (so.per_billed > 0 OR so.custom_track_shipment_status IN {_TRANSIT})",
}
_BASE = ("so.company=%(c)s AND so.docstatus=1 AND so.transaction_date>=%(fy)s "
         "AND IFNULL(so.custom_sales_status,'') NOT IN ('Cancelled','Duplicated','')")


@frappe.whitelist()
def cod_summary(company=None, from_date=None, to_date=None):
    """Count + value per pipeline bucket. Scoped to the current fiscal year, and
    optionally to a transaction-date range so all four cards show the SAME cohort
    (e.g. orders placed this month) — a coherent funnel rather than mixing a
    filtered bucket with full-year totals."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    params = {"c": target, "fy": _fy_start()}
    date_cond = ""
    if from_date:
        date_cond += " AND so.transaction_date >= %(fd)s"
        params["fd"] = from_date
    if to_date:
        date_cond += " AND so.transaction_date <= %(td)s"
        params["td"] = to_date
    # One pass, classified by CASE (priority = collected → returned → toreturn →
    # delivered → todeliver), so the return-DN join materialises once.
    case = (
        "CASE WHEN IFNULL(so.custom_reference_number,'') LIKE 'CATH%%' THEN 'collected' "
        "WHEN ret.so IS NOT NULL THEN 'returned' "
        f"WHEN so.custom_track_shipment_status IN {_RETURNISH} THEN 'toreturn' "
        "WHEN so.custom_track_shipment_status='Delivered' THEN 'delivered' "
        f"WHEN (so.per_billed>0 OR so.custom_track_shipment_status IN {_TRANSIT}) THEN 'todeliver' "
        "ELSE 'other' END")
    rows = frappe.db.sql(
        f"SELECT {case} bucket, COUNT(*) n, ROUND(SUM(so.grand_total)) val "
        f"FROM `tabSales Order` so {_RET_JOIN} WHERE {_BASE}{date_cond} GROUP BY bucket",
        params, as_dict=True)
    out = {b: {"count": 0, "value": 0.0} for b in BUCKETS}
    for r in rows:
        if r.bucket in out:
            out[r.bucket] = {"count": r.n or 0, "value": flt(r.val)}
    return out


@frappe.whitelist()
def list_bucket(company=None, bucket="delivered", search=None, from_date=None, to_date=None, limit=500):
    """Orders in one pipeline bucket (current fiscal year), newest first.

    Date range + search are applied SERVER-SIDE (the buckets hold tens of
    thousands of rows, so client-side filtering of a 500-row window would be
    wrong). Returns the true filtered count + value plus the first `limit` rows."""
    assert_portal_access()
    target = _target(company)
    if not target or bucket not in _COND:
        return {"count": 0, "value": 0, "rows": []}
    params = {"c": target, "fy": _fy_start(), "limit": min(int(limit or 500), 1000)}
    conds = [_BASE, "(" + _COND[bucket] + ")"]
    if search:
        conds.append("(so.name LIKE %(s)s OR so.customer LIKE %(s)s)")
        params["s"] = f"%{search}%"
    if from_date:
        conds.append("so.transaction_date >= %(fd)s")
        params["fd"] = from_date
    if to_date:
        conds.append("so.transaction_date <= %(td)s")
        params["td"] = to_date
    where = " AND ".join(conds)

    tot = frappe.db.sql(
        f"SELECT COUNT(*) n, ROUND(SUM(so.grand_total)) val FROM `tabSales Order` so {_RET_JOIN} WHERE {where}",
        params, as_dict=True)[0]
    rows = frappe.db.sql(
        f"""SELECT so.name, so.customer, so.grand_total AS value, so.transaction_date AS date,
                   so.custom_track_shipment_status AS track, so.custom_tracking_company AS carrier,
                   so.custom_shipping_city AS city, so.custom_reference_number AS reference
            FROM `tabSales Order` so {_RET_JOIN} WHERE {where}
            ORDER BY so.transaction_date DESC, so.creation DESC LIMIT %(limit)s""",
        params, as_dict=True)
    from accounting_portal.api.customers import _cities_for
    missing = list({r["customer"] for r in rows if not (r.get("city") or "").strip()})
    cities = _cities_for(missing) if missing else {}
    rinfo = _return_info_for([r["name"] for r in rows]) if bucket in ("toreturn", "returned") else {}
    for r in rows:
        r["value"] = flt(r["value"])
        r["bucket"] = bucket
        if not (r.get("city") or "").strip():
            r["city"] = cities.get(r["customer"]) or ""
        ri = rinfo.get(r["name"]) or {}
        r["return_shipment"] = ri.get("shipment") or ""
        r["return_status"] = ri.get("status") or ""
        r["returned_on"] = ri.get("date") or ""
    return {"count": tot.n or 0, "value": flt(tot.val), "rows": rows}


def _return_info_for(names):
    """Map each Sales Order to the Return Shipment batch (Codx warehouse module)
    that processed it — joined via its outbound Delivery Note. Surfaces the
    warehouse-side return record + its status next to the accounting bucket."""
    if not names:
        return {}
    rows = frappe.db.sql(
        """SELECT odn.against_sales_order so,
                  SUBSTRING_INDEX(GROUP_CONCAT(rsi.parent ORDER BY rs.posting_date DESC, rs.modified DESC), ',', 1) shipment,
                  SUBSTRING_INDEX(GROUP_CONCAT(rs.status ORDER BY rs.posting_date DESC, rs.modified DESC), ',', 1) status,
                  MAX(rs.posting_date) dt
           FROM `tabReturn Shipment Item` rsi
           JOIN `tabReturn Shipment` rs ON rs.name=rsi.parent
           JOIN `tabDelivery Note Item` odn ON odn.parent=rsi.delivery_note
           WHERE odn.against_sales_order IN %(names)s AND rs.docstatus < 2
           GROUP BY odn.against_sales_order""",
        {"names": tuple(names)}, as_dict=True)
    return {r.so: {"shipment": r.shipment, "status": r.status, "date": str(r.dt or "")} for r in rows}


@frappe.whitelist()
def get_return_shipment(name=None):
    """One warehouse return batch: header stats + items scanned + the Sales Orders
    it covers (via each item's outbound Delivery Note)."""
    assert_portal_access()
    if not name or not frappe.db.exists("Return Shipment", name):
        return None
    rs = frappe.get_doc("Return Shipment", name)
    items = [{
        "item_code": it.item_code, "sku": it.sku, "item_name": it.item_name,
        "ordered_qty": it.ordered_qty, "actual_qty": it.actual_qty,
        "missing_qty": flt(it.missing_qty), "is_complete": int(it.is_complete or 0),
        "delivery_note": it.delivery_note, "awb": it.awb,
    } for it in rs.items[:400]]
    dns = list({it.delivery_note for it in rs.items if it.delivery_note})
    orders = []
    if dns:
        orders = [o.so for o in frappe.db.sql(
            "SELECT DISTINCT against_sales_order so FROM `tabDelivery Note Item` "
            "WHERE parent IN %(dns)s AND IFNULL(against_sales_order,'')!='' ORDER BY so DESC",
            {"dns": tuple(dns)}, as_dict=True)]
    return {
        "name": rs.name, "status": rs.status, "posting_date": str(rs.posting_date or ""),
        "shipping_company": rs.shipping_company, "company": rs.company,
        "total_orders": rs.total_orders or len(orders),
        "total_ordered_qty": flt(rs.total_ordered_qty), "total_actual_qty": flt(rs.total_actual_qty),
        "total_missing_qty": flt(rs.total_missing_qty), "return_percentage": flt(rs.return_percentage),
        "missing_skus": rs.missing_skus or "", "items": items, "n_items": len(rs.items),
        "orders": orders[:500], "sales_returns": rs.sales_returns_created or "",
    }


# ── Cathedis remittance parsing ──
def _pdf_text(raw):
    import pypdf
    reader = pypdf.PdfReader(io.BytesIO(raw))
    return "\n".join((p.extract_text() or "") for p in reader.pages)


# Moroccan number format: groups of 3 separated by a space, decimal comma.
_AMT = r"(\d{1,3}(?: \d{3})*,\d{2})"
# Each delivery row ends with: Livré-le-date  Montant  Status  Frais  V.D.(1.5%).
# Anchoring on that tail (after collapsing the wrapped name/city lines into one
# space-separated string) is far more robust than the old prefix+date regex,
# which dropped ~14% of rows and under-summed. The row's N° CMD is then the
# first "<tracking> <cmd>" pair in the text between this tail and the previous.
_TAIL_RE = re.compile(
    r"\d{2}/\d{2}/\d{4}\s+" + _AMT +
    r"\s+(Livr\w+|Retourn\w+|Refus\w+|Annul\w+)\s+" + _AMT + r"\s+" + _AMT)
_CMD_RE = re.compile(r"(\d{6,8})\s+(\d{4,8})")


def _num(s):
    return flt((s or "0").replace(" ", "").replace(",", "."))


def parse_remittance_text(text):
    flat = re.sub(r"\s+", " ", text or "")
    ref_m = re.search(r"CATH\d+", flat)
    rows = []
    prev = 0
    for m in _TAIL_RE.finditer(flat):
        head = flat[prev:m.start()]
        prev = m.end()
        c = _CMD_RE.search(head)
        rows.append({
            "tracking": c.group(1) if c else None,
            "cmd": c.group(2) if c else None,
            "amount": _num(m.group(1)), "status": m.group(2),
            "fee": _num(m.group(3)), "commission": _num(m.group(4)),
        })

    def _tot(label):
        mt = re.search(label + r"\s*:?\s*(\d[\d ]*,\d{2})", flat)
        return _num(mt.group(1)) if mt else 0.0
    printed = {"delivered": _tot("Total livr."), "net": _tot("Net . rembourser"),
               "fees": _tot("Frais de port"), "declared": _tot("Valeurs d.clar.es")}
    return {"reference": ref_m.group(0) if ref_m else None, "rows": rows, "printed": printed}


# Payment types that mean the customer paid AHEAD (online card / bank) — so the
# cash Cathedis collects on delivery is the order total minus what's prepaid.
# COD + "manual" are pure cash-on-delivery (manual = COD, per ops).
_PREPAID_TYPES = {"Payzone Maroc", "Virement bancaire", "Bank Transfer"}


def _pay_method(payment_type):
    pt = (payment_type or "").strip()
    if pt == "Payzone Maroc":
        return "Card"
    if pt in ("Virement bancaire", "Bank Transfer"):
        return "Bank"
    return "COD"  # COD, manual, or blank


def _expected_cash(o):
    """How much CASH Cathedis should collect on delivery = total − already paid.
    advance_paid isn't reliably recorded for card/bank orders, so when the
    payment type is prepaid we assume the whole order is settled ahead."""
    total = flt(o.grand_total)
    adv = flt(o.get("advance_paid"))
    if (o.get("payment_type") or "").strip() in _PREPAID_TYPES:
        return round(total - (adv if adv > 0 else total), 2)
    return round(total - adv, 2)


@frappe.whitelist()
def match_remittance(company=None, content_b64=None, filename=None):
    """Parse an uploaded Cathedis remittance (base64 PDF) and match every line to
    its Sales Order. Returns matched / variance / already-collected / not-found —
    a dry-run preview; nothing is written. The file's Montant is the CASH collected,
    so each line is matched against the order's EXPECTED cash (total − prepaid),
    which lets fully card/bank-paid orders (expected 0, file 0) match cleanly."""
    assert_portal_access()
    target = _target(company)
    if not target:
        frappe.throw("No company in scope")
    if not content_b64:
        frappe.throw("No file content")
    try:
        raw = base64.b64decode(content_b64.split(",")[-1])
        parsed = parse_remittance_text(_pdf_text(raw))
    except Exception as e:
        frappe.throw(f"Couldn't read the PDF: {e}")

    names = ["#" + r["cmd"] for r in parsed["rows"] if r.get("cmd")]
    found = {}
    if names:
        for o in frappe.get_all(
            "Sales Order",
            filters={"name": ["in", names], "company": target},
            fields=["name", "customer", "grand_total", "advance_paid", "payment_type",
                    "custom_reference_number", "custom_track_shipment_status"]):
            found[o.name] = o

    matched, variance, already, not_found = [], [], [], []
    for r in parsed["rows"]:
        nm = ("#" + r["cmd"]) if r.get("cmd") else None
        o = found.get(nm) if nm else None
        if not o:
            not_found.append(r)
            continue
        r["order"] = nm
        r["customer"] = o.customer
        r["grand_total"] = flt(o.grand_total)
        r["advance"] = flt(o.get("advance_paid"))
        r["method"] = _pay_method(o.get("payment_type"))
        exp = _expected_cash(o)
        r["expected"] = exp
        r["gap"] = round(r["amount"] - exp, 2)
        if (o.custom_reference_number or "").upper().startswith("CATH"):
            r["existing_reference"] = o.custom_reference_number
            already.append(r)
        elif abs(exp - r["amount"]) > 0.5:
            variance.append(r)
        else:
            matched.append(r)

    return {
        "reference": parsed["reference"],
        "filename": filename,
        "totals": {
            "lines": len(parsed["rows"]),
            "matched": len(matched), "variance": len(variance),
            "already_collected": len(already), "not_found": len(not_found),
            # Gross COD = sum of every line's Montant (no deduction) — this is what
            # must tie to the file's printed "Total livré".
            "gross_cod": round(sum(r["amount"] for r in parsed["rows"]), 2),
            "matched_value": round(sum(r["amount"] for r in matched), 2),
            "net_remitted": round(sum(r["amount"] - r["fee"] - r["commission"] for r in matched), 2),
            "carrier_fees": round(sum(r["fee"] + r["commission"] for r in matched), 2),
            "by_method": {
                "cod": sum(1 for r in matched if r.get("method") == "COD"),
                "card": sum(1 for r in matched if r.get("method") == "Card"),
                "bank": sum(1 for r in matched if r.get("method") == "Bank"),
            },
            "printed": parsed.get("printed") or {},
        },
        "matched": matched[:1000], "variance": variance[:200],
        "already_collected": already[:200], "not_found": not_found[:200],
    }


def _collect_poster(action):
    """Stamp the remittance reference + mark Fully Received on each order."""
    import json
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    reference = p.get("reference")
    orders = p.get("orders") or []
    has_pc = frappe.get_meta("Sales Order").has_field("custom_payment_collection")
    done = 0
    for nm in orders:
        if not frappe.db.exists("Sales Order", nm):
            continue
        vals = {"custom_reference_number": reference}
        if has_pc:
            vals["custom_payment_collection"] = "Fully Received"
        frappe.db.set_value("Sales Order", nm, vals, update_modified=True)
        done += 1
    return {"voucher_type": "Sales Order", "voucher_no": f"{reference} ({done})", "result": "collected"}


_actions.register_poster(COLLECT_ACTION, _collect_poster)


@frappe.whitelist()
def apply_remittance(company=None, reference=None, orders=None, amount=0, dedupe_key=None):
    """Mark the matched orders Collected — stamp the Cathedis reference and move
    them out of Delivered. Audited through the write gateway."""
    assert_can_write()
    target = _target(company)
    if not target:
        frappe.throw("No company in scope")
    if not reference:
        frappe.throw("Missing remittance reference")
    if isinstance(orders, str):
        import json
        orders = json.loads(orders)
    orders = [o for o in (orders or []) if o]
    if not orders:
        frappe.throw("No orders to collect")
    key = dedupe_key or f"cod:{target}:{reference}"
    return _actions.execute(
        COLLECT_ACTION, target, key,
        payload={"reference": reference, "orders": orders},
        amount=flt(amount), notes=f"Cathedis {reference}: {len(orders)} orders collected")
