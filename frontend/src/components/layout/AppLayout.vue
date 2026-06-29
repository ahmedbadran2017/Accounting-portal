<template>
  <!-- Signed into the site but with no accounting-portal role: a clear message
       instead of a broken/blank shell or a confusing bounce to login. -->
  <div v-if="noAccess" class="min-h-screen grid place-items-center bg-app-bg p-6">
    <div class="bg-white border border-line rounded-card shadow-card p-8 text-center max-w-md">
      <div class="w-14 h-14 rounded-full grid place-items-center mx-auto" style="background:#fef2f2"><Icon name="shield" :size="26" color="#b91c1c" /></div>
      <div class="text-[17px] font-bold mt-4">{{ L("No access to this portal", "لا تملك صلاحية الدخول", "Accès non autorisé") }}</div>
      <div class="text-[12.5px] text-ink-3 mt-2 leading-relaxed">{{ L("Your account isn't authorised for the Justyol accounting portal. Ask a Super Admin to grant you a role, then sign in again.", "حسابك غير مصرّح له بالدخول إلى بورتال محاسبة Justyol. اطلب من مسؤول (Super Admin) أن يمنحك صلاحية ثم سجّل الدخول من جديد.", "Votre compte n'est pas autorisé pour ce portail. Demandez un rôle à un Super Admin.") }}</div>
      <div v-if="user" class="text-[11px] text-ink-muted mt-3 font-mono bg-app-warm rounded-chip px-3 py-1.5 inline-block">{{ user }}</div>
      <div class="mt-5">
        <button class="h-9 px-4 rounded-chip text-[12.5px] font-bold text-white bg-ink hover:bg-ink/90" @click="onLogout">{{ L("Sign out", "تسجيل الخروج", "Se déconnecter") }}</button>
      </div>
    </div>
  </div>
  <div v-else class="min-h-screen flex bg-app-bg text-ink">
    <!-- ───────── Sidebar ───────── -->
    <aside
      class="fixed lg:static inset-block-0 z-40 w-[248px] bg-white/80 backdrop-blur border-line-2 flex flex-col transition-transform"
      :class="[sideBorder, open ? 'translate-x-0' : sideHidden]"
    >
      <!-- Brand -->
      <div class="h-[60px] flex items-center gap-2.5 px-4 border-b border-line">
        <img :src="LOGO_URL" alt="Justyol" class="h-[15px] w-auto" />
        <span class="w-px h-[18px] bg-line-2"></span>
        <span class="text-[16px] font-bold tracking-tight text-brand-dark">Books</span>
      </div>

      <!-- Entity switcher -->
      <div class="px-3 pt-3 relative" v-click-outside="() => (entityOpen = false)">
        <button class="w-full flex items-center gap-2.5 p-2 rounded-chip border border-line-2 bg-app-warm hover:bg-white"
                @click="entityOpen = !entityOpen">
          <span class="w-7 h-7 rounded-lg grid place-items-center text-white text-[10px] font-bold flex-shrink-0"
                :style="{ background: entity.badge }">{{ entity.code }}</span>
          <span class="flex-1 text-start min-w-0">
            <span class="block text-[12px] font-semibold truncate">{{ entity.name }}</span>
            <span class="block text-[10px] text-ink-muted">{{ entity.place }} · {{ entity.ccy }}</span>
          </span>
          <Icon name="chevDown" :size="15" color="#a8a29e" />
        </button>
        <div v-if="entityOpen"
             class="absolute z-50 inset-inline-3 mt-1 bg-white rounded-chip border border-line-2 shadow-cardHover p-1 animate-fadeIn">
          <button v-for="e in entities" :key="e.id"
                  class="w-full flex items-center gap-2.5 p-2 rounded-lg hover:bg-app-warm"
                  @click="pickEntity(e.id)">
            <span class="w-7 h-7 rounded-lg grid place-items-center text-white text-[10px] font-bold flex-shrink-0"
                  :style="{ background: e.badge }">{{ e.code }}</span>
            <span class="flex-1 text-start min-w-0">
              <span class="block text-[12px] font-semibold truncate">{{ e.name }}</span>
              <span class="block text-[10px] text-ink-muted">{{ e.place }} · {{ e.ccy }}</span>
            </span>
            <Icon v-if="e.id === entityId" name="check" :size="15" color="#0b5c4f" />
          </button>
        </div>
      </div>

      <!-- Nav tree -->
      <nav class="flex-1 overflow-y-auto px-3 py-3 space-y-3.5">
        <div v-for="g in groups" :key="g.label">
          <div class="px-2 mb-1 text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ t(g.label) }}</div>
          <div class="space-y-0.5">
            <template v-for="m in g.items" :key="m.id">
              <button class="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-[10px] text-[12.5px]"
                      :class="activeModule === m.id
                        ? 'text-accent-dark font-semibold bg-app-warm shadow-[inset_0_0_0_1px_#f3e4de]'
                        : 'text-ink-2 font-medium hover:bg-app-warm/70'"
                      @click="goModule(m.id)">
                <Icon :name="m.icon" :size="16" :color="activeModule === m.id ? '#0b5c4f' : '#a8a29e'" />
                <span class="flex-1 text-start">{{ t('nav.' + m.id) }}</span>
                <span v-if="badgeFor(m)"
                      class="min-w-[18px] h-[18px] px-1.5 rounded-full bg-rose-50 text-rose-600 text-[10px] font-bold grid place-items-center">{{ badgeFor(m) }}</span>
              </button>
              <!-- Sub-tabs of the active module -->
              <div v-if="activeModule === m.id && subtabs(m.id).length" class="mt-0.5 mb-1 space-y-0.5">
                <button v-for="s in subtabs(m.id)" :key="s[0]"
                        class="w-full flex items-center gap-2.5 py-1.5 ps-8 pe-2.5 rounded-lg text-[11.5px] text-start"
                        :class="activeSub === s[0] ? 'text-accent-dark font-semibold bg-accent-soft' : 'text-ink-3 font-normal hover:bg-app-warm/60'"
                        @click="goSub(m.id, s[0])">
                  <span class="w-[5px] h-[5px] rounded-full flex-shrink-0"
                        :style="{ background: activeSub === s[0] ? '#0f766e' : '#cfc9c4' }"></span>
                  {{ t(s[1]) }}
                </button>
              </div>
            </template>
          </div>
        </div>

      </nav>

      <!-- Footer user -->
      <div class="p-3 border-t border-line flex items-center gap-2.5">
        <div class="w-8 h-8 rounded-full bg-app-warm grid place-items-center text-[11px] font-bold text-ink-3">{{ initials }}</div>
        <div class="flex-1 leading-tight min-w-0">
          <div class="text-[12px] font-semibold truncate">{{ fullName || user }}</div>
          <div class="text-[10px] text-ink-muted">{{ role || t("header.finance_lead") }}</div>
        </div>
        <button class="p-1.5 rounded-lg hover:bg-app-warm text-ink-3" :title="t('common.logout')" @click="onLogout">
          <Icon name="arrow" :size="16" />
        </button>
      </div>
    </aside>

    <div v-if="open" class="fixed inset-0 bg-black/25 z-30 lg:hidden" @click="open = false" />

    <!-- ───────── Main column ───────── -->
    <div class="flex-1 flex flex-col min-w-0">
      <header class="h-[60px] bg-white/70 backdrop-blur border-b border-line flex items-center gap-3 px-4 lg:px-5 sticky top-0 z-20">
        <button class="lg:hidden p-2 -ms-2 text-ink-3" @click="open = true"><Icon name="list" :size="20" /></button>

        <!-- Search — opens the ⌘K command palette -->
        <button type="button" @click="paletteOpen = true"
                class="hidden sm:flex items-center gap-2 w-64 lg:w-80 bg-app-warm border border-line-2 rounded-chip px-3 py-2 hover:border-accent/40">
          <Icon name="search" :size="16" color="#a8a29e" />
          <span class="flex-1 text-start text-[12.5px] text-ink-muted truncate">{{ t("header.search") }}</span>
          <kbd class="text-[10px] text-ink-muted border border-line-2 rounded px-1.5 py-0.5">⌘K</kbd>
        </button>

        <!-- Spacer pins the controls to the right edge -->
        <div class="flex-1"></div>

        <span class="hidden md:inline-flex items-center gap-1.5 text-[11px] font-semibold text-success-dark bg-success/10 px-2.5 py-1.5 rounded-chip">
          <span class="w-1.5 h-1.5 rounded-full bg-success animate-pulse"></span>{{ t("header.synced") }}
        </span>

        <div class="relative" v-click-outside="() => (langOpen = false)">
          <button class="inline-flex items-center gap-1.5 text-[12px] font-semibold text-ink-3 hover:text-ink px-2 py-1.5 rounded-lg hover:bg-app-warm" :aria-label="L('Language','اللغة','Langue')" @click="langOpen = !langOpen">
            <Icon name="globe" :size="15" />
            <span>{{ localeLabel }}</span>
            <Icon name="chevDown" :size="12" class="transition-transform" :class="langOpen ? 'rotate-180' : ''" />
          </button>
          <div v-if="langOpen" class="absolute end-0 mt-1 w-40 bg-white rounded-chip border border-line-2 shadow-cardHover p-1 z-50 animate-fadeIn">
            <button v-for="lc in LOCALES" :key="lc" class="w-full flex items-center justify-between gap-2 px-2.5 py-2 rounded-lg text-start text-[12.5px] hover:bg-app-warm"
                    :class="locale === lc ? 'font-bold text-accent-dark bg-app-warm/60' : 'text-ink-2'" @click="pickLocale(lc)">
              <span :dir="lc === 'ar' ? 'rtl' : 'ltr'">{{ LOCALE_NAMES[lc] }}</span>
              <Icon v-if="locale === lc" name="check" :size="14" color="#0b5c4f" />
            </button>
          </div>
        </div>

        <div class="relative" v-click-outside="() => (createMenuOpen = false)">
          <button class="inline-flex items-center gap-1.5 text-[12.5px] font-semibold text-white bg-brand hover:bg-brand-dark px-3 py-2 rounded-chip shadow-brand" @click="createMenuOpen = !createMenuOpen">
            <Icon name="plus" :size="16" /><span class="hidden sm:inline">{{ t("header.create") }}</span>
          </button>
          <div v-if="createMenuOpen" class="absolute end-0 mt-1 w-48 bg-white rounded-chip border border-line-2 shadow-cardHover p-1 z-50 animate-fadeIn">
            <button v-for="o in createOptions" :key="o.type" class="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg hover:bg-app-warm text-start" @click="openCreate(o.type)">
              <Icon :name="o.icon" :size="15" color="#0b5c4f" /><span class="text-[12.5px] font-medium">{{ o.label }}</span>
            </button>
          </div>
        </div>
      </header>

      <main class="flex-1 p-[22px] max-w-[1500px] w-full mx-auto">
        <!-- Key by entity so switching company remounts the page and re-fetches
             (pages that load only in onMounted would otherwise show stale data). -->
        <router-view :key="entityId" />
      </main>
    </div>

    <CommandPalette :open="paletteOpen" @close="paletteOpen = false" @create="openCreate" />
    <CreateModal :type="createType" @close="createType = null" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import api from "@/services/api";
