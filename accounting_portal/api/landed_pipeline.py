"""Landed Cost Pipeline — from "a charge was paid" to "it lives in the product".

The 2026 reality this fixes (verified on production): 2,458 Purchase Receipts
worth 15.5M MAD, only 3 covered by a posted Landed Cost Voucher; 12 draft LCVs
holding 754K of charges; freight/customs otherwise stranded outside inventory,
so item valuation (and every Delivery Note's COGS) misses the landed component.

Flow: charge inbox (booked charges not yet capitalised) → shipment builder
(pick receipts + charges, preview the per-item allocation) → post via the
audited gateway (LCV: Dr stock / Cr the same expense account — the P&L charge
zeroes out and the cost is absorbed; ERPNext reposts later SLEs so COGS heals)
→ draft triage for the LCVs the team already started.
"""
import json

import frappe
from frappe.utils import flt, nowdate

from accounting_portal.api.permissions import assert_portal_access, assert_can_write, resolve_companies
from accounting_portal.api import _actions
from accounting_portal.api.landed_engine import _INBOUND

LCV_ACTION = "Post landed cost"
_FROM = "2026-01-01"  # working window agreed with the CFO — 2025 stays in P&L


def _target(company):
    companies = resolve_companies(company)
    if not companies:
        return None
    return company if (company and company in companies) else companies[0]


def _used_charge_sources(target):
    """Charge-voucher names already referenced by a submitted LCV (we stamp the
    source voucher into each charge line's description as 'src:<name>')."""
    rows = frappe.db.sql(
        """SELECT t.description FROM `tabLanded Cost Taxes and Charges` t
           JOIN `tabLanded Cost Voucher` l ON l.name=t.parent
           WHERE l.company=%s AND l.docstatus=1 AND t.description LIKE '%%src:%%'""", (target,))
    used = set()
    for (desc,) in rows:
        for part in str(desc).split():
            if part.startswith("src:"):
                used.add(part[4:])
    return used


@frappe.whitelist()
def pipeline_overview(company=None):
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    uncovered = frappe.db.sql(
        """SELECT COUNT(*), SUM(pr.base_grand_total) FROM `tabPurchase Receipt` pr
           WHERE pr.company=%s AND pr.docstatus=1 AND pr.posting_date>=%s
           AND pr.name NOT IN (
             SELECT lpr.receipt_document FROM `tabLanded Cost Purchase Receipt` lpr
             JOIN `tabLanded Cost Voucher` l ON l.name=lpr.parent WHERE l.docstatus=1)""",
        (target, _FROM))[0]
    drafts = frappe.db.sql(
        """SELECT COUNT(*), SUM(total_taxes_and_charges) FROM `tabLanded Cost Voucher`
           WHERE company=%s AND docstatus=0""", (target,))[0]
    posted = frappe.db.sql(
        """SELECT COUNT(*), SUM(total_taxes_and_charges) FROM `tabLanded Cost Voucher`
           WHERE company=%s AND docstatus=1 AND posting_date>=%s""", (target, _FROM))[0]
    inbox = charge_inbox(company=target)
    return {"company": target, "from_date": _FROM,
            "uncovered_receipts": {"n": int(uncovered[0] or 0), "value": flt(uncovered[1])},
            "drafts": {"n": int(drafts[0] or 0), "value": flt(drafts[1])},
            "posted": {"n": int(posted[0] or 0), "value": flt(posted[1])},
            "inbox_total": round(sum(flt(c["amount"]) for c in inbox), 2), "inbox_n": len(inbox)}


