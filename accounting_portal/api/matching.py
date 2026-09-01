"""Revenue <-> COGS matching — the monthly reconciliation screen.

Answers one question per month, honestly: does every dirham of revenue have
its cost, and every dirham of cost its revenue?

Raw doc counts LIE here (measured 2026-09-01: 81K DNs vs 67K SIs looked
catastrophic; 79% of the gap was returns whose cost self-cancels). So the
match is at the ORDER level, returns are shown as their own self-cancelling
column, and the "missing" figure only counts the buckets that actually
distort the P&L — in BOTH directions:

  cost with no revenue:  collected-but-never-invoiced, delivered-awaiting-
                         invoice, order-closed-with-goods-out
  revenue with no cost:  invoice stands but the goods came back and no
                         credit note was ever raised; invoice with no
                         shipment anywhere on its order

A tie-out footer reconciles DN cost + direct-PI + direct-PR + the rest to
the GL COGS section, so this screen's totals always agree with the P&L.
"""

import json

import frappe
from frappe.utils import flt, nowdate

from accounting_portal.api.permissions import assert_portal_access, resolve_companies

CACHE_SEC = 300

# buckets that carry an action in the UI
B_RETURNED = "returned"          # self-cancelling — no accounting action
B_COLLECTED = "collected"        # money in, no invoice -> bill now
B_DELIVERED = "delivered"        # delivered, awaiting invoice -> bill
B_CLOSED = "closed"              # order closed with goods out -> review
B_NO_SO = "no_so"                # DN with no order link -> review
B_REV_NO_COST = "rev_no_cost"    # invoice, no shipment on its order
B_REV_RETURNED = "rev_returned"  # invoice stands, goods returned, no CN


def _base_sets(company, year):
    """One pass over the year's documents -> classified DN and SI rows."""
    dns = frappe.db.sql(
        """SELECT d.name, DATE_FORMAT(d.posting_date,'%%Y-%%m') ym, d.customer, d.status,
                  d.base_grand_total value,
                  (SELECT x.against_sales_order FROM `tabDelivery Note Item` x
                   WHERE x.parent=d.name AND IFNULL(x.against_sales_order,'')!='' LIMIT 1) so,
                  (SELECT 1 FROM `tabDelivery Note Item` x WHERE x.parent=d.name
                   AND IFNULL(x.against_sales_invoice,'')!='' LIMIT 1) si_direct
           FROM `tabDelivery Note` d
           WHERE d.company=%s AND d.docstatus=1 AND d.is_return=0
             AND YEAR(d.posting_date)=%s""", (company, year), as_dict=True)
    # per-DN cost from the stock ledger, one grouped query
    cogs = dict(frappe.db.sql(
        """SELECT sle.voucher_no, SUM(-sle.stock_value_difference)
           FROM `tabStock Ledger Entry` sle
           JOIN `tabWarehouse` w ON w.name=sle.warehouse
           WHERE w.company=%s AND sle.is_cancelled=0 AND sle.actual_qty<0
             AND sle.voucher_type='Delivery Note' AND YEAR(sle.posting_date)=%s
           GROUP BY sle.voucher_no""", (company, year)))
    sis = frappe.db.sql(
        """SELECT s.name, DATE_FORMAT(s.posting_date,'%%Y-%%m') ym, s.customer,
                  s.base_net_total value,
                  (SELECT x.sales_order FROM `tabSales Invoice Item` x
                   WHERE x.parent=s.name AND IFNULL(x.sales_order,'')!='' LIMIT 1) so,
                  (SELECT 1 FROM `tabSales Invoice Item` x WHERE x.parent=s.name
                   AND IFNULL(x.delivery_note,'')!='' LIMIT 1) dn_direct,
                  (SELECT 1 FROM `tabSales Invoice Item` x JOIN `tabItem` i ON i.name=x.item_code
                   WHERE x.parent=s.name AND i.is_stock_item=1 LIMIT 1) has_stock_item,
                  (SELECT 1 FROM `tabSales Invoice` cn WHERE cn.docstatus=1 AND cn.is_return=1
                   AND cn.return_against=s.name LIMIT 1) has_cn
           FROM `tabSales Invoice` s
           WHERE s.company=%s AND s.docstatus=1 AND s.is_return=0
             AND YEAR(s.posting_date)=%s""", (company, year), as_dict=True)

    def chunked(seq, fn):
        out = set()
        seq = [s for s in seq if s]
        for i in range(0, len(seq), 5000):
            out |= fn(seq[i:i + 5000])
        return out

    all_sos = list({d.so for d in dns} | {s.so for s in sis})
    so_with_si = chunked(all_sos, lambda c: {r[0] for r in frappe.db.sql(
        """SELECT DISTINCT sii.sales_order FROM `tabSales Invoice Item` sii
           JOIN `tabSales Invoice` s ON s.name=sii.parent
           WHERE s.docstatus=1 AND s.is_return=0 AND sii.sales_order IN %s""", (c,))})
    so_with_dn = chunked(all_sos, lambda c: {r[0] for r in frappe.db.sql(
        """SELECT DISTINCT di.against_sales_order FROM `tabDelivery Note Item` di
           JOIN `tabDelivery Note` dn ON dn.name=di.parent
           WHERE dn.docstatus=1 AND dn.is_return=0 AND di.against_sales_order IN %s""", (c,))})
    so_returned = chunked(all_sos, lambda c: {r[0] for r in frappe.db.sql(
        """SELECT DISTINCT di.against_sales_order FROM `tabDelivery Note Item` di
           JOIN `tabDelivery Note` dn ON dn.name=di.parent
           WHERE dn.docstatus=1 AND dn.is_return=1 AND di.against_sales_order IN %s""", (c,))})
    so_paid = chunked(all_sos, lambda c: {r[0] for r in frappe.db.sql(
        """SELECT DISTINCT per.reference_name FROM `tabPayment Entry Reference` per
           JOIN `tabPayment Entry` pe ON pe.name=per.parent
           WHERE pe.docstatus=1 AND per.reference_doctype='Sales Order'
             AND per.reference_name IN %s""", (c,))})
    so_status = {}
    live = [s for s in all_sos if s]
    for i in range(0, len(live), 5000):
        for r in frappe.db.sql("SELECT name, status FROM `tabSales Order` WHERE name IN %s",
                               (live[i:i + 5000],)):
            so_status[r[0]] = r[1]

    for d in dns:
        d.cogs = flt(cogs.get(d.name))
        if d.si_direct or (d.so and d.so in so_with_si):
            d.bucket = "matched"
        elif d.so and d.so in so_returned:
            d.bucket = B_RETURNED
        elif d.so and d.so in so_paid:
            d.bucket = B_COLLECTED
        elif not d.so:
            d.bucket = B_NO_SO
        elif so_status.get(d.so) in ("Closed", "Completed"):
            d.bucket = B_CLOSED
        else:
            d.bucket = B_DELIVERED
    for s in sis:
        if not s.has_stock_item:
            s.bucket = "service"           # no cost expected — excluded from missing
        elif s.so and s.so in so_returned and not s.has_cn:
            s.bucket = B_REV_RETURNED      # cost reversed, revenue standing
        elif s.dn_direct or (s.so and s.so in so_with_dn):
            s.bucket = "matched"
        else:
            s.bucket = B_REV_NO_COST
    return dns, sis


