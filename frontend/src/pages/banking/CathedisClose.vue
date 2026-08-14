<template>
  <div class="space-y-3.5">
    <!-- Headline -->
    <div class="flex items-center gap-2 flex-wrap">
      <span class="text-[13px] font-bold">{{ L("Cathedis clearing close","إقفال حساب Cathedis","Clôture Cathedis") }}</span>
      <span class="text-[11px] text-ink-muted flex-1">{{ L("Delivered invoices whose COD cash reached the bank but the collection receipt was never booked — post the missing receipt (Dr Cathedis / Cr customer). Bank & revenue untouched.","فواتير متسلّمة وصل كاشها للبنك بس سند القبض ما اتعملش — نعمل السند الناقص (مدين Cathedis / دائن العميل). البنك والإيراد ما يتلمسوش.","Factures livrées dont le cash COD a atteint la banque sans reçu d'encaissement.") }}</span>
    </div>

    <!-- KPI row -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-2.5">
      <div v-for="s in stats" :key="s.label" class="bg-white rounded-[12px] border p-3.5 shadow-card" :style="{ borderColor: s.bd || '#efe9e6' }">
        <div class="text-[10.5px] text-ink-muted font-semibold">{{ s.label }}</div>
        <div class="text-[19px] font-bold tnum mt-[3px]" :style="{ color: s.color || '#1c1917' }">{{ s.value }}</div>
        <div class="text-[10.5px] text-ink-3 mt-0.5">{{ s.sub }}</div>
      </div>
    </div>

    <!-- Action bar -->
    <div v-if="canWrite" class="bg-white border border-line rounded-[12px] shadow-card p-3 flex flex-wrap items-center gap-2">
      <span class="text-[11.5px] text-ink-muted">{{ L("Post missing collection receipts","ترحيل سندات القبض الناقصة","Poster les reçus manquants") }}</span>
      <div class="flex-1"></div>
      <button class="h-[30px] px-3 rounded-[8px] text-[11.5px] font-bold border border-line text-ink-2 hover:bg-app-warm disabled:opacity-50"
              :disabled="running" @click="runBatch(10)">{{ L("Test 10","جرّب 10","Test 10") }}</button>
      <button class="h-[30px] px-3 rounded-[8px] text-[11.5px] font-bold border border-line text-ink-2 hover:bg-app-warm disabled:opacity-50"
              :disabled="running" @click="runBatch(50)">{{ L("Post 50","رحّل 50","Poster 50") }}</button>
      <button class="h-[30px] px-3.5 rounded-[8px] text-[11.5px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand disabled:opacity-50"
              :disabled="running || !sum || !sum.ready_count" @click="runAll">
        {{ running ? L("Posting…","جارٍ الترحيل…","…") : L("Close all","اقفل الكل","Tout clôturer") }}
      </button>
    </div>

    <!-- Progress / result banner -->
    <div v-if="progress" class="rounded-[12px] border px-4 py-3 text-[12px]"
         :style="progress.failed ? 'background:#fffbeb;border-color:#fde68a;color:#92400e' : 'background:#ecfdf5;border-color:#a7f3d0;color:#047857'">
      <div class="font-bold">{{ L("Posted","تم الترحيل","Postés") }}: {{ progress.posted }} · {{ L("skipped","تخطّي","ignorés") }}: {{ progress.skipped }} · {{ L("failed","فشل","échoués") }}: {{ progress.failed }}</div>
      <div class="mt-0.5">{{ L("Cathedis","Cathedis","Cathedis") }}: {{ fmtNum(progress.cathedis_before) }} → <b>{{ fmtNum(progress.cathedis_after) }}</b>
        <span class="text-ink-3">({{ deltaLabel }})</span></div>
    </div>

    <!-- Worklist -->
    <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
      <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2">
        <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#fff7ed"><Icon name="truck" :size="14" color="#c2410c" /></span>
        <span class="text-[13px] font-bold">{{ L("Delivered · unpaid","متسلّمة · غير مدفوعة","Livrées · impayées") }}</span>
        <span class="text-[11px] text-ink-muted">{{ st.total.value }} {{ L("invoices","فاتورة","factures") }}</span>
        <div class="flex-1"></div>
        <input v-model.trim="st.search.value" :placeholder="L('Search invoice / customer / tracking…','بحث فاتورة / عميل / تتبّع…','Recherche…')"
               class="h-[30px] w-[240px] max-w-full text-[12px] px-3 rounded-[8px] border border-line focus:border-brand outline-none" />
        <select v-model="onlyFilter" class="h-[30px] text-[12px] px-2 rounded-[8px] border border-line">
          <option value="ready">{{ L("Ready","جاهزة","Prêtes") }}</option>
          <option value="anomaly">{{ L("Anomalies (SI>SO)","شاذة (فاتورة>أوردر)","Anomalies") }}</option>
          <option value="">{{ L("All","الكل","Toutes") }}</option>
        </select>
      </div>
      <div v-if="st.error.value" class="py-8 text-center text-[12px] text-sale">{{ st.error.value }} · <button class="underline" @click="st.load()">{{ L("Retry","إعادة","Réessayer") }}</button></div>
      <div v-else class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead>
            <tr style="background:#fafaf9">
              <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Invoice","الفاتورة","Facture") }}</th>
              <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Customer","العميل","Client") }}</th>
              <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Unpaid","غير مدفوع","Impayé") }}</th>
              <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Order","الأوردر","Commande") }}</th>
              <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Receipt date","تاريخ السند","Date reçu") }}</th>
              <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Tracking","التتبّع","Suivi") }}</th>
              <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in st.rows.value" :key="r.invoice" class="border-t border-line-hair hover:bg-app-warm/60">
              <td class="px-4 py-2.5 font-mono font-semibold whitespace-nowrap">{{ r.invoice }}</td>
              <td class="px-4 py-2.5 truncate max-w-[170px]">{{ r.customer }}</td>
              <td class="px-4 py-2.5 text-end tnum font-bold">{{ fmtNum(r.outstanding) }}</td>
              <td class="px-4 py-2.5 text-end tnum" :class="Math.abs(r.diff) > 5 ? 'text-amber-600' : 'text-ink-3'">
                {{ fmtNum(r.so_total) }}<span v-if="Math.abs(r.diff) > 5" class="text-[10px]"> (Δ{{ fmtNum(r.diff) }})</span>
              </td>
              <td class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ r.pe_date }}</td>
              <td class="px-4 py-2.5 text-ink-3 font-mono text-[11px] whitespace-nowrap">{{ r.tracking || "—" }}</td>
              <td class="px-4 py-2.5 text-end">
                <span v-if="r.state === 'anomaly'" class="text-[10px] font-bold text-amber-600">{{ L("review","مراجعة","revue") }}</span>
                <button v-else-if="canWrite" class="h-[26px] px-2.5 rounded-[7px] text-[10.5px] font-bold text-white bg-brand hover:bg-brand-dark disabled:opacity-50"
                        :disabled="running" @click="postOne(r)">{{ L("Post","رحّل","Poster") }}</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="!st.loading.value && !st.rows.value.length && !st.error.value" class="py-12 text-center text-[12px] text-ink-muted">
        {{ L("Nothing to post — Cathedis is clean.","لا شيء للترحيل — Cathedis نظيف.","Rien à poster.") }}
      </div>
      <ServerPager :t="st" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import ServerPager from "@/components/ServerPager.vue";
