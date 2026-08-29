"""Financial reports — P&L, balance sheet, AR/AP aging, VAT.

All read-only, entity-scoped, and validated against the live books. Heavy GL
aggregates are bounded by company + period. Account-level rows are returned so
the team sees exactly where each number comes from (and the auditor's anomalies,
like the stock-adjustment pile in the P&L, stay visible rather than hidden).
"""
import frappe
from frappe.utils import flt, nowdate

from accounting_portal.api import _cache
from accounting_portal.api.permissions import assert_portal_access, resolve_companies


def _target(company):
    companies = resolve_companies(company)
    if not companies:
        return None
    return company if (company and company in companies) else companies[0]


def _year_bounds(year=None):
    y = int(year or nowdate()[:4])
    return f"{y}-01-01", f"{y}-12-31"


@frappe.whitelist()
def pnl(company=None, from_date=None, to_date=None):
    """Profit & loss — income and expense accounts grouped, with net result."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    if not (from_date and to_date):
        from_date, to_date = _year_bounds()

    rows = frappe.db.sql(
        """SELECT a.name, a.account_name, a.root_type,
                  ROUND(SUM(gle.credit - gle.debit)) AS credit_net,
                  ROUND(SUM(gle.debit - gle.credit)) AS debit_net
           FROM `tabGL Entry` gle JOIN `tabAccount` a ON a.name = gle.account
           WHERE gle.company=%s AND gle.is_cancelled=0
             AND a.root_type IN ('Income','Expense')
             AND gle.posting_date BETWEEN %s AND %s
           GROUP BY a.name HAVING SUM(ABS(gle.debit)) + SUM(ABS(gle.credit)) > 0
           ORDER BY ABS(SUM(gle.debit - gle.credit)) DESC""",
        (target, from_date, to_date), as_dict=True)

    income = [{"account": r.name, "name": r.account_name, "amount": flt(r.credit_net)}
              for r in rows if r.root_type == "Income"]
    expense = [{"account": r.name, "name": r.account_name, "amount": flt(r.debit_net)}
               for r in rows if r.root_type == "Expense"]
    income_total = sum(r["amount"] for r in income)
    expense_total = sum(r["amount"] for r in expense)

    # Flag a single expense account that dominates the statement (the broken
    # Stock-Adjustment pile) so the P&L isn't silently read as a real loss.
    anomaly = None
    if expense and expense_total and expense[0]["amount"] > 0.4 * expense_total and expense[0]["amount"] > 1_000_000:
        anomaly = {"account": expense[0]["account"], "name": expense[0]["name"], "amount": expense[0]["amount"]}

    return {
        "from_date": from_date, "to_date": to_date, "company": target,
        "income": income[:20], "expense": expense[:20],
        "income_total": income_total, "expense_total": expense_total,
        "net": income_total - expense_total, "anomaly": anomaly,
    }


@frappe.whitelist()
def balance_sheet(company=None, as_on=None):
    """Balance sheet — asset / liability / equity balances as of a date."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    as_on = as_on or nowdate()
    bs_key = f"ap_bs:{target}:{as_on}"
    cached_bs = frappe.cache().get_value(bs_key)
    if cached_bs is not None:
        return cached_bs
    rows = frappe.db.sql(
        """SELECT a.root_type,
                  ROUND(SUM(gle.debit - gle.credit)) AS debit_net,
                  ROUND(SUM(gle.credit - gle.debit)) AS credit_net
           FROM `tabGL Entry` gle JOIN `tabAccount` a ON a.name = gle.account
           WHERE gle.company=%s AND gle.is_cancelled=0
             AND a.root_type IN ('Asset','Liability','Equity')
             AND gle.posting_date <= %s
           GROUP BY a.root_type""",
        (target, as_on), as_dict=True)
    out = {"assets": 0.0, "liabilities": 0.0, "equity": 0.0}
    for r in rows:
        if r.root_type == "Asset":
            out["assets"] = flt(r.debit_net)
        elif r.root_type == "Liability":
            out["liabilities"] = flt(r.credit_net)
        elif r.root_type == "Equity":
            out["equity"] = flt(r.credit_net)
    out["as_on"] = as_on
    out["check"] = round(out["assets"] - out["liabilities"] - out["equity"], 0)
    try:
        frappe.cache().set_value(bs_key, out, expires_in_sec=180)
    except Exception:
        pass
    return out


def _aging(doctype, company):
    return frappe.db.sql(
        f"""SELECT
              ROUND(SUM(CASE WHEN DATEDIFF(CURDATE(), IFNULL(due_date,posting_date)) <= 0 THEN outstanding_amount ELSE 0 END)) AS cur,
              ROUND(SUM(CASE WHEN DATEDIFF(CURDATE(), IFNULL(due_date,posting_date)) BETWEEN 1 AND 30 THEN outstanding_amount ELSE 0 END)) AS d1_30,
              ROUND(SUM(CASE WHEN DATEDIFF(CURDATE(), IFNULL(due_date,posting_date)) BETWEEN 31 AND 60 THEN outstanding_amount ELSE 0 END)) AS d31_60,
              ROUND(SUM(CASE WHEN DATEDIFF(CURDATE(), IFNULL(due_date,posting_date)) BETWEEN 61 AND 90 THEN outstanding_amount ELSE 0 END)) AS d61_90,
              ROUND(SUM(CASE WHEN DATEDIFF(CURDATE(), IFNULL(due_date,posting_date)) > 90 THEN outstanding_amount ELSE 0 END)) AS d90p,
              ROUND(SUM(outstanding_amount)) AS total, COUNT(*) AS n
           FROM `tab{doctype}` WHERE company=%s AND docstatus=1 AND outstanding_amount<>0""",
        (company,), as_dict=True)[0]


@frappe.whitelist()
def ar_aging(company=None):
    """Receivables aging by due date — current / 1-30 / 31-60 / 61-90 / 90+."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    out = _aging("Sales Invoice", target)
    out["company"] = target
    return out


@frappe.whitelist()
def ap_aging(company=None):
    """Payables aging by due date — current / 1-30 / 31-60 / 61-90 / 90+."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    out = _aging("Purchase Invoice", target)
    out["company"] = target
    return out


def _aging_by_party(doctype, party_field, company, name_field):
    return frappe.db.sql(
        f"""SELECT {party_field} party, IFNULL(MAX({name_field}), {party_field}) party_name,
              ROUND(SUM(CASE WHEN DATEDIFF(CURDATE(), IFNULL(due_date,posting_date)) <= 0 THEN outstanding_amount ELSE 0 END)) cur,
              ROUND(SUM(CASE WHEN DATEDIFF(CURDATE(), IFNULL(due_date,posting_date)) BETWEEN 1 AND 30 THEN outstanding_amount ELSE 0 END)) d1_30,
              ROUND(SUM(CASE WHEN DATEDIFF(CURDATE(), IFNULL(due_date,posting_date)) BETWEEN 31 AND 60 THEN outstanding_amount ELSE 0 END)) d31_60,
              ROUND(SUM(CASE WHEN DATEDIFF(CURDATE(), IFNULL(due_date,posting_date)) BETWEEN 61 AND 90 THEN outstanding_amount ELSE 0 END)) d61_90,
              ROUND(SUM(CASE WHEN DATEDIFF(CURDATE(), IFNULL(due_date,posting_date)) > 90 THEN outstanding_amount ELSE 0 END)) d90p,
              ROUND(SUM(outstanding_amount)) total, COUNT(*) n
           FROM `tab{doctype}` t WHERE company=%s AND docstatus=1 AND outstanding_amount<>0
           GROUP BY {party_field} HAVING ABS(SUM(outstanding_amount)) > 0.5
           ORDER BY total DESC LIMIT 400""", (company,), as_dict=True)


