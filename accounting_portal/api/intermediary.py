"""Payment-through-an-intermediary (agent) flow.

Justyol buys from foreign suppliers (Turkey/China, invoiced in TRY/USD) but pays
a Moroccan intermediary in MAD, who then settles the supplier abroad. The
intermediary is a payment agent → a clearing/receivable, NOT the company's cash.

This module surfaces each intermediary's position (funded → settled → balance)
and the open foreign-currency payables, and lets the team:
  • FUND an intermediary  — a MAD journal (Dr intermediary / Cr bank)
  • SETTLE a supplier bill — pay the FX invoice with the intermediary as the
    "paid from" account, so ERPNext computes the FX gain/loss reliably.
"""
import frappe
from frappe.utils import flt, nowdate

from accounting_portal.api.permissions import assert_portal_access, assert_can_write, resolve_companies
from accounting_portal.api import _actions

# Name signals for an intermediary / exchange-office clearing account.
_INTER_KW = ("transfer from maslak", "intermediary", "exchange office", "bisfor",
             "vavien", "istanbul exchange", "morocco-t", "morocco petty cash usd")

# Clean accounts created by the portal live under this dedicated group (placed
# under "136. Other Receivables" — the money is with an agent, not in our cash).
_GROUP_NAME = "Due From Intermediaries"


def _is_inter(nm, parent):
    low = (nm or "").lower()
    return any(k in low for k in _INTER_KW) or _GROUP_NAME.lower() in (parent or "").lower()


def _target(company):
    companies = resolve_companies(company)
    if not companies:
        return None
    return company if (company and company in companies) else companies[0]


def _ccy(target):
    return frappe.db.get_value("Company", target, "default_currency") or "MAD"


@frappe.whitelist()
def intermediary_review(company=None):
    """Each intermediary clearing account: funded (Dr) → settled (Cr) → balance,
    with a hygiene flag; plus the open foreign-currency payables to settle."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    base = _ccy(target)
    accts = frappe.db.sql(
        """SELECT a.name, a.account_number num, a.account_name nm, a.account_type at,
                  a.parent_account pa,
                  a.root_type rt, a.account_currency ccy, a.disabled,
                  ROUND(COALESCE((SELECT SUM(g.debit-g.credit) FROM `tabGL Entry` g WHERE g.account=a.name AND g.is_cancelled=0),0)) bal,
                  ROUND(COALESCE((SELECT SUM(g.debit)  FROM `tabGL Entry` g WHERE g.account=a.name AND g.is_cancelled=0),0)) funded,
                  ROUND(COALESCE((SELECT SUM(g.credit) FROM `tabGL Entry` g WHERE g.account=a.name AND g.is_cancelled=0),0)) settled,
                  (SELECT COUNT(*) FROM `tabGL Entry` g WHERE g.account=a.name AND g.is_cancelled=0) n,
                  (SELECT MAX(posting_date) FROM `tabGL Entry` g WHERE g.account=a.name AND g.is_cancelled=0) last
           FROM `tabAccount` a WHERE a.company=%s AND a.is_group=0 AND a.root_type='Asset'""",
        (target,), as_dict=True)
    inter = []
    for a in accts:
        if not _is_inter(a.nm, a.pa):
            continue
        clean = _GROUP_NAME.lower() in (a.pa or "").lower()
        a["bal"], a["funded"], a["settled"] = flt(a["bal"]), flt(a["funded"]), flt(a["settled"])
        a["n"] = int(a["n"] or 0)
        a["last"] = str(a["last"] or "")[:10]
        # An asset intermediary should never be credit (negative) — that means
        # payments were booked out without funding / clearing the payable first.
        # Portal-created accounts under the dedicated group are Bank-typed on
        # purpose (Payment Entry demands it) — don't flag those.
        a["flag"] = ("negative" if a["bal"] < -1 else
                     ("ok" if clean else ("cash_type" if a["at"] in ("Bank", "Cash") else "ok")))
        inter.append(a)
    inter.sort(key=lambda x: -abs(x["bal"]))
    fx = frappe.db.sql(
        """SELECT COUNT(*) n, SUM(outstanding_amount) v FROM `tabPurchase Invoice`
           WHERE company=%s AND docstatus=1 AND outstanding_amount > 0 AND currency != %s""",
        (target, base), as_dict=True)[0]
    return {"company": target, "currency": base, "accounts": inter,
            "open_fx_payables": {"n": int(fx.n or 0), "amount": flt(fx.v)}}


@frappe.whitelist()
def intermediary_options(company=None):
    """Intermediary clearing accounts + funding banks + open FX supplier bills."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    base = _ccy(target)
    accts = frappe.db.sql(
        """SELECT name, account_name nm, account_number num, account_type at, parent_account pa
           FROM `tabAccount`
           WHERE company=%s AND is_group=0 AND disabled=0 AND root_type='Asset'""", (target,), as_dict=True)
    inter = [{"name": a.name, "nm": a.nm, "num": a.num}
             for a in accts if _is_inter(a.nm, a.pa)]
    banks = frappe.db.sql(
        """SELECT name, account_name nm FROM `tabAccount`
           WHERE company=%s AND is_group=0 AND disabled=0 AND account_type='Bank' ORDER BY name""",
        (target,), as_dict=True)
    bills = frappe.db.sql(
        """SELECT pi.name, pi.supplier, IFNULL(s.supplier_name, pi.supplier) supplier_name,
                  pi.currency, pi.outstanding_amount, pi.grand_total, pi.posting_date
           FROM `tabPurchase Invoice` pi LEFT JOIN `tabSupplier` s ON s.name=pi.supplier
           WHERE pi.company=%s AND pi.docstatus=1 AND pi.outstanding_amount > 0 AND pi.currency != %s
           ORDER BY pi.posting_date DESC LIMIT 100""", (target, base), as_dict=True)
    for b in bills:
        b["outstanding_amount"] = flt(b["outstanding_amount"])
        b["posting_date"] = str(b["posting_date"])[:10]
    return {"company": target, "currency": base, "intermediaries": inter, "banks": banks, "bills": bills}


