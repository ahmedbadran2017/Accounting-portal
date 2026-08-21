"""Per-item activity log — who touched this SKU's cost, and what they saved.

The cost work leaves its trail in four different stores, and until now nobody
could see them together:
  * `Accounting Portal Action`  — the gated applies/reverts (status, voucher, amount)
  * `Version`                   — field edits on the Item itself (weight, defaults)
  * `ap_itemcost_<item>`        — a saved verified cost with no import shipments
  * `ap_sheet_<PR>`             — saved costs inside a shipment's draft sheet

This merges them into one timeline, newest first, for a SKU or for every member
of a model family.
"""
import json

import frappe
from frappe.utils import flt

from accounting_portal.api.permissions import assert_portal_access

# Item fields worth surfacing; everything else is noise on a 126k-row table
_WATCHED = {
    "weight_per_unit": "Weight",
    "weight_uom": "Weight unit",
    "valuation_rate": "Valuation rate",
    "item_name": "Name",
    "disabled": "Disabled",
    "is_stock_item": "Stock item",
    "standard_rate": "Standard rate",
    "last_purchase_rate": "Last purchase rate",
}


def _actions(items):
    rows = frappe.db.sql(
        """SELECT name, reference_name item, status, amount, voucher_type, voucher_no,
                  notes, payload, proposed_by, approved_by, posted_on, creation, modified
           FROM `tabAccounting Portal Action`
           WHERE reference_doctype='Item' AND reference_name IN %s
           ORDER BY creation DESC LIMIT 200""", (items,), as_dict=True)
    out = []
    for r in rows:
        anchor = rate = None
        pins = 0
        try:
            p = frappe.parse_json(r.payload or "{}") or {}
            anchor = p.get("date")
            pins = len(p.get("retro_pins") or [])
            rws = p.get("rows") or []
            if rws:
                rate = flt(rws[0].get("rate"))
        except Exception:
            pass
        # a reverted action reads better stamped at the moment it was undone
        ts = str(r.modified if r.status == "Reverted" else (r.posted_on or r.creation))[:19]
        out.append({
            "ts": ts, "item": r.item, "kind": "apply", "status": r.status,
            "who": r.approved_by or r.proposed_by,
            "title": {"Posted": "Cost applied", "Reverted": "Apply undone",
                      "Proposed": "Apply proposed", "Failed": "Apply failed",
                      "Rejected": "Apply rejected"}.get(r.status, r.status),
            "rate": rate, "anchor": anchor, "pins": pins,
            "amount": flt(r.amount), "voucher": r.voucher_no,
            "note": (r.notes or "")[:400], "ref": r.name,
        })
    return out


def _saves(items):
    """Draft saves. Each store keeps only its LATEST stamp, so this is a
    current-state row, not a full history — labelled as such in the UI."""
    out = []
    for it in items:
        raw = frappe.db.get_default(f"ap_itemcost_{it}")
        if raw:
            try:
                d = json.loads(raw) or {}
            except Exception:
                d = {}
            if d.get("on"):
                out.append({"ts": str(d["on"])[:19], "item": it, "kind": "save",
                            "status": "Draft", "who": d.get("by"),
                            "title": "Verified cost saved", "rate": flt(d.get("cost")),
                            "note": d.get("note") or "", "scope": "item"})
    # shipment sheets carry per-item costs; find the ones naming our items
    sheets = frappe.db.sql(
        """SELECT defkey, defvalue FROM `tabDefaultValue`
           WHERE defkey LIKE 'ap_sheet_%%'""", as_dict=True)
    for s in sheets:
        try:
            d = json.loads(s.defvalue or "null") or {}
        except Exception:
            continue
        costs = d.get("costs") or {}
        if not d.get("on"):
            continue
        for it in items:
            if it in costs:
                out.append({"ts": str(d["on"])[:19], "item": it, "kind": "save",
                            "status": "Draft", "who": d.get("by"),
                            "title": "Verified cost saved in shipment sheet",
                            "rate": flt(costs[it]), "note": d.get("note") or "",
                            "scope": s.defkey.replace("ap_sheet_", "")})
    return out


def _edits(items):
    rows = frappe.db.sql(
        """SELECT docname item, owner, creation, data FROM `tabVersion`
           WHERE ref_doctype='Item' AND docname IN %s
           ORDER BY creation DESC LIMIT 300""", (items,), as_dict=True)
    out = []
    for r in rows:
        try:
            d = json.loads(r.data or "{}") or {}
        except Exception:
            continue
        for ch in (d.get("changed") or []):
            if not ch or len(ch) < 3:
                continue
            field = ch[0]
            if field not in _WATCHED:
                continue
            out.append({
                "ts": str(r.creation)[:19], "item": r.item, "kind": "edit",
                "status": "", "who": r.owner,
                "title": f"{_WATCHED[field]} changed",
                "field": field, "old": ch[1], "new": ch[2],
            })
        if d.get("added") or d.get("removed"):
            names = set()
            for grp in ("added", "removed"):
                for row in (d.get(grp) or []):
                    if row and row[0]:
                        names.add(row[0])
            if names:
                out.append({"ts": str(r.creation)[:19], "item": r.item, "kind": "edit",
                            "status": "", "who": r.owner,
                            "title": "Item defaults changed",
                            "field": ", ".join(sorted(names)[:3]), "old": None, "new": None})
    return out


@frappe.whitelist()
def item_activity(item_code=None, items=None, limit=60):
    """Merged timeline for one SKU (item_code) or a model's members (items,
    JSON list). Newest first. Read-only."""
    assert_portal_access()
    lst = []
    if items:
        lst = json.loads(items) if isinstance(items, str) else list(items)
    if item_code:
        lst.append(item_code)
    lst = sorted({str(x) for x in lst if x})
    if not lst:
        return {"rows": [], "items": []}
    rows = _actions(lst) + _saves(lst) + _edits(lst)
    rows.sort(key=lambda r: r.get("ts") or "", reverse=True)
    return {"rows": rows[:int(limit or 60)], "items": lst,
            "counts": {"apply": len([r for r in rows if r["kind"] == "apply"]),
                       "save": len([r for r in rows if r["kind"] == "save"]),
                       "edit": len([r for r in rows if r["kind"] == "edit"])}}
