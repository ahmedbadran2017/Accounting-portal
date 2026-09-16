import { createApp } from "vue";
import App from "./App.vue";
import router from "./router";
import i18n, { applyLocale } from "./i18n";
// Latin → Inter, Arabic → Alexandria (same as the Supplier Portal).
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";
import "@fontsource/inter/800.css";
import "@fontsource/alexandria/400.css";
import "@fontsource/alexandria/500.css";
import "@fontsource/alexandria/600.css";
import "@fontsource/alexandria/700.css";
import "@fontsource/alexandria/800.css";
import "./index.css";

// Apply the persisted locale's lang/dir on first paint.
applyLocale(i18n.global.locale.value);

// Stale-chunk safety net: after a deploy replaces hashed route chunks, an
// already-open tab may try to import a filename that no longer exists. Vite
// fires `vite:preloadError`; do a one-time hard reload (fresh HTML → current
// chunk names) instead of leaving the user on a broken navigation.
let _reloadedForChunk = false;
window.addEventListener("vite:preloadError", (e) => {
  if (_reloadedForChunk) return;
  _reloadedForChunk = true;
  e.preventDefault();
  window.location.reload();
});

const app = createApp(App);

// Every deploy renames the JavaScript chunks and deletes the old files, so a tab
// left open across one asks for a file that is gone. The router already recovers
// when that happens during navigation; this catches the other half — a chunk
// imported by a component that is already on screen. The symptom was a piece of
// the page quietly missing, most often a document's action bar, with nothing in
// the console the accountant would ever see and nothing in the server log at all.
const CHUNK_RE = /Failed to fetch dynamically imported module|Importing a module script failed|error loading dynamically imported module|Unable to preload/i;
const RELOAD_ONCE = "ap_chunk_reload_global";
function recoverFromStaleBundle(err) {
  if (!CHUNK_RE.test(String((err && (err.message || err)) || ""))) return false;
  let seen = "";
  try { seen = sessionStorage.getItem(RELOAD_ONCE) || ""; } catch { /* private mode */ }
  // Once per page, so a genuinely missing file cannot put us in a reload loop.
  if (seen === location.pathname) return false;
  try { sessionStorage.setItem(RELOAD_ONCE, location.pathname); } catch { /* ignore */ }
  window.location.reload();
  return true;
}

app.config.errorHandler = (err, vm, info) => {
  if (recoverFromStaleBundle(err)) return;
  console.error(`[Accounting Portal] ${info}:`, err);
};

window.addEventListener("unhandledrejection", (ev) => {
  if (recoverFromStaleBundle(ev.reason)) ev.preventDefault();
});

app.use(i18n);
app.use(router);

app.directive("click-outside", {
  mounted(el, binding) {
    el.__handler__ = (event) => {
      if (!(el === event.target || el.contains(event.target))) binding.value?.(event);
    };
    document.addEventListener("click", el.__handler__);
    document.addEventListener("touchstart", el.__handler__, { passive: true });
  },
  unmounted(el) {
    document.removeEventListener("click", el.__handler__);
    document.removeEventListener("touchstart", el.__handler__);
    delete el.__handler__;
  },
});

app.mount("#app");
