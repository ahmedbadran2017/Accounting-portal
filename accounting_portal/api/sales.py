"""Sales · COD endpoints — live ERPNext, entity-scoped.

Sales Order carries the COD lifecycle (custom_sales_status / custom_logistics_
status / custom_track_shipment_status / custom_tracking_company /
custom_shipping_city). Sales Invoice = revenue recognised on delivery (VAT 20%).
Every list is scoped to one company and excludes cancelled documents.
"""
import json

import frappe
from frappe.utils import add_days, flt, getdate, nowdate

from accounting_portal.api import _actions, _paginate
from accounting_portal.api.permissions import assert_can_write, assert_portal_access, resolve_companies

SO_ACTION = "Create Sales Order"


def _month_start():
    return getdate(nowdate()).replace(day=1).isoformat()


@frappe.whitelist()
def orders_summary(company=None, since=None):
    """CFO order metrics for one company since `since` (default: month-to-date):
    GMV, order count, AOV, the COD funnel, realised (delivered) value, and the
    delivery / RTO rates. The numbers behind the orders list's summary strip."""
    assert_portal_access()
    companies = resolve_companies(company)
    if not companies:
        return {}
    target = company if (company and company in companies) else companies[0]
    since = since or _month_start()
    r = frappe.db.sql(
        """
        SELECT COUNT(*) AS total, ROUND(SUM(grand_total)) AS gmv, ROUND(AVG(grand_total)) AS aov,
               SUM(custom_logistics_status='Delivered') AS delivered,
               SUM(custom_logistics_status='Shipped') AS in_transit,
               SUM(custom_logistics_status='Pending') AS pending,
               SUM(custom_track_shipment_status IN ('Delivery Exception','Failed Attempt')
                   OR custom_sales_status='Returned' OR custom_logistics_status='Returned') AS exceptions,
               ROUND(SUM(CASE WHEN custom_logistics_status='Delivered' THEN grand_total ELSE 0 END)) AS delivered_value
        FROM `tabSales Order`
        WHERE company=%s AND docstatus=1 AND transaction_date >= %s
        """,
        (target, since), as_dict=True)[0]
    total = r.total or 0
    return {
        "company": target, "since": since,
        "orders": total, "gmv": flt(r.gmv), "aov": flt(r.aov),
        "delivered": r.delivered or 0, "in_transit": r.in_transit or 0, "pending": r.pending or 0,
        "exceptions": r.exceptions or 0, "delivered_value": flt(r.delivered_value),
        "delivery_rate": round((r.delivered or 0) / total * 100, 1) if total else 0,
        "rto_rate": round((r.exceptions or 0) / total * 100, 1) if total else 0,
    }


# ── COD state machine ──
# Map the raw ERPNext COD fields onto the portal's state vocabulary
# (placed → confirmed → transit → delivered → settled, plus cancelled /
# undelivered). Kept server-side so the list and detail agree.
def _order_state(row):
    sales = (row.get("custom_sales_status") or "").strip()
    logi = (row.get("custom_logistics_status") or "").strip()
    track = (row.get("custom_track_shipment_status") or "").strip()
    status = (row.get("status") or "").strip()

    if sales in ("Cancelled", "Duplicated") or status == "Cancelled":
        return "cancelled"
    if track in ("Delivery Exception", "Failed Attempt"):
        return "undelivered"
    if logi == "Delivered" or track == "Delivered":
        # Billed + paid → settled, otherwise just delivered.
        return "settled" if status in ("Completed", "Closed") else "delivered"
    if logi == "Shipped":
        return "transit"
    if sales == "Confirmed":
        return "confirmed"
    return "placed"


# SQL mirror of _order_state so the list can filter / sort / count / paginate on
# state server-side, instead of pulling everything and bucketing in the browser.
_STATE_CASE = """CASE
  WHEN (so.custom_sales_status IN ('Cancelled','Duplicated') OR so.status='Cancelled') THEN 'cancelled'
  WHEN so.custom_track_shipment_status IN ('Delivery Exception','Failed Attempt') THEN 'undelivered'
  WHEN (so.custom_logistics_status='Delivered' OR so.custom_track_shipment_status='Delivered')
       THEN (CASE WHEN so.status IN ('Completed','Closed') THEN 'settled' ELSE 'delivered' END)
  WHEN so.custom_logistics_status='Shipped' THEN 'transit'
  WHEN so.custom_sales_status='Confirmed' THEN 'confirmed'
  ELSE 'placed' END"""

_SORT_COLS = {"date": "so.transaction_date", "value": "so.grand_total",
              "customer": "so.customer", "id": "so.name"}


