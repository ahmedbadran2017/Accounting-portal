"""Index `amended_from` on every doctype the document toolbar can act on.

`docops.doc_state` runs on every document page. To decide whether Amend should
be offered it asks "has anything been amended from this one?":

    frappe.db.get_value(doctype, {"amended_from": name}, "name")

`amended_from` carries no index on any of these tables, so that is a full scan —
215,758 rows and 748ms measured on a Sales Order, on every single page open.
It is the slowest of the seven calls a document page makes, by two orders of
magnitude.

Nine doctypes, the largest being Sales Order at 268k rows, Purchase Order at
220k and Delivery Note at 139k.

Created ALGORITHM=INPLACE, LOCK=NONE so the tables stay readable and writable
throughout, with a short lock timeout so a blocked ALTER fails fast instead of
queueing every reader behind it. Idempotent.
"""
import frappe

DOCTYPES = (
    "Sales Order", "Purchase Order", "Delivery Note", "Payment Entry",
    "Sales Invoice", "Purchase Receipt", "Purchase Invoice",
    "Journal Entry", "Additional Salary",
)

INDEX = "ap_amended_from"


def execute():
    for dt in DOCTYPES:
        table = "tab" + dt
        if not frappe.db.table_exists(dt):
            continue
        if frappe.db.sql("SHOW INDEX FROM `%s` WHERE Key_name=%%s" % table, INDEX):
            continue
        if not frappe.db.has_column(dt, "amended_from"):
            continue
        frappe.db.commit()
        frappe.db.sql("SET SESSION lock_wait_timeout = 20")
        frappe.db.sql("SET SESSION innodb_lock_wait_timeout = 20")
        frappe.db.sql(
            "ALTER TABLE `%s` ADD INDEX `%s` (`amended_from`), ALGORITHM=INPLACE, LOCK=NONE"
            % (table, INDEX))
        frappe.db.commit()
