"""Re-create the `amended_from` indexes — the right way this time.

v1_add_amended_from_index created them with a plain ALTER TABLE. They lasted
until the next `bench migrate` and then vanished. Frappe's own schema sync does
this, in database/schema.py:

    if (current_def["index"] and not self.set_index) ...:
        self.table.drop_index.append(self)

`set_index` is the DocField's `search_index` flag. A column that carries an index
in the database while its field says search_index = 0 is treated as drift and
dropped. Measured on production: the two COMPOSITE indexes this app created
survived every migrate, and both SINGLE-COLUMN ones were gone — Frappe only looks
up one-column indexes when deciding what to drop.

So the index is not the thing to create: the flag is. With search_index = 1 on
the field, Frappe creates `<fieldname>_index` itself and maintains it from then
on. The ALTER here is only so the index exists before the next migrate rather
than after it, and it uses Frappe's own naming so the sync recognises it instead
of adding a second one.

Why these fields: docops.doc_state runs on every document page and asks "has
anything been amended from this one?" — a full scan of 215,758 rows, 748ms,
measured, on every page open.
"""
import frappe

DOCTYPES = (
    "Sales Order", "Purchase Order", "Delivery Note", "Payment Entry",
    "Sales Invoice", "Purchase Receipt", "Purchase Invoice",
    "Journal Entry", "Additional Salary",
)
FIELD = "amended_from"


def execute():
    for dt in DOCTYPES:
        _index(dt, FIELD)
    frappe.clear_cache()


def _index(doctype, fieldname):
    if not frappe.db.table_exists(doctype) or not frappe.db.has_column(doctype, fieldname):
        return
    frappe.make_property_setter(
        {"doctype": doctype, "fieldname": fieldname, "property": "search_index",
         "value": 1, "property_type": "Check"},
        is_system_generated=True)
    index = fieldname + "_index"
    table = "tab" + doctype
    if frappe.db.sql("SHOW INDEX FROM `%s` WHERE Key_name=%%s" % table, (index,)):
        return
    frappe.db.commit()
    frappe.db.sql("SET SESSION lock_wait_timeout = 20")
    frappe.db.sql("SET SESSION innodb_lock_wait_timeout = 20")
    frappe.db.sql("ALTER TABLE `%s` ADD INDEX `%s` (`%s`), ALGORITHM=INPLACE, LOCK=NONE"
                  % (table, index, fieldname))
    frappe.db.commit()
