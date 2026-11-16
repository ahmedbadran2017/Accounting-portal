"""Partners — the numbers the company's partners follow, daily and monthly.

One read-only page (/accounting/partners, also installable as a phone app) for
people who hold the `Partner` role and nothing else. They never reach the rest
of the portal: `Partner` is deliberately NOT a portal role (permissions.py), so
every other endpoint keeps refusing them; only this module lets them in.

What each figure is, and where it comes from (Justyol Morocco, MAD, VAT included
— what the customer pays):

  orders        Sales Orders by order date; cancelled / duplicated ones and the
                bogus test orders above 20,000 MAD are left out
  confirmed     orders the call centre marked Confirmed
  shipped       non-return Delivery Notes (the parcel left the warehouse)
  delivered     Cathedis itself (the nightly `Cathedis Parcel` mirror): the
                parcel's delivery date and the amount it collected
  returned      return Delivery Notes (the goods are back in the warehouse)
  cash banked   Cathedis remittances that reached the bank (credits to the COD
                clearing account 108.021.003 from bank journal entries)
  at Cathedis   parcels Cathedis delivered and has not paid us for yet
  cash          the real bank and petty-cash accounts — never the clearing,
                intercompany or credit-card accounts that are typed "Bank"
  margin        estimated: modelled landed cost (pnl_estimated) against net
                revenue, on the last complete month; final once the container
                costing is locked

Advertising is not here on purpose: it is booked monthly, mostly in Türkiye, in
TRY — a daily figure from the books would be invented.

Phone notifications (Web Push) use no extra package: the server sends an EMPTY
push signed with a VAPID key (PyJWT + cryptography, both Frappe dependencies);
the service worker then asks `digest` for the text and shows it. Empty pushes
need no payload encryption, which is the part that would need pywebpush.
"""
import base64
import hashlib
import json
import time

import frappe
from frappe.utils import add_days, add_to_date, cint, date_diff, flt, get_datetime, getdate, now_datetime, nowdate

from accounting_portal.api.permissions import get_portal_role, has_all_access

CO = "Justyol Morocco"
ROLE_PARTNER = "Partner"
JUNK_ABOVE = 20000          # single orders above this are test / bogus (investor pack, Oct 2026)
CATHEDIS = "108.021.003"
TZ_SHIFT_H = -2             # server clock is Istanbul; partners read Morocco time
CACHE_KEY = "ap_partners:summary:v3"
MATURE_OPEN = 0.10          # a month's delivery rate is shown once ≤10% of its parcels are still moving
CACHE_TTL = 300
SUB_DT = "Partner Push Subscription"
_VAPID_KEY = "ap_partner_vapid"
_SUBJECT = "mailto:info@justyol.com"


# ── access ───────────────────────────────────────────────────────────────────

def is_partner(user=None):
    user = user or frappe.session.user
    return ROLE_PARTNER in set(frappe.get_roles(user))


def can_see(user=None):
    """Partners, and anyone who may open the portal (the owners check the page too)."""
    user = user or frappe.session.user
    if not user or user == "Guest":
        return False
    return is_partner(user) or has_all_access(user) or bool(get_portal_role(user))


def assert_partner_access():
    if not can_see():
        frappe.throw("Not permitted", frappe.PermissionError)


# ── small helpers ────────────────────────────────────────────────────────────

def _one(sql, args=()):
    r = frappe.db.sql(sql, args)
    return flt(r[0][0]) if r and r[0][0] is not None else 0.0


def _pct(a, b):
    return round((a - b) / b * 100, 1) if b else None


def _month_bounds(ym):
    y, m = int(ym[:4]), int(ym[5:7])
    ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
    return f"{ym}-01", str(add_days(f"{ny:04d}-{nm:02d}-01", -1))


def _prev_month(ym, k=1):
    y, m = int(ym[:4]), int(ym[5:7])
    for _ in range(k):
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return f"{y:04d}-{m:02d}"


_ORDER_OK = """company = %(co)s AND docstatus = 1 AND status != 'Cancelled'
               AND IFNULL(custom_sales_status, '') NOT IN ('Cancelled', 'Duplicated')
               AND base_grand_total <= %(junk)s"""


# ── the Morocco day ──────────────────────────────────────────────────────────
# The books date an order on the server's day (Istanbul), which ends at 22:00 in
# Morocco: at 22:25 a partner would see "tomorrow" with seven orders. Counts the
# page shows are therefore cut by the Morocco day from the order's creation time.
# (transaction_date is kept within a day of the window so a back-dated document
# created today never lands in today.)

def _m_today():
    return str(getdate(add_to_date(now_datetime(), hours=TZ_SHIFT_H)))


