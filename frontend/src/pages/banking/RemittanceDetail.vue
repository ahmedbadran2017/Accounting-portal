<template>
  <div class="space-y-3.5">
    <button class="inline-flex items-center gap-1.5 text-[12px] font-semibold text-ink-3 hover:text-ink" @click="back">
      <Icon name="arrow" :size="14" class="rtl:rotate-180 rotate-180" />{{ L("Back to remittances","العودة للدفعات","Retour aux lots") }}
    </button>
    <div v-if="loading" class="bg-white rounded-card border border-line shadow-card"><TableLoading :rows="4" /></div>
    <template v-else-if="d">
      <!-- Reconciliation header -->
      <div class="bg-white rounded-card border border-line shadow-card p-5">
        <div class="flex items-start gap-3 flex-wrap">
          <span class="w-11 h-11 rounded-[12px] grid place-items-center flex-shrink-0" style="background:#fff4e0"><Icon name="truck" :size="20" color="#b45309" /></span>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="text-[15px] font-bold font-mono">{{ d.ref }}</span>
              <span class="text-[10px] font-bold px-2 py-0.5 rounded-full" :style="stBadge(d.status)">{{ stLabel(d.status) }}</span>
            </div>
            <div class="text-[11.5px] text-ink-muted mt-0.5">{{ d.carrier }} · {{ d.n_orders }} {{ L("orders","طلب","cmd") }} · {{ d.n_deposits }} {{ L("deposits","إيداع","dépôts") }}</div>
          </div>
        </div>
        <div class="grid grid-cols-3 gap-2 mt-4">
          <div class="rounded-[10px] px-3 py-2.5" style="background:#fafaf9;border:1px solid #f0efed">
            <div class="text-[9.5px] text-ink-muted font-bold uppercase tracking-wide">{{ L("Expected","المتوقَّع","Attendu") }}</div>
            <div class="text-[16px] font-bold tnum">{{ fmt(d.expected) }}</div>
          </div>
          <div class="rounded-[10px] px-3 py-2.5" style="background:#fafaf9;border:1px solid #f0efed">
            <div class="text-[9.5px] text-ink-muted font-bold uppercase tracking-wide">{{ L("Collected","المُحصَّل","Collecté") }}</div>
            <div class="text-[16px] font-bold tnum">{{ fmt(d.collected) }}</div>
          </div>
          <div class="rounded-[10px] px-3 py-2.5" :style="d.variance ? 'background:#fff5f5;border:1px solid #fecaca' : 'background:#f0fdf4;border:1px solid #bbf7d0'">
            <div class="text-[9.5px] text-ink-muted font-bold uppercase tracking-wide">{{ L("Variance","الفرق","Écart") }}</div>
            <div class="text-[16px] font-bold tnum" :class="d.variance < 0 ? 'text-sale' : d.variance > 0 ? 'text-amber-700' : 'text-success-dark'">{{ d.variance > 0 ? "+" : "" }}{{ fmt(d.variance) }}</div>
          </div>
        </div>
      </div>

      <div class="grid lg:grid-cols-2 gap-3.5">
        <!-- Orders collected -->
        <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
          <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><Icon name="cart" :size="14" color="#0b5c4f" /><span class="text-[12px] font-bold">{{ L("Orders","الطلبات","Commandes") }}</span><span class="text-[10px] text-ink-muted">{{ d.n_orders }}</span></div>
          <div class="overflow-y-auto max-h-[360px]">
            <table class="w-full text-[12px]">
              <tbody>
                <tr v-for="(o, i) in d.orders" :key="i" class="border-t border-line-hair hover:bg-app-warm/50 cursor-pointer" @click="goOrder(o.name)">
                  <td class="px-4 py-2 font-mono text-[11px]">{{ o.name }}<div class="text-[10px] text-ink-muted font-sans truncate max-w-[150px]">{{ o.customer }}</div></td>
                  <td class="px-4 py-2 text-end tnum font-semibold">{{ fmt(o.value) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        <!-- Deposits -->
        <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
          <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><Icon name="coins" :size="14" color="#047857" /><span class="text-[12px] font-bold">{{ L("Deposits","الإيداعات","Dépôts") }}</span><span class="text-[10px] text-ink-muted">{{ d.n_deposits }}</span></div>
          <div class="overflow-y-auto max-h-[360px]">
            <table class="w-full text-[12px]">
              <tbody>
                <tr v-for="(p, i) in d.deposits" :key="i" class="border-t border-line-hair hover:bg-app-warm/50 cursor-pointer" @click="goReceipt(p.name)">
                  <td class="px-4 py-2 font-mono text-[11px]">{{ p.name }}<div class="text-[10px] text-ink-muted font-sans">{{ p.date }} · {{ p.method }}</div></td>
                  <td class="px-4 py-2 text-end tnum font-semibold">{{ fmt(p.amount) }}</td>
                </tr>
                <tr v-if="!d.deposits.length"><td colspan="2" class="px-4 py-6 text-center text-ink-muted">{{ L("No deposits matched.","لا إيداعات.","Aucun dépôt.") }}</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";

const route = useRoute();
const router = useRouter();
const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US");

const d = ref(null);
const loading = ref(true);
function back() { router.push("/accounting/banking/remittance"); }
function goOrder(n) { router.push({ path: "/accounting/sales/orders", query: { id: n } }); }
function goReceipt(n) { router.push({ path: "/accounting/sales/payments", query: { id: n } }); }
async function load() {
  const id = route.query.id;
  if (!id) { loading.value = false; return; }
  loading.value = true; d.value = null;
  try { d.value = await api.call("accounting_portal.api.cod.get_remittance", { ref: id, company: currentCompany() }); }
  catch { d.value = null; }
  finally { loading.value = false; }
  if (!d.value) router.replace({ path: "/accounting/banking/remittance", query: {} });
}
watch(() => route.query.id, load, { immediate: true });

const ST = {
  matched: { en: "Matched", ar: "مطابقة", fr: "Rapproché", bg: "#ecfdf5", fg: "#047857" },
  short: { en: "Short", ar: "نقص", fr: "Manque", bg: "#fef2f2", fg: "#b91c1c" },
  over: { en: "Over", ar: "زيادة", fr: "Excédent", bg: "#fffbeb", fg: "#b45309" },
};
function stLabel(s) { const x = ST[s] || ST.matched; return locale.value === "ar" ? x.ar : locale.value === "fr" ? x.fr : x.en; }
function stBadge(s) { const x = ST[s] || ST.matched; return `background:${x.bg};color:${x.fg}`; }
</script>
