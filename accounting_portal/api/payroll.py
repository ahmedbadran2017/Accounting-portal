"""Payroll — a full payroll section over ERPNext HR (Salary Slips, Payroll
Entries, Salary Structures) with the accounting lens Justyol lacked: one
consolidated cost-to-company, salary payable outstanding, completeness alerts,
the component→GL-account map, and a month-end **close** operation (verify → sign
off / lock, with undo). Entity-scoped (Morocco + Maslak), cached.

Money is returned at full precision (2 decimals) — this is an accounting system,
so figures are exact, never rounded to thousands.
"""
import json

import frappe
from frappe.utils import flt, add_months, nowdate, getdate, get_last_day

from accounting_portal.api.permissions import assert_portal_access, resolve_companies


def _m(v):
    """Money at accounting precision (2 decimals), never truncated to thousands."""
    return flt(v, 2)


def _target(company):
    companies = resolve_companies(company)
    if not companies:
        return None
    return company if (company and company in companies) else companies[0]


def _ccy(target):
    return frappe.db.get_value("Company", target, "default_currency") or "MAD"


def _period(from_date, to_date):
    if from_date and to_date:
        return from_date, to_date
    return add_months(nowdate(), -12), nowdate()


def _employer_contrib(target, fd, td):
    """Employer-side costs (social security, unemployment employer share) booked to
    the GL directly, not inside the slip."""
    return _m(frappe.db.sql(
        """SELECT SUM(g.debit-g.credit) FROM `tabGL Entry` g JOIN `tabAccount` a ON a.name=g.account
           WHERE g.company=%s AND g.is_cancelled=0 AND g.posting_date BETWEEN %s AND %s
             AND (a.account_name LIKE '%%Social Security%%' OR a.account_name LIKE '%%Unemployment%%'
                  OR a.account_name LIKE '%%Employer%%')""", (target, fd, td))[0][0])


def _salary_payable(target):
    """Outstanding owed to employees (credit balance on payable accounts)."""
    v = frappe.db.sql(
        """SELECT SUM(g.credit-g.debit) FROM `tabGL Entry` g JOIN `tabAccount` a ON a.name=g.account
           WHERE g.company=%s AND g.is_cancelled=0
             AND (a.account_name LIKE '%%Payroll Payable%%' OR a.account_name LIKE '%%Salary Payable%%'
                  OR a.account_name LIKE '%%Wages Payable%%')""", (target,))[0][0]
    return _m(v)


