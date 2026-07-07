"""Accountant write operations — the team works the books from the portal.

Every posting goes through the _actions write gateway, so it inherits the same
controls as everything else: capability check, idempotency, an audit record, and
a propose→approve→post gate for material entries. This module owns the Journal
Entry operation (the accountant's core tool: corrections, accruals,
reclassifications); other documents (Payment Entry, Sales Invoice…) follow.
"""
import json

import frappe
from frappe.utils import flt, nowdate

from accounting_portal.api import _actions, _paginate
from accounting_portal.api.permissions import assert_can_write, assert_portal_access, resolve_companies

JE_ACTION = "Post Correction"


@frappe.whitelist()
def party_options(party_type=None, q=None, limit=25):
    """Search parties for a JE line. Receivable accounts need a Customer,
    Payable a Supplier; Employee for advances/payroll."""
    assert_portal_access()
    dt = {"Customer": "Customer", "Supplier": "Supplier", "Employee": "Employee"}.get(party_type)
    if not dt:
        return []
    name_field = "employee_name" if dt == "Employee" else f"{dt.lower()}_name"
    active = "status='Active'" if dt == "Employee" else "IFNULL(disabled,0)=0"
    cond = ""
    params = {"lim": min(int(limit or 25), 50)}
    if q:
        cond = f" AND (name LIKE %(q)s OR {name_field} LIKE %(q)s)"
        params["q"] = f"%{q}%"
    return frappe.db.sql(
        f"""SELECT name, {name_field} AS label FROM `tab{dt}`
            WHERE {active}{cond} ORDER BY {name_field} LIMIT %(lim)s""",
        params, as_dict=True)


@frappe.whitelist()
def account_options(company=None):
    """Postable (non-group) accounts for the company — the JE form's picker."""
    assert_portal_access()
    companies = resolve_companies(company)
    if not companies:
        return []
    target = company if (company and company in companies) else companies[0]
    return frappe.db.sql(
        """SELECT name, account_name, IFNULL(account_type, '') AS type, account_currency AS currency
           FROM `tabAccount` WHERE company=%s AND is_group=0 AND disabled=0
           ORDER BY name""",
        (target,), as_dict=True)


def _je_poster(action):
    """Create + submit a balanced Journal Entry from the action payload."""
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    je = frappe.get_doc({
        "doctype": "Journal Entry",
        "company": action.company,
        "posting_date": p.get("posting_date") or nowdate(),
        "voucher_type": "Journal Entry",
        # Allow lines on accounts whose currency differs from the company default
        # (the books carry USD/TRY accounts); same-currency lines just use rate 1.
        "multi_currency": 1,
        "user_remark": p.get("remark") or "Posted via Accounting Portal",
        "accounts": [
            {
                "account": ln["account"],
                "debit_in_account_currency": flt(ln.get("debit")),
                "credit_in_account_currency": flt(ln.get("credit")),
                "party_type": ln.get("party_type") or None,
                "party": ln.get("party") or None,
            }
            for ln in (p.get("lines") or [])
        ],
    })
    je.insert(ignore_permissions=True)
    je.submit()
    return {"voucher_type": "Journal Entry", "voucher_no": je.name, "result": "submitted"}


_actions.register_poster(JE_ACTION, _je_poster)


@frappe.whitelist()
def propose_inventory_correction(company=None):
    """Diagnose the perpetual-stock-not-relieving-to-COGS break and propose a
    reclassification journal (NOT posted) the accountant reviews, edits and
    submits — it then runs through the gated propose→approve→post flow.

    Default proposal nets the Stock-Adjustment churn against the over-stated
    Stock asset; the alternative routes it to COGS for delivered goods.
    """
    assert_portal_access()
    companies = resolve_companies(company)
    if not companies:
        return {}
    target = company if (company and company in companies) else companies[0]

    def _top(where):
        r = frappe.db.sql(
            f"""SELECT a.name, ROUND(SUM(g.debit-g.credit)) bal FROM `tabGL Entry` g
                JOIN `tabAccount` a ON a.name=g.account
                WHERE g.company=%s AND g.is_cancelled=0 AND {where}
                GROUP BY a.name ORDER BY ABS(SUM(g.debit-g.credit)) DESC LIMIT 1""",
            (target,), as_dict=True)
        return (r[0].name, flt(r[0].bal)) if r else (None, 0.0)

    stock_acct, stock_bal = _top("a.account_type='Stock'")
    adj_acct, adj_bal = _top("a.account_name LIKE '%%Stock Adjustment%%'")
    cogs_acct, _ = _top("a.account_type='Cost of Goods Sold'")
    if not (stock_acct and adj_acct):
        return {"available": False}

    # Net the misnamed adjustment against the over-stated stock: zero the
    # adjustment and reduce stock by the same amount.
    amount = round(min(abs(stock_bal), abs(adj_bal)), 2)
    # Adjustment carries a credit balance (negative) → debit it to clear; stock
    # is a debit balance (positive) → credit it to reduce.
    lines = [
        {"account": adj_acct, "debit": amount, "credit": 0,
         "label": "Clear the Stock-Adjustment churn"},
        {"account": stock_acct, "debit": 0, "credit": amount,
         "label": "Reduce over-stated stock-in-hand"},
    ]
    return {
        "available": True, "company": target,
        "stock_account": stock_acct, "stock_balance": stock_bal,
        "adjustment_account": adj_acct, "adjustment_balance": adj_bal,
        "cogs_account": cogs_acct,
        "suggested_amount": amount,
        "lines": lines,
        "remark": "Reclassify Stock-Adjustment churn against over-stated stock (inventory health fix)",
        "stock_after": round(stock_bal - amount, 2),
        "note_alt": cogs_acct,  # alternative credit target for delivered goods
    }


