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
    # Logged into the site but without any accounting-portal role: return a marked
    # payload (instead of throwing) so the SPA shows a clear "no access" screen
    # rather than bouncing them to the login page with no explanation.
    if not (has_all_access(user) or get_portal_role(user)):
        return {
            "user": user, "full_name": frappe.db.get_value("User", user, "full_name"),
            "has_access": False, "role": None, "is_admin": False,
            "companies": [], "capabilities": {},
        }
    return {
        "user": user,
        "full_name": frappe.db.get_value("User", user, "full_name"),
        "has_access": True,
        "role": get_portal_role(user),
        "is_admin": has_all_access(user),
        "companies": allowed_companies(user),
        "capabilities": {
            "manage_users": can_manage_users(user),
            "post_entries": can_write(user),
        },
    }
