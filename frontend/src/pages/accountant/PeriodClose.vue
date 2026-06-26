<template>
  <div class="grid lg:grid-cols-[1.4fr_1fr] gap-3.5">
    <!-- Checklist -->
    <div class="bg-white border border-line rounded-[14px] p-4 shadow-card">
      <div class="flex items-center gap-2 flex-wrap">
        <span class="text-[13px] font-bold">{{ L("Period-close checklist", "قائمة إقفال الفترة", "Liste de clôture") }}</span>
        <span v-if="live !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="live ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ live ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échant.") }}</span>
        <span class="ms-auto text-[11px] font-bold px-2 py-0.5 rounded-full" :style="ready ? 'background:#ecfdf5;color:#047857' : 'background:#fffbeb;color:#b45309'">{{ ready ? L("Ready to lock", "جاهز للإقفال", "Prêt") : (data.blocked + data.pending) + " " + L("open", "متبقّي", "ouverts") }}</span>
      </div>
      <div class="text-[11px] text-ink-muted mb-3 mt-0.5">{{ monthLabel }} · {{ L("everything must tie before locking", "كل شيء يجب أن يتطابق قبل الإقفال", "tout doit concorder avant verrouillage") }}</div>
      <div v-if="loading"><TableLoading :rows="6" /></div>
      <div v-else class="flex flex-col gap-2.5">
        <button v-for="c in items" :key="c.key" @click="go(c.link)"
                class="flex items-center gap-2.5 px-3 py-2.5 border rounded-[11px] text-start hover:shadow-card transition-all"
                :style="{ borderColor: meta(c).bd, background: c.state === 'done' ? '#fdfdfc' : meta(c).bg + '55' }">
          <span class="w-[24px] h-[24px] rounded-[7px] grid place-items-center flex-shrink-0" :style="{ background: meta(c).bg }"><Icon :name="meta(c).icon" :size="13" :color="meta(c).fg" /></span>
          <div class="flex-1 min-w-0">
            <div class="text-[12px] font-semibold">{{ L(c.en, c.ar, c.fr) }}</div>
            <div v-if="c.state !== 'done'" class="text-[10.5px] text-ink-muted">{{ valueLabel(c) }}</div>
          </div>
          <span class="text-[10px] font-bold px-2 py-0.5 rounded-badge border whitespace-nowrap" :style="{ background: meta(c).bg, color: meta(c).fg, borderColor: meta(c).bd }">{{ statusLabel(c) }}</span>
          <Icon name="arrow" :size="12" color="#cfc9c4" class="rtl:rotate-180 flex-shrink-0" />
        </button>
      </div>
    </div>

    <div class="flex flex-col gap-3.5">
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
            <div class="text-[12.5px] font-bold">{{ L("Period lock", "قفل الفترة", "Verrouillage") }}</div>
            <div class="text-[10.5px]" style="color:#a8a29e">{{ L("Stops back-dated postings", "يمنع القيود بأثر رجعي", "Bloque les écritures antidatées") }}</div>
          </div>
        </div>
        <div class="flex items-center gap-2.5 mt-3 px-3 py-2.5 rounded-[10px]" style="background:rgba(255,255,255,.06)">
          <span class="w-[7px] h-[7px] rounded-full" :style="{ background: lockedUpto ? '#34d399' : '#fbbf24' }"></span>
          <span class="flex-1 text-[11.5px]" style="color:#e7e5e4">{{ lockedUpto ? L("Locked up to", "مقفلة حتى", "Verrouillé au") + " " + lockedUpto : L("Not locked", "غير مقفلة", "Non verrouillé") }}</span>
        </div>
        <template v-if="isAdmin">
          <div class="flex items-center gap-2 mt-2.5">
            <input v-model="lockDate" type="date" class="flex-1 h-8 rounded-[8px] px-2 text-[12px] text-ink bg-white/90 border-0 focus:outline-none" />
            <button class="h-8 px-3 rounded-[8px] text-[11.5px] font-bold text-ink" style="background:#fbbf24" :disabled="lockBusy || !lockDate" @click="lock(lockDate)">{{ lockBusy ? "…" : L("Lock", "قفل", "Verrouiller") }}</button>
          </div>
          <button v-if="lockedUpto" class="mt-2 text-[10.5px] font-semibold" style="color:#a8a29e" :disabled="lockBusy" @click="lock('')">{{ L("Unlock", "إلغاء القفل", "Déverrouiller") }}</button>
          <p class="text-[10px] mt-2" style="color:#a8a29e">{{ L("Locks posting on/before the date across all companies.", "يمنع القيود في هذا التاريخ وقبله لكل الشركات.", "Bloque les écritures à cette date et avant, toutes sociétés.") }}</p>
        </template>
        <p v-else class="text-[10px] mt-2" style="color:#a8a29e">{{ L("Only an admin can lock the period.", "المشرف فقط يمكنه قفل الفترة.", "Seul un admin peut verrouiller.") }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";
import { useAuth } from "@/composables/useAuth";
import { useToast } from "@/composables/useToast";

const { locale } = useI18n();
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

const data = ref(SAMPLE);
const live = ref(null);
const loading = ref(true);
const items = computed(() => data.value.items || []);
const ready = computed(() => !!data.value.ready);
const monthLabel = computed(() => { const m = data.value.month || ""; const [y, mo] = m.split("-"); const arr = locale.value === "ar" ? ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"] : ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]; return mo ? `${arr[+mo - 1]} ${y}` : m; });
const count = (s) => items.value.filter((i) => i.state === s).length;
const pct = (s) => (items.value.length ? count(s) / items.value.length * 100 : 0);
function go(link) { if (link) router.push(link); }

async function load() {
  loading.value = true;
  try { data.value = await api.call("accounting_portal.api.reports.period_close_status", { company: currentCompany() }); live.value = true; }
  catch { data.value = SAMPLE; live.value = false; }
  finally { loading.value = false; }
}
onMounted(() => { load(); loadLock(); });
watch(entityId, load);
</script>
