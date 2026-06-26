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
import frappe
from frappe.utils import flt, nowdate

from accounting_portal.api.permissions import assert_portal_access, resolve_companies

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

    f.sort(key=lambda x: SEV_WEIGHT.get(x["severity"], 0), reverse=True)
    summary = {
        "high": sum(1 for x in f if x["severity"] == "high"),
        "medium": sum(1 for x in f if x["severity"] == "medium"),
        "low": sum(1 for x in f if x["severity"] == "low"),
        "count": len(f),
        "exposure": sum(abs(x["amount"]) for x in f if x["severity"] == "high"),
    }
    return {"company": target, "generated_on": nowdate(), "findings": f, "summary": summary}


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
                "model": model, "max_tokens": 500,
                "system": (
                    "You are the Justyol accounting auditor speaking to the finance team. "
                    "Answer ONLY from the FINDINGS provided — they are real, live figures from the books. "
                    "Be concise (2-5 sentences). Cite the exact amounts and account names. Always end with the "
                    "concrete next action. If the question isn't covered by the findings, say what you can see "
                    "and where in the portal to look. Never invent numbers or accounts."),
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
    ai = _claude_answer(question, ctx)
    return {
        "answer": ai or _rule_answer(question, data),
        "source": "ai" if ai else "rules",
        "findings_count": len((data.get("findings") or [])),
    }
