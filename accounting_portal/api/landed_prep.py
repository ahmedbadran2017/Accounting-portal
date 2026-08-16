"""Landed-basis preparation (B4) — turn the year's inbound import charges into
ONE trusted, human-approved landed cost per kg (and per item via weight).

Why: the single catalogue crawl (Verify & Fix) must apply the FULL true cost —
product + inbound landed — in one pass. The landed component therefore needs to
be prepared and FROZEN first:

    1. charge_pool(year): every freight/customs/handling account with 2026
       activity, with a suggested inbound/outbound classification the team can
       override per account (Cathedis last-mile & couriers are SELLING costs and
       stay OPEX — never landed).
    2. kg base: ACTUAL imported kg for the year (non-local receipts × item
       weight; 2026 coverage ≈ 93%, extrapolated to 100%).
    3. freeze_basis(): Super Admin locks pool ÷ kg into ap_landed_basis_<year>.
       From then on landed_unit(item) = frozen rate × weight — the number the
       Verify & Fix screen adds on top of the product cost.

Analysis + configuration only — nothing here posts to the GL.
"""
import json

import frappe
from frappe.utils import flt, now_datetime

from accounting_portal.api.permissions import (
    assert_can_write, assert_portal_access, can_manage_users, resolve_companies)

SALES = "Justyol Morocco"
_DOMESTIC_GROUPS = ("Morocco Local Suppliers", "Local")

# Accounts that are OUTBOUND (selling/delivery) by nature — suggested excluded.
_OUTBOUND_HINTS = ("cathadis cargo", "cathedis cargo", "aramex", "local delivery",
                   "bisfor logistic", "last mile")
# Accounts that are INBOUND import costs — suggested included.
# NOTE: 153.03 (Expenses Included In Valuation) is deliberately NOT here — a
# charge parked in that clearing account may still get capitalized onto a
# specific receipt via a Landed Cost Voucher; including it in the pool AND
# LCV-ing it would double-count. It surfaces as "review" for the team to decide.
_INBOUND_HINTS = ("sea freight", "custom duty", "custom agent", "customs",
                  "inspection", "stuffing", "haulage", "demurrage", "container",
                  "clearance", "forklift")


def _target(company):
    companies = resolve_companies(company)
    if not companies:
        return None
    return company if (company and company in companies) else companies[0]


def _suggest(account_name):
    n = account_name.lower()
    for h in _OUTBOUND_HINTS:
        if h in n:
            return "outbound"
    for h in _INBOUND_HINTS:
        if h in n:
            return "inbound"
    return "review"   # e.g. the 770.07 parent with per-order sync noise


def _overrides_key(year):
    return f"ap_landed_pool_incl_{year}"


def _basis_key(year):
    return f"ap_landed_basis_{year}"


def _get_overrides(year):
    try:
        return json.loads(frappe.db.get_default(_overrides_key(year)) or "{}")
    except Exception:
        return {}


@frappe.whitelist()
def charge_pool(company=None, year=2026):
    """The year's charge accounts with net amounts, suggested classification and
    the team's include/exclude decision. Also the kg base + resulting rate."""
    assert_portal_access()
    target = _target(company) or SALES
    year = int(year)
    rows = frappe.db.sql(
        """SELECT g.account, ROUND(SUM(g.debit-g.credit),0) net, COUNT(*) entries
           FROM `tabGL Entry` g
           WHERE g.company=%s AND g.is_cancelled=0 AND YEAR(g.posting_date)=%s
             AND (g.account LIKE '770.07%%' OR g.account LIKE '770.0.7%%'
                  OR g.account LIKE '153.03%%' OR g.account LIKE '770.04%%'
                  OR g.account LIKE '770.05.012%%')
           GROUP BY g.account
           HAVING ABS(SUM(g.debit-g.credit))>100
           ORDER BY ABS(SUM(g.debit-g.credit)) DESC""", (target, year), as_dict=True)
    ov = _get_overrides(year)
    pool = 0.0
    for r in rows:
        r["suggested"] = _suggest(r.account)
        r["included"] = bool(ov[r.account]) if r.account in ov else (r.suggested == "inbound")
        r["net"] = flt(r.net)
        if r["included"]:
            pool += r["net"]
    kg = kg_stats(target, year)
    est_kg = flt(kg.get("est_kg"))
    rate = round(pool / est_kg, 2) if est_kg > 0 and pool > 0 else 0.0
    basis = get_basis(year=year)
    return {"company": target, "year": year, "rows": rows,
            "pool": round(pool), "kg": kg, "rate_kg": rate, "frozen": basis}


