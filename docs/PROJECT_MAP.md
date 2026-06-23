# Justyol Accounting Portal — Complete Project Map

> The single reference for the whole system: the real ERPNext accounting model
> (documents, accounts, GL impact, cycles), the live data reality, and the
> portal that mirrors and operates it. Figures validated on `admin-dev` (Justyol
> Morocco) June 2026.

---

## 0. System overview

- **Business**: cross-border COD (cash-on-delivery) e-commerce. Source in Türkiye + China (USD/TRY), sell in Morocco (MAD) via Shopify/YouCan, deliver + collect cash through carriers (mainly **Cathadis**).
- **Entities (4 companies)**: Justyol Holding (consolidated, USD), **Justyol Morocco** (sales engine, MAD), Maslak LTD (Türkiye sourcing, TRY), Justyol China (USD). China sits outside the Holding tree.
- **Currencies in the books**: MAD (base for Morocco), USD, TRY, EUR, EGP.
- **Users / roles** (portal-only, desk_access=0): `Accounting Super Admin`, `Accounting Admin`, `Accountant`, `Accounting Viewer`. Created by `install.py`; gated by `api/permissions.py`.
- **Environments**: `22f16c59…` = DEV (`admin-dev.justyol.com`), `959bbd5d…` = PROD (`admin.justyol.com`). Near-identical clones; distinguish by the `accounting_portal` install footprint.

---

## 1. Chart of accounts (≈826 accounts)

| Root type | Accounts | Groups |
|---|---|---|
| Expense | 294 | 60 |
| Asset | 236 | 90 |
| Liability | 202 | 76 |
| Equity | 67 | 8 |
| Income | 27 | 11 |

Account names are dotted codes (e.g. `120.01`). **Dots break Frappe's GL report `parse_json`** → always use raw GL Entry SQL. Always filter `is_cancelled = 0`.

### Key control / clearing accounts (Justyol Morocco, live balances)

| Account | Role | Balance (MAD) |
|---|---|---|
| `153.01 Türkiye Purchases Stock in Hand` | Inventory on hand | **+685.6M** ⚠ |
| `71.004 Stock Adjustment` | P&L stock-adj sink | **−680.9M** ⚠ |
| `600.002 Good Sales at Morocco` | Revenue | −21.27M |
| `71.801 Cost of Goods Sold` | COGS | +11.24M |
| `321.01 Stock Received But Not Billed` | GRNI | −4.72M |
| `71.999 Correction Need Income` | Unreconciled corrections | **+3.69M** ⚠ |
| `600.998 Morocco Other Sales (incl VAT)` | Revenue | −3.14M |
| `120.01 Debtors` | Receivables | **−2.85M** ⚠ |
| `320.101 Creditors USD` | USD payables | −2.77M |
| `770.07.004 Cathadis Cargo Fee` | Last-mile cost | +2.08M |
| `770.07.801 Danish Sea Freight` | Inbound freight | +1.93M |
| `191.020 VAT 20%` | VAT output | +1.91M |
| `108.021.003 Cathadis Transactions` | **COD collection clearing** (Bank) | — |
| Bank accounts (all) | Liquidity | +1.52M |
| Cash accounts (all) | Liquidity | **−0.85M** ⚠ (overdraft) |

**Cash on hand (Bank+Cash) = 675K MAD.**

---

## 2. Document types (the cycle, with real volumes)

Volumes = submitted docs, Justyol Morocco.

| Doctype | Volume | Purpose |
|---|---|---|
| Sales Order | **226,493** | The COD order (Shopify/YouCan). Carries the whole lifecycle. |
| Delivery Note | **102,314** | Challan — carrier dispatch + tracking. |
| Payment Entry | **52,684** | COD receipts (Cathadis) + supplier payments. |
| Sales Invoice | **48,839** | Revenue recognition (VAT 20%) on delivery. |
| Stock Entry | 6,297 | Inventory moves / adjustments. |
| Purchase Order | 5,873 | Sourcing PO (TR/CN). |
| Purchase Receipt | 5,312 | Goods received (GRN). |
| Journal Entry | 1,697 | Accruals, corrections, FX, reclass. |
| Purchase Invoice | 719 | Supplier bill. |
| Expense Claim | 0 | Not used. |

### 2.1 Sales Order — the COD spine

- **Standard fields**: customer, transaction_date, grand_total, net_total, total_taxes_and_charges, discount_amount, status, delivery_status, billing_status, per_delivered, per_billed, advance_paid, currency, territory.
- **COD custom fields** (the operational + attribution layer):
  - Lifecycle: `custom_sales_status`, `custom_logistics_status`, `custom_track_shipment_status`, `custom_cancellation_reason`, `custom_allocated_to` (the agent), `custom_first_reminder`, `custom_second_reminder`.
  - Shipping: `custom_tracking_company` (carrier), `custom_tracking_number`, `custom_awb`, `custom_tracking_url`, `custom_label_url`, `custom_expected_ship_date`, `custom_shipping_city`, `custom_shipping_governorate`, `custom_shipping_phone`, `custom_customer_phone`, `custom_shipping_address_json`.
  - Attribution (≈98% empty — unreliable): `custom_channel`, `custom_youcan_order_id`, `custom_utm_source/medium/campaign/content`, `custom_ad_campaign`, `custom_whatsapp_campaign`.
  - Commercial: `custom_payment_collection`, `custom_margin`, `custom_margin_applied`, `custom_customs_value`, `custom_international_shipping_order`, dropship fields, `custom_is_from_sales_exchange`.
