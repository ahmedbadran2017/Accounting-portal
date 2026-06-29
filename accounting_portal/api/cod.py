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

from accounting_portal.api import _actions, _paginate
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


def _remit_status(variance, expected):
    """Matched if the deposit ties to expected; short if under, over if above."""
    if expected and abs(variance) / expected <= 0.005:
        return "matched"
    return "short" if variance < 0 else "over"


@frappe.whitelist()
def cod_remittances(company=None, search=None, variance_only=0, limit=100):
    """COD remittance batches: each carrier reference (CATH…) groups the orders it
    collected (expected) against what was actually deposited to the bank, with the
    variance. Powers the remittance workbench + the variance queue."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return []
    conds = ["company=%(c)s", "docstatus=1", _ref_present("custom_reference_number")]
    params = {"c": target, "limit": min(int(limit or 100), 2000)}
    if search:
        conds.append("(custom_reference_number LIKE %(s)s OR IFNULL(custom_tracking_company,'') LIKE %(s)s)")
        params["s"] = f"%{search}%"
    batches = frappe.db.sql(
        f"""SELECT custom_reference_number AS ref,
                   IFNULL(NULLIF(custom_tracking_company,''),'Cathedis') AS carrier,
                   COUNT(*) AS orders, ROUND(SUM(grand_total)) AS expected,
                   MAX(transaction_date) AS date
            FROM `tabSales Order` WHERE {' AND '.join(conds)}
            GROUP BY custom_reference_number, custom_tracking_company
            ORDER BY MAX(transaction_date) DESC LIMIT %(limit)s""", params, as_dict=True)
    refs = [b["ref"] for b in batches]
    deposits = {}
    if refs:
        for r in frappe.db.sql(
                """SELECT reference_no AS ref, ROUND(SUM(paid_amount)) AS amt, COUNT(*) AS n
                   FROM `tabPayment Entry` WHERE company=%(c)s AND docstatus=1
                     AND payment_type='Receive' AND reference_no IN %(r)s
                   GROUP BY reference_no""", {"c": target, "r": refs}, as_dict=True):
            deposits[r.ref] = r
    out = []
    for b in batches:
        d = deposits.get(b["ref"])
        b["collected"] = flt(d.amt) if d else 0
        b["deposits"] = d.n if d else 0
        b["variance"] = round(b["collected"] - flt(b["expected"]), 0)
        b["status"] = _remit_status(b["variance"], flt(b["expected"]))
        b["date"] = str(b.get("date") or "")
        if not (int(variance_only or 0) and b["status"] == "matched"):
            out.append(b)
    return out


@frappe.whitelist()
def get_remittance(ref=None, company=None):
    """One remittance batch: the orders it collected, the deposits posted against
    it, and the reconciliation totals."""
    assert_portal_access()
    target = _target(company)
    if not target or not ref:
        return None
    orders = frappe.db.sql(
        """SELECT name, customer, ROUND(grand_total) AS value, transaction_date AS date,
                  IFNULL(NULLIF(custom_track_shipment_status,''), custom_logistics_status) AS status
           FROM `tabSales Order` WHERE company=%s AND docstatus=1 AND custom_reference_number=%s
           ORDER BY transaction_date DESC LIMIT 500""", (target, ref), as_dict=True)
    if not orders:
        return None
    deposits = frappe.db.sql(
        """SELECT name, party AS customer, ROUND(paid_amount) AS amount, posting_date AS date,
                  IFNULL(mode_of_payment,'—') AS method
           FROM `tabPayment Entry` WHERE company=%s AND docstatus=1 AND payment_type='Receive'
             AND reference_no=%s ORDER BY posting_date DESC LIMIT 500""", (target, ref), as_dict=True)
    expected = sum(flt(o.value) for o in orders)
    collected = sum(flt(d.amount) for d in deposits)
    carrier = frappe.db.get_value("Sales Order", {"custom_reference_number": ref, "company": target}, "custom_tracking_company") or "Cathedis"
    variance = round(collected - expected, 0)
    return {
        "ref": ref, "carrier": carrier, "company": target,
        "orders": orders, "deposits": deposits,
        "n_orders": len(orders), "n_deposits": len(deposits),
        "expected": round(expected), "collected": round(collected), "variance": variance,
        "status": _remit_status(variance, expected),
    }


# Carrier remittance-reference prefixes. Cathedis changed the format from
# "CATH…" to "RDF-…" in June 2026; both mean "this order's cash was remitted".
# Keep this the single source of truth — add a prefix here if the carrier changes
# it again, and parsing + every "is collected" query updates together.
_REF_PREFIXES = ("CATH", "RDF")
_REF_RE = re.compile(r"(?:" + "|".join(_REF_PREFIXES) + r")[-\w]+")


def _ref_present(col):
    return "(" + " OR ".join(f"IFNULL({col},'') LIKE '{p}%%'" for p in _REF_PREFIXES) + ")"


def _ref_absent(col):
    return "(" + " AND ".join(f"IFNULL({col},'') NOT LIKE '{p}%%'" for p in _REF_PREFIXES) + ")"


def _is_ref(s):
    return (s or "").upper().startswith(_REF_PREFIXES)


# ── bucket classifier (must agree with the SQL conditions below) ──
# To Return = carrier flagged it back (track) but the goods haven't physically
# returned. Returned = a submitted return Delivery Note exists (goods back in the
# warehouse, inventory restocked) — the authoritative physical-return signal.
def cod_bucket(ref, track, has_return_dn=False):
    if _is_ref(ref):
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
# Collected = the Cathedis remittance reference is present on EITHER the Sales
# Order OR its Sales Invoice. The book's matching process stamps the invoice
# (~47.5k), the portal's reconcile stamps the order — both count.
_INV_JOIN = (
    "LEFT JOIN (SELECT sii.sales_order so, MAX(si.custom_reference_number) ref "
    "FROM `tabSales Invoice Item` sii JOIN `tabSales Invoice` si ON si.name=sii.parent "
    # docstatus<2 (not just submitted): a carrier remittance ref is stamped on the
    # invoice when the carrier pays — that means COLLECTED regardless of whether the
    # invoice has been submitted yet. Requiring docstatus=1 left ~4.4k collected
    # orders (ref on a still-draft invoice) stuck in the 'delivered' bucket.
    "WHERE si.company=%(c)s AND si.docstatus<2 "
    "AND " + _ref_present("si.custom_reference_number") + " "
    "AND IFNULL(sii.sales_order,'')!='' GROUP BY sii.sales_order) inv ON inv.so=so.name")
_COLLECTED = "(" + _ref_present("so.custom_reference_number") + " OR inv.so IS NOT NULL)"
_NOTCOLL = "(" + _ref_absent("so.custom_reference_number") + " AND inv.so IS NULL)"
# Flags orders that have a submitted return Delivery Note (goods physically back).
# Uses the indexed `return_against` (set iff is_return=1 — verified identical for
# this book) instead of the unindexed is_return, ~2.5x faster.
_RET_JOIN = (
    "LEFT JOIN (SELECT DISTINCT dni.against_sales_order so "
    "FROM `tabDelivery Note` dn JOIN `tabDelivery Note Item` dni ON dni.parent=dn.name "
    "WHERE IFNULL(dn.return_against,'')!='' AND dn.docstatus=1 AND dn.company=%(c)s "
    "AND IFNULL(dni.against_sales_order,'')!='') ret ON ret.so=so.name")
_COND = {
    "collected": _COLLECTED,
    "returned": f"{_NOTCOLL} AND ret.so IS NOT NULL",
    "toreturn": f"{_NOTCOLL} AND ret.so IS NULL AND so.custom_track_shipment_status IN {_RETURNISH}",
    "delivered": f"{_NOTCOLL} AND ret.so IS NULL AND so.custom_track_shipment_status='Delivered'",
    "todeliver": f"{_NOTCOLL} AND ret.so IS NULL "
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
    # The classification join scans every return DN (~0.7s); the result is the
    # same for all cards, so cache it briefly (busted on collect). Card switches
    # don't re-request it (the frontend only reloads on date/entity change).
    ck = f"ap_cod_summary:{target}:{from_date or ''}:{to_date or ''}"
    cached = frappe.cache().get_value(ck)
    if cached is not None:
        return cached
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
        f"CASE WHEN {_COLLECTED} THEN 'collected' "
        "WHEN ret.so IS NOT NULL THEN 'returned' "
        f"WHEN so.custom_track_shipment_status IN {_RETURNISH} THEN 'toreturn' "
        "WHEN so.custom_track_shipment_status='Delivered' THEN 'delivered' "
        f"WHEN (so.per_billed>0 OR so.custom_track_shipment_status IN {_TRANSIT}) THEN 'todeliver' "
        "ELSE 'other' END")
    rows = frappe.db.sql(
        f"SELECT {case} bucket, COUNT(*) n, ROUND(SUM(so.grand_total)) val "
        f"FROM `tabSales Order` so {_RET_JOIN} {_INV_JOIN} WHERE {_BASE}{date_cond} GROUP BY bucket",
        params, as_dict=True)
    out = {b: {"count": 0, "value": 0.0} for b in BUCKETS}
    for r in rows:
        if r.bucket in out:
            out[r.bucket] = {"count": r.n or 0, "value": flt(r.val)}
    frappe.cache().set_value(ck, out, expires_in_sec=300)
    return out


def _bust_summary_cache(company):
    try:
        frappe.cache().delete_keys(f"ap_cod_summary:{company}")
        frappe.cache().delete_keys(f"ap_cod_list:{company}")
    except Exception:
        pass


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
    # Cache the unfiltered (no-search) view so re-visiting a card is instant.
    ck = None
    if not search:
        ck = f"ap_cod_list:{target}:{bucket}:{from_date or ''}:{to_date or ''}:{params['limit']}"
        cached = frappe.cache().get_value(ck)
        if cached is not None:
            return cached
    conds = [_BASE, "(" + _COND[bucket] + ")"]
    if search:
        # Match order #, customer, the remittance ref (on the order or its
        # invoice), and the invoice number itself.
        conds.append(
            "(so.name LIKE %(s)s OR so.customer LIKE %(s)s "
            "OR IFNULL(so.custom_reference_number,'') LIKE %(s)s OR IFNULL(inv.ref,'') LIKE %(s)s "
            "OR EXISTS (SELECT 1 FROM `tabSales Invoice Item` x JOIN `tabSales Invoice` y ON y.name=x.parent "
            "WHERE x.sales_order=so.name AND y.name LIKE %(s)s))")
        params["s"] = f"%{search}%"
    if from_date:
        conds.append("so.transaction_date >= %(fd)s")
        params["fd"] = from_date
    if to_date:
        conds.append("so.transaction_date <= %(td)s")
        params["td"] = to_date
    where = " AND ".join(conds)
    # Every bucket references the invoice-CATH flag (collected = SO or SI ref);
    # the return-DN join is needed by all except 'collected'.
    join = _INV_JOIN + ("" if bucket == "collected" else " " + _RET_JOIN)

    # One pass: window functions give the full count + value alongside the page
    # of rows, so the heavy join materialises once instead of twice.
    rows = frappe.db.sql(
        f"""SELECT so.name, so.customer, so.grand_total AS value, so.transaction_date AS date,
                   so.custom_track_shipment_status AS track, so.custom_tracking_company AS carrier,
                   so.custom_shipping_city AS city,
                   COALESCE(NULLIF(so.custom_reference_number,''), inv.ref) AS reference,
                   COUNT(*) OVER() AS _cnt, ROUND(SUM(so.grand_total) OVER()) AS _val
            FROM `tabSales Order` so {join} WHERE {where}
            ORDER BY so.transaction_date DESC, so.creation DESC LIMIT %(limit)s""",
        params, as_dict=True)
    tot_n = rows[0]["_cnt"] if rows else 0
    tot_val = rows[0]["_val"] if rows else 0
    for r in rows:
        r.pop("_cnt", None)
        r.pop("_val", None)
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
    result = {"count": tot_n or 0, "value": flt(tot_val), "rows": rows}
    if ck:
        frappe.cache().set_value(ck, result, expires_in_sec=300)
    return result


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
    ref_m = _REF_RE.search(flat)
    rows = []
    prev = 0
    for m in _TAIL_RE.finditer(flat):
        head = flat[prev:m.start()]
        prev = m.end()
        c = _CMD_RE.search(head)
        # The carrier's 7-digit #ID leads every row and is stored on the Sales
        # Order as custom_tracking_number — extract it INDEPENDENTLY of the N° CMD
        # so rows whose order ref the parser can't read (#…-ex exchanges, YC-…
        # YouCan ids) can still be matched by tracking number.
        tkm = re.search(r"\d{7}", head)
        rows.append({
            "tracking": tkm.group(0) if tkm else (c.group(1) if c else None),
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
    trackings = [r["tracking"] for r in parsed["rows"] if r.get("tracking")]
    _fields = ["name", "customer", "grand_total", "advance_paid", "payment_type",
               "custom_reference_number", "custom_track_shipment_status", "custom_tracking_number"]
    found, by_track = {}, {}
    if names:
        for o in frappe.get_all("Sales Order", filters={"name": ["in", names], "company": target}, fields=_fields):
            found[o.name] = o
    # Secondary key: the carrier tracking number. Catches orders the N° CMD can't
    # match — exchanges (#…-ex) and YouCan (YC-…) — which carry their own SO name.
    if trackings:
        for o in frappe.get_all("Sales Order",
                                filters={"custom_tracking_number": ["in", trackings], "company": target},
                                fields=_fields):
            if o.custom_tracking_number:
                by_track.setdefault(o.custom_tracking_number, o)

    matched, variance, already, not_found = [], [], [], []
    for r in parsed["rows"]:
        nm = ("#" + r["cmd"]) if r.get("cmd") else None
        o = (found.get(nm) if nm else None) or (by_track.get(r.get("tracking")) if r.get("tracking") else None)
        if not o:
            not_found.append(r)
            continue
        r["order"] = o.name
        r["customer"] = o.customer
        r["grand_total"] = flt(o.grand_total)
        r["advance"] = flt(o.get("advance_paid"))
        r["method"] = _pay_method(o.get("payment_type"))
        exp = _expected_cash(o)
        r["expected"] = exp
        r["gap"] = round(r["amount"] - exp, 2)
        if _is_ref(o.custom_reference_number):
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
        # Defense-in-depth: only stamp orders in this action's company.
        if frappe.db.get_value("Sales Order", nm, "company") != action.company:
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
    # Company scope: only stamp orders that actually belong to this company. The
    # `orders` list comes from the client, so never trust it across companies.
    in_company = set(frappe.get_all(
        "Sales Order", filters={"name": ["in", orders], "company": target}, pluck="name"))
    stray = [o for o in orders if o not in in_company]
    if stray:
        frappe.throw(f"{len(stray)} order(s) are not in {target}: {', '.join(stray[:5])}")
    key = dedupe_key or f"cod:{target}:{reference}"
    res = _actions.execute(
        COLLECT_ACTION, target, key,
        payload={"reference": reference, "orders": orders},
        amount=flt(amount), notes=f"Cathedis {reference}: {len(orders)} orders collected")
    _bust_summary_cache(target)  # bucket counts changed
    return res


@frappe.whitelist()
def carrier_aging(company=None):
    """COD cash held by carriers — delivered-but-not-collected order value, by
    carrier, bucketed by age (days since the order). The carrier float, aged."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {"carriers": []}
    ck = f"ap_carrier_aging:{target}"
    cached = frappe.cache().get_value(ck)
    if cached is not None:
        return cached
    rows = frappe.db.sql(
        f"""SELECT IFNULL(NULLIF(so.custom_tracking_company,''),'—') AS carrier,
                   ROUND(SUM(CASE WHEN DATEDIFF(CURDATE(),so.transaction_date)<=3 THEN so.grand_total ELSE 0 END)) AS d0_3,
                   ROUND(SUM(CASE WHEN DATEDIFF(CURDATE(),so.transaction_date) BETWEEN 4 AND 7 THEN so.grand_total ELSE 0 END)) AS d4_7,
                   ROUND(SUM(CASE WHEN DATEDIFF(CURDATE(),so.transaction_date) BETWEEN 8 AND 14 THEN so.grand_total ELSE 0 END)) AS d8_14,
                   ROUND(SUM(CASE WHEN DATEDIFF(CURDATE(),so.transaction_date)>14 THEN so.grand_total ELSE 0 END)) AS d15p,
                   ROUND(SUM(so.grand_total)) AS total, COUNT(*) AS n,
                   ROUND(AVG(DATEDIFF(CURDATE(),so.transaction_date)),1) AS avg_days
            FROM `tabSales Order` so {_INV_JOIN}
            WHERE so.company=%(c)s AND so.docstatus=1
              AND so.custom_track_shipment_status='Delivered' AND {_NOTCOLL}
            GROUP BY carrier HAVING total>0 ORDER BY total DESC LIMIT 20""",
        {"c": target}, as_dict=True)
    for r in rows:
        for k in ("d0_3", "d4_7", "d8_14", "d15p", "total"):
            r[k] = flt(r[k])
        r["avg_days"] = flt(r["avg_days"])
        r["alert"] = (flt(r["d8_14"]) + flt(r["d15p"])) > 0.2 * max(1, flt(r["total"]))
    result = {"carriers": rows, "total": sum(r["total"] for r in rows),
              "aged": sum(flt(r["d8_14"]) + flt(r["d15p"]) for r in rows)}
    try:
        frappe.cache().set_value(ck, result, expires_in_sec=180)
    except Exception:
        pass
    return result


