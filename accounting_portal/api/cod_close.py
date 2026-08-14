"""Cathedis clearing close — book the missing COD collection receipts.

Diagnosis (Justyol Morocco, FY2026): the Cathedis clearing account
(108.021.003) carries a large CREDIT residual because the daily bank-remittance
JEs (Dr Bank / Cr Cathedis) were posted, but the matching per-order collection
Payment Entries (Dr Cathedis / Cr Debtor) were NOT. So thousands of *delivered*
invoices sit UNPAID even though their COD cash reached the bank. The unpaid AR
and the Cathedis credit are the two legs of the same missing Payment Entry.

This pillar rebuilds that missing leg — one Payment Entry per delivered-unpaid
invoice, crediting the customer's Debtors and debiting Cathedis clearing. It
reuses the audited/reversible "Record Payment" action, so every receipt shows in
the Activity log with a working Undo. It NEVER touches the bank (the remittance
already did) and NEVER touches revenue (the invoice already did) — it only moves
Debtors → Cathedis, draining both distortions at once.

Scope guards (all must hold): FY2026, carrier = Cathedis, shipment status =
Delivered, real customer (not the 2025 lump), outstanding > 0, and the invoice is
NOT larger than its source order (the 11 SI>SO anomalies are excluded for manual
review). Receipt date = MAX(invoice date, delivery date) so it never predates the
invoice nor reopens 2025.
"""
import json

import frappe
from frappe.utils import flt, getdate

from accounting_portal.api import _actions
from accounting_portal.api.permissions import (
    assert_can_write, assert_portal_access, resolve_companies)

PE_ACTION = "Record Payment"          # reuse the existing audited+reversible poster
CATHEDIS_PREFIX = "108.021.003"       # Cathedis clearing account
DUMMY_CUSTOMER = "Justyol Morocco Sales 2025"
FY = 2026


def _target(company):
    companies = resolve_companies(company)
    if not companies:
        return None
    return company if (company and company in companies) else companies[0]


def _cathedis_account(target):
    acct = frappe.db.get_value(
        "Account", {"company": target, "name": ["like", f"{CATHEDIS_PREFIX}%"], "is_group": 0}, "name")
    if not acct:
        frappe.throw(f"No Cathedis clearing account ({CATHEDIS_PREFIX}…) found for {target}")
    return acct


def _cathedis_balance(target):
    row = frappe.db.sql(
        """SELECT ROUND(SUM(debit - credit), 2) FROM `tabGL Entry`
           WHERE company=%s AND account LIKE %s AND is_cancelled=0""",
        (target, f"{CATHEDIS_PREFIX}%"))
    return flt(row[0][0]) if row and row[0][0] is not None else 0.0


# The delivered-unpaid worklist. One row per Sales Invoice. Joins its source Sales
# Order (for shipment status, carrier, order value, tracking) and its Delivery
# Note (for the delivery/collection date). GROUP BY the invoice so a multi-line
# invoice yields a single row; a single source SO is required (COD is 1 SO→1 SI).
_WORKLIST_SQL = """
  SELECT si.name AS invoice, si.customer, si.posting_date AS si_date,
         ROUND(si.base_grand_total, 2) AS si_total,
         ROUND(si.outstanding_amount, 2) AS outstanding,
         MAX(so.name) AS sales_order,
         ROUND(MAX(so.base_grand_total), 2) AS so_total,
         MAX(so.custom_tracking_number) AS tracking,
         MAX(dn.posting_date) AS dn_date,
         COUNT(DISTINCT sii.sales_order) AS n_so
  FROM `tabSales Invoice` si
  JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
  JOIN `tabSales Order` so ON so.name = sii.sales_order
  LEFT JOIN `tabDelivery Note Item` dni ON dni.against_sales_order = so.name
  LEFT JOIN `tabDelivery Note` dn ON dn.name = dni.parent AND dn.docstatus = 1
  WHERE si.company = %(c)s AND si.docstatus = 1 AND YEAR(si.posting_date) = %(fy)s
    AND si.customer != %(dummy)s AND si.outstanding_amount > 0.5
    AND so.custom_track_shipment_status = 'Delivered'
    AND IFNULL(so.custom_tracking_company, '') = 'Cathedis'
    {search}
  GROUP BY si.name
  HAVING n_so = 1
"""


def _receipt_date(si_date, dn_date):
    """MAX(invoice date, delivery date) — never predates the invoice, never 2025."""
    si_d = getdate(si_date)
    if dn_date:
        dn_d = getdate(dn_date)
        return (dn_d if dn_d > si_d else si_d).isoformat()
    return si_d.isoformat()


def _classify(r):
    """Tag each row: 'ready' (post it), or 'anomaly' (SI>SO → manual review)."""
    si_t, so_t = flt(r["si_total"]), flt(r["so_total"])
    if si_t > so_t + 5:
        return "anomaly"
    return "ready"


