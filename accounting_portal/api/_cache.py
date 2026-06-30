"""Tiny read-through cache for the heavy GL-aggregate report endpoints.

The big analytical reads (financial statements, trial balance, chart of accounts,
FX revaluation, item margins, verified DD) each scan the multi-million-row GL
Entry table and take 2–6 s cold. They don't change second-to-second, so a short
TTL makes repeat visits / navigation instant — the same pattern that took the
dashboard cockpit from 8 s to 1 ms. Caches self-expire; reports tolerate being a
couple of minutes stale. Call bust_report_caches() after a write for freshness.
"""
import frappe

_PREFIXES = (
    "ap_coa:", "ap_tb:", "ap_gl:", "ap_items:", "ap_fs:", "ap_vdd:", "ap_fxr:", "ap_auditor:",
    # report/cockpit caches that previously survived writes (audit finding)
    "ap_bs:", "ap_invh:", "ap_consol:", "ap_command:", "ap_cod_summary:",
    "ap_carrier_aging:", "ap_sales_cohort:", "ap_arap_recon:", "ap_purch_summary:",
    # page-invariant list count/summary caches (short TTL, bust so a new doc shows at once)
    "ap_orders_sc:", "ap_orders_tot:", "ap_inv_sum:", "ap_rcpt_sum:",
    "ap_team_perf:",
)


def cached(key, ttl, builder):
    """Return cached value for `key`, else build it, cache it for `ttl` s, return."""
    hit = frappe.cache().get_value(key)
    if hit is not None:
        return hit
    val = builder()
    try:
        frappe.cache().set_value(key, val, expires_in_sec=ttl)
    except Exception:
        pass
    return val


def bust_report_caches(company=None):
    """Drop the report caches (after a write). Clears every period/param variant."""
    for p in _PREFIXES:
        try:
            frappe.cache().delete_keys(p + (company or ""))
        except Exception:
            pass