@frappe.whitelist()
def list_orders(company=None, state=None, search=None, customer=None, active=0,
                start=0, page_size=25, sort_field="date", sort_dir="desc"):
    """Server-paginated COD sales orders. Returns one page (start/page_size) plus
    the total count and per-state counts for the pipeline strip — so the UI pages
    through the full set at high speed instead of capping at a client-side 500."""
    assert_portal_access()
    companies = resolve_companies(company)
    if not companies:
        return {"rows": [], "total": 0, "state_counts": {}}
    target = company if (company and company in companies) else companies[0]
    start = max(0, int(start or 0))
    page_size = min(max(1, int(page_size or 25)), 100)

    conds = ["so.company = %(company)s", "so.docstatus < 2"]
    params = {"company": target}
    if customer:
        conds.append("so.customer = %(customer)s"); params["customer"] = customer
    if search:
        conds.append("(so.name LIKE %(s)s OR so.customer LIKE %(s)s)"); params["s"] = f"%{search}%"
    base_where = " AND ".join(conds)

    state_where = base_where
    if state:
        state_where += f" AND {_STATE_CASE} = %(state)s"; params["state"] = state
    elif int(active or 0):
        state_where += f" AND {_STATE_CASE} NOT IN ('placed','cancelled')"

    total = frappe.db.sql(f"SELECT COUNT(*) FROM `tabSales Order` so WHERE {state_where}", params)[0][0]
    state_counts = {r[0]: r[1] for r in frappe.db.sql(
        f"SELECT {_STATE_CASE} st, COUNT(*) FROM `tabSales Order` so WHERE {base_where} GROUP BY st", params)}

    col = _SORT_COLS.get(sort_field, "so.transaction_date")
    direction = "ASC" if str(sort_dir).lower() == "asc" else "DESC"
    params["ps"] = page_size
    params["st"] = start
    rows = frappe.db.sql(
        f"""SELECT so.name, so.customer, so.grand_total AS value, so.status,
                   so.transaction_date AS date, so.custom_sales_status,
                   so.custom_logistics_status, so.custom_track_shipment_status,
                   so.custom_tracking_company AS carrier, so.custom_shipping_city AS city,
                   {_STATE_CASE} AS state
            FROM `tabSales Order` so WHERE {state_where}
            ORDER BY {col} {direction}, so.creation {direction}
            LIMIT %(ps)s OFFSET %(st)s""", params, as_dict=True)

    # Per-page backfill (only this page's rows): city from the customer Address,
    # carrier/track from the linked Delivery Note when the order's own are empty.
    from accounting_portal.api.customers import _cities_for
    missing = list({r["customer"] for r in rows if not (r.get("city") or "").strip()})
    cities = _cities_for(missing) if missing else {}
    ship = _dn_shipment_for([r["name"] for r in rows])
    for r in rows:
        r["value"] = flt(r["value"])
        if not (r.get("city") or "").strip():
            r["city"] = cities.get(r["customer"]) or ""
        s = ship.get(r["name"])
        if s:
            if not (r.get("carrier") or "").strip():
                r["carrier"] = s.get("carrier") or r.get("carrier")
            if not (r.get("custom_track_shipment_status") or "").strip():
                r["custom_track_shipment_status"] = s.get("track") or r.get("custom_track_shipment_status")
    return {"rows": rows, "total": total, "start": start, "page_size": page_size,
            "state_counts": state_counts}


def _dn_shipment_for(order_names):
    """Latest Delivery Note carrier/track per Sales Order (one bulk query)."""
    names = [n for n in (order_names or []) if n]
    if not names:
        return {}
    rows = frappe.db.sql(
        """SELECT dni.against_sales_order AS so,
                  dn.custom_tracking_company AS carrier,
                  dn.custom_track_shipment_status AS track, dn.name AS dn
           FROM `tabDelivery Note Item` dni
           JOIN `tabDelivery Note` dn ON dn.name = dni.parent
           WHERE dni.against_sales_order IN %(names)s AND dn.docstatus = 1
           ORDER BY dn.posting_date DESC, dn.creation DESC""",
        {"names": tuple(names)}, as_dict=True)
    out = {}
    for d in rows:
        out.setdefault(d.so, {"carrier": d.carrier, "track": d.track, "dn": d.dn})
    return out