def _m_bounds(d0, d1):
    """Server-clock [start, end) of Morocco days d0..d1."""
    return (get_datetime(add_to_date(f"{d0} 00:00:00", hours=-TZ_SHIFT_H)),
            get_datetime(add_to_date(f"{add_days(d1, 1)} 00:00:00", hours=-TZ_SHIFT_H)))


def _m_args(d0, d1, until=None):
    s, e = _m_bounds(d0, d1)
    if until and until < e:
        e = until
    return {"co": CO, "junk": JUNK_ABOVE, "s": s, "e": e,
            "ta": add_days(d0, -1), "tb": add_days(d1, 1)}


_M_WINDOW = "creation >= %(s)s AND creation < %(e)s AND transaction_date BETWEEN %(ta)s AND %(tb)s"


def _m_orders(d0, d1, until=None):
    """(count, value, confirmed) of real orders placed on Morocco days d0..d1."""
    r = frappe.db.sql(f"""SELECT COUNT(*), SUM(base_grand_total), SUM(IFNULL(custom_sales_status, '') = 'Confirmed')
                          FROM `tabSales Order` WHERE {_ORDER_OK} AND {_M_WINDOW}""", _m_args(d0, d1, until))
    return int(r[0][0] or 0), flt(r[0][1]), int(flt(r[0][2]))


def _m_orders_by_day(d0, d1):
    a = _m_args(d0, d1)
    a["sh"] = TZ_SHIFT_H
    return {str(d): (int(n), flt(v)) for d, n, v in frappe.db.sql(
        f"""SELECT DATE(DATE_ADD(creation, INTERVAL %(sh)s HOUR)) d, COUNT(*), SUM(base_grand_total)
            FROM `tabSales Order` WHERE {_ORDER_OK} AND {_M_WINDOW} GROUP BY d""", a)}


def _m_hours(day):
    a = _m_args(day, day)
    a["sh"] = TZ_SHIFT_H
    hours = [0] * 24
    for h, n in frappe.db.sql(f"""SELECT HOUR(DATE_ADD(creation, INTERVAL %(sh)s HOUR)), COUNT(*)
                                  FROM `tabSales Order` WHERE {_ORDER_OK} AND {_M_WINDOW} GROUP BY 1""", a):
        hours[int(h) % 24] += int(n)
    return hours


# Where an order came from. Every channel lands as a Sales Order, so the counts
# above already hold them all; this only splits them:
#   shopify  the shop (Shopify order id / '#…' number)
#   landing  the landing pages (custom_channel 'Landing Page', utm fb/ig/…)
#   agent    the AI agent: channel 'Manual' created by the Guest API user, day and night
#   manual   the team keying an order by hand (channel 'Manual' by a real user, or none)
_CHANNEL = """CASE WHEN IFNULL(custom_channel, '') = 'Landing Page' THEN 'landing'
                   WHEN IFNULL(custom_channel, '') = 'Manual' AND owner = 'Guest' THEN 'agent'
                   WHEN IFNULL(shopify_order_id, '') != '' OR name LIKE '#%%' OR IFNULL(custom_order_source, '') != '' THEN 'shopify'
                   ELSE 'manual' END"""


def _m_channels(d0, d1):
    out = {"shopify": [0, 0.0], "landing": [0, 0.0], "agent": [0, 0.0], "manual": [0, 0.0]}
    for ch, n, v in frappe.db.sql(f"""SELECT {_CHANNEL} ch, COUNT(*), SUM(base_grand_total) FROM `tabSales Order`
                                      WHERE {_ORDER_OK} AND {_M_WINDOW} GROUP BY ch""", _m_args(d0, d1)):
        out[ch] = [int(n), round(flt(v))]
    return out


def _by_day(sql, d0, d1, args=None):
    a = {"co": CO, "a": d0, "b": d1}
    a.update(args or {})
    return {str(d): (flt(n), flt(v)) for d, n, v in frappe.db.sql(sql, a)}


def _shipped(d0, d1):
    return _by_day("""SELECT posting_date, COUNT(*), SUM(base_grand_total) FROM `tabDelivery Note`
                      WHERE company = %(co)s AND docstatus = 1 AND is_return = 0
                        AND posting_date BETWEEN %(a)s AND %(b)s GROUP BY posting_date""", d0, d1)


def _returned(d0, d1):
    return _by_day("""SELECT posting_date, COUNT(*), -SUM(base_grand_total) FROM `tabDelivery Note`
                      WHERE company = %(co)s AND docstatus = 1 AND is_return = 1
                        AND posting_date BETWEEN %(a)s AND %(b)s GROUP BY posting_date""", d0, d1)


def _delivered(d0, d1):
    return _by_day("""SELECT delivery_date, COUNT(*), SUM(amount) FROM `tabCathedis Parcel`
                      WHERE delivery_date BETWEEN %(a)s AND %(b)s GROUP BY delivery_date""", d0, d1)