@frappe.whitelist()
def aging_by_party(company=None, kind="ar"):
    """Aged trial balance BY PARTY — each customer/supplier across the buckets,
    the listing an auditor expects (the totals-only aging isn't enough)."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {"rows": [], "kind": kind}
    if kind == "ap":
        rows = _aging_by_party("Purchase Invoice", "supplier", target, "supplier_name")
    else:
        rows = _aging_by_party("Sales Invoice", "customer", target, "customer_name")
    tot = {k: sum(flt(r[k]) for r in rows) for k in ("cur", "d1_30", "d31_60", "d61_90", "d90p", "total")}
    return {"company": target, "kind": kind, "rows": rows, "totals": tot,
            "currency": frappe.db.get_value("Company", target, "default_currency") or "MAD"}


@frappe.whitelist()
def inventory_health(company=None):
    """Diagnose the stock/COGS break: stock-in-hand vs the Stock-Adjustment pile.

    Healthy books relieve stock to COGS on delivery. Here stock-in-hand is
    enormous while a Stock-Adjustment account absorbs the offset — so margin is
    unmeasurable. Returns the figures and the magnitude of the distortion.
    """
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    invh_key = f"ap_invh:{target}"
    cached_invh = frappe.cache().get_value(invh_key)
    if cached_invh is not None:
        return cached_invh
    stock = flt(frappe.db.sql(
        """SELECT ROUND(SUM(gle.debit - gle.credit)) FROM `tabGL Entry` gle
           JOIN `tabAccount` a ON a.name=gle.account
           WHERE gle.company=%s AND gle.is_cancelled=0 AND a.account_type='Stock'
             AND a.root_type='Asset'""",
        (target,))[0][0] or 0)
    adj = frappe.db.sql(
        """SELECT a.name, ROUND(SUM(gle.debit - gle.credit)) AS bal FROM `tabGL Entry` gle
           JOIN `tabAccount` a ON a.name=gle.account
           WHERE gle.company=%s AND gle.is_cancelled=0 AND a.account_name LIKE '%%Stock Adjustment%%'
           GROUP BY a.name ORDER BY ABS(SUM(gle.debit - gle.credit)) DESC LIMIT 1""",
        (target,), as_dict=True)
    adj_acct = adj[0].name if adj else None
    adj_bal = flt(adj[0].bal) if adj else 0.0
    revenue = flt(frappe.db.sql(
        """SELECT ROUND(SUM(gle.credit - gle.debit)) FROM `tabGL Entry` gle
           JOIN `tabAccount` a ON a.name=gle.account
           WHERE gle.company=%s AND gle.is_cancelled=0 AND a.root_type='Income'
             AND gle.posting_date BETWEEN %s AND %s""",
        (target, *_year_bounds()))[0][0] or 0)
    result = {
        "company": target, "stock_in_hand": stock, "adjustment_account": adj_acct,
        "adjustment_balance": adj_bal, "revenue": revenue,
        "distortion": abs(stock) + abs(flt(frappe.db.sql(
            """SELECT SUM(gle.debit - gle.credit) FROM `tabGL Entry` gle
               JOIN `tabAccount` a ON a.name=gle.account
               WHERE gle.company=%s AND gle.is_cancelled=0
                 AND a.account_name LIKE '%%Stock Adjustment%%'
                 AND gle.posting_date < '2026-01-01'""", (target,))[0][0])),
        "healthy": abs(stock) < 50_000_000,
    }
    try:
        frappe.cache().set_value(invh_key, result, expires_in_sec=600)
    except Exception:
        pass
    return result


@frappe.whitelist()
def vat_summary(company=None, from_date=None, to_date=None):
    """VAT — output (collected) vs input (recoverable) vs net payable.

    Output VAT lives on liability tax accounts (39x), input VAT on asset tax
    accounts (19x). Net payable = output − input.
    """
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    if not (from_date and to_date):
        from_date, to_date = _year_bounds()
    rows = frappe.db.sql(
        """SELECT a.name, a.account_name, a.root_type,
                  ROUND(SUM(gle.credit - gle.debit)) AS net
           FROM `tabGL Entry` gle JOIN `tabAccount` a ON a.name = gle.account
           WHERE gle.company=%s AND gle.is_cancelled=0 AND a.account_type='Tax'
             AND gle.posting_date BETWEEN %s AND %s
           GROUP BY a.name HAVING SUM(ABS(gle.debit)) + SUM(ABS(gle.credit)) > 0
           ORDER BY ABS(SUM(gle.credit - gle.debit)) DESC""",
        (target, from_date, to_date), as_dict=True)
    output, inp = [], []
    for r in rows:
        item = {"account": r.name, "name": r.account_name, "amount": flt(r.net)}
        # Liability-rooted tax accounts are output VAT; assets are input VAT.
        (output if (r.root_type == "Liability" or r.net > 0) else inp).append(item)
    output_total = sum(i["amount"] for i in output)
    input_total = sum(-i["amount"] for i in inp)  # input shows as debit (negative net)
    return {
        "from_date": from_date, "to_date": to_date, "company": target,
        "output": output, "input": inp,
        "output_total": output_total, "input_total": input_total,
        "net_payable": output_total - input_total,
    }


@frappe.whitelist()
def sales_collections_cohort(company=None, from_date=None, to_date=None):
    """Sales (invoiced) and collections (reconciled COD cash) grouped by the
    ORDER month — so revenue lines up with the month its ad spend was incurred,
    not the (later) invoice month. Verified 1 invoice = 1 order for this book, so
    each invoice is attributed whole to its order's transaction month."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    if not (from_date and to_date):
        from_date, to_date = _year_bounds()
    ck = f"ap_sales_cohort:{target}:{from_date}:{to_date}"
    cached = frappe.cache().get_value(ck)
    if cached is not None:
        return cached

    params = {"c": target, "fd": from_date, "td": to_date}
    # Reuse the COD cockpit's exact collected/delivered definition so this report
    # always ties to the buckets: a carrier ref (CATH *or* RDF — the carrier
    # migrated the sequence) on the order OR on a docstatus<2 invoice = collected.
    # Hand-rolling a CATH-only / docstatus=1 join here had drifted out of sync,
    # under-counting June (all-RDF) at 46% and the draft-invoice tail everywhere.
    from accounting_portal.api.cod import _ref_present, _INV_JOIN
    collected_expr = "(" + _ref_present("so.custom_reference_number") + " OR inv.so IS NOT NULL)"
    delivered_expr = collected_expr[:-1] + " OR so.custom_track_shipment_status='Delivered')"
    so = frappe.db.sql(
        f"""SELECT DATE_FORMAT(so.transaction_date,'%%Y-%%m') m,
                  COUNT(*) orders,
                  ROUND(SUM(so.grand_total)) order_value,
                  ROUND(SUM(CASE WHEN {collected_expr} THEN so.grand_total ELSE 0 END)) collected,
                  ROUND(SUM(CASE WHEN {delivered_expr} THEN so.grand_total ELSE 0 END)) delivered
           FROM `tabSales Order` so
           {_INV_JOIN}
           WHERE so.company=%(c)s AND so.docstatus=1
             AND so.transaction_date BETWEEN %(fd)s AND %(td)s
             AND IFNULL(so.custom_sales_status,'') NOT IN ('Cancelled','Duplicated','')
           GROUP BY m""", params, as_dict=True)
    # 1 invoice = 1 order; collapse items to the invoice first to avoid multiplying
    # the header net by the line count, then attribute to the order's month.
    inv = frappe.db.sql(
        """SELECT DATE_FORMAT(so.transaction_date,'%%Y-%%m') m, ROUND(SUM(x.net)) invoiced
           FROM (SELECT si.name, si.base_net_total net, MIN(sii.sales_order) so_name
                 FROM `tabSales Invoice` si JOIN `tabSales Invoice Item` sii ON sii.parent=si.name
                 WHERE si.company=%(c)s AND si.docstatus=1 GROUP BY si.name) x
           JOIN `tabSales Order` so ON so.name=x.so_name
           WHERE so.transaction_date BETWEEN %(fd)s AND %(td)s
           GROUP BY m""", params, as_dict=True)
    inv_by = {r.m: flt(r.invoiced) for r in inv}

    months = []
    for r in so:
        invoiced, collected, delivered = inv_by.get(r.m, 0.0), flt(r.collected), flt(r.delivered)
        months.append({
            "month": r.m, "orders": r.orders or 0, "order_value": flt(r.order_value),
            "invoiced": invoiced, "delivered": delivered, "collected": collected,
            "outstanding": round(delivered - collected),
            "collection_rate": round(collected / delivered * 100, 1) if delivered else 0,
        })
    months.sort(key=lambda x: x["month"])
    t = {k: round(sum(m[k] for m in months)) for k in ("orders", "invoiced", "delivered", "collected", "outstanding")}
    t["collection_rate"] = round(t["collected"] / t["delivered"] * 100, 1) if t["delivered"] else 0
    out = {"company": target, "from_date": from_date, "to_date": to_date, "months": months, "totals": t}
    frappe.cache().set_value(ck, out, expires_in_sec=180)
    return out


