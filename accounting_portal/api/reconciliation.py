"""COD Cash Reconciliation — Pillar 1 (read engine).

The −2.85M debtor credit balance on Justyol Morocco is over-collection: COD cash
(via Cathadis) credits debtors faster than Sales Invoices debit them. Validated
on the live instance: 1,079 Payment Entries hold ~3.51M unallocated while only
265 invoices (~114k) are open. Reconciliation = allocate unallocated receipts to
open invoices (same party); the residual is collected-without-invoice and is
flagged. The allocation WRITE is posted through accounting_portal.api._actions
(idempotent + audited) — added as the next slice; this module is the read side.
"""
import json

import frappe
from frappe.utils import flt, nowdate

from accounting_portal.api import _actions, _paginate
from accounting_portal.api.permissions import assert_can_write, assert_portal_access, resolve_companies


def _target(company):
    companies = resolve_companies(company)
    if not companies:
        return None
    return company if (company and company in companies) else companies[0]


@frappe.whitelist()
def cod_summary(company=None):
    """The reconciliation headline: net debtor, unallocated receipts, open
    invoices, and how much is collected-without-invoice (the real gap)."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    net_debtor = flt(frappe.db.sql(
        "SELECT COALESCE(SUM(debit-credit),0) FROM `tabGL Entry` WHERE company=%s AND is_cancelled=0 AND party_type='Customer'",
        (target,))[0][0])
    ua = frappe.db.sql(
        "SELECT COALESCE(SUM(unallocated_amount),0), COUNT(*) FROM `tabPayment Entry` WHERE company=%s AND docstatus=1 AND payment_type='Receive' AND unallocated_amount>0",
        (target,))[0]
    oi = frappe.db.sql(
        "SELECT COALESCE(SUM(outstanding_amount),0), COUNT(*) FROM `tabSales Invoice` WHERE company=%s AND docstatus=1 AND outstanding_amount>0",
        (target,))[0]
    unalloc, outstanding = flt(ua[0]), flt(oi[0])
    return {
        "company": target,
        "net_debtor": net_debtor,
        "unallocated_amount": unalloc, "unallocated_count": ua[1],
        "outstanding_amount": outstanding, "outstanding_count": oi[1],
        # Best case the matching could clear; the rest is cash with no open invoice.
        "matchable": min(unalloc, outstanding),
        "collected_no_invoice": max(0.0, unalloc - outstanding),
    }


@frappe.whitelist()
def list_accounts(company=None):
    """Bank & Cash accounts with live balances — the Banking → Accounts tab.
    A negative Cash balance (overdraft) is a control flag worth seeing here."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return []
    return frappe.db.sql(
        """
        SELECT a.name AS account, a.account_type AS type, a.account_currency AS ccy,
               ROUND(SUM(gl.debit - gl.credit)) AS balance
        FROM `tabAccount` a
        JOIN `tabGL Entry` gl ON gl.account = a.name AND gl.is_cancelled = 0
        WHERE a.company = %s AND a.account_type IN ('Bank', 'Cash')
        GROUP BY a.name, a.account_type, a.account_currency
        ORDER BY ABS(SUM(gl.debit - gl.credit)) DESC
        """,
        (target,), as_dict=True)


@frappe.whitelist()
def unmatched_payments(company=None, limit=50):
    """COD receipts holding unallocated cash (the queue to reconcile), biggest first."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return []
    return frappe.db.sql(
        """
        SELECT name, party AS customer, posting_date AS date, mode_of_payment AS mode,
               paid_amount, unallocated_amount, reference_no
        FROM `tabPayment Entry`
        WHERE company=%s AND docstatus=1 AND payment_type='Receive' AND unallocated_amount>0
        ORDER BY unallocated_amount DESC LIMIT %s
        """,
        (target, min(int(limit or 50), 200)), as_dict=True)


@frappe.whitelist()
def open_invoices(company=None, limit=50):
    """Sales invoices still carrying an outstanding balance, biggest first."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return []
    return frappe.db.sql(
        """
        SELECT name, customer, posting_date AS date, grand_total, outstanding_amount, status
        FROM `tabSales Invoice`
        WHERE company=%s AND docstatus=1 AND outstanding_amount>0
        ORDER BY outstanding_amount DESC LIMIT %s
        """,
        (target, min(int(limit or 50), 200)), as_dict=True)