@frappe.whitelist()
def list_challans(company=None, limit=100):
    """Delivery Notes (COD challans) for one company — carrier, tracking, status."""
    assert_portal_access()
    companies = resolve_companies(company)
    if not companies:
        return []
    target = company if (company and company in companies) else companies[0]
    return frappe.db.sql(
        """
        SELECT name, customer, posting_date AS date,
               IFNULL(NULLIF(custom_tracking_company, ''), '—') AS carrier,
               IFNULL(NULLIF(custom_tracking_number, ''), '—') AS tracking,
               IFNULL(NULLIF(custom_track_shipment_status, ''), IFNULL(custom_logistics_status, status)) AS status,
               custom_tracking_url AS tracking_url
        FROM `tabDelivery Note`
        WHERE company=%s AND docstatus=1
        ORDER BY posting_date DESC, creation DESC LIMIT %s
        """,
        (target, min(int(limit or 100), 500)), as_dict=True)


@frappe.whitelist()
def challans_summary(company=None):
    """Insights for the Delivery challans tab — month-to-date delivery funnel."""
    assert_portal_access()
    companies = resolve_companies(company)
    if not companies:
        return {}
    target = company if (company and company in companies) else companies[0]
    r = frappe.db.sql(
        """
        SELECT COUNT(*) AS total,
               SUM(custom_track_shipment_status='Delivered' OR custom_logistics_status='Delivered') AS delivered,
               SUM(custom_track_shipment_status IN ('In Transit','Out For Delivery') OR custom_logistics_status='Shipped') AS in_transit,
               SUM(custom_track_shipment_status IN ('Delivery Exception','Failed Attempt') OR custom_logistics_status='Returned') AS exceptions
        FROM `tabDelivery Note`
        WHERE company=%s AND docstatus=1 AND posting_date >= %s
        """,
        (target, _month_start()), as_dict=True)[0]
    total = r.total or 0
    return {
        "company": target, "total": total, "delivered": r.delivered or 0,
        "in_transit": r.in_transit or 0, "exceptions": r.exceptions or 0,
        "delivery_rate": round((r.delivered or 0) / total * 100, 1) if total else 0,
    }


@frappe.whitelist()
def list_receipts(company=None, search=None, start=0, page_size=25, sort_field="date", sort_dir="desc"):
    """COD receipts (Payment Entry · Receive) for one company — the cash landing,
    server-paginated."""
    assert_portal_access()
    companies = resolve_companies(company)
    if not companies:
        return {"rows": [], "total": 0}
    target = company if (company and company in companies) else companies[0]
    conds = ["pe.company=%(c)s", "pe.docstatus=1", "pe.payment_type='Receive'"]
    params = {"c": target}
    if search:
        conds.append("(pe.name LIKE %(s)s OR pe.party LIKE %(s)s OR IFNULL(pe.reference_no,'') LIKE %(s)s)")
        params["s"] = f"%{search}%"
    sort = {"date": "pe.posting_date", "collected": "pe.paid_amount", "customer": "pe.party", "id": "pe.name"}
    col = sort.get(sort_field, "pe.posting_date")
    d = "ASC" if str(sort_dir).lower() == "asc" else "DESC"
    where = " AND ".join(conds)
    rows, total, s, ps = _paginate.page_query(
        "`tabPayment Entry` pe", where, params,
        "pe.name, pe.party AS customer, IFNULL(NULLIF(pe.reference_no,''),'—') AS ref, "
        "IFNULL(NULLIF(pe.mode_of_payment,''),'—') AS method, pe.paid_amount AS collected, pe.posting_date AS date",
        f"{col} {d}, pe.creation {d}", start, page_size)
    # KPI totals over the WHOLE filtered set (Received / Avg / via-Cathedis share).
    summ = frappe.db.sql(
        f"""SELECT IFNULL(SUM(pe.paid_amount),0) total,
                   SUM(CASE WHEN pe.mode_of_payment LIKE '%%ath%%' THEN 1 ELSE 0 END) cath
            FROM `tabPayment Entry` pe WHERE {where}""", params, as_dict=True)[0]
    return {"rows": rows, "total": total, "start": s, "page_size": ps,
            "summary": {"count": total, "total": flt(summ.total),
                        "avg": (flt(summ.total) / total) if total else 0, "cath": int(summ.cath or 0)}}


