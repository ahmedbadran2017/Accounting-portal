"""Two indexes the portal's busiest list queries had nothing to stand on.

Both were applied to production on 2026-09-17 and are recorded here so a rebuilt
site, a DEV clone or a fresh install gets them too. Idempotent.

1. `tabSales Order (company, transaction_date, creation)`

   The orders list runs:

       SELECT ... FROM `tabSales Order`
       WHERE company = %s AND docstatus < 2
       ORDER BY transaction_date DESC, creation DESC
       LIMIT 25

   with no index on `company` at all — a full scan of 268K rows and a filesort
   for every page (type=ALL, 252ms measured).

   The third column matters. A two-column (company, transaction_date) index was
   tried first and made it WORSE, 252ms to 1,118ms: the optimizer switched to a
   range scan over 107K index entries and still had to filesort, because the
   second ORDER BY key was not in the index. Adding `creation` lets the index
   serve the whole sort. The filesort disappears and the page query drops below
   a millisecond.

2. `tabToDo (allocated_to, status)`

   The header notification bell reads a user's open assignments. `tabToDo` is
   375K rows indexed only on name / modified / reference, so this was a full
   scan on every page load. The team's heaviest users carry 20-36K open todos
   each. Full scan of 375,646 rows becomes a ref lookup of 3.

Both are created ALGORITHM=INPLACE, LOCK=NONE so the tables stay readable and
writable throughout; each took about a second on production.
"""
import frappe

INDEXES = (
    ("tabSales Order", "ap_so_company_date_creation", "`company`, `transaction_date`, `creation`"),
    ("tabToDo", "ap_todo_owner_status", "`allocated_to`, `status`"),
)


def execute():
    for table, name, cols in INDEXES:
        if frappe.db.sql("SHOW INDEX FROM `%s` WHERE Key_name=%%s" % table, name):
            continue
        frappe.db.commit()
        # Fail fast instead of queueing behind — or in front of — a long
        # transaction holding the table. A blocked ALTER blocks every reader
        # after it, which is how a metadata lock takes a site down.
        frappe.db.sql("SET SESSION lock_wait_timeout = 20")
        frappe.db.sql("SET SESSION innodb_lock_wait_timeout = 20")
        frappe.db.sql(
            "ALTER TABLE `%s` ADD INDEX `%s` (%s), ALGORITHM=INPLACE, LOCK=NONE"
            % (table, name, cols))
        frappe.db.commit()
