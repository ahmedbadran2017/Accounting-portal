<template>
  <div class="space-y-3.5">
    <div v-if="loading"><TableLoading :rows="8" /></div>
    <template v-else>
      <!-- Toolbar: net working capital + export -->
      <div class="flex items-center gap-3 flex-wrap">
        <div class="inline-flex items-center gap-2 bg-white border border-line rounded-card px-3.5 py-2 shadow-card">
          <span class="text-[11px] font-bold text-ink-muted uppercase tracking-wider">{{ L("Net working capital", "صافي رأس المال العامل", "BFR net") }}</span>
          <span class="text-[15px] font-extrabold tnum" :style="{ color: wc >= 0 ? '#047857' : '#be123c' }">{{ money(wc) }} <span class="text-[10px] text-ink-muted">MAD</span></span>
          <span class="text-[10px] text-ink-muted">{{ L("AR − AP", "مدينة − دائنة", "AR − AP") }}</span>
        </div>
        <button @click="exportCSV" class="ms-auto inline-flex items-center gap-1.5 h-9 px-3 rounded-chip border border-line-2 bg-white text-[12px] font-semibold text-ink-2 hover:bg-app-warm">
          <Icon name="download" :size="14" />{{ L("Export", "تصدير", "Exporter") }}
        </button>
      </div>

      <!-- Headline -->
      <div class="grid sm:grid-cols-2 gap-3.5">
        <button @click="drill('/accounting/sales/delivered')" class="bg-white rounded-card border border-line shadow-card p-5 text-start hover:-translate-y-0.5 hover:shadow-cardHover transition-all">
          <div class="flex items-center gap-2"><span class="w-7 h-7 rounded-[9px] grid place-items-center" style="background:#eff6ff"><Icon name="trend" :size="15" color="#0369a1" /></span><span class="text-[12px] font-bold text-ink-3">{{ L("Receivables (AR)", "الذمم المدينة", "Créances") }}</span><Icon name="arrow" :size="12" color="#a8a29e" class="ms-auto rtl:rotate-180" /></div>
          <div class="text-[26px] font-extrabold tnum mt-2" style="color:#0369a1">{{ money(ar.operational) }}<span class="text-[12px] text-ink-muted ms-1">MAD</span></div>
          <div class="text-[11px] text-ink-muted mt-1">{{ L("operational — what's really owed to us", "تشغيلي — المستحق الحقيقي لنا", "opérationnel") }}</div>
          <div class="mt-2 inline-flex items-center gap-1.5 text-[10.5px] font-bold px-2 py-0.5 rounded-full" style="background:#fef2f2;color:#be123c"><Icon name="alert" :size="11" />{{ L("GL broken — needs reconciliation", "الـ GL مكسور — يحتاج مطابقة", "GL à réconcilier") }}</div>
        </button>
        <button @click="drill('/accounting/purchases/topay')" class="bg-white rounded-card border border-line shadow-card p-5 text-start hover:-translate-y-0.5 hover:shadow-cardHover transition-all">
          <div class="flex items-center gap-2"><span class="w-7 h-7 rounded-[9px] grid place-items-center" style="background:#fef2f2"><Icon name="wallet" :size="15" color="#be123c" /></span><span class="text-[12px] font-bold text-ink-3">{{ L("Payables (AP)", "الذمم الدائنة", "Dettes") }}</span><Icon name="arrow" :size="12" color="#a8a29e" class="ms-auto rtl:rotate-180" /></div>
          <div class="text-[26px] font-extrabold tnum mt-2" style="color:#be123c">{{ money(ap.net_invoice) }}<span class="text-[12px] text-ink-muted ms-1">MAD</span></div>
          <div class="text-[11px] text-ink-muted mt-1">{{ L("net of supplier advances", "صافي بعد المقدّمات", "net des avances") }}</div>
          <div class="mt-2 inline-flex items-center gap-1.5 text-[10.5px] font-bold px-2 py-0.5 rounded-full" :style="ap.reconciled ? 'background:#ecfdf5;color:#047857' : 'background:#fffbeb;color:#b45309'"><Icon :name="ap.reconciled ? 'check' : 'alert'" :size="11" />{{ ap.reconciled ? L("ties to GL", "مطابق للـ GL", "concorde") : L("small gap to GL", "فرق بسيط مع الـ GL", "léger écart") }}</div>
        </button>
      </div>

      <!-- AR reconciliation -->
      <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
        <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><Icon name="trend" :size="14" color="#0369a1" /><span class="text-[12px] font-bold">{{ L("Receivables — operational vs book", "الذمم المدينة — تشغيلي مقابل دفتري", "Créances — opérationnel vs comptable") }}</span></div>
        <table class="w-full text-[12.5px]">
          <tbody>
            <tr class="border-b border-line-hair hover:bg-app-warm/60 cursor-pointer" @click="drill('/accounting/sales/delivered')"><td class="px-4 py-2.5"><Icon name="arrow" :size="10" color="#cfc9c4" class="inline me-1 rtl:rotate-180" />{{ L("Carrier float (delivered · not collected)", "عهدة الناقل (مُسلّم · غير محصّل)", "En cours transporteur") }}</td><td class="px-4 py-2.5 text-end tnum font-semibold">{{ fmt(ar.carrier_float) }}</td></tr>
            <tr class="border-b border-line-hair hover:bg-app-warm/60 cursor-pointer" @click="drill('/accounting/sales/invoices')"><td class="px-4 py-2.5"><Icon name="arrow" :size="10" color="#cfc9c4" class="inline me-1 rtl:rotate-180" />{{ L("Invoiced & unpaid", "متفوتر وغير مدفوع", "Facturé impayé") }}</td><td class="px-4 py-2.5 text-end tnum font-semibold">{{ fmt(ar.si_outstanding) }}</td></tr>
            <tr class="border-b border-line-hair bg-accent/5"><td class="px-4 py-2.5 font-bold">{{ L("= Operational receivable", "= المستحق التشغيلي", "= Créance opérationnelle") }}</td><td class="px-4 py-2.5 text-end tnum font-extrabold">{{ fmt(ar.operational) }}</td></tr>
            <tr class="border-b border-line-hair"><td class="px-4 py-2.5 text-ink-3">{{ L("Book balance — GL Debtors", "الرصيد الدفتري — مدينون", "Solde GL Débiteurs") }}</td><td class="px-4 py-2.5 text-end tnum font-bold" :class="ar.gl_debtors < 0 ? 'text-sale' : ''">{{ fmt(ar.gl_debtors) }}</td></tr>
          </tbody>
        </table>
        <div class="px-4 py-2.5 bg-sale/5 border-t border-line-hair text-[11px] text-sale flex items-start gap-2 flex-wrap">
          <Icon name="alert" :size="13" class="mt-0.5 flex-shrink-0" />
          <span class="flex-1 min-w-[200px]">{{ L("GL Debtors is a credit balance (wrong sign) — COD collections aren't applied to invoices. Run the Cathedis reconciliation to clear it.", "مدينون برصيد دائن (إشارة عكسية) — تحصيلات الـ COD غير مطبّقة على الفواتير. شغّل مطابقة كاتدييس.", "Débiteurs créditeur — encaissements COD non affectés.") }}</span>
          <button @click="goReconcile" class="inline-flex items-center gap-1.5 h-7 px-3 rounded-chip text-[11px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand flex-shrink-0"><Icon name="trend" :size="12" color="#fff" />{{ L("Reconcile now", "صالِح الآن", "Réconcilier") }}<Icon name="arrow" :size="11" color="#fff" class="rtl:rotate-180" /></button>
        </div>
      </div>

      <!-- AP reconciliation -->
      <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
        <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><Icon name="wallet" :size="14" color="#be123c" /><span class="text-[12px] font-bold">{{ L("Payables — operational vs book", "الذمم الدائنة — تشغيلي مقابل دفتري", "Dettes — opérationnel vs comptable") }}</span></div>
        <table class="w-full text-[12.5px]">
          <tbody>
            <tr class="border-b border-line-hair hover:bg-app-warm/60 cursor-pointer" @click="drill('/accounting/purchases/topay')"><td class="px-4 py-2.5"><Icon name="arrow" :size="10" color="#cfc9c4" class="inline me-1 rtl:rotate-180" />{{ L("Unpaid bills (To pay + Billed)", "فواتير غير مدفوعة", "Factures impayées") }}</td><td class="px-4 py-2.5 text-end tnum font-semibold">{{ fmt(ap.pi_unpaid) }}</td></tr>
            <tr class="border-b border-line-hair hover:bg-app-warm/60 cursor-pointer" @click="drill('/accounting/purchases/payments')"><td class="px-4 py-2.5"><Icon name="arrow" :size="10" color="#cfc9c4" class="inline me-1 rtl:rotate-180" />{{ L("− Supplier advances (prepaid)", "− دفعات مقدّمة للمورّدين", "− Avances fournisseurs") }}</td><td class="px-4 py-2.5 text-end tnum font-semibold text-accent-dark">({{ fmt(ap.advances) }})</td></tr>
            <tr class="border-b border-line-hair bg-accent/5"><td class="px-4 py-2.5 font-bold">{{ L("= Net bills owed", "= صافي المستحق", "= Net dû") }}</td><td class="px-4 py-2.5 text-end tnum font-extrabold">{{ fmt(ap.net_invoice) }}</td></tr>
            <tr class="border-b border-line-hair"><td class="px-4 py-2.5 text-ink-3">{{ L("Book balance — GL Creditors", "الرصيد الدفتري — دائنون", "Solde GL Créditeurs") }}</td><td class="px-4 py-2.5 text-end tnum font-bold">{{ fmt(ap.gl_creditors) }}</td></tr>
            <tr><td class="px-4 py-2.5 text-ink-muted text-[11.5px]">{{ L("Gap to GL", "الفرق مع الـ GL", "Écart") }}</td><td class="px-4 py-2.5 text-end tnum text-[11.5px]" :class="Math.abs(ap.invoice_gap) > 1000 ? 'text-sale font-semibold' : 'text-ink-muted'">{{ fmt(ap.invoice_gap) }}</td></tr>
          </tbody>
        </table>
        <div class="px-4 py-2.5 bg-app-warm/30 border-t border-line-hair flex items-center justify-between flex-wrap gap-2 cursor-pointer hover:bg-app-warm/50" @click="drill('/accounting/purchases/received')">
          <span class="text-[11.5px] text-ink-2"><b>{{ L("GRNI", "GRNI", "GRNI") }}</b> · {{ L("received, not billed (accrued liability)", "مستلم بلا فاتورة (التزام مستحق)", "reçu non facturé") }}</span>
          <span class="text-[11.5px] tnum">{{ L("op", "تشغيلي", "op") }} <b>{{ fmt(ap.grni) }}</b> · {{ L("GL", "دفتري", "GL") }} {{ fmt(ap.gl_grni) }} · {{ L("gap", "فرق", "écart") }} <span :class="Math.abs(ap.grni_gap) > 1000 ? 'text-sale font-semibold' : ''">{{ fmt(ap.grni_gap) }}</span></span>
        </div>
        <AgingBar :a="r.ap_aging" :L="L" :fmt="fmt" />
      </div>

      <!-- Follow-up: who we owe + where prepaid cash sits -->
      <div class="grid sm:grid-cols-2 gap-3.5">
        <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
          <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><Icon name="wallet" :size="14" color="#be123c" /><span class="text-[12px] font-bold">{{ L("Top suppliers we owe", "أكبر دائنين", "Principaux créditeurs") }}</span></div>
          <button v-for="(t, i) in (r.top_creditors || [])" :key="t.party" @click="drill('/accounting/purchases/vendors', { id: t.party })"
                  class="w-full flex items-center gap-2.5 px-4 py-2.5 border-t border-line-hair first:border-t-0 hover:bg-app-warm/60 text-start">
            <span class="w-5 text-[11px] font-bold text-ink-muted tnum">{{ i + 1 }}</span>
            <span class="flex-1 truncate text-[12px]">{{ t.name }}</span>
            <span class="tnum font-bold text-[12.5px] text-sale">{{ fmt(t.owed) }}</span>
          </button>
          <div v-if="!(r.top_creditors || []).length" class="py-6 text-center text-[11px] text-ink-muted">—</div>
        </div>
        <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
          <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><Icon name="coins" :size="14" color="#b45309" /><span class="text-[12px] font-bold">{{ L("Prepaid — to match to bills", "مقدّمات — للمطابقة", "Avances à affecter") }}</span></div>
          <button v-for="t in (r.top_advances || [])" :key="t.party" @click="drill('/accounting/purchases/payments')"
                  class="w-full flex items-center gap-2.5 px-4 py-2.5 border-t border-line-hair first:border-t-0 hover:bg-app-warm/60 text-start">
            <span class="flex-1 truncate text-[12px]">{{ t.name }}<span class="text-ink-muted text-[10px] ms-1.5">· {{ t.n }} {{ L("pmts", "دفعة", "pmts") }}</span></span>
            <span class="tnum font-bold text-[12.5px]" style="color:#b45309">{{ fmt(t.adv) }}</span>
          </button>
          <div v-if="!(r.top_advances || []).length" class="py-6 text-center text-[11px] text-ink-muted">—</div>
        </div>
      </div>

      <!-- Aged trial balance by party (the auditor's listing) -->
      <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
        <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2 flex-wrap">
          <Icon name="list" :size="14" color="#0b5c4f" /><span class="text-[12px] font-bold">{{ L("Aged by party","الأعمار حسب الطرف","Ancienneté par tiers") }}</span>
          <div class="ms-auto flex gap-1 bg-app-warm/60 rounded-chip p-0.5">
            <button type="button" class="px-2.5 py-1 rounded-lg text-[11px]" :class="agingKind==='ar' ? 'bg-white font-bold text-accent-dark shadow-card' : 'text-ink-3'" @click="loadAging('ar')">{{ L("Receivable","مدينة","Créances") }}</button>
            <button type="button" class="px-2.5 py-1 rounded-lg text-[11px]" :class="agingKind==='ap' ? 'bg-white font-bold text-accent-dark shadow-card' : 'text-ink-3'" @click="loadAging('ap')">{{ L("Payable","دائنة","Dettes") }}</button>
          </div>
        </div>
        <div class="overflow-x-auto max-h-[420px] overflow-y-auto">
          <table class="w-full text-[12px]">
            <thead><tr style="background:#fafaf9" class="text-[10px] font-bold uppercase tracking-wider text-ink-muted sticky top-0">
              <th class="px-4 py-2 text-start">{{ L("Party","الطرف","Tiers") }}</th>
              <th class="px-2 py-2 text-end">{{ L("Current","حالي","Courant") }}</th><th class="px-2 py-2 text-end">1–30</th><th class="px-2 py-2 text-end">31–60</th><th class="px-2 py-2 text-end">61–90</th><th class="px-2 py-2 text-end">90+</th><th class="px-4 py-2 text-end">{{ L("Total","الإجمالي","Total") }}</th>
            </tr></thead>
            <tbody>
              <tr v-for="p in agingRows" :key="p.party" class="border-t border-line-hair hover:bg-app-warm/40">
                <td class="px-4 py-2 truncate max-w-[220px]">{{ p.party_name || p.party }}</td>
                <td class="px-2 py-2 text-end tnum text-ink-3">{{ fmt(p.cur) }}</td><td class="px-2 py-2 text-end tnum">{{ fmt(p.d1_30) }}</td><td class="px-2 py-2 text-end tnum">{{ fmt(p.d31_60) }}</td><td class="px-2 py-2 text-end tnum text-amber-700">{{ fmt(p.d61_90) }}</td><td class="px-2 py-2 text-end tnum text-sale font-semibold">{{ fmt(p.d90p) }}</td>
                <td class="px-4 py-2 text-end tnum font-bold">{{ fmt(p.total) }}</td>
              </tr>
              <tr v-if="agingTotals" class="border-t-2 border-line-2" style="background:#fafaf9">
                <td class="px-4 py-2 font-bold">{{ L("TOTAL","الإجمالي","TOTAL") }}</td>
                <td class="px-2 py-2 text-end tnum font-bold">{{ fmt(agingTotals.cur) }}</td><td class="px-2 py-2 text-end tnum font-bold">{{ fmt(agingTotals.d1_30) }}</td><td class="px-2 py-2 text-end tnum font-bold">{{ fmt(agingTotals.d31_60) }}</td><td class="px-2 py-2 text-end tnum font-bold">{{ fmt(agingTotals.d61_90) }}</td><td class="px-2 py-2 text-end tnum font-bold">{{ fmt(agingTotals.d90p) }}</td>
                <td class="px-4 py-2 text-end tnum font-bold">{{ fmt(agingTotals.total) }}</td>
              </tr>
              <tr v-if="!agingRows.length"><td colspan="7" class="px-4 py-8 text-center text-ink-muted">—</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { fmtAmount } from "@/utils/helpers";
import { ref, computed, watch, h } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";

const { locale } = useI18n();
const router = useRouter();
const { entityId } = useUi();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US");
const money = (n) => fmtAmount(n);

function goReconcile() { router.push("/accounting/sales/collected?recon=1"); }
function drill(path, query) { router.push(query ? { path, query } : path); }

const r = ref({ ar: {}, ap: {}, ar_aging: {}, ap_aging: {}, top_creditors: [], top_advances: [] });
const loading = ref(true);
const ar = computed(() => r.value.ar || {});
const ap = computed(() => r.value.ap || {});
const wc = computed(() => Number(r.value.working_capital) || 0);

const SAMPLE = {
  working_capital: -2803650,
  ar: { carrier_float: 981370, si_outstanding: 0, operational: 981370, gl_debtors: -2851136, wrong_sign: true },
  ap: { pi_unpaid: 7560155, advances: 3775135, net_invoice: 3785020, gl_creditors: 4046355, invoice_gap: -261335, grni: 4376059, gl_grni: 3136293, grni_gap: 1239766, reconciled: false },
  top_creditors: [{ party: "BISFOR", name: "BISFOR LOGISTIC SARL", owed: 3356108 }, { party: "Meta", name: "Meta / Facebook Ads", owed: 734812 }, { party: "China", name: "Justyol China", owed: 248305 }],
  top_advances: [{ party: "Maslak", name: "Maslak LTD", n: 5, adv: 800462 }, { party: "BISFOR", name: "BISFOR LOGISTIC SARL", n: 15, adv: 689579 }, { party: "Aramex", name: "ARAMEX", n: 7, adv: 473699 }],
  ar_aging: { cur: 0, d1_30: 0, d31_60: 0, d61_90: 0, d90p: 0, total: 0 },
  ap_aging: { cur: 257180, d1_30: 800000, d31_60: 900000, d61_90: 600000, d90p: 640000, total: 3198528 },
};
async function load() {
  loading.value = true;
  try { r.value = await api.call("accounting_portal.api.reports.ar_ap_reconciliation", { company: currentCompany() }) || SAMPLE; }
  catch { r.value = SAMPLE; }
  finally { loading.value = false; }
}
watch(entityId, load, { immediate: true });

const agingKind = ref("ap"), agingRows = ref([]), agingTotals = ref(null);
async function loadAging(kind) {
  agingKind.value = kind;
  try {
    const res = await api.call("accounting_portal.api.reports.aging_by_party", { company: currentCompany(), kind });
    agingRows.value = res?.rows || []; agingTotals.value = res?.totals || null;
  } catch { agingRows.value = []; agingTotals.value = null; }
}
watch(entityId, () => loadAging(agingKind.value), { immediate: true });

function exportCSV() {
  const a = r.value.ar || {}, p = r.value.ap || {};
  const lines = [
    ["Section", "Line", "Amount"],
    ["AR", "Carrier float (delivered, not collected)", a.carrier_float],
    ["AR", "Invoiced & unpaid", a.si_outstanding],
    ["AR", "= Operational receivable", a.operational],
    ["AR", "GL Debtors (book)", a.gl_debtors],
    ["AP", "Unpaid bills (To pay + Billed)", p.pi_unpaid],
    ["AP", "Supplier advances (prepaid)", -p.advances],
    ["AP", "= Net bills owed", p.net_invoice],
    ["AP", "GL Creditors (book)", p.gl_creditors],
    ["AP", "Gap to GL", p.invoice_gap],
    ["AP", "GRNI operational", p.grni],
    ["AP", "GRNI GL", p.gl_grni],
    ["", "Net working capital (AR − AP)", r.value.working_capital],
  ];
  const csv = "﻿" + lines.map((row) => row.map((v) => `"${String(v ?? "").replace(/"/g, '""')}"`).join(",")).join("\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8;" }));
  const el = document.createElement("a"); el.href = url; el.download = "receivables-payables.csv";
  document.body.appendChild(el); el.click(); el.remove(); URL.revokeObjectURL(url);
}

