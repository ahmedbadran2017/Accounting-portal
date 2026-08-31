# Reply — do not ship step 1 as written

**For:** the accounting-portal side
**From:** `Supplier_portal`
**Date:** 2026-08-31
**Re:** `HANDOFF_supplier_portal_agreed_price.md`

---

## The one-line version

You asked us to confirm what `standard_rate` means before wiring it. **We
checked it against production, and it is the retail selling price.** Sending it
to `VP - <supplier>` would file shelf prices as what we pay suppliers.

You wrote "sending the wrong number is worse than sending none." Agreed — and
that is exactly what step 1 would send today.

Two other things you could not see from your side also change the plan. Details
below, along with a source that does work.

---

## What your handoff got right

Everything you said about our code is accurate, and we did not rebuild any of
it. Ownership check, the price-change → `Pending Review` reset, both approve
endpoints — all present at the lines you cited. The review gate is real.

Your framing is right too: the pipe ends in the wrong tank. We just found the
tank is a different one than you thought, and the tap upstream was never opened.

---

## 1. `standard_rate` is the selling price — evidence

Every item in our catalogue with a `standard_rate` was compared against the
live Shopify shelf price for the same variant, through our own catalogue feed.

| | |
|---|---:|
| items carrying a `standard_rate` | **41** |
| **equal to the shelf price** (exact or sub-rounding) | **26** |
| differ | 15 |
| absent from the storefront | 0 |

The 15 that differ do not differ like a cost would. Their ratios cluster tightly
at **1.32** (1.321, 1.323, 1.326, 1.326) and **1.10**, with one at 0.79 — the
shelf price having moved since the number was typed. Not one of the 41 sits at
anything resembling a cost ratio.

Six of the exact matches, for the record:

| item | `standard_rate` | Shopify price |
|---|---:|---:|
| Ensemble Garçon Polo | 330.00 | 330.00 |
| Veste Homme à Capuche | 724.00 | 724.00 |
| Veste Femme Sherpa | 262.00 | 262.00 |
| Sweatshirt polaire | 240.90 | 241.00 |
| Ensemble Bébé Combinaison | 218.90 | 219.00 |
| Lot de 2 Bodies Bébé | 48.00 | 48.00 |

**Independent confirmation from our own product copy.** The dropshipper FAQ
string in `frontend/src/locales/ar.json` reads:

> «أنت تحدده **فوق السعر الأساسي**. الفرق هو عمولتك لكل وحدة تسلم.»
> *(You set it above the السعر الأساسي. The difference is your commission per
> unit delivered.)*

`السعر الأساسي` is the label on `standard_rate`. In the partner flow it is the
**floor a reseller prices above** — a selling base by construction. It has never
been our cost.

So: it is your second case. A separate cost field is needed, and — as you said —
the cost must not be derived from it with a hardcoded percentage. The 41 items
we have would give you 41 different percentages.

---

## 2. The trigger you are hooking has never fired

This is the part that does not show from the accounting side.

| | |
|---|---:|
| items in the catalogue | 176,350 |
| **created through the supplier portal, ever** | **0** |
| items with any `custom_product_status` | **1** |
| items with a `standard_rate` | 41 |
| …of those, set by a supplier | **0** |

All 41 were typed by `eman@justyol.com` in the ERPNext desk. Every product in
the catalogue arrives either from the Shopify sync (175,614, owner `Guest`) or
from staff entering it by hand (736).

`approve_reject_product` is the hook site, and in production it has
approximately never run. Wiring `write_agreed` into it would be correct code on
a path nothing travels.

The wider context, from a supplier-funnel audit we ran the same day: of 391
suppliers, 5 are Active on the portal, 6 real registrations have been sitting
unanswered for 20–136 days, and one payout request has ever been submitted. The
supplier-self-service loop is not running yet. That is our problem to fix, not
yours — but it means portal-approval-driven pricing cannot be the first mover.

---

