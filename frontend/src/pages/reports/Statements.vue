<template>
  <div class="space-y-3.5">
    <div class="flex items-center gap-2">
      <span class="inline-flex items-center gap-1.5 text-[10.5px] font-bold uppercase tracking-wider px-2 py-1 rounded-chip"
            :class="live ? 'text-success-dark bg-success-soft' : 'text-amber-700 bg-amber-50'">
        <span class="w-1.5 h-1.5 rounded-full" :class="live ? 'bg-success' : 'bg-amber-500'"></span>{{ live ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échantillon") }}
      </span>
      <span class="text-[11px] text-ink-muted">{{ L("Fiscal year to date","السنة المالية حتى اليوم","Exercice à ce jour") }}</span>
    </div>

    <div class="grid lg:grid-cols-[1.4fr_1fr] gap-3.5">
      <!-- Profit & loss -->
      <div class="bg-white rounded-card border border-line overflow-hidden shadow-card">
        <div class="px-4 py-3 border-b border-line flex items-center gap-2">
          <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#ecfdf5"><Icon name="trend" :size="14" color="#047857" /></span>
          <span class="text-[13px] font-bold">{{ L("Profit & loss","الأرباح والخسائر","Résultat") }}</span>
        </div>
        <table class="w-full text-[12px]">
          <tbody>
            <tr class="border-b border-line-hair"><td class="px-4 py-1.5 text-[10px] font-bold uppercase tracking-wider text-ink-muted" colspan="2">{{ L("Income","الإيرادات","Produits") }}</td></tr>
            <tr v-for="(r,i) in pnl.income" :key="'i'+i" class="border-b border-line-hair"><td class="px-4 py-1.5 text-ink-2">{{ r.name }}</td><td class="px-4 py-1.5 text-end tnum font-medium text-success-dark">{{ money0(r.amount) }}</td></tr>
            <tr class="border-b border-line-2 bg-app-warm/40"><td class="px-4 py-1.5 font-semibold">{{ L("Total income","إجمالي الإيرادات","Total produits") }}</td><td class="px-4 py-1.5 text-end tnum font-bold text-success-dark">{{ money0(pnl.income_total) }}</td></tr>
            <tr class="border-b border-line-hair"><td class="px-4 pt-3 pb-1.5 text-[10px] font-bold uppercase tracking-wider text-ink-muted" colspan="2">{{ L("Expense","المصروفات","Charges") }}</td></tr>
            <tr v-for="(r,i) in pnl.expense" :key="'e'+i" class="border-b border-line-hair" :class="pnl.anomaly && r.account===pnl.anomaly.account ? 'bg-amber-50' : ''">
              <td class="px-4 py-1.5 text-ink-2">{{ r.name }}<span v-if="pnl.anomaly && r.account===pnl.anomaly.account" class="ms-1.5 text-[9.5px] font-bold text-amber-700">⚠ {{ L("anomaly","شذوذ","anomalie") }}</span></td>
              <td class="px-4 py-1.5 text-end tnum font-medium text-sale">{{ money0(r.amount) }}</td>
            </tr>
            <tr class="border-b border-line-2 bg-app-warm/40"><td class="px-4 py-1.5 font-semibold">{{ L("Total expense","إجمالي المصروفات","Total charges") }}</td><td class="px-4 py-1.5 text-end tnum font-bold text-sale">{{ money0(pnl.expense_total) }}</td></tr>
            <tr><td class="px-4 py-2.5 font-bold">{{ L("Net result","صافي النتيجة","Résultat net") }}</td><td class="px-4 py-2.5 text-end tnum font-extrabold" :class="pnl.net>=0 ? 'text-success-dark' : 'text-sale'">{{ money0(pnl.net) }}</td></tr>
          </tbody>
        </table>
        <div v-if="pnl.anomaly" class="px-4 py-2.5 border-t border-line bg-amber-50/60 text-[11px] text-amber-800 flex items-start gap-1.5">
          <Icon name="alert" :size="13" color="#b45309" class="mt-px flex-shrink-0" />
          <span>{{ L("“"+pnl.anomaly.name+"” of "+money0(pnl.anomaly.amount)+" dominates expense — perpetual inventory isn't relieving to COGS. The auditor flags this for a correcting entry.","«"+pnl.anomaly.name+"» بمقدار "+money0(pnl.anomaly.amount)+" يهيمن على المصروفات — الجرد المستمر لا يُرحّل لتكلفة المبيعات. المدقّق يرصده لقيد تصحيحي.","« "+pnl.anomaly.name+" » domine les charges — l'inventaire perpétuel ne se solde pas en CMV.") }}</span>
        </div>
      </div>

      <!-- Balance sheet -->
      <div class="bg-white rounded-card border border-line overflow-hidden shadow-card h-fit">
        <div class="px-4 py-3 border-b border-line flex items-center gap-2">
          <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#eff6ff"><Icon name="ledger" :size="14" color="#0369a1" /></span>
          <span class="text-[13px] font-bold">{{ L("Balance sheet","الميزانية","Bilan") }}</span>
        </div>
        <table class="w-full text-[12px]">
          <tbody>
            <tr class="border-b border-line-hair"><td class="px-4 py-2 text-ink-2">{{ L("Assets","الأصول","Actif") }}</td><td class="px-4 py-2 text-end tnum font-semibold">{{ money0(bs.assets) }}</td></tr>
            <tr class="border-b border-line-hair"><td class="px-4 py-2 text-ink-2">{{ L("Liabilities","الخصوم","Passif") }}</td><td class="px-4 py-2 text-end tnum font-semibold">{{ money0(bs.liabilities) }}</td></tr>
            <tr class="border-b border-line-hair"><td class="px-4 py-2 text-ink-2">{{ L("Equity","حقوق الملكية","Capitaux") }}</td><td class="px-4 py-2 text-end tnum font-semibold">{{ money0(bs.equity) }}</td></tr>
            <tr><td class="px-4 py-2 font-bold">{{ L("Check (A−L−E)","التحقّق","Contrôle") }}</td><td class="px-4 py-2 text-end tnum font-bold" :class="Math.abs(bs.check)<1 ? 'text-success-dark' : 'text-sale'">{{ money0(bs.check) }}</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Aging -->
    <div class="grid sm:grid-cols-2 gap-3.5">
      <AgingCard :title="L('Receivables aging','أعمار الذمم المدينة','Âge des créances')" icon="coins" tint="#ecfdf5" color="#047857" :data="ar" />
      <AgingCard :title="L('Payables aging','أعمار الذمم الدائنة','Âge des dettes')" icon="doc" tint="#fef2f2" color="#b91c1c" :data="ap" />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, h } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { useUi } from "@/composables/useUi";
import { loadPnl, loadBalanceSheet, loadArAging, loadApAging, money0, agingBuckets } from "@/composables/useReports";

const { locale } = useI18n();
const { entityId } = useUi();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

const live = ref(false);
const pnl = ref({ income: [], expense: [], income_total: 0, expense_total: 0, net: 0, anomaly: null });
const bs = ref({ assets: 0, liabilities: 0, equity: 0, check: 0 });
const ar = ref({});
const ap = ref({});

async function load() {
  const [p, b, a, q] = await Promise.all([loadPnl(), loadBalanceSheet(), loadArAging(), loadApAging()]);
  live.value = p.live;
  pnl.value = p.data; bs.value = b.data; ar.value = a.data; ap.value = q.data;
}
onMounted(load);
watch(entityId, load);

const AgingCard = {
  props: ["title", "icon", "tint", "color", "data"],
  setup(props) {
    return () => {
      const buckets = agingBuckets(props.data || {}, L);
      const max = Math.max(1, ...buckets.map((b) => Math.abs(b.v)));
      const toneColor = { ok: "#16a34a", warn: "#d97706", bad: "#dc2626" };
      return h("div", { class: "bg-white rounded-card border border-line overflow-hidden shadow-card" }, [
        h("div", { class: "px-4 py-3 border-b border-line flex items-center gap-2" }, [
          h("span", { class: "w-[26px] h-[26px] rounded-[8px] grid place-items-center", style: `background:${props.tint}` }, [h(Icon, { name: props.icon, size: 14, color: props.color })]),
          h("span", { class: "text-[13px] font-bold flex-1" }, props.title),
          h("span", { class: "text-[12px] font-bold tnum" }, money0((props.data || {}).total)),
          h("span", { class: "text-[10px] text-ink-muted ms-1" }, `${(props.data || {}).n || 0} ${L("docs", "مستند", "docs")}`),
        ]),
        h("div", { class: "p-4 space-y-2" }, buckets.map((bk) =>
          h("div", { class: "flex items-center gap-2.5" }, [
            h("span", { class: "text-[11px] text-ink-3 w-14 flex-shrink-0" }, bk.k),
            h("div", { class: "flex-1 h-[18px] rounded bg-app-warm overflow-hidden" }, [
              h("div", { class: "h-full rounded", style: `width:${Math.max(2, Math.abs(bk.v) / max * 100)}%;background:${toneColor[bk.tone]}` }),
            ]),
            h("span", { class: "text-[11.5px] tnum font-semibold w-20 text-end flex-shrink-0" }, money0(bk.v)),
          ])
        )),
      ]);
    };
  },
};
</script>