@frappe.whitelist()
def payroll_cockpit(company=None, from_date=None, to_date=None):
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    fd, td = _period(from_date, to_date)
    currency = _ccy(target)
    ck = f"ap_payroll_cockpit:{target}:{fd}:{td}"
    cached = frappe.cache().get_value(ck)
    if cached is not None:
        return cached

    active = frappe.db.count("Employee", {"company": target, "status": "Active"})
    tot = frappe.db.sql(
        """SELECT SUM(gross_pay) gross, SUM(total_deduction) ded, SUM(net_pay) net,
                  COUNT(*) slips, COUNT(DISTINCT employee) emps
           FROM `tabSalary Slip` WHERE company=%s AND docstatus=1 AND start_date BETWEEN %s AND %s""",
        (target, fd, td), as_dict=True)[0]
    employer = _employer_contrib(target, fd, td)
    monthly = [
        {"m": r.m, "gross": _m(r.gross), "net": _m(r.net), "ded": _m(r.ded), "slips": r.slips}
        for r in frappe.db.sql(
            """SELECT DATE_FORMAT(start_date,'%%Y-%%m') m, SUM(gross_pay) gross,
                      SUM(net_pay) net, SUM(total_deduction) ded, COUNT(*) slips
               FROM `tabSalary Slip` WHERE company=%s AND docstatus=1 AND start_date BETWEEN %s AND %s
               GROUP BY m ORDER BY m DESC LIMIT 12""", (target, fd, td), as_dict=True)][::-1]
    by_dept = frappe.db.sql(
        """SELECT IFNULL(NULLIF(e.department,''),'—') dept, COUNT(DISTINCT e.name) heads,
                  SUM(ss.net_pay) net
           FROM `tabEmployee` e
           LEFT JOIN `tabSalary Slip` ss ON ss.employee=e.name AND ss.docstatus=1 AND ss.start_date BETWEEN %s AND %s
           WHERE e.company=%s AND e.status='Active' GROUP BY dept ORDER BY net DESC LIMIT 12""",
        (fd, td, target), as_dict=True)
    for d in by_dept:
        d["net"] = _m(d["net"])

    # completeness: latest run month, active employees without a slip that month
    last_m = frappe.db.sql(
        "SELECT DATE_FORMAT(MAX(start_date),'%%Y-%%m') FROM `tabSalary Slip` WHERE company=%s AND docstatus=1",
        (target,))[0][0]
    missing = 0
    if last_m:
        missing = frappe.db.sql(
            """SELECT COUNT(*) FROM `tabEmployee` e WHERE e.company=%s AND e.status='Active'
               AND NOT EXISTS(SELECT 1 FROM `tabSalary Slip` s WHERE s.employee=e.name AND s.docstatus=1
                              AND DATE_FORMAT(s.start_date,'%%Y-%%m')=%s)""", (target, last_m))[0][0]
    no_structure = frappe.db.sql(
        """SELECT COUNT(*) FROM `tabEmployee` e WHERE e.company=%s AND e.status='Active'
           AND NOT EXISTS(SELECT 1 FROM `tabSalary Structure Assignment` a
                          WHERE a.employee=e.name AND a.docstatus=1)""", (target,))[0][0]

    out = {
        "company": target, "currency": currency, "from_date": str(fd), "to_date": str(td),
        "headcount": active,
        "gross": _m(tot.gross), "net": _m(tot.net), "deductions": _m(tot.ded),
        "slips": tot.slips or 0, "paid_employees": tot.emps or 0,
        "employer_contrib": employer,
        "cost_to_company": _m(_m(tot.gross) + employer),
        # only a credit balance is genuinely "owed to employees"; a debit balance is
        # an advance/overpayment, not an outstanding payable.
        "salary_payable": _m(max(0.0, _salary_payable(target))),
        "monthly": monthly, "by_department": by_dept,
        "last_month": last_m, "missing_slips": int(missing or 0), "no_structure": int(no_structure or 0),
    }
    frappe.cache().set_value(ck, out, expires_in_sec=600)
    return out


def _departments(target):
    """Distinct departments that have at least one employee in this company."""
    return [r[0] for r in frappe.db.sql(
        """SELECT DISTINCT NULLIF(department,'') d FROM `tabEmployee`
           WHERE company=%s AND department IS NOT NULL AND department!='' ORDER BY d""", (target,)) if r[0]]


