"""Keep the accounting team out of the ERPNext Desk — with a logged escape hatch.

Why: the Desk lets anyone post anything (a bare JE to any account, a payroll run
with a stale employee list, a freight bill on a P&L account). The portal is where
the rules live. Every day the accountants keep the Desk as a fallback is a day
the portal's gaps stay invisible and the books keep collecting side-door errors.

How: at the request layer, exactly like logistics_portal's deskguard. Roles and
permissions stay untouched — the portal's own server methods save on the user's
behalf through those same permissions. Any user holding the `Portal Only` marker
role gets bounced from /app to the portal's desk-pass page.

The escape hatch is the point, not a loophole: instead of stalling and phoning
the owner, the accountant writes one line (what they need the Desk for) and gets
the Desk for an hour, immediately, no approval. Each pass is a row in
`Accounting Portal Action` (action_type "Desk pass") and Team performance shows
what was actually done during the window — so every remaining gap in the portal
shows up as data, ranked by how often people still need the Desk for it.

Fail-open: this runs on every request. Any error here must let the request
through — except the redirect itself, which is an HTTPException by design.
"""
import json
from urllib.parse import quote

import frappe
from frappe.utils import add_to_date, get_datetime, now_datetime
from werkzeug.exceptions import HTTPException
from werkzeug.utils import redirect as _wz_redirect
from werkzeug.wrappers import Response

from accounting_portal.api.permissions import assert_super_admin

LOCK_ROLE = "Portal Only"
PASS_MINUTES = 60
_PASS_KEY = "ap_desk_pass:"          # NOT in _cache._PREFIXES — a write must not revoke a pass
_PASS_PAGE = "/accounting/desk-pass"
# Holders of these are never locked, so the lock can't strand the people who
# administer it (and a Super Admin who ticks the wrong row stays in control).
_SAFE_ROLES = {"Accounting Super Admin", "System Manager"}
_ACTION = "Desk pass"

# Documents whose *creation* is counted inside a pass window. Version rows
# (edits, submits, cancels) are counted for any doctype except the noise below.
_TRACK_CREATES = (
    "Journal Entry", "Payment Entry", "Purchase Invoice", "Sales Invoice", "Purchase Order",
    "Purchase Receipt", "Sales Order", "Delivery Note", "Stock Entry", "Stock Reconciliation",
    "Landed Cost Voucher", "Additional Salary", "Expense Claim", "Payroll Entry", "Salary Slip",
    "Item", "Item Price", "Supplier", "Customer", "Account", "Bank Transaction",
    "Payment Reconciliation", "Employee", "Salary Structure Assignment",
)
_VERSION_NOISE = {"ToDo", "Comment", "Communication", "Notification Log", "Version",
                  "Error Log", "File", "Activity Log", "Email Queue", "User", "Accounting Portal Action"}


# ── state ──────────────────────────────────────────────────────────────────────

def ensure_lock_role():
    """Create the marker role if missing (idempotent; no desk access of its own)."""
    if frappe.db.exists("Role", LOCK_ROLE):
        return
    frappe.get_doc({"doctype": "Role", "role_name": LOCK_ROLE, "desk_access": 0,
                    "restrict_to_domain": ""}).insert(ignore_permissions=True)
    frappe.db.commit()


def is_locked(user=None):
    user = user or frappe.session.user
    if not user or user in ("Guest", "Administrator"):
        return False
    roles = set(frappe.get_roles(user) or [])
    if LOCK_ROLE not in roles:
        return False
    return not (roles & _SAFE_ROLES)


def pass_until(user=None):
    """Datetime the user's current desk pass expires, or None."""
    user = user or frappe.session.user
    raw = frappe.cache().get_value(_PASS_KEY + user)
    if not raw:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode()
    try:
        until = get_datetime(str(raw))
    except Exception:
        return None
    return until if until and until > now_datetime() else None


def _safe_next(nxt):
    nxt = (nxt or "").strip()
    # Only ever send them to the Desk of THIS site — never to a full URL.
    if nxt.startswith("/app") and "://" not in nxt and not nxt.startswith("//"):
        return nxt
    return "/app"


