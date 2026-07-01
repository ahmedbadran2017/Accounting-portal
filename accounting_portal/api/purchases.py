"""Purchases endpoints — live ERPNext, entity-scoped.

Purchase Invoice = bills (3-way match vs PO + Goods Receipt). Lists are scoped
to one company and exclude cancelled docs. The 3-way match flag is derived from
whether every line is linked to a Purchase Order (and a receipt).
"""
import json

import frappe
from frappe.utils import flt, nowdate

from accounting_portal.api import _actions, _paginate
from accounting_portal.api.permissions import assert_can_write, assert_portal_access, resolve_companies
from accounting_portal.api.sales import _voucher_journal


def _bill_status(row):
    """Normalise ERPNext Purchase Invoice status → portal vocabulary."""
    if row.get("is_return"):
        return "ret"
    s = (row.get("status") or "").strip()
    if s in ("Overdue", "Unpaid"):
        return "overdue"
    return "paid"


_BILL_SORT = {"date": "pi.posting_date", "amount": "pi.grand_total", "supplier": "pi.supplier", "id": "pi.name"}


@frappe.whitelist()
def list_bills(company=None, search=None, from_date=None, to_date=None, start=0, page_size=25, sort_field="date", sort_dir="desc"):
    """Bills for one company with a derived 3-way-match flag, server-paginated."""
    assert_portal_access()
    companies = resolve_companies(company)
    if not companies:
        return {"rows": [], "total": 0}
    target = company if (company and company in companies) else companies[0]
    currency = frappe.db.get_value("Company", target, "default_currency")
    conds = ["pi.company = %(company)s", "pi.docstatus = 1"]
    params = {"company": target}
    if from_date:
        conds.append("pi.posting_date >= %(fd)s"); params["fd"] = from_date
    if to_date:
        conds.append("pi.posting_date <= %(td)s"); params["td"] = to_date
    if search:
        conds.append("(pi.name LIKE %(s)s OR pi.supplier LIKE %(s)s OR pi.bill_no LIKE %(s)s)")
        params["s"] = f"%{search}%"
    col = _BILL_SORT.get(sort_field, "pi.posting_date")
    d = "ASC" if str(sort_dir).lower() == "asc" else "DESC"
    rows, total, s, ps = _paginate.page_query(
        "`tabPurchase Invoice` pi", " AND ".join(conds), params,
        "pi.name, pi.supplier, pi.grand_total, pi.base_grand_total, pi.currency AS doc_currency, "
        "pi.is_return, pi.status, pi.posting_date AS date, pi.bill_no, "
        "(SELECT COUNT(*) FROM `tabPurchase Invoice Item` it WHERE it.parent = pi.name) AS n_items, "
        "(SELECT COUNT(*) FROM `tabPurchase Invoice Item` it WHERE it.parent = pi.name AND IFNULL(it.purchase_order,'')<>'') AS n_po",
        f"{col} {d}, pi.creation {d}", start, page_size)
    for r in rows:
        # Each bill shows its OWN transaction currency (USD/TRY suppliers), not the
        # company default — otherwise a USD bill reads as "MAD <usd amount>".
        r["currency"] = r.get("doc_currency") or currency
        r["base_currency"] = currency
        r["status_norm"] = _bill_status(r)
        # 3-way matched when every line ties back to a PO; else a match exception.
        r["match"] = "ok" if (r["n_items"] and r["n_po"] == r["n_items"]) else "exc"
        r["amount"] = flt(r["grand_total"]) * (-1 if r["is_return"] else 1)
        # Base-currency amount (company currency) for any cross-bill totals.
        r["base_amount"] = flt(r["base_grand_total"]) * (-1 if r["is_return"] else 1)
    return {"rows": rows, "total": total, "start": s, "page_size": ps}


@frappe.whitelist()
def get_bill(name):
    """One bill: header, 3-way-match legs (PO / receipt / invoice), posted journal."""
    assert_portal_access()
    pi = frappe.db.get_value(
        "Purchase Invoice", name,
        ["name", "supplier", "company", "grand_total", "base_grand_total", "currency",
         "outstanding_amount", "is_return", "status", "posting_date", "due_date", "bill_no"], as_dict=True,
    )
    if not pi:
        frappe.throw("Bill not found")
    if pi.company not in resolve_companies():
        frappe.throw("Not permitted", frappe.PermissionError)
    items = frappe.db.sql(
        """SELECT pii.item_name AS name, pii.item_code, pii.custom_sku AS sku, i.image,
                  pii.qty, pii.rate, pii.amount,
                  IFNULL(pii.purchase_order, '') AS po, IFNULL(pii.purchase_receipt, '') AS pr
           FROM `tabPurchase Invoice Item` pii
           LEFT JOIN `tabItem` i ON i.name = pii.item_code
           WHERE pii.parent = %s ORDER BY pii.idx""",
        (name,), as_dict=True,
    )
    n = len(items)
    has_po = n and all(i.po for i in items)
    has_pr = n and all(i.pr for i in items)
    pi["items"] = items
    pi["match"] = {"po": bool(has_po), "grn": bool(has_pr), "matched": bool(has_po and has_pr)}
    pi["status_norm"] = _bill_status(pi)
    pi["related_orders"] = sorted({i.po for i in items if i.po})
    pi["related_receipts"] = sorted({i.pr for i in items if i.pr})
    pi["related_payments"] = [r.name for r in frappe.db.sql(
        """SELECT DISTINCT parent AS name FROM `tabPayment Entry Reference`
           WHERE reference_doctype='Purchase Invoice' AND reference_name=%s""", (name,), as_dict=True)]
    pi["journal"] = _voucher_journal(name)
    return pi


@frappe.whitelist()
def list_vendors(company=None, limit=60):
    """Top suppliers for one company ranked by outstanding payable (GL party
    balance). Powers the Vendors cards — live, with a real payable figure."""
    assert_portal_access()
    companies = resolve_companies(company)
    if not companies:
        return []
    target = company if (company and company in companies) else companies[0]
    currency = frappe.db.get_value("Company", target, "default_currency") or "MAD"
    rows = frappe.db.sql(
        """
        SELECT g.party AS name, COALESCE(s.supplier_name, g.party) AS supplier_name,
               s.supplier_group,
               ROUND(SUM(g.credit - g.debit)) AS payable,
               (SELECT COUNT(*) FROM `tabPurchase Invoice` pi
                  WHERE pi.supplier = g.party AND pi.company = %(c)s AND pi.docstatus = 1) AS n_bills
        FROM `tabGL Entry` g
        LEFT JOIN `tabSupplier` s ON s.name = g.party
        WHERE g.party_type = 'Supplier' AND g.company = %(c)s AND g.is_cancelled = 0
        GROUP BY g.party
        HAVING ABS(SUM(g.credit - g.debit)) > 0
        ORDER BY payable DESC
        LIMIT %(limit)s
        """,
        {"c": target, "limit": min(int(limit or 60), 200)}, as_dict=True,
    )
    for r in rows:
        r["currency"] = currency
    return rows


