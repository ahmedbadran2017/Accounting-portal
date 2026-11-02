"""Excel (.xlsx) downloads — real workbooks with numeric cells, built server-side
with frappe.utils.xlsxutils, so a statement or a ledger opens in Excel exactly as
the Desk's export did. Each endpoint is a GET that streams a file; the browser
session cookie authenticates it, so the frontend just opens the URL.

Why server-side: the SPA has no spreadsheet library, and a CSV renamed .xlsx is
not Excel (dates and numbers arrive as text, RTL names break). Frappe already
ships openpyxl for its own exports, so the cost is one endpoint per report.
"""
import frappe
from frappe.utils import flt
from frappe.utils.xlsxutils import make_xlsx

from accounting_portal.api.permissions import assert_portal_access

_MAX_ROWS = 50000


def _send(filename, sheet, data, widths=None):
    xlsx = make_xlsx(data, sheet, column_widths=widths)
    frappe.response["filename"] = filename
    frappe.response["filecontent"] = xlsx.getvalue()
    frappe.response["type"] = "binary"


def _num(v):
    v = flt(v)
    return v if v else None


@frappe.whitelist()
def statement_xlsx(party_type=None, party=None, company=None, from_date=None, to_date=None):
    """Customer / supplier account statement as a workbook: header block, opening,
    every movement with running balance, totals and closing."""
    assert_portal_access()
    from accounting_portal.api.reports import party_statement
    s = party_statement(party_type=party_type, party=party, company=company, from_date=from_date, to_date=to_date)
    if not s:
        frappe.throw("No statement")
    data = [
        ["Account statement", s.get("party_name") or party, "", "", "", ""],
        ["Company", s.get("company"), "Currency", s.get("currency"), "", ""],
        ["Period", f"{s.get('from_date') or ''} → {s.get('to_date') or ''}", "", "", "", ""],
        [],
        ["Date", "Voucher", "Type", "Debit", "Credit", "Balance"],
        ["", "Opening balance", "", None, None, flt(s.get("opening"))],
    ]
    for r in s.get("rows") or []:
        data.append([r.get("date"), r.get("doc"), r.get("type"), _num(r.get("debit")), _num(r.get("credit")), flt(r.get("balance"))])
    data.append(["", "Totals", "", flt(s.get("debit_total")), flt(s.get("credit_total")), ""])
    data.append(["", "Closing balance", "", None, None, flt(s.get("closing"))])
    safe = "".join(ch for ch in str(party) if ch.isalnum() or ch in "-_ ")[:40].strip() or "party"
    _send(f"statement-{safe}-{from_date or ''}-{to_date or ''}.xlsx", "Statement", data, [12, 22, 18, 14, 14, 16])


