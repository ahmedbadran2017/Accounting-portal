# Justyol Accounting Portal

A standalone internal accounting portal for Justyol — a **Frappe custom app** (`accounting_portal`) serving a **Vue 3 SPA** at `/accounting/*`, built on the exact same architecture as the Supplier Portal.

It reads live data from the existing ERPNext instance (4 companies: Justyol Holding, Justyol China, Maslak LTD, Justyol Morocco) and presents multi-company AP / AR / General Ledger / reporting to the internal accounting team and management.

## Architecture

| Layer | Path | Purpose |
|-------|------|---------|
| Routes | `accounting_portal/hooks.py` | `website_route_rules` mount the SPA at `/accounting/*` |
| SPA shell | `accounting_portal/www/accounting.html` | Loads the built Vite bundle, hides Frappe chrome |
| API | `accounting_portal/api/*.py` | `@frappe.whitelist()` endpoints, role-gated |
| Roles | `accounting_portal/install.py` | Portal-only roles created on install/migrate |
| Frontend | `frontend/` | Vue 3 + Vite + Tailwind + frappe-ui + vue-i18n (EN/AR) |

### Roles
- **Accounting Super Admin** — full access + manage portal users/roles
- **Accounting Admin** — full access, no user management
- **Accountant** — operational (AP/AR, journal entries, reconciliation)
- **Accounting Viewer** — read-only dashboards & reports (management/owners)

## Backend endpoints (so far)
- `accounting_portal.api.auth.get_session_info` — session context for the SPA
- `accounting_portal.api.permissions.whoami` — role + capabilities
- `accounting_portal.api.dashboard.get_overview` — per-company receivable / payable / cash & bank / YTD P&L
- `accounting_portal.api.dashboard.get_recent_entries` — recent GL feed

All GL queries filter `is_cancelled = 0` and scope to the user's allowed companies.

## Local development
```bash
cd frontend
npm install
# Proxies /api to admin.justyol.com by default. Override for a local bench:
#   VITE_PROXY_TARGET=http://localhost:8000 npm run dev
npm run dev          # http://localhost:8090/accounting
```
The SPA renders without a backend (login page); live data needs a reachable ERPNext.

## Deploy (to the ERPNext bench)
```bash
# 1. Build the SPA → emits accounting_portal/public/{app.js,app.css,assets/}
cd frontend && npm run build

# 2. On the server: install the app into the bench, then migrate
bench get-app accounting_portal <repo-url>
bench --site <site> install-app accounting_portal
bench --site <site> migrate          # creates the 4 roles
bench build --app accounting_portal
bench --site <site> clear-cache
```
Then assign one of the accounting roles to each team member's User and they can log in at `https://<site>/accounting`.

## Status
Foundation/skeleton complete: auth, role gating, layout, i18n (EN/AR + RTL), build pipeline, and a live multi-company dashboard. AP / AR / General Ledger / Reports pages are stubbed (`ComingSoon`) pending the agreed design.
