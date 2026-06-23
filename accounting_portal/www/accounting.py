import os

import frappe

no_cache = 1


def get_context(context):
    context.no_cache = 1
    # Cache-bust the (fixed-name) Vite bundle: the HTML is no_cache, but it
    # points at /assets/accounting_portal/app.js which browsers/CDNs cache hard.
    # Stamp the URL with the bundle's mtime so every rebuild serves a fresh URL.
    try:
        app_js = frappe.get_app_path("accounting_portal", "public", "app.js")
        context.asset_version = int(os.path.getmtime(app_js))
    except Exception:
        context.asset_version = frappe.utils.cint(frappe.utils.now_datetime().timestamp())
    return context
