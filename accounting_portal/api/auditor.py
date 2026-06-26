"""AI Auditor — the continuous controls engine.

Runs a set of anomaly-detection rules against the live books and returns
findings: each carries a severity, a plain-language explanation, the amount and
account it came from, a recommended fix, and a drill target (where in the portal
the team goes to act). The rules encode the pathologies found in Justyol's books
(stock/COGS break, unmatched COD, GRNI gap, correction pile, negative cash…).

This is the rule layer. Narration/conversational answers via the Claude API sit
on top of these findings (server-side key, added when wired); the findings
themselves are fully real and update every time the controls run.
"""
import json

import frappe
from frappe.utils import add_days, flt, nowdate

from accounting_portal.api.permissions import (
    assert_can_write, assert_portal_access, resolve_companies,
)

SEV_WEIGHT = {"high": 3, "medium": 2, "low": 1}


def _target(company):
    companies = resolve_companies(company)
    if not companies:
        return None
    return company if (company and company in companies) else companies[0]


def _metrics(company):
    """Key live balances the rules reason over (2 bounded GL aggregates)."""
    by_type = {r.account_type: flt(r.debit_net) for r in frappe.db.sql(
        """SELECT a.account_type, ROUND(SUM(gle.debit - gle.credit)) AS debit_net
           FROM `tabGL Entry` gle JOIN `tabAccount` a ON a.name = gle.account
           WHERE gle.company=%s AND gle.is_cancelled=0
             AND a.account_type IN ('Receivable','Payable','Cash','Bank','Stock')
           GROUP BY a.account_type""", (company,), as_dict=True)}
    named = {r.name: flt(r.bal) for r in frappe.db.sql(
        """SELECT a.name, ROUND(SUM(gle.debit - gle.credit)) AS bal
           FROM `tabGL Entry` gle JOIN `tabAccount` a ON a.name = gle.account
           WHERE gle.company=%s AND gle.is_cancelled=0
             AND (a.account_name LIKE '%%Correction Need%%'
               OR a.account_name LIKE '%%Received But Not Billed%%'
               OR a.account_name LIKE '%%Stock Adjustment%%')
           GROUP BY a.name ORDER BY ABS(SUM(gle.debit - gle.credit)) DESC""",
        (company,), as_dict=True)}
    return by_type, named


def _pick(named, needle):
    for name, bal in named.items():
        if needle.lower() in name.lower():
            return name, bal
    return None, 0.0