@frappe.whitelist()
def match_candidates(payment, limit=10):
    """Open invoices for a receipt's customer, ranked by closeness to the
    unallocated amount — the suggestions a reconcile action would draw from."""
    assert_portal_access()
    pe = frappe.db.get_value(
        "Payment Entry", payment, ["party", "unallocated_amount", "company"], as_dict=True)
    if not pe:
        frappe.throw("Payment not found")
    candidates = frappe.db.sql(
        """
        SELECT name, posting_date AS date, grand_total, outstanding_amount
        FROM `tabSales Invoice`
        WHERE company=%s AND customer=%s AND docstatus=1 AND outstanding_amount>0
        ORDER BY ABS(outstanding_amount - %s) ASC LIMIT %s
        """,
        (pe.company, pe.party, flt(pe.unallocated_amount), min(int(limit or 10), 50)), as_dict=True)
    return {
        "payment": payment, "customer": pe.party,
        "unallocated": flt(pe.unallocated_amount), "candidates": candidates,
    }


# ── Reconcile an unallocated COD receipt to the customer's open invoices ──
RECONCILE_ACTION = "Reconcile COD"


def _reconcile_receipt_poster(action):
    """Allocate a customer Receive Payment Entry to its open invoices via Payment
    Reconciliation — clears the unallocated amount off the debtor."""
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    pe = frappe.get_doc("Payment Entry", p["payment"])
    inv_names = set(p["invoices"])
    pr = frappe.get_doc({
        "doctype": "Payment Reconciliation", "company": pe.company,
        "party_type": "Customer", "party": pe.party,
        # Receive: the debtor (receivable) account is the paid_from leg.
        "receivable_payable_account": pe.paid_from,
    })
    pr.get_unreconciled_entries()
    invs = [x.as_dict() for x in pr.invoices if x.invoice_number in inv_names]
    pays = [x.as_dict() for x in pr.payments if x.reference_name == p["payment"]]
    if not invs or not pays:
        frappe.throw("Nothing left to reconcile (already applied?)")
    pr.allocate_entries({"invoices": invs, "payments": pays})
    pr.reconcile()
    return {"voucher_type": "Payment Entry", "voucher_no": p["payment"], "result": "reconciled"}


_actions.register_poster(RECONCILE_ACTION, _reconcile_receipt_poster)


@frappe.whitelist()
def reconcile_receipt(company=None, payment=None, invoices=None, dedupe_key=None):
    """Apply an unallocated COD receipt to one or more open invoices (gated)."""
    assert_can_write()
    target = _target(company)
    if not target or not payment:
        frappe.throw("Payment is required")
    if isinstance(invoices, str):
        invoices = json.loads(invoices)
    names = sorted({i for i in (invoices or []) if i})
    if not names:
        frappe.throw("Select at least one invoice")
    amt = flt(frappe.db.get_value("Payment Entry", payment, "unallocated_amount"))
    key = dedupe_key or f"recv:{payment}:{','.join(names)}"
    return _actions.execute(
        RECONCILE_ACTION, target, key, payload={"payment": payment, "invoices": names},
        amount=amt, notes=f"Reconcile {payment} → {len(names)} invoice(s)")


# ── Bank reconciliation (mark book entries cleared against the statement) ──
CLEAR_BANK_ACTION = "Clear Bank Entry"


@frappe.whitelist()
def fiscal_years(company=None):
    """ERPNext Fiscal Years (newest first) + which one covers today — drives the
    year filter on the banking screens."""
    assert_portal_access()
    from frappe.utils import nowdate
    rows = frappe.db.sql(
        """SELECT name, year_start_date start, year_end_date `end` FROM `tabFiscal Year`
           WHERE disabled=0 ORDER BY year_start_date DESC LIMIT 12""", as_dict=True)
    for r in rows:
        r["start"] = str(r["start"]); r["end"] = str(r["end"])
    today = nowdate()
    current = next((r["name"] for r in rows if r["start"] <= today <= r["end"]),
                   rows[0]["name"] if rows else None)
    return {"years": rows, "current": current}