@frappe.whitelist()
def gl_xlsx(company=None, account=None, party=None, voucher_no=None, from_date=None, to_date=None, include_cancelled=0, group_by=None):
    """General ledger, the WHOLE filtered set (not the page on screen), up to
    50,000 rows, oldest first, with the running balance when one account is
    filtered. Pulls pages from ledger.general_ledger so filters and totals stay
    identical to the screen."""
    assert_portal_access()
    from accounting_portal.api.ledger import general_ledger
    # Walk in big pages and compute the whole-set totals once. Paging at 500 with
    # the aggregate re-run every time took 19.8s for a single account-month.
    rows, start, page = [], 0, 5000
    first = None
    frappe.flags.ap_gl_bulk = True
    try:
        while True:
            frappe.flags.ap_gl_skip_totals = first is not None
            r = general_ledger(company=company, account=account or None, party=party or None, voucher_no=voucher_no or None,
                               from_date=from_date or None, to_date=to_date or None, start=start, page_size=page,
                               include_cancelled=include_cancelled, group_by=group_by or None)
            if first is None:
                first = r
            got = r.get("rows") or []
            rows.extend(got)
            # Step by the page size the endpoint ACTUALLY used, not the one asked
            # for. If it clamps the request, stepping by the request would skip
            # rows or stop early and hand over a silently truncated workbook.
            served = int(r.get("page_size") or 0) or len(got) or page
            start += served
            if len(got) < served or start >= min(int(first.get("total") or 0), _MAX_ROWS):
                break
    finally:
        frappe.flags.ap_gl_bulk = False
        frappe.flags.ap_gl_skip_totals = False
    rows.reverse()   # newest-first on screen → oldest-first in the workbook
    single = bool(account) and not (first or {}).get('grouped')
    head = ["Date", "Voucher type", "Voucher", "Account", "Party type", "Party", "Debit", "Credit",
            "Account currency", "Debit (account currency)", "Credit (account currency)", "Cost center", "Against", "Remarks", "Cancelled"]
    if single:
        head.append("Balance")
    data = [
        ["General ledger", first.get("company") if first else company, "Currency", first.get("currency") if first else ""],
        ["Account", account or "(all)", "Party", party or "(all)"],
        ["Period", f"{from_date or ''} → {to_date or ''}", "Rows", len(rows)],
        ["Totals", "", "Debit", flt(first.get("total_dr")) if first else 0, "Credit", flt(first.get("total_cr")) if first else 0,
         "Opening", flt(first.get("opening")) if (first and single) else "", "Closing", flt(first.get("closing")) if (first and single) else ""],
        [],
        head,
    ]
    for g in rows:
        row = [g.get("date"), g.get("voucher_type"), g.get("ref"), g.get("account"), g.get("party_type") or "", g.get("party") or "",
               _num(g.get("dr")), _num(g.get("cr")), g.get("account_currency") or "", _num(g.get("dr_acc")), _num(g.get("cr_acc")),
               g.get("cost_center") or "", g.get("against") or "", (g.get("remarks") or "")[:500], "yes" if g.get("is_cancelled") else ""]
        if single:
            row.append(flt(g.get("balance")))
        data.append(row)
    tag = (account or "all").split(" ")[0]
    _send(f"general-ledger-{tag}-{from_date or ''}-{to_date or ''}.xlsx", "General ledger", data,
          [12, 16, 20, 40, 12, 28, 14, 14, 10, 16, 16, 24, 30, 40, 9, 16])


# ── Generic list export ────────────────────────────────────────────────────────
# Every transaction list is already a server-paginated endpoint returning
# {rows, total}. The export just walks that same endpoint with its own filters,
# so what lands in Excel is exactly what the accountant filtered on screen —
# not the 25 rows that happened to be on the page.

