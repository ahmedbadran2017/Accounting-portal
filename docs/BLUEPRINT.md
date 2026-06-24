# Justyol Accounting Portal — Master Blueprint

> The definitive screen-by-screen, field-by-field plan. Status: ✅ built · 🔨 to
> build · ⚪ optional · 💠 CFO rec · 🎨 UX rec · `↳` = an ERPNext doctype already
> exists (wire, don't rebuild). Validated on `admin-dev` (Justyol Morocco).

## Build log — 2026-06-24 (overnight)
Shipped + committed + verified (build green, rendered in local preview, data
validated vs admin-dev). **Deploy:** `git pull && bench build` (or symlink the
pre-built `public/app.js|css`) `&& bench --site … clear-cache`.
- ✅ **Sales Order detail** — Customer & shipping, Tracking (+track link),
  Financial (net/VAT/gross/billed/delivered), clickable Related documents.
- ✅ **Reports** — live P&L (with Stock-Adjustment anomaly flagged), balance
  sheet, AR/AP aging (5 buckets), VAT cockpit (output/input/net). `api/reports.py`.
- ✅ **AI Auditor** — `api/auditor.py` controls engine (6 anomaly rules over live
  balances) + Copilot anomaly feed wired live with drill-to-fix.
- ✅ **Payment Entry** — record COD receipts via the gateway (`api/payments.py` +
  PaymentEntryForm). ⚠️ submit path needs one live verification on deploy.
- ✅ **Settings → Activity & audit** — every portal write (Accounting Portal Action).
- ✅ **Inventory health** card on Items — closes the auditor's #1 (685M COGS break).
- ⏳ Next: reusable combobox + loading/empty/error rollout; multi-entity
  consolidation P&L; Sales Invoice create; period-close.

## ✦ AI Auditor & assistant — the intelligent layer
- **1 · Continuous audit (anomaly engine)** 🔨
  - Cash & collection: negative cash overdraft · unmatched COD aging (−2.85M) · revenue-recognition gap (delivered≠invoiced) · unallocated-advance growth
  - Margin & inventory: negative/outlier margin · 685M stock anomaly · GRNI aging (4.7M) · Correction-Need growth (3.69M) · valuation drift
  - Integrity: duplicate orders/payments · VAT output−input mismatch · round/large/backdated/weekend JEs · approval bypass · period-lock breach
  - Carrier & RTO: settlement variance · RTO spike · in-transit cash overdue per carrier
- **2 · Assistant** 🔨 — suggests receipt↔invoice matches `↳ Payment Reconciliation` · runs close · drafts correcting/accrual entries · conversational Q&A (trilingual, live data)
- **3 · Insight (CFO advisor)** 💠 — narrated digest ✅UI (sample) · severity ranking · cash-flow forecast · margin watch by SKU/channel/carrier
- **4 · Act (governed)** 💠 — one-click fix → proposes entry via gateway · human-in-the-loop approval · audit-trail review
- **Engine** — rules (scheduled + on-demand) · findings store · Claude Opus (narration · reasoning · agentic tool-use over read+write endpoints) · guardrails · books-context
- **Surfaces** — dashboard digest banner ✅ · Copilot chat dock · per-screen "ask the auditor" · alerts inbox

## Sales · COD ✅ live
### Sales Order 🔨 partial
- **List** ✅ — insights (GMV·AOV·realised·backlog·RTO) · state funnel (placed→confirmed→transit→delivered→settled) · columns `#order, customer, city, carrier, shipment, state, posting, value` · search+state filter. 🔨 filters (date·carrier·agent) · new · export. 🎨 pagination/virtual scroll (100-cap vs 226K) · bulk · saved filters
- **Details** 🔨 partial
  - Products ✅ `image, item_name, qty, rate, amount`
  - Customer+shipping 🔨 `custom_customer_phone, custom_shipping_phone, custom_shipping_city, custom_shipping_governorate, custom_shipping_address_json`
  - Tracking 🔨 `custom_tracking_company, custom_tracking_number, custom_awb, custom_tracking_url, custom_label_url, custom_expected_ship_date, custom_track_shipment_status`
  - Financial 🔨 `net_total, total_taxes_and_charges (VAT 20%), grand_total, discount_amount, advance_paid, per_billed, per_delivered`
  - Attribution ⚪ `custom_channel, custom_utm_*, custom_ad_campaign, custom_whatsapp_campaign` (≈98% empty)
  - Unit economics 💠 — AOV − COGS − last-mile − RTO
  - Lifecycle timeline ✅ · GL journal (real) ✅ · Related docs 🔨 (Delivery/Invoice/Payment) · Tabs+sticky 🎨
  - Actions 🔨 — confirm · create delivery/invoice · record payment · cancel(reason) · assign agent · note → gateway
- **Create** 🔨 — customer* (combobox 🎨) · items* (search+qty+rate→total+VAT) · shipping (city/gov/phone/carrier) · channel · draft/submit→gateway · inline validation
- GL: on delivery the invoice posts Dr 120.01 Debtors / Cr revenue + Cr 191.020 VAT

### Sales Invoice 🔨 partial
- List ✅ (insights rev·VAT·overdue; `name,customer,net,vat,gross,status`) · Details ✅ (products+images · totals · payment status · GL journal) · related 🔨
- GL: Dr 120.01 Debtors (gross) / Cr revenue (net) + Cr 191.020 VAT 20%
- 💠 payment terms/schedule · tax breakdown · e-invoicing (DGI) · write-off · 🎨 print/PDF · 🔨 create (from order)

### Customer ✅ built
- List (ranked LTV, cached) · Details (header+store credit · stats · 4 connections · contact+segment · activity · ledger) · Create (name·phone·email·city·group)
- 💠 RFM/segment `↳ Customer RFM Score · Customer Segment` · credit control (limit·block overdue) `↳ Dunning`

### Payment / Receipt 🔨 next
- List ✅ `name, party, reference_no, mode_of_payment, paid_amount, posting_date`
- GL (Receive): Dr Bank/Cash clearing / Cr 120.01 Debtors · unallocated→debtor credit
- 🔨 Details (party·allocation·GL·related) · Record (customer·amount·mode·reference·allocate `↳ Payment Reconciliation`→gateway)
- 💠 bank charges/deductions · partial & multi-invoice allocation · customer advances

### Delivery Note 🔨 partial — List ✅ (funnel · track link) · Details/Create 🔨 (from order · carrier+tracking→gateway)
### Credit note · returns 🔨 partial — List ✅ (returned/exception orders) · no SI returns (reversal on order)
### COD analytics 💠 new — per-carrier receivable sub-ledger (auditor #1) · in-transit cash aging · RTO cost · carrier settlement reconciliation

## Growth & marketing 🔨 new (missed in audit)
- WhatsApp campaigns `↳ WhatsApp Campaign (+Recipient)` · media-buyer tasks/ad spend → CAC `↳ Media Buyer Task` · sales daily dashboard `↳ Sales Daily Dashboard`

## Purchases · sourcing · customs 🔨 partial
- Bill ✅ (list · 3-way match legs PO·GRN·bill · GL journal). GL: GRN Dr Stock/Cr GRNI · bill Dr GRNI/Cr Creditors · pay Dr Creditors/Cr Bank
- 🔨 Vendors · PO · Goods Receipt · create bill
- 💠 Landed cost (freight Danish 1.9M·Cathadis 2.08M + customs → SKU) `↳ Landed Cost Voucher`
- 🔨 International shipping & customs `↳ Commercial Invoice · Packing List · Loading Plan` · Türkiye invoicing `↳ Turkey Official/Supplier Invoice`
- 💠 debit notes · supplier advances

## Accountant ✅ live
- **Journal Entry** ✅ operable — create+post (date·memo·account/debit/credit · balance+currency guard) → gateway (audited; ≥10k needs approver). 🎨 searchable account combobox. 💠 recurring/template · reversing · prepaid/accrual amortization · FX revaluation `↳ Exchange Rate Revaluation`. 🔨 maker-checker queue · detail view
- General ledger · trial balance · chart of accounts ✅ live
- 💠 Period lock/close `↳ Period Closing Voucher · Account Closing Balance`
- 🔨 Fixed assets · depreciation `↳ Asset` · P&L tools (per-item margin · COGS/revenue import) `↳ PL Item Analysis · PL COGS/Revenue Import`

## Banking & COD ✅ live
- Accounts (bank/cash balances, −845k overdraft) ✅ · COD reconciliation cockpit (net debtor −2.85M · unallocated 3.51M vs open 114k) ✅
- 🔨 Match write-back (allocate receipt→invoice) `↳ Payment Reconciliation` · 🎨 drag/click-to-match
- 💠 Bank reconciliation `↳ Bank Reconciliation Tool · Bank Transaction` · 🔨 remittance · carrier aging

## Items & margin 🔨 to build
- Landed-cost engine · true per-order gross margin
- 💠 Perpetual inventory health (fix 685M/677M anomaly) `↳ Stock Reconciliation` · COGS recognition on delivery
- ⚪ stock valuation/movement reports · pricing/promotions/coupons/loyalty `↳ Pricing Rule · Promotional Scheme · Coupon Code · Loyalty Program`

## Reports & close 🔨 to build
- 🔨 P&L · balance sheet · cash flow
- 💠 AR/AP aging (0-30/30-60/60-90/90+) · VAT report (output−input + import VAT, DGI) · margin by SKU/channel/carrier/city · cash-flow forecast
- 💠 customer/supplier statements `↳ Process Statement Of Accounts` · budget vs actual `↳ Budget`
- 🎨 export · print/PDF · date-range + period comparison · 🔨 period-close checklist · audit-trail review

## Multi-entity & consolidation 🔨 new (was missing)
- Entities: Holding (USD) · Morocco (MAD) · Maslak/Türkiye (TRY) · China (USD) · switcher + scoping ✅
- 🔨 Consolidated statements (Holding P&L/BS/cash flow rollup) `↳ Consolidated.vue (sample)`
- 💠 Intercompany (TR→MA flows · Creditors USD 2.77M · reconcile balances) · Eliminations · FX translation `↳ Currency Exchange · Exchange Rate Revaluation`

## Expenses & OpEx 🔨 new (was missing)
- 🔨 operating expenses (Meta/ad spend · rent · SaaS · salaries · bank fees) · 💠 categories→COA · approval · recurring `↳ Subscription · recurring JE`

## Notifications & reminders 🔨 new (was missing)
- Order reminders `↳ custom_first_reminder · custom_second_reminder` · payment reminders `↳ Dunning` 💠 · delivery email/WhatsApp `↳ WhatsApp Campaign` · in-app needs-attention inbox 🎨

## Settings & administration 🔨 new (was missing)
- Portal users + role assignment (4 roles ✅; management UI 🔨) · audit-trail activity screen (Accounting Portal Action) 🔨 · company config · fiscal year · naming series · configurable approval thresholds+delegation 🔨 · tax templates · currencies+rates · COA editor `↳ exist` 💠

## Cap table & governance ⚪ CFO later
- shareholders · board · voting rights · liquidation priority `↳ Board · Shareholder Type · Voting Rights Type · Priority on Liquidation`

## UX & experience 🎨 foundations
- **Critical** — pagination/virtual scroll · searchable comboboxes · loading skeletons + empty + error/retry states
- **Workflow** — needs-attention inbox · bulk actions · global ⌘K search · sticky action bar · tabs · saved filters
- **Polish** — optimistic UI + toasts · inline editing · print/PDF · comments · attachments · column customization · density · responsive/tablet
- **Accessibility & i18n** — focus · ARIA · contrast (WCAG AA) · keyboard nav · RTL Arabic polish

## Foundations & master data ✅ built
- Write gateway (capability · idempotency · audit · propose→approve→post) · audit trail · entity scoping · 4 roles · live⇄sample bridge · cache-bust · trilingual ✅
- 💠 Accounting dimensions — carrier · channel · city as GL dimensions (slice revenue/cost/margin) `↳ Accounting Dimension · Cost Center` ★
- Dashboard CFO KPIs (cash 675k · net +73k · sparklines) ✅