@frappe.whitelist()
def bank_rec_accounts(company=None, from_date=None, to_date=None):
    """Bank/cash accounts with balance + unreconciled count. When a period (fiscal
    year) is given, each account also carries opening → in/out → closing, so the
    year's movement is isolated from the carried-forward balance."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return []
    period = bool(from_date or to_date)
    ck = f"ap_bankrec_acc:{target}:{from_date}:{to_date}"
    cached = frappe.cache().get_value(ck)
    if cached is not None:
        return cached
    accts = frappe.db.sql(
        """SELECT a.name, a.account_name, a.account_type, IFNULL(a.account_currency,'MAD') AS ccy,
                  ROUND(SUM(g.debit - g.credit)) AS book
           FROM `tabAccount` a JOIN `tabGL Entry` g ON g.account=a.name AND g.is_cancelled=0
           WHERE a.company=%(c)s AND a.is_group=0 AND a.account_type IN ('Bank','Cash')
           GROUP BY a.name HAVING COUNT(*) > 0
           ORDER BY ABS(SUM(g.debit - g.credit)) DESC LIMIT 40""", {"c": target}, as_dict=True)
    names = tuple(r.name for r in accts) or ("",)
    opening, pin, pout, pn = {}, {}, {}, {}
    if from_date:
        for r in frappe.db.sql(
                """SELECT account, SUM(debit-credit) v FROM `tabGL Entry`
                   WHERE company=%(c)s AND is_cancelled=0 AND account IN %(n)s AND posting_date < %(fd)s
                   GROUP BY account""", {"c": target, "n": names, "fd": from_date}, as_dict=True):
            opening[r.account] = flt(r.v)
    if period:
        conds = ["company=%(c)s", "is_cancelled=0", "account IN %(n)s"]
        p = {"c": target, "n": names}
        if from_date:
            conds.append("posting_date >= %(fd)s"); p["fd"] = from_date
        if to_date:
            conds.append("posting_date <= %(td)s"); p["td"] = to_date
        for r in frappe.db.sql(
                f"""SELECT account, SUM(debit) i, SUM(credit) o, COUNT(*) n FROM `tabGL Entry`
                    WHERE {' AND '.join(conds)} GROUP BY account""", p, as_dict=True):
            pin[r.account] = flt(r.i); pout[r.account] = flt(r.o); pn[r.account] = r.n
    for r in accts:
        pe = frappe.db.sql(
            """SELECT COUNT(*) n, ROUND(SUM(ABS(paid_amount))) v FROM `tabPayment Entry`
               WHERE company=%s AND docstatus=1 AND (paid_to=%s OR paid_from=%s) AND clearance_date IS NULL""",
            (target, r.name, r.name), as_dict=True)[0]
        je = frappe.db.sql(
            """SELECT COUNT(DISTINCT je.name) n,
                      ROUND(SUM(ABS(jea.debit_in_account_currency - jea.credit_in_account_currency))) v
               FROM `tabJournal Entry` je
               JOIN `tabJournal Entry Account` jea ON jea.parent=je.name
               WHERE je.company=%s AND je.docstatus=1 AND jea.account=%s AND je.clearance_date IS NULL""",
            (target, r.name), as_dict=True)[0]
        r["book"] = flt(r["book"])
        r["uncleared_n"] = (pe.n or 0) + (je.n or 0)
        r["uncleared_v"] = flt(pe.v) + flt(je.v)
        op, i, o = opening.get(r.name, 0.0), pin.get(r.name, 0.0), pout.get(r.name, 0.0)
        r["opening"] = round(op)
        r["period_in"] = round(i)
        r["period_out"] = round(o)
        r["period_n"] = pn.get(r.name, 0)
        r["closing"] = round(op + i - o) if period else flt(r["book"])
        r["period"] = period
    frappe.cache().set_value(ck, accts, expires_in_sec=180)
    return accts


@frappe.whitelist()
def bank_uncleared(company=None, account=None, from_date=None, to_date=None, search=None, limit=400):
    """Uncleared book entries (Payment Entries + Journal Entries) hitting one bank
    account — what hasn't been ticked off against the statement yet."""
    assert_portal_access()
    target = _target(company)
    if not target or not account:
        return []
    lim = min(int(limit or 400), 1000)
    p = {"c": target, "a": account, "lim": lim}
    pe_c = ["pe.company=%(c)s", "pe.docstatus=1", "(pe.paid_to=%(a)s OR pe.paid_from=%(a)s)", "pe.clearance_date IS NULL"]
    je_c = ["je.company=%(c)s", "je.docstatus=1", "jea.account=%(a)s", "je.clearance_date IS NULL"]
    if from_date:
        pe_c.append("pe.posting_date>=%(fd)s"); je_c.append("je.posting_date>=%(fd)s"); p["fd"] = from_date
    if to_date:
        pe_c.append("pe.posting_date<=%(td)s"); je_c.append("je.posting_date<=%(td)s"); p["td"] = to_date
    if search:
        pe_c.append("(pe.name LIKE %(s)s OR IFNULL(pe.party,'') LIKE %(s)s OR IFNULL(pe.reference_no,'') LIKE %(s)s)")
        je_c.append("(je.name LIKE %(s)s OR IFNULL(je.user_remark,'') LIKE %(s)s OR IFNULL(je.cheque_no,'') LIKE %(s)s)")
        p["s"] = f"%{search}%"
    pe = frappe.db.sql(
        f"""SELECT pe.name AS voucher, 'Payment Entry' AS doctype, pe.posting_date AS date,
                   CASE WHEN pe.paid_to=%(a)s THEN pe.paid_amount ELSE -pe.paid_amount END AS amount,
                   IFNULL(pe.party,'') AS party, IFNULL(pe.reference_no,'') AS ref
            FROM `tabPayment Entry` pe WHERE {' AND '.join(pe_c)}
            ORDER BY pe.posting_date DESC LIMIT %(lim)s""", p, as_dict=True)
    je = frappe.db.sql(
        f"""SELECT je.name AS voucher, 'Journal Entry' AS doctype, je.posting_date AS date,
                   ROUND(SUM(jea.debit - jea.credit), 2) AS amount, '' AS party,
                   IFNULL(je.cheque_no, IFNULL(je.user_remark,'')) AS ref
            FROM `tabJournal Entry` je JOIN `tabJournal Entry Account` jea
              ON jea.parent=je.name AND jea.account=%(a)s
            WHERE {' AND '.join(je_c)} GROUP BY je.name
            ORDER BY je.posting_date DESC LIMIT %(lim)s""", p, as_dict=True)
    rows = pe + je
    for r in rows:
        r["amount"] = flt(r["amount"]); r["date"] = str(r.get("date") or "")
    rows.sort(key=lambda x: x["date"], reverse=True)
    return rows[:lim]


