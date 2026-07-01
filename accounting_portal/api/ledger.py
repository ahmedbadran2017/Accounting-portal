"""Accountant endpoints — General Ledger, Trial Balance, Chart of Accounts.

All live ERPNext, entity-scoped, filtering is_cancelled = 0. Balances use the
net sum(debit - credit) convention; the trial balance presents each account's
net on the debit or credit side.
"""
import frappe
from frappe.utils import flt

from accounting_portal.api import _cache
from accounting_portal.api.permissions import assert_portal_access, resolve_companies


def _target(company):
    companies = resolve_companies(company)
    if not companies:
        return None
    return company if (company and company in companies) else companies[0]


@frappe.whitelist()
def general_ledger(company=None, account=None, party=None, voucher_no=None,
                   from_date=None, to_date=None, limit=200):
    """GL entries for one company, filterable by account / party / voucher / date
    range — the portal's replacement for the ERPNext General Ledger report. When a
    single account is filtered, an opening balance and a running balance are
    returned so it reads like a true account statement."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {"rows": [], "opening": 0.0}
    limit = min(int(limit or 200), 1000)
    ck = f"ap_gl:{target}:{account or ''}:{party or ''}:{voucher_no or ''}:{from_date or ''}:{to_date or ''}:{limit}"
    cached_hit = frappe.cache().get_value(ck)
    if cached_hit is not None:
        return cached_hit
    conds = ["gl.company = %(company)s", "gl.is_cancelled = 0"]
    params = {"company": target, "limit": limit}
    if account:
        conds.append("gl.account = %(account)s"); params["account"] = account
    if party:
        conds.append("gl.party = %(party)s"); params["party"] = party
    if voucher_no:
        conds.append("gl.voucher_no LIKE %(vno)s"); params["vno"] = f"%{voucher_no}%"
    if from_date:
        conds.append("gl.posting_date >= %(fd)s"); params["fd"] = from_date
    if to_date:
        conds.append("gl.posting_date <= %(td)s"); params["td"] = to_date

    # Opening balance (debit−credit before from_date) for a single-account view.
    opening = 0.0
    if account and from_date:
        opening = flt(frappe.db.sql(
            """SELECT COALESCE(SUM(debit-credit),0) FROM `tabGL Entry`
               WHERE company=%s AND account=%s AND is_cancelled=0 AND posting_date < %s""",
            (target, account, from_date))[0][0])

    rows = frappe.db.sql(
        f"""
        SELECT gl.posting_date AS date, gl.voucher_type, gl.voucher_no AS ref,
               gl.account, gl.party, gl.debit AS dr, gl.credit AS cr, gl.remarks
        FROM `tabGL Entry` gl
        WHERE {' AND '.join(conds)}
        ORDER BY gl.posting_date DESC, gl.creation DESC
        LIMIT %(limit)s
        """,
        params, as_dict=True,
    )
    # Running balance only makes sense for a single account; compute oldest→newest.
    if account:
        run = opening + sum(flt(r["dr"]) - flt(r["cr"]) for r in rows)
        for r in rows:
            r["balance"] = round(run, 2)
            run -= (flt(r["dr"]) - flt(r["cr"]))
    result = {"rows": rows, "opening": round(opening, 2),
              "total_dr": round(sum(flt(r["dr"]) for r in rows), 2),
              "total_cr": round(sum(flt(r["cr"]) for r in rows), 2)}
    try:
        frappe.cache().set_value(ck, result, expires_in_sec=120)
    except Exception:
        pass
    return result


@frappe.whitelist()
def trial_balance(company=None):
    """Net trial balance per account for one company (non-zero balances only).

    Flags anomalies the auditor cares about: an asset/expense carrying a credit
    balance, or a liability/income carrying a debit balance (a sign the account
    is mis-stated), and any single balance above an outsized threshold.
    """
    assert_portal_access()
    target = _target(company)
    if not target:
        return {"rows": [], "total_dr": 0, "total_cr": 0}

    def _build():
        rows = frappe.db.sql(
            """
            SELECT acc.account_number AS code, acc.account_name AS name,
                   acc.root_type, acc.account_type,
                   SUM(gl.debit - gl.credit) AS bal
            FROM `tabGL Entry` gl
            JOIN `tabAccount` acc ON acc.name = gl.account
            WHERE gl.is_cancelled = 0 AND gl.company = %s
            GROUP BY gl.account
            HAVING ABS(SUM(gl.debit - gl.credit)) > 0.005
            ORDER BY acc.lft
            """,
            (target,), as_dict=True,
        )
        out, total_dr, total_cr = [], 0.0, 0.0
        for r in rows:
            bal = flt(r.bal)
            dr = bal if bal > 0 else 0.0
            cr = -bal if bal < 0 else 0.0
            total_dr += dr
            total_cr += cr
            debit_nature = r.root_type in ("Asset", "Expense")
            anomaly = (debit_nature and bal < 0) or (not debit_nature and bal > 0) or abs(bal) >= 50_000_000
            out.append({"code": r.code, "name": r.name, "root_type": r.root_type,
                        "dr": dr, "cr": cr, "anomaly": bool(anomaly)})
        return {"rows": out, "total_dr": total_dr, "total_cr": total_cr}

    return _cache.cached(f"ap_tb:{target}", 180, _build)


@frappe.whitelist()
def chart_of_accounts(company=None):
    """Accounts grouped by root_type with their net balances (non-zero)."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return []

    def _build():
        rows = frappe.db.sql(
            """
            SELECT acc.name AS account, acc.account_number AS code, acc.account_name AS name,
                   acc.root_type, acc.account_type,
                   SUM(gl.debit - gl.credit) AS bal
            FROM `tabGL Entry` gl
            JOIN `tabAccount` acc ON acc.name = gl.account
            WHERE gl.is_cancelled = 0 AND gl.company = %s
            GROUP BY gl.account
            HAVING ABS(SUM(gl.debit - gl.credit)) > 0.005
            ORDER BY acc.root_type, acc.lft
            """,
            (target,), as_dict=True,
        )
        for r in rows:
            r["bal"] = flt(r.bal)
            debit_nature = r.root_type in ("Asset", "Expense")
            wrong_sign = (debit_nature and r["bal"] < 0) or (not debit_nature and r["bal"] > 0)
            oversized = abs(r["bal"]) >= 50_000_000
            # Keep the historical flag (debit-nature credit balances + oversized) but
            # also surface credit-nature debit balances — both are real sign anomalies.
            r["anomaly"] = bool(wrong_sign or oversized)
            if oversized:
                r["anomaly_reason"] = "oversized"
            elif wrong_sign:
                r["anomaly_reason"] = "credit_balance" if debit_nature else "debit_balance"
            else:
                r["anomaly_reason"] = None
        return rows

    return _cache.cached(f"ap_coa:{target}", 180, _build)


@frappe.whitelist()
def pending_journals(company=None, limit=50):
    """Draft (docstatus = 0) Journal Entries for one company — the maker-checker
    queue. Submitted entries are already posted; cancelled are excluded."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return []
    limit = min(int(limit or 50), 200)
    return frappe.db.sql(
        """
        SELECT je.name AS ref, je.total_debit AS amount, je.posting_date AS date,
               je.title, je.user_remark AS remark, je.voucher_type
        FROM `tabJournal Entry` je
        WHERE je.company = %s AND je.docstatus = 0
        ORDER BY je.modified DESC
        LIMIT %s
        """,
        (target, limit), as_dict=True,
    )


# ── Chart-of-accounts cleanup ─────────────────────────────────────────────────
from accounting_portal.api import _actions  # noqa: E402
from accounting_portal.api.permissions import assert_super_admin  # noqa: E402

DISABLE_ACCT_ACTION = "Toggle account disabled"


@frappe.whitelist()
def account_cleanup(company=None):
    """Surface CoA clutter: leaf accounts with no GL activity (candidates to
    disable) and same-name account pairs (to review — often a legit AR/AP pair,
    not a true duplicate). Read-only."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    active = {r[0] for r in frappe.db.sql(
        "SELECT DISTINCT account FROM `tabGL Entry` WHERE company=%s AND is_cancelled=0", (target,))}
    leaves = frappe.db.sql(
        """SELECT name, account_number num, account_name nm, root_type rt, disabled
           FROM `tabAccount` WHERE company=%s AND is_group=0 ORDER BY account_number""",
        (target,), as_dict=True)
    dead, by_name = [], {}
    for a in leaves:
        if a.name not in active:
            dead.append({"account": a.name, "num": a.num, "name": a.nm, "root": a.rt,
                         "disabled": int(a.disabled or 0)})
        key = "".join(ch for ch in (a.nm or "").lower() if ch.isalnum())
        by_name.setdefault(key, []).append({"num": a.num, "name": a.nm, "root": a.rt})
    pairs = [{"name": v[0]["name"], "accounts": v} for k, v in by_name.items() if len(v) > 1]
    pairs.sort(key=lambda x: x["name"])
    return {
        "company": target, "leaves": len(leaves),
        "dead": dead, "dead_count": len(dead),
        "dead_active": sum(1 for d in dead if not d["disabled"]),
        "name_pairs": pairs[:60], "name_pair_count": len(pairs),
    }


@frappe.whitelist()
def set_account_disabled(company=None, account=None, disabled=1, dry_run=1):
    """Disable/enable an account. Super-admin only; audited; reversible (undo flips
    it back). Guarded so a disable never hides an account that still has activity."""
    assert_super_admin()
    target = _target(company)
    if not (target and account):
        frappe.throw("Account required")
    acc = frappe.db.get_value("Account", account, ["company", "is_group", "disabled"], as_dict=True)
    if not acc or acc.company != target:
        frappe.throw("Account not in this company")
    if acc.is_group:
        frappe.throw("Can't disable a group account")
    want = int(disabled or 0)
    if want and frappe.db.exists("GL Entry", {"account": account, "company": target, "is_cancelled": 0}):
        frappe.throw("Account has ledger activity — not a dead account")
    if int(dry_run or 0):
        return {"dry_run": True, "account": account, "from": int(acc.disabled or 0), "to": want}
    key = f"disable_acct:{target}:{account}:{want}"
    res = _actions.execute(
        DISABLE_ACCT_ACTION, target, key,
        payload={"account": account, "to": want, "old": int(acc.disabled or 0)},
        amount=0, notes=f"{'Disable' if want else 'Enable'} account {account}")
    return {"dry_run": False, "account": account, "to": want, "result": res}


def _disable_acct_poster(action):
    import json
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    if p.get("account"):
        frappe.db.set_value("Account", p["account"], {"disabled": int(p.get("to") or 0)}, update_modified=True)
    return {"voucher_type": "Account", "voucher_no": p.get("account"), "result": "toggled"}


def _disable_acct_reverter(action):
    import json
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    if p.get("account"):
        frappe.db.set_value("Account", p["account"], {"disabled": int(p.get("old") or 0)}, update_modified=True)
    return {"restored": p.get("account")}


_actions.register_poster(DISABLE_ACCT_ACTION, _disable_acct_poster)
_actions.register_reverter(DISABLE_ACCT_ACTION, _disable_acct_reverter)


# ── Cash & Bank hygiene: the CoA is polluted with credit cards, carrier clearing,
# personal petty cash and junk all typed as Bank/Cash — which distorts the cash
# picture. This classifies every Bank/Cash account and drives the cleanup. ───────

RECLASS_ACTION = "Reclassify account"


def _cb_classify(name, typ):
    """Heuristic bucket + suggestion for a Bank/Cash account by its name."""
    s = (name or "").lower()
    if "credite card" in s or "credit card" in s or "kredi" in s:
        return "credit_card", "Credit card → move to Liability (not cash)"
    if "transaction" in s or any(k in s for k in ("cathadis", "cathedis", "aramex", "cash plus",
                                                  "trendyol", "payzone", "deposite", "3rd part")):
        return "clearing", "Carrier / clearing account → not cash"
    if any(k in s for k in ("delete after", "write off", "who paid unknown", "clean this",
                            "only tax", "personal temporary")):
        return "junk", "Junk → close (disable)"
    if any(k in s for k in ("exchange office", "intermediary", "transfer from", "istanbul exchange", "bisfor")):
        return "interco", "Intercompany / FX clearing → not cash"
    if any(k in s for k in ("advance", "injection", "promisses", "non official net wage")):
        return "advance", "Advance / other → not cash"
    if "petty cash" in s or "safe " in s or " safe" in s or "wise" in s:
        return "petty", "Petty / personal cash"
    return ("bank", "Bank account") if typ == "Bank" else ("petty", "Cash account")


