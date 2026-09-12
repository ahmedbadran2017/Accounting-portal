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


# ── Timezone ────────────────────────────────────────────────────────────────
# Timestamps are stored in the site's timezone (Istanbul), so a Morocco clerk's
# 10:54 is written as 12:54. Every hour-of-day figure below is converted to the
# person's own wall clock, otherwise the two companies can't be compared.
_TZ_BY_COUNTRY = {
    "Morocco": "Africa/Casablanca",
    "Turkey": "Europe/Istanbul",
    "China": "Asia/Shanghai",
    "Egypt": "Africa/Cairo",
}
_TZ_FALLBACK = "Europe/Istanbul"


def _server_tz():
    return frappe.db.get_single_value("System Settings", "time_zone") or _TZ_FALLBACK


def _local_tz(company, override=None):
    if override:
        return override
    country = frappe.db.get_value("Company", company, "country")
    return _TZ_BY_COUNTRY.get(country) or _server_tz()


def _tz_probe(local_tz, server_tz, sample):
    """MySQL's named-timezone tables carry real DST history — including Morocco's
    Ramadan shift to UTC+0 — so conversion is done in SQL when they're loaded.
    Returns (works, offset_minutes_at_sample)."""
    try:
        row = frappe.db.sql(
            "SELECT CONVERT_TZ(%s, %s, %s), TIMESTAMPDIFF(MINUTE, %s, CONVERT_TZ(%s, %s, %s))",
            (sample, server_tz, local_tz, sample, sample, server_tz, local_tz))[0]
        if row[0] is None:
            return False, 0
        return True, int(row[1] or 0)
    except Exception:
        return False, 0


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
        frappe.cache().set_value(ck, out, expires_in_sec=600)
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
    frappe.cache().set_value(ck, out, expires_in_sec=600)
    return out


@frappe.whitelist()
def accountant_detail(company=None, user=None, from_date=None, to_date=None):
    """Deep scorecard for one accountant: per-doctype quality breakdown, a monthly
    created/submitted/cancelled trend, recent documents, and how they compare to the
    team. Super-admin only. Reuses team_performance (cached) for the headline +
    ranking so the two screens always agree."""
    assert_super_admin()
    target = _target(company)
    if not target or not user:
        return {}
    if not (from_date and to_date):
        from_date, to_date = add_days(nowdate(), -90), nowdate()
    end = str(to_date) + " 23:59:59"
    currency = frappe.db.get_value("Company", target, "default_currency") or "MAD"

    team = team_performance(target, from_date, to_date)
    members = team.get("members", [])
    me = next((m for m in members if m["user"] == user), None)
    rank = next((i + 1 for i, m in enumerate(members) if m["user"] == user), None)
    team_avg_per_day = round(sum(m["per_day"] for m in members) / len(members), 1) if members else 0.0

    # per-doctype quality breakdown
    by_doctype = []
    for dt, vf, code in _DOCTYPES:
        r = frappe.db.sql(
            f"""SELECT COUNT(*) c, SUM(docstatus=1) sub, SUM(docstatus=2) can, SUM(docstatus=0) dft,
                       ROUND(SUM(CASE WHEN docstatus=1 THEN {vf} ELSE 0 END)) val
                FROM `tab{dt}` WHERE company=%s AND owner=%s AND creation BETWEEN %s AND %s""",
            (target, user, from_date, end), as_dict=True)[0]
        if r.c:
            created = r.c
            by_doctype.append({
                "code": code, "label": dt, "created": created,
                "submitted": int(r.sub or 0), "cancelled": int(r.can or 0), "draft": int(r.dft or 0),
                "value": flt(r.val),
                "rework_pct": round(int(r.can or 0) / created * 100, 1) if created else 0.0})

    # monthly created / submitted / cancelled trend (last 12 buckets)
    union = " UNION ALL ".join(
        f"SELECT DATE_FORMAT(creation,'%%Y-%%m') m, docstatus ds FROM `tab{dt}` "
        f"WHERE company=%s AND owner=%s AND creation BETWEEN %s AND %s" for dt, _, _ in _DOCTYPES)
    params = []
    for _ in _DOCTYPES:
        params += [target, user, from_date, end]
    monthly = [
        {"m": x.m, "created": x.created, "submitted": int(x.sub or 0), "cancelled": int(x.can or 0)}
        for x in frappe.db.sql(
            f"SELECT m, COUNT(*) created, SUM(ds=1) sub, SUM(ds=2) can FROM ({union}) t "
            "GROUP BY m ORDER BY m DESC LIMIT 12", params, as_dict=True)][::-1]

    # recent documents across the accounting doctypes
    runion = " UNION ALL ".join(
        f"SELECT '{code}' code, name, creation, docstatus, {vf} amt FROM `tab{dt}` "
        f"WHERE company=%s AND owner=%s AND creation BETWEEN %s AND %s" for dt, vf, code in _DOCTYPES)
    recent = [
        {"code": x.code, "name": x.name, "date": str(x.d), "docstatus": x.docstatus, "amount": flt(x.amt)}
        for x in frappe.db.sql(
            f"SELECT code, name, DATE(creation) d, docstatus, ROUND(amt) amt FROM ({runion}) t "
            "ORDER BY creation DESC LIMIT 15", params, as_dict=True)]

    urow = frappe.db.get_value(
        "User", user, ["full_name", "enabled", "user_image", "last_active"], as_dict=True) or {}

    return {
        "company": target, "currency": currency,
        "from_date": str(from_date), "to_date": str(to_date),
        "user": user, "name": urow.get("full_name") or (me or {}).get("name") or user,
        "image": urow.get("user_image") or "", "enabled": int(urow.get("enabled") or 0),
        "rank": rank, "members": len(members),
        "summary": me or {},
        "by_doctype": by_doctype, "monthly": monthly, "recent": recent,
        "team": {"rework_pct": team.get("totals", {}).get("rework_pct", 0.0),
                 "avg_per_day": team_avg_per_day},
    }