import CommandPalette from "@/components/CommandPalette.vue";
import CreateModal from "@/components/CreateModal.vue";
import { useAuth } from "@/composables/useAuth";
import { useUi } from "@/composables/useUi";
import { applyLocale, LOCALES, LOCALE_LABEL, RTL_LOCALES } from "@/i18n";
import { NAV_GROUPS, SUBTABS, defaultSub } from "@/data/nav";
import { LOGO_URL } from "@/utils/constants";

const { t, locale } = useI18n();
const route = useRoute();
const router = useRouter();
const { user, fullName, role, logout, hasAccess, isLoggedIn } = useAuth();
const noAccess = computed(() => isLoggedIn.value && !hasAccess.value);
const { entityId, setEntity, entities } = useUi();

const open = ref(false);
const entityOpen = ref(false);
const paletteOpen = ref(false);
const createMenuOpen = ref(false);
const createType = ref(null);
const groups = NAV_GROUPS;

// Live "My work" badge — open tasks assigned to the current user.
const workCount = ref(0);
async function loadWorkCount() {
  try { const r = await api.call("accounting_portal.api.docops.my_work_count", {}); workCount.value = r.count || 0; }
  catch { workCount.value = 0; }
}
function badgeFor(m) {
  if (m.id === "mywork") return workCount.value > 0 ? String(workCount.value) : "";
  return m.badge || "";
}
onMounted(loadWorkCount);
watch(() => route.path, loadWorkCount);