@frappe.whitelist()
def payroll_employees(company=None, search=None, status="Active", department=None):
    """Roster: employees with base salary, status, last slip, and YTD gross/net.
    Filterable by status (Active / Inactive / Left / all) and department."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {"rows": []}
    year = getdate(nowdate()).year
    conds = ["e.company=%(c)s"]
    params = {"c": target, "y0": f"{year}-01-01", "y1": f"{year}-12-31"}
    if status and status != "all":
        conds.append("e.status=%(st)s"); params["st"] = status
    if department and department != "all":
        conds.append("e.department=%(dp)s"); params["dp"] = department
    if search:
        conds.append("(e.employee_name LIKE %(s)s OR e.name LIKE %(s)s OR IFNULL(e.department,'') LIKE %(s)s)")
        params["s"] = f"%{search}%"
    rows = frappe.db.sql(
        f"""SELECT e.name, e.employee_name nm, e.department dept, e.designation desig, e.status,
                   (SELECT a.base FROM `tabSalary Structure Assignment` a
                    WHERE a.employee=e.name AND a.docstatus=1 ORDER BY a.from_date DESC LIMIT 1) base,
                   (SELECT MAX(s.start_date) FROM `tabSalary Slip` s WHERE s.employee=e.name AND s.docstatus=1) last_slip,
                   (SELECT SUM(s.gross_pay) FROM `tabSalary Slip` s WHERE s.employee=e.name AND s.docstatus=1
                    AND s.start_date BETWEEN %(y0)s AND %(y1)s) ytd_gross,
                   (SELECT SUM(s.net_pay) FROM `tabSalary Slip` s WHERE s.employee=e.name AND s.docstatus=1
                    AND s.start_date BETWEEN %(y0)s AND %(y1)s) ytd_net
            FROM `tabEmployee` e WHERE {' AND '.join(conds)}
            ORDER BY e.status='Active' DESC, e.employee_name LIMIT 300""", params, as_dict=True)
    for r in rows:
        r["base"] = _m(r["base"]); r["ytd_gross"] = _m(r["ytd_gross"]); r["ytd_net"] = _m(r["ytd_net"])
        r["last_slip"] = str(r["last_slip"] or "")[:10]
    return {"company": target, "rows": rows, "currency": _ccy(target),
            "departments": _departments(target),
            "statuses": ["Active", "Inactive", "Left", "Suspended"]}


@frappe.whitelist()
def employee_payroll(company=None, employee=None):
    """One employee: profile, current salary structure components, slip history, YTD."""
    assert_portal_access()
    target = _target(company)
    if not (target and employee):
        return {}
    e = frappe.db.get_value(
        "Employee", employee,
        ["name", "employee_name", "department", "designation", "status", "date_of_joining",
         "company", "cell_number"], as_dict=True)
    if not e:
        frappe.throw("Employee not found")
    base = _m(frappe.db.sql(
        """SELECT base FROM `tabSalary Structure Assignment` WHERE employee=%s AND docstatus=1
           ORDER BY from_date DESC LIMIT 1""", (employee,))[0][0]) if frappe.db.exists(
        "Salary Structure Assignment", {"employee": employee, "docstatus": 1}) else 0.0
    # latest slip's components as the current structure
    latest = frappe.db.get_value("Salary Slip", {"employee": employee, "docstatus": 1},
                                 "name", order_by="start_date desc")
    components = []
    if latest:
        components = [
            {"component": r.salary_component, "type": "earning" if r.parentfield == "earnings" else "deduction",
             "amount": _m(r.amount)}
            for r in frappe.db.sql(
                """SELECT salary_component, parentfield, amount FROM `tabSalary Detail`
                   WHERE parent=%s ORDER BY parentfield DESC, amount DESC""", (latest,), as_dict=True)]
    slips = [
        {"name": r.name, "month": str(r.start_date)[:7], "gross": _m(r.gross_pay),
         "ded": _m(r.total_deduction), "net": _m(r.net_pay), "status": r.status}
        for r in frappe.db.sql(
            """SELECT name, start_date, gross_pay, total_deduction, net_pay, status
               FROM `tabSalary Slip` WHERE employee=%s AND docstatus=1
               ORDER BY start_date DESC LIMIT 18""", (employee,), as_dict=True)]
    year = getdate(nowdate()).year
    ytd = frappe.db.sql(
        """SELECT SUM(gross_pay) g, SUM(net_pay) n, COUNT(*) c FROM `tabSalary Slip`
           WHERE employee=%s AND docstatus=1 AND start_date BETWEEN %s AND %s""",
        (employee, f"{year}-01-01", f"{year}-12-31"), as_dict=True)[0]
    e["date_of_joining"] = str(e["date_of_joining"] or "")[:10]
    return {"company": target, "currency": _ccy(target),
            "employee": e, "base": base, "components": components, "slips": slips,
            "ytd": {"gross": _m(ytd.g), "net": _m(ytd.n), "slips": ytd.c or 0}}


@frappe.whitelist()
def payroll_runs(company=None):
    """Bulk payroll runs (Payroll Entries) with slip counts + totals, latest first."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {"runs": []}
    runs = frappe.db.sql(
        """SELECT pe.name, pe.posting_date, pe.start_date, pe.end_date, pe.docstatus,
                  (SELECT COUNT(*) FROM `tabSalary Slip` s WHERE s.payroll_entry=pe.name AND s.docstatus=1) slips,
                  (SELECT SUM(s.net_pay) FROM `tabSalary Slip` s WHERE s.payroll_entry=pe.name AND s.docstatus=1) net
           FROM `tabPayroll Entry` pe WHERE pe.company=%s ORDER BY pe.posting_date DESC LIMIT 24""",
        (target,), as_dict=True)
    for r in runs:
        r["month"] = str(r.start_date)[:7]
        r["net"] = _m(r["net"])
        r["status"] = "Posted" if r.docstatus == 1 else ("Cancelled" if r.docstatus == 2 else "Draft")
    return {"company": target, "runs": runs, "currency": _ccy(target)}


