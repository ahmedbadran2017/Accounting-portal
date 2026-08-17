"""Shipment Costing — the PR-centric costing workspace (Purchases → Shipments).

The team's unit of work is the SHIPMENT (one Purchase Receipt): open its
costing file, verify the product cost of every line against the supplier
invoice, attach its freight bills (air: its share of a consolidated Bisfor
bill by kg; sea: the container's own bills), and SAVE — a draft sheet, no
posting. The list screen is the work queue: 51 shipments with statuses, the
unallocated-bill inbox, the reconciliation counter and the final Apply.

The final application stays ITEM-level under the hood (ERPNext moving average
lives on the item, not the shipment): apply_batch() turns the completed
sheets into per-item verified costs (qty-weighted across a product's receipt
lines) and drives the existing gated/reversible fix_item_cost — so all the
guardrails (frozen landed basis, reserved/disabled skips, dedupe, undo)
apply unchanged.

Draft sheets are stored as frappe defaults (ap_sheet_<PR>) — pure UI state,
nothing touches the GL until apply.
"""
import json

import frappe
from frappe.utils import flt, now_datetime

from accounting_portal.api.permissions import assert_can_write, assert_portal_access

SALES = "Justyol Morocco"


def _sheet_key(pr):
    return f"ap_sheet_{pr}"


def _sheets_bulk():
    """{pr: sheet dict} for every saved draft sheet (one query)."""
    rows = frappe.db.sql(
        """SELECT defkey, defvalue FROM `tabDefaultValue`
           WHERE parent='__default' AND defkey LIKE 'ap_sheet_%%'""")
    out = {}
    for k, v in rows:
        try:
            out[k[len("ap_sheet_"):]] = json.loads(v or "{}") or {}
        except Exception:
            continue
    return out


def _pr_lines(pr_names):
    """{pr: [{item_code, qty, weight, book_rate}]} for the given receipts —
    one query, qty-weighted book rate per item line."""
    if not pr_names:
        return {}
    rows = frappe.db.sql(
        """SELECT pri.parent pr, pri.item_code ic, SUM(pri.qty) qty,
                  IFNULL(MAX(i.weight_per_unit),0) w,
                  ROUND(SUM(pri.base_amount)/NULLIF(SUM(pri.qty),0),2) book_rate,
                  MAX(i.item_name) item_name, MAX(i.custom_sku) sku
           FROM `tabPurchase Receipt Item` pri
           JOIN `tabItem` i ON i.name=pri.item_code
           WHERE pri.parent IN %s AND pri.docstatus=1
           GROUP BY pri.parent, pri.item_code""", (tuple(pr_names),), as_dict=True)
    out = {}
    for r in rows:
        out.setdefault(r.pr, []).append(r)
    return out


def _fixed_map():
    from accounting_portal.api.cost_trace import _fixed_items, _fix_is_current
    from accounting_portal.api.landed_prep import get_basis
    basis_on = (get_basis() or {}).get("on")
    fixed = _fixed_items()
    return {ic for ic, stamp in fixed.items() if _fix_is_current(stamp, basis_on)}


def _status(sheet, n_lines, freight_src, n_fixed_lines):
    """pending → progress → costed (sheet complete + real freight) → applied."""
    costs = (sheet or {}).get("costs") or {}
    n_verified = sum(1 for v in costs.values() if flt(v) > 0)
    if n_lines and n_fixed_lines >= n_lines:
        return "applied", n_verified
    if n_verified >= n_lines and n_lines and freight_src == "bills":
        return "costed", n_verified
    if n_verified or freight_src == "bills":
        return "progress", n_verified
    return "pending", n_verified