@frappe.whitelist()
def charge_inbox(company=None):
    """Booked inbound charges (freight/customs/clearance accounts) since 2026
    not yet stamped into a submitted LCV. Grouped per source voucher."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return []
    rows = frappe.db.sql(
        f"""SELECT g.voucher_type vt, g.voucher_no vn, g.account, a.account_name,
                   g.posting_date dt, SUM(g.debit-g.credit) amount,
                   MAX(IFNULL(g.remarks,'')) remarks
            FROM `tabGL Entry` g JOIN `tabAccount` a ON a.name=g.account
            WHERE g.company=%s AND g.is_cancelled=0 AND g.posting_date>=%s
              AND g.voucher_type != 'Landed Cost Voucher' AND {_INBOUND}
            GROUP BY g.voucher_type, g.voucher_no, g.account, a.account_name, g.posting_date
            HAVING SUM(g.debit-g.credit) > 0.5
            ORDER BY g.posting_date DESC LIMIT 500""", (target, _FROM), as_dict=True)
    used = _used_charge_sources(target)
    # Credits these accounts received from receipt-GL reposts = charges ALREADY
    # capitalised by earlier LCVs (incl. the pre-portal drafts, which carry no
    # src-stamp). Surfaced per row so nobody re-attaches an absorbed bill.
    absorbed = dict(frappe.db.sql(
        f"""SELECT g.account, ROUND(SUM(g.credit - g.debit)) FROM `tabGL Entry` g
            JOIN `tabAccount` a ON a.name=g.account
            WHERE g.company=%s AND g.is_cancelled=0 AND g.posting_date>=%s
              AND g.voucher_type IN ('Purchase Receipt', 'Purchase Invoice') AND {_INBOUND}
            GROUP BY g.account HAVING SUM(g.credit - g.debit) > 0.5""", (target, _FROM)))
    out = []
    for r in rows:
        if r.vn in used:
            continue
        r["amount"] = flt(r.amount, 2)
        r["dt"] = str(r.dt)[:10]
        r["remarks"] = (r.remarks or "")[:120]
        r["account_absorbed"] = flt(absorbed.get(r.account))
        out.append(r)
    return out


@frappe.whitelist()
def receipts_uncovered(company=None, q=None, limit=100):
    """Submitted 2026 Purchase Receipts with no posted LCV over them."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return []
    cond, params = "", {"c": target, "f": _FROM, "lim": min(int(limit or 100), 300)}
    if q:
        cond = " AND (pr.name LIKE %(q)s OR pr.supplier LIKE %(q)s)"
        params["q"] = f"%{q}%"
    return frappe.db.sql(
        f"""SELECT pr.name, pr.supplier, pr.posting_date dt, pr.base_grand_total value,
                   pr.currency, (SELECT COUNT(*) FROM `tabPurchase Receipt Item` i WHERE i.parent=pr.name) items
            FROM `tabPurchase Receipt` pr
            WHERE pr.company=%(c)s AND pr.docstatus=1 AND pr.posting_date>=%(f)s {cond}
            AND pr.name NOT IN (
              SELECT lpr.receipt_document FROM `tabLanded Cost Purchase Receipt` lpr
              JOIN `tabLanded Cost Voucher` l ON l.name=lpr.parent WHERE l.docstatus=1)
            ORDER BY pr.posting_date DESC LIMIT %(lim)s""", params, as_dict=True)


