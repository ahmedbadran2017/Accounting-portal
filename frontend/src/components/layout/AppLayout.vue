<template>
  <!-- Signed into the site but with no accounting-portal role: a clear message
       instead of a broken/blank shell or a confusing bounce to login. -->
  <div v-if="noAccess" class="min-h-screen grid place-items-center bg-app-bg p-6">
    <div class="bg-white border border-line rounded-card shadow-card p-8 text-center max-w-md">
      <div class="w-14 h-14 rounded-full grid place-items-center mx-auto" style="background:#fef2f2"><Icon name="shield" :size="26" color="#b91c1c" /></div>
      <div class="text-[18px] font-bold mt-4">{{ L("No access to this portal", "لا تملك صلاحية الدخول", "Accès non autorisé") }}</div>
      <div class="text-[13px] text-ink-3 mt-2 leading-relaxed">{{ L("Your account isn't authorised for the Justyol accounting portal. Ask a Super Admin to grant you a role, then sign in again.", "حسابك غير مصرّح له بالدخول إلى بورتال محاسبة Justyol. اطلب من مسؤول (Super Admin) أن يمنحك صلاحية ثم سجّل الدخول من جديد.", "Votre compte n'est pas autorisé pour ce portail. Demandez un rôle à un Super Admin.") }}</div>
      <div v-if="user" class="text-[11px] text-ink-muted mt-3 font-mono bg-app-warm rounded-chip px-3 py-1.5 inline-block">{{ user }}</div>
      <div class="mt-5">
        <UiButton variant="secondary" size="md" @click="onLogout">{{ L("Sign out", "تسجيل الخروج", "Se déconnecter") }}</UiButton>
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
          <span class="w-7 h-7 rounded-lg grid place-items-center text-white text-[11px] font-bold flex-shrink-0"
                :style="{ background: entity.badge }">{{ entity.code }}</span>
          <span class="flex-1 text-start min-w-0">
            <span class="block text-[12px] font-semibold truncate">{{ entity.name }}</span>
            <span class="block text-[11px] text-ink-muted">{{ entity.place }} · {{ entity.ccy }}</span>
          </span>
          <Icon name="chevDown" :size="15" color="#a8a29e" />
        </button>
        <div v-if="entityOpen"
             class="absolute z-50 inset-inline-3 mt-1 bg-white rounded-chip border border-line-2 shadow-cardHover p-1 animate-fadeIn">
          <button v-for="e in entities" :key="e.id"
                  class="w-full flex items-center gap-2.5 p-2 rounded-lg hover:bg-app-warm"
                  @click="pickEntity(e.id)">
            <span class="w-7 h-7 rounded-lg grid place-items-center text-white text-[11px] font-bold flex-shrink-0"
                  :style="{ background: e.badge }">{{ e.code }}</span>
            <span class="flex-1 text-start min-w-0">
              <span class="block text-[12px] font-semibold truncate">{{ e.name }}</span>
              <span class="block text-[11px] text-ink-muted">{{ e.place }} · {{ e.ccy }}</span>
            </span>
            <Icon v-if="e.id === entityId" name="check" :size="15" color="#0b5c4f" />
          </button>
        </div>
      </div>

      <!-- Nav tree -->
      <nav class="flex-1 overflow-y-auto px-3 py-3 space-y-3.5">
        <div v-for="g in groups" :key="g.label">
          <div class="px-2 mb-1 text-[11px] font-bold uppercase tracking-wider text-ink-muted">{{ t(g.label) }}</div>
          <div class="space-y-0.5">
            <template v-for="m in g.items" :key="m.id">
              <button class="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-[10px] text-[13px]"
                      :class="activeModule === m.id
                        ? 'text-accent-dark font-semibold bg-app-warm shadow-[inset_0_0_0_1px_#f3e4de]'
                        : 'text-ink-2 font-medium hover:bg-app-warm/70'"
                      @click="goModule(m.id)">
                <Icon :name="m.icon" :size="16" :color="activeModule === m.id ? '#0b5c4f' : '#a8a29e'" />
                <span class="flex-1 text-start">{{ t('nav.' + m.id) }}</span>
                <span v-if="badgeFor(m)"
                      class="min-w-[18px] h-[18px] px-1.5 rounded-full bg-rose-50 text-rose-600 text-[11px] font-bold grid place-items-center">{{ badgeFor(m) }}</span>
              </button>
              <!-- Sub-tabs of the active module -->
              <div v-if="activeModule === m.id && subtabs(m.id).length" class="mt-0.5 mb-1 space-y-0.5">
                <button v-for="s in subtabs(m.id)" :key="s[0]"
                        class="w-full flex items-center gap-2.5 py-1.5 ps-8 pe-2.5 rounded-lg text-[12px] text-start"
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
          <div class="text-[11px] text-ink-muted">{{ role || t("header.finance_lead") }}</div>
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
          <span class="flex-1 text-start text-[13px] text-ink-muted truncate">{{ t("header.search") }}</span>
          <kbd class="text-[11px] text-ink-muted border border-line-2 rounded px-1.5 py-0.5">⌘K</kbd>
        </button>

        <!-- Spacer pins the controls to the right edge -->
        <div class="flex-1"></div>

        <!-- Notifications: approvals waiting, documents assigned to me, mentions -->
        <div class="relative" v-click-outside="() => (notifOpen = false)">
          <button class="inline-flex items-center gap-1.5 text-[11px] font-bold px-2.5 py-1.5 rounded-chip"
                  :style="notifTotal ? 'background:#fffbeb;color:#92400e' : 'color:#8a837b'"
                  :title="L('Notifications','الإشعارات','Notifications')" @click="toggleNotif">
            <Icon name="bell" :size="14" :color="notifTotal ? '#92400e' : '#a8a29e'" /><span v-if="notifTotal" class="tnum">{{ notifTotal }}</span>
          </button>
          <div v-if="notifOpen" class="absolute z-50 end-0 top-10 w-[360px] max-h-[70vh] overflow-auto bg-white border border-line rounded-[12px] shadow-pop">
            <div class="px-3 py-2 border-b border-line-hair flex items-center gap-2 text-[12px]">
              <span class="font-bold">{{ L("Notifications","الإشعارات","Notifications") }}</span>
              <span v-if="notif.counts?.approval" class="px-1.5 py-0.5 rounded-full text-[11px] font-bold" style="background:#fffbeb;color:#92400e">{{ notif.counts.approval }} {{ L("approvals","موافقات","approbations") }}</span>
              <span v-if="notif.counts?.assignment" class="px-1.5 py-0.5 rounded-full text-[11px] font-bold" style="background:#eff6ff;color:#0369a1">{{ notif.counts.assignment }} {{ L("assigned","مُسند","assignés") }}</span>
              <button class="ms-auto text-ink-muted hover:text-ink" @click="loadNotif">↻</button>
            </div>
            <button v-for="n in (notif.rows || [])" :key="n.kind + n.id" class="w-full text-start px-3 py-2 border-b border-line-hair/60 hover:bg-app-warm/50 flex gap-2.5" @click="openNotif(n)">
              <span class="w-6 h-6 rounded-full grid place-items-center flex-shrink-0 mt-0.5"
                    :style="n.kind === 'approval' ? 'background:#fffbeb' : n.kind === 'assignment' ? 'background:#eff6ff' : 'background:#f5f3ff'">
                <Icon :name="n.kind === 'approval' ? 'shield' : n.kind === 'assignment' ? 'check' : 'send'" :size="12" :color="n.kind === 'approval' ? '#92400e' : n.kind === 'assignment' ? '#0369a1' : '#6d28d9'" />
              </span>
              <span class="min-w-0 flex-1">
                <span class="block text-[12px] font-semibold truncate">{{ n.title }}<span v-if="n.ref_name" class="font-mono text-[11px] text-ink-muted ms-1">{{ n.ref_name }}</span></span>
                <span class="block text-[11px] text-ink-3 truncate">{{ n.detail }}</span>
                <span class="block text-[11px] text-ink-muted">{{ n.on }}<span v-if="n.amount"> · {{ Math.round(n.amount).toLocaleString() }}</span></span>
              </span>
            </button>
            <div v-if="!(notif.rows || []).length" class="px-3 py-8 text-center text-[12px] text-ink-muted">{{ L("Nothing waiting.","لا شيء منتظر.","Rien en attente.") }}</div>
          </div>
        </div>
        <!-- Connectivity: bound to real API results, not a decorative dot -->
        <span class="hidden md:inline-flex items-center gap-1.5 text-[11px] font-semibold px-2.5 py-1.5 rounded-chip"
              :class="healthy ? 'text-success-dark bg-success/10' : 'text-rose-700 bg-rose-50'"
              :title="healthy ? L('Connected to ERPNext','متصل بـ ERPNext','Connecté') : L('Connection problem — data may be stale','مشكلة اتصال، البيانات قد تكون قديمة','Problème de connexion')">
          <span class="w-1.5 h-1.5 rounded-full" :class="healthy ? 'bg-success' : 'bg-rose-500 animate-pulse'"></span>{{ healthy ? L("Connected", "متصل", "Connecté") : L("Offline", "غير متصل", "Hors ligne") }}
        </span>
        <span v-if="apiHealth.samples" class="hidden md:inline-flex items-center gap-1.5 text-[11px] font-bold px-2.5 py-1.5 rounded-chip" style="background:#fffbeb;color:#92400e" :title="apiHealth.sampleMethods.join(', ')">
          {{ L("Some data failed to load", "تعذّر تحميل بعض البيانات", "Certaines données n'ont pas pu être chargées") }}
        </span>

        <div class="relative" v-click-outside="() => (langOpen = false)">
          <button class="inline-flex items-center gap-1.5 text-[12px] font-semibold text-ink-3 hover:text-ink px-2 py-1.5 rounded-lg hover:bg-app-warm" :aria-label="L('Language','اللغة','Langue')" @click="langOpen = !langOpen">
            <Icon name="globe" :size="15" />
            <span>{{ localeLabel }}</span>
            <Icon name="chevDown" :size="12" class="transition-transform" :class="langOpen ? 'rotate-180' : ''" />
          </button>
          <div v-if="langOpen" class="absolute end-0 mt-1 w-40 bg-white rounded-chip border border-line-2 shadow-cardHover p-1 z-50 animate-fadeIn">
            <button v-for="lc in LOCALES" :key="lc" class="w-full flex items-center justify-between gap-2 px-2.5 py-2 rounded-lg text-start text-[13px] hover:bg-app-warm"
                    :class="locale === lc ? 'font-bold text-accent-dark bg-app-warm/60' : 'text-ink-2'" @click="pickLocale(lc)">
              <span :dir="lc === 'ar' ? 'rtl' : 'ltr'">{{ LOCALE_NAMES[lc] }}</span>
              <Icon v-if="locale === lc" name="check" :size="14" color="#0b5c4f" />
            </button>
          </div>
        </div>

        <div class="relative" v-click-outside="() => (createMenuOpen = false)">
          <UiButton variant="create" size="md" icon="plus" @click="createMenuOpen = !createMenuOpen"><span class="hidden sm:inline">{{ t("header.create") }}</span>
          </UiButton>
          <div v-if="createMenuOpen" class="absolute end-0 mt-1 w-48 bg-white rounded-chip border border-line-2 shadow-cardHover p-1 z-50 animate-fadeIn">
            <button v-for="o in createOptions" :key="o.type" class="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg hover:bg-app-warm text-start" @click="openCreate(o.type)">
              <Icon :name="o.icon" :size="15" color="#0b5c4f" /><span class="text-[13px] font-medium">{{ o.label }}</span>
            </button>
          </div>
        </div>
      </header>

      <!-- A newer build is on the server: this tab is running old code. Reported
           three times as "the portal can't do X" before this existed. -->
      <div v-if="staleTab" class="flex items-center gap-2 px-4 py-2 text-[12px] font-semibold" style="background:#fffbeb;color:#92400e;border-bottom:1px solid #fde68a">
        <Icon name="refresh" :size="14" color="#92400e" />
        {{ L("A newer version of the portal is available — reload to get it.", "في نسخة أحدث من البورتال — اعمل تحديث للصفحة.", "Une nouvelle version est disponible — rechargez.") }}
        <button class="ms-auto h-7 px-3 rounded-chip text-[12px] font-bold text-white" style="background:#92400e" @click="hardReload">{{ L("Reload now", "تحديث الآن", "Recharger") }}</button>
      </div>

      <main class="flex-1 p-[22px] max-w-[1500px] w-full mx-auto">
        <!-- Key by entity so switching company remounts the page and re-fetches
             (pages that load only in onMounted would otherwise show stale data). -->
        <router-view :key="entityId" />
      </main>
    </div>

    <CommandPalette :open="paletteOpen" @close="paletteOpen = false" @create="openCreate" />
    <CreateModal :type="createType" @close="createType = null" />
    <JournalEntryForm v-if="formOpen === 'journal'" @close="formOpen = null" @posted="(r) => onFormPosted('journal', r)" />
    <NewExpenseModal v-if="formOpen === 'expense'" @close="formOpen = null" @posted="(r) => onFormPosted('expense', r)" />
    <PaymentEntryForm v-if="formOpen === 'payment'" @close="formOpen = null" @posted="(r) => onFormPosted('payment', r)" />
    <PaymentEntryForm v-if="formOpen === 'payment_out'" direction="out" @close="formOpen = null" @posted="(r) => onFormPosted('payment_out', r)" />
    <SalesOrderForm v-if="formOpen === 'order'" @close="formOpen = null" @posted="(r) => onFormPosted('order', r)" />
    <NewInvoiceModal v-if="formOpen === 'sales_invoice'" kind="sales" @close="formOpen = null" @posted="formOpen = null" />
    <NewInvoiceModal v-if="formOpen === 'purchase_invoice'" kind="purchase" @close="formOpen = null" @posted="formOpen = null" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import api, { apiHealth } from "@/services/api";