def _banked(d0, d1):
    return _by_day("""SELECT posting_date, COUNT(DISTINCT voucher_no), SUM(credit - debit) FROM `tabGL Entry`
                      WHERE company = %(co)s AND is_cancelled = 0 AND account LIKE %(acc)s
                        AND voucher_type = 'Journal Entry' AND posting_date BETWEEN %(a)s AND %(b)s
                      GROUP BY posting_date""", d0, d1, {"acc": CATHEDIS + "%"})


def _series(day_map, days, idx):
    return [round(flt((day_map.get(d) or (0, 0))[idx]), 2) for d in days]


# ── sections ─────────────────────────────────────────────────────────────────

PERIODS = ("today", "yesterday", "7d", "30d", "month", "last_month")


def _window(key):
    """(d0, d1, prev0, prev1, live) in Morocco days. A single day compares with the
    same weekday a week before (Cathedis neither delivers nor pays on Sundays);
    a span compares with the span just before it; a month with the same days of
    the month before."""
    t = _m_today()
    if key == "yesterday":
        d = str(add_days(t, -1))
        return d, d, str(add_days(d, -7)), str(add_days(d, -7)), False
    if key in ("7d", "30d"):
        n = 7 if key == "7d" else 30
        d1 = str(add_days(t, -1))
        d0 = str(add_days(d1, -(n - 1)))
        return d0, d1, str(add_days(d0, -n)), str(add_days(d0, -1)), False
    if key == "month":
        d0 = t[:7] + "-01"
        p0, pe = _month_bounds(_prev_month(t[:7]))
        p1 = str(min(getdate(add_days(p0, date_diff(t, d0))), getdate(pe)))
        return d0, t, p0, p1, True
    if key == "last_month":
        d0, d1 = _month_bounds(_prev_month(t[:7]))
        p0, p1 = _month_bounds(_prev_month(t[:7], 2))
        return d0, d1, p0, p1, False
    return t, t, str(add_days(t, -7)), str(add_days(t, -7)), True


def _totals(d0, d1):
    sh, rt, dl, bk = _shipped(d0, d1), _returned(d0, d1), _delivered(d0, d1), _banked(d0, d1)
    tot = lambda m, i: round(sum(flt(v[i]) for v in m.values()), 2)
    return {"shipped": tot(sh, 0), "returned": tot(rt, 0), "delivered": tot(dl, 0),
            "delivered_value": tot(dl, 1), "banked": tot(bk, 1)}, (sh, rt, dl, bk)


def _period(key):
    key = key if key in PERIODS else "today"
    now = now_datetime()
    d0, d1, p0, p1, live = _window(key)
    single = d0 == d1
    n, v, conf = _m_orders(d0, d1)
    # what was left out of the count, so it reconciles with the shop's own list
    excl = frappe.db.sql(f"""SELECT SUM(IFNULL(custom_sales_status, '') = 'Duplicated'),
                                    SUM(status = 'Cancelled' OR IFNULL(custom_sales_status, '') = 'Cancelled')
                             FROM `tabSales Order` WHERE company = %(co)s AND docstatus = 1 AND {_M_WINDOW}""",
                         _m_args(d0, d1))
    out = {"key": key, "from": d0, "to": d1, "prev_from": p0, "prev_to": p1, "live": live,
           "excluded_duplicated": int(flt(excl[0][0])), "excluded_cancelled": int(flt(excl[0][1])),
           "single_day": single, "orders": n, "orders_value": round(v), "confirmed": conf,
           "avg_order": round(v / n, 1) if n else None}
    if key == "today":
        # like for like: what yesterday and last week had by this same minute
        y_n = _m_orders(str(add_days(d0, -1)), str(add_days(d0, -1)), add_days(now, -1))[0]
        w_n = _m_orders(p0, p1, add_days(now, -7))[0]
        out["compare"] = [{"k": "same_hour_yesterday", "prev": y_n, "pct": _pct(n, y_n)},
                          {"k": "same_hour_last_week", "prev": w_n, "pct": _pct(n, w_n)}]
        out["hour_now"] = (now.hour + TZ_SHIFT_H) % 24
    else:
        pn, pv, _pc = _m_orders(p0, p1)
        out["compare"] = [{"k": "previous", "prev": pn, "pct": _pct(n, pn)}]
        if key == "yesterday":
            b = str(add_days(d0, -1))
            bn = _m_orders(b, b)[0]
            out["compare"].append({"k": "day_before", "prev": bn, "pct": _pct(n, bn)})
        out["orders_value_prev"] = round(pv)
        out["avg_order_prev"] = round(pv / pn, 1) if pn else None
    # the chart: hours for a single day, days for a span
    if single:
        out["hours"] = _m_hours(d0)
    else:
        by = _m_orders_by_day(d0, d1)
        out["days"] = [{"d": str(add_days(d0, i)), "n": (by.get(str(add_days(d0, i))) or (0, 0))[0]}
                       for i in range(date_diff(d1, d0) + 1)]
    # the operational cards: totals for the period against the comparison window,
    # each with a day-by-day line (the week up to the day for a single day)
    cur, maps = _totals(d0, d1)
    prev, _pm = _totals(p0, p1)
    s0 = str(add_days(d1, -6)) if single else d0
    days = [str(add_days(s0, i)) for i in range(date_diff(d1, s0) + 1)]
    if single:
        maps = _totals(s0, d1)[1]
    by_o = _m_orders_by_day(s0, d1)
    sh, rt, dl, bk = maps
    out["cards"] = {k: {"value": cur[k], "prev": prev[k], "pct": _pct(cur[k], prev[k])} for k in cur}
    out["cards"]["avg_order"] = {"value": out["avg_order"], "prev": out.get("avg_order_prev"),
                                 "pct": _pct(out["avg_order"] or 0, out.get("avg_order_prev") or 0)
                                 if out.get("avg_order_prev") else None}
    if key == "today":
        yv = _m_orders(p0, p1)
        out["cards"]["avg_order"]["prev"] = round(yv[1] / yv[0], 1) if yv[0] else None
        out["cards"]["avg_order"]["pct"] = _pct(out["avg_order"] or 0, out["cards"]["avg_order"]["prev"] or 0) \
            if out["cards"]["avg_order"]["prev"] else None
    out["spark_days"] = days
    out["spark"] = {
        "shipped": _series(sh, days, 0), "returned": _series(rt, days, 0), "delivered": _series(dl, days, 0),
        "delivered_value": _series(dl, days, 1), "banked": _series(bk, days, 1),
        "avg_order": [round(by_o[d][1] / by_o[d][0], 1) if by_o.get(d, (0, 0))[0] else 0 for d in days],
    }
    out["channels"] = _m_channels(d0, d1)
    out["funnel"] = _funnel(d0, d1)
    return out


