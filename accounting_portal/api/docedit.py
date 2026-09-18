"""Draft editor + one-click redate — the two things that kept sending the
accountants back to the ERPNext Desk.

What the Desk trail showed (Jun–Sep 2026): 705 Payment Entries, 347 Journal
Entries and 353 Purchase Invoices were cancelled and re-created by hand as
amendments — to change a posting date (JE ×221, PE ×160), a bank/cash account or
mode of payment, a reference date, a line's expense account, an amount. The
portal could amend (cancel → linked draft) but the draft itself was read-only
beyond three cosmetic fields, so the edit still needed the Desk.

Two entry points:
- get_draft / save_draft — a schema-driven editor for a docstatus-0 document
  (header fields + child rows). Saving runs ERPNext's own validate, so totals,
  taxes and currency amounts recompute exactly as they would in the Desk. Not
  gated (a draft posts nothing); every save is logged as "Edit draft".
- redate — the single most common amendment, as one click: cancel → copy →
  new posting date → submit. Gated like Amend (it reverses posted GL).
"""
import json

import frappe
from frappe.utils import flt, cint, getdate

from accounting_portal.api import _actions, bulk
from accounting_portal.api.permissions import (
    assert_can_write, assert_portal_access, resolve_companies,
)

REDATE_ACTION = "Redate document"
EDIT_ACTION = "Edit draft"

# Field spec: (fieldname, type, options_key, read_only)
#   type ∈ Date · Data · Text · Currency · Float · Int · Check · Select · Link · Party
#   options_key → a list in the `options` dict returned by get_draft (Select/Link)
#   Party → the frontend searches accountant.party_options with the row/header party_type
#   ro          → never editable
#   roe         → editable only on a row the user is adding (an existing line's
#                 item cannot change: ERPNext's update_child_qty_rate reads qty,
#                 rate, uom and the date off an existing row and ignores a new
#                 item_code, so offering it would be a control that does nothing)
_H = lambda f, t, o=None, ro=False, roe=False: {  # noqa: E731
    "field": f, "type": t, "options": o, "ro": ro, "ro_existing": roe}

# The additional discount ERPNext puts at the foot of an order or invoice: a
# percentage OR a flat amount, applied to the net or the grand total. It is the
# one thing a supplier's price negotiation lands on that the portal had no field
# for, so an order with a deal on it went to the Desk. Draft only — ERPNext does
# not mark any of the three editable after submit, and it should not: the
# discount moves the total, and the total is posted.
_DISCOUNT = lambda: [  # noqa: E731
    _H("apply_discount_on", "Select", "discount_on"),
    _H("additional_discount_percentage", "Float"),
    _H("discount_amount", "Currency"),
]

