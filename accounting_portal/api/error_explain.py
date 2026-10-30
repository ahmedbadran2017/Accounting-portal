"""Turn an ERPNext error into an explanation the accountant can act on.

Why: a failed save or submit used to surface ERPNext's raw exception —
"StockOverReturnError: Item 47350849732862 has already been returned" — in a
four-second toast. The accountant then tried again, got the same toast, and on
2026-10-30 opened four identical debit-note drafts on one bill before the fifth
attempt went through. The facts that explain the error (which debit note already
returned the item, which lines repeat it, that three duplicate drafts exist) were
all in the database; nobody showed them.

How: when a write fails, the portal's API client posts the exception type, the
message and the call's own arguments here. A handler that recognises the error
reads the documents involved and returns a structured explanation:

    {code, severity, title{en,ar,fr}, body{..}, facts[], lines{}, note{..},
     actions[], technical}

The client shows it in one popup. `actions` are ready-made fixes; each one maps
to a gated endpoint below (remove the offending lines, delete duplicate drafts,
drop a closed-order link, clear a disabled price list) or simply opens a
document. Anything no handler recognises still gets the popup, with the cleaned
message and the raw text tucked under "Technical detail".

Read-only except for the action endpoints, which only ever touch drafts.
"""
import json
import re

import frappe
from frappe.utils import flt, fmt_money, formatdate

from accounting_portal.api import _actions
from accounting_portal.api.permissions import assert_portal_access, assert_can_write, resolve_companies


def T(en, ar, fr):
    return {"en": en, "ar": ar, "fr": fr}


def _clean(msg):
    msg = re.sub(r"<[^>]+>", "", str(msg or ""))
    msg = re.sub(r"^[\w.]+(Error|Exception):\s*", "", msg.strip())
    return re.sub(r"\s+", " ", msg).strip()


def _money(v, cur="MAD"):
    return fmt_money(flt(v), currency=cur)


def _doc_from_args(args):
    dt = args.get("doctype") or args.get("dt")
    dn = args.get("name") or args.get("dn") or args.get("docname")
    names = args.get("names")
    if not dn and names:
        try:
            names = names if isinstance(names, list) else json.loads(names)
        except Exception:
            names = []
        dn = names[0] if len(names) == 1 else None   # a batch of one (Submit on a single row)
    if dt and dn and frappe.db.exists(dt, dn):
        return dt, dn
    return None, None


# ── 1. Item already returned (debit / credit note) ───────────────────────────

