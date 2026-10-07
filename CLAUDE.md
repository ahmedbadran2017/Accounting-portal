# Justyol Accounting Portal — read this first

A Frappe app (`accounting_portal`) that serves a Vue 3 SPA at `/accounting/*` on the Justyol ERPNext
instance (`admin.justyol.com`). The accounting team does its daily work here instead of the ERPNext Desk:
sales/COD, purchases and bills, banking and COD remittances, payroll, journals, reports, and an AI auditor.

The books cover 4 companies:

| Company | Currency | Role |
|---|---|---|
| **Justyol Morocco** | MAD | The only sales entity |
| **Maslak LTD** | TRY | Sourcing in Türkiye |
| **Justyol China** | USD | Sourcing hubs |
| **Justyol Holding** | USD | Consolidation |

The business is cross-border cash-on-delivery e-commerce: Shopify orders, delivered and collected by the
carrier Cathedis (spelled `Cathadis` in account names).

Deeper reference:

| File | What it holds |
|---|---|
| `docs/PROJECT_MAP.md` | Accounting model, key accounts, document cycle |
| `docs/BLUEPRINT.md` | Screen plan |
| `docs/PRICING_CHAIN.md` | Pricing chain |
| `DEPLOY.md` | How the app is installed |
| `docs/DEPLOY_SMOKE_TEST.md` | Checks to run after a deploy |

`README.md` is out of date: it describes the June 2026 skeleton.

## Layout
- `accounting_portal/api/*.py` — about 65 modules of `@frappe.whitelist()` endpoints. Key shared modules:
  - `permissions.py` — `assert_portal_access`, role gates.
  - `_actions.py` — the audited write gateway (`execute`, `digest`, approval gate).
  - `_cache.py` — redis cache. Every new prefix must be registered in `_PREFIXES`.
  - `_paginate.py` — server-side pagination.
- `accounting_portal/hooks.py`:
  - route rules
  - `before_request` → `deskguard.block_desk_for_accountants`
  - `doc_events`, `scheduler_events`
- `accounting_portal/accounting_portal/doctype/` — two doctypes:
  - `Accounting Portal Action` — the audit log of every portal write
  - `Bank Statement Import AP`
- `accounting_portal/patches/` + `patches.txt`.
- `frontend/` — Vue 3 + Vite + Tailwind + vue-i18n.
  - Locales: `src/locales/{en,ar,fr}.json`. Arabic is RTL. All three must stay in parity.
  - Navigation: `src/data/nav.js`.
  - Pages: `src/pages/<module>/`. Shared pieces: `src/components/`, `src/composables/`.

## Build, run, deploy
- Dev: `cd frontend && npm i && npm run dev` → `http://localhost:8090/accounting`.
  - `/api` is proxied to `admin.justyol.com`; set `VITE_PROXY_TARGET` to change it.
  - Restart the dev server after editing `tailwind.config.js`.
- **The built bundle is committed.** Run `npm run build` and commit `accounting_portal/public/*` in the same
  commit as the source change (see any recent commit).
- **Deploy is done by the owner, not by you.** He runs a script on the server: git pull, build, then bench
  migrate.
  - Python changes need a **docker-level restart**. Gunicorn runs with `--preload`, so `bench restart` does
    nothing.
  - Hook changes also need `frappe.clear_cache()`.
  - There is no SSH. Never handle the GitHub token.
- Several containers each hold their own copy of the app. A fix applied inside one container is not live in
  the others.
- If `bench migrate` hangs on "Updating DocTypes", an idle DB connection (usually the Shopify sync) holds a
  metadata lock. Find it in `information_schema.processlist` and `KILL` it.

## Hard rules (each one was learned from a real incident)
1. **PROD is live money.**
   - `22f16c59…` = DEV (`admin-dev`). `959bbd5d…` = PROD.
   - If you have the ERPNext MCP tools, every write through `run_python_code` / `run_database_query` on
     PROD **commits**. There is no dry-run.
   - Preview by computing and printing. Write only after the owner explicitly says to apply.
2. **Idempotency:** never use `frappe.generate_hash` for a key. It is random and ignores its input. It
   silently disabled every dedupe guard, and a month's salaries were paid twice. Use `_actions.digest()`.
3. **Writes go through `_actions.execute(...)`.** It logs to `Accounting Portal Action` and dedupes.
   - Material actions can require a second approver. The gate is toggled at runtime (`ap_require_approval`)
     and is currently OFF.
4. **No fabricated data.** A failed load shows "Load failed" and an empty value, never a sample figure.
   `liveOrSample` keeps only the *shape* of its fallback (`blankLike`).
5. **SQL:**
   - Always filter `is_cancelled = 0` on GL and Stock Ledger entries.
   - Never wrap a date column in `YEAR()` or `MONTH()` inside a `WHERE`; use `BETWEEN`.
   - Do not scan `tabComment` (3M+ rows).
   - `tabToDo` has no index on `allocated_to`.
   - Account names contain dots, which break Frappe's General Ledger report. Query `tabGL Entry` directly.
6. **Indexes:** `bench migrate` drops any single-column index whose field has `search_index=0`.
   - Single-column: set the property setter (`search_index=1`) instead of using `ALTER TABLE`. See
     `patches/v2_index_amended_from.py`.
   - Composite indexes survive.
7. **Frontend production build:**
   - `App.vue` must keep a **single root node**. A fragment root crashes only in production.
   - The bundle is served with an mtime cache-buster (`?v=`). Do not switch to hashed chunk names that the
     shell cannot find.
