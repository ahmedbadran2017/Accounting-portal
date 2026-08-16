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


@frappe.whitelist()
def freeze_basis(company=None, year=2026, rate_kg=None):
    """Super Admin locks the landed basis. rate_kg defaults to the computed
    pool÷kg; an explicit override is recorded as such. After freezing, the
    Verify & Fix screen starts adding landed_unit = rate × weight."""
    if not can_manage_users():
        frappe.throw("Restricted to the Super Admin", frappe.PermissionError)
    snap = charge_pool(company=company, year=year)
    r = flt(rate_kg) if rate_kg not in (None, "") else flt(snap["rate_kg"])
    if r <= 0:
        frappe.throw("Cannot freeze a zero rate — review the pool first")
    basis = {"rate_kg": round(r, 2), "pool": snap["pool"], "est_kg": snap["kg"]["est_kg"],
             "coverage_pct": snap["kg"]["coverage_pct"],
             "overridden": rate_kg not in (None, ""),
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
    """The landed add-on per unit for this item (0 until the basis is frozen)."""
    b = get_basis(year=year)
    if not b:
        return 0.0
    w = flt(frappe.db.get_value("Item", item_code, "weight_per_unit"))
    return round(flt(b["rate_kg"]) * w, 2)