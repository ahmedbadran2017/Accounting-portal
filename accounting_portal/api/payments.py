"""Payment Entry — record COD receipts and supplier payments from the portal.

The collection team's daily tool: a customer paid (via carrier/cash/bank), record
the receipt so it clears the books. Like every write it goes through the gateway
(capability → idempotency → audit → propose/approve for material amounts). The
poster builds a real, balanced Payment Entry and submits it.
"""
import json

import frappe
from frappe.utils import flt, nowdate

from accounting_portal.api import _actions
from accounting_portal.api.permissions import assert_can_write, assert_portal_access, resolve_companies

PE_ACTION = "Record Payment"


def _target(company):
    companies = resolve_companies(company)
    if not companies:
        return None
    return company if (company and company in companies) else companies[0]


@frappe.whitelist()
def deposit_accounts(company=None):
    """Bank/Cash accounts — the deposit (paid-to) picker for receipts."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return []
    return frappe.db.sql(
        """SELECT name, account_name, account_type, account_currency AS currency
           FROM `tabAccount` WHERE company=%s AND is_group=0 AND disabled=0
             AND account_type IN ('Bank','Cash') AND name NOT LIKE '%%CLOSED%%'
           ORDER BY account_type DESC, name""", (target,), as_dict=True)


@frappe.whitelist()
def party_options(company=None, party_type="Customer", search=None):
    """Search parties (Customer/Supplier) for the payment party picker."""
    assert_portal_access()
    like = f"%{(search or '').strip()}%"
    return frappe.db.sql(
        f"""SELECT name, customer_name AS label FROM `tabCustomer`
            WHERE (name LIKE %s OR customer_name LIKE %s) ORDER BY customer_name LIMIT 20"""
        if party_type == "Customer" else
        f"""SELECT name, supplier_name AS label FROM `tabSupplier`
            WHERE (name LIKE %s OR supplier_name LIKE %s) ORDER BY supplier_name LIMIT 20""",
        (like, like), as_dict=True)


def _pe_poster(action):
    """Build + submit a Payment Entry from the action payload."""
    from erpnext.accounts.party import get_party_account
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    is_receive = (p.get("payment_type") or "Receive") == "Receive"
    party_type = "Customer" if is_receive else "Supplier"
    amt = flt(p.get("amount"))
    party_acct = get_party_account(party_type, p["party"], action.company)
    bank = p["account"]
    posting_date = p.get("posting_date") or nowdate()
    # ERPNext requires a reference no/date when the bank/cash leg is a Bank
    # account. Default it so a COD receipt never fails for a missing reference.
    ref_no = p.get("reference_no") or f"COD-{(p.get('party') or '')[:24]}-{posting_date}"

    pe = frappe.get_doc({
        "doctype": "Payment Entry",
        "payment_type": "Receive" if is_receive else "Pay",
        "company": action.company,
        "posting_date": posting_date,
        "mode_of_payment": p.get("mode") or None,
        "party_type": party_type,
        "party": p["party"],
        "paid_amount": amt,
        "received_amount": amt,
        "source_exchange_rate": 1,
        "target_exchange_rate": 1,
        "reference_no": ref_no,
        "reference_date": posting_date,
        "paid_from": party_acct if is_receive else bank,
        "paid_to": bank if is_receive else party_acct,
    })
    for ref in (p.get("references") or []):
        pe.append("references", {
            "reference_doctype": "Sales Invoice" if is_receive else "Purchase Invoice",
            "reference_name": ref["name"], "allocated_amount": flt(ref.get("amount")),
        })
    pe.insert(ignore_permissions=True)
    pe.submit()
    return {"voucher_type": "Payment Entry", "voucher_no": pe.name, "result": "submitted"}


_actions.register_poster(PE_ACTION, _pe_poster)


@frappe.whitelist()
def create_payment_entry(company=None, party=None, amount=None, account=None,
                         mode=None, reference_no=None, posting_date=None,
                         payment_type="Receive", references=None, dedupe_key=None):
    """Record a Payment Entry through the write gateway.

    Receive (default): customer paid into `account` (a bank/cash account).
    Material amounts (≥ threshold) are Proposed and need an approver.
    """
    assert_can_write()
    target = _target(company)
    if not target:
        frappe.throw("No company in scope")
    if not party:
        frappe.throw("Select a party")
    amt = flt(amount)
    if amt <= 0:
        frappe.throw("Amount must be positive")
    if not account:
        frappe.throw("Select a deposit account")
    if isinstance(references, str):
        references = json.loads(references)

    posting_date = posting_date or nowdate()
    key = dedupe_key or f"pe:{target}:{party}:{posting_date}:{round(amt, 2)}:{reference_no or ''}"
    payload = {
        "payment_type": payment_type, "party": party, "amount": amt, "account": account,
        "mode": mode, "reference_no": reference_no, "posting_date": posting_date,
        "references": references or [],
    }
    return _actions.execute(PE_ACTION, target, key, payload=payload, amount=amt,
                            notes=f"{payment_type} {amt:,.0f} from {party}")