_SCHEMA = {
    "Journal Entry": {
        "header": [_H("posting_date", "Date"), _H("voucher_type", "Select", "voucher_types"),
                   _H("cheque_no", "Data"), _H("cheque_date", "Date"), _H("user_remark", "Text")],
        "child": {"field": "accounts", "can_add": True, "can_remove": True,
                  "columns": [_H("account", "Link", "accounts"), _H("party_type", "Select", "party_types"),
                              _H("party", "Party"), _H("debit_in_account_currency", "Currency"),
                              _H("credit_in_account_currency", "Currency"), _H("cost_center", "Link", "cost_centers"),
                              _H("user_remark", "Data")]},
    },
    "Payment Entry": {
        "header": [_H("posting_date", "Date"), _H("payment_type", "Select", "payment_types"),
                   _H("mode_of_payment", "Link", "modes"), _H("party_type", "Select", "party_types"),
                   _H("party", "Party"), _H("paid_from", "Link", "accounts"), _H("paid_to", "Link", "accounts"),
                   _H("paid_amount", "Currency"), _H("received_amount", "Currency"),
                   _H("source_exchange_rate", "Float"), _H("target_exchange_rate", "Float"),
                   _H("reference_no", "Data"), _H("reference_date", "Date"), _H("remarks", "Text")],
        "child": {"field": "references", "can_add": False, "can_remove": True, "fill": "outstanding",
                  "columns": [_H("reference_doctype", "Data", ro=True), _H("reference_name", "Data", ro=True),
                              _H("total_amount", "Currency", ro=True), _H("outstanding_amount", "Currency", ro=True),
                              _H("allocated_amount", "Currency")]},
    },
    "Purchase Invoice": {
        "header": [_H("posting_date", "Date"), _H("due_date", "Date"), _H("bill_no", "Data"),
                   _H("bill_date", "Date")] + _DISCOUNT() + [_H("remarks", "Text")],
        # A bill that arrives with a line missing is the accountant's daily case —
        # on the Desk they just add it. Only the two invoice doctypes allow it:
        # a stock line (Delivery Note / Purchase Receipt) also needs a warehouse
        # and batch handling, which this editor does not ask for.
        "child": {"field": "items", "can_add": True, "can_remove": True,
                  "columns": [_H("item_code", "Item"), _H("item_name", "Data", ro=True),
                              _H("qty", "Float"), _H("rate", "Currency"), _H("expense_account", "Link", "accounts"),
                              _H("cost_center", "Link", "cost_centers")]},
        # After submit: the account a line hit can still change (allow_on_submit) —
        # the clean-fix doctrine (edit the line, repost the ledger; no correction JE).
        # The Desk trail showed 203 Purchase Invoices reposted this way in 6 months.
        "submitted": {"columns": [_H("item_code", "Data", ro=True), _H("item_name", "Data", ro=True),
                                  _H("amount", "Currency", ro=True), _H("expense_account", "Link", "accounts"),
                                  _H("cost_center", "Link", "cost_centers")]},
        # The tax rows carry their own account, and it is the one that goes wrong:
        # a bill booked to the wrong VAT account posts the whole tax line to the
        # wrong place. ERPNext leaves account_head open after submit for exactly
        # this, and the repost below makes the ledger follow.
        "submitted_tax": {"field": "taxes",
                          "columns": [_H("description", "Data", ro=True), _H("tax_amount", "Currency", ro=True),
                                      _H("account_head", "Link", "accounts"), _H("cost_center", "Link", "cost_centers")]},
    },
    "Sales Invoice": {
        # po_no is the one header field ERPNext leaves open after submit, and the
        # customer's PO number is exactly what arrives late.
        "header": [_H("posting_date", "Date"), _H("due_date", "Date"), _H("po_no", "Data")]
                  + _DISCOUNT() + [_H("remarks", "Text")],
        "child": {"field": "items", "can_add": True, "can_remove": True,
                  "columns": [_H("item_code", "Item"), _H("item_name", "Data", ro=True),
                              _H("qty", "Float"), _H("rate", "Currency")]},
        "submitted": {"columns": [_H("item_code", "Data", ro=True), _H("item_name", "Data", ro=True),
                                  _H("amount", "Currency", ro=True), _H("income_account", "Link", "accounts"),
                                  _H("cost_center", "Link", "cost_centers")]},
        # The tax rows carry their own account, and it is the one that goes wrong:
        # a bill booked to the wrong VAT account posts the whole tax line to the
        # wrong place. ERPNext leaves account_head open after submit for exactly
        # this, and the repost below makes the ledger follow.
        "submitted_tax": {"field": "taxes",
                          "columns": [_H("description", "Data", ro=True), _H("tax_amount", "Currency", ro=True),
                                      _H("account_head", "Link", "accounts"), _H("cost_center", "Link", "cost_centers")]},
    },
    "Additional Salary": {
        "header": [_H("employee", "Party"), _H("salary_component", "Link", "components"),
                   _H("amount", "Currency"), _H("payroll_date", "Date"),
                   _H("overwrite_salary_structure_amount", "Check")],
        "child": None,
    },
    "Delivery Note": {
        "header": [_H("posting_date", "Date"), _H("remarks", "Text")],
        "child": {"field": "items", "can_add": False, "can_remove": True,
                  "columns": [_H("item_code", "Data", ro=True), _H("item_name", "Data", ro=True),
                              _H("qty", "Float"), _H("rate", "Currency")]},
    },
    "Purchase Receipt": {
        "header": [_H("posting_date", "Date"), _H("supplier_delivery_note", "Data"), _H("remarks", "Text")],
        "child": {"field": "items", "can_add": False, "can_remove": True,
                  "columns": [_H("item_code", "Data", ro=True), _H("item_name", "Data", ro=True),
                              _H("qty", "Float"), _H("rate", "Currency")]},
    },
    # Orders: editable as drafts AND as submitted documents ("Update Items" on the
    # Desk — qty/rate only, through ERPNext's update_child_qty_rate).
    "Sales Order": {
        "header": [_H("delivery_date", "Date"), _H("po_no", "Data")] + _DISCOUNT(),
        # A draft order takes lines like any other draft — the Desk allows it and
        # the portal used to refuse, which is why an order that arrived with the
        # wrong item had to be opened in the Desk to fix one row.
        "child": {"field": "items", "can_add": True, "can_remove": True,
                  "columns": [_H("item_code", "Item"), _H("item_name", "Data", ro=True),
                              _H("qty", "Float"), _H("rate", "Currency")]},
        # Once submitted only qty and rate move, through update_child_qty_rate.
        "submitted_ok": True,
        "submitted_columns": [_H("item_code", "Item", roe=True), _H("item_name", "Data", ro=True),
                              _H("qty", "Float"), _H("rate", "Currency"), _H("delivery_date", "Date")],
    },
    "Purchase Order": {
        "header": [_H("schedule_date", "Date")],
        "child": {"field": "items", "can_add": True, "can_remove": True,
                  "columns": [_H("item_code", "Item"), _H("item_name", "Data", ro=True),
                              _H("qty", "Float"), _H("rate", "Currency")]},
        "submitted_ok": True,
        "submitted_columns": [_H("item_code", "Item", roe=True), _H("item_name", "Data", ro=True),
                              _H("qty", "Float"), _H("rate", "Currency"), _H("schedule_date", "Date")],
    },
}


