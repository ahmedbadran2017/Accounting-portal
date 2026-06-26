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
    # Match an amount too: "1500" finds docs whose grand_total/paid_amount rounds to it.
    amt = None
    try:
        amt = float(q.replace(",", "")) if q.replace(",", "").replace(".", "").isdigit() else None
    except ValueError:
        amt = None

    if target:
        amt_sql = " OR ROUND(grand_total)=%(amt)s" if amt is not None else ""
        pe_amt_sql = " OR ROUND(paid_amount)=%(amt)s" if amt is not None else ""
        je_amt_sql = " OR ROUND(total_debit)=%(amt)s" if amt is not None else ""
        p = {"c": target, "like": like, "n": n, "amt": amt}

        add(frappe.db.sql(f"SELECT name, customer FROM `tabSales Invoice` WHERE company=%(c)s AND (name LIKE %(like)s OR customer LIKE %(like)s{amt_sql}) ORDER BY modified DESC LIMIT %(n)s", p, as_dict=True),
            "Invoice", "receipt", lambda r: {"path": "/accounting/sales/invoices", "query": {"id": r["name"]}},
            lambda r: r["name"], lambda r: r.get("customer"))
        add(frappe.db.sql(f"SELECT name, customer FROM `tabSales Order` WHERE company=%(c)s AND (name LIKE %(like)s OR customer LIKE %(like)s{amt_sql}) ORDER BY modified DESC LIMIT %(n)s", p, as_dict=True),
            "Order", "cart", lambda r: {"path": "/accounting/sales/orders", "query": {"id": r["name"]}},
            lambda r: r["name"], lambda r: r.get("customer"))
        add(frappe.db.sql(f"SELECT name, customer FROM `tabDelivery Note` WHERE company=%(c)s AND (name LIKE %(like)s OR customer LIKE %(like)s{amt_sql}) ORDER BY modified DESC LIMIT %(n)s", p, as_dict=True),
            "Delivery Note", "truck", lambda r: {"path": "/accounting/sales/challans", "query": {"id": r["name"]}},
            lambda r: r["name"], lambda r: r.get("customer"))
        add(frappe.db.sql(f"SELECT name, supplier FROM `tabPurchase Invoice` WHERE company=%(c)s AND (name LIKE %(like)s OR supplier LIKE %(like)s{amt_sql}) ORDER BY modified DESC LIMIT %(n)s", p, as_dict=True),
            "Bill", "doc", lambda r: {"path": "/accounting/purchases/bills", "query": {"id": r["name"]}},
            lambda r: r["name"], lambda r: r.get("supplier"))
        add(frappe.db.sql(f"SELECT name, supplier FROM `tabPurchase Order` WHERE company=%(c)s AND (name LIKE %(like)s OR supplier LIKE %(like)s{amt_sql}) ORDER BY modified DESC LIMIT %(n)s", p, as_dict=True),
            "Purchase Order", "cart", lambda r: {"path": "/accounting/purchases/tobuy", "query": {"id": r["name"]}},
            lambda r: r["name"], lambda r: r.get("supplier"))
        add(frappe.db.sql(f"SELECT name, supplier FROM `tabPurchase Receipt` WHERE company=%(c)s AND (name LIKE %(like)s OR supplier LIKE %(like)s{amt_sql}) ORDER BY modified DESC LIMIT %(n)s", p, as_dict=True),
            "Purchase Receipt", "box", lambda r: {"path": "/accounting/purchases/received", "query": {"id": r["name"]}},
            lambda r: r["name"], lambda r: r.get("supplier"))
        add(frappe.db.sql(f"SELECT name, party FROM `tabPayment Entry` WHERE company=%(c)s AND (name LIKE %(like)s OR party LIKE %(like)s OR reference_no LIKE %(like)s{pe_amt_sql}) ORDER BY modified DESC LIMIT %(n)s", p, as_dict=True),
            "Payment", "coins", lambda r: {"path": "/accounting/purchases/payments", "query": {"id": r["name"]}},
            lambda r: r["name"], lambda r: r.get("party"))
        add(frappe.db.sql(f"SELECT name, title, user_remark FROM `tabJournal Entry` WHERE company=%(c)s AND (name LIKE %(like)s OR title LIKE %(like)s OR user_remark LIKE %(like)s{je_amt_sql}) ORDER BY modified DESC LIMIT %(n)s", p, as_dict=True),
            "Journal", "ledger", lambda r: {"path": "/accounting/accountant/journals", "query": {"id": r["name"]}},
            lambda r: r["name"], lambda r: (r.get("title") or r.get("user_remark") or "Journal Entry"))
    add(frappe.db.sql("SELECT name, item_name, custom_sku FROM `tabItem` WHERE name LIKE %s OR item_name LIKE %s OR IFNULL(custom_sku,'') LIKE %s ORDER BY modified DESC LIMIT %s",
                      (like, like, like, n), as_dict=True),
        "Item", "box", lambda r: {"path": "/accounting/items/items", "query": {"id": r["name"]}},
        lambda r: r.get("item_name") or r["name"], lambda r: r.get("custom_sku") or r["name"])
    return out
