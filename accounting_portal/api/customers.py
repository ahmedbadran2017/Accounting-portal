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


def _norm_city(c):
    """Tidy the messy Shopify city strings (casa/CASA → Casa) for display."""
    c = (c or "").strip()
    if not c:
        return "—"
    # Title-case latin; leave Arabic/other scripts untouched.
    return c.title() if c.isascii() else c


def _customer_city(name):
    """City from the customer's most-recent linked Address (the real source —
    the order custom_shipping_city field is ~empty; Address.city is populated)."""
    row = frappe.db.sql(
        """SELECT a.city FROM `tabAddress` a
           JOIN `tabDynamic Link` dl ON dl.parent=a.name AND dl.parenttype='Address'
             AND dl.link_doctype='Customer' AND dl.link_name=%s
           WHERE a.city IS NOT NULL AND a.city != ''
           ORDER BY a.modified DESC LIMIT 1""", (name,))
    return _norm_city(row[0][0]) if row else "—"


def _customer_contact(name):
    """Phone + email from the customer's linked Contact (the Customer doc's own
    mobile_no/email_id are empty on live data — the values live on the Contact)."""
    row = frappe.db.sql(
        """SELECT COALESCE(NULLIF(ct.mobile_no,''), NULLIF(ct.phone,'')) AS phone,
                  ct.email_id AS email, ct.name AS contact
           FROM `tabContact` ct
           JOIN `tabDynamic Link` dl ON dl.parent=ct.name AND dl.parenttype='Contact'
             AND dl.link_doctype='Customer' AND dl.link_name=%s
           ORDER BY ct.modified DESC LIMIT 1""", (name,), as_dict=True)
    if not row:
        return {"phone": None, "email": None, "contact": None}
    r = row[0]
    # phone may also sit only in the child Contact Phone table.
    phone = r.phone
    if not phone and r.contact:
        phone = frappe.db.get_value(
            "Contact Phone", {"parent": r.contact}, "phone",
            order_by="is_primary_mobile_no desc")
    return {"phone": phone, "email": r.email, "contact": r.contact}


def _cities_for(names):
    """Bulk most-recent city for many customers in one query (for the top list)."""
    if not names:
        return {}
    rows = frappe.db.sql(
        """SELECT dl.link_name AS customer,
                  SUBSTRING_INDEX(GROUP_CONCAT(a.city ORDER BY a.modified DESC SEPARATOR '||'), '||', 1) AS city
           FROM `tabAddress` a
           JOIN `tabDynamic Link` dl ON dl.parent=a.name AND dl.parenttype='Address'
             AND dl.link_doctype='Customer'
           WHERE dl.link_name IN %(names)s AND a.city IS NOT NULL AND a.city != ''
           GROUP BY dl.link_name""",
        {"names": tuple(names)}, as_dict=True)
    return {r.customer: _norm_city(r.city) for r in rows}