8. **Users and roles:** never `user.save()` to change roles.
   - A Role Profile wipes the roles.
   - The ERPNext Employee hook creates an "apply to all" Employee User Permission, which broke payroll
     generation.
   - Use `deskguard.set_marker()`, which writes `Has Role` rows directly.
9. **Desk lock** (`deskguard.py`):
   - Accountants with the `Portal Only` marker are bounced from `/app` to a logged 60-minute pass.
   - `Desk Blocked` is a hard lock with no pass.
   - Never `raise frappe.Redirect` in `before_request`; raise a werkzeug `HTTPException(response=redirect(...))`.
   - Don't lift the lock to work around a missing screen. Build the screen. The logged passes are the
     backlog.
10. **Fixing posted documents:**
    - If only the account is wrong (2026, small count): edit the lines, then run a
      `Repost Accounting Ledger`. No correction journal entries.
    - If the amount or party is wrong: cancel and amend.
    - 2025 is closed: leave it.
11. **Bills:** vendor bills are Purchase Invoices, not journal entries.
    - Bill from the **receipt**, not the PO rate.
    - A guard refuses receipt lines whose rate is far above stock valuation (`540af55`).

## UI conventions (from the September 2026 restructure)
- Say each fact once. `DocHeader` holds the id, party, date, status and the one key number. Everything
  else goes in a `FactCard`, which hides empty rows.
- The action sits on the document (for example, `PayBillModal` is shared).
- The sidebar is the only navigation. Nothing in the menu leads to a placeholder.
- Use the shared helpers: `routeForDoc()`, `StatusPill`, `LiveBadge`, `UiButton`.
- Money is shown large and counts small.
- Arrow icons point right: back is `rotate-180 rtl:rotate-0`, next is `rtl:rotate-180`.
- Reports show revenue **VAT-inclusive** (what the customer paid). Only VAT actually paid is a cost line.

## Accounting facts the code depends on
- Since June 2026, a delivered Sales Order can show `per_billed` = 83.33% even though its invoice exists:
  the invoice links through the Delivery Note. To check whether an order is invoiced, look via the SO **or**
  the DN.
- Salary slips are multi-currency (MAD/TRY/USD/EGP). Sum `base_gross_pay`, never `gross_pay`.
- Payroll payable accounts must stay **untyped**.
  - Never set an account type on a clearing account. Typing the Cathadis clearing account as Receivable
    once dropped 787 payment legs.
- `Cathadis Transactions` (108.021.003) is the COD clearing account. Payment Entries debit it; the bank
  journal entry per remittance batch credits it.
- Maslak's Türkiye revenue is intercompany paper. Group reports eliminate it.
  - In `group_pnl.py`, an expense counts as intercompany only if its name contains "intercompan" or
    "internal invoic".

## Recent history (newest first, all deployed as of 6 Oct 2026)
- `bf19304` Clear P&L page (`api/clear_pnl.py`, `pages/reports/ClearPnl.vue`).
  - Periodic method: sales − (opening stock + purchases + freight − closing stock) − expenses.
- `d1e4a24` Group P&L stopped dropping Türkiye's office rent as intercompany.
- `252ef1f` / `984acfa` / `82ddcf9` / `173bbbe`:
  - search by bare Shopify number
  - SO↔PO links
  - advance payments shown on the order
- `30acaf7` Payroll sheet stopped double-counting overtime and lateness against Adjustments.
- `725ec09` Re-keying a cancelled pay adjustment no longer silently dedupes (`_fresh_adj_key`).
- `6db99de` Desk hard lock (`Desk Blocked`); the lock now survives Role Profiles.
- `3c31d0a` VAT-inclusive revenue across the portal.
- Late Sept: a payroll cycle rebuilt around the team's own sheet model:
  - approving a month creates Additional Salary
  - advances settle through `ref_doctype`
  - pay is capped at the ledger
- Mid Sept: the idempotency fix (`a1da8f5`), the UI restructure, ⌘K search (31 ms), the draft editor and
  redate (`api/docedit.py`), and the performance waves.

## Known open work (code side)
- **Duplicate sales invoices:** 2,469 Sales Invoices for Justyol Morocco in 2026 (mostly Jan and Apr) are
  exact copies created twice, and each copy has its own Cathedis Payment Entry (≈441K MAD).
  - Cancellation is **pending the owner's go-ahead**: cancel the Payment Entry first, then the invoice.
  - Find out which bulk path created them and make sure it is now covered by `_actions.digest`.
- **Missing COD collection Payment Entries.** Some cash reached the bank with no invoice matched to it. It
  shows once the duplicate copies are gone. This is the "Cathedis close" feature (`api/cod_close.py`).
- Clear P&L classifier: in `_cat()`, `770.012.*` subscriptions match the `770.01` premises prefix. Make
  the prefix match exact.
- `admin.justyol.com/pnl-2026` (an older page that lives outside this app) disagrees with Clear P&L. Retire
  it or repoint it.
- The never-need-ERPNext backlog:
  - creating POs, Delivery Notes and bills from scratch
  - FX revaluation, opening balances, period lock
  - the Item master

## Working style the owner expects
- Commit messages are one plain sentence about the user-visible effect (see `git log`), ending with a
  `Co-Authored-By:` trailer when an AI wrote it.
- Run `git pull --rebase` before you push; more than one session pushes to `main`.
- Verify against real PROD data, read-only, before claiming something works. Measure performance instead
  of guessing.
- The team works in Arabic and French. The UI must keep EN, AR (RTL) and FR in parity.
