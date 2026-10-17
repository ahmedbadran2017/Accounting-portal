"""Cathedis parcel mirror — the carrier's word, kept locally.

The cycle radar needs, for every parcel, what Cathedis says: delivered or
returned, how much it collected, when it paid us. Asking Cathedis live on every
screen load would mean ~95K lookups per view, so this module keeps one row per
parcel in `Cathedis Parcel` and refreshes it once a night.

Only OPEN parcels are asked again. A parcel is final once Cathedis says PAID
(delivered and funded) or RETURN_CUSTOMER (back with us); those never change.
In steady state that is a few thousand parcels a night, fetched in bulk
(~5,000 AWBs per call), so the nightly run takes seconds. The first run fills
the whole year (~95K parcels, about a minute).
"""
from datetime import timedelta

import frappe
from frappe.utils import flt, get_datetime, now_datetime

from accounting_portal.api.permissions import assert_portal_access, assert_can_write

_MOD = "codx_erp.codx_erp.report.cathedis_status_comparison.cathedis_status_comparison"
FINAL = ("PAID", "RETURN_CUSTOMER")
SINCE = "2025-12-01"          # 2026 orders can ship in December
CHUNK = 5000
FIELDS = ["code", "nomOrder", "status", "deliveryStatus", "amount", "declaredValue",
          "c2cShippingFees", "deliveryDate", "returnDate", "fundedDate", "updatedOn"]
COLS = ["awb", "nom_order", "status", "delivery_status", "amount", "declared_value",
        "shipping_fees", "delivery_date", "return_date", "funded_date", "cathedis_updated"]
JOB = "ap_cathedis_sync"
LAST = "ap_cathedis_sync_last"


def _local(ts):
    """Cathedis stamps UTC; Morocco is UTC+1 — a 23:30 UTC funding is next day."""
    if not ts:
        return None
    try:
        return get_datetime(str(ts)[:19].replace("T", " ")) + timedelta(hours=1)
    except Exception:
        return None


def _row(x):
    ds = x.get("deliveryStatus")
    if isinstance(ds, dict):
        ds = ds.get("name")
    upd = _local(x.get("updatedOn"))
    d = {k: _local(x.get(k)) for k in ("deliveryDate", "returnDate", "fundedDate")}
    return (
        x.get("code"), (x.get("nomOrder") or "")[:140], x.get("status") or "", (ds or "")[:140],
        flt(x.get("amount")), flt(x.get("declaredValue")), flt(x.get("c2cShippingFees")),
        d["deliveryDate"].date() if d["deliveryDate"] else None,
        d["returnDate"].date() if d["returnDate"] else None,
        d["fundedDate"].date() if d["fundedDate"] else None,
        upd,
    )


def _upsert(rows):
    if not rows:
        return
    now = now_datetime()
    cols = ["name", "creation", "modified", "modified_by", "owner", "docstatus", "idx"] + COLS + ["synced_on"]
    ph = "(" + ",".join(["%s"] * len(cols)) + ")"
    upd = ", ".join(f"`{c}`=VALUES(`{c}`)" for c in COLS[1:] + ["synced_on", "modified"])
    vals = []
    for r in rows:
        vals.extend([r[0], now, now, "Administrator", "Administrator", 0, 0] + list(r) + [now])
    frappe.db.sql(
        f"INSERT INTO `tabCathedis Parcel` ({','.join('`%s`' % c for c in cols)}) VALUES "
        + ",".join([ph] * len(rows)) + f" ON DUPLICATE KEY UPDATE {upd}", tuple(vals))


def _open_awbs():
    """Every AWB on a 2026 Moroccan delivery note that is not final yet."""
    return frappe.db.sql_list(
        """SELECT DISTINCT dn.custom_awb FROM `tabDelivery Note` dn
           LEFT JOIN `tabCathedis Parcel` p ON p.name = dn.custom_awb
           WHERE dn.company = 'Justyol Morocco' AND dn.docstatus = 1 AND dn.is_return = 0
             AND dn.posting_date >= %s AND IFNULL(dn.custom_awb, '') != ''
             AND (p.name IS NULL OR p.status NOT IN %s)""", (SINCE, FINAL))


def sync(rebuild=True):
    """Refresh every open parcel. Safe to run twice at once (a DB lock)."""
    if frappe.db.sql("SELECT GET_LOCK(%s, 0)", JOB)[0][0] != 1:
        return {"skipped": "already running"}
    started = now_datetime()
    asked = got = 0
    try:
        fetch = frappe.get_attr(_MOD + ".fetch_cathedis_deliveries_by_awb")
        awbs = _open_awbs()
        for i in range(0, len(awbs), CHUNK):
            part = awbs[i:i + CHUNK]
            asked += len(part)
            # session_info=None: the fetch logs in itself (one login per 5,000)
            rows = [_row(x) for x in (fetch(part, FIELDS, None) or []) if x.get("code")]
            got += len(rows)
            for j in range(0, len(rows), 1000):
                _upsert(rows[j:j + 1000])
            frappe.db.commit()
    finally:
        frappe.db.sql("SELECT RELEASE_LOCK(%s)", JOB)
    res = {"asked": asked, "updated": got, "started": str(started),
           "seconds": round((now_datetime() - started).total_seconds())}
    frappe.db.set_default(LAST, frappe.as_json(res))
    frappe.db.commit()
    if rebuild:
        try:
            frappe.get_attr("accounting_portal.api.radar.rebuild")()
        except Exception:
            frappe.log_error(title="radar rebuild after Cathedis sync", message=frappe.get_traceback())
    return res


def nightly():
    """Scheduler hook (cron, once a night)."""
    try:
        sync()
    except Exception:
        frappe.log_error(title="Cathedis nightly sync", message=frappe.get_traceback())


@frappe.whitelist()
def sync_now():
    """'Refresh from Cathedis' button: one background run, never two."""
    assert_can_write()
    frappe.enqueue("accounting_portal.api.cathedis_sync.sync", queue="long", timeout=1800,
                   job_id=JOB, deduplicate=True)
    return {"queued": True}


@frappe.whitelist()
def status():
    assert_portal_access()
    last = frappe.db.get_default(LAST)
    counts = dict(frappe.db.sql("SELECT status, COUNT(*) FROM `tabCathedis Parcel` GROUP BY status"))
    return {"last": frappe.parse_json(last) if last else None, "parcels": counts,
            "running": not frappe.db.sql("SELECT IS_FREE_LOCK(%s)", JOB)[0][0]}
