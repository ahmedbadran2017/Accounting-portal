"""Auth / session endpoints for the Accounting Portal.

Login itself uses Frappe's built-in /api/method/login (handled by the
frontend useAuth composable). These helpers expose just enough session
context for the SPA to render the right shell after login.
"""
import frappe

from accounting_portal.api.permissions import (
    assert_portal_access,
    get_portal_role,
    has_all_access,
    can_manage_users,
    can_write,
    allowed_companies,
)


@frappe.whitelist()
def get_session_info():
    """Return the logged-in user's portal context.

    Shape mirrors what the SPA's useAuth/useRole composables expect:
      { user, full_name, role, is_admin, companies, capabilities }
    """
    user = frappe.session.user
    if user == "Guest":
        frappe.throw("Not permitted", frappe.PermissionError)
    # Any logged-in Frappe user without an accounting role is denied — keeps
    # the portal internal even if someone else has a site login.
    assert_portal_access(user)
    return {
        "user": user,
        "full_name": frappe.db.get_value("User", user, "full_name"),
        "role": get_portal_role(user),
        "is_admin": has_all_access(user),
        "companies": allowed_companies(user),
        "capabilities": {
            "manage_users": can_manage_users(user),
            "post_entries": can_write(user),
        },
    }