def _funnel(d0, d1):
    """The orders placed in the window, each counted at the furthest station it reached."""
    a = _m_args(d0, d1)
    received = int(_one(f"""SELECT COUNT(*) FROM `tabSales Order` WHERE company = %(co)s AND docstatus = 1
                            AND base_grand_total <= %(junk)s AND {_M_WINDOW}""", a))
    confirmed = int(_one(f"""SELECT COUNT(*) FROM `tabSales Order` WHERE {_ORDER_OK}
                             AND IFNULL(custom_sales_status, '') = 'Confirmed' AND {_M_WINDOW}""", a))
    row = frappe.db.sql("""
        SELECT COUNT(DISTINCT so.name),
               COUNT(DISTINCT IF(p.delivery_date IS NOT NULL OR p.status = 'PAID', so.name, NULL)),
               COUNT(DISTINCT IF(p.status = 'PAID', so.name, NULL))
        FROM `tabSales Order` so
        JOIN `tabDelivery Note Item` di ON di.against_sales_order = so.name
        JOIN `tabDelivery Note` dn ON dn.name = di.parent AND dn.docstatus = 1 AND dn.is_return = 0
        LEFT JOIN `tabCathedis Parcel` p ON p.awb = dn.custom_awb AND IFNULL(dn.custom_awb, '') != ''
        WHERE so.company = %(co)s AND so.docstatus = 1 AND so.base_grand_total <= %(junk)s
          AND so.creation >= %(s)s AND so.creation < %(e)s AND so.transaction_date BETWEEN %(ta)s AND %(tb)s""", a)
    shipped, delivered, collected = (int(x or 0) for x in row[0]) if row else (0, 0, 0)
    return {"from": d0, "to": d1, "received": received, "confirmed": confirmed,
            "shipped": shipped, "delivered": delivered, "collected": collected}