import { useServerTable } from "@/composables/useServerTable";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useToast } from "@/composables/useToast";
import { useAuth } from "@/composables/useAuth";
import { useUi } from "@/composables/useUi";

const { locale } = useI18n();
const { entityId } = useUi();
const toast = useToast();
const { can } = useAuth();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmtNum = (n) => Math.round(Number(n) || 0).toLocaleString("en-US");
const canWrite = computed(() => can("post_entries"));

const M = "accounting_portal.api.cod_close";
const sum = ref(null);
const running = ref(false);
const progress = ref(null);
const onlyFilter = ref("ready");

async function loadSummary() {
  try { sum.value = await api.call(`${M}.summary`, { company: currentCompany() }, { fresh: true }); }
  catch (e) { sum.value = null; }
}
loadSummary();

const st = useServerTable(
  (params) => api.call(`${M}.worklist`, { company: currentCompany(), only: onlyFilter.value, ...params }),
  { pageSize: 50 });
st.load();
watch(onlyFilter, () => { st.page.value = 1; st.load(); });
watch(entityId, () => { st.page.value = 1; st.load(); loadSummary(); });

const stats = computed(() => {
  const s = sum.value || {};
  return [
    { label: L("Cathedis balance","رصيد Cathedis","Solde Cathedis"), value: fmtNum(s.cathedis_balance), sub: L("target ≈ 0","الهدف ≈ 0","cible ≈ 0"),
      color: Math.abs(Number(s.cathedis_balance) || 0) > 1000 ? "#b91c1c" : "#047857" },
    { label: L("Ready to post","جاهزة للترحيل","Prêtes"), value: fmtNum(s.ready_count), sub: fmtNum(s.ready_value) + " MAD", bd: "#a7f3d0" },
    { label: L("Anomalies (SI>SO)","شاذة","Anomalies"), value: fmtNum(s.anomaly_count), sub: L("manual review","مراجعة يدوية","revue"), bd: "#fde68a", color: "#b45309" },
    { label: L("Total unpaid","إجمالي غير المدفوع","Total impayé"), value: fmtNum(s.total_count), sub: L("delivered invoices","فواتير متسلّمة","factures livrées") },
  ];
});

