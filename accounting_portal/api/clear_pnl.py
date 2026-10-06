"""Clear P&L — the group's result for a period, read the way an owner reads it.

    sales − (opening stock + purchases − closing stock) − expenses = result

Why this exists. The monthly views disagree because each prices the goods sold
differently: the booked ledger (polluted unit costs, stock write-ups), the cost
model (what goods *should* cost), and the old /pnl-2026 page (hand-uploaded
courier files, inbound freight left out, an imputed Turkish VAT refund added as
income). This one never prices an individual sale. It takes what came in, what
is left, and what was spent — every figure straight from the ledger — so the
only judgement in it is the value of the stock, and that is shown on its own.

Perimeter: the group. Morocco sells; Maslak (Türkiye) and Justyol China only
source. Intercompany sales and receipts between them are left out entirely —
goods enter at what the group paid outside (Maslak's Turkish suppliers, China's
suppliers, Morocco's own suppliers), never at a transfer price.

Goods purchases are measured on RECEIPT (Purchase Receipt lines, plus stock
bought directly on an invoice), because stock is valued from those same
receipts: counting the invoice instead would put a 2025 receipt billed in 2026
into this year's purchases while it already sits in the opening stock.

VAT: off = everything net of VAT. On = sales as the customer paid them, input
VAT on third-party invoices as part of what purchases cost, and the VAT actually
settled with the state as a cost. Read-only.
"""
import calendar

import frappe
from frappe.utils import flt, getdate, add_days, nowdate

from accounting_portal.api.permissions import assert_portal_access

JM, ML, JC = "Justyol Morocco", "Maslak LTD", "Justyol China"
GROUP = (JM, ML, JC, "Justyol Holding")
_CACHE = "ap_clear_pnl:v1:"


# ── account classification (same rules as the investor pack) ─────────────────
def _cat(company, name, root):
    k = (name or "").split(" ")[0]
    if company == JM:
        if root == "Income":
            if k.startswith("600.998"): return "nonsale"
            if k.startswith("600.902"): return "other_income"
            return "sales"
        if k.startswith("71.005"): return "packaging"
        if k.startswith("71."): return "goods_booked"          # replaced by the stock movement
        if k.startswith(("770.07.004", "770.07.005", "770.07.008", "770.04.005")): return "courier"
        if k.startswith(("770.07", "770.0.7")): return "freight"
        if k.startswith("760"): return "marketing"
        if k.startswith(("720", "708")): return "payroll"
        if k.startswith(("770.01", "770.001")): return "premises"
        if k.startswith("770.09.07"): return "tax"
        if k.startswith(("78.401", "78.801")): return "fx_finance"
        if k.startswith("78.301"): return "bank_fees"
        return "admin"
    # Maslak / China: sourcing entities — their revenue and goods legs are intercompany
    if k.startswith(("67.001", "999.", "9.")): return "excluded"     # owner's private / "no effect" invoices
    if root == "Income": return "ic"
    if k.startswith("71."): return "ic"
    if k.startswith("760"): return "marketing"
    if k.startswith(("720", "708")): return "payroll"
    if k.startswith(("770.01", "770.001")): return "premises"
    if k.startswith(("770.07", "770.0.7")): return "freight"
    if k.startswith("770.09.07"): return "tax"
    if k.startswith(("78.401", "78.801")): return "fx_finance"
    if k.startswith("78.301"): return "bank_fees"
    return "admin"


def _period(year, from_month, to_month):
    y = int(year or nowdate()[:4])
    fm = max(1, min(12, int(from_month or 1)))
    if to_month:
        tm = int(to_month)
    else:  # default: the last complete month of the year asked for
        today = getdate(nowdate())
        tm = 12 if y < today.year else max(1, today.month - 1)
    tm = max(fm, min(12, tm))
    start = f"{y}-{fm:02d}-01"
    end = f"{y}-{tm:02d}-{calendar.monthrange(y, tm)[1]:02d}"
    return y, fm, tm, start, end


