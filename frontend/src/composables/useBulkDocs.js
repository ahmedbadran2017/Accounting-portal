// Bulk submit / cancel / delete-drafts for a server-paginated document list.
// One composable, one BulkBar contract, so every transaction list (journals,
// invoices, bills, payments, orders) offers the same three batch actions the
// ERPNext list view did — routed through api/bulk.py (audited, gated by total).
import { useI18n } from "vue-i18n";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useToast } from "@/composables/useToast";

export function useBulkDocs(doctype, table) {
  const { locale } = useI18n();
  const toast = useToast();
  const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
  // `table` may be a getter so the composable can be wired before the table const exists.
  const T = () => (typeof table === "function" ? table() : table);
  const n = () => T().selected.value.size;

  async function run(fn, verb) {
    const st = T();
    const names = [...st.selected.value];
    if (!names.length) return;
    try {
      const r = await api.call(`accounting_portal.api.bulk.${fn}`, { doctype, names, company: currentCompany() });
      if (r && r.status && r.status !== "Posted") {
        toast.success(L("Queued for approval (batch over 10,000)", "بانتظار الموافقة (الدفعة فوق 10٬000)", "En attente d'approbation"));
      } else {
        let res = r && r.result; res = typeof res === "string" ? JSON.parse(res) : res;
        const ok = res?.ok ?? names.length, fail = res?.fail || 0;
        (fail ? toast.error : toast.success)(`${verb}: ${ok} ${L("done", "تم", "ok")}${fail ? ` · ${fail} ${L("failed", "فشل", "échec")}` : ""}`);
      }
      st.clearSelection(); st.load();
    } catch (e) { toast.error(String(e?.message || e).slice(0, 180)); }
  }

  const actions = [
    { key: "submit", label: L("Submit", "ترحيل", "Soumettre"), icon: "check", color: "#047857",
      run: () => run("bulk_submit", L("Submitted", "تم الترحيل", "Soumis")),
      confirm: () => L(`Submit ${n()} selected?`, `ترحيل ${n()} مستند؟`, `Soumettre ${n()} ?`) },
    { key: "cancel", label: L("Cancel", "إلغاء", "Annuler"), icon: "close", color: "#be123c",
      run: () => run("bulk_cancel", L("Cancelled", "تم الإلغاء", "Annulé")),
      confirm: () => L(`Cancel ${n()} submitted documents? This reverses their ledger entries.`, `إلغاء ${n()} مستند مرحّل؟ ده بيعكس قيودهم.`, `Annuler ${n()} documents ?`) },
    { key: "delete", label: L("Delete drafts", "حذف المسودات", "Supprimer brouillons"), icon: "close", color: "#57534e",
      run: () => run("bulk_delete", L("Deleted", "تم الحذف", "Supprimé")),
      confirm: () => L(`Delete ${n()} drafts for good? Submitted rows are skipped.`, `حذف ${n()} مسودة نهائيًا؟ المرحّل بيتخطى.`, `Supprimer ${n()} brouillons ?`) },
  ];
  return { actions };
}
