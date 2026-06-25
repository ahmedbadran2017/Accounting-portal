import api from "@/services/api";
import { useToast } from "@/composables/useToast";
import { currentCompany } from "@/composables/useLive";

// Build Submit/Cancel BulkBar action descriptors for one doctype. Routed through
// the gated/audited backend (accounting_portal.api.bulk). `keyField` is the row
// property holding the document name; `onDone` refreshes the list.
export function useBulkDocActions(doctype, { keyField = "name", onDone, L, ops = ["submit", "cancel"] }) {
  const toast = useToast();
  const names = (rows) => rows.map((r) => r[keyField]).filter(Boolean);

  async function run(fn, rows, okMsg) {
    try {
      const res = await api.call(fn, { doctype, names: names(rows), company: currentCompany() });
      const r = res && res.result ? res.result : null;
      if (res && res.status === "Proposed") {
        toast.info(L("Sent for approval (material total)", "أُرسل للموافقة (مبلغ كبير)", "Approbation requise"));
      } else {
        const ok = r && r.ok != null ? r.ok : rows.length;
        const fail = r && r.fail ? r.fail : 0;
        toast.success(okMsg + ` · ${ok}` + (fail ? ` · ${fail} ${L("failed", "فشل", "échec")}` : ""));
        onDone && onDone();
      }
    } catch (e) { toast.error(String((e && e.message) || L("Failed", "فشل", "Échec")).slice(0, 160)); }
  }

  const all = [
    { key: "submit", label: L("Submit", "ترحيل", "Soumettre"), icon: "check", color: "#0369a1",
      confirm: (rows) => L(`Submit ${rows.length} document(s)?`, `ترحيل ${rows.length} مستند؟`, `Soumettre ${rows.length} ?`),
      run: (rows) => run("accounting_portal.api.bulk.bulk_submit", rows, L("Submitted", "تم الترحيل", "Soumis")) },
    { key: "cancel", label: L("Cancel", "إلغاء", "Annuler"), icon: "x", color: "#be123c",
      confirm: (rows) => L(`Cancel ${rows.length} document(s)? This reverses their journal entries.`, `إلغاء ${rows.length} مستند؟ سيُعكَس القيد المحاسبي.`, `Annuler ${rows.length} ? Les écritures seront annulées.`),
      run: (rows) => run("accounting_portal.api.bulk.bulk_cancel", rows, L("Cancelled", "تم الإلغاء", "Annulé")) },
  ];
  return all.filter((a) => ops.includes(a.key));
}