import CommandPalette from "@/components/CommandPalette.vue";
import CreateModal from "@/components/CreateModal.vue";
import JournalEntryForm from "@/components/JournalEntryForm.vue";
import NewExpenseModal from "@/components/NewExpenseModal.vue";
import PaymentEntryForm from "@/components/PaymentEntryForm.vue";
import SalesOrderForm from "@/components/SalesOrderForm.vue";
import NewInvoiceModal from "@/components/NewInvoiceModal.vue";
import { useAuth } from "@/composables/useAuth";
import { useUi } from "@/composables/useUi";
import { applyLocale, LOCALES, LOCALE_LABEL, RTL_LOCALES } from "@/i18n";
import { NAV_GROUPS, SUBTABS, defaultSub, tabsFor } from "@/data/nav";
import { LOGO_URL } from "@/utils/constants";
import UiButton from "@/components/UiButton.vue";

const { t, locale } = useI18n();
const route = useRoute();
const router = useRouter();
const { user, fullName, role, logout, hasAccess, isLoggedIn, staleTab, refreshBuild } = useAuth();
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
onMounted(() => { syncHeader(true); window.addEventListener("online", onOnline); window.addEventListener("offline", onOffline); });
onUnmounted(() => { window.removeEventListener("online", onOnline); window.removeEventListener("offline", onOffline); });
// The header signals cost four requests. Refetching them on every route change
// made rapid navigation four times heavier than the page itself, so they refresh
// at most twice a minute — they are counters, not the page content.
let lastHeaderSync = 0;
function syncHeader(force) {
  if (!force && Date.now() - lastHeaderSync < 30000) return;
  lastHeaderSync = Date.now();
  loadWorkCount(); loadApprovals(); loadNotif(); refreshBuild();
}
watch(() => route.path, () => syncHeader(false));