@frappe.whitelist()
def salary_slip_detail(company=None, slip=None):
    """Full component breakdown for one salary slip."""
    assert_portal_access()
    target = _target(company)
    if not (target and slip):
        return {}
    s = frappe.db.get_value(
        "Salary Slip", slip,
        ["name", "employee_name", "employee", "start_date", "end_date", "posting_date",
         "gross_pay", "total_deduction", "net_pay", "status", "department"], as_dict=True)
    if not s:
        frappe.throw("Slip not found")
    lines = frappe.db.sql(
        """SELECT salary_component, parentfield, amount FROM `tabSalary Detail`
           WHERE parent=%s ORDER BY parentfield DESC, amount DESC""", (slip,), as_dict=True)
    earnings = [{"component": r.salary_component, "amount": _m(r.amount)} for r in lines if r.parentfield == "earnings"]
    deductions = [{"component": r.salary_component, "amount": _m(r.amount)} for r in lines if r.parentfield == "deductions"]
    for k in ("start_date", "end_date", "posting_date"):
        s[k] = str(s[k] or "")[:10]
    for k in ("gross_pay", "total_deduction", "net_pay"):
        s[k] = _m(s[k])
    return {"company": target, "slip": s, "earnings": earnings, "deductions": deductions,
            "currency": _ccy(target)}


@frappe.whitelist()
def payroll_components(company=None, from_date=None, to_date=None):
    """Component catalog: each earning/deduction with its period total and the GL
    account it posts to (the payroll→accounting map)."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    fd, td = _period(from_date, to_date)
    acct = {r.parent: r.account for r in frappe.db.sql(
        "SELECT parent, account FROM `tabSalary Component Account` WHERE company=%s", (target,), as_dict=True)}
    rows = frappe.db.sql(
        """SELECT sd.salary_component comp, sd.parentfield typ, SUM(sd.amount) tot, COUNT(*) n
           FROM `tabSalary Detail` sd JOIN `tabSalary Slip` ss ON ss.name=sd.parent
           WHERE ss.company=%s AND ss.docstatus=1 AND ss.start_date BETWEEN %s AND %s
           GROUP BY sd.salary_component, sd.parentfield ORDER BY tot DESC""", (target, fd, td), as_dict=True)
    earnings, deductions = [], []
    for r in rows:
        item = {"component": r.comp, "total": _m(r.tot), "count": r.n,
                "account": acct.get(r.comp, ""), "account_short": (acct.get(r.comp, "") or "").split(" - ")[0]}
        (earnings if r.typ == "earnings" else deductions).append(item)
    return {"company": target, "currency": _ccy(target),
            "from_date": str(fd), "to_date": str(td),
            "earnings": earnings, "deductions": deductions,
            "earning_total": _m(sum(x["total"] for x in earnings)),
            "deduction_total": _m(sum(x["total"] for x in deductions))}


@frappe.whitelist()
def payroll_gl_recon(company=None, from_date=None, to_date=None):
    """Tie each salary component's slip total to its mapped GL account's actual
    movement in the period — surfaces payroll that didn't post cleanly (manual
    adjustments, mis-postings). Earnings count +, deductions −."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    fd, td = _period(from_date, to_date)
    currency = _ccy(target)
    acct = {r.parent: r.account for r in frappe.db.sql(
        "SELECT parent, account FROM `tabSalary Component Account` WHERE company=%s", (target,), as_dict=True)}
    # expected per account from the slips
    exp, aname = {}, {}
    for r in frappe.db.sql(
            """SELECT sd.salary_component comp, sd.parentfield typ, SUM(sd.amount) amt
               FROM `tabSalary Detail` sd JOIN `tabSalary Slip` ss ON ss.name=sd.parent
               WHERE ss.company=%s AND ss.docstatus=1 AND ss.start_date BETWEEN %s AND %s
               GROUP BY sd.salary_component, sd.parentfield""", (target, fd, td), as_dict=True):
        a = acct.get(r.comp)
        if not a:
            continue
        exp[a] = exp.get(a, 0.0) + (flt(r.amt) if r.typ == "earnings" else -flt(r.amt))
    if not exp:
        return {"company": target, "currency": currency, "from_date": str(fd), "to_date": str(td),
                "rows": [], "total_expected": 0, "total_actual": 0, "total_variance": 0, "mismatched": 0}
    # actual GL per those accounts
    accts = tuple(exp.keys())
    gl = {r.account: flt(r.bal) for r in frappe.db.sql(
        """SELECT account, SUM(debit-credit) bal FROM `tabGL Entry`
           WHERE company=%(c)s AND is_cancelled=0 AND account IN %(a)s
             AND posting_date BETWEEN %(fd)s AND %(td)s GROUP BY account""",
        {"c": target, "a": accts, "fd": fd, "td": td}, as_dict=True)}
    for a in accts:
        aname[a] = frappe.db.get_value("Account", a, "account_name") or a
    rows = []
    for a, e in exp.items():
        actual = gl.get(a, 0.0)
        var = _m(actual - e)
        rows.append({"account": a, "num": a.split(" - ")[0], "name": aname.get(a, a),
                     "expected": _m(e), "actual": _m(actual), "variance": var,
                     "tied": abs(var) < 0.01})
    rows.sort(key=lambda x: -abs(x["variance"]))
    return {"company": target, "currency": currency, "from_date": str(fd), "to_date": str(td),
            "rows": rows,
            "total_expected": _m(sum(r["expected"] for r in rows)),
            "total_actual": _m(sum(r["actual"] for r in rows)),
            "total_variance": _m(sum(r["variance"] for r in rows)),
            "mismatched": sum(1 for r in rows if not r["tied"])}


