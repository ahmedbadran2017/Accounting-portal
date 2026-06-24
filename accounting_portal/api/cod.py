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
BUCKETS = ("to_deliver", "delivered", "collected", "returned")


def _fy_start():
    return getdate(nowdate()).replace(month=1, day=1).isoformat()


def _target(company):
    companies = resolve_companies(company)
    if not companies:
        return None
    return company if (company and company in companies) else companies[0]


# ── bucket classifier (must agree with the SQL conditions below) ──
def cod_bucket(ref, track):
    if (ref or "").upper().startswith("CATH"):
        return "collected"
    track = (track or "").strip()
    if track in RETURN_TRACK:
        return "returned"
    if track == "Delivered":
        return "delivered"
    return "to_deliver"


_COND = {
    "collected": "IFNULL(so.custom_reference_number,'') LIKE 'CATH%%'",
    "returned": "IFNULL(so.custom_reference_number,'') NOT LIKE 'CATH%%' "
                "AND so.custom_track_shipment_status IN ('Return','Returned','Return Issued','Delivery Exception','Failed Attempt')",
    "delivered": "IFNULL(so.custom_reference_number,'') NOT LIKE 'CATH%%' "
                 "AND so.custom_track_shipment_status='Delivered'",
    "to_deliver": "IFNULL(so.custom_reference_number,'') NOT LIKE 'CATH%%' "
                  "AND so.custom_track_shipment_status NOT IN "
                  "('Delivered','Return','Returned','Return Issued','Delivery Exception','Failed Attempt') "
                  "AND (so.per_billed > 0 OR so.custom_track_shipment_status IN ('In Transit','Out For Delivery','Picked up'))",
}
_BASE = ("so.company=%(c)s AND so.docstatus=1 AND so.transaction_date>=%(fy)s "
         "AND IFNULL(so.custom_sales_status,'') NOT IN ('Cancelled','Duplicated','')")


@frappe.whitelist()
def cod_summary(company=None):
    """Count + value per pipeline bucket for the current fiscal year."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    params = {"c": target, "fy": _fy_start()}
    out = {}
    for b in BUCKETS:
        r = frappe.db.sql(
            f"SELECT COUNT(*) n, ROUND(SUM(so.grand_total)) val FROM `tabSales Order` so "
            f"WHERE {_BASE} AND ({_COND[b]})", params, as_dict=True)[0]
        out[b] = {"count": r.n or 0, "value": flt(r.val)}
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
        f"SELECT COUNT(*) n, ROUND(SUM(so.grand_total)) val FROM `tabSales Order` so WHERE {where}",
        params, as_dict=True)[0]
    rows = frappe.db.sql(
        f"""SELECT so.name, so.customer, so.grand_total AS value, so.transaction_date AS date,
                   so.custom_track_shipment_status AS track, so.custom_tracking_company AS carrier,
                   so.custom_shipping_city AS city, so.custom_reference_number AS reference
            FROM `tabSales Order` so WHERE {where}
            ORDER BY so.transaction_date DESC, so.creation DESC LIMIT %(limit)s""",
        params, as_dict=True)
    from accounting_portal.api.customers import _cities_for
    missing = list({r["customer"] for r in rows if not (r.get("city") or "").strip()})
    cities = _cities_for(missing) if missing else {}
    for r in rows:
        r["value"] = flt(r["value"])
        r["bucket"] = bucket
        if not (r.get("city") or "").strip():
            r["city"] = cities.get(r["customer"]) or ""
    return {"count": tot.n or 0, "value": flt(tot.val), "rows": rows}


# ── Cathedis remittance parsing ──
def _pdf_text(raw):
    import pypdf
    reader = pypdf.PdfReader(io.BytesIO(raw))
    return "\n".join((p.extract_text() or "") for p in reader.pages)


# Moroccan number format: groups of 3 separated by a space, decimal comma.
_AMT = r"(\d{1,3}(?: \d{3})*,\d{2})"
# #ID  N°CMD  ...name/city + 1-2 dates...  Montant  Status  Frais  (1.5%)
_ROW_RE = re.compile(
    r"(\d{6,8})\s+(\d{4,8})\s.+?(?:\d{2}/\d{2}/\d{4}\s+){1,2}" + _AMT +
    r"\s+(Livr\w+|Retourn\w+|Refus\w+|Annul\w+)\s+" + _AMT + r"\s+" + _AMT,
    re.S)


def _num(s):
    return flt((s or "0").replace(" ", "").replace(",", "."))


def parse_remittance_text(text):
    text = text or ""
    ref_m = re.search(r"CATH\d+", text)
    rows = []
    for m in _ROW_RE.finditer(text):
        rows.append({
            "tracking": m.group(1), "cmd": m.group(2),
            "amount": _num(m.group(3)), "status": m.group(4),
            "fee": _num(m.group(5)), "commission": _num(m.group(6)),
        })

    def _tot(label):
        mt = re.search(label + r"\s*:?\s*(\d[\d ]*,\d{2})", text)
        return _num(mt.group(1)) if mt else 0.0
    printed = {"net": _tot("Net . rembourser"), "fees": _tot("Frais de port"),
               "declared": _tot("Valeurs d.clar.es")}
    return {"reference": ref_m.group(0) if ref_m else None, "rows": rows, "printed": printed}


@frappe.whitelist()
def match_remittance(company=None, content_b64=None, filename=None):
    """Parse an uploaded Cathedis remittance (base64 PDF) and match every line to
    its Sales Order. Returns matched / variance / already-collected / not-found —
    a dry-run preview; nothing is written."""
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

    names = ["#" + r["cmd"] for r in parsed["rows"]]
    found = {}
    if names:
        for o in frappe.get_all(
            "Sales Order",
            filters={"name": ["in", names], "company": target},
            fields=["name", "customer", "grand_total", "custom_reference_number",
                    "custom_track_shipment_status"]):
            found[o.name] = o

    matched, variance, already, not_found = [], [], [], []
    for r in parsed["rows"]:
        nm = "#" + r["cmd"]
        o = found.get(nm)
        if not o:
            not_found.append(r)
            continue
        r["order"] = nm
        r["customer"] = o.customer
        r["grand_total"] = flt(o.grand_total)
        if (o.custom_reference_number or "").upper().startswith("CATH"):
            r["existing_reference"] = o.custom_reference_number
            already.append(r)
        elif abs(flt(o.grand_total) - r["amount"]) > 0.5:
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
            "matched_value": round(sum(r["amount"] for r in matched), 2),
            "net_remitted": round(sum(r["amount"] - r["fee"] - r["commission"] for r in matched), 2),
            "carrier_fees": round(sum(r["fee"] + r["commission"] for r in matched), 2),
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