@frappe.whitelist()
def fund_intermediary(company=None, intermediary=None, bank=None, amount=None, posting_date=None, notes=None):
    """Move money from a bank to an intermediary (Dr intermediary / Cr bank), MAD.
    Goes through the audited, reversible journal gateway."""
    assert_can_write()
    target = _target(company)
    if not (target and intermediary and bank):
        frappe.throw("company, intermediary and bank are required")
    amt = flt(amount)
    if amt <= 0:
        frappe.throw("Amount must be greater than zero")
    for a in (intermediary, bank):
        if not frappe.db.exists("Account", {"name": a, "company": target, "is_group": 0}):
            frappe.throw(f"Account not found: {a}")
    from accounting_portal.api.accountant import create_journal_entry
    return create_journal_entry(
        company=target, posting_date=posting_date or nowdate(),
        lines=[{"account": intermediary, "debit": amt, "credit": 0},
               {"account": bank, "debit": 0, "credit": amt}],
        remark=notes or f"Fund intermediary {intermediary}",
        dedupe_key="fundinter:" + frappe.generate_hash(f"{target}:{intermediary}:{bank}:{amt}:{posting_date or nowdate()}", 12))


ACCT_ACTION = "Create intermediary account"


@frappe.whitelist()
def create_intermediary_account(company=None, account_name=None, currency=None):
    """One clean, reusable clearing account per intermediary, created under a
    dedicated "Due From Intermediaries" group (136. Other Receivables side of the
    balance sheet). Typed Bank on purpose: ERPNext's Payment Entry only pays from
    Bank/Cash accounts, and Settle rides a Payment Entry so ERPNext books the FX.
    Audited + reversible (revert disables the account; no GL is ever touched)."""
    assert_can_write()
    target = _target(company)
    nm = (account_name or "").strip()
    if not (target and nm):
        frappe.throw("company and account_name are required")
    if len(nm) > 120:
        frappe.throw("Account name too long")
    ccy = (currency or "").strip() or _ccy(target)
    if not frappe.db.exists("Currency", ccy):
        frappe.throw(f"Unknown currency: {ccy}")
    if frappe.db.exists("Account", {"company": target, "account_name": nm}):
        frappe.throw(f"An account named '{nm}' already exists in {target}")
    return _actions.execute(
        ACCT_ACTION, target, f"interacct:{target}:{nm.lower()}",
        payload={"account_name": nm, "currency": ccy},
        amount=0, notes=f"New intermediary account '{nm}' ({ccy})")