_LIST_EXPORTS = {
    "payroll_sheet": ("accounting_portal.api.payroll.payroll_sheet", "Payroll sheet",
                      [("employee", "ID"), ("employee_name", "Employee"),
                       ("designation", "Position"), ("contract", "Contract"),
                       ("base", "Salary"), ("rate", "Salary per hour"),
                       ("contract_hours", "General hours"), ("holiday_hours", "Public holiday"),
                       ("overtime_hours", "Overtime (hour)"), ("missing_hours", "Missing"),
                       ("delay_hours", "Delay (hour)"), ("total_hours", "Total hour"),
                       ("gross", "Payment"), ("bonus", "Performance"), ("advance", "Advance"),
                       ("other_deduction", "Other deductions"), ("net", "Net payment"), ("rib", "RIB"), ("sent", "Send"),
                       ("sent_on", "Sent on")]),
    "purchase_orders": ("accounting_portal.api.purchases.list_purchase_orders", "Purchase orders",
                        [("name", "Order"), ("date", "Date"), ("schedule_date", "Required by"),
                         ("supplier_name", "Vendor"), ("currency", "Currency"), ("amount", "Amount"),
                         ("base_amount", "Amount (company ccy)"), ("per_received", "% received"),
                         ("per_billed", "% billed"), ("status", "Status"), ("docstatus", "Docstatus")]),
    "bills": ("accounting_portal.api.purchases.list_bills", "Bills",
              [("name", "Bill"), ("date", "Date"), ("supplier", "Supplier"), ("bill_no", "Supplier invoice"),
               ("currency", "Currency"), ("amount", "Amount"), ("base_amount", "Amount (company ccy)"),
               ("status_norm", "Status"), ("match", "3-way match"), ("docstatus", "Docstatus")]),
    "invoices": ("accounting_portal.api.sales.list_invoices", "Sales invoices",
                 [("name", "Invoice"), ("date", "Date"), ("customer", "Customer"), ("net", "Net"),
                  ("vat", "VAT"), ("gross", "Gross"), ("outstanding_amount", "Outstanding"), ("status", "Status")]),
    "orders": ("accounting_portal.api.sales.list_orders", "Sales orders",
               [("name", "Order"), ("date", "Date"), ("customer", "Customer"), ("city", "City"),
                ("value", "Value"), ("state", "State"), ("carrier", "Carrier"),
                ("custom_track_shipment_status", "Tracking")]),
    "journals": ("accounting_portal.api.accountant.list_journals", "Journals",
                 [("name", "Entry"), ("date", "Date"), ("type", "Type"), ("amount", "Debit total"),
                  ("reference", "Cheque / ref"), ("remark", "Remark"), ("status", "Status")]),
    "payments_in": ("accounting_portal.api.sales.list_receipts", "Payments received",
                    [("name", "Payment"), ("date", "Date"), ("customer", "Party"), ("method", "Method"),
                     ("ref", "Reference"), ("collected", "Amount")]),
    "payments_out": ("accounting_portal.api.payments.list_payments_made", "Payments made",
                     [("name", "Payment"), ("date", "Date"), ("party_name", "Supplier"), ("method", "Method"),
                      ("reference_no", "Reference"), ("currency", "Currency"), ("amount", "Amount"),
                      ("unallocated", "Unallocated")]),
    "challans": ("accounting_portal.api.sales.list_challans", "Delivery notes",
                 [("name", "Delivery note"), ("date", "Date"), ("customer", "Customer"),
                  ("carrier", "Carrier"), ("tracking", "Tracking"), ("status", "Status")]),
}


def _collect_rows(key, filters):
    """Every row of a filtered list, through the list's own endpoint, so an
    export matches the screen."""
    spec = _LIST_EXPORTS.get(key)
    if not spec:
        frappe.throw("Unknown list")
    method, sheet, cols = spec
    fn = frappe.get_attr(method)
    filters.pop("cmd", None)
    for junk in ("start", "page_size", "limit", "key", "names"):
        filters.pop(junk, None)
    filters = {k: v for k, v in filters.items() if v not in (None, "", "undefined")}
    # Only pass what the list endpoint actually declares. The URL carries whatever
    # the screen had on it, and an unknown key would be a 500 instead of a download.
    import inspect
    target_fn = getattr(fn, "__wrapped__", fn)
    try:
        accepted = set(inspect.signature(target_fn).parameters)
        filters = {k: v for k, v in filters.items() if k in accepted}
    except (TypeError, ValueError):
        pass

    rows, start, page = [], 0, 200
    total = None
    while True:
        res = fn(start=start, page_size=page, **filters) or {}
        got = res.get("rows") or []
        if total is None:
            total = int(res.get("total") or len(got))
        rows.extend(got)
        start += page
        if len(got) < page or start >= min(total, _MAX_ROWS):
            break
    return rows, filters, sheet, cols


@frappe.whitelist()
def list_xlsx(key=None, **filters):
    """Excel of a whole filtered list. `key` picks the list; every other query
    parameter is passed through to that list's own endpoint (company, search,
    from_date, to_date, sort…), so the workbook matches the screen."""
    assert_portal_access()
    rows, filters, sheet, cols = _collect_rows(key, filters)
    data = [
        [sheet, filters.get("company") or "", "Rows", len(rows)],
        ["Filters", ", ".join(f"{k}={v}" for k, v in sorted(filters.items()) if k != "company") or "(none)"],
        [],
        [label for _f, label in cols],
    ]
    numeric = {"amount", "base_amount", "net", "vat", "gross", "outstanding_amount", "value", "collected", "unallocated"}
    for r in rows:
        data.append([_num(r.get(f)) if f in numeric else (r.get(f) if r.get(f) is not None else "") for f, _l in cols])
    _send(f"{key}-{frappe.utils.nowdate()}.xlsx", sheet, data, [18] * len(cols))


