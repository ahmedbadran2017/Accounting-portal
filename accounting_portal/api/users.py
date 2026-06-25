"""Portal user & role management — so the Super Admin onboards teammates and sets
their access level from the portal, without opening ERPNext's user desk."""
import frappe

from accounting_portal.api.permissions import (
    PORTAL_ROLES_SET, ROLE_VIEWER, get_portal_role, can_manage_users,
    assert_portal_access,
)

_ASSIGNABLE = [
    {"role": "Accounting Super Admin", "label": "Super Admin", "desc": "Full access + manages users"},
    {"role": "Accounting Admin", "label": "Admin", "desc": "Full access, posts entries"},
    {"role": "Accountant", "label": "Accountant", "desc": "Posts entries (approval-gated)"},
    {"role": "Accounting Viewer", "label": "Viewer", "desc": "Read-only"},
]


def _assert_manager():
    if not can_manage_users():
        frappe.throw("Only a Super Admin can manage portal users", frappe.PermissionError)


@frappe.whitelist()
def list_portal_users():
    """The team: everyone holding a portal role, their level, status, last seen.
    Readable by any portal user; editing is gated to managers (see capability)."""
    assert_portal_access()
    rows = frappe.db.sql(
        """SELECT DISTINCT hr.parent AS user FROM `tabHas Role` hr WHERE hr.role IN %(roles)s""",
        {"roles": tuple(PORTAL_ROLES_SET)}, as_dict=True)
    out = []
    for r in rows:
        info = frappe.db.get_value(
            "User", r.user, ["full_name", "enabled", "last_active", "user_image"], as_dict=True)
        if not info:
            continue
        out.append({
            "user": r.user, "full_name": info.full_name or r.user,
            "role": get_portal_role(r.user), "enabled": int(info.enabled or 0),
            "last_active": str(info.last_active) if info.last_active else None,
            "image": info.user_image,
        })
    out.sort(key=lambda x: (not x["enabled"], x["full_name"].lower()))
    return {"users": out, "roles": _ASSIGNABLE, "can_manage": can_manage_users(),
            "me": frappe.session.user}


@frappe.whitelist()
def set_portal_role(user=None, role=None):
    """Set a user's single portal role (swaps out any other portal role)."""
    _assert_manager()
    if not user or not frappe.db.exists("User", user):
        frappe.throw("User not found")
    if role not in PORTAL_ROLES_SET:
        frappe.throw("Unknown role")
    if user == frappe.session.user and role != "Accounting Super Admin":
        frappe.throw("You can't downgrade your own Super Admin access")
    u = frappe.get_doc("User", user)
    u.remove_roles(*[r for r in PORTAL_ROLES_SET if r != role])
    u.add_roles(role)
    return {"user": user, "role": get_portal_role(user)}


@frappe.whitelist()
def set_user_enabled(user=None, enabled=None):
    """Enable/disable a teammate's login. Can't disable yourself or Administrator."""
    _assert_manager()
    if not user or not frappe.db.exists("User", user):
        frappe.throw("User not found")
    flag = 1 if str(enabled) in ("1", "true", "True") else 0
    if flag == 0 and user in (frappe.session.user, "Administrator"):
        frappe.throw("You can't disable this account")
    u = frappe.get_doc("User", user)
    u.enabled = flag
    u.save(ignore_permissions=True)
    return {"user": user, "enabled": flag}


@frappe.whitelist()
def invite_user(email=None, full_name=None, role=None):
    """Create (or re-activate) a portal user and grant a role. ERPNext sends the
    welcome/password email via its standard new-user flow."""
    _assert_manager()
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        frappe.throw("A valid email is required")
    role = role if role in PORTAL_ROLES_SET else ROLE_VIEWER
    if frappe.db.exists("User", email):
        u = frappe.get_doc("User", email)
        if not u.enabled:
            u.enabled = 1
            u.save(ignore_permissions=True)
        u.add_roles(role)
        return {"user": email, "role": get_portal_role(email), "existed": True}
    u = frappe.get_doc({
        "doctype": "User", "email": email,
        "first_name": (full_name or email.split("@")[0]).strip(),
        "user_type": "System User", "send_welcome_email": 1,
    })
    u.flags.ignore_permissions = True
    u.insert()
    u.add_roles(role)
    return {"user": email, "role": get_portal_role(email), "existed": False}