def _delivery_rate(d0, d1):
    """Of the parcels SHIPPED in the window, delivered against returned. Counting
    events by their own date overstates a recent month instead: a return is
    recorded a week or two after the delivery it failed, so the latest weeks show
    the deliveries but not yet their returns. Parcels still on the way are
    counted apart (`open`) and left out of the rate.
    Returns (rate %, delivered, returned, open)."""
    r = frappe.db.sql("""
        SELECT COUNT(DISTINCT dn.name),
               COUNT(DISTINCT IF(p.status = 'PAID' OR p.delivery_status = 'Livré' OR p.delivery_date IS NOT NULL,
                                 dn.name, NULL)),
               COUNT(DISTINCT IF((p.status = 'RETURN_CUSTOMER' OR rdn.name IS NOT NULL)
                                 AND NOT (IFNULL(p.status, '') = 'PAID' OR IFNULL(p.delivery_status, '') = 'Livré'
                                          OR p.delivery_date IS NOT NULL), dn.name, NULL))
        FROM `tabDelivery Note` dn
        LEFT JOIN `tabCathedis Parcel` p ON p.awb = dn.custom_awb AND IFNULL(dn.custom_awb, '') != ''
        LEFT JOIN `tabDelivery Note` rdn ON rdn.return_against = dn.name AND rdn.docstatus = 1 AND rdn.is_return = 1
        WHERE dn.company = %s AND dn.docstatus = 1 AND dn.is_return = 0 AND dn.posting_date BETWEEN %s AND %s""",
                      (CO, d0, d1))
    shipped, dl, rt = (int(x or 0) for x in r[0]) if r else (0, 0, 0)
    rate = round(dl / (dl + rt) * 100, 1) if (dl + rt) else None
    return rate, dl, rt, max(0, shipped - dl - rt)


def _courier_per_parcel(ym):
    d0, d1 = _month_bounds(ym)
    cost = _one("""SELECT SUM(debit - credit) FROM `tabGL Entry` WHERE company = %s AND is_cancelled = 0
                   AND (account LIKE '770.07.004%%' OR account LIKE '770.07.008%%')
                   AND posting_date BETWEEN %s AND %s""", (CO, d0, d1))
    parcels = _one("""SELECT COUNT(*) FROM `tabDelivery Note` WHERE company = %s AND docstatus = 1
                      AND is_return = 0 AND posting_date BETWEEN %s AND %s""", (CO, d0, d1))
    return (round(cost / parcels, 1) if parcels and cost > 0 else None), round(cost)


def _margin(ym):
    """Estimated gross margin on a month: net revenue against the modelled landed
    cost of the units delivered (the same model as the estimated P&L)."""
    try:
        from accounting_portal.api.pnl_estimated import _unit_costs
        costs, _meta = _unit_costs(CO)
    except Exception:
        return None
    d0, d1 = _month_bounds(ym)
    revenue = _one("""SELECT SUM(g.credit - g.debit) FROM `tabGL Entry` g JOIN `tabAccount` a ON a.name = g.account
                      WHERE g.company = %s AND g.is_cancelled = 0 AND a.root_type = 'Income'
                        AND (a.name LIKE '600.002%%' OR a.name LIKE '600.903%%')
                        AND g.posting_date BETWEEN %s AND %s""", (CO, d0, d1))
    product = covered = units = 0.0
    for ic, q in frappe.db.sql("""SELECT item_code, SUM(-actual_qty) FROM `tabStock Ledger Entry`
                                  WHERE company = %s AND is_cancelled = 0 AND voucher_type = 'Delivery Note'
                                    AND posting_date BETWEEN %s AND %s GROUP BY item_code""", (CO, d0, d1)):
        q = flt(q)
        units += q
        c = costs.get(ic)
        if c and flt(c.get("cost")) > 0:
            product += q * flt(c["cost"])
            covered += q
    if revenue <= 0 or not units:
        return None
    share = covered / units
    if share < 0.6:
        return {"month": ym, "pct": None, "coverage": round(share * 100)}
    # scale the covered cost to all units (the uncovered ones sell at the same mix)
    cost_all = product / share if share else product
    return {"month": ym, "pct": round((revenue - cost_all) / revenue * 100, 1), "coverage": round(share * 100)}