def _tie_out(company, year):
    """DN cost + everything else that writes into the COGS section = GL."""
    gl = flt(frappe.db.sql(
        """SELECT SUM(g.debit-g.credit) FROM `tabGL Entry` g
           JOIN `tabAccount` a ON a.name=g.account
           WHERE g.company=%s AND g.is_cancelled=0 AND YEAR(g.posting_date)=%s
             AND a.account_type='Cost of Goods Sold'""", (company, year))[0][0])
    by_vt = dict(frappe.db.sql(
        """SELECT g.voucher_type, SUM(g.debit-g.credit) FROM `tabGL Entry` g
           JOIN `tabAccount` a ON a.name=g.account
           WHERE g.company=%s AND g.is_cancelled=0 AND YEAR(g.posting_date)=%s
             AND a.account_type='Cost of Goods Sold'
           GROUP BY g.voucher_type""", (company, year)))
    dn = flt(by_vt.get("Delivery Note"))
    pi = flt(by_vt.get("Purchase Invoice"))
    pr = flt(by_vt.get("Purchase Receipt"))
    je = flt(by_vt.get("Journal Entry"))
    other = gl - dn - pi - pr - je
    return {"gl_total": round(gl), "dn": round(dn), "direct_pi": round(pi),
            "direct_pr": round(pr), "je": round(je), "other": round(other)}


