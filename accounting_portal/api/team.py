"""Team performance — accountant productivity & quality scorecards.

SUPER-ADMIN ONLY (sensitive employee-evaluation data). Attributes the accounting
documents people post — Journal Entries, Payment Entries, Purchase & Sales
Invoices — to their owner, and surfaces four lenses:

  • Volume    — documents created / submitted, and the financial value moved.
  • Quality   — rework: the cancellation rate (cancelled ÷ created). The single
                strongest signal of careless or error-prone work.
  • Cadence   — distinct active days and per-active-day throughput.
  • Backlog   — stuck drafts the member created but never submitted.

Read-only, entity-scoped, cached. Operations-only doctypes (Delivery Notes) are
deliberately excluded so the page reflects *accountants*, not the whole team.
"""
import frappe
from frappe.utils import flt, add_days, nowdate

from accounting_portal.api.permissions import assert_super_admin, resolve_companies


def _target(company):
    companies = resolve_companies(company)
    if not companies:
        return None
    return company if (company and company in companies) else companies[0]


# (doctype, value field already in company currency, short code)
_DOCTYPES = (
    ("Journal Entry", "total_debit", "JE"),
    ("Payment Entry", "base_paid_amount", "PE"),
    ("Purchase Invoice", "base_grand_total", "PI"),
    ("Sales Invoice", "base_grand_total", "SI"),
)
_REWORK_FLAG = 20.0   # cancellation rate (%) at/above which a member is flagged…
_FLAG_MIN_CANCELLED = 5  # …but only once they've cancelled a meaningful count.


@frappe.whitelist()
def team_performance(company=None, from_date=None, to_date=None):
    assert_super_admin()
    target = _target(company)
    if not target:
        return {}
    if not (from_date and to_date):
        from_date, to_date = add_days(nowdate(), -90), nowdate()
    ck = f"ap_team_perf:{target}:{from_date}:{to_date}"
    cached = frappe.cache().get_value(ck)
    if cached is not None:
        return cached

    end = str(to_date) + " 23:59:59"
    currency = frappe.db.get_value("Company", target, "default_currency") or "MAD"

    users = {}
    for dt, vf, code in _DOCTYPES:
        for r in frappe.db.sql(
                f"""SELECT owner, COUNT(*) c, SUM(docstatus=1) sub, SUM(docstatus=2) can,
                           SUM(docstatus=0) dft,
                           ROUND(SUM(CASE WHEN docstatus=1 THEN {vf} ELSE 0 END)) val,
                           MAX(creation) last_at
                    FROM `tab{dt}`
                    WHERE company=%s AND creation BETWEEN %s AND %s
                    GROUP BY owner""", (target, from_date, end), as_dict=True):
            u = users.setdefault(r.owner, {
                "created": 0, "submitted": 0, "cancelled": 0, "draft": 0,
                "value": 0.0, "by": {}, "last_at": ""})
            u["created"] += r.c
            u["submitted"] += int(r.sub or 0)
            u["cancelled"] += int(r.can or 0)
            u["draft"] += int(r.dft or 0)
            u["value"] += flt(r.val)
            u["by"][code] = r.c
            if str(r.last_at) > u["last_at"]:
                u["last_at"] = str(r.last_at)

    if not users:
        out = {"company": target, "from_date": str(from_date), "to_date": str(to_date),
               "currency": currency, "members": [], "totals": {},
               "doctypes": [{"code": c, "label": dt} for dt, _, c in _DOCTYPES]}
        frappe.cache().set_value(ck, out, expires_in_sec=300)
        return out

    # Distinct active days across all accounting doctypes — one owner+date pair is
    # one active day, so a person posting JEs and PEs on the same day counts once.
    union = " UNION ".join(
        f"SELECT owner, DATE(creation) d FROM `tab{dt}` WHERE company=%s AND creation BETWEEN %s AND %s"
        for dt, _, _ in _DOCTYPES)
    params = []
    for _ in _DOCTYPES:
        params += [target, from_date, end]
    active = {r.owner: r.days for r in frappe.db.sql(
        f"SELECT owner, COUNT(*) days FROM ({union}) t GROUP BY owner", params, as_dict=True)}

    members = []
    for uid, d in users.items():
        urow = frappe.db.get_value(
            "User", uid, ["full_name", "enabled", "user_image"], as_dict=True) or {}
        created = d["created"]
        days = active.get(uid, 0)
        rework = round(d["cancelled"] / created * 100, 1) if created else 0.0
        members.append({
            "user": uid,
            "name": urow.get("full_name") or uid,
            "image": urow.get("user_image") or "",
            "enabled": int(urow.get("enabled") or 0),
            "created": created,
            "submitted": d["submitted"],
            "cancelled": d["cancelled"],
            "draft": d["draft"],
            "value": round(d["value"]),
            "by": d["by"],
            "active_days": days,
            "per_day": round(created / days, 1) if days else 0.0,
            "rework_pct": rework,
            "clean_pct": round(d["submitted"] / created * 100, 1) if created else 0.0,
            "flagged": bool(rework >= _REWORK_FLAG and d["cancelled"] >= _FLAG_MIN_CANCELLED),
            "last_at": d["last_at"][:10],
        })
    members.sort(key=lambda m: -m["created"])

    totals = {
        "members": len(members),
        "created": sum(m["created"] for m in members),
        "submitted": sum(m["submitted"] for m in members),
        "cancelled": sum(m["cancelled"] for m in members),
        "draft": sum(m["draft"] for m in members),
        "value": sum(m["value"] for m in members),
        "flagged": sum(1 for m in members if m["flagged"]),
    }
    totals["rework_pct"] = round(totals["cancelled"] / totals["created"] * 100, 1) if totals["created"] else 0.0

    out = {"company": target, "from_date": str(from_date), "to_date": str(to_date),
           "currency": currency, "members": members, "totals": totals,
           "doctypes": [{"code": c, "label": dt} for dt, _, c in _DOCTYPES]}
    frappe.cache().set_value(ck, out, expires_in_sec=300)
    return out
