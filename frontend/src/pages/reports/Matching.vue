<template>
  <div class="space-y-3.5">
    <div class="flex items-center gap-2 flex-wrap">
      <span class="text-[13px] font-bold">{{ L("Revenue ↔ Cost matching","مطابقة الإيراد والتكلفة","Rapprochement CA ↔ coût") }}</span>
      <span class="text-[11px] text-ink-muted">{{ L("every month: does each dirham of revenue have its cost, and each cost its revenue?","كل شهر: هل كل إيراد قصاده تكلفته وكل تكلفة قصادها إيرادها؟","chaque mois : chaque dirham a-t-il sa contrepartie ?") }}</span>
      <div class="ms-auto flex items-center gap-1.5">
        <button @click="view = 'month'" class="text-[11.5px] font-semibold px-3 py-1.5 rounded-full border transition"
                :class="view === 'month' ? 'bg-accent text-white border-accent' : 'bg-white text-ink-3 border-line-2 hover:bg-app-warm'">{{ L("By month","بالشهور","Par mois") }}</button>
        <button @click="view = 'cycle'; if (!cy) loadCycle();" class="text-[11.5px] font-semibold px-3 py-1.5 rounded-full border transition"
                :class="view === 'cycle' ? 'bg-accent text-white border-accent' : 'bg-white text-ink-3 border-line-2 hover:bg-app-warm'">{{ L("By cycle","بالدورة","Par cycle") }}</button>
        <span class="w-2"></span>
        <button v-for="yy in years" :key="yy" @click="year = yy; reload()" class="text-[11.5px] font-semibold px-3 py-1.5 rounded-full border transition"
                :class="year === yy ? 'bg-ink text-white border-ink' : 'bg-white text-ink-3 border-line-2 hover:bg-app-warm'">{{ yy }}</button>
      </div>
    </div>

    <!-- ═══════════ CYCLE VIEW: every order must tell its full story ═══════════ -->
    <template v-if="view === 'cycle'">
      <TableLoading v-if="cyLoading" :rows="6" />
      <template v-else-if="cy">
        <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <div class="bg-white rounded-card border border-line shadow-card px-4 py-3">
            <div class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Orders","أوردرات","Commandes") }}</div>
            <div class="text-[19px] font-extrabold tnum" dir="ltr">{{ n(cy.orders) }}</div>
          </div>
          <div class="bg-white rounded-card border border-line shadow-card px-4 py-3">
            <div class="text-[10px] font-bold uppercase tracking-wider" style="color:#047857">{{ L("Complete story","قصة كاملة","Histoire complète") }}</div>
            <div class="text-[19px] font-extrabold tnum" style="color:#047857" dir="ltr">{{ n(cy.complete) }} <span class="text-[12px]">({{ cy.orders ? Math.round(100*cy.complete/cy.orders) : 0 }}%)</span></div>
          </div>
          <div class="bg-white rounded-card border border-line shadow-card px-4 py-3">
            <div class="text-[10px] font-bold uppercase tracking-wider" style="color:#b91c1c">{{ L("Incomplete","قصة ناقصة","Incomplète") }}</div>
            <div class="text-[19px] font-extrabold tnum" style="color:#b91c1c" dir="ltr">{{ n(cy.incomplete) }}</div>
          </div>
          <div class="bg-white rounded-card border border-line shadow-card px-4 py-3">
            <div class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("The contract","العقد","Le contrat") }}</div>
            <div class="text-[10.5px] text-ink-3 leading-snug mt-0.5">{{ L("delivered→DN+SI · returned pre-invoice→no SI · post-invoice→CN+refund","متسلم→إذن+فاتورة · راجع قبل الفوترة→بلا فاتورة · بعدها→CN+استرداد","livré→BL+facture · retour→avoir+remb.") }}</div>
          </div>
        </div>
        <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
          <table class="w-full text-[12px]">
            <thead><tr style="background:#fafaf9">
              <th class="px-4 py-2.5 text-start hcell">{{ L("Exception","الاستثناء","Exception") }}</th>
              <th class="px-4 py-2.5 text-end hcell">{{ L("Orders","أوردرات","Cmd") }}</th>
              <th class="px-4 py-2.5 text-end hcell">{{ L("Revenue at stake","إيراد متأثر","CA en jeu") }}</th>
              <th class="px-4 py-2.5 text-end hcell">{{ L("Fix","التصليح","Action") }}</th>
            </tr></thead>
            <tbody>
              <tr v-for="(b, k) in cy.buckets" :key="k" class="border-t border-line-hair hover:bg-app-warm/40 cursor-pointer"
                  :class="cyBucket === k ? 'bg-app-warm/60' : ''" @click="pickCycle(k)">
                <td class="px-4 py-2.5 font-semibold">{{ cyLabel(k) }}</td>
                <td class="px-4 py-2.5 text-end tnum">{{ n(b.n) }}</td>
                <td class="px-4 py-2.5 text-end tnum">{{ n(b.value) }}</td>
                <td class="px-4 py-2.5 text-end text-[11px] text-ink-muted">{{ cyAction(b.action) }}</td>
              </tr>
              <tr v-if="!Object.keys(cy.buckets || {}).length"><td colspan="4" class="px-4 py-10 text-center text-[12.5px]" style="color:#047857">{{ L("Every order tells its complete story. 🎉","كل أوردر بيحكي قصته كاملة 🎉","Toutes les commandes sont complètes 🎉") }}</td></tr>
            </tbody>
          </table>
        </div>
        <div v-if="cyBucket" class="bg-white rounded-card border border-line shadow-card overflow-hidden">
          <div class="px-4 py-2.5 text-[11.5px] font-bold border-b border-line-hair" style="background:#fafaf9">{{ cyLabel(cyBucket) }} <span class="text-ink-muted font-normal" dir="ltr">{{ drillRows.length }} / {{ drillTotal }}</span></div>
          <TableLoading v-if="drillLoading" :rows="4" />
          <table v-else class="w-full text-[11.5px]">
            <tbody>
              <tr v-for="d in drillRows" :key="d.so" class="border-t border-line-hair first:border-t-0 hover:bg-app-warm/30">
                <td class="px-4 py-2 font-mono text-[11px]">{{ d.doc }}</td>
                <td class="px-4 py-2 font-mono text-[10.5px] text-ink-muted">{{ d.so }}</td>
                <td class="px-4 py-2 text-end tnum">{{ n(d.amount) }}</td>
                <td class="px-4 py-2 text-end w-32">
                  <button v-if="d.action === 'bill'" class="h-6 px-2 rounded-[7px] text-[10.5px] font-bold text-white bg-brand hover:bg-brand-dark disabled:opacity-50" :disabled="busy === d.doc" @click="bill(d)">{{ busy === d.doc ? "…" : L("Make invoice","اعمل فاتورة","Facturer") }}</button>
                  <button v-else-if="d.action === 'credit_note'" class="h-6 px-2 rounded-[7px] text-[10.5px] font-bold text-white hover:opacity-90 disabled:opacity-50" style="background:#b45309" :disabled="busy === d.doc" @click="creditNote(d)">{{ busy === d.doc ? "…" : L("Credit note","إشعار دائن","Avoir") }}</button>
                  <span v-else class="text-[10px] text-ink-muted">{{ L("review","مراجعة","à revoir") }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </template>

    <div v-if="view === 'month'" class="bg-white rounded-card border border-line overflow-hidden shadow-card">
      <TableLoading v-if="loading" :rows="8" />
      <div v-else-if="!rows.length" class="py-14 text-center text-[12.5px] text-ink-muted">{{ L("No data for this year.","لا توجد بيانات لهذه السنة.","Aucune donnée.") }}</div>
      <div v-else class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead><tr style="background:#fafaf9">
            <th class="px-3 py-2.5 text-start hcell">{{ L("Month","الشهر","Mois") }}</th>
            <th class="px-3 py-2.5 text-end hcell">{{ L("Invoices","فواتير","Factures") }}</th>
            <th class="px-3 py-2.5 text-end hcell">{{ L("Revenue","الإيراد","CA") }}</th>
            <th class="px-3 py-2.5 text-end hcell">{{ L("DNs","أذون","BL") }}</th>
            <th class="px-3 py-2.5 text-end hcell">{{ L("DN cost","تكلفة الأذون","Coût BL") }}</th>
            <th class="px-3 py-2.5 text-end hcell" :title="L('cost went out and came back — cancels itself','خرجت ورجعت — تلغي نفسها','annulé par retour')">{{ L("Returns","مرتجعات","Retours") }}</th>
            <th class="px-3 py-2.5 text-end hcell" style="color:#b91c1c">{{ L("Cost, no revenue","تكلفة بلا إيراد","Coût sans CA") }}</th>
            <th class="px-3 py-2.5 text-end hcell" style="color:#b45309">{{ L("Revenue, no cost","إيراد بلا تكلفة","CA sans coût") }}</th>
            <th class="px-3 py-2.5 text-end hcell">{{ L("GM as booked","الهامش المسجل","MB comptable") }}</th>
          </tr></thead>
          <tbody>
            <template v-for="r in rows" :key="r.month">
              <tr class="border-t border-line-hair hover:bg-app-warm/40 cursor-pointer" @click="toggle(r.month)">
                <td class="px-3 py-2.5 font-semibold whitespace-nowrap">
                  <Icon :name="open === r.month ? 'chevDown' : 'chev'" :size="12" class="inline me-1" />{{ r.month }}
                </td>
                <td class="px-3 py-2.5 text-end tnum">{{ n(r.si_count) }}</td>
                <td class="px-3 py-2.5 text-end tnum">{{ n(r.revenue) }}</td>
                <td class="px-3 py-2.5 text-end tnum">{{ n(r.dn_count) }}</td>
                <td class="px-3 py-2.5 text-end tnum">{{ n(r.dn_cogs) }}</td>
                <td class="px-3 py-2.5 text-end tnum text-ink-muted">{{ n(r.returned.n) }}</td>
                <td class="px-3 py-2.5 text-end tnum font-bold" :style="r.cost_without_revenue > 1000 ? 'color:#b91c1c' : 'color:#047857'">{{ n(r.cost_without_revenue) }}</td>
                <td class="px-3 py-2.5 text-end tnum font-bold" :style="r.revenue_without_cost > 1000 ? 'color:#b45309' : 'color:#047857'">{{ n(r.revenue_without_cost) }}</td>
                <td class="px-3 py-2.5 text-end tnum">{{ gm(r) }}</td>
              </tr>
              <tr v-if="open === r.month" class="border-t border-line-hair" style="background:#fafaf9">
                <td colspan="9" class="px-4 py-3">
                  <div class="flex items-center gap-1.5 flex-wrap mb-2">
                    <button v-for="b in bucketsOf(r)" :key="b.key" @click="pick(r.month, b.key)"
                            class="text-[11px] font-semibold px-2.5 py-1 rounded-full border transition"
                            :class="bucket === b.key ? 'bg-ink text-white border-ink' : 'bg-white text-ink-3 border-line-2 hover:bg-app-warm'">
                      {{ b.label }} · {{ n(b.n) }} · {{ n(b.amt) }}
                    </button>
                  </div>
                  <TableLoading v-if="drillLoading" :rows="3" />
                  <table v-else-if="drillRows.length" class="w-full text-[11.5px] bg-white rounded-[10px] border border-line-hair">
                    <tbody>
                      <tr v-for="d in drillRows" :key="d.doc" class="border-t border-line-hair first:border-t-0">
                        <td class="px-3 py-2 font-mono text-[11px]">{{ d.doc }}</td>
                        <td class="px-3 py-2 truncate max-w-[220px]">{{ d.customer || "—" }}</td>
                        <td class="px-3 py-2 text-end tnum">{{ n(d.amount) }}</td>
                        <td class="px-3 py-2 text-end w-32">
                          <button v-if="d.action === 'bill'" class="h-6 px-2 rounded-[7px] text-[10.5px] font-bold text-white bg-brand hover:bg-brand-dark disabled:opacity-50"
                                  :disabled="busy === d.doc" @click="bill(d)">
                            {{ busy === d.doc ? "…" : L("Make invoice","اعمل فاتورة","Facturer") }}
                          </button>
                          <button v-else-if="d.action === 'credit_note'" class="h-6 px-2 rounded-[7px] text-[10.5px] font-bold text-white hover:opacity-90 disabled:opacity-50" style="background:#b45309"
                                  :disabled="busy === d.doc" @click="creditNote(d)">
                            {{ busy === d.doc ? "…" : L("Credit note","إشعار دائن","Avoir") }}
                          </button>
                          <span v-else class="text-[10px] text-ink-muted">{{ L("review","مراجعة","à revoir") }}</span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                  <div v-else class="text-[11.5px] text-ink-muted py-2">{{ L("Pick a bucket above to list its documents.","اختر فئة من فوق لعرض مستنداتها.","Choisissez une catégorie.") }}</div>
                  <div v-if="drillTotal > drillRows.length" class="text-[10.5px] text-ink-muted mt-1.5" dir="ltr">{{ drillRows.length }} / {{ drillTotal }}</div>
                </td>
              </tr>
            </template>
          </tbody>
          <tfoot v-if="d0"><tr class="border-t-2 border-line font-bold" style="background:#fafaf9">
            <td class="px-3 py-2.5">{{ L("Total","الإجمالي","Total") }}</td>
            <td></td>
            <td class="px-3 py-2.5 text-end tnum">{{ n(d0.total.revenue) }}</td>
            <td></td>
            <td class="px-3 py-2.5 text-end tnum">{{ n(d0.total.dn_cogs) }}</td>
            <td></td>
            <td class="px-3 py-2.5 text-end tnum" style="color:#b91c1c">{{ n(d0.total.cost_without_revenue) }}</td>
            <td class="px-3 py-2.5 text-end tnum" style="color:#b45309">{{ n(d0.total.revenue_without_cost) }}</td>
            <td></td>
          </tr></tfoot>
        </table>
      </div>
    </div>

    <!-- tie-out to the P&L -->
    <div v-if="view === 'month' && d0 && d0.tie_out" class="bg-white rounded-card border border-line shadow-card px-4 py-3">
      <div class="text-[11.5px] font-bold mb-1.5">{{ L("Ties out to the P&L COGS section","التسوية مع بند الكوجز في قائمة الدخل","Rapproché du P&L") }}</div>
      <div class="flex items-center gap-x-4 gap-y-1 flex-wrap text-[11.5px] tnum" dir="ltr">
        <span>{{ L("DN cost","تكلفة الأذون","Coût BL") }}: <b>{{ n(d0.tie_out.dn) }}</b></span>
        <span>+ {{ L("direct supplier bills","فواتير موردين مباشرة","factures directes") }}: <b>{{ n(d0.tie_out.direct_pi) }}</b></span>
        <span>+ {{ L("direct receipts","إيصالات مباشرة","réceptions directes") }}: <b>{{ n(d0.tie_out.direct_pr) }}</b></span>
        <span>+ {{ L("journal entries","قيود يدوية","OD") }}: <b>{{ n(d0.tie_out.je) }}</b></span>
        <span>+ {{ L("other","أخرى","autres") }}: <b>{{ n(d0.tie_out.other) }}</b></span>
        <span>= {{ L("GL COGS","كوجز الدفاتر","COGS GL") }}: <b>{{ n(d0.tie_out.gl_total) }}</b></span>
      </div>
      <div class="text-[10.5px] text-ink-muted mt-1">{{ L("Direct bills/receipts/JEs in COGS are pollution being cleaned — this line shrinking to 'DN cost = GL' is the goal.","الفواتير والقيود المباشرة في الكوجز تلوث بيتنضف — الهدف إن السطر ده يبقى: تكلفة الأذون = الدفاتر.","Les écritures directes sont en cours de nettoyage.") }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";

const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const n = (v) => (v == null ? "—" : Math.round(v).toLocaleString("en-US"));

const years = [2026, 2025];
const year = ref(2026);
const view = ref("month");
const cy = ref(null);
const cyLoading = ref(false);
const cyBucket = ref("");
const loading = ref(false);
const d0 = ref(null);
const rows = ref([]);
const open = ref("");
const bucket = ref("");
const drillRows = ref([]);
const drillTotal = ref(0);
const drillLoading = ref(false);
const busy = ref("");

const gm = (r) => (r.revenue ? Math.round((100 * (r.revenue - r.dn_cogs)) / r.revenue) + "%" : "—");

function bucketsOf(r) {
  return [
    { key: "collected", label: L("Collected, no invoice", "متحصّل بلا فاتورة", "Encaissé sans facture"), n: r.collected.n, amt: r.collected.cogs },
    { key: "delivered", label: L("Delivered, awaiting invoice", "متسلّم مستني فاتورة", "Livré, à facturer"), n: r.delivered.n, amt: r.delivered.cogs },
    { key: "closed", label: L("Closed with goods out", "مقفول والبضاعة برة", "Clos, marchandise sortie"), n: r.closed.n, amt: r.closed.cogs },
    { key: "rev_returned", label: L("Revenue standing, goods returned", "إيراد واقف وبضاعته رجعت", "CA maintenu, retourné"), n: r.rev_returned.n, amt: r.rev_returned.value },
    { key: "rev_no_cost", label: L("Invoice with no shipment", "فاتورة بلا شحنة", "Facture sans BL"), n: r.rev_no_cost.n, amt: r.rev_no_cost.value },
    { key: "returned", label: L("Returns (self-cancelling)", "مرتجعات (تلغي نفسها)", "Retours (auto-annulés)"), n: r.returned.n, amt: r.returned.cogs },
  ].filter((b) => b.n > 0);
}

async function load() {
  loading.value = true; open.value = ""; bucket.value = ""; drillRows.value = [];
  try {
    d0.value = await api.call("accounting_portal.api.matching.monthly",
      { company: currentCompany(), year: year.value }, { fresh: true });
    rows.value = d0.value?.rows || [];
  } catch (e) { alert((e && e.message) || e); }
  finally { loading.value = false; }
}
function toggle(m) {
  open.value = open.value === m ? "" : m;
  bucket.value = ""; drillRows.value = []; drillTotal.value = 0;
}
async function pick(m, b) {
  bucket.value = b; drillLoading.value = true;
  try {
    const r = await api.call("accounting_portal.api.matching.drill",
      { company: currentCompany(), year: year.value, month: m, bucket: b }, { fresh: true });
    drillRows.value = r.rows || []; drillTotal.value = r.total || 0;
  } catch (e) { alert((e && e.message) || e); }
  finally { drillLoading.value = false; }
}
async function bill(d) {
  if (!confirm(L(`Create + submit a Sales Invoice from ${d.doc}?`, `إنشاء وترحيل فاتورة من ${d.doc}؟`, `Créer la facture depuis ${d.doc} ?`))) return;
  busy.value = d.doc;
  try {
    await api.call("accounting_portal.api.sales.bill_delivery_note",
      { company: currentCompany(), delivery_note: d.doc, submit: 1 });
    drillRows.value = drillRows.value.filter((x) => x.doc !== d.doc);
  } catch (e) { alert((e && e.message) || e); }
  finally { busy.value = ""; }
}
async function creditNote(d) {
  if (!confirm(L(`Issue a credit note against ${d.doc}? The goods already came back.`, `إصدار إشعار دائن على ${d.doc}؟ البضاعة رجعت بالفعل.`, `Émettre un avoir sur ${d.doc} ?`))) return;
  busy.value = d.doc;
  try {
    await api.call("accounting_portal.api.sales.create_sales_return",
      { company: currentCompany(), invoice: d.doc, reason: "matching screen — goods returned, invoice stood" });
    drillRows.value = drillRows.value.filter((x) => x.doc !== d.doc);
  } catch (e) { alert((e && e.message) || e); }
  finally { busy.value = ""; }
}
const CY_LABELS = {
  delivered_no_si: () => L("Carrier-confirmed delivered, awaiting invoice", "تسليم مؤكد من الكاريير — مستني فاتورة", "Livraison confirmée, à facturer"),
  stuck_at_carrier: () => L("Shipped, carrier does NOT confirm delivery", "متشحن والكاريير مش مأكد التسليم", "Expédié, non confirmé par transporteur"),
  collected_no_si: () => L("Collected, never invoiced", "متحصّل بلا فاتورة", "Encaissé sans facture"),
  returned_no_cn: () => L("Returned after invoicing — no credit note", "راجع بعد الفوترة — بلا إشعار دائن", "Retour facturé sans avoir"),
  cn_no_refund: () => L("Credit note without formal refund", "إشعار دائن بلا استرداد رسمي", "Avoir sans remboursement"),
  goods_out_cancelled: () => L("Cancelled order, goods went out", "أوردر ملغي وبضاعته خرجت", "Annulée, marchandise sortie"),
  rev_no_dn: () => L("Invoice with no shipment", "فاتورة بلا شحنة", "Facture sans BL"),
  in_transit: () => L("In transit (young — just watching)", "في السكة (حديث — مراقبة بس)", "En transit (récent)"),
};
const cyLabel = (k) => (CY_LABELS[k] ? CY_LABELS[k]() : k);
const cyAction = (a) => a === "bill" ? L("Make invoice", "فاتورة", "Facturer")
  : a === "credit_note" ? L("Credit note", "إشعار دائن", "Avoir")
  : a === "none" ? L("wait", "استنى", "attendre") : L("review", "مراجعة", "revoir");

async function loadCycle() {
  cyLoading.value = true; cyBucket.value = ""; drillRows.value = [];
  try {
    cy.value = await api.call("accounting_portal.api.matching.cycle",
      { company: currentCompany(), year: year.value }, { fresh: true });
  } catch (e) { alert((e && e.message) || e); }
  finally { cyLoading.value = false; }
}
async function pickCycle(b) {
  cyBucket.value = b; drillLoading.value = true;
  try {
    const r = await api.call("accounting_portal.api.matching.cycle_drill",
      { company: currentCompany(), year: year.value, bucket: b }, { fresh: true });
    drillRows.value = r.rows || []; drillTotal.value = r.total || 0;
  } catch (e) { alert((e && e.message) || e); }
  finally { drillLoading.value = false; }
}
function reload() { load(); if (view.value === "cycle" || cy.value) loadCycle(); }
const { entityId } = useUi();
watch(entityId, reload);
onMounted(load);
</script>

<style scoped>
.hcell { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--ink-muted, #78716c); }
</style>
