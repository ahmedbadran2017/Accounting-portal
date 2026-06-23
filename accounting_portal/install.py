"""Install / migrate hooks for the Accounting Portal.

Creates the portal-only role hierarchy. Roles are portal-only (desk_access=0)
so accounting-team members log into the SPA, not the ERPNext desk.

Role hierarchy (broadest → narrowest):
    Accounting Super Admin  — full access + manage portal users/roles
    Accounting Admin        — full access, cannot manage users
    Accountant              — operational: AP/AR, journal entries, reconciliation
    Accounting Viewer       — read-only dashboards & reports (management/owners)
"""
import frappe


# Order matters: broadest first. Mirrored in accounting_portal.api.permissions.
PORTAL_ROLES = [
    "Accounting Super Admin",
    "Accounting Admin",
    "Accountant",
    "Accounting Viewer",
]


def after_install():
    _create_portal_roles()


def _create_portal_roles():
    """Create the 4 accounting portal roles. Idempotent — safe on every migrate."""
    created = []
    for role_name in PORTAL_ROLES:
        if not frappe.db.exists("Role", role_name):
            frappe.get_doc({
                "doctype": "Role",
                "role_name": role_name,
                "desk_access": 0,   # portal-only; no ERPNext desk
                "restrict_to_domain": "",
            }).insert(ignore_permissions=True)
            created.append(role_name)
    if created:
        frappe.db.commit()
        print(f"Accounting portal roles created: {', '.join(created)}")
