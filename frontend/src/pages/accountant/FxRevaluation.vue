<template>
  <div class="space-y-3">
    <div class="flex items-center gap-2 flex-wrap">
      <span class="text-[13px] font-bold">{{ L("FX revaluation","إعادة تقييم العملات","Réévaluation FX") }}</span>
      <span v-if="isLive !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="isLive ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ isLive ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échant.") }}</span>
      <span class="text-[11px] text-ink-muted">{{ L("unrealized gain/loss on foreign-currency balances at the latest rate","ربح/خسارة غير محققة على الأرصدة بالعملات الأجنبية بآخر سعر","plus/moins-value latente") }}</span>
    </div>

    <div class="grid grid-cols-2 lg:grid-cols-3 gap-3">
      <div class="bg-white border border-line rounded-[14px] p-4 shadow-card">
        <div class="text-[10.5px] font-semibold text-ink-3">{{ L("Net unrealized","صافي غير المحقق","Net latent") }}</div>
        <div class="text-[20px] font-bold tnum mt-1.5" :style="{ color: (d.summary.total_unrealized || 0) < 0 ? '#be123c' : '#047857' }">{{ money(d.summary.total_unrealized) }} {{ d.currency }}</div>
      </div>
      <div class="bg-white border border-line rounded-[14px] p-4 shadow-card">
        <div class="text-[10.5px] font-semibold text-ink-3">{{ L("Accounts","حسابات","Comptes") }}</div>
        <div class="text-[20px] font-bold tnum mt-1.5">{{ d.summary.count || 0 }}</div>
      </div>
      <div class="bg-white border border-line rounded-[14px] p-4 shadow-card" :style="d.summary.missing_rate ? 'border-color:#fde68a;background:#fffbeb' : ''">
        <div class="text-[10.5px] font-semibold text-ink-3">{{ L("Missing a rate","بدون سعر","Sans taux") }}</div>
        <div class="text-[20px] font-bold tnum mt-1.5" :style="d.summary.missing_rate ? 'color:#b45309' : ''">{{ d.summary.missing_rate || 0 }}</div>
      </div>
    </div>

    <div v-if="d.summary.missing_rate" class="rounded-[12px] border border-amber-200 bg-amber-50 px-4 py-2.5 flex items-center gap-2.5">
      <Icon name="alert" :size="15" color="#b45309" />
      <span class="text-[11.5px] text-ink-2">{{ d.summary.missing_rate }} {{ L("account(s) have no exchange rate — set it in","حساب بدون سعر صرف — حدّده في","compte(s) sans taux — définissez-le dans") }} <button class="font-bold text-accent-dark hover:underline" @click="goRates">{{ L("Settings · Currencies","الإعدادات · العملات","Param. · Devises") }}</button>{{ L(" to include them.",".",".") }}</span>
    </div>

    <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
      <TableLoading v-if="loading" :rows="8" />
      <div v-else class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead><tr style="background:#fafaf9">
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Account","الحساب","Compte") }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Balance","الرصيد","Solde") }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Book value","القيمة الدفترية","Valeur compt.") }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Rate","السعر","Taux") }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Revalued","المُعاد تقييمه","Réévalué") }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Unrealized","غير محقق","Latent") }}</th>
          </tr></thead>
          <tbody>
            <tr v-for="(r, i) in d.rows" :key="i" class="border-t border-line-hair hover:bg-app-warm/40 cursor-pointer" @click="drill(r.account)" :class="r.rate === null ? 'bg-amber-50/40' : ''">
              <td class="px-4 py-2.5 font-mono text-[11px] truncate max-w-[240px] hover:text-accent-dark">{{ r.account }}</td>
              <td class="px-4 py-2.5 text-end tnum">{{ money(r.bal_acct) }} <span class="text-[10px] text-ink-muted">{{ r.ccy }}</span></td>
              <td class="px-4 py-2.5 text-end tnum text-ink-3">{{ money(r.bal_base) }}</td>
              <td class="px-4 py-2.5 text-end tnum">{{ r.rate === null ? "—" : r.rate }}</td>
              <td class="px-4 py-2.5 text-end tnum">{{ r.revalued === null ? "—" : money(r.revalued) }}</td>
              <td class="px-4 py-2.5 text-end tnum font-bold" :style="{ color: r.unrealized === null ? '#b45309' : (r.unrealized < 0 ? '#be123c' : '#047857') }">{{ r.unrealized === null ? L("set rate","حدّد السعر","taux") : money(r.unrealized) }}</td>
            </tr>
            <tr v-if="!d.rows.length"><td colspan="6" class="px-4 py-10 text-center text-ink-muted text-[12px]">{{ L("No foreign-currency balances.","لا أرصدة بعملات أجنبية.","Aucun solde en devise.") }}</td></tr>
          </tbody>
        </table>
      </div>
    </div>
    <p class="text-[10.5px] text-ink-muted px-1">{{ L("Diagnostic preview. Post the revaluation entry in ERPNext once all rates are set.","معاينة تشخيصية. رحّل قيد إعادة التقييم في ERPNext بعد ضبط كل الأسعار.","Aperçu. Passez l'écriture dans ERPNext une fois les taux définis.") }}</p>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";

const { locale } = useI18n();
const { entityId } = useUi();
const router = useRouter();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const money = (n) => { if (n === null || n === undefined) return "—"; n = Number(n) || 0; const a = Math.abs(n); return (n < 0 ? "−" : "") + (a >= 1e6 ? (a / 1e6).toFixed(2) + "M" : a >= 1e3 ? (a / 1e3).toFixed(1) + "K" : Math.round(a).toLocaleString()); };

const d = ref({ rows: [], summary: {}, currency: "MAD" });
const isLive = ref(null);
const loading = ref(true);

async function load() {
  loading.value = true;
  try { d.value = await api.call("accounting_portal.api.accountant.fx_revaluation", { company: currentCompany() }); isLive.value = true; }
  catch { d.value = { rows: [], summary: {}, currency: "MAD" }; isLive.value = false; }
  finally { loading.value = false; }
}
onMounted(load);
watch(entityId, load);

function drill(account) { if (account) router.push({ path: "/accounting/accountant/gl", query: { account } }); }
function goRates() { router.push("/accounting/settings/currencies"); }
</script>