def _over_return(doctype, name, message, **_):
    if doctype not in ("Purchase Invoice", "Sales Invoice") or not name:
        return None
    doc = frappe.get_doc(doctype, name)
    if not doc.get("is_return") or not doc.get("return_against"):
        return None
    buying = doctype == "Purchase Invoice"
    item_tbl = "Purchase Invoice Item" if buying else "Sales Invoice Item"
    back = "purchase_invoice_item" if buying else "sales_invoice_item"
    orig = doc.return_against
    orig_qty = dict(frappe.db.sql(f"SELECT name, qty FROM `tab{item_tbl}` WHERE parent=%s", orig))
    done = dict(frappe.db.sql(
        f"""SELECT i.{back}, SUM(ABS(i.qty)) FROM `tab{item_tbl}` i
            JOIN `tab{doctype}` p ON p.name = i.parent
            WHERE p.return_against=%s AND p.docstatus=1 AND p.name!=%s AND IFNULL(i.{back},'')!=''
            GROUP BY i.{back}""", (orig, name)))
    item_in_msg = (re.search(r"Item\s+(\S+)", message or "") or [None, None])[1]
    clash = []
    for r in doc.items:
        link = r.get(back)
        if link and link in orig_qty:
            if flt(done.get(link)) + abs(flt(r.qty)) > flt(orig_qty[link]) + 1e-9:
                clash.append(r)
        elif item_in_msg and r.item_code == item_in_msg:
            clash.append(r)
    if not clash:
        return None
    from accounting_portal.api.docedit import _line_orders
    orders = _line_orders(doc)
    cur = doc.currency or "MAD"
    prior = frappe.db.sql(
        f"""SELECT name, posting_date, grand_total{', bill_no' if buying else ''} FROM `tab{doctype}`
            WHERE return_against=%s AND docstatus=1 AND name!=%s ORDER BY posting_date""",
        (orig, name), as_dict=True)
    dups = frappe.db.sql_list(
        f"SELECT name FROM `tab{doctype}` WHERE return_against=%s AND docstatus=0 AND name!=%s ORDER BY name",
        (orig, name))
    party = doc.get("supplier") if buying else doc.get("customer")
    orig_ref = frappe.db.get_value(doctype, orig, "bill_no") if buying else None
    left_rows = len(doc.items) - len(clash)
    left_net = flt(doc.net_total) - sum(flt(r.net_amount or r.amount) for r in clash)
    n = len(clash)
    note_kind = T("debit note", "إشعار مدين", "avoir") if buying else T("credit note", "إشعار دائن", "avoir")
    x = {
        "code": "over_return", "severity": "warning", "icon": "refresh",
        "title": T(f"{n} line{'s' if n > 1 else ''} already returned",
                   f"{n} سطر اترجّعوا قبل كده",
                   f"{n} ligne{'s' if n > 1 else ''} déjà retournée{'s' if n > 1 else ''}"),
        "body": T(
            f"{orig} ({party}{' · ' + orig_ref if orig_ref else ''}) already has a submitted {note_kind['en']} for "
            f"{'these lines' if n > 1 else 'this line'}. This draft returns {'them' if n > 1 else 'it'} a second time, so ERPNext refuses it.",
            f"الفاتورة {orig} ({party}{' · ' + orig_ref if orig_ref else ''}) عليها {note_kind['ar']} مرحّل بالفعل "
            f"{'بالسطور دي' if n > 1 else 'بالسطر ده'}. المسودة دي بترجّعها تاني، فـ ERPNext بيرفضها.",
            f"La facture {orig} ({party}{' · ' + orig_ref if orig_ref else ''}) a déjà un {note_kind['fr']} validé "
            f"pour {'ces lignes' if n > 1 else 'cette ligne'}. Ce brouillon {'les' if n > 1 else 'la'} retourne une deuxième fois, donc ERPNext le refuse."),
        "facts": [{"label": T("Already submitted", "مرحّل بالفعل", "Déjà validé"),
                   "value": p.name + (f" · {p.bill_no}" if buying and p.get("bill_no") else ""),
                   "amount": _money(p.grand_total, cur), "doc": {"doctype": doctype, "name": p.name}} for p in prior],
        "lines": {
            "columns": [{"key": "idx", "label": T("Line", "السطر", "Ligne")},
                        {"key": "item", "label": T("Item", "الصنف", "Article")},
                        {"key": "order", "label": T("Order", "الأوردر", "Commande")},
                        {"key": "amount", "label": T("Amount", "المبلغ", "Montant"), "num": True}],
            "rows": [{"idx": r.idx, "item": r.item_name or r.item_code, "order": orders.get(r.name) or "—",
                      "amount": _money(abs(flt(r.amount)), cur)} for r in clash]},
        "note": T(f"{len(dups)} more identical draft{'s' if len(dups) > 1 else ''} on this bill: {', '.join(dups)}.",
                  f"فيه {len(dups)} مسودة تانية زي دي على نفس الفاتورة: {', '.join(dups)}.",
                  f"{len(dups)} autre{'s' if len(dups) > 1 else ''} brouillon{'s' if len(dups) > 1 else ''} identique{'s' if len(dups) > 1 else ''} sur cette facture : {', '.join(dups)}.") if dups else None,
        "actions": [],
    }
    if left_rows > 0:
        x["actions"].append({
            "kind": "remove_lines", "primary": True, "doctype": doctype, "name": name,
            "rows": [r.name for r in clash],
            "label": T(f"Remove {'these ' + str(n) + ' lines' if n > 1 else 'this line'} and keep the rest ({left_rows} lines · {_money(abs(left_net), cur)} excl. VAT)",
                       f"شيل {'السطور دي' if n > 1 else 'السطر ده'} وسيب الباقي ({left_rows} سطر · {_money(abs(left_net), cur)} قبل الضريبة)",
                       f"Retirer {'ces ' + str(n) + ' lignes' if n > 1 else 'cette ligne'} et garder le reste ({left_rows} lignes · {_money(abs(left_net), cur)} HT)")})
    if prior:
        x["actions"].append({"kind": "open", "doctype": doctype, "name": prior[-1].name,
                             "label": T(f"Open the submitted {note_kind['en']}", f"افتح الـ{note_kind['ar']} المرحّل", f"Ouvrir l'{note_kind['fr']} déjà validé")})
    if dups:
        x["actions"].append({"kind": "delete_drafts", "doctype": doctype, "names": dups,
                             "label": T(f"Delete the {len(dups)} duplicate draft{'s' if len(dups) > 1 else ''}",
                                        f"امسح الـ{len(dups)} مسودة المكررة",
                                        f"Supprimer les {len(dups)} brouillons en double")})
    return x


