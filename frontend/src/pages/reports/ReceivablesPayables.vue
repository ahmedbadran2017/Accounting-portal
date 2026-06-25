<template>
  <div class="space-y-3.5">
    <div v-if="loading"><TableLoading :rows="8" /></div>
    <template v-else>
      <!-- Headline -->
      <div class="grid sm:grid-cols-2 gap-3.5">
        <div class="bg-white rounded-card border border-line shadow-card p-5">
          <div class="flex items-center gap-2"><span class="w-7 h-7 rounded-[9px] grid place-items-center" style="background:#eff6ff"><Icon name="trend" :size="15" color="#0369a1" /></span><span class="text-[12px] font-bold text-ink-3">{{ L("Receivables (AR)", "الذمم المدينة", "Créances") }}</span></div>
          <div class="text-[26px] font-extrabold tnum mt-2" style="color:#0369a1">{{ money(ar.carrier_float + ar.si_outstanding) }}<span class="text-[12px] text-ink-muted ms-1">MAD</span></div>
          <div class="text-[11px] text-ink-muted mt-1">{{ L("operational — what's really owed to us", "تشغيلي — المستحق الحقيقي لنا", "opérationnel") }}</div>
          <div class="mt-2 inline-flex items-center gap-1.5 text-[10.5px] font-bold px-2 py-0.5 rounded-full" style="background:#fef2f2;color:#be123c">
            <Icon name="alert" :size="11" />{{ L("GL broken — needs reconciliation", "الـ GL مكسور — يحتاج مطابقة", "GL à réconcilier") }}
          </div>
        </div>
        <div class="bg-white rounded-card border border-line shadow-card p-5">
          <div class="flex items-center gap-2"><span class="w-7 h-7 rounded-[9px] grid place-items-center" style="background:#fef2f2"><Icon name="wallet" :size="15" color="#be123c" /></span><span class="text-[12px] font-bold text-ink-3">{{ L("Payables (AP)", "الذمم الدائنة", "Dettes") }}</span></div>
          <div class="text-[26px] font-extrabold tnum mt-2" style="color:#be123c">{{ money(ap.net_invoice) }}<span class="text-[12px] text-ink-muted ms-1">MAD</span></div>
          <div class="text-[11px] text-ink-muted mt-1">{{ L("net of supplier advances", "صافي بعد المقدّمات", "net des avances") }}</div>
          <div class="mt-2 inline-flex items-center gap-1.5 text-[10.5px] font-bold px-2 py-0.5 rounded-full" :style="ap.reconciled ? 'background:#ecfdf5;color:#047857' : 'background:#fffbeb;color:#b45309'">
            <Icon :name="ap.reconciled ? 'check' : 'alert'" :size="11" />{{ ap.reconciled ? L("ties to GL", "مطابق للـ GL", "concorde") : L("small gap to GL", "فرق بسيط مع الـ GL", "léger écart") }}
          </div>
        </div>
      </div>

      <!-- AR reconciliation -->
      <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
        <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><Icon name="trend" :size="14" color="#0369a1" /><span class="text-[12px] font-bold">{{ L("Receivables — operational vs book", "الذمم المدينة — تشغيلي مقابل دفتري", "Créances — opérationnel vs comptable") }}</span></div>
        <table class="w-full text-[12.5px]">
          <tbody>
            <tr class="border-b border-line-hair"><td class="px-4 py-2.5">{{ L("Carrier float (delivered · not collected)", "عهدة الناقل (مُسلّم · غير محصّل)", "En cours transporteur") }}</td><td class="px-4 py-2.5 text-end tnum font-semibold">{{ fmt(ar.carrier_float) }}</td></tr>
            <tr class="border-b border-line-hair"><td class="px-4 py-2.5">{{ L("Invoiced & unpaid", "متفوتر وغير مدفوع", "Facturé impayé") }}</td><td class="px-4 py-2.5 text-end tnum font-semibold">{{ fmt(ar.si_outstanding) }}</td></tr>
            <tr class="border-b border-line-hair bg-accent/5"><td class="px-4 py-2.5 font-bold">{{ L("= Operational receivable", "= المستحق التشغيلي", "= Créance opérationnelle") }}</td><td class="px-4 py-2.5 text-end tnum font-extrabold">{{ fmt(ar.carrier_float + ar.si_outstanding) }}</td></tr>
            <tr class="border-b border-line-hair"><td class="px-4 py-2.5 text-ink-3">{{ L("Book balance — GL Debtors", "الرصيد الدفتري — مدينون", "Solde GL Débiteurs") }}</td><td class="px-4 py-2.5 text-end tnum font-bold" :class="ar.gl_debtors < 0 ? 'text-sale' : ''">{{ fmt(ar.gl_debtors) }}</td></tr>
          </tbody>
        </table>
        <div class="px-4 py-2.5 bg-sale/5 border-t border-line-hair text-[11px] text-sale flex items-start gap-1.5">
          <Icon name="alert" :size="13" class="mt-0.5 flex-shrink-0" />
          <span>{{ L("GL Debtors is a credit balance (wrong sign) — COD collections aren't applied to invoices. Run the Cathedis reconciliation to clear it.", "مدينون برصيد دائن (إشارة عكسية) — تحصيلات الـ COD غير مطبّقة على الفواتير. شغّل مطابقة كاتدييس.", "Débiteurs créditeur — encaissements COD non affectés.") }}</span>
        </div>
        <AgingBar :a="r.ar_aging" :L="L" :fmt="fmt" />
      </div>

      <!-- AP reconciliation -->
      <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
        <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><Icon name="wallet" :size="14" color="#be123c" /><span class="text-[12px] font-bold">{{ L("Payables — operational vs book", "الذمم الدائنة — تشغيلي مقابل دفتري", "Dettes — opérationnel vs comptable") }}</span></div>
        <table class="w-full text-[12.5px]">
          <tbody>
            <tr class="border-b border-line-hair"><td class="px-4 py-2.5">{{ L("Unpaid bills (To pay + Billed)", "فواتير غير مدفوعة", "Factures impayées") }}</td><td class="px-4 py-2.5 text-end tnum font-semibold">{{ fmt(ap.pi_unpaid) }}</td></tr>
            <tr class="border-b border-line-hair"><td class="px-4 py-2.5">{{ L("− Supplier advances (prepaid)", "− دفعات مقدّمة للمورّدين", "− Avances fournisseurs") }}</td><td class="px-4 py-2.5 text-end tnum font-semibold text-accent-dark">({{ fmt(ap.advances) }})</td></tr>
            <tr class="border-b border-line-hair bg-accent/5"><td class="px-4 py-2.5 font-bold">{{ L("= Net bills owed", "= صافي المستحق", "= Net dû") }}</td><td class="px-4 py-2.5 text-end tnum font-extrabold">{{ fmt(ap.net_invoice) }}</td></tr>
            <tr class="border-b border-line-hair"><td class="px-4 py-2.5 text-ink-3">{{ L("Book balance — GL Creditors", "الرصيد الدفتري — دائنون", "Solde GL Créditeurs") }}</td><td class="px-4 py-2.5 text-end tnum font-bold">{{ fmt(ap.gl_creditors) }}</td></tr>
            <tr><td class="px-4 py-2.5 text-ink-muted text-[11.5px]">{{ L("Gap to GL", "الفرق مع الـ GL", "Écart") }}</td><td class="px-4 py-2.5 text-end tnum text-[11.5px]" :class="Math.abs(ap.invoice_gap) > 1000 ? 'text-sale font-semibold' : 'text-ink-muted'">{{ fmt(ap.invoice_gap) }}</td></tr>
          </tbody>
        </table>
        <!-- GRNI -->
        <div class="px-4 py-2.5 bg-app-warm/30 border-t border-line-hair flex items-center justify-between flex-wrap gap-2">
          <span class="text-[11.5px] text-ink-2"><b>{{ L("GRNI", "GRNI", "GRNI") }}</b> · {{ L("received, not billed (accrued liability)", "مستلم بلا فاتورة (التزام مستحق)", "reçu non facturé") }}</span>
          <span class="text-[11.5px] tnum">{{ L("op", "تشغيلي", "op") }} <b>{{ fmt(ap.grni) }}</b> · {{ L("GL", "دفتري", "GL") }} {{ fmt(ap.gl_grni) }} · {{ L("gap", "فرق", "écart") }} <span :class="Math.abs(ap.grni_gap) > 1000 ? 'text-sale font-semibold' : ''">{{ fmt(ap.grni_gap) }}</span></span>
        </div>
        <AgingBar :a="r.ap_aging" :L="L" :fmt="fmt" />
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useI18n } from "vue-i18n";
import { h } from "vue";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";

