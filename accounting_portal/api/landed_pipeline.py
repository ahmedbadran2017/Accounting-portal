"""Landed Cost Pipeline — from "a charge was paid" to "it lives in the product".

The 2026 reality this fixes (verified on production): 2,458 Purchase Receipts
worth 15.5M MAD, only 3 covered by a posted Landed Cost Voucher; 12 draft LCVs
holding 754K of charges; freight/customs otherwise stranded outside inventory,
so item valuation (and every Delivery Note's COGS) misses the landed component.

Flow: charge inbox (booked charges not yet capitalised) → shipment builder
(pick receipts + charges, preview the per-item allocation) → post via the
audited gateway. Landed charges are billed to the 153.03 "Expenses Included In
Valuation" clearing account (a balance-sheet holding account, NOT a P&L 770.07
account); the LCV posts Dr stock / Cr 153.03 so 153.03 nets back to zero and the
cost lands in inventory — never in the P&L until it sells as COGS. Each charge is
allocated by its own basis (freight→weight, customs→value, agent→qty), posting
one voucher per basis-group. ERPNext reposts later SLEs so COGS heals.
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

# Domestic (Moroccan) purchases already carry their full cost — there is no import
# freight/customs to allocate — so they never need a landed cost voucher. We key
# off supplier_group, NOT country: the local sellers (keyza, Beauty Mall, …) are
# mis-tagged country="Turkey" but correctly grouped as "Morocco Local Suppliers".
_DOMESTIC_SUPPLIER_GROUPS = ("Morocco Local Suppliers", "Local")
_DOMESTIC_SQL = "COALESCE(sup.supplier_group,'') NOT IN (" + \
    ",".join("'" + g.replace("'", "''") + "'" for g in _DOMESTIC_SUPPLIER_GROUPS) + ")"

# A charge's natural distribution basis, keyed by category. Freight/handling ride
# on weight; duties/insurance scale with value; per-piece fees with quantity.
_CATEGORY_BASIS = {
    "freight": "Weight", "sea_freight": "Weight", "air_freight": "Weight",
    "handling": "Weight", "haulage": "Weight", "demurrage": "Weight", "forklift": "Weight",
    "customs": "Amount", "duty": "Amount", "insurance": "Amount", "vat": "Amount",
    "agent": "Qty", "clearance": "Qty", "stamp": "Qty",
}
# Sane conversion-rate band per source currency → MAD. A receipt booked outside
# the band (e.g. USD@45 or the TRY ×1e6 typos) is corrupt; block capitalisation.
_FX_BAND = {"USD": (8.0, 12.0), "TRY": (0.15, 0.45), "EUR": (9.0, 13.0), "MAD": (1.0, 1.0)}


def _target(company):
    companies = resolve_companies(company)
    if not companies:
        return None
    return company if (company and company in companies) else companies[0]


def _valuation_clearing(company):
    """The balance-sheet clearing account landed charges must sit on
    (Company → Expenses Included In Valuation, e.g. 153.03). Landed cost is a
    pending inventory cost, never a period expense — parking it here (not a P&L
    770.07 account) keeps the P&L clean and lets the account net back to zero."""
    acc = frappe.get_cached_value("Company", company, "expenses_included_in_valuation")
    if not acc:
        frappe.throw("Set the company's 'Expenses Included In Valuation' account (e.g. 153.03) first")
    return acc


def _account_root(account):
    return frappe.get_cached_value("Account", account, "root_type") if account else None


def _fx_offenders(receipts):
    """Receipts whose conversion_rate is outside the sane band for their currency."""
    bad = []
    for r in receipts:
        cur, rate = frappe.db.get_value("Purchase Receipt", r, ["currency", "conversion_rate"])
        lo, hi = _FX_BAND.get(cur, (0, 1e9))
        if flt(rate) < lo or flt(rate) > hi:
            bad.append({"receipt": r, "currency": cur, "rate": flt(rate), "band": [lo, hi]})
    return bad


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
        f"""SELECT COUNT(*), SUM(pr.base_grand_total) FROM `tabPurchase Receipt` pr
           JOIN `tabSupplier` sup ON sup.name = pr.supplier
           WHERE pr.company=%s AND pr.docstatus=1 AND pr.posting_date>=%s
           AND {_DOMESTIC_SQL}
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
    # 153.03 clearing: landed charges billed but not yet capitalised. Trends to ~0
    # when every inbound cost has flowed onto inventory via an LCV.
    clearing_acc = frappe.get_cached_value("Company", target, "expenses_included_in_valuation")
    clearing_bal = flt(frappe.db.sql(
        """SELECT SUM(debit-credit) FROM `tabGL Entry`
           WHERE company=%s AND account=%s AND is_cancelled=0""", (target, clearing_acc))[0][0]) if clearing_acc else 0.0
    uncovered_n = int(uncovered[0] or 0)
    return {"company": target, "from_date": _FROM,
            "uncovered_receipts": {"n": uncovered_n, "value": flt(uncovered[1])},
            "drafts": {"n": int(drafts[0] or 0), "value": flt(drafts[1])},
            "posted": {"n": int(posted[0] or 0), "value": flt(posted[1])},
            "clearing_account": clearing_acc, "clearing_balance": round(clearing_bal, 2),
            "is_month_closeable": abs(clearing_bal) < 1.0 and uncovered_n == 0,
            "inbox_total": round(sum(flt(c["amount"]) for c in inbox), 2), "inbox_n": len(inbox)}