@frappe.whitelist()
def list_credits(company=None, limit=100):
    """Returns / credit notes — COD orders returned or in delivery exception.
    There are no per-customer Sales-Invoice returns in this book; the revenue
    reversal lives on the order, so that's the real credit-note source."""
    assert_portal_access()
    companies = resolve_companies(company)
    if not companies:
        return []
    target = company if (company and company in companies) else companies[0]
    return frappe.db.sql(
        """
        SELECT name, customer,
               CASE WHEN custom_logistics_status='Returned' OR custom_sales_status='Returned'
                    THEN 'Returned' ELSE custom_track_shipment_status END AS reason,
               transaction_date AS date, ROUND(grand_total) AS amount
        FROM `tabSales Order`
        WHERE company=%s AND docstatus=1
          AND (custom_sales_status='Returned' OR custom_logistics_status='Returned'
               OR custom_track_shipment_status IN ('Delivery Exception','Failed Attempt'))
        ORDER BY transaction_date DESC, creation DESC LIMIT %s
        """,
        (target, min(int(limit or 100), 500)), as_dict=True)


@frappe.whitelist()
def get_order(name):
    """One order: header, COD operational fields, and the live posted journal."""
    assert_portal_access()
    so = frappe.db.get_value(
        "Sales Order", name,
        ["name", "customer", "company", "grand_total", "net_total",
         "total_taxes_and_charges", "status", "transaction_date",
         "custom_sales_status", "custom_logistics_status",
         "custom_track_shipment_status", "custom_tracking_company",
         "custom_shipping_city", "custom_shipping_governorate",
         "custom_shipping_phone", "custom_customer_phone",
         "custom_tracking_number", "custom_awb", "custom_tracking_url",
         "custom_channel", "advance_paid", "per_billed", "per_delivered",
         "custom_reference_number"],
        as_dict=True,
    )
    if not so:
        frappe.throw("Order not found")
    if so.company not in resolve_companies():
        frappe.throw("Not permitted", frappe.PermissionError)
    so["state"] = _order_state(so)
    so["items"] = frappe.db.sql(
        """SELECT soi.item_name AS name, soi.item_code, soi.qty, soi.rate, soi.amount, i.image
           FROM `tabSales Order Item` soi
           LEFT JOIN `tabItem` i ON i.name = soi.item_code
           WHERE soi.parent = %s ORDER BY soi.idx""",
        (name,), as_dict=True,
    )
    so["related_invoices"] = [r.name for r in frappe.db.sql(
        "SELECT DISTINCT parent AS name FROM `tabSales Invoice Item` WHERE sales_order=%s ORDER BY parent", (name,), as_dict=True)]
    so["related_deliveries"] = [r.name for r in frappe.db.sql(
        "SELECT DISTINCT parent AS name FROM `tabDelivery Note Item` WHERE against_sales_order=%s ORDER BY parent", (name,), as_dict=True)]
    # Payments that settled this order's invoices.
    if so["related_invoices"]:
        so["related_payments"] = [r.name for r in frappe.db.sql(
            """SELECT DISTINCT per.parent AS name FROM `tabPayment Entry Reference` per
               JOIN `tabPayment Entry` pe ON pe.name = per.parent
               WHERE per.reference_doctype='Sales Invoice' AND per.reference_name IN %(inv)s
                 AND pe.docstatus=1 ORDER BY per.parent""",
            {"inv": tuple(so["related_invoices"])}, as_dict=True)]
    else:
        so["related_payments"] = []
    # Cathedis remittance ref — on the Sales Order, else on a matched invoice
    # (the book's reconciliation stamps custom_reference_number on either).
    ref = (so.get("custom_reference_number") or "").strip()
    if not ref.upper().startswith("CATH") and so["related_invoices"]:
        hit = frappe.db.sql(
            """SELECT MAX(custom_reference_number) FROM `tabSales Invoice`
               WHERE name IN %(inv)s AND IFNULL(custom_reference_number,'') LIKE 'CATH%%'""",
            {"inv": tuple(so["related_invoices"])})
        if hit and hit[0][0]:
            ref = hit[0][0]
    so["remittance_ref"] = ref if ref.upper().startswith("CATH") else ""
    # Backfill city/phone from the customer's Address/Contact (the order's own
    # custom fields are largely empty on live data).
    from accounting_portal.api.customers import _customer_city, _customer_contact
    if not (so.get("custom_shipping_city") or "").strip():
        c = _customer_city(so["customer"])
        so["custom_shipping_city"] = "" if c == "—" else c
    if not (so.get("custom_customer_phone") or so.get("custom_shipping_phone") or "").strip():
        so["custom_customer_phone"] = _customer_contact(so["customer"])["phone"] or ""
    # Carrier / track status from the linked Delivery Note when the order is bare.
    sh = _dn_shipment_for([name]).get(name)
    if sh:
        if not (so.get("custom_tracking_company") or "").strip():
            so["custom_tracking_company"] = sh.get("carrier")
        if not (so.get("custom_track_shipment_status") or "").strip():
            so["custom_track_shipment_status"] = sh.get("track")
    so["journal"] = _voucher_journal(name)
    return so