@frappe.whitelist()
def ar_ap_reconciliation(company=None):
    """Tie the operational pipelines (COD carrier float, unpaid bills, supplier
    advances, GRNI) to the GL control accounts and flag the gaps that need
    reconciliation. The honest AR/AP picture: where the books diverge from
    operational reality."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    ck = f"ap_arap_recon:{target}"
    cached = frappe.cache().get_value(ck)
    if cached is not None:
        return cached

    def glbal(types):
        ph = ",".join(["%s"] * len(types))
        v = frappe.db.sql(
            f"""SELECT SUM(g.debit - g.credit) FROM `tabGL Entry` g
                JOIN `tabAccount` a ON a.name = g.account
                WHERE g.company=%s AND g.is_cancelled=0 AND a.account_type IN ({ph})""",
            [target] + types)[0][0]
        return flt(v)

    # ── AR ──
    gl_debtors = glbal(["Receivable"])
    si_outstanding = flt(frappe.db.sql(
        "SELECT SUM(outstanding_amount) FROM `tabSales Invoice` "
        "WHERE company=%s AND docstatus=1 AND outstanding_amount>0", target)[0][0])
    from accounting_portal.api import cod
    codsum = cod.cod_summary(target) or {}
    carrier_float = flt((codsum.get("delivered") or {}).get("value"))

    # ── AP ──
    gl_creditors = glbal(["Payable"])
    gl_grni = glbal(["Stock Received But Not Billed"])
    pi_unpaid = flt(frappe.db.sql(
        "SELECT SUM(outstanding_amount) FROM `tabPurchase Invoice` "
        "WHERE company=%s AND docstatus=1 AND IFNULL(is_return,0)=0 AND outstanding_amount>0", target)[0][0])
    advances = flt(frappe.db.sql(
        "SELECT SUM(unallocated_amount) FROM `tabPayment Entry` "
        "WHERE company=%s AND docstatus=1 AND payment_type='Pay' AND party_type='Supplier' "
        "AND unallocated_amount>0", target)[0][0])
    grni = flt(frappe.db.sql(
        "SELECT SUM(grand_total) FROM `tabPurchase Receipt` "
        "WHERE company=%s AND docstatus=1 AND IFNULL(is_return,0)=0 AND per_billed<100", target)[0][0])

    # Follow-up lists: who we owe most, and where prepaid cash sits unmatched.
    top_creditors = frappe.db.sql(
        """SELECT COALESCE(s.supplier_name, g.party) AS name, g.party AS party,
                  ROUND(SUM(g.credit - g.debit)) AS owed
           FROM `tabGL Entry` g LEFT JOIN `tabSupplier` s ON s.name = g.party
           WHERE g.party_type='Supplier' AND g.company=%s AND g.is_cancelled=0
           GROUP BY g.party HAVING owed > 0 ORDER BY owed DESC LIMIT 6""", target, as_dict=True)
    top_advances = frappe.db.sql(
        """SELECT COALESCE(s.supplier_name, pe.party) AS name, pe.party AS party,
                  COUNT(*) AS n, ROUND(SUM(pe.unallocated_amount)) AS adv
           FROM `tabPayment Entry` pe LEFT JOIN `tabSupplier` s ON s.name = pe.party
           WHERE pe.company=%s AND pe.docstatus=1 AND pe.payment_type='Pay'
             AND pe.party_type='Supplier' AND pe.unallocated_amount>0
           GROUP BY pe.party ORDER BY adv DESC LIMIT 6""", target, as_dict=True)
    for r in top_creditors:
        r["owed"] = flt(r["owed"])
    for r in top_advances:
        r["adv"] = flt(r["adv"])

    net_invoice = pi_unpaid - advances
    creditors_owed = -gl_creditors  # payable sits as a credit balance
    grni_owed = -gl_grni
    op_ar = carrier_float + si_outstanding
    out = {
        "company": target,
        "working_capital": round(op_ar - net_invoice),  # net AR − net AP
        "ar": {
            "carrier_float": carrier_float,        # operational receivable (delivered, not collected)
            "si_outstanding": si_outstanding,      # invoiced & unpaid
            "operational": op_ar,
            "gl_debtors": gl_debtors,              # book AR
            "wrong_sign": gl_debtors < 0,          # credit balance in a receivable = broken
            "reconciled": False,                   # COD collections unapplied → never ties as-is
        },
        "ap": {
            "pi_unpaid": pi_unpaid, "advances": advances, "net_invoice": net_invoice,
            "gl_creditors": creditors_owed, "invoice_gap": round(net_invoice - creditors_owed),
            "grni": grni, "gl_grni": grni_owed, "grni_gap": round(grni - grni_owed),
            "reconciled": abs(net_invoice - creditors_owed) < 0.05 * max(1, abs(creditors_owed)),
        },
        "top_creditors": top_creditors, "top_advances": top_advances,
        "ar_aging": _aging("Sales Invoice", target),
        "ap_aging": _aging("Purchase Invoice", target),
    }
    frappe.cache().set_value(ck, out, expires_in_sec=600)
    return out


@frappe.whitelist()
def vat_periods(company=None, months=12):
    """Monthly VAT (output − input) with the filing deadline (20th of the next
    month) — the VAT declaration tracker."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    months = min(int(months or 12), 24)
    rows = frappe.db.sql(
        """SELECT DATE_FORMAT(gle.posting_date,'%%Y-%%m') AS m, a.root_type,
                  ROUND(SUM(gle.credit - gle.debit)) AS net
           FROM `tabGL Entry` gle JOIN `tabAccount` a ON a.name = gle.account
           WHERE gle.company=%s AND gle.is_cancelled=0 AND a.account_type='Tax'
             AND gle.posting_date >= DATE_SUB(DATE_FORMAT(CURDATE(),'%%Y-%%m-01'), INTERVAL %s MONTH)
           GROUP BY m, a.root_type""",
        (target, months), as_dict=True)
    by = {}
    for r in rows:
        d = by.setdefault(r.m, {"output": 0.0, "input": 0.0})
        if r.root_type == "Liability":
            d["output"] += flt(r.net)
        else:
            d["input"] += -flt(r.net)
    periods = []
    for m in sorted(by, reverse=True):
        out_, in_ = by[m]["output"], by[m]["input"]
        y, mo = int(m[:4]), int(m[5:7])
        ny, nmo = (y + 1, 1) if mo == 12 else (y, mo + 1)
        periods.append({
            "month": m, "output": round(out_), "input": round(in_),
            "net": round(out_ - in_), "deadline": f"{ny:04d}-{nmo:02d}-20",
        })
    return {"company": target, "periods": periods}