# ── 1b. A new note started from the original bill / invoice ─────────────────
#
# Same error, other side: the accountant pressed "Debit note" on the bill itself,
# so the arguments name the original, not a return. Seen on PUR-INV-05670: three
# lines already returned by PUR-INV-06738 and a draft PUR-INV-06735 holding the
# other eight — the right move is to open that draft, not to start a fifth.

def _original_returned(doctype, name, message, **_):
    if doctype not in ("Purchase Invoice", "Sales Invoice") or not name:
        return None
    doc = frappe.get_doc(doctype, name)
    if doc.get("is_return"):
        return None
    buying = doctype == "Purchase Invoice"
    item_tbl = "Purchase Invoice Item" if buying else "Sales Invoice Item"
    back = "purchase_invoice_item" if buying else "sales_invoice_item"
    cur = doc.currency or "MAD"
    done = dict(frappe.db.sql(
        f"""SELECT i.{back}, SUM(ABS(i.qty)) FROM `tab{item_tbl}` i JOIN `tab{doctype}` p ON p.name=i.parent
            WHERE p.return_against=%s AND p.docstatus=1 AND IFNULL(i.{back},'')!='' GROUP BY i.{back}""", (name,)))
    gone = [r for r in doc.items if flt(done.get(r.name)) >= flt(r.qty) - 1e-9 and r.name in done]
    prior = frappe.db.sql(
        f"""SELECT name, grand_total{', bill_no' if buying else ''} FROM `tab{doctype}`
            WHERE return_against=%s AND docstatus=1 ORDER BY posting_date""", (name,), as_dict=True)
    drafts = frappe.db.sql(
        f"""SELECT name, grand_total, (SELECT COUNT(*) FROM `tab{item_tbl}` i WHERE i.parent=p.name) n
            FROM `tab{doctype}` p WHERE return_against=%s AND docstatus=0 AND is_return=1 ORDER BY name""",
        (name,), as_dict=True)
    if not (gone or drafts):
        return None
    note_kind = T("debit note", "إشعار مدين", "avoir") if buying else T("credit note", "إشعار دائن", "avoir")
    left = len(doc.items) - len(gone)
    if drafts:
        d0 = drafts[0]
        title = T(f"This bill already has a draft {note_kind['en']}", f"الفاتورة دي عليها {note_kind['ar']} مسودة بالفعل",
                  f"Cette facture a déjà un {note_kind['fr']} en brouillon")
        body = T(f"{d0.name} ({d0.n} lines · {_money(abs(d0.grand_total), cur)}) is waiting as a draft. Open it, adjust the lines and submit it — a new one would return the same goods twice.",
                 f"{d0.name} ({d0.n} سطر · {_money(abs(d0.grand_total), cur)}) موجود كمسودة. افتحه وعدّل السطور واعتمده — لو عملت واحد جديد هيرجّع نفس البضاعة مرتين.",
                 f"{d0.name} ({d0.n} lignes · {_money(abs(d0.grand_total), cur)}) attend en brouillon. Ouvrez-le, ajustez les lignes et validez — un nouveau retournerait deux fois la même marchandise.")
    elif not left:
        title = T("Everything on this bill is already returned", "كل سطور الفاتورة اترجّعت بالفعل", "Tout est déjà retourné sur cette facture")
        body = T("Nothing is left to return.", "مفيش حاجة فاضلة ترجع.", "Il ne reste rien à retourner.")
    else:
        title = T(f"{len(gone)} lines of this bill are already returned", f"{len(gone)} سطر من الفاتورة اترجّعوا بالفعل",
                  f"{len(gone)} lignes de cette facture sont déjà retournées")
        body = T(f"The new {note_kind['en']} will carry only the {left} remaining lines.",
                 f"الـ{note_kind['ar']} الجديد هياخد الـ{left} سطر الباقيين بس.",
                 f"Le nouvel {note_kind['fr']} ne portera que les {left} lignes restantes.")
    from accounting_portal.api.docedit import _line_orders
    orders = _line_orders(doc)
    x = {
        "code": "return_from_original", "severity": "warning", "icon": "refresh", "title": title, "body": body,
        "facts": [{"label": T("Already submitted", "مرحّل بالفعل", "Déjà validé"),
                   "value": p.name + (f" · {p.bill_no}" if buying and p.get("bill_no") else ""),
                   "amount": _money(p.grand_total, cur), "doc": {"doctype": doctype, "name": p.name}} for p in prior]
                 + [{"label": T("Draft", "مسودة", "Brouillon"), "value": f"{d.name} · {d.n}",
                     "amount": _money(d.grand_total, cur), "doc": {"doctype": doctype, "name": d.name}} for d in drafts],
        "lines": {
            "columns": [{"key": "idx", "label": T("Line", "السطر", "Ligne")},
                        {"key": "item", "label": T("Already returned", "اترجّع بالفعل", "Déjà retourné")},
                        {"key": "order", "label": T("Order", "الأوردر", "Commande")},
                        {"key": "amount", "label": T("Amount", "المبلغ", "Montant"), "num": True}],
            "rows": [{"idx": r.idx, "item": r.item_name or r.item_code, "order": orders.get(r.name) or "—",
                      "amount": _money(abs(flt(r.amount)), cur)} for r in gone]} if gone else None,
        "note": T(f"{len(drafts) - 1} more draft{'s' if len(drafts) > 2 else ''} on this bill.",
                  f"فيه {len(drafts) - 1} مسودة زيادة على نفس الفاتورة.",
                  f"{len(drafts) - 1} brouillon(s) de plus sur cette facture.") if len(drafts) > 1 else None,
        "actions": [],
    }
    if drafts:
        x["actions"].append({"kind": "open", "primary": True, "doctype": doctype, "name": drafts[0].name,
                             "label": T(f"Open the draft {drafts[0].name}", f"افتح المسودة {drafts[0].name}",
                                        f"Ouvrir le brouillon {drafts[0].name}")})
    if len(drafts) > 1:
        x["actions"].append({"kind": "delete_drafts", "doctype": doctype, "names": [d.name for d in drafts[1:]],
                             "label": T(f"Delete the {len(drafts) - 1} extra draft(s)", f"امسح الـ{len(drafts) - 1} مسودة الزيادة",
                                        f"Supprimer les {len(drafts) - 1} brouillons en trop")})
    return x


