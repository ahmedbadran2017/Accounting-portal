"""Supplier cheques at maturity ("Chèques fournisseurs à payer").

Suppliers are paid with cheques dated ~90 days ahead. The bill is settled the day
the cheque is handed over, but the money leaves the bank only on the cheque's
date. Booking the payment on the cheque date left the supplier looking unpaid for
three months; booking it on the hand-over date showed money gone from BMCE that
was still there. Both facts are true, so they are two entries:

  1. hand-over — Payment Entry (Pay) from the "Chèques fournisseurs à payer"
                 account: the "Chèque à échéance" payment method, cheque number
                 in reference_no, the cheque's maturity in reference_date. The
                 bill closes; the cheque sits in that account as a liability.
  2. debit     — Internal Transfer bank → that account on the day the bank pays
                 the cheque. Posted from Purchases › Cheques ("Mark cleared"),
                 which also stamps the cheque's clearance date.

The account's balance is therefore always "cheques given, not yet debited" — the
figure the next 90 days of cash depend on.
"""
import json

import frappe
from frappe.utils import flt, nowdate

from accounting_portal.api import _actions
from accounting_portal.api._actions import digest as _digest

PDC_ACCOUNT_NAME = "Chèques fournisseurs à payer"
PDC_MODE = "Chèque à échéance"
BANK_MODE = "BMCE -  0000192100011303 - MAD"
ENCASH_ACTION = "Encash supplier cheque"


def pdc_account(company):
    return frappe.db.get_value("Account", {"company": company, "account_name": PDC_ACCOUNT_NAME,
                                           "is_group": 0, "disabled": 0}, "name")


def default_bank(company):
    return frappe.db.get_value("Mode of Payment Account", {"parent": BANK_MODE, "company": company},
                               "default_account")


def _encash_poster(action):
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    src = frappe.db.get_value("Payment Entry", p["payment"],
                              ["company", "reference_no", "paid_amount", "party_name", "party"], as_dict=True)
    pe = frappe.new_doc("Payment Entry")
    pe.company = src.company
    pe.payment_type = "Internal Transfer"
    pe.posting_date = p["posting_date"]
    pe.paid_from = p["bank"]
    pe.paid_to = p["account"]
    pe.paid_amount = flt(src.paid_amount)
    pe.received_amount = flt(src.paid_amount)
    pe.source_exchange_rate = 1
    pe.target_exchange_rate = 1
    pe.reference_no = src.reference_no or p["payment"]
    pe.reference_date = p["posting_date"]
    pe.remarks = f"Encaissement chèque {src.reference_no or ''} — {src.party_name or src.party} — {p['payment']}"
    pe.flags.ignore_permissions = True
    pe.insert()
    pe.submit()
    # The cheque register reads clearance_date: the cheque is cleared the day the
    # bank paid it, which is the day of this transfer.
    frappe.get_doc("Payment Entry", p["payment"]).db_set("clearance_date", p["posting_date"], update_modified=False)
    return {"voucher_type": "Payment Entry", "voucher_no": pe.name,
            "result": {"payment": p["payment"], "encashment": pe.name, "amount": flt(pe.paid_amount)}}


def _encash_reverter(action):
    out = _actions._cancel_voucher_reverter(action)
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    if str(frappe.db.get_value("Payment Entry", p["payment"], "clearance_date") or "") == str(p["posting_date"]):
        frappe.get_doc("Payment Entry", p["payment"]).db_set("clearance_date", None, update_modified=False)
    return out


_actions.register_poster(ENCASH_ACTION, _encash_poster)
_actions.register_reverter(ENCASH_ACTION, _encash_reverter)


def encash(target, payment, posting_date=None, bank=None):
    """Post the bank leg of one supplier cheque. Called by mark_cheques_cleared
    for cheques paid through the cheque account."""
    acc = pdc_account(target)
    src = frappe.db.get_value("Payment Entry", payment,
                              ["company", "docstatus", "payment_type", "paid_from", "paid_amount",
                               "reference_date", "reference_no", "clearance_date"], as_dict=True)
    if not acc or not src or src.company != target or src.docstatus != 1 or src.payment_type != "Pay" \
            or src.paid_from != acc:
        frappe.throw(f"{payment} is not a cheque at maturity of this company")
    if src.clearance_date:
        frappe.throw(f"{payment} is already cleared")
    bank = bank or default_bank(target)
    if not bank or frappe.db.get_value("Account", bank, "account_type") != "Bank" or bank == acc:
        frappe.throw("No bank account to debit the cheque from")
    date = posting_date or (str(src.reference_date) if src.reference_date else nowdate())
    return _actions.execute(
        ENCASH_ACTION, target, _digest(f"pdc:{payment}"),
        payload={"payment": payment, "bank": bank, "account": acc, "posting_date": date},
        amount=flt(src.paid_amount), reference_doctype="Payment Entry", reference_name=payment,
        notes=f"Cheque {src.reference_no or ''} debited from {bank} on {date}")