@frappe.whitelist()
def draft_lcvs(company=None):
    """The stalled drafts — review, then submit or delete from the portal."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return []
    drafts = frappe.db.sql(
        """SELECT name, posting_date dt, total_taxes_and_charges total, distribute_charges_based_on basis
           FROM `tabLanded Cost Voucher` WHERE company=%s AND docstatus=0
           ORDER BY posting_date""", (target,), as_dict=True)
    for d in drafts:
        d["dt"] = str(d.dt or "")[:10]
        d["total"] = flt(d.total, 2)
        d["receipts"] = [r[0] for r in frappe.db.sql(
            "SELECT receipt_document FROM `tabLanded Cost Purchase Receipt` WHERE parent=%s", (d["name"],))]
        d["charges"] = frappe.db.sql(
            """SELECT expense_account, description, base_amount amount
               FROM `tabLanded Cost Taxes and Charges` WHERE parent=%s""", (d["name"],), as_dict=True)
        d["items_n"] = frappe.db.count("Landed Cost Item", {"parent": d["name"]})
    return drafts


@frappe.whitelist()
def submit_draft_lcv(company=None, name=None):
    """Submit an existing draft LCV through the gateway (audited, gated)."""
    assert_can_write()
    target = _target(company)
    doc = frappe.get_doc("Landed Cost Voucher", name)
    if doc.company != target:
        frappe.throw("Voucher is not in this company")
    if doc.docstatus != 0:
        frappe.throw(f"{name} is not a draft")
    return _actions.execute(
        LCV_ACTION, target, f"lcvsubmit:{name}",
        payload={"mode": "submit_draft", "name": name},
        amount=flt(doc.total_taxes_and_charges),
        reference_doctype="Landed Cost Voucher", reference_name=name,
        notes=f"Submit draft landed cost {name} ({flt(doc.total_taxes_and_charges):,.0f})")


DEL_ACTION = "Delete LCV draft"


@frappe.whitelist()
def delete_draft_lcv(company=None, name=None):
    """Drop a stale draft (draft only — never touches submitted vouchers).
    Goes through the gateway so the audit trail records who dropped what."""
    assert_can_write()
    target = _target(company)
    doc = frappe.get_doc("Landed Cost Voucher", name)
    if doc.company != target or doc.docstatus != 0:
        frappe.throw("Only a draft of this company can be deleted")
    return _actions.execute(
        DEL_ACTION, target, f"lcvdel:{name}",
        payload={"name": name}, amount=0,
        notes=f"Delete stalled landed-cost draft {name} ({flt(doc.total_taxes_and_charges):,.0f})")


def _del_draft_poster(action):
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    if frappe.db.get_value("Landed Cost Voucher", p["name"], "docstatus") == 0:
        frappe.delete_doc("Landed Cost Voucher", p["name"], ignore_permissions=True)
    return {"voucher_type": "Landed Cost Voucher", "voucher_no": p["name"], "result": "draft deleted"}


def _load_receipt_items(receipts):
    return frappe.db.sql(
        """SELECT pri.parent receipt, pri.name detail, pri.item_code, pri.description,
                  pri.qty, pri.base_rate rate, pri.base_amount amount, pri.cost_center,
                  IFNULL(it.weight_per_unit, 0) wpu
           FROM `tabPurchase Receipt Item` pri
           LEFT JOIN `tabItem` it ON it.name = pri.item_code
           WHERE pri.parent IN %s""",
        (tuple(receipts),), as_dict=True)


def _basis(i, mode):
    """A line's share basis: customs scale with value, freight with weight."""
    if mode == "Qty":
        return flt(i.get("qty"))
    if mode == "Weight":
        return flt(i.get("qty")) * flt(i.get("wpu"))
    return flt(i.get("amount"))


