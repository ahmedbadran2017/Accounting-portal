"""Dashboard endpoints — live multi-company accounting KPIs.

Reads straight from ERPNext's GL Entry + Account tables. All queries filter
`is_cancelled = 0` (cancelled entries must never count) and scope to the
companies the user is allowed to see.

Balances use the accounting convention sum(debit - credit):
  • Asset / Expense accounts carry a debit (positive) balance
  • Liability / Income / Equity carry a credit (negative) balance
So Payables (a liability) are reported as a positive "amount owed" by negating.
"""
import frappe
from frappe.utils import flt, getdate, nowdate

from accounting_portal.api.permissions import assert_portal_access, allowed_companies


def _company_filter(companies):
    """Build a safe SQL IN-list for the given company names."""
    if not companies:
        return "1=0", []
    placeholders = ", ".join(["%s"] * len(companies))
    return f"gl.company IN ({placeholders})", list(companies)


def _resolve_companies(company=None):
    """Companies the user may see, optionally narrowed to one. Validates the
    requested company against the allowed set so a caller can't read an entity
    they're not permitted to (and so a bad value yields nothing, not an error)."""
    allowed = allowed_companies()
    if company:
        return [c for c in allowed if c == company]
    return allowed


def _month_start():
    """First day of the month containing today (server date at runtime)."""
    d = getdate(nowdate())
    return d.replace(day=1).isoformat()


@frappe.whitelist()
def get_overview():
    """Per-company snapshot: receivables, payables, cash & bank, and a
    fiscal-year-to-date P&L (income, expense, net).

    Returns:
        {
          "as_of": "2026-06-23",
          "companies": [
            {"company", "currency", "receivable", "payable",
             "cash_bank", "income_ytd", "expense_ytd", "net_ytd"},
            ...
          ],
          "totals": { ... summed across companies (note: mixed-currency) ... }
        }
    """
    assert_portal_access()
    companies = allowed_companies()
    if not companies:
        return {"as_of": nowdate(), "companies": [], "totals": {}}

    where, params = _company_filter(companies)
    fy_start = _fiscal_year_start()

    # Balance-sheet style figures (all-time, by account_type).
    bs = frappe.db.sql(
        f"""
        SELECT gl.company AS company, acc.account_type AS account_type,
               SUM(gl.debit - gl.credit) AS bal
        FROM `tabGL Entry` gl
        JOIN `tabAccount` acc ON acc.name = gl.account
        WHERE gl.is_cancelled = 0
          AND {where}
          AND acc.account_type IN ('Receivable', 'Payable', 'Cash', 'Bank')
        GROUP BY gl.company, acc.account_type
        """,
        params,
        as_dict=True,
    )

    # P&L figures, fiscal-year-to-date, by root_type.
    pl = frappe.db.sql(
        f"""
        SELECT gl.company AS company, acc.root_type AS root_type,
               SUM(gl.credit - gl.debit) AS amt
        FROM `tabGL Entry` gl
        JOIN `tabAccount` acc ON acc.name = gl.account
        WHERE gl.is_cancelled = 0
          AND {where}
          AND gl.posting_date >= %s
          AND acc.root_type IN ('Income', 'Expense')
        GROUP BY gl.company, acc.root_type
        """,
        params + [fy_start],
        as_dict=True,
    )

    by_company = {c: {
        "company": c,
        "currency": frappe.db.get_value("Company", c, "default_currency"),
        "receivable": 0.0, "payable": 0.0, "cash_bank": 0.0,
        "income_ytd": 0.0, "expense_ytd": 0.0, "net_ytd": 0.0,
    } for c in companies}

    for r in bs:
        row = by_company.get(r.company)
        if not row:
            continue
        bal = flt(r.bal)
        if r.account_type == "Receivable":
            row["receivable"] += bal
        elif r.account_type == "Payable":
            row["payable"] += -bal          # liability → report as positive owed
        elif r.account_type in ("Cash", "Bank"):
            row["cash_bank"] += bal

    for r in pl:
        row = by_company.get(r.company)
        if not row:
            continue
        amt = flt(r.amt)
        if r.root_type == "Income":
            row["income_ytd"] += amt        # credit-positive
        elif r.root_type == "Expense":
            row["expense_ytd"] += -amt       # expenses are debit-positive

    for row in by_company.values():
        row["net_ytd"] = row["income_ytd"] - row["expense_ytd"]

    companies_out = [by_company[c] for c in companies]
    totals = {
        "receivable": sum(r["receivable"] for r in companies_out),
        "payable": sum(r["payable"] for r in companies_out),
        "cash_bank": sum(r["cash_bank"] for r in companies_out),
        "income_ytd": sum(r["income_ytd"] for r in companies_out),
        "expense_ytd": sum(r["expense_ytd"] for r in companies_out),
        "net_ytd": sum(r["net_ytd"] for r in companies_out),
    }
    return {"as_of": nowdate(), "fy_start": fy_start,
            "companies": companies_out, "totals": totals}


