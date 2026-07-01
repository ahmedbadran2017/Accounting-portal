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
    }


# ── Generate (create Payroll Entry + draft slips) ──────────────────────────────

@frappe.whitelist()
def payroll_generate(company=None, month=None, notes=None):
    assert_can_write()
    target = _target(company)
    if not (target and month):
        frappe.throw("company and month are required")
    from accounting_portal.api import _actions
    key = "payroll-run:" + frappe.generate_hash(f"{target}:{month}", 14)
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
        "payroll_payable_account": payable, "cost_center": cc,
    })
    pe.fill_employee_details()
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
        frappe.get_doc("Payroll Entry", pe).cancel()
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
    key = "payroll-submit:" + frappe.generate_hash(f"{target}:{month}", 14)
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
        frappe.get_doc("Payroll Entry", r.name).submit_salary_slips()
        done.append(r.name)
    # Any stray draft slips not tied to a run — submit directly.
    for s in frappe.get_all("Salary Slip",
                            {"company": target, "docstatus": 0}, ["name", "start_date"]):
        if str(s.start_date)[:7] == month:
            frappe.get_doc("Salary Slip", s.name).submit()
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
            frappe.get_doc("Salary Slip", s.name).cancel()
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
    key = "payroll-pay:" + frappe.generate_hash(f"{target}:{month}:{bank_account}:{total}", 14)
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


_register()