const createOptions = computed(() => [
  { type: "customer", icon: "user", label: L("Customer", "عميل", "Client") },
  { type: "order", icon: "receipt", label: L("Sales order", "أمر بيع", "Commande") },
  { type: "invoice", icon: "receipt", label: L("Invoice", "فاتورة", "Facture") },
]);
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

function openCreate(type) { createMenuOpen.value = false; paletteOpen.value = false; createType.value = type; }

// Global ⌘K / Ctrl+K opens the command palette; Esc closes overlays.
function onKey(e) {
  if ((e.metaKey || e.ctrlKey) && (e.key === "k" || e.key === "K")) {
    e.preventDefault();
    paletteOpen.value = !paletteOpen.value;
  } else if (e.key === "Escape") {
    paletteOpen.value = false; createMenuOpen.value = false; createType.value = null; entityOpen.value = false;
  }
}
onMounted(() => window.addEventListener("keydown", onKey));
onUnmounted(() => window.removeEventListener("keydown", onKey));

// Sidebar is a left/right drawer on mobile, static column on lg+. Hide
// direction flips for RTL so the drawer slides off the correct edge.
const sideBorder = "border-e border-line-2";
const sideHidden = computed(() =>
  RTL_LOCALES.has(locale.value) ? "translate-x-full lg:translate-x-0" : "-translate-x-full lg:translate-x-0");

const entity = computed(() => entities.find((e) => e.id === entityId.value) || entities[0]);
const activeModule = computed(() => route.params.module || "dashboard");
const activeSub = computed(() => route.params.sub || null);
const localeLabel = computed(() => LOCALE_LABEL[locale.value]);
const initials = computed(() => {
  const s = fullName.value || user.value || "?";
  return s.split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
});

const subtabs = (m) => SUBTABS[m] || [];

function goModule(m) {
  open.value = false;
  const sub = defaultSub(m);
  router.push(sub ? `/accounting/${m}/${sub}` : `/accounting/${m}`);
}
function goSub(m, s) {
  open.value = false;
  router.push(s ? `/accounting/${m}/${s}` : `/accounting/${m}`);
}
function pickEntity(id) { setEntity(id); entityOpen.value = false; }
// Language picker — a dropdown of the three locales in their native names,
// instead of a blind cycle button (you couldn't tell what tapping it would do).
const langOpen = ref(false);
const LOCALE_NAMES = { en: "English", ar: "العربية", fr: "Français" };
function pickLocale(lc) {
  locale.value = lc;
  applyLocale(lc);
  langOpen.value = false;
}
async function onLogout() { await logout(); router.push({ name: "Login" }); }
</script>
