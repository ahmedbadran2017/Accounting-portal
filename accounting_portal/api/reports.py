"""Financial reports — P&L, balance sheet, AR/AP aging, VAT.

All read-only, entity-scoped, and validated against the live books. Heavy GL
aggregates are bounded by company + period. Account-level rows are returned so
the team sees exactly where each number comes from (and the auditor's anomalies,
like the stock-adjustment pile in the P&L, stay visible rather than hidden).
"""
import frappe
from frappe.utils import flt, nowdate

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
    stock = flt(frappe.db.sql(
        """SELECT ROUND(SUM(gle.debit - gle.credit)) FROM `tabGL Entry` gle
           JOIN `tabAccount` a ON a.name=gle.account
           WHERE gle.company=%s AND gle.is_cancelled=0 AND a.account_type='Stock'""",
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
    return {
        "company": target, "stock_in_hand": stock, "adjustment_account": adj_acct,
        "adjustment_balance": adj_bal, "revenue": revenue,
        "distortion": abs(stock) + abs(adj_bal),
        "healthy": abs(stock) < 50_000_000,
    }


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
    # Collected = the Cathedis ref is on the order OR its invoice (the book's
    # matching stamps the invoice), so join the CATH-stamped invoices.
    so = frappe.db.sql(
        """SELECT DATE_FORMAT(so.transaction_date,'%%Y-%%m') m,
                  COUNT(*) orders,
                  ROUND(SUM(so.grand_total)) order_value,
                  ROUND(SUM(CASE WHEN IFNULL(so.custom_reference_number,'') LIKE 'CATH%%' OR inv.so IS NOT NULL THEN so.grand_total ELSE 0 END)) collected,
                  ROUND(SUM(CASE WHEN IFNULL(so.custom_reference_number,'') LIKE 'CATH%%' OR inv.so IS NOT NULL
                                  OR so.custom_track_shipment_status='Delivered' THEN so.grand_total ELSE 0 END)) delivered
           FROM `tabSales Order` so
           LEFT JOIN (SELECT DISTINCT sii.sales_order so FROM `tabSales Invoice Item` sii
                      JOIN `tabSales Invoice` si ON si.name=sii.parent
                      WHERE si.company=%(c)s AND si.docstatus=1
                        AND IFNULL(si.custom_reference_number,'') LIKE 'CATH%%'
                        AND IFNULL(sii.sales_order,'')!='') inv ON inv.so=so.name
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
    frappe.cache().set_value(ck, out, expires_in_sec=300)
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
    ]
    return {"company": target, "month": ym,
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
