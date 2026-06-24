"""Purchases endpoints — live ERPNext, entity-scoped.

Purchase Invoice = bills (3-way match vs PO + Goods Receipt). Lists are scoped
to one company and exclude cancelled docs. The 3-way match flag is derived from
whether every line is linked to a Purchase Order (and a receipt).
"""
import frappe
from frappe.utils import flt

from accounting_portal.api.permissions import assert_portal_access, resolve_companies
from accounting_portal.api.sales import _voucher_journal


def _bill_status(row):
    """Normalise ERPNext Purchase Invoice status → portal vocabulary."""
    if row.get("is_return"):
        return "ret"
    s = (row.get("status") or "").strip()
    if s in ("Overdue", "Unpaid"):
        return "overdue"
    return "paid"


@frappe.whitelist()
def list_bills(company=None, search=None, limit=100):
    """Bills for one company with a derived 3-way-match flag, excluding cancelled."""
    assert_portal_access()
    companies = resolve_companies(company)
    if not companies:
        return []
    target = company if (company and company in companies) else companies[0]
    currency = frappe.db.get_value("Company", target, "default_currency")
    limit = min(int(limit or 100), 500)
    conds = ["pi.company = %(company)s", "pi.docstatus = 1"]
    params = {"company": target, "limit": limit}
    if search:
        conds.append("(pi.name LIKE %(s)s OR pi.supplier LIKE %(s)s OR pi.bill_no LIKE %(s)s)")
        params["s"] = f"%{search}%"
    rows = frappe.db.sql(
        f"""
        SELECT pi.name, pi.supplier, pi.grand_total, pi.is_return, pi.status,
               pi.posting_date AS date, pi.bill_no,
               (SELECT COUNT(*) FROM `tabPurchase Invoice Item` it WHERE it.parent = pi.name) AS n_items,
               (SELECT COUNT(*) FROM `tabPurchase Invoice Item` it
                  WHERE it.parent = pi.name AND IFNULL(it.purchase_order, '') <> '') AS n_po
        FROM `tabPurchase Invoice` pi
        WHERE {' AND '.join(conds)}
        ORDER BY pi.posting_date DESC, pi.creation DESC
        LIMIT %(limit)s
        """,
        params, as_dict=True,
    )
    for r in rows:
        r["currency"] = currency
        r["status_norm"] = _bill_status(r)
        # 3-way matched when every line ties back to a PO; else a match exception.
        r["match"] = "ok" if (r["n_items"] and r["n_po"] == r["n_items"]) else "exc"
        r["amount"] = flt(r["grand_total"]) * (-1 if r["is_return"] else 1)
    return rows


@frappe.whitelist()
def get_bill(name):
    """One bill: header, 3-way-match legs (PO / receipt / invoice), posted journal."""
    assert_portal_access()
    pi = frappe.db.get_value(
        "Purchase Invoice", name,
        ["name", "supplier", "company", "grand_total", "is_return", "status",
         "posting_date", "bill_no"], as_dict=True,
    )
    if not pi:
        frappe.throw("Bill not found")
    if pi.company not in resolve_companies():
        frappe.throw("Not permitted", frappe.PermissionError)
    items = frappe.db.sql(
        """SELECT item_name AS name, qty, rate, amount,
                  IFNULL(purchase_order, '') AS po, IFNULL(purchase_receipt, '') AS pr
           FROM `tabPurchase Invoice Item` WHERE parent = %s ORDER BY idx""",
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
def get_supplier(name):
    """Full supplier detail: header, computed stats, contact, connections, and
    the supplier ledger (GL party entries) — the purchase-cycle counterpart of
    get_customer."""
    assert_portal_access()
    s = frappe.db.get_value(
        "Supplier", name,
        ["name", "supplier_name", "supplier_group", "supplier_type",
         "country", "default_currency", "tax_id", "creation"], as_dict=True)
    if not s:
        frappe.throw("Supplier not found")
    company = resolve_companies()[0] if resolve_companies() else None
    ccy = s.default_currency or frappe.db.get_value("Company", company, "default_currency") or "MAD"

    # GL party balance (credit−debit > 0 ⇒ we owe the supplier).
    payable = flt(frappe.db.sql(
        """SELECT COALESCE(SUM(credit - debit), 0) FROM `tabGL Entry`
           WHERE party_type='Supplier' AND party=%s AND is_cancelled=0""", (name,))[0][0])

    bills = frappe.db.sql(
        """SELECT COUNT(*) AS n, ROUND(SUM(grand_total)) AS billed,
                  ROUND(SUM(outstanding_amount)) AS outstanding
           FROM `tabPurchase Invoice` WHERE supplier=%s AND docstatus=1""",
        (name,), as_dict=True)[0]
    n_pos = frappe.db.count("Purchase Order", {"supplier": name, "docstatus": 1})
    n_pe = frappe.db.count("Payment Entry", {"party_type": "Supplier", "party": name, "docstatus": 1})
    n_grn = frappe.db.count("Purchase Receipt", {"supplier": name, "docstatus": 1})

    ledger = frappe.db.sql(
        """SELECT posting_date AS date, voucher_no AS doc, voucher_type AS type,
                  debit AS dr, credit AS cr
           FROM `tabGL Entry`
           WHERE party_type='Supplier' AND party=%s AND is_cancelled=0
           ORDER BY posting_date DESC, creation DESC LIMIT 10""", (name,), as_dict=True)
    running = payable
    for e in ledger:
        e["balance"] = round(running, 2)
        running -= (flt(e["cr"]) - flt(e["dr"]))

    return {
        "name": s.name, "supplier_name": s.supplier_name or s.name,
        "group": s.supplier_group, "type": s.supplier_type, "country": s.country,
        "tax_id": s.tax_id, "currency": ccy,
        "since": str(s.creation)[:4] if s.creation else "—",
        "payable": payable,
        "stats": {"billed": flt(bills.billed), "n_bills": bills.n or 0,
                  "outstanding": flt(bills.outstanding), "payable": payable},
        "connections": {"bills": bills.n or 0, "pos": n_pos, "receipts": n_grn, "payments": n_pe},
        "ledger": ledger,
    }