const deltaLabel = computed(() => {
  if (!progress.value) return "";
  const d = Math.round((Number(progress.value.cathedis_after) || 0) - (Number(progress.value.cathedis_before) || 0));
  return (d >= 0 ? "+" : "") + d.toLocaleString("en-US");
});

async function afterPost() { await loadSummary(); await st.load(); }

async function postOne(r) {
  if (running.value) return;
  running.value = true;
  try {
    const res = await api.call(`${M}.post_one`, { company: currentCompany(), invoice: r.invoice });
    if (res.status === "Posted") toast.success(L("Receipt posted","تم ترحيل السند","Reçu posté"));
    else toast.info(res.status + (res.detail ? " · " + res.detail : ""));
    await afterPost();
  } catch (e) { toast.error(e.message || "Failed"); }
  finally { running.value = false; }
}

async function runBatch(limit) {
  if (running.value) return;
  running.value = true;
  try {
    const res = await api.call(`${M}.post_batch`, { company: currentCompany(), limit });
    progress.value = res;
    toast.success(L(`Posted ${res.posted}`, `تم ترحيل ${res.posted}`, `${res.posted} postés`));
    await afterPost();
  } catch (e) { toast.error(e.message || "Failed"); }
  finally { running.value = false; }
}

// Loop batches of 200 until no READY rows remain (or a batch makes no progress).
async function runAll() {
  if (running.value) return;
  if (!window.confirm(L(
    `Post collection receipts for all ${sum.value?.ready_count || 0} ready invoices? This is reversible per-receipt from the Activity log.`,
    `ترحيل سندات القبض لكل الـ${sum.value?.ready_count || 0} فاتورة الجاهزة؟ كل سند قابل للعكس من سجل النشاط.`,
    `Poster tous les ${sum.value?.ready_count || 0} reçus ?`))) return;
  running.value = true;
  let posted = 0, failed = 0, skipped = 0, before = null, after = null;
  try {
    for (let i = 0; i < 400; i++) { // hard cap on rounds (400×50 = 20k) — safety
      const res = await api.call(`${M}.post_batch`, { company: currentCompany(), limit: 50 });
      if (before === null) before = res.cathedis_before;
      after = res.cathedis_after;
      posted += res.posted; failed += res.failed; skipped += res.skipped;
      progress.value = { posted, failed, skipped, cathedis_before: before, cathedis_after: after };
      if (res.posted === 0) break; // nothing advanced → done (or all remaining fail)
    }
    toast.success(L(`Done — ${posted} posted`, `تم — ${posted} سند`, `Terminé — ${posted}`));
    await afterPost();
  } catch (e) { toast.error(e.message || "Failed"); }
  finally { running.value = false; }
}
</script>