# ── 1c. Payment allocated beyond its amount ─────────────────────────────────
#
# PAY-54942: amount edited 3,597 → 2,000, still allocated 3,597 to order #268495.

def _payment_difference(doctype, name, message, **_):
    if doctype != "Payment Entry" or not name:
        return None
    doc = frappe.get_doc("Payment Entry", name)
    if doc.docstatus != 0:
        return None
    cur = doc.paid_to_account_currency if doc.payment_type == "Receive" else doc.paid_from_account_currency
    cur = cur or "MAD"
    amt = flt(doc.paid_amount if doc.payment_type == "Receive" else (doc.received_amount or doc.paid_amount))
    alloc = sum(flt(r.allocated_amount) for r in doc.references)
    if alloc <= amt + 0.005:
        return None
    return {
        "code": "payment_over_allocated", "severity": "warning", "icon": "bank",
        "title": T("The payment is allocated for more than its amount", "الدفعة متوزعة بأكتر من مبلغها",
                   "Le paiement est affecté au-delà de son montant"),
        "body": T(f"{name} is for {_money(amt, cur)} but still allocates {_money(alloc, cur)} to its documents — the amount was changed and the allocation was not. ERPNext refuses to post it until they match.",
                  f"{name} مبلغها {_money(amt, cur)} لكن لسه متوزع منها {_money(alloc, cur)} على المستندات — المبلغ اتغيّر والتوزيع ماتغيّرش. ERPNext مش هيرحّلها لحد ما يتساووا.",
                  f"{name} est de {_money(amt, cur)} mais affecte encore {_money(alloc, cur)} — le montant a changé, pas l'affectation. ERPNext refuse de la comptabiliser tant qu'ils diffèrent."),
        "facts": [{"label": T("Allocated to", "متوزع على", "Affecté à"), "value": f"{r.reference_doctype} {r.reference_name}",
                   "amount": _money(r.allocated_amount, cur), "doc": {"doctype": r.reference_doctype, "name": r.reference_name}}
                  for r in doc.references],
        "lines": None, "note": None,
        "actions": [{"kind": "realloc_payment", "primary": True, "doctype": "Payment Entry", "name": name,
                     "label": T(f"Allocate {_money(amt, cur)} and keep the payment as a draft",
                                f"وزّع {_money(amt, cur)} بس وسيب الدفعة مسودة",
                                f"Affecter {_money(amt, cur)} et garder le brouillon")},
                    {"kind": "open", "doctype": "Payment Entry", "name": name,
                     "label": T("Open the payment", "افتح الدفعة", "Ouvrir le paiement")}],
    }


