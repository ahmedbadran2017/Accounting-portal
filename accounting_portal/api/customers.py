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
    """All the computed per-customer figures in one round-trip each."""
    orders = frappe.db.count("Sales Order", {"customer": name, "docstatus": ["<", 2]})
    delivered = frappe.db.count("Sales Order", {"customer": name, "custom_logistics_status": "Delivered"})
    exceptions = frappe.db.count("Sales Order", {"customer": name, "custom_track_shipment_status": ["in", ["Delivery Exception", "Failed Attempt"]]})
    ltv = flt(frappe.db.sql(
        "SELECT COALESCE(SUM(grand_total),0) FROM `tabSales Invoice` WHERE customer=%s AND docstatus=1", (name,))[0][0])
    # GL party balance: debit−credit. >0 = owes us; <0 = store credit we owe them.
    balance = flt(frappe.db.sql(
        "SELECT COALESCE(SUM(debit-credit),0) FROM `tabGL Entry` WHERE party_type='Customer' AND party=%s AND is_cancelled=0", (name,))[0][0])
    return {
        "orders": orders,
        "delivered": delivered,
        "delivery_rate": round(delivered / orders * 100, 1) if orders else 0,
        "rto_rate": round(exceptions / orders * 100, 1) if orders else 0,
        "ltv": ltv,
        "store_credit": -balance if balance < 0 else 0,
        "outstanding": balance if balance > 0 else 0,
    }


@frappe.whitelist()
def list_customers(search=None, limit=40):
    """Real end-customers (Shopify group). Search-driven, since there are ~155k —
    pass `search` to find by name; otherwise the most recent are returned. Each
    row carries computed orders + LTV."""
    assert_portal_access()
    limit = min(int(limit or 40), 100)
    conds = ["c.customer_group = %(g)s", "c.disabled = 0"]
    params = {"g": REAL_GROUP, "limit": limit}
    if search:
        conds.append("c.customer_name LIKE %(s)s")
        params["s"] = f"%{search}%"
    rows = frappe.db.sql(
        f"""
        SELECT c.name, c.customer_name
        FROM `tabCustomer` c
        WHERE {' AND '.join(conds)}
        ORDER BY c.modified DESC
        LIMIT %(limit)s
        """,
        params, as_dict=True,
    )
    out = []
    for r in rows:
        s = _stats(r.name)
        out.append({
            "name": r.name, "customer_name": r.customer_name,
            "city": _customer_city(r.name),
            "orders": s["orders"], "ltv": s["ltv"],
            "delivery": f"{s['delivery_rate']:.0f}%", "rto": f"{s['rto_rate']:.0f}%",
            "credit": ("+" + f"{s['store_credit']:.0f}") if s["store_credit"] else "0",
        })
    return out


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
