"""Saving a new price list no longer makes it the default for every document.

ERPNext's Price List.on_update (set_default_if_missing) writes the list being
saved into Buying Settings (or Selling Settings) whenever that setting is
empty. Justyol's supplier lists are versioned ("Awani - Buying - 20/10/2026")
and each version is disabled when the next one arrives, so the setting ended
up pointing at one supplier's list, and once that list was disabled every
new purchase document started from a disabled list and was refused. That
blocked bill imports on 23 Oct 2026 (PUR-INV-06637).

The team cleared the setting on purpose: each order takes its supplier's own
list. So when the setting was empty before the save, it is put back to empty
after it. A default someone sets by hand in the settings is left alone.
"""
import frappe

_SIDES = (("Buying Settings", "buying_price_list", "buying"),
          ("Selling Settings", "selling_price_list", "selling"))
_FLAG = "portal_empty_price_list_defaults"


def note_empty_defaults(doc, method=None):
    """validate: remember which settings were empty before ERPNext fills them."""
    doc.flags[_FLAG] = [(s, f) for s, f, side in _SIDES
                        if doc.get(side) and not frappe.db.get_single_value(s, f)]


def keep_defaults_empty(doc, method=None):
    """on_update (runs after ERPNext's own): undo the default it just set."""
    for settings, field in doc.flags.get(_FLAG) or []:
        if frappe.db.get_single_value(settings, field) != doc.name:
            continue
        frappe.db.set_single_value(settings, field, None)
        # Buying/Selling Settings mirror the field into the global defaults,
        # and new documents are built from those, so clear that copy too.
        frappe.db.set_default(field, "")
