<template>
  <div class="space-y-3.5">
    <!-- KPI cards -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <StatCard :label="L('Orders','الطلبات','Commandes')" :value="(d.totals.orders||0).toLocaleString()" :sub="L('placed · FY 2026','مُسجّلة · 2026','passées · 2026')" icon="cart" color="#1c1917" glow="#a8a29e" tint="#fafaf9" />
      <StatCard :label="L('Invoiced (net)','المفوتر (صافي)','Facturé (HT)')" :value="money(d.totals.invoiced)" sub="MAD" icon="receipt" color="#0f766e" glow="#5dcaa5" tint="#e1f5ee" valueColor="#0f766e" />
      <StatCard :label="L('Collected','المحصّل','Encaissé')" :value="money(d.totals.collected)" :sub="d.totals.collection_rate + '% ' + L('of delivered','من المُسلّم','du livré')" icon="coins" color="#7c3aed" glow="#a78bfa" tint="#f5f3ff" valueColor="#7c3aed" />
      <StatCard :label="L('Outstanding','غير محصّل','En souffrance')" :value="money(d.totals.outstanding)" :sub="L('delivered − collected','مُسلّم − محصّل','livré − encaissé')" icon="alert" color="#be123c" glow="#f87171" tint="#fef2f2" :valueColor="d.totals.outstanding ? '#be123c' : undefined" />
    </div>

    <div class="bg-white rounded-card border border-line overflow-hidden shadow-card">
      <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
        <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#e1f5ee"><Icon name="chart" :size="14" color="#0b5c4f" /></span>
        <span class="text-[13px] font-bold">{{ L("Sales & collections by order month","المبيعات والتحصيلات بشهر الطلب","Ventes & encaissements par mois de commande") }}</span>
        <span v-if="isLive !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="isLive ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ isLive ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échant.") }}</span>
        <span class="hidden lg:inline text-[11px] text-ink-muted">{{ L("revenue attributed to when the order was placed (matches ad spend)","الإيراد منسوب لوقت الطلب (يطابق الإعلانات)","produit attribué à la date de commande") }}</span>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead>
            <tr style="background:#fafaf9">
              <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Order month","شهر الطلب","Mois") }}</th>
              <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Orders","الطلبات","Cmds") }}</th>
              <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Invoiced","المفوتر","Facturé") }}</th>
              <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Delivered","المُسلّم","Livré") }}</th>
              <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Collected","المحصّل","Encaissé") }}</th>
              <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted w-[140px]">{{ L("Collection","التحصيل","Encaiss.") }}</th>
              <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Outstanding","غير محصّل","Souffrance") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="m in d.months" :key="m.month" class="border-t border-line-hair hover:bg-app-warm/60">
              <td class="px-4 py-2.5 font-semibold whitespace-nowrap">{{ monthLabel(m.month) }}</td>
              <td class="px-4 py-2.5 text-end tnum text-ink-2">{{ m.orders.toLocaleString() }}</td>
              <td class="px-4 py-2.5 text-end tnum font-semibold">{{ fmt(m.invoiced) }}</td>
              <td class="px-4 py-2.5 text-end tnum text-ink-3">{{ fmt(m.delivered) }}</td>
              <td class="px-4 py-2.5 text-end tnum font-bold" style="color:#7c3aed">{{ fmt(m.collected) }}</td>
              <td class="px-4 py-2.5">
                <div class="flex items-center gap-2">
                  <div class="flex-1 h-1.5 rounded-full bg-app-warm overflow-hidden min-w-[60px]">
                    <div class="h-full rounded-full" :style="{ width: Math.min(100, m.collection_rate) + '%', background: rateColor(m.collection_rate) }"></div>
                  </div>
                  <span class="text-[10.5px] font-bold tnum w-9 text-end" :style="{ color: rateColor(m.collection_rate) }">{{ Math.round(m.collection_rate) }}%</span>
                </div>
              </td>
              <td class="px-4 py-2.5 text-end tnum">
                <button v-if="m.outstanding > 0" @click="openOutstanding(m)" class="text-sale font-semibold hover:underline inline-flex items-center gap-1" :title="L('Track these orders — delivered, not yet collected','تتبّع هذه الطلبات — مُسلّمة وغير محصّلة','Suivre ces commandes')">{{ fmt(m.outstanding) }}<Icon name="arrow" :size="11" class="rtl:rotate-180 opacity-50" /></button>
                <span v-else class="text-ink-muted">{{ fmt(m.outstanding) }}</span>
              </td>
            </tr>
          </tbody>
          <tfoot>
            <tr class="border-t-2 border-line-2 font-bold" style="background:#fafaf9">
              <td class="px-4 py-2.5">{{ L("Total","الإجمالي","Total") }}</td>
              <td class="px-4 py-2.5 text-end tnum">{{ (d.totals.orders||0).toLocaleString() }}</td>
              <td class="px-4 py-2.5 text-end tnum">{{ fmt(d.totals.invoiced) }}</td>
              <td class="px-4 py-2.5 text-end tnum text-ink-3">{{ fmt(d.totals.delivered) }}</td>
              <td class="px-4 py-2.5 text-end tnum" style="color:#7c3aed">{{ fmt(d.totals.collected) }}</td>
              <td class="px-4 py-2.5 text-[11px] tnum">{{ d.totals.collection_rate }}%</td>
              <td class="px-4 py-2.5 text-end tnum text-sale">{{ fmt(d.totals.outstanding) }}</td>
            </tr>
          </tfoot>
        </table>
      </div>
      <TableLoading v-if="loading" />
      <div v-else-if="!d.months.length" class="py-12 text-center text-[12px] text-ink-muted">{{ L("No data.","لا توجد بيانات.","Aucune donnée.") }}</div>

      <div class="px-4 py-2.5 border-t border-line text-[11px] text-ink-3 flex items-start gap-1.5">
        <Icon name="spark" :size="13" color="#7c3aed" class="flex-shrink-0 mt-px" />
        {{ L("Collected counts only reconciled Cathedis remittances — the Outstanding column is the cash delivered but not yet reconciled.",
              "المحصّل بيعدّ التحويلات المطابَقة فقط — وعمود غير محصّل هو الكاش المُسلّم اللي لسه ماتطابقش.",
              "Encaissé = remises Cathedis rapprochées uniquement.") }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { fmtAmount } from "@/utils/helpers";
import { ref, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import StatCard from "@/components/StatCard.vue";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";

const { locale } = useI18n();
const { entityId } = useUi();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US");
const money = (n) => fmtAmount(n);
const MON = { "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr", "05": "May", "06": "Jun", "07": "Jul", "08": "Aug", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec" };
const monthLabel = (m) => { const [y, mm] = String(m).split("-"); return (MON[mm] || mm) + " " + y; };

// Outstanding = delivered cash not yet collected/reconciled for orders PLACED that
// month. Drill into the COD "delivered" bucket (delivered, not collected) scoped to
// the month's order dates — exactly those orders, so the team can track them.
const router = useRouter();
function openOutstanding(m) {
  const [y, mo] = String(m.month).split("-").map(Number);
  const pad = (n) => String(n).padStart(2, "0");
  const from = `${y}-${pad(mo)}-01`;
  const to = `${y}-${pad(mo)}-${pad(new Date(y, mo, 0).getDate())}`;
  router.push({ path: "/accounting/sales/delivered", query: { from, to } });
}
function rateColor(r) { return r >= 70 ? "#047857" : r >= 30 ? "#b45309" : "#be123c"; }

const SAMPLE = { months: [
  { month: "2026-01", orders: 11329, invoiced: 1441145, delivered: 1100000, collected: 475396, outstanding: 624604, collection_rate: 43.2 },
  { month: "2026-04", orders: 10440, invoiced: 1431011, delivered: 980000, collected: 130173, outstanding: 849827, collection_rate: 13.3 },
  { month: "2026-05", orders: 12325, invoiced: 1391779, delivered: 760000, collected: 20504, outstanding: 739496, collection_rate: 2.7 },
], totals: { orders: 34094, invoiced: 4263935, delivered: 2840000, collected: 626073, outstanding: 2213927, collection_rate: 22.0 } };

const d = ref({ months: [], totals: {} });
const isLive = ref(null);
const loading = ref(true);

async function load() {
  loading.value = true;
  try {
    const r = await api.call("accounting_portal.api.reports.sales_collections_cohort", { company: currentCompany() });
    d.value = (r && r.months) ? r : SAMPLE;
    isLive.value = !!(r && r.months);
  } catch { d.value = SAMPLE; isLive.value = false; }
  finally { loading.value = false; }
}
onMounted(load);
watch(entityId, load);
</script>