// Every entry here opens a REAL form that posts to ERPNext. (The old "order" and
// "invoice" entries wrote a fake document to memory and toasted success.)
const createOptions = computed(() => [
  { type: "journal", icon: "ledger", label: L("Journal entry", "قيد يومية", "Écriture") },
  { type: "expense", icon: "doc", label: L("Expense / supplier bill", "مصروف / فاتورة مورد", "Dépense / facture") },
  { type: "payment", icon: "coins", label: L("Payment received", "دفعة محصّلة", "Encaissement") },
  { type: "payment_out", icon: "coins", label: L("Payment made", "دفعة مصروفة", "Paiement") },
  { type: "order", icon: "receipt", label: L("Sales order", "أمر بيع", "Commande") },
  { type: "sales_invoice", icon: "receipt", label: L("Sales invoice", "فاتورة بيع", "Facture de vente") },
  { type: "purchase_invoice", icon: "cart", label: L("Supplier invoice (items)", "فاتورة شراء بأصناف", "Facture d'achat") },
  { type: "customer", icon: "user", label: L("Customer", "عميل", "Client") },
]);
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

// Which real form is open: journal / expense / payment / order render their own
// modal components; customer keeps the small CreateModal.
const formOpen = ref(null);
function openCreate(type) {
  createMenuOpen.value = false; paletteOpen.value = false;
  if (type === "customer") { createType.value = "customer"; return; }
  if (["journal", "expense", "payment", "payment_out", "order", "sales_invoice", "purchase_invoice"].includes(type)) { formOpen.value = type; return; }
  createType.value = null;
}
function hardReload() { window.location.reload(true); }
function onFormPosted(type, res) {
  formOpen.value = null;
  const v = res && (res.voucher_no || res.name);
  if (type === "journal") router.push({ path: "/accounting/accountant/journals", query: v ? { id: v } : {} });
  else if (type === "expense") router.push("/accounting/expenses");
  else if (type === "payment") router.push({ path: "/accounting/sales/payments", query: v ? { id: v } : {} });
  else if (type === "payment_out") router.push({ path: "/accounting/purchases/payments", query: v ? { id: v } : {} });
  else if (type === "order") router.push({ path: "/accounting/sales/orders", query: v ? { id: v } : {} });
}