def _clear_bank_poster(action):
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    date = p.get("date") or nowdate()
    for e in p["entries"]:
        frappe.db.set_value(e["doctype"], e["name"], "clearance_date", date)
    frappe.db.commit()
    first = p["entries"][0] if p["entries"] else {}
    return {"voucher_type": first.get("doctype"), "voucher_no": first.get("name"),
            "result": {"cleared": len(p["entries"]), "date": date}}


def _clear_bank_reverter(action):
    """Undo a bank clearing: remove the clearance_date — but only where it still
    holds the date this action set, so a later re-clear (different statement) isn't
    wiped."""
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    set_date = p.get("date")
    done = 0
    for e in (p.get("entries") or []):
        cur = frappe.db.get_value(e["doctype"], e["name"], "clearance_date")
        if cur and (not set_date or str(cur) == str(set_date)):
            frappe.db.set_value(e["doctype"], e["name"], "clearance_date", None)
            done += 1
    frappe.db.commit()
    return {"uncleared": done}


_actions.register_poster(CLEAR_BANK_ACTION, _clear_bank_poster)
_actions.register_reverter(CLEAR_BANK_ACTION, _clear_bank_reverter)


@frappe.whitelist()
def mark_bank_cleared(company=None, entries=None, clearance_date=None):
    """Stamp the statement clearance date on the selected book entries (no GL
    impact — a reconciliation marker). Audited; one batch."""
    assert_can_write()
    target = _target(company)
    ents = entries if isinstance(entries, list) else json.loads(entries or "[]")
    ents = [e for e in ents if e.get("doctype") in ("Payment Entry", "Journal Entry") and e.get("name")]
    if not target or not ents:
        frappe.throw("No entries selected")
    for e in ents:
        if frappe.db.get_value(e["doctype"], e["name"], "company") != target:
            frappe.throw(f"{e['name']} belongs to another company")
    date = clearance_date or nowdate()
    key = "clrbank:" + frappe.generate_hash("".join(sorted(e["name"] for e in ents)) + date, 16)
    res = _actions.execute(CLEAR_BANK_ACTION, target, key,
                           payload={"entries": ents, "date": date}, amount=0,
                           notes=f"Reconciled {len(ents)} bank entr(ies) on {date}")
    try:
        frappe.cache().delete_keys("ap_bankrec_acc")
    except Exception:
        pass
    return res


