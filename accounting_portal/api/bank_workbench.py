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
    # include_cleared: entries reconciled in earlier sessions must match, not
    # resurface as "missing in books"
    res = match_statement(company=target, account=account, transactions=txns, include_cleared=1)
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
def in_account_options(company=None):
    """Postable accounts for recording a bank line's other side. Money-in
    (Dr bank / Cr this) → carrier clearing, other banks/cash, income, receivables;
    also used by bulk register where the other side may be an Expense (bank
    charges). Excludes group accounts."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return []
    return frappe.db.sql(
        """SELECT name, account_name nm, account_number num, account_type typ, root_type rt
           FROM `tabAccount`
           WHERE company=%s AND is_group=0 AND disabled=0
             AND root_type IN ('Asset', 'Income', 'Liability', 'Expense')
           ORDER BY name LIMIT 2000""", (target,), as_dict=True)


@frappe.whitelist()
def bulk_register(company=None, name=None, idxs=None, account=None):
    """Register several same-direction pending lines as ONE combined journal —
    Dr/Cr the picked account against the bank for the total — and link every
    line to it. Built for batches of identical items (bank charges, per-transfer
    commissions). Gated on the total; on Proposed, lines stay pending."""
    assert_can_write()
    target = _target(company)
    doc, lines = _load(name, target)
    idxs = json.loads(idxs) if isinstance(idxs, str) else (idxs or [])
    idxs = [int(i) for i in idxs]
    sel = [l for l in lines if l["i"] in idxs and l.get("status") == "pending"]
    if not sel:
        frappe.throw("No pending lines selected")
    if not account or frappe.db.get_value("Account", account, "company") != target:
        frappe.throw("Pick a valid account")
    signs = {1 if flt(l["amount"]) >= 0 else -1 for l in sel}
    if len(signs) > 1:
        frappe.throw("Select lines of one direction only (all money-in, or all money-out)")
    total = round(sum(abs(flt(l["amount"])) for l in sel), 2)
    is_in = flt(sel[0]["amount"]) >= 0
    # money-in: Dr bank / Cr account ; money-out: Dr account / Cr bank
    if is_in:
        je_lines = [{"account": doc.account, "debit": total, "credit": 0},
                    {"account": account, "debit": 0, "credit": total}]
    else:
        je_lines = [{"account": account, "debit": total, "credit": 0},
                    {"account": doc.account, "debit": 0, "credit": total}]
    from accounting_portal.api.accountant import create_journal_entry
    res = create_journal_entry(
        company=target, posting_date=max(l["date"] for l in sel if l.get("date")) or nowdate(),
        lines=je_lines,
        remark=f"Bank batch · {len(sel)} × {(sel[0].get('description') or '')[:60]} · {doc.name}",
        dedupe_key="bsibulk:" + frappe.generate_hash(f"{doc.name}:{sorted(idxs)}:{account}", 12))
    if res.get("status") == "Proposed":
        return {"proposed": True, "n": len(sel), "total": total, **_stats(doc)}
    vno = res.get("voucher_no")
    if vno:
        frappe.db.set_value("Journal Entry", vno, "clearance_date",
                            max(l["date"] for l in sel if l.get("date")), update_modified=False)
        now = str(frappe.utils.now())[:16]
        for l in lines:
            if l["i"] in idxs and l.get("status") == "pending":
                l.update({"status": "created", "voucher": vno, "voucher_type": "Journal Entry",
                          "by": frappe.session.user, "at": now})
        _save(doc, lines)
    return {"voucher": vno, "n": len(sel), "total": total, **_stats(doc), "lines": lines}


@frappe.whitelist()
def rematch_import(company=None, name=None):
    """Re-run auto-match on the PENDING lines of an existing import — now against
    ALL book entries (cleared included). Rescues imports created before the
    include_cleared fix, and picks up entries booked after the upload."""
    assert_can_write()
    target = _target(company)
    doc, lines = _load(name, target)
    pending = [l for l in lines if l.get("status") == "pending"]
    if not pending:
        return {"newly_matched": 0, **_stats(doc)}
    from accounting_portal.api.bank_import import match_statement
    res = match_statement(company=target, account=doc.account,
                          transactions=[{"date": l["date"], "amount": l["amount"],
                                         "description": l.get("description")} for l in pending],
                          include_cleared=1)
    # vouchers already pinned to other lines must not be consumed twice
    taken = {l.get("voucher") for l in lines if l.get("voucher")}
    taken |= {v.get("voucher") for l in lines for v in (l.get("vouchers") or []) if isinstance(v, dict) and v.get("voucher")}
    matched_keys = {}
    for m in res.get("matched", []):
        book = m.get("book") or {}
        if book.get("voucher") in taken:
            continue
        s = m.get("statement") or {}
        matched_keys.setdefault((str(s.get("date"))[:10], flt(s.get("amount"))), []).append(book)
    newly = 0
    for l in lines:
        if l.get("status") != "pending":
            continue
        pool = matched_keys.get((l["date"], flt(l["amount"])))
        if pool:
            book = pool.pop(0)
            l["status"] = "matched"
            l["voucher"] = book.get("voucher")
            l["voucher_type"] = book.get("doctype")
            l["by"] = "auto"
            newly += 1
    _save(doc, lines)
    return {"newly_matched": newly, **_stats(doc), "lines": lines}


@frappe.whitelist()
def match_candidates(company=None, name=None, idx=None, search=None):
    """Book entries a pending line could be.
    Default: uncleared/close (±2% or ±2 MAD, ±45 days) — the auto suggestions.
    With `search`: any submitted entry on this account whose voucher/party/ref
    matches the text (amount tolerance dropped) — for splits where one bank line
    covers several invoices/payments, the accountant searches by supplier or
    description and links them together."""
    assert_portal_access()
    target = _target(company)
    doc, lines = _load(name, target)
    l = lines[int(idx)]
    amt, date = abs(flt(l["amount"])), l["date"]
    if search:
        s = f"%{search}%"
        p = {"c": target, "a": doc.account, "s": s}
        pe = frappe.db.sql(
            """SELECT name voucher, 'Payment Entry' voucher_type, posting_date date,
                      CASE WHEN paid_to=%(a)s THEN paid_amount ELSE -paid_amount END amount,
                      IFNULL(party,'') party, IFNULL(reference_no,'') ref,
                      (clearance_date IS NOT NULL) cleared
               FROM `tabPayment Entry`
               WHERE company=%(c)s AND docstatus=1 AND (paid_to=%(a)s OR paid_from=%(a)s)
                 AND (name LIKE %(s)s OR IFNULL(party,'') LIKE %(s)s
                      OR IFNULL(party_name,'') LIKE %(s)s OR IFNULL(reference_no,'') LIKE %(s)s
                      OR IFNULL(remarks,'') LIKE %(s)s)
               ORDER BY (clearance_date IS NOT NULL), posting_date DESC LIMIT 25""", p, as_dict=True)
        je = frappe.db.sql(
            """SELECT je.name voucher, 'Journal Entry' voucher_type, je.posting_date date,
                      ROUND(SUM(jea.debit - jea.credit), 2) amount, MAX(IFNULL(jea.party,'')) party,
                      IFNULL(je.cheque_no, IFNULL(je.user_remark,'')) ref,
                      (je.clearance_date IS NOT NULL) cleared
               FROM `tabJournal Entry` je JOIN `tabJournal Entry Account` jea
                 ON jea.parent=je.name AND jea.account=%(a)s
               WHERE je.company=%(c)s AND je.docstatus=1
                 AND (je.name LIKE %(s)s OR IFNULL(je.user_remark,'') LIKE %(s)s
                      OR IFNULL(je.cheque_no,'') LIKE %(s)s OR IFNULL(jea.party,'') LIKE %(s)s)
               GROUP BY je.name ORDER BY (je.clearance_date IS NOT NULL), je.posting_date DESC LIMIT 25""",
            p, as_dict=True)
    else:
        tol = max(abs(amt) * 0.02, 2)
        p = {"c": target, "a": doc.account, "lo": amt - tol, "hi": amt + tol, "d": date, "amt": amt, "tol": tol}
        pe = frappe.db.sql(
            """SELECT name voucher, 'Payment Entry' voucher_type, posting_date date,
                      CASE WHEN paid_to=%(a)s THEN paid_amount ELSE -paid_amount END amount,
                      IFNULL(party,'') party, IFNULL(reference_no,'') ref,
                      (clearance_date IS NOT NULL) cleared
               FROM `tabPayment Entry`
               WHERE company=%(c)s AND docstatus=1 AND (paid_to=%(a)s OR paid_from=%(a)s)
                 AND ABS(paid_amount) BETWEEN %(lo)s AND %(hi)s
                 AND ABS(DATEDIFF(posting_date, %(d)s)) <= 45
               ORDER BY (clearance_date IS NOT NULL), ABS(DATEDIFF(posting_date, %(d)s)) LIMIT 8""", p, as_dict=True)
        je = frappe.db.sql(
            """SELECT je.name voucher, 'Journal Entry' voucher_type, je.posting_date date,
                      ROUND(SUM(jea.debit - jea.credit), 2) amount, '' party,
                      IFNULL(je.cheque_no, IFNULL(je.user_remark,'')) ref,
                      (je.clearance_date IS NOT NULL) cleared
               FROM `tabJournal Entry` je JOIN `tabJournal Entry Account` jea
                 ON jea.parent=je.name AND jea.account=%(a)s
               WHERE je.company=%(c)s AND je.docstatus=1
                 AND ABS(DATEDIFF(je.posting_date, %(d)s)) <= 45
               GROUP BY je.name HAVING ABS(ABS(SUM(jea.debit - jea.credit)) - %(amt)s) <= %(tol)s
               ORDER BY (je.clearance_date IS NOT NULL), ABS(DATEDIFF(je.posting_date, %(d)s)) LIMIT 8""",
            p, as_dict=True)
    # exclude vouchers already pinned to another line of THIS import
    # `vouchers` on a split line is a list of {voucher, voucher_type} dicts —
    # collect the voucher NAMES, not the dicts (a dict is unhashable in a set).
    taken = {x.get("voucher") for x in lines if x.get("voucher")}
    taken |= {v.get("voucher") for x in lines for v in (x.get("vouchers") or []) if isinstance(v, dict) and v.get("voucher")}
    rows = [r for r in pe + je if r["voucher"] not in taken]
    for r in rows:
        r["amount"] = flt(r["amount"])
        r["date"] = str(r["date"])[:10]
        r["cleared"] = int(r.get("cleared") or 0)
    return {"rows": rows[:30], "line_amount": flt(l["amount"])}


def _clear(vt, vn, date):
    if vt in ("Payment Entry", "Journal Entry") and date:
        frappe.db.set_value(vt, vn, "clearance_date", date, update_modified=False)


def _unclear_line(l):
    """Undo clearance for whatever a line was linked to (single or split)."""
    for v in (l.get("vouchers") or ([{"voucher": l["voucher"], "voucher_type": l.get("voucher_type")}] if l.get("voucher") else [])):
        vt, vn = v.get("voucher_type"), v.get("voucher")
        if vt in ("Payment Entry", "Journal Entry") and vn:
            frappe.db.set_value(vt, vn, "clearance_date", None, update_modified=False)


@frappe.whitelist()
def line_action(company=None, name=None, idx=None, action=None,
                voucher=None, voucher_type=None, vouchers=None, reason=None):
    """Act on one statement line: match / match_multi / created / ignore / reset.
    match & created stamp the book entry's clearance date to the line date;
    match_multi links SEVERAL entries to one line (a bank line paying several
    invoices) and clears them all."""
    assert_can_write()
    target = _target(company)
    doc, lines = _load(name, target)
    idx = int(idx)
    if idx < 0 or idx >= len(lines):
        frappe.throw("Line not found")
    l = lines[idx]
    if action == "reset":
        _unclear_line(l)
        for k in ("voucher", "voucher_type", "vouchers", "reason", "by", "split"):
            l.pop(k, None)
        l["status"] = "pending"
    elif action == "ignore":
        l["status"] = "ignored"
        l["reason"] = (reason or "")[:140]
        l["by"] = frappe.session.user
    elif action == "match_multi":
        vs = json.loads(vouchers) if isinstance(vouchers, str) else (vouchers or [])
        clean = []
        for v in vs:
            vt, vn = v.get("voucher_type"), v.get("voucher")
            if not (vt and vn) or not frappe.db.exists(vt, vn):
                frappe.throw(f"{vt} {vn} not found")
            clean.append({"voucher": vn, "voucher_type": vt})
        if not clean:
            frappe.throw("Select at least one entry")
        l["status"] = "matched"
        l["vouchers"] = clean
        l["voucher"] = clean[0]["voucher"]           # for compact display
        l["voucher_type"] = clean[0]["voucher_type"]
        l["split"] = len(clean)
        l["by"] = frappe.session.user
        for v in clean:
            _clear(v["voucher_type"], v["voucher"], l.get("date"))
    elif action in ("match", "created"):
        if not (voucher and voucher_type):
            frappe.throw("voucher and voucher_type are required")
        if not frappe.db.exists(voucher_type, voucher):
            frappe.throw(f"{voucher_type} {voucher} not found")
        l["status"] = "matched" if action == "match" else "created"
        l["voucher"] = voucher
        l["voucher_type"] = voucher_type
        l.pop("vouchers", None); l.pop("split", None)
        l["by"] = frappe.session.user
        _clear(voucher_type, voucher, l.get("date"))
    else:
        frappe.throw(f"Unknown action: {action}")
    l["at"] = str(frappe.utils.now())[:16]
    _save(doc, lines)
    return {"line": l, **_stats(doc)}