def _rates(y):
    from accounting_portal.api.group_pnl import _month_rates
    usd = _month_rates({"MAD", "TRY", "USD"}, "USD", y)       # ccy -> USD per month
    mad = {}
    for m in range(1, 13):
        u_mad = flt(usd["MAD"][m]) or 0.105263
        mad[m] = {"MAD": 1.0, "TRY": flt(usd["TRY"][m]) / u_mad, "USD": 1 / u_mad, "MAD_USD": u_mad}
    return mad


def _stock_at(company, date):
    return flt(frappe.db.sql("""SELECT IFNULL(SUM(stock_value_difference),0) FROM `tabStock Ledger Entry`
                                WHERE company=%s AND is_cancelled=0 AND posting_date<=%s""", (company, date))[0][0])


def _pool_at(date):
    return flt(frappe.db.sql("""SELECT IFNULL(SUM(debit-credit),0) FROM `tabGL Entry`
                                WHERE company=%s AND is_cancelled=0 AND account LIKE '153.03%%' AND posting_date<=%s""",
                             (JM, date))[0][0])


@frappe.whitelist()
def clear_pnl(year=None, from_month=None, to_month=None, vat=1, fresh=0):
    assert_portal_access()
    y, fm, tm, start, end = _period(year, from_month, to_month)
    vat = 1 if str(vat) in ("1", "true", "True") else 0
    key = f"{_CACHE}{y}:{fm}:{tm}:{vat}"
    if not int(fresh or 0):
        hit = frappe.cache().get_value(key)
        if hit:
            return hit
    R = _rates(y)
    args = {"s": start, "e": end, "ic": GROUP}

    # ── ledger: income and expenses by category, MAD ──────────────────────────
    cat = {}
    by_co = {}
    for co in (JM, ML, JC):
        ccy = {JM: "MAD", ML: "TRY", JC: "USD"}[co]
        for r in frappe.db.sql("""SELECT a.name, a.root_type rt, MONTH(g.posting_date) m, SUM(g.credit-g.debit) v
                                  FROM `tabGL Entry` g JOIN `tabAccount` a ON a.name=g.account
                                  WHERE g.company=%(c)s AND g.is_cancelled=0 AND a.root_type IN ('Income','Expense')
                                    AND g.posting_date BETWEEN %(s)s AND %(e)s
                                  GROUP BY a.name, a.root_type, MONTH(g.posting_date)""", {**args, "c": co}, as_dict=True):
            c = _cat(co, r.name, r.rt)
            v = flt(r.v) * R[int(r.m)][ccy]
            if r.rt == "Expense":
                v = -v                                   # costs as positive numbers
            cat[c] = cat.get(c, 0) + v
            by_co.setdefault(c, {}).setdefault(co, 0)
            by_co[c][co] += v

    # ── goods purchases on receipt, from third parties only ───────────────────
    def q(sql, extra=None):
        return frappe.db.sql(sql, {**args, **(extra or {})}, as_dict=True)
    goods = []
    # Morocco: stock received (Purchase Receipt lines, returns netted)
    jm_rec = q("""SELECT IF(s.country='Morocco' OR pr.supplier IN (SELECT name FROM `tabSupplier` WHERE supplier_group LIKE '%%Morocco%%'),'local','import') src,
                         MONTH(pr.posting_date) m, SUM(pri.base_net_amount) v
                  FROM `tabPurchase Receipt` pr JOIN `tabPurchase Receipt Item` pri ON pri.parent=pr.name
                  LEFT JOIN `tabSupplier` s ON s.name=pr.supplier
                  WHERE pr.company='Justyol Morocco' AND pr.docstatus=1 AND pr.supplier NOT IN %(ic)s
                    AND pr.posting_date BETWEEN %(s)s AND %(e)s GROUP BY src, m""")
    for src in ("import", "local"):
        goods.append({"key": f"jm_receipts_{src}",
                      "label": {"import": "Morocco — imported goods received (third-party suppliers)",
                                "local": "Morocco — goods received from Moroccan suppliers"}[src],
                      "amount": sum(flt(r.v) for r in jm_rec if r.src == src)})
    # Morocco: stock bought straight on an invoice (no receipt) + goods lines booked to cost of goods
    jm_inv = q("""SELECT SUM(CASE WHEN IFNULL(i.is_stock_item,0)=1 AND IFNULL(pii.pr_detail,'')='' THEN pii.base_net_amount
                                  WHEN IFNULL(i.is_stock_item,0)=0 AND pii.expense_account LIKE '71.%%'
                                       AND pii.expense_account NOT LIKE '71.005%%' AND pii.expense_account NOT LIKE '71.004%%' THEN pii.base_net_amount
                                  ELSE 0 END) goods,
                         SUM(CASE WHEN IFNULL(i.is_stock_item,0)=0 AND pii.expense_account LIKE '153.03%%' THEN pii.base_net_amount ELSE 0 END) pool
                  FROM `tabPurchase Invoice` pi JOIN `tabPurchase Invoice Item` pii ON pii.parent=pi.name LEFT JOIN `tabItem` i ON i.name=pii.item_code
                  WHERE pi.company='Justyol Morocco' AND pi.docstatus=1 AND pi.supplier NOT IN %(ic)s
                    AND pi.posting_date BETWEEN %(s)s AND %(e)s""")[0]
    goods.append({"key": "jm_invoiced_goods", "label": "Morocco — goods billed without a receipt (local sellers, direct invoices)",
                  "amount": flt(jm_inv.goods)})
    # Maslak: Turkish goods at what Maslak paid (receipts + direct stock invoices), TRY → MAD by month
    ml_rec = q("""SELECT MONTH(pr.posting_date) m, SUM(pri.base_net_amount) v FROM `tabPurchase Receipt` pr
                  JOIN `tabPurchase Receipt Item` pri ON pri.parent=pr.name
                  WHERE pr.company='Maslak LTD' AND pr.docstatus=1 AND pr.supplier NOT IN %(ic)s
                    AND pr.posting_date BETWEEN %(s)s AND %(e)s GROUP BY m""")
    ml_inv = q("""SELECT MONTH(pi.posting_date) m, SUM(pii.base_net_amount) v FROM `tabPurchase Invoice` pi
                  JOIN `tabPurchase Invoice Item` pii ON pii.parent=pi.name JOIN `tabItem` i ON i.name=pii.item_code
                  WHERE pi.company='Maslak LTD' AND pi.docstatus=1 AND pi.supplier NOT IN %(ic)s AND i.is_stock_item=1
                    AND IFNULL(pii.pr_detail,'')='' AND pi.posting_date BETWEEN %(s)s AND %(e)s GROUP BY m""")
    goods.append({"key": "ml_goods", "label": "Türkiye — goods bought from Turkish suppliers (Maslak's cost)",
                  "amount": sum(flt(r.v) * R[int(r.m)]["TRY"] for r in ml_rec + ml_inv)})
    # China: goods received at the MU hubs, USD → MAD
    jc_rec = q("""SELECT MONTH(pr.posting_date) m, SUM(pri.base_net_amount) v FROM `tabPurchase Receipt` pr
                  JOIN `tabPurchase Receipt Item` pri ON pri.parent=pr.name
                  WHERE pr.company='Justyol China' AND pr.docstatus=1 AND pr.supplier NOT IN %(ic)s
                    AND pr.posting_date BETWEEN %(s)s AND %(e)s GROUP BY m""")
    goods.append({"key": "jc_goods", "label": "China — goods received at the MU hubs",
                  "amount": sum(flt(r.v) * R[int(r.m)]["USD"] for r in jc_rec)})
    goods_total = sum(g["amount"] for g in goods)
    freight = [{"key": "freight_expensed", "label": "Inbound freight, customs and port charges (expensed)",
                "amount": cat.get("freight", 0)},
               {"key": "freight_capitalised", "label": "Inbound freight charged to stock (153.03)", "amount": flt(jm_inv.pool)}]
    freight_total = sum(f["amount"] for f in freight)

    # ── stock: subledger at cost + the unallocated landed-cost pool ───────────
    d0 = add_days(start, -1)
    r0, r1 = (R[12] if fm == 1 else R[fm - 1]), R[tm]
    if fm == 1:   # opening rates = the previous December
        r0 = _rates(y - 1)[12]
    stock = []
    for key, label, fn, ccy in (("jm", "Morocco — warehouses", lambda d: _stock_at(JM, d), "MAD"),
                                ("pool", "Morocco — freight paid on stock, not yet in item cost (153.03)", _pool_at, "MAD"),
                                ("ml", "Türkiye — physical stock", lambda d: _stock_at(ML, d), "TRY"),
                                ("jc", "China — MU hubs", lambda d: _stock_at(JC, d), "USD")):
        o, c = fn(str(d0)), fn(end)
        stock.append({"key": key, "label": label, "currency": ccy, "open_own": round(o), "close_own": round(c),
                      "open": o * r0[ccy], "close": c * r1[ccy]})
    open_total = sum(s["open"] for s in stock)
    close_total = sum(s["close"] for s in stock)

    # ── VAT ──────────────────────────────────────────────────────────────────
    from accounting_portal.api import vat_gross
    vg = vat_gross.by_month(JM, start, end)
    vat_out = sum(flt(v["in_price"]) for v in vg.values())
    vat_settled = sum(flt(v["paid"]) for v in vg.values())
    vat_in = flt(frappe.db.sql("""SELECT IFNULL(SUM(base_total_taxes_and_charges),0) FROM `tabPurchase Invoice`
                                  WHERE company='Justyol Morocco' AND docstatus=1 AND supplier NOT IN %(ic)s
                                    AND posting_date BETWEEN %(s)s AND %(e)s AND IFNULL(base_total_taxes_and_charges,0)>0""",
                               args)[0][0])

    # ── the statement ─────────────────────────────────────────────────────────
    sales_net = cat.get("sales", 0)
    sales = sales_net + (vat_out if vat else 0)
    purchases = goods_total + freight_total + (vat_in if vat else 0)
    cogs = open_total + purchases - close_total
    gross = sales - cogs
    EXP = [("payroll", "Payroll (Morocco + Türkiye team)"), ("marketing", "Marketing and ads"),
           ("courier", "Delivery to customers (Cathedis)"), ("premises", "Rent, warehouses and premises"),
           ("admin", "Admin, subscriptions and professional fees"), ("packaging", "Packaging"),
           ("bank_fees", "Bank and payment fees")]
    expenses = [{"key": k, "label": lbl, "amount": cat.get(k, 0),
                 "morocco": by_co.get(k, {}).get(JM, 0), "turkiye": by_co.get(k, {}).get(ML, 0) + by_co.get(k, {}).get(JC, 0)}
                for k, lbl in EXP]
    if vat:
        expenses.append({"key": "vat_settled", "label": "VAT paid to the tax office", "amount": vat_settled,
                         "morocco": vat_settled, "turkiye": 0})
    exp_total = sum(e["amount"] for e in expenses)
    other_income = cat.get("other_income", 0)
    operating = gross - exp_total + other_income
    below = [{"key": "tax", "label": "Advance corporate tax", "amount": -cat.get("tax", 0)},
             {"key": "fx_finance", "label": "Exchange differences and finance cost", "amount": -cat.get("fx_finance", 0)}]
    net = operating + sum(b["amount"] for b in below)

    # the ladder: where the result turns
    jm_ = lambda k: by_co.get(k, {}).get(JM, 0)
    tr_ = lambda k: by_co.get(k, {}).get(ML, 0) + by_co.get(k, {}).get(JC, 0)
    on_goods = gross - cat.get("courier", 0) - jm_("marketing")
    morocco_op = on_goods - sum(jm_(k) for k in ("payroll", "premises", "admin", "packaging", "bank_fees")) \
        - (vat_settled if vat else 0) + other_income
    turk = sum(tr_(k) for k in ("payroll", "marketing", "premises", "admin", "bank_fees"))
    ladder = [{"key": "on_goods", "label": "Profit on goods (after delivery and Morocco ads)", "amount": on_goods},
              {"key": "morocco_op", "label": "Morocco operation (after its payroll, rent and admin)", "amount": morocco_op},
              {"key": "turkiye", "label": "Türkiye sourcing and marketing team", "amount": -turk},
              {"key": "operating", "label": "Operating result", "amount": operating},
              {"key": "net", "label": "Net result", "amount": net}]

    # ── how far to trust it ───────────────────────────────────────────────────
    flags = []
    months = tm - fm + 1
    for k, lbl in (("payroll", "Morocco payroll"), ("courier", "Cathedis fees")):
        rows = frappe.db.sql("""SELECT MONTH(g.posting_date) m, SUM(g.debit-g.credit) v FROM `tabGL Entry` g
                                JOIN `tabAccount` a ON a.name=g.account WHERE g.company=%s AND g.is_cancelled=0
                                AND a.root_type='Expense' AND g.posting_date BETWEEN %s AND %s
                                AND a.name LIKE %s GROUP BY MONTH(g.posting_date)""",
                             (JM, start, end, "720%" if k == "payroll" else "770.07.004%"), as_dict=True)
        mv = {int(r.m): flt(r.v) for r in rows}
        vals = sorted(v for v in mv.values() if v > 0)
        if len(vals) >= 3:
            med = vals[len(vals) // 2]
            thin = [calendar.month_abbr[m] for m in range(fm, tm + 1) if mv.get(m, 0) < 0.5 * med]
            if thin:
                flags.append({"level": "warn", "text": f"{lbl} looks incomplete in {', '.join(thin)} — month not closed; costs understated."})
    drafts = {dt: frappe.db.count(dt, {"company": JM, "docstatus": 0, "posting_date": ["between", [start, end]]})
              for dt in ("Purchase Invoice", "Payment Entry", "Journal Entry")}
    if sum(drafts.values()):
        flags.append({"level": "info", "text": "Unposted drafts in the period: " +
                      ", ".join(f"{n} {dt}" for dt, n in drafts.items() if n) + " — not in these figures."})
    flags.append({"level": "warn", "text": "Closing stock is the ledger value, not a count. Goods received from Türkiye "
                  "in early 2026 carry an exchange-rate error in their cost; a physical count valued at supplier "
                  "cost is what settles the cost of goods sold."})

    usd = sum(R[m]["MAD_USD"] for m in range(fm, tm + 1)) / months
    out = {"year": y, "from_month": fm, "to_month": tm, "start": start, "end": end, "vat": vat,
           "usd_rate": usd, "months": months,
           "sales": {"net": sales_net, "vat": vat_out, "total": sales},
           "purchases": {"goods": goods, "goods_total": goods_total, "freight": freight, "freight_total": freight_total,
                         "vat_in": vat_in if vat else 0, "total": purchases},
           "stock": {"lines": stock, "open": open_total, "close": close_total, "change": close_total - open_total},
           "cogs": cogs, "gross": gross, "expenses": expenses, "expenses_total": exp_total,
           "other_income": other_income, "operating": operating, "below": below, "net": net,
           "ladder": ladder, "flags": flags,
           "excluded": {"intercompany_revenue": cat.get("ic", 0), "nonsale_vat_recovery": cat.get("nonsale", 0),
                        "owner_private": cat.get("excluded", 0), "booked_cost_of_goods": cat.get("goods_booked", 0)}}
    frappe.cache().set_value(key, out, expires_in_sec=600)
    return out
