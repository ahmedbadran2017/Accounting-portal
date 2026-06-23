// Post-build asset URL rewrite. Vite's base + renderBuiltUrl still don't catch
// url() references inside compiled CSS that came in via @fontsource (the font
// CSS is imported from JS; its url() values get written off the assetsDir root
// — not the configured base). On prod the SPA is served at
// /assets/accounting_portal/, so a CSS ref of url(/assets/inter-...woff2) 404s.
// This reads app.css and prefixes every bare /assets/<file> url(). Idempotent.
import fs from "node:fs";
import path from "node:path";

const ROOT = path.resolve(new URL("../", import.meta.url).pathname);
const CSS = path.join(ROOT, "../accounting_portal/public/app.css");
const PREFIX = "/assets/accounting_portal/assets/";
const URL_RE = /url\((['"]?)\/assets\/(?!accounting_portal\/)([^'")]+)\1\)/g;

if (!fs.existsSync(CSS)) {
  console.error(`[fix-asset-urls] ${CSS} not found — Vite build probably failed.`);
  process.exit(1);
}

const before = fs.readFileSync(CSS, "utf8");
let rewrites = 0;
const after = before.replace(URL_RE, (_m, quote, file) => {
  rewrites += 1;
  return `url(${quote}${PREFIX}${file}${quote})`;
});

if (rewrites === 0) {
  console.log("[fix-asset-urls] nothing to rewrite (URLs already correct).");
} else {
  fs.writeFileSync(CSS, after, "utf8");
  console.log(`[fix-asset-urls] rewrote ${rewrites} url() references → ${PREFIX}<file>.`);
}
