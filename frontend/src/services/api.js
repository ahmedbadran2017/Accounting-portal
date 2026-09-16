/**
 * Thin wrapper over frappeApi exposing `api.call(method, args)`.
 *  - method: dotted Python path, e.g. "accounting_portal.api.dashboard.get_overview"
 *  - args:   optional plain object → POST body
 * Resolves to Frappe's `.message` envelope value, or throws an Error whose
 * `.message` carries a human-readable cause.
 *
 * Performance layer (safe by construction):
 *  1. In-flight dedupe — identical concurrent reads share one request (no
 *     staleness risk; the entry is dropped as soon as it resolves).
 *  2. Short read-cache — a successful READ is cached for a few seconds so
 *     navigating away and back renders instantly instead of re-hitting a 1–2s
 *     aggregate. ANY write flushes the whole cache, so a read after a write is
 *     always fresh. Only clearly-read methods are ever cached.
 */
import { reactive } from "vue";
import { frappeApi, extractApiError } from "@/utils/helpers";

// Real connectivity signal for the header chip (it used to be a hardcoded green
// "synced" dot). ok flips false on a network/5xx failure and back on the next
// success; `samples` counts screens that fell back to sample data this session.
export const apiHealth = reactive({ ok: true, lastOk: 0, lastFail: 0, fails: 0, samples: 0, sampleMethods: [] });

const READ_TTL_MS = 12000;
// A method is a cacheable read if its function name starts with a read verb or
// carries a read token. Everything else (create/post/mark/clear/revert/close/…)
// is treated as a write: never cached, and it flushes the cache first.
const READ_RE = /(^|\.)(get|list|search|whoami)[a-z_]*$|(cockpit|summary|overview|trial|balance|aging|forecast|statement|recon|health|breakdown|transactions|digest|feed|report|options|settlements|remittance|ledger|detail|history|status|fixable|revertable|employees|runs|components|consolidated|preview)/i;

const _cache = new Map();    // key → { ts, value }
const _inflight = new Map(); // key → Promise

function isRead(method) { return READ_RE.test(method); }
function keyOf(method, args) { return method + "|" + (args ? JSON.stringify(args) : ""); }

function bustCache() { _cache.clear(); }

async function _fetch(method, args) {
  const url = `/api/method/${method}`;
  const res = await frappeApi(url, args || {});
  let body;
  try { body = await res.json(); } catch { body = null; }
  if (!res.ok) {
    const err = new Error(extractApiError(body) || `HTTP ${res.status}`);
    err.status = res.status;
    err._body = body;
    if (res.status >= 500 || res.status === 0) { apiHealth.ok = false; apiHealth.lastFail = Date.now(); apiHealth.fails++; }
    throw err;
  }
  apiHealth.ok = true; apiHealth.lastOk = Date.now();
  return body && "message" in body ? body.message : body;
}

async function call(method, args = null, opts = null) {
  const read = isRead(method) && !(opts && opts.fresh);
  // A write invalidates every cached read so nothing goes stale after a mutation.
  if (!isRead(method)) bustCache();

  const key = keyOf(method, args);
  if (read) {
    const hit = _cache.get(key);
    if (hit && Date.now() - hit.ts < READ_TTL_MS) return hit.value;
    const pending = _inflight.get(key);
    if (pending) return pending;
  }

  const p = _fetch(method, args)
    .then((value) => { if (read) _cache.set(key, { ts: Date.now(), value }); return value; })
    .finally(() => { _inflight.delete(key); });
  if (read) _inflight.set(key, p);
  return p;
}

export const api = { call, bustCache };
export default api;