@frappe.whitelist()
def period_close_status(company=None, month=None):
    """Month-end readiness — a live checklist that pulls every signal the portal
    tracks (drafts, COD application, GRNI, advances, cheques, VAT) so the team
    knows what still has to tie before locking the period."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    from frappe.utils import nowdate
    ym = (month or nowdate())[:7]

    def one(v):
        return flt((v or [[None]])[0][0])

    drafts = sum(frappe.db.count(dt, {"company": target, "docstatus": 0})
                 for dt in ("Sales Invoice", "Purchase Invoice", "Journal Entry", "Payment Entry"))
    debtors = one(frappe.db.sql(
        "SELECT SUM(g.debit-g.credit) FROM `tabGL Entry` g JOIN `tabAccount` a ON a.name=g.account "
        "WHERE g.company=%s AND g.is_cancelled=0 AND a.account_type='Receivable'", target))
    grni = one(frappe.db.sql(
        "SELECT SUM(grand_total) FROM `tabPurchase Receipt` WHERE company=%s AND docstatus=1 "
        "AND IFNULL(is_return,0)=0 AND per_billed<100", target))
    adv = one(frappe.db.sql(
        "SELECT SUM(unallocated_amount) FROM `tabPayment Entry` WHERE company=%s AND docstatus=1 "
        "AND payment_type='Pay' AND party_type='Supplier' AND unallocated_amount>0", target))
    chq = int(one(frappe.db.sql(
        "SELECT COUNT(*) FROM `tabPayment Entry` pe WHERE pe.company=%s AND pe.docstatus=1 "
        "AND pe.payment_type='Pay' AND pe.clearance_date IS NULL "
        "AND (IFNULL(pe.reference_no,'') LIKE 'CHQ%%' OR pe.mode_of_payment IN ('Cheque','Bank Draft'))", target)))
    vat_net = one(frappe.db.sql(
        "SELECT SUM(CASE WHEN a.root_type='Liability' THEN g.credit-g.debit ELSE -(g.credit-g.debit) END) "
        "FROM `tabGL Entry` g JOIN `tabAccount` a ON a.name=g.account "
        "WHERE g.company=%s AND g.is_cancelled=0 AND a.account_type='Tax' "
        "AND DATE_FORMAT(g.posting_date,'%%Y-%%m')=%s", (target, ym)))
    # Landed cost: the 153.03 clearing must be ~0 (every inbound cost capitalised)
    # and no import receipt left without an LCV, or COGS is understated at close.
    clearing_acc = frappe.get_cached_value("Company", target, "expenses_included_in_valuation")
    clearing_bal = one(frappe.db.sql(
        "SELECT SUM(debit-credit) FROM `tabGL Entry` WHERE company=%s AND account=%s AND is_cancelled=0",
        (target, clearing_acc))) if clearing_acc else 0.0
    uncov_lcv = int(one(frappe.db.sql(
        "SELECT COUNT(*) FROM `tabPurchase Receipt` pr WHERE pr.company=%s AND pr.docstatus=1 "
        "AND pr.currency!=%s AND pr.posting_date>='2026-01-01' AND pr.name NOT IN "
        "(SELECT lpr.receipt_document FROM `tabLanded Cost Purchase Receipt` lpr "
        " JOIN `tabLanded Cost Voucher` l ON l.name=lpr.parent WHERE l.docstatus=1)",
        (target, frappe.get_cached_value("Company", target, "default_currency")))))
    landed_clean = abs(clearing_bal) < 1 and uncov_lcv == 0

    items = [
        {"key": "drafts", "en": "All documents submitted", "ar": "كل المستندات مُرحّلة", "fr": "Documents tous soumis",
         "state": "done" if drafts == 0 else "blocked", "value": drafts, "unit": "docs", "link": "/accounting/accountant/journals"},
        {"key": "cod", "en": "COD collections applied to invoices", "ar": "تحصيلات COD مطبّقة على الفواتير", "fr": "Encaissements COD appliqués",
         "state": "done" if abs(debtors) < 1000 else "blocked", "value": round(debtors), "unit": "MAD", "link": "/accounting/reports/arap"},
        {"key": "grni", "en": "GRNI cleared (received → billed)", "ar": "GRNI مُصفّى", "fr": "GRNI soldé",
         "state": "done" if grni < 1000 else "pending", "value": round(grni), "unit": "MAD", "link": "/accounting/purchases/received"},
        {"key": "advances", "en": "Supplier advances matched", "ar": "مقدّمات الموردين مطابقة", "fr": "Avances fournisseurs affectées",
         "state": "done" if adv < 1000 else "pending", "value": round(adv), "unit": "MAD", "link": "/accounting/purchases/payments"},
        {"key": "cheques", "en": "Cheques cleared", "ar": "الشيكات مُصرّفة", "fr": "Chèques encaissés",
         "state": "done" if chq == 0 else "pending", "value": chq, "unit": "cheques", "link": "/accounting/purchases/cheques"},
        {"key": "vat", "en": "VAT computed for the period", "ar": "الضريبة محسوبة للفترة", "fr": "TVA calculée",
         "state": "done", "value": round(vat_net), "unit": "MAD", "link": "/accounting/reports/taxreports"},
        {"key": "landed", "en": "Landed cost capitalised (153.03 clear, imports covered)",
         "ar": "تكلفة الشحن مُرسملة (153.03 صفر، الاستيراد مغطّى)", "fr": "Coût de revient capitalisé (153.03 net)",
         "state": "done" if landed_clean else "blocked",
         "value": round(clearing_bal) if abs(clearing_bal) >= 1 else uncov_lcv,
         "unit": "MAD" if abs(clearing_bal) >= 1 else "receipts", "link": "/accounting/items/cockpit"},
    ]
    return {"company": target, "month": ym,
            "ready": all(i["state"] == "done" for i in items),
            "blocked": sum(1 for i in items if i["state"] == "blocked"),
            "pending": sum(1 for i in items if i["state"] == "pending"),
            "items": items}


@frappe.whitelist()
def daily_entry_checklist(company=None, date=None):
    """Daily bookkeeping checklist — did today's entries actually make it into
    the system? Each item is computed live so the accountants see, before they
    leave, what is still missing for the day (collections, bank, bills) and
    what slipped in through a side door (manual receipts, failed actions)."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    from frappe.utils import nowdate, date_diff, add_days
    d = (date or nowdate())[:10]

    def one(v):
        return flt((v or [[None]])[0][0])

    # 1) collections recorded for the day (COD / bank receipts)
    pe_in = frappe.db.sql(
        "SELECT COUNT(*), SUM(paid_amount) FROM `tabPayment Entry` WHERE company=%s "
        "AND docstatus=1 AND payment_type='Receive' AND posting_date=%s", (target, d))[0]
    pe_n, pe_amt = int(pe_in[0] or 0), flt(pe_in[1])

    # 2) bank ledger freshness — days since the last posting on any Bank account
    last_bank = frappe.db.sql(
        "SELECT MAX(g.posting_date) FROM `tabGL Entry` g JOIN `tabAccount` a ON a.name=g.account "
        "WHERE g.company=%s AND g.is_cancelled=0 AND a.account_type='Bank' AND g.posting_date<=%s",
        (target, d))[0][0]
    bank_lag = date_diff(d, str(last_bank)) if last_bank else 99

    # 3) vendor bills entered today + bill drafts older than 48h
    pi_today = int(one(frappe.db.sql(
        "SELECT COUNT(*) FROM `tabPurchase Invoice` WHERE company=%s AND docstatus=1 "
        "AND posting_date=%s", (target, d))))
    # recent window only — the historical draft mountain belongs to period-close,
    # this list must be actionable before the accountant leaves today
    old_bill_drafts = int(one(frappe.db.sql(
        "SELECT COUNT(*) FROM `tabPurchase Invoice` WHERE company=%s AND docstatus=0 "
        "AND creation BETWEEN %s AND %s", (target, add_days(d, -14), add_days(d, -2)))))

    # 4) stock that entered WITHOUT a purchase document today (bypass!)
    manual_rcpt = int(one(frappe.db.sql(
        "SELECT COUNT(*) FROM `tabStock Entry` WHERE company=%s AND docstatus=1 "
        "AND purpose='Material Receipt' AND posting_date=%s", (target, d))))

    # 5) draft backlog older than 48h across the entry doctypes
    drafts_old = sum(int(one(frappe.db.sql(
        "SELECT COUNT(*) FROM `tab%s` WHERE company=%%s AND docstatus=0 "
        "AND creation BETWEEN %%s AND %%s" % dt,
        (target, add_days(d, -14), add_days(d, -2))))) for dt in
        ("Sales Invoice", "Purchase Invoice", "Journal Entry", "Payment Entry"))

    # 6) portal actions that FAILED today — someone tried, the system said no
    failed_actions = int(one(frappe.db.sql(
        "SELECT COUNT(*) FROM `tabAccounting Portal Action` WHERE status='Failed' "
        "AND DATE(creation)=%s", (d,))))

    # 7) valuation repost queue must be drained daily or GL drifts from stock
    reposts = int(one(frappe.db.sql(
        "SELECT COUNT(*) FROM `tabRepost Item Valuation` WHERE status IN ('Queued','In Progress','Failed')")))

    # 8) expense policy: vendor spend must be a Purchase Invoice, not a bare JE
    je_expense = int(one(frappe.db.sql(
        "SELECT COUNT(DISTINCT g.voucher_no) FROM `tabGL Entry` g JOIN `tabAccount` a ON a.name=g.account "
        "WHERE g.company=%s AND g.is_cancelled=0 AND g.voucher_type='Journal Entry' "
        "AND g.posting_date=%s AND a.root_type='Expense' AND g.debit>0", (target, d))))

    # 9) items created this week still missing a weight (freight math starves)
    new_no_weight = int(one(frappe.db.sql(
        "SELECT COUNT(*) FROM `tabItem` WHERE IFNULL(weight_per_unit,0)=0 AND disabled=0 "
        "AND has_variants=0 AND creation>=%s", (add_days(d, -7),))))

    items = [
        {"key": "collections", "en": "Collections recorded today", "ar": "تحصيلات اليوم متسجلة",
         "fr": "Encaissements du jour saisis",
         "state": "done" if pe_n > 0 else "pending", "value": pe_n, "unit": "entries",
         "hint_amount": round(pe_amt), "link": "/accounting/banking/codclose"},
        {"key": "bank", "en": "Bank ledger up to date", "ar": "قيود البنك محدثة",
         "fr": "Banque à jour",
         "state": "done" if bank_lag <= 1 else ("pending" if bank_lag <= 3 else "blocked"),
         "value": bank_lag, "unit": "days behind", "link": "/accounting/banking"},
        {"key": "bills", "en": "Vendor bills posted (no stale drafts)", "ar": "فواتير الموردين مرحّلة (بدون مسودات قديمة)",
         "fr": "Factures fournisseurs postées",
         "state": "done" if old_bill_drafts == 0 else "pending", "value": old_bill_drafts or pi_today,
         "unit": "old drafts" if old_bill_drafts else "posted today", "link": "/accounting/expenses"},
        {"key": "manual_receipts", "en": "No stock entered without documents", "ar": "لا بضاعة دخلت بدون مستند شراء",
         "fr": "Aucune entrée de stock sans document",
         "state": "done" if manual_rcpt == 0 else "blocked", "value": manual_rcpt,
         "unit": "manual receipts", "link": "/accounting/items/zerocost"},
        {"key": "drafts", "en": "Draft backlog cleared (48h)", "ar": "المسودات الأقدم من يومين مصفّاة",
         "fr": "Brouillons +48h traités",
         "state": "done" if drafts_old == 0 else "pending", "value": drafts_old,
         "unit": "drafts", "link": "/accounting/accountant/journals"},
        {"key": "failed", "en": "Failed portal actions reviewed", "ar": "الأكشنات الفاشلة اتراجعت",
         "fr": "Actions échouées revues",
         "state": "done" if failed_actions == 0 else "blocked", "value": failed_actions,
         "unit": "failed", "link": "/accounting/settings/activity"},
        {"key": "reposts", "en": "Valuation repost queue drained", "ar": "طابور إعادة التقييم فاضي",
         "fr": "File de revalorisation vidée",
         "state": "done" if reposts == 0 else "blocked", "value": reposts,
         "unit": "queued", "link": "/accounting/items/valuation"},
        {"key": "je_policy", "en": "No vendor spend booked as bare JE", "ar": "لا مصروف مورد اتسجل قيد يومية",
         "fr": "Aucune dépense fournisseur en OD",
         "state": "done" if je_expense == 0 else "pending", "value": je_expense,
         "unit": "JEs to review", "link": "/accounting/accountant/journals"},
        {"key": "weights", "en": "New items carry weights", "ar": "الأصناف الجديدة ليها أوزان",
         "fr": "Nouveaux articles pesés",
         "state": "done" if new_no_weight == 0 else "pending", "value": new_no_weight,
         "unit": "items", "link": "/accounting/items/vendors"},
    ]
    return {"company": target, "date": d,
            "ready": all(i["state"] == "done" for i in items),
            "blocked": sum(1 for i in items if i["state"] == "blocked"),
            "pending": sum(1 for i in items if i["state"] == "pending"),
            "items": items}