# ── Activity trail ──────────────────────────────────────────────────────────
# The scorecard above counts documents *created*, and only four doctypes — which
# undercounts anyone whose day is spent submitting and correcting existing work.
# The trail below is the complete record: creations from the document tables,
# plus every edit / submit / cancel from tabVersion, which Frappe writes for all
# doctypes. Each event is stamped in the person's own timezone.
_ACT_DOCTYPES = (
    ("Journal Entry", "JE", "total_debit"),
    ("Payment Entry", "PE", "base_paid_amount"),
    ("Purchase Invoice", "PI", "base_grand_total"),
    ("Sales Invoice", "SI", "base_grand_total"),
    ("Purchase Order", "PO", "base_grand_total"),
    ("Purchase Receipt", "PR", "base_grand_total"),
    ("Sales Order", "SO", "base_grand_total"),
    ("Delivery Note", "DN", "base_grand_total"),
    ("Stock Entry", "STE", "total_amount"),
    ("Stock Reconciliation", "REC", None),
    ("Landed Cost Voucher", "LCV", None),
    ("Additional Salary", "ADS", "amount"),
    ("Expense Claim", "EXP", "grand_total"),
    ("Pick List", "PCK", None),
)
_CODE_BY_DT = {dt: code for dt, code, _ in _ACT_DOCTYPES}
# Events returned in the feed — the counters and grids are always complete, this
# only bounds the payload. Sized so a day, a week or a fortnight comes back whole;
# longer ranges keep the most recent slice and report the remainder.
_TIMELINE_CAP = 1200
_DAILY_GRID_MAX_DAYS = 62    # beyond this a date×hour grid stops being readable


def _describe(data):
    """Turn a Version diff into (kind, one-line summary)."""
    try:
        d = frappe.parse_json(data) or {}
    except Exception:
        return "edited", ""
    # Stored diffs are user data of varying shape — never trust the arity.
    changed = [c for c in (d.get("changed") or []) if isinstance(c, (list, tuple)) and len(c) >= 3]
    for f, old, new in (c[:3] for c in changed):
        if f == "docstatus":
            if str(new) == "1":
                return "submitted", ""
            if str(new) == "2":
                return "cancelled", ""
    bits = []
    for f, old, new in (c[:3] for c in changed[:4]):
        if f in ("status", "modified_by", "_comments", "base_in_words", "in_words"):
            continue
        bits.append(f"{f}: {str(old)[:22]} → {str(new)[:22]}")
        if len(bits) == 3:
            break
    rows = len(d.get("added") or []) + len(d.get("removed") or []) + len(d.get("row_changed") or [])
    if rows:
        bits.append(f"{rows} row change{'s' if rows > 1 else ''}")
    return "edited", " · ".join(bits)