@frappe.whitelist()
def run_controls(company=None):
    """Run the controls and return findings + a summary, ranked by severity."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {"findings": [], "summary": {}}
    ck = f"ap_auditor:{target}"
    hit = frappe.cache().get_value(ck)
    if hit is not None:
        return hit
    by_type, named = _metrics(target)
    f = []

    stock = by_type.get("Stock", 0)
    adj_acct, adj_bal = _pick(named, "Stock Adjustment")
    if abs(stock) > 50_000_000:
        f.append({
            "id": "stock_cogs", "severity": "high", "metric": "Stock in hand",
            "title": "Perpetual inventory isn't relieving to COGS",
            "detail": f"Stock-in-hand carries {stock:,.0f} MAD while “{adj_acct or 'Stock Adjustment'}” absorbs {adj_bal:,.0f}. "
                      "Deliveries aren't posting cost of goods sold against stock, so margin is unmeasurable and the balance sheet is overstated.",
            "amount": stock, "account": adj_acct,
            "recommendation": "Reconcile stock valuation and post COGS on delivery; reclassify the Stock-Adjustment pile via a correcting entry.",
            "drill": {"module": "items", "sub": "", "label": "Inventory health"},
        })

    debtors = by_type.get("Receivable", 0)
    if debtors < -100_000:
        f.append({
            "id": "unmatched_cod", "severity": "high", "metric": "Debtors (net)",
            "title": "Collected COD not applied to invoices",
            "detail": f"Debtors show a net credit of {debtors:,.0f} MAD — cash collected by carriers sits unallocated instead of clearing customer invoices. "
                      "The receivable sub-ledger can't be trusted until these are matched.",
            "amount": debtors, "account": "Debtors",
            "recommendation": "Match carrier remittances to invoices in Banking → COD reconcile; allocate advances on Debtors.",
            "drill": {"module": "banking", "sub": "", "label": "COD reconcile"},
        })

    grni_acct, grni_bal = _pick(named, "Received But Not Billed")
    if abs(grni_bal) > 250_000:
        f.append({
            "id": "grni_gap", "severity": "medium", "metric": "GRNI",
            "title": "Goods received but not billed",
            "detail": f"“{grni_acct}” stands at {grni_bal:,.0f} MAD — the three-way match (PO ↔ receipt ↔ bill) is incomplete, so liabilities and stock cost are misstated.",
            "amount": grni_bal, "account": grni_acct,
            "recommendation": "Clear the GRNI by matching supplier bills to receipts; investigate aged items.",
            "drill": {"module": "purchases", "sub": "", "label": "Purchases"},
        })

    corr_acct, corr_bal = _pick(named, "Correction Need")
    if abs(corr_bal) > 100_000:
        f.append({
            "id": "correction_pile", "severity": "high", "metric": "Correction Need",
            "title": "“Correction Need” pile is material",
            "detail": f"“{corr_acct}” holds {corr_bal:,.0f} MAD of entries parked for correction. A balance this size distorts the P&L and must be triaged and reclassified.",
            "amount": corr_bal, "account": corr_acct,
            "recommendation": "Triage the account line by line; post reclassifying journals to the correct accounts.",
            "drill": {"module": "accountant", "sub": "", "label": "Journals"},
        })

    cash = by_type.get("Cash", 0)
    if cash < 0:
        f.append({
            "id": "negative_cash", "severity": "high", "metric": "Cash on hand",
            "title": "Cash account is overdrawn",
            "detail": f"The cash account shows {cash:,.0f} MAD — a negative physical-cash balance is impossible and points to unrecorded receipts or misposted payments.",
            "amount": cash, "account": "Cash",
            "recommendation": "Reconcile cash movements; find the missing receipts or correct the mispostings.",
            "drill": {"module": "banking", "sub": "", "label": "Banking"},
        })

    payable = by_type.get("Payable", 0)
    if payable < -1_000_000:
        f.append({
            "id": "payables_load", "severity": "medium", "metric": "Creditors",
            "title": "Large supplier payable outstanding",
            "detail": f"Creditors stand at {payable:,.0f} MAD. Review the aged 90+ concentration against available cash to avoid a liquidity squeeze.",
            "amount": payable, "account": "Creditors",
            "recommendation": "Review AP aging; schedule payments against the COD cash pipeline.",
            "drill": {"module": "reports", "sub": "statements", "label": "AP aging"},
        })

    bank = by_type.get("Bank", 0)
    if bank < -100_000:
        f.append({
            "id": "negative_bank", "severity": "medium", "metric": "Bank balance",
            "title": "Bank account is overdrawn on the books",
            "detail": f"Bank accounts net to {bank:,.0f} MAD. A negative book balance usually means uncleared/unreconciled entries or a missed deposit.",
            "amount": bank, "account": "Bank",
            "recommendation": "Run bank reconciliation; clear uncleared entries and find the missing deposits.",
            "drill": {"module": "banking", "sub": "bankrec", "label": "Bank reconciliation"},
        })

    # Revenue recognition gap — delivered but not invoiced.
    dn = frappe.db.sql(
        """SELECT COUNT(*) n, ROUND(SUM(grand_total)) v FROM `tabDelivery Note`
           WHERE company=%s AND docstatus=1 AND IFNULL(per_billed,0) < 100 AND grand_total > 0""",
        (target,), as_dict=True)[0]
    if (dn.n or 0) > 0 and abs(flt(dn.v)) > 100_000:
        f.append({
            "id": "rev_recognition", "severity": "high", "metric": "Unbilled deliveries",
            "title": "Delivered orders not yet invoiced",
            "detail": f"{dn.n:,} delivered Delivery Notes worth {flt(dn.v):,.0f} MAD have no Sales Invoice — revenue is delivered but unrecognised, understating income and receivables.",
            "amount": flt(dn.v), "account": "Revenue",
            "recommendation": "Bill the delivered notes from Reports → Missing docs / Sales → To-bill.",
            "drill": {"module": "sales", "sub": "tobill", "label": "To-bill queue"},
        })

    # Document compliance — submitted bills with no source file attached.
    miss = flt(frappe.db.sql(
        """SELECT COUNT(*) FROM `tabPurchase Invoice` pi
           WHERE pi.company=%s AND pi.docstatus=1
             AND NOT EXISTS (SELECT 1 FROM `tabFile` fl
                 WHERE fl.attached_to_doctype='Purchase Invoice' AND fl.attached_to_name=pi.name)""",
        (target,))[0][0])
    if miss > 50:
        f.append({
            "id": "missing_docs", "severity": "medium", "metric": "Missing documents",
            "title": "Supplier bills without a source document",
            "detail": f"{int(miss):,} submitted bills have no invoice/receipt file attached — an audit-trail and VAT-deduction risk.",
            "amount": miss, "account": None,
            "recommendation": "Upload the missing source files from Reports → Missing docs; assign by supplier.",
            "drill": {"module": "reports", "sub": "missingdocs", "label": "Missing docs"},
        })

    # Aged payables 90+.
    ap90 = flt(frappe.db.sql(
        """SELECT ROUND(SUM(outstanding_amount)) FROM `tabPurchase Invoice`
           WHERE company=%s AND docstatus=1 AND outstanding_amount > 0
             AND DATEDIFF(CURDATE(), IFNULL(due_date, posting_date)) > 90""", (target,))[0][0])
    if ap90 > 500_000:
        f.append({
            "id": "ap_aged_90", "severity": "medium", "metric": "Payables 90+",
            "title": "Supplier payables aged over 90 days",
            "detail": f"{ap90:,.0f} MAD of supplier bills are more than 90 days overdue — supplier-relationship and possible penalty risk.",
            "amount": ap90, "account": "Creditors",
            "recommendation": "Review the 90+ AP aging and schedule payments against the COD cash pipeline.",
            "drill": {"module": "purchases", "sub": "topay", "label": "To pay" },
        })

    # Aged receivables 90+ (positive outstanding).
    ar90 = flt(frappe.db.sql(
        """SELECT ROUND(SUM(outstanding_amount)) FROM `tabSales Invoice`
           WHERE company=%s AND docstatus=1 AND outstanding_amount > 0
             AND DATEDIFF(CURDATE(), IFNULL(due_date, posting_date)) > 90""", (target,))[0][0])
    if ar90 > 500_000:
        f.append({
            "id": "ar_aged_90", "severity": "medium", "metric": "Receivables 90+",
            "title": "Customer receivables aged over 90 days",
            "detail": f"{ar90:,.0f} MAD of customer invoices are more than 90 days outstanding — collection risk; provision may be required.",
            "amount": ar90, "account": "Debtors",
            "recommendation": "Chase or provide for the aged 90+ receivables; reconcile against COD collections.",
            "drill": {"module": "reports", "sub": "arap", "label": "AR/AP" },
        })

    # Draft pile-up — unsubmitted documents sitting in the books.
    drafts = 0
    for dt in ("Journal Entry", "Purchase Invoice", "Sales Invoice", "Payment Entry"):
        drafts += frappe.db.count(dt, {"company": target, "docstatus": 0})
    if drafts > 20:
        f.append({
            "id": "draft_pileup", "severity": "low", "metric": "Draft documents",
            "title": "Unsubmitted draft documents are piling up",
            "detail": f"{drafts:,} documents are still in Draft (not posted to the ledger). They don't hit the books until submitted and can hide real activity.",
            "amount": drafts, "account": None,
            "recommendation": "Review and submit or cancel the drafts (bulk Submit on each list).",
            "drill": {"module": "accountant", "sub": "journals", "label": "Journals"},
        })

    f.sort(key=lambda x: SEV_WEIGHT.get(x["severity"], 0), reverse=True)
    summary = {
        "high": sum(1 for x in f if x["severity"] == "high"),
        "medium": sum(1 for x in f if x["severity"] == "medium"),
        "low": sum(1 for x in f if x["severity"] == "low"),
        "count": len(f),
        "exposure": sum(abs(x["amount"]) for x in f if x["severity"] == "high"),
    }
    result = {"company": target, "generated_on": nowdate(), "findings": f, "summary": summary}
    try:
        frappe.cache().set_value(ck, result, expires_in_sec=120)
    except Exception:
        pass
    return result


# ── Conversational auditor — grounded on the live findings ──
def _context_text(data):
    """Render the live findings as compact grounding text for the model."""
    fs = data.get("findings") or []
    if not fs:
        return "No control findings — the books look healthy on the checked controls."
    lines = [f"Company: {data.get('company')}. {len(fs)} open finding(s)."]
    for x in fs:
        lines.append(
            f"- [{x['severity'].upper()}] {x['title']}: {x['detail']} "
            f"(amount {x.get('amount'):,.0f}, account {x.get('account') or '—'}). "
            f"Fix: {x.get('recommendation')}")
    return "\n".join(lines)


def _claude_answer(question, ctx):
    """Ask Claude, grounded strictly on the findings. Returns None on any failure
    so the caller falls back to the deterministic responder."""
    key = frappe.conf.get("anthropic_api_key")
    if not key:
        return None
    model = frappe.conf.get("auditor_model") or "claude-sonnet-4-6"
    try:
        import requests
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={
                "model": model, "max_tokens": 700,
                "system": (
                    "You are the Justyol Group's Accounting Manager and CFO, speaking to your accounting team. "
                    "You think like a CFO: triage by financial risk and cash impact, protect the audit trail, and "
                    "decide what gets fixed first and by whom. "
                    "Reason ONLY from the FINDINGS and TEAM/TASKS context provided — they are real, live figures from "
                    "the books. Cite exact amounts and account names. When asked what to do, give a prioritized plan: "
                    "for each issue say the action, who should own it (accountant), and a sensible deadline. Keep it "
                    "crisp and managerial (bullet points are good). If something isn't in the findings, say what you "
                    "can see and where in the portal to look. Never invent numbers or accounts."),
                "messages": [{"role": "user", "content": f"FINDINGS:\n{ctx}\n\nQUESTION: {question}"}],
            },
            timeout=20)
        if r.status_code == 200:
            body = r.json()
            parts = body.get("content") or []
            text = "".join(p.get("text", "") for p in parts if p.get("type") == "text").strip()
            return text or None
        frappe.log_error(f"auditor claude {r.status_code}: {r.text[:300]}", "AI Auditor")
    except Exception as e:
        frappe.log_error(f"auditor claude error: {e}", "AI Auditor")
    return None


def _rule_answer(question, data):
    """Deterministic grounded answer when the model is unavailable."""
    fs = data.get("findings") or []
    s = data.get("summary") or {}
    q = (question or "").lower()
    if not fs:
        return "No control findings right now — the books look healthy on the checked controls (stock/COGS, COD, GRNI, corrections, cash, payables)."
    top = fs[0]
    if any(w in q for w in ("fix", "do first", "priority", "recommend", "action", "أصلح", "أولوية")):
        return f"Start with the highest-severity item — {top['title']}: {top.get('recommendation')} (amount {top.get('amount'):,.0f}, account {top.get('account') or '—'})."
    if any(w in q for w in ("exposure", "how much", "total", "risk", "تعرّض", "كم")):
        return f"Open findings: {s.get('high', 0)} high, {s.get('medium', 0)} medium. High-severity exposure totals {s.get('exposure', 0):,.0f} MAD. Biggest: {top['title']}."
    if any(w in q for w in ("biggest", "worst", "main", "أكبر", "أهم")):
        return f"{top['title']} — {top['detail']} Fix: {top.get('recommendation')}"
    # keyword match against a specific finding
    for x in fs:
        if any(t in q for t in (x["id"].split("_") + x["metric"].lower().split())):
            return f"{x['title']} — {x['detail']} Fix: {x.get('recommendation')}"
    titles = "; ".join(f"{x['title']} ({x.get('amount'):,.0f})" for x in fs[:4])
    return f"I'm tracking {len(fs)} finding(s): {titles}. Ask about any one, or which to fix first."


@frappe.whitelist()
def ask_auditor(question=None, company=None):
    """Conversational auditor grounded on the live control findings. Uses Claude
    when configured, else a deterministic responder — either way only the real
    findings are used as the source."""
    assert_portal_access()
    if not (question or "").strip():
        frappe.throw("Ask a question")
    target = _target(company)
    data = run_controls(target)
    ctx = _context_text(data)
    try:
        board = remediation_board(target)
        bs = board.get("summary") or {}
        if board.get("tasks"):
            ctx += f"\n\nTEAM/TASKS: {bs.get('open', 0)} open, {bs.get('done', 0)} done. Assigned:\n"
            for t in board["tasks"][:12]:
                ctx += f"- {t['title']} → {t.get('assigned_to') or 'unassigned'} ({t.get('priority')}, due {t.get('due')}, {t.get('status')})\n"
    except Exception:
        pass
    ai = _claude_answer(question, ctx)
    return {
        "answer": ai or _rule_answer(question, data),
        "source": "ai" if ai else "rules",
        "findings_count": len((data.get("findings") or [])),
    }


# ── CFO task board — turn findings into assigned tasks for the accountants ──
SEV_PRIORITY = {"high": "High", "medium": "Medium", "low": "Low"}
SEV_DUE_DAYS = {"high": 3, "medium": 7, "low": 14}


def _marker(company, fid):
    return f"⟦AUDIT:{company}:{fid}⟧"


def _existing_task(company, fid):
    return frappe.db.get_value(
        "ToDo", {"description": ["like", f"%{_marker(company, fid)}%"], "status": "Open"}, "name")


def _finding(data, fid):
    return next((x for x in (data.get("findings") or []) if x["id"] == fid), None)


@frappe.whitelist()
def assign_finding(company=None, finding_id=None, to_user=None, priority=None, due_date=None):
    """Turn a control finding into a task (ToDo) assigned to an accountant.
    Idempotent per finding — re-assigning updates the same task."""
    assert_can_write()
    target = _target(company)
    fnd = _finding(run_controls(target), finding_id)
    if not fnd:
        frappe.throw("Finding not found")
    if not to_user:
        frappe.throw("Pick an accountant to own this")
    pr = priority or SEV_PRIORITY.get(fnd["severity"], "Medium")
    dd = due_date or add_days(nowdate(), SEV_DUE_DAYS.get(fnd["severity"], 7))
    desc = (f"<b>{fnd['title']}</b><br>{fnd['detail']}<br><br>"
            f"<b>Fix:</b> {fnd.get('recommendation')}<br>"
            f"<b>Amount:</b> {flt(fnd.get('amount')):,.0f} &middot; <b>Account:</b> {fnd.get('account') or '—'}<br>"
            f"<span style='color:#aaa'>{_marker(target, finding_id)}</span>")
    existing = _existing_task(target, finding_id)
    if existing:
        todo = frappe.get_doc("ToDo", existing)
        todo.allocated_to = to_user
        todo.priority = pr
        todo.date = dd
    else:
        todo = frappe.get_doc({
            "doctype": "ToDo", "allocated_to": to_user, "description": desc,
            "priority": pr, "date": dd, "status": "Open", "assigned_by": frappe.session.user})
    todo.flags.ignore_permissions = True
    todo.save(ignore_permissions=True) if existing else todo.insert(ignore_permissions=True)
    # Notify the accountant (ERPNext bell + the portal's My-work badge picks it up).
    if not existing and to_user != frappe.session.user:
        try:
            frappe.get_doc({
                "doctype": "Notification Log", "for_user": to_user, "type": "Assignment",
                "subject": f"Audit task assigned: {fnd['title']}", "from_user": frappe.session.user,
                "document_type": "ToDo", "document_name": todo.name,
            }).insert(ignore_permissions=True)
        except Exception:
            pass
    frappe.db.commit()
    return {"task": todo.name, "finding_id": finding_id, "assigned_to": to_user,
            "priority": pr, "due": str(dd)}


@frappe.whitelist()
def auto_plan(company=None, assignees=None):
    """CFO auto-plan: create a task for every finding that doesn't have one yet,
    round-robin across the given accountants (or all enabled users), prioritized by
    severity with a severity-based deadline. Returns the plan it created."""
    assert_can_write()
    target = _target(company)
    findings = run_controls(target).get("findings") or []
    if isinstance(assignees, str):
        assignees = json.loads(assignees or "[]")
    if not assignees:
        assignees = [u.name for u in frappe.get_all(
            "User", filters={"enabled": 1, "user_type": "System User"}, fields=["name"], limit=20)]
    if not assignees:
        frappe.throw("No accountants available to assign to")
    created, i = [], 0
    for fnd in findings:
        if _existing_task(target, fnd["id"]):
            continue
        res = assign_finding(target, fnd["id"], assignees[i % len(assignees)])
        created.append({**res, "title": fnd["title"], "severity": fnd["severity"]})
        i += 1
    return {"created": len(created), "skipped": len(findings) - len(created), "tasks": created}


@frappe.whitelist()
def remediation_board(company=None):
    """All open audit tasks (findings turned into ToDos) with owner / priority / due."""
    assert_portal_access()
    target = _target(company)
    marker = f"⟦AUDIT:{target}:"
    rows = frappe.get_all(
        "ToDo", filters={"description": ["like", f"%{marker}%"]},
        fields=["name", "allocated_to", "priority", "date", "status", "description"],
        order_by="date asc", limit=200)
    out = []
    for r in rows:
        d = r.get("description") or ""
        m = d.find(marker)
        fid = d[m + len(marker):].split("⟧")[0] if m >= 0 else ""
        a, b = d.find("<b>"), d.find("</b>")
        title = d[a + 3:b] if (a >= 0 and b > a) else "Audit task"
        out.append({"task": r["name"], "finding_id": fid, "title": title,
                    "assigned_to": r.get("allocated_to"), "priority": r.get("priority"),
                    "due": str(r.get("date") or ""), "status": r.get("status")})
    order = {"High": 0, "Medium": 1, "Low": 2}
    out.sort(key=lambda t: (order.get(t["priority"], 1), t["due"] or "9999"))
    open_n = sum(1 for t in out if t["status"] == "Open")
    return {"company": target, "tasks": out,
            "summary": {"open": open_n, "done": len(out) - open_n, "total": len(out)}}


@frappe.whitelist()
def close_task(task=None):
    """Mark an audit task done."""
    assert_can_write()
    todo = frappe.get_doc("ToDo", task)
    todo.status = "Closed"
    todo.flags.ignore_permissions = True
    todo.save(ignore_permissions=True)
    frappe.db.commit()
    return {"task": task, "status": "Closed"}