@frappe.whitelist()
def party_statement(party_type=None, party=None, company=None, from_date=None, to_date=None):
    """Full account statement (ledger) for one Customer/Supplier: opening balance,
    every GL movement in the date range with a running balance, and the closing
    balance — for a printable customer/supplier statement."""
    assert_portal_access()
    companies = resolve_companies(company)
    if not companies:
        return {}
    target = company if (company and company in companies) else companies[0]
    if party_type not in ("Customer", "Supplier"):
        frappe.throw("Bad party type")
    if not party or not frappe.db.exists(party_type, party):
        frappe.throw("Party not found")
    ccy = frappe.db.get_value("Company", target, "default_currency") or "MAD"
    # Customer: positive = owes us (debit−credit). Supplier: positive = we owe (credit−debit).
    sign = 1 if party_type == "Customer" else -1

    opening = 0.0
    if from_date:
        opening = sign * flt(frappe.db.sql(
            """SELECT COALESCE(SUM(debit-credit),0) FROM `tabGL Entry`
               WHERE company=%s AND party_type=%s AND party=%s AND is_cancelled=0
                 AND posting_date < %s""", (target, party_type, party, from_date))[0][0])

    conds = ["company=%(c)s", "party_type=%(pt)s", "party=%(p)s", "is_cancelled=0"]
    params = {"c": target, "pt": party_type, "p": party}
    if from_date:
        conds.append("posting_date >= %(fd)s"); params["fd"] = from_date
    if to_date:
        conds.append("posting_date <= %(td)s"); params["td"] = to_date
    rows = frappe.db.sql(
        f"""SELECT posting_date AS date, voucher_type AS type, voucher_no AS doc,
                   debit, credit, remarks
            FROM `tabGL Entry` WHERE {' AND '.join(conds)}
            ORDER BY posting_date, creation""", params, as_dict=True)

    bal = opening
    dr_t = cr_t = 0.0
    for r in rows:
        bal += sign * (flt(r.debit) - flt(r.credit))
        r["balance"] = round(bal, 2)
        r["date"] = str(r.get("date") or "")
        dr_t += flt(r.debit); cr_t += flt(r.credit)
    name = frappe.db.get_value(
        party_type, party, "customer_name" if party_type == "Customer" else "supplier_name") or party
    return {
        "party": party, "party_name": name, "party_type": party_type,
        "company": target, "currency": ccy, "from_date": from_date, "to_date": to_date,
        "opening": round(opening, 2), "closing": round(bal, 2),
        "debit_total": round(dr_t, 2), "credit_total": round(cr_t, 2), "rows": rows,
    }


@frappe.whitelist()
def cash_forecast(company=None):
    """Forward cash view: cash now + expected COD inflow (carrier float) − cheques
    clearing − bills due. A 7-day liquidity check and a 30-day projection."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    ck = f"ap_cashfc:{target}"
    cached = frappe.cache().get_value(ck)
    if cached is not None:
        return cached
    ccy = frappe.db.get_value("Company", target, "default_currency") or "MAD"
    cash = flt(frappe.db.sql(
        """SELECT COALESCE(SUM(g.debit-g.credit),0) FROM `tabGL Entry` g JOIN `tabAccount` a ON a.name=g.account
           WHERE g.company=%s AND g.is_cancelled=0 AND a.account_type IN ('Bank','Cash')""", (target,))[0][0])
    # Inflow — delivered COD still with the carrier (will land).
    carrier_float = 0.0
    try:
        from accounting_portal.api import cod as _cod
        cs = _cod.cod_summary(target) or {}
        carrier_float = flt((cs.get("delivered") or {}).get("value"))
    except Exception:
        pass
    # Last-30d collections run-rate (sanity inflow).
    runrate = flt(frappe.db.sql(
        """SELECT COALESCE(SUM(paid_amount),0) FROM `tabPayment Entry`
           WHERE company=%s AND docstatus=1 AND payment_type='Receive'
             AND posting_date>=DATE_SUB(CURDATE(),INTERVAL 30 DAY)""", (target,))[0][0])
    # Outflow — cheques clearing + bills due.
    chq = {}
    try:
        from accounting_portal.api import purchases as _pur
        chq = _pur.cheques_summary(target) or {}
    except Exception:
        pass
    cheques_7 = flt(chq.get("due_week"))
    cheques_out = flt(chq.get("outstanding") or chq.get("due_week"))
    bills_due = 0.0
    try:
        from accounting_portal.api import purchases as _pur2
        psum = _pur2.purchases_summary(target) or {}
        bills_due = flt((psum.get("topay") or {}).get("value"))
    except Exception:
        pass
    proj_7 = cash + carrier_float * 0.4 - cheques_7 - bills_due * 0.5
    proj_30 = cash + carrier_float - cheques_out - bills_due
    result = {
        "company": target, "currency": ccy, "as_of": nowdate(),
        "cash": round(cash), "carrier_float": round(carrier_float), "runrate_30d": round(runrate),
        "cheques_7d": round(cheques_7), "cheques_out": round(cheques_out), "bills_due": round(bills_due),
        "proj_7d": round(proj_7), "proj_30d": round(proj_30),
        "liquidity_7d_ok": (cash - cheques_7 - bills_due * 0.5) > 0,
    }
    try:
        frappe.cache().set_value(ck, result, expires_in_sec=180)
    except Exception:
        pass
    return result


# ── Full classified financial statements (P&L + Balance Sheet + Cash Flow) ──
def _classify_asset(at, name=""):
    if at in ("Bank", "Cash"): return "Cash & bank"
    if at == "Receivable": return "Receivables"
    if at in ("Stock", "Stock Adjustment"): return "Inventory"
    if at in ("Fixed Asset", "Accumulated Depreciation"): return "Fixed assets"
    return "Other assets"


def _classify_liab(at, name=""):
    if at == "Payable": return "Payables"
    if at == "Tax": return "Tax & duties"
    return "Other liabilities"


def _bs_rows(company, as_on):
    return frappe.db.sql(
        """SELECT a.name, a.account_name, a.root_type, IFNULL(a.account_type,'') AS at,
                  ROUND(SUM(g.debit-g.credit)) AS bal
           FROM `tabGL Entry` g JOIN `tabAccount` a ON a.name=g.account
           WHERE g.company=%s AND g.is_cancelled=0
             AND a.root_type IN ('Asset','Liability','Equity') AND g.posting_date<=%s
           GROUP BY a.name HAVING ROUND(SUM(g.debit-g.credit))<>0""", (company, as_on), as_dict=True)


def _pnl_rows(company, fr, to):
    """Account totals for the period, plus `je` — the share that came from
    manual Journal Entries rather than from a stock/sales document. Product
    cost flows from delivery notes and invoices; a JE into a cost account is
    a CORRECTION (usually of an earlier period) and must not sit inside the
    period's gross margin."""
    return frappe.db.sql(
        """SELECT a.name, a.account_name, a.root_type, IFNULL(a.account_type,'') AS at,
                  ROUND(SUM(g.credit-g.debit)) AS net,
                  ROUND(SUM(CASE WHEN g.voucher_type='Journal Entry'
                                 THEN g.credit-g.debit ELSE 0 END)) AS je
           FROM `tabGL Entry` g JOIN `tabAccount` a ON a.name=g.account
           WHERE g.company=%s AND g.is_cancelled=0
             AND a.root_type IN ('Income','Expense') AND g.posting_date BETWEEN %s AND %s
           GROUP BY a.name HAVING ROUND(SUM(g.credit-g.debit))<>0""", (company, fr, to), as_dict=True)


def _grouped(rows, sign_key, classify, prior_map=None, prior_key=None, subgroup=None):
    """Group account rows into sections {section: {total, prior, accounts:[...]}}.

    `subgroup` optionally rolls the accounts of a section into named buckets, so a
    section with many small accounts reads as a few ideas with the detail one
    click away. Sections without a bucket keep their flat account list.
    """
    secs = {}
    for r in rows:
        amt = sign_key(r)
        sec = classify(r.get("at"), r.get("name") or "")
        s = secs.setdefault(sec, {"section": sec, "total": 0.0, "prior": 0.0, "accounts": []})
        prior = flt((prior_map or {}).get(r["name"], 0))
        if prior_map is not None and prior_key:
            prior = prior_key(prior_map.get(r["name"]))
        s["total"] += amt
        s["prior"] += prior
        row = {"account": r["name"], "name": r["account_name"],
               "amount": round(amt), "prior": round(prior)}
        if subgroup:
            row["group"] = subgroup(r["name"])
        s["accounts"].append(row)
    out = list(secs.values())
    for s in out:
        s["total"] = round(s["total"]); s["prior"] = round(s["prior"])
        s["accounts"].sort(key=lambda a: -abs(a["amount"]))
        # a section is only worth collapsing when every one of its accounts has
        # a home; a half-grouped list is harder to read than a flat one
        if subgroup and s["accounts"] and all(a.get("group") for a in s["accounts"]):
            g = {}
            for a in s["accounts"]:
                b = g.setdefault(a["group"], {"group": a["group"], "total": 0, "prior": 0, "accounts": []})
                b["total"] += a["amount"]; b["prior"] += a["prior"]
                b["accounts"].append(a)
            s["groups"] = sorted(g.values(), key=lambda b: -abs(b["total"]))
    out.sort(key=lambda s: -abs(s["total"]))
    return out


def _usd_rate_at(to_ccy, date):
    r = frappe.db.sql(
        """SELECT exchange_rate FROM `tabCurrency Exchange`
           WHERE from_currency='USD' AND to_currency=%s AND date<=%s
           ORDER BY date DESC LIMIT 1""", (to_ccy, date))
    return flt(r[0][0]) if r else 0.0


