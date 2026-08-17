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
    return {ic for ic, f in fixed.items() if _fix_is_current(f["stamp"], basis_on)}


def _status(sheet, n_lines, freight_src, n_fixed_lines):
    """pending → progress → costed (sheet complete + real freight) → applied."""
    costs = (sheet or {}).get("costs") or {}
    n_verified = sum(1 for v in costs.values() if flt(v) > 0)
    freight_ok = freight_src in ("bills", "rate")
    if n_lines and n_fixed_lines >= n_lines and freight_ok:
        return "applied", n_verified
    if n_verified >= n_lines and n_lines and freight_ok:
        return "costed", n_verified
    if n_verified or freight_ok:
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
    # the CROSS-SHIPMENT picture per line: an item's applied cost is weighted
    # over ALL its shipments, so each line must show what else it belongs to
    # and what (elsewhere) still blocks it
    all_lines = _pr_lines([r["name"] for r in sr["receipts"]])
    costed = {r["name"] for r in sr["receipts"] if r["source"] in ("bills", "rate")}
    sheets_all = _sheets_bulk()
    item_prs = {}
    for prn, ls in all_lines.items():
        for l in ls:
            if l.ic in set(items):
                item_prs.setdefault(l.ic, set()).add(prn)
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
        others = sorted(item_prs.get(l.ic, set()) - {pr})
        wait_freight = [p for p in others if p not in costed]
        wait_verify = [p for p in others
                       if p in costed
                       and flt(((sheets_all.get(p) or {}).get("costs") or {}).get(l.ic)) <= 0]
        out_lines.append({
            "item_code": l.ic, "item_name": l.item_name, "sku": l.sku,
            "qty": round(flt(l.qty)), "weight": flt(l.w),
            "book_rate": flt(l.book_rate),
            "suggested": flt(t.get("cost_mad")) or None, "source": t.get("source"),
            "verified": flt(costs.get(l.ic)) or None,
            "landed_unit": round(flt(l.w) * landed_kg, 2),
            "fixed": l.ic in fixed,
            # cross-shipment picture: [] = this shipment is its whole story
            "other_prs": others,
            "wait_freight": wait_freight, "wait_verify": wait_verify,
        })
    # bill picker with MATCHING SIGNALS: bills near-identical in label need
    # help — (a) a shipment ref written in the bill's bill_no/remarks is an
    # exact match ⭐; (b) date proximity ranks the rest (a container's bills
    # arrive around its receipt date)
    from frappe.utils import date_diff
    pr_tail = pr.split("-")[-2] + "-" + pr.split("-")[-1] if pr.endswith("-1") else pr.split("-")[-1]
    picker = []
    for b in sr["bills"]:
        if b["excluded"]:
            continue
        ref = (b.get("ref_text") or "")
        ref_match = bool(pr in ref or (len(pr_tail) >= 4 and pr_tail in ref))
        days = abs(date_diff(b["dt"], head["dt"])) if b["dt"] else 999
        picker.append({"voucher": b["voucher"], "dt": b["dt"], "supplier": b["supplier"],
                       "account": b["account"], "amount": b["amount"], "n_prs": len(b["prs"]),
                       "attached": pr in b["prs"], "ref_match": ref_match, "days": days,
                       "kg": b.get("kg"), "kg_source": b.get("kg_source"),
                       "implied_rate": b.get("implied_rate")})
    picker.sort(key=lambda x: (not x["attached"], not x["ref_match"], x["days"]))
    return {"pr": pr, "dt": head["dt"], "supplier": head["supplier"],
            "channel": head["channel"], "kg": kg, "qty": head["qty"],
            "freight": {"source": head["source"], "landed": head["landed"],
                        "rate_kg": landed_kg, "bills": head["bills"],
                        "bill_kg": head.get("bill_kg"), "book_kg": kg,
                        "confirmed_rate": head.get("confirmed_rate"),
                        "band_rate": head.get("band_rate")},
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
    """The batch-Apply card: how many sheet items are truly READY (every
    shipment costed + verified) vs still waiting, and how many applied."""
    assert_portal_access()
    data = shipments(company=company, year=year)
    ready, waiting, n_cand = _batch_readiness(year=year)
    fixed = _fixed_map()
    return {"counts": data["counts"], "total": len(data["rows"]),
            "recon": data["recon"], "frozen": data["frozen"],
            "items_with_verified_cost": n_cand,
            "items_ready": len([ic for ic in ready if ic not in fixed]),
            "items_waiting": waiting,
            "items_applied": len(fixed & set(ready))}


def _live_landed(items, receipts):
    """{item: live landed/unit} from the CURRENT shipment costs (bills/rate
    sources only) — the per-shipment-submit path, no frozen snapshot needed.
    Same kg-split math as the frozen distributor."""
    costed = {r["name"]: {"cost": flt(r["landed"]), "kg": flt(r["kg"]), "qty": flt(r["qty"]),
                          "qty0": flt(r.get("qty0") or 0), "bill_kg": flt(r.get("bill_kg") or 0)}
              for r in receipts if r["source"] in ("bills", "rate")}
    from accounting_portal.api.landed_prep import _hist_landed_units
    hist = _hist_landed_units(set(items)) if items else {}
    if not (costed or hist) or not items:
        return {}
    lines = _pr_lines(list(costed))
    agg = {}
    for prn, lns in lines.items():
        pc = costed[prn]
        # zero-weight lines carry the shipment's AVERAGE unit weight (bill kg is
        # the best average source when captured) — no free-riding, no zero landed
        avg_w = 0.0
        if pc["qty0"] > 0 and pc["qty"] > 0:
            best_kg = pc["bill_kg"] or pc["kg"]
            avg_w = best_kg / pc["qty"] if best_kg > 0 else 0.0
        eff_total = pc["kg"] + pc["qty0"] * avg_w
        for l in lns:
            if l.ic not in items:
                continue
            q = flt(l.qty)
            if q <= 0:
                continue
            if eff_total > 0:
                eff = q * (flt(l.w) if flt(l.w) > 0 else avg_w)
                share = pc["cost"] * eff / eff_total
            elif pc["qty"] > 0:
                share = pc["cost"] * q / pc["qty"]
            else:
                share = 0.0
            a = agg.setdefault(l.ic, [0.0, 0.0])
            a[0] += q
            a[1] += share
    # blend the HISTORICAL layer (pre-current-year receipts at contract
    # tariffs) into the same weighted average
    for ic, hh in hist.items():
        a = agg.setdefault(ic, [0.0, 0.0])
        a[0] += hh["qty"]
        a[1] += hh["value"]
    return {ic: round(v / q, 2) for ic, (q, v) in agg.items() if q > 0}


@frappe.whitelist()
def apply_shipment(pr=None, year=None, dry_run=1):
    """The shipment's SUBMIT: apply the full cost (verified product + live
    landed) to every line item whose data is COMPLETE — i.e. every one of the
    item's import shipments this year is freight-costed AND carries a verified
    cost in its sheet (the item's cost is a weighted average across them, so a
    missing shipment would understate it). Items still waiting are reported
    with WHAT they wait for. dry_run=1 previews. Retroactive month restatement
    stays a separate step (the monthly true-up)."""
    assert_can_write()
    if not pr:
        frappe.throw("pr required")
    from accounting_portal.api.landed_prep import shipment_review
    sr = shipment_review(year=year)
    all_prs = [r["name"] for r in sr["receipts"]]
    if pr not in all_prs:
        frappe.throw(f"{pr} is not one of {sr['year']}'s import shipments")
    costed = {r["name"] for r in sr["receipts"] if r["source"] in ("bills", "rate")}
    sheets = _sheets_bulk()
    lines_all = _pr_lines(all_prs)
    item_prs = {}
    for prn, lns in lines_all.items():
        for l in lns:
            item_prs.setdefault(l.ic, set()).add(prn)
    my_items = [l.ic for l in (lines_all.get(pr) or [])]
    fixed = _fixed_map()
    live_landed = _live_landed(set(my_items), sr["receipts"])

    def weighted_product(ic):
        q_tot = val = 0.0
        for prn in item_prs.get(ic, ()):
            v = flt(((sheets.get(prn) or {}).get("costs") or {}).get(ic))
            for l in lines_all.get(prn) or []:
                if l.ic == ic and v > 0 and flt(l.qty) > 0:
                    q_tot += flt(l.qty)
                    val += flt(l.qty) * v
        return round(val / q_tot, 2) if q_tot > 0 else 0.0

    rows, ready = [], []
    for ic in my_items:
        prs_i = sorted(item_prs.get(ic, ()))
        waiting_freight = [p for p in prs_i if p not in costed]
        waiting_verify = [p for p in prs_i
                          if flt(((sheets.get(p) or {}).get("costs") or {}).get(ic)) <= 0]
        if ic in fixed:
            rows.append({"item_code": ic, "status": "already_applied"})
            continue
        if waiting_freight:
            rows.append({"item_code": ic, "status": "waiting_freight", "prs": waiting_freight})
            continue
        if waiting_verify:
            rows.append({"item_code": ic, "status": "waiting_verify", "prs": waiting_verify})
            continue
        product = weighted_product(ic)
        landed = flt(live_landed.get(ic))
        full = round(product + landed, 2)
        rows.append({"item_code": ic, "status": "ready", "product": product,
                     "landed": landed, "full": full})
        ready.append((ic, product, landed, full))

    if str(dry_run) in ("1", "true", "True"):
        counts = {}
        for r in rows:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        return {"dry_run": True, "pr": pr, "rows": rows, "counts": counts}

    from accounting_portal.api.valuation import fix_item_cost
    done, skipped = [], []
    for ic, product, landed, full in ready:
        try:
            res = fix_item_cost(
                company=SALES, item_code=ic, rate=full, full_rate=1,
                note=f"Shipment submit {pr} — product {product} + landed {landed} = {full} "
                     f"(weighted across {len(item_prs.get(ic, ()))} shipment(s))")
            done.append({"item_code": ic, "full": full,
                         "voucher": (res or {}).get("voucher_no")})
        except Exception as e:
            skipped.append({"item_code": ic, "reason": str(e)[:140]})
            continue
    return {"dry_run": False, "pr": pr, "posted": done, "skipped": skipped,
            "rows": rows}


@frappe.whitelist()
def item_landed_detail(item_code=None, year=None):
    """The SKU page's ② freight section: this item's import shipments with each
    one's channel / freight status / this item's landed share, the LIVE landed
    per unit, and what is still missing. Air shipments expose band/confirmed
    rates so the rate can be confirmed right from the item page."""
    assert_portal_access()
    if not item_code:
        frappe.throw("item_code required")
    if not frappe.db.exists("Item", item_code):
        frappe.throw(f"Unknown item: {item_code}")
    from accounting_portal.api.landed_prep import shipment_review
    sr = shipment_review(year=year)
    mine = []
    lines = _pr_lines([r["name"] for r in sr["receipts"]])
    by_name = {r["name"]: r for r in sr["receipts"]}
    for prn, lns in lines.items():
        for l in lns:
            if l.ic != item_code:
                continue
            h = by_name[prn]
            pr_kg, cost = flt(h["kg"]), flt(h["landed"])
            qty0, pr_qty = flt(h.get("qty0") or 0), flt(h["qty"])
            avg_w = ((flt(h.get("bill_kg") or 0) or pr_kg) / pr_qty) if (qty0 > 0 and pr_qty > 0) else 0.0
            eff_total = pr_kg + qty0 * avg_w
            line_kg = flt(l.qty) * (flt(l.w) if flt(l.w) > 0 else avg_w)
            share = round(cost * line_kg / eff_total, 2) if (eff_total > 0 and h["source"] in ("bills", "rate")) else 0.0
            mine.append({"pr": prn, "dt": h["dt"], "supplier": h["supplier"],
                         "channel": h["channel"], "source": h["source"],
                         "rate_kg": h["rate_kg"], "confirmed_rate": h.get("confirmed_rate"),
                         "band_rate": h.get("band_rate"), "kg": h["kg"],
                         "qty": round(flt(l.qty)), "line_kg": round(line_kg, 1),
                         "share": share, "n_bills": len(h["bills"])})
    mine.sort(key=lambda x: x["dt"], reverse=True)
    # historical layer: pre-current-year receipts at the CONTRACT tariffs —
    # one summary row per item; already blended into landed_unit by _live_landed
    from accounting_portal.api.landed_prep import _hist_landed_units
    hh = (_hist_landed_units({item_code}) or {}).get(item_code)
    hist_row = None
    if hh and hh["qty"] > 0:
        hist_row = {"n_prs": hh["n_prs"], "qty": round(hh["qty"]),
                    "channels": hh["channels"],
                    "landed_total": round(hh["value"], 2),
                    "unit": round(hh["value"] / hh["qty"], 2)}
    landed = flt(_live_landed({item_code}, sr["receipts"]).get(item_code))
    waiting = [m["pr"] for m in mine if m["source"] not in ("bills", "rate")]
    # the PR sheets' weighted verified cost, if the team already verified this
    # item during a bulk pass — prefills the SKU page input
    sheets = _sheets_bulk()
    q_tot = val = 0.0
    for m in mine:
        v = flt(((sheets.get(m["pr"]) or {}).get("costs") or {}).get(item_code))
        if v > 0 and m["qty"] > 0:
            q_tot += m["qty"]
            val += m["qty"] * v
    sheet_cost = round(val / q_tot, 2) if q_tot > 0 else None
    saved_meta = None
    if sheet_cost is None and not mine:
        # orphan: read the per-item fallback saved by save_item_cost
        try:
            fb = json.loads(frappe.db.get_default(f"ap_itemcost_{item_code}") or "null") or {}
            if flt(fb.get("cost")) > 0:
                sheet_cost = flt(fb.get("cost"))
                saved_meta = {"by": fb.get("by"), "on": fb.get("on")}
        except Exception:
            pass
    is_local = bool(frappe.db.sql(
        """SELECT 1 FROM `tabPurchase Invoice Item` pii
           JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
           JOIN `tabSupplier` s ON s.name=pi.supplier
           WHERE pi.company=%s AND pi.docstatus=1 AND pii.item_code=%s
             AND IFNULL(s.supplier_group,'') IN ('Morocco Local Suppliers', 'Local')
           LIMIT 1""", (SALES, item_code))) and not mine and not hist_row
    return {"item_code": item_code, "receipts": mine, "sheet_cost": sheet_cost,
            "saved_meta": saved_meta, "local": is_local,
            "landed_unit": landed, "historical": hist_row,
            "waiting": waiting, "complete": (not waiting) and bool(mine or hist_row),
            "no_receipts": not mine and not hist_row,
            "frozen": bool(sr["frozen"]), "year": sr["year"]}


@frappe.whitelist()
def save_item_cost(item_code=None, cost=None, note=None, year=None):
    """The SKU page's ① Save: persist the verified product cost. Written into
    the item's line in EVERY one of its shipments' draft sheets (the same
    store the bulk path uses — both paths always agree). Orphans (no import
    shipments) store to a per-item fallback key. Pure draft — posts nothing."""
    assert_can_write()
    if not item_code:
        frappe.throw("item_code required")
    v = flt(cost)
    if v <= 0:
        frappe.throw("A positive verified product cost is required")
    if v < 0.5:
        frappe.throw(f"Verified cost {v} MAD/unit looks like a broken FX conversion, "
                     "not a real price — check the Currency Exchange records")
    d = item_landed_detail(item_code=item_code, year=year)
    prs = [m["pr"] for m in d["receipts"]]
    stamp = {"by": frappe.session.user, "on": str(now_datetime())[:19]}
    updated, kept = [], []
    if prs:
        for pr in prs:
            sheet = None
            try:
                sheet = json.loads(frappe.db.get_default(_sheet_key(pr)) or "null")
            except Exception:
                pass
            sheet = sheet or {}
            costs = sheet.get("costs") or {}
            cur = flt(costs.get(item_code))
            # a DIFFERENT deliberate per-shipment price is kept, not clobbered —
            # per-PR prices can legitimately differ; edit them in the sheet itself
            if cur > 0 and abs(cur - v) > 0.005 * max(cur, v):
                kept.append({"pr": pr, "existing": cur})
                continue
            costs[item_code] = round(v, 2)
            sheet.update({"costs": costs, **stamp})
            if (note or "").strip():
                sheet["note"] = note.strip()
            frappe.db.set_default(_sheet_key(pr), json.dumps(sheet))
            updated.append(pr)
    else:
        frappe.db.set_default(f"ap_itemcost_{item_code}",
                              json.dumps({"cost": round(v, 2),
                                          "note": (note or "").strip() or None, **stamp}))
    frappe.db.commit()
    return {"item_code": item_code, "cost": round(v, 2),
            "saved_to": (updated if prs else ["item"]), "kept_different": kept if prs else []}


@frappe.whitelist()
def apply_item(item_code=None, rate=None, note=None, year=None):
    """The SKU page's ④ Submit: apply verified product cost + this item's LIVE
    landed. Blocked while any of the item's shipments is not freight-costed
    (its landed would be understated). Gated/reversible via fix_item_cost."""
    assert_can_write()
    if not item_code:
        frappe.throw("item_code required")
    product = flt(rate)
    if product <= 0:
        frappe.throw("A positive verified product cost is required")
    if product < 0.5:
        # a sub-0.5-MAD "cost" is almost always a broken currency conversion
        # (seen on stale-FX environments), not a real price — refuse loudly
        frappe.throw(f"Verified cost {product} MAD/unit looks like a broken FX conversion, "
                     "not a real price — check the Currency Exchange records for the invoice date")
    d = item_landed_detail(item_code=item_code, year=year)
    if d["waiting"]:
        frappe.throw("Freight not assembled yet for: " + ", ".join(d["waiting"][:5])
                     + " — confirm the rate / attach the bills first (its landed would be understated)")
    landed = flt(d["landed_unit"])
    full = round(product + landed, 2)
    from accounting_portal.api.valuation import fix_item_cost
    return fix_item_cost(
        company=SALES, item_code=item_code, rate=full, full_rate=1,
        note=((note or "").strip() or f"SKU verify — {item_code}")
             + f" · product {product} + landed {landed} = {full} "
             f"({len(d['receipts'])} shipment(s))")




def _batch_readiness(year=None):
    """Shared by apply_batch + readiness: every item seen in any sheet, split
    into ready (ALL its shipments freight-costed + verified in all their
    sheets → full = weighted product + live landed) vs waiting — the SAME
    completeness rule as the per-shipment and per-item submits."""
    from accounting_portal.api.landed_prep import shipment_review
    sr = shipment_review(year=year)
    all_prs = [r["name"] for r in sr["receipts"]]
    costed = {r["name"] for r in sr["receipts"] if r["source"] in ("bills", "rate")}
    sheets = _sheets_bulk()
    lines_all = _pr_lines(all_prs)
    item_prs = {}
    for prn, lns in lines_all.items():
        for l in lns:
            item_prs.setdefault(l.ic, set()).add(prn)
    candidates = set()
    for prn, sheet in sheets.items():
        for ic, v in ((sheet or {}).get("costs") or {}).items():
            if flt(v) > 0 and ic in item_prs:
                candidates.add(ic)
    live = _live_landed(candidates, sr["receipts"])
    ready, waiting = {}, {"freight": 0, "verify": 0}
    for ic in candidates:
        prs_i = item_prs.get(ic, set())
        if any(p not in costed for p in prs_i):
            waiting["freight"] += 1
            continue
        if any(flt(((sheets.get(p) or {}).get("costs") or {}).get(ic)) <= 0 for p in prs_i):
            waiting["verify"] += 1
            continue
        q_tot = val = 0.0
        for prn in prs_i:
            v = flt(((sheets.get(prn) or {}).get("costs") or {}).get(ic))
            for l in lines_all.get(prn) or []:
                if l.ic == ic and flt(l.qty) > 0:
                    q_tot += flt(l.qty)
                    val += flt(l.qty) * v
        if q_tot <= 0:
            continue
        product = round(val / q_tot, 2)
        landed = flt(live.get(ic))
        ready[ic] = {"product": product, "landed": landed,
                     "full": round(product + landed, 2)}
    return ready, waiting, len(candidates)


@frappe.whitelist()
def apply_batch(company=None, limit=20, dry_run=1, year=None):
    """Apply in waves — same completeness rule as the per-shipment submit
    (NO frozen-basis requirement): an item posts only when every one of its
    shipments is freight-costed and verified. Each post is undoable."""
    assert_can_write()
    limit = min(int(limit or 20), 100)
    ready, waiting, n_cand = _batch_readiness(year=year)
    fixed = _fixed_map()
    todo = sorted([ic for ic in ready if ic not in fixed])[:limit]
    n_ready_total = len([ic for ic in ready if ic not in fixed])
    if str(dry_run) in ("1", "true", "True"):
        return {"dry_run": True, "waiting": waiting,
                "next_wave": [{"item_code": ic, "rate": ready[ic]["full"]} for ic in todo],
                "remaining": max(n_ready_total - len(todo), 0)}
    from accounting_portal.api.valuation import fix_item_cost
    done, skipped = [], []
    for ic in todo:
        r = ready[ic]
        try:
            res = fix_item_cost(
                company=SALES, item_code=ic, rate=r["full"], full_rate=1,
                note=f"Batch apply — product {r['product']} + landed {r['landed']} = {r['full']}")
            done.append({"item_code": ic, "rate": r["full"],
                         "voucher": (res or {}).get("voucher_no")})
        except Exception as e:
            skipped.append({"item_code": ic, "reason": str(e)[:140]})
            continue
    return {"dry_run": False, "posted": done, "skipped": skipped,
            "remaining": max(n_ready_total - len(todo), 0)}
