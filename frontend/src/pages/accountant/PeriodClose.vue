<template>
  <div class="grid lg:grid-cols-[1.4fr_1fr] gap-3.5">
    <!-- Checklist -->
    <div class="bg-white border border-line rounded-[14px] p-4 shadow-card">
      <div class="flex items-center gap-2 flex-wrap">
        <span class="text-[13px] font-bold">{{ scope === 'day' ? L("Daily entries", "الإدخالات اليومية", "Saisies du jour") : L("Period close", "إقفال الفترة", "Clôture") }}</span>
        <!-- The day checklist and the month checklist were two screens that
             rendered the same list, and payroll kept a third close of its own
             that neither linked to. One screen, two scopes. -->
        <div class="flex gap-0.5 bg-app-warm rounded-chip p-0.5">
          <button v-for="sc in [['day', L('Day','اليوم','Jour')], ['month', L('Month','الشهر','Mois')]]" :key="sc[0]"
                  class="px-2.5 py-1 rounded-lg text-[12px] font-semibold"
                  :class="scope === sc[0] ? 'bg-white text-accent-dark shadow-card' : 'text-ink-3'"
                  @click="setScope(sc[0])">{{ sc[1] }}</button>
        </div>
        <input v-if="scope === 'day'" v-model="day" type="date" class="h-[28px] px-2 rounded-[8px] border border-line text-[12px]" @change="load" />
        <LiveBadge :live="live" />
        <span class="ms-auto text-[11px] font-bold px-2 py-0.5 rounded-full" :style="ready ? 'background:#ecfdf5;color:#047857' : 'background:#fffbeb;color:#b45309'">{{ ready ? L("Ready to lock", "جاهز للإقفال", "Prêt") : (data.blocked + data.pending) + " " + L("open", "متبقّي", "ouverts") }}</span>
      </div>
      <div class="text-[11px] text-ink-muted mb-3 mt-0.5">
        <template v-if="scope === 'day'">{{ day }} · {{ L("leave the books updated before you leave the desk", "سيب الدفاتر محدثة قبل ما تقوم", "laissez les livres à jour avant de partir") }}</template>
        <template v-else>{{ monthLabel }} · {{ L("everything must tie before locking", "كل شيء يجب أن يتطابق قبل الإقفال", "tout doit concorder avant verrouillage") }}</template>
      </div>
      <div v-if="loading"><TableLoading :rows="6" /></div>
      <CloseChecklist v-else :items="items" :currency="data.currency || 'MAD'" @open="go" />
    </div>

    <div v-if="scope === 'month'" class="flex flex-col gap-3.5">
      <!-- Readiness gauge -->
      <div class="bg-white border border-line rounded-[14px] p-4 shadow-card">
        <div class="text-[13px] font-bold mb-2.5">{{ L("Readiness", "الجاهزية", "Préparation") }}</div>
        <div class="flex h-2.5 rounded-full overflow-hidden bg-app-warm">
          <div :style="{ width: pct('done') + '%', background: '#047857' }"></div>
          <div :style="{ width: pct('pending') + '%', background: '#b45309' }"></div>
          <div :style="{ width: pct('blocked') + '%', background: '#be123c' }"></div>
        </div>
        <div class="flex flex-wrap gap-x-4 gap-y-1 mt-2.5 text-[11px]">
          <span class="inline-flex items-center gap-1"><span class="w-2 h-2 rounded-full" style="background:#047857"></span>{{ L("Done", "تم", "Fait") }} <b>{{ count('done') }}</b></span>
          <span class="inline-flex items-center gap-1"><span class="w-2 h-2 rounded-full" style="background:#b45309"></span>{{ L("Pending", "معلّق", "En attente") }} <b>{{ count('pending') }}</b></span>
          <span class="inline-flex items-center gap-1"><span class="w-2 h-2 rounded-full" style="background:#be123c"></span>{{ L("Blocked", "محظور", "Bloqué") }} <b>{{ count('blocked') }}</b></span>
        </div>
      </div>

      <!-- Lock period -->
      <div class="rounded-[14px] p-4 text-white" style="background:linear-gradient(135deg,#1c1917,#292524);box-shadow:0 8px 24px -14px rgba(28,25,23,.6)">
        <div class="flex items-center gap-2.5">
          <span class="w-[30px] h-[30px] rounded-[8px] grid place-items-center" style="background:rgba(255,255,255,.1)"><Icon name="lock" :size="16" color="#fbbf24" /></span>
          <div class="flex-1">
            <div class="text-[13px] font-bold">{{ L("Period lock", "قفل الفترة", "Verrouillage") }}</div>
            <div class="text-[11px]" style="color:#a8a29e">{{ L("Stops back-dated postings", "يمنع القيود بأثر رجعي", "Bloque les écritures antidatées") }}</div>
          </div>
        </div>
        <div class="flex items-center gap-2.5 mt-3 px-3 py-2.5 rounded-[10px]" style="background:rgba(255,255,255,.06)">
          <span class="w-[7px] h-[7px] rounded-full" :style="{ background: lockedUpto ? '#34d399' : '#fbbf24' }"></span>
          <span class="flex-1 text-[12px]" style="color:#e7e5e4">{{ lockedUpto ? L("Locked up to", "مقفلة حتى", "Verrouillé au") + " " + lockedUpto : L("Not locked", "غير مقفلة", "Non verrouillé") }}</span>
        </div>
        <template v-if="isAdmin">
          <div class="flex items-center gap-2 mt-2.5">
            <input v-model="lockDate" type="date" class="flex-1 h-8 rounded-[8px] px-2 text-[12px] text-ink bg-white/90 border-0 focus:outline-none" />
            <button class="h-8 px-3 rounded-[8px] text-[12px] font-bold text-ink" style="background:#fbbf24" :disabled="lockBusy || !lockDate" @click="lock(lockDate)">{{ lockBusy ? "…" : L("Lock", "قفل", "Verrouiller") }}</button>
          </div>
          <button v-if="lockedUpto" class="mt-2 text-[11px] font-semibold" style="color:#a8a29e" :disabled="lockBusy" @click="lock('')">{{ L("Unlock", "إلغاء القفل", "Déverrouiller") }}</button>
          <p class="text-[11px] mt-2" style="color:#a8a29e">{{ L("Locks posting on/before the date across all companies.", "يمنع القيود في هذا التاريخ وقبله لكل الشركات.", "Bloque les écritures à cette date et avant, toutes sociétés.") }}</p>
        </template>
        <p v-else class="text-[11px] mt-2" style="color:#a8a29e">{{ L("Only an admin can lock the period.", "المشرف فقط يمكنه قفل الفترة.", "Seul un admin peut verrouiller.") }}</p>
      </div>

      <!-- Year-end close -->
      <div v-if="isAdmin" class="rounded-[14px] p-4 bg-white border border-line shadow-card">
        <div class="flex items-center gap-2.5">
          <span class="w-[30px] h-[30px] rounded-[8px] grid place-items-center" style="background:#f5f3ff"><Icon name="ledger" :size="16" color="#7c3aed" /></span>
          <div class="flex-1"><div class="text-[13px] font-bold">{{ L("Year-end close", "إقفال السنة", "Clôture annuelle") }}</div>
            <div class="text-[11px] text-ink-muted">{{ L("Rolls P&L into retained earnings", "يرحّل الأرباح والخسائر لحقوق الملكية", "P&L → réserves") }}</div></div>
        </div>
        <div class="mt-3 space-y-1.5">
          <div v-for="y in years" :key="y.name" class="flex items-center gap-2 text-[12px] px-2.5 py-1.5 rounded-[9px] bg-app-warm/40">
            <span class="flex-1 font-semibold">{{ y.name }} <span class="text-[11px] text-ink-muted">{{ y.sd }} → {{ y.ed }}</span></span>
            <span v-if="y.closed" class="text-[11px] font-bold text-emerald-700">{{ L("closed ✓","مُقفلة ✓","clôturé") }}</span>
            <button v-else class="h-7 px-2.5 rounded-chip text-[11px] font-semibold text-white bg-brand hover:bg-brand-dark disabled:opacity-50" :disabled="closeBusy===y.name" @click="closeYear(y)">{{ closeBusy===y.name ? '…' : L("Close","إقفال","Clôturer") }}</button>
          </div>
          <p class="text-[11px] text-ink-muted">{{ L("Posts a Period Closing Voucher — reversible. Do this after the year is otherwise final.", "يرحّل Period Closing Voucher — قابل للتراجع. بعد ما السنة تخلص فعليًا.", "Réversible.") }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import LiveBadge from "@/components/LiveBadge.vue";
import CloseChecklist from "@/components/CloseChecklist.vue";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";
import { currentCompany, blankLike } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";
import { useAuth } from "@/composables/useAuth";
import { useToast } from "@/composables/useToast";

const { locale } = useI18n();
const route = useRoute();
const router = useRouter();
const { entityId } = useUi();
const { isAdmin } = useAuth();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US");

const lockedUpto = ref(null);
const lockDate = ref(new Date().toISOString().slice(0, 10));
const lockBusy = ref(false);
async function loadLock() {
  try { const r = await api.call("accounting_portal.api.settings.get_period_lock", {}); const d = r && r.acc_frozen_upto; lockedUpto.value = (d && String(d) > "0001-01-01") ? String(d).slice(0, 10) : null; } catch { /* */ }
}
async function lock(date) {
  lockBusy.value = true;
  try {
    const r = await api.call("accounting_portal.api.settings.set_period_lock", { date: date || "" });
    const d = r && r.acc_frozen_upto; lockedUpto.value = (d && String(d) > "0001-01-01") ? String(d).slice(0, 10) : null;
    toast.success(date ? L("Period locked", "تم القفل", "Verrouillé") : L("Unlocked", "تم إلغاء القفل", "Déverrouillé"));
  } catch (e) { toast.error(String((e && e.message) || L("Failed", "فشل", "Échec")).slice(0, 140)); }
  finally { lockBusy.value = false; }
}

const META = {
  done: { bg: "#ecfdf5", fg: "#047857", bd: "#a7f3d0", icon: "check" },
  pending: { bg: "#fffbeb", fg: "#b45309", bd: "#fde68a", icon: "clock" },
  blocked: { bg: "#fef2f2", fg: "#be123c", bd: "#fecaca", icon: "alert" },
};
const meta = (c) => META[c.state] || META.pending;
const statusLabel = (c) => ({ done: L("Done", "تم", "Fait"), pending: L("Pending", "معلّق", "En attente"), blocked: L("Blocked", "محظور", "Bloqué") }[c.state]);
function valueLabel(c) {
  if (c.unit === "MAD") return fmt(Math.abs(c.value)) + " MAD " + L("outstanding", "متبقّي", "en attente");
  if (c.unit === "docs") return c.value + " " + L("unsubmitted drafts", "مسودة غير مُرحّلة", "brouillons");
  if (c.unit === "cheques") return c.value + " " + L("uncleared", "غير مُصرّفة", "non encaissés");
  return fmt(c.value);
}

const SAMPLE = { month: "2026-06", ready: false, blocked: 1, pending: 3, items: [
  { key: "drafts", en: "All documents submitted", ar: "كل المستندات مُرحّلة", fr: "Documents tous soumis", state: "done", value: 0, unit: "docs", link: "/accounting/accountant/journals" },
  { key: "cod", en: "COD collections applied to invoices", ar: "تحصيلات COD مطبّقة", fr: "Encaissements COD appliqués", state: "blocked", value: -2851136, unit: "MAD", link: "/accounting/reports/arap" },
  { key: "grni", en: "GRNI cleared (received → billed)", ar: "GRNI مُصفّى", fr: "GRNI soldé", state: "pending", value: 4376059, unit: "MAD", link: "/accounting/purchases/received" },
  { key: "advances", en: "Supplier advances matched", ar: "مقدّمات الموردين مطابقة", fr: "Avances affectées", state: "pending", value: 3775135, unit: "MAD", link: "/accounting/purchases/payments" },
  { key: "cheques", en: "Cheques cleared", ar: "الشيكات مُصرّفة", fr: "Chèques encaissés", state: "pending", value: 12, unit: "cheques", link: "/accounting/purchases/cheques" },
  { key: "vat", en: "VAT computed for the period", ar: "الضريبة محسوبة", fr: "TVA calculée", state: "done", value: 142057, unit: "MAD", link: "/accounting/reports/taxreports" },
] };

// Blank until the server answers — the old initializer painted a full
// fabricated screen (hero figures and all) on every entry.
const data = ref(blankLike(SAMPLE));
const live = ref(null);
const loading = ref(true);
const items = computed(() => data.value.items || []);
const ready = computed(() => !!data.value.ready);
const monthLabel = computed(() => { const m = data.value.month || ""; const [y, mo] = m.split("-"); const arr = locale.value === "ar" ? ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"] : ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]; return mo ? `${arr[+mo - 1]} ${y}` : m; });
const count = (s) => items.value.filter((i) => i.state === s).length;
const pct = (s) => (items.value.length ? count(s) / items.value.length * 100 : 0);
function go(link) { if (link) router.push(link); }

const props = defineProps({ scope: { type: String, default: "" } });
// The sub in the URL picks the scope; the toggle can then change it.
// Opened from the navigation this is the daily habit, so it lands on the day;
// the month is one click away and keeps the lock and the fiscal-year close.
const scope = ref(props.scope === "month" || route.query.scope === "month" ? "month" : "day");
const day = ref(new Date().toISOString().slice(0, 10));
function setScope(s) {
  scope.value = s;
  router.replace({ query: { ...route.query, scope: s } });
  load();
}

async function load() {
  loading.value = true;
  try {
    data.value = scope.value === "day"
      ? await api.call("accounting_portal.api.reports.daily_entry_checklist", { company: currentCompany(), date: day.value })
      : await api.call("accounting_portal.api.reports.period_close_status", { company: currentCompany() });
    live.value = true;
  } catch { data.value = blankLike(SAMPLE); live.value = false; }
  finally { loading.value = false; }
}
const years = ref([]), closeBusy = ref("");
async function loadYears() {
  try { const r = await api.call("accounting_portal.api.settings.fiscal_years_for_close", { company: currentCompany() }); years.value = r?.years || []; }
  catch { years.value = []; }
}
async function closeYear(y) {
  if (closeBusy.value) return;
  if (!window.confirm(L(`Close ${y.name}? Rolls P&L into retained earnings. Reversible.`, `إقفال ${y.name}؟ يرحّل الأرباح والخسائر لحقوق الملكية. قابل للتراجع.`, `Clôturer ${y.name} ?`))) return;
  closeBusy.value = y.name;
  try { await api.call("accounting_portal.api.settings.close_fiscal_year", { company: currentCompany(), fiscal_year: y.name }); toast.success(L("Year closed", "أُقفلت السنة", "Clôturé")); loadYears(); }
  catch (e) { toast.error(String(e?.message || e).slice(0, 180)); }
  finally { closeBusy.value = ""; }
}
onMounted(() => { load(); loadLock(); loadYears(); });
watch(entityId, load);
</script>