@frappe.whitelist()
def shipments(company=None, year=None):
    """The work queue: every import shipment with its costing status, plus the
    unallocated-bill inbox, the reconciliation counter and overall progress."""
    assert_portal_access()
    from accounting_portal.api.landed_prep import shipment_review
    sr = shipment_review(company=company, year=year)
    sheets = _sheets_bulk()
    lines = _pr_lines([r["name"] for r in sr["receipts"]])
    fixed = _fixed_map()
    counts = {"pending": 0, "progress": 0, "costed": 0, "applied": 0}
    rows = []
    for r in sr["receipts"]:
        lns = lines.get(r["name"]) or []
        n_fixed = sum(1 for l in lns if l.ic in fixed)
        status, n_verified = _status(sheets.get(r["name"]), len(lns), r["source"], n_fixed)
        counts[status] += 1
        rows.append({
            "name": r["name"], "dt": r["dt"], "supplier": r["supplier"],
            "kg": r["kg"], "qty": r["qty"], "channel": r["channel"],
            "n_lines": len(lns), "n_verified": n_verified, "n_fixed": n_fixed,
            "freight": {"source": r["source"], "landed": r["landed"],
                        "rate_kg": r["rate_kg"], "n_bills": len(r["bills"])},
            "status": status,
        })
    inbox = [b for b in sr["bills"] if not b["excluded"] and not b["prs"]]
    years = [int(y[0]) for y in frappe.db.sql(
        """SELECT DISTINCT YEAR(pr.posting_date) FROM `tabPurchase Receipt` pr
           LEFT JOIN `tabSupplier` s ON s.name=pr.supplier
           WHERE pr.company=%s AND pr.docstatus=1
             AND IFNULL(s.supplier_group,'') NOT IN ('Morocco Local Suppliers','Local')
           ORDER BY 1 DESC""", (SALES,))]
    return {"company": sr["company"], "year": sr["year"], "years": years, "rows": rows,
            "counts": counts, "recon": sr["recon"], "crosscheck": sr["crosscheck"],
            "inbox": inbox, "frozen": bool(sr["frozen"])}


@frappe.whitelist()
def get_sheet(pr=None, year=None):
    """One shipment's costing file: header, product lines (book rate + engine
    suggestion + saved verified cost + fixed flag), attached freight bills with
    this PR's share, and the pickable bill list."""
    assert_portal_access()
    if not pr:
        frappe.throw("pr required")
    from accounting_portal.api.landed_prep import shipment_review
    from accounting_portal.api.cost_trace import _true_cost_bulk, _fx_series
    sr = shipment_review(year=year)
    head = next((r for r in sr["receipts"] if r["name"] == pr), None)
    if not head:
        frappe.throw(f"{pr} is not one of {sr['year']}'s import shipments")
    lns = (_pr_lines([pr]).get(pr)) or []
    items = [l.ic for l in lns]
    tc = _true_cost_bulk(items, _fx_series()) if items else {}
    sheet = None
    try:
        sheet = json.loads(frappe.db.get_default(_sheet_key(pr)) or "null")
    except Exception:
        pass
    costs = (sheet or {}).get("costs") or {}
    fixed = _fixed_map()
    kg = flt(head["kg"])
    landed_kg = flt(head["rate_kg"])
    out_lines = []
    for l in lns:
        t = tc.get(l.ic) or {}
        out_lines.append({
            "item_code": l.ic, "item_name": l.item_name, "sku": l.sku,
            "qty": round(flt(l.qty)), "weight": flt(l.w),
            "book_rate": flt(l.book_rate),
            "suggested": flt(t.get("cost_mad")) or None, "source": t.get("source"),
            "verified": flt(costs.get(l.ic)) or None,
            "landed_unit": round(flt(l.w) * landed_kg, 2),
            "fixed": l.ic in fixed,
        })
    # bill picker: every live bill, flagged whether it's attached to THIS pr
    picker = [{"voucher": b["voucher"], "dt": b["dt"], "supplier": b["supplier"],
               "account": b["account"], "amount": b["amount"], "n_prs": len(b["prs"]),
               "attached": pr in b["prs"]}
              for b in sr["bills"] if not b["excluded"]]
    return {"pr": pr, "dt": head["dt"], "supplier": head["supplier"],
            "channel": head["channel"], "kg": kg, "qty": head["qty"],
            "freight": {"source": head["source"], "landed": head["landed"],
                        "rate_kg": landed_kg, "bills": head["bills"]},
            "lines": out_lines, "picker": picker,
            "sheet": {"note": (sheet or {}).get("note"),
                      "by": (sheet or {}).get("by"), "on": (sheet or {}).get("on")},
            "frozen": bool(sr["frozen"])}


@frappe.whitelist()
def save_sheet(pr=None, costs=None, note=None):
    """Save the draft sheet (verified product cost per line). Pure UI state —
    posts nothing. `costs` = JSON {item_code: rate}; zero/empty clears a line."""
    assert_can_write()
    if not pr:
        frappe.throw("pr required")
    if not frappe.db.exists("Purchase Receipt", {"name": pr, "docstatus": 1, "company": SALES}):
        frappe.throw(f"{pr} is not a submitted {SALES} receipt")
    costs = json.loads(costs) if isinstance(costs, str) else (costs or {})
    valid_items = {l.ic for l in (_pr_lines([pr]).get(pr) or [])}
    clean = {}
    for ic, v in costs.items():
        if ic not in valid_items:
            frappe.throw(f"{ic} is not a line of {pr}")
        if flt(v) > 0:
            clean[ic] = round(flt(v), 2)
    sheet = {"costs": clean, "note": (note or "").strip() or None,
             "by": frappe.session.user, "on": str(now_datetime())[:19]}
    frappe.db.set_default(_sheet_key(pr), json.dumps(sheet))
    frappe.db.commit()
    return {"pr": pr, "saved": len(clean)}


