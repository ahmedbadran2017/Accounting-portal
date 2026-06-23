"""Customer endpoints — the full COD customer cycle, live from ERPNext.

What the live data looks like (validated June 2026):
  • ~155k customers live in customer_group 'Shopify Group Customer'
    (customer_type Individual). Aggregate/clearing accounts (PAYZONE, DEPOSITE,
    CASH PLUS, the "Justyol … Sales" buckets) sit in OTHER groups, so we scope
    to the Shopify group to show real end-customers.
  • mobile_no / email_id and the custom_rfm_segment / custom_lifecycle_stage /
    loyalty_program_tier fields EXIST but are unpopulated → we COMPUTE the
    segment/lifecycle from orders + LTV + recency instead of reading them.
  • Nothing useful is stored per-customer: LTV, order count, delivery rate, RTO
    and store credit are all derived from Sales Invoice / Sales Order / GL Entry.

Create: a Customer needs only customer_name + group; phone/email/city are
optional and, when given, are written to a linked Contact / the shipping city.
"""
import frappe
from frappe.utils import flt, nowdate

from accounting_portal.api.permissions import assert_portal_access, assert_can_write

REAL_GROUP = "Shopify Group Customer"


def _segment(orders, ltv):
    """Compute an RFM-ish segment (the stored field is empty on live data)."""
    if orders >= 10 or ltv >= 8000:
        return "Loyal · high value"
    if orders >= 4:
        return "Repeat"
    if orders >= 2:
        return "Promising"
    return "New"


def _customer_city(name):
    """Best-effort city — the most recent order's shipping city (Customer has none)."""
    return frappe.db.get_value(
        "Sales Order", {"customer": name, "custom_shipping_city": ["is", "set"]},
        "custom_shipping_city", order_by="transaction_date desc",
    ) or "—"


def _stats(name):
    """Per-customer figures for one customer (indexed on `customer`, so fast).

    LTV = delivered Sales-Order value. In this COD business revenue is realised
    on delivery and is NOT invoiced per end-customer (it lands in the Cathadis
    clearing account), so per-customer Sales-Invoice sums read ~0 — the delivered
    order value is the only meaningful lifetime figure."""
    o = frappe.db.sql(
        """
        SELECT COUNT(*) AS orders,
               SUM(custom_logistics_status='Delivered') AS delivered,
               SUM(custom_track_shipment_status IN ('Delivery Exception','Failed Attempt')) AS exceptions,
               ROUND(SUM(CASE WHEN custom_logistics_status='Delivered' THEN grand_total ELSE 0 END)) AS ltv
        FROM `tabSales Order` WHERE customer=%s AND docstatus=1
        """, (name,), as_dict=True)[0]
    orders, delivered, exceptions = (o.orders or 0), (o.delivered or 0), (o.exceptions or 0)
    # GL party balance: debit−credit. >0 = owes us; <0 = store credit we owe them.
    balance = flt(frappe.db.sql(
        "SELECT COALESCE(SUM(debit-credit),0) FROM `tabGL Entry` WHERE party_type='Customer' AND party=%s AND is_cancelled=0", (name,))[0][0])
    return {
        "orders": orders,
        "delivered": delivered,
        "delivery_rate": round(delivered / orders * 100, 1) if orders else 0,
        "rto_rate": round(exceptions / orders * 100, 1) if orders else 0,
        "ltv": flt(o.ltv),
        "store_credit": -balance if balance < 0 else 0,
        "outstanding": balance if balance > 0 else 0,
    }


# Top-customers ranking is a heavy GROUP BY over every Shopify order (~seconds),
# so it's computed once and cached. HAVING ltv>0 keeps only customers with real
# delivered value — which also drops test/undelivered-spam accounts for free.
TOP_CACHE_KEY = "ap_top_customers"

_TOP_SQL = """
    SELECT so.customer AS name, c.customer_name,
           COUNT(*) AS orders,
           SUM(so.custom_logistics_status='Delivered') AS delivered,
           SUM(so.custom_track_shipment_status IN ('Delivery Exception','Failed Attempt')) AS exceptions,
           ROUND(SUM(CASE WHEN so.custom_logistics_status='Delivered' THEN so.grand_total ELSE 0 END)) AS ltv
    FROM `tabSales Order` so
    JOIN `tabCustomer` c ON c.name = so.customer
    WHERE c.customer_group = %(g)s AND so.docstatus = 1
    GROUP BY so.customer
    HAVING ltv > 0
    ORDER BY ltv DESC
    LIMIT 100
"""


def _row(r, city="—", credit="0"):
    orders, delivered, exceptions = (r["orders"] or 0), (r["delivered"] or 0), (r["exceptions"] or 0)
    return {
        "name": r["name"], "customer_name": r["customer_name"], "city": city,
        "orders": orders, "ltv": f"{int(r['ltv'] or 0):,}",
        "delivery": f"{round(delivered / orders * 100)}%" if orders else "0%",
        "rto": f"{round(exceptions / orders * 100)}%" if orders else "0%",
        "credit": credit,
    }