@frappe.whitelist()
def get_recent_entries(limit=20, company=None):
    """Most recent GL entries across allowed companies (audit feed)."""
    assert_portal_access()
    companies = allowed_companies()
    if company:
        companies = [c for c in companies if c == company]
    if not companies:
        return []
    where, params = _company_filter(companies)
    limit = min(int(limit or 20), 100)
    rows = frappe.db.sql(
        f"""
        SELECT gl.posting_date, gl.company, gl.account, gl.voucher_type,
               gl.voucher_no, gl.debit, gl.credit, gl.party_type, gl.party,
               gl.remarks
        FROM `tabGL Entry` gl
        WHERE gl.is_cancelled = 0 AND {where}
        ORDER BY gl.posting_date DESC, gl.creation DESC
        LIMIT %s
        """,
        params + [limit],
        as_dict=True,
    )
    return rows


@frappe.whitelist()
def get_cod_cockpit(company=None, from_date=None, to_date=None):
    """Entity-scoped COD financial cockpit (the Dashboard hero) — all live.

    from_date/to_date scope the FLOW metrics (collections, channels, cash-flow,
    pipeline funnel, procurement); default is the current month. Point-in-time
    balances (cash on hand, receivable, payable, carrier float) stay as-of-now.

    Defaults to the first allowed company (Justyol Morocco for the team). Every
    figure is month-to-date off Bank/Cash GL movement, scoped to one company,
    filtering is_cancelled = 0. Validated against the live instance: Cathadis
    (108.021.003) carries ~99% of COD collection — surfaced as a concentration
    warning.

    Returns:
        {
          "company", "currency", "as_of", "month_start",
          "cash_collected_mtd", "paid_out_mtd", "net_cash",
          "receivable", "payable",
          "channels": [{"account", "cash_in", "share", "is_clearing"}],
          "cash_flow": [{"day": "DD", "in": n, "out": n}]
        }
    """
    assert_portal_access()
    companies = _resolve_companies(company)
    if not companies:
        return {}
    target = company if (company and company in companies) else companies[0]
    period_start = from_date or _month_start()
    period_end = to_date or nowdate()
    # Heavy aggregate (≈8s uncached) — serve from a short-lived cache so the
    # dashboard is instant. Busted on any portal write via _bust_cockpit_cache.
    ck = f"ap_cockpit:{target}:{period_start}:{period_end}"
    cached = frappe.cache().get_value(ck)
    if cached is not None:
        return cached
    currency = frappe.db.get_value("Company", target, "default_currency")
    month_start = period_start

    # Month-to-date Bank/Cash movement, per account → channels + totals.
    chan = frappe.db.sql(
        """
        SELECT gl.account AS account,
               SUM(gl.debit) AS cash_in, SUM(gl.credit) AS cash_out
        FROM `tabGL Entry` gl
        JOIN `tabAccount` acc ON acc.name = gl.account
        WHERE gl.is_cancelled = 0 AND gl.company = %s
          AND acc.account_type IN ('Bank', 'Cash')
          AND gl.posting_date >= %s AND gl.posting_date <= %s
        GROUP BY gl.account
        ORDER BY cash_in DESC
        """,
        (target, period_start, period_end),
        as_dict=True,
    )
    collected = sum(flt(r.cash_in) for r in chan)
    paid_out = sum(flt(r.cash_out) for r in chan)
    channels = [
        {
            "account": r.account,
            "cash_in": flt(r.cash_in),
            "share": round(flt(r.cash_in) / collected * 100, 1) if collected else 0,
            # A single Bank/Cash account taking the lion's share is the COD
            # clearing-account concentration risk the auditor flags.
            "is_clearing": bool(collected and flt(r.cash_in) / collected > 0.5),
        }
        for r in chan if flt(r.cash_in) > 0
    ]

    # Daily money-in / money-out for the cash-flow bars.
    flow = frappe.db.sql(
        """
        SELECT DATE_FORMAT(gl.posting_date, '%%d') AS day,
               SUM(gl.debit) AS cin, SUM(gl.credit) AS cout
        FROM `tabGL Entry` gl
        JOIN `tabAccount` acc ON acc.name = gl.account
        WHERE gl.is_cancelled = 0 AND gl.company = %s
          AND acc.account_type IN ('Bank', 'Cash')
          AND gl.posting_date >= %s AND gl.posting_date <= %s
        GROUP BY day ORDER BY day
        """,
        (target, period_start, period_end),
        as_dict=True,
    )
    cash_flow = [{"day": r.day, "in": flt(r.cin), "out": flt(r.cout)} for r in flow]

    # All-time AR / AP balances (account_type), scoped to the entity.
    bal = frappe.db.sql(
        """
        SELECT acc.account_type AS t, SUM(gl.debit - gl.credit) AS bal
        FROM `tabGL Entry` gl
        JOIN `tabAccount` acc ON acc.name = gl.account
        WHERE gl.is_cancelled = 0 AND gl.company = %s
          AND acc.account_type IN ('Receivable', 'Payable')
        GROUP BY acc.account_type
        """,
        (target,),
        as_dict=True,
    )
    receivable = next((flt(r.bal) for r in bal if r.t == "Receivable"), 0.0)
    payable = -next((flt(r.bal) for r in bal if r.t == "Payable"), 0.0)

    # Actual liquidity — the real cash on hand (Bank + Cash account balances).
    # The #1 CFO number; a negative Cash balance is a control flag.
    cashb = frappe.db.sql(
        """
        SELECT acc.account_type AS t, SUM(gl.debit - gl.credit) AS bal
        FROM `tabGL Entry` gl JOIN `tabAccount` acc ON acc.name = gl.account
        WHERE gl.is_cancelled = 0 AND gl.company = %s AND acc.account_type IN ('Bank', 'Cash')
        GROUP BY acc.account_type
        """,
        (target,), as_dict=True)
    bank_balance = next((flt(r.bal) for r in cashb if r.t == "Bank"), 0.0)
    cash_balance = next((flt(r.bal) for r in cashb if r.t == "Cash"), 0.0)

    # COD pipeline funnel + the collection gap (the heart of the control tower).
    # Reuses the cached cod_summary / cohort so this stays cheap.
    pipeline, carrier_float, reconciled_pct, returns_exposure, cohort = {}, 0.0, 0.0, 0.0, []
    try:
        from accounting_portal.api import cod as _cod
        pipeline = _cod.cod_summary(target, period_start, period_end) or {}
        coll_v = flt((pipeline.get("collected") or {}).get("value"))
        deliv_v = flt((pipeline.get("delivered") or {}).get("value"))
        carrier_float = deliv_v                                  # delivered, cash not yet reconciled
        cash_due = coll_v + deliv_v
        reconciled_pct = round(coll_v / cash_due * 100, 1) if cash_due else 0.0
        returns_exposure = flt((pipeline.get("toreturn") or {}).get("value"))
    except Exception:
        pass
    try:
        from accounting_portal.api import reports as _rep
        coh = _rep.sales_collections_cohort(target) or {}
        cohort = (coh.get("months") or [])[-6:]
    except Exception:
        pass
    # Procure-to-pay gaps (GRNI + AP) for the dashboard's purchases strip.
    purchases = {}
    try:
        from accounting_portal.api import purchases as _pur
        purchases = _pur.purchases_summary(target, period_start, period_end) or {}
    except Exception:
        pass
    # Cheques due — supplier cheques clearing within 7 days (cash-out heads-up).
    cheques = {}
    try:
        from accounting_portal.api import purchases as _pur2
        cheques = _pur2.cheques_summary(target) or {}
    except Exception:
        pass
    # AR/AP reconciliation headline for the dashboard's books card.
    arap = {}
    try:
        from accounting_portal.api import reports as _rep
        rec = _rep.ar_ap_reconciliation(target) or {}
        arap = {
            "ar_operational": (rec.get("ar") or {}).get("operational", 0),
            "ar_gl": (rec.get("ar") or {}).get("gl_debtors", 0),
            "ar_broken": (rec.get("ar") or {}).get("wrong_sign", False),
            "ap_net": (rec.get("ap") or {}).get("net_invoice", 0),
            "ap_reconciled": (rec.get("ap") or {}).get("reconciled", False),
            "working_capital": rec.get("working_capital", 0),
        }
    except Exception:
        pass

    result = {
        "company": target, "currency": currency,
        "as_of": nowdate(), "month_start": month_start,
        "period_start": period_start, "period_end": period_end,
        "cash_on_hand": bank_balance + cash_balance,
        "bank_balance": bank_balance, "cash_balance": cash_balance,
        "cash_collected_mtd": collected, "paid_out_mtd": paid_out,
        "net_cash": collected - paid_out,
        "receivable": receivable, "payable": payable,
        "channels": channels, "cash_flow": cash_flow,
        "pipeline": pipeline, "carrier_float": carrier_float,
        "reconciled_pct": reconciled_pct, "returns_exposure": returns_exposure,
        "cohort": cohort, "purchases": purchases, "arap": arap, "cheques": cheques,
    }
    frappe.cache().set_value(ck, result, expires_in_sec=180)
    return result


