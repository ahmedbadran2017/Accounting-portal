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

# ── Server-side guards on core doctypes ──
# FX guard: rejects purchase documents whose exchange rate is implausible vs the
# books' Currency Exchange reference (the root cause of the ×4.5 inventory-cost
# inflation — USD receipts saved at the TRY rate). Runtime-togglable
# (ap_fx_guard / ap_fx_guard_tolerance defaults) — see api/fx_guard.py.
doc_events = {
    "Purchase Receipt": {
        "validate": [
            "accounting_portal.api.fx_guard.validate_fx",
            # stock may not arrive at no cost — OFF by default, see stock_guard
            "accounting_portal.api.stock_guard.validate_purchase_receipt",
        ],
    },
    "Purchase Invoice": {
        "validate": [
            "accounting_portal.api.fx_guard.validate_fx",
            # new freight bills must debit 153.03 (clearing), not the 770.07
            # P&L family — see api/landed_guard.py (runtime-togglable)
            "accounting_portal.api.landed_guard.validate_landed_account",
        ],
    },
    "Stock Entry": {
        "validate": "accounting_portal.api.stock_guard.validate_stock_entry",
    },
}
