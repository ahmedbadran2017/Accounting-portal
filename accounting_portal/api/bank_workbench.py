"""Bank reconciliation workbench — statement imports as persistent work sessions.

The old flow parsed + matched inside a modal: close it and the work was gone.
Here every upload becomes a `Bank Statement Import AP` record — the file, the
parsed lines, and each line's status (pending / matched / created / ignored,
with the voucher or reason) — so a 1,400-line statement can be worked through
over days, by several accountants, with full history of who did what.

Line lifecycle:
  pending  → matched  (auto-match on import, or manual match to an uncleared
                       book entry; marks the entry cleared at the line's date)
           → created  (the line was missing in the books; the accountant
                       registered it via the expense modal — JE or paid PI —
                       and the new voucher is pinned to the line)
           → ignored  (bank noise / duplicate, with a reason)
  Every action stamps who + when on the line.
"""
import json

import frappe
from frappe.utils import flt, nowdate

from accounting_portal.api.permissions import assert_portal_access, assert_can_write, resolve_companies

BSI = "Bank Statement Import AP"


def _target(company):
    companies = resolve_companies(company)
    if not companies:
        return None
    return company if (company and company in companies) else companies[0]


def _load(name, target):
    doc = frappe.get_doc(BSI, name)
    if doc.company != target:
        frappe.throw("Import not found in this company")
    lines = json.loads(doc.lines or "[]")
    return doc, lines


def _save(doc, lines):
    doc.n_total = len(lines)
    doc.n_matched = sum(1 for l in lines if l.get("status") == "matched")
    doc.n_created = sum(1 for l in lines if l.get("status") == "created")
    doc.n_ignored = sum(1 for l in lines if l.get("status") == "ignored")
    pending = doc.n_total - doc.n_matched - doc.n_created - doc.n_ignored
    doc.status = "Done" if pending == 0 else f"{pending} pending"
    doc.lines = json.dumps(lines, default=str)
    doc.save(ignore_permissions=True)
    frappe.db.commit()


def _stats(doc):
    return {"name": doc.name, "account": doc.account, "file_name": doc.file_name,
            "file_url": doc.file_url, "from_date": str(doc.from_date or ""),
            "to_date": str(doc.to_date or ""), "n_total": doc.n_total,
            "n_matched": doc.n_matched, "n_created": doc.n_created,
            "n_ignored": doc.n_ignored, "status": doc.status,
            "owner": doc.owner, "modified": str(doc.modified)[:16]}


@frappe.whitelist()
def create_import(company=None, account=None, file_url=None, file_name=None, mapping=None):
    """Parse the uploaded statement, auto-match against the books, persist
    everything as a resumable work session."""
    assert_can_write()
    target = _target(company)
    if not (target and account and file_url):
        frappe.throw("company, account and file_url are required")
    if frappe.db.get_value("Account", account, "company") != target:
        frappe.throw("Account not in this company")
    from accounting_portal.api.bank_import import parse_statement, match_statement
    parsed = parse_statement(file_url=file_url, mapping=mapping)
    txns = parsed.get("transactions") or []
    if not txns:
        frappe.throw("No transactions parsed from the file — check the column mapping")
    res = match_statement(company=target, account=account, transactions=txns)
    matched_keys = {}
    for m in res.get("matched", []):
        s = m.get("statement") or {}
        matched_keys[(s.get("date"), flt(s.get("amount")))] = m.get("book") or {}
    lines, used = [], set()
    for i, t in enumerate(sorted(txns, key=lambda x: (x.get("date") or "", x.get("amount") or 0))):
        key = (t.get("date"), flt(t.get("amount")))
        book = matched_keys.get(key) if key not in used else None
        line = {"i": i, "date": str(t.get("date") or "")[:10], "amount": flt(t.get("amount")),
                "description": (t.get("description") or "")[:180], "status": "pending"}
        if book:
            used.add(key)
            line["status"] = "matched"
            line["voucher"] = book.get("voucher")
            line["voucher_type"] = book.get("doctype")
            line["by"] = "auto"
        lines.append(line)
    dates = [l["date"] for l in lines if l["date"]]
    doc = frappe.get_doc({"doctype": BSI, "company": target, "account": account,
                          "file_url": file_url, "file_name": file_name or file_url.rsplit("/", 1)[-1],
                          "from_date": min(dates) if dates else None,
                          "to_date": max(dates) if dates else None,
                          "lines": "[]"})
    doc.insert(ignore_permissions=True)
    _save(doc, lines)
    return {"name": doc.name, **_stats(doc)}


