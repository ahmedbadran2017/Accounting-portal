// Batch actions for a server-paginated document list. One composable, one
// BulkBar contract, so every transaction list (journals, invoices, bills,
// payments, orders) offers the same set.
//
// Submit, cancel and delete post to the ledger and go through api/bulk.py —
// audited, gated by the batch total. Assign, tag and print do not: an
// assignment is a ToDo, a tag is a label, a print is a read. The Desk list view
// offers all six, and the three that were missing are why a sixty-invoice split
// across three people meant sixty clicks here and one there.
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

  // Frappe renders the batch straight to one PDF. The names travel in the query
  // string, so this is capped well below the Desk's 500 — a URL has a limit and
  // a silently truncated print is worse than a refused one.
  const PRINT_MAX = 50;
  function printSelected() {
    const names = [...T().selected.value];
    if (names.length > PRINT_MAX) {
      toast.error(L(`Print up to ${PRINT_MAX} at a time (${names.length} selected)`,
        `اطبع ${PRINT_MAX} كحد أقصى في المرة (المحدد ${names.length})`,
        `Jusqu'à ${PRINT_MAX} à la fois (${names.length} sélectionnés)`));
      return;
    }
    const q = new URLSearchParams({ doctype, name: JSON.stringify(names), no_letterhead: "0" });
    window.open(`/api/method/frappe.utils.print_format.download_multi_pdf?${q.toString()}`, "_blank", "noopener");
  }

  async function call(fn, args, done) {
    const st = T();
    try {
      const r = await api.call(`accounting_portal.api.bulk.${fn}`, {
        doctype, names: [...st.selected.value], company: currentCompany(), ...args });
      toast.success(done(r));
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
    { key: "assign", label: L("Assign", "إسناد", "Assigner"), icon: "user", color: "#0369a1",
      prompt: {
        kind: "user",
        label: L("Assign the selection to", "إسناد المحدد إلى", "Assigner la sélection à"),
        options: () => api.call("accounting_portal.api.docops.assignable_users", {}),
      },
      run: (_rows, user) => call("bulk_assign", { to_user: user },
        (r) => L(`Assigned ${r.assigned} to ${r.user}${r.already ? ` · ${r.already} already were` : ""}`,
                 `تم إسناد ${r.assigned} إلى ${r.user}${r.already ? ` · ${r.already} كانوا مُسندين` : ""}`,
                 `${r.assigned} assignés à ${r.user}`)) },
    { key: "tag", label: L("Tag", "وسم", "Étiqueter"), icon: "flag", color: "#7c3aed",
      prompt: {
        kind: "text",
        label: L("Add a tag to the selection", "أضف وسمًا للمحدد", "Ajouter une étiquette"),
        placeholder: L("e.g. to-review", "مثال: للمراجعة", "ex. à-revoir"),
      },
      run: (_rows, tag) => call("bulk_tag", { tag },
        (r) => L(`Tagged ${r.tagged} with "${r.tag}"`, `تم وسم ${r.tagged} بـ "${r.tag}"`, `${r.tagged} étiquetés`)) },
    { key: "print", label: L("Print", "طباعة", "Imprimer"), icon: "doc", color: "#44403c",
      run: () => printSelected() },
  ];
  return { actions };
}
