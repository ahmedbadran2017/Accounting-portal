/* Justyol Partners — service worker (served at /partners-sw.js (file partners_sw.js), scope /accounting/partners).
 *
 * - Opens offline: the page shell and the last numbers are kept; the page says
 *   how old they are.
 * - Morning summary: the server sends an EMPTY push (no payload, so nothing to
 *   decrypt); this worker asks the server for the text and shows it.
 */
const VERSION = "partners-v1";
const SHELL = "/accounting/partners";
const SUMMARY = "/api/method/accounting_portal.api.partners.get_summary";
const DIGEST = "/api/method/accounting_portal.api.partners.digest";
const ICON = "/assets/accounting_portal/partners/icon-192.png";
const BADGE = "/assets/accounting_portal/partners/badge-96.png";

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.add(new Request(SHELL, { credentials: "same-origin" })).catch(() => null)));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil((async () => {
    for (const k of await caches.keys()) if (k !== VERSION) await caches.delete(k);
    await self.clients.claim();
  })());
});

async function networkFirst(req, key) {
  const cache = await caches.open(VERSION);
  try {
    const res = await fetch(req);
    if (res && res.ok) cache.put(key || req, res.clone());
    return res;
  } catch (err) {
    const hit = await cache.match(key || req);
    if (hit) return hit;
    throw err;
  }
}

async function cacheFirst(req) {
  const cache = await caches.open(VERSION);
  const hit = await cache.match(req);
  if (hit) return hit;
  const res = await fetch(req);
  if (res && res.ok) cache.put(req, res.clone());
  return res;
}

self.addEventListener("fetch", (e) => {
  const req = e.request;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (req.method === "GET" && req.mode === "navigate" && url.pathname.startsWith(SHELL)) {
    e.respondWith(networkFirst(req, SHELL));
    return;
  }
  // the numbers: always fresh when online, the last copy when not (POST → keyed as a GET)
  if (url.pathname === SUMMARY) {
    e.respondWith((async () => {
      const key = new Request(SUMMARY);
      const cache = await caches.open(VERSION);
      try {
        const res = await fetch(req.clone());
        if (res && res.ok) cache.put(key, res.clone());
        return res;
      } catch (err) {
        const hit = await cache.match(key);
        if (hit) {
          const body = await hit.text();
          return new Response(body, { headers: { "Content-Type": "application/json", "X-From-Cache": "1" } });
        }
        throw err;
      }
    })());
    return;
  }
  // built bundle files never change under the same name (hashed chunks, ?v= stamped entry)
  if (req.method === "GET" && url.pathname.startsWith("/assets/accounting_portal/")) {
    e.respondWith(cacheFirst(req));
  }
});

self.addEventListener("push", (e) => {
  e.waitUntil((async () => {
    let lang = "ar";
    try { const c = await self.clients.matchAll({ type: "window" }); if (c[0] && /lang=en/.test(c[0].url)) lang = "en"; } catch (_) { /* default */ }
    let n = { title: "Justyol", body: "أرقام إمبارح جاهزة — افتح اللوحة", url: SHELL, tag: "partners-daily" };
    try {
      const res = await fetch(DIGEST + "?lang=" + lang, { credentials: "same-origin" });
      if (res.ok) { const j = await res.json(); if (j && j.message) n = j.message; }
    } catch (_) { /* keep the generic text */ }
    await self.registration.showNotification(n.title, {
      body: n.body, icon: ICON, badge: BADGE, tag: n.tag, renotify: true, dir: lang === "en" ? "ltr" : "rtl",
      lang, data: { url: n.url || SHELL },
    });
  })());
});

self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const target = (e.notification.data && e.notification.data.url) || SHELL;
  e.waitUntil((async () => {
    const wins = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    for (const w of wins) if (w.url.includes(SHELL)) { await w.focus(); return; }
    await self.clients.openWindow(target);
  })());
});