# ─────────────────────────────────────────────────────────────────────────────
# Month-end payroll CLOSE
#
# A verification + sign-off operation, not slip generation. For a chosen month it
# checks completeness (every active employee has a submitted slip, no drafts left,
# the run posted to the GL), then lets the accountant LOCK the month with an
# audited, reversible sign-off (an Accounting Portal Action — no GL side effect).
# Slip creation stays in ERPNext HR; the portal verifies and closes.
# ─────────────────────────────────────────────────────────────────────────────

CLOSE_ACTION = "Close payroll month"


def _close_dedupe(target, month):
    return f"payroll-close:{target}:{month}"


def _closed_record(target, month):
    name = frappe.db.get_value(
        "Accounting Portal Action",
        {"dedupe_key": _close_dedupe(target, month), "status": "Posted"},
        ["name", "posted_on", "proposed_by", "notes"], as_dict=True)
    return name


@frappe.whitelist()
def payroll_close_status(company=None, month=None):
    """Everything the Close screen needs for one month: completeness, run status,
    GL posting, payable, the missing-slip roster, and whether it's already closed.
    Also returns the list of months available to close (latest first)."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    currency = _ccy(target)
    # months that have any slip activity, newest first
    months = [r[0] for r in frappe.db.sql(
        """SELECT DISTINCT DATE_FORMAT(start_date,'%%Y-%%m') m FROM `tabSalary Slip`
           WHERE company=%s AND docstatus<2 ORDER BY m DESC LIMIT 24""", (target,)) if r[0]]
    if not month:
        month = months[0] if months else str(getdate(nowdate()))[:7]

    active = frappe.db.count("Employee", {"company": target, "status": "Active"})
    sub = frappe.db.sql(
        """SELECT COUNT(*) slips, COUNT(DISTINCT employee) emps,
                  SUM(gross_pay) gross, SUM(total_deduction) ded, SUM(net_pay) net
           FROM `tabSalary Slip`
           WHERE company=%s AND docstatus=1 AND DATE_FORMAT(start_date,'%%Y-%%m')=%s""",
        (target, month), as_dict=True)[0]
    drafts = frappe.db.sql(
        """SELECT COUNT(*) FROM `tabSalary Slip`
           WHERE company=%s AND docstatus=0 AND DATE_FORMAT(start_date,'%%Y-%%m')=%s""",
        (target, month))[0][0]
    missing = frappe.db.sql(
        """SELECT e.name, e.employee_name nm, IFNULL(NULLIF(e.department,''),'—') dept
           FROM `tabEmployee` e WHERE e.company=%s AND e.status='Active'
             AND NOT EXISTS(SELECT 1 FROM `tabSalary Slip` s WHERE s.employee=e.name AND s.docstatus=1
                            AND DATE_FORMAT(s.start_date,'%%Y-%%m')=%s)
           ORDER BY e.employee_name LIMIT 200""", (target, month), as_dict=True)
    runs = frappe.db.sql(
        """SELECT name, docstatus,
                  (SELECT COUNT(*) FROM `tabSalary Slip` s WHERE s.payroll_entry=pe.name AND s.docstatus=1) slips
           FROM `tabPayroll Entry` pe
           WHERE company=%s AND DATE_FORMAT(start_date,'%%Y-%%m')=%s ORDER BY creation DESC""",
        (target, month), as_dict=True)
    for r in runs:
        r["status"] = "Posted" if r.docstatus == 1 else ("Cancelled" if r.docstatus == 2 else "Draft")
    employer = _employer_contrib(target, f"{month}-01", _month_end(month))

    slips_n = int(sub.slips or 0)
    emps_n = int(sub.emps or 0)
    net = _m(sub.net)
    gross = _m(sub.gross)
    run_submitted = any(r["docstatus"] == 1 for r in runs)
    # If there's no Payroll Entry at all but individual slips are submitted, the
    # month still posted to the GL — treat submitted slips as the posting signal.
    posted_gl = run_submitted or slips_n > 0
    closed = _closed_record(target, month)

    checklist = [
        {"key": "slips", "ok": (missing == [] and emps_n >= active and active > 0),
         "n": emps_n, "of": active},
        {"key": "drafts", "ok": int(drafts or 0) == 0, "n": int(drafts or 0)},
        {"key": "posted", "ok": bool(posted_gl)},
    ]
    ready = all(s["ok"] for s in checklist)

    return {
        "company": target, "currency": currency, "month": month, "months": months,
        "active": active, "slips": slips_n, "emps_with_slip": emps_n,
        "drafts": int(drafts or 0), "missing": missing, "missing_count": len(missing),
        "gross": gross, "net": net, "deductions": _m(sub.ded),
        "employer_contrib": employer, "cost_to_company": _m(gross + employer),
        "runs": runs, "posted_gl": bool(posted_gl),
        "salary_payable": _m(max(0.0, _salary_payable(target))),
        "checklist": checklist, "ready": ready,
        "closed": bool(closed),
        "closed_on": str(closed.posted_on)[:19] if closed else None,
        "closed_by": (closed.proposed_by if closed else None),
        "closed_action": (closed.name if closed else None),
    }


def _month_end(month):
    """'2026-05' → last calendar day of that month (yyyy-mm-dd)."""
    return str(get_last_day(f"{month}-01"))


@frappe.whitelist()
def payroll_close_month(company=None, month=None, notes=None, reopen=0):
    """Lock (or reopen) a payroll month. Audited + reversible, no GL posting."""
    assert_portal_access()
    target = _target(company)
    if not (target and month):
        frappe.throw("company and month are required")
    from accounting_portal.api import _actions
    dk = _close_dedupe(target, month)
    if int(reopen or 0):
        rec = _closed_record(target, month)
        if rec:
            return _actions.revert_action(rec.name)
        return {"reopened": False, "month": month}
    st = payroll_close_status(target, month)
    return _actions.execute(
        CLOSE_ACTION, target, dk,
        payload={"month": month, "net": st.get("net"), "slips": st.get("slips"),
                 "active": st.get("active"), "missing": st.get("missing_count"),
                 "ready": st.get("ready")},
        amount=0, notes=notes or f"Payroll month {month} closed")


def _close_month_poster(doc):
    """No GL — the audited Accounting Portal Action row IS the sign-off artifact."""
    p = json.loads(doc.payload or "{}")
    return {"voucher_type": "Payroll Close", "voucher_no": p.get("month"), "result": p}


def _close_month_reverter(doc):
    """Reopen = simply flip the sign-off action back (handled by revert_action)."""
    return {"reopened": True, "month": json.loads(doc.payload or "{}").get("month")}


# Wire the close sign-off into the write gateway: no-GL, exempt from the approval
# gate, and reversible (reopen).
def _register():
    from accounting_portal.api import _actions
    _actions.register_poster(CLOSE_ACTION, _close_month_poster)
    _actions.register_reverter(CLOSE_ACTION, _close_month_reverter)
    _actions._NO_GATE.add(CLOSE_ACTION)


_register()