@frappe.whitelist()
def propose_correction_pile(company=None):
    """Diagnose the “Correction Need” pile and propose a reclassification journal
    (NOT posted) to clear it to COGS — the parked stock-delivery corrections. The
    accountant reviews/edits the target account and submits via the gated flow."""
    assert_portal_access()
    companies = resolve_companies(company)
    if not companies:
        return {}
    target = company if (company and company in companies) else companies[0]

    def _top(where):
        r = frappe.db.sql(
            f"""SELECT a.name, ROUND(SUM(g.debit-g.credit)) bal, COUNT(*) n FROM `tabGL Entry` g
                JOIN `tabAccount` a ON a.name=g.account
                WHERE g.company=%s AND g.is_cancelled=0 AND {where}
                GROUP BY a.name ORDER BY ABS(SUM(g.debit-g.credit)) DESC LIMIT 1""",
            (target,), as_dict=True)
        return (r[0].name, flt(r[0].bal), r[0].n) if r else (None, 0.0, 0)

    acct, bal, n = _top("a.account_name LIKE '%%Correction%%'")
    cogs, _, _ = _top("a.account_type='Cost of Goods Sold'")
    if not acct or abs(bal) < 1:
        return {"available": False}
    amount = round(abs(bal), 2)
    # Debit balance ⇒ credit it to clear, debit the target; and vice-versa.
    if bal >= 0:
        lines = [{"account": acct, "debit": 0, "credit": amount, "label": "Clear the Correction-Need pile"},
                 {"account": cogs, "debit": amount, "credit": 0, "label": "Reclassify to COGS"}]
    else:
        lines = [{"account": acct, "debit": amount, "credit": 0, "label": "Clear the Correction-Need pile"},
                 {"account": cogs, "debit": 0, "credit": amount, "label": "Reclassify to COGS"}]
    return {
        "available": True, "company": target,
        "account": acct, "balance": bal, "entries": n, "cogs_account": cogs,
        "suggested_amount": amount, "lines": lines, "after": 0,
        "remark": "Reclassify the Correction-Need pile to COGS (triage)",
    }


@frappe.whitelist()
def create_journal_entry(company=None, posting_date=None, lines=None, remark=None, dedupe_key=None):
    """Post a balanced Journal Entry through the write gateway.

    `lines`: [{account, debit, credit, party_type?, party?}, …] — debits must
    equal credits. Material entries (≥ the gateway threshold) are recorded as
    Proposed and require an approver before they post.
    """
    assert_can_write()
    companies = resolve_companies(company)
    if not companies:
        frappe.throw("No company in scope")
    target = company if (company and company in companies) else companies[0]

    if isinstance(lines, str):
        lines = json.loads(lines)
    lines = lines or []
    if len(lines) < 2:
        frappe.throw("A journal entry needs at least two lines")

    dr = sum(flt(ln.get("debit")) for ln in lines)
    cr = sum(flt(ln.get("credit")) for ln in lines)
    if round(dr - cr, 2) != 0:
        frappe.throw(f"Debits ({dr:,.2f}) and credits ({cr:,.2f}) must balance")
    if dr <= 0:
        frappe.throw("Journal entry has no amount")

    posting_date = posting_date or nowdate()
    key = dedupe_key or f"je:{target}:{posting_date}:{round(dr, 2)}:{(remark or '')[:40]}"
    payload = {"posting_date": posting_date, "lines": lines, "remark": remark}
    return _actions.execute(JE_ACTION, target, key, payload=payload, amount=dr, notes=remark)