@frappe.whitelist()
def preview_lcv(company=None, receipts=None, charges=None, distribute_by="Amount"):
    """Allocation preview — NOTHING is posted. Per item: allocated charge and
    old → new unit cost, plus how many later stock moves would be reposted."""
    assert_portal_access()
    target = _target(company)
    receipts = json.loads(receipts) if isinstance(receipts, str) else (receipts or [])
    charges = json.loads(charges) if isinstance(charges, str) else (charges or [])
    if not (target and receipts and charges):
        frappe.throw("receipts and charges are required")
    items = _load_receipt_items(receipts)
    if not items:
        frappe.throw("No items on those receipts")
    total_charge = sum(flt(c.get("amount")) for c in charges)
    base = sum(_basis(i, distribute_by) for i in items)
    weightless = sum(1 for i in items if distribute_by == "Weight" and flt(i.wpu) <= 0)
    if distribute_by == "Weight" and base <= 0:
        frappe.throw("None of these items has a weight — set item weights first, or distribute by value/qty")
    rows = []
    for i in items:
        share = _basis(i, distribute_by) / base if base else 0
        alloc = round(total_charge * share, 2)
        i_qty = flt(i.qty) or 1
        rows.append({"receipt": i.receipt, "item_code": i.item_code,
                     "qty": flt(i.qty), "rate": flt(i.rate, 2),
                     "alloc": alloc, "per_unit": round(alloc / i_qty, 2),
                     "new_rate": round(flt(i.rate) + alloc / i_qty, 2)})
    rows.sort(key=lambda r: -r["alloc"])
    min_dt = frappe.db.sql(
        "SELECT MIN(posting_date) FROM `tabPurchase Receipt` WHERE name IN %s", (tuple(receipts),))[0][0]
    later_moves = frappe.db.sql(
        """SELECT COUNT(*) FROM `tabStock Ledger Entry`
           WHERE is_cancelled=0 AND posting_date >= %s AND item_code IN %s""",
        (min_dt, tuple({r["item_code"] for r in rows})))[0][0]
    return {"total_charge": round(total_charge, 2), "distribute_by": distribute_by,
            "lines": rows[:250], "lines_n": len(rows), "weightless_n": weightless,
            "later_moves_to_repost": int(later_moves or 0)}


@frappe.whitelist()
def post_lcv(company=None, receipts=None, charges=None, distribute_by="Amount", posting_date=None, notes=None):
    """Create + submit the Landed Cost Voucher via the audited gateway.
    Each charge line carries 'src:<voucher>' so the inbox never re-offers it.
    Accounting: Dr stock in hand / Cr the same expense account each charge was
    booked on — the P&L expense zeroes and the cost is capitalised."""
    assert_can_write()
    target = _target(company)
    receipts = json.loads(receipts) if isinstance(receipts, str) else (receipts or [])
    charges = json.loads(charges) if isinstance(charges, str) else (charges or [])
    if not (target and receipts and charges):
        frappe.throw("receipts and charges are required")
    for r in receipts:
        row = frappe.db.get_value("Purchase Receipt", r, ["company", "docstatus"], as_dict=True)
        if not row or row.company != target or row.docstatus != 1:
            frappe.throw(f"{r} is not a submitted receipt of {target}")
    total = 0.0
    for c in charges:
        amt = flt(c.get("amount"))
        if amt <= 0:
            frappe.throw("Every charge needs a positive amount")
        if not c.get("expense_account"):
            frappe.throw("Every charge needs an expense account")
        total += amt
    key = "lcv:" + frappe.generate_hash(f"{target}:{sorted(receipts)}:{total}:{distribute_by}", 12)
    return _actions.execute(
        LCV_ACTION, target, key,
        payload={"mode": "create", "receipts": receipts, "charges": charges,
                 "distribute_by": distribute_by, "posting_date": str(posting_date or nowdate())[:10]},
        amount=total,
        notes=notes or f"Landed cost {total:,.0f} over {len(receipts)} receipt(s)")


def _charge_desc(c):
    desc = (c.get("description") or c["expense_account"])[:100]
    if c.get("source"):
        desc = f"{desc} src:{c['source']}"
    return desc


def _new_lcv(company, posting_date, receipts, basis):
    doc = frappe.new_doc("Landed Cost Voucher")
    doc.company = company
    doc.posting_date = posting_date or nowdate()
    doc.distribute_charges_based_on = basis
    for r in receipts:
        pr = frappe.db.get_value("Purchase Receipt", r, ["supplier", "base_grand_total"], as_dict=True)
        doc.append("purchase_receipts", {
            "receipt_document_type": "Purchase Receipt", "receipt_document": r,
            "supplier": pr.supplier, "grand_total": pr.base_grand_total})
    doc.get_items_from_purchase_receipts()
    if not doc.get("items"):
        frappe.throw("The selected receipts carry no item lines")
    return doc