@frappe.whitelist()
def refresh_cockpit(company=None):
    """Force-refresh the dashboard cache (the UI's 'refresh' affordance)."""
    assert_portal_access()
    for cs in _resolve_companies(company):
        _bust_cockpit_cache(cs)
    return get_cod_cockpit(company)


def _bust_cockpit_cache(company):
    """Drop the cached cockpit + command-center for a company (call after writes)."""
    frappe.cache().delete_value(f"ap_cockpit:{company}")
    frappe.cache().delete_value(f"ap_command:{company}")


def _build_alerts(target, ccy):
    """Real, live alerts for the dashboard feed (replaces hardcoded anomalies).
    Each: severity high/medium/low, title, detail, route to drill in."""
    out = []

    def add(sev, title, detail, route):
        out.append({"severity": sev, "title": title, "detail": detail, "route": route})

    # Negative cash position.
    cash = flt(frappe.db.sql(
        """SELECT COALESCE(SUM(g.debit-g.credit),0) FROM `tabGL Entry` g
           JOIN `tabAccount` a ON a.name=g.account
           WHERE g.company=%s AND g.is_cancelled=0 AND a.account_type IN ('Bank','Cash')""",
        (target,))[0][0])
    if cash < 0:
        add("high", "Negative cash balance", f"{round(cash):,.0f} {ccy} across bank + cash", "/accounting/banking")

    # Debtors carrying a credit balance (collections not applied to invoices).
    deb = flt(frappe.db.sql(
        """SELECT COALESCE(SUM(g.debit-g.credit),0) FROM `tabGL Entry` g
           JOIN `tabAccount` a ON a.name=g.account
           WHERE g.company=%s AND g.is_cancelled=0 AND a.account_type='Receivable'""",
        (target,))[0][0])
    if deb < -1000:
        add("high", "Debtors have a credit balance", f"{round(deb):,.0f} {ccy} — collections unapplied to invoices", "/accounting/reports/arap")

    # GRNI — received but not billed (Purchase Receipt per_billed<100).
    try:
        from accounting_portal.api import purchases as _pur
        psum = _pur.purchases_summary(target) or {}
        grni = (psum.get("received") or {}).get("value", 0)
        if grni and grni > 50000:
            add("medium", "Goods received, not billed (GRNI)", f"{round(grni):,.0f} {ccy} awaiting supplier invoice", "/accounting/purchases/received")
        overdue_ap = (psum.get("topay") or {}).get("value", 0)
        if overdue_ap and overdue_ap > 50000:
            add("medium", "Bills due now", f"{round(overdue_ap):,.0f} {ccy} payable due or overdue", "/accounting/purchases/topay")
    except Exception:
        pass

    # Delivered-but-not-invoiced aged > 60 days (revenue recognition gap).
    try:
        from accounting_portal.api import sales as _sal
        tb = (_sal.to_bill_queue(target) or {}).get("summary", {})
        if tb.get("value_over_60", 0) > 10000:
            add("medium", "Delivered, not invoiced (>60d)", f"{round(tb['value_over_60']):,.0f} {ccy} revenue unrecognised", "/accounting/sales/tobill")
    except Exception:
        pass

    # Supplier cheques clearing within 7 days (cash-out heads-up).
    try:
        from accounting_portal.api import purchases as _pur2
        chq = _pur2.cheques_summary(target) or {}
        due = chq.get("due_soon_value") or chq.get("due_value") or 0
        if due and due > 0:
            add("low", "Cheques clearing soon", f"{round(due):,.0f} {ccy} within 7 days", "/accounting/purchases/cheques")
    except Exception:
        pass

    sev_order = {"high": 0, "medium": 1, "low": 2}
    out.sort(key=lambda a: sev_order.get(a["severity"], 3))
    return out


