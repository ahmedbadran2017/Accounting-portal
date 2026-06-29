"""Shared server-side pagination helper for the list endpoints.

Each list runs one COUNT and one bounded SELECT (LIMIT/OFFSET) for the requested
page, so the UI fetches a page at a time at high speed instead of pulling up to
500 rows and paginating in the browser.
"""
import frappe


def page_query(from_sql, where, params, fields, order_by, start=0, page_size=25, max_ps=100):
    """Return (rows, total, start, page_size) for one page.

    from_sql: the table + alias (and any JOINs), e.g. "`tabSales Invoice` si".
    where:    the WHERE body (without the keyword), referencing %(...)s in params.
    fields:   the SELECT list. order_by: the ORDER BY body.
    """
    start = max(0, int(start or 0))
    page_size = min(max(1, int(page_size or 25)), max_ps)
    total = frappe.db.sql(f"SELECT COUNT(*) FROM {from_sql} WHERE {where}", params)[0][0]
    p = {**params, "_ps": page_size, "_st": start}
    rows = frappe.db.sql(
        f"SELECT {fields} FROM {from_sql} WHERE {where} ORDER BY {order_by} "
        "LIMIT %(_ps)s OFFSET %(_st)s", p, as_dict=True)
    return rows, total, start, page_size
