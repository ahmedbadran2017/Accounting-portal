"""Cycle radar — every order of a month, carried to its last station.

One question per order: did its story end cleanly? The stations, each read
from the one source that is allowed to say so:

  order      the Sales Order (value, payment type, exchange flag)
  shipped    a non-return Delivery Note (the stock left, the cost was booked)
  carrier    Cathedis itself, via the nightly `Cathedis Parcel` mirror
             (PAID = delivered and funded, RETURN_CUSTOMER = came back,
             UNPAID + 'Livré' = delivered, money not sent yet)
  invoiced   a submitted Sales Invoice, net of credit notes
  collected  Payment Entries on the invoice or the order: the Cathedis COD
             receipt must equal what Cathedis says it collected; a prepaid
             parcel (Cathedis amount 0) must be paid by a Payzone/bank receipt
  cost       the delivery note's stock cost, judged against the item's own
             history and its selling price (see _line_flag)

An order that passes every station is "clean". Otherwise it lands in exactly
ONE exception bucket — the first broken station — so counts never overlap and
each bucket has one fix. Orders still moving (in transit, delivered but not
funded yet, return on its way) are "watch", not exceptions.

Months are order cohorts (Sales Order date): "of the orders placed in May, how
many are fully closed?" — the documents may land in later months.

Built as a snapshot (nightly, right after the Cathedis sync, or on the Rebuild
button) and served from cache. It is deliberately NOT in _cache._PREFIXES:
busting it on every posting would mean a ~30 s year-wide rebuild on the next
view; the screen shows when the snapshot was taken instead.
"""
import os

import frappe
from frappe.utils import flt, nowdate, now_datetime, date_diff

from accounting_portal.api.permissions import assert_portal_access, assert_can_write, resolve_companies
from accounting_portal.api import _actions

CATHEDIS = "108.021.003"
WATCH_DAYS = 20       # a parcel/return still moving after this is an exception
FUND_DAYS = 15        # delivered, Cathedis has not paid us after this → late
# Jan–Jun 2026: Cathedis collected 25 MAD shipping per parcel that the order's
# own invoice never carried; it is booked in one monthly invoice to "Cathedis
# COD Customers" (17 Oct 2026). A 24–26 gap on those months is that, not an error.
SHIP_LUMP_UNTIL = "2026-06"
SHIP_FEE = (24.0, 26.0)
DRILL_CAP = 300
CK = "ap_radar:v1:{}:{}"
JOB = "ap_radar_build"

# bucket -> fix. 'bill' = invoice + COD receipt (invoice_net), 'credit_note' =
# the existing return flow, 'review' = a person decides (the row links to docs)
BUCKETS = {
    # money in, no revenue
    "collected_no_invoice":   "bill",
    "delivered_no_invoice":   "bill",
    "prepaid_no_invoice":     "review",
    # revenue and cash disagree
    "exchange_overbilled":    "review",
    "prepaid_cod_receipt":    "review",
    "prepaid_unmatched":      "review",
    "funded_no_receipt":      "review",
    "amount_mismatch":        "review",
    "invoice_vs_paid":        "review",
    "transfer_late":          "review",
    # returns
    "returned_but_collected": "review",
    "returned_invoice_stands": "credit_note",
    "return_not_received":    "review",
    # carrier
    "invoiced_not_delivered": "review",
    "stuck_at_carrier":       "review",
    "no_carrier_record":      "review",
    # documents
    "dup_dn":                 "review",
    "cancelled_goods_out":    "review",
    "invoice_no_shipment":    "review",
    # cost of goods
    "cogs_zero":              "review",
    "cogs_high":              "review",
    "cogs_low":               "review",
}
WATCH = ("in_transit", "awaiting_transfer", "return_in_progress")


# ─────────────────────────────── cost judgement ──────────────────────────────

def _median(xs):
    s = sorted(xs)
    n = len(s)
    if not n:
        return 0.0
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def _item_refs(lines):
    """Per item: median unit cost and median unit selling price (HT) over the
    year's delivery lines. Medians, so a handful of bad lines cannot drag the
    reference toward themselves."""
    costs, prices = {}, {}
    for _dn, item, qty, cost, price in lines:
        if qty <= 0:
            continue
        if cost > 0:
            costs.setdefault(item, []).append(cost / qty)
        if price > 0:
            prices.setdefault(item, []).append(price / qty)
    return ({k: (_median(v), len(v)) for k, v in costs.items()},
            {k: _median(v) for k, v in prices.items()})


