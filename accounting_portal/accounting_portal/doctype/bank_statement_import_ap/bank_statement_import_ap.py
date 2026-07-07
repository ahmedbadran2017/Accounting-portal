# Copyright (c) 2026, Justyol
# A persisted bank-statement reconciliation session: the uploaded file, its
# parsed lines with per-line status (pending/matched/created/ignored), and the
# running stats. The workbench reads/writes lines through api/bank_workbench.py.
from frappe.model.document import Document


class BankStatementImportAP(Document):
    pass
