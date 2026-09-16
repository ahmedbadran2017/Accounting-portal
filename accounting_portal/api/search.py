"""Global search — find any document, party or SKU from the ⌘K palette and jump
to its portal page, so the team never searches in ERPNext.

Two things were wrong with the first version and both made it useless in
practice. It scoped every document query to ONE company, chosen as the first of
the user's allowed companies in alphabetical order — Justyol China, which holds
almost nothing — so searching from the group view returned nothing at all. And
it matched document ids with a leading wildcard, `name LIKE '%q%'`, which no
index can serve: 4.2 seconds across seven tables, against 0ms for the anchored
form. A document id is unique across the group, so there is no reason to scope
it to a company and no reason not to anchor it.
"""
import frappe

from accounting_portal.api.permissions import assert_portal_access, resolve_companies

# (label, icon, table, party column, route) — searched in this order.
_DOCS = [
    ("Invoice", "receipt", "Sales Invoice", "customer", "/accounting/sales/invoices"),
    ("Order", "cart", "Sales Order", "customer", "/accounting/sales/orders"),
    ("Bill", "doc", "Purchase Invoice", "supplier", "/accounting/purchases/bills"),
    ("Payment", "coins", "Payment Entry", "party", "/accounting/purchases/payments"),
    ("Delivery Note", "truck", "Delivery Note", "customer", "/accounting/sales/challans"),
    ("Journal", "ledger", "Journal Entry", None, "/accounting/accountant/journals"),
    ("Purchase Order", "cart", "Purchase Order", "supplier", "/accounting/purchases/tobuy"),
    ("Purchase Receipt", "box", "Purchase Receipt", "supplier", "/accounting/purchases/received"),
]


@frappe.whitelist()
def global_search(company=None, query=None, limit=5):
    """Search parties, documents and items by id, name or reference."""
    assert_portal_access()
    q = (query or "").strip()
    if len(q) < 2:
        return []
    comps = resolve_companies(company) or []
    if not comps:
        return []
    n = min(int(limit or 5), 8)
    like = f"%{q}%"
    out = []

    def add(rows, typ, icon, path, label_key, sub_key=None):
        for r in rows:
            out.append({"key": f"{typ}-{r['name']}", "type": typ, "icon": icon,
                        "label": r.get(label_key) or r["name"],
                        "sub": (r.get(sub_key) if sub_key else None) or r["name"],
                        "to": {"path": path, "query": {"id": r["name"]}}})

    # Parties first: this is what a name-shaped query is almost always after,
    # and both tables are small enough for a contains match.
    add(frappe.db.sql("SELECT name, customer_name FROM `tabCustomer` WHERE name LIKE %s OR customer_name LIKE %s ORDER BY modified DESC LIMIT %s",
                      (like, like, n), as_dict=True),
        "Customer", "user", "/accounting/sales/customers", "customer_name")
    add(frappe.db.sql("SELECT name, supplier_name FROM `tabSupplier` WHERE name LIKE %s OR supplier_name LIKE %s ORDER BY modified DESC LIMIT %s",
                      (like, like, n), as_dict=True),
        "Supplier", "building", "/accounting/purchases/vendors", "supplier_name")

    amt = None
    bare = q.replace(",", "").replace(".", "")
    if bare.isdigit():
        try:
            amt = float(q.replace(",", ""))
        except ValueError:
            amt = None

    # An id-shaped query — a digit or a '#', no spaces — is never a party name,
    # and searching the party columns for it costs 2.8s of leading-wildcard scan
    # for nothing. Skipping them takes the same search to 3ms.
    id_like = " " not in q and (q.startswith("#") or any(ch.isdigit() for ch in q))

    ph = ", ".join(["%s"] * len(comps))
    for typ, icon, table, party, path in _DOCS:
        conds, params = [], list(comps)
        # Anchored on the id so the primary key serves it. Frappe ids are
        # prefixed by series, so a prefix match is what an accountant types.
        conds.append("name LIKE %s"); params.append(f"{q}%")
        if party and not id_like:
            conds.append(f"`{party}` LIKE %s"); params.append(like)
        if table == "Payment Entry":
            # A bank reference IS id-shaped, so this one stays either way.
            conds.append("reference_no LIKE %s"); params.append(like)
        if table == "Journal Entry" and not id_like:
            conds.append("title LIKE %s"); params.append(like)
            conds.append("user_remark LIKE %s"); params.append(like)
        if amt is not None:
            col = {"Payment Entry": "paid_amount", "Journal Entry": "total_debit"}.get(table, "grand_total")
            conds.append(f"ROUND({col})=%s"); params.append(amt)
        params.append(n)
        sel = "name" + (f", `{party}` AS party_label" if party else "")
        rows = frappe.db.sql(
            f"SELECT {sel} FROM `tab{table}` WHERE company IN ({ph}) AND ({' OR '.join(conds)}) "
            f"ORDER BY modified DESC LIMIT %s", params, as_dict=True)
        add(rows, typ, icon, path, "name", "party_label" if party else None)

    add(frappe.db.sql("SELECT name, item_name, custom_sku FROM `tabItem` WHERE name LIKE %s OR item_name LIKE %s OR IFNULL(custom_sku,'') LIKE %s ORDER BY modified DESC LIMIT %s",
                      (like, like, like, n), as_dict=True),
        "Item", "box", "/accounting/items/items", "item_name", "custom_sku")
    return out