def _line_flag(item, qty, cost, price, cref, pref):
    """'zero' | 'high' | 'low' | None for one delivery line.

    Two independent witnesses, so a single wrong reference cannot condemn a
    line on its own:
      history  the item's median unit cost (needs ≥5 deliveries to count)
      price    what this line sold for (HT); the item's median price when the
               line itself sold at 0 (an exchange)
    high  = 1.8× its own history, or above its selling price while also above
            history (or the whole item costs more than it sells for)
    low   = under 0.4× its own history (a write-down or a mis-keyed receipt)
    """
    if qty <= 0:
        return None
    if cost <= 0.01:
        return "zero"
    uc = cost / qty
    med, n = cref.get(item, (0.0, 0))
    hist = med if n >= 5 and med > 0 else None
    up = price / qty if price > 0 else pref.get(item, 0.0)
    if hist and uc >= 1.8 * hist:
        return "high"
    if hist and uc <= 0.4 * hist:
        return "low"
    if up and uc >= up:
        item_upside_down = hist is not None and pref.get(item) and hist >= pref.get(item)
        if hist is None or uc >= 1.3 * hist or item_upside_down:
            return "high"
    return None


# ──────────────────────────────── data loading ───────────────────────────────

def _load(company, year):
    y0, y1 = f"{year}-01-01", f"{year}-12-31"
    docs_from = f"{int(year) - 1}-11-01"
    sos = frappe.db.sql(
        """SELECT name, DATE_FORMAT(transaction_date, '%%Y-%%m') ym, status, docstatus,
                  IFNULL(custom_sales_status, '') ss, base_grand_total gt,
                  IFNULL(payment_type, '') pt, IFNULL(custom_is_from_sales_exchange, 0) ex, customer
           FROM `tabSales Order`
           WHERE company = %s AND docstatus IN (1, 2) AND transaction_date BETWEEN %s AND %s""",
        (company, y0, y1), as_dict=True)
    dns = frappe.db.sql(
        """SELECT dn.name, dn.is_return, dn.posting_date, IFNULL(dn.custom_awb, '') awb,
                  IFNULL(NULLIF(dn.custom_track_shipment_status, ''), IFNULL(dn.custom_logistics_status, '')) trk,
                  dn.return_against, MAX(di.against_sales_order) so
           FROM `tabDelivery Note` dn JOIN `tabDelivery Note Item` di ON di.parent = dn.name
           WHERE dn.company = %s AND dn.docstatus = 1 AND dn.posting_date >= %s
           GROUP BY dn.name""", (company, docs_from), as_dict=True)
    sis = frappe.db.sql(
        """SELECT si.name, si.is_return, si.return_against, si.base_grand_total gt,
                  si.outstanding_amount os, MAX(it.sales_order) so, MAX(it.delivery_note) dn
           FROM `tabSales Invoice` si JOIN `tabSales Invoice Item` it ON it.parent = si.name
           WHERE si.company = %s AND si.docstatus = 1 AND si.posting_date >= %s
           GROUP BY si.name""", (company, docs_from), as_dict=True)
    pays = frappe.db.sql(
        """SELECT per.reference_doctype, per.reference_name, LEFT(pe.paid_to, 11), SUM(per.allocated_amount)
           FROM `tabPayment Entry Reference` per JOIN `tabPayment Entry` pe ON pe.name = per.parent
           WHERE pe.docstatus = 1 AND pe.company = %s AND pe.payment_type = 'Receive'
             AND pe.posting_date >= %s AND per.reference_doctype IN ('Sales Invoice', 'Sales Order')
           GROUP BY 1, 2, 3""", (company, docs_from))
    je_pays = frappe.db.sql(
        """SELECT jea.reference_name, SUM(jea.credit_in_account_currency - jea.debit_in_account_currency)
           FROM `tabJournal Entry Account` jea JOIN `tabJournal Entry` je ON je.name = jea.parent
           WHERE je.docstatus = 1 AND je.company = %s AND je.posting_date >= %s
             AND jea.reference_type = 'Sales Invoice'
           GROUP BY 1""", (company, docs_from))
    cost = frappe.db.sql(
        """SELECT voucher_no, item_code, SUM(-actual_qty), SUM(-stock_value_difference)
           FROM `tabStock Ledger Entry`
           WHERE company = %s AND voucher_type = 'Delivery Note' AND is_cancelled = 0
             AND actual_qty < 0 AND posting_date >= %s
           GROUP BY 1, 2""", (company, docs_from))
    price = frappe.db.sql(
        """SELECT di.parent, di.item_code, SUM(di.base_net_amount)
           FROM `tabDelivery Note Item` di JOIN `tabDelivery Note` dn ON dn.name = di.parent
           WHERE dn.company = %s AND dn.docstatus = 1 AND dn.is_return = 0 AND dn.posting_date >= %s
           GROUP BY 1, 2""", (company, docs_from))
    parcels = {r[0]: r for r in frappe.db.sql(
        """SELECT name, status, delivery_status, amount, delivery_date, return_date, funded_date,
                  DATE(cathedis_updated)
           FROM `tabCathedis Parcel`""")}
    bank = {
        "funded": {r[0]: [int(r[1]), flt(r[2])] for r in frappe.db.sql(
            """SELECT DATE_FORMAT(funded_date, '%%Y-%%m'), COUNT(*), SUM(amount) FROM `tabCathedis Parcel`
               WHERE funded_date BETWEEN %s AND %s GROUP BY 1""", (y0, y1))},
        "credited": dict(frappe.db.sql(
            """SELECT DATE_FORMAT(posting_date, '%%Y-%%m'), SUM(credit - debit) FROM `tabGL Entry`
               WHERE is_cancelled = 0 AND company = %s AND account LIKE %s
                 AND voucher_type = 'Journal Entry' AND posting_date BETWEEN %s AND %s
               GROUP BY 1""", (company, CATHEDIS + "%", y0, y1))),
    }
    # money by POSTING month, so the cycle view agrees with the P&L
    money = {
        "sales": frappe.db.sql(
            """SELECT DATE_FORMAT(posting_date, '%%Y-%%m'), is_return, SUM(base_grand_total),
                      SUM(outstanding_amount), COUNT(*)
               FROM `tabSales Invoice` WHERE docstatus = 1 AND company = %s
                 AND posting_date BETWEEN %s AND %s GROUP BY 1, 2""", (company, y0, y1)),
        "receipts": frappe.db.sql(
            """SELECT DATE_FORMAT(posting_date, '%%Y-%%m'), payment_type,
                      LEFT(IF(payment_type = 'Receive', paid_to, paid_from), 11), SUM(base_paid_amount)
               FROM `tabPayment Entry` WHERE docstatus = 1 AND company = %s AND party_type = 'Customer'
                 AND posting_date BETWEEN %s AND %s GROUP BY 1, 2, 3""", (company, y0, y1)),
        "cogs": frappe.db.sql(
            """SELECT DATE_FORMAT(g.posting_date, '%%Y-%%m'), g.voucher_type, SUM(g.debit - g.credit)
               FROM `tabGL Entry` g JOIN `tabAccount` a ON a.name = g.account
               WHERE g.company = %s AND g.is_cancelled = 0 AND g.posting_date BETWEEN %s AND %s
                 AND a.account_type = 'Cost of Goods Sold' GROUP BY 1, 2""", (company, y0, y1)),
    }
    return sos, dns, sis, pays, je_pays, cost, price, parcels, bank, money