@frappe.whitelist()
def attach_bill(pr=None, voucher=None, attached=None, year=None):
    """Attach/detach ONE freight bill to this shipment from the PR side — a
    thin wrapper over landed_prep.allocate_bill (same validation, same kg
    split, same frozen-basis gate)."""
    assert_can_write()
    if not (pr and voucher):
        frappe.throw("pr + voucher required")
    from accounting_portal.api.landed_prep import _allocs, _year, allocate_bill
    cur = list((_allocs(_year(year)).get(voucher)) or [])
    want = str(attached) in ("1", "true", "True", "yes")
    if want and pr not in cur:
        cur.append(pr)
    elif not want and pr in cur:
        cur.remove(pr)
    return allocate_bill(year=year, voucher=voucher, prs=json.dumps(cur))


@frappe.whitelist()
def readiness(company=None, year=None):
    """The final-Apply card: is everything prepared? (all sheets costed, no
    unallocated bills, basis frozen) + how many items are ready vs applied."""
    assert_portal_access()
    data = shipments(company=company, year=year)
    weighted = _verified_item_costs()
    fixed = _fixed_map()
    ready_items = [ic for ic in weighted if ic not in fixed]
    return {"counts": data["counts"], "total": len(data["rows"]),
            "recon": data["recon"], "frozen": data["frozen"],
            "items_with_verified_cost": len(weighted),
            "items_ready": len(ready_items), "items_applied": len(fixed & set(weighted))}


def _verified_item_costs():
    """{item: qty-weighted verified product cost} across ALL saved sheets —
    the bridge from shipment-level review to item-level application."""
    sheets = _sheets_bulk()
    if not sheets:
        return {}
    lines = _pr_lines(list(sheets))
    agg = {}
    for pr, sheet in sheets.items():
        costs = (sheet or {}).get("costs") or {}
        for l in lines.get(pr) or []:
            v = flt(costs.get(l.ic))
            q = flt(l.qty)
            if v > 0 and q > 0:
                a = agg.setdefault(l.ic, [0.0, 0.0])
                a[0] += q
                a[1] += q * v
    return {ic: round(val / q, 2) for ic, (q, val) in agg.items() if q > 0}


@frappe.whitelist()
def apply_batch(company=None, limit=20, dry_run=1):
    """The final Apply, in waves: for each item with a verified sheet cost and
    no current fix, drive the existing gated/reversible fix_item_cost at
    (weighted verified product cost + frozen landed). dry_run=1 previews the
    next wave; every posted item is individually undoable in Activity."""
    assert_can_write()
    from accounting_portal.api.landed_prep import get_basis
    frozen = bool(get_basis())
    limit = min(int(limit or 20), 100)
    weighted = _verified_item_costs()
    fixed = _fixed_map()
    todo = sorted([ic for ic in weighted if ic not in fixed])[:limit]
    if str(dry_run) in ("1", "true", "True"):
        # preview works WITHOUT the frozen basis — only the real run is gated
        return {"dry_run": True, "frozen": frozen,
                "next_wave": [{"item_code": ic, "rate": weighted[ic]} for ic in todo],
                "remaining": max(len([i for i in weighted if i not in fixed]) - len(todo), 0)}
    if not frozen:
        frappe.throw("Landed basis is not frozen — finish the freight side (unallocated = 0) "
                     "and freeze before applying")
    from accounting_portal.api.valuation import fix_item_cost
    done, skipped = [], []
    for ic in todo:
        try:
            res = fix_item_cost(company=SALES, item_code=ic, rate=weighted[ic],
                                note=f"Shipment costing sheet — qty-weighted verified cost {weighted[ic]}")
            done.append({"item_code": ic, "rate": weighted[ic],
                         "voucher": (res or {}).get("voucher_no")})
        except Exception as e:
            skipped.append({"item_code": ic, "reason": str(e)[:140]})
            continue
    return {"dry_run": False, "posted": done, "skipped": skipped,
            "remaining": max(len([i for i in weighted if i not in fixed]) - len(todo), 0)}