@frappe.whitelist()
def command_center(company=None):
    """Dashboard command strip + live alerts: collected today, approvals waiting,
    AR/AP aging buckets, and a real alerts feed."""
    assert_portal_access()
    cs = _resolve_companies(company)
    if not cs:
        return {}
    target = cs[0]
    ck = f"ap_command:{target}"
    cached = frappe.cache().get_value(ck)
    if cached is not None:
        return cached
    ccy = frappe.db.get_value("Company", target, "default_currency") or "MAD"
    today = nowdate()
    collected_today = flt(frappe.db.sql(
        """SELECT COALESCE(SUM(paid_amount),0) FROM `tabPayment Entry`
           WHERE company=%s AND docstatus=1 AND payment_type='Receive' AND posting_date=%s""",
        (target, today))[0][0])
    approvals = 0
    if frappe.db.exists("DocType", "Accounting Portal Action"):
        approvals = frappe.db.count("Accounting Portal Action", {"company": target, "status": "Proposed"})
    from accounting_portal.api.reports import _aging
    result = {
        "company": target, "currency": ccy,
        "collected_today": collected_today,
        "approvals_pending": approvals,
        "ar_aging": _aging("Sales Invoice", target),
        "ap_aging": _aging("Purchase Invoice", target),
        "alerts": _build_alerts(target, ccy),
    }
    frappe.cache().set_value(ck, result, expires_in_sec=180)
    return result


def _fiscal_year_start():
    """Start date of the fiscal year containing today. Falls back to Jan 1."""
    try:
        fy = frappe.db.sql(
            """SELECT year_start_date FROM `tabFiscal Year`
               WHERE %s BETWEEN year_start_date AND year_end_date
               ORDER BY year_start_date DESC LIMIT 1""",
            (nowdate(),),
        )
        if fy:
            return str(fy[0][0])
    except Exception:
        pass
    return f"{getdate(nowdate()).year}-01-01"