- **Portal state machine** (`api/sales._order_state`): placed → confirmed → transit → delivered → settled (+ cancelled, undelivered). Derived from sales/logistics/track status + status.
- **June actuals**: 7,553 orders · GMV 1.53M · AOV 202 · 4,092 pending (54%) · 2,779 delivered (37%) · realised 548K · 92 returns.

### 2.2 Delivery Note (challan)
Fields: customer, status, `custom_tracking_company`, `custom_tracking_number`, `custom_track_shipment_status`, `custom_logistics_status`, `custom_tracking_url`, territory. **No shipping city field.**

### 2.3 Sales Invoice
Fields: customer, posting_date, net_total, total_taxes_and_charges (VAT 20%), grand_total, outstanding_amount, status. Lines → `Sales Invoice Item` (item_code, item_name, qty, rate, amount) → `Item.image` (Shopify CDN / `/files/`). **SI returns = 0** (returns live on the order, not as SI credit notes).
- **GL on submit**: Dr `120.01 Debtors` (gross) / Cr revenue (net) + Cr `191.020 VAT` (tax).

### 2.4 Payment Entry
Fields: party_type/party, payment_type (Receive/Pay), paid_amount, unallocated_amount, mode_of_payment, reference_no, posting_date, references (→ invoices). COD receipts come via `mode_of_payment = "Cathadis Transactions"` (4,629 / 866K in June = 98.9%).
- **GL on submit (Receive)**: Dr Bank/Cash clearing / Cr `120.01 Debtors`. Unallocated → debtor credit balance.

### 2.5 Purchase Order → Goods Receipt → Purchase Invoice
3-way match: PO (commitment) → GRN (Dr Stock/GRNI) → Bill (moves GRNI → Creditors). Portal `get_bill` reads the match legs from the PI items' `purchase_order` / `purchase_receipt` links.

### 2.6 Journal Entry
Fields: company, posting_date, voucher_type, user_remark, multi_currency, accounts[] (account, debit/credit_in_account_currency, party_type, party). The accountant's universal tool — accruals, corrections, FX, reclass.

---

## 3. The accounting cycles

### 3.1 Revenue · COD
`Sales Order → Delivery Note → Sales Invoice → Payment Entry (Cathadis) → reconciliation`.
GL: invoice Dr Debtors / Cr Revenue+VAT; receipt Cr Debtors. Revenue recognised on delivery.

### 3.2 Procurement
`Purchase Order → Goods Receipt → Purchase Invoice → 3-way match → supplier payment`.
GL: GRN Dr Stock / Cr GRNI; bill Dr GRNI / Cr Creditors; payment Dr Creditors / Cr Bank.

### 3.3 Inventory & COGS
Stock Entry moves + valuation; COGS should relieve stock on delivery. Landed cost = inbound freight (`770.07.801`, `770.07.004`) + duty + FX allocated to SKUs.

### 3.4 GL & adjustments
Journal Entries for accruals/corrections/FX. FX uses the Currency-Exchange stored-rate workaround (see memory `fx-corrections`).

### 3.5 Banking & cash; close & reporting
Bank/Cash accounts, payment reconciliation, bank rec; Trial Balance → P&L / Balance Sheet / Cash Flow; period close.

---

## 4. The pathologies (why the portal is a control tower)

1. **Inventory/COGS broken**: `153.01` +685.6M stock vs `71.004` −680.9M adjustment; stock-adjustment P&L 677.8M vs revenue 7.81M → margin unmeasurable ("margin 0 of 7,697").
2. **Negative book gross margin**: revenue 7.81M vs COGS 10.5M.
3. **Unmatched COD debtors −2.85M**: 1,079 receipts hold 3.51M unallocated vs only 265 open invoices (114K). Cash collected without matching invoices (bulk Cathadis remittances on the aggregate customer).
4. **GRNI −4.72M**: purchases received not billed.
5. **"Correction Need" +3.69M**: a literal correction pile.
6. **Negative cash −845K**; **USD creditors 2.77M** FX exposure.
7. **Carrier not a GL dimension**: 98.9% via one Cathadis clearing account → can't sub-ledger per carrier.

---

## 5. Portal architecture

### 5.1 Backend (Frappe app `accounting_portal`, 11 API modules · 43 endpoints)