@frappe.whitelist()
def summary(company=None):
    """KPI row for the close screen: Cathedis balance + the worklist totals."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    rows = frappe.db.sql(_WORKLIST_SQL.format(search=""),
                         {"c": target, "fy": FY, "dummy": DUMMY_CUSTOMER}, as_dict=True)
    ready = [r for r in rows if _classify(r) == "ready"]
    anomaly = [r for r in rows if _classify(r) == "anomaly"]
    return {
        "company": target,
        "cathedis_account": _cathedis_account(target),
        "cathedis_balance": _cathedis_balance(target),
        "total_count": len(rows),
        "ready_count": len(ready),
        "ready_value": round(sum(flt(r["outstanding"]) for r in ready), 2),
        "anomaly_count": len(anomaly),
        "anomaly_value": round(sum(flt(r["outstanding"]) for r in anomaly), 2),
    }


@frappe.whitelist()
def worklist(company=None, start=0, page_size=50, search=None, only=None):
    """Paginated delivered-unpaid invoices. `only`='ready'|'anomaly' filters."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {"rows": [], "total": 0}
    params = {"c": target, "fy": FY, "dummy": DUMMY_CUSTOMER}
    sc = ""
    if search:
        sc = "AND (si.name LIKE %(s)s OR si.customer LIKE %(s)s OR so.custom_tracking_number LIKE %(s)s)"
        params["s"] = f"%{search}%"
    rows = frappe.db.sql(_WORKLIST_SQL.format(search=sc), params, as_dict=True)
    for r in rows:
        r["state"] = _classify(r)
        r["pe_date"] = _receipt_date(r["si_date"], r["dn_date"])
        r["si_date"] = str(r["si_date"] or "")
        r["dn_date"] = str(r["dn_date"] or "")
        r["diff"] = round(flt(r["si_total"]) - flt(r["so_total"]), 2)
    if only in ("ready", "anomaly"):
        rows = [r for r in rows if r["state"] == only]
    total = len(rows)
    start, page_size = int(start or 0), min(int(page_size or 50), 500)
    return {"rows": rows[start:start + page_size], "total": total}


def _post_invoice(target, cathedis, r):
    """Post one collection receipt for worklist row `r` via the gated action.
    Returns (status, detail). Skips if already settled (idempotent)."""
    inv = r["invoice"]
    outstanding = flt(frappe.db.get_value("Sales Invoice", inv, "outstanding_amount"))
    if outstanding <= 0.5:
        return ("skipped", "already settled")
    # Belt-and-braces idempotency: if a submitted Payment Entry already references
    # this invoice, don't add a second receipt (covers partial allocations and any
    # concurrent-run race the outstanding check alone would miss).
    if frappe.db.exists("Payment Entry Reference",
                        {"reference_doctype": "Sales Invoice", "reference_name": inv, "docstatus": 1}):
        return ("skipped", "already has a receipt")
    amt = round(outstanding, 2)
    pe_date = _receipt_date(r["si_date"], r["dn_date"])
    ref_no = (r.get("tracking") or "").strip() or f"CATH-{inv}"
    payload = {
        "payment_type": "Receive", "party_type": "Customer", "party": r["customer"],
        "account": cathedis, "amount": amt, "posting_date": pe_date,
        "reference_no": ref_no, "mode": None,
        "references": [{"doctype": "Sales Invoice", "name": inv, "amount": amt}],
    }
    res = _actions.execute(
        PE_ACTION, target, f"codclose:{inv}", payload=payload, amount=amt,
        reference_doctype="Sales Invoice", reference_name=inv,
        notes=f"Cathedis COD collection — {inv} ({r['customer']}) @ {pe_date}")
    return (res.get("status", "?"), res.get("voucher_no") or res.get("result"))


@frappe.whitelist()
def post_one(company=None, invoice=None):
    """Post a single delivered-unpaid invoice's collection receipt (for the sample
    test). Returns the result + the new Cathedis balance."""
    assert_can_write()
    target = _target(company)
    if not target or not invoice:
        frappe.throw("company + invoice required")
    params = {"c": target, "fy": FY, "dummy": DUMMY_CUSTOMER, "s": invoice}
    rows = frappe.db.sql(
        _WORKLIST_SQL.format(search="AND si.name = %(s)s"), params, as_dict=True)
    if not rows:
        frappe.throw(f"{invoice} is not an eligible delivered-unpaid Cathedis invoice")
    r = rows[0]
    if _classify(r) != "ready":
        frappe.throw(f"{invoice} is an anomaly (invoice > order) — excluded from auto-post")
    status, detail = _post_invoice(target, _cathedis_account(target), r)
    return {"invoice": invoice, "status": status, "detail": detail,
            "cathedis_balance": _cathedis_balance(target)}


@frappe.whitelist()
def post_batch(company=None, limit=25):
    """Post up to `limit` READY receipts in one call. Returns per-invoice results
    plus before/after Cathedis balance. The frontend calls this repeatedly (small
    batches) so progress is visible and any failure is isolated, not fatal."""
    assert_can_write()
    target = _target(company)
    if not target:
        frappe.throw("company required")
    cathedis = _cathedis_account(target)
    before = _cathedis_balance(target)
    limit = min(int(limit or 25), 500)
    rows = frappe.db.sql(_WORKLIST_SQL.format(search=""),
                         {"c": target, "fy": FY, "dummy": DUMMY_CUSTOMER}, as_dict=True)
    rows = [r for r in rows if _classify(r) == "ready"][:limit]
    results, posted, failed, skipped = [], 0, 0, 0
    for r in rows:
        try:
            status, detail = _post_invoice(target, cathedis, r)
        except Exception:
            status, detail = "failed", frappe.get_traceback().splitlines()[-1][:200]
            frappe.db.rollback()
        if status == "Posted":
            posted += 1
        elif status == "skipped":
            skipped += 1
        else:
            failed += 1
        results.append({"invoice": r["invoice"], "customer": r["customer"],
                        "amount": flt(r["outstanding"]), "status": status, "detail": detail})
    return {
        "posted": posted, "failed": failed, "skipped": skipped,
        "cathedis_before": before, "cathedis_after": _cathedis_balance(target),
        "results": results,
    }