@frappe.whitelist()
def get_bank_account(company=None, account=None, from_date=None, to_date=None,
                     start=0, page_size=60, limit=None):
    """One bank/cash account — header, balance, period in/out, uncleared, and the
    recent ledger with a running balance."""
    assert_portal_access()
    target = _target(company)
    a = frappe.db.get_value("Account", account, ["account_name", "account_type", "account_currency", "company"], as_dict=True)
    if not a or a.company != target:
        frappe.throw("Account not found")
    balance = flt(frappe.db.sql(
        "SELECT SUM(debit-credit) FROM `tabGL Entry` WHERE account=%s AND is_cancelled=0", account)[0][0])
    # Opening (carried forward) = balance before the period start; the period's own
    # in/out; closing = opening + in − out. Falls back to last 30 days if no period.
    opening = flt(frappe.db.sql(
        "SELECT SUM(debit-credit) FROM `tabGL Entry` WHERE account=%s AND is_cancelled=0 AND posting_date < %s",
        (account, from_date))[0][0]) if from_date else None
    fconds = ["account=%(acc)s", "is_cancelled=0"]
    fp = {"acc": account}
    if from_date:
        fconds.append("posting_date >= %(fd)s"); fp["fd"] = from_date
    if to_date:
        fconds.append("posting_date <= %(td)s"); fp["td"] = to_date
    if not (from_date or to_date):
        fconds.append("posting_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)")
    fl = frappe.db.sql(
        f"""SELECT ROUND(SUM(debit)) inflow, ROUND(SUM(credit)) outflow, COUNT(*) n
            FROM `tabGL Entry` WHERE {' AND '.join(fconds)}""", fp, as_dict=True)[0]
    closing = round(flt(opening) + flt(fl.inflow) - flt(fl.outflow)) if from_date else balance
    pe = frappe.db.sql(
        """SELECT COUNT(*) n, ROUND(SUM(ABS(paid_amount))) v FROM `tabPayment Entry`
           WHERE company=%s AND docstatus=1 AND (paid_to=%s OR paid_from=%s) AND clearance_date IS NULL""",
        (target, account, account), as_dict=True)[0]
    je = frappe.db.sql(
        """SELECT COUNT(DISTINCT je.name) n,
                  ROUND(SUM(ABS(jea.debit_in_account_currency - jea.credit_in_account_currency))) v
           FROM `tabJournal Entry` je JOIN `tabJournal Entry Account` jea ON jea.parent=je.name
           WHERE je.company=%s AND je.docstatus=1 AND jea.account=%s AND je.clearance_date IS NULL""",
        (target, account), as_dict=True)[0]
    # Server-paginated ledger (one page at a time) + optional date window.
    start = max(0, int(start or 0))
    page_size = min(max(1, int(page_size or limit or 60)), 200)
    lconds = ["account=%(acc)s", "is_cancelled=0"]
    lp = {"acc": account}
    if from_date:
        lconds.append("posting_date >= %(fd)s"); lp["fd"] = from_date
    if to_date:
        lconds.append("posting_date <= %(td)s"); lp["td"] = to_date
    lwhere = " AND ".join(lconds)
    ledger_total = frappe.db.sql(f"SELECT COUNT(*) FROM `tabGL Entry` WHERE {lwhere}", lp)[0][0]
    ledger = frappe.db.sql(
        f"""SELECT posting_date AS date, voucher_type AS type, voucher_no AS voucher,
                   IFNULL(against,'') AS against, ROUND(debit,2) AS debit, ROUND(credit,2) AS credit, creation
            FROM `tabGL Entry` WHERE {lwhere}
            ORDER BY posting_date DESC, creation DESC LIMIT %(ps)s OFFSET %(st)s""",
        {**lp, "ps": page_size, "st": start}, as_dict=True)
    if ledger:
        # The first (newest) row's running balance = the account's true balance minus
        # the net of every entry NEWER than it (regardless of the date filter), so the
        # Balance column is the real account balance at each row, on any page.
        f0 = ledger[0]
        newer = flt(frappe.db.sql(
            """SELECT SUM(debit-credit) FROM `tabGL Entry`
               WHERE account=%s AND is_cancelled=0
                 AND (posting_date > %s OR (posting_date = %s AND creation > %s))""",
            (account, f0["date"], f0["date"], f0["creation"]))[0][0])
        running = balance - newer
        for e in ledger:
            e["debit"] = flt(e["debit"]); e["credit"] = flt(e["credit"])
            e["balance"] = round(running, 2)
            e["date"] = str(e.get("date") or "")
            e.pop("creation", None)
            running -= (e["debit"] - e["credit"])
    return {
        "account": account, "name": a.account_name, "type": a.account_type,
        "currency": a.account_currency or "MAD", "balance": balance,
        "inflow": flt(fl.inflow), "outflow": flt(fl.outflow), "period_n": fl.n or 0,
        "opening": (round(flt(opening)) if opening is not None else None), "closing": closing,
        "uncleared_n": (pe.n or 0) + (je.n or 0), "uncleared_v": flt(pe.v) + flt(je.v),
        "ledger": ledger, "ledger_total": ledger_total, "start": start, "page_size": page_size,
    }


