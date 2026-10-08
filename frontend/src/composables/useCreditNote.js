// Supplier credit note = ERPNext "Debit Note" (a return Purchase Invoice against
// a posted bill). Created as a DRAFT through the audited document flow, so the
// accountant trims it to what the supplier actually credits before submitting.
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";

export async function openCreditNoteDraft(bill) {
  const r = await api.call("accounting_portal.api.docflow.create",
    { doctype: "Purchase Invoice", name: bill, key: "debit_note", company: currentCompany() });
  let res = r && r.result;
  res = typeof res === "string" ? JSON.parse(res) : res;
  if (!res || !res.new_doc) throw new Error("The credit note draft was not created");
  return res.new_doc;
}