def _tags(orders, delivery_rate, rto_rate, ltv):
    """Attractive, always-fresh customer tags computed from behaviour (no stored
    doctype needed — these are 100% derivable and would only go stale if cached).
    Returns tone keys; the frontend maps them to a localized label + colour."""
    tags = []
    if (delivery_rate < 50 and orders >= 3) or rto_rate >= 10:
        tags.append("risk")
    if ltv >= 8000 or orders >= 20:
        tags.append("vip")
    elif orders >= 10 and delivery_rate >= 70:
        tags.append("loyal")
    elif orders >= 4:
        tags.append("returning")
    elif orders <= 2:
        tags.append("new")
    return tags[:2]


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
TOP_CACHE_KEY = "ap_top_customers_v2"  # bump when the row shape changes

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
    dr = (delivered / orders * 100) if orders else 0
    rr = (exceptions / orders * 100) if orders else 0
    return {
        "name": r["name"], "customer_name": r["customer_name"], "city": city,
        "orders": orders, "ltv": f"{int(r['ltv'] or 0):,}",
        "delivery": f"{round(dr)}%", "rto": f"{round(rr)}%",
        "credit": credit, "tags": _tags(orders, dr, rr, flt(r["ltv"] or 0)),
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
                "tags": _tags(s["orders"], s["delivery_rate"], s["rto_rate"], s["ltv"]),
            })
        return out

    cached = frappe.cache().get_value(TOP_CACHE_KEY)
    if cached is None:
        top = frappe.db.sql(_TOP_SQL, {"g": REAL_GROUP}, as_dict=True)
        cities = _cities_for([r["name"] for r in top])
        cached = [_row(r, city=cities.get(r["name"], "—")) for r in top]
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
    contact = _customer_contact(name)
    phone = contact["phone"] or c.mobile_no or None
    email = contact["email"] or c.email_id or None

    # Connections — counts of linked documents.
    invoices = frappe.db.count("Sales Invoice", {"customer": name, "docstatus": 1})
    receipts = frappe.db.count("Payment Entry", {"party_type": "Customer", "party": name, "docstatus": 1})
    returns = frappe.db.count("Sales Order", {"customer": name, "custom_sales_status": "Returned"})

    # Customer ledger — recent GL party entries with a running balance. We pull
    # the latest rows, then walk them oldest→newest from the current party
    # balance to show a real running balance per line.
    ledger = frappe.db.sql(
        """
        SELECT posting_date AS date, voucher_no AS doc, voucher_type AS type,
               debit AS dr, credit AS cr
        FROM `tabGL Entry`
        WHERE party_type='Customer' AND party=%s AND is_cancelled=0
        ORDER BY posting_date DESC, creation DESC LIMIT 10
        """,
        (name,), as_dict=True,
    )
    running = s["outstanding"] - s["store_credit"]  # net party balance (dr−cr)
    for e in ledger:  # newest first: show balance after the row, then unwind
        e["balance"] = round(running, 2)
        running -= (flt(e["dr"]) - flt(e["cr"]))

    return {
        "name": c.name, "customer_name": c.customer_name, "city": city,
        "mobile_no": phone, "email_id": email, "contact": contact["contact"],
        "customer_group": c.customer_group, "territory": c.territory,
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


def _default_territory():
    """A valid territory for new customers (root if no company default)."""
    return frappe.db.get_single_value("Selling Settings", "territory") \
        or frappe.db.get_value("Territory", {"is_group": 0}, "name") \
        or "All Territories"


def _upsert_contact(customer, name, phone, email):
    """Create or update the customer's primary Contact with phone/email."""
    existing = _customer_contact(customer)["contact"]
    contact = frappe.get_doc("Contact", existing) if existing else frappe.get_doc({
        "doctype": "Contact", "first_name": name or customer,
        "links": [{"link_doctype": "Customer", "link_name": customer}],
    })
    if phone:
        contact.set("phone_nos", [{"phone": phone, "is_primary_mobile_no": 1, "is_primary_phone": 1}])
    if email:
        contact.set("email_ids", [{"email_id": email, "is_primary": 1}])
    contact.flags.ignore_mandatory = True
    contact.save(ignore_permissions=True) if existing else contact.insert(ignore_permissions=True)


def _upsert_city(customer, name, city):
    """Create or update the customer's primary Address city."""
    existing = frappe.db.sql(
        """SELECT a.name FROM `tabAddress` a
           JOIN `tabDynamic Link` dl ON dl.parent=a.name AND dl.parenttype='Address'
             AND dl.link_doctype='Customer' AND dl.link_name=%s
           ORDER BY a.modified DESC LIMIT 1""", (customer,))
    if existing:
        frappe.db.set_value("Address", existing[0][0], "city", city)
    else:
        frappe.get_doc({
            "doctype": "Address", "address_title": name or customer,
            "address_type": "Shipping", "city": city, "address_line1": city,
            "links": [{"link_doctype": "Customer", "link_name": customer}],
        }).insert(ignore_permissions=True)


@frappe.whitelist()
def create_customer(customer_name, phone=None, city=None, email=None):
    """Create a COD customer (Shopify group) + seed Contact (phone/email) and
    Address (city). Errors propagate so the UI can show the real reason."""
    assert_can_write()
    customer_name = (customer_name or "").strip()
    if not customer_name:
        frappe.throw("Customer name is required")
    doc = frappe.get_doc({
        "doctype": "Customer",
        "customer_name": customer_name,
        "customer_group": REAL_GROUP,
        "customer_type": "Individual",
        "territory": _default_territory(),
    }).insert(ignore_permissions=True)
    if phone or email:
        _upsert_contact(doc.name, customer_name, phone, email)
    if city:
        _upsert_city(doc.name, customer_name, city)
    frappe.db.commit()
    return {"name": doc.name, "customer_name": doc.customer_name, "city": city or "—"}


@frappe.whitelist()
def update_customer(name, customer_name=None, phone=None, email=None, city=None):
    """Edit a customer's core data: name on the Customer; phone/email on its
    Contact; city on its Address. Only the provided fields are touched."""
    assert_can_write()
    if not name or not frappe.db.exists("Customer", name):
        frappe.throw("Customer not found")
    if customer_name and customer_name.strip():
        frappe.db.set_value("Customer", name, "customer_name", customer_name.strip())
    if phone or email:
        _upsert_contact(name, customer_name, phone, email)
    if city and city.strip() and city.strip() != "—":
        _upsert_city(name, customer_name, city.strip())
    frappe.db.commit()
    return get_customer(name)