def _order_lines_locked(doc):
    """Whether a submitted order's lines are past changing, and why — the same
    three conditions the Desk uses to decide whether to offer Update Items at all.
    The portal used to open the editor regardless and let the user type into a
    document ERPNext would refuse on save."""
    st = doc.get("status") or ""
    if st in ("Closed", "Delivered"):
        return st.lower()
    received = flt(doc.get("per_delivered" if doc.doctype == "Sales Order" else "per_received"))
    if received >= 100 or flt(doc.get("per_billed")) >= 100:
        return "completed"
    return ""
# Additional Salary has no party_type field; the Party picker searches Employees.
_PARTY_FIXED = {"Additional Salary": "Employee"}
# Redate is the amend-and-resubmit shortcut; these carry a posting_date.
_REDATE_OK = ("Journal Entry", "Payment Entry", "Purchase Invoice", "Sales Invoice", "Additional Salary")
_REDATE_FIELD = {"Additional Salary": "payroll_date"}

_TYPE_CAST = {"Currency": flt, "Float": flt, "Int": cint, "Check": cint}


def _company_ok(doc):
    if doc.company not in resolve_companies():
        frappe.throw("Not permitted", frappe.PermissionError)


def _options(doctype, company):
    out = {}
    acc = frappe.db.sql(
        "SELECT name AS value, name AS label, account_type AS type, account_currency AS currency "
        "FROM `tabAccount` WHERE company=%s AND is_group=0 AND disabled=0 ORDER BY name", (company,), as_dict=True)
    out["accounts"] = acc
    out["cost_centers"] = frappe.db.sql(
        "SELECT name AS value, name AS label FROM `tabCost Center` WHERE company=%s AND is_group=0 AND disabled=0 ORDER BY name",
        (company,), as_dict=True)
    out["party_types"] = [{"value": v, "label": v} for v in ("", "Customer", "Supplier", "Employee")]
    out["discount_on"] = [{"value": "", "label": "—"},
                          {"value": "Grand Total", "label": "Grand Total"},
                          {"value": "Net Total", "label": "Net Total"}]
    if doctype == "Journal Entry":
        out["voucher_types"] = [{"value": v, "label": v} for v in (
            "Journal Entry", "Bank Entry", "Cash Entry", "Credit Card Entry", "Contra Entry",
            "Debit Note", "Credit Note", "Write Off Entry", "Exchange Rate Revaluation", "Deferred Revenue", "Deferred Expense")]
    if doctype == "Payment Entry":
        out["payment_types"] = [{"value": v, "label": v} for v in ("Receive", "Pay", "Internal Transfer")]
        out["modes"] = [{"value": r[0], "label": r[0]} for r in frappe.db.sql(
            "SELECT name FROM `tabMode of Payment` WHERE enabled=1 ORDER BY name")]
    if doctype == "Additional Salary":
        out["components"] = [{"value": r[0], "label": f"{r[0]} ({r[1]})"} for r in frappe.db.sql(
            "SELECT name, type FROM `tabSalary Component` WHERE IFNULL(disabled,0)=0 ORDER BY type, name")]
    return out


def _val(v):
    if v is None:
        return ""
    return str(v)