@frappe.whitelist()
def accountant_activity(company=None, user=None, from_date=None, to_date=None, tz=None):
    """Every action one person took, on their own clock.

    Returns the raw timeline plus three aggregations: total per hour-of-day, a
    date×hour grid for short ranges, and a weekday×hour grid that shows the
    working rhythm over any range. Super-admin only."""
    assert_super_admin()
    target = _target(company)
    if not target or not user:
        return {}
    if not (from_date and to_date):
        from_date, to_date = add_days(nowdate(), -13), nowdate()
    ck = f"ap_team_act:{target}:{user}:{from_date}:{to_date}:{tz or ''}"
    cached = frappe.cache().get_value(ck)
    if cached is not None:
        return cached

    server_tz = _server_tz()
    local_tz = _local_tz(target, tz)
    tz_ok, offset_min = _tz_probe(local_tz, server_tz, str(to_date) + " 12:00:00")

    # Widen the server-time window by a day either side, then trim on local dates,
    # so events near midnight land in the right local day whatever the offset.
    win_start = str(add_days(from_date, -1)) + " 00:00:00"
    win_end = str(add_days(to_date, 1)) + " 23:59:59"
    lt = (f"CONVERT_TZ(%s, '{server_tz}', '{local_tz}')" if tz_ok else "%s")

    events = []

    # 1 ── documents created
    for dt, code, vf in _ACT_DOCTYPES:
        if not frappe.db.table_exists(dt):
            continue
        amt = vf or "0"
        try:
            rows = frappe.db.sql(
                f"""SELECT name, {lt.replace('%s', 'creation')} lt, docstatus ds, {amt} amt
                    FROM `tab{dt}`
                    WHERE company=%s AND owner=%s AND creation BETWEEN %s AND %s""",
                (target, user, win_start, win_end), as_dict=True)
        except Exception:
            continue
        for r in rows:
            if not r.lt:
                continue
            events.append({"kind": "created", "code": code, "doctype": dt, "name": r.name,
                           "at": str(r.lt), "docstatus": r.ds, "amount": flt(r.amt), "note": ""})

    # 2 ── edits / submits / cancels, any doctype
    vrows = frappe.db.sql(
        f"""SELECT ref_doctype, docname, {lt.replace('%s', 'creation')} lt, data
            FROM tabVersion
            WHERE owner=%s AND creation BETWEEN %s AND %s
            ORDER BY creation""", (user, win_start, win_end), as_dict=True)

    # Versions carry no company, so resolve it in one pass per doctype and keep
    # only this entity's documents.
    by_dt = {}
    for r in vrows:
        by_dt.setdefault(r.ref_doctype, set()).add(r.docname)
    in_company = {}
    for dt, names in by_dt.items():
        if not frappe.db.table_exists(dt):
            continue
        cols = frappe.db.get_table_columns(dt) or []
        if "company" not in cols:
            in_company[dt] = set(names)   # company-less masters: attribute to the entity in view
            continue
        names = list(names)
        keep = set()
        for i in range(0, len(names), 500):
            chunk = names[i:i + 500]
            ph = ", ".join(["%s"] * len(chunk))
            keep.update(x[0] for x in frappe.db.sql(
                f"SELECT name FROM `tab{dt}` WHERE company=%s AND name IN ({ph})",
                [target] + chunk))
        in_company[dt] = keep

    for r in vrows:
        if not r.lt or r.docname not in in_company.get(r.ref_doctype, ()):
            continue
        kind, note = _describe(r.data)
        events.append({"kind": kind, "code": _CODE_BY_DT.get(r.ref_doctype, r.ref_doctype[:3].upper()),
                       "doctype": r.ref_doctype, "name": r.docname,
                       "at": str(r.lt), "docstatus": None, "amount": 0.0, "note": note})

    # 3 ── comments
    for r in frappe.db.sql(
            f"""SELECT reference_doctype dt, reference_name dn, {lt.replace('%s', 'creation')} lt, content
                FROM tabComment
                WHERE owner=%s AND comment_type='Comment' AND creation BETWEEN %s AND %s""",
            (user, win_start, win_end), as_dict=True):
        if not r.lt or r.dn not in in_company.get(r.dt, ()):
            continue
        events.append({"kind": "comment", "code": _CODE_BY_DT.get(r.dt, "—"), "doctype": r.dt,
                       "name": r.dn, "at": str(r.lt), "docstatus": None, "amount": 0.0,
                       "note": frappe.utils.strip_html(r.content or "")[:90]})

    # Trim to the requested LOCAL calendar days
    lo, hi = str(from_date), str(to_date)
    events = [e for e in events if lo <= e["at"][:10] <= hi]
    events.sort(key=lambda e: e["at"])

    # ── aggregations (all on the local clock) ──
    hours = [0] * 24
    week = [[0] * 24 for _ in range(7)]
    days = {}
    kinds = {"created": 0, "submitted": 0, "cancelled": 0, "edited": 0, "comment": 0}
    for e in events:
        day, hh = e["at"][:10], int(e["at"][11:13])
        hours[hh] += 1
        row = days.setdefault(day, [0] * 24)
        row[hh] += 1
        kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1

    heat = []
    for day in sorted(days):
        dow = frappe.utils.getdate(day).weekday()          # Mon=0 … Sun=6
        dow = (dow + 1) % 7                                 # → Sun=0 … Sat=6
        for h in range(24):
            week[dow][h] += days[day][h]
        heat.append({"d": day, "dow": dow, "total": sum(days[day]), "h": days[day]})
    span_days = (frappe.utils.getdate(to_date) - frappe.utils.getdate(from_date)).days + 1
    if span_days > _DAILY_GRID_MAX_DAYS:
        heat = heat[-_DAILY_GRID_MAX_DAYS:]

    total = len(events)
    busiest = hours.index(max(hours)) if total else None
    # Earliest and latest time *of day* over the period — not the first and last
    # event chronologically, which over a multi-day range says nothing useful.
    clock = sorted(e["at"][11:16] for e in events)
    stats = {
        "actions": total,
        "active_days": len(days),
        "per_day": round(total / len(days), 1) if days else 0.0,
        "first_at": clock[0] if clock else "",
        "last_at": clock[-1] if clock else "",
        "busiest_hour": busiest,
        "busiest_count": hours[busiest] if busiest is not None else 0,
        "active_hours": sum(1 for h in hours if h),
        "peak_day": max(heat, key=lambda x: x["total"])["d"] if heat else "",
        **kinds,
    }

    urow = frappe.db.get_value("User", user, ["full_name", "user_image"], as_dict=True) or {}
    sign = "+" if offset_min >= 0 else "−"
    out = {
        "company": target, "user": user,
        "name": urow.get("full_name") or user, "image": urow.get("user_image") or "",
        "currency": frappe.db.get_value("Company", target, "default_currency") or "MAD",
        "from_date": str(from_date), "to_date": str(to_date),
        "tz": {"local": local_tz, "server": server_tz, "ok": tz_ok,
               "offset_min": offset_min,
               "label": f"{sign}{abs(offset_min) // 60}h" if offset_min else "same",
               "shifted": bool(offset_min)},
        "stats": stats, "hours": hours, "heatmap": heat, "week": week,
        "daily_grid": span_days <= _DAILY_GRID_MAX_DAYS,
        "timeline": events[-_TIMELINE_CAP:][::-1],
        "truncated": max(0, total - _TIMELINE_CAP),
    }
    # Short TTL: today's row should feel live, but re-opening a person shouldn't
    # replay a dozen scans.
    frappe.cache().set_value(ck, out, expires_in_sec=120)
    return out