def kg_stats(target, year):
    """ACTUAL imported kg for the year: non-local receipts × item weight,
    extrapolated over the (small) unweighted remainder."""
    row = frappe.db.sql(
        """SELECT
             SUM(CASE WHEN IFNULL(i.weight_per_unit,0)>0 THEN pri.qty*i.weight_per_unit ELSE 0 END) kg_w,
             SUM(CASE WHEN IFNULL(i.weight_per_unit,0)>0 THEN pri.qty ELSE 0 END) units_w,
             SUM(pri.qty) units_all
           FROM `tabPurchase Receipt Item` pri
           JOIN `tabPurchase Receipt` pr ON pr.name=pri.parent
           JOIN `tabItem` i ON i.name=pri.item_code
           LEFT JOIN `tabSupplier` s ON s.name=pr.supplier
           WHERE pr.company=%s AND pr.docstatus=1 AND YEAR(pr.posting_date)=%s
             AND IFNULL(s.supplier_group,'') NOT IN %s""",
        (target, int(year), _DOMESTIC_GROUPS), as_dict=True)[0]
    kg_w, units_w, units_all = flt(row.kg_w), flt(row.units_w), flt(row.units_all)
    avg = kg_w / units_w if units_w else 0.0
    return {"kg_weighted": round(kg_w), "units_weighted": round(units_w),
            "units_all": round(units_all),
            "coverage_pct": round(100 * units_w / units_all, 1) if units_all else 0,
            "est_kg": round(avg * units_all) if units_all else 0}


@frappe.whitelist()
def set_pool_include(company=None, year=2026, account=None, included=None):
    """Team decision: include/exclude one account from the landed pool.
    Blocked once the basis is frozen (unfreeze first)."""
    assert_can_write()
    if get_basis(year=year):
        frappe.throw("Basis is frozen — a Super Admin must unfreeze before reclassifying")
    if not account:
        frappe.throw("account required")
    ov = _get_overrides(int(year))
    ov[account] = 1 if str(included) in ("1", "true", "True", "yes") else 0
    frappe.db.set_default(_overrides_key(int(year)), json.dumps(ov))
    frappe.db.commit()
    return charge_pool(company=company, year=year)


@frappe.whitelist()
def get_basis(year=2026):
    """The frozen landed basis for the year, or None."""
    try:
        b = json.loads(frappe.db.get_default(_basis_key(int(year))) or "null")
        return b or None
    except Exception:
        return None


# ── Two-channel model: AIR (door-to-door tariff per kg, date-banded) vs SEA
# (pooled bills ÷ sea kg). The unit of classification is the PURCHASE RECEIPT —
# one PR = one shipment, so each PR carries its channel and its landed cost. ──

def _air_key(year):
    return f"ap_air_rates_{year}"


def _chan_key(year):
    return f"ap_pr_channel_{year}"


def get_air_rates(year=2026):
    """Date-banded air tariff [{from, rate}] sorted ascending. The team edits
    these (100 → 110 → 126 MAD/kg over 2026)."""
    try:
        rates = json.loads(frappe.db.get_default(_air_key(int(year))) or "[]")
    except Exception:
        rates = []
    return sorted(rates, key=lambda r: r.get("from") or "")


def _air_rate_at(rates, date):
    val = 0.0
    for r in rates:
        if str(r.get("from") or "")[:10] <= str(date)[:10]:
            val = flt(r.get("rate"))
    return val


