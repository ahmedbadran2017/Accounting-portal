/**
 * Thin wrapper over frappeApi exposing `api.call(method, args)`.
 *  - method: dotted Python path, e.g. "accounting_portal.api.dashboard.get_overview"
 *  - args:   optional plain object → POST body
 * Resolves to Frappe's `.message` envelope value, or throws an Error whose
 * `.message` carries a human-readable cause.
 */
import { frappeApi, extractApiError } from "@/utils/helpers";

async function call(method, args = null) {
  const url = `/api/method/${method}`;
  const res = await frappeApi(url, args || {});
  let body;
  try { body = await res.json(); } catch { body = null; }
  if (!res.ok) {
    const err = new Error(extractApiError(body) || `HTTP ${res.status}`);
    err.status = res.status;
    err._body = body;
    throw err;
  }
  return body && "message" in body ? body.message : body;
}

export const api = { call };
export default api;
