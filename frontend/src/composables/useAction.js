import api from "@/services/api";

// Front door for the write gateway (api/_actions.py). Pillars that post to
// ERPNext surface their actions through here so the UI gets one consistent
// approve / reject / audit flow. Individual pillar writes (match remittance,
// post correction…) call their own endpoints, which route through execute().
export function useAction() {
  const listActions = (company, status, limit = 50) =>
    api.call("accounting_portal.api._actions.list_actions", { company, status, limit });
  const approve = (name) => api.call("accounting_portal.api._actions.approve_action", { name });
  const reject = (name, reason) => api.call("accounting_portal.api._actions.reject_action", { name, reason });
  return { listActions, approve, reject };
}
