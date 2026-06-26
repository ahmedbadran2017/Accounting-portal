# Deploy & Smoke-Test Runbook

Covers the batch built in the CFO Control Tower push (audit fixes A/B/C, dashboard
date-filter + perf, Items & margin, Banking COD-recon, AI auditor chat,
consolidation, cash forecast). Everything is committed + pushed.

## 1. Deploy

No new DocTypes and no schema changes were added in this batch — every new
endpoint is auto-whitelisted by module path, so **no `bench migrate` is required**.

```bash
# on the bench host, as the frappe user
cd ~/frappe-bench
git -C apps/accounting_portal pull          # pull the committed code
bench build --app accounting_portal          # rebuild the Vue bundle (or copy the committed bundle)
bench --site <site> clear-cache
bench restart                                # reload the Python workers
```

> If you deploy the committed bundle directly (instead of `bench build`), make sure
> the fixed-name JS/CSS in `accounting_portal/public/` matches the latest commit so
> the browser cache-busts (see the prod-gotchas note).

Config already in place (no action needed): `anthropic_api_key` is set in
`site_config.json` — the AI auditor uses it. To change the model, set
`auditor_model` (default `claude-sonnet-4-6`).

## 2. Smoke test — in priority order

Do these on **admin-dev first**, then prod. Each line is one check.

### A. AI auditor chat (the only path not exercisable offline)
- [ ] Copilot → ask "what's the biggest issue?" → answer cites real figures
      (≈686M stock, −2.85M debtors…) and a next action.
- [ ] Ask "how much exposure?" → ≈693M MAD high-severity.
- [ ] If answers look generic/templated, the Claude call failed and it fell back to
      the rule responder — check `bench --site <site> console` logs for "AI Auditor"
      error entries (bad key/model/network). The chat still works either way.

### B. Inventory correcting-entry generator (gated write)
- [ ] Items → "Propose correcting entry" → modal shows Dr 71.004 / Cr 153.01
      ≈680,873,788, stock-after ≈3.75M.
- [ ] Toggle offset to COGS 71.801 → line 2 account switches.
- [ ] Submit → toast "Sent for approval" (NOT "Posted" — 680M is above the
      material threshold). Verify an `Accounting Portal Action` row is **Proposed**,
      and **no Journal Entry posted yet**. Approve only when you actually intend to.

### C. Banking — COD remittance + match (gated write)
- [ ] Banking → COD remittance → 223 batches load with expected/collected/variance.
- [ ] Open a batch → orders ‖ deposits reconcile; variance ties.
- [ ] Variance queue → Match on an unallocated receipt → pick invoice → Reconcile →
      toast; verify the receipt's unallocated amount dropped (or it's Proposed if
      material). Test on a small receipt first.

### D. Items & margin
- [ ] Items list → real SKUs, cost, Sell/Landed/COD-fee/RTO/True-margin columns.
- [ ] A high-RTO SKU (e.g. FR2817) shows true margin well below gross.
- [ ] Open an item → prices across lists + stock + recent purchases.
- [ ] Price lists → 8 real lists; open Morocco → 27k prices.
- [ ] Landed cost → 19 vouchers; open MAT-LCV-2026-00018 → freight/customs/duties
      split (Arabic descriptions classified) + per-item allocation.
- [ ] "+ Set price" → search item, pick list, save → price persists (reversible).

### E. Consolidation
- [ ] Switch entity to **Justyol Holding** (group) → Consolidated view: 4 entities
      translated to USD, group ≈$73M assets / $70.5M net, distortion banner shown.

### F. Cash forecast
- [ ] Reports → Cash forecast → 7-day liquidity banner (red — bills 7.3M vs cash
      675K), 30-day projection negative, component cards real.

### G. Dashboard (perf + date filter)
- [ ] Dashboard loads fast (cached cockpit, was ≈8s) and the date-preset chips
      (This month default) re-scope the flow metrics; balances stay put.
- [ ] Alerts feed shows **Live** badge (not the old fake 676M fixtures); command
      strip shows collected-today / approvals / AR-AP aging.

### H. Cross-cutting (from the audit)
- [ ] Sales → Delivery challans + Returns + To-bill tabs all load (were dead).
- [ ] Any detail page with a bad/old `?id` redirects to its list (self-heal).
- [ ] Live/Sample badges are localized in AR/FR.

## 3. If something breaks

- A 404/`MethodNotFound` on an `accounting_portal.api.*` call → the restart didn't
  pick up the new module; re-run `bench restart`.
- A blank screen in prod → stale bundle; rebuild/copy + hard refresh (cache-bust).
- A gated write posts directly when it should be Proposed → check `MATERIAL_THRESHOLD`
  in `api/_actions.py`.

## 4. Known-not-built (intentional)

- Item create / Landed-Cost-Voucher create (Shopify-synced / ERPNext-owned).
- Intercompany eliminations + FX-revaluation journals (surfaced as balances/notes).
- GRNI-clearing + Correction-pile (71.999) triage workbenches (Phase 5 extensions).
- Bank rules tab (removed — no live data).
