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

const app = createApp(App);

app.config.errorHandler = (err, vm, info) => {
  console.error(`[Accounting Portal] ${info}:`, err);
};

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
