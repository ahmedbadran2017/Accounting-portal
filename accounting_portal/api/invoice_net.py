"""Invoice safety net — no delivered Cathedis parcel stays without an invoice.

How an order is invoiced today (two hooks that live outside this app):

  1. manifest submit — codx_erp's CustomShipment.on_submit enqueues
     create_draft_sales_invoices_for_shipment: one DRAFT invoice per delivery
     note on the manifest, dated the submit day.
  2. carrier says 'Livré' — ecommerce_integrations' Shipment Tracking
     update_delivered_status submits the delivery note's draft invoices and
     posts the COD Payment Entry into Cathedis clearing.

Step 2 only submits drafts; it never creates one, and it runs once per status
change. Measured 10 Oct 2026, 2,345 delivered orders (460K MAD) had no invoice:
  * the step-1 background job silently never ran for whole manifests
    (SH-000245 466 notes, SH-000250 343, SH-000264 239, SH-000304 320 → 0 drafts);
  * a manifest submitted after its parcels were delivered (SH-000289/294 on
    6 Oct) creates drafts after step 2 already fired — nobody submits them.

No polling (the owner wants no load on the server): two event hooks, each a
single indexed lookup, that enqueue work only for the order that fell through.
  * Shipment Tracking after_insert, status Delivered — runs right after step 2;
    if the delivery note still has no submitted invoice, finish the job.
  * Sales Invoice after_insert, a draft whose delivery note is already
    Delivered — the late-manifest case; submit it now.
The work reuses the same two functions, so the invoice and its payment are what
a normal day produces. The invoice is dated the manifest submit day, never later
than the delivery day (a late manifest must not push September sales into
October). Orders a person should look at are left alone: two delivery notes on
one order (the same parcel keyed twice), a return note, zero value
(exchanges), cancelled, or a prepayment on the order (a COD receipt on top
would double it).
"""
import frappe
from frappe.utils import flt, getdate

_COMPANY = "Justyol Morocco"
_DELIVERED = ("Delivered", "Received")


def _billed(dn, so):
    return bool(frappe.db.sql(
        """SELECT 1 FROM `tabSales Invoice Item` it JOIN `tabSales Invoice` si ON si.name = it.parent
           WHERE si.docstatus = 1 AND si.is_return = 0 AND (it.delivery_note = %s OR it.sales_order = %s)
           LIMIT 1""", (dn, so)))


def _enqueue(dn, so):
    frappe.enqueue("accounting_portal.api.invoice_net.process", queue="short", timeout=300,
                   enqueue_after_commit=True, job_id=f"ap_invoice_net:{dn}", deduplicate=True,
                   dn=dn, so=so)


def on_tracking(doc, method=None):
    """Shipment Tracking after_insert — the carrier hook has just run."""
    if doc.get("is_return") or doc.get("track_shipment_status") not in _DELIVERED or not doc.sales_order:
        return
    for (dn,) in frappe.db.sql(
            """SELECT DISTINCT dn.name FROM `tabDelivery Note Item` d
               JOIN `tabDelivery Note` dn ON dn.name = d.parent
               WHERE d.against_sales_order = %s AND dn.docstatus = 1 AND dn.is_return = 0
                 AND dn.company = %s""", (doc.sales_order, _COMPANY)):
        if not _billed(dn, doc.sales_order):
            _enqueue(dn, doc.sales_order)


def on_draft_invoice(doc, method=None):
    """Sales Invoice after_insert — a draft created after its parcel arrived."""
    if doc.docstatus != 0 or doc.company != _COMPANY or doc.is_return:
        return
    row = next((i for i in doc.items if i.delivery_note), None)
    if not row:
        return
    if frappe.db.get_value("Delivery Note", row.delivery_note, "custom_track_shipment_status") in _DELIVERED:
        _enqueue(row.delivery_note, row.sales_order)


def _skip_reason(dn, so):
    if _billed(dn, so):
        return "billed"
    if frappe.db.sql("""SELECT 1 FROM `tabDelivery Note` WHERE return_against = %s AND docstatus < 2 LIMIT 1""", dn):
        return "returned"
    notes = frappe.db.sql(
        """SELECT COUNT(DISTINCT d.parent) FROM `tabDelivery Note Item` d
           JOIN `tabDelivery Note` dn ON dn.name = d.parent
           WHERE d.against_sales_order = %s AND dn.docstatus = 1 AND dn.is_return = 0""", so)[0][0]
    if notes > 1:
        return "two delivery notes"
    s = frappe.db.get_value("Sales Order", so, ["grand_total", "status", "custom_sales_status"], as_dict=True)
    if not s or not flt(s.grand_total):
        return "zero value"
    if s.status == "Cancelled" or s.custom_sales_status == "Cancelled":
        return "cancelled"
    if frappe.db.sql(
            """SELECT 1 FROM `tabPayment Entry Reference` per JOIN `tabPayment Entry` pe ON pe.name = per.parent
               WHERE pe.docstatus = 1 AND per.reference_doctype = 'Sales Order' AND per.reference_name = %s
               LIMIT 1""", so):
        return "prepaid"
    return None


def _drafts(dn):
    return [r[0] for r in frappe.db.sql(
        """SELECT DISTINCT si.name FROM `tabSales Invoice` si
           JOIN `tabSales Invoice Item` it ON it.parent = si.name
           WHERE it.delivery_note = %s AND si.docstatus = 0""", dn)]


def process(dn, so):
    """Background job: draft (if missing), date, submit + COD receipt for one note."""
    reason = _skip_reason(dn, so)
    if reason:
        return reason
    info = frappe.db.sql(
        """SELECT MAX(s.parent) sh, MAX(DATE(sh.modified)) shipped, MAX(DATE(o.custom_delivered_at)) delivered,
                  dn.posting_date
           FROM `tabDelivery Note` dn
           JOIN `tabSales Order` o ON o.name = %s
           LEFT JOIN `tabShipment Delivery Note` s ON s.delivery_note = dn.name
           LEFT JOIN `tabShipment` sh ON sh.name = s.parent AND sh.docstatus = 1
           WHERE dn.name = %s GROUP BY dn.name""", (so, dn), as_dict=True)[0]
    dates = [d for d in (info.shipped, info.delivered) if d]
    date = min(dates) if dates else info.posting_date

    drafts = _drafts(dn)
    if not drafts:
        create = frappe.get_attr("codx_erp.overrides.shipment.create_draft_sales_invoices_for_shipment")
        create([dn], info.sh or "INVOICE-NET")
        drafts = _drafts(dn)
    if len(drafts) != 1:
        frappe.log_error(f"{dn}: expected one draft invoice, found {drafts}", "invoice_net")
        return "drafts"

    si = frappe.get_doc("Sales Invoice", drafts[0])
    si.set_posting_time = 1
    si.posting_date = date
    if si.due_date and getdate(si.due_date) < getdate(date):
        si.due_date = date
    si.save(ignore_permissions=True)
    frappe.db.commit()

    # the carrier hook's own submit + COD Payment Entry
    frappe.get_doc({"doctype": "Shipment Tracking", "sales_order": so}) \
        ._submit_related_invoices_and_create_payments(dn)
    frappe.db.commit()
    return si.name
