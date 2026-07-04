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

# Name signals for an intermediary / exchange-office clearing account.
_INTER_KW = ("transfer from maslak", "intermediary", "exchange office", "bisfor",
             "vavien", "istanbul exchange", "morocco-t", "morocco petty cash usd")


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
        low = (a.nm or "").lower()
        if not any(k in low for k in _INTER_KW):
            continue
        a["bal"], a["funded"], a["settled"] = flt(a["bal"]), flt(a["funded"]), flt(a["settled"])
        a["n"] = int(a["n"] or 0)
        a["last"] = str(a["last"] or "")[:10]
        # An asset intermediary should never be credit (negative) — that means
        # payments were booked out without funding / clearing the payable first.
        a["flag"] = ("negative" if a["bal"] < -1 else ("cash_type" if a["at"] in ("Bank", "Cash") else "ok"))
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
        """SELECT name, account_name nm, account_number num, account_type at FROM `tabAccount`
           WHERE company=%s AND is_group=0 AND disabled=0 AND root_type='Asset'""", (target,), as_dict=True)
    inter = [{"name": a.name, "nm": a.nm, "num": a.num}
             for a in accts if any(k in (a.nm or "").lower() for k in _INTER_KW)]
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


@frappe.whitelist()
def settle_via_intermediary(company=None, invoice=None, intermediary=None, reference_no=None, posting_date=None):
    """Settle a foreign-currency supplier bill by paying it FROM the intermediary
    clearing account — ERPNext computes the FX gain/loss. Reuses the proven Pay
    Bill gateway (audited, gated for material amounts, reversible)."""
    from accounting_portal.api.purchases import pay_bill
    return pay_bill(company=company, invoice=invoice, paid_from=intermediary,
                    reference_no=reference_no, reference_date=posting_date,
                    dedupe_key="settleinter:" + frappe.generate_hash(f"{invoice}:{intermediary}", 12))