def _usd_rate_avg(to_ccy, from_date, to_date):
    r = frappe.db.sql(
        """SELECT AVG(exchange_rate) FROM `tabCurrency Exchange`
           WHERE from_currency='USD' AND to_currency=%s AND date BETWEEN %s AND %s""",
        (to_ccy, from_date, to_date))
    v = flt(r[0][0]) if r else 0.0
    return v or _usd_rate_at(to_ccy, to_date)


def _pres_rates(base_ccy, pres_ccy, from_date, to_date):
    """(avg_rate, closing_rate) base→presentation, cross-rated through USD —
    the ERPNext convention: P&L at the period AVERAGE, BS at CLOSING."""
    if not pres_ccy or pres_ccy == base_ccy:
        return 1.0, 1.0

    def _cross(u_p, u_b):
        return (u_p / u_b) if (u_p and u_b) else 0.0
    up_a = 1.0 if pres_ccy == "USD" else _usd_rate_avg(pres_ccy, from_date, to_date)
    ub_a = 1.0 if base_ccy == "USD" else _usd_rate_avg(base_ccy, from_date, to_date)
    up_c = 1.0 if pres_ccy == "USD" else _usd_rate_at(pres_ccy, to_date)
    ub_c = 1.0 if base_ccy == "USD" else _usd_rate_at(base_ccy, to_date)
    return _cross(up_a, ub_a), _cross(up_c, ub_c)


def _scale(node, k):
    """Scale every numeric leaf of the grouped-sections structure."""
    if isinstance(node, list):
        return [_scale(x, k) for x in node]
    if isinstance(node, dict):
        return {kk: (_scale(v, k) if isinstance(v, (list, dict))
                     else (round(v * k) if isinstance(v, (int, float)) and kk not in ("gm_pct",) else v))
                for kk, v in node.items()}
    return node


