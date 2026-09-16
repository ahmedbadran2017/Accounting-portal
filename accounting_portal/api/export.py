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
def gl_xlsx(company=None, account=None, party=None, voucher_no=None, from_date=None, to_date=None, include_cancelled=0):
    """General ledger, the WHOLE filtered set (not the page on screen), up to
    50,000 rows, oldest first, with the running balance when one account is
    filtered. Pulls pages from ledger.general_ledger so filters and totals stay
    identical to the screen."""
    assert_portal_access()
    from accounting_portal.api.ledger import general_ledger
    rows, start, page = [], 0, 500
    first = None
    while True:
        r = general_ledger(company=company, account=account or None, party=party or None, voucher_no=voucher_no or None,
                           from_date=from_date or None, to_date=to_date or None, start=start, page_size=page,
                           include_cancelled=include_cancelled)
        if first is None:
            first = r
        got = r.get("rows") or []
        rows.extend(got)
        start += page
        if len(got) < page or start >= min(int(r.get("total") or 0), _MAX_ROWS):
            break
    rows.reverse()   # newest-first on screen → oldest-first in the workbook
    single = bool(account)
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
