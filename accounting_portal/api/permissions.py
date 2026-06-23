"""Portal role & capability helpers for the Accounting Portal.

Single source of truth for "what can this user do". Every whitelisted API
method calls assert_portal_access() first, then capability checks for writes.

Role hierarchy (broadest → narrowest):
    Accounting Super Admin  — sees everything, manages portal users & roles
    Accounting Admin        — sees everything, cannot manage users
    Accountant              — operational: post JEs, manage AP/AR, reconcile
    Accounting Viewer       — read-only dashboards & reports (owners/management)
"""
import frappe


ROLE_SUPER_ADMIN = "Accounting Super Admin"
ROLE_ADMIN = "Accounting Admin"
ROLE_ACCOUNTANT = "Accountant"
ROLE_VIEWER = "Accounting Viewer"

# Roles that grant full read access to every company's data.
ALL_ACCESS_ROLES = {ROLE_SUPER_ADMIN, ROLE_ADMIN, "System Manager", "Administrator"}
# Roles that can perform write/posting operations.
WRITE_ROLES = {ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_ACCOUNTANT, "System Manager", "Administrator"}
# Any role that may open the portal at all.
PORTAL_ROLES_SET = {ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_ACCOUNTANT, ROLE_VIEWER}


def get_portal_role(user=None):
    """Return the highest-priority accounting role the user holds, or None."""
    user = user or frappe.session.user
    roles = set(frappe.get_roles(user))
    for r in (ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_ACCOUNTANT, ROLE_VIEWER):
        if r in roles:
            return r
    if "System Manager" in roles or user == "Administrator":
        return ROLE_SUPER_ADMIN
    return None


def has_all_access(user=None):
    user = user or frappe.session.user
    roles = set(frappe.get_roles(user))
    return bool(roles & ALL_ACCESS_ROLES) or user == "Administrator"


def can_write(user=None):
    """Can this user post/modify accounting data (JEs, payments, AP/AR)?"""
    user = user or frappe.session.user
    roles = set(frappe.get_roles(user))
    return bool(roles & WRITE_ROLES) or user == "Administrator"


def can_manage_users(user=None):
    """Only Super Admin manages portal users & role assignment."""
    user = user or frappe.session.user
    roles = set(frappe.get_roles(user))
    return ROLE_SUPER_ADMIN in roles or user == "Administrator"


def assert_portal_access(user=None):
    """Raise PermissionError unless the user holds any accounting portal role."""
    user = user or frappe.session.user
    if has_all_access(user):
        return
    if get_portal_role(user):
        return
    frappe.throw("Not permitted", frappe.PermissionError)


def assert_can_write(user=None):
    """Raise PermissionError unless the user may post/modify accounting data."""
    if not can_write(user):
        frappe.throw("Not permitted to modify accounting data", frappe.PermissionError)


def allowed_companies(user=None):
    """Return the list of Company names this user may see.

    Today every portal role sees all companies (the team is small and works
    across all 4 entities). The hook is here so per-company scoping can be
    added later — e.g. by reading a custom 'allowed_companies' field on User —
    without touching every endpoint.
    """
    return frappe.get_all("Company", pluck="name", order_by="name")


def resolve_companies(company=None, user=None):
    """The companies this user may see, optionally narrowed to one.

    Validates a requested company against the allowed set, so an endpoint can
    accept a `company` arg from the client without letting a user read an
    entity they aren't permitted to. A bad/unknown value yields an empty list
    (→ no rows), never an error or a permission bypass.
    """
    allowed = allowed_companies(user)
    if company:
        return [c for c in allowed if c == company]
    return allowed


@frappe.whitelist()
def whoami():
    """Expose the current user's accounting role + capabilities to the SPA.

    Requires login (not guest) — this is an internal portal. The SPA calls
    this right after login to decide routing and which UI controls to show.
    """
    user = frappe.session.user
    if user == "Guest":
        frappe.throw("Not permitted", frappe.PermissionError)
    return {
        "user": user,
        "full_name": frappe.db.get_value("User", user, "full_name"),
        "role": get_portal_role(user),
        "is_all_access": has_all_access(user),
        "companies": allowed_companies(user),
        "capabilities": {
            "manage_users": can_manage_users(user),
            "post_entries": can_write(user),
            "view_reports": True,
        },
    }