# ──────────────────────────────── classification ─────────────────────────────

def _carrier(dn, parcels, have_parcels, rdn):
    """(outcome, cod, funded, event_date, label) — Cathedis first, the DN's
    own tracking field only when the mirror has no row for this parcel."""
    p = parcels.get(dn.awb) if dn.awb else None
    if p:
        _awb, st, ds, amt, d_dt, r_dt, f_dt, upd = p
        label = f"{st} · {ds}" if ds else st
        if st == "PAID":
            return "delivered", flt(amt), True, f_dt or d_dt, label
        if st == "RETURN_CUSTOMER":
            return "returned", flt(amt), False, r_dt or upd, label
        if ds == "Livré":
            return "delivered", flt(amt), False, d_dt or upd, label
        if rdn:
            # Cathedis often leaves a failed parcel at UNPAID ('Client
            # Injoignable') after handing it back; our return delivery note
            # proves the goods are home (2,549 of 2,700 "stuck" on 17 Oct 2026)
            return "returned", flt(amt), False, upd, label + " · return received"
        return "open", flt(amt), False, upd, label
    trk = (dn.trk or "")
    if trk in ("Delivered", "Received"):
        return "delivered", None, False, None, trk
    if rdn or "Return" in trk:
        return "returned", None, False, None, trk or "Return"
    if dn.awb and have_parcels and date_diff(nowdate(), dn.posting_date) > 5:
        return "no_record", None, False, None, ""
    return "open", None, False, None, trk


