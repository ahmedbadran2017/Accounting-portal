/**
 * Shared utilities for the Accounting Portal frontend.
 * Mirrors the supplier portal's helper contract (frappeApi + error extraction)
 * so composables behave identically.
 */

let _csrfToken = null;

/** Fresh per-form-open nonce so the write gateway can tell a double-click
 * (same key → deduped) from a genuinely separate identical entry (new key → posts). */
export function newClientKey() {
  const c = typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : "";
  return c || `ck-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

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
// A request with no timeout can hang for as long as the browser will hold it.
// When that happened the screen kept its loading skeleton forever: the activity
// panel span spinning and the document action bar simply never appeared, with
// nothing on screen or in the log to say why. Every call now gives up and
// reports instead of waiting silently.
const REQUEST_TIMEOUT_MS = 45000;

export async function frappeApi(url, body = null, options = {}) {
  const { method = "POST", timeout = REQUEST_TIMEOUT_MS, ...rest } = options;
  const ctl = typeof AbortController !== "undefined" ? new AbortController() : null;
  const timer = ctl && timeout ? setTimeout(() => ctl.abort(), timeout) : null;
  let res;
  try {
    res = await fetch(url, {
      method,
      headers: {
        "Content-Type": "application/json",
        "X-Frappe-CSRF-Token": getCsrfToken(),
      },
      body: body ? JSON.stringify(body) : undefined,
      signal: ctl ? ctl.signal : undefined,
      ...rest,
    });
  } catch (e) {
    if (e && e.name === "AbortError") {
      const err = new Error(`The server did not answer within ${Math.round(timeout / 1000)}s.`);
      err.status = 0;
      err.timeout = true;
      throw err;
    }
    throw e;
  } finally {
    if (timer) clearTimeout(timer);
  }
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
// The locale is pinned deliberately. Passing `undefined` follows the browser,
// and an Arabic browser renders Arabic-Indic numerals — which nobody here reads
// in a ledger. Grouping and digit shape stay the same in all three languages;
// only the words around the number change.
const NUM_LOCALE = "en-US";

export function fmtMoney(amount, currency = "", decimals = 2) {
  const n = Number(amount || 0);
  const s = n.toLocaleString(NUM_LOCALE, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
  return currency ? `${s} ${currency}` : s;
}

/**
 * Exact amount for accounting display: grouped thousands, full integer part,
 * up to 2 decimals only when the value actually has them (no ".00" clutter, and
 * crucially NO K/M abbreviation — an accounting system shows every digit).
 * 174230 → "174,230"   128844.735 → "128,844.74"   -1234.5 → "-1,234.5"
 */
export function fmtAmount(n) {
  return Number(n || 0).toLocaleString(NUM_LOCALE, { maximumFractionDigits: 2 });
}

/** Whole units — for counts and for totals where the decimals are noise. */
export function fmtWhole(n) {
  return Math.round(Number(n || 0)).toLocaleString(NUM_LOCALE);
}

export function fmtDate(s, fallback = "—") {
  if (!s) return fallback;
  const d = new Date(s);
  return isNaN(d) ? fallback : d.toLocaleDateString();
}

/** Where a document lives in the portal.
 *
 * There were six of these maps plus seven hand-written branches, and they
 * disagreed: only the General Ledger checked the party type on a Payment Entry,
 * so everywhere else a customer receipt opened the supplier-payment screen. Two
 * of them also pointed Purchase Orders at `purchases/orders`, a sub that does
 * not exist, and landed the user on the "pending build" placeholder.
 *
 * Returns null when the doctype has no portal page — callers use that to decide
 * whether a row is clickable at all, instead of showing a hand cursor that does
 * nothing.
 */
const DOC_PATHS = {
  "Sales Invoice":        "sales/invoices",
  "Sales Order":          "sales/orders",
  "Delivery Note":        "sales/challans",
  "Purchase Invoice":     "purchases/bills",
  "Purchase Order":       "purchases/tobuy",
  "Purchase Receipt":     "purchases/received",
  "Journal Entry":        "accountant/journals",
  "Landed Cost Voucher":  "items/landed",
  "Item":                 "items/items",
  "Customer":             "sales/customers",
  "Supplier":             "purchases/vendors",
};

export function routeForDoc(doctype, name, partyType) {
  if (!doctype || !name) return null;
  if (doctype === "Payment Entry") {
    // A receipt from a customer belongs under Sales; a payment to a supplier
    // under Purchases. Sending both to Purchases was the most common misroute.
    const path = partyType === "Customer" ? "/accounting/sales/payments" : "/accounting/purchases/payments";
    return { path, query: { id: name } };
  }
  const p = DOC_PATHS[doctype];
  return p ? { path: `/accounting/${p}`, query: { id: name } } : null;
}

/** Short codes the activity and audit screens use, mapped to real doctypes. */
export const DOC_CODE = {
  SI: "Sales Invoice", SO: "Sales Order", DN: "Delivery Note",
  PI: "Purchase Invoice", PO: "Purchase Order", PR: "Purchase Receipt",
  JE: "Journal Entry", PE: "Payment Entry", LCV: "Landed Cost Voucher",
};