const { locale } = useI18n();
const { entityId } = useUi();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US");
const money = (n) => { n = Number(n) || 0; const a = Math.abs(n); return a >= 1e6 ? (n / 1e6).toFixed(2) + "M" : a >= 1e3 ? Math.round(n / 1e3) + "K" : Math.round(n).toLocaleString(); };

const r = ref({ ar: {}, ap: {}, ar_aging: {}, ap_aging: {} });
const loading = ref(true);
const ar = computed(() => r.value.ar || {});
const ap = computed(() => r.value.ap || {});

const SAMPLE = {
  ar: { carrier_float: 981370, si_outstanding: 0, gl_debtors: -2851136, wrong_sign: true },
  ap: { pi_unpaid: 7560155, advances: 3775135, net_invoice: 3785020, gl_creditors: 4046355, invoice_gap: -261335, grni: 4376059, gl_grni: 3136293, grni_gap: 1239766, reconciled: false },
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

// Inline aging strip component (cur / 1-30 / 31-60 / 61-90 / 90+).
const AgingBar = {
  props: ["a", "L", "fmt"],
  setup(p) {
    const segs = [
      { k: "cur", c: "#047857", l: () => p.L("Current", "حالي", "Courant") },
      { k: "d1_30", c: "#65a30d", l: () => p.L("1-30", "1-30", "1-30") },
      { k: "d31_60", c: "#d97706", l: () => p.L("31-60", "31-60", "31-60") },
      { k: "d61_90", c: "#ea580c", l: () => p.L("61-90", "61-90", "61-90") },
      { k: "d90p", c: "#be123c", l: () => p.L("90+", "90+", "90+") },
    ];
    return () => {
      const a = p.a || {}; const total = Math.max(1, Number(a.total) || 0);
      return h("div", { class: "px-4 py-3 border-t border-line-hair" }, [
        h("div", { class: "flex h-2.5 rounded-full overflow-hidden bg-app-warm" },
          segs.map((s) => h("div", { style: { width: ((Number(a[s.k]) || 0) / total * 100) + "%", background: s.c } }))),
        h("div", { class: "flex flex-wrap gap-x-4 gap-y-1 mt-2" },
          segs.map((s) => h("span", { class: "text-[10.5px] text-ink-3 inline-flex items-center gap-1" }, [
            h("span", { class: "w-2 h-2 rounded-full inline-block", style: { background: s.c } }),
            s.l() + " ", h("b", { class: "tnum" }, p.fmt(a[s.k] || 0)),
          ]))),
      ]);
    };
  },
};
</script>