def _classify(company, year):
    sos, dns, sis, pays, je_pays, cost_rows, price_rows, parcels, bank, money = _load(company, year)
    have_parcels = bool(parcels)
    today = nowdate()

    dn_by_name = {d.name: d for d in dns}
    dn_by_so, rdn_by_so = {}, {}
    for d in dns:
        so = d.so or (dn_by_name[d.return_against].so if d.return_against in dn_by_name else None)
        if not so:
            continue
        (rdn_by_so if d.is_return else dn_by_so).setdefault(so, []).append(d)

    si_by_name = {s.name: s for s in sis}
    si_so = {}
    si_by_so, cn_by_so = {}, {}
    for s in sis:
        so = s.so or (dn_by_name[s.dn].so if s.dn in dn_by_name else None)
        if s.is_return:
            orig = si_by_name.get(s.return_against)
            so = so or (orig and (orig.so or (dn_by_name[orig.dn].so if orig.dn in dn_by_name else None)))
            if so:
                cn_by_so.setdefault(so, []).append(s)
            continue
        if so:
            si_so[s.name] = so
            si_by_so.setdefault(so, []).append(s)

    cath, other = {}, {}
    for dt, name, acc, amt in pays:
        so = name if dt == "Sales Order" else si_so.get(name)
        if not so:
            continue
        tgt = cath if acc == CATHEDIS else other
        tgt[so] = tgt.get(so, 0.0) + flt(amt)
    for name, amt in je_pays:
        so = si_so.get(name)
        if so:
            other[so] = other.get(so, 0.0) + flt(amt)

    # cost lines per DN: (dn, item, qty, cost, price)
    price = {(r[0], r[1]): flt(r[2]) for r in price_rows}
    lines_by_dn = {}
    all_lines = []
    units = {}            # DN posting month -> [qty, cost]  (cost per unit sold)
    y0 = f"{year}-01-01"
    for dn, item, qty, cst in cost_rows:
        ln = (dn, item, flt(qty), flt(cst), price.get((dn, item), 0.0))
        lines_by_dn.setdefault(dn, []).append(ln)
        d = dn_by_name.get(dn)
        # item references come from THIS year's deliveries only: Nov–Dec of the
        # year before still carry the costs the vendor workbench later fixed
        # (an item verified at 29 showed a 118 "median" from 2025 lines)
        if d is not None and str(d.posting_date) >= y0:
            all_lines.append(ln)
        if d is not None:
            u = units.setdefault(str(d.posting_date)[:7], [0.0, 0.0])
            u[0] += ln[2]
            u[1] += ln[3]
    cref, pref = _item_refs(all_lines)

    months = {}
    rows = {}             # "YYYY-MM|bucket" -> drill rows

    def mrow(ym):
        return months.setdefault(ym, {
            "month": ym, "orders": 0, "order_value": 0.0, "cancelled": 0, "not_shipped": 0,
            "shipped": 0, "delivered": 0, "returned": 0, "open": 0, "invoiced": 0, "invoiced_value": 0.0,
            "collected": 0, "cod_collected": 0.0, "cogs": 0.0, "clean": 0,
            "exceptions": 0, "exception_value": 0.0, "watch": 0, "buckets": {}})

    for o in sos:
        m = mrow(o.ym)
        cancelled = o.docstatus == 2 or o.status == "Cancelled" or o.ss == "Cancelled"
        ex = bool(o.ex) or "-ex" in o.name
        out = [d for d in dn_by_so.get(o.name, [])]
        rdn = rdn_by_so.get(o.name, [])
        my_si = si_by_so.get(o.name, [])
        inv = sum(flt(s.gt) for s in my_si) + sum(flt(s.gt) for s in cn_by_so.get(o.name, []))
        pc, po = cath.get(o.name, 0.0), other.get(o.name, 0.0)
        b, outcome, cod, funded, ev, label = None, None, None, False, None, ""
        dn = None

        if cancelled:
            m["cancelled"] += 1
        else:
            m["orders"] += 1
            m["order_value"] += flt(o.gt)

        if out:
            dn = sorted(out, key=lambda d: (str(d.posting_date), d.name))[-1]
            outcome, cod, funded, ev, label = _carrier(dn, parcels, have_parcels, rdn)
            awbs = [d.awb for d in out if d.awb]
            if len(out) - len(rdn) > 1 and (len(set(awbs)) < len(awbs) or len(awbs) < len(out)):
                b = "dup_dn"

        if b:
            pass
        elif not out:
            if not cancelled:
                if my_si and inv > 1:
                    b = "invoice_no_shipment"
                else:
                    m["not_shipped"] += 1
        elif cancelled and outcome != "delivered":
            if not rdn and outcome != "returned":
                b = "cancelled_goods_out"
            elif outcome == "returned" and not rdn:
                b = "return_not_received"
        else:
            m["shipped"] += 1
            if outcome == "delivered":
                m["delivered"] += 1
                if not my_si or inv <= 0.5:
                    if ex:
                        b = "collected_no_invoice" if (cod or 0) > 0.5 else None
                    elif cod is not None and cod <= 0.5:
                        b = "prepaid_no_invoice"
                    elif funded:
                        b = "collected_no_invoice"
                    else:
                        b = "delivered_no_invoice"
                else:
                    m["invoiced"] += 1
                    m["invoiced_value"] += inv
                    if ex and cod is not None and inv > cod + 1:
                        b = "exchange_overbilled"
                    elif cod is not None and cod <= 0.5 and funded:
                        if pc > 0.5:
                            b = "prepaid_cod_receipt"
                        elif po < inv - 1:
                            b = "prepaid_unmatched"
                    elif cod is not None and cod > 0.5:
                        if not funded:
                            age = date_diff(today, ev) if ev else 0
                            b = "transfer_late" if age > FUND_DAYS else "awaiting_transfer"
                        elif pc < 0.5 and po < inv - 1:
                            b = "funded_no_receipt"
                        elif pc > 0.5 and abs(pc - cod) > 1:
                            gap = cod - pc
                            lump = o.ym <= SHIP_LUMP_UNTIL and SHIP_FEE[0] <= gap <= SHIP_FEE[1]
                            if not lump:
                                b = "amount_mismatch"
                    if b is None and abs(inv - pc - po) > 1:
                        b = "invoice_vs_paid"
                if funded:
                    m["collected"] += 1
                    m["cod_collected"] += flt(cod)
            elif outcome == "returned":
                m["returned"] += 1
                if pc > 0.5:
                    b = "returned_but_collected"
                elif inv > 1:
                    b = "returned_invoice_stands"
                elif not rdn:
                    age = date_diff(today, ev) if ev else date_diff(today, dn.posting_date)
                    b = "return_not_received" if age > WATCH_DAYS else "return_in_progress"
            elif outcome == "no_record":
                b = "no_carrier_record"
            else:
                m["open"] += 1
                if inv > 1:
                    b = "invoiced_not_delivered"
                else:
                    b = "in_transit" if date_diff(today, dn.posting_date) <= WATCH_DAYS else "stuck_at_carrier"

        # cost: every delivered parcel's stock cost, judged line by line
        dcost, cflag = 0.0, None
        if dn is not None and outcome == "delivered":
            rank = {"zero": 3, "high": 2, "low": 1}
            for d in out:
                for ln in lines_by_dn.get(d.name, []):
                    dcost += ln[3]
                    f = _line_flag(ln[1], ln[2], ln[3], ln[4], cref, pref)
                    if f and rank[f] > rank.get(cflag, 0):
                        cflag = f
            m["cogs"] += dcost
            if b is None and cflag:
                b = "cogs_" + cflag

        if b is None:
            if outcome in ("delivered", "returned"):
                m["clean"] += 1
            continue
        if b in WATCH:
            m["watch"] += 1
        else:
            m["exceptions"] += 1
        val = dcost if b.startswith("cogs_") else (inv if inv > 0.5 else (flt(cod) if cod else flt(o.gt)))
        bb = m["buckets"].setdefault(b, {"n": 0, "value": 0.0})
        bb["n"] += 1
        bb["value"] += val
        if b not in WATCH:
            m["exception_value"] += val
        key = f"{o.ym}|{b}"
        lst = rows.setdefault(key, [])
        if len(lst) < DRILL_CAP:
            lst.append({
                "so": o.name, "customer": o.customer, "dn": dn.name if dn else None,
                "awb": dn.awb if dn else None, "carrier": label,
                "si": my_si[0].name if my_si else None,
                "invoiced": round(inv, 2), "cod": None if cod is None else round(cod, 2),
                "cathedis_receipt": round(pc, 2), "other_receipt": round(po, 2),
                "cost": round(dcost, 2), "order_value": round(flt(o.gt), 2),
                "payment_type": o.pt, "exchange": 1 if ex else 0,
                # an exchange is never billed at its copied price — a person
                # bills the Sales Exchange difference
                "action": "review" if ex and BUCKETS.get(b) == "bill" else BUCKETS.get(b, "none"),
            })

    out_months = []
    for ym in sorted(months):
        m = months[ym]
        for k in ("order_value", "invoiced_value", "cod_collected", "cogs", "exception_value"):
            m[k] = round(m[k])
        for v in m["buckets"].values():
            v["value"] = round(v["value"])
        done = m["clean"] + m["exceptions"]
        m["clean_pct"] = round(100.0 * m["clean"] / done, 1) if done else None
        f = bank["funded"].get(ym, [0, 0.0])
        m["bank"] = {"funded_parcels": f[0], "cathedis_funded": round(f[1]),
                     "bank_credited": round(flt(bank["credited"].get(ym))),
                     "diff": round(flt(bank["credited"].get(ym)) - f[1])}
        out_months.append(m)

    _attach_money(out_months, money, units, bank, today)

    # items whose whole cost history sits above what they sell for — fix at the
    # source (Vendor Workbench), not order by order
    items = []
    for item, (med, n) in cref.items():
        p = pref.get(item)
        if n >= 5 and p and med >= p:
            items.append({"item": item, "deliveries": n, "unit_cost": round(med, 2),
                          "unit_price": round(p, 2), "ratio": round(med / p, 2)})
    items.sort(key=lambda r: -(r["unit_cost"] - r["unit_price"]) * r["deliveries"])

    tot = {}
    for k in ("orders", "order_value", "shipped", "delivered", "returned", "open", "invoiced",
              "invoiced_value", "collected", "cod_collected", "cogs", "clean", "exceptions",
              "exception_value", "watch", "not_shipped", "cancelled"):
        tot[k] = sum(m[k] for m in out_months)
    tot["money"] = {k: round(sum(flt(m["money"][k]) for m in out_months))
                    for k in ("sales", "invoices", "uncollected", "collected", "cathedis", "payzone",
                              "bank", "refunds", "cogs", "cogs_dn", "cogs_other", "margin")}
    tot["money"]["gm_pct"] = (round(100.0 * tot["money"]["margin"] / tot["money"]["sales"], 1)
                              if tot["money"]["sales"] else None)
    tot["anomalies"] = sum(len(m["anomalies"]) for m in out_months)
    done = tot["clean"] + tot["exceptions"]
    tot["clean_pct"] = round(100.0 * tot["clean"] / done, 1) if done else None
    tb = {}
    for m in out_months:
        for k, v in m["buckets"].items():
            t = tb.setdefault(k, {"n": 0, "value": 0})
            t["n"] += v["n"]
            t["value"] += v["value"]
    tot["buckets"] = tb

    last = frappe.db.get_default("ap_cathedis_sync_last")
    summary = {
        "company": company, "year": int(year), "built_on": str(now_datetime())[:19],
        "parcels": len(parcels), "cathedis_sync": frappe.parse_json(last) if last else None,
        "months": out_months, "total": tot, "actions": BUCKETS, "watch": list(WATCH),
        "items": items[:60],
    }
    return summary, rows