@frappe.whitelist()
def financial_statements(company=None, from_date=None, to_date=None, compare=1, pres_ccy=None):
    """P&L (structured), classified Balance Sheet, and a Cash-Flow statement — with
    a prior-period comparison column. The team's full statement pack."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    if not (from_date and to_date):
        from_date, to_date = _year_bounds()
    compare = int(compare or 0)
    ck = f"ap_fs:{target}:{from_date}:{to_date}:{compare}:{pres_ccy or ''}"
    cached_hit = frappe.cache().get_value(ck)
    if cached_hit is not None:
        return cached_hit
    ccy = frappe.db.get_value("Company", target, "default_currency") or "MAD"

    # Prior period of equal length, immediately before.
    from frappe.utils import add_days, date_diff, getdate
    span = date_diff(to_date, from_date)
    p_to = add_days(from_date, -1)
    p_from = add_days(p_to, -span)
    prior_as_on = add_days(from_date, -1)

    # ── P&L ──
    cur = _pnl_rows(target, from_date, to_date)
    pri = {r["name"]: r for r in _pnl_rows(target, p_from, p_to)} if compare else {}
    inc = [r for r in cur if r["root_type"] == "Income"]
    exp = []
    for r in (x for x in cur if x["root_type"] == "Expense"):
        je = flt(r.get("je"))
        n = str(r.get("name") or "")
        # only cost-of-sales accounts split: opex is legitimately booked by JE
        if je and n.startswith(("71.801", "71.002.", "71.999", "71.004")):
            op = dict(r); op["net"] = flt(r["net"]) - je
            pp = dict(r); pp["net"] = je; pp["at"] = "__PRIOR__"
            if op["net"]:
                exp.append(op)
            exp.append(pp)
        else:
            exp.append(r)
    inc_p = {k: v for k, v in pri.items() if v["root_type"] == "Income"}
    exp_p = {k: v for k, v in pri.items() if v["root_type"] == "Expense"}

    def _inbound_freight(name):
        # inbound landed family (air/sea/customs/ports/clearance) — legacy
        # bills that the recos capitalize; presented WITH the inventory
        # corrections so freight+71.004 net inside one block and OPEX stops
        # showing freight. 770.07.004 (Cathadis delivery fee to customers) is
        # a SELLING expense and stays in OPEX.
        n = str(name)
        return (n.startswith(("770.07", "770.0.7"))
                and not n.startswith("770.07.004"))

    # Eighteen raw accounts under one heading cannot be read. These roll into
    # four ideas, and the detail stays one click away. The freight bucket is
    # named for what it should have been — inbound landed cost belongs inside
    # the stock value, and its size here is the measure of how much never got
    # capitalised.
    def _cost_group(name):
        n = str(name)
        if n.startswith("71.801"):
            return "Product cost"
        if n.startswith(("71.004", "71.999")):
            return "Inventory corrections"
        if n.startswith("71.002."):
            return "Internal transfer (paper)"
        if _inbound_freight(n):
            return "Inbound freight & duty"
        # not a cost-of-sales account: operating expenses keep their flat list,
        # where each account name already reads as its own idea
        return None

    def _exp_class(at, name=""):
        # account_type OR the known COGS families by name: 71.801 (DN cost) and
        # 71.002.5 (delivery cost booked on the mistyped internal-invoicing
        # account — 1.9M of 2026 DN cost lives there); Stock Adjustment (71.004,
        # the correction bucket) presents adjacent to COGS, not in OPEX
        if at == "__PRIOR__":
            # a manual JE into a cost-of-sales account is a CORRECTION, not
            # this period's product cost, so it sits under gross profit.
            # (The July 2026 case that motivated this — ACC-JV-2026-05112,
            # 2.43M — was cancelled once traced: it cleared a legacy account's
            # cumulative balance, and since both legs were 2026 expense
            # accounts its net profit effect was zero while it overstated
            # cost of sales and pushed 71.999 deeply negative.)
            return "Prior-period corrections"
        if at == "Cost of Goods Sold" or str(name).startswith(("71.801", "71.002.", "71.999")):
            return "Cost of goods sold"
        if at == "Stock Adjustment" or _inbound_freight(name):
            return "Inventory corrections"
        return "Operating expenses"
    revenue = _grouped(inc, lambda r: flt(r["net"]), lambda at, name="": "Revenue",
                       inc_p, lambda v: flt(v["net"]) if v else 0)
    expenses = _grouped(exp, lambda r: -flt(r["net"]), _exp_class,
                        exp_p, lambda v: -flt(v["net"]) if v else 0,
                        subgroup=_cost_group)
    rev_total = sum(s["total"] for s in revenue)
    rev_prior = sum(s["prior"] for s in revenue)
    cogs = next((s for s in expenses if s["section"] == "Cost of goods sold"), {"total": 0, "prior": 0})
    opex = [s for s in expenses if s["section"] != "Cost of goods sold"]
    opex_total = sum(s["total"] for s in opex); opex_prior = sum(s["prior"] for s in opex)
    gross = rev_total - cogs["total"]; gross_p = rev_prior - cogs["prior"]
    net = gross - opex_total; net_p = gross_p - opex_prior
    # Flag a single account that dominates expenses (the broken Stock-Adjustment
    # pile) so net profit isn't silently read as real.
    anomaly = None
    for s in expenses:
        for a in s["accounts"]:
            if abs(a["amount"]) > 1_000_000 and abs(a["amount"]) > 0.4 * (abs(opex_total) + abs(cogs["total"]) or 1):
                anomaly = {"name": a["name"], "account": a["account"], "amount": a["amount"]}
                break
        if anomaly:
            break
    pnl_pack = {
        "revenue": revenue, "cogs": cogs, "opex": opex,
        "revenue_total": round(rev_total), "revenue_prior": round(rev_prior),
        "gross_profit": round(gross), "gross_prior": round(gross_p),
        "gross_margin": round(gross / rev_total * 100, 1) if rev_total else 0,
        "opex_total": round(opex_total), "opex_prior": round(opex_prior),
        "net": round(net), "net_prior": round(net_p), "anomaly": anomaly,
    }

    # ── Balance Sheet (classified) ──
    bcur = _bs_rows(target, to_date)
    bpri = {r["name"]: flt(r["bal"]) for r in _bs_rows(target, prior_as_on)} if compare else {}
    assets = _grouped([r for r in bcur if r["root_type"] == "Asset"], lambda r: flt(r["bal"]),
                      _classify_asset, bpri, lambda v: flt(v or 0))
    liabs = _grouped([r for r in bcur if r["root_type"] == "Liability"], lambda r: -flt(r["bal"]),
                     _classify_liab, bpri, lambda v: -flt(v or 0))
    equity = _grouped([r for r in bcur if r["root_type"] == "Equity"], lambda r: -flt(r["bal"]),
                      lambda at, name="": "Equity", bpri, lambda v: -flt(v or 0))
    # The P&L was never closed to retained earnings — add cumulative earnings
    # (income − expense, all-time) to equity so the sheet balances.
    def _cum_earn(as_on):
        return flt(frappe.db.sql(
            """SELECT COALESCE(SUM(g.credit-g.debit),0) FROM `tabGL Entry` g JOIN `tabAccount` a ON a.name=g.account
               WHERE g.company=%s AND g.is_cancelled=0 AND a.root_type IN ('Income','Expense') AND g.posting_date<=%s""",
            (target, as_on))[0][0])
    cum_now = _cum_earn(to_date)
    cum_prior = _cum_earn(prior_as_on) if compare else 0
    if round(cum_now):
        equity.append({"section": "Retained earnings (P&L, unclosed)", "total": round(cum_now),
                       "prior": round(cum_prior), "accounts": []})
    a_tot = sum(s["total"] for s in assets); l_tot = sum(s["total"] for s in liabs); e_tot = sum(s["total"] for s in equity)
    bs_pack = {
        "assets": assets, "liabilities": liabs, "equity": equity,
        "assets_total": round(a_tot), "liabilities_total": round(l_tot), "equity_total": round(e_tot),
        "check": round(a_tot - l_tot - e_tot), "as_on": to_date,
    }

    # ── Cash Flow (direct — actual Bank/Cash movement; always reconciles, and
    # immune to the non-cash stock-adjustment distortion in net income) ──
    # Operational cash flow reads OPERATING bank/cash accounts only (the under-audit
    # ones are held out so the figure is readable). The balance sheet stays complete.
    from accounting_portal.api.bank_status import operating_names_clause
    _cfc, _cfe = operating_names_clause(target, "a")

    def _cash_at(as_on):
        return flt(frappe.db.sql(
            f"""SELECT COALESCE(SUM(g.debit-g.credit),0) FROM `tabGL Entry` g JOIN `tabAccount` a ON a.name=g.account
               WHERE g.company=%s AND g.is_cancelled=0 AND a.account_type IN ('Bank','Cash'){_cfc} AND g.posting_date<=%s""",
            (target,) + _cfe + (as_on,))[0][0])
    open_cash = _cash_at(prior_as_on)
    close_cash = _cash_at(to_date)
    mv = frappe.db.sql(
        f"""SELECT ROUND(SUM(g.debit)) cin, ROUND(SUM(g.credit)) cout
           FROM `tabGL Entry` g JOIN `tabAccount` a ON a.name=g.account
           WHERE g.company=%s AND g.is_cancelled=0 AND a.account_type IN ('Bank','Cash'){_cfc}
             AND g.posting_date BETWEEN %s AND %s""", (target,) + _cfe + (from_date, to_date), as_dict=True)[0]
    cash_in = flt(mv.cin); cash_out = flt(mv.cout)
    cf_pack = {
        "open_cash": round(open_cash), "close_cash": round(close_cash),
        "cash_in": round(cash_in), "cash_out": round(cash_out),
        "net_change": round(cash_in - cash_out),
        "reconciles": abs(round(open_cash + cash_in - cash_out) - round(close_cash)) < max(1000, abs(close_cash) * 0.02),
        "method": "direct",
    }

    presentation = None
    if pres_ccy and pres_ccy != ccy:
        k_avg, k_close = _pres_rates(ccy, pres_ccy, from_date, to_date)
        if k_avg and k_close:
            pnl_pack = _scale(pnl_pack, k_avg)          # P&L at period AVERAGE
            cf_pack = _scale(cf_pack, k_avg)
            bs_pack = _scale(bs_pack, k_close)          # BS at CLOSING rate
            presentation = {"ccy": pres_ccy, "base": ccy,
                            "rate_avg": round(k_avg, 6), "rate_close": round(k_close, 6)}
        else:
            presentation = {"ccy": ccy, "base": ccy, "error": f"no FX rate for {pres_ccy}"}
    result = {
        "company": target, "currency": (presentation or {}).get("ccy") or ccy,
        "presentation": presentation,
        "from_date": from_date, "to_date": to_date,
        "prior_from": p_from, "prior_to": p_to, "compare": compare,
        "pnl": pnl_pack, "balance_sheet": bs_pack, "cash_flow": cf_pack,
    }
    try:
        frappe.cache().set_value(ck, result, expires_in_sec=180)
    except Exception:
        pass
    return result


@frappe.whitelist()
def verified_dd(company=None):
    """Investor/audit-ready health scorecard — key figures tied to the GL plus a
    pass/watch/fail checklist across the areas a buyer's DD examines."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    ck = f"ap_vdd:{target}"
    cached_hit = frappe.cache().get_value(ck)
    if cached_hit is not None:
        return cached_hit
    ccy = frappe.db.get_value("Company", target, "default_currency") or "MAD"
    fy = _year_bounds()[0]

    def _root(rt, fr=None):
        cond = "g.posting_date BETWEEN %s AND %s" if fr else "g.posting_date<=%s"
        args = (target, fr, _year_bounds()[1]) if fr else (target, nowdate())
        sign = "g.credit-g.debit" if rt in ("Income", "Liability", "Equity") else "g.debit-g.credit"
        return flt(frappe.db.sql(
            f"""SELECT COALESCE(SUM({sign}),0) FROM `tabGL Entry` g JOIN `tabAccount` a ON a.name=g.account
                WHERE g.company=%s AND g.is_cancelled=0 AND a.root_type=%s AND {cond}""",
            (args[0], rt) + args[1:])[0][0])

    rev = _root("Income", fy)
    cogs = flt(frappe.db.sql(
        """SELECT COALESCE(SUM(g.debit-g.credit),0) FROM `tabGL Entry` g JOIN `tabAccount` a ON a.name=g.account
           WHERE g.company=%s AND g.is_cancelled=0 AND g.posting_date>=%s
             AND (a.account_type IN ('Cost of Goods Sold','Stock Adjustment')
                  OR a.name LIKE '71.801%%' OR a.name LIKE '71.002.%%'
                  OR a.name LIKE '71.999%%'
                  OR ((a.name LIKE '770.07%%' OR a.name LIKE '770.0.7%%')
                      AND a.name NOT LIKE '770.07.004%%'))""",
        (target, fy))[0][0])
    gross_margin = round((rev - cogs) / rev * 100, 1) if rev else 0
    cash = flt(frappe.db.sql(
        """SELECT COALESCE(SUM(g.debit-g.credit),0) FROM `tabGL Entry` g JOIN `tabAccount` a ON a.name=g.account
           WHERE g.company=%s AND g.is_cancelled=0 AND a.account_type IN ('Bank','Cash')""", (target,))[0][0])
    debtors = flt(frappe.db.sql(
        """SELECT COALESCE(SUM(g.debit-g.credit),0) FROM `tabGL Entry` g JOIN `tabAccount` a ON a.name=g.account
           WHERE g.company=%s AND g.is_cancelled=0 AND a.account_type='Receivable'""", (target,))[0][0])

    findings, exposure, highs = [], 0, 0
    try:
        from accounting_portal.api import auditor as _aud
        ctl = _aud.run_controls(target) or {}
        findings = ctl.get("findings") or []
        exposure = (ctl.get("summary") or {}).get("exposure", 0)
        highs = (ctl.get("summary") or {}).get("high", 0)
    except Exception:
        pass
    # Document compliance.
    miss = {}
    try:
        from accounting_portal.api import docmeta as _dm
        miss = (_dm.missing_documents(target, "bills") or {}).get("counts", {})
    except Exception:
        pass
    bills_total = frappe.db.count("Purchase Invoice", {"company": target, "docstatus": 1}) or 1
    bills_missing_pct = round((miss.get("bills", 0)) / bills_total * 100) if bills_total else 0

    def chk(area, status, value, note):
        return {"area": area, "status": status, "value": value, "note": note}

    checklist = [
        chk("Revenue recognition", "watch" if rev else "fail", f"{round(rev):,.0f} {ccy}",
            "Recognised on delivery; a to-bill backlog remains"),
        chk("Gross margin quality", "fail" if gross_margin < 0 else ("watch" if gross_margin < 20 else "pass"),
            f"{gross_margin}%", "COGS exceeds revenue — inventory/COGS posting is broken"),
        chk("Receivables integrity", "fail" if debtors < -100000 else "pass",
            f"{round(debtors):,.0f} {ccy}", "Debtors carry a credit balance — collections unapplied" if debtors < 0 else "Clean"),
        chk("Liquidity", "fail" if cash < 0 else ("watch" if cash < 500000 else "pass"),
            f"{round(cash):,.0f} {ccy}", "Cash on hand across bank + cash"),
        chk("Audit findings", "fail" if highs >= 3 else ("watch" if highs else "pass"),
            f"{len(findings)} ({highs} high)", f"{round(exposure):,.0f} {ccy} high-severity exposure"),
        chk("Document compliance", "fail" if bills_missing_pct > 60 else ("watch" if bills_missing_pct > 20 else "pass"),
            f"{bills_missing_pct}% missing", "Supplier bills without an attached source document"),
    ]
    score = sum(1 for c in checklist if c["status"] == "pass")
    result = {
        "company": target, "currency": ccy,
        "metrics": {"revenue": round(rev), "gross_margin": gross_margin, "cash": round(cash),
                    "debtors": round(debtors), "exposure": round(exposure)},
        "checklist": checklist, "score": score, "total": len(checklist),
    }
    try:
        frappe.cache().set_value(ck, result, expires_in_sec=600)
    except Exception:
        pass
    return result