@frappe.whitelist()
def get_draft(doctype=None, name=None):
    """The editable view of a draft. Returns supported=False (not an error) when
    the document is not a draft or the doctype has no editor, so the UI can fall
    back to the small after-submit field editor."""
    assert_portal_access()
    if doctype not in _SCHEMA or not name or not frappe.db.exists(doctype, name):
        return {"supported": False, "reason": "unsupported"}
    doc = frappe.get_doc(doctype, name)
    _company_ok(doc)
    spec = _SCHEMA[doctype]
    submitted_mode = doc.docstatus == 1 and (spec.get("submitted_ok") or spec.get("submitted"))
    if doc.docstatus != 0 and not submitted_mode:
        return {"supported": False, "reason": "not_draft", "docstatus": doc.docstatus}
    meta = frappe.get_meta(doctype)
    header = []
    for h in spec["header"]:
        if not meta.has_field(h["field"]):
            continue
        df = meta.get_field(h["field"])
        # A submitted document still takes the fields ERPNext marks editable after
        # submit — the customer PO number on an invoice, the promised date on an
        # order. The editor used to drop the whole header the moment a document was
        # submitted, so those became unreachable from the portal even though our own
        # allow-list named them and the Desk edits them in place.
        if submitted_mode and not df.allow_on_submit:
            continue
        header.append({**h, "label": df.label if df else h["field"], "value": _val(doc.get(h["field"]))})
    child = None
    if spec["child"]:
        cf = spec["child"]["field"]
        cmeta = frappe.get_meta(meta.get_field(cf).options)
        cols = []
        col_spec = spec["child"]["columns"]
        if submitted_mode:
            col_spec = (spec.get("submitted") or {}).get("columns") or spec.get("submitted_columns") or col_spec
        for c in col_spec:
            if not cmeta.has_field(c["field"]):
                continue
            df = cmeta.get_field(c["field"])
            cols.append({**c, "label": df.label if df else c["field"]})
        rows = []
        for r in doc.get(cf) or []:
            row = {"name": r.name, "idx": r.idx}
            for c in cols:
                row[c["field"]] = _val(r.get(c["field"]))
            rows.append(row)
        # A draft takes whatever the doctype allows. A submitted order takes lines
        # too — that is what the Desk's Update Items does — unless it is closed or
        # fully received/billed. A submitted invoice never does: there the editor
        # only moves a line's account and reposts.
        locked = ""
        if not submitted_mode:
            can_add, can_remove = spec["child"]["can_add"], spec["child"]["can_remove"]
        elif spec.get("submitted_ok"):
            locked = _order_lines_locked(doc)
            can_add = can_remove = not locked
        else:
            can_add = can_remove = False
        child = {"field": cf, "label": meta.get_field(cf).label or cf, "columns": cols, "rows": rows,
                 "can_add": can_add, "can_remove": can_remove, "locked": locked,
                 # Drives the "Get outstanding invoices" picker on a Payment Entry;
                 # without it the allocation endpoints are unreachable from the UI.
                 "fill": spec["child"].get("fill")}
    tax = None
    ts = spec.get("submitted_tax")
    if submitted_mode and ts and meta.has_field(ts["field"]):
        tmeta = frappe.get_meta(meta.get_field(ts["field"]).options)
        tcols = [{**c, "label": (tmeta.get_field(c["field"]).label or c["field"])}
                 for c in ts["columns"] if tmeta.has_field(c["field"])]
        tax = {"field": ts["field"], "label": meta.get_field(ts["field"]).label or ts["field"],
               "columns": tcols,
               "rows": [{"name": r.name, "idx": r.idx, **{c["field"]: _val(r.get(c["field"])) for c in tcols}}
                        for r in (doc.get(ts["field"]) or [])]}
    return {"supported": True, "doctype": doctype, "name": name, "company": doc.company, "tax": tax,
            "docstatus": doc.docstatus, "submitted_mode": bool(submitted_mode),
            "submitted_kind": ("reaccount" if spec.get("submitted") else "update_items") if submitted_mode else None,
            "is_return": bool(doc.get("is_return")),
            # Changing the lines of a reserved order releases the reservation. The
            # Desk asks before it does that; so does the portal now.
            "reserved_stock": bool(submitted_mode and doctype == "Sales Order" and frappe.db.exists(
                "Stock Reservation Entry", {"voucher_no": name, "docstatus": 1})),
            "currency": doc.get("currency") or doc.get("paid_from_account_currency") or frappe.get_cached_value("Company", doc.company, "default_currency"),
            "party_type_fixed": _PARTY_FIXED.get(doctype), "header": header, "child": child,
            "options": _options(doctype, doc.company)}


def _cast(spec_type, v):
    if v in (None, ""):
        return None if spec_type in ("Date", "Link", "Party", "Select", "Data", "Text", "Item") else 0
    fn = _TYPE_CAST.get(spec_type)
    return fn(v) if fn else v


