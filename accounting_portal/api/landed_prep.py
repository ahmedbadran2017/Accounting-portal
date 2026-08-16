"""Landed-basis preparation (B4 v3) — ACTUAL cost per shipment, bill by bill.

The unit of costing is the PURCHASE RECEIPT (one PR = one shipment). Instead of
a modeled rate, every shipment carries its REAL freight bills:

    1. charge_pool(year): the shipping-charge ACCOUNTS (sources). The team
       includes/excludes each — included accounts define which vouchers count
       as freight bills.
    2. bills(): every voucher on the included accounts = one freight bill
       (Bisfor air bills, sea-freight bills, customs, clearance…). The team is
       entering the missing ones; they appear here automatically.
    3. allocate_bill(voucher, prs): attach a bill to the shipment(s) it covers.
       A consolidated bill (e.g. one Bisfor bill covering several air
       shipments) is split across its PRs by kg.
    4. Reconciliation counter: Σ allocated = Σ bills, unallocated = 0. That —
       not a guess — is the freeze gate.
    5. freeze_basis(): snapshots each PR's actual landed cost. From then on
       landed_unit(item) = the item's weighted share of its receipts' actual
       costs — the number Verify & Fix adds on top of the product cost.

The air tariff bands (100 → 110 → 126 MAD/kg) are kept as an ESTIMATE for
shipments whose bills are not yet entered, and as a cross-check
(Σ air kg × tariff ≈ Σ air bills). Analysis + configuration only — nothing
here posts to the GL.
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
                   "last mile")
# Accounts that are INBOUND import costs — suggested included.
# NOTE: 153.03 (Expenses Included In Valuation) is deliberately NOT here — a
# charge parked in that clearing account may still get capitalized onto a
# specific receipt via a Landed Cost Voucher; including it in the pool AND
# LCV-ing it would double-count. It surfaces as "review" for the team to decide.
_INBOUND_HINTS = ("sea freight", "custom duty", "custom agent", "customs",
                  "inspection", "stuffing", "haulage", "demurrage", "container",
                  "clearance", "forklift", "bisfor")


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
    the team's include/exclude decision. Included accounts are the BILL SOURCES:
    their vouchers appear in the bill list for shipment allocation.
    (71.002.503 is scanned too — Bisfor air bills were mislabeled there.)"""
    assert_portal_access()
    target = _target(company) or SALES
    year = int(year)
    rows = frappe.db.sql(
        """SELECT g.account, ROUND(SUM(g.debit-g.credit),0) net, COUNT(*) entries
           FROM `tabGL Entry` g
           WHERE g.company=%s AND g.is_cancelled=0 AND YEAR(g.posting_date)=%s
             AND (g.account LIKE '770.07%%' OR g.account LIKE '770.0.7%%'
                  OR g.account LIKE '153.03%%' OR g.account LIKE '770.04%%'
                  OR g.account LIKE '770.05.012%%' OR g.account LIKE '71.002.503%%')
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
    basis = get_basis(year=year)
    return {"company": target, "year": year, "rows": rows,
            "pool": round(pool), "kg": kg, "frozen": basis}


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
    """Team decision: include/exclude one account from the bill sources.
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


# ── Air tariff bands — kept as ESTIMATE for not-yet-billed air shipments and
# as the cross-check Σ(air kg × tariff) ≈ Σ air bills. ──

def _air_key(year):
    return f"ap_air_rates_{year}"


def _chan_key(year):
    return f"ap_pr_channel_{year}"


def _alloc_key(year):
    return f"ap_bill_alloc_{year}"


def _excl_key(year):
    return f"ap_bill_excl_{year}"


def _excluded_bills(year):
    """Vouchers the team excluded from the freight-bill list (e.g. the non-
    freight entries sharing a mixed account like 71.002.503, or reversal JEs)."""
    try:
        return set(json.loads(frappe.db.get_default(_excl_key(int(year))) or "[]"))
    except Exception:
        return set()


def get_air_rates(year=2026):
    """Date-banded air tariff [{from, rate}] sorted ascending (100 → 110 → 126
    MAD/kg over 2026, at their real change dates)."""
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


def _allocs(year):
    """{voucher_no: [pr, pr, …]} — which shipments each freight bill covers."""
    try:
        return json.loads(frappe.db.get_default(_alloc_key(int(year))) or "{}")
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


# ── Freight BILLS: every voucher on the included accounts, allocatable to the
# shipment(s) it covers. ──

def _bill_rows(target, year, pool=None):
    """One row per voucher on the included charge accounts (the actual freight
    bills). Sign kept: reversals show negative and net out when allocated."""
    pool = pool or charge_pool(company=target, year=year)
    accounts = tuple(r.account for r in pool["rows"] if r["included"])
    if not accounts:
        return []
    rows = frappe.db.sql(
        """SELECT g.voucher_type vt, g.voucher_no voucher,
                  MIN(g.posting_date) dt, ROUND(SUM(g.debit-g.credit),2) amount,
                  SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT g.account), ',', 1) account
           FROM `tabGL Entry` g
           WHERE g.company=%s AND g.is_cancelled=0 AND YEAR(g.posting_date)=%s
             AND g.account IN %s
           GROUP BY g.voucher_type, g.voucher_no
           HAVING ABS(SUM(g.debit-g.credit))>1
           ORDER BY MIN(g.posting_date)""", (target, int(year), accounts), as_dict=True)
    pis = [r.voucher for r in rows if r.vt == "Purchase Invoice"]
    sup = {}
    if pis:
        sup = dict(frappe.db.sql(
            "SELECT name, supplier FROM `tabPurchase Invoice` WHERE name IN %s", (tuple(pis),)))
    excl = _excluded_bills(year)
    for r in rows:
        r["supplier"] = sup.get(r.voucher) or ""
        r["dt"] = str(r.dt or "")
        r["excluded"] = r.voucher in excl
    return rows


@frappe.whitelist()
def exclude_bill(company=None, year=2026, voucher=None, excluded=None):
    """Team decision: this voucher on a freight account is NOT a freight bill
    (mixed account / reversal JE) — drop it from the list and the freeze gate.
    Blocked when frozen."""
    assert_can_write()
    if get_basis(year=year):
        frappe.throw("Basis is frozen — unfreeze before excluding bills")
    if not voucher:
        frappe.throw("voucher required")
    ex = _excluded_bills(int(year))
    if str(excluded) in ("1", "true", "True", "yes"):
        ex.add(voucher)
    else:
        ex.discard(voucher)
    frappe.db.set_default(_excl_key(int(year)), json.dumps(sorted(ex)))
    frappe.db.commit()
    return {"voucher": voucher, "excluded": voucher in ex}


@frappe.whitelist()
def allocate_bill(company=None, year=2026, voucher=None, prs=None):
    """Attach one freight bill to the shipment(s) it covers. `prs` = JSON list
    of Purchase Receipt names (empty list clears the allocation). The bill's
    amount is split across its PRs by kg. Blocked when frozen."""
    assert_can_write()
    if get_basis(year=year):
        frappe.throw("Basis is frozen — unfreeze before re-allocating bills")
    if not voucher:
        frappe.throw("voucher required")
    prs = json.loads(prs) if isinstance(prs, str) else (prs or [])
    prs = [p for p in prs if p]
    if prs:
        found = frappe.db.sql(
            "SELECT name FROM `tabPurchase Receipt` WHERE name IN %s AND docstatus=1",
            (tuple(prs),))
        missing = set(prs) - {f[0] for f in found}
        if missing:
            frappe.throw(f"Unknown/unsubmitted receipts: {', '.join(sorted(missing))}")
    al = _allocs(int(year))
    if prs:
        al[voucher] = prs
    else:
        al.pop(voucher, None)
    frappe.db.set_default(_alloc_key(int(year)), json.dumps(al))
    frappe.db.commit()
    return {"voucher": voucher, "prs": prs}


def _pr_costs_from_bills(bill_rows, allocs, kg_by_pr, qty_by_pr):
    """Split every allocated bill over its PRs (by kg, falling back to qty,
    falling back to equal parts). Returns ({pr: cost}, {pr: [bill share dicts]},
    allocated_total)."""
    costs, detail, allocated = {}, {}, 0.0
    for b in bill_rows:
        prs = allocs.get(b["voucher"]) or []
        if not prs:
            continue
        w = {p: flt(kg_by_pr.get(p)) for p in prs}
        base = sum(w.values())
        if base <= 0:
            w = {p: flt(qty_by_pr.get(p)) for p in prs}
            base = sum(w.values())
        if base <= 0:
            w = {p: 1.0 for p in prs}
            base = float(len(prs))
        allocated += flt(b["amount"])
        for p in prs:
            share = round(flt(b["amount"]) * w[p] / base, 2)
            costs[p] = round(costs.get(p, 0.0) + share, 2)
            detail.setdefault(p, []).append(
                {"voucher": b["voucher"], "supplier": b.get("supplier") or "",
                 "share": share, "amount": flt(b["amount"]), "n_prs": len(prs)})
    return costs, detail, round(allocated, 2)


@frappe.whitelist()
def shipment_review(company=None, year=2026):
    """The whole basis screen in one call: bill sources (accounts), the freight
    BILLS with their allocations, the shipment list with each PR's ACTUAL cost
    (or tariff estimate while its bills are missing), the reconciliation
    counter, and the air-tariff cross-check."""
    assert_portal_access()
    target = _target(company) or SALES
    year = int(year)
    air_rates = get_air_rates(year)
    prs = _import_receipts(target, year)
    pool_snap = charge_pool(company=target, year=year)
    bill_rows = _bill_rows(target, year, pool=pool_snap)
    allocs = _allocs(year)
    kg_by_pr = {r["name"]: flt(r["kg"]) for r in prs}
    qty_by_pr = {r["name"]: flt(r["qty"]) for r in prs}
    live_bills = [b for b in bill_rows if not b["excluded"]]
    costs, detail, allocated = _pr_costs_from_bills(live_bills, allocs, kg_by_pr, qty_by_pr)

    for b in bill_rows:
        b["prs"] = (allocs.get(b["voucher"]) or []) if not b["excluded"] else []

    air_kg = air_cost_est = actual_total = 0.0
    est_count = 0
    for r in prs:
        kg = flt(r["kg"])
        actual = flt(costs.get(r["name"]))
        r["bills"] = detail.get(r["name"]) or []
        if actual:
            r["source"] = "bills"
            r["landed"] = round(actual)
            r["rate_kg"] = round(actual / kg, 2) if kg > 0 else 0
            actual_total += actual
        elif r["channel"] == "air" and _air_rate_at(air_rates, r["dt"]) > 0:
            rate = _air_rate_at(air_rates, r["dt"])
            r["source"] = "est"
            r["rate_kg"] = rate
            r["landed"] = round(kg * rate)
            est_count += 1
        else:
            r["source"] = "none"
            r["rate_kg"] = 0
            r["landed"] = 0
            est_count += 1
        if r["channel"] == "air":
            air_kg += kg
            air_cost_est += kg * _air_rate_at(air_rates, r["dt"])

    bills_total = round(sum(flt(b["amount"]) for b in live_bills), 2)
    unallocated = [b for b in live_bills if not b["prs"]]
    chan_by_pr = {r["name"]: r["channel"] for r in prs}
    air_bills = round(sum(flt(b["amount"]) for b in live_bills
                          if b["prs"] and any(chan_by_pr.get(p) == "air" for p in b["prs"])), 2)
    return {"company": target, "year": year,
            "air_rates": air_rates, "receipts": prs,
            "pool_rows": pool_snap["rows"],
            "bills": bill_rows,
            "recon": {"bills_total": bills_total, "allocated": allocated,
                      "unallocated": round(bills_total - allocated, 2),
                      "unallocated_count": len(unallocated),
                      "uncosted_receipts": est_count,
                      "actual_total": round(actual_total, 2)},
            "crosscheck": {"air_kg": round(air_kg, 1),
                           "air_tariff_cost": round(air_cost_est),
                           "air_bills": air_bills},
            "frozen": get_basis(year=year)}


def _landed_units_bulk(item_codes, year=2026):
    """{item: landed cost per UNIT} — each item's weighted share of its import
    receipts' ACTUAL costs (frozen snapshot). Within a PR the cost spreads over
    the lines by kg (fallback: by qty). Returns {} until the basis is frozen
    (single-crawl discipline: every consumer sees landed only once locked)."""
    basis = get_basis(year=year)
    if not (basis and item_codes):
        return {}
    pr_costs = basis.get("pr_costs") or {}
    if not pr_costs:
        return {}
    rows = frappe.db.sql(
        """SELECT pri.item_code ic, pr.name pr, pri.qty, IFNULL(i.weight_per_unit,0) w
           FROM `tabPurchase Receipt Item` pri
           JOIN `tabPurchase Receipt` pr ON pr.name=pri.parent
           JOIN `tabItem` i ON i.name=pri.item_code
           WHERE pr.docstatus=1 AND pri.item_code IN %s AND pr.name IN %s""",
        (tuple(item_codes), tuple(pr_costs.keys())), as_dict=True)
    agg = {}
    for r in rows:
        pc = pr_costs.get(r.pr) or {}
        cost, pr_kg, pr_qty = flt(pc.get("cost")), flt(pc.get("kg")), flt(pc.get("qty"))
        q = flt(r.qty)
        if cost <= 0 or q <= 0:
            share = 0.0
        elif pr_kg > 0:
            # weighted PR: kg split — a zero-weight line gets 0 (fix its weight,
            # don't let it double-dip on top of the fully-distributed kg shares)
            share = cost * (q * flt(r.w)) / pr_kg
        elif pr_qty > 0:
            # whole PR unweighted: fall back to qty split
            share = cost * q / pr_qty
        else:
            share = 0.0
        a = agg.setdefault(r.ic, [0.0, 0.0])   # qty, landed value
        a[0] += q
        a[1] += share
    return {ic: round(v / q, 2) for ic, (q, v) in agg.items() if q > 0}


@frappe.whitelist()
def freeze_basis(company=None, year=2026):
    """Super Admin locks the basis: snapshots each shipment's ACTUAL landed cost
    (from its allocated bills; air shipments still missing bills freeze at the
    tariff estimate, flagged). Blocked while any freight bill is unallocated —
    the reconciliation must read unallocated = 0 first."""
    if not can_manage_users():
        frappe.throw("Restricted to the Super Admin", frappe.PermissionError)
    snap = shipment_review(company=company, year=year)
    if snap["recon"]["unallocated_count"]:
        frappe.throw(f"{snap['recon']['unallocated_count']} freight bill(s) are not allocated "
                     "to any shipment — allocate (or exclude their account) before freezing")
    pr_costs, est, uncosted = {}, 0, []
    for r in snap["receipts"]:
        if r["source"] == "none":
            uncosted.append(r["name"])
        if r["source"] == "est":
            est += 1
        pr_costs[r["name"]] = {"cost": flt(r["landed"]), "kg": flt(r["kg"]),
                               "qty": flt(r["qty"]), "src": r["source"]}
    sea_uncosted = [r["name"] for r in snap["receipts"]
                    if r["channel"] == "sea" and r["source"] != "bills"]
    if sea_uncosted:
        frappe.throw("Sea shipments without allocated bills: "
                     + ", ".join(sea_uncosted[:5])
                     + " — sea has no tariff fallback; allocate their bills first")
    if not any(flt(v["cost"]) > 0 for v in pr_costs.values()):
        frappe.throw("Nothing to freeze — no shipment has a cost yet (allocate bills "
                     "or set the air tariff first)")
    basis = {"pr_costs": pr_costs,
             "air_rates": snap["air_rates"],
             "bills_total": snap["recon"]["bills_total"],
             "actual_total": snap["recon"]["actual_total"],
             "estimated_receipts": est, "uncosted_receipts": uncosted,
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
    its weighted share of its import receipts' actual costs."""
    return flt(_landed_units_bulk([item_code], year=year).get(item_code))
