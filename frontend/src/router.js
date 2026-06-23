import { createRouter, createWebHistory } from "vue-router";
import { useAuth } from "@/composables/useAuth";

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
  const auth = useAuth();
  if (!auth.isInitialized.value) await auth.init();
  if (to.meta.requiresAuth && !auth.isLoggedIn.value) {
    return { name: "Login", query: { redirect: to.fullPath } };
  }
  if (to.meta.guest && auth.isLoggedIn.value) return { name: "Module", params: { module: "dashboard" } };
  return true;
});

export default router;