# ── The same lists, one row per line ─────────────────────────────────────────
#
# The list export has one row per document. Checking a supplier's bills against
# their statement, or a consignment bill against the orders it covers, needs the
# lines: item, quantity, rate, and the customer order each line serves (Hanane,
# 2 Nov 2026, on Christelle Paris). Header fields repeat on every line so the
# sheet filters and pivots on its own.

_LINE_EXPORTS = {
    # key: (doctype, child doctype, date field, party field, extra header fields, extra line fields)
    "bills": ("Purchase Invoice", "Purchase Invoice Item", "posting_date", "supplier",
              [("bill_no", "Supplier invoice"), ("bill_date", "Supplier invoice date"), ("is_return", "Return")],
              [("purchase_order", "Purchase order"), ("purchase_receipt", "Receipt"), ("expense_account", "Account")]),
    "invoices": ("Sales Invoice", "Sales Invoice Item", "posting_date", "customer",
                 [("is_return", "Return")],
                 [("sales_order", "Sales order"), ("delivery_note", "Delivery note"), ("income_account", "Account")]),
    "purchase_orders": ("Purchase Order", "Purchase Order Item", "transaction_date", "supplier", [],
                        [("sales_order", "Customer order"), ("received_qty", "Received qty"), ("billed_amt", "Billed")]),
    "orders": ("Sales Order", "Sales Order Item", "transaction_date", "customer", [],
               [("delivered_qty", "Delivered qty"), ("billed_amt", "Billed")]),
}
_LINE_NUM = {"qty", "rate", "amount", "net_amount", "base_amount", "received_qty", "delivered_qty", "billed_amt",
             "grand_total"}


@frappe.whitelist()
def lines_xlsx(key=None, names=None, **filters):
    """One row per line for the selected documents (`names`, JSON list) or, with
    no selection, for the whole filtered list as on screen."""
    assert_portal_access()
    from accounting_portal.api.permissions import resolve_companies
    spec = _LINE_EXPORTS.get(key)
    if not spec:
        frappe.throw("Line export is not available for this list")
    dt, child, date_f, party_f, head_extra, line_extra = spec
    company = filters.get("company")
    if names:
        names = frappe.parse_json(names) if isinstance(names, str) else names
        names = [n for n in (names or []) if n][:5000]
        sheet = f"{dt} lines"
    else:
        rows, _f, sheet, _c = _collect_rows(key, dict(filters))
        names = [r.get("name") for r in rows if r.get("name")]
        sheet = f"{sheet} — lines"
    if not names:
        frappe.throw("No documents to export")
    allowed = tuple(resolve_companies(company) or ("",))
    hmeta, cmeta = frappe.get_meta(dt), frappe.get_meta(child)
    head = [(date_f, "Date"), (party_f, "Party")] + [h for h in head_extra if hmeta.has_field(h[0])] + \
           [("currency", "Currency"), ("status", "Status"), ("grand_total", "Document total")]
    line = [("idx", "Line"), ("item_code", "Item"), ("item_name", "Item name"), ("qty", "Qty"), ("uom", "UOM"),
            ("rate", "Rate"), ("amount", "Amount"), ("net_amount", "Net amount"), ("base_amount", "Amount (company ccy)"),
            ("item_tax_template", "Tax template"), ("warehouse", "Warehouse")] + \
           [l for l in line_extra if cmeta.has_field(l[0])]
    line = [l for l in line if l[0] == "idx" or cmeta.has_field(l[0])]
    with_order = dt == "Purchase Invoice" and cmeta.has_field("po_detail")
    sel = ", ".join([f"p.`{f}` AS `h_{f}`" for f, _l in head] + [f"i.`{f}` AS `l_{f}`" for f, _l in line]
                    + (["poi.sales_order AS customer_order"] if with_order else []))
    join = " LEFT JOIN `tabPurchase Order Item` poi ON poi.name = i.po_detail" if with_order else ""
    out = []
    for k in range(0, len(names), 500):
        chunk = tuple(names[k:k + 500])
        out += frappe.db.sql(
            f"""SELECT p.name AS doc, {sel} FROM `tab{dt}` p JOIN `tab{child}` i ON i.parent = p.name {join}
                WHERE p.name IN %(n)s AND p.company IN %(c)s
                ORDER BY p.`{date_f}` DESC, p.name, i.idx""", {"n": chunk, "c": allowed}, as_dict=True)
        if len(out) >= _MAX_ROWS:
            break
    cols = [("doc", dt)] + [(f"h_{f}", l) for f, l in head] + [(f"l_{f}", l) for f, l in line] + \
           ([("customer_order", "Customer order")] if with_order else [])
    data = [
        [sheet, company or "", "Documents", len({r.doc for r in out}), "Lines", len(out)],
        [],
        [label for _f, label in cols],
    ]
    for r in out[:_MAX_ROWS]:
        row = []
        for f, _l in cols:
            v = r.get(f)
            bare = f.split("_", 1)[1] if f[:2] in ("h_", "l_") else f
            if bare in _LINE_NUM:
                row.append(flt(v))
            elif bare == "is_return":
                row.append("Yes" if v else "")
            else:
                row.append("" if v is None else (str(v) if not isinstance(v, (int, float)) else v))
        data.append(row)
    _send(f"{key}-lines-{frappe.utils.nowdate()}.xlsx", sheet[:28], data, [18] * len(cols))