@frappe.whitelist()
def monthly(company=None, year=None):
    assert_portal_access()
    companies = resolve_companies(company)
    target = company if (company and company in companies) else (companies[0] if companies else None)
    if not target:
        return {}
    y = int(year or nowdate()[:4])
    ck = f"ap_match:{target}:{y}"
    hit = frappe.cache().get_value(ck)
    if hit is not None:
        return hit
    dns, sis = _base_sets(target, y)
    months = sorted({d.ym for d in dns} | {s.ym for s in sis})
    rows = []
    # return DNs give cost BACK — net them per month so the table's cost and
    # GM agree with the P&L (gross outbound alone overstated COGS by ~2.2M)
    ret_in = dict(frappe.db.sql(
        """SELECT DATE_FORMAT(sle.posting_date,'%%Y-%%m'), SUM(sle.stock_value_difference)
           FROM `tabStock Ledger Entry` sle
           JOIN `tabWarehouse` w ON w.name=sle.warehouse
           JOIN `tabDelivery Note` dn ON dn.name=sle.voucher_no
           WHERE w.company=%s AND sle.is_cancelled=0 AND sle.voucher_type='Delivery Note'
             AND dn.is_return=1 AND YEAR(sle.posting_date)=%s
           GROUP BY 1""", (target, y)))
    for m in months:
        md = [d for d in dns if d.ym == m]
        ms = [s for s in sis if s.ym == m]
        def dsum(b): return round(sum(flt(d.cogs) for d in md if d.bucket == b))
        def dcnt(b): return sum(1 for d in md if d.bucket == b)
        def ssum(b): return round(sum(flt(s.value) for s in ms if s.bucket == b))
        def scnt(b): return sum(1 for s in ms if s.bucket == b)
        revenue = round(sum(flt(s.value) for s in ms))
        dn_cogs = round(sum(flt(d.cogs) for d in md) - flt(ret_in.get(m)))
        cost_no_rev = dsum(B_COLLECTED) + dsum(B_DELIVERED) + dsum(B_CLOSED) + dsum(B_NO_SO)
        rev_no_cost = ssum(B_REV_NO_COST) + ssum(B_REV_RETURNED)
        rows.append({
            "month": m,
            "si_count": len(ms), "revenue": revenue,
            "dn_count": len(md), "dn_cogs": dn_cogs,
            "matched_dn": dcnt("matched"),
            "returned": {"n": dcnt(B_RETURNED), "cogs": dsum(B_RETURNED)},
            "collected": {"n": dcnt(B_COLLECTED), "cogs": dsum(B_COLLECTED)},
            "delivered": {"n": dcnt(B_DELIVERED), "cogs": dsum(B_DELIVERED)},
            "closed": {"n": dcnt(B_CLOSED) + dcnt(B_NO_SO),
                       "cogs": dsum(B_CLOSED) + dsum(B_NO_SO)},
            "rev_no_cost": {"n": scnt(B_REV_NO_COST), "value": ssum(B_REV_NO_COST)},
            "rev_returned": {"n": scnt(B_REV_RETURNED), "value": ssum(B_REV_RETURNED)},
            "service": {"n": scnt("service"), "value": ssum("service")},
            "cost_without_revenue": cost_no_rev,       # margin UNDERstated by this
            "revenue_without_cost": rev_no_cost,       # margin OVERstated by up to this
        })
    tot = {}
    for k in ("revenue", "dn_cogs", "cost_without_revenue", "revenue_without_cost"):
        tot[k] = sum(r[k] for r in rows)
    out = {"company": target, "year": y, "rows": rows, "total": tot,
           "tie_out": _tie_out(target, y)}
    frappe.cache().set_value(ck, out, expires_in_sec=CACHE_SEC)
    return out


@frappe.whitelist()
def drill(company=None, year=None, month=None, bucket=None, limit=100):
    """The documents behind one month x bucket cell, oldest first."""
    assert_portal_access()
    companies = resolve_companies(company)
    target = company if (company and company in companies) else (companies[0] if companies else None)
    if not target or not month or not bucket:
        return {"rows": []}
    y = int(year or str(month)[:4])
    dns, sis = _base_sets(target, y)
    lim = min(int(limit or 100), 300)
    if bucket in (B_REV_NO_COST, B_REV_RETURNED):
        rows = [{"doc": s.name, "doctype": "Sales Invoice", "customer": s.customer,
                 "amount": round(flt(s.value)), "so": s.so,
                 "action": "credit_note" if bucket == B_REV_RETURNED else "review"}
                for s in sis if s.ym == month and s.bucket == bucket]
    else:
        want = [B_CLOSED, B_NO_SO] if bucket == "closed" else [bucket]
        rows = [{"doc": d.name, "doctype": "Delivery Note", "customer": d.customer,
                 "amount": round(flt(d.cogs)), "so": d.so,
                 "action": "bill" if d.bucket in (B_COLLECTED, B_DELIVERED) else "review"}
                for d in dns if d.ym == month and d.bucket in want]
    rows.sort(key=lambda r: -r["amount"])
    return {"rows": rows[:lim], "total": len(rows), "shown": min(len(rows), lim)}