# ───────────────────────── money + month-level radar ─────────────────────────

PAYZONE = "108.021.006"


def _attach_money(out_months, money, units, bank, today):
    """Per month (posting date): sales, collections, cost of goods, margin —
    then the month-level radar: things that are not logical for a month even
    when every single order looks fine."""
    by = {m["month"]: m for m in out_months}

    def mm(ym):
        if ym not in by:   # a month with postings but no orders of its own
            by[ym] = {"month": ym, "orders": 0, "order_value": 0, "cancelled": 0, "not_shipped": 0,
                      "shipped": 0, "delivered": 0, "returned": 0, "open": 0, "invoiced": 0,
                      "invoiced_value": 0, "collected": 0, "cod_collected": 0, "cogs": 0, "clean": 0,
                      "exceptions": 0, "exception_value": 0, "watch": 0, "buckets": {}, "clean_pct": None,
                      "bank": {"funded_parcels": 0, "cathedis_funded": 0, "bank_credited": 0, "diff": 0}}
            out_months.append(by[ym])
        m = by[ym]
        m.setdefault("money", {"sales": 0.0, "invoices": 0, "credit_notes": 0.0, "uncollected": 0.0,
                               "collected": 0.0, "cathedis": 0.0, "payzone": 0.0, "bank": 0.0,
                               "refunds": 0.0, "cogs": 0.0, "cogs_dn": 0.0, "cogs_bills": 0.0,
                               "cogs_receipts": 0.0, "cogs_journals": 0.0, "cogs_other": 0.0})
        return m["money"]

    for m in list(out_months):
        mm(m["month"])
    for ym, is_ret, gt, os_, n in money["sales"]:
        x = mm(ym)
        x["sales"] += flt(gt)
        if is_ret:
            x["credit_notes"] += flt(gt)
        else:
            x["invoices"] += int(n)
            x["uncollected"] += flt(os_)
    for ym, ptype, acc, amt in money["receipts"]:
        x = mm(ym)
        if ptype == "Pay":
            x["refunds"] += flt(amt)
            continue
        key = "cathedis" if acc == CATHEDIS else ("payzone" if acc == PAYZONE else "bank")
        x[key] += flt(amt)
    for ym, vt, amt in money["cogs"]:
        x = mm(ym)
        x["cogs"] += flt(amt)
        k = {"Delivery Note": "cogs_dn", "Purchase Invoice": "cogs_bills",
             "Purchase Receipt": "cogs_receipts", "Journal Entry": "cogs_journals"}.get(vt, "cogs_other")
        x[k] += flt(amt)

    out_months.sort(key=lambda m: m["month"])
    cur = str(today)[:7]
    for m in out_months:
        x = m["money"]
        x["collected"] = x["cathedis"] + x["payzone"] + x["bank"] - x["refunds"]
        x["cogs_other"] = x["cogs"] - x["cogs_dn"]
        x["margin"] = x["sales"] - x["cogs"]
        x["gm_pct"] = round(100.0 * x["margin"] / x["sales"], 1) if x["sales"] else None
        q, c = units.get(m["month"], [0.0, 0.0])
        x["units"] = round(q)
        x["unit_cost"] = round(c / q, 2) if q else None
        for k, v in list(x.items()):
            if isinstance(v, float) and k not in ("gm_pct", "unit_cost"):
                x[k] = round(v)
        fin = m["delivered"] + m["returned"]
        m["return_rate"] = round(100.0 * m["returned"] / fin, 1) if fin else None

    closed = [m for m in out_months if m["month"] < cur]
    med_gm = _median([m["money"]["gm_pct"] for m in closed if m["money"]["gm_pct"] is not None])
    med_uc = _median([m["money"]["unit_cost"] for m in closed if m["money"]["unit_cost"]])
    med_rr = _median([m["return_rate"] for m in closed if m["return_rate"] is not None])

    for m in out_months:
        x, an = m["money"], []
        is_closed = m["month"] < cur
        if x["sales"] and x["cogs"] > x["sales"]:
            an.append({"key": "negative_margin", "sev": "high", "a": x["cogs"], "b": x["sales"]})
        elif is_closed and x["gm_pct"] is not None and med_gm and abs(x["gm_pct"] - med_gm) > 8:
            an.append({"key": "margin_off", "sev": "high" if abs(x["gm_pct"] - med_gm) > 15 else "medium",
                       "a": x["gm_pct"], "b": round(med_gm, 1)})
        if x["cogs"] and abs(x["cogs_other"]) > 0.03 * abs(x["cogs"]):
            an.append({"key": "cost_outside_deliveries", "sev": "high" if abs(x["cogs_other"]) > 0.15 * abs(x["cogs"]) else "medium",
                       "a": x["cogs_other"], "b": x["cogs_bills"], "c": x["cogs_journals"]})
        if x["unit_cost"] and med_uc and (x["unit_cost"] > 1.25 * med_uc or x["unit_cost"] < 0.8 * med_uc):
            an.append({"key": "unit_cost_jump", "sev": "medium", "a": x["unit_cost"], "b": round(med_uc, 2)})
        if is_closed and x["sales"] and x["uncollected"] > 0.01 * x["sales"]:
            an.append({"key": "uncollected", "sev": "high" if x["uncollected"] > 0.03 * x["sales"] else "medium",
                       "a": x["uncollected"], "b": x["sales"]})
        if x["sales"] and x["uncollected"] < -0.005 * x["sales"]:
            an.append({"key": "overcollected", "sev": "medium", "a": -x["uncollected"]})
        f, cr = flt(m["bank"]["cathedis_funded"]), flt(m["bank"]["bank_credited"])
        if is_closed and f and abs(cr - f) > 0.03 * f:
            an.append({"key": "bank_gap", "sev": "medium", "a": round(cr), "b": round(f)})
        if is_closed and m["return_rate"] is not None and med_rr and m["return_rate"] > med_rr + 8:
            an.append({"key": "returns_spike", "sev": "medium", "a": m["return_rate"], "b": round(med_rr, 1)})
        m["anomalies"] = an