@frappe.whitelist()
def save_draft(doctype=None, name=None, header=None, rows=None, tax=None):
    """Apply edits to a draft and save it through ERPNext's validate. `header` is
    {field: value}; `rows` is the full child table as the user left it — rows
    with a `name` are updated, rows without one are appended (where allowed),
    rows missing from the list are removed (where allowed)."""
    assert_can_write()
    if doctype not in _SCHEMA or not name or not frappe.db.exists(doctype, name):
        frappe.throw("Not editable")
    doc = frappe.get_doc(doctype, name)
    _company_ok(doc)
    header = header if isinstance(header, dict) else json.loads(header or "{}")
    rows = rows if isinstance(rows, list) else json.loads(rows or "null")
    tax = tax if isinstance(tax, list) else json.loads(tax or "null")
    spec = _SCHEMA[doctype]
    if doc.docstatus == 1 and spec.get("submitted_ok"):
        return _update_submitted_items(doc, spec, header, rows)
    if doc.docstatus == 1 and spec.get("submitted"):
        return _reaccount_submitted(doc, spec, header, rows, tax)
    if doc.docstatus != 0:
        frappe.throw("Only a draft can be edited. Amend the document first.")
    before = {}
    changed = {}
    for h in spec["header"]:
        f = h["field"]
        if h["ro"] or f not in header or not doc.meta.has_field(f):
            continue
        new = _cast(h["type"], header[f])
        old = doc.get(f)
        if _val(old) != _val(new):
            before[f] = _val(old)
            changed[f] = _val(new)
            doc.set(f, new)
    row_note = None
    if rows is not None and spec["child"]:
        cf = spec["child"]["field"]
        cols = [c for c in spec["child"]["columns"] if not c["ro"]]
        existing = {r.name: r for r in (doc.get(cf) or [])}
        kept = []
        added = 0
        for r in rows:
            rn = r.get("name")
            if rn and rn in existing:
                row = existing[rn]
            else:
                if not spec["child"]["can_add"]:
                    continue
                row = doc.append(cf, {})
                added += 1
            prev_item = row.get("item_code")
            for c in cols:
                if c["field"] in r:
                    row.set(c["field"], _cast(c["type"], r[c["field"]]))
            # A new line, or a line whose item changed, must let ERPNext refill the
            # fields that hang off item_code (name, description, uom, conversion
            # factor, default accounts) — otherwise the row keeps the old item's.
            if row.meta.has_field("item_code") and row.get("item_code") != prev_item:
                for dep in ("item_name", "description", "uom", "stock_uom", "conversion_factor"):
                    if row.meta.has_field(dep):
                        row.set(dep, None)
                if row.meta.has_field("qty") and not flt(row.get("qty")):
                    row.set("qty", 1)
            # An order line carries its own promised date, and ERPNext refuses the
            # save without one. A row typed into the portal has no way to supply it,
            # so it inherits the order's — which is what the Desk grid pre-fills too.
            for df in ("delivery_date", "schedule_date"):
                if row.meta.has_field(df) and not row.get(df):
                    row.set(df, doc.get(df) or doc.get("transaction_date") or frappe.utils.nowdate())
            # A credit/debit note carries negative quantities; ERPNext rejects the
            # save otherwise ("quantity must be negative number").
            if doc.get("is_return") and row.meta.has_field("qty") and flt(row.get("qty")) > 0:
                row.set("qty", -abs(flt(row.get("qty"))))
            kept.append(row)
        removed = 0
        if spec["child"]["can_remove"]:
            keep_names = {r.name for r in kept if r.name}
            for rn, row in existing.items():
                if rn not in keep_names:
                    doc.remove(row)
                    removed += 1
        for i, row in enumerate(doc.get(cf) or [], start=1):
            row.idx = i
        row_note = {"rows": len(doc.get(cf) or []), "added": added, "removed": removed}
    if doctype in ("Purchase Invoice", "Sales Invoice") and changed.get("posting_date"):
        doc.set_posting_time = 1
    # Moving a date leaves the payment schedule behind. The schedule was written
    # from the OLD posting date, and ERPNext then refuses the save with "Due Date
    # cannot be before Posting / Supplier Invoice Date" — pointing at the two
    # dates on screen, which are in the right order, while the row it actually
    # objects to is not on screen at all. Reproduced on PUR-INV-05635-1: posting
    # 2025-04-21 → 2026-04-21 with a schedule row still on 2025-04-21.
    #
    # The Desk clears the schedule from its own form script whenever a date
    # moves. Emptying it here does the same: ERPNext's set_payment_schedule
    # rebuilds it from the new dates and the supplier's terms.
    if doc.meta.has_field("payment_schedule") and any(
            changed.get(f) for f in ("posting_date", "due_date", "bill_date", "transaction_date")):
        doc.set("payment_schedule", [])
    doc.flags.ignore_permissions = True
    doc.save()
    _actions.record(
        EDIT_ACTION, doc.company, reference_doctype=doctype, reference_name=name,
        voucher_type=doctype, voucher_no=name,
        amount=flt(doc.get(bulk._ALLOWED.get(doctype, "")) or 0) if bulk._ALLOWED.get(doctype) else 0,
        payload=json.dumps({"before": before, "after": changed, "rows": row_note}),
        result=json.dumps({"saved": name}), notes=f"Edited draft {name}")
    return get_draft(doctype, name)


def _submitted_header_changes(doc, spec, header):
    """Apply the header fields ERPNext marks editable-after-submit, and report the
    diff. Anything not flagged allow_on_submit is left alone — ERPNext would throw
    on save, and a field the portal cannot actually change should never be offered.
    The caller saves; it knows whether the ledger has to be reposted too."""
    before, after = {}, {}
    for h in spec["header"]:
        f = h["field"]
        if h["ro"] or f not in (header or {}) or not doc.meta.has_field(f):
            continue
        if not doc.meta.get_field(f).allow_on_submit:
            continue
        new = _cast(h["type"], header[f])
        if _val(doc.get(f)) != _val(new):
            before[f] = _val(doc.get(f))
            after[f] = _val(new)
            doc.set(f, new)
    return before, after