// ── Header signals: real connectivity + pending approvals ──
const online = ref(typeof navigator === "undefined" ? true : navigator.onLine);
const onOnline = () => { online.value = true; }; const onOffline = () => { online.value = false; };
const healthy = computed(() => online.value && apiHealth.ok);
const approvals = ref(0);
async function loadApprovals() {
  try { const r = await api.call("accounting_portal.api._actions.pending_count", {}, { fresh: true }); approvals.value = r?.count || 0; }
  catch { approvals.value = 0; }
}

// ── Notifications: approvals + assignments + mentions ──
const notifOpen = ref(false);
const notif = ref({ rows: [], counts: {}, total: 0 });
const notifTotal = computed(() => notif.value.total || approvals.value || 0);
async function loadNotif() {
  try { notif.value = (await api.call("accounting_portal.api.docops.notifications", { limit: 25 }, { fresh: true })) || notif.value; }
  catch { /* the approvals count still shows */ }
}
function toggleNotif() { notifOpen.value = !notifOpen.value; if (notifOpen.value) loadNotif(); }
const NOTIF_ROUTE = {
  "Sales Invoice": "sales/invoices", "Purchase Invoice": "purchases/bills", "Sales Order": "sales/orders",
  "Purchase Order": "purchases/tobuy", "Delivery Note": "sales/challans", "Purchase Receipt": "purchases/received",
  "Journal Entry": "accountant/journals", "Payment Entry": "purchases/payments", "Item": "items/items",
};
function openNotif(n) {
  notifOpen.value = false;
  if (n.kind === "approval") { router.push("/accounting/settings/activity"); return; }
  const r = NOTIF_ROUTE[n.ref_doctype];
  if (r && n.ref_name) router.push({ path: `/accounting/${r}`, query: { id: n.ref_name } });
  else router.push("/accounting/mywork");
}

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

// Same list the pages use: the pipeline stages belong to the strip of cards
// inside the two bucket screens, which carries their counts, not to a flat list
// of ten sidebar rows that all open the same component.
const subtabs = (m) => tabsFor(m);

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