const AgingBar = {
  props: ["a", "L", "fmt"],
  setup(props) {
    const segs = [
      { k: "cur", c: "#047857", l: () => props.L("Current", "حالي", "Courant") },
      { k: "d1_30", c: "#65a30d", l: () => props.L("1-30", "1-30", "1-30") },
      { k: "d31_60", c: "#d97706", l: () => props.L("31-60", "31-60", "31-60") },
      { k: "d61_90", c: "#ea580c", l: () => props.L("61-90", "61-90", "61-90") },
      { k: "d90p", c: "#be123c", l: () => props.L("90+", "90+", "90+") },
    ];
    return () => {
      const a = props.a || {}; const total = Math.max(1, Number(a.total) || 0);
      return h("div", { class: "px-4 py-3 border-t border-line-hair" }, [
        h("div", { class: "flex h-2.5 rounded-full overflow-hidden bg-app-warm" },
          segs.map((s) => h("div", { style: { width: ((Number(a[s.k]) || 0) / total * 100) + "%", background: s.c } }))),
        h("div", { class: "flex flex-wrap gap-x-4 gap-y-1 mt-2" },
          segs.map((s) => h("span", { class: "text-[10.5px] text-ink-3 inline-flex items-center gap-1" }, [
            h("span", { class: "w-2 h-2 rounded-full inline-block", style: { background: s.c } }),
            s.l() + " ", h("b", { class: "tnum" }, props.fmt(a[s.k] || 0)),
          ]))),
      ]);
    };
  },
};
</script>
