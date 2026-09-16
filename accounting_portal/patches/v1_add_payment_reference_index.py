"""Index `reference_no` on Payment Entry — the bank reference the ⌘K palette searches.

Every keystroke in the palette runs one query per document table. Seven of them
answer in 0ms off the primary key; Payment Entry took 274ms, because it also
matches the bank reference and `reference_no` carries no index at all. Anchored
or not made no difference: without an index every predicate on that column reads
the whole table.

Created ALGORITHM=INPLACE, LOCK=NONE so the table stays readable and writable
throughout, with a short lock timeout so a blocked ALTER fails fast instead of
queueing every reader behind it. Idempotent.
"""
import frappe

INDEX = "ap_pe_reference_no"


def execute():
    if not frappe.db.table_exists("Payment Entry"):
        return
    if frappe.db.sql("SHOW INDEX FROM `tabPayment Entry` WHERE Key_name=%s", INDEX):
        return
    if not frappe.db.has_column("Payment Entry", "reference_no"):
        return
    frappe.db.commit()
    frappe.db.sql("SET SESSION lock_wait_timeout = 20")
    frappe.db.sql("SET SESSION innodb_lock_wait_timeout = 20")
    frappe.db.sql(
        "ALTER TABLE `tabPayment Entry` ADD INDEX `%s` (`reference_no`), "
        "ALGORITHM=INPLACE, LOCK=NONE" % INDEX)
    frappe.db.commit()
