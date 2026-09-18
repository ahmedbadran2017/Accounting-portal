"""Standalone invoices — a Sales Invoice or an item-based Purchase Invoice raised
from nothing, without an order, delivery note or receipt to derive it from.

The audit found this was the last real hole: a service invoice to a customer, or
a supplier bill that carries items (not the single-line expense the expense modal
posts), could only be created in the Desk. Everything here goes through the write
gateway, so it is audited and gated by amount like every other posting, and both
support a draft-first flow (post it, review it in the draft editor, submit).
"""
import json

import frappe
from frappe.utils import flt, nowdate

from accounting_portal.api import _actions
from accounting_portal.api.permissions import assert_can_write, assert_portal_access, resolve_companies

SI_ACTION = "Create sales invoice"
PI_ACTION = "Create purchase invoice"


def _target(company):
    comps = resolve_companies(company)
    if not comps:
        frappe.throw("No company in scope")
    return company if (company and company in comps) else comps[0]


@frappe.whitelist()
def invoice_options(company=None, kind="sales"):
    """Everything the standalone invoice form needs: tax templates, income /
    expense accounts, cost centres, currencies and the company default."""
    assert_portal_access()
    target = _target(company)
    ccy = frappe.get_cached_value("Company", target, "default_currency")
    if kind == "purchase":
        tpl = frappe.get_all("Purchase Taxes and Charges Template", filters={"company": target},
                             fields=["name", "is_default"], order_by="is_default desc, name")
        accounts = frappe.db.sql(
            """SELECT name AS value, name AS label FROM `tabAccount`
               WHERE company=%s AND is_group=0 AND disabled=0 AND root_type='Expense' ORDER BY name""",
            (target,), as_dict=True)
    else:
        tpl = frappe.get_all("Sales Taxes and Charges Template", filters={"company": target},
                             fields=["name", "is_default"], order_by="is_default desc, name")
        accounts = frappe.db.sql(
            """SELECT name AS value, name AS label FROM `tabAccount`
               WHERE company=%s AND is_group=0 AND disabled=0 AND root_type='Income' ORDER BY name""",
            (target,), as_dict=True)
    return {
        "company": target, "currency": ccy,
        "tax_templates": [t.name for t in tpl],
        "default_tax_template": next((t.name for t in tpl if t.is_default), ""),
        "accounts": accounts,
        "cost_centers": frappe.db.sql(
            """SELECT name AS value, name AS label FROM `tabCost Center`
               WHERE company=%s AND is_group=0 AND IFNULL(disabled,0)=0 ORDER BY name""",
            (target,), as_dict=True),
        "currencies": frappe.get_all("Currency", filters={"enabled": 1}, pluck="name", order_by="name"),
    }


def _lines(items):
    if isinstance(items, str):
        items = json.loads(items)
    out = []
    for it in items or []:
        if not it.get("item_code") or flt(it.get("qty")) <= 0:
            continue
        ln = {"item_code": it["item_code"], "qty": flt(it["qty"]), "rate": flt(it.get("rate")),
              "account": it.get("account") or None, "cost_center": it.get("cost_center") or None,
              "description": it.get("description") or None}
        # Lines pulled from an order or a receipt carry the link back to it.
        # Drop these and the source document's per_billed never moves, so it
        # sits in "To Bill" forever even though it has been billed — which is
        # the whole reason the Desk's "Get Items From" exists rather than
        # retyping the lines.
        for f in ("purchase_order", "po_detail", "purchase_receipt", "pr_detail",
                  "sales_order", "so_detail", "delivery_note", "dn_detail",
                  "uom", "conversion_factor"):
            if it.get(f):
                ln[f] = it[f]
        out.append(ln)
    if not out:
        frappe.throw("Add at least one item")
    return out


def _party_address(party_type, party):
    """This book marks `customer_address` mandatory on Sales Invoice (a Property
    Setter — all 70k existing invoices carry one), so a standalone invoice must
    resolve the party's address or the insert fails with ERPNext's generic error."""
    rows = frappe.db.sql(
        """SELECT dl.parent AS name, a.is_primary_address
           FROM `tabDynamic Link` dl JOIN `tabAddress` a ON a.name = dl.parent
           WHERE dl.link_doctype=%s AND dl.link_name=%s AND dl.parenttype='Address'
             AND IFNULL(a.disabled,0)=0
           ORDER BY a.is_primary_address DESC, a.modified DESC LIMIT 1""",
        (party_type, party), as_dict=True)
    return rows[0].name if rows else None


