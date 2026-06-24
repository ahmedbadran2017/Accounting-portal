"""Sales · COD endpoints — live ERPNext, entity-scoped.

Sales Order carries the COD lifecycle (custom_sales_status / custom_logistics_
status / custom_track_shipment_status / custom_tracking_company /
custom_shipping_city). Sales Invoice = revenue recognised on delivery (VAT 20%).
Every list is scoped to one company and excludes cancelled documents.
"""
import frappe
from frappe.utils import flt, getdate, nowdate

from accounting_portal.api.permissions import assert_portal_access, resolve_companies


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


@frappe.whitelist()
def list_orders(company=None, state=None, search=None, limit=100, customer=None):
    """COD sales orders for one company (newest first), excluding cancelled docs.
    Optional `state` filters by the mapped portal state; `search` matches the
    order id or customer; `customer` restricts to one customer exactly."""
    assert_portal_access()
    companies = resolve_companies(company)
    if not companies:
        return []
    target = company if (company and company in companies) else companies[0]
    limit = min(int(limit or 100), 500)

    conds = ["so.company = %(company)s", "so.docstatus < 2"]
    params = {"company": target, "limit": limit}
    if customer:
        conds.append("so.customer = %(customer)s")
        params["customer"] = customer
    if search:
        conds.append("(so.name LIKE %(s)s OR so.customer LIKE %(s)s)")
        params["s"] = f"%{search}%"
    rows = frappe.db.sql(
        f"""
        SELECT so.name, so.customer, so.grand_total AS value, so.status,
               so.transaction_date AS date, so.custom_sales_status,
               so.custom_logistics_status, so.custom_track_shipment_status,
               so.custom_tracking_company AS carrier, so.custom_shipping_city AS city
        FROM `tabSales Order` so
        WHERE {' AND '.join(conds)}
        ORDER BY so.transaction_date DESC, so.creation DESC
        LIMIT %(limit)s
        """,
        params, as_dict=True,
    )
    # The order's own custom_shipping_city is ~empty; backfill from the
    # customer's most-recent Address (one bulk query) so the City column is real.
    from accounting_portal.api.customers import _cities_for
    missing = list({r["customer"] for r in rows if not (r.get("city") or "").strip()})
    cities = _cities_for(missing) if missing else {}
    for r in rows:
        r["state"] = _order_state(r)
        r["value"] = flt(r["value"])
        if not (r.get("city") or "").strip():
            r["city"] = cities.get(r["customer"]) or ""
    if state:
        rows = [r for r in rows if r["state"] == state]
    return rows


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
def list_receipts(company=None, limit=100):
    """COD receipts (Payment Entry · Receive) for one company — the cash landing."""
    assert_portal_access()
    companies = resolve_companies(company)
    if not companies:
        return []
    target = company if (company and company in companies) else companies[0]
    return frappe.db.sql(
        """
        SELECT name, party AS customer, IFNULL(NULLIF(reference_no, ''), '—') AS ref,
               IFNULL(NULLIF(mode_of_payment, ''), '—') AS method, paid_amount AS collected,
               posting_date AS date
        FROM `tabPayment Entry`
        WHERE company=%s AND docstatus=1 AND payment_type='Receive'
        ORDER BY posting_date DESC, creation DESC LIMIT %s
        """,
        (target, min(int(limit or 100), 500)), as_dict=True)


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
         "custom_channel", "advance_paid", "per_billed", "per_delivered"],
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
    # Backfill city/phone from the customer's Address/Contact (the order's own
    # custom fields are largely empty on live data).
    from accounting_portal.api.customers import _customer_city, _customer_contact
    if not (so.get("custom_shipping_city") or "").strip():
        c = _customer_city(so["customer"])
        so["custom_shipping_city"] = "" if c == "—" else c
    if not (so.get("custom_customer_phone") or so.get("custom_shipping_phone") or "").strip():
        so["custom_customer_phone"] = _customer_contact(so["customer"])["phone"] or ""
    so["journal"] = _voucher_journal(name)
    return so


@frappe.whitelist()
def list_invoices(company=None, search=None, limit=100):
    """Sales invoices for one company (revenue; VAT 20%), excluding cancelled."""
    assert_portal_access()
    companies = resolve_companies(company)
    if not companies:
        return []
    target = company if (company and company in companies) else companies[0]
    limit = min(int(limit or 100), 500)
    conds = ["si.company = %(company)s", "si.docstatus < 2"]
    params = {"company": target, "limit": limit}
    if search:
        conds.append("(si.name LIKE %(s)s OR si.customer LIKE %(s)s)")
        params["s"] = f"%{search}%"
    return frappe.db.sql(
        f"""
        SELECT si.name, si.customer, si.net_total AS net,
               si.total_taxes_and_charges AS vat, si.grand_total AS gross,
               si.status, si.posting_date AS date, si.outstanding_amount
        FROM `tabSales Invoice` si
        WHERE {' AND '.join(conds)}
        ORDER BY si.posting_date DESC, si.creation DESC
        LIMIT %(limit)s
        """,
        params, as_dict=True,
    )


@frappe.whitelist()
def get_invoice(name):
    """One invoice: header, line items, totals, payment status, posted journal."""
    assert_portal_access()
    si = frappe.db.get_value(
        "Sales Invoice", name,
        ["name", "customer", "company", "net_total", "total_taxes_and_charges",
         "grand_total", "status", "posting_date", "outstanding_amount"], as_dict=True,
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