_INV_SORT = {"date": "si.posting_date", "gross": "si.grand_total", "customer": "si.customer",
             "id": "si.name", "outstanding": "si.outstanding_amount"}


@frappe.whitelist()
def list_invoices(company=None, search=None, start=0, page_size=25, sort_field="date", sort_dir="desc"):
    """Sales invoices for one company (revenue; VAT 20%), server-paginated."""
    assert_portal_access()
    companies = resolve_companies(company)
    if not companies:
        return {"rows": [], "total": 0}
    target = company if (company and company in companies) else companies[0]
    conds = ["si.company = %(company)s", "si.docstatus < 2"]
    params = {"company": target}
    if search:
        conds.append("(si.name LIKE %(s)s OR si.customer LIKE %(s)s)")
        params["s"] = f"%{search}%"
    col = _INV_SORT.get(sort_field, "si.posting_date")
    d = "ASC" if str(sort_dir).lower() == "asc" else "DESC"
    where = " AND ".join(conds)
    rows, total, s, ps = _paginate.page_query(
        "`tabSales Invoice` si", where, params,
        "si.name, si.customer, si.net_total AS net, si.total_taxes_and_charges AS vat, "
        "si.grand_total AS gross, si.status, si.posting_date AS date, si.due_date, "
        "si.outstanding_amount, si.is_return, si.currency, si.docstatus",
        f"{col} {d}, si.creation {d}", start, page_size)
    # KPI totals over the WHOLE filtered set (not just this page).
    summ = frappe.db.sql(
        f"""SELECT IFNULL(SUM(si.net_total),0) net, IFNULL(SUM(si.total_taxes_and_charges),0) vat,
                   SUM(CASE WHEN si.docstatus=1 AND si.outstanding_amount>0
                            AND si.due_date IS NOT NULL AND si.due_date < CURDATE() THEN 1 ELSE 0 END) overdue
            FROM `tabSales Invoice` si WHERE {where}""", params, as_dict=True)[0]
    return {"rows": rows, "total": total, "start": s, "page_size": ps,
            "summary": {"count": total, "net": flt(summ.net), "vat": flt(summ.vat),
                        "overdue": int(summ.overdue or 0)}}


@frappe.whitelist()
def get_invoice(name):
    """One invoice: header, line items, totals, payment status, posted journal."""
    assert_portal_access()
    si = frappe.db.get_value(
        "Sales Invoice", name,
        ["name", "customer", "company", "net_total", "total_taxes_and_charges",
         "grand_total", "status", "posting_date", "due_date", "outstanding_amount",
         "is_return", "currency", "docstatus"], as_dict=True,
    )
    if not si:
        frappe.throw("Invoice not found")
    if si.company not in resolve_companies():
        frappe.throw("Not permitted", frappe.PermissionError)
    si["lines"] = frappe.db.sql(
        """SELECT sii.item_name AS name, sii.item_code, sii.qty, sii.rate, sii.amount, i.image
           FROM `tabSales Invoice Item` sii
           LEFT JOIN `tabItem` i ON i.name = sii.item_code
           WHERE sii.parent = %s ORDER BY sii.idx""",
        (name,), as_dict=True,
    )
    si["paid"] = flt(si.outstanding_amount) <= 0
    si["related_orders"] = [r.name for r in frappe.db.sql(
        "SELECT DISTINCT sales_order AS name FROM `tabSales Invoice Item` WHERE parent=%s AND IFNULL(sales_order,'')!=''", (name,), as_dict=True)]
    si["related_deliveries"] = [r.name for r in frappe.db.sql(
        "SELECT DISTINCT delivery_note AS name FROM `tabSales Invoice Item` WHERE parent=%s AND IFNULL(delivery_note,'')!=''", (name,), as_dict=True)]
    si["related_payments"] = [r.name for r in frappe.db.sql(
        """SELECT DISTINCT parent AS name FROM `tabPayment Entry Reference`
           WHERE reference_doctype='Sales Invoice' AND reference_name=%s""", (name,), as_dict=True)]
    from accounting_portal.api.customers import _customer_city, _customer_contact
    si["city"] = _customer_city(si["customer"])
    si["phone"] = _customer_contact(si["customer"])["phone"] or ""
    si["journal"] = _voucher_journal(name)
    return si


