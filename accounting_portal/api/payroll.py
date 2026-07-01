"""Payroll — a full read-only payroll section over ERPNext HR (Salary Slips,
Payroll Entries, Salary Structures) with the accounting lens Justyol lacked:
one consolidated cost-to-company, salary payable outstanding, completeness alerts,
and the component→GL-account map. Entity-scoped (Morocco + Maslak), cached.
"""
import frappe
from frappe.utils import flt, add_months, nowdate, getdate

from accounting_portal.api.permissions import assert_portal_access, resolve_companies


def _target(company):
    companies = resolve_companies(company)
    if not companies:
        return None
    return company if (company and company in companies) else companies[0]


def _period(from_date, to_date):
    if from_date and to_date:
        return from_date, to_date
    return add_months(nowdate(), -12), nowdate()


def _employer_contrib(target, fd, td):
    """Employer-side costs (social security, unemployment employer share) booked to
    the GL directly, not inside the slip."""
    return flt(frappe.db.sql(
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
    return flt(v)


@frappe.whitelist()
def payroll_cockpit(company=None, from_date=None, to_date=None):
    assert_portal_access()
    target = _target(company)
    if not target:
        return {}
    fd, td = _period(from_date, to_date)
    currency = frappe.db.get_value("Company", target, "default_currency") or "MAD"
    ck = f"ap_payroll_cockpit:{target}:{fd}:{td}"
    cached = frappe.cache().get_value(ck)
    if cached is not None:
        return cached

    active = frappe.db.count("Employee", {"company": target, "status": "Active"})
    tot = frappe.db.sql(
        """SELECT ROUND(SUM(gross_pay)) gross, ROUND(SUM(total_deduction)) ded, ROUND(SUM(net_pay)) net,
                  COUNT(*) slips, COUNT(DISTINCT employee) emps
           FROM `tabSalary Slip` WHERE company=%s AND docstatus=1 AND start_date BETWEEN %s AND %s""",
        (target, fd, td), as_dict=True)[0]
    employer = _employer_contrib(target, fd, td)
    monthly = [
        {"m": r.m, "gross": flt(r.gross), "net": flt(r.net), "ded": flt(r.ded), "slips": r.slips}
        for r in frappe.db.sql(
            """SELECT DATE_FORMAT(start_date,'%%Y-%%m') m, ROUND(SUM(gross_pay)) gross,
                      ROUND(SUM(net_pay)) net, ROUND(SUM(total_deduction)) ded, COUNT(*) slips
               FROM `tabSalary Slip` WHERE company=%s AND docstatus=1 AND start_date BETWEEN %s AND %s
               GROUP BY m ORDER BY m DESC LIMIT 12""", (target, fd, td), as_dict=True)][::-1]
    by_dept = frappe.db.sql(
        """SELECT IFNULL(NULLIF(e.department,''),'—') dept, COUNT(DISTINCT e.name) heads,
                  ROUND(SUM(ss.net_pay)) net
           FROM `tabEmployee` e
           LEFT JOIN `tabSalary Slip` ss ON ss.employee=e.name AND ss.docstatus=1 AND ss.start_date BETWEEN %s AND %s
           WHERE e.company=%s AND e.status='Active' GROUP BY dept ORDER BY net DESC LIMIT 12""",
        (fd, td, target), as_dict=True)
    for d in by_dept:
        d["net"] = flt(d["net"])

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
        "gross": flt(tot.gross), "net": flt(tot.net), "deductions": flt(tot.ded),
        "slips": tot.slips or 0, "paid_employees": tot.emps or 0,
        "employer_contrib": round(employer),
        "cost_to_company": round(flt(tot.gross) + employer),
        # only a credit balance is genuinely "owed to employees"; a debit balance is
        # an advance/overpayment, not an outstanding payable.
        "salary_payable": round(max(0.0, _salary_payable(target))),
        "monthly": monthly, "by_department": by_dept,
        "last_month": last_m, "missing_slips": int(missing or 0), "no_structure": int(no_structure or 0),
    }
    frappe.cache().set_value(ck, out, expires_in_sec=300)
    return out


@frappe.whitelist()
def payroll_employees(company=None, search=None, status="Active"):
    """Roster: active employees with base salary, last slip, and YTD gross/net."""
    assert_portal_access()
    target = _target(company)
    if not target:
        return {"rows": []}
    year = getdate(nowdate()).year
    conds = ["e.company=%(c)s"]
    params = {"c": target, "y0": f"{year}-01-01", "y1": f"{year}-12-31"}
    if status and status != "all":
        conds.append("e.status=%(st)s"); params["st"] = status
    if search:
        conds.append("(e.employee_name LIKE %(s)s OR e.name LIKE %(s)s OR IFNULL(e.department,'') LIKE %(s)s)")
        params["s"] = f"%{search}%"
    rows = frappe.db.sql(
        f"""SELECT e.name, e.employee_name nm, e.department dept, e.designation desig, e.status,
                   (SELECT ROUND(a.base) FROM `tabSalary Structure Assignment` a
                    WHERE a.employee=e.name AND a.docstatus=1 ORDER BY a.from_date DESC LIMIT 1) base,
                   (SELECT MAX(s.start_date) FROM `tabSalary Slip` s WHERE s.employee=e.name AND s.docstatus=1) last_slip,
                   (SELECT ROUND(SUM(s.gross_pay)) FROM `tabSalary Slip` s WHERE s.employee=e.name AND s.docstatus=1
                    AND s.start_date BETWEEN %(y0)s AND %(y1)s) ytd_gross,
                   (SELECT ROUND(SUM(s.net_pay)) FROM `tabSalary Slip` s WHERE s.employee=e.name AND s.docstatus=1
                    AND s.start_date BETWEEN %(y0)s AND %(y1)s) ytd_net
            FROM `tabEmployee` e WHERE {' AND '.join(conds)}
            ORDER BY e.status='Active' DESC, e.employee_name LIMIT 300""", params, as_dict=True)
    for r in rows:
        r["base"] = flt(r["base"]); r["ytd_gross"] = flt(r["ytd_gross"]); r["ytd_net"] = flt(r["ytd_net"])
        r["last_slip"] = str(r["last_slip"] or "")[:10]
    return {"company": target, "rows": rows,
            "currency": frappe.db.get_value("Company", target, "default_currency") or "MAD"}


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
    base = flt(frappe.db.sql(
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
             "amount": flt(r.amount)}
            for r in frappe.db.sql(
                """SELECT salary_component, parentfield, amount FROM `tabSalary Detail`
                   WHERE parent=%s ORDER BY parentfield DESC, amount DESC""", (latest,), as_dict=True)]
    slips = [
        {"name": r.name, "month": str(r.start_date)[:7], "gross": flt(r.gross_pay),
         "ded": flt(r.total_deduction), "net": flt(r.net_pay), "status": r.status}
        for r in frappe.db.sql(
            """SELECT name, start_date, gross_pay, total_deduction, net_pay, status
               FROM `tabSalary Slip` WHERE employee=%s AND docstatus=1
               ORDER BY start_date DESC LIMIT 18""", (employee,), as_dict=True)]
    year = getdate(nowdate()).year
    ytd = frappe.db.sql(
        """SELECT ROUND(SUM(gross_pay)) g, ROUND(SUM(net_pay)) n, COUNT(*) c FROM `tabSalary Slip`
           WHERE employee=%s AND docstatus=1 AND start_date BETWEEN %s AND %s""",
        (employee, f"{year}-01-01", f"{year}-12-31"), as_dict=True)[0]
    e["date_of_joining"] = str(e["date_of_joining"] or "")[:10]
    return {"company": target, "currency": frappe.db.get_value("Company", target, "default_currency") or "MAD",
            "employee": e, "base": base, "components": components, "slips": slips,
            "ytd": {"gross": flt(ytd.g), "net": flt(ytd.n), "slips": ytd.c or 0}}


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
                  (SELECT ROUND(SUM(s.net_pay)) FROM `tabSalary Slip` s WHERE s.payroll_entry=pe.name AND s.docstatus=1) net
           FROM `tabPayroll Entry` pe WHERE pe.company=%s ORDER BY pe.posting_date DESC LIMIT 24""",
        (target,), as_dict=True)
    for r in runs:
        r["month"] = str(r.start_date)[:7]
        r["net"] = flt(r["net"])
        r["status"] = "Posted" if r.docstatus == 1 else ("Cancelled" if r.docstatus == 2 else "Draft")
    return {"company": target, "runs": runs,
            "currency": frappe.db.get_value("Company", target, "default_currency") or "MAD"}


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
    earnings = [{"component": r.salary_component, "amount": flt(r.amount)} for r in lines if r.parentfield == "earnings"]
    deductions = [{"component": r.salary_component, "amount": flt(r.amount)} for r in lines if r.parentfield == "deductions"]
    for k in ("start_date", "end_date", "posting_date"):
        s[k] = str(s[k] or "")[:10]
    for k in ("gross_pay", "total_deduction", "net_pay"):
        s[k] = flt(s[k])
    return {"company": target, "slip": s, "earnings": earnings, "deductions": deductions,
            "currency": frappe.db.get_value("Company", target, "default_currency") or "MAD"}


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
        """SELECT sd.salary_component comp, sd.parentfield typ, ROUND(SUM(sd.amount)) tot, COUNT(*) n
           FROM `tabSalary Detail` sd JOIN `tabSalary Slip` ss ON ss.name=sd.parent
           WHERE ss.company=%s AND ss.docstatus=1 AND ss.start_date BETWEEN %s AND %s
           GROUP BY sd.salary_component, sd.parentfield ORDER BY tot DESC""", (target, fd, td), as_dict=True)
    earnings, deductions = [], []
    for r in rows:
        item = {"component": r.comp, "total": flt(r.tot), "count": r.n,
                "account": acct.get(r.comp, ""), "account_short": (acct.get(r.comp, "") or "").split(" - ")[0]}
        (earnings if r.typ == "earnings" else deductions).append(item)
    return {"company": target, "currency": frappe.db.get_value("Company", target, "default_currency") or "MAD",
            "from_date": str(fd), "to_date": str(td),
            "earnings": earnings, "deductions": deductions,
            "earning_total": round(sum(x["total"] for x in earnings)),
            "deduction_total": round(sum(x["total"] for x in deductions))}