def _update_submitted_items(doc, spec, header, rows):
    """'Update Items' on a submitted order, through ERPNext's own
    update_child_qty_rate — which recomputes the order's totals, reservations and
    status, and refuses a line that has already been delivered, received or billed.
    Lines can be changed, added, re-dated and removed, exactly as the Desk grid
    allows; any after-submit header field is applied first. Audited with the diff."""
    before, after = _submitted_header_changes(doc, spec, header)
    if after:
        doc.flags.ignore_permissions = True
        doc.save()
    date_field = "delivery_date" if doc.doctype == "Sales Order" else "schedule_date"
    existing = {r.name: r for r in (doc.get("items") or [])}
    # A save that carries no line list at all is a header-only save; echo the lines
    # back unchanged so nothing is read as a deletion.
    if not isinstance(rows, list):
        rows = [{"name": n} for n in existing]
    trans, diff = [], []
    for r in rows:
        row = existing.get(r.get("name"))
        if row is None:
            item = (r.get("item_code") or "").strip()
            if not item:
                continue                    # a blank line the user added and left empty
            qty = flt(r.get("qty")) or 1
            rate = flt(r.get("rate"))
            when = _val(r.get(date_field)) or _val(doc.get(date_field)) or frappe.utils.nowdate()
            # No docname: ERPNext builds the row from the item master — warehouse,
            # UOM, conversion factor, item tax template and all.
            trans.append({"item_code": item, "qty": qty, "rate": rate, date_field: when})
            diff.append({"added": item, "qty": qty, "rate": rate})
            continue
        qty = flt(r.get("qty")) if r.get("qty") not in (None, "") else flt(row.qty)
        rate = flt(r.get("rate")) if r.get("rate") not in (None, "") else flt(row.rate)
        when = _val(r.get(date_field)) or _val(row.get(date_field)) or _val(doc.get(date_field)) or ""
        if qty != flt(row.qty) or rate != flt(row.rate) or when != _val(row.get(date_field)):
            diff.append({"item": row.item_code, "qty": [flt(row.qty), qty], "rate": [flt(row.rate), rate],
                         "date": [_val(row.get(date_field)), when]})
        trans.append({"docname": row.name, "name": row.name, "item_code": row.item_code, "qty": qty, "rate": rate,
                      "uom": row.uom, "conversion_factor": row.conversion_factor or 1, date_field: when})
    # Anything ERPNext does not see in the list it deletes — and refuses to, for a
    # line already delivered, received, billed or ordered against.
    kept = {t.get("docname") for t in trans if t.get("docname")}
    for name, row in existing.items():
        if name not in kept:
            diff.append({"removed": row.item_code, "qty": flt(row.qty)})
    if diff and _order_lines_locked(doc):
        frappe.throw("This order's lines can no longer change: it is "
                     + (doc.get("status") or "").lower() + " or fully received and billed.")
    if not diff and not after:
        frappe.throw("Nothing changed")
    if diff:
        frappe.flags.ignore_permissions = True
        try:
            frappe.get_attr("erpnext.controllers.accounts_controller.update_child_qty_rate")(
                doc.doctype, json.dumps(trans), doc.name)
        finally:
            frappe.flags.ignore_permissions = False
    _actions.record(
        EDIT_ACTION, doc.company, reference_doctype=doc.doctype, reference_name=doc.name,
        voucher_type=doc.doctype, voucher_no=doc.name,
        amount=flt(frappe.db.get_value(doc.doctype, doc.name, "grand_total") or 0),
        payload=json.dumps({"update_items": diff, "before": before, "after": after}),
        result=json.dumps({"saved": doc.name}),
        notes=f"Updated {len(diff)} line change(s) and {len(after)} field(s) on submitted {doc.doctype} {doc.name}")
    return get_draft(doc.doctype, doc.name)


# ── Clean fix on a posted invoice: change the line's account, repost the ledger ─

REPOST_ACTION = "Repost ledger"
_GL_DOCTYPES = ("Journal Entry", "Payment Entry", "Purchase Invoice", "Sales Invoice", "Delivery Note", "Purchase Receipt")


def _make_repost(company, doctype, name):
    r = frappe.get_doc({"doctype": "Repost Accounting Ledger", "company": company, "delete_cancelled_entries": 0,
                        "vouchers": [{"voucher_type": doctype, "voucher_no": name}]})
    r.flags.ignore_permissions = True
    r.insert()
    r.submit()
    return r.name