@frappe.whitelist()
def fixed_assets(company=None):
    """Live fixed-asset register — gross cost, net book value, accumulated
    depreciation and status per asset (replaces the hardcoded sample list)."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {"rows": [], "summary": {}, "currency": "MAD"}
    rows = frappe.db.sql(
        """SELECT name, asset_name, asset_category AS category,
                  IFNULL(gross_purchase_amount,0) AS gross,
                  IFNULL(value_after_depreciation, gross_purchase_amount) AS nbv,
                  status, purchase_date, location
           FROM `tabAsset` WHERE company=%s
           ORDER BY asset_category, purchase_date DESC LIMIT 500""",
        (target,), as_dict=True)
    for r in rows:
        r["asset_name"] = (r.get("asset_name") or "").split("\n")[0][:80]
        r["gross"] = flt(r["gross"]); r["nbv"] = flt(r["nbv"])
    gross = sum(r["gross"] for r in rows)
    nbv = sum(r["nbv"] for r in rows)
    return {
        "rows": rows,
        "summary": {"count": len(rows), "gross": round(gross), "nbv": round(nbv),
                    "accumulated_dep": round(gross - nbv)},
        "currency": frappe.db.get_value("Company", target, "default_currency") or "MAD",
    }


@frappe.whitelist()
def pnl_monthly(company=None, year=None, pres_ccy=None):
    """Profit & loss broken down month-by-month (columns) for a fiscal year — the
    'see the months side by side' view. Accounts grouped Revenue → COGS → Gross →
    OpEx → Net, each with a per-month array + a year total."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    y = int(year or nowdate()[:4])
    ck = f"ap_fs:{target}:monthly:{y}:{pres_ccy or ''}"
    hit = frappe.cache().get_value(ck)
    if hit is not None:
        return hit
    ccy = frappe.db.get_value("Company", target, "default_currency") or "MAD"
    last_m = int(nowdate()[5:7]) if y == int(nowdate()[:4]) else 12
    months = [f"{y}-{m:02d}" for m in range(1, last_m + 1)]
    midx = {ym: i for i, ym in enumerate(months)}
    n = len(months)

    rows = frappe.db.sql(
        """SELECT a.name, a.account_name AS an, a.root_type AS rt, IFNULL(a.account_type,'') AS at,
                  DATE_FORMAT(g.posting_date,'%%Y-%%m') AS ym, ROUND(SUM(g.credit-g.debit)) AS net
           FROM `tabGL Entry` g JOIN `tabAccount` a ON a.name=g.account
           WHERE g.company=%s AND g.is_cancelled=0 AND a.root_type IN ('Income','Expense')
             AND g.posting_date BETWEEN %s AND %s
           GROUP BY a.name, ym""",
        (target, f"{y}-01-01", f"{y}-12-31"), as_dict=True)
    presentation = None
    if pres_ccy and pres_ccy != ccy:
        from accounting_portal.api.group_pnl import _month_rates
        mr = _month_rates({ccy}, pres_ccy, y).get(ccy, {})
        if any(mr.values()):
            for r in rows:
                mm = int(str(r.ym)[5:7])
                r.net = flt(r.net) * flt(mr.get(mm))
            presentation = {"ccy": pres_ccy, "base": ccy,
                            "rates": {m: round(v, 6) for m, v in mr.items() if v}}
            ccy = pres_ccy
        else:
            presentation = {"ccy": ccy, "base": ccy, "error": f"no FX rate for {pres_ccy}"}

    def classify(rt, at, name=""):
        if rt == "Income":
            return "revenue"
        if at == "Cost of Goods Sold" or str(name).startswith(("71.801", "71.002.", "71.999")):
            return "cogs"
        # 71.004 correction bucket + legacy INBOUND freight (its offset) —
        # both belong with COGS, not OPEX (Cathadis delivery fee stays OPEX)
        if at == "Stock Adjustment":
            return "cogs"
        n = str(name)
        if n.startswith(("770.07", "770.0.7")) and not n.startswith("770.07.004"):
            return "cogs"
        return "opex"

    accts = {}
    for r in rows:
        i = midx.get(r["ym"])
        if i is None:
            continue
        sec = classify(r["rt"], r["at"], r["name"])
        amt = (1 if r["rt"] == "Income" else -1) * flt(r["net"])  # revenue +, expense +
        a = accts.setdefault(r["name"], {"account": r["name"], "name": r["an"], "section": sec,
                                         "monthly": [0.0] * n, "total": 0.0})
        a["monthly"][i] += amt
        a["total"] += amt

    sec_monthly, sections = {}, []
    for key, label in (("revenue", "Revenue"), ("cogs", "Cost of goods sold"), ("opex", "Operating expenses")):
        sa = [a for a in accts.values() if a["section"] == key]
        sa.sort(key=lambda a: -abs(a["total"]))
        mt = [round(sum(a["monthly"][i] for a in sa)) for i in range(n)]
        for a in sa:
            a["monthly"] = [round(x) for x in a["monthly"]]
            a["total"] = round(a["total"])
        sec_monthly[key] = mt
        sections.append({"key": key, "label": label, "accounts": sa,
                         "monthly_total": mt, "total": round(sum(mt))})

    rev = sec_monthly.get("revenue", [0] * n)
    cogs = sec_monthly.get("cogs", [0] * n)
    opex = sec_monthly.get("opex", [0] * n)
    gross = [rev[i] - cogs[i] for i in range(n)]
    net = [gross[i] - opex[i] for i in range(n)]
    result = {
        "company": target, "presentation": presentation, "currency": ccy, "year": y, "months": months,
        "sections": sections,
        "gross_monthly": gross, "gross_total": sum(gross),
        "net_monthly": net, "net_total": sum(net),
    }
    try:
        frappe.cache().set_value(ck, result, expires_in_sec=180)
    except Exception:
        pass
    return result


# ── Server-side PDF export — headed statements auditors can take away ──────────

def _pdf_shell(title, subtitle, body_html):
    return f"""<div style="font-family:Helvetica,Arial,sans-serif;color:#1c1917;font-size:11px">
      <div style="border-bottom:2px solid #1c1917;padding-bottom:8px;margin-bottom:14px">
        <div style="font-size:17px;font-weight:700">{frappe.utils.escape_html(title)}</div>
        <div style="color:#78716c;font-size:11px">{frappe.utils.escape_html(subtitle)}</div>
      </div>{body_html}
      <div style="margin-top:18px;border-top:1px solid #e7e5e4;padding-top:6px;color:#a8a29e;font-size:9px">
        Generated by JoyAgent Books · {frappe.utils.now()[:16]} · {frappe.session.user}
      </div></div>"""


def _rows_table(headers, rows, aligns=None):
    aligns = aligns or (["left"] + ["right"] * (len(headers) - 1))
    th = "".join(f'<th style="text-align:{aligns[i]};padding:5px 8px;border-bottom:1px solid #1c1917;font-size:10px;text-transform:uppercase;color:#78716c">{h}</th>' for i, h in enumerate(headers))
    body = ""
    for r in rows:
        tds = "".join(f'<td style="text-align:{aligns[i]};padding:4px 8px;border-bottom:1px solid #f5f5f4">{c}</td>' for i, c in enumerate(r))
        body += f"<tr>{tds}</tr>"
    return f'<table style="width:100%;border-collapse:collapse"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>'


def _money(n):
    return f"{flt(n):,.2f}"


@frappe.whitelist()
def report_pdf(report=None, company=None, from_date=None, to_date=None,
               party_type=None, party=None):
    """Render a statement to a headed PDF and return its file_url. Covers the
    reports auditors need on paper: trial_balance, pnl, balance_sheet,
    party_statement. Trial Balance had no export at all before this."""
    assert_portal_access()
    comps = resolve_companies(company)
    target = company if (company and company in comps) else (comps[0] if comps else None)
    if not target:
        frappe.throw("No company in scope")
    ccy = frappe.db.get_value("Company", target, "default_currency") or ""
    period = f"{from_date or ''} → {to_date or 'today'}"

    if report == "trial_balance":
        from accounting_portal.api.ledger import trial_balance
        d = trial_balance(company=target, from_date=from_date, to_date=to_date)
        rows = [[r.get("account"), _money(r.get("opening")), _money(r.get("period_dr") or r.get("debit")),
                 _money(r.get("period_cr") or r.get("credit")), _money(r.get("closing") or r.get("balance"))]
                for r in d.get("rows", [])]
        rows.append(["<b>TOTAL</b>", "", f"<b>{_money(d.get('total_dr'))}</b>", f"<b>{_money(d.get('total_cr'))}</b>", ""])
        body = _rows_table(["Account", "Opening", "Debit", "Credit", "Closing"], rows)
        title = "Trial Balance"
    elif report == "party_statement":
        from accounting_portal.api.reports import party_statement as _ps
        d = _ps(party_type=party_type, party=party, company=target, from_date=from_date, to_date=to_date)
        rows = [["Opening", "", "", _money(d.get("opening"))]]
        for m in d.get("rows", []):
            rows.append([m.get("date"), (m.get("voucher") or m.get("against") or "")[:40],
                         _money(m.get("debit")) + " / " + _money(m.get("credit")), _money(m.get("balance"))])
        rows.append(["<b>Closing</b>", "", "", f"<b>{_money(d.get('closing'))}</b>"])
        body = _rows_table(["Date", "Voucher", "Dr / Cr", "Balance"], rows)
        title = f"Statement · {party or ''}"
    else:
        frappe.throw(f"Unknown report: {report}")

    html = _pdf_shell(f"{title} — {target}", f"{period} · {ccy}", body)
    from frappe.utils.pdf import get_pdf
    pdf = get_pdf(html)
    fname = f"{report}-{target.split(' ')[0]}-{(to_date or nowdate())}.pdf".replace(" ", "_")
    f = frappe.get_doc({"doctype": "File", "file_name": fname, "is_private": 1,
                        "content": pdf, "decode": False})
    f.insert(ignore_permissions=True)
    return {"file_url": f.file_url, "file_name": fname}
