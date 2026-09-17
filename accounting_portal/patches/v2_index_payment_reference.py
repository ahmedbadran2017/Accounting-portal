"""Re-create the Payment Entry `reference_no` index — see v2_index_amended_from
for why the first attempt did not survive a migrate.

The bank reference is what the ⌘K palette matches besides the document id, and
`reference_no` carries no index, so that one query read all 85,968 payments:
274ms of the 851ms a keystroke cost.
"""
import frappe

from accounting_portal.patches.v2_index_amended_from import _index


def execute():
    _index("Payment Entry", "reference_no")
    frappe.clear_cache()