def _reaccount_submitted(doc, spec, header, rows, tax=None):
    before, after = _submitted_header_changes(doc, spec, header)
    rows = rows or []
    cols = [c for c in spec["submitted"]["columns"] if not c["ro"]]
    by_name = {r.get("name"): r for r in rows if r.get("name")}
    diff = []
    for row in doc.get("items") or []:
        r = by_name.get(row.name)
        if not r:
            continue
        for c in cols:
            f = c["field"]
            if f in r and _val(r[f]) != _val(row.get(f)):
                diff.append({"row": row.idx, "item": row.item_code, "field": f, "from": _val(row.get(f)), "to": _val(r[f])})
                row.set(f, r[f] or None)
    ts = spec.get("submitted_tax")
    if ts and tax:
        tcols = [c for c in ts["columns"] if not c["ro"]]
        by_tax = {r.get("name"): r for r in tax if r.get("name")}
        for row in doc.get(ts["field"]) or []:
            r = by_tax.get(row.name)
            if not r:
                continue
            for c in tcols:
                f = c["field"]
                if f in r and _val(r[f]) != _val(row.get(f)):
                    diff.append({"row": row.idx, "tax": row.description, "field": f,
                                 "from": _val(row.get(f)), "to": _val(r[f])})
                    row.set(f, r[f] or None)
    if not diff and not after:
        frappe.throw("Nothing changed")
    doc.flags.ignore_permissions = True
    doc.save()                                   # only allow_on_submit fields — ERPNext enforces it
    # The ledger is rebuilt only when a line's account moved. A customer PO number
    # or a promised date does not touch a single GL row, and reposting for one
    # would delete and rewrite every entry on the voucher for nothing.
    if not diff:
        _actions.record(
            EDIT_ACTION, doc.company, reference_doctype=doc.doctype, reference_name=doc.name,
            voucher_type=doc.doctype, voucher_no=doc.name,
            amount=flt(frappe.db.get_value(doc.doctype, doc.name, "grand_total") or 0),
            payload=json.dumps({"before": before, "after": after}),
            result=json.dumps({"saved": doc.name}),
            notes=f"Edited {len(after)} field(s) on submitted {doc.doctype} {doc.name}")
        return get_draft(doc.doctype, doc.name)
    repost = _make_repost(doc.company, doc.doctype, doc.name)
    _actions.record(
        REPOST_ACTION, doc.company, reference_doctype=doc.doctype, reference_name=doc.name,
        voucher_type="Repost Accounting Ledger", voucher_no=repost,
        amount=flt(frappe.db.get_value(doc.doctype, doc.name, "grand_total") or 0),
        payload=json.dumps({"changes": diff, "before": before, "after": after}),
        result=json.dumps({"repost": repost}),
        notes=f"Re-accounted {len(diff)} line(s) on {doc.doctype} {doc.name} and reposted")
    return get_draft(doc.doctype, doc.name)


@frappe.whitelist()
def repost_ledger(doctype=None, name=None, company=None):
    """Repost one submitted voucher's GL (Repost Accounting Ledger) — after an
    after-submit field change, or when the ledger and the document disagree."""
    assert_can_write()
    if doctype not in _GL_DOCTYPES or not name or not frappe.db.exists(doctype, name):
        frappe.throw("Repost is not available for this document")
    d = frappe.db.get_value(doctype, name, ["company", "docstatus"], as_dict=True)
    if d.company not in resolve_companies(company):
        frappe.throw("Not permitted", frappe.PermissionError)
    if d.docstatus != 1:
        frappe.throw("Only a submitted document can be reposted")
    repost = _make_repost(d.company, doctype, name)
    _actions.record(
        REPOST_ACTION, d.company, reference_doctype=doctype, reference_name=name,
        voucher_type="Repost Accounting Ledger", voucher_no=repost, amount=0,
        payload=json.dumps({"doctype": doctype, "name": name}), result=json.dumps({"repost": repost}),
        notes=f"Repost ledger of {doctype} {name}")
    return {"repost": repost}


# ── Redate: cancel → copy → new date → submit, one click ───────────────────────

def _redate_poster(action):
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    dt, name, new_date = p["doctype"], p["name"], p["posting_date"]
    d = frappe.get_doc(dt, name)
    d.flags.ignore_permissions = True
    if d.docstatus == 1:
        d.cancel()
    elif d.docstatus != 2:
        frappe.throw("Only a submitted or cancelled document can be redated")
    new = frappe.copy_doc(d)
    new.amended_from = name
    new.set(_REDATE_FIELD.get(dt, "posting_date"), new_date)
    if new.meta.has_field("set_posting_time"):
        new.set_posting_time = 1
    # The copy carries the original's payment schedule, still written against the
    # OLD date. Moving the document forward then fails on "Due Date cannot be
    # before Posting / Supplier Invoice Date" — about a row nobody can see.
    # Empty it and ERPNext rebuilds it from the new date and the party's terms.
    if new.meta.has_field("payment_schedule"):
        new.set("payment_schedule", [])
        if new.meta.has_field("due_date") and new.get("due_date") and str(new.due_date) < str(new_date):
            new.due_date = None          # let it be derived rather than trail the posting date
    new.flags.ignore_permissions = True
    new.insert()
    new.submit()
    return {"voucher_type": dt, "voucher_no": new.name,
            "result": {"amended_from": name, "new_doc": new.name, "posting_date": str(new_date)}}