@frappe.whitelist()
def charge_inbox(company=None):
    """Booked inbound charges (freight/customs/clearance accounts) since 2026
    not yet stamped into a submitted LCV. Grouped per source voucher."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return []
    clearing = frappe.get_cached_value("Company", target, "expenses_included_in_valuation")
    rows = frappe.db.sql(
        f"""SELECT g.voucher_type vt, g.voucher_no vn, g.account, a.account_name,
                   a.root_type, g.posting_date dt, SUM(g.debit-g.credit) amount,
                   MAX(IFNULL(g.remarks,'')) remarks
            FROM `tabGL Entry` g JOIN `tabAccount` a ON a.name=g.account
            WHERE g.company=%(c)s AND g.is_cancelled=0 AND g.posting_date>=%(f)s
              AND g.voucher_type != 'Landed Cost Voucher'
              AND ({_INBOUND} OR g.account = %(clr)s)
            GROUP BY g.voucher_type, g.voucher_no, g.account, a.account_name, a.root_type, g.posting_date
            HAVING SUM(g.debit-g.credit) > 0.5
            ORDER BY g.posting_date DESC LIMIT 500""",
        {"c": target, "f": _FROM, "clr": clearing}, as_dict=True)
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
        # A charge sitting on a P&L (Expense) account distorts the P&L and won't
        # net cleanly — it should be re-pointed to the 153.03 clearing account.
        r["is_legacy_pl"] = (r.get("root_type") == "Expense")
        out.append(r)
    return out


def _uncovered_where(target, search):
    """Shared WHERE for the uncovered-import-receipt lists. Excludes domestic
    (Moroccan-local) suppliers — those carry their full cost already."""
    cond = ""
    params = {"c": target, "f": _FROM}
    if search:
        cond = " AND (pr.name LIKE %(q)s OR pr.supplier LIKE %(q)s)"
        params["q"] = f"%{search}%"
    where = (f"""FROM `tabPurchase Receipt` pr
            JOIN `tabSupplier` sup ON sup.name = pr.supplier
            WHERE pr.company=%(c)s AND pr.docstatus=1 AND pr.posting_date>=%(f)s
            AND {_DOMESTIC_SQL} {cond}
            AND pr.name NOT IN (
              SELECT lpr.receipt_document FROM `tabLanded Cost Purchase Receipt` lpr
              JOIN `tabLanded Cost Voucher` l ON l.name=lpr.parent WHERE l.docstatus=1)""")
    return where, params


@frappe.whitelist()
def receipts_uncovered(company=None, q=None, limit=100):
    """Submitted 2026 import Purchase Receipts with no posted LCV over them
    (array form, used by the shipment pipeline). Domestic suppliers excluded."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return []
    where, params = _uncovered_where(target, q)
    params["lim"] = min(int(limit or 100), 300)
    return frappe.db.sql(
        f"""SELECT pr.name, pr.supplier, pr.posting_date dt, pr.base_grand_total value,
                   pr.currency, (SELECT COUNT(*) FROM `tabPurchase Receipt Item` i WHERE i.parent=pr.name) items
            {where}
            ORDER BY pr.posting_date DESC LIMIT %(lim)s""", params, as_dict=True)


