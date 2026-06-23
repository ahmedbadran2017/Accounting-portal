# Deploying the Accounting Portal (JoyAgent Books)

The portal is a Frappe app (`accounting_portal`) that serves a pre-built Vue SPA
at `/accounting/*`. The built bundle is committed, so the production bench does
**not** need Node — it only installs the app and runs migrate.

## 0. One-time: push this app to a Git repo
The server pulls the app with `bench get-app <url>`, so it must be on Git first.

```bash
cd /Users/ahmedbadran/Accounting/accounting_portal
# (already a git repo with a first commit — see below)
git remote add origin git@github.com:ahmedbadran2017/accounting_portal.git
git push -u origin main
```

## 1. Rebuild the SPA before every deploy commit
Whenever frontend code changes, rebuild and commit the bundle:

```bash
cd /Users/ahmedbadran/Accounting/accounting_portal/frontend
npm install            # first time only
npm run build          # emits ../accounting_portal/public/{app.js,app.css,assets/}
cd ..
git add -A && git commit -m "build: refresh SPA bundle"
git push
```

(Or run `./deploy.sh` from the repo root, which does build + commit + push.)

## 2. Install on the ERPNext bench (run on the server)
```bash
cd ~/frappe-bench                         # your bench directory
bench get-app accounting_portal https://github.com/ahmedbadran2017/accounting_portal
bench --site admin.justyol.com install-app accounting_portal
bench --site admin.justyol.com migrate    # creates the 4 portal roles
bench --site admin.justyol.com clear-cache
bench restart                             # or: sudo supervisorctl restart all
```

## 3. Updating an already-installed app
```bash
cd ~/frappe-bench/apps/accounting_portal && git pull
cd ~/frappe-bench
bench --site admin.justyol.com migrate
bench --site admin.justyol.com clear-cache
bench restart
```

## 4. Give your team access
The app creates four **portal-only** roles on install/migrate:

| Role | Who | Sees |
|------|-----|------|
| `Accounting Super Admin` | finance lead | everything + manage users |
| `Accounting Admin` | senior accountants | everything |
| `Accountant` | accounting team | AP/AR, journals, reconciliation |
| `Accounting Viewer` | owners / management | read-only · lands on **Consolidated** |

For each user: **User → Roles** → add one of the above. Then they log in at:

```
https://admin.justyol.com/accounting
```

The login uses ERPNext's standard auth; the role decides the landing entity
(Viewer → Holding/Consolidated, everyone else → Justyol Morocco).

## Notes
- The dashboards currently show the **June-2026 snapshot** from the design
  handoff. Wiring each screen to live ERPNext queries is the next phase; the
  backend endpoints (`accounting_portal/api/dashboard.py`) are already scaffolded
  and read real GL data (`get_overview`, `get_recent_entries`).
- The AI Auditor chat returns canned context-aware replies until the Claude API
  is connected.
