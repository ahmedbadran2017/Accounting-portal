<template>
  <div class="min-h-screen flex bg-app-bg text-ink">
    <!-- ───────── Sidebar ───────── -->
    <aside
      class="fixed lg:static inset-block-0 z-40 w-[248px] bg-white/80 backdrop-blur border-line-2 flex flex-col transition-transform"
      :class="[sideBorder, open ? 'translate-x-0' : sideHidden]"
    >
      <!-- Brand -->
      <div class="h-[60px] flex flex-col justify-center px-4 border-b border-line">
        <img :src="LOGO_URL" alt="Justyol" class="h-[18px] w-auto self-start" />
        <div class="text-[10.5px] text-ink-muted mt-1">{{ t("app.title") }}</div>
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
            <Icon v-if="e.id === entityId" name="check" :size="15" color="#a33a22" />
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
                <Icon :name="m.icon" :size="16" :color="activeModule === m.id ? '#a33a22' : '#a8a29e'" />
                <span class="flex-1 text-start">{{ t('nav.' + m.id) }}</span>
                <span v-if="m.badge"
                      class="min-w-[18px] h-[18px] px-1.5 rounded-full bg-rose-50 text-rose-600 text-[10px] font-bold grid place-items-center">{{ m.badge }}</span>
              </button>
              <!-- Sub-tabs of the active module -->
              <div v-if="activeModule === m.id && subtabs(m.id).length" class="mt-0.5 mb-1 space-y-0.5">
                <button v-for="s in subtabs(m.id)" :key="s[0]"
                        class="w-full flex items-center gap-2.5 py-1.5 ps-8 pe-2.5 rounded-lg text-[11.5px] text-start"
                        :class="activeSub === s[0] ? 'text-accent-dark font-semibold bg-accent-soft' : 'text-ink-3 font-normal hover:bg-app-warm/60'"
                        @click="goSub(m.id, s[0])">
                  <span class="w-[5px] h-[5px] rounded-full flex-shrink-0"
                        :style="{ background: activeSub === s[0] ? '#c4492a' : '#cfc9c4' }"></span>
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

        <div class="flex-1 max-w-md relative hidden sm:block">
          <span class="absolute inset-block-0 flex items-center ps-3 text-ink-muted"><Icon name="search" :size="16" /></span>
          <input :placeholder="t('header.search')" readonly @click="paletteOpen = true" @focus="paletteOpen = true"
                 class="w-full bg-app-warm border border-line-2 rounded-chip ps-9 pe-9 py-2 text-[12.5px] cursor-pointer focus:outline-none hover:border-accent/40" />
          <kbd class="absolute end-3 inset-block-0 my-auto h-fit text-[10px] text-ink-muted border border-line-2 rounded px-1.5 py-0.5">⌘K</kbd>
        </div>
        <div class="flex-1 sm:hidden" />

        <span class="hidden md:inline-flex items-center gap-1.5 text-[11px] font-semibold text-success-dark bg-success/10 px-2.5 py-1.5 rounded-chip">
          <span class="w-1.5 h-1.5 rounded-full bg-success animate-pulse"></span>{{ t("header.synced") }}
        </span>

        <button class="text-[12px] font-semibold text-ink-3 hover:text-ink px-2 py-1.5 rounded-lg hover:bg-app-warm" @click="cycleLocale">
          {{ localeLabel }}
        </button>

        <div class="relative" v-click-outside="() => (createMenuOpen = false)">
          <button class="inline-flex items-center gap-1.5 text-[12.5px] font-semibold text-white bg-accent hover:bg-accent-dark px-3 py-2 rounded-chip shadow-prim" @click="createMenuOpen = !createMenuOpen">
            <Icon name="plus" :size="16" /><span class="hidden sm:inline">{{ t("header.create") }}</span>
          </button>
          <div v-if="createMenuOpen" class="absolute end-0 mt-1 w-48 bg-white rounded-chip border border-line-2 shadow-cardHover p-1 z-50 animate-fadeIn">
            <button v-for="o in createOptions" :key="o.type" class="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg hover:bg-app-warm text-start" @click="openCreate(o.type)">
              <Icon :name="o.icon" :size="15" color="#a33a22" /><span class="text-[12.5px] font-medium">{{ o.label }}</span>
            </button>
          </div>
        </div>
      </header>

      <main class="flex-1 p-[22px] max-w-[1500px] w-full mx-auto">
        <router-view />
      </main>
    </div>

    <CommandPalette :open="paletteOpen" @close="paletteOpen = false" @create="openCreate" />
    <CreateModal :type="createType" @close="createType = null" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
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
const { user, fullName, role, logout } = useAuth();
const { entityId, setEntity, entities } = useUi();

const open = ref(false);
const entityOpen = ref(false);
const paletteOpen = ref(false);
const createMenuOpen = ref(false);
const createType = ref(null);
const groups = NAV_GROUPS;

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
function cycleLocale() {
  const i = LOCALES.indexOf(locale.value);
  locale.value = LOCALES[(i + 1) % LOCALES.length];
  applyLocale(locale.value);
}
async function onLogout() { await logout(); router.push({ name: "Login" }); }
</script>
