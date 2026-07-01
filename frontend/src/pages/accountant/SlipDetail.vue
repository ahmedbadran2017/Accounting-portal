<template>
  <div class="space-y-3.5">
    <div class="flex items-center gap-2">
      <button type="button" class="inline-flex items-center gap-1.5 h-8 px-3 rounded-chip border border-line-2 bg-white text-[12px] font-semibold text-ink-2 hover:bg-app-warm" @click="back">
        <Icon name="arrow" :size="13" class="rotate-180" />{{ L("Back","رجوع","Retour") }}
      </button>
      <button v-if="d.slip" type="button" class="ms-auto inline-flex items-center gap-1.5 h-8 px-3.5 rounded-chip text-[12px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand" @click="printPayslip">
        <Icon name="doc" :size="13" />{{ L("Print / PDF","طباعة / PDF","Imprimer") }}
      </button>
    </div>
    <TableLoading v-if="loading" :rows="4" />
    <div v-else-if="!d.slip" class="bg-white rounded-card border border-line shadow-card px-4 py-14 text-center text-[12px] text-ink-muted">{{ L("Slip not found.","المسير غير موجود.","Introuvable.") }}</div>
    <template v-else>
      <div class="bg-white rounded-card border border-line shadow-card px-4 py-3.5 flex items-center gap-3 flex-wrap">
        <div>
          <div class="text-[14px] font-extrabold">{{ s.employee_name }}</div>
          <div class="text-[11px] text-ink-muted font-mono">{{ s.name }} · {{ s.start_date }} → {{ s.end_date }}</div>
        </div>
        <div class="ms-auto text-end">
          <div class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Net pay","الصافي","Net") }}</div>
          <div class="text-[22px] font-extrabold tnum" style="color:#0f766e">{{ money(s.net_pay) }} <span class="text-[12px] text-ink-muted font-bold">{{ ccy }}</span></div>
        </div>
      </div>
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
          <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><span class="w-2.5 h-2.5 rounded-sm bg-teal-600"></span><span class="text-[12px] font-bold">{{ L("Earnings","الاستحقاقات","Gains") }}</span><span class="ms-auto tnum font-bold">{{ money(s.gross_pay) }}</span></div>
          <table class="w-full text-[12px]"><tbody>
            <tr v-for="(r,i) in d.earnings" :key="i" class="border-t border-line-hair first:border-t-0"><td class="px-4 py-2">{{ r.component }}</td><td class="px-4 py-2 text-end tnum font-semibold">{{ money(r.amount) }}</td></tr>
          </tbody></table>
        </div>
        <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
          <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><span class="w-2.5 h-2.5 rounded-sm bg-rose-600"></span><span class="text-[12px] font-bold">{{ L("Deductions","الخصومات","Retenues") }}</span><span class="ms-auto tnum font-bold text-rose-600">−{{ money(s.total_deduction) }}</span></div>
          <table class="w-full text-[12px]"><tbody>
            <tr v-for="(r,i) in d.deductions" :key="i" class="border-t border-line-hair first:border-t-0"><td class="px-4 py-2">{{ r.component }}</td><td class="px-4 py-2 text-end tnum font-semibold text-rose-600">−{{ money(r.amount) }}</td></tr>
            <tr v-if="!d.deductions.length"><td colspan="2" class="px-4 py-4 text-center text-ink-muted">{{ L("None","لا شيء","Aucune") }}</td></tr>
          </tbody></table>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";

const { locale } = useI18n();
const { entityId } = useUi();
const route = useRoute();
const router = useRouter();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const money = (n) => Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const d = ref({ earnings: [], deductions: [] });
const loading = ref(true);
const slip = computed(() => route.query.slip);
const s = computed(() => d.value.slip || {});
const ccy = computed(() => d.value.currency || "MAD");

async function load() {
  if (!slip.value) return;
  loading.value = true;
  try { d.value = await api.call("accounting_portal.api.payroll.salary_slip_detail", { company: currentCompany(), slip: slip.value }) || { earnings: [], deductions: [] }; }
  catch { d.value = { earnings: [], deductions: [] }; }
  finally { loading.value = false; }
}
load();
watch(slip, load);
watch(entityId, () => router.push({ path: "/accounting/payroll" }));
function back() { router.back(); }