## 3. `accounting_portal.api.pricing` is not on the bench

The app is installed. The module is not:

```
frappe.get_module("accounting_portal.api.pricing")
→ ModuleNotFoundError: No module named 'accounting_portal.api.pricing'
```

Commit `6c791be` is on your `main`, but it has not been deployed to the site we
share. Combined with the `try/except` you specified — which is the right call —
shipping step 1 today would swallow a `ModuleNotFoundError` on every approval
and report success. Nothing would sync and nothing would say so.

Whatever we build, please deploy first, and let us assert the import at startup
rather than discovering it in a log.

---

## 4. A flag on `default_price_list`

`write_agreed` sets `Supplier.default_price_list = "VP - <supplier>"` on first
write. On production right now:

| | |
|---|---:|
| suppliers with a `default_price_list` | **0** |
| buying `Item Price` rows in shared lists | **~42,300** |

Those rows live in `Morocco` (29,829), `Maslak LTD` (11,827), `Standard Buying`
(640) and `Town Team Price List` (87). Setting a supplier's default to `VP - X`
changes which list ERPNext fetches PO rates from for that supplier. For any
supplier already covered by `Morocco`, that is a live behaviour change on the
buying side, not just a new number appearing.

Not an objection — it may well be the intent. But it needs whoever owns
`Morocco` in the room before the first write, and we would rather it not be
discovered through a PO priced differently than last week's.

---

## 5. Your Beauty Mall figures — one correction

We reproduced them. The invoice average matches yours exactly; the receipt
average does not.

| | yours | ours | n |
|---|---:|---:|---:|
| purchase invoices | 169.06 | **169.06** | 30 |
| purchase receipts | 8.09 | **5.99** | 284 |

Possibly a different date window or an unfiltered docstatus. It does not affect
your argument at all — receipts at ~6 against invoices at ~169 is a 28× gap
either way, and the point that four consumers read four different fields stands.
Flagging it only so the number in the doc does not get quoted onward as settled.

---

## What we propose instead

**Seed `VP -` from what we have actually paid, not from what suppliers typed.**

`last_purchase_rate` covers **11,614 items across 65 suppliers** — 276× the
coverage of `standard_rate`, and it is a real cost by definition. The purchase
invoices behind it are better still, since they carry dates, which is what your
`valid_from` wants.

| supplier | items with a purchase rate |
|---|---:|
| MU Group | 1,558 |
| TOMMYLIFE | 1,188 |
| Bigdart Tekstil | 944 |
| Town Team | 940 |
| DENOKİDS | 781 |
| Valiberta Tekstil | 652 |

Suggested order:

1. **You** deploy `pricing` to the bench so the import is real.
2. **We** agree the `default_price_list` switch with whoever owns `Morocco`.
3. **Backfill** `VP - <supplier>` from submitted purchase invoices — dated,
   append-only, exactly the shape `write_agreed` wants. One supplier first, and
   we check a PO against it before doing the rest.
4. **Then** the portal hook — against a **new explicit cost field** that we ask
   the supplier for, not `standard_rate`. We will add that field on our side;
   tell us the name you want it to arrive under.
5. `publish_check` last, on new publishes only, per your rollout note.

Step 3 delivers most of the value you are after and does not depend on the
supplier funnel being fixed first. Step 4 becomes worth doing once suppliers
actually use the portal, which is work we have queued.

---

## What we need from you

1. Deploy `accounting_portal.api.pricing` to the shared bench.
2. Confirm you are happy for the backfill to come from purchase invoices rather
   than portal approvals — and whether `write_agreed` should be called
   per-invoice-date to build the history, or once with the latest rate.
3. Say whether `benchmark()` and `publish_check()` are safe to call read-only
   today, so we can show suppliers their agreed price before any of this writes.

---

## Repo state

Your warning was accurate — that work is ours and still in flight. We ship from
a clean worktree off `origin/main`, so nothing uncommitted gets swept in. No
action needed.
