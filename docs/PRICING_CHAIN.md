# The Price Chain — vendor price lists → PO → invoice truth → website pricing

Approved architecture (2026-08-28). One chain, one direction, four layers.
Factors in the existing **Supplier Portal** (Frappe app `supplier_portal`,
Portal User → Supplier auth, suppliers already see their items & POs).

```
المورد يقدّم سعر          فريق المشتريات يعتمد        الـPO تسحب آخر سعر ساري
(Supplier Portal)   →    (Accounting Portal)     →   (ERPNext Item Price)
                                                            ↓
سعر الموقع  ←  أساس التسعير  ←  حقبة التكلفة الحقيقية  ←  الفاتورة
(Shopify)      (Pricing screen)    (era engine — unchanged)
```

## Layer 0 — ownership (prerequisite)

- Supplier Portal currently keys items by `Item.default_supplier`. Our TRUE
  attribution is the workbench volume-wins map (+ manual pins). **Sync the
  attribution map into `Item.default_supplier`** (one-off + on pin change) so
  the supplier sees exactly the catalog we attribute to him.
- **Close the existing hole**: `products.update_product` lets suppliers write
  `standard_rate` straight into the Item master with no review. Remove
  `standard_rate` from its allowed fields — all price input goes through the
  submission flow below.

## Layer 1 — the agreed price (append-only, per supplier)

- One fresh Buying Price List per supplier: **`VP - <Supplier>`** (currency
  pinned per supplier). The old buying lists are POLLUTED (356B-type rates,
  246 records > 2K) — quarantined, never reused, never read.
- Every price is an **Item Price row with `valid_from`**. An update is a NEW
  row with a new date — history is never edited (same doctrine as invoice
  eras). The supplier's own price history becomes reviewable.

## Layer 2 — who enters prices, and the approval gate

Two entry paths, one gate:

1. **Supplier self-service** (Supplier Portal, new "My Prices" tab): grid of
   his items → current agreed price + history → he submits new price +
   effective date. Creates a PENDING submission — never touches the active
   list directly.
2. **Team path** (Accounting Portal → Vendors → new "Price List" step): same
   grid + per-vendor Excel import (same round-trip the team already uses for
   weights). Team submissions can be self-approved by role.

**Approval queue** (Accounting Portal): each pending submission shows the
diff vs (a) current list price, (b) latest INVOICE era — jump > ±50% is
flagged red. Approve → Item Price row created in `VP - <Supplier>` with the
effective date. Rejected → archived with reason. Everything audited via
Accounting Portal Action.

Entry guards on both paths: currency locked to the supplier's, positive
sane bounds, and the >±50%-vs-era confirmation — this is the anti-pollution
firewall that the old lists never had.

## Layer 3 — PO pulls the latest valid price

- POs (portal procure-to-pay flow) set `buying_price_list = VP - <Supplier>`
  → ERPNext natively fetches the latest `valid_from ≤ PO date` price.
- Guards: item with no list price → yellow "ask the vendor first"; manual
  rate different from list → visible deviation chip (allowed but recorded).

## Layer 4 — invoice stays the judge (unchanged)

The era engine keeps building TRUE cost from Purchase Invoices only.
New free comparison: **invoiced rate vs approved list rate** per era row —
"the vendor billed above the agreed price" becomes visible in the costs step.

## Layer 5 — website pricing basis

Per product, pricing basis source hierarchy:
1. verified cost override (if set)
2. latest invoice era (product + freight)
3. **approved list price** (+ modeled freight by weight) — this is what lets
   a NEW product be priced on the site before the first invoice exists.

Then: + non-recoverable supplier TVA + COD fee (~5% model) + returns share
(21% return trips must be carried by sold units) → ÷ (1 − target margin) →
**site price incl. output TVA**. Pricing screen shows: basis, current
Shopify price, actual margin, proposed price; push to Shopify is a gated
action (later phase).

## Build phases

- **P1 (now, team-only value)**: VP lists + Vendors "Price List" step + Excel
  import + guards + PO fetch wiring + invoice-vs-list comparison.
- **P2**: Supplier Portal "My Prices" + submission queue + approval screen +
  close the standard_rate hole + default_supplier sync.
- **P3**: Pricing screen + margin model + gated Shopify push.
- **P4**: notifications (price updated / billed-above-agreed), RFQ flow,
  daily-checklist hook (pending submissions > 48h).