def _build(doctype, action):
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    sales = doctype == "Sales Invoice"
    doc = frappe.get_doc({
        "doctype": doctype,
        "company": action.company,
        "posting_date": p.get("posting_date") or nowdate(),
        "set_posting_time": 1,
        ("customer" if sales else "supplier"): p["party"],
        "currency": p.get("currency") or frappe.get_cached_value("Company", action.company, "default_currency"),
        "due_date": p.get("due_date") or None,
        "remarks": p.get("remarks") or None,
    })
    if sales:
        addr = p.get("customer_address") or _party_address("Customer", p["party"])
        if addr:
            doc.customer_address = addr
    else:
        doc.bill_no = p.get("bill_no") or None
        doc.bill_date = p.get("bill_date") or None
    if p.get("exchange_rate"):
        doc.conversion_rate = flt(p["exchange_rate"])
    for ln in p["items"]:
        row = {"item_code": ln["item_code"], "qty": ln["qty"], "rate": ln["rate"],
               "cost_center": ln.get("cost_center")}
        if ln.get("description"):
            row["description"] = ln["description"]
        if ln.get("account"):
            row["income_account" if sales else "expense_account"] = ln["account"]
        child = doc.append("items", row)
        for f in ("purchase_order", "po_detail", "purchase_receipt", "pr_detail",
                  "sales_order", "so_detail", "delivery_note", "dn_detail",
                  "uom", "conversion_factor"):
            if ln.get(f) and child.meta.has_field(f):
                child.set(f, ln[f])
    if p.get("tax_template"):
        doc.taxes_and_charges = p["tax_template"]
        doc.set_taxes()
    # A supplier invoice is booked at the figures printed on it. A percentage
    # template cannot reproduce a mixed one: JUNCTION's 1883/2026 carries
    # 18,297.00 of exempt sea freight and 5,815.94 taxed at 20%, so the VAT on
    # the paper is 1,163.19 and a flat 20% template computes 4,822.59. An exact
    # amount is entered as ERPNext's "Actual" charge — the same row the Desk
    # takes — and it reproduces the document to the centime.
    vat = flt(p.get("vat_amount") or 0)
    if vat:
        head = p.get("vat_account") or _default_vat_account(action.company, sales)
        if not head:
            frappe.throw("No VAT account to post the tax amount to")
        doc.set("taxes", [t for t in (doc.get("taxes") or []) if t.account_head != head])
        doc.append("taxes", {
            "charge_type": "Actual", "account_head": head, "category": "Total",
            "description": p.get("vat_label") or "VAT (as invoiced)", "tax_amount": vat,
        })
    doc.flags.ignore_permissions = True
    doc.insert()
    if int(p.get("submit") or 0):
        doc.submit()
    return {"voucher_type": doctype, "voucher_no": doc.name,
            "result": {"invoice": doc.name, "docstatus": doc.docstatus, "total": flt(doc.grand_total)}}


_actions.register_poster(SI_ACTION, lambda a: _build("Sales Invoice", a))
_actions.register_poster(PI_ACTION, lambda a: _build("Purchase Invoice", a))


def _address_required():
    v = frappe.db.get_value("Property Setter",
                            {"doc_type": "Sales Invoice", "field_name": "customer_address", "property": "reqd"},
                            "value")
    return str(v) == "1"


def _create(doctype, action_type, company, party, items, **kw):
    assert_can_write()
    target = _target(company)
    if not party:
        frappe.throw("Select a customer" if doctype == "Sales Invoice" else "Select a supplier")
    lines = _lines(items)
    if doctype == "Sales Invoice" and _address_required() and not (kw.get("customer_address") or _party_address("Customer", party)):
        frappe.throw(f"{party} has no address on file, and this company requires one on a sales invoice. "
                     "Add an address to the customer first.")
    net = sum(ln["qty"] * ln["rate"] for ln in lines)
    posting = kw.get("posting_date") or nowdate()
    key = f"{action_type}:{target}:{party}:{posting}:{round(net, 2)}:{kw.get('client_key') or ''}"
    payload = {"party": party, "items": lines, "posting_date": posting,
               "due_date": kw.get("due_date"), "remarks": kw.get("remarks"),
               "currency": kw.get("currency"), "exchange_rate": kw.get("exchange_rate"),
               "tax_template": kw.get("tax_template"), "bill_no": kw.get("bill_no"),
               "vat_amount": flt(kw.get("vat_amount") or 0), "vat_account": kw.get("vat_account"),
               "vat_label": kw.get("vat_label"),
               "customer_address": kw.get("customer_address"),
               "bill_date": kw.get("bill_date"),
               "submit": int(str(kw.get("submit") or 0) in ("1", "true", "True"))}
    return _actions.execute(action_type, target, key, payload=payload, amount=net,
                            notes=f"{doctype} for {party} ({net:,.0f})")