# ── 2. A linked order is closed / on hold ────────────────────────────────────

_ORDER_RE = re.compile(r"(Purchase Order|Sales Order|Purchase Receipt|Delivery Note)\s+(.+?)\s+status is\s+(Closed|On Hold)")


def _closed_order(doctype, name, message, **_):
    m = _ORDER_RE.search(_clean(message))
    if not m:
        return None
    odt, oname, status = m.group(1), m.group(2).strip(), m.group(3)
    since = frappe.db.get_value(odt, oname, "modified") if frappe.db.exists(odt, oname) else None
    is_return = bool(doctype and name and frappe.db.get_value(doctype, name, "is_return")) if doctype in ("Purchase Invoice", "Sales Invoice") else False
    st = T(status.lower(), "مقفول" if status == "Closed" else "موقوف", "clôturé" if status == "Closed" else "en attente")
    x = {
        "code": "closed_order", "severity": "warning", "icon": "lock",
        "title": T(f"The order {oname} is {st['en']}", f"الأوردر {oname} {st['ar']}", f"La commande {oname} est {st['fr']}"),
        "body": T(f"One of the lines points at {odt} {oname}, which is {st['en']}"
                  f"{' since ' + formatdate(since) if since else ''}. ERPNext refuses any new document that references it.",
                  f"سطر من السطور مربوط بـ {oname}، وده {st['ar']}{' من ' + formatdate(since) if since else ''}. ERPNext بيرفض أي مستند جديد مربوط بيه.",
                  f"Une des lignes fait référence à {oname}, {st['fr']}{' depuis le ' + formatdate(since) if since else ''}. ERPNext refuse tout nouveau document qui la cite."),
        "facts": [], "lines": None, "note": None,
        "actions": [{"kind": "open", "doctype": odt, "name": oname,
                     "label": T("Open the order", "افتح الأوردر", "Ouvrir la commande")}],
    }
    if is_return and frappe.db.get_value(doctype, name, "docstatus") == 0:
        x["actions"].insert(0, {"kind": "unlink_closed", "primary": True, "doctype": doctype, "name": name,
                                "label": T("Drop the closed-order links from this return",
                                           "شيل ربط الأوردرات المقفولة من المرتجع ده",
                                           "Retirer les liens vers les commandes clôturées")})
        x["note"] = T("A return doesn't need to update a closed order: it still posts against its original bill.",
                      "المرتجع مش محتاج يحدّث أوردر مقفول، وهيترحّل على فاتورته الأصلية عادي.",
                      "Un retour n'a pas besoin de mettre à jour une commande clôturée : il reste rattaché à sa facture d'origine.")
    return x


