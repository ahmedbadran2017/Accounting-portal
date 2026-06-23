/**
 * Shared utilities for the Accounting Portal frontend.
 * Mirrors the supplier portal's helper contract (frappeApi + error extraction)
 * so composables behave identically.
 */

let _csrfToken = null;

/** CSRF token for Frappe API requests (cached for the session). */
export function getCsrfToken() {
  if (_csrfToken) return _csrfToken;
  _csrfToken =
    window.csrf_token ||
    document.cookie.match(/csrf_token=([^;]+)/)?.[1] ||
    "";
  return _csrfToken;
}

// Redirect-once guard so N parallel 401s don't loop the login redirect.
let _authExpiryHandled = false;

function handleAuthExpiry() {
  if (_authExpiryHandled) return;
  _authExpiryHandled = true;
  _csrfToken = null;
  try { localStorage.removeItem("ap_auth"); } catch {}
  const here = window.location.pathname + window.location.search;
  if (here.startsWith("/accounting/login") || here === "/" || here === "/accounting") return;
  window.location.assign(`/accounting/login?redirect=${encodeURIComponent(here)}`);
}

/** Authenticated Frappe API call with CSRF + JSON. Returns the raw Response. */
export async function frappeApi(url, body = null, options = {}) {
  const { method = "POST", ...rest } = options;
  const res = await fetch(url, {
    method,
    headers: {
      "Content-Type": "application/json",
      "X-Frappe-CSRF-Token": getCsrfToken(),
    },
    body: body ? JSON.stringify(body) : undefined,
    ...rest,
  });
  // 401 = expired session → bounce to login. 403 may be a legit per-action
  // permission error, so don't log the user out for it.
  if (res.status === 401) handleAuthExpiry();
  return res;
}

/** Pull the most useful human-readable message out of a Frappe error shape. */
export function extractApiError(e, fallback = "common.error_loading", t = null) {
  if (!e) return t ? t(fallback) : fallback;
  if (typeof e === "string") return e;
  if (Array.isArray(e.messages) && e.messages[0]) return e.messages[0];
  if (typeof e.exception === "string") return e.exception;
  if (typeof e._server_messages === "string") {
    try {
      const arr = JSON.parse(e._server_messages);
      if (Array.isArray(arr) && arr[0]) {
        const obj = JSON.parse(arr[0]);
        if (obj?.message) return String(obj.message).replace(/<[^>]+>/g, "");
      }
    } catch {}
  }
  if (typeof e.message === "string") return e.message;
  return t ? t(fallback) : fallback;
}

export function parseServerMessage(result, fallback = "An error occurred") {
  try {
    if (result?._server_messages) {
      const messages = JSON.parse(result._server_messages);
      if (messages?.[0]) {
        const parsed = JSON.parse(messages[0]);
        return parsed.message || fallback;
      }
    }
  } catch {}
  return result?.message || fallback;
}

// ── Formatting ──

/**
 * Format a money amount with thousands separators and a currency suffix.
 * Internal finance tool → 2 decimals, grouped, currency code after the number
 * (matches how the team reads TRY / USD / MAD figures).
 */
export function fmtMoney(amount, currency = "", decimals = 2) {
  const n = Number(amount || 0);
  const s = n.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
  return currency ? `${s} ${currency}` : s;
}

export function fmtDate(s, fallback = "—") {
  if (!s) return fallback;
  const d = new Date(s);
  return isNaN(d) ? fallback : d.toLocaleDateString();
}
