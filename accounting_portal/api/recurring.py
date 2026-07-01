"""Recurring expenses — detect monthly/quarterly bills from history, flag what's
due, and (gated) pre-create the next bill as a DRAFT so it shows up early with a
reminder. No Auto Repeat needed: we copy the last bill forward as a draft, which
is safer and fully reversible (deleting the draft undoes it).
"""
import frappe
from frappe.utils import flt, getdate, add_months, nowdate, date_diff

from accounting_portal.api import _actions
from accounting_portal.api.expenses import _classify, _COLOR
from accounting_portal.api.permissions import (
    assert_portal_access, assert_can_write, resolve_companies)

RECUR_DRAFT_ACTION = "Create recurring draft"


def _target(company):
    companies = resolve_companies(company)
    if not companies:
        return None
    return company if (company and company in companies) else companies[0]


@frappe.whitelist()
def recurring_overview(company=None):
    """Supplier+expense-account combinations that recur (≥3 distinct months), with
    their cadence, next expected date and a due/overdue status."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    currency = frappe.db.get_value("Company", target, "default_currency") or "MAD"
    rows = frappe.db.sql(
        """SELECT pi.supplier, pii.expense_account acct, a.account_name accn, a.account_number num,
                  COUNT(DISTINCT DATE_FORMAT(pi.posting_date, '%%Y-%%m')) months,
                  ROUND(AVG(pii.base_amount)) avg_amt, ROUND(SUM(pii.base_amount)) total,
                  MAX(pi.posting_date) last_dt, MIN(pi.posting_date) first_dt
           FROM `tabPurchase Invoice Item` pii JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
           JOIN `tabAccount` a ON a.name=pii.expense_account
           WHERE pi.company=%s AND pi.docstatus=1 AND a.root_type='Expense'
           GROUP BY pi.supplier, pii.expense_account HAVING months>=3
           ORDER BY MAX(pi.posting_date) DESC LIMIT 80""", target, as_dict=True)

    today = getdate(nowdate())
    out = []
    for r in rows:
        span = date_diff(r.last_dt, r.first_dt)
        interval = round(span / (r.months - 1)) if r.months > 1 else 30
        cadence, step = ("Monthly", 1) if interval <= 45 else (("Quarterly", 3) if interval <= 135 else ("Yearly", 12))
        nxt = add_months(getdate(r.last_dt), step)
        dd = date_diff(nxt, today)  # days until next expected (negative = past)
        status = "overdue" if dd < -3 else ("due" if dd <= 7 else "ok")
        out.append({
            "supplier": r.supplier, "account": r.acct, "account_name": r.accn, "num": r.num,
            "category": _classify(r.num, r.accn), "color": _COLOR.get(_classify(r.num, r.accn), "#78716c"),
            "avg_amt": flt(r.avg_amt), "total": flt(r.total), "months": r.months, "cadence": cadence,
            "last": str(r.last_dt), "next": str(nxt), "days_until": dd, "status": status,
        })
    # due/overdue first, then by next date
    out.sort(key=lambda x: (0 if x["status"] == "overdue" else 1 if x["status"] == "due" else 2, x["days_until"]))
    return {"company": target, "currency": currency, "recurring": out,
            "due": sum(1 for x in out if x["status"] == "due"),
            "overdue": sum(1 for x in out if x["status"] == "overdue"),
            "monthly_total": round(sum(x["avg_amt"] for x in out if x["cadence"] == "Monthly"))}


@frappe.whitelist()
def create_recurring_draft(company=None, supplier=None, expense_account=None, dry_run=1):
    """Pre-create the next bill for a recurring expense as a DRAFT Purchase Invoice
    (a copy of the latest one, re-dated). Gated by write capability; audited;
    reversible (undo deletes the draft). Idempotent per calendar month."""
    assert_can_write()
    target = _target(company)
    if not (target and supplier and expense_account):
        frappe.throw("Supplier and account required")
    last = frappe.db.sql(
        """SELECT pi.name, pi.posting_date FROM `tabPurchase Invoice` pi
           JOIN `tabPurchase Invoice Item` pii ON pii.parent=pi.name
           WHERE pi.company=%s AND pi.supplier=%s AND pii.expense_account=%s AND pi.docstatus=1
           ORDER BY pi.posting_date DESC LIMIT 1""", (target, supplier, expense_account), as_dict=True)
    if not last:
        frappe.throw("No prior bill to copy")
    tmpl = last[0].name
    next_date = nowdate()
    preview = {"template": tmpl, "supplier": supplier, "account": expense_account, "next_date": next_date}
    if int(dry_run or 0):
        return {"dry_run": True, **preview}
    key = f"recur_draft:{target}:{supplier}:{expense_account}:{next_date[:7]}"
    res = _actions.execute(
        RECUR_DRAFT_ACTION, target, key,
        payload={"template": tmpl, "next_date": next_date},
        amount=0, notes=f"Recurring draft for {supplier} · {expense_account}")
    return {"dry_run": False, **preview, "result": res}


def _recur_draft_poster(action):
    import json
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    tmpl = p.get("template")
    d = frappe.copy_doc(frappe.get_doc("Purchase Invoice", tmpl))
    d.posting_date = p.get("next_date") or nowdate()
    d.set_posting_time = 1
    d.bill_no = ""
    d.bill_date = None
    d.due_date = None
    d.insert(ignore_permissions=True)  # stays a draft (docstatus 0)
    return {"voucher_type": "Purchase Invoice", "voucher_no": d.name, "result": "draft created"}


def _recur_draft_reverter(action):
    vn = action.voucher_no
    if vn and frappe.db.exists("Purchase Invoice", vn):
        doc = frappe.get_doc("Purchase Invoice", vn)
        if doc.docstatus == 0:
            frappe.delete_doc("Purchase Invoice", vn, ignore_permissions=True)
            return {"deleted": vn}
    return {"deleted": None}


_actions.register_poster(RECUR_DRAFT_ACTION, _recur_draft_poster)
_actions.register_reverter(RECUR_DRAFT_ACTION, _recur_draft_reverter)