# ── 3. Not enough stock ──────────────────────────────────────────────────────

_STOCK_RE = re.compile(r"([\d.,]+)\s+units of\s+(?:Item\s+)?(.+?)\s+needed in\s+(?:Warehouse\s+)?(.+?)\s+on\s+([\d-]+)")


def _negative_stock(doctype, name, message, **_):
    m = _STOCK_RE.search(_clean(message))
    if not m:
        return None
    qty, item, wh, on = m.group(1), m.group(2).strip(), m.group(3).strip(), m.group(4)
    item_code = item.split(":")[0].strip()
    now = flt(frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": wh}, "actual_qty"))
    return {
        "code": "negative_stock", "severity": "warning", "icon": "box",
        "title": T("Not enough stock", "المخزون مش كفاية", "Stock insuffisant"),
        "body": T(f"{qty} more unit(s) of {item} are needed in {wh} on {on}. The book stock there is too low at that date.",
                  f"محتاج {qty} وحدة زيادة من {item} في {wh} بتاريخ {on}. المخزون المسجّل هناك أقل من كده في التاريخ ده.",
                  f"Il manque {qty} unité(s) de {item} dans {wh} au {on}. Le stock comptable y est insuffisant à cette date."),
        "facts": [{"label": T("In stock today", "الموجود النهارده", "En stock aujourd'hui"), "value": f"{now:g}", "amount": None, "doc": None}],
        "lines": None,
        "note": T("Book the receipt first, pick another warehouse, or move the document's date to after the stock arrived.",
                  "سجّل الاستلام الأول، أو اختار مخزن تاني، أو غيّر تاريخ المستند لبعد ما البضاعة وصلت.",
                  "Enregistrez d'abord la réception, choisissez un autre entrepôt, ou datez le document après l'arrivée du stock."),
        "actions": [],
    }


# ── 4. Disabled price list ───────────────────────────────────────────────────

def _price_list(doctype, name, message, **_):
    m = re.search(r"Price List\s+(.+?)\s+is disabled", _clean(message))
    if not m:
        return None
    pl = m.group(1).strip()
    x = {
        "code": "price_list_disabled", "severity": "warning", "icon": "info",
        "title": T(f"The price list {pl} is disabled", f"قائمة الأسعار {pl} متوقفة", f"La liste de prix {pl} est désactivée"),
        "body": T("The document still carries a price list that was switched off. Your rates don't depend on it.",
                  "المستند لسه عليه قائمة أسعار اتوقفت. الأسعار اللي إنت كاتبها مش معتمدة عليها.",
                  "Le document porte encore une liste de prix désactivée. Vos prix n'en dépendent pas."),
        "facts": [], "lines": None, "note": None, "actions": [],
    }
    if doctype and name and frappe.db.get_value(doctype, name, "docstatus") == 0:
        x["actions"].append({"kind": "clear_price_list", "primary": True, "doctype": doctype, "name": name,
                             "label": T("Remove the price list from this draft", "شيل قائمة الأسعار من المسودة", "Retirer la liste de prix du brouillon")})
    return x


# ── 5. Due date before posting date ──────────────────────────────────────────

def _due_date(doctype, name, message, **_):
    if "Due Date cannot be before" not in _clean(message):
        return None
    d = frappe.db.get_value(doctype, name, ["posting_date", "due_date", "bill_date"], as_dict=True) if doctype and name else None
    facts = []
    if d:
        for f, lbl in (("posting_date", T("Posting date", "تاريخ القيد", "Date comptable")),
                       ("bill_date", T("Supplier invoice date", "تاريخ فاتورة المورد", "Date facture fournisseur")),
                       ("due_date", T("Due date", "تاريخ الاستحقاق", "Échéance"))):
            if d.get(f):
                facts.append({"label": lbl, "value": formatdate(d[f]), "amount": None, "doc": None})
    return {
        "code": "due_date", "severity": "warning", "icon": "clock",
        "title": T("The due date is before the invoice date", "تاريخ الاستحقاق قبل تاريخ الفاتورة", "L'échéance est avant la date de facture"),
        "body": T("The payment schedule still uses an older date. Set the due date on or after the posting and supplier invoice dates.",
                  "جدول الدفع لسه على تاريخ قديم. خلّي تاريخ الاستحقاق في نفس يوم أو بعد تاريخ القيد وتاريخ فاتورة المورد.",
                  "L'échéancier utilise encore une ancienne date. Mettez l'échéance au plus tôt à la date comptable et à la date de la facture fournisseur."),
        "facts": facts, "lines": None, "note": None, "actions": [],
    }


# ── 6. Bank payment without a reference ──────────────────────────────────────

def _bank_ref(doctype, name, message, **_):
    if "Reference No and Reference Date is mandatory" not in _clean(message):
        return None
    return {
        "code": "bank_reference", "severity": "warning", "icon": "bank",
        "title": T("The transfer reference is missing", "رقم التحويل ناقص", "La référence du virement manque"),
        "body": T("A bank payment needs the transfer number and its date, exactly as they appear on the bank statement.",
                  "أي دفعة بنكية محتاجة رقم التحويل وتاريخه زي ما هما في كشف البنك.",
                  "Un paiement bancaire exige le numéro du virement et sa date, tels qu'ils figurent sur le relevé."),
        "facts": [], "lines": None, "note": None, "actions": [],
    }


# ── 7. Supplier invoice number already used ──────────────────────────────────

def _dup_bill_no(doctype, name, message, **_):
    m = re.search(r"Supplier Invoice No exists in Purchase Invoice\s+(\S+)", _clean(message))
    if not m:
        return None
    other = m.group(1).strip().rstrip(".")
    return {
        "code": "duplicate_bill_no", "severity": "warning", "icon": "copy",
        "title": T("This supplier invoice is already booked", "فاتورة المورد دي متسجلة قبل كده", "Cette facture fournisseur est déjà saisie"),
        "body": T(f"The same supplier invoice number is on {other}. Booking it twice would make you pay twice.",
                  f"نفس رقم فاتورة المورد موجود على {other}. تسجيلها مرتين يعني هتدفعها مرتين.",
                  f"Le même numéro de facture fournisseur figure sur {other}. La saisir deux fois la ferait payer deux fois."),
        "facts": [], "lines": None, "note": None,
        "actions": [{"kind": "open", "doctype": "Purchase Invoice", "name": other, "primary": True,
                     "label": T("Open the existing bill", "افتح الفاتورة الموجودة", "Ouvrir la facture existante")}],
    }


_HANDLERS = [
    (re.compile(r"StockOverReturnError|has already been returned"), _over_return),
    (re.compile(r"StockOverReturnError|has already been returned|already has a draft return"), _original_returned),
    (re.compile(r"InvalidStatusError|status is (Closed|On Hold)"), _closed_order),
    (re.compile(r"NegativeStockError|units of .* needed in"), _negative_stock),
    (re.compile(r"Price List .* is disabled"), _price_list),
    (re.compile(r"Due Date cannot be before"), _due_date),
    (re.compile(r"Reference No and Reference Date is mandatory"), _bank_ref),
    (re.compile(r"Supplier Invoice No exists"), _dup_bill_no),
    (re.compile(r"Difference Amount must be zero"), _payment_difference),
]


def _generic(message):
    clean = _clean(message) or "—"
    return {
        "code": "generic", "severity": "danger", "icon": "alert",
        "title": T("The action didn't go through", "العملية ماتمتش", "L'opération n'a pas abouti"),
        "body": {"en": clean, "ar": clean, "fr": clean},
        "facts": [], "lines": None, "note": None, "actions": [],
    }


@frappe.whitelist()
def explain(exc_type=None, message=None, args=None):
    """Explain a failed write. Always returns an explanation (generic at worst)."""
    assert_portal_access()
    try:
        args = args if isinstance(args, dict) else json.loads(args or "{}")
    except Exception:
        args = {}
    doctype, name = _doc_from_args(args or {})
    raw = f"{exc_type or ''}: {message or ''}".strip(": ")
    x = None
    for pat, fn in _HANDLERS:
        if pat.search(raw):
            try:
                x = fn(doctype=doctype, name=name, message=message or "")
            except Exception:
                frappe.log_error(title="error_explain handler failed", message=frappe.get_traceback())
                x = None
            if x:
                break
    x = x or _generic(message)
    x["technical"] = raw[:600]
    try:
        frappe.cache().hincrby("ap_error_explain", x["code"], 1)
    except Exception:
        pass
    return x


# ── Action endpoints (drafts only, gated, audited) ───────────────────────────

_EDITABLE = ("Purchase Invoice", "Sales Invoice", "Payment Entry")


def _draft(doctype, name, company):
    assert_can_write()
    if doctype not in _EDITABLE or not name or not frappe.db.exists(doctype, name):
        frappe.throw("Not available for this document")
    doc = frappe.get_doc(doctype, name)
    if doc.company not in resolve_companies(company):
        frappe.throw("Not permitted", frappe.PermissionError)
    if doc.docstatus != 0:
        frappe.throw("Only a draft can be changed here")
    return doc


def _log(doc, notes, payload):
    _actions.record("Edit draft", doc.company, reference_doctype=doc.doctype, reference_name=doc.name,
                    voucher_type=doc.doctype, voucher_no=doc.name, amount=0,
                    payload=json.dumps(payload), result=json.dumps({"saved": doc.name}), notes=notes)


@frappe.whitelist()
def remove_lines(doctype=None, name=None, rows=None, company=None):
    doc = _draft(doctype, name, company)
    rows = set(rows if isinstance(rows, list) else json.loads(rows or "[]"))
    gone = [r for r in doc.items if r.name in rows]
    if not gone or len(gone) == len(doc.items):
        frappe.throw("Nothing to remove, or it would leave the document empty")
    for r in gone:
        doc.remove(r)
    for i, r in enumerate(doc.items, 1):
        r.idx = i
    doc.flags.ignore_permissions = True
    doc.save()
    _log(doc, f"Removed {len(gone)} line(s) already returned", {"removed": [r.item_code for r in gone]})
    return {"name": doc.name, "lines": len(doc.items), "grand_total": doc.grand_total}


@frappe.whitelist()
def delete_drafts(doctype=None, names=None, company=None):
    names = names if isinstance(names, list) else json.loads(names or "[]")
    done = []
    for n in names:
        doc = _draft(doctype, n, company)
        company_of = doc.company
        frappe.delete_doc(doctype, n, ignore_permissions=True)
        _actions.record("Delete draft", company_of, reference_doctype=doctype, reference_name=n,
                        voucher_type=doctype, voucher_no=n, amount=0, payload=json.dumps({"name": n}),
                        result=json.dumps({"deleted": n}), notes=f"Deleted duplicate draft {n} from the error popup")
        done.append(n)
    return {"deleted": done}


@frappe.whitelist()
def unlink_closed(doctype=None, name=None, company=None):
    doc = _draft(doctype, name, company)
    from accounting_portal.api.docflow import _unlink_closed_orders
    _unlink_closed_orders(doc)
    doc.flags.ignore_permissions = True
    doc.save()
    _log(doc, "Dropped closed-order links from a return", {})
    return {"name": doc.name}


@frappe.whitelist()
def clear_price_list(doctype=None, name=None, company=None):
    doc = _draft(doctype, name, company)
    for f in ("buying_price_list", "selling_price_list"):
        if doc.meta.has_field(f):
            doc.set(f, None)
    doc.flags.ignore_permissions = True
    doc.save()
    _log(doc, "Cleared a disabled price list", {})
    return {"name": doc.name}


@frappe.whitelist()
def realloc_payment(doctype=None, name=None, company=None):
    """Cap a draft payment's allocations at its amount (oldest reference first)."""
    doc = _draft("Payment Entry", name, company)
    from accounting_portal.api.docedit import realloc_payment as _realloc
    before = {r.reference_name: flt(r.allocated_amount) for r in doc.references}
    _realloc(doc)
    doc.flags.ignore_permissions = True
    doc.save()
    _log(doc, "Re-allocated a payment", {"before": before,
                                         "after": {r.reference_name: flt(r.allocated_amount) for r in doc.references}})
    return {"name": doc.name}