@frappe.whitelist()
def to_bill_queue(company=None, search=None, limit=300):
    """Delivered-but-not-invoiced delivery notes — the revenue-recognition gap.
    Returns the queue + total exposure + aging by days since delivery."""
    assert_portal_access()
    companies = resolve_companies(company)
    if not companies:
        return {"rows": [], "summary": {}}
    target = company if (company and company in companies) else companies[0]
    ccy = frappe.db.get_value("Company", target, "default_currency") or "MAD"
    base = "company=%(c)s AND docstatus=1 AND status='To Bill'"
    params = {"c": target, "limit": min(int(limit or 300), 1000)}
    where = base
    if search:
        where += " AND (name LIKE %(s)s OR customer LIKE %(s)s)"
        params["s"] = f"%{search}%"
    rows = frappe.db.sql(
        f"""SELECT name, customer, posting_date AS date, ROUND(base_grand_total) AS value,
                   DATEDIFF(CURDATE(), posting_date) AS age,
                   IFNULL(NULLIF(custom_tracking_company,''),'—') AS carrier
            FROM `tabDelivery Note` WHERE {where}
            ORDER BY posting_date ASC LIMIT %(limit)s""", params, as_dict=True)
    s = frappe.db.sql(
        f"""SELECT COUNT(*) AS n, ROUND(SUM(base_grand_total)) AS val,
                   SUM(DATEDIFF(CURDATE(),posting_date)<=7) AS w1,
                   SUM(DATEDIFF(CURDATE(),posting_date) BETWEEN 8 AND 30) AS w2,
                   SUM(DATEDIFF(CURDATE(),posting_date) BETWEEN 31 AND 60) AS w3,
                   SUM(DATEDIFF(CURDATE(),posting_date)>60) AS w4,
                   ROUND(SUM(CASE WHEN DATEDIFF(CURDATE(),posting_date)>60 THEN base_grand_total ELSE 0 END)) AS val_w4
            FROM `tabDelivery Note` WHERE {base}""", {"c": target}, as_dict=True)[0]
    return {
        "rows": rows,
        "summary": {
            "company": target, "currency": ccy, "count": s.n or 0, "value": flt(s.val),
            "aging": {"w1": s.w1 or 0, "w2": s.w2 or 0, "w3": s.w3 or 0, "w4": s.w4 or 0},
            "value_over_60": flt(s.val_w4),
        },
    }


@frappe.whitelist()
def get_challan(name):
    """One Delivery Note: header, carrier/tracking, line items, linked SO/SI."""
    assert_portal_access()
    dn = frappe.db.get_value(
        "Delivery Note", name,
        ["name", "customer", "company", "posting_date", "grand_total", "status",
         "custom_tracking_company", "custom_tracking_number", "custom_tracking_url",
         "custom_track_shipment_status", "custom_logistics_status"], as_dict=True)
    if not dn:
        frappe.throw("Delivery note not found")
    if dn.company not in resolve_companies():
        frappe.throw("Not permitted", frappe.PermissionError)
    dn["carrier"] = dn.get("custom_tracking_company") or "—"
    dn["tracking"] = dn.get("custom_tracking_number") or "—"
    dn["tracking_url"] = dn.get("custom_tracking_url") or ""
    dn["ship_status"] = dn.get("custom_track_shipment_status") or dn.get("custom_logistics_status") or dn.get("status")
    dn["lines"] = frappe.db.sql(
        """SELECT dni.item_name AS name, dni.item_code, dni.qty, dni.rate, dni.amount,
                  dni.custom_sku AS sku, i.image
           FROM `tabDelivery Note Item` dni
           LEFT JOIN `tabItem` i ON i.name = dni.item_code
           WHERE dni.parent = %s ORDER BY dni.idx""", (name,), as_dict=True)
    dn["related_orders"] = [r.name for r in frappe.db.sql(
        "SELECT DISTINCT against_sales_order AS name FROM `tabDelivery Note Item` WHERE parent=%s AND IFNULL(against_sales_order,'')!=''", (name,), as_dict=True)]
    dn["related_invoices"] = [r.name for r in frappe.db.sql(
        "SELECT DISTINCT against_sales_invoice AS name FROM `tabDelivery Note Item` WHERE parent=%s AND IFNULL(against_sales_invoice,'')!=''", (name,), as_dict=True)]
    from accounting_portal.api.customers import _customer_city, _customer_contact
    dn["city"] = _customer_city(dn["customer"])
    dn["phone"] = _customer_contact(dn["customer"])["phone"] or ""
    return dn


def _voucher_journal(voucher_no):
    """The live GL postings for a voucher (the auto-posted journal)."""
    return frappe.db.sql(
        """
        SELECT account AS acc, debit AS dr, credit AS cr, party
        FROM `tabGL Entry`
        WHERE voucher_no = %s AND is_cancelled = 0
        ORDER BY CASE WHEN debit > 0 THEN 0 ELSE 1 END, account
        """,
        (voucher_no,), as_dict=True,
    )