def _mtd():
    today = _m_today()
    ym = today[:7]
    d0 = f"{ym}-01"
    day_n = getdate(today).day
    pm = _prev_month(ym)
    p0, p_end = _month_bounds(pm)
    p1 = str(min(getdate(add_days(p0, day_n - 1)), getdate(p_end)))
    n, v, _c = _m_orders(d0, today)
    pn, pv, _pc = _m_orders(p0, p1)
    dv = _one("SELECT SUM(amount) FROM `tabCathedis Parcel` WHERE delivery_date BETWEEN %s AND %s", (d0, today))
    pdv = _one("SELECT SUM(amount) FROM `tabCathedis Parcel` WHERE delivery_date BETWEEN %s AND %s", (p0, p1))
    # the running month's parcels are mostly still on the way: count them, and
    # take the rate from the latest month whose parcels have (nearly) all ended
    _r, dl, rt, still_open = _delivery_rate(d0, today)
    rate_month = rate = prate = None
    for k in (1, 2, 3):
        m = _prev_month(ym, k)
        a, b = _month_bounds(m)
        r_, dl_, rt_, op_ = _delivery_rate(a, b)
        if r_ is not None and op_ <= MATURE_OPEN * (dl_ + rt_ + op_):
            rate_month, rate = m, r_
            pa, pb = _month_bounds(_prev_month(m))
            prate = _delivery_rate(pa, pb)[0]
            break
    # courier bills land at (or after) month end: take the latest month that has them
    courier = courier_prev = None
    courier_month = pm
    for k in (1, 2, 3):
        m = _prev_month(ym, k)
        c, _total = _courier_per_parcel(m)
        if c:
            courier, courier_month = c, m
            courier_prev = _courier_per_parcel(_prev_month(m))[0]
            break
    return {
        "from": d0, "to": today, "prev_from": p0, "prev_to": p1, "last_month": pm,
        "orders": n, "orders_prev": pn, "orders_value": round(v), "orders_value_prev": round(pv),
        "orders_value_delta_pct": _pct(v, pv),
        "delivered_value": round(dv), "delivered_value_prev": round(pdv), "delivered_value_delta_pct": _pct(dv, pdv),
        "delivery_rate": rate, "delivery_rate_prev": prate, "delivery_rate_month": rate_month,
        "delivery_rate_delta_pt": round(rate - prate, 1) if rate is not None and prate is not None else None,
        "delivered_parcels": dl, "returned_parcels": rt, "open_parcels": still_open,
        "avg_order": round(v / n, 1) if n else None, "avg_order_prev": round(pv / pn, 1) if pn else None,
        "courier_per_parcel": courier, "courier_per_parcel_prev": courier_prev, "courier_month": courier_month,
        "margin": _margin(pm),
    }


_NOT_CASH = ("108.", "133.", "102.001.400")


def _cash():
    rows = frappe.db.sql("""SELECT a.name, a.account_name, SUM(g.debit - g.credit) FROM `tabAccount` a
                            JOIN `tabGL Entry` g ON g.account = a.name AND g.is_cancelled = 0
                            WHERE a.company = %s AND a.account_type IN ('Bank', 'Cash') AND a.is_group = 0
                            GROUP BY a.name""", (CO,))
    accounts = []
    for name, label, bal in rows:
        bal = flt(bal)
        low = (label or name).lower()
        if name.startswith(_NOT_CASH) or "credit" in low or "write off" in low or abs(bal) < 1:
            continue
        accounts.append({"account": label or name, "balance": round(bal)})
    accounts.sort(key=lambda x: -x["balance"])
    cod = frappe.db.sql("""SELECT COUNT(*), SUM(amount) FROM `tabCathedis Parcel`
                           WHERE status = 'UNPAID' AND delivery_status = 'Livré'""")
    stock = frappe.db.sql("""SELECT SUM(b.stock_value), SUM(b.actual_qty) FROM `tabBin` b
                             JOIN `tabWarehouse` w ON w.name = b.warehouse
                             WHERE w.company = %s AND b.actual_qty > 0 AND w.name NOT LIKE 'Container %%'""", (CO,))
    suppliers = _one("""SELECT SUM(g.credit - g.debit) FROM `tabGL Entry` g JOIN `tabAccount` a ON a.name = g.account
                        WHERE g.company = %s AND g.is_cancelled = 0 AND a.account_type = 'Payable'
                          AND g.party_type = 'Supplier'""", (CO,))
    return {
        "banks": sum(a["balance"] for a in accounts), "accounts": accounts,
        "cod_at_carrier": round(flt(cod[0][1])) if cod else 0, "cod_parcels": int(cod[0][0] or 0) if cod else 0,
        "stock_value": round(flt(stock[0][0])) if stock else 0, "stock_units": round(flt(stock[0][1])) if stock else 0,
        "suppliers_balance": round(suppliers),
    }


def _containers():
    """Containers still at sea: their warehouse still holds the goods."""
    out = []
    for w, units, skus in frappe.db.sql("""SELECT b.warehouse, SUM(b.actual_qty), COUNT(*) FROM `tabBin` b
                                           JOIN `tabWarehouse` w ON w.name = b.warehouse
                                           WHERE w.company = %s AND w.name LIKE 'Container %%' AND b.actual_qty > 0
                                             AND b.item_code != 'Pallets'
                                           GROUP BY b.warehouse""", (CO,)):
        # a container still at sea has not been emptied at all; leftovers in an
        # arrived container's warehouse (stock moved between containers) are not a ship
        if _one("""SELECT COUNT(*) FROM `tabStock Ledger Entry` WHERE warehouse = %s AND is_cancelled = 0
                   AND actual_qty < 0""", (w,)):
            continue
        no = cint("".join(ch for ch in w.split("-")[0] if ch.isdigit()))
        d = frappe.db.get_value("Shipment Costing", {"company": CO, "container_no": no},
                                ["name", "container_id", "shipped_on"], as_dict=True) if no else None
        kg = _one("SELECT SUM(gross_kg) FROM `tabShipment Costing Line` WHERE parent = %s", (d.name,)) if d else 0
        shipped_on = str(d.shipped_on) if d and d.shipped_on else None
        out.append({"no": no, "container_id": (d.container_id if d else "") or "", "shipped_on": shipped_on,
                    "days_at_sea": (getdate(nowdate()) - getdate(shipped_on)).days if shipped_on else None,
                    "units": round(flt(units)), "skus": int(skus), "kg": round(kg)})
    out.sort(key=lambda x: -x["no"])
    return out