@frappe.whitelist()
def get_supplier(name, company=None):
    """Full supplier detail: header, computed stats, contact, connections, and
    the supplier ledger (GL party entries) — the purchase-cycle counterpart of
    get_customer. Everything is scoped to the selected company so the figures
    tie with list_vendors in the multi-company group."""
    assert_portal_access()
    s = frappe.db.get_value(
        "Supplier", name,
        ["name", "supplier_name", "supplier_group", "supplier_type",
         "country", "default_currency", "tax_id", "creation"], as_dict=True)
    if not s:
        frappe.throw("Supplier not found")
    target = _target(company)
    if not target:
        frappe.throw("Not permitted", frappe.PermissionError)
    ccy = s.default_currency or frappe.db.get_value("Company", target, "default_currency") or "MAD"

    # GL party balance for THIS company (credit−debit > 0 ⇒ we owe the supplier).
    payable = flt(frappe.db.sql(
        """SELECT COALESCE(SUM(credit - debit), 0) FROM `tabGL Entry`
           WHERE party_type='Supplier' AND party=%s AND company=%s AND is_cancelled=0""",
        (name, target))[0][0])

    bills = frappe.db.sql(
        """SELECT COUNT(*) AS n, ROUND(SUM(grand_total)) AS billed,
                  ROUND(SUM(outstanding_amount)) AS outstanding
           FROM `tabPurchase Invoice` WHERE supplier=%s AND company=%s AND docstatus=1""",
        (name, target), as_dict=True)[0]
    n_pos = frappe.db.count("Purchase Order", {"supplier": name, "company": target, "docstatus": 1})
    n_pe = frappe.db.count("Payment Entry", {"party_type": "Supplier", "party": name, "company": target, "docstatus": 1})
    n_grn = frappe.db.count("Purchase Receipt", {"supplier": name, "company": target, "docstatus": 1})

    ledger = frappe.db.sql(
        """SELECT posting_date AS date, voucher_no AS doc, voucher_type AS type,
                  debit AS dr, credit AS cr
           FROM `tabGL Entry`
           WHERE party_type='Supplier' AND party=%s AND company=%s AND is_cancelled=0
           ORDER BY posting_date DESC, creation DESC LIMIT 10""", (name, target), as_dict=True)
    running = payable
    for e in ledger:
        e["balance"] = round(running, 2)
        running -= (flt(e["cr"]) - flt(e["dr"]))

    return {
        "name": s.name, "supplier_name": s.supplier_name or s.name,
        "group": s.supplier_group, "type": s.supplier_type, "country": s.country,
        "tax_id": s.tax_id, "currency": ccy, "company": target,
        "since": str(s.creation)[:4] if s.creation else "—",
        "payable": payable,
        "stats": {"billed": flt(bills.billed), "n_bills": bills.n or 0,
                  "outstanding": flt(bills.outstanding), "payable": payable},
        "connections": {"bills": bills.n or 0, "pos": n_pos, "receipts": n_grn, "payments": n_pe},
        "ledger": ledger,
    }


# ── Procure-to-pay pipeline (To Buy → Received → Billed → To Pay → Paid) ──
def _target(company):
    companies = resolve_companies(company)
    if not companies:
        return None
    return company if (company and company in companies) else companies[0]


def _fy_start():
    from frappe.utils import getdate, nowdate
    return getdate(nowdate()).replace(month=1, day=1).isoformat()


# bucket -> (doctype, condition, date field, due field, value expr, has_return)
# Value exprs are in COMPANY (base) currency so cross-document sums are valid for
# USD/TRY suppliers: base_grand_total for PO/PR/paid; outstanding_amount is already
# stored in company currency.
_PURCH = {
    "tobuy":    ("Purchase Order",   "per_received < 100",                                          "transaction_date", "schedule_date", "base_grand_total",   False),
    "received": ("Purchase Receipt", "per_billed < 100",                                            "posting_date",     "NULL",          "base_grand_total",   True),
    "billed":   ("Purchase Invoice", "outstanding_amount > 0 AND due_date > CURDATE()",             "posting_date",     "due_date",      "outstanding_amount", True),
    "topay":    ("Purchase Invoice", "outstanding_amount > 0 AND (due_date <= CURDATE() OR due_date IS NULL)", "posting_date", "due_date", "outstanding_amount", True),
    "paid":     ("Purchase Invoice", "outstanding_amount <= 0",                                     "posting_date",     "due_date",      "base_grand_total",   True),
}
PURCH_BUCKETS = ("tobuy", "received", "billed", "topay", "paid")


def _purch_where(bucket, params, search=False, from_date=None, to_date=None):
    dt, cond, date_f, _due, _val, has_ret = _PURCH[bucket]
    conds = ["company=%(c)s", "docstatus=1", f"({cond})", f"{date_f} >= %(fy)s"]
    if has_ret:
        conds.append("IFNULL(is_return,0)=0")
    if from_date:
        conds.append(f"{date_f} >= %(fd)s"); params["fd"] = from_date
    if to_date:
        conds.append(f"{date_f} <= %(td)s"); params["td"] = to_date
    if search:
        conds.append("(name LIKE %(s)s OR supplier LIKE %(s)s OR IFNULL(supplier_name,'') LIKE %(s)s)")
    return dt, date_f, _due, _val, " AND ".join(conds)


