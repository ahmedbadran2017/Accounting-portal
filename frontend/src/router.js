import { createRouter, createWebHistory } from "vue-router";
import { useAuth } from "@/composables/useAuth";
import { SUBTABS } from "@/data/nav";

// Modules Module.vue actually dispatches to a real page. Anything else falls to
// the generic "pending build" placeholder.
const REAL_MODULES = new Set([
  "dashboard", "copilot", "mywork", "sales", "purchases", "banking",
  "accountant", "items", "reports", "settings", "consolidation",
]);
// Reverse index: a sub-tab slug → its parent module (first match wins). Lets a
// link/search/typed URL that addresses a sub as if it were a top-level module
// (e.g. /accounting/journals) resolve to the real screen (/accounting/accountant/journals)
// instead of the empty placeholder.
const SUB_TO_MODULE = {};
for (const [mod, subs] of Object.entries(SUBTABS)) {
  for (const [slug] of subs) if (!(slug in SUB_TO_MODULE)) SUB_TO_MODULE[slug] = mod;
}

import AppLayout from "@/components/layout/AppLayout.vue";
const Login = () => import("@/pages/auth/Login.vue");
const Module = () => import("@/pages/Module.vue");

const routes = [
  { path: "/", redirect: "/accounting/dashboard" },
  { path: "/accounting", redirect: "/accounting/dashboard" },
  { path: "/accounting/login", name: "Login", component: Login, meta: { guest: true } },
  {
    path: "/accounting",
    component: AppLayout,
    meta: { requiresAuth: true },
    children: [
      // One dynamic route covers every module + optional sub-tab. Module.vue
      // dispatches to Dashboard / Copilot / generic ModulePage.
      { path: ":module/:sub?", name: "Module", component: Module },
    ],
  },
  { path: "/accounting/:pathMatch(.*)*", redirect: "/accounting/dashboard" },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
});

router.beforeEach(async (to) => {
  // Safety net: a sub-slug used as a top-level module (no real sub of its own)
  // redirects to its proper module/sub so it renders the real screen.
  const m = to.params.module;
  if (m && !REAL_MODULES.has(m) && SUB_TO_MODULE[m] && !to.params.sub) {
    return { name: "Module", params: { module: SUB_TO_MODULE[m], sub: m }, query: to.query, replace: true };
  }

  const auth = useAuth();
  if (!auth.isInitialized.value) await auth.init();
  if (to.meta.requiresAuth && !auth.isLoggedIn.value) {
    return { name: "Login", query: { redirect: to.fullPath } };
  }
  if (to.meta.guest && auth.isLoggedIn.value) return { name: "Module", params: { module: "dashboard" } };
  return true;
});

export default router;