def _inter_group(company):
    """Find or create the 'Due From Intermediaries' group for this company."""
    g = frappe.db.get_value("Account", {"company": company, "account_name": _GROUP_NAME, "is_group": 1}, "name")
    if g:
        return g
    parent = (frappe.db.get_value("Account", {"company": company, "is_group": 1, "account_number": "136."}, "name")
              or frappe.db.get_value("Account", {"company": company, "is_group": 1,
                                                 "account_name": ["like", "%Other Receivables%"]}, "name")
              or frappe.db.get_value("Account", {"company": company, "is_group": 1, "root_type": "Asset",
                                                 "parent_account": ["!=", ""]}, "name"))
    if not parent:
        frappe.throw("No Asset group account found to place the intermediaries group under")
    num = "136.100" if not frappe.db.exists("Account", {"company": company, "account_number": "136.100"}) else None
    doc = frappe.get_doc({"doctype": "Account", "company": company, "account_name": _GROUP_NAME,
                          "parent_account": parent, "is_group": 1, "root_type": "Asset",
                          **({"account_number": num} if num else {})})
    doc.insert(ignore_permissions=True)
    return doc.name


def _create_acct_poster(action):
    import json
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    group = _inter_group(action.company)
    gnum = frappe.db.get_value("Account", group, "account_number")
    num = None
    if gnum:
        for i in range(1, 1000):
            cand = f"{gnum}.{i:03d}"
            if not frappe.db.exists("Account", {"company": action.company, "account_number": cand}):
                num = cand
                break
    doc = frappe.get_doc({"doctype": "Account", "company": action.company,
                          "account_name": p["account_name"], "parent_account": group,
                          "is_group": 0, "root_type": "Asset", "account_type": "Bank",
                          "account_currency": p.get("currency"),
                          **({"account_number": num} if num else {})})
    doc.insert(ignore_permissions=True)
    return {"voucher_type": "Account", "voucher_no": doc.name, "result": doc.name}


def _create_acct_reverter(action):
    # A fresh clearing account carries no GL — disabling it fully undoes the action.
    if action.voucher_no and frappe.db.exists("Account", action.voucher_no):
        frappe.db.set_value("Account", action.voucher_no, {"disabled": 1}, update_modified=True)
    return {"voucher_type": "Account", "voucher_no": action.voucher_no, "result": "disabled"}


_actions.register_poster(ACCT_ACTION, _create_acct_poster)
_actions.register_reverter(ACCT_ACTION, _create_acct_reverter)
_actions._NO_GATE.add(ACCT_ACTION)  # master data — no GL, no approval gate


@frappe.whitelist()
def settle_via_intermediary(company=None, invoice=None, intermediary=None, reference_no=None, posting_date=None):
    """Settle a foreign-currency supplier bill by paying it FROM the intermediary
    clearing account — ERPNext computes the FX gain/loss. Reuses the proven Pay
    Bill gateway (audited, gated for material amounts, reversible)."""
    from accounting_portal.api.purchases import pay_bill
    return pay_bill(company=company, invoice=invoice, paid_from=intermediary,
                    reference_no=reference_no, reference_date=posting_date,
                    dedupe_key="settleinter:" + frappe.generate_hash(f"{invoice}:{intermediary}", 12))
