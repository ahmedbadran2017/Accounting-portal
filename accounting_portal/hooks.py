app_name = "accounting_portal"
app_title = "Accounting Portal"
app_publisher = "Justyol"
app_description = "Internal accounting portal for Justyol (multi-company AP/AR/GL)"
app_email = "info@justyol.com"
app_license = "MIT"

# ── Website route rules — serve the Vue SPA for every /accounting/* path ──
# Mirrors the supplier_portal pattern: a single built bundle answers all
# client-side routes. Without these, Frappe matches no route for deep links
# like /accounting/payables and renders its own 404 before the SPA boots.
website_route_rules = [
    {"from_route": "/accounting/<path:app_path>", "to_route": "accounting"},
    {"from_route": "/accounting", "to_route": "accounting"},
]

# This is an INTERNAL portal — no guest-accessible endpoints. Authentication
# uses Frappe's standard /api/method/login. Every api.* method is gated by a
# portal-role check (see accounting_portal.api.permissions).
guest_methods = []

# ── Install / Migrate hooks ──
after_install = "accounting_portal.install.after_install"
after_migrate = [
    # Idempotent — safe to run on every migrate.
    "accounting_portal.install._create_portal_roles",
]

# Whitelisted method overrides — none.
override_whitelisted_methods = {}
