<template>
  <div class="space-y-3.5">
    <!-- Pipeline strip -->
    <div class="grid grid-cols-2 lg:grid-cols-5 gap-3">
      <button v-for="b in PIPE" :key="b.key" class="group relative bg-white border rounded-[16px] p-4 text-start transition-all overflow-hidden"
              :class="bucket === b.key ? 'shadow-cardHover -translate-y-0.5' : 'border-line shadow-card hover:-translate-y-0.5 hover:shadow-cardHover'"
              :style="bucket === b.key ? { borderColor: b.color + '66' } : {}" @click="goBucket(b.key)">
        <span class="absolute top-0 inset-x-0 h-[3px]" :style="{ background: b.color, opacity: bucket === b.key ? 1 : .25 }"></span>
        <div class="relative flex items-start gap-2.5">
          <span class="w-9 h-9 rounded-[11px] grid place-items-center flex-shrink-0" :style="{ background: b.tint }"><Icon :name="b.icon" :size="17" :color="b.color" /></span>
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-1.5">
              <span class="text-[10.5px] text-ink-muted font-bold uppercase tracking-wider">{{ b.label() }}</span>
              <span v-if="dateScope" class="text-[8.5px] font-bold px-1.5 py-px rounded-full" :style="{ background: b.tint, color: b.color }">{{ dateScope }}</span>
            </div>
            <div class="text-[24px] font-extrabold tnum leading-tight tracking-tight" :style="{ color: bucket === b.key ? b.color : '#1c1917' }">{{ cardCount(b.key).toLocaleString() }}</div>
          </div>
        </div>
        <div class="relative mt-2 text-[11px] text-ink-3 font-semibold tnum">{{ money(cardValue(b.key)) }} <span class="text-ink-muted font-normal">{{ ccy }}</span></div>
        <div class="relative mt-1 text-[10px] text-ink-muted">{{ b.hint() }}</div>
      </button>
    </div>

    <!-- Table -->
    <div class="bg-white rounded-card border border-line overflow-hidden shadow-card">
      <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
        <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" :style="{ background: active.tint }"><Icon :name="active.icon" :size="14" :color="active.color" /></span>
        <span class="text-[13px] font-bold">{{ active.label() }}</span>
        <span v-if="live !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="live ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ live ? "Live" : "Sample" }}</span>
        <span class="hidden lg:inline text-[11px] text-ink-muted">{{ bucketCount.toLocaleString() }} {{ L("docs","مستند","docs") }} · {{ dateScope || "FY 2026" }}<span v-if="bucketCount > rows.length"> · {{ L("first","أول","premiers") }} {{ rows.length }}</span></span>
        <div class="relative ms-auto">
          <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
          <input v-model.trim="srch" :placeholder="L('Document / supplier…','مستند / مورّد…','Document / fournisseur…')" class="w-44 sm:w-60 h-9 bg-app-warm/40 border border-line-2 rounded-[10px] ps-9 pe-3 text-[12.5px] focus:outline-none focus:border-accent/40 focus:bg-white" />
        </div>
      </div>

      <div class="flex items-center gap-2 px-4 py-2.5 border-b border-line-hair flex-wrap bg-app-warm/20">
        <Icon name="clock" :size="13" color="#a8a29e" />
        <button v-for="p in DATE_PRESETS" :key="p.key" class="text-[11px] font-semibold px-2.5 py-1 rounded-full border transition"
                :class="datePreset === p.key ? 'bg-ink text-white border-ink' : 'bg-white text-ink-3 border-line-2 hover:bg-app-warm'" @click="setPreset(p.key)">{{ p.label() }}</button>
        <div v-if="datePreset === 'range'" class="flex items-center gap-1">
          <input type="date" v-model="dateFrom" class="h-7 border border-line-2 rounded-chip px-2 text-[11px] focus:outline-none focus:border-accent/40" />
          <span class="text-ink-muted text-[11px]">→</span>
          <input type="date" v-model="dateTo" class="h-7 border border-line-2 rounded-chip px-2 text-[11px] focus:outline-none focus:border-accent/40" />
        </div>
        <span v-if="loading" class="ms-2 text-[11px] text-ink-muted inline-flex items-center gap-1.5"><span class="w-1.5 h-1.5 rounded-full bg-accent animate-pulse"></span>{{ L("loading…","تحميل…","…") }}</span>
      </div>

      <TableToolbar :t="tt" :filename="bucket" />
      <div class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead>
            <tr style="background:#fafaf9">
              <th v-if="selectable" class="px-3 py-2.5 w-9"><input type="checkbox" :checked="allPageSelected" @change="toggleAllPage" class="accent-accent w-3.5 h-3.5 align-middle" /></th>
              <th v-for="c in cols" v-show="!tt.hidden.value.has(c.key)" :key="c.key"
                  class="px-4 py-2.5 text-[10px] font-bold uppercase tracking-wider text-ink-muted whitespace-nowrap cursor-pointer select-none hover:text-ink-2"
                  :class="c.align === 'e' ? 'text-end' : 'text-start'" @click="tt.toggleSort(c.key)">
                <span class="inline-flex items-center gap-1" :class="c.align === 'e' ? 'flex-row-reverse' : ''">{{ colLabel(c) }}
                  <Icon v-if="tt.sortKey.value === c.key" name="chevDown" :size="11" :class="tt.sortDir.value === 1 ? '' : 'rotate-180'" color="#0b5c4f" /></span>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="o in tt.pageRows.value" :key="o.name" class="border-t border-line-hair hover:bg-app-warm/70 cursor-pointer" :class="selected.has(o.name) ? 'bg-accent/5' : ''" @click="open(o.name)">
              <td v-if="selectable" class="px-3 py-2.5 w-9" @click.stop><input type="checkbox" :checked="selected.has(o.name)" @change="toggleRow(o)" class="accent-accent w-3.5 h-3.5 align-middle" /></td>
              <td v-show="!tt.hidden.value.has('name')" class="px-4 py-2.5 font-mono font-semibold whitespace-nowrap">{{ o.name }}</td>
              <td v-show="!tt.hidden.value.has('supplier_name')" class="px-4 py-2.5 truncate max-w-[200px]">{{ o.supplier_name }}</td>
              <td v-show="!tt.hidden.value.has('date')" class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ o.date }}</td>
              <td v-show="!tt.hidden.value.has('due')" class="px-4 py-2.5 whitespace-nowrap">
                <span v-if="o.due" :class="isOverdue(o.due) ? 'text-sale font-semibold' : 'text-ink-2'">{{ o.due }}</span>
                <span v-else class="text-ink-muted">—</span>
              </td>
              <td v-show="!tt.hidden.value.has('info')" class="px-4 py-2.5 text-end whitespace-nowrap">
                <template v-if="bucket === 'tobuy' || bucket === 'received'">
                  <span class="inline-flex items-center gap-1.5">
                    <span class="w-12 h-1.5 rounded-full bg-app-warm overflow-hidden"><span class="block h-full rounded-full" :style="{ width: Math.round(o.progress) + '%', background: active.color }"></span></span>
                    <span class="text-[11px] tnum text-ink-3">{{ Math.round(o.progress) }}%</span>
                  </span>
                </template>
                <template v-else-if="bucket === 'paid'">
                  <span v-if="o.method" class="text-[10px] font-bold px-2 py-0.5 rounded-full" :style="methodStyle(o.method)">{{ o.method }}</span>
                  <span v-else class="text-ink-muted">—</span>
                </template>
                <span v-else class="tnum font-bold text-sale">{{ fmt(o.progress) }}</span>
              </td>
              <td v-show="!tt.hidden.value.has('value')" class="px-4 py-2.5 text-end font-bold tnum whitespace-nowrap">{{ fmt(o.value) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="!tt.sorted.value.length && !loading" class="py-12 text-center text-[12px] text-ink-muted">{{ L("Nothing in this stage.","لا شيء في هذه المرحلة.","Rien ici.") }}</div>
      <TablePager :t="tt" />
    </div>

    <!-- Selection bar -->
    <transition name="fade">
      <div v-if="selected.size" class="fixed bottom-5 inset-x-0 z-40 flex justify-center px-4 pointer-events-none">
        <div class="pointer-events-auto bg-ink text-white rounded-[14px] shadow-xl flex items-center gap-3 ps-4 pe-2 py-2 max-w-full">
          <span class="text-[12.5px] font-bold">{{ selected.size }} {{ L("selected","محدد","sél.") }}</span>
          <span class="text-[12px] text-white/70 tnum">{{ fmt(selTotal) }} {{ ccy }}</span>
          <span v-if="selSupplier" class="text-[11px] text-white/60 truncate max-w-[160px]">· {{ selSupplier }}</span>
          <span v-if="!sameSupplier" class="text-[11px] font-semibold text-amber-300">{{ L("mixed suppliers — pick one","موردون مختلفون","fournisseurs mixtes") }}</span>
          <button @click="clearSel" class="text-[11px] text-white/60 hover:text-white px-1.5">{{ L("clear","مسح","effacer") }}</button>
          <button @click="openGroup" :disabled="!sameSupplier" class="inline-flex items-center gap-1.5 h-8 px-3.5 rounded-[10px] text-[12px] font-bold text-white disabled:opacity-40" :style="{ background: groupMode === 'bill' ? '#0891b2' : '#047857' }">
            <Icon :name="groupMode === 'bill' ? 'doc' : 'wallet'" :size="14" color="#fff" />{{ groupMode === "bill" ? L("Bill together","افوترهم معًا","Facturer ensemble") : L("Pay together","ادفعهم معًا","Payer ensemble") }}
          </button>
        </div>
      </div>
    </transition>

    <!-- Group action dialog -->
    <div v-if="payOpen" class="fixed inset-0 z-50 grid place-items-center bg-black/30 p-4" @click.self="payOpen = false">
      <div class="bg-white rounded-card shadow-xl w-full max-w-sm p-5 space-y-3.5">
        <div class="flex items-center gap-2">
          <span class="w-8 h-8 rounded-[9px] grid place-items-center" :style="{ background: groupMode === 'bill' ? '#ecfeff' : '#ecfdf5' }"><Icon :name="groupMode === 'bill' ? 'doc' : 'wallet'" :size="16" :color="groupMode === 'bill' ? '#0891b2' : '#047857'" /></span>
          <div>
            <div class="text-[14px] font-bold">{{ groupMode === "bill" ? L("Bill together","افوترهم معًا","Facturer ensemble") : L("Pay together","ادفعهم معًا","Payer ensemble") }}</div>
            <div class="text-[11px] text-ink-muted">{{ selected.size }} {{ groupMode === "bill" ? L("receipts","إيصال","réceptions") : L("bills","فاتورة","factures") }} · {{ selSupplier }} · {{ fmt(selTotal) }} {{ ccy }}</div>
          </div>
        </div>
        <template v-if="groupMode === 'pay'">
          <div>
            <label class="text-[11px] font-bold text-ink-3">{{ L("Method","الطريقة","Méthode") }}</label>
            <select v-model="payMode" class="w-full h-9 mt-1 border border-line-2 rounded-[9px] px-2 text-[12.5px] bg-white focus:outline-none focus:border-accent/40">
              <option value="">{{ L("Select…","اختر…","Choisir…") }}</option>
              <option v-for="m in modes" :key="m.mode" :value="m.mode">{{ m.mode }}</option>
            </select>
          </div>
          <div class="grid grid-cols-2 gap-2">
            <div>
              <label class="text-[11px] font-bold text-ink-3">{{ L("Reference No","رقم المرجع","Référence") }}</label>
              <input v-model.trim="payRef" :placeholder="L('Cheque / txn no','شيك / معاملة','Chèque / réf')" class="w-full h-9 mt-1 border border-line-2 rounded-[9px] px-2 text-[12.5px] focus:outline-none focus:border-accent/40" />
            </div>
            <div>
              <label class="text-[11px] font-bold text-ink-3">{{ L("Date","التاريخ","Date") }}</label>
              <input type="date" v-model="payDate" class="w-full h-9 mt-1 border border-line-2 rounded-[9px] px-2 text-[12.5px] focus:outline-none focus:border-accent/40" />
            </div>
          </div>
        </template>
        <p class="text-[10.5px] text-ink-muted">{{ groupMode === "bill" ? L("One Purchase Invoice with all selected receipts' lines · clears their GRNI.","فاتورة شراء واحدة بكل بنود الإيصالات المحددة.","Une seule facture avec toutes les lignes.") : L("One Payment Entry settles all selected bills · bank/cheque needs a reference.","قيد دفع واحد يسوّي كل الفواتير المحددة.","Une seule écriture règle toutes les factures.") }}</p>
        <div class="flex gap-2 justify-end pt-1">
          <button @click="payOpen = false" class="h-9 px-3 rounded-[9px] text-[12px] font-semibold text-ink-3 hover:bg-app-warm">{{ L("Cancel","إلغاء","Annuler") }}</button>
          <button @click="confirmGroup" :disabled="posting || (groupMode === 'pay' && !payMode)" class="h-9 px-4 rounded-[9px] text-[12px] font-bold text-white disabled:opacity-50" :style="{ background: groupMode === 'bill' ? '#0891b2' : '#047857' }">{{ posting ? L("Working…","جارٍ…","…") : (groupMode === "bill" ? L("Create invoice","أنشئ الفاتورة","Créer facture") : L("Pay","دفع","Payer")) }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableToolbar from "@/components/TableToolbar.vue";
import TablePager from "@/components/TablePager.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";
import { useTableTools } from "@/composables/useTableTools";
import { useToast } from "@/composables/useToast";

const toast = useToast();

const route = useRoute();
const router = useRouter();
const { locale } = useI18n();
const { entityId } = useUi();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US");
const money = (n) => { n = Number(n) || 0; const a = Math.abs(n); return a >= 1e6 ? (n / 1e6).toFixed(2) + "M" : a >= 1e3 ? Math.round(n / 1e3) + "K" : Math.round(n).toLocaleString(); };
const today = new Date().toISOString().slice(0, 10);
const isOverdue = (d) => d && d < today;
function methodStyle(m) {
  m = (m || "").toLowerCase();
  if (/cheque|chèque|شيك/.test(m)) return "background:#fffbeb;color:#b45309";
  if (/bank|virement|transfer|حوالة|تحويل/.test(m)) return "background:#eff6ff;color:#0369a1";
  if (/cash|كاش|espèce/.test(m)) return "background:#ecfdf5;color:#047857";
  return "background:#f5f3ff;color:#6d28d9";
}

const PIPE = [
  { key: "tobuy", color: "#0369a1", icon: "cart", tint: "#eff6ff", label: () => L("To buy", "للشراء", "À acheter"), hint: () => L("ordered · not received", "مطلوب · لم يُستلم", "commandé") },
  { key: "received", color: "#b45309", icon: "box", tint: "#fffbeb", label: () => L("Received", "مُستلم", "Reçu"), hint: () => L("received · not billed (GRNI)", "مُستلم · بلا فاتورة", "reçu · non facturé") },
  { key: "billed", color: "#0891b2", icon: "doc", tint: "#ecfeff", label: () => L("Billed", "متفوتر", "Facturé"), hint: () => L("owed · not due yet", "مستحق · لم يَحِن", "dû · pas échu") },
  { key: "topay", color: "#be123c", icon: "wallet", tint: "#fef2f2", label: () => L("To pay", "للدفع", "À payer"), hint: () => L("due / overdue", "مستحق / متأخّر", "échu / en retard") },
  { key: "paid", color: "#047857", icon: "check", tint: "#ecfdf5", label: () => L("Paid", "مدفوع", "Payé"), hint: () => L("settled", "مُسوّى", "réglé") },
];
const bucket = computed(() => (PIPE.some((b) => b.key === route.params.sub) ? route.params.sub : "topay"));
const active = computed(() => PIPE.find((b) => b.key === bucket.value) || PIPE[3]);

const DATE_PRESETS = [
  { key: "all", label: () => L("All", "الكل", "Tout") },
  { key: "today", label: () => L("Today", "اليوم", "Auj.") },
  { key: "7d", label: () => L("7 days", "7 أيام", "7 j") },
  { key: "30d", label: () => L("30 days", "30 يوم", "30 j") },
  { key: "month", label: () => L("This month", "هذا الشهر", "Ce mois") },
  { key: "range", label: () => L("Range", "نطاق", "Plage") },
];

const cols = [
  { key: "name", label: L("Document", "المستند", "Document"), align: "s" },
  { key: "supplier_name", label: L("Supplier", "المورّد", "Fournisseur"), align: "s" },
  { key: "date", label: L("Date", "التاريخ", "Date"), align: "s" },
  { key: "due", label: L("Due", "الاستحقاق", "Échéance"), align: "s" },
  { key: "info", label: L("Progress", "التقدّم", "Suivi"), align: "e" },
  { key: "value", label: L("Value", "القيمة", "Valeur"), align: "e" },
];
function colLabel(c) {
  if (c.key !== "info") return c.label;
  if (bucket.value === "paid") return L("Method", "الطريقة", "Méthode");
  if (bucket.value === "billed" || bucket.value === "topay") return L("Owed", "المستحق", "Dû");
  return L("Received", "مُستلم", "Reçu");
}

const rows = ref([]);
const sum = ref({});
const live = ref(null);
const loading = ref(false);
const srch = ref("");
const datePreset = ref("month");
const dateFrom = ref("");
const dateTo = ref("");
const bucketCount = ref(0);
const bucketValue = ref(0);
const tt = useTableTools(rows, cols, { defaultSort: "value", defaultDir: -1, accessor: (r, k) => (k === "info" ? Number(r.progress) || 0 : r[k]) });

const dateScope = computed(() => { if (datePreset.value === "all") return ""; const p = DATE_PRESETS.find((x) => x.key === datePreset.value); return p ? p.label() : ""; });
function cardCount(k) { return (sum.value[k] && sum.value[k].count) || 0; }
function cardValue(k) { return (sum.value[k] && sum.value[k].value) || 0; }
const ccy = computed(() => sum.value.currency || "MAD");

function bounds(key) {
  const iso = (d) => d.toISOString().slice(0, 10);
  const now = new Date(); const t = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  if (key === "today") return [iso(t), iso(now)];
  if (key === "7d") { const s = new Date(t); s.setDate(s.getDate() - 7); return [iso(s), iso(now)]; }
  if (key === "30d") { const s = new Date(t); s.setDate(s.getDate() - 30); return [iso(s), iso(now)]; }
  if (key === "month") return [iso(new Date(now.getFullYear(), now.getMonth(), 1)), iso(now)];
  if (key === "range") return [dateFrom.value || null, dateTo.value || null];
  return [null, null];
}

const SAMPLE_SUM = { tobuy: { count: 1319, value: 3333693 }, received: { count: 1713, value: 4202082 }, billed: { count: 2, value: 257180 }, topay: { count: 141, value: 3198528 }, paid: { count: 99, value: 4970687 } };
async function loadSummary() {
  const [fd, td] = bounds(datePreset.value);
  try { sum.value = await api.call("accounting_portal.api.purchases.purchases_summary", { company: currentCompany(), from_date: fd || undefined, to_date: td || undefined }) || {}; }
  catch { sum.value = SAMPLE_SUM; }
}
async function loadRows() {
  loading.value = true;
  const [fd, td] = bounds(datePreset.value);
  try {
    const r = await api.call("accounting_portal.api.purchases.list_purchase_bucket", { company: currentCompany(), bucket: bucket.value, search: srch.value || undefined, from_date: fd || undefined, to_date: td || undefined, limit: 500 });
    rows.value = r.rows || []; bucketCount.value = r.count || 0; bucketValue.value = r.value || 0; live.value = true;
  } catch { rows.value = []; bucketCount.value = 0; bucketValue.value = 0; live.value = false; }
  finally { loading.value = false; }
}

function setPreset(k) { datePreset.value = k; if (k !== "range") { loadSummary(); loadRows(); } }
let timer;
watch(entityId, loadSummary, { immediate: true });
watch([bucket, entityId], () => { tt.reset(); loadRows(); }, { immediate: true });
watch([dateFrom, dateTo], () => { clearTimeout(timer); timer = setTimeout(() => { loadSummary(); loadRows(); }, 300); });
watch(srch, () => { clearTimeout(timer); timer = setTimeout(loadRows, 300); });

function goBucket(k) { router.push(`/accounting/purchases/${k}`); }
function open(name) { router.push({ path: `/accounting/purchases/${bucket.value}`, query: { id: name } }); }

// ── Group payment (To Pay / Billed) ──
const selectable = computed(() => bucket.value === "topay" || bucket.value === "billed" || bucket.value === "received");
const groupMode = computed(() => (bucket.value === "received" ? "bill" : "pay"));
const selected = ref(new Set());
const posting = ref(false);
const payOpen = ref(false);
const payMode = ref("");
const payRef = ref("");
const payDate = ref(new Date().toISOString().slice(0, 10));
const modes = ref([]);

function toggleRow(o) { const s = new Set(selected.value); s.has(o.name) ? s.delete(o.name) : s.add(o.name); selected.value = s; }
const allPageSelected = computed(() => { const p = tt.pageRows.value; return p.length > 0 && p.every((r) => selected.value.has(r.name)); });
function toggleAllPage() { const s = new Set(selected.value); const p = tt.pageRows.value; const all = p.every((r) => s.has(r.name)); p.forEach((r) => (all ? s.delete(r.name) : s.add(r.name))); selected.value = s; }
function clearSel() { selected.value = new Set(); }

const selRows = computed(() => rows.value.filter((r) => selected.value.has(r.name)));
const selTotal = computed(() => selRows.value.reduce((a, r) => a + (Number(groupMode.value === "bill" ? r.value : r.progress) || 0), 0));
const selSuppliers = computed(() => [...new Set(selRows.value.map((r) => r.supplier))]);
const sameSupplier = computed(() => selSuppliers.value.length === 1);
const selSupplier = computed(() => (selRows.value[0] ? selRows.value[0].supplier_name : ""));

async function openGroup() {
  if (!sameSupplier.value) return;
  if (groupMode.value === "bill") { payOpen.value = true; return; }
  payRef.value = ""; payMode.value = "";
  payDate.value = new Date().toISOString().slice(0, 10);
  payOpen.value = true;
  if (!modes.value.length) {
    try { modes.value = await api.call("accounting_portal.api.purchases.payment_modes", { company: currentCompany() }); }
    catch { modes.value = []; }
  }
}
function confirmGroup() { return groupMode.value === "bill" ? confirmGroupBill() : confirmGroupPay(); }

async function confirmGroupBill() {
  posting.value = true;
  try {
    const res = await api.call("accounting_portal.api.purchases.make_invoice_group", {
      company: currentCompany(), receipts: [...selected.value],
    });
    payOpen.value = false;
    if (res && res.status === "Proposed") toast.info(L("Sent for approval (material amount)", "أُرسل للموافقة (مبلغ كبير)", "Envoyé pour approbation"));
    else { toast.success(L("Invoice created", "أُنشئت الفاتورة", "Facture créée") + (res && res.voucher_no ? " · " + res.voucher_no : "")); clearSel(); loadSummary(); loadRows(); }
  } catch (e) { toast.error((e && e.message ? String(e.message) : L("Billing failed", "فشلت الفوترة", "Échec")).slice(0, 160)); }
  finally { posting.value = false; }
}
async function confirmGroupPay() {
  posting.value = true;
  try {
    const m = modes.value.find((x) => x.mode === payMode.value);
    const res = await api.call("accounting_portal.api.purchases.pay_bills_group", {
      company: currentCompany(), invoices: [...selected.value], mode: payMode.value,
      paid_from: (m && m.account) || undefined, reference_no: payRef.value || undefined, reference_date: payDate.value || undefined,
    });
    payOpen.value = false;
    if (res && res.status === "Proposed") toast.info(L("Sent for approval (material amount)", "أُرسل للموافقة (مبلغ كبير)", "Envoyé pour approbation"));
    else { toast.success(L("Paid", "تم الدفع", "Payé") + (res && res.voucher_no ? " · " + res.voucher_no : "")); clearSel(); loadSummary(); loadRows(); }
  } catch (e) { toast.error((e && e.message ? String(e.message) : L("Payment failed", "فشل الدفع", "Échec")).slice(0, 160)); }
  finally { posting.value = false; }
}
watch(bucket, clearSel);
</script>
