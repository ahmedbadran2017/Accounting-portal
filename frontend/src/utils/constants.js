// Shared constants — single source of truth.

export const ASSET_BASE = import.meta.env.DEV ? "" : "/assets/accounting_portal";
export const asset = (path) => `${ASSET_BASE}${path}`;

// Route paths (client-side, under the /accounting mount).
export const ROUTES = {
  LOGIN: "/accounting/login",
  DASHBOARD: "/accounting/dashboard",
  PAYABLES: "/accounting/payables",
  RECEIVABLES: "/accounting/receivables",
  GENERAL_LEDGER: "/accounting/general-ledger",
  REPORTS: "/accounting/reports",
};

// API endpoints.
export const API = {
  LOGIN: "/api/method/login",
  LOGOUT: "/api/method/logout",
  SESSION_INFO: "accounting_portal.api.auth.get_session_info",
  WHOAMI: "/api/method/accounting_portal.api.permissions.whoami",
};