@frappe.whitelist()
def list_imports(company=None, account=None):
    assert_portal_access()
    target = _target(company)
    if not target:
        return []
    filters = {"company": target}
    if account:
        filters["account"] = account
    out = []
    for n in frappe.get_all(BSI, filters=filters, order_by="modified desc", limit=30, pluck="name"):
        out.append(_stats(frappe.get_doc(BSI, n)))
    return out


@frappe.whitelist()
def get_import(company=None, name=None):
    assert_portal_access()
    target = _target(company)
    doc, lines = _load(name, target)
    return {**_stats(doc), "lines": lines}


@frappe.whitelist()
def match_candidates(company=None, name=None, idx=None):
    """Book entries a pending line could be — uncleared, close in amount
    (±2% or ±2 MAD) and date (±45 days)."""
    assert_portal_access()
    target = _target(company)
    doc, lines = _load(name, target)
    l = lines[int(idx)]
    amt, date = abs(flt(l["amount"])), l["date"]
    tol = max(abs(amt) * 0.02, 2)
    p = {"c": target, "a": doc.account, "lo": amt - tol, "hi": amt + tol, "d": date}
    pe = frappe.db.sql(
        """SELECT name voucher, 'Payment Entry' voucher_type, posting_date date,
                  CASE WHEN paid_to=%(a)s THEN paid_amount ELSE -paid_amount END amount,
                  IFNULL(party,'') party, IFNULL(reference_no,'') ref
           FROM `tabPayment Entry`
           WHERE company=%(c)s AND docstatus=1 AND (paid_to=%(a)s OR paid_from=%(a)s)
             AND clearance_date IS NULL AND ABS(paid_amount) BETWEEN %(lo)s AND %(hi)s
             AND ABS(DATEDIFF(posting_date, %(d)s)) <= 45
           ORDER BY ABS(DATEDIFF(posting_date, %(d)s)) LIMIT 8""", p, as_dict=True)
    je = frappe.db.sql(
        """SELECT je.name voucher, 'Journal Entry' voucher_type, je.posting_date date,
                  ROUND(SUM(jea.debit - jea.credit), 2) amount, '' party,
                  IFNULL(je.cheque_no, IFNULL(je.user_remark,'')) ref
           FROM `tabJournal Entry` je JOIN `tabJournal Entry Account` jea
             ON jea.parent=je.name AND jea.account=%(a)s
           WHERE je.company=%(c)s AND je.docstatus=1 AND je.clearance_date IS NULL
             AND ABS(DATEDIFF(je.posting_date, %(d)s)) <= 45
           GROUP BY je.name HAVING ABS(ABS(SUM(jea.debit - jea.credit)) - %(amt)s) <= %(tol)s
           ORDER BY ABS(DATEDIFF(je.posting_date, %(d)s)) LIMIT 8""",
        {**p, "amt": amt, "tol": tol}, as_dict=True)
    rows = pe + je
    for r in rows:
        r["amount"] = flt(r["amount"])
        r["date"] = str(r["date"])[:10]
    return rows[:10]


@frappe.whitelist()
def line_action(company=None, name=None, idx=None, action=None,
                voucher=None, voucher_type=None, reason=None):
    """Act on one statement line: match / created / ignore / reset.
    match & created stamp the book entry's clearance date to the line date."""
    assert_can_write()
    target = _target(company)
    doc, lines = _load(name, target)
    idx = int(idx)
    if idx < 0 or idx >= len(lines):
        frappe.throw("Line not found")
    l = lines[idx]
    if action == "reset":
        # un-clear the previously linked entry if we cleared it
        if l.get("status") == "matched" and l.get("voucher") and l.get("voucher_type") in ("Payment Entry", "Journal Entry"):
            frappe.db.set_value(l["voucher_type"], l["voucher"], "clearance_date", None, update_modified=False)
        for k in ("voucher", "voucher_type", "reason", "by"):
            l.pop(k, None)
        l["status"] = "pending"
    elif action == "ignore":
        l["status"] = "ignored"
        l["reason"] = (reason or "")[:140]
        l["by"] = frappe.session.user
    elif action in ("match", "created"):
        if not (voucher and voucher_type):
            frappe.throw("voucher and voucher_type are required")
        if not frappe.db.exists(voucher_type, voucher):
            frappe.throw(f"{voucher_type} {voucher} not found")
        l["status"] = "matched" if action == "match" else "created"
        l["voucher"] = voucher
        l["voucher_type"] = voucher_type
        l["by"] = frappe.session.user
        # tick the book entry off against the statement at the line's date
        if voucher_type in ("Payment Entry", "Journal Entry") and l.get("date"):
            frappe.db.set_value(voucher_type, voucher, "clearance_date", l["date"], update_modified=False)
    else:
        frappe.throw(f"Unknown action: {action}")
    l["at"] = str(frappe.utils.now())[:16]
    _save(doc, lines)
    return {"line": l, **_stats(doc)}