def _path(company, year, part):
    d = frappe.get_site_path("private", "radar")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{frappe.scrub(company)}-{year}-{part}.json")


def _save(company, year, summary, rows):
    """The snapshot lives in a file — redis on this bench is cleared by other
    apps' cache resets, which dropped it twice on its first day. Redis is only
    a fast copy in front of the file."""
    for part, val in (("summary", summary), ("rows", rows)):
        tmp = _path(company, year, part) + ".tmp"
        with open(tmp, "w") as f:
            f.write(frappe.as_json(val, indent=None))
        os.replace(tmp, _path(company, year, part))
        frappe.cache().set_value(CK.format(company, year) + ":" + part, val)


def _read(company, year, part):
    hit = frappe.cache().get_value(CK.format(company, year) + ":" + part)
    if hit is not None:
        return hit
    try:
        with open(_path(company, year, part)) as f:
            val = frappe.parse_json(f.read())
    except FileNotFoundError:
        return None
    frappe.cache().set_value(CK.format(company, year) + ":" + part, val)
    return val


def rebuild(company="Justyol Morocco", year=None):
    """Build and store the snapshot (nightly, after the Cathedis sync)."""
    y = int(year or nowdate()[:4])
    if frappe.db.sql("SELECT GET_LOCK(%s, 0)", JOB)[0][0] != 1:
        return {"skipped": "already building"}
    try:
        summary, rows = _classify(company, y)
        _save(company, y, summary, rows)
    finally:
        frappe.db.sql("SELECT RELEASE_LOCK(%s)", JOB)
    return {"built_on": summary["built_on"]}