@frappe.whitelist()
def bank_transactions(company=None, from_date=None, to_date=None, search=None,
                      start=0, page_size=50, sort_field="date", sort_dir="desc"):
    """Live bank & cash movements (GL entries on Bank/Cash accounts) — the
    statement-style transactions feed, server-paginated."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {"rows": [], "total": 0}
    conds = ["g.company=%(c)s", "g.is_cancelled=0", "a.account_type IN ('Bank','Cash')"]
    p = {"c": target}
    if from_date:
        conds.append("g.posting_date>=%(fd)s"); p["fd"] = from_date
    if to_date:
        conds.append("g.posting_date<=%(td)s"); p["td"] = to_date
    if search:
        conds.append("(g.voucher_no LIKE %(s)s OR IFNULL(g.against,'') LIKE %(s)s OR a.account_name LIKE %(s)s OR IFNULL(g.remarks,'') LIKE %(s)s)")
        p["s"] = f"%{search}%"
    sort = {"date": "g.posting_date", "amount": "(g.debit-g.credit)", "voucher": "g.voucher_no", "account": "a.account_name"}
    col = sort.get(sort_field, "g.posting_date")
    d = "ASC" if str(sort_dir).lower() == "asc" else "DESC"
    rows, total, st_, ps = _paginate.page_query(
        "`tabGL Entry` g JOIN `tabAccount` a ON a.name=g.account", " AND ".join(conds), p,
        "g.posting_date AS date, g.voucher_type AS type, g.voucher_no AS voucher, "
        "a.account_name AS account, IFNULL(g.against,'') AS against, ROUND(g.debit - g.credit, 2) AS amount",
        f"{col} {d}, g.creation {d}", start, page_size)
    for r in rows:
        r["amount"] = flt(r["amount"]); r["date"] = str(r.get("date") or "")
    return {"rows": rows, "total": total, "start": st_, "page_size": ps}