@frappe.whitelist()
def set_air_rates(year=2026, rates=None):
    """Replace the air-tariff bands. Blocked once frozen."""
    assert_can_write()
    if get_basis(year=year):
        frappe.throw("Basis is frozen — unfreeze before editing air rates")
    rates = json.loads(rates) if isinstance(rates, str) else (rates or [])
    clean = []
    for r in rates:
        d, v = str(r.get("from") or "")[:10], flt(r.get("rate"))
        if len(d) == 10 and v > 0:
            clean.append({"from": d, "rate": v})
    frappe.db.set_default(_air_key(int(year)), json.dumps(sorted(clean, key=lambda x: x["from"])))
    frappe.db.commit()
    return get_air_rates(year)


def _channels(year):
    try:
        return json.loads(frappe.db.get_default(_chan_key(int(year))) or "{}")
    except Exception:
        return {}


def _import_receipts(target, year):
    """The year's import PRs (non-local) with their kg and suggested channel
    (sea when any line landed in a Container* warehouse, else air)."""
    rows = frappe.db.sql(
        """SELECT pr.name, pr.posting_date dt, pr.supplier,
                  ROUND(SUM(pri.qty),0) qty,
                  ROUND(SUM(pri.qty*IFNULL(i.weight_per_unit,0)),1) kg,
                  MAX(CASE WHEN pri.warehouse LIKE 'Container%%' THEN 1 ELSE 0 END) has_container
           FROM `tabPurchase Receipt` pr
           JOIN `tabPurchase Receipt Item` pri ON pri.parent=pr.name
           JOIN `tabItem` i ON i.name=pri.item_code
           LEFT JOIN `tabSupplier` s ON s.name=pr.supplier
           WHERE pr.company=%s AND pr.docstatus=1 AND YEAR(pr.posting_date)=%s
             AND IFNULL(s.supplier_group,'') NOT IN %s
           GROUP BY pr.name ORDER BY pr.posting_date DESC""",
        (target, int(year), _DOMESTIC_GROUPS), as_dict=True)
    ov = _channels(year)
    for r in rows:
        r["suggested"] = "sea" if r.has_container else "air"
        r["channel"] = ov.get(r.name) or r["suggested"]
        r["dt"] = str(r.dt or "")
    return rows


@frappe.whitelist()
def set_pr_channel(company=None, year=2026, pr=None, channel=None):
    """Team decision: this shipment (PR) came by air or sea. Blocked when frozen."""
    assert_can_write()
    if get_basis(year=year):
        frappe.throw("Basis is frozen — unfreeze before reclassifying shipments")
    if not pr or channel not in ("air", "sea"):
        frappe.throw("pr + channel (air|sea) required")
    ov = _channels(int(year))
    ov[pr] = channel
    frappe.db.set_default(_chan_key(int(year)), json.dumps(ov))
    frappe.db.commit()
    return {"pr": pr, "channel": channel}


@frappe.whitelist()
def shipment_review(company=None, year=2026):
    """The full two-channel picture for the basis screen: air tariff bands, the
    PR classification list (each with its computed landed), sea pool ÷ sea kg,
    and totals. This is what freeze_basis snapshots."""
    assert_portal_access()
    target = _target(company) or SALES
    year = int(year)
    air_rates = get_air_rates(year)
    prs = _import_receipts(target, year)
    pool_snap = charge_pool(company=target, year=year)
    sea_kg = sum(flt(r["kg"]) for r in prs if r["channel"] == "sea")
    sea_rate = round(flt(pool_snap["pool"]) / sea_kg, 2) if sea_kg > 0 else 0.0
    air_kg = air_cost = 0.0
    for r in prs:
        if r["channel"] == "air":
            rate = _air_rate_at(air_rates, r["dt"])
            r["rate_kg"] = rate
            r["landed"] = round(flt(r["kg"]) * rate)
            air_kg += flt(r["kg"]); air_cost += r["landed"]
        else:
            r["rate_kg"] = sea_rate
            r["landed"] = round(flt(r["kg"]) * sea_rate)
    return {"company": target, "year": year,
            "air_rates": air_rates, "receipts": prs,
            "pool_rows": pool_snap["rows"],   # the account table (one call for the card)
            "sea": {"pool": pool_snap["pool"], "kg": round(sea_kg, 1), "rate_kg": sea_rate},
            "air": {"kg": round(air_kg, 1), "cost": round(air_cost)},
            "frozen": get_basis(year=year)}