@frappe.whitelist()
def list_journals(company=None, search=None, from_date=None, to_date=None,
                  start=0, page_size=25, sort_field="date", sort_dir="desc"):
    """Journal Entries for one company, server-paginated. Includes drafts
    (docstatus 0) so they can be submitted."""
    assert_portal_access()
    companies = resolve_companies(company)
    if not companies:
        return {"rows": [], "total": 0}
    target = company if (company and company in companies) else companies[0]
    conds = ["je.company=%(c)s", "je.docstatus<2"]
    params = {"c": target}
    if from_date:
        conds.append("je.posting_date >= %(fd)s"); params["fd"] = from_date
    if to_date:
        conds.append("je.posting_date <= %(td)s"); params["td"] = to_date
    if search:
        conds.append("(je.name LIKE %(s)s OR IFNULL(je.user_remark,'') LIKE %(s)s OR IFNULL(je.cheque_no,'') LIKE %(s)s OR je.voucher_type LIKE %(s)s)")
        params["s"] = f"%{search}%"
    sort = {"date": "je.posting_date", "amount": "je.total_debit", "id": "je.name", "type": "je.voucher_type"}
    col = sort.get(sort_field, "je.posting_date")
    d = "ASC" if str(sort_dir).lower() == "asc" else "DESC"
    rows, total, s, ps = _paginate.page_query(
        "`tabJournal Entry` je", " AND ".join(conds), params,
        "je.name, je.posting_date AS date, je.voucher_type AS type, ROUND(je.total_debit,2) AS amount, "
        "IFNULL(je.user_remark,'') AS remark, je.docstatus, IFNULL(je.cheque_no,'') AS reference",
        f"{col} {d}, je.creation {d}", start, page_size)
    for r in rows:
        r["amount"] = flt(r["amount"])
        r["date"] = str(r.get("date") or "")
        r["status"] = ["draft", "submitted", "cancelled"][r["docstatus"]] if r["docstatus"] < 3 else "—"
    return {"rows": rows, "total": total, "start": s, "page_size": ps}


@frappe.whitelist()
def get_journal(name=None):
    """One Journal Entry — header + its account lines (Dr/Cr, party, references)."""
    assert_portal_access()
    je = frappe.db.get_value(
        "Journal Entry", name,
        ["name", "company", "posting_date", "voucher_type", "user_remark", "total_debit",
         "total_credit", "docstatus", "cheque_no", "cheque_date", "clearance_date"], as_dict=True)
    if not je:
        frappe.throw("Journal not found")
    if je.company not in resolve_companies():
        frappe.throw("Not permitted", frappe.PermissionError)
    accounts = frappe.db.sql(
        """SELECT jea.account, IFNULL(a.account_name, jea.account) AS account_name,
                  jea.party_type, jea.party, ROUND(jea.debit, 2) AS debit, ROUND(jea.credit, 2) AS credit,
                  jea.reference_type, jea.reference_name
           FROM `tabJournal Entry Account` jea LEFT JOIN `tabAccount` a ON a.name=jea.account
           WHERE jea.parent=%s ORDER BY jea.idx""", name, as_dict=True)
    for r in accounts:
        r["debit"] = flt(r["debit"]); r["credit"] = flt(r["credit"])
    je["accounts"] = accounts
    je["total_debit"] = flt(je.total_debit)
    je["status"] = ["Draft", "Submitted", "Cancelled"][je.docstatus] if je.docstatus < 3 else "—"
    je["posting_date"] = str(je.posting_date or "")
    je["clearance_date"] = str(je.clearance_date or "")
    return je


# ── Opening-balance entry ────────────────────────────────────────────────────
OPENING_ACTION = "Opening Entry"


def _opening_poster(action):
    """Create + submit an opening-balance Journal Entry (is_opening = Yes)."""
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    je = frappe.get_doc({
        "doctype": "Journal Entry",
        "company": action.company,
        "posting_date": p.get("posting_date") or nowdate(),
        "voucher_type": "Opening Entry",
        "is_opening": "Yes",
        "multi_currency": 1,
        "user_remark": p.get("remark") or "Opening balance via Accounting Portal",
        "accounts": [
            {
                "account": ln["account"],
                "debit_in_account_currency": flt(ln.get("debit")),
                "credit_in_account_currency": flt(ln.get("credit")),
                "party_type": ln.get("party_type") or None,
                "party": ln.get("party") or None,
            }
            for ln in (p.get("lines") or [])
        ],
    })
    je.insert(ignore_permissions=True)
    je.submit()
    return {"voucher_type": "Journal Entry", "voucher_no": je.name, "result": "opening submitted"}