_actions.register_poster(REDATE_ACTION, _redate_poster)


@frappe.whitelist()
def redate(doctype=None, name=None, posting_date=None, company=None):
    """Move a posted document to another date without retyping it: cancel, copy
    as an amendment with the new date, submit. Gated by the document amount."""
    assert_can_write()
    if doctype not in _REDATE_OK:
        frappe.throw(f"Redate is not available for {doctype}")
    if not (name and posting_date):
        frappe.throw("Document and new date are required")
    new_date = str(getdate(posting_date))
    doc_company = frappe.db.get_value(doctype, name, "company")
    if not doc_company or doc_company not in resolve_companies(company):
        frappe.throw("Not permitted", frappe.PermissionError)
    field = _REDATE_FIELD.get(doctype, "posting_date")
    if str(frappe.db.get_value(doctype, name, field)) == new_date:
        frappe.throw("That is already the document's date")
    if frappe.db.get_value(doctype, name, "docstatus") not in (1, 2):
        frappe.throw("Only a submitted document can be redated — a draft is edited directly")
    if frappe.db.get_value(doctype, {"amended_from": name}, "name"):
        frappe.throw("This document was already amended")
    amt = flt(frappe.db.get_value(doctype, name, bulk._ALLOWED[doctype]) or 0) if doctype in bulk._ALLOWED else 0
    key = f"redate:{doctype}:{name}:{new_date}"
    return _actions.execute(
        REDATE_ACTION, doc_company, key,
        payload={"doctype": doctype, "name": name, "posting_date": new_date},
        amount=amt, reference_doctype=doctype, reference_name=name,
        notes=f"Redate {doctype} {name} → {new_date}")


# ── "Get outstanding invoices" for a draft Payment Entry ───────────────────────

@frappe.whitelist()
def outstanding_for_payment(name=None):
    """Open invoices of the payment's party that this draft could settle, oldest
    first. The Desk's "Get outstanding invoices" — receipts had no allocation UI
    at all, so cash landed on the wrong invoice and could only be re-pointed in
    the Desk."""
    assert_portal_access()
    if not name or not frappe.db.exists("Payment Entry", name):
        frappe.throw("Payment not found")
    pe = frappe.get_doc("Payment Entry", name)
    if pe.company not in resolve_companies():
        frappe.throw("Not permitted", frappe.PermissionError)
    dt = "Sales Invoice" if pe.party_type == "Customer" else "Purchase Invoice"
    if not pe.party:
        return {"rows": [], "doctype": dt, "unallocated": 0}
    taken = {r.reference_name for r in pe.references if r.reference_name}
    party_col = "customer" if dt == "Sales Invoice" else "supplier"
    rows = frappe.db.sql(
        f"""SELECT name, posting_date AS date, due_date, ROUND(grand_total,2) AS total,
                   ROUND(outstanding_amount,2) AS outstanding, currency
            FROM `tab{dt}` WHERE company=%s AND {party_col}=%s AND docstatus=1
              AND IFNULL(is_return,0)=0 AND outstanding_amount > 0
            ORDER BY posting_date, name""", (pe.company, pe.party), as_dict=True)
    rows = [r for r in rows if r.name not in taken]
    for r in rows:
        r["date"] = str(r["date"] or "")
        r["due_date"] = str(r["due_date"] or "")
    allocated = sum(flt(r.allocated_amount) for r in pe.references)
    return {"rows": rows, "doctype": dt, "party": pe.party,
            "paid_amount": flt(pe.paid_amount), "allocated": allocated,
            "unallocated": round(flt(pe.paid_amount) - allocated, 2)}


@frappe.whitelist()
def allocate_payment(name=None, rows=None):
    """Append chosen invoices to a DRAFT payment's references with the amounts the
    user set (auto-filled oldest-first against the unallocated balance)."""
    assert_can_write()
    if not name or not frappe.db.exists("Payment Entry", name):
        frappe.throw("Payment not found")
    pe = frappe.get_doc("Payment Entry", name)
    if pe.company not in resolve_companies():
        frappe.throw("Not permitted", frappe.PermissionError)
    if pe.docstatus != 0:
        frappe.throw("Only a draft payment can be re-allocated — amend it first")
    rows = rows if isinstance(rows, list) else json.loads(rows or "[]")
    dt = "Sales Invoice" if pe.party_type == "Customer" else "Purchase Invoice"
    added = 0
    for r in rows:
        amt = flt(r.get("amount"))
        if not r.get("name") or amt <= 0:
            continue
        pe.append("references", {"reference_doctype": r.get("doctype") or dt,
                                 "reference_name": r["name"], "allocated_amount": amt})
        added += 1
    if not added:
        frappe.throw("Nothing to allocate")
    pe.flags.ignore_permissions = True
    pe.save()
    return get_draft("Payment Entry", name)