def _landed_units_bulk(item_codes, year=2026):
    """{item: landed cost per UNIT} — the weighted average over the item's
    import-receipt lines: air lines at the tariff of their date, sea lines at
    the pooled sea rate. Returns {} until the basis is frozen (single-crawl
    discipline: every consumer sees landed only once it is locked)."""
    basis = get_basis(year=year)
    if not (basis and item_codes):
        return {}
    air_rates = basis.get("air_rates") or []
    sea_rate = flt(basis.get("sea_rate_kg"))
    chan = _channels(year)
    rows = frappe.db.sql(
        """SELECT pri.item_code ic, pr.name pr, pr.posting_date dt,
                  pri.qty, IFNULL(i.weight_per_unit,0) w,
                  MAX(CASE WHEN pri.warehouse LIKE 'Container%%' THEN 1 ELSE 0 END) has_c
           FROM `tabPurchase Receipt Item` pri
           JOIN `tabPurchase Receipt` pr ON pr.name=pri.parent
           JOIN `tabItem` i ON i.name=pri.item_code
           LEFT JOIN `tabSupplier` s ON s.name=pr.supplier
           WHERE pr.company=%s AND pr.docstatus=1 AND YEAR(pr.posting_date)=%s
             AND pri.item_code IN %s
             AND IFNULL(s.supplier_group,'') NOT IN %s
           GROUP BY pri.name""",
        (SALES, int(year), tuple(item_codes), _DOMESTIC_GROUPS), as_dict=True)
    agg = {}
    for r in rows:
        ch = chan.get(r.pr) or ("sea" if r.has_c else "air")
        rate = _air_rate_at(air_rates, str(r.dt)) if ch == "air" else sea_rate
        a = agg.setdefault(r.ic, [0.0, 0.0])   # qty, landed value
        q = flt(r.qty)
        a[0] += q
        a[1] += q * flt(r.w) * rate
    return {ic: round(v / q, 2) for ic, (q, v) in agg.items() if q > 0}


@frappe.whitelist()
def freeze_basis(company=None, year=2026, rate_kg=None):
    """Super Admin locks the two-channel landed basis: the air tariff bands +
    the pooled sea rate + (implicitly) the PR channel map, which becomes
    read-only. After freezing, landed_unit() starts returning per-item landed
    and the Verify & Fix crawl applies product + landed."""
    if not can_manage_users():
        frappe.throw("Restricted to the Super Admin", frappe.PermissionError)
    snap = shipment_review(company=company, year=year)
    air_rates = snap["air_rates"]
    sea_rate = flt(snap["sea"]["rate_kg"])
    has_sea = flt(snap["sea"]["kg"]) > 0
    if not air_rates and not has_sea:
        frappe.throw("Nothing to freeze — set the air tariff bands and/or classify sea shipments first")
    if has_sea and sea_rate <= 0:
        frappe.throw("Sea shipments exist but the sea rate is 0 — review the charge pool first")
    basis = {"air_rates": air_rates, "sea_rate_kg": sea_rate,
             "sea_pool": snap["sea"]["pool"], "sea_kg": snap["sea"]["kg"],
             "air_kg": snap["air"]["kg"], "air_cost": snap["air"]["cost"],
             # legacy single-rate field kept for old readers (≈ blended, info only)
             "rate_kg": sea_rate or (flt(air_rates[-1]["rate"]) if air_rates else 0),
             "by": frappe.session.user, "on": str(now_datetime())[:19]}
    frappe.db.set_default(_basis_key(int(year)), json.dumps(basis))
    frappe.db.commit()
    return basis


@frappe.whitelist()
def unfreeze_basis(year=2026):
    if not can_manage_users():
        frappe.throw("Restricted to the Super Admin", frappe.PermissionError)
    frappe.db.set_default(_basis_key(int(year)), "")
    frappe.db.commit()
    return {"frozen": None}


def landed_unit(item_code, year=2026):
    """The landed add-on per unit for this item (0 until the basis is frozen):
    weighted over its import receipts — air lines at the tariff of their date,
    sea lines at the pooled sea rate."""
    return flt(_landed_units_bulk([item_code], year=year).get(item_code))