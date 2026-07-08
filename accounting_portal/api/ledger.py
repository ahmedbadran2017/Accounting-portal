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
def trial_balance(company=None, from_date=None, to_date=None):
    """Net trial balance per account for one company (non-zero balances only).

    With a fiscal-year period each account also carries opening (carried forward)
    → period debit/credit → closing, so a year can be cleaned in isolation.

    Flags anomalies the auditor cares about: an asset/expense carrying a credit
    balance, or a liability/income carrying a debit balance, and outsized balances.
    """
    assert_portal_access()
    target = _target(company)
    if not target:
        return {"rows": [], "total_dr": 0, "total_cr": 0}
    period = bool(from_date or to_date)

    def _build():
        p = {"c": target}
        upto = "gl.is_cancelled = 0 AND gl.company = %(c)s"
        if to_date:
            upto += " AND gl.posting_date <= %(td)s"; p["td"] = to_date
        rows = frappe.db.sql(
            f"""SELECT gl.account AS acct, acc.account_number AS code, acc.account_name AS name,
                       acc.root_type, SUM(gl.debit - gl.credit) AS bal
                FROM `tabGL Entry` gl JOIN `tabAccount` acc ON acc.name = gl.account
                WHERE {upto} GROUP BY gl.account
                HAVING ABS(SUM(gl.debit - gl.credit)) > 0.005 ORDER BY acc.lft""",
            p, as_dict=True)
        opening, pdr, pcr = {}, {}, {}
        if period:
            if from_date:
                for r in frappe.db.sql(
                        """SELECT account, SUM(debit-credit) v FROM `tabGL Entry`
                           WHERE is_cancelled=0 AND company=%(c)s AND posting_date < %(fd)s GROUP BY account""",
                        {"c": target, "fd": from_date}, as_dict=True):
                    opening[r.account] = flt(r.v)
            conds, pp = ["is_cancelled=0", "company=%(c)s"], {"c": target}
            if from_date:
                conds.append("posting_date >= %(fd)s"); pp["fd"] = from_date
            if to_date:
                conds.append("posting_date <= %(td)s"); pp["td"] = to_date
            for r in frappe.db.sql(
                    f"""SELECT account, SUM(debit) d, SUM(credit) cr FROM `tabGL Entry`
                        WHERE {' AND '.join(conds)} GROUP BY account""", pp, as_dict=True):
                pdr[r.account] = flt(r.d); pcr[r.account] = flt(r.cr)
        out, total_dr, total_cr = [], 0.0, 0.0
        for r in rows:
            bal = flt(r.bal)
            dr = bal if bal > 0 else 0.0
            cr = -bal if bal < 0 else 0.0
            total_dr += dr
            total_cr += cr
            debit_nature = r.root_type in ("Asset", "Expense")
            anomaly = (debit_nature and bal < 0) or (not debit_nature and bal > 0) or abs(bal) >= 50_000_000
            row = {"code": r.code, "name": r.name, "root_type": r.root_type,
                   "dr": dr, "cr": cr, "anomaly": bool(anomaly)}
            if period:
                row.update({"opening": round(opening.get(r.acct, 0.0), 2),
                            "period_dr": round(pdr.get(r.acct, 0.0), 2),
                            "period_cr": round(pcr.get(r.acct, 0.0), 2),
                            "closing": round(bal, 2), "period": True})
            out.append(row)
        return {"rows": out, "total_dr": total_dr, "total_cr": total_cr, "period": period}

    return _cache.cached(f"ap_tb:{target}:{from_date}:{to_date}", 180, _build)


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


POSTABLE_ACTION = "Make account postable"


@frappe.whitelist()
def make_account_postable(company=None, account=None):
    """Turn an EMPTY group account (is_group=1, no children, no GL) into a
    postable leaf so expenses can actually be booked to it. Common CoA bug: the
    same account is a leaf in one company but a childless group in another
    (e.g. Domain Name Expenses). Gated, audited, reversible (back to group)."""
    assert_super_admin()
    target = _target(company)
    if not (target and account):
        frappe.throw("Account required")
    acc = frappe.db.get_value("Account", account, ["company", "is_group", "account_name"], as_dict=True)
    if not acc or acc.company != target:
        frappe.throw("Account not in this company")
    if not acc.is_group:
        frappe.throw("Account is already postable")
    if frappe.db.count("Account", {"parent_account": account}):
        frappe.throw("Group has children — convert a child, not the parent")
    if frappe.db.count("GL Entry", {"account": account, "is_cancelled": 0}):
        frappe.throw("Group has ledger entries — cannot convert")
    key = f"postable:{target}:{account}"
    return _actions.execute(
        POSTABLE_ACTION, target, key, payload={"account": account}, amount=0,
        notes=f"Make {account} postable (empty group → leaf)")


def _postable_poster(action):
    import json
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    doc = frappe.get_doc("Account", p["account"])
    doc.is_group = 0
    doc.save(ignore_permissions=True)
    return {"voucher_type": "Account", "voucher_no": p["account"], "result": "now postable"}


def _postable_reverter(action):
    import json
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    if p.get("account") and not frappe.db.count("GL Entry", {"account": p["account"], "is_cancelled": 0}):
        doc = frappe.get_doc("Account", p["account"])
        doc.is_group = 1
        doc.save(ignore_permissions=True)
    return {"restored": p.get("account")}


_actions.register_poster(POSTABLE_ACTION, _postable_poster)
_actions.register_reverter(POSTABLE_ACTION, _postable_reverter)
_actions._NO_GATE.add(POSTABLE_ACTION)  # master-data structure fix, no GL


@frappe.whitelist()
def make_postable_bulk(company=None, accounts=None):
    """Convert several empty expense groups to postable leaves in one go."""
    import json
    assert_super_admin()
    accounts = json.loads(accounts) if isinstance(accounts, str) else (accounts or [])
    ok, failed = [], []
    for a in accounts:
        try:
            make_account_postable(company=company, account=a); ok.append(a)
        except Exception as e:
            failed.append({"account": a, "error": str(e)[:120]})
    return {"converted": len(ok), "ok": ok, "failed": failed}


# ── Chart-of-Accounts audit (per company + across all companies) ──────────────

_JUNK_KW = ("delete after", "write off", "who paid unknown", "clean this",
            "only tax purpose", "personal temporary", "test account", "dont use", "don't use")
TRIM_ACTION = "Trim account name"