@frappe.whitelist()
def purchases_summary(company=None, from_date=None, to_date=None):
    """Count + value per procure-to-pay stage (current fiscal year, optional range)."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    ck = f"ap_purch_summary:{target}:{from_date or ''}:{to_date or ''}"
    cached = frappe.cache().get_value(ck)
    if cached is not None:
        return cached
    out = {}
    for b in PURCH_BUCKETS:
        params = {"c": target, "fy": _fy_start()}
        dt, _df, _due, val, where = _purch_where(b, params, from_date=from_date, to_date=to_date)
        r = frappe.db.sql(f"SELECT COUNT(*) n, ROUND(SUM({val})) val FROM `tab{dt}` WHERE {where}",
                          params, as_dict=True)[0]
        out[b] = {"count": r.n or 0, "value": flt(r.val)}
    out["currency"] = frappe.db.get_value("Company", target, "default_currency") or "MAD"
    frappe.cache().set_value(ck, out, expires_in_sec=600)
    return out


@frappe.whitelist()
def list_purchase_bucket(company=None, bucket="topay", search=None, from_date=None, to_date=None, limit=500):
    """Documents in one procure-to-pay stage. Each stage is a different doctype:
    To Buy = Purchase Order, Received = Purchase Receipt, Billed/To Pay/Paid =
    Purchase Invoice (split by due date / payment status)."""
    assert_portal_access()
    target = _target(company)
    if not target or bucket not in _PURCH:
        return {"count": 0, "value": 0, "rows": []}
    params = {"c": target, "fy": _fy_start(), "limit": min(int(limit or 500), 1000)}
    if search:
        params["s"] = f"%{search}%"
    dt, date_f, due_f, val, where = _purch_where(bucket, params, search=bool(search), from_date=from_date, to_date=to_date)
    # progress / owed differs by doctype
    prog = {"tobuy": "per_received", "received": "per_billed",
            "billed": "outstanding_amount", "topay": "outstanding_amount", "paid": "0"}[bucket]
    order_by = "due ASC" if bucket in ("billed", "topay") else f"{date_f} DESC"
    rows = frappe.db.sql(
        f"""SELECT name, supplier, IFNULL(supplier_name, supplier) AS supplier_name,
                   {date_f} AS date, {due_f} AS due, {val} AS value,
                   {prog} AS progress, status,
                   COUNT(*) OVER() AS _cnt, ROUND(SUM({val}) OVER()) AS _val
            FROM `tab{dt}` WHERE {where}
            ORDER BY {order_by} LIMIT %(limit)s""",
        params, as_dict=True)
    cnt = rows[0]["_cnt"] if rows else 0
    total = rows[0]["_val"] if rows else 0
    methods = _pi_methods([r["name"] for r in rows]) if bucket == "paid" else {}
    for r in rows:
        r.pop("_cnt", None); r.pop("_val", None)
        r["value"] = flt(r["value"])
        r["date"] = str(r.get("date") or "")
        r["due"] = str(r.get("due") or "") if r.get("due") else ""
        r["bucket"] = bucket
        r["method"] = methods.get(r["name"], "")
    ccy = frappe.db.get_value("Company", target, "default_currency") or "MAD"
    return {"count": cnt or 0, "value": flt(total), "currency": ccy, "rows": rows}


def _pi_methods(names):
    """Payment method(s) that settled each Purchase Invoice — from the Payment
    Entries referencing it."""
    if not names:
        return {}
    rows = frappe.db.sql(
        """SELECT per.reference_name inv,
                  SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT IFNULL(pe.mode_of_payment,'') ORDER BY pe.posting_date DESC), ',', 1) method
           FROM `tabPayment Entry Reference` per
           JOIN `tabPayment Entry` pe ON pe.name=per.parent AND pe.docstatus=1
           WHERE per.reference_doctype='Purchase Invoice' AND per.reference_name IN %(n)s
           GROUP BY per.reference_name""",
        {"n": tuple(names)}, as_dict=True)
    return {r.inv: r.method for r in rows}


def _linked(child_dt, field, value):
    return [r.parent for r in frappe.db.sql(
        f"SELECT DISTINCT parent FROM `tab{child_dt}` WHERE {field}=%s AND IFNULL(parent,'')!=''",
        value, as_dict=True)]


@frappe.whitelist()
def get_purchase_doc(name=None, doctype=None):
    """One procure-to-pay document (PO / PR / Invoice) — header, lines, the docs
    it links to up- and down-stream, and its GL lines."""
    assert_portal_access()
    dt = doctype if doctype in ("Purchase Order", "Purchase Receipt", "Purchase Invoice") else None
    if not dt or not name or not frappe.db.exists(dt, name):
        return None
    doc = frappe.get_doc(dt, name)
    codes = list({it.item_code for it in doc.items if it.item_code})
    imeta = {}
    if codes:
        for r in frappe.db.sql(
                "SELECT name, custom_sku AS sku, image FROM `tabItem` WHERE name IN %(c)s",
                {"c": tuple(codes)}, as_dict=True):
            imeta[r.name] = r
    items = [{"item_code": it.item_code, "item_name": it.get("item_name") or it.item_code,
              "sku": (imeta.get(it.item_code) or {}).get("sku") or "",
              "image": (imeta.get(it.item_code) or {}).get("image") or "",
              "qty": flt(it.qty), "rate": flt(it.rate), "amount": flt(it.amount)} for it in doc.items[:200]]
    header = {
        "name": doc.name, "doctype": dt, "supplier": doc.supplier,
        "supplier_name": doc.get("supplier_name") or doc.supplier,
        "date": str(doc.get("posting_date") or doc.get("transaction_date") or ""),
        "due": str(doc.get("due_date") or doc.get("schedule_date") or ""),
        "status": doc.get("status") or "", "net": flt(doc.get("net_total")),
        "tax": flt(doc.get("total_taxes_and_charges")), "grand": flt(doc.grand_total),
        "outstanding": flt(doc.get("outstanding_amount")),
        "per_received": flt(doc.get("per_received")), "per_billed": flt(doc.get("per_billed")),
        "currency": doc.get("currency") or "MAD",
    }
    conn = {"orders": [], "receipts": [], "invoices": [], "payments": []}
    if dt == "Purchase Order":
        conn["receipts"] = _linked("Purchase Receipt Item", "purchase_order", name)
        conn["invoices"] = _linked("Purchase Invoice Item", "purchase_order", name)
    elif dt == "Purchase Receipt":
        conn["orders"] = sorted({it.get("purchase_order") for it in doc.items if it.get("purchase_order")})
        conn["invoices"] = _linked("Purchase Invoice Item", "purchase_receipt", name)
    elif dt == "Purchase Invoice":
        conn["orders"] = sorted({it.get("purchase_order") for it in doc.items if it.get("purchase_order")})
        conn["receipts"] = sorted({it.get("purchase_receipt") for it in doc.items if it.get("purchase_receipt")})
        conn["payments"] = [r.parent for r in frappe.db.sql(
            "SELECT DISTINCT parent FROM `tabPayment Entry Reference` "
            "WHERE reference_doctype='Purchase Invoice' AND reference_name=%s", name, as_dict=True)]
    gl = frappe.db.sql(
        "SELECT a.account_name AS name, ge.account, ROUND(ge.debit) dr, ROUND(ge.credit) cr "
        "FROM `tabGL Entry` ge JOIN `tabAccount` a ON a.name=ge.account "
        "WHERE ge.voucher_no=%s AND ge.is_cancelled=0 ORDER BY ge.debit DESC", name, as_dict=True)
    return {"header": header, "items": items, "connections": conn, "gl": gl}


# ── Pipeline actions: move a doc down the procure-to-pay chain (gated writes) ──
PR_ACTION = "Make Receipt"
PI_ACTION = "Make Invoice"
PAY_ACTION = "Pay Bill"


def _bust_purch_cache():
    try:
        frappe.cache().delete_keys("ap_purch_summary")
    except Exception:
        pass


def _make_receipt_poster(action):
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    pr = frappe.get_attr("erpnext.buying.doctype.purchase_order.purchase_order.make_purchase_receipt")(p["source"])
    pr.flags.ignore_permissions = True
    pr.insert()
    pr.reload()
    pr.submit()
    return {"voucher_type": "Purchase Receipt", "voucher_no": pr.name,
            "result": {"from_po": p["source"], "grand_total": flt(pr.grand_total)}}


def _make_invoice_poster(action):
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    pi = frappe.get_attr("erpnext.stock.doctype.purchase_receipt.purchase_receipt.make_purchase_invoice")(p["source"])
    pi.flags.ignore_permissions = True
    pi.insert()
    pi.reload()
    pi.submit()
    return {"voucher_type": "Purchase Invoice", "voucher_no": pi.name,
            "result": {"from_pr": p["source"], "grand_total": flt(pi.grand_total)}}


def _pay_bill_poster(action):
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    pe = frappe.get_attr("erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry")(
        "Purchase Invoice", p["invoice"])
    if p.get("paid_from"):
        pe.paid_from = p["paid_from"]
    if p.get("mode"):
        pe.mode_of_payment = p["mode"]
    if p.get("reference_no"):
        pe.reference_no = p["reference_no"]
        pe.reference_date = p.get("reference_date") or nowdate()
    # Overriding paid_from (different account / currency) can wipe the amounts
    # get_payment_entry computed → "Paid Amount is mandatory". Recompute, then
    # backstop from the allocated reference amount so it's never blank.
    try:
        pe.set_amounts()
    except Exception:
        pass
    alloc = sum(flt(r.allocated_amount) for r in (pe.get("references") or []))
    if not flt(pe.paid_amount):
        pe.paid_amount = flt(pe.received_amount) or alloc
    if not flt(pe.received_amount):
        pe.received_amount = flt(pe.paid_amount) or alloc
    pe.flags.ignore_permissions = True
    pe.insert()
    pe.reload()
    pe.submit()
    return {"voucher_type": "Payment Entry", "voucher_no": pe.name,
            "result": {"invoice": p["invoice"], "paid": flt(pe.paid_amount), "mode": pe.get("mode_of_payment")}}


_actions.register_poster(PR_ACTION, _make_receipt_poster)
_actions.register_poster(PI_ACTION, _make_invoice_poster)
_actions.register_poster(PAY_ACTION, _pay_bill_poster)


@frappe.whitelist()
def make_receipt(company=None, purchase_order=None, dedupe_key=None):
    """Create + submit a Purchase Receipt from a PO (To Buy → Received)."""
    assert_can_write()
    target = _target(company)
    if not target or not purchase_order or not frappe.db.exists("Purchase Order", purchase_order):
        frappe.throw("Purchase Order not found")
    po = frappe.db.get_value("Purchase Order", purchase_order,
                             ["company", "docstatus", "per_received", "grand_total"], as_dict=True)
    if po.company != target:
        frappe.throw("Purchase Order belongs to another company")
    if po.docstatus != 1:
        frappe.throw("Purchase Order is not submitted")
    if flt(po.per_received) >= 100:
        frappe.throw("Already fully received")
    res = _actions.execute(PR_ACTION, target, dedupe_key or f"pr:{purchase_order}",
                           payload={"source": purchase_order}, amount=flt(po.grand_total),
                           reference_doctype="Purchase Order", reference_name=purchase_order,
                           notes=f"Receipt for {purchase_order}")
    _bust_purch_cache()
    return res


@frappe.whitelist()
def make_invoice_from_receipt(company=None, purchase_receipt=None, dedupe_key=None):
    """Create + submit a Purchase Invoice from a Receipt (Received → Billed/To Pay)."""
    assert_can_write()
    target = _target(company)
    if not target or not purchase_receipt or not frappe.db.exists("Purchase Receipt", purchase_receipt):
        frappe.throw("Purchase Receipt not found")
    pr = frappe.db.get_value("Purchase Receipt", purchase_receipt,
                             ["company", "docstatus", "per_billed", "grand_total"], as_dict=True)
    if pr.company != target:
        frappe.throw("Purchase Receipt belongs to another company")
    if pr.docstatus != 1:
        frappe.throw("Purchase Receipt is not submitted")
    if flt(pr.per_billed) >= 100:
        frappe.throw("Already fully billed")
    res = _actions.execute(PI_ACTION, target, dedupe_key or f"pi:{purchase_receipt}",
                           payload={"source": purchase_receipt}, amount=flt(pr.grand_total),
                           reference_doctype="Purchase Receipt", reference_name=purchase_receipt,
                           notes=f"Invoice for {purchase_receipt}")
    _bust_purch_cache()
    return res


@frappe.whitelist()
def pay_bill(company=None, invoice=None, paid_from=None, mode=None, reference_no=None,
             reference_date=None, dedupe_key=None):
    """Create + submit a Payment Entry settling a Purchase Invoice (To Pay → Paid)."""
    assert_can_write()
    target = _target(company)
    if not target or not invoice or not frappe.db.exists("Purchase Invoice", invoice):
        frappe.throw("Invoice not found")
    pi = frappe.db.get_value("Purchase Invoice", invoice,
                             ["company", "docstatus", "outstanding_amount"], as_dict=True)
    if pi.company != target:
        frappe.throw("Invoice belongs to another company")
    if pi.docstatus != 1:
        frappe.throw("Invoice is not submitted")
    if flt(pi.outstanding_amount) <= 0:
        frappe.throw("Invoice already settled")
    res = _actions.execute(
        PAY_ACTION, target, dedupe_key or f"pay:{invoice}",
        payload={"invoice": invoice, "paid_from": paid_from, "mode": mode,
                 "reference_no": reference_no, "reference_date": reference_date},
        amount=flt(pi.outstanding_amount), reference_doctype="Purchase Invoice",
        reference_name=invoice, notes=f"Payment for {invoice}")
    _bust_purch_cache()
    return res


@frappe.whitelist()
def payment_modes(company=None):
    """Mode-of-payment options + their default bank/cash account for this company,
    for the Pay Bill dialog."""
    assert_portal_access()
    target = _target(company)
    rows = frappe.db.sql(
        """SELECT mop.name AS mode, mopa.default_account AS account
           FROM `tabMode of Payment` mop
           LEFT JOIN `tabMode of Payment Account` mopa
             ON mopa.parent=mop.name AND mopa.company=%s
           WHERE mop.enabled=1 ORDER BY mop.name""", target, as_dict=True)
    return rows


# ── Group payment: settle many invoices of ONE supplier with one Payment Entry ──
GRP_PAY_ACTION = "Group Pay"


def _group_pay_poster(action):
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    invoices = p["invoices"]
    pe = frappe.get_attr("erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry")(
        "Purchase Invoice", invoices[0])
    pe.references = []
    total = 0.0
    for inv in invoices:
        pi = frappe.get_doc("Purchase Invoice", inv)
        pe.append("references", {
            "reference_doctype": "Purchase Invoice", "reference_name": inv,
            "due_date": pi.due_date, "total_amount": pi.grand_total,
            "outstanding_amount": pi.outstanding_amount, "allocated_amount": pi.outstanding_amount})
        total += flt(pi.outstanding_amount)
    pe.paid_amount = total
    pe.received_amount = total
    if p.get("paid_from"):
        pe.paid_from = p["paid_from"]
    if p.get("mode"):
        pe.mode_of_payment = p["mode"]
    if p.get("reference_no"):
        pe.reference_no = p["reference_no"]
        pe.reference_date = p.get("reference_date") or nowdate()
    pe.flags.ignore_permissions = True
    pe.insert()
    pe.reload()
    pe.submit()
    return {"voucher_type": "Payment Entry", "voucher_no": pe.name,
            "result": {"invoices": invoices, "count": len(invoices), "paid": flt(pe.paid_amount)}}


_actions.register_poster(GRP_PAY_ACTION, _group_pay_poster)


@frappe.whitelist()
def pay_bills_group(company=None, invoices=None, mode=None, paid_from=None,
                    reference_no=None, reference_date=None, dedupe_key=None):
    """Settle several Purchase Invoices of ONE supplier with a single Payment
    Entry (one cash-out, one reference per invoice). All invoices must be the
    same company + same supplier + unpaid."""
    assert_can_write()
    target = _target(company)
    names = invoices if isinstance(invoices, list) else json.loads(invoices or "[]")
    names = [n for n in names if n]
    if not target or len(names) < 1:
        frappe.throw("No invoices given")
    rows = frappe.db.sql(
        """SELECT name, supplier, company, docstatus, outstanding_amount, is_return
           FROM `tabPurchase Invoice` WHERE name IN %(n)s""", {"n": tuple(names)}, as_dict=True)
    if len(rows) != len(names):
        frappe.throw("Some invoices were not found")
    suppliers = {r.supplier for r in rows}
    if len(suppliers) != 1:
        frappe.throw("All invoices must belong to the same supplier to pay together")
    for r in rows:
        if r.company != target:
            frappe.throw(f"{r.name} belongs to another company")
        if r.docstatus != 1 or r.is_return:
            frappe.throw(f"{r.name} is not a submitted bill")
        if flt(r.outstanding_amount) <= 0:
            frappe.throw(f"{r.name} is already settled")
    total = sum(flt(r.outstanding_amount) for r in rows)
    key = dedupe_key or "paygrp:" + frappe.generate_hash("".join(sorted(names)), 16)
    res = _actions.execute(
        GRP_PAY_ACTION, target, key,
        payload={"invoices": sorted(names), "mode": mode, "paid_from": paid_from,
                 "reference_no": reference_no, "reference_date": reference_date},
        amount=total, reference_doctype="Purchase Invoice", reference_name=sorted(names)[0],
        notes=f"Group payment · {len(names)} bills · {next(iter(suppliers))}")
    _bust_purch_cache()
    return res


# ── Group billing: consolidate many receipts of ONE supplier into one invoice ──
GRP_BILL_ACTION = "Group Bill"


def _group_bill_poster(action):
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    receipts = p["receipts"]
    mk = frappe.get_attr("erpnext.stock.doctype.purchase_receipt.purchase_receipt.make_purchase_invoice")
    target = None
    for r in receipts:
        target = mk(r, target_doc=target)
    target.flags.ignore_permissions = True
    target.insert()
    target.reload()
    target.submit()
    return {"voucher_type": "Purchase Invoice", "voucher_no": target.name,
            "result": {"receipts": receipts, "count": len(receipts), "grand": flt(target.grand_total)}}


_actions.register_poster(GRP_BILL_ACTION, _group_bill_poster)


@frappe.whitelist()
def make_invoice_group(company=None, receipts=None, dedupe_key=None):
    """Consolidate several Purchase Receipts of ONE supplier into a single
    Purchase Invoice (merged line items). All must be same company + supplier +
    not yet fully billed."""
    assert_can_write()
    target = _target(company)
    names = receipts if isinstance(receipts, list) else json.loads(receipts or "[]")
    names = [n for n in names if n]
    if not target or len(names) < 1:
        frappe.throw("No receipts given")
    rows = frappe.db.sql(
        """SELECT name, supplier, company, docstatus, per_billed, is_return, grand_total
           FROM `tabPurchase Receipt` WHERE name IN %(n)s""", {"n": tuple(names)}, as_dict=True)
    if len(rows) != len(names):
        frappe.throw("Some receipts were not found")
    suppliers = {r.supplier for r in rows}
    if len(suppliers) != 1:
        frappe.throw("All receipts must belong to the same supplier to bill together")
    for r in rows:
        if r.company != target:
            frappe.throw(f"{r.name} belongs to another company")
        if r.docstatus != 1 or r.is_return:
            frappe.throw(f"{r.name} is not a submitted receipt")
        if flt(r.per_billed) >= 100:
            frappe.throw(f"{r.name} is already billed")
    total = sum(flt(r.grand_total) for r in rows)
    key = dedupe_key or "billgrp:" + frappe.generate_hash("".join(sorted(names)), 16)
    res = _actions.execute(
        GRP_BILL_ACTION, target, key, payload={"receipts": sorted(names)},
        amount=total, reference_doctype="Purchase Receipt", reference_name=sorted(names)[0],
        notes=f"Group bill · {len(names)} receipts · {next(iter(suppliers))}")
    _bust_purch_cache()
    return res


# ── Cheque register (supplier cheques — track issued → cleared) ──
_CHQ_COND = "(IFNULL(pe.reference_no,'') LIKE 'CHQ%%' OR pe.mode_of_payment IN ('Cheque','Bank Draft'))"
CLEAR_CHQ_ACTION = "Clear Cheque"
# An outstanding cheque this many days past its cheque date has almost certainly
# been cashed at the bank — the cash-out is already in the GL; it's just never
# been reconciled (clearance_date left blank), so it lingers as "Outstanding".
STALE_CHQ_DAYS = 45


def _chq_status(due, cleared):
    from frappe.utils import getdate, nowdate
    if cleared:
        return "cleared"
    if due and getdate(due) > getdate(nowdate()):
        return "postdated"
    return "outstanding"


@frappe.whitelist()
def cheques_summary(company=None):
    """Counts + values per cheque state — outstanding / due ≤7d / post-dated / cleared."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    r = frappe.db.sql(
        f"""SELECT
              ROUND(SUM(CASE WHEN pe.clearance_date IS NULL THEN pe.paid_amount ELSE 0 END)) outstanding,
              SUM(CASE WHEN pe.clearance_date IS NULL THEN 1 ELSE 0 END) outstanding_n,
              ROUND(SUM(CASE WHEN pe.clearance_date IS NULL AND pe.reference_date<=DATE_ADD(CURDATE(),INTERVAL 7 DAY) THEN pe.paid_amount ELSE 0 END)) due_week,
              SUM(CASE WHEN pe.clearance_date IS NULL AND pe.reference_date<=DATE_ADD(CURDATE(),INTERVAL 7 DAY) THEN 1 ELSE 0 END) due_week_n,
              ROUND(SUM(CASE WHEN pe.clearance_date IS NULL AND pe.reference_date>CURDATE() THEN pe.paid_amount ELSE 0 END)) postdated,
              SUM(CASE WHEN pe.clearance_date IS NULL AND pe.reference_date>CURDATE() THEN 1 ELSE 0 END) postdated_n,
              ROUND(SUM(CASE WHEN pe.clearance_date IS NOT NULL THEN pe.paid_amount ELSE 0 END)) cleared,
              SUM(CASE WHEN pe.clearance_date IS NOT NULL THEN 1 ELSE 0 END) cleared_n,
              ROUND(SUM(CASE WHEN pe.clearance_date IS NULL AND pe.reference_date < DATE_SUB(CURDATE(),INTERVAL {STALE_CHQ_DAYS} DAY) THEN pe.paid_amount ELSE 0 END)) stale,
              SUM(CASE WHEN pe.clearance_date IS NULL AND pe.reference_date < DATE_SUB(CURDATE(),INTERVAL {STALE_CHQ_DAYS} DAY) THEN 1 ELSE 0 END) stale_n
            FROM `tabPayment Entry` pe
            WHERE pe.company=%s AND pe.docstatus=1 AND pe.payment_type='Pay' AND {_CHQ_COND}""",
        target, as_dict=True)[0]
    return {k: flt(v) for k, v in r.items()}