// Render a clean payslip in a new window and open the print dialog (→ Save as PDF).
function printPayslip() {
  const sl = s.value, cur = ccy.value, comp = d.value.company || "";
  const rows = (arr, sign) => arr.map((r) => `<tr><td>${esc(r.component)}</td><td class="n">${sign}${money(r.amount)}</td></tr>`).join("");
  const ar = locale.value === "ar";
  const t = (en, arT) => (ar ? arT : en);
  const html = `<!doctype html><html dir="${ar ? "rtl" : "ltr"}"><head><meta charset="utf-8"><title>Payslip ${esc(sl.name)}</title>
<style>
  *{box-sizing:border-box} body{font-family:${ar ? "'Alexandria',Arial" : "'Inter',Arial"},sans-serif;color:#1c1917;margin:0;padding:32px;font-size:13px}
  .hd{display:flex;justify-content:space-between;align-items:flex-start;border-bottom:2px solid #0f766e;padding-bottom:12px;margin-bottom:16px}
  .co{font-size:18px;font-weight:800;color:#0f766e} .ttl{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#78716c;margin-top:2px}
  .meta{display:grid;grid-template-columns:1fr 1fr;gap:6px 24px;margin:14px 0 18px;font-size:12px}
  .meta b{color:#57534e;font-weight:600} .cols{display:flex;gap:20px} .box{flex:1;border:1px solid #e7e5e4;border-radius:10px;overflow:hidden}
  .box h4{margin:0;padding:8px 12px;background:#fafaf9;font-size:12px;border-bottom:1px solid #e7e5e4;display:flex;justify-content:space-between}
  table{width:100%;border-collapse:collapse} td{padding:6px 12px;border-top:1px solid #f0eee9;font-size:12px} .n{text-align:${ar ? "left" : "right"};font-variant-numeric:tabular-nums;font-weight:600}
  .net{margin-top:18px;background:#ecfdf5;border:1px solid #a7f3d0;border-radius:10px;padding:14px 16px;display:flex;justify-content:space-between;align-items:center}
  .net .lbl{font-size:12px;text-transform:uppercase;letter-spacing:.1em;color:#047857;font-weight:700} .net .v{font-size:22px;font-weight:800;color:#0f766e;font-variant-numeric:tabular-nums}
  .ft{margin-top:26px;font-size:10.5px;color:#a8a29e;text-align:center}
  @media print{body{padding:0}}
</style></head><body>
  <div class="hd"><div><div class="co">${esc(comp)}</div><div class="ttl">${t("Payslip", "قسيمة راتب")}</div></div>
    <div style="text-align:${ar ? "left" : "right"};font-size:12px"><div><b>${esc(sl.name)}</b></div><div>${esc(sl.start_date)} → ${esc(sl.end_date)}</div></div></div>
  <div class="meta">
    <div><b>${t("Employee", "الموظف")}:</b> ${esc(sl.employee_name)} (${esc(sl.employee)})</div>
    <div><b>${t("Designation", "المسمى")}:</b> ${esc(sl.designation || "—")}</div>
    <div><b>${t("Department", "القسم")}:</b> ${esc(sl.department || "—")}</div>
    <div><b>${t("Bank", "البنك")}:</b> ${esc(sl.bank_name || "—")} ${esc(sl.bank_account_no || "")}</div>
  </div>
  <div class="cols">
    <div class="box"><h4><span>${t("Earnings", "الاستحقاقات")}</span><span class="n">${money(sl.gross_pay)}</span></h4><table>${rows(d.earnings, "")}</table></div>
    <div class="box"><h4><span>${t("Deductions", "الخصومات")}</span><span class="n">−${money(sl.total_deduction)}</span></h4><table>${d.deductions.length ? rows(d.deductions, "−") : `<tr><td colspan=2 style="text-align:center;color:#a8a29e">${t("None", "لا شيء")}</td></tr>`}</table></div>
  </div>
  <div class="net"><span class="lbl">${t("Net pay", "صافي الراتب")}</span><span class="v">${money(sl.net_pay)} ${esc(cur)}</span></div>
  <div class="ft">${t("Generated from Justyol Accounting Portal", "صادر من بوابة حسابات Justyol")} · ${new Date().toLocaleDateString()}</div>
</body></html>`;
  const w = window.open("", "_blank");
  if (!w) return;
  w.document.write(html); w.document.close();
  w.focus(); setTimeout(() => w.print(), 350);
}
function esc(x) { return String(x == null ? "" : x).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
</script>