def _coa_scan(company, detail=True):
    """Run the CoA checks for one company. Returns counts (+ capped detail lists)."""
    accts = frappe.db.sql(
        """SELECT a.name, a.account_number num, a.account_name nm, a.root_type rt, a.account_type at,
                  a.is_group ig, a.disabled dis, a.account_currency ccy,
                  ROUND(COALESCE((SELECT SUM(g.debit-g.credit) FROM `tabGL Entry` g
                                  WHERE g.account=a.name AND g.is_cancelled=0),0)) bal,
                  (SELECT COUNT(*) FROM `tabGL Entry` g WHERE g.account=a.name AND g.is_cancelled=0) n
           FROM `tabAccount` a WHERE a.company=%s ORDER BY a.account_number""", (company,), as_dict=True)
    # children per account (to spot empty groups — a group with no child can't be
    # posted to and has no leaf under it, so that expense simply can't be booked).
    kids = dict(frappe.db.sql(
        """SELECT parent_account, COUNT(*) FROM `tabAccount`
           WHERE company=%s AND parent_account IS NOT NULL AND parent_account != ''
           GROUP BY parent_account""", (company,)))
    dead, sign, junk, spaces, miscash, outliers, grpgl, emptygrp = [], [], [], [], [], [], [], []
    byname = {}
    for a in accts:
        nm, num = (a.nm or ""), (a.num or "")
        rec = {"account": a.name, "num": num, "nm": nm, "root": a.rt, "typ": a.at,
               "ccy": a.ccy, "bal": flt(a.bal), "n": int(a.n or 0), "disabled": int(a.dis or 0)}
        if nm != nm.strip() or num != num.strip():
            spaces.append(rec)
        if a.ig:
            if int(a.n or 0) > 0:
                grpgl.append(rec)
            # empty group with no children and no GL → should be a postable leaf
            elif not int(kids.get(a.name, 0)) and not int(a.dis or 0):
                emptygrp.append(rec)
            continue
        low = nm.lower()
        if rec["n"] == 0 and not rec["disabled"]:
            dead.append(rec)
        debit_nat = a.rt in ("Asset", "Expense")
        if (debit_nat and rec["bal"] < -100) or (not debit_nat and rec["bal"] > 100):
            sign.append({**rec, "expected": "debit" if debit_nat else "credit"})
        for kw in _JUNK_KW:
            if kw in low:
                junk.append(rec); break
        if a.at in ("Bank", "Cash"):
            bucket, suggestion = _cb_classify(nm, a.at)
            if bucket not in ("bank", "petty"):
                miscash.append({**rec, "bucket": bucket, "suggestion": suggestion})
        if abs(rec["bal"]) >= 50_000_000:
            outliers.append(rec)
        key = "".join(ch for ch in low if ch.isalnum())
        if key:
            byname.setdefault(key, []).append({"account": a.name, "num": num, "root": a.rt})
    dups = [{"name": v[0]["num"], "accounts": v} for k, v in byname.items() if len(v) > 1]
    checks = {"dead": dead, "sign": sign, "junk": junk, "spaces": spaces,
              "miscash": miscash, "outliers": outliers, "group_with_gl": grpgl,
              "empty_group": emptygrp, "duplicates": dups}
    counts = {k: len(v) for k, v in checks.items()}
    # weighted health score (100 = clean)
    score = 100
    score -= min(25, counts["sign"] * 2)
    score -= min(20, counts["group_with_gl"] * 10)
    score -= min(15, counts["miscash"])
    score -= min(12, counts["empty_group"])
    score -= min(10, counts["junk"] * 3)
    score -= min(10, counts["duplicates"])
    score -= min(8, counts["spaces"] // 6)
    score -= min(7, counts["dead"] // 100)
    score = max(0, score)
    out = {"company": company, "total": len(accts), "counts": counts, "score": score,
           "currency": frappe.db.get_value("Company", company, "default_currency") or "MAD"}
    if detail:
        out["checks"] = {k: (v[:80] if k != "duplicates" else v[:60]) for k, v in checks.items()}
    return out


@frappe.whitelist()
def coa_audit(company=None):
    """Full Chart-of-Accounts audit for one company: findings per check + score."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    return _coa_scan(target, detail=True)


@frappe.whitelist()
def coa_audit_all():
    """Per-company CoA health across every company the user can see (summary only)."""
    assert_portal_access()
    comps = resolve_companies() or []
    return {"companies": [_coa_scan(c, detail=False) for c in comps]}


@frappe.whitelist()
def trim_account(company=None, account=None):
    """Strip stray leading/trailing spaces from an account's name/number. Super-admin;
    audited; reversible."""
    assert_super_admin()
    target = _target(company)
    if not (target and account):
        frappe.throw("Account required")
    acc = frappe.db.get_value("Account", account, ["company", "account_name", "account_number"], as_dict=True)
    if not acc or acc.company != target:
        frappe.throw("Account not in this company")
    new_nm = (acc.account_name or "").strip()
    new_num = (acc.account_number or "").strip()
    if new_nm == (acc.account_name or "") and new_num == (acc.account_number or ""):
        frappe.throw("Nothing to trim")
    key = f"trim_acct:{target}:{account}"
    return _actions.execute(
        TRIM_ACTION, target, key,
        payload={"account": account, "new_nm": new_nm, "new_num": new_num,
                 "old_nm": acc.account_name or "", "old_num": acc.account_number or ""},
        amount=0, notes=f"Trim {account}")


def _trim_poster(action):
    import json
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    frappe.db.set_value("Account", p["account"],
                        {"account_name": p.get("new_nm"), "account_number": p.get("new_num")}, update_modified=True)
    return {"voucher_type": "Account", "voucher_no": p["account"], "result": "trimmed"}


def _trim_reverter(action):
    import json
    p = action.payload if isinstance(action.payload, dict) else json.loads(action.payload or "{}")
    frappe.db.set_value("Account", p["account"],
                        {"account_name": p.get("old_nm"), "account_number": p.get("old_num")}, update_modified=True)
    return {"restored": p["account"]}


_actions.register_poster(TRIM_ACTION, _trim_poster)
_actions.register_reverter(TRIM_ACTION, _trim_reverter)


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