@frappe.whitelist()
def create_sales_invoice(company=None, customer=None, items=None, posting_date=None, due_date=None,
                         tax_template=None, currency=None, exchange_rate=None, remarks=None,
                         customer_address=None, submit=0, client_key=None,
                         vat_amount=None, vat_account=None, vat_label=None):
    """A Sales Invoice raised directly — a service or one-off sale with no order
    or delivery note behind it."""
    return _create("Sales Invoice", SI_ACTION, company, customer, items, posting_date=posting_date,
                   due_date=due_date, tax_template=tax_template, currency=currency,
                   exchange_rate=exchange_rate, remarks=remarks, customer_address=customer_address,
                   submit=submit, client_key=client_key,
                   vat_amount=vat_amount, vat_account=vat_account, vat_label=vat_label)


@frappe.whitelist()
def create_purchase_invoice(company=None, supplier=None, items=None, posting_date=None, due_date=None,
                            tax_template=None, currency=None, exchange_rate=None, remarks=None,
                            bill_no=None, bill_date=None, submit=0, client_key=None,
                            vat_amount=None, vat_account=None, vat_label=None):
    """A Purchase Invoice with item lines, raised without a PO or receipt — goods
    billed straight, or a supplier bill that itemises what was supplied."""
    return _create("Purchase Invoice", PI_ACTION, company, supplier, items, posting_date=posting_date,
                   due_date=due_date, tax_template=tax_template, currency=currency,
                   exchange_rate=exchange_rate, remarks=remarks, bill_no=bill_no, bill_date=bill_date,
                   submit=submit, client_key=client_key,
                   vat_amount=vat_amount, vat_account=vat_account, vat_label=vat_label)


def _default_vat_account(company, sales):
    """The account a typed VAT amount posts to, when the screen does not name one.
    Taken from the company's default purchase/sales tax template so it is the
    same account a percentage template would have used."""
    tpl_dt = "Sales Taxes and Charges Template" if sales else "Purchase Taxes and Charges Template"
    tpl = frappe.db.get_value(tpl_dt, {"company": company, "is_default": 1}, "name") \
        or frappe.db.get_value(tpl_dt, {"company": company}, "name")
    if tpl:
        head = frappe.db.get_value("Purchase Taxes and Charges" if not sales else "Sales Taxes and Charges",
                                   {"parent": tpl, "parenttype": tpl_dt}, "account_head")
        if head:
            return head
    return frappe.db.get_value("Account", {"company": company, "is_group": 0, "disabled": 0,
                                           "account_type": "Tax"}, "name")


@frappe.whitelist()
def tax_options(company=None, side="buying"):
    """Tax templates and tax accounts for the invoice screens' VAT block."""
    assert_portal_access()
    target = _target(company)
    sales = str(side).lower() == "selling"
    tpl_dt = "Sales Taxes and Charges Template" if sales else "Purchase Taxes and Charges Template"
    templates = frappe.db.sql(
        "SELECT name AS value, name AS label, is_default FROM `tab" + tpl_dt + "` "
        "WHERE company=%s ORDER BY is_default DESC, name", (target,), as_dict=True)
    accounts = frappe.db.sql(
        """SELECT name AS value, name AS label FROM `tabAccount`
           WHERE company=%s AND is_group=0 AND disabled=0
             AND (account_type='Tax' OR name LIKE '391.6%%' OR name LIKE '191.0%%')
           ORDER BY name""", (target,), as_dict=True)
    return {"templates": templates, "accounts": accounts,
            "default_account": _default_vat_account(target, sales)}