def _months():
    """The last twelve months, the running one last."""
    today = _m_today()
    ym = today[:7]
    out = []
    for k in range(11, -1, -1):
        m = _prev_month(ym, k)
        d0, d1 = _month_bounds(m)
        d1 = min(d1, today)
        n, v, _c = _m_orders(d0, d1)
        dv = _one("SELECT SUM(amount) FROM `tabCathedis Parcel` WHERE delivery_date BETWEEN %s AND %s", (d0, d1))
        rate, dl, rt, still_open = _delivery_rate(d0, d1)
        mature = rate is not None and still_open <= MATURE_OPEN * (dl + rt + still_open)
        out.append({"month": m, "orders": n, "orders_value": round(v), "delivered_value": round(dv),
                    "delivery_rate": rate if mature else None, "complete": m != ym})
    return out


def _common():
    return {"company": CO, "currency": "MAD", "generated_at": str(now_datetime())[:16], "tz_shift": TZ_SHIFT_H,
            "morocco_today": _m_today(), "mtd": _mtd(), "cash": _cash(), "containers": _containers(),
            "months": _months()}


def _cached(key, fn, fresh=False):
    cache = frappe.cache()
    if not fresh:
        hit = cache.get_value(key)
        if hit:
            return hit
    val = fn()
    cache.set_value(key, val, expires_in_sec=CACHE_TTL)
    return val


def warm():
    """Hourly: rebuild the shared sections and today, so a partner opening the app
    never waits for the cost model (~9 s cold)."""
    try:
        _cached(CACHE_KEY, _common, fresh=True)
        _cached(CACHE_KEY + ":p:today", lambda: _period("today"), fresh=True)
    except Exception:
        frappe.log_error(title="Partners summary warm-up failed")


@frappe.whitelist()
def get_summary(period="today", fresh=0):
    """Everything the page shows: the chosen period (today, yesterday, 7d, 30d,
    month, last_month) plus the month, cash, containers and twelve months —
    each cached five minutes (the page refreshes itself)."""
    assert_partner_access()
    period = period if period in PERIODS else "today"
    data = dict(_cached(CACHE_KEY, _common, cint(fresh)))
    data["period"] = _cached(CACHE_KEY + ":p:" + period, lambda: _period(period), cint(fresh))
    return data


# ── phone notifications (Web Push, empty pushes signed with VAPID) ───────────