@frappe.whitelist()
def receipts_uncovered_page(company=None, start=0, page_size=25, search=None, **kwargs):
    """Server-paginated + searchable form for the cockpit table. Returns
    {rows, total} so the whole backlog is reachable, not just the first page."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {"rows": [], "total": 0}
    where, params = _uncovered_where(target, search)
    total = frappe.db.sql(f"SELECT COUNT(*) {where}", params)[0][0]
    params["start"] = max(int(start or 0), 0)
    params["ps"] = min(max(int(page_size or 25), 1), 200)
    rows = frappe.db.sql(
        f"""SELECT pr.name, pr.supplier, pr.posting_date dt, pr.base_grand_total value,
                   pr.currency, (SELECT COUNT(*) FROM `tabPurchase Receipt Item` i WHERE i.parent=pr.name) items
            {where}
            ORDER BY pr.posting_date DESC LIMIT %(ps)s OFFSET %(start)s""", params, as_dict=True)
    return {"rows": rows, "total": int(total or 0)}


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
    # Guard the trap: a pre-portal draft that charges a P&L (770.07) account would
    # post Dr stock / Cr P&L, leaving the abnormal balances we're fixing. Block it
    # — rebuild the shipment through the cockpit so charges credit 153.03 instead.
    pl = [t.expense_account for t in doc.get("taxes") or []
          if frappe.get_cached_value("Account", t.expense_account, "root_type") == "Expense"]
    if pl:
        frappe.throw("This draft charges a P&L account (" + ", ".join(sorted(set(pl))[:2])
                     + "…) — rebuild it in the Landed Cockpit so charges credit the 153.03 clearing account, then delete this draft.")
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


CANCEL_LCV_ACTION = "Un-capitalise landed cost"


@frappe.whitelist()
def cancel_lcv(company=None, name=None, notes=None):
    """Cancel a SUBMITTED Landed Cost Voucher — reverses its GL (Dr charge acct /
    Cr stock) and reposts every later stock move so item valuation and COGS drop
    back to pre-LCV. Use to un-capitalise the pre-portal LCVs that charged P&L
    (770.07) accounts, then rebuild the shipment cleanly through the cockpit onto
    153.03. Gated/audited. Not auto-revertible — rebuild via the cockpit to redo."""
    assert_can_write()
    target = _target(company)
    doc = frappe.get_doc("Landed Cost Voucher", name)
    if doc.company != target:
        frappe.throw("Voucher is not in this company")
    if doc.docstatus != 1:
        frappe.throw(f"{name} is not a submitted voucher")
    return _actions.execute(
        CANCEL_LCV_ACTION, target, f"lcvcancel:{name}",
        payload={"name": name}, amount=flt(doc.total_taxes_and_charges),
        reference_doctype="Landed Cost Voucher", reference_name=name,
        notes=notes or f"Un-capitalise (cancel) landed cost {name} ({flt(doc.total_taxes_and_charges):,.0f}) — rebuild via cockpit")


def _cancel_lcv_poster(action):
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    doc = frappe.get_doc("Landed Cost Voucher", p["name"])
    if doc.docstatus == 1:
        doc.cancel()
    return {"voucher_type": "Landed Cost Voucher", "voucher_no": p["name"],
            "result": "cancelled — inventory & COGS reposted back to pre-LCV"}


def _cancel_lcv_reverter(action):
    frappe.throw("Un-capitalising an LCV can't be auto-reversed — rebuild the shipment "
                 "in the Landed Cockpit to re-capitalise the cost onto 153.03.")


_actions.register_poster(CANCEL_LCV_ACTION, _cancel_lcv_poster)
_actions.register_reverter(CANCEL_LCV_ACTION, _cancel_lcv_reverter)


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


def _charge_basis(c, default_basis):
    """Resolve a charge's distribution basis: explicit category → its natural
    basis, else an explicit 'basis', else the voucher-level default."""
    cat = (c.get("category") or "").lower().strip()
    return _CATEGORY_BASIS.get(cat) or c.get("basis") or default_basis


@frappe.whitelist()
def preview_lcv(company=None, receipts=None, charges=None, distribute_by="Amount"):
    """Allocation preview — NOTHING is posted. Each charge is allocated over the
    items by ITS OWN basis (freight by weight, customs by value, agent by qty),
    so per-item landed cost is accurate. Returns per-item old→new unit cost, a
    per-basis breakdown, and blocking guardrail flags (FX out of band, no weight)."""
    assert_portal_access()
    target = _target(company)
    receipts = json.loads(receipts) if isinstance(receipts, str) else (receipts or [])
    charges = json.loads(charges) if isinstance(charges, str) else (charges or [])
    if not (target and receipts and charges):
        frappe.throw("receipts and charges are required")
    items = _load_receipt_items(receipts)
    if not items:
        frappe.throw("No items on those receipts")

    acc = {i.item_code: {"receipt": i.receipt, "item_code": i.item_code, "qty": flt(i.qty),
                         "rate": flt(i.rate, 2), "alloc": 0.0} for i in items}
    by_basis = {}
    needs_weight = False
    for c in charges:
        b = _charge_basis(c, distribute_by)
        amt = flt(c.get("amount"))
        by_basis[b] = round(by_basis.get(b, 0.0) + amt, 2)
        base = sum(_basis(i, b) for i in items)
        if b == "Weight" and base <= 0:
            needs_weight = True
            continue
        for i in items:
            share = _basis(i, b) / base if base else 0
            acc[i.item_code]["alloc"] += amt * share
    rows = []
    for r in acc.values():
        q = r["qty"] or 1
        r["alloc"] = round(r["alloc"], 2)
        r["per_unit"] = round(r["alloc"] / q, 2)
        r["new_rate"] = round(r["rate"] + r["alloc"] / q, 2)
        rows.append(r)
    rows.sort(key=lambda r: -r["alloc"])

    fx_bad = _fx_offenders(receipts)
    pl_charges = [c.get("description") or c.get("expense_account") for c in charges
                  if _account_root(c.get("expense_account")) == "Expense"]
    min_dt = frappe.db.sql(
        "SELECT MIN(posting_date) FROM `tabPurchase Receipt` WHERE name IN %s", (tuple(receipts),))[0][0]
    later_moves = frappe.db.sql(
        """SELECT COUNT(*) FROM `tabStock Ledger Entry`
           WHERE is_cancelled=0 AND posting_date >= %s AND item_code IN %s""",
        (min_dt, tuple({r["item_code"] for r in rows})))[0][0]
    return {"total_charge": round(sum(by_basis.values()), 2), "by_basis": by_basis,
            "lines": rows[:250], "lines_n": len(rows),
            "later_moves_to_repost": int(later_moves or 0),
            "blocked": bool(fx_bad) or needs_weight,
            "fx_offenders": fx_bad, "needs_weight": needs_weight,
            "legacy_pl_charges": pl_charges}


@frappe.whitelist()
def post_lcv(company=None, receipts=None, charges=None, distribute_by="Amount", posting_date=None, notes=None):
    """Create + submit the Landed Cost Voucher(s) via the audited gateway.
    Charges are grouped by basis (freight→weight, customs→value, agent→qty) and
    post one voucher per group; each carries 'src:<voucher>' so the inbox never
    re-offers it. Accounting: Dr stock in hand / Cr the account each charge sits
    on (153.03 clearing for new charges) — the cost is capitalised into inventory.
    Blocks on FX out of band before posting."""
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
    fx_bad = _fx_offenders(receipts)
    if fx_bad:
        frappe.throw("FX out of band — fix the purchase rate before capitalising: "
                     + ", ".join(f"{b['receipt']} {b['currency']}@{b['rate']}" for b in fx_bad))
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


@frappe.whitelist()
def record_landed_charge(company=None, supplier=None, category=None, amount=None,
                         posting_date=None, bill_no=None, description=None,
                         tax_amount=0, tax_account=None, paid_from=None,
                         currency=None, exchange_rate=None,
                         attachment=None, attachment_name=None):
    """Book a freight / customs / clearance vendor bill onto the 153.03 clearing
    account (never a P&L 770.07 account) so it can be capitalised cleanly by an
    LCV. A thin wrapper over create_supplier_bill that pins the expense account to
    the company's Expenses-Included-In-Valuation account and tags the category so
    the cockpit picks the right distribution basis. Gated/audited/reversible."""
    from accounting_portal.api.expenses import create_supplier_bill
    assert_can_write()
    target = _target(company)
    cat = (category or "").lower().strip()
    if cat and cat not in _CATEGORY_BASIS:
        frappe.throw(f"Unknown landed-cost category '{category}'. Use one of: {', '.join(sorted(_CATEGORY_BASIS))}")
    clearing = _valuation_clearing(target)
    label = (description or category or "Landed charge").strip()
    desc = f"[{cat or 'landed'}] {label}"[:180]
    return create_supplier_bill(
        company=target, supplier=supplier, expense_account=clearing, amount=amount,
        posting_date=posting_date, bill_no=bill_no, description=desc,
        tax_amount=tax_amount, tax_account=tax_account, paid_from=paid_from,
        currency=currency, exchange_rate=exchange_rate,
        attachment=attachment, attachment_name=attachment_name)


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
    default_basis = p.get("distribute_by") or "Amount"
    # Group charges by their resolved basis so freight rides on weight and customs
    # on value even inside one shipment. Each group posts its own voucher(s).
    groups = {}
    for c in p["charges"]:
        groups.setdefault(_charge_basis(c, default_basis), []).append(c)
    created = []
    for basis, charges in groups.items():
        if basis == "Weight":
            # 'Distribute Manually' (our weight vehicle) allows exactly ONE charge
            # row per voucher — so weight charges post one voucher each.
            for c in charges:
                doc = _new_lcv(action.company, p.get("posting_date"), p["receipts"], "Distribute Manually")
                _apply_weight_shares(doc, flt(c["amount"]))
                doc.append("taxes", {"expense_account": c["expense_account"],
                                     "description": _charge_desc(c), "amount": flt(c["amount"])})
                doc.insert(ignore_permissions=True)
                doc.submit()
                created.append(doc.name)
        else:
            doc = _new_lcv(action.company, p.get("posting_date"), p["receipts"], basis)
            for c in charges:
                doc.append("taxes", {"expense_account": c["expense_account"],
                                     "description": _charge_desc(c), "amount": flt(c["amount"])})
            doc.insert(ignore_permissions=True)
            doc.submit()
            created.append(doc.name)
    # stash every voucher on the action so revert can cancel them all
    frappe.db.set_value(action.doctype, action.name, "payload",
                        json.dumps({**p, "created": created}, default=str), update_modified=False)
    total = sum(flt(c.get("amount")) for c in p["charges"])
    bases = ", ".join(f"{b}×{len(cs)}" for b, cs in groups.items())
    return {"voucher_type": "Landed Cost Voucher", "voucher_no": created[0],
            "result": f"{total:,.0f} → {len(created)} LCV [{bases}]: {', '.join(created)}"[:140]}


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
