# Handoff — wire the Supplier Portal into the agreed-price cycle

**For:** whoever works in `Supplier_portal` (`git@github.com:ahmedbadran2017/Supplier_portal.git`)
**From:** the accounting-portal side, which is built and waiting for the call
**Date:** 2026-08-31

---

## The one-line version

The supplier portal already collects a price from the supplier and already makes
an admin approve it. That price lands in `Item.standard_rate` and stops there.
**Send it to `VP - <supplier>` on approval instead, and the whole buying side
starts using it.**

This is roughly a 20-line change at one call site. It is not a new feature.

---

## What is already right in the portal (do not rebuild it)

The old blueprint claimed the portal was an unguarded hole where suppliers wrote
prices straight into the item master. That is **not true today**:

| | where |
|---|---|
| Supplier submits his own products and prices | `api/products.py::create_product`, `::update_product` |
| Ownership check (deny-by-default) | `api/products.py::_validate_item_ownership` (L65) |
| Price sanity bounds (0 … 10,000,000) | `api/products.py` L421-430 |
| **A price change resets Approved → Pending Review** | `api/products.py` L445-451 |
| Admin approves / rejects | `api/admin.py::approve_reject_product` (L2897), `::bulk_approve_reject_products` (L2930) |
| Bulk sheet upload | `api/products.py` ~L1090-1130 |

So the supplier door and the review gate both exist. **The plumbing is fine; the
pipe ends in the wrong tank.**

---

## The actual gap

The price is written to **`Item.standard_rate`** — one field on the item master.

1. **No history.** Change it and June's price is gone. There is no `valid_from`,
   so "what did we agree when that invoice was raised" is unanswerable.
2. **Not per supplier, not dated.** It sits on the item, not on the relationship.
3. **It never reaches the buying side.** Purchase Orders read
   `Supplier.default_price_list`, not `standard_rate`. So the PO, the receipt,
   the stock valuation, the partner commission and the site price never see the
   number the supplier actually gave us.

That third point is the whole problem. Measured on PROD:

| Beauty Mall, same goods | rate |
|---|---:|
| what its receipts were costed at (this is what feeds COGS) | **8.09** |
| what its invoices say | 169.06 |
| what the storefront integration carries | 277.27 |
| what its partner commission was computed on (avg `base_price`) | **1.70** |

Four numbers for one price, because four consumers each read a different field.

---

## What to change

### 1. On approval, write the agreed price

In `api/admin.py::approve_reject_product`, after the item is saved with
`custom_product_status = "Approved"`:

```python
if new_status == "Approved":
    try:
        from accounting_portal.api import pricing
        supplier = _get_item_supplier(item_code)          # already in products.py
        rate = float(item.standard_rate or 0)
        if supplier and rate > 0:
            pricing.write_agreed(
                supplier,
                [{"item_code": item_code, "rate": rate,
                  "valid_from": frappe.utils.nowdate()}],
                confirm=True,          # an admin just approved it deliberately
            )
    except Exception:
        frappe.log_error(title="agreed price sync", message=frappe.get_traceback())
```

Do the same in `bulk_approve_reject_products` (one `write_agreed` call with all
the rows, not one per item).

**Why `confirm=True`:** `write_agreed` refuses a rate more than ±50% from the
last invoice unless confirmed. Here a human admin has just looked at it and
pressed approve, so the guard has already been satisfied by a person. If you
would rather have the portal surface the deviation before approving, call
`pricing.benchmark(supplier, item_code)` first and show it — that is the nicer
version, but it is optional.

**Why wrapped in try/except:** approving a product must not fail because the
accounting app is mid-deploy. Log and carry on; the daily checklist will surface
anything that did not sync.

### 2. Decide what `standard_rate` means (needed before step 1 ships)

`standard_rate` is ERPNext's **selling** rate field, and the portal labels it
"Standard rate / السعر الأساسي". Before wiring it to a **buying** price list,
confirm with the business which it is:

- If it is **what we pay the supplier** → the code above is correct as written.
- If it is **his retail/list price** and our cost is a discount off it → add a
  separate cost field, and send *that* to `write_agreed`. Do not derive the cost
  with a hardcoded percentage.

Evidence it may be the latter: the Beauty Mall integration carries an average of
277.27 while our invoices from him average 169.06 (ratio ~1.64), and that feed
goes to Shopify. **Confirm before shipping** — sending the wrong number is worse
than sending none.

### 3. Optional, later — show the supplier his agreed price

Once step 1 is live, `pricing.agreed_price(supplier, item_code)` gives the
portal a read for a "your agreed price / effective from" column, so the supplier
sees what was approved rather than what he last typed.

---

## The API you are calling

Module: `accounting_portal.api.pricing` (already on `main` in the Accounting
repo, commit `6c791be`).

```python
write_agreed(supplier, rows, confirm=False, bench_fn=None)
    rows = [{"item_code": str, "rate": float, "valid_from": "YYYY-MM-DD"}]
    -> {"saved": [item_code], "flagged": [...], "invalid": [...], "price_list": str}
```

Behaviour worth knowing:

- **Creates `VP - <supplier>` on first write** and sets it as
  `Supplier.default_price_list`, so ERPNext then fetches the price onto POs by
  itself. Nothing else to wire.
- **Append-only.** A new price closes the previous row at `valid_from - 1 day`.
  A same-day correction replaces rather than stacks. **Backdating behind the
  latest row is refused** — it would silently rewrite a period that documents
  were already priced from.
- **Bounds:** 0.05 … 100,000 in the supplier's currency. Outside that, the row
  comes back in `invalid` rather than being written.
- It is the **only** function that writes an approved price. Please do not add a
  second writer — two "agreed" prices for one item is the exact failure this
  removes.

Other calls available if useful:

```python
agreed_price(supplier, item_code, on_date=None) -> float
benchmark(supplier, item_code)  -> (rate, "invoice" | "receipt" | "none")
publish_check(item_code, supplier=None) -> {"ok": bool, "reason": str, ...}
```

`publish_check` is the gate: **no product goes live without an approved price.**
Worth calling before publishing to the storefront — every zero-cost item in the
book got there by being published with nobody having decided its cost.

> **Rollout order matters.** 4,912 sellable items would fail `publish_check`
> today because no `VP -` list exists yet. Seed and approve first, then turn the
> gate on, and apply it to **new** publishes only. Turning it on early stops the
> store.

---

## Repo state warning

At the time of writing, `/Users/ahmedbadran/Supplier/supplier_portal` has **49
modified files uncommitted** — someone's work in flight, including
`frontend/src/locales/ar.json` and `en.json`. Do not `git add -A` there. Either
wait for that work to land, or branch from a clean commit and merge later.

---

## How to check it worked

After the change, approve one product in the portal, then:

```python
from accounting_portal.api import pricing
pricing.agreed_price("<supplier>", "<item_code>")   # should be the approved rate
frappe.db.get_value("Supplier", "<supplier>", "default_price_list")  # "VP - <supplier>"
```

Then raise a Purchase Order for that supplier and item — the rate should arrive
by itself, with nobody typing it.

And in the Accounting portal, `Items → Agreed prices` shows the cycle's state:
what is waiting for review, what is live with no agreed price, and where a vendor
billed above what was agreed.