# ── Carrier settlements: cash the carriers actually collected & remitted ──────
# Carriers collect COD cash into their own holding account ("X Transactions",
# 108.021.00x, typed Bank) — that's "the carrier is holding our money". They then
# sweep it to the real operating bank (BMCE). So per carrier we show: collected
# (deposited into the carrier account this period), still held (current account
# balance), and swept-to-bank (the difference).
_CARRIER_DEP = ("pe.company=%(c)s AND pe.docstatus=1 AND pe.payment_type='Receive' "
                "AND a.account_type='Bank' AND a.account_name LIKE '%%Transaction%%'")


@frappe.whitelist()
def carrier_settlements(company=None, from_date=None, to_date=None):
    """Money the shipping carriers (Cathedis, Aramex, Cash Plus…) actually collected
    for us and where it stands: collected into the carrier account this period,
    still sitting with the carrier, and swept to our operating bank."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {"by_carrier": [], "by_month": [], "total": 0}
    conds = [_CARRIER_DEP]
    params = {"c": target}
    if from_date:
        conds.append("pe.posting_date>=%(fd)s"); params["fd"] = from_date
    if to_date:
        conds.append("pe.posting_date<=%(td)s"); params["td"] = to_date
    where = " AND ".join(conds)
    # collected into each carrier account this period
    rows = frappe.db.sql(
        f"""SELECT pe.paid_to AS account, a.account_name AS carrier,
                   ROUND(SUM(pe.paid_amount)) AS collected, COUNT(*) AS deposits,
                   MAX(pe.posting_date) AS last_date
            FROM `tabPayment Entry` pe JOIN `tabAccount` a ON a.name=pe.paid_to
            WHERE {where} GROUP BY pe.paid_to ORDER BY collected DESC""", params, as_dict=True)
    # current balance still sitting in each carrier account (point-in-time, all-time)
    held = {}
    if rows:
        for h in frappe.db.sql(
                """SELECT account, ROUND(SUM(debit-credit)) bal FROM `tabGL Entry`
                   WHERE company=%(c)s AND is_cancelled=0 AND account IN %(accts)s GROUP BY account""",
                {"c": target, "accts": tuple(r["account"] for r in rows)}, as_dict=True):
            held[h.account] = flt(h.bal)
    for r in rows:
        r["collected"] = flt(r["collected"])
        r["held"] = held.get(r["account"], 0.0)
        r["swept"] = round(r["collected"] - r["held"], 0)  # left the carrier account → bank
        r["last_date"] = str(r.get("last_date") or "")
    by_month = frappe.db.sql(
        f"""SELECT DATE_FORMAT(pe.posting_date,'%%Y-%%m') ym, ROUND(SUM(pe.paid_amount)) collected
            FROM `tabPayment Entry` pe JOIN `tabAccount` a ON a.name=pe.paid_to
            WHERE {where} GROUP BY ym ORDER BY ym DESC LIMIT 12""", params, as_dict=True)
    for m in by_month:
        m["collected"] = flt(m["collected"])
    return {
        "company": target, "currency": frappe.db.get_value("Company", target, "default_currency") or "MAD",
        "by_carrier": rows, "by_month": list(reversed(by_month)),
        "total_collected": sum(r["collected"] for r in rows),
        "total_held": sum(r["held"] for r in rows),
        "deposits": sum(r["deposits"] for r in rows),
    }


@frappe.whitelist()
def list_carrier_deposits(company=None, carrier=None, search=None, from_date=None, to_date=None,
                          start=0, page_size=25, sort_field="date", sort_dir="desc"):
    """The actual carrier deposit Payment Entries — server-paginated. `carrier` is
    the carrier holding account name to scope to one carrier."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {"rows": [], "total": 0}
    conds = [_CARRIER_DEP]
    params = {"c": target}
    if carrier:
        conds.append("a.account_name=%(car)s"); params["car"] = carrier
    if search:
        conds.append("(pe.name LIKE %(s)s OR IFNULL(pe.reference_no,'') LIKE %(s)s OR pe.party LIKE %(s)s)")
        params["s"] = f"%{search}%"
    if from_date:
        conds.append("pe.posting_date>=%(fd)s"); params["fd"] = from_date
    if to_date:
        conds.append("pe.posting_date<=%(td)s"); params["td"] = to_date
    sort = {"date": "pe.posting_date", "amount": "pe.paid_amount", "id": "pe.name", "carrier": "a.account_name"}
    col = sort.get(sort_field, "pe.posting_date")
    d = "ASC" if str(sort_dir).lower() == "asc" else "DESC"
    rows, total, s, ps = _paginate.page_query(
        "`tabPayment Entry` pe JOIN `tabAccount` a ON a.name=pe.paid_to", " AND ".join(conds), params,
        "pe.name, pe.posting_date AS date, a.account_name AS carrier, pe.party AS customer, "
        "IFNULL(NULLIF(pe.reference_no,''),'—') AS reference, ROUND(pe.paid_amount,2) AS amount",
        f"{col} {d}, pe.creation {d}", start, page_size)
    return {"rows": rows, "total": total, "start": s, "page_size": ps}