@frappe.whitelist()
def item_options(company=None, search=None, limit=20):
    """Items for the Sales Order create picker — code, name, image, last sell rate."""
    assert_portal_access()
    like = f"%{(search or '').strip()}%"
    return frappe.db.sql(
        """SELECT i.name AS item_code, i.item_name, i.image,
                  (SELECT price_list_rate FROM `tabItem Price` ip
                     WHERE ip.item_code=i.name AND ip.selling=1 ORDER BY ip.modified DESC LIMIT 1) AS rate
           FROM `tabItem` i
           WHERE i.disabled=0 AND (i.name LIKE %(s)s OR i.item_name LIKE %(s)s)
           ORDER BY i.modified DESC LIMIT %(limit)s""",
        {"s": like, "limit": min(int(limit or 20), 40)}, as_dict=True)


def _so_poster(action):
    """Create + submit a COD Sales Order from the action payload."""
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    company = action.company
    dd = p.get("delivery_date") or add_days(nowdate(), 3)
    wh = p.get("warehouse") or frappe.db.get_value(
        "Warehouse", {"company": company, "is_group": 0, "disabled": 0}, "name")
    so = frappe.get_doc({
        "doctype": "Sales Order",
        "company": company,
        "customer": p["customer"],
        "transaction_date": p.get("posting_date") or nowdate(),
        "delivery_date": dd,
        "order_type": "Sales",
        "ignore_pricing_rule": 1,
        "set_warehouse": wh,
        "items": [{
            "item_code": it["item_code"], "qty": flt(it.get("qty") or 1),
            "rate": flt(it.get("rate")), "delivery_date": dd, "warehouse": wh,
        } for it in (p.get("items") or [])],
    })
    # COD operational fields — only set the ones that exist on this site.
    for fld, val in (("custom_shipping_city", p.get("city")), ("custom_customer_phone", p.get("phone")),
                     ("custom_tracking_company", p.get("carrier")),
                     ("custom_sales_status", "Pending"), ("custom_logistics_status", "Pending")):
        if val and so.meta.has_field(fld):
            so.set(fld, val)
    # VAT 20% template rows.
    tpl = p.get("tax_template")
    if tpl and frappe.db.exists("Sales Taxes and Charges Template", tpl):
        from erpnext.controllers.accounts_controller import get_taxes_and_charges
        so.taxes_and_charges = tpl
        so.set("taxes", [])
        for t in get_taxes_and_charges("Sales Taxes and Charges Template", tpl):
            so.append("taxes", t)
    so.insert(ignore_permissions=True)
    # A Justyol hook updates the order right after insert (COD status fields), so
    # reload to the latest timestamp before submit to avoid TimestampMismatchError.
    so.reload()
    so.submit()
    return {"voucher_type": "Sales Order", "voucher_no": so.name, "result": "submitted"}


_actions.register_poster(SO_ACTION, _so_poster)


@frappe.whitelist()
def create_sales_order(company=None, customer=None, items=None, city=None, phone=None,
                       carrier=None, delivery_date=None, dedupe_key=None):
    """Create a COD Sales Order through the write gateway (audited; ≥ threshold
    needs an approver). `items`: [{item_code, qty, rate}, …]."""
    assert_can_write()
    companies = resolve_companies(company)
    if not companies:
        frappe.throw("No company in scope")
    target = company if (company and company in companies) else companies[0]
    if not customer:
        frappe.throw("Select a customer")
    if isinstance(items, str):
        items = json.loads(items)
    items = [it for it in (items or []) if it.get("item_code") and flt(it.get("qty")) > 0]
    if not items:
        frappe.throw("Add at least one item")
    net = sum(flt(it.get("qty")) * flt(it.get("rate")) for it in items)
    gross = round(net * 1.2, 2)  # COD orders carry VAT 20%
    tax_tpl = frappe.db.get_value(
        "Sales Taxes and Charges Template", {"company": target, "is_default": 1}, "name")
    key = dedupe_key or f"so:{target}:{customer}:{nowdate()}:{round(gross, 2)}"
    payload = {"customer": customer, "items": items, "city": city, "phone": phone,
               "carrier": carrier, "delivery_date": delivery_date, "tax_template": tax_tpl}
    return _actions.execute(SO_ACTION, target, key, payload=payload, amount=gross,
                            notes=f"Sales Order for {customer} ({gross:,.0f})")


SR_ACTION = "Sales Return"