# ── request hook ───────────────────────────────────────────────────────────────

def _bounce(dest):
    # frappe.Redirect is only honoured by the website path resolver; from a
    # before_request hook the only thing the request layer returns as-is is an
    # HTTPException carrying a real response. 302, so a later unlock isn't cached.
    raise HTTPException(response=_wz_redirect(dest, code=302))


def block_desk_for_accountants():
    """before_request hook: bounce `Portal Only` users from /app unless they hold a pass."""
    try:
        req = getattr(frappe.local, "request", None)
        if req is None:
            return
        path = getattr(req, "path", "") or ""
        desk = path == "/app" or path.startswith("/app/")
        # The Desk's own RPC surface — closes the "tab left open before the lock"
        # loophole. The portal SPA never calls these (it calls accounting_portal.*).
        desk_api = path.startswith("/api/method/frappe.desk.") or path.startswith("/api/method/frappe.client.")
        if not (desk or desk_api):
            return
        user = getattr(getattr(frappe, "session", None), "user", None)
        if not user or user in ("Guest", "Administrator"):
            return
        if not is_locked(user) or pass_until(user):
            return
        if desk_api:
            body = json.dumps({"exc_type": "PermissionError",
                               "exception": "The Desk is locked for this account. Request a desk pass in the portal."})
            raise HTTPException(response=Response(body, status=403, mimetype="application/json"))
        _bounce(_PASS_PAGE + "?next=" + quote(path, safe="/"))
    except HTTPException:
        raise
    except Exception:
        return


# ── API: the locked user's side ────────────────────────────────────────────────