def _target(company):
    companies = resolve_companies(company)
    return company if (company and company in companies) else (companies[0] if companies else None)


@frappe.whitelist()
def summary(company=None, year=None):
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    y = int(year or nowdate()[:4])
    hit = _read(target, y, "summary")
    if hit is None:
        # first view ever: build it now, once
        rebuild(target, y)
        hit = _read(target, y, "summary")
    return hit or {"building": True}


@frappe.whitelist()
def drill(company=None, year=None, month=None, bucket=None, limit=100):
    """Rows behind one month × bucket (month 'all' = the whole year)."""
    assert_portal_access()
    target = _target(company)
    if not target or not bucket:
        return {"rows": []}
    y = int(year or nowdate()[:4])
    rows = _read(target, y, "rows") or {}
    lim = min(int(limit or 100), DRILL_CAP)
    if month and month != "all":
        lst = rows.get(f"{month}|{bucket}") or []
    else:
        lst = []
        for k in sorted(rows):
            if k.endswith("|" + bucket):
                lst.extend(rows[k])
    lst = sorted(lst, key=lambda r: -(r.get("invoiced") or r.get("cod") or r.get("cost") or 0))
    return {"rows": lst[:lim], "total": len(lst), "shown": min(len(lst), lim)}


@frappe.whitelist()
def month_docs(company=None, month=None, kind=None, limit=200):
    """The documents behind a month-level alert, read live (small, indexed):
    unpaid_invoices · overpaid_invoices · cost_outside (COGS not from a
    delivery note: supplier bills, journals, receipts posted straight to cost)."""
    assert_portal_access()
    target = _target(company)
    if not target or not month or kind not in ("unpaid_invoices", "overpaid_invoices", "cost_outside"):
        return {"rows": []}
    d0 = f"{month}-01"
    d1 = str(frappe.utils.get_last_day(d0))
    lim = min(int(limit or 200), 500)
    if kind == "cost_outside":
        rows = frappe.db.sql(
            """SELECT g.voucher_type doctype, g.voucher_no name, MIN(g.posting_date) date,
                      SUM(g.debit - g.credit) amount, MAX(g.against) party, MAX(a.account_name) note
               FROM `tabGL Entry` g JOIN `tabAccount` a ON a.name = g.account
               WHERE g.company = %s AND g.is_cancelled = 0 AND g.posting_date BETWEEN %s AND %s
                 AND a.account_type = 'Cost of Goods Sold' AND g.voucher_type != 'Delivery Note'
               GROUP BY g.voucher_type, g.voucher_no
               HAVING ABS(SUM(g.debit - g.credit)) > 0.5
               ORDER BY ABS(SUM(g.debit - g.credit)) DESC LIMIT %s""", (target, d0, d1, lim), as_dict=True)
    else:
        cond = "outstanding_amount > 0.5" if kind == "unpaid_invoices" else "outstanding_amount < -0.5"
        rows = frappe.db.sql(
            f"""SELECT 'Sales Invoice' doctype, name, posting_date date, outstanding_amount amount,
                       customer party, base_grand_total note
                FROM `tabSales Invoice`
                WHERE company = %s AND docstatus = 1 AND is_return = 0 AND posting_date BETWEEN %s AND %s
                  AND {cond}
                ORDER BY ABS(outstanding_amount) DESC LIMIT %s""", (target, d0, d1, lim), as_dict=True)
    for r in rows:
        r["date"] = str(r["date"])
        r["amount"] = round(flt(r["amount"]), 2)
        if kind != "cost_outside":
            r["note"] = round(flt(r["note"]), 2)
        elif r.get("party"):
            r["party"] = str(r["party"])[:60]
    return {"rows": rows, "total": len(rows)}