@frappe.whitelist()
def cash_bank_review(company=None):
    """Every Bank/Cash-typed account with balance, activity and a suggested
    classification — so the mislabelled ones (credit cards, carrier clearing,
    intercompany, junk, dead) can be cleaned up."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    rows = frappe.db.sql(
        """SELECT a.name, a.account_number num, a.account_name nm, a.account_type typ,
                  a.account_currency ccy, a.disabled,
                  ROUND(COALESCE((SELECT SUM(g.debit-g.credit) FROM `tabGL Entry` g
                                  WHERE g.account=a.name AND g.is_cancelled=0),0)) bal,
                  (SELECT COUNT(*) FROM `tabGL Entry` g WHERE g.account=a.name AND g.is_cancelled=0) n,
                  (SELECT MAX(g.posting_date) FROM `tabGL Entry` g WHERE g.account=a.name AND g.is_cancelled=0) last
           FROM `tabAccount` a
           WHERE a.company=%s AND a.is_group=0 AND a.account_type IN ('Bank','Cash')
           ORDER BY a.account_type, a.account_number""", (target,), as_dict=True)
    out = []
    for r in rows:
        bucket, suggestion = _cb_classify(r.nm, r.typ)
        r["bal"] = flt(r["bal"]); r["n"] = int(r["n"] or 0)
        r["last"] = str(r["last"] or "")[:10]
        r["disabled"] = int(r["disabled"] or 0)
        r["bucket"] = bucket
        r["suggestion"] = suggestion
        r["dead"] = (r["bal"] == 0 and r["n"] == 0)
        r["neg_cash"] = (r["typ"] == "Cash" and r["bal"] < 0)
        r["misclassified"] = bucket not in ("bank", "petty")
        out.append(r)
    summary = {
        "total": len(out),
        "dead": sum(1 for x in out if x["dead"] and not x["disabled"]),
        "misclassified": sum(1 for x in out if x["misclassified"] and not x["dead"]),
        "negative_cash": sum(1 for x in out if x["neg_cash"]),
        "real_bank": sum(1 for x in out if x["bucket"] == "bank"),
    }
    return {"company": target, "rows": out, "summary": summary}


@frappe.whitelist()
def reclassify_account(company=None, account=None, account_type=None):
    """Change an account's type (e.g. take a credit card / clearing account out of
    the Bank/Cash cash picture). Super-admin only; audited; reversible."""
    assert_super_admin()
    target = _target(company)
    if not (target and account):
        frappe.throw("Account required")
    acc = frappe.db.get_value("Account", account, ["company", "is_group", "account_type"], as_dict=True)
    if not acc or acc.company != target:
        frappe.throw("Account not in this company")
    if acc.is_group:
        frappe.throw("Can't reclassify a group account")
    new = (account_type or "").strip()
    key = f"reclass_acct:{target}:{account}:{new}"
    return _actions.execute(
        RECLASS_ACTION, target, key,
        payload={"account": account, "to": new, "old": acc.account_type or ""},
        amount=0, notes=f"Reclassify {account} → {new or 'none'}")


def _reclass_poster(action):
    import json
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    frappe.db.set_value("Account", p["account"], {"account_type": (p.get("to") or None)}, update_modified=True)
    return {"voucher_type": "Account", "voucher_no": p["account"], "result": p.get("to") or "cleared"}


def _reclass_reverter(action):
    import json
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    frappe.db.set_value("Account", p["account"], {"account_type": (p.get("old") or None)}, update_modified=True)
    return {"restored": p["account"]}


_actions.register_poster(RECLASS_ACTION, _reclass_poster)
_actions.register_reverter(RECLASS_ACTION, _reclass_reverter)


@frappe.whitelist()
def disable_dead_accounts(company=None):
    """One-click cleanup: disable every Bank/Cash account with zero ledger activity
    (each an audited, individually-reversible action)."""
    assert_super_admin()
    target = _target(company)
    if not target:
        frappe.throw("company required")
    accts = frappe.db.sql(
        """SELECT a.name FROM `tabAccount` a
           WHERE a.company=%s AND a.is_group=0 AND a.account_type IN ('Bank','Cash') AND a.disabled=0
             AND NOT EXISTS(SELECT 1 FROM `tabGL Entry` g WHERE g.account=a.name AND g.is_cancelled=0)""",
        (target,), pluck=True)
    done = []
    for acc in accts:
        try:
            set_account_disabled(target, acc, 1, 0)
            done.append(acc)
        except Exception:
            frappe.clear_last_message()
    return {"disabled": len(done), "accounts": done}
