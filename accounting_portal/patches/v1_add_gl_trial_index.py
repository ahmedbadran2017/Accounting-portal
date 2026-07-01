"""Add a covering index for the portal's trial-balance / chart-of-accounts scans.

Both `ledger.trial_balance` and `ledger.chart_of_accounts` run:

    SELECT gl.account, SUM(gl.debit - gl.credit)
    FROM `tabGL Entry` gl
    WHERE gl.is_cancelled = 0 AND gl.company = %s
    GROUP BY gl.account

with no date filter — a full company scan (~500K rows ≈ 1.8s on Justyol Morocco).
A covering index on (company, is_cancelled, account, debit, credit) lets MySQL
aggregate straight from the index (loose index scan, no table lookup), turning
that into a sub-0.3s read. Idempotent — safe to re-run.
"""
import frappe

INDEX = "ap_company_account_cov"


def execute():
    if frappe.db.sql("SHOW INDEX FROM `tabGL Entry` WHERE Key_name=%s", INDEX):
        return
    frappe.db.commit()
    # Covering index: equality columns first (company, is_cancelled), then the
    # GROUP BY column (account), then the aggregated columns (debit, credit).
    frappe.db.sql(
        "ALTER TABLE `tabGL Entry` "
        "ADD INDEX `ap_company_account_cov` (company, is_cancelled, account, debit, credit)")
    frappe.db.commit()