def _apply_weight_shares(doc, total):
    """Manual per-item allocation = weight share × total, residual on the
    heaviest line so the sum ties out to the charge exactly."""
    weights = dict(frappe.db.sql(
        "SELECT name, IFNULL(weight_per_unit,0) FROM `tabItem` WHERE name IN %s",
        (tuple({it.item_code for it in doc.items}),)))
    base = sum(flt(it.qty) * flt(weights.get(it.item_code)) for it in doc.items)
    if base <= 0:
        frappe.throw("None of these items has a weight — cannot distribute by weight")
    allocated, heaviest = 0.0, None
    for it in doc.items:
        share = flt(it.qty) * flt(weights.get(it.item_code)) / base
        it.applicable_charges = round(total * share, 2)
        allocated += it.applicable_charges
        if heaviest is None or it.applicable_charges > heaviest.applicable_charges:
            heaviest = it
    heaviest.applicable_charges = round(heaviest.applicable_charges + (total - allocated), 2)


def _lcv_poster(action):
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    if p.get("mode") == "submit_draft":
        doc = frappe.get_doc("Landed Cost Voucher", p["name"])
        doc.submit()
        return {"voucher_type": "Landed Cost Voucher", "voucher_no": doc.name, "result": "submitted"}
    mode = p.get("distribute_by") or "Amount"
    if mode == "Weight":
        # ERPNext's 'Distribute Manually' (our weight vehicle) allows exactly ONE
        # charge row per voucher — so weight mode posts one voucher per charge,
        # each weight-allocated over the same receipts. Cleaner accounting too:
        # every charge credits its own account on its own voucher.
        created = []
        for c in p["charges"]:
            doc = _new_lcv(action.company, p.get("posting_date"), p["receipts"], "Distribute Manually")
            _apply_weight_shares(doc, flt(c["amount"]))
            doc.append("taxes", {"expense_account": c["expense_account"],
                                 "description": _charge_desc(c), "amount": flt(c["amount"])})
            doc.insert(ignore_permissions=True)
            doc.submit()
            created.append(doc.name)
        # stash every voucher on the action so revert can cancel them all
        frappe.db.set_value(action.doctype, action.name, "payload",
                            json.dumps({**p, "created": created}, default=str), update_modified=False)
        total = sum(flt(c.get("amount")) for c in p["charges"])
        return {"voucher_type": "Landed Cost Voucher", "voucher_no": created[0],
                "result": f"{total:,.0f} by weight → {len(created)} voucher(s): {', '.join(created)}"[:130]}
    doc = _new_lcv(action.company, p.get("posting_date"), p["receipts"], mode)
    for c in p["charges"]:
        doc.append("taxes", {"expense_account": c["expense_account"],
                             "description": _charge_desc(c), "amount": flt(c["amount"])})
    doc.insert(ignore_permissions=True)
    doc.submit()
    return {"voucher_type": "Landed Cost Voucher", "voucher_no": doc.name,
            "result": f"{flt(doc.total_taxes_and_charges):,.0f} over {len(p['receipts'])} receipts"}


def _lcv_reverter(action):
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    names = p.get("created") or ([action.voucher_no] if action.voucher_no else [])
    cancelled = []
    for n in names:
        if n and frappe.db.exists("Landed Cost Voucher", n):
            doc = frappe.get_doc("Landed Cost Voucher", n)
            if doc.docstatus == 1:
                doc.cancel()
                cancelled.append(n)
    return {"voucher_type": "Landed Cost Voucher", "voucher_no": action.voucher_no,
            "result": f"cancelled {len(cancelled)}: {', '.join(cancelled)}"[:130]}


_actions.register_poster(LCV_ACTION, _lcv_poster)
_actions.register_reverter(LCV_ACTION, _lcv_reverter)
_actions.register_poster(DEL_ACTION, _del_draft_poster)
_actions._NO_GATE.add(DEL_ACTION)  # draft-only, no GL — audited but ungated