- `api/permissions.py` — roles, `resolve_companies`, `assert_portal_access/can_write`, `whoami`. Entity scoping for every endpoint.
- `api/_actions.py` — **write gateway**: capability check + idempotency (`dedupe_key`) + audit (`Accounting Portal Action` doctype) + propose→approve→post gate (material ≥10k → distinct approver). `register_poster`, `execute`, `approve_action`, `reject_action`, `list_actions`. Posters lazy-bootstrapped.
- `api/dashboard.py` — `get_cod_cockpit` (cash on hand, collected/paid MTD, AR/AP, channels, daily flow), `get_overview`, `get_recent_entries`.
- `api/sales.py` — `orders_summary`, `list_orders`, `get_order` (+items+images), `list_invoices`, `get_invoice` (+lines+images), `list_challans` + `challans_summary`, `list_receipts`, `list_credits`.
- `api/customers.py` — `list_customers` (ranked by delivered value, cached), `get_customer`, `create_customer`.
- `api/purchases.py` — `list_bills`, `get_bill` (3-way match).
- `api/reconciliation.py` — `cod_summary`, `unmatched_payments`, `open_invoices`, `match_candidates`, `list_accounts`.
- `api/ledger.py` — `general_ledger`, `trial_balance`, `chart_of_accounts`, `pending_journals`.
- `api/accountant.py` — **`create_journal_entry`** (post via gateway), `account_options`.
- `api/auth.py` — `get_session_info`.
- New doctype: `Accounting Portal Action` (audit trail).

### 5.2 Frontend (Vue 3 SPA · 38 pages · 12 composables)

- Shell: `App.vue` (single root — prod requirement), `AppLayout.vue` (sidebar, entity switcher, header), `Module.vue` dispatch, `ScaffoldTable.vue` (config-driven live tables w/ insights + search + clickable rows).
- Modules/pages: Dashboard · Sales (Orders/Customers/Invoices + details, challans/receipts/payments/credits) · Purchases (Vendors/Bills+detail) · Banking (Remittance/Variance/Aging/BankRec) · Accountant (Journals/COA/GL/TrialBalance/FixedAssets/PeriodClose) · Items (Items/LandedCost) · Reports · Settings · Copilot · Consolidated.
- Composables: `useLive` (live⇄sample bridge + `currentCompany`), `useDashboard`, `useOrders`, `useInvoices`, `useBills`, `useCustomers`, `useReconciliation`, `useAction`, `useAuth`, `useUi`, `useCreated`, `useToast`.
- Live⇄sample pattern: every screen tries the live endpoint, falls back to a representative June sample, shows a Live/Sample badge. Bundle is fixed-name (`app.js`) + mtime cache-bust.
- Design: terracotta accent `#c4492a`, warm-gray bg, Inter (Latin) + Alexandria (Arabic). Trilingual EN/AR-RTL/FR.

---

## 6. Doctype ↔ portal mapping + status

| ERPNext | Portal screen | Read | Operate (write) |
|---|---|---|---|
| Sales Order | Sales · orders (+detail, CFO strip, products) | ✅ live | ⏳ confirm / actions |
| Delivery Note | Sales · challans (insights + track) | ✅ live | ⏳ |
| Sales Invoice | Sales · invoices (+detail, products) | ✅ live | ⏳ create |
| Payment Entry | Sales · receipts / payments; Banking | ✅ live | ⏭️ **record (next)** |
| Payment recon | Banking · variance (COD cockpit) | ✅ live | ⏳ match write-back |
| Customer | Sales · customers (+detail) | ✅ live | ✅ create |
| Purchase Invoice | Purchases · bills (+detail, 3-way) | ✅ live | ⏳ |
| Purchase Order / GRN | Purchases | ⏳ | ⏳ |
| Journal Entry | Accountant · journals | ✅ live | ✅ **create + post** |
| Bank/Cash accounts | Banking · accounts | ✅ live | — |
| GL / Trial balance | Accountant · GL / TB | ✅ live | — |
| Stock / COGS / margin | Items · landed cost | ⏳ | ⏳ correcting entries |
| P&L / BS / Cash flow / Close | Reports / Period close | ⏳ | ⏳ |

Legend: ✅ done · ⏭️ next · ⏳ planned.

---

## 7. Build roadmap (full operation — "the team works from here")

Pattern (proven): **form → write gateway → audit → approval**.

1. ✅ Write gateway + audit (`Accounting Portal Action`).
2. ✅ Journal Entry — create + post (live, audited, currency-guarded).
3. ⏭️ **Payment Entry** — record COD receipt / supplier payment.
4. COD reconciliation write-back — the "Match" button (Payment Reconciliation).
5. Sales Invoice create; Purchase cycle (PO/GRN/Bill) operate.
6. Inventory/COGS: landed-cost + true-margin engine + proposed correcting entries (fix the 685M).
7. GRNI 4.72M clearing workbench; "Correction Need" 3.69M triage.
8. Financial statements (P&L/BS/Cash Flow) + period-close checklist + bank rec.
9. Multi-entity consolidation + intercompany + FX revaluation.
10. Live AI Auditor (controls engine → Claude API narration → drill-to-fix).

### Cross-cutting guarantees
- Every write is **entity-scoped, idempotent, audited**, and material entries need a **second approver**.
- Reads validated against the live DB (MCP) before shipping; deploy only finished work.
- Dev-against-`admin-dev` for fast live iteration; `localhost:8090` for instant UI review.