def _sr_poster(action):
    """Build + submit a credit note (return Sales Invoice) against the original —
    reverses revenue and clears the customer's debtor balance."""
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    make = frappe.get_attr("erpnext.accounts.doctype.sales_invoice.sales_invoice.make_sales_return")
    ret = make(p.get("invoice"))
    # This book's make_sales_return mis-sets amended_from to the source invoice,
    # which blocks insert ("cannot be amended … not cancelled"). A return is not
    # an amendment — clear it so the credit note gets its own name. (Verified by a
    # reversible test on admin-dev: CN posts Dr Revenue+VAT / Cr Debtors.)
    ret.amended_from = None
    if p.get("reason"):
        ret.remarks = ("Refund: " + str(p["reason"]))[:500]
    ret.flags.ignore_permissions = True
    ret.insert()
    ret.reload()
    ret.submit()
    return {"voucher_type": "Sales Invoice", "voucher_no": ret.name, "result": "credit_note"}


_actions.register_poster(SR_ACTION, _sr_poster)


@frappe.whitelist()
def create_sales_return(company=None, invoice=None, reason=None, dedupe_key=None):
    """Create a return Sales Invoice (credit note) against an original — the
    financial reversal behind a refund. Through the write gateway (audited; a
    large refund needs an approver)."""
    assert_can_write()
    companies = resolve_companies(company)
    if not companies:
        frappe.throw("No company in scope")
    target = company if (company and company in companies) else companies[0]
    if not invoice or not frappe.db.exists("Sales Invoice", invoice):
        frappe.throw("Invoice not found")
    si = frappe.db.get_value("Sales Invoice", invoice,
                             ["company", "docstatus", "is_return", "grand_total"], as_dict=True)
    if si.company != target:
        frappe.throw("Invoice belongs to another company")
    if si.docstatus != 1:
        frappe.throw("Only a submitted invoice can be returned")
    if si.is_return:
        frappe.throw("This is already a credit note")
    if frappe.db.exists("Sales Invoice", {"return_against": invoice, "docstatus": 1}):
        frappe.throw("A credit note already exists for this invoice")
    key = dedupe_key or f"sireturn:{target}:{invoice}"
    return _actions.execute(
        SR_ACTION, target, key, payload={"invoice": invoice, "reason": reason},
        reference_doctype="Sales Invoice", reference_name=invoice, amount=flt(si.grand_total),
        notes=f"Credit note for {invoice} ({flt(si.grand_total):,.0f})")


# ── Bill a Delivery Note (recognise delivered-but-unbilled revenue) ──────────
BILL_DN_ACTION = "Bill Delivery Note"


def _bill_dn_poster(action):
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    si = frappe.get_attr(
        "erpnext.stock.doctype.delivery_note.delivery_note.make_sales_invoice")(p["delivery_note"])
    si.update_stock = 0  # the Delivery Note already moved stock — don't double-update
    si.flags.ignore_permissions = True
    si.insert()
    si.reload()
    if p.get("submit", 1):
        si.submit()
    return {"voucher_type": "Sales Invoice", "voucher_no": si.name,
            "result": {"from_dn": p["delivery_note"], "grand_total": flt(si.grand_total)}}


_actions.register_poster(BILL_DN_ACTION, _bill_dn_poster)


@frappe.whitelist()
def bill_delivery_note(company=None, delivery_note=None, submit=1, dedupe_key=None):
    """Create + submit a Sales Invoice from a delivered-but-unbilled Delivery Note —
    closes the revenue-recognition gap the To-Bill queue surfaces."""
    assert_can_write()
    companies = resolve_companies(company)
    target = company if (company and company in companies) else (companies[0] if companies else None)
    if not target or not delivery_note or not frappe.db.exists("Delivery Note", delivery_note):
        frappe.throw("Delivery Note not found")
    dn = frappe.db.get_value("Delivery Note", delivery_note,
                             ["company", "docstatus", "per_billed", "grand_total"], as_dict=True)
    if dn.company != target:
        frappe.throw("Delivery Note belongs to another company")
    if dn.docstatus != 1:
        frappe.throw("Delivery Note is not submitted")
    if flt(dn.per_billed) >= 100:
        frappe.throw("Already fully billed")
    res = _actions.execute(BILL_DN_ACTION, target, dedupe_key or f"billdn:{delivery_note}",
                           payload={"delivery_note": delivery_note, "submit": int(submit or 0)},
                           amount=flt(dn.grand_total), reference_doctype="Delivery Note",
                           reference_name=delivery_note, notes=f"Invoice for {delivery_note}")
    return res
