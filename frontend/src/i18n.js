import { createI18n } from "vue-i18n";
import en from "./locales/en.json";
import ar from "./locales/ar.json";
import fr from "./locales/fr.json";

const saved = (() => {
  try { return localStorage.getItem("ap_locale"); } catch { return null; }
})();

const i18n = createI18n({
  legacy: false,
  globalInjection: true,
  locale: saved || "en",
  fallbackLocale: "en",
  messages: { en, ar, fr },
});

export const LOCALES = ["en", "ar", "fr"];
export const LOCALE_LABEL = { en: "EN", ar: "ع", fr: "FR" };
export const RTL_LOCALES = new Set(["ar"]);

/** Apply <html lang/dir> for the locale and persist the choice. */
export function applyLocale(locale) {
  const html = document.documentElement;
  html.setAttribute("lang", locale);
  html.setAttribute("dir", RTL_LOCALES.has(locale) ? "rtl" : "ltr");
  try { localStorage.setItem("ap_locale", locale); } catch {}
}

export default i18n;