@frappe.whitelist()
def list_customers(search=None, limit=40):
    """Top real end-customers by delivered order value (the meaningful COD LTV).

    Default view = the cached top-100 ranking. `search` runs a fast name lookup
    instead and computes each match's stats live (few rows)."""
    assert_portal_access()
    limit = min(int(limit or 40), 100)

    if search:
        rows = frappe.db.sql(
            """
            SELECT name, customer_name FROM `tabCustomer`
            WHERE customer_group=%(g)s AND disabled=0 AND customer_name LIKE %(s)s
            ORDER BY modified DESC LIMIT %(limit)s
            """,
            {"g": REAL_GROUP, "s": f"%{search}%", "limit": limit}, as_dict=True)
        out = []
        for r in rows:
            s = _stats(r.name)
            out.append({
                "name": r.name, "customer_name": r.customer_name,
                "city": _customer_city(r.name), "orders": s["orders"],
                "ltv": f"{int(s['ltv']):,}",
                "delivery": f"{s['delivery_rate']:.0f}%", "rto": f"{s['rto_rate']:.0f}%",
                "credit": ("+" + f"{int(s['store_credit']):,}") if s["store_credit"] else "0",
            })
        return out

    cached = frappe.cache().get_value(TOP_CACHE_KEY)
    if cached is None:
        cached = [_row(r) for r in frappe.db.sql(_TOP_SQL, {"g": REAL_GROUP}, as_dict=True)]
        frappe.cache().set_value(TOP_CACHE_KEY, cached, expires_in_sec=3600)
    return cached[:limit]


@frappe.whitelist()
def get_customer(name):
    """Full customer detail: header, computed stats, contact, segment, connections,
    recent activity, and the customer ledger (GL party entries)."""
    assert_portal_access()
    c = frappe.db.get_value(
        "Customer", name,
        ["name", "customer_name", "customer_group", "territory", "mobile_no",
         "email_id", "custom_rfm_segment", "custom_lifecycle_stage",
         "loyalty_program_tier", "creation"], as_dict=True,
    )
    if not c:
        frappe.throw("Customer not found")
    s = _stats(name)
    city = _customer_city(name)

    # Connections — counts of linked documents.
    invoices = frappe.db.count("Sales Invoice", {"customer": name, "docstatus": 1})
    receipts = frappe.db.count("Payment Entry", {"party_type": "Customer", "party": name, "docstatus": 1})
    returns = frappe.db.count("Sales Order", {"customer": name, "custom_sales_status": "Returned"})

    # Customer ledger — recent GL party entries with a running balance.
    ledger = frappe.db.sql(
        """
        SELECT posting_date AS date, voucher_no AS doc, voucher_type AS type,
               debit AS dr, credit AS cr
        FROM `tabGL Entry`
        WHERE party_type='Customer' AND party=%s AND is_cancelled=0
        ORDER BY posting_date DESC, creation DESC LIMIT 8
        """,
        (name,), as_dict=True,
    )

    return {
        "name": c.name, "customer_name": c.customer_name, "city": city,
        "mobile_no": c.mobile_no, "email_id": c.email_id,
        "since": str(c.creation)[:4] if c.creation else "—",
        "store_credit": s["store_credit"], "outstanding": s["outstanding"],
        "stats": {"ltv": s["ltv"], "orders": s["orders"],
                  "delivery_rate": s["delivery_rate"], "rto_rate": s["rto_rate"]},
        # Stored segment/lifecycle are empty on live data → compute + flag.
        "segment": c.custom_rfm_segment or _segment(s["orders"], s["ltv"]),
        "segment_computed": not bool(c.custom_rfm_segment),
        "lifecycle": c.custom_lifecycle_stage or ("Repeat" if s["orders"] > 1 else "New"),
        "loyalty_tier": c.loyalty_program_tier or "—",
        "connections": {"orders": s["orders"], "invoices": invoices, "receipts": receipts, "returns": returns},
        "ledger": ledger,
    }


@frappe.whitelist()
def create_customer(customer_name, phone=None, city=None, email=None):
    """Create a COD customer (Shopify group). Optionally seeds a primary Contact
    with the phone/email. City is informational (lives on the order, not the
    customer) and is returned for the confirmation toast."""
    assert_can_write()
    if not customer_name:
        frappe.throw("Customer name is required")
    doc = frappe.get_doc({
        "doctype": "Customer",
        "customer_name": customer_name,
        "customer_group": REAL_GROUP,
        "customer_type": "Individual",
        "territory": "All Territories",
    }).insert(ignore_permissions=True)

    if phone or email:
        contact = frappe.get_doc({
            "doctype": "Contact", "first_name": customer_name,
            "links": [{"link_doctype": "Customer", "link_name": doc.name}],
        })
        if phone:
            contact.append("phone_nos", {"phone": phone, "is_primary_mobile_no": 1})
        if email:
            contact.append("email_ids", {"email_id": email, "is_primary": 1})
        contact.insert(ignore_permissions=True)

    frappe.db.commit()
    return {"name": doc.name, "customer_name": doc.customer_name, "city": city or "—"}
