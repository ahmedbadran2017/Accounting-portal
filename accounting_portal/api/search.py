"""Global search — find any document/party/SKU from the ⌘K palette and jump to
its portal page, so the team never searches in ERPNext."""
import frappe

from accounting_portal.api.permissions import assert_portal_access, resolve_companies


def _target(company):
    companies = resolve_companies(company)
    if not companies:
        return None
    return company if (company and company in companies) else companies[0]


@frappe.whitelist()
def global_search(company=None, query=None, limit=5):
    """Search the core doctypes by name/id and return jump targets for the palette."""
    assert_portal_access()
    q = (query or "").strip()
    if len(q) < 2:
        return []
    target = _target(company)
    like = f"%{q}%"
    n = min(int(limit or 5), 8)
    out = []

    def add(rows, typ, icon, route_fn, label_fn, sub_fn=None):
        for r in rows:
            out.append({"key": f"{typ}-{r['name']}", "type": typ, "icon": icon,
                        "label": label_fn(r), "sub": sub_fn(r) if sub_fn else r["name"],
                        "to": route_fn(r)})

    add(frappe.db.sql("SELECT name, customer_name FROM `tabCustomer` WHERE name LIKE %s OR customer_name LIKE %s ORDER BY modified DESC LIMIT %s",
                      (like, like, n), as_dict=True),
        "Customer", "user", lambda r: {"path": "/accounting/sales/customers", "query": {"id": r["name"]}},
        lambda r: r.get("customer_name") or r["name"])
    add(frappe.db.sql("SELECT name, supplier_name FROM `tabSupplier` WHERE name LIKE %s OR supplier_name LIKE %s ORDER BY modified DESC LIMIT %s",
                      (like, like, n), as_dict=True),
        "Supplier", "building", lambda r: {"path": "/accounting/purchases/vendors", "query": {"id": r["name"]}},
        lambda r: r.get("supplier_name") or r["name"])
    if target:
        add(frappe.db.sql("SELECT name, customer FROM `tabSales Invoice` WHERE company=%s AND name LIKE %s ORDER BY modified DESC LIMIT %s",
                          (target, like, n), as_dict=True),
            "Invoice", "receipt", lambda r: {"path": "/accounting/sales/invoices", "query": {"id": r["name"]}},
            lambda r: r["name"], lambda r: r.get("customer"))
        add(frappe.db.sql("SELECT name, customer FROM `tabSales Order` WHERE company=%s AND name LIKE %s ORDER BY modified DESC LIMIT %s",
                          (target, like, n), as_dict=True),
            "Order", "cart", lambda r: {"path": "/accounting/sales/orders", "query": {"id": r["name"]}},
            lambda r: r["name"], lambda r: r.get("customer"))
        add(frappe.db.sql("SELECT name, supplier FROM `tabPurchase Invoice` WHERE company=%s AND name LIKE %s ORDER BY modified DESC LIMIT %s",
                          (target, like, n), as_dict=True),
            "Bill", "doc", lambda r: {"path": "/accounting/purchases/bills", "query": {"id": r["name"]}},
            lambda r: r["name"], lambda r: r.get("supplier"))
        add(frappe.db.sql("SELECT name, party FROM `tabPayment Entry` WHERE company=%s AND (name LIKE %s OR reference_no LIKE %s) ORDER BY modified DESC LIMIT %s",
                          (target, like, like, n), as_dict=True),
            "Payment", "coins", lambda r: {"path": "/accounting/purchases/payments", "query": {"id": r["name"]}},
            lambda r: r["name"], lambda r: r.get("party"))
    add(frappe.db.sql("SELECT name, item_name, custom_sku FROM `tabItem` WHERE name LIKE %s OR item_name LIKE %s OR IFNULL(custom_sku,'') LIKE %s ORDER BY modified DESC LIMIT %s",
                      (like, like, like, n), as_dict=True),
        "Item", "box", lambda r: {"path": "/accounting/items/items", "query": {"id": r["name"]}},
        lambda r: r.get("item_name") or r["name"], lambda r: r.get("custom_sku") or r["name"])
    return out
