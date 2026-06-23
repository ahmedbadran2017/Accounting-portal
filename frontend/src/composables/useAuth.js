import { ref, computed } from "vue";
import { frappeApi } from "@/utils/helpers";
import { API } from "@/utils/constants";
import { useUi } from "@/composables/useUi";

// ── Module-scoped singleton state ──
const user = ref(null);
const fullName = ref(null);
const role = ref(null);
const isAdmin = ref(false);
const companies = ref([]);
const capabilities = ref({});
const isLoading = ref(true);
const isInitialized = ref(false);

const isLoggedIn = computed(() => user.value && user.value !== "Guest");
const isGuest = computed(() => !isLoggedIn.value);

function _applySession(data) {
  user.value = data?.user || null;
  fullName.value = data?.full_name || null;
  role.value = data?.role || null;
  isAdmin.value = !!data?.is_admin;
  companies.value = data?.companies || [];
  capabilities.value = data?.capabilities || {};
  // Pick the default landing entity by role (Viewer → consolidated, else Morocco).
  if (data?.role) useUi().applyRoleDefault(data.role);
}

function _clear() {
  _applySession(null);
}

async function init() {
  if (isInitialized.value) return;
  isLoading.value = true;
  // Dev-only: render the authed shell without a backend. Enable in the console
  // with `localStorage.ap_dev_user='Demo Accountant'` then reload. Tree-shaken
  // out of production builds via import.meta.env.DEV.
  if (import.meta.env.DEV) {
    let demo = null, off = null;
    try { demo = localStorage.getItem("ap_dev_user"); off = localStorage.getItem("ap_dev_off"); } catch {}
    // In dev, default to a demo session so `npm run dev` shows the authed shell
    // with no backend. Set localStorage.ap_dev_off='1' to test the real login.
    if (!demo && !off) demo = "Demo Accountant";
    if (demo) {
      _applySession({
        user: "demo@justyol.com", full_name: demo, role: "Accounting Admin",
        is_admin: true, companies: ["Justyol Morocco", "Maslak LTD", "Justyol China", "Justyol Holding"],
        capabilities: { manage_users: false, post_entries: true },
      });
      isLoading.value = false; isInitialized.value = true; return;
    }
  }
  try {
    const res = await frappeApi(`/api/method/${API.SESSION_INFO}`);
    if (res.ok) {
      const { message } = await res.json();
      _applySession(message);
    } else {
      _clear();
    }
  } catch {
    _clear();
  } finally {
    isLoading.value = false;
    isInitialized.value = true;
  }
}

async function login(email, password) {
  const res = await frappeApi(API.LOGIN, { usr: email, pwd: password });
  if (!res.ok) {
    let data = {};
    try { data = await res.json(); } catch {}
    const err = new Error(data.message || data.exc_type || "Login failed");
    err.status = res.status;
    throw err;
  }
  isInitialized.value = false;
  await init();
}

async function logout() {
  try { await frappeApi(API.LOGOUT); } catch {}
  _clear();
  isInitialized.value = false;
}

export function can(action) {
  return !!capabilities.value[action];
}

export function useAuth() {
  return {
    user, fullName, role, isAdmin, companies, capabilities,
    isLoggedIn, isGuest, isLoading, isInitialized,
    init, login, logout, can,
  };
}
