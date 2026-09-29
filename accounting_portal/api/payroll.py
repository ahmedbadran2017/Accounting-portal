"""Payroll — a full payroll section over ERPNext HR (Salary Slips, Payroll
Entries, Salary Structures) with the accounting lens Justyol lacked: one
consolidated cost-to-company, salary payable outstanding, completeness alerts,
the component→GL-account map, and a month-end **close** operation (verify → sign
off / lock, with undo). Entity-scoped (Morocco + Maslak), cached.

Money is returned at full precision (2 decimals) — this is an accounting system,
so figures are exact, never rounded to thousands.
"""
import json
import re

import frappe

from accounting_portal.api._actions import digest as _digest
from frappe.utils import (flt, cint, add_months, nowdate, getdate, get_last_day,
                          now_datetime)

from accounting_portal.api.permissions import assert_portal_access, assert_can_write, resolve_companies


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


def _as_privileged(doc):
    """Run an HRMS document method as the portal, not as the signed-in user.

    An `Accountant` may post payroll by the portal's own model, but that role
    carries no HRMS DocType permissions, and `submit_salary_slips()` opens with
    `check_permission("write")`. Generate would succeed and Submit slips would
    die with a bare "Not permitted", leaving the accrual unposted. The flag has
    to be set on the freshly fetched document, not inherited from an earlier one.
    """
    doc.flags.ignore_permissions = True
    return doc

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
                   (SELECT a.salary_structure FROM `tabSalary Structure Assignment` a
                    WHERE a.employee=e.name AND a.docstatus=1 ORDER BY a.from_date DESC LIMIT 1) structure,
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
        r["has_structure"] = bool(r.get("structure"))
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
def payroll_run_detail(company=None, run=None):
    """One Payroll Entry (run): header + the salary slips it produced."""
    assert_portal_access()
    target = _target(company)
    if not (target and run):
        return {}
    pe = frappe.db.get_value(
        "Payroll Entry", run,
        ["name", "company", "posting_date", "start_date", "end_date", "payroll_frequency",
         "payroll_payable_account", "cost_center", "currency", "docstatus", "number_of_employees"],
        as_dict=True)
    if not pe or pe.company != target:
        frappe.throw("Run not found")
    slips = [
        {"name": r.name, "employee": r.employee, "employee_name": r.employee_name,
         "gross": _m(r.gross_pay), "ded": _m(r.total_deduction), "net": _m(r.net_pay),
         "status": r.status, "docstatus": r.docstatus}
        for r in frappe.db.sql(
            """SELECT name, employee, employee_name, gross_pay, total_deduction, net_pay, status, docstatus
               FROM `tabSalary Slip` WHERE payroll_entry=%s ORDER BY employee_name""", (run,), as_dict=True)]
    for kf in ("posting_date", "start_date", "end_date"):
        pe[kf] = str(pe[kf] or "")[:10]
    pe["status"] = "Posted" if pe.docstatus == 1 else ("Cancelled" if pe.docstatus == 2 else "Draft")
    return {"company": target, "currency": _ccy(target), "run": pe, "slips": slips,
            "gross": _m(sum(s["gross"] for s in slips)),
            "net": _m(sum(s["net"] for s in slips)),
            "submitted": sum(1 for s in slips if s["docstatus"] == 1),
            "drafts": sum(1 for s in slips if s["docstatus"] == 0)}


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
         "gross_pay", "total_deduction", "net_pay", "status", "department", "designation",
         "bank_name", "bank_account_no"], as_dict=True)
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
    slip_months = [r[0] for r in frappe.db.sql(
        """SELECT DISTINCT DATE_FORMAT(start_date,'%%Y-%%m') m FROM `tabSalary Slip`
           WHERE company=%s AND docstatus<2 ORDER BY m DESC LIMIT 24""", (target,)) if r[0]]
    # Also offer the recent CALENDAR months (incl. the current one) even when they
    # have no slips yet — so a fresh month can be started/closed (the team begins
    # the new month's payroll near month-end).
    cal_months, d = [], getdate(nowdate()).replace(day=1)
    for _ in range(14):
        cal_months.append(str(d)[:7])
        d = getdate(add_months(d, -1))
    months = sorted(set(slip_months) | set(cal_months), reverse=True)
    if not month:
        # default to the latest month that actually has slips, else the current month
        month = slip_months[0] if slip_months else str(getdate(nowdate()))[:7]

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

    # The sheet is the first step of the month now, so it belongs in the list of
    # things that have to be true before it closes — first, because everything
    # below it is built on the figures it approves.
    appr = _sheet_approved(target, month)
    checklist = [
        {"key": "sheet", "ok": bool(appr), "n": int(appr.get("documents") or 0) if appr else 0},
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
        "checklist": checklist, "ready": ready, "sheet_approved": appr or None,
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


# ─────────────────────────────────────────────────────────────────────────────
# FULL payroll operations — generate slips → submit → pay. Every step goes through
# the write gateway (audited, idempotent, gated for material amounts, reversible),
# so the team runs the whole cycle from the portal instead of ERPNext HR.
#   • Generate  → creates a Payroll Entry + draft Salary Slips (no GL yet)
#   • Submit    → submits the slips (posts the salary accrual to the GL)
#   • Pay       → posts the bank "Bank Entry" journal that clears salary payable
# ─────────────────────────────────────────────────────────────────────────────

RUN_ACTION = "Run payroll"          # generate the run + draft slips
SUBMIT_SLIPS_ACTION = "Submit payroll slips"
PAY_ACTION = "Pay salaries"


def _payroll_defaults(target):
    """Best-guess Payroll Entry defaults (payable account, cost center) taken from
    the company's most recent run, then company settings."""
    last = frappe.db.get_value(
        "Payroll Entry", {"company": target}, ["payroll_payable_account", "cost_center"],
        order_by="creation desc", as_dict=True) or frappe._dict()
    payable = last.payroll_payable_account or frappe.db.get_value(
        "Company", target, "default_payroll_payable_account")
    cc = last.cost_center or frappe.db.get_value("Company", target, "cost_center")
    return payable, cc


def _month_bounds(month):
    return f"{month}-01", str(get_last_day(f"{month}-01"))


def _bank_accounts(target):
    return frappe.db.sql(
        """SELECT name, account_name nm FROM `tabAccount`
           WHERE company=%s AND is_group=0 AND disabled=0 AND account_type='Bank' ORDER BY name""",
        (target,), as_dict=True)


@frappe.whitelist()
def payroll_run_preview(company=None, month=None):
    """Read-only: what a generate/submit/pay would touch for the month — eligible
    employees (active + assigned a salary structure, no slip yet), current draft /
    submitted counts, outstanding payable, and the account defaults + bank list."""
    assert_portal_access()
    target = _target(company)
    if not (target and month):
        return {}
    start, end = _month_bounds(month)
    eligible = frappe.db.sql(
        """SELECT e.name, e.employee_name nm FROM `tabEmployee` e
           WHERE e.company=%s AND e.status='Active'
             AND EXISTS(SELECT 1 FROM `tabSalary Structure Assignment` a
                        WHERE a.employee=e.name AND a.docstatus=1 AND a.from_date<=%s)
             AND NOT EXISTS(SELECT 1 FROM `tabSalary Slip` s WHERE s.employee=e.name AND s.docstatus<2
                            AND DATE_FORMAT(s.start_date,'%%Y-%%m')=%s)
           ORDER BY e.employee_name""", (target, end, month), as_dict=True)
    drafts = frappe.db.sql(
        """SELECT name, employee_name nm, net_pay FROM `tabSalary Slip`
           WHERE company=%s AND docstatus=0 AND DATE_FORMAT(start_date,'%%Y-%%m')=%s""",
        (target, month), as_dict=True)
    submitted = frappe.db.sql(
        """SELECT COUNT(*) n, SUM(net_pay) net FROM `tabSalary Slip`
           WHERE company=%s AND docstatus=1 AND DATE_FORMAT(start_date,'%%Y-%%m')=%s""",
        (target, month), as_dict=True)[0]
    payable, cc = _payroll_defaults(target)
    to_pay = _pay_plan(target, month)
    return {
        "company": target, "currency": _ccy(target), "month": month,
        "eligible": eligible, "eligible_count": len(eligible),
        "drafts": drafts, "draft_count": len(drafts),
        "submitted_count": int(submitted.n or 0), "submitted_net": _m(submitted.net),
        "payable_account": payable, "cost_center": cc,
        "banks": _bank_accounts(target),
        "to_pay_net": _m(sum(p["amount"] for p in to_pay)), "to_pay_count": len(to_pay),
        # Generating slips before the sheet is approved produces a full month for
        # everyone — no absence, no delay, no overtime — and nothing on the screen
        # said so. The run strip shows this as its own step now.
        "sheet_approved": _sheet_approved(target, month) or None,
    }


# ── Generate (create Payroll Entry + draft slips) ──────────────────────────────

@frappe.whitelist()
def payroll_generate(company=None, month=None, notes=None):
    assert_can_write()
    target = _target(company)
    if not (target and month):
        frappe.throw("company and month are required")
    from accounting_portal.api import _actions
    # Preflight: HRMS answers "No employees found" for a month that is simply
    # already run, which reads like a broken portal. Say what is actually true.
    start, _end = _month_bounds(month)
    done = frappe.db.sql(
        "SELECT employee, payroll_entry FROM `tabSalary Slip` WHERE company=%s AND start_date=%s AND docstatus=1",
        (target, start), as_dict=True)
    if done:
        slipped = {r.employee for r in done}
        active = set(frappe.get_all("Employee", {"company": target, "status": "Active"}, pluck="name"))
        assigned = set(frappe.get_all("Salary Structure Assignment", {"company": target, "docstatus": 1}, pluck="employee"))
        remaining = sorted((active & assigned) - slipped)
        runs = sorted({r.payroll_entry for r in done if r.payroll_entry})
        if not remaining:
            frappe.throw(f"{month} is already run: {len(done)} submitted slips"
                         f"{' (' + ', '.join(runs[:4]) + ('…' if len(runs) > 4 else '') + ')' if runs else ''}. "
                         "Nothing left to generate — see Runs.")
    key = "payroll-run:" + _digest(f"{target}:{month}", 14)
    return _actions.execute(RUN_ACTION, target, key, payload={"month": month},
                            amount=0, notes=notes or f"Generate payroll slips {month}")


def _run_poster(doc):
    p = json.loads(doc.payload or "{}")
    target, month = doc.company, p["month"]
    start, end = _month_bounds(month)
    payable, cc = _payroll_defaults(target)
    pe = frappe.get_doc({
        "doctype": "Payroll Entry", "company": target, "posting_date": end,
        "start_date": start, "end_date": end, "payroll_frequency": "Monthly",
        "currency": _ccy(target), "exchange_rate": 1,
        # HRMS looks salary structures up with
        #   WHERE salary_slip_based_on_timesheet = %(salary_slip_based_on_timesheet)s
        # and this field was never set, so it arrived as NULL — and `= NULL` is
        # never true in SQL. Zero structures means zero employees, and the run
        # died with "No employees found" on a company where all 27 active staff
        # were correctly assigned. Measured on PROD: None -> 0 structures,
        # 0 -> 21 structures -> 27 employees.
        "salary_slip_based_on_timesheet": 0,
        "payroll_payable_account": payable, "cost_center": cc,
    })
    try:
        pe.fill_employee_details()
    except frappe.ValidationError:
        frappe.clear_last_message()
        # The old message named the payable account and the assignment count, so
        # it read as "your assignments are wrong" — and sent us auditing 127
        # perfectly good assignments while the real cause was the NULL filter
        # above. Report every input HRMS had, so a zero is visible where it is.
        n_slipped = frappe.db.count("Salary Slip", {"company": target, "start_date": start, "docstatus": 1})
        n_active = frappe.db.count("Employee", {"company": target, "status": "Active"})
        try:
            n_struct = len(frappe.get_attr(
                "hrms.payroll.doctype.payroll_entry.payroll_entry.get_salary_structure")(
                target, _ccy(target), 0, "Monthly") or [])
        except Exception:
            n_struct = -1
        n_assigned = frappe.db.count("Salary Structure Assignment",
                                     {"company": target, "docstatus": 1, "payroll_payable_account": payable})
        frappe.throw(
            f"HRMS found no one to run for {month}. What it had to work with: "
            f"{n_active} active employees · {n_struct} active monthly {_ccy(target)} salary structures · "
            f"{n_assigned} assignments on {payable} · {n_slipped} already hold a submitted slip. "
            "A zero on structures means the lookup is failing, not the data; otherwise "
            "the missing people need an assignment (Employees → Assign structure).")
    if not pe.get("employees"):
        frappe.throw("No eligible employees to run (each needs a submitted Salary Structure Assignment).")
    pe.insert(ignore_permissions=True)
    pe.submit()
    pe.create_salary_slips()  # inline for small runs; enqueues for big ones
    n = frappe.db.count("Salary Slip", {"payroll_entry": pe.name})
    return {"voucher_type": "Payroll Entry", "voucher_no": pe.name,
            "result": {"payroll_entry": pe.name, "employees": len(pe.employees), "slips_created": n}}


def _run_reverter(doc):
    """Undo a generate: delete the draft slips it created, then cancel the run.
    Refuses if any of its slips are already submitted (use the submit-undo first)."""
    pe = doc.voucher_no
    if not pe or not frappe.db.exists("Payroll Entry", pe):
        return {"noop": True}
    if frappe.db.exists("Salary Slip", {"payroll_entry": pe, "docstatus": 1}):
        frappe.throw("This run has submitted slips — revert the submission first.")
    for s in frappe.get_all("Salary Slip", {"payroll_entry": pe, "docstatus": 0}, pluck="name"):
        frappe.delete_doc("Salary Slip", s, force=1, ignore_permissions=True)
    if frappe.db.get_value("Payroll Entry", pe, "docstatus") == 1:
        _as_privileged(frappe.get_doc("Payroll Entry", pe)).cancel()
    return {"cancelled_run": pe}


# ── Submit slips (post the accrual to the GL) ──────────────────────────────────

@frappe.whitelist()
def payroll_submit_slips(company=None, month=None, notes=None):
    assert_can_write()
    target = _target(company)
    if not (target and month):
        frappe.throw("company and month are required")
    net = flt(frappe.db.sql(
        """SELECT SUM(net_pay) FROM `tabSalary Slip`
           WHERE company=%s AND docstatus=0 AND DATE_FORMAT(start_date,'%%Y-%%m')=%s""",
        (target, month))[0][0])
    from accounting_portal.api import _actions
    key = "payroll-submit:" + _digest(f"{target}:{month}", 14)
    return _actions.execute(SUBMIT_SLIPS_ACTION, target, key, payload={"month": month},
                            amount=net, notes=notes or f"Submit payroll slips {month}")


def _submit_poster(doc):
    p = json.loads(doc.payload or "{}")
    target, month = doc.company, p["month"]
    # Submit through each month's Payroll Entry so HRMS posts the accrual JV.
    runs = frappe.get_all("Payroll Entry",
                          {"company": target, "docstatus": 1}, ["name", "start_date"])
    runs = [r for r in runs if str(r.start_date)[:7] == month
            and frappe.db.exists("Salary Slip", {"payroll_entry": r.name, "docstatus": 0})]
    done = []
    for r in runs:
        _as_privileged(frappe.get_doc("Payroll Entry", r.name)).submit_salary_slips()
        done.append(r.name)
    # Any stray draft slips not tied to a run — submit directly.
    for s in frappe.get_all("Salary Slip",
                            {"company": target, "docstatus": 0}, ["name", "start_date"]):
        if str(s.start_date)[:7] == month:
            _as_privileged(frappe.get_doc("Salary Slip", s.name)).submit()
    return {"voucher_type": "Payroll Entry", "voucher_no": ",".join(done) or None,
            "result": {"runs_submitted": done, "month": month}}


def _submit_reverter(doc):
    """Cancel the month's submitted slips (reverses the accrual GL)."""
    p = json.loads(doc.payload or "{}")
    target, month = doc.company, p["month"]
    cancelled = 0
    for s in frappe.get_all("Salary Slip",
                            {"company": target, "docstatus": 1}, ["name", "start_date"]):
        if str(s.start_date)[:7] == month:
            _as_privileged(frappe.get_doc("Salary Slip", s.name)).cancel()
            cancelled += 1
    return {"cancelled_slips": cancelled, "month": month}


# ── Pay salaries (bank entry that clears salary payable) ───────────────────────

def _pay_plan(target, month):
    """Per-employee net still owed for the month = submitted-slip net minus what a
    prior Bank Entry already paid against that employee's payable/run."""
    slips = frappe.db.sql(
        """SELECT s.employee, s.employee_name nm, s.net_pay, s.payroll_entry pe
           FROM `tabSalary Slip` s
           WHERE s.company=%s AND s.docstatus=1 AND DATE_FORMAT(s.start_date,'%%Y-%%m')=%s""",
        (target, month), as_dict=True)
    plan = []
    for s in slips:
        payable, _cc = _payroll_defaults(target)
        acct = frappe.db.get_value("Payroll Entry", s.pe, "payroll_payable_account") if s.pe else payable
        # already paid to this employee against this run
        paid = flt(frappe.db.sql(
            """SELECT SUM(jea.debit) FROM `tabJournal Entry Account` jea
               JOIN `tabJournal Entry` je ON je.name=jea.parent
               WHERE je.docstatus=1 AND jea.party_type='Employee' AND jea.party=%s
                 AND jea.reference_type='Payroll Entry' AND jea.reference_name=%s""",
            (s.employee, s.pe))[0][0]) if s.pe else 0.0
        owe = _m(flt(s.net_pay) - paid)
        if owe > 0.005:
            plan.append({"employee": s.employee, "nm": s.employee_name, "amount": owe,
                         "account": acct, "pe": s.pe})
    return plan


@frappe.whitelist()
def payroll_pay(company=None, month=None, bank_account=None, notes=None):
    assert_can_write()
    target = _target(company)
    if not (target and month and bank_account):
        frappe.throw("company, month and bank_account are required")
    plan = _pay_plan(target, month)
    if not plan:
        frappe.throw("Nothing to pay — salaries for this month are already settled.")
    total = _m(sum(p["amount"] for p in plan))
    from accounting_portal.api import _actions
    key = "payroll-pay:" + _digest(f"{target}:{month}:{bank_account}:{total}", 14)
    return _actions.execute(PAY_ACTION, target, key,
                            payload={"month": month, "bank_account": bank_account},
                            amount=total, notes=notes or f"Pay salaries {month}")


def _pay_poster(doc):
    p = json.loads(doc.payload or "{}")
    target, month, bank = doc.company, p["month"], p["bank_account"]
    plan = _pay_plan(target, month)
    if not plan:
        frappe.throw("Nothing left to pay for this month.")
    start, end = _month_bounds(month)
    total = _m(sum(x["amount"] for x in plan))
    accounts = [{"account": x["account"], "party_type": "Employee", "party": x["employee"],
                 "debit_in_account_currency": x["amount"], "credit_in_account_currency": 0,
                 "reference_type": "Payroll Entry", "reference_name": x["pe"]} for x in plan]
    accounts.append({"account": bank, "debit_in_account_currency": 0,
                     "credit_in_account_currency": total})
    mm = month[5:7] + "-" + month[2:4]
    je = frappe.get_doc({
        "doctype": "Journal Entry", "voucher_type": "Bank Entry", "company": target,
        "posting_date": nowdate(), "multi_currency": 1,
        "cheque_no": f"SALARY {mm}", "cheque_date": nowdate(),
        "user_remark": f"Payment of salaries from {start} to {end}",
        "accounts": accounts,
    })
    je.insert(ignore_permissions=True)
    je.submit()
    return {"voucher_type": "Journal Entry", "voucher_no": je.name,
            "result": {"paid": total, "employees": len(plan), "bank": bank}}


# ── Assign a salary structure (so a new/unassigned employee becomes payable) ───

ASSIGN_ACTION = "Assign salary structure"


@frappe.whitelist()
def assignment_options(company=None):
    """Active salary structures for the company + defaults, for the assign form."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    structures = frappe.db.sql(
        """SELECT name, currency FROM `tabSalary Structure`
           WHERE company=%s AND docstatus=1 AND is_active='Yes' ORDER BY name""", (target,), as_dict=True)
    payable, cc = _payroll_defaults(target)
    return {"company": target, "currency": _ccy(target), "structures": structures,
            "default_from": str(get_last_day(nowdate()).replace(day=1)),
            "payable_account": payable, "cost_center": cc}


@frappe.whitelist()
def list_structure_assignments(company=None, employee=None, limit=300):
    """Who is on which structure, at what base, from when.

    The portal could create an assignment but never show one, so the only way to
    answer "is this person assigned, and at what base" was the Desk list — opened
    16 times in a fortnight. A payroll run that reports "No employees found" is
    almost always answered here.
    """
    assert_portal_access()
    target = _target(company)
    if not target:
        return {"rows": []}
    conds = ["a.company = %(c)s", "a.docstatus < 2"]
    params = {"c": target, "lim": int(limit or 300)}
    if employee:
        conds.append("a.employee = %(e)s"); params["e"] = employee
    rows = frappe.db.sql(
        """SELECT a.name, a.employee, e.employee_name nm, e.status emp_status,
                  a.salary_structure, a.from_date, a.base, a.currency, a.docstatus
           FROM `tabSalary Structure Assignment` a
           JOIN `tabEmployee` e ON e.name = a.employee
           WHERE """ + " AND ".join(conds) + """
           ORDER BY e.employee_name, a.from_date DESC
           LIMIT %(lim)s""", params, as_dict=True)
    # Only the newest row per employee is the one payroll will actually use;
    # the rest are history, and showing them all equally is how people end up
    # reading a superseded base as the current salary.
    seen = set()
    for r in rows:
        r["base"] = _m(r["base"])
        r["current"] = r["employee"] not in seen
        seen.add(r["employee"])
    # Active staff with no assignment at all — the actual cause of an empty run.
    unassigned = frappe.db.sql(
        """SELECT e.name, e.employee_name nm FROM `tabEmployee` e
           WHERE e.company=%s AND e.status='Active'
             AND NOT EXISTS (SELECT 1 FROM `tabSalary Structure Assignment` a
                             WHERE a.employee=e.name AND a.docstatus=1)
           ORDER BY e.employee_name""", (target,), as_dict=True)
    return {"company": target, "currency": _ccy(target), "rows": rows,
            "unassigned": unassigned, "count": len(rows)}


@frappe.whitelist()
def assign_structure(company=None, employee=None, salary_structure=None, from_date=None, base=None, notes=None):
    """Assign a salary structure to an employee (Salary Structure Assignment) so the
    payroll run can generate their slip. Audited + reversible (cancels the SSA)."""
    assert_can_write()
    target = _target(company)
    if not (target and employee and salary_structure):
        frappe.throw("company, employee and salary_structure are required")
    if not frappe.db.exists("Employee", {"name": employee, "company": target}):
        frappe.throw("Employee not found in this company")
    if not frappe.db.exists("Salary Structure", {"name": salary_structure, "company": target, "docstatus": 1}):
        frappe.throw("Salary structure not found")
    payable, _cc = _payroll_defaults(target)
    fd = from_date or str(get_last_day(nowdate()).replace(day=1))
    from accounting_portal.api import _actions
    key = "assign-ssa:" + _digest(f"{target}:{employee}:{salary_structure}:{fd}", 14)
    return _actions.execute(
        ASSIGN_ACTION, target, key,
        payload={"employee": employee, "salary_structure": salary_structure, "from_date": fd,
                 "base": flt(base or 0), "currency": _ccy(target), "payable": payable},
        amount=0, notes=notes or f"Assign {salary_structure} to {employee}")


def _assign_poster(doc):
    p = json.loads(doc.payload or "{}")
    ssa = frappe.get_doc({
        "doctype": "Salary Structure Assignment", "company": doc.company,
        "employee": p["employee"], "salary_structure": p["salary_structure"],
        "from_date": p["from_date"], "currency": p.get("currency") or _ccy(doc.company),
        "base": flt(p.get("base") or 0), "payroll_payable_account": p.get("payable"),
    })
    ssa.insert(ignore_permissions=True)
    ssa.submit()
    return {"voucher_type": "Salary Structure Assignment", "voucher_no": ssa.name,
            "result": {"employee": p["employee"], "structure": p["salary_structure"]}}


# ── Pay adjustments: bonuses & one-off deductions (Additional Salary) ──────────
# These are entered/reviewed PER MONTH and picked up automatically when the slip
# is generated — the "review everything before creating the slip" board.

ADJ_ACTION = "Add pay adjustment"


@frappe.whitelist()
def component_options(company=None):
    """Salary components split into earnings / deductions for the adjustment picker."""
    assert_portal_access()
    rows = frappe.db.sql("SELECT name, type FROM `tabSalary Component` WHERE disabled=0 ORDER BY type, name", as_dict=True)
    return {"earnings": [r.name for r in rows if r.type == "Earning"],
            "deductions": [r.name for r in rows if r.type == "Deduction"]}


# An Additional Salary belongs to a month either by its `payroll_date` or, for a
# ranged/recurring one, by its from/to window.
#
# The obvious way to write that is wrong, and shipped wrong:
#
#     payroll_date BETWEEN start AND end
#     OR (IFNULL(from_date,'0001-01-01') <= end AND IFNULL(to_date,'9999-12-31') >= start)
#
# Every one-off entry here has from_date and to_date NULL, so the second branch
# collapses to `'0001-01-01' <= end AND '9999-12-31' >= start` — true for every
# month that ever was. Measured on production: for September 2026 it matched all
# 640 adjustments ever created, 432,541 MAD, instead of none. That is what made
# the payroll sheet report a net of 272,000 against a gross of 134,000.
#
# The window only applies when a window was actually set.
_ADDSAL_MONTH = """(
    (a.payroll_date IS NOT NULL AND a.payroll_date BETWEEN %(s)s AND %(e)s)
 OR (a.payroll_date IS NULL
     AND (a.from_date IS NOT NULL OR a.to_date IS NOT NULL)
     AND IFNULL(a.from_date,'0001-01-01') <= %(e)s
     AND IFNULL(a.to_date,'9999-12-31') >= %(s)s)
)"""


@frappe.whitelist()
def pay_adjustments(company=None, month=None):
    """All bonuses / one-off deductions (Additional Salary) that apply to the month,
    grouped per employee — the pre-slip review board."""
    assert_portal_access()
    target = _target(company)
    if not (target and month):
        return {}
    start, end = _month_bounds(month)
    rows = frappe.db.sql(
        """SELECT a.name, a.employee, e.employee_name nm, a.salary_component comp, a.type, a.amount
           FROM `tabAdditional Salary` a JOIN `tabEmployee` e ON e.name=a.employee
           WHERE a.company=%(c)s AND a.docstatus<2 AND """ + _ADDSAL_MONTH + """
           ORDER BY e.employee_name, a.type""", {"c": target, "s": start, "e": end}, as_dict=True)
    # Approving the sheet writes Additional Salary too, so from this month on the
    # board carries rows nobody keyed by hand. Editing or deleting one of those
    # here would move the slip away from the sheet and leave no sign of it, so
    # they are marked, and the two write endpoints refuse them.
    mine = set(_sheet_approved(target, month).get("names") or [])
    by = {}
    for r in rows:
        r["amount"] = _m(r["amount"])
        r["from_sheet"] = 1 if r.name in mine else 0
        emp = by.setdefault(r.employee, {"employee": r.employee, "nm": r.nm, "earn": 0.0, "ded": 0.0, "items": []})
        emp["items"].append({"name": r.name, "comp": r.comp, "type": r.type,
                             "amount": r["amount"], "from_sheet": r["from_sheet"]})
        if r.type == "Earning":
            emp["earn"] += r["amount"]
        else:
            emp["ded"] += r["amount"]
    emps = sorted(by.values(), key=lambda x: x["nm"])
    for e in emps:
        e["earn"], e["ded"] = _m(e["earn"]), _m(e["ded"])
        e["net"] = _m(e["earn"] - e["ded"])
    return {"company": target, "currency": _ccy(target), "month": month, "employees": emps,
            "earn_total": _m(sum(e["earn"] for e in emps)), "ded_total": _m(sum(e["ded"] for e in emps)),
            "count": len(rows), "from_sheet_count": sum(1 for r in rows if r["from_sheet"])}


@frappe.whitelist()
def add_adjustment(company=None, employee=None, salary_component=None, amount=None, month=None, notes=None):
    """Add a bonus / deduction for an employee in a month (Additional Salary).
    Audited + reversible. Picked up automatically when the slip is generated."""
    assert_can_write()
    target = _target(company)
    if not (target and employee and salary_component and month):
        frappe.throw("company, employee, salary_component and month are required")
    amt = _m(amount)
    if amt <= 0:
        frappe.throw("Amount must be greater than zero")
    if not frappe.db.exists("Employee", {"name": employee, "company": target}):
        frappe.throw("Employee not found in this company")
    from accounting_portal.api import _actions
    key = "payadj:" + _digest(f"{target}:{employee}:{salary_component}:{amt}:{month}", 14)
    return _actions.execute(
        ADJ_ACTION, target, key,
        payload={"employee": employee, "salary_component": salary_component, "amount": amt, "month": month},
        amount=0, notes=notes or f"{salary_component} for {employee} ({month})")


def _adj_poster(doc):
    p = json.loads(doc.payload or "{}")
    ctype = frappe.db.get_value("Salary Component", p["salary_component"], "type")
    a = frappe.get_doc({
        "doctype": "Additional Salary", "company": doc.company, "employee": p["employee"],
        "salary_component": p["salary_component"], "type": ctype, "amount": flt(p["amount"]),
        "currency": _ccy(doc.company), "payroll_date": _month_end(p["month"]),
        "overwrite_salary_structure_amount": 0,
    })
    a.insert(ignore_permissions=True)
    if a.meta.is_submittable:
        a.submit()
    return {"voucher_type": "Additional Salary", "voucher_no": a.name,
            "result": {"employee": p["employee"], "component": p["salary_component"], "amount": flt(p["amount"])}}


ADJ_EDIT_ACTION = "Edit adjustment"


def _assert_not_sheet_owned(target, name):
    """Refuse to edit or delete an adjustment the payroll sheet wrote.

    Once a month is approved the adjustments board carries rows nobody keyed by
    hand. Changing one here moves the slip away from the sheet with nothing on
    either screen to say so — and the next re-approval would overwrite the change
    anyway. The sheet is where that figure lives.
    """
    d = frappe.db.get_value("Additional Salary", name, ["payroll_date", "from_date"], as_dict=True)
    if not d:
        return
    month = str(d.payroll_date or d.from_date or "")[:7]
    if not month:
        return
    if name in set(_sheet_approved(target, month).get("names") or []):
        frappe.throw(f"This line came from the {month} payroll sheet. Change it on the sheet and "
                     "re-approve the month — editing it here would silently split the two.")


@frappe.whitelist()
def update_adjustment(company=None, name=None, amount=None, salary_component=None, notes=None):
    """Change a bonus / deduction that is already there.

    ERPNext has no editable field on a submitted Additional Salary — not amount,
    not component, not the date; every one of them is `allow_on_submit = 0`. So
    "edit" is cancel-and-replace, in ERPNext and here alike. That is exactly what
    the team has been doing by hand on the Desk: 172 adjustments touched in 60
    days, each correction a delete and a re-entry under a new document name.

    This does the same thing as ONE gated action, so the audit trail reads
    "Edit adjustment: 1,500 → 1,200" instead of an unexplained delete followed
    by an unexplained insert.
    """
    assert_can_write()
    target = _target(company)
    if not (target and name):
        frappe.throw("company and name are required")
    old = frappe.db.get_value("Additional Salary", {"name": name, "company": target},
                              ["name", "employee", "salary_component", "amount", "payroll_date", "docstatus"],
                              as_dict=True)
    if not old:
        frappe.throw("Adjustment not found")
    if old.docstatus == 2:
        frappe.throw("This adjustment is already cancelled")
    _assert_not_sheet_owned(target, old.name)
    amt = _m(amount) if amount is not None else _m(old.amount)
    comp = salary_component or old.salary_component
    if amt <= 0:
        frappe.throw("Amount must be greater than zero")
    # Changing it after the slip is out changes nothing on the payslip and
    # quietly desynchronises the two. Say so rather than let it look applied.
    if old.payroll_date:
        start, end = _month_bounds(str(old.payroll_date)[:7])
        if frappe.db.exists("Salary Slip", {"employee": old.employee, "docstatus": 1,
                                            "start_date": [">=", start], "end_date": ["<=", end]}):
            frappe.throw("The payslip for this month is already submitted — the adjustment "
                         "cannot change it. Cancel the slip first, or post a correction next month.")
    from accounting_portal.api import _actions
    key = "payadjedit:" + _digest(f"{name}:{comp}:{amt}", 14)
    return _actions.execute(
        ADJ_EDIT_ACTION, target, key,
        payload={"name": name, "salary_component": comp, "amount": amt,
                 "employee": old.employee, "payroll_date": str(old.payroll_date or "")},
        amount=0,
        notes=notes or f"{old.salary_component} {_m(old.amount)} \u2192 {comp} {amt} for {old.employee}")


def _adj_edit_poster(doc):
    p = json.loads(doc.payload or "{}")
    old = frappe.get_doc("Additional Salary", p["name"])
    if old.docstatus == 1:
        old.cancel()
    frappe.delete_doc("Additional Salary", p["name"], force=1, ignore_permissions=True)
    ctype = frappe.db.get_value("Salary Component", p["salary_component"], "type")
    a = frappe.get_doc({
        "doctype": "Additional Salary", "company": doc.company, "employee": p["employee"],
        "salary_component": p["salary_component"], "type": ctype, "amount": flt(p["amount"]),
        "currency": _ccy(doc.company), "payroll_date": p.get("payroll_date") or None,
        "overwrite_salary_structure_amount": 0,
    })
    a.insert(ignore_permissions=True)
    if a.meta.is_submittable:
        a.submit()
    return {"voucher_type": "Additional Salary", "voucher_no": a.name,
            "result": {"replaced": p["name"], "with": a.name, "amount": flt(p["amount"])}}


@frappe.whitelist()
def remove_adjustment(company=None, name=None):
    """Remove a bonus / deduction (cancels + deletes the Additional Salary)."""
    assert_can_write()
    target = _target(company)
    if not (target and name and frappe.db.exists("Additional Salary", {"name": name, "company": target})):
        frappe.throw("Adjustment not found")
    _assert_not_sheet_owned(target, name)
    d = frappe.get_doc("Additional Salary", name)
    if d.docstatus == 1:
        d.cancel()
    frappe.delete_doc("Additional Salary", name, force=1, ignore_permissions=True)
    return {"removed": name}


# ── Full employee control: create / edit / status (HR master data) ─────────────

EMP_UPDATE_ACTION = "Update employee"
EMP_CREATE_ACTION = "Create employee"
_EMP_EDITABLE = ("employee_name", "first_name", "last_name", "gender", "date_of_birth", "salutation",
                 "date_of_joining", "status", "department", "designation", "employment_type",
                 "reports_to", "branch", "cell_number", "personal_email", "company_email",
                 "bank_name", "bank_ac_no", "iban", "relieving_date")
_EMP_DATES = ("date_of_birth", "date_of_joining", "relieving_date")


@frappe.whitelist()
def employee_form_options(company=None):
    """Dropdown sources for the employee create/edit form."""
    assert_portal_access()
    target = _target(company)
    return {
        "departments": frappe.get_all("Department", {"company": target}, pluck="name"),
        "designations": frappe.get_all("Designation", pluck="name"),
        "employment_types": frappe.get_all("Employment Type", pluck="name"),
        "genders": frappe.get_all("Gender", pluck="name"),
        "statuses": ["Active", "Inactive", "Suspended", "Left"],
    }


@frappe.whitelist()
def employee_profile(company=None, employee=None):
    """The editable fields for one employee."""
    assert_portal_access()
    target = _target(company)
    if not (target and employee):
        return {}
    e = frappe.db.get_value("Employee", {"name": employee, "company": target},
                            list(_EMP_EDITABLE) + ["name"], as_dict=True)
    if not e:
        frappe.throw("Employee not found")
    for k in _EMP_DATES:
        e[k] = str(e[k] or "")[:10]
    return e


@frappe.whitelist()
def update_employee(company=None, employee=None, fields=None, notes=None):
    """Edit an employee (name, department, status, bank, contact…). Audited +
    reversible — the prior values are captured and restored on undo."""
    assert_can_write()
    target = _target(company)
    if not (target and employee) or not frappe.db.exists("Employee", {"name": employee, "company": target}):
        frappe.throw("Employee not found")
    fields = fields if isinstance(fields, dict) else json.loads(fields or "{}")
    fields = {k: v for k, v in fields.items() if k in _EMP_EDITABLE}
    if not fields:
        frappe.throw("Nothing to update")
    prior = {k: frappe.db.get_value("Employee", employee, k) for k in fields}
    from accounting_portal.api import _actions
    key = "empupd:" + _digest(f"{employee}:{json.dumps(fields, sort_keys=True, default=str)}", 14)
    return _actions.execute(
        EMP_UPDATE_ACTION, target, key,
        payload={"employee": employee, "fields": fields,
                 "prior": {k: (str(v) if v not in (None, "") else None) for k, v in prior.items()}},
        amount=0, notes=notes or f"Update {employee}")


def _emp_apply(name, fields):
    emp = frappe.get_doc("Employee", name)
    for k, v in fields.items():
        emp.set(k, v if v not in ("", None) else None)
    emp.save(ignore_permissions=True)
    return emp


def _update_emp_poster(doc):
    p = json.loads(doc.payload or "{}")
    _emp_apply(p["employee"], p["fields"])
    return {"voucher_type": "Employee", "voucher_no": p["employee"], "result": p["fields"]}


def _update_emp_reverter(doc):
    p = json.loads(doc.payload or "{}")
    _emp_apply(p["employee"], p.get("prior") or {})
    return {"restored": list((p.get("prior") or {}).keys())}


@frappe.whitelist()
def create_employee(company=None, first_name=None, last_name=None, gender=None, date_of_birth=None,
                    date_of_joining=None, department=None, designation=None, employment_type=None,
                    cell_number=None, company_email=None, bank_name=None, bank_ac_no=None, iban=None, notes=None):
    """Add a new employee. Audited + reversible (deletes the fresh record on undo
    if it has no slips yet)."""
    assert_can_write()
    target = _target(company)
    if not (target and first_name and gender and date_of_birth and date_of_joining):
        frappe.throw("first name, gender, date of birth and joining date are required")
    payload = {"first_name": first_name, "last_name": last_name, "gender": gender,
               "date_of_birth": date_of_birth, "date_of_joining": date_of_joining,
               "department": department, "designation": designation, "employment_type": employment_type,
               "cell_number": cell_number, "company_email": company_email,
               "bank_name": bank_name, "bank_ac_no": bank_ac_no, "iban": iban}
    from accounting_portal.api import _actions
    key = "empnew:" + _digest(f"{target}:{first_name}:{last_name}:{date_of_joining}:{date_of_birth}", 14)
    return _actions.execute(EMP_CREATE_ACTION, target, key, payload=payload, amount=0,
                            notes=notes or f"New employee {first_name} {last_name or ''}".strip())


def _create_emp_poster(doc):
    p = json.loads(doc.payload or "{}")
    e = frappe.get_doc({"doctype": "Employee", "company": doc.company, "status": "Active",
                        **{k: v for k, v in p.items() if v not in ("", None)}})
    e.insert(ignore_permissions=True)
    return {"voucher_type": "Employee", "voucher_no": e.name,
            "result": {"employee": e.name, "employee_name": e.employee_name}}


def _create_emp_reverter(doc):
    name = doc.voucher_no
    if not name or not frappe.db.exists("Employee", name):
        return {"noop": True}
    if frappe.db.exists("Salary Slip", {"employee": name}) or frappe.db.exists("Salary Structure Assignment", {"employee": name}):
        frappe.throw("This employee already has payroll records — set status to Inactive instead of deleting.")
    frappe.delete_doc("Employee", name, force=1, ignore_permissions=True)
    return {"deleted": name}


# ── HR quick entries that used to need the Desk ────────────────────────────────
# The Desk trail (Jun–Sep 2026) showed Rofayda hand-keying 127 Employee Check-ins
# and 3 Employee Advances, Hanane 21 check-ins — none of which the portal offered.

ADV_ACTION = "Employee advance"
CHECKIN_ACTION = "Employee check-in"


@frappe.whitelist()
def list_checkins(company=None, from_date=None, to_date=None, employee=None):
    """Attendance log (Employee Checkin) for the company over a date range."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {"rows": []}
    if not (from_date and to_date):
        d = getdate(nowdate())
        from_date, to_date = d.replace(day=1), get_last_day(d)
    conds, params = ["e.company=%(c)s", "ec.time BETWEEN %(f)s AND %(t)s"], {
        "c": target, "f": f"{from_date} 00:00:00", "t": f"{to_date} 23:59:59"}
    if employee:
        conds.append("ec.employee=%(e)s"); params["e"] = employee
    rows = frappe.db.sql(
        f"""SELECT ec.name, ec.employee, e.employee_name nm, ec.log_type, ec.time, IFNULL(ec.device_id,'') device,
                   IFNULL(ec.attendance,'') attendance
            FROM `tabEmployee Checkin` ec JOIN `tabEmployee` e ON e.name=ec.employee
            WHERE {' AND '.join(conds)} ORDER BY ec.time DESC LIMIT 500""", params, as_dict=True)
    for r in rows:
        r["time"] = str(r["time"])[:16]
        r["deletable"] = int(r["device"] == "portal" and not r["attendance"])
    return {"company": target, "from_date": str(from_date), "to_date": str(to_date), "rows": rows}


@frappe.whitelist()
def add_checkin(company=None, employee=None, log_type=None, time=None):
    """Record one IN/OUT punch by hand (device_id 'portal'). Not gated — an
    attendance log posts nothing to the ledger — but audited."""
    assert_can_write()
    target = _target(company)
    if not (target and employee and time):
        frappe.throw("employee and time are required")
    if log_type not in ("IN", "OUT"):
        frappe.throw("log_type must be IN or OUT")
    if not frappe.db.exists("Employee", {"name": employee, "company": target}):
        frappe.throw("Employee not found in this company")
    doc = frappe.get_doc({"doctype": "Employee Checkin", "employee": employee, "log_type": log_type,
                          "time": str(time).replace("T", " ")[:19], "device_id": "portal"})
    doc.insert(ignore_permissions=True)
    from accounting_portal.api import _actions
    _actions.record(
        CHECKIN_ACTION, target, reference_doctype="Employee", reference_name=employee,
        voucher_type="Employee Checkin", voucher_no=doc.name, amount=0,
        payload=json.dumps({"employee": employee, "log_type": log_type, "time": str(doc.time)}),
        result=json.dumps({"name": doc.name}), notes=f"{log_type} {employee} {str(doc.time)[:16]}")
    return {"name": doc.name}


@frappe.whitelist()
def delete_checkin(name=None):
    """Remove a punch entered from the portal that attendance has not consumed yet."""
    assert_can_write()
    row = frappe.db.get_value("Employee Checkin", name, ["device_id", "attendance", "employee"], as_dict=True)
    if not row:
        frappe.throw("Not found")
    if row.device_id != "portal" or row.attendance:
        frappe.throw("Only portal-entered punches not yet used by attendance can be removed")
    if not frappe.db.exists("Employee", {"name": row.employee, "company": ["in", resolve_companies()]}):
        frappe.throw("Not permitted", frappe.PermissionError)
    frappe.delete_doc("Employee Checkin", name, ignore_permissions=True)
    return {"deleted": name}


@frappe.whitelist()
def advance_options(company=None):
    """Advance accounts + payment modes for the Employee Advance form."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    default = frappe.db.get_value("Company", target, "default_employee_advance_account")
    accounts = frappe.db.sql(
        """SELECT name AS value, name AS label FROM `tabAccount`
           WHERE company=%s AND is_group=0 AND disabled=0 AND root_type='Asset'
             AND (name LIKE '%%dvance%%' OR name LIKE '%%mploy%%' OR name=%s) ORDER BY name""",
        (target, default or ""), as_dict=True)
    modes = frappe.db.sql(
        """SELECT mop.name AS value, mop.name AS label, mopa.default_account AS account
           FROM `tabMode of Payment` mop LEFT JOIN `tabMode of Payment Account` mopa
             ON mopa.parent=mop.name AND mopa.company=%s
           WHERE mop.enabled=1 ORDER BY mop.name""", (target,), as_dict=True)
    return {"company": target, "currency": _ccy(target), "default_account": default,
            "accounts": accounts, "modes": modes}


@frappe.whitelist()
def list_employee_advances(company=None, limit=200):
    assert_portal_access()
    target = _target(company)
    if not target:
        return {"rows": []}
    rows = frappe.db.sql(
        """SELECT a.name, a.employee, e.employee_name nm, a.posting_date, a.purpose, a.advance_amount,
                  a.paid_amount, a.claimed_amount, a.return_amount, a.status, a.docstatus, a.advance_account
           FROM `tabEmployee Advance` a JOIN `tabEmployee` e ON e.name=a.employee
           WHERE a.company=%s AND a.docstatus<2 ORDER BY a.posting_date DESC, a.creation DESC LIMIT %s""",
        (target, int(limit or 200)), as_dict=True)
    for r in rows:
        r["posting_date"] = str(r["posting_date"])
        for k in ("advance_amount", "paid_amount", "claimed_amount", "return_amount"):
            r[k] = _m(r.get(k))
        r["open"] = _m(r["advance_amount"] - r["claimed_amount"] - r["return_amount"])
    return {"company": target, "currency": _ccy(target), "rows": rows,
            "open_total": _m(sum(r["open"] for r in rows if r["docstatus"] == 1)),
            "unpaid_total": _m(sum(r["advance_amount"] - r["paid_amount"] for r in rows if r["docstatus"] == 1))}


@frappe.whitelist()
def create_employee_advance(company=None, employee=None, amount=None, purpose=None, posting_date=None,
                            mode_of_payment=None, advance_account=None, repay_from_salary=0, notes=None):
    """Book an Employee Advance (submitted). Gated by amount like any payment;
    reversible by cancelling the voucher."""
    assert_can_write()
    target = _target(company)
    if not (target and employee and purpose):
        frappe.throw("employee and purpose are required")
    amt = _m(amount)
    if amt <= 0:
        frappe.throw("Amount must be greater than zero")
    if not frappe.db.exists("Employee", {"name": employee, "company": target}):
        frappe.throw("Employee not found in this company")
    from accounting_portal.api import _actions
    pd = str(getdate(posting_date or nowdate()))
    key = "empadv:" + _digest(f"{target}:{employee}:{amt}:{pd}:{purpose[:30]}", 14)
    return _actions.execute(
        ADV_ACTION, target, key,
        payload={"employee": employee, "amount": amt, "purpose": purpose, "posting_date": pd,
                 "mode_of_payment": mode_of_payment, "advance_account": advance_account,
                 "repay_from_salary": int(str(repay_from_salary) in ("1", "true", "True"))},
        amount=amt, notes=notes or f"Advance {amt} to {employee}")


def _adv_poster(doc):
    p = json.loads(doc.payload or "{}")
    a = frappe.get_doc({
        "doctype": "Employee Advance", "company": doc.company, "employee": p["employee"],
        "posting_date": p.get("posting_date") or nowdate(), "currency": _ccy(doc.company), "exchange_rate": 1,
        "purpose": p["purpose"], "advance_amount": flt(p["amount"]),
        "advance_account": p.get("advance_account") or frappe.db.get_value(
            "Company", doc.company, "default_employee_advance_account"),
        "mode_of_payment": p.get("mode_of_payment") or None,
        "repay_unclaimed_amount_from_salary": int(p.get("repay_from_salary") or 0),
    })
    a.insert(ignore_permissions=True)
    a.submit()
    return {"voucher_type": "Employee Advance", "voucher_no": a.name,
            "result": {"advance": a.name, "amount": flt(p["amount"])}}



# ── Salary structures (Desk trail: 13 created + 156 line edits in 6 months) ─────

SS_ACTION = "Save salary structure"
SS_ACTIVE_ACTION = "Toggle salary structure"


@frappe.whitelist()
def structure_options(company=None):
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    comps = frappe.db.sql("SELECT name AS value, CONCAT(name, ' (', type, ')') AS label, type FROM `tabSalary Component` "
                          "WHERE IFNULL(disabled,0)=0 ORDER BY type, name", as_dict=True)
    modes = [r[0] for r in frappe.db.sql("SELECT name FROM `tabMode of Payment` WHERE enabled=1 ORDER BY name")]
    banks = _bank_accounts(target) if "_bank_accounts" in globals() else []
    return {"company": target, "currency": _ccy(target), "components": comps, "modes": modes, "banks": banks,
            "frequencies": ["Monthly", "Fortnightly", "Bimonthly", "Weekly", "Daily"]}


@frappe.whitelist()
def list_salary_structures(company=None):
    assert_portal_access()
    target = _target(company)
    if not target:
        return {"rows": []}
    rows = frappe.db.sql(
        """SELECT s.name, s.currency, s.payroll_frequency, s.docstatus, s.is_active, s.modified,
                  (SELECT COUNT(*) FROM `tabSalary Structure Assignment` a WHERE a.salary_structure=s.name AND a.docstatus=1) assigned,
                  (SELECT SUM(d.amount) FROM `tabSalary Detail` d WHERE d.parent=s.name AND d.parentfield='earnings') earn,
                  (SELECT SUM(d.amount) FROM `tabSalary Detail` d WHERE d.parent=s.name AND d.parentfield='deductions') ded
           FROM `tabSalary Structure` s WHERE s.company=%s AND s.docstatus<2 ORDER BY s.is_active DESC, s.modified DESC""",
        (target,), as_dict=True)
    for r in rows:
        r["earn"], r["ded"] = _m(r.get("earn")), _m(r.get("ded"))
        r["modified"] = str(r["modified"])[:10]
    return {"company": target, "currency": _ccy(target), "rows": rows}


@frappe.whitelist()
def get_salary_structure(name=None):
    assert_portal_access()
    if not name or not frappe.db.exists("Salary Structure", name):
        frappe.throw("Structure not found")
    s = frappe.get_doc("Salary Structure", name)
    if s.company not in resolve_companies():
        frappe.throw("Not permitted", frappe.PermissionError)
    rows = lambda f: [{"salary_component": d.salary_component, "amount": _m(d.amount),  # noqa: E731
                       "formula": d.formula or "", "amount_based_on_formula": int(d.amount_based_on_formula or 0)}
                      for d in s.get(f) or []]
    return {"name": s.name, "company": s.company, "currency": s.currency, "payroll_frequency": s.payroll_frequency,
            "docstatus": s.docstatus, "is_active": s.is_active, "mode_of_payment": s.mode_of_payment,
            "payment_account": s.payment_account, "earnings": rows("earnings"), "deductions": rows("deductions")}


def _ss_poster(doc):
    p = json.loads(doc.payload or "{}")
    if p.get("name") and frappe.db.exists("Salary Structure", p["name"]):
        s = frappe.get_doc("Salary Structure", p["name"])
        if s.docstatus != 0:
            frappe.throw("Only a draft structure can be edited — create a new one and re-assign")
        s.set("earnings", []); s.set("deductions", [])
    else:
        s = frappe.new_doc("Salary Structure")
        s.name = p["structure_name"]
        s.company = doc.company
    s.currency = p.get("currency") or _ccy(doc.company)
    s.payroll_frequency = p.get("payroll_frequency") or "Monthly"
    s.is_active = "Yes"
    s.mode_of_payment = p.get("mode_of_payment") or None
    s.payment_account = p.get("payment_account") or None
    for f in ("earnings", "deductions"):
        for r in p.get(f) or []:
            if not r.get("salary_component"):
                continue
            s.append(f, {"salary_component": r["salary_component"], "amount": flt(r.get("amount")),
                         "amount_based_on_formula": 1 if r.get("formula") else 0, "formula": r.get("formula") or None})
    s.flags.ignore_permissions = True
    s.save()
    if int(p.get("submit") or 0):
        s.submit()
    return {"voucher_type": "Salary Structure", "voucher_no": s.name,
            "result": {"structure": s.name, "docstatus": s.docstatus}}


def _ss_active_poster(doc):
    p = json.loads(doc.payload or "{}")
    frappe.db.set_value("Salary Structure", p["name"], "is_active", "Yes" if p["active"] else "No")
    return {"voucher_type": "Salary Structure", "voucher_no": p["name"], "result": {"is_active": p["active"]}}


@frappe.whitelist()
def save_salary_structure(company=None, name=None, structure_name=None, currency=None, payroll_frequency=None,
                          earnings=None, deductions=None, mode_of_payment=None, payment_account=None, submit=0):
    """Create (or edit a draft) salary structure: fixed-amount earnings/deductions.
    Submitted structures are immutable in ERPNext — make a new one and re-assign."""
    assert_can_write()
    target = _target(company)
    if not target:
        frappe.throw("No company in scope")
    earnings = earnings if isinstance(earnings, list) else json.loads(earnings or "[]")
    deductions = deductions if isinstance(deductions, list) else json.loads(deductions or "[]")
    structure_name = (structure_name or "").strip()
    if not name and not structure_name:
        frappe.throw("Structure name is required")
    if not name and frappe.db.exists("Salary Structure", structure_name):
        frappe.throw(f"A structure named '{structure_name}' already exists")
    if not any(r.get("salary_component") for r in earnings):
        frappe.throw("At least one earning component is required")
    from accounting_portal.api import _actions
    key = "ss:" + _digest(f"{target}:{name or structure_name}:{str(frappe.utils.now_datetime())[:19]}", 14)
    return _actions.execute(SS_ACTION, target, key,
                            payload={"name": name, "structure_name": structure_name, "currency": currency,
                                     "payroll_frequency": payroll_frequency, "earnings": earnings, "deductions": deductions,
                                     "mode_of_payment": mode_of_payment, "payment_account": payment_account,
                                     "submit": int(str(submit) in ("1", "true", "True"))},
                            amount=0, notes=f"{'Edit' if name else 'Create'} salary structure {name or structure_name}")


@frappe.whitelist()
def set_structure_active(company=None, name=None, active=None):
    assert_can_write()
    target = _target(company)
    if not (name and frappe.db.exists("Salary Structure", {"name": name, "company": target})):
        frappe.throw("Structure not found")
    flag = 1 if str(active) in ("1", "true", "True", "Yes") else 0
    from accounting_portal.api import _actions
    return _actions.execute(SS_ACTIVE_ACTION, target, f"ss-active:{name}:{flag}:{str(frappe.utils.now_datetime())[:19]}",
                            payload={"name": name, "active": flag}, amount=0,
                            notes=f"{'Activate' if flag else 'Deactivate'} salary structure {name}")


# Generate/pay register via the shared cancel-voucher undo where applicable.
def _register():
    from accounting_portal.api import _actions
    _actions.register_poster(CLOSE_ACTION, _close_month_poster)
    _actions.register_reverter(CLOSE_ACTION, _close_month_reverter)
    _actions._NO_GATE.add(CLOSE_ACTION)
    _actions.register_poster(RUN_ACTION, _run_poster)
    _actions.register_reverter(RUN_ACTION, _run_reverter)
    _actions._NO_GATE.add(RUN_ACTION)  # creates drafts only (no GL) → no approval gate
    _actions.register_poster(SUBMIT_SLIPS_ACTION, _submit_poster)
    _actions.register_reverter(SUBMIT_SLIPS_ACTION, _submit_reverter)
    _actions.register_poster(PAY_ACTION, _pay_poster)
    _actions.register_reverter(PAY_ACTION, _actions._cancel_voucher_reverter)
    _actions.register_poster(ASSIGN_ACTION, _assign_poster)
    _actions.register_reverter(ASSIGN_ACTION, _actions._cancel_voucher_reverter)
    _actions._NO_GATE.add(ASSIGN_ACTION)  # HR master data — no GL, no approval gate
    _actions.register_poster(ADJ_ACTION, _adj_poster)
    _actions.register_reverter(ADJ_ACTION, _actions._cancel_voucher_reverter)
    _actions._NO_GATE.add(ADJ_ACTION)  # pre-slip input — no GL until the slip posts
    _actions.register_poster(ADJ_EDIT_ACTION, _adj_edit_poster)
    _actions.register_reverter(ADJ_EDIT_ACTION, _actions._cancel_voucher_reverter)
    _actions._NO_GATE.add(ADJ_EDIT_ACTION)
    _actions.register_poster(EMP_UPDATE_ACTION, _update_emp_poster)
    _actions.register_reverter(EMP_UPDATE_ACTION, _update_emp_reverter)
    _actions._NO_GATE.add(EMP_UPDATE_ACTION)
    _actions.register_poster(EMP_CREATE_ACTION, _create_emp_poster)
    _actions.register_reverter(EMP_CREATE_ACTION, _create_emp_reverter)
    _actions._NO_GATE.add(EMP_CREATE_ACTION)
    _actions.register_poster(ADV_ACTION, _adv_poster)
    _actions.register_reverter(ADV_ACTION, _actions._cancel_voucher_reverter)
    _actions.register_poster(SS_ACTION, _ss_poster)
    _actions._NO_GATE.add(SS_ACTION)
    _actions.register_poster(SS_ACTIVE_ACTION, _ss_active_poster)
    _actions._NO_GATE.add(SS_ACTIVE_ACTION)


_register()


# ── The monthly payroll sheet ─────────────────────────────────────────────────
#
# The team's real payroll model lives in a Google Sheet ("EXTRA 2026") and is
# hour-based, not month-based:
#
#     rate      = base / contract hours (208)
#     hours     = contract + public holidays + overtime x rate − missing − delay
#     gross     = hours x rate
#     net       = gross + bonus + commission − advance
#
# Verified against their own numbers: 10,000/208 = 48.0769/h, and
# (208 − 4 missing − 0.95 delay) x 48.0769 = 9,762 — the figure in their January
# sheet to the dirham. August's submitted ERPNext slips match the sheet on every
# line, because the sheet is calculated and then the result is typed in by hand.
#
# This endpoint computes that model from the data we already hold, so the
# calculation happens once instead of twice. It writes nothing to ERPNext: this
# is the reference sheet, and `payroll_sheet_save` only stores the few figures
# that have no system source yet (delay, overtime, manual corrections).

SHEET_KEY = "ap_payroll_sheet"
DEFAULT_CONTRACT_HOURS = 208.0      # 48h/week x 52 / 12, the sheet's own basis
HOURS_PER_DAY = 8.0
OVERTIME_RATE = 1.5
DEFAULT_GRACE_MINUTES = 15.0
# Employee ids are HR-EMP-*, so a settings row keyed like this cannot collide
# with a person inside the same override store.
SHEET_SETTINGS_KEY = "__sheet"
SHEET_APPROVED_KEY = "__approved"

# The four components approving a month writes, and the only ones the sheet owns.
#
# Not invented: these are what this company's own submitted slips already use —
# 220 absence deductions, 121 overtime lines, 107 holiday lines, 26 advance
# deductions — because the team already keys the sheet's result in by hand as
# Additional Salary on top of a full `Net Wage of Employee` from the structure.
# Approving the month does exactly what they do, from figures already computed.
#
# `Due to Late Entry or Absence Encashment` deliberately, NOT the `... MAD`
# variant: the MAD one carries no Salary Component Account for this company, so
# a slip built on it fails at submission. The unsuffixed one maps to
# 720.001.007.010 MAD and is the one every existing slip used.
SHEET_HOLIDAY_COMPONENT = "National Holiday  & Public Holiday Pay - Ulusal Bayram & Genel Tatil"
SHEET_OVERTIME_COMPONENT = "Overtime - Fazla Mesai 50%"
SHEET_ABSENCE_COMPONENT = "Due to Late Entry or Absence Encashment"
SHEET_ADVANCE_COMPONENT = "Advance Deduction - Avans Kesintisi"


def _sheet_store(target, month):
    return f"{SHEET_KEY}_{frappe.scrub(target)}_{month}"


def _sheet_overrides(target, month):
    try:
        return frappe.parse_json(frappe.db.get_default(_sheet_store(target, month)) or "{}") or {}
    except Exception:
        return {}


def _sheet_approved(target, month, ov=None):
    """What a previous approval of this month wrote, if any."""
    if ov is None:
        ov = _sheet_overrides(target, month)
    return ov.get(SHEET_APPROVED_KEY) or {}


def _deducted_advances(target, before_month):
    """What earlier approved months already took off an advance, per employee.

    The advance column is an outstanding balance on `Employee Advance`, and
    deducting it through an Additional Salary does not touch that document — no
    claim, no return, nothing. So the balance survives the deduction and the next
    month would present it again, and the month after that: a 5,000 advance
    collected once and deducted for as long as the person is employed.

    Until an approval also settles the advance itself, this is what keeps the
    figure honest — each approved month records what it deducted, and later
    months net it off. Only months strictly BEFORE this one count, so
    re-approving a month never subtracts its own deduction from itself.
    """
    out = {}
    prefix = _sheet_store(target, "")
    for k, v in frappe.db.sql(
            """SELECT defkey, defvalue FROM `tabDefaultValue` WHERE defkey LIKE %s""",
            (prefix + "%",)):
        # `_` is a single-character wildcard in LIKE and these keys are made of
        # them, so the prefix is re-checked here rather than trusted to the query.
        k = str(k)
        if not k.startswith(prefix):
            continue
        m = k.rsplit("_", 1)[-1]
        if not (len(m) == 7 and m < str(before_month)):
            continue
        try:
            stamp = (frappe.parse_json(v or "{}") or {}).get(SHEET_APPROVED_KEY) or {}
        except Exception:
            continue
        for emp, amt in (stamp.get("advances") or {}).items():
            out[emp] = flt(out.get(emp) or 0) + flt(amt)
    return out


def _sheet_settings(target, month, ov=None):
    """The reference the delay column is measured against.

    Deliberately NOT the Shift Type. `Morocco Office` starts at 09:30 with
    `enable_late_entry_marking = 0` and a zero grace period, so ERPNext never
    computed lateness at all — while the arrival mode this month is 11:00 and
    the spreadsheet's whole-month delay for the same people is under an hour.
    Measuring from 09:30 would invent roughly thirty hours a month per person.

    So the start of the day is a figure the person doing the payroll sets and
    can see on screen, and the suggestion converges on their own numbers
    instead of on a Shift Type nobody maintains.
    """
    if ov is None:
        ov = _sheet_overrides(target, month)
    s = ov.get(SHEET_SETTINGS_KEY) or {}
    g = s.get("grace_minutes")
    return {
        "day_start": s.get("day_start") or "",
        "grace_minutes": flt(DEFAULT_GRACE_MINUTES if g in (None, "") else g),
    }


def _auto_delay(target, start, end, day_start="", grace=DEFAULT_GRACE_MINUTES):
    """Late arrival per employee, in hours, from the punch times we hold.

    Only a row that carries a punch counts: `in_time` is set on 302 of this
    month's 590 attendance rows, and a row without one says nothing about when
    the person arrived. Arriving early is zero, never a credit — GREATEST(...,0)
    is what stops an early bird from cancelling someone else's lateness.

    With no reference start set there is NO suggestion. Falling back to the
    shift was measured on this month: 284 hours of "lateness" across 15 people,
    topping out at 31.7 for one of them, against a whole-month figure under an
    hour in the spreadsheet. A number that wrong offered as a suggestion is
    worse than an empty column, so the column stays empty until someone says
    when the day starts.
    """
    if not day_start:
        return {}
    rows = frappe.db.sql(
        """SELECT a.employee, SUM(GREATEST(
                      TIME_TO_SEC(TIME(a.in_time))
                    - TIME_TO_SEC(%(ds)s)
                    - %(g)s * 60, 0)) / 3600 AS late
           FROM `tabAttendance` a
           WHERE a.company=%(c)s AND a.docstatus=1 AND a.in_time IS NOT NULL
             AND a.status IN ('Present', 'Half Day')
             AND a.attendance_date BETWEEN %(s)s AND %(e)s
           GROUP BY a.employee""",
        {"c": target, "s": start, "e": end,
         "ds": day_start, "g": flt(grace)}, as_dict=True)
    return {r.employee: flt(r.late, 2) for r in rows}


def _holiday_hours(holiday_list, start, end):
    """Paid public holidays in the month, in hours.

    `weekly_off` is the field that separates a rest day from a public holiday —
    on this site the Morocco list carries every Sunday with weekly_off = 1 and
    real holidays with 0. Counting the whole list would pay four extra Sundays.
    """
    if not holiday_list:
        return 0.0
    n = frappe.db.sql(
        """SELECT COUNT(*) FROM `tabHoliday`
           WHERE parent=%s AND holiday_date BETWEEN %s AND %s AND IFNULL(weekly_off,0)=0""",
        (holiday_list, start, end))[0][0]
    return flt(n) * HOURS_PER_DAY


def _base_salary(ssa_base, structure):
    """`SSA.base` is 0 for most people here; the monthly salary sits in the
    structure's own `Net Wage of Employee` earning. Prefer the assignment when
    it carries a figure, fall back to the structure."""
    if flt(ssa_base) > 0:
        return flt(ssa_base)
    amt = frappe.db.get_value("Salary Detail",
                              {"parent": structure, "parentfield": "earnings",
                               "salary_component": "Net Wage of Employee"}, "amount")
    return flt(amt)


@frappe.whitelist()
def payroll_sheet(company=None, month=None, start=0, page_size=None):
    """The month's payroll sheet — one row per employee, the sheet's own columns.

    `start` / `page_size` exist so the generic Excel exporter can call this like
    any other list; the sheet is one screen of people and is never paged.
    """
    assert_portal_access()
    target = _target(company)
    if not (target and month):
        return {}
    start, end = _month_bounds(month)
    ov = _sheet_overrides(target, month)

    emps = frappe.db.sql(
        """SELECT e.name, e.employee_name nm, e.designation, e.department,
                  e.holiday_list, e.status, e.relieving_date, e.date_of_joining,
                  e.employment_type, e.bank_name, e.bank_ac_no, e.iban,
                  ssa.base, ssa.salary_structure
           FROM `tabEmployee` e
           JOIN `tabSalary Structure Assignment` ssa
             ON ssa.employee = e.name AND ssa.docstatus = 1
            AND ssa.from_date = (SELECT MAX(s2.from_date) FROM `tabSalary Structure Assignment` s2
                                 WHERE s2.employee = e.name AND s2.docstatus = 1 AND s2.from_date <= %(end)s)
           WHERE e.company = %(c)s AND e.status = 'Active'
           ORDER BY e.employee_name""", {"c": target, "end": end}, as_dict=True)

    # Absences, in hours, already split from the noise. A day nobody recorded is
    # NOT an absence — see the attendance review: 69% of what the device calls
    # absence is a rest day, someone who has left, or someone with no device.
    att = {r.employee: r for r in frappe.db.sql(
        """SELECT a.employee,
                  SUM(CASE WHEN a.status='Absent' THEN 1 ELSE 0 END) absent_days,
                  SUM(CASE WHEN a.status='Half Day' THEN 1 ELSE 0 END) half_days,
                  SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END) present_days
           FROM `tabAttendance` a
           WHERE a.company=%(c)s AND a.docstatus=1
             AND a.attendance_date BETWEEN %(s)s AND %(e)s
           GROUP BY a.employee""", {"c": target, "s": start, "e": end}, as_dict=True)}
    punched = {r[0] for r in frappe.db.sql(
        """SELECT DISTINCT employee FROM `tabEmployee Checkin`
           WHERE time BETWEEN %s AND %s""", (start, end + " 23:59:59"))}
    cfg = _sheet_settings(target, month, ov)
    late = _auto_delay(target, start, end, cfg["day_start"], cfg["grace_minutes"])

    # Outstanding advance, floored at zero PER ADVANCE. Summing the raw
    # difference gave −1,000 on this company, because an advance that was
    # claimed or returned for more than it paid goes negative — and a negative
    # deduction quietly ADDS to net pay. An over-settled advance is a zero to
    # deduct, not a bonus.
    adv = {}
    for r in frappe.db.sql(
        """SELECT employee, IFNULL(paid_amount,0) - IFNULL(claimed_amount,0)
                          - IFNULL(return_amount,0) AS bal
           FROM `tabEmployee Advance` WHERE company=%s AND docstatus=1""",
            (target,), as_dict=True):
        adv[r.employee] = flt(adv.get(r.employee) or 0) + max(flt(r.bal), 0.0)
    # …less whatever earlier approved months already deducted against it.
    for emp, done in _deducted_advances(target, month).items():
        if emp in adv:
            adv[emp] = max(flt(adv[emp]) - flt(done), 0.0)

    approved = _sheet_approved(target, month, ov)
    mine = [n for n in (approved.get("names") or []) if n]
    extra, args = {}, {"c": target, "s": start, "e": end}
    skip = ""
    if mine:
        skip = " AND a.name NOT IN %(skip)s"
        args["skip"] = tuple(mine)
    for r in frappe.db.sql(
        """SELECT a.employee, a.salary_component comp, c.type, SUM(a.amount) amt
           FROM `tabAdditional Salary` a
           JOIN `tabSalary Component` c ON c.name = a.salary_component
           WHERE a.company=%(c)s AND a.docstatus=1 AND """ + _ADDSAL_MONTH + skip + """
           GROUP BY a.employee, a.salary_component, c.type""",
            args, as_dict=True):
        slot = extra.setdefault(r.employee, {"bonus": 0.0, "deduct": 0.0})
        slot["bonus" if r.type == "Earning" else "deduct"] += flt(r.amt)

    rows, totals = [], {"gross": 0.0, "net": 0.0, "advance": 0.0,
                        "sent": 0, "sent_net": 0.0, "no_rib": 0}
    for e in emps:
        o = ov.get(e.name, {})
        base = _base_salary(e.base, e.salary_structure)
        hours = flt(o.get("contract_hours") or DEFAULT_CONTRACT_HOURS)
        rate = (base / hours) if hours else 0.0
        a = att.get(e.name) or frappe._dict({})
        tracked = e.name in punched
        # An employee with no punch at all this month is not absent — they are
        # untracked. Calling that absence is how the device's blind spot turns
        # into a pay cut.
        auto_missing = ((flt(a.absent_days) * HOURS_PER_DAY)
                        + (flt(a.half_days) * HOURS_PER_DAY / 2)) if tracked else 0.0
        # The attendance figure is a SUGGESTION, never the default. The review of
        # this data found 69% of recorded absence to be a rest day, someone who
        # had left, or someone with no device — and on this month it proposes 92
        # missing hours for one logistics agent and 88 for another. Defaulting to
        # it would halve real salaries on bad data. It is shown beside the field
        # and applied only when a person accepts it.
        missing = flt(o["missing_hours"]) if "missing_hours" in o else 0.0
        # Delay is offered on the same terms as absence: computed from real
        # punches, shown beside the field, applied only when someone accepts it.
        auto_delay = flt(late.get(e.name) or 0)
        delay = flt(o.get("delay_hours") or 0)
        over = flt(o.get("overtime_hours") or 0)
        hol = flt(o["holiday_hours"]) if "holiday_hours" in o else _holiday_hours(e.holiday_list, start, end)
        x = extra.get(e.name) or {}
        bonus = flt(o["bonus"]) if "bonus" in o else flt(x.get("bonus") or 0)
        advance = flt(o["advance"]) if "advance" in o else flt(adv.get(e.name) or 0)

        total_hours = hours + hol + (over * OVERTIME_RATE) - missing - delay
        gross = _m(max(total_hours, 0) * rate)
        net = _m(gross + bonus - advance - flt(x.get("deduct") or 0))
        rows.append({
            "employee": e.name, "employee_name": e.nm,
            "designation": e.designation, "department": e.department,
            "base": _m(base), "rate": flt(rate, 4), "contract_hours": hours,
            "holiday_hours": hol, "overtime_hours": over, "missing_hours": missing,
            "delay_hours": delay, "total_hours": flt(max(total_hours, 0), 2),
            "gross": gross, "bonus": _m(bonus), "advance": _m(advance),
            "other_deduction": _m(x.get("deduct") or 0), "net": net,
            "tracked": tracked, "present_days": int(a.present_days or 0),
            "auto_missing_hours": auto_missing, "auto_delay_hours": auto_delay,
            # ERPNext holds Full-time / Part-time here, not the CDI / CDD the
            # spreadsheet tracks, and every contract end date on this company is
            # empty — so the column shows what the master says and takes a typed
            # value over it rather than guessing a contract type from nothing.
            "contract": (o.get("contract") or e.employment_type or ""),
            "employment_type": e.employment_type or "",
            "rib": (e.bank_ac_no or e.iban or ""), "bank_name": e.bank_name or "",
            # "Send" in the spreadsheet is the only record that a salary actually
            # left the bank. It is a state, so it carries who ticked it and when.
            "sent": 1 if o.get("sent") else 0, "sent_on": o.get("sent_on") or "",
            "sent_by": o.get("sent_by") or "",
            "edited": sorted(k for k in o.keys()
                             if k not in ("sent", "sent_on", "sent_by")),
            "note": o.get("note") or "",
        })
        totals["gross"] += gross; totals["net"] += net; totals["advance"] += _m(advance)
        if o.get("sent"):
            totals["sent"] += 1
            totals["sent_net"] += net
        if not (e.bank_ac_no or e.iban):
            totals["no_rib"] += 1

    slips = {r.employee: r for r in frappe.db.sql(
        """SELECT employee, name, docstatus, ROUND(net_pay,2) net FROM `tabSalary Slip`
           WHERE company=%s AND docstatus<2 AND start_date=%s""", (target, start), as_dict=True)}
    for r in rows:
        s = slips.get(r["employee"])
        r["slip"] = s.name if s else None
        r["slip_net"] = flt(s.net) if s else None
        r["slip_docstatus"] = s.docstatus if s else None
        # The number the portal computes and the number already posted should be
        # the same. While they are not, that gap is the whole point of the sheet.
        r["gap"] = _m((flt(s.net) - r["net"])) if s else None

    return {"company": target, "month": month, "currency": _ccy(target),
            "contract_hours": DEFAULT_CONTRACT_HOURS, "overtime_rate": OVERTIME_RATE,
            "rows": rows, "count": len(rows), "total": len(rows),
            "total_gross": _m(totals["gross"]), "total_net": _m(totals["net"]),
            "total_advance": _m(totals["advance"]),
            "sent_count": totals["sent"], "sent_net": _m(totals["sent_net"]),
            "approved": approved or None,
            "no_rib_count": totals["no_rib"],
            "day_start": cfg["day_start"], "grace_minutes": cfg["grace_minutes"],
            "posted_slips": len(slips)}


@frappe.whitelist()
def payroll_sheet_save(company=None, month=None, employee=None, values=None):
    """Store the figures the systems cannot supply — delay, overtime, and any
    correction to what attendance produced. Kept in the portal, not written to
    ERPNext: nothing here posts until the month is approved."""
    assert_can_write()
    target = _target(company)
    if not (target and month and employee):
        frappe.throw("company, month and employee are required")
    vals = values if isinstance(values, dict) else frappe.parse_json(values or "{}")
    numeric = ("contract_hours", "holiday_hours", "overtime_hours", "missing_hours",
               "delay_hours", "bonus", "advance")
    text = ("note", "contract")
    ov = _sheet_overrides(target, month)
    row = ov.get(employee, {})
    for k in numeric + text:
        if k not in vals:
            continue
        v = vals[k]
        # An empty value clears the override and hands the field back to the
        # system that derives it, rather than pinning it at zero forever.
        if v in (None, ""):
            row.pop(k, None)
        else:
            row[k] = (str(v)[:200] if k in text else flt(v))
    # Marking a salary as sent is a claim about money leaving the bank, so it
    # records who made it. Un-ticking clears the stamp with it — a stale name
    # against a box nobody has ticked reads as evidence and is not.
    if "sent" in vals:
        if cint(vals.get("sent")):
            row["sent"] = 1
            row["sent_on"] = now_datetime().strftime("%Y-%m-%d %H:%M")
            row["sent_by"] = frappe.session.user
        else:
            for k in ("sent", "sent_on", "sent_by"):
                row.pop(k, None)
    if row:
        ov[employee] = row
    else:
        ov.pop(employee, None)
    frappe.db.set_default(_sheet_store(target, month), json.dumps(ov))
    frappe.db.commit()
    return {"saved": employee, "overrides": row}


@frappe.whitelist()
def payroll_sheet_settings(company=None, month=None, values=None):
    """The month's reference start time and grace period for the delay column.

    Stored beside the per-employee overrides and per month, because the office
    day can move and last month's sheet must keep producing last month's
    numbers.
    """
    assert_can_write()
    target = _target(company)
    if not (target and month):
        frappe.throw("company and month are required")
    vals = values if isinstance(values, dict) else frappe.parse_json(values or "{}")
    ov = _sheet_overrides(target, month)
    cur = ov.get(SHEET_SETTINGS_KEY) or {}
    if "day_start" in vals:
        v = (vals.get("day_start") or "").strip()
        # HH:MM only — anything else would land in the SQL as a silent NULL and
        # quietly fall back to the shift, which is the number we are avoiding.
        if v and not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", v):
            frappe.throw("Start time must look like 09:30")
        cur["day_start"] = v
    if "grace_minutes" in vals:
        cur["grace_minutes"] = max(flt(vals.get("grace_minutes")), 0.0)
    ov[SHEET_SETTINGS_KEY] = cur
    frappe.db.set_default(_sheet_store(target, month), json.dumps(ov))
    frappe.db.commit()
    return _sheet_settings(target, month)


@frappe.whitelist()
def payroll_sheet_bank(company=None, employee=None, rib=None, bank_name=None):
    """Store an employee's bank account, the one column the sheet cannot derive.

    Not one of the 27 active people on this company carries a `bank_ac_no`, an
    IBAN or a bank name — the account numbers live only in the spreadsheet's RIB
    tab, which is why payroll cannot leave it. This writes them onto the
    employee record where the rest of the system can reach them.

    `db.set_value` rather than a document save: an Employee here can fail
    validation on unrelated stale fields (a missing relieving date), and a bank
    number must not be hostage to that. The comment is the audit trail.
    """
    assert_can_write()
    target = _target(company)
    emp = frappe.db.get_value("Employee", employee,
                              ["name", "company", "employee_name", "bank_ac_no"], as_dict=True)
    if not emp:
        frappe.throw("Employee not found")
    if emp.company != target:
        frappe.throw("That employee is not on %s" % target)
    new = (rib or "").strip()[:60]
    frappe.db.set_value("Employee", emp.name, {
        "bank_ac_no": new,
        **({"bank_name": (bank_name or "").strip()[:80]} if bank_name is not None else {}),
    }, update_modified=True)
    frappe.get_doc({
        "doctype": "Comment", "comment_type": "Info",
        "reference_doctype": "Employee", "reference_name": emp.name,
        "content": "Bank account set from the payroll sheet: %s" % (new or "(cleared)"),
    }).insert(ignore_permissions=True)
    frappe.db.commit()
    return {"employee": emp.name, "rib": new}


# ── Approve the month (write the sheet's figures into ERPNext) ─────────────────
#
# Up to here the sheet computed and posted nothing. This is the crossing.
#
# What it writes is deliberately NOT a salary slip. The structure already holds
# each person's month at full value and the slips prove it: August's are all
# 21/21 payment days with `Net Wage of Employee` untouched and every variable
# piece hanging off an Additional Salary. That is the team's own convention,
# arrived at by hand, and it is the right one — the base stays auditable against
# the contract and the month's movement stays a document you can read, cancel and
# re-post one line at a time.
#
# So approving a month writes four Additional Salary rows per person, on the four
# components their slips already use, and the slip that follows lands on the
# sheet's net by construction:
#
#     base (structure)  +  holiday x rate  +  overtime x 1.5 x rate
#                       −  (missing + delay) x rate  −  advance
#
# Bonuses are the one thing it refuses to write. The sheet's bonus column reads
# whatever Additional Salary already exists for the month, so writing it back
# would pay it twice; and a bonus typed into a reference sheet has no component
# and no account behind it. If that column was overridden, approval stops and
# says which people to fix in Adjustments, where a bonus becomes a real document.

APPROVE_ACTION = "Approve payroll sheet"


def _approve_lines(target, month):
    """Every Additional Salary approving this month would create, plus anything
    that should stop it. Read-only, and the single source for both the preview
    and the poster — a preview that computes its numbers differently from the
    thing it previews is not a preview."""
    d = payroll_sheet(company=target, month=month) or {}
    rows = d.get("rows") or []
    start, _end = _month_bounds(month)
    lines, blocks, warns = [], [], []

    posted = frappe.db.sql(
        """SELECT COUNT(*) n, SUM(net_pay) net FROM `tabSalary Slip`
           WHERE company=%s AND start_date=%s AND docstatus=1""", (target, start), as_dict=True)[0]
    if posted.n:
        blocks.append(f"{month} already has {int(posted.n)} submitted slips "
                      f"({_m(posted.net)} {d.get('currency')}). Approve before the run, not after — "
                      "revert the submission first if those slips are wrong.")

    for comp in (SHEET_HOLIDAY_COMPONENT, SHEET_OVERTIME_COMPONENT,
                 SHEET_ABSENCE_COMPONENT, SHEET_ADVANCE_COMPONENT):
        if not frappe.db.exists("Salary Component", comp):
            blocks.append(f"Salary component missing: {comp}")
        elif not frappe.db.get_value("Salary Component Account",
                                     {"parent": comp, "company": target}, "account"):
            # Caught in review: the `... MAD` variant of the absence component has
            # no account on this company, and a slip built on it fails only at
            # submission — long after anyone would connect it to this screen.
            blocks.append(f"{comp} has no account for {target} — the slip would fail at submission.")

    edited_bonus = [r["employee_name"] for r in rows if "bonus" in (r.get("edited") or [])]
    if edited_bonus:
        blocks.append("Bonus was typed into the sheet for " + ", ".join(edited_bonus[:5])
                      + ("…" if len(edited_bonus) > 5 else "")
                      + ". A bonus needs a component and an account: put it in Adjustments and it "
                        "flows into the slip on its own.")

    for r in rows:
        rate = flt(r["rate"])
        per = []
        hol = _m(flt(r["holiday_hours"]) * rate)
        ot = _m(flt(r["overtime_hours"]) * OVERTIME_RATE * rate)
        # One component, because the company has one: it is literally named
        # "Due to Late Entry OR Absence". The hours stay split on the sheet.
        cut = _m((flt(r["missing_hours"]) + flt(r["delay_hours"])) * rate)
        adv = _m(r["advance"])
        if hol:
            per.append({"component": SHEET_HOLIDAY_COMPONENT, "type": "Earning", "amount": hol,
                        "basis": f"{r['holiday_hours']}h x {flt(rate, 2)}"})
        if ot:
            per.append({"component": SHEET_OVERTIME_COMPONENT, "type": "Earning", "amount": ot,
                        "basis": f"{r['overtime_hours']}h x {OVERTIME_RATE} x {flt(rate, 2)}"})
        if cut:
            per.append({"component": SHEET_ABSENCE_COMPONENT, "type": "Deduction", "amount": cut,
                        "basis": f"({r['missing_hours']} + {r['delay_hours']})h x {flt(rate, 2)}"})
        if adv:
            per.append({"component": SHEET_ADVANCE_COMPONENT, "type": "Deduction", "amount": adv,
                        "basis": "outstanding advance"})
        if per:
            lines.append({"employee": r["employee"], "employee_name": r["employee_name"],
                          "base": r["base"], "net": r["net"], "items": per})

    # Not a blocker — a month where nobody was absent is a real month. But a month
    # where the device recorded absence and the sheet still says none is usually a
    # sheet nobody has filled in yet, and that is worth seeing before it posts.
    suggested = sum(flt(r.get("auto_missing_hours")) for r in rows)
    if suggested and not any(flt(r["missing_hours"]) for r in rows):
        warns.append(f"The sheet deducts nothing for absence, while attendance suggests "
                     f"{flt(suggested, 1)} hours across the month. Review the Missing column first.")
    if not any(flt(r["delay_hours"]) for r in rows) and not d.get("day_start"):
        warns.append("No start of day is set, so the delay column is empty and nothing is "
                     "deducted for lateness.")
    if not lines and not blocks:
        blocks.append(f"Nothing to write for {month}: no holiday, overtime, absence, delay or "
                      "advance on any row. The structure already pays the full month.")

    earn = sum(i["amount"] for l in lines for i in l["items"] if i["type"] == "Earning")
    ded = sum(i["amount"] for l in lines for i in l["items"] if i["type"] == "Deduction")
    return {
        "company": target, "month": month, "currency": d.get("currency"),
        "lines": lines, "employees": len(lines),
        "rows": len(rows), "documents": sum(len(l["items"]) for l in lines),
        "earn_total": _m(earn), "ded_total": _m(ded),
        "sheet_gross": d.get("total_gross"), "sheet_net": d.get("total_net"),
        "blocks": blocks, "warnings": warns,
        "approved": _sheet_approved(target, month) or None,
    }


@frappe.whitelist()
def payroll_sheet_approve_preview(company=None, month=None):
    assert_portal_access()
    target = _target(company)
    if not (target and month):
        return {}
    return _approve_lines(target, month)


@frappe.whitelist()
def payroll_sheet_approve(company=None, month=None, notes=None):
    assert_can_write()
    target = _target(company)
    if not (target and month):
        frappe.throw("company and month are required")
    plan = _approve_lines(target, month)
    if plan["blocks"]:
        frappe.throw("<br>".join(plan["blocks"]))
    from accounting_portal.api import _actions
    # The figures go into the key, so correcting the sheet and approving again is
    # a new action rather than a silent no-op on the old one — and re-clicking the
    # same numbers stays idempotent.
    fig = ";".join(f"{l['employee']}:{i['component']}:{i['amount']}"
                   for l in plan["lines"] for i in l["items"])
    key = "payroll-approve:" + _digest(f"{target}:{month}:{fig}", 16)
    return _actions.execute(
        APPROVE_ACTION, target, key, payload={"month": month},
        amount=_m(plan["earn_total"] - plan["ded_total"]),
        notes=notes or f"Approve payroll sheet {month}: {plan['documents']} adjustments "
                       f"for {plan['employees']} employees")


def _approve_poster(doc):
    p = json.loads(doc.payload or "{}")
    target, month = doc.company, p["month"]
    plan = _approve_lines(target, month)
    if plan["blocks"]:
        frappe.throw("<br>".join(plan["blocks"]))

    ov = _sheet_overrides(target, month)
    prev = (ov.get(SHEET_APPROVED_KEY) or {}).get("names") or []
    # Re-approving replaces the previous approval's rows rather than adding to
    # them. Only the rows THIS screen created are touched — a bonus someone keyed
    # by hand for the same month survives, because it was never ours.
    removed = []
    for n in prev:
        if not frappe.db.exists("Additional Salary", n):
            continue
        a = frappe.get_doc("Additional Salary", n)
        if a.docstatus == 1:
            _as_privileged(a).cancel()
        frappe.delete_doc("Additional Salary", n, force=1, ignore_permissions=True)
        removed.append(n)

    created, pay_date = [], _month_end(month)
    for l in plan["lines"]:
        for i in l["items"]:
            a = frappe.get_doc({
                "doctype": "Additional Salary", "company": target, "employee": l["employee"],
                "salary_component": i["component"], "type": i["type"],
                "amount": flt(i["amount"]), "currency": _ccy(target),
                "payroll_date": pay_date, "overwrite_salary_structure_amount": 0,
            })
            a.insert(ignore_permissions=True)
            if a.meta.is_submittable:
                a.submit()
            created.append(a.name)

    ov[SHEET_APPROVED_KEY] = {
        "names": created, "month": month, "documents": len(created),
        # Recorded per employee so later months can net it off — see
        # `_deducted_advances`. An Employee Advance is not marked repaid by a
        # salary deduction, so this is the only record that it happened.
        "advances": {l["employee"]: i["amount"] for l in plan["lines"] for i in l["items"]
                     if i["component"] == SHEET_ADVANCE_COMPONENT},
        "employees": len(plan["lines"]), "at": now_datetime().strftime("%Y-%m-%d %H:%M"),
        "by": frappe.session.user, "net": _m(plan["sheet_net"]), "action": doc.name,
    }
    frappe.db.set_default(_sheet_store(target, month), json.dumps(ov))
    # The names deliberately stay OUT of the result: an action's `result` column
    # is truncated at 4,000 characters, and 27 people x 4 components is over a
    # hundred ids — a reverter reading a half-truncated list would undo half a
    # month and report success. The stamp in the sheet store is the record.
    return {"voucher_type": "Additional Salary", "voucher_no": created[0] if created else None,
            "result": {"month": month, "created": len(created), "replaced": len(removed),
                       "employees": len(plan["lines"]), "first": created[0] if created else None,
                       "last": created[-1] if created else None}}


def _approve_reverter(doc):
    """Undo an approval: cancel and delete exactly the rows it created, and clear
    the stamp so the sheet stops excluding them from its own bonus column."""
    target, month = doc.company, (json.loads(doc.payload or "{}") or {}).get("month")
    if not month:
        return {"noop": True}
    ov = _sheet_overrides(target, month)
    stamp = ov.get(SHEET_APPROVED_KEY) or {}
    if stamp.get("action") and stamp["action"] != doc.name:
        # A later approval already replaced these rows and owns the month now;
        # deleting its documents to undo an older action would be wrong.
        frappe.throw(f"{month} was approved again since ({stamp['action']}) — revert that one instead.")
    names = stamp.get("names") or []
    gone = []
    for n in names:
        if not frappe.db.exists("Additional Salary", n):
            continue
        a = frappe.get_doc("Additional Salary", n)
        if a.docstatus == 1:
            _as_privileged(a).cancel()
        frappe.delete_doc("Additional Salary", n, force=1, ignore_permissions=True)
        gone.append(n)
    ov.pop(SHEET_APPROVED_KEY, None)
    frappe.db.set_default(_sheet_store(target, month), json.dumps(ov))
    return {"removed": len(gone), "month": month}


def _register_sheet():
    from accounting_portal.api import _actions
    _actions.register_poster(APPROVE_ACTION, _approve_poster)
    _actions.register_reverter(APPROVE_ACTION, _approve_reverter)


_register_sheet()


# ── Excel round-trip ──────────────────────────────────────────────────────────
#
# Download the sheet, edit it where a spreadsheet is genuinely faster — pasting a
# month of absence hours out of the punch-device export, say — and upload it back.
#
# Only the columns the sheet does not derive are read. Rate, total hours, payment
# and net are recomputed on the way back in, so a stale formula in the workbook
# cannot become a salary. Rows are matched on the ID column the export now
# carries; matching on the name was never going to hold here, where the same
# person appears as "Hajar AOUAMER" in one system and "AOUAMER Hajar" in another.

_IMPORT_FIELDS = {
    "id": "__employee", "employee id": "__employee",
    # Their own workbook heads the name column "Team" and carries no id at all,
    # so it uploads too — matched on the name, with whatever misses reported.
    "employee": "employee_name", "team": "employee_name",
    "general hours": "contract_hours",
    "public holiday": "holiday_hours",
    "overtime (hour)": "overtime_hours",
    "overtime(hour)": "overtime_hours",
    "missing": "missing_hours",
    "missing day": "missing_hours",
    "delay (hour)": "delay_hours",
    "delay(hour)": "delay_hours",
    "performance": "bonus",
    "advance": "advance",
    "contract": "contract",
    "send": "sent",
    "rib": "__rib",
}
_IMPORT_NUMERIC = ("contract_hours", "holiday_hours", "overtime_hours",
                   "missing_hours", "delay_hours", "bonus", "advance")


def _import_bool(v):
    return 1 if str(v).strip().lower() in ("1", "true", "yes", "oui", "y", "x", "✓", "نعم") else 0


def _import_number(v):
    """A figure out of a spreadsheet the team keys in French locale.

    Their own workbook stores 48,07692308 and 9 762 — a comma decimal and a
    non-breaking space thousands separator. `flt` on that reads 48 and 9, which
    would land as a salary. Normalised here, once.
    """
    if v in (None, ""):
        return None
    if isinstance(v, (int, float)):
        return flt(v)
    t = str(v).replace(" ", "").replace(" ", "").strip()
    if not t:
        return None
    if "," in t and "." in t:
        t = t.replace(",", "") if t.rfind(".") > t.rfind(",") else t.replace(".", "").replace(",", ".")
    else:
        t = t.replace(",", ".")
    try:
        return flt(t)
    except Exception:
        return None


@frappe.whitelist()
def payroll_sheet_import(company=None, month=None, file_url=None, apply=0):
    """Read an edited payroll-sheet workbook. With apply=0 it only reports what
    would change — which is how it should be read before it is trusted."""
    if cint(apply):
        assert_can_write()
    else:
        assert_portal_access()
    target = _target(company)
    if not (target and month and file_url):
        frappe.throw("company, month and file_url are required")
    from accounting_portal.api.bank_import import _file_bytes, _rows_from_excel, _rows_from_csv

    ext = (file_url or "").rsplit(".", 1)[-1].lower()
    content = _file_bytes(file_url)
    if ext in ("xlsx", "xlsm"):
        raw = _rows_from_excel(content)
    elif ext == "csv":
        raw = _rows_from_csv(content)
    else:
        frappe.throw("Upload an .xlsx or .csv file")

    head_at, cols = None, {}
    for idx, row in enumerate(raw[:20]):
        found = {}
        for ci, cell in enumerate(row):
            f = _IMPORT_FIELDS.get(str(cell or "").strip().lower())
            if f and f not in found:
                found[f] = ci
        # A header row is the one carrying the columns that matter, not merely the
        # first row with text in it — their workbook has a title band above it.
        if len(found) >= 3:
            head_at, cols = idx, found
            break
    if head_at is None:
        frappe.throw("No payroll-sheet header found. Download the sheet, edit it and upload that file — "
                     "the header needs at least the ID, Missing and Delay columns.")

    sheet = payroll_sheet(company=target, month=month) or {}
    by_id = {r["employee"]: r for r in (sheet.get("rows") or [])}
    by_name = {}
    for r in sheet.get("rows") or []:
        by_name.setdefault(" ".join(sorted(str(r["employee_name"]).lower().split())), r)

    def cell(row, field):
        ci = cols.get(field)
        return row[ci] if ci is not None and ci < len(row) else None

    changes, unmatched, per_emp, ribs = [], [], {}, {}
    for row in raw[head_at + 1:]:
        if not any(str(c).strip() for c in row if c is not None):
            continue
        emp = str(cell(row, "__employee") or "").strip()
        cur = by_id.get(emp)
        if not cur:
            nm = str(cell(row, "employee_name") or "").strip()
            cur = by_name.get(" ".join(sorted(nm.lower().split()))) if nm else None
        if not cur:
            label = emp or str(cell(row, "employee_name") or "")
            if label:
                unmatched.append(label[:60])
            continue

        vals = {}
        for f in _IMPORT_NUMERIC:
            if f not in cols:
                continue
            v = _import_number(cell(row, f))
            if v is None:
                continue
            if abs(flt(v) - flt(cur.get(f))) > 0.005:
                vals[f] = v
                changes.append({"employee": cur["employee"], "employee_name": cur["employee_name"],
                                "field": f, "from": flt(cur.get(f)), "to": flt(v)})
        if "contract" in cols:
            v = str(cell(row, "contract") or "").strip()[:20]
            if v and v != (cur.get("contract") or ""):
                vals["contract"] = v
                changes.append({"employee": cur["employee"], "employee_name": cur["employee_name"],
                                "field": "contract", "from": cur.get("contract") or "", "to": v})
        if "sent" in cols:
            v = _import_bool(cell(row, "sent"))
            if v != cint(cur.get("sent")):
                vals["sent"] = v
                changes.append({"employee": cur["employee"], "employee_name": cur["employee_name"],
                                "field": "sent", "from": cint(cur.get("sent")), "to": v})
        if "__rib" in cols:
            v = str(cell(row, "__rib") or "").strip()[:60]
            if v and v != (cur.get("rib") or ""):
                ribs[cur["employee"]] = v
                changes.append({"employee": cur["employee"], "employee_name": cur["employee_name"],
                                "field": "rib", "from": cur.get("rib") or "", "to": v})
        if vals:
            per_emp[cur["employee"]] = vals

    out = {"company": target, "month": month, "matched": len(per_emp) + len(ribs),
           "unmatched": unmatched[:40], "unmatched_count": len(unmatched),
           "changes": changes[:400], "change_count": len(changes),
           "columns": sorted(k for k in cols if not k.startswith("__")),
           "applied": False}
    if not cint(apply):
        return out

    for emp, vals in per_emp.items():
        payroll_sheet_save(company=target, month=month, employee=emp, values=vals)
    for emp, rib in ribs.items():
        payroll_sheet_bank(company=target, employee=emp, rib=rib)
    out["applied"] = True
    return out