def _b64u(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _vapid():
    """(private PEM, public key base64url) — made once, kept in Defaults."""
    raw = frappe.db.get_default(_VAPID_KEY)
    if raw:
        try:
            k = json.loads(raw)
            return k["private_pem"], k["public"]
        except Exception:
            pass
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    pub = _b64u(key.public_key().public_bytes(serialization.Encoding.X962,
                                              serialization.PublicFormat.UncompressedPoint))
    frappe.db.set_default(_VAPID_KEY, json.dumps({"private_pem": pem, "public": pub}))
    return pem, pub


@frappe.whitelist()
def push_key():
    assert_partner_access()
    return {"public_key": _vapid()[1]}


@frappe.whitelist()
def push_subscribe(subscription=None, user_agent=None):
    """Remember this phone/browser for the morning summary."""
    assert_partner_access()
    sub = json.loads(subscription) if isinstance(subscription, str) else (subscription or {})
    endpoint = (sub.get("endpoint") or "").strip()
    if not endpoint.startswith("ht" + "tps://"):
        frappe.throw("Invalid subscription")
    key = hashlib.sha1(endpoint.encode()).hexdigest()
    if frappe.db.exists(SUB_DT, key):
        frappe.db.set_value(SUB_DT, key, {"user": frappe.session.user, "enabled": 1})
    else:
        frappe.get_doc({"doctype": SUB_DT, "name": key, "endpoint_hash": key, "user": frappe.session.user,
                        "endpoint": endpoint, "user_agent": (user_agent or "")[:140], "enabled": 1}
                       ).insert(ignore_permissions=True)
    return {"ok": True, "count": frappe.db.count(SUB_DT, {"user": frappe.session.user, "enabled": 1})}


@frappe.whitelist()
def push_unsubscribe(endpoint=None):
    assert_partner_access()
    if endpoint:
        key = hashlib.sha1(endpoint.strip().encode()).hexdigest()
        if frappe.db.exists(SUB_DT, key) and frappe.db.get_value(SUB_DT, key, "user") == frappe.session.user:
            frappe.delete_doc(SUB_DT, key, ignore_permissions=True, force=1)
    return {"ok": True}


def _fmt(v):
    return f"{flt(v):,.0f}"


def _digest_text(lang="ar"):
    """Yesterday in one line: orders, deliveries, cash banked."""
    yday = str(add_days(_m_today(), -1))
    n, v, _c = _m_orders(yday, yday)
    dl = _delivered(yday, yday).get(yday, (0, 0))
    bk = _banked(yday, yday).get(yday, (0, 0))
    if lang == "en":
        title = "Justyol · yesterday"
        body = (f"{_fmt(n)} orders ({_fmt(v)} MAD) · {_fmt(dl[0])} delivered"
                + f" · {_fmt(bk[1])} MAD banked")
    else:
        title = "Justyol · أرقام إمبارح"
        body = (f"{_fmt(n)} طلب ({_fmt(v)} د.م) · اتسلّم {_fmt(dl[0])}"
                + f" · دخل البنك {_fmt(bk[1])} د.م")
    return {"title": title, "body": body, "url": "/accounting/partners", "tag": "partners-daily-" + yday}


@frappe.whitelist()
def digest(lang="ar"):
    """What the phone shows when a push arrives (the push itself carries nothing)."""
    assert_partner_access()
    return _digest_text("en" if lang == "en" else "ar")


def _send_one(endpoint, pem, pub):
    import jwt
    import requests
    from urllib.parse import urlparse
    u = urlparse(endpoint)
    token = jwt.encode({"aud": f"{u.scheme}://{u.netloc}", "exp": int(time.time()) + 12 * 3600, "sub": _SUBJECT},
                       pem, algorithm="ES256")
    if isinstance(token, bytes):
        token = token.decode()
    r = requests.post(endpoint, data=b"", timeout=10, headers={
        "TTL": "43200", "Urgency": "normal", "Content-Length": "0",
        "Authorization": f"vapid t={token}, k={pub}"})
    return r.status_code


def _push(users=None):
    pem, pub = _vapid()
    filters = {"enabled": 1}
    if users:
        filters["user"] = ["in", users]
    sent = gone = failed = 0
    for s in frappe.get_all(SUB_DT, filters=filters, fields=["name", "endpoint"]):
        try:
            code = _send_one(s.endpoint, pem, pub)
        except Exception:
            code = 0
        if code in (200, 201, 202, 204):
            sent += 1
            frappe.db.set_value(SUB_DT, s.name, {"last_sent": now_datetime(), "last_status": str(code)},
                                update_modified=False)
        elif code in (404, 410):
            gone += 1
            frappe.delete_doc(SUB_DT, s.name, ignore_permissions=True, force=1)
        else:
            failed += 1
            frappe.db.set_value(SUB_DT, s.name, "last_status", str(code), update_modified=False)
    frappe.db.commit()
    return {"sent": sent, "removed": gone, "failed": failed}


def send_daily_digest():
    """Scheduler (09:00 Morocco): every subscribed phone gets yesterday's numbers."""
    if not frappe.db.count(SUB_DT, {"enabled": 1}):
        return
    try:
        _push()
    except Exception:
        frappe.log_error(title="Partners push digest failed")


@frappe.whitelist()
def push_test():
    """Send the summary now to my own phones — the page's "try it" button."""
    assert_partner_access()
    return _push([frappe.session.user])


# ── the installable app: service worker + manifest at the site root ──────────

class PartnersPwaRenderer:
    """Serves /partners-sw.js and /partners.webmanifest from the app.

    A service worker can only control pages at or below its own URL, and the
    built assets live under /assets/…; serving it from the site root lets it
    control /accounting/partners. Registered through the `page_renderer` hook."""

    FILES = {
        # on disk with an underscore: frappe.get_app_path scrubs "-" to "_"
        "partners-sw.js": ("partners_sw.js", "application/javascript"),
        "partners.webmanifest": ("partners.webmanifest", "application/manifest+json"),
    }

    def __init__(self, path=None, http_status_code=None):
        self.path = (path or "").strip("/")
        self.http_status_code = http_status_code or 200

    def can_render(self):
        return self.path in self.FILES

    def render(self):
        from werkzeug.wrappers import Response
        fname, mime = self.FILES[self.path]
        with open(frappe.get_app_path("accounting_portal", "pwa", fname)) as f:
            body = f.read()
        headers = {"Cache-Control": "no-cache"}
        if fname.endswith(".js"):
            headers["Service-Worker-Allowed"] = "/accounting/partners"
        return Response(body, status=200, mimetype=mime, headers=headers)