@frappe.whitelist()
def statements_xlsx(report=None, company=None, from_date=None, to_date=None):
    """P&L / balance sheet / cash flow as a workbook — section rows in bold-ish
    order with their accounts underneath, numbers as numbers."""
    assert_portal_access()
    from accounting_portal.api.reports import financial_statements
    d = financial_statements(company=company, from_date=from_date, to_date=to_date, compare=0) or {}
    key = {"balance_sheet": "balance_sheet", "cash_flow": "cash_flow"}.get(report, "pnl")
    p = d.get(key) or {}
    ccy = d.get("currency") or ""
    data = [[{"pnl": "Profit & loss", "balance_sheet": "Balance sheet", "cash_flow": "Cash flow"}[key],
             d.get("company") or company, "Currency", ccy],
            ["Period", f"{d.get('from_date') or ''} → {d.get('to_date') or ''}"], [], ["Line", "Account", "Amount"]]

    def sections(secs):
        for sec in secs or []:
            data.append([sec.get("section") or "—", "", flt(sec.get("total"))])
            for a in sec.get("accounts") or []:
                data.append(["", a.get("name") or a.get("account") or "", flt(a.get("amount"))])

    if key == "pnl":
        sections(p.get("revenue")); data.append(["Revenue", "", flt(p.get("revenue_total"))])
        sections([p.get("cogs")] if p.get("cogs") else [])
        data.append(["Gross profit", "", flt(p.get("gross_profit"))])
        sections(p.get("opex")); data.append(["Operating expenses", "", flt(p.get("opex_total"))])
        data.append(["NET RESULT", "", flt(p.get("net"))])
    elif key == "balance_sheet":
        data.append(["ASSETS", "", ""]); sections(p.get("assets"))
        data.append(["Total assets", "", flt(p.get("assets_total"))])
        data.append(["LIABILITIES", "", ""]); sections(p.get("liabilities"))
        data.append(["Total liabilities", "", flt(p.get("liabilities_total"))])
        data.append(["EQUITY", "", ""]); sections(p.get("equity"))
        data.append(["Total equity", "", flt(p.get("equity_total"))])
        data.append(["Out of balance", "", flt(p.get("check"))])
    else:
        for k, label in (("open_cash", "Opening cash"), ("cash_in", "Cash in"), ("cash_out", "Cash out"),
                         ("net_change", "Net movement"), ("close_cash", "Closing cash")):
            if k in p:
                data.append([label, "", flt(p.get(k))])
        data.append(["Method", p.get("method") or "direct", ""])
        data.append(["Reconciles with bank movement", "yes" if p.get("reconciles") else "no", ""])
    _send(f"{key}-{(to_date or frappe.utils.nowdate())}.xlsx", key[:28], data, [42, 46, 18])
