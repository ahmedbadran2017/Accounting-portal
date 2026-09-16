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
        out.append({"item_code": it["item_code"], "qty": flt(it["qty"]), "rate": flt(it.get("rate")),
                    "account": it.get("account") or None, "cost_center": it.get("cost_center") or None,
                    "description": it.get("description") or None})
    if not out:
        frappe.throw("Add at least one item")
    return out


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
    if not sales:
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
        doc.append("items", row)
    if p.get("tax_template"):
        doc.taxes_and_charges = p["tax_template"]
        doc.set_taxes()
    doc.flags.ignore_permissions = True
    doc.insert()
    if int(p.get("submit") or 0):
        doc.submit()
    return {"voucher_type": doctype, "voucher_no": doc.name,
            "result": {"invoice": doc.name, "docstatus": doc.docstatus, "total": flt(doc.grand_total)}}


_actions.register_poster(SI_ACTION, lambda a: _build("Sales Invoice", a))
_actions.register_poster(PI_ACTION, lambda a: _build("Purchase Invoice", a))


def _create(doctype, action_type, company, party, items, **kw):
    assert_can_write()
    target = _target(company)
    if not party:
        frappe.throw("Select a customer" if doctype == "Sales Invoice" else "Select a supplier")
    lines = _lines(items)
    net = sum(ln["qty"] * ln["rate"] for ln in lines)
    posting = kw.get("posting_date") or nowdate()
    key = f"{action_type}:{target}:{party}:{posting}:{round(net, 2)}:{kw.get('client_key') or ''}"
    payload = {"party": party, "items": lines, "posting_date": posting,
               "due_date": kw.get("due_date"), "remarks": kw.get("remarks"),
               "currency": kw.get("currency"), "exchange_rate": kw.get("exchange_rate"),
               "tax_template": kw.get("tax_template"), "bill_no": kw.get("bill_no"),
               "bill_date": kw.get("bill_date"),
               "submit": int(str(kw.get("submit") or 0) in ("1", "true", "True"))}
    return _actions.execute(action_type, target, key, payload=payload, amount=net,
                            notes=f"{doctype} for {party} ({net:,.0f})")


@frappe.whitelist()
def create_sales_invoice(company=None, customer=None, items=None, posting_date=None, due_date=None,
                         tax_template=None, currency=None, exchange_rate=None, remarks=None,
                         submit=0, client_key=None):
    """A Sales Invoice raised directly — a service or one-off sale with no order
    or delivery note behind it."""
    return _create("Sales Invoice", SI_ACTION, company, customer, items, posting_date=posting_date,
                   due_date=due_date, tax_template=tax_template, currency=currency,
                   exchange_rate=exchange_rate, remarks=remarks, submit=submit, client_key=client_key)


@frappe.whitelist()
def create_purchase_invoice(company=None, supplier=None, items=None, posting_date=None, due_date=None,
                            tax_template=None, currency=None, exchange_rate=None, remarks=None,
                            bill_no=None, bill_date=None, submit=0, client_key=None):
    """A Purchase Invoice with item lines, raised without a PO or receipt — goods
    billed straight, or a supplier bill that itemises what was supplied."""
    return _create("Purchase Invoice", PI_ACTION, company, supplier, items, posting_date=posting_date,
                   due_date=due_date, tax_template=tax_template, currency=currency,
                   exchange_rate=exchange_rate, remarks=remarks, bill_no=bill_no, bill_date=bill_date,
                   submit=submit, client_key=client_key)