_actions.register_poster(OPENING_ACTION, _opening_poster)


@frappe.whitelist()
def create_opening_entry(company=None, posting_date=None, lines=None, remark=None, dedupe_key=None):
    """Post a balanced opening-balance entry (is_opening = Yes) through the gateway.
    `lines`: [{account, debit, credit, party_type?, party?}, …] — must balance."""
    assert_can_write()
    companies = resolve_companies(company)
    if not companies:
        frappe.throw("No company in scope")
    target = company if (company and company in companies) else companies[0]
    if isinstance(lines, str):
        lines = json.loads(lines)
    lines = lines or []
    if len(lines) < 2:
        frappe.throw("An opening entry needs at least two lines")
    dr = sum(flt(ln.get("debit")) for ln in lines)
    cr = sum(flt(ln.get("credit")) for ln in lines)
    if round(dr - cr, 2) != 0:
        frappe.throw(f"Debits ({dr:,.2f}) and credits ({cr:,.2f}) must balance")
    if dr <= 0:
        frappe.throw("Opening entry has no amount")
    posting_date = posting_date or nowdate()
    key = dedupe_key or f"open:{target}:{posting_date}:{round(dr, 2)}:{(remark or '')[:40]}"
    payload = {"posting_date": posting_date, "lines": lines, "remark": remark}
    return _actions.execute(OPENING_ACTION, target, key, payload=payload, amount=dr, notes=remark or "Opening entry")


# ── FX revaluation preview (unrealized gain/loss on foreign-currency balances) ─
@frappe.whitelist()
def fx_revaluation(company=None):
    """Unrealized FX gain/loss on monetary foreign-currency account balances,
    revalued at the latest stored rate. Read-only diagnostic (ERPNext's own
    revaluation tool crashes on these books' missing rates). Fixed assets / stock
    / equity are excluded — only monetary items are revalued. Accounts missing a
    rate are flagged so the team can set it in Settings → Currencies."""
    assert_portal_access()
    companies = resolve_companies(company)
    target = company if (company and company in companies) else (companies[0] if companies else None)
    if not target:
        return {"rows": [], "summary": {}}
    ck = f"ap_fxr:{target}"
    cached_hit = frappe.cache().get_value(ck)
    if cached_hit is not None:
        return cached_hit
    base = frappe.db.get_value("Company", target, "default_currency") or "MAD"
    accts = frappe.db.sql(
        """SELECT a.name AS account, a.account_currency AS ccy,
                  ROUND(SUM(g.debit_in_account_currency - g.credit_in_account_currency), 2) AS bal_acct,
                  ROUND(SUM(g.debit - g.credit), 2) AS bal_base
           FROM `tabGL Entry` g JOIN `tabAccount` a ON a.name = g.account
           WHERE g.company=%s AND g.is_cancelled=0 AND a.is_group=0
             AND a.account_currency IS NOT NULL AND a.account_currency <> %s
             AND a.root_type IN ('Asset','Liability')
             AND IFNULL(a.account_type,'') NOT IN ('Fixed Asset','Stock','Capital Work in Progress','Accumulated Depreciation')
           GROUP BY a.name HAVING ABS(SUM(g.debit - g.credit)) > 0.5
           ORDER BY ABS(SUM(g.debit - g.credit)) DESC""",
        (target, base), as_dict=True)
    rate_cache = {}

    def rate_for(ccy):
        if ccy not in rate_cache:
            r = frappe.db.sql(
                """SELECT exchange_rate FROM `tabCurrency Exchange`
                   WHERE from_currency=%s AND to_currency=%s ORDER BY date DESC LIMIT 1""",
                (ccy, base))
            rate_cache[ccy] = flt(r[0][0]) if r else None
        return rate_cache[ccy]

    rows, total, missing = [], 0.0, 0
    for a in accts:
        r = rate_for(a["ccy"])
        if r is None:
            missing += 1
            rows.append({**a, "rate": None, "revalued": None, "unrealized": None})
            continue
        revalued = round(flt(a["bal_acct"]) * r, 2)
        unrealized = round(revalued - flt(a["bal_base"]), 2)
        total += unrealized
        rows.append({**a, "rate": r, "revalued": revalued, "unrealized": unrealized})
    result = {
        "company": target, "currency": base, "rows": rows,
        "summary": {"count": len(rows), "total_unrealized": round(total, 2),
                    "missing_rate": missing},
    }
    try:
        frappe.cache().set_value(ck, result, expires_in_sec=180)
    except Exception:
        pass
    return result