@frappe.whitelist()
def list_cheques(company=None, search=None, status=None, from_date=None, to_date=None, limit=300):
    """Supplier cheques with their state — cheque no, supplier, due (cheque) date,
    bank, amount, cleared. Ordered by due date so the soonest-to-clear are first."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return []
    conds = ["pe.company=%(c)s", "pe.docstatus=1", "pe.payment_type='Pay'", _CHQ_COND]
    params = {"c": target, "limit": min(int(limit or 300), 1000)}
    if from_date:
        conds.append("pe.reference_date >= %(fd)s"); params["fd"] = from_date
    if to_date:
        conds.append("pe.reference_date <= %(td)s"); params["td"] = to_date
    if search:
        conds.append("(pe.name LIKE %(s)s OR IFNULL(pe.reference_no,'') LIKE %(s)s OR pe.party LIKE %(s)s OR IFNULL(pe.party_name,'') LIKE %(s)s)")
        params["s"] = f"%{search}%"
    rows = frappe.db.sql(
        f"""SELECT pe.name, pe.party, IFNULL(s.supplier_name, pe.party) AS supplier_name,
                   IFNULL(pe.reference_no,'') AS cheque_no, pe.reference_date AS due,
                   pe.clearance_date AS cleared_on, pe.paid_amount AS amount,
                   pe.paid_from_account_currency AS currency, IFNULL(pe.mode_of_payment,'') AS bank,
                   DATEDIFF(CURDATE(), pe.reference_date) AS age_days
            FROM `tabPayment Entry` pe LEFT JOIN `tabSupplier` s ON s.name=pe.party
            WHERE {' AND '.join(conds)}
            ORDER BY pe.clearance_date IS NOT NULL, pe.reference_date ASC LIMIT %(limit)s""",
        params, as_dict=True)
    out = []
    for r in rows:
        st = _chq_status(r.get("due"), r.get("cleared_on"))
        age = int(r.get("age_days") or 0)
        stale = st == "outstanding" and age > STALE_CHQ_DAYS
        if status == "stale":
            if not stale:
                continue
        elif status and status != st:
            continue
        r["amount"] = flt(r["amount"])
        r["due"] = str(r.get("due") or "")
        r["cleared_on"] = str(r.get("cleared_on") or "")
        r["status"] = st
        r["age_days"] = age
        r["stale"] = stale
        out.append(r)
    return out


def _clear_cheque_poster(action):
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    names = p["names"]
    dates = p.get("dates") or {}          # per-cheque actual bank clearance date
    default = p.get("date") or nowdate()  # fallback for any cheque without its own date
    applied = {}
    for n in names:
        d = dates.get(n) or default
        frappe.db.set_value("Payment Entry", n, "clearance_date", d)
        applied[n] = d
    frappe.db.commit()
    return {"voucher_type": "Payment Entry", "voucher_no": (names[0] if names else None),
            "result": {"cleared": applied, "n": len(names)}}


def _clear_cheque_reverter(action):
    """Undo a cheque clearing: remove the clearance_date — only where it still holds
    the date this action set (don't wipe a later re-clear)."""
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    dates = p.get("dates") or {}
    default = p.get("date")
    done = 0
    for n in (p.get("names") or []):
        set_date = dates.get(n) or default
        cur = frappe.db.get_value("Payment Entry", n, "clearance_date")
        if cur and (not set_date or str(cur) == str(set_date)):
            frappe.db.set_value("Payment Entry", n, "clearance_date", None)
            done += 1
    frappe.db.commit()
    return {"uncleared": done}


_actions.register_poster(CLEAR_CHQ_ACTION, _clear_cheque_poster)
_actions.register_reverter(CLEAR_CHQ_ACTION, _clear_cheque_reverter)


@frappe.whitelist()
def mark_cheques_cleared(company=None, names=None, clearance_date=None, dates=None):
    """Stamp the bank clearance date on the selected cheques (a reconciliation
    marker — no GL impact). Audited; one batch action.

    `dates`: optional JSON map {payment_entry_name: 'YYYY-MM-DD'} so each cheque
    gets its real bank-clearing date. `clearance_date` is the fallback for any
    cheque not in the map (and the whole batch if `dates` is omitted)."""
    assert_can_write()
    target = _target(company)
    names = names if isinstance(names, list) else json.loads(names or "[]")
    names = [n for n in names if n]
    dates = dates if isinstance(dates, dict) else (json.loads(dates) if dates else {})
    if not target or not names:
        frappe.throw("No cheques selected")
    rows = frappe.db.sql("SELECT name, company FROM `tabPayment Entry` WHERE name IN %(n)s",
                         {"n": tuple(names)}, as_dict=True)
    if len(rows) != len(names):
        frappe.throw("Some cheques were not found")
    for r in rows:
        if r.company != target:
            frappe.throw(f"{r.name} belongs to another company")
    date = clearance_date or nowdate()
    dates = {n: d for n, d in dates.items() if n in names and d}
    sig = "".join(f"{n}:{dates.get(n, date)}" for n in sorted(names))
    key = "clrchq:" + frappe.generate_hash(sig, 16)
    res = _actions.execute(CLEAR_CHQ_ACTION, target, key,
                           payload={"names": sorted(names), "date": date, "dates": dates}, amount=0,
                           notes=f"Cleared {len(names)} cheque(s)")
    _bust_purch_cache()
    return res


# ── Advance matching: apply an unallocated supplier payment to open bills ──
MATCH_ADV_ACTION = "Match Advance"


def _match_advance_poster(action):
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    pe = frappe.get_doc("Payment Entry", p["payment"])
    inv_names = set(p["invoices"])
    pr = frappe.get_doc({"doctype": "Payment Reconciliation", "company": pe.company,
                         "party_type": "Supplier", "party": pe.party,
                         "receivable_payable_account": pe.paid_to})
    pr.get_unreconciled_entries()
    invs = [x.as_dict() for x in pr.invoices if x.invoice_number in inv_names]
    pays = [x.as_dict() for x in pr.payments if x.reference_name == p["payment"]]
    if not invs or not pays:
        frappe.throw("Nothing left to reconcile (already applied?)")
    pr.allocate_entries({"invoices": invs, "payments": pays})
    pr.reconcile()
    return {"voucher_type": "Payment Entry", "voucher_no": p["payment"],
            "result": {"payment": p["payment"], "invoices": sorted(inv_names), "n": len(inv_names)}}


_actions.register_poster(MATCH_ADV_ACTION, _match_advance_poster)


@frappe.whitelist()
def advance_match_options(company=None, payment=None):
    """An unallocated supplier advance + the supplier's open bills to apply it to."""
    assert_portal_access()
    target = _target(company)
    pe = frappe.db.get_value("Payment Entry", payment,
                             ["party", "party_name", "paid_to", "unallocated_amount", "company",
                              "payment_type", "party_type", "paid_from_account_currency"], as_dict=True)
    if not pe or pe.company != target or pe.payment_type != "Pay" or pe.party_type != "Supplier":
        frappe.throw("Not a supplier advance for this company")
    bills = frappe.db.sql(
        """SELECT name, posting_date AS date, due_date, ROUND(outstanding_amount,2) AS outstanding,
                  ROUND(grand_total,2) AS total
           FROM `tabPurchase Invoice`
           WHERE company=%s AND supplier=%s AND docstatus=1 AND IFNULL(is_return,0)=0 AND outstanding_amount>0
           ORDER BY due_date ASC, posting_date ASC LIMIT 100""", (target, pe.party), as_dict=True)
    for b in bills:
        b["outstanding"] = flt(b["outstanding"]); b["total"] = flt(b["total"])
        b["date"] = str(b.get("date") or ""); b["due_date"] = str(b.get("due_date") or "")
    return {"payment": payment, "party": pe.party, "party_name": pe.party_name or pe.party,
            "unallocated": flt(pe.unallocated_amount), "currency": pe.paid_from_account_currency or "MAD",
            "bills": bills}


@frappe.whitelist()
def apply_advance(company=None, payment=None, invoices=None, dedupe_key=None):
    """Reconcile an unallocated supplier payment against selected open bills
    (ERPNext Payment Reconciliation), through the gated/audited engine."""
    assert_can_write()
    target = _target(company)
    names = invoices if isinstance(invoices, list) else json.loads(invoices or "[]")
    names = [n for n in names if n]
    pe = frappe.db.get_value("Payment Entry", payment,
                             ["party", "company", "unallocated_amount", "payment_type", "party_type"], as_dict=True)
    if not pe or pe.company != target:
        frappe.throw("Payment not found")
    if pe.payment_type != "Pay" or pe.party_type != "Supplier":
        frappe.throw("Not a supplier payment")
    if flt(pe.unallocated_amount) <= 0:
        frappe.throw("This payment has nothing left to allocate")
    if not names:
        frappe.throw("Select at least one bill")
    rows = frappe.db.sql("SELECT name, supplier, company FROM `tabPurchase Invoice` WHERE name IN %(n)s",
                         {"n": tuple(names)}, as_dict=True)
    if len(rows) != len(names):
        frappe.throw("Some bills were not found")
    for r in rows:
        if r.company != target or r.supplier != pe.party:
            frappe.throw(f"{r.name} is not an open bill for this supplier")
    key = dedupe_key or "matchadv:" + frappe.generate_hash(payment + "".join(sorted(names)), 16)
    res = _actions.execute(
        MATCH_ADV_ACTION, target, key, payload={"payment": payment, "invoices": sorted(names)},
        amount=flt(pe.unallocated_amount), reference_doctype="Payment Entry", reference_name=payment,
        notes=f"Apply advance {payment} to {len(names)} bill(s)")
    _bust_purch_cache()
    return res


@frappe.whitelist()
def create_supplier(supplier_name=None, supplier_group=None, supplier_type=None,
                    tax_id=None, currency=None, country=None):
    """Onboard a supplier from the portal."""
    assert_can_write()
    if not (supplier_name or "").strip():
        frappe.throw("Supplier name is required")
    group = supplier_group or frappe.db.get_value("Supplier Group", {"is_group": 0}, "name") or "All Supplier Groups"
    doc = frappe.get_doc({
        "doctype": "Supplier", "supplier_name": supplier_name.strip(),
        "supplier_group": group, "supplier_type": supplier_type or "Company",
        "tax_id": tax_id or None, "default_currency": currency or None, "country": country or None,
    })
    doc.flags.ignore_permissions = True
    doc.insert()
    return {"name": doc.name, "supplier_name": doc.supplier_name}


@frappe.whitelist()
def update_supplier(name=None, supplier_name=None, supplier_group=None,
                    supplier_type=None, tax_id=None, currency=None):
    """Edit a supplier's master fields from the portal."""
    assert_can_write()
    if not name or not frappe.db.exists("Supplier", name):
        frappe.throw("Supplier not found")
    doc = frappe.get_doc("Supplier", name)
    doc.flags.ignore_permissions = True
    if supplier_name:
        doc.supplier_name = supplier_name.strip()
    if supplier_group:
        doc.supplier_group = supplier_group
    if supplier_type:
        doc.supplier_type = supplier_type
    if tax_id is not None:
        doc.tax_id = tax_id or None
    if currency is not None:
        doc.default_currency = currency or None
    doc.save()
    return {"name": doc.name, "supplier_name": doc.supplier_name}


@frappe.whitelist()
def supplier_groups():
    assert_portal_access()
    return [r.name for r in frappe.db.sql(
        "SELECT name FROM `tabSupplier Group` WHERE is_group=0 ORDER BY name", as_dict=True)]


@frappe.whitelist()
def bulk_create_suppliers(rows=None):
    """Create many suppliers from a pasted/imported list. Each row: supplier_name
    (required), group, tax_id, currency. Skips duplicates by name; never throws on
    a bad row — returns a per-row result."""
    assert_can_write()
    data = rows if isinstance(rows, list) else json.loads(rows or "[]")
    out = []
    for r in data[:500]:
        nm = (r.get("supplier_name") or r.get("name") or "").strip()
        if not nm:
            out.append({"name": "", "status": "skipped", "error": "no name"}); continue
        try:
            if frappe.db.exists("Supplier", {"supplier_name": nm}):
                out.append({"name": nm, "status": "exists"}); continue
            res = create_supplier(supplier_name=nm, supplier_group=(r.get("group") or None),
                                  tax_id=(r.get("tax_id") or None), currency=(r.get("currency") or None))
            out.append({"name": res["name"], "status": "created"})
        except Exception as e:
            out.append({"name": nm, "status": "error", "error": str(e)[:120]})
    return {"results": out,
            "created": sum(1 for x in out if x["status"] == "created"),
            "exists": sum(1 for x in out if x["status"] == "exists"),
            "failed": sum(1 for x in out if x["status"] in ("error", "skipped"))}


# ── Create Purchase Order (procure-to-pay START) ────────────────────────────
PO_ACTION = "Create Purchase Order"


def _create_po_poster(action):
    """Build + (optionally) submit a Purchase Order from the action payload."""
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    company = action.company
    txn = p.get("transaction_date") or nowdate()
    sched = p.get("schedule_date") or nowdate()
    po = frappe.get_doc({
        "doctype": "Purchase Order",
        "company": company,
        "supplier": p["supplier"],
        "transaction_date": txn,
        "schedule_date": sched,
        "items": [{
            "item_code": it["item_code"], "qty": flt(it.get("qty") or 1),
            "rate": flt(it.get("rate") or 0),
            "schedule_date": it.get("schedule_date") or sched,
        } for it in (p.get("items") or [])],
    })
    # Programmatic POs must fetch item_name/uom/conversion_rate/base amounts that
    # the desk form fetches on the client, else mandatory-field validation fails.
    po.set_missing_values()
    po.run_method("calculate_taxes_and_totals")
    po.flags.ignore_permissions = True
    po.insert()
    submitted = False
    if p.get("submit"):
        po.reload()
        po.submit()
        submitted = True
    return {"voucher_type": "Purchase Order", "voucher_no": po.name,
            "result": {"supplier": po.supplier, "grand_total": flt(po.grand_total),
                       "submitted": submitted}}


_actions.register_poster(PO_ACTION, _create_po_poster)


@frappe.whitelist()
def create_purchase_order(company=None, supplier=None, items=None, transaction_date=None,
                          schedule_date=None, submit=1, dedupe_key=None):
    """Create a Purchase Order through the write gateway — the procurement start
    that previously had to be done in ERPNext. `items`: [{item_code, qty, rate}, …]."""
    assert_can_write()
    target = _target(company)
    if not target:
        frappe.throw("No company in scope")
    if not supplier or not frappe.db.exists("Supplier", supplier):
        frappe.throw("Select a supplier")
    if isinstance(items, str):
        items = json.loads(items or "[]")
    items = [it for it in (items or []) if it.get("item_code") and flt(it.get("qty")) > 0]
    if not items:
        frappe.throw("Add at least one line item")
    amount = sum(flt(it.get("qty")) * flt(it.get("rate") or 0) for it in items)
    key = dedupe_key or f"po:create:{target}:{supplier}:" + frappe.generate_hash(
        json.dumps(items, sort_keys=True, default=str), 12)
    payload = {"company": target, "supplier": supplier, "items": items,
               "transaction_date": transaction_date, "schedule_date": schedule_date,
               "submit": int(submit or 0)}
    res = _actions.execute(PO_ACTION, target, key, payload=payload, amount=amount,
                           reference_doctype="Supplier", reference_name=supplier,
                           notes=f"Purchase Order for {supplier} ({amount:,.0f})")
    _bust_purch_cache()
    return res


@frappe.whitelist()
def supplier_options(search=None, company=None, limit=15):
    """Supplier search for the PO picker — by name."""
    assert_portal_access()
    like = f"%{(search or '').strip()}%"
    return frappe.db.sql(
        """SELECT name, supplier_name, default_currency AS ccy FROM `tabSupplier`
           WHERE disabled=0 AND (name LIKE %s OR supplier_name LIKE %s)
           ORDER BY modified DESC LIMIT %s""",
        (like, like, min(int(limit or 15), 30)), as_dict=True)


@frappe.whitelist()
def po_item_options(search=None, supplier=None, limit=15):
    """Item search for the PO picker — includes the last purchase rate as a default."""
    assert_portal_access()
    like = f"%{(search or '').strip()}%"
    return frappe.db.sql(
        """SELECT name AS item_code, item_name, custom_sku AS sku, stock_uom AS uom,
                  IFNULL(last_purchase_rate, 0) AS rate
           FROM `tabItem`
           WHERE disabled=0 AND is_purchase_item=1
             AND (name LIKE %s OR item_name LIKE %s OR IFNULL(custom_sku,'') LIKE %s)
           ORDER BY modified DESC LIMIT %s""",
        (like, like, like, min(int(limit or 15), 30)), as_dict=True)


# ── Debit Note / purchase return (return goods / claw back a bill) ───────────
DEBIT_NOTE_ACTION = "Debit Note"


def _debit_note_poster(action):
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    rd = frappe.get_attr(
        "erpnext.controllers.sales_and_purchase_return.make_return_doc")("Purchase Invoice", p["invoice"])
    # The return must post no earlier than the original bill.
    rd.set_posting_time = 1
    rd.posting_date = nowdate()
    rd.posting_time = frappe.utils.nowtime()
    rd.flags.ignore_permissions = True
    rd.insert()
    rd.reload()
    if p.get("submit", 1):
        rd.submit()
    return {"voucher_type": "Purchase Invoice", "voucher_no": rd.name,
            "result": {"against": p["invoice"], "grand_total": flt(rd.grand_total)}}


_actions.register_poster(DEBIT_NOTE_ACTION, _debit_note_poster)


@frappe.whitelist()
def make_debit_note(company=None, invoice=None, submit=1, dedupe_key=None):
    """Create a Debit Note (purchase return) against a submitted Purchase Invoice —
    returns goods to / claws back a bill from the supplier."""
    assert_can_write()
    target = _target(company)
    if not target or not invoice or not frappe.db.exists("Purchase Invoice", invoice):
        frappe.throw("Bill not found")
    pi = frappe.db.get_value("Purchase Invoice", invoice,
                             ["company", "docstatus", "is_return", "grand_total"], as_dict=True)
    if pi.company != target:
        frappe.throw("Bill belongs to another company")
    if pi.docstatus != 1:
        frappe.throw("Bill is not submitted")
    if pi.is_return:
        frappe.throw("This is already a return")
    res = _actions.execute(DEBIT_NOTE_ACTION, target, dedupe_key or f"debit:{invoice}",
                           payload={"invoice": invoice, "submit": int(submit or 0)},
                           amount=abs(flt(pi.grand_total)), reference_doctype="Purchase Invoice",
                           reference_name=invoice, notes=f"Debit note against {invoice}")
    _bust_purch_cache()
    return res