@frappe.whitelist()
def desk_status():
    user = frappe.session.user
    if user == "Guest":
        frappe.throw("Not permitted", frappe.PermissionError)
    until = pass_until(user)
    remaining = int((until - now_datetime()).total_seconds() // 60) if until else 0
    return {"user": user, "locked": is_locked(user), "pass_until": str(until)[:16] if until else None,
            "remaining_min": max(0, remaining), "minutes": PASS_MINUTES}


@frappe.whitelist()
def request_desk_pass(reason=None, next=None, company=None):
    """Open the Desk for PASS_MINUTES, immediately, and log why. No approval —
    the pass is a data point, not a gate."""
    user = frappe.session.user
    if user == "Guest":
        frappe.throw("Not permitted", frappe.PermissionError)
    dest = _safe_next(next)
    if not is_locked(user):
        return {"locked": False, "redirect": dest}
    reason = (reason or "").strip()
    if len(reason) < 3:
        frappe.throw("Write what you need the Desk for")
    if not company:
        try:
            from accounting_portal.api.permissions import allowed_companies
            cs = allowed_companies(user) or []
            c0 = cs[0] if cs else None
            company = c0.get("name") if isinstance(c0, dict) else c0
        except Exception:
            company = None
    start = now_datetime()
    until = add_to_date(start, minutes=PASS_MINUTES)
    frappe.cache().set_value(_PASS_KEY + user, str(until), expires_in_sec=PASS_MINUTES * 60)
    doc = frappe.get_doc({
        "doctype": "Accounting Portal Action", "action_type": _ACTION, "status": "Posted",
        "company": company or None, "reference_doctype": "User", "reference_name": user,
        "proposed_by": user, "approved_by": user, "posted_on": start,
        "notes": reason[:500],
        "payload": json.dumps({"next": dest, "minutes": PASS_MINUTES,
                               "from": str(start)[:19], "until": str(until)[:19]}),
        "result": json.dumps({"until": str(until)[:19]}),
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"locked": True, "pass_until": str(until)[:16], "redirect": dest}


# ── API: the owner's side — where do people still need the Desk? ───────────────

def _window(payload, creation):
    try:
        p = json.loads(payload or "{}")
    except Exception:
        p = {}
    start = get_datetime(p.get("from") or creation)
    until = get_datetime(p.get("until")) if p.get("until") else add_to_date(start, minutes=PASS_MINUTES)
    return start, until


@frappe.whitelist()
def desk_passes(from_date=None, to_date=None, user=None):
    """Every desk pass in the period with what was actually done during it, plus
    the gap ranking: which doctypes keep pulling people back to the Desk."""
    assert_super_admin()
    from frappe.utils import add_days, nowdate
    if not (from_date and to_date):
        from_date, to_date = add_days(nowdate(), -30), nowdate()
    filters = {"action_type": _ACTION,
               "creation": ["between", [str(from_date) + " 00:00:00", str(to_date) + " 23:59:59"]]}
    if user:
        filters["owner"] = user
    rows = frappe.get_all("Accounting Portal Action", filters=filters,
                          fields=["name", "owner", "creation", "notes", "payload"],
                          order_by="creation desc", limit=500)
    passes = []
    for r in rows:
        start, until = _window(r.payload, r.creation)
        passes.append({"id": r.name, "user": r.owner, "reason": r.notes or "",
                       "start": start, "until": until, "touched": {}})
    if passes:
        users = sorted({p["user"] for p in passes})
        lo = min(p["start"] for p in passes)
        hi = max(p["until"] for p in passes)

        def bump(owner, when, dt, kind):
            for p in passes:
                if p["user"] == owner and p["start"] <= when <= p["until"]:
                    t = p["touched"].setdefault(dt, {"created": 0, "edited": 0})
                    t[kind] += 1
                    return

        for dt in _TRACK_CREATES:
            if not frappe.db.exists("DocType", dt):
                continue
            try:
                hits = frappe.db.sql(
                    f"SELECT owner, creation FROM `tab{dt}` WHERE owner IN %(u)s AND creation BETWEEN %(lo)s AND %(hi)s",
                    {"u": tuple(users), "lo": lo, "hi": hi})
            except Exception:
                continue
            for owner, when in hits:
                bump(owner, when, dt, "created")
        vers = frappe.db.sql(
            "SELECT owner, creation, ref_doctype FROM `tabVersion` "
            "WHERE owner IN %(u)s AND creation BETWEEN %(lo)s AND %(hi)s",
            {"u": tuple(users), "lo": lo, "hi": hi})
        for owner, when, dt in vers:
            if dt in _VERSION_NOISE:
                continue
            bump(owner, when, dt, "edited")

    names = {}
    for p in passes:
        if p["user"] not in names:
            names[p["user"]] = frappe.db.get_value("User", p["user"], "full_name") or p["user"]

    gaps = {}
    for p in passes:
        for dt, t in p["touched"].items():
            g = gaps.setdefault(dt, {"doctype": dt, "passes": 0, "created": 0, "edited": 0})
            g["passes"] += 1
            g["created"] += t["created"]
            g["edited"] += t["edited"]
    gap_rows = sorted(gaps.values(), key=lambda g: (-g["passes"], -(g["created"] + g["edited"])))
    idle = sum(1 for p in passes if not p["touched"])

    out = [{"id": p["id"], "user": p["user"], "full_name": names[p["user"]], "reason": p["reason"],
            "start": str(p["start"])[:16], "until": str(p["until"])[:16],
            "touched": [{"doctype": dt, **t} for dt, t in sorted(p["touched"].items(), key=lambda kv: -(kv[1]["created"] + kv[1]["edited"]))]}
           for p in passes]
    return {"from_date": str(from_date), "to_date": str(to_date), "passes": out, "gaps": gap_rows,
            "summary": {"passes": len(passes), "users": len(names), "idle": idle,
                        "hours": round(len(passes) * PASS_MINUTES / 60, 1)},
            "locked_users": [{"user": u, "full_name": frappe.db.get_value("User", u, "full_name") or u}
                             for u in sorted(x[0] for x in frappe.db.sql(
                                 "SELECT parent FROM `tabHas Role` WHERE role=%s", LOCK_ROLE))],
            "minutes": PASS_MINUTES, "tz_note": "server time"}