@frappe.whitelist()
def rebuild_now(company=None, year=None):
    """'Rebuild' button: one background build, never two at once."""
    assert_can_write()
    target = _target(company)
    frappe.enqueue("accounting_portal.api.radar.rebuild", queue="long", timeout=900,
                   job_id=JOB, deduplicate=True, company=target, year=int(year or nowdate()[:4]))
    return {"queued": True}


# ─────────────────────────────── the one write ───────────────────────────────
# A delivered order with no invoice: the same path a normal day takes
# (invoice_net.process — draft from the manifest, dated the shipping day,
# submitted with its COD receipt). Audited and deduped through _actions.

RADAR_BILL = "Radar Invoice Delivered Order"


def _bill_poster(action):
    p = frappe.parse_json(action.payload) if isinstance(action.payload, str) else action.payload
    res = frappe.get_attr("accounting_portal.api.invoice_net.process")(p["dn"], p["so"])
    si = frappe.db.sql_list(
        """SELECT DISTINCT si.name FROM `tabSales Invoice` si JOIN `tabSales Invoice Item` it ON it.parent = si.name
           WHERE si.docstatus = 1 AND si.is_return = 0 AND it.delivery_note = %s""", p["dn"])
    if not si:
        frappe.throw(f"Not invoiced: {res}")
    return {"voucher_type": "Sales Invoice", "voucher_no": si[0], "result": {"invoice_net": res}}


_actions.register_poster(RADAR_BILL, _bill_poster)


@frappe.whitelist()
def bill_order(company=None, so=None, dn=None):
    assert_can_write()
    target = _target(company)
    if not so or not dn or frappe.db.get_value("Delivery Note", dn, "company") != target:
        frappe.throw("Delivery note not found for this company")
    gt = flt(frappe.db.get_value("Sales Order", so, "base_grand_total"))
    return _actions.execute(RADAR_BILL, target, f"radar_bill:{dn}", payload={"so": so, "dn": dn},
                            amount=gt, reference_doctype="Delivery Note", reference_name=dn,
                            notes=f"Radar: invoice delivered order {so}")
