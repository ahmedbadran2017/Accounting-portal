<template>
  <div class="space-y-3.5">
    <!-- KPI cockpit -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <StatCard :label="L('Uncovered receipts','استلامات بلا تكلفة','Réceptions non couvertes')" :value="ov.uncovered_receipts ? ov.uncovered_receipts.n : 0"
                :sub="fmt0(ov.uncovered_receipts && ov.uncovered_receipts.value) + ' ' + ccy" icon="package" color="#b45309" />
      <StatCard :label="L('153.03 clearing','153.03 الوسيط','153.03 attente')" :value="fmt0(ov.clearing_balance)"
                :sub="clearingOk ? L('clean ✓','نظيف ✓','net ✓') : L('should trend to 0','المفروض يقرب صفر','doit tendre vers 0')" icon="scale"
                :value-color="clearingOk ? '#047857' : '#e11d48'" />
      <StatCard :label="L('Charges to capitalise','تكاليف للترسيم','À capitaliser')" :value="fmt0(ov.inbox_total)"
                :sub="(ov.inbox_n||0) + ' ' + L('bills','فاتورة','factures')" icon="inbox" color="#4338ca" />
      <StatCard :label="L('Month closeable','قابل للإقفال','Mois clôturable')" :value="ov.is_month_closeable ? L('Yes','نعم','Oui') : L('No','لا','Non')"
                :sub="L('153.03≈0 & all covered','153.03≈0 وكله مغطّى','couvert')" icon="check-circle"
                :value-color="ov.is_month_closeable ? '#047857' : '#b45309'" />
    </div>

    <div v-if="loading" class="py-10 text-center text-[12px] text-ink-muted">{{ L("Loading…","جارٍ التحميل…","Chargement…") }}</div>

    <div v-else-if="err" class="bg-rose-50 border border-rose-200 rounded-card px-4 py-6 text-center">
      <p class="text-[12px] text-rose-700 font-medium">{{ err }}</p>
      <button @click="load" class="mt-3 h-8 px-3 rounded-chip text-[12px] font-bold text-white bg-rose-600 hover:bg-rose-700">{{ L("Retry","إعادة المحاولة","Réessayer") }}</button>
    </div>

    <template v-else>
      <!-- Stale FX totals — receipts whose base_grand_total kept an old conversion rate -->
      <div v-if="staleTotals.length" class="bg-amber-50 rounded-card border border-amber-200 overflow-hidden">
        <div class="flex items-center gap-2 px-4 py-2.5 border-b border-amber-200">
          <Icon name="alert" :size="14" color="#b45309" />
          <h3 class="text-[13px] font-bold text-amber-800">{{ staleTotals.length }} {{ L("shipments show a stale FX total (display only)","شحنة عندها إجمالي بسعر صرف قديم (عرض فقط)","totaux FX périmés") }}</h3>
          <button v-if="canWrite" @click="fixAllTotals" :disabled="busy==='all'" class="ms-auto h-8 px-3 rounded-chip text-[12px] font-bold text-white bg-amber-600 hover:bg-amber-700 disabled:opacity-40">
            {{ busy==='all' ? '…' : L('Fix all '+staleTotals.length,'صلّح الكل '+staleTotals.length,'Corriger tout') }}
          </button>
        </div>
        <table class="w-full text-[12px]">
          <thead class="bg-amber-100/40 text-[10px] uppercase text-amber-800/70">
            <tr><th class="text-start px-3 py-1.5">{{ L("Receipt","الاستلام","Réception") }}</th><th class="text-end px-2 py-1.5">{{ L("Shown","المعروض","Affiché") }}</th><th class="text-end px-2 py-1.5">{{ L("Correct","الصحيح","Correct") }}</th><th class="text-center px-2 py-1.5">×</th><th class="px-3 py-1.5"></th></tr>
          </thead>
          <tbody class="divide-y divide-amber-200/60">
            <tr v-for="r in staleTotals" :key="r.name">
              <td class="px-3 py-1.5 font-medium"><router-link :to="{ path: '/accounting/purchases/received', query: { id: r.name } }" class="text-accent-dark hover:underline">{{ r.name }}</router-link> <span class="text-ink-muted">· {{ r.currency }}@{{ r.conversion_rate }}</span></td>
              <td class="px-2 py-1.5 text-end tnum text-rose-600">{{ fmt0(r.current) }}</td>
              <td class="px-2 py-1.5 text-end tnum text-emerald-700 font-semibold">{{ fmt0(r.correct) }}</td>
              <td class="px-2 py-1.5 text-center tnum text-ink-muted">{{ r.ratio }}</td>
              <td class="px-3 py-1.5 text-end">
                <button v-if="canWrite" @click="fixTotals(r)" :disabled="busy===r.name" class="h-7 px-2.5 rounded-chip text-[11px] font-bold text-amber-700 border border-amber-300 hover:bg-amber-100 disabled:opacity-40">
                  {{ busy===r.name ? '…' : L('Fix','صلّح','Corriger') }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
        <div class="px-4 py-2 text-[10.5px] text-amber-700/80 border-t border-amber-200">
          {{ L("Recomputes base grand total at the corrected rate (base net + taxes). No GL/stock impact — a display field only. Audited & reversible.","بيعيد حساب الإجمالي بالسعر المصحّح (صافي + ضرائب). مايمسّش القيود/المخزون — حقل عرض فقط. مدقّق وقابل للتراجع.","Recalcule le total. Aucun impact comptable.") }}
        </div>
      </div>

      <!-- Uncovered import receipts (domestic/local suppliers excluded — they carry their cost already) -->
      <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
        <div class="flex items-center gap-2 px-4 py-2.5 border-b border-line-hair flex-wrap">
          <h3 class="text-[13px] font-bold">{{ L("Import shipments awaiting landed cost","شحنات استيراد مستنية التكلفة","Imports à couvrir") }}</h3>
          <span class="text-[11px] text-ink-muted">{{ (recsT.total.value || 0).toLocaleString() }}</span>
          <input v-model="recsT.search.value" type="search"
                 :placeholder="L('Search receipt / supplier…','ابحث باسم الاستلام / المورد…','Rechercher…')"
                 class="ms-auto h-8 w-56 px-3 rounded-chip text-[12px] border border-line-2 bg-app-warm/30 focus:bg-white outline-none" />
        </div>
        <table class="w-full text-[12px]">
          <thead class="bg-app-warm/40 text-[10px] uppercase text-ink-muted">
            <tr>
              <th class="text-start px-3 py-1.5">{{ L("Receipt","الاستلام","Réception") }}</th>
              <th class="text-start px-2 py-1.5">{{ L("Supplier","المورد","Fournisseur") }}</th>
              <th class="text-end px-2 py-1.5">{{ L("Value","القيمة","Valeur") }}</th>
              <th class="text-end px-2 py-1.5">{{ L("Matched charges","تكاليف مربوطة","Charges liées") }}</th>
              <th class="text-end px-3 py-1.5">{{ L("Date","التاريخ","Date") }}</th>
              <th class="px-3 py-1.5"></th>
            </tr>
          </thead>
          <tbody class="divide-y divide-line-hair">
            <tr v-for="r in recsT.rows.value" :key="r.name" class="hover:bg-app-warm/30 cursor-pointer" @click="openOne(r.name)">
              <td class="px-3 py-1.5 font-medium"><router-link :to="{ path: '/accounting/purchases/received', query: { id: r.name } }" class="text-accent-dark hover:underline" @click.stop>{{ r.name }}</router-link> <span class="text-ink-muted">· {{ r.currency }}</span></td>
              <td class="px-2 py-1.5 truncate max-w-[150px]">{{ r.supplier }}</td>
              <td class="px-2 py-1.5 text-end tnum">{{ fmt0(r.value) }}</td>
              <td class="px-2 py-1.5 text-end tnum">
                <span v-if="matchedFor(r.name).length" class="text-emerald-700 font-semibold">{{ fmt0(matchedSum(r.name)) }}</span>
                <span v-else class="text-ink-muted">—</span>
              </td>
              <td class="px-3 py-1.5 text-end text-ink-muted">{{ r.dt }}</td>
              <td class="px-3 py-1.5 text-end">
                <button v-if="canWrite" @click.stop="openOne(r.name)" class="h-7 px-2.5 rounded-chip text-[11px] font-bold text-white bg-emerald-600 hover:bg-emerald-700">
                  {{ L("Capitalise","ترسيم","Capitaliser") }}
                </button>
              </td>
            </tr>
            <tr v-if="recsT.loading.value"><td colspan="6" class="px-3 py-8 text-center text-[12px] text-ink-muted">{{ L("Loading…","جارٍ التحميل…","Chargement…") }}</td></tr>
            <tr v-else-if="recsT.error.value"><td colspan="6" class="px-3 py-8 text-center text-[12px] text-rose-600">{{ L("Couldn't load shipments","تعذّر تحميل الشحنات","Échec de chargement") }} — <button @click="recsT.load()" class="underline font-semibold">{{ L("Retry","إعادة المحاولة","Réessayer") }}</button></td></tr>
            <tr v-else-if="!recsT.rows.value.length"><td colspan="6" class="px-3 py-8 text-center text-[12px] text-ink-muted">{{ recsT.search.value ? L("No match","لا نتائج","Aucun résultat") : L("Every import shipment is covered ✓","كل شحنات الاستيراد مغطّاة ✓","Tout est couvert ✓") }}</td></tr>
          </tbody>
        </table>
        <ServerPager v-if="recsT.total.value > recsT.pageSize.value" :t="recsT" />
      </div>

      <!-- Charge inbox preview -->
      <div v-if="inbox.length" class="bg-white rounded-card border border-line shadow-card overflow-hidden">
        <div class="px-4 py-2.5 border-b border-line-hair"><h3 class="text-[13px] font-bold">{{ L("Charges in the clearing inbox","تكاليف في صندوق الترسيم","Charges en attente") }}</h3></div>
        <table class="w-full text-[12px]">
          <tbody class="divide-y divide-line-hair">
            <tr v-for="(c,i) in inbox.slice(0,12)" :key="i">
              <td class="px-3 py-1.5 truncate max-w-[240px]">{{ c.account_name }} <span v-if="c.is_legacy_pl" class="text-[10px] text-amber-600">· {{ L('P&L','مصروف','P&L') }}</span></td>
              <td class="px-2 py-1.5 text-ink-muted truncate max-w-[160px]">{{ c.remarks }}</td>
              <td class="px-3 py-1.5 text-end tnum font-semibold">{{ fmt0(c.amount) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Posted LCVs — review / un-capitalise the ones on P&L accounts -->
      <div v-if="posted.length" class="bg-white rounded-card border border-line shadow-card overflow-hidden">
        <div class="flex items-center gap-2 px-4 py-2.5 border-b border-line-hair">
          <h3 class="text-[13px] font-bold">{{ L("Posted landed cost","تكاليف مُرحّلة","Coûts capitalisés") }}</h3>
          <span v-if="onPlCount" class="text-[10.5px] font-bold text-amber-700 bg-amber-50 border border-amber-200 rounded-chip px-2 py-0.5">{{ onPlCount }} {{ L("on P&L → un-capitalise & rebuild","على P&L → ألغِ وأعد البناء","sur P&L") }}</span>
        </div>
        <table class="w-full text-[12px]">
          <thead class="bg-app-warm/40 text-[10px] uppercase text-ink-muted">
            <tr><th class="text-start px-2.5 py-1.5">{{ L("Voucher","السند","Bon") }}</th><th class="text-start px-2 py-1.5">{{ L("Shipment","الشحنة","Expédition") }}</th><th class="text-end px-2 py-1.5">{{ L("Total","الإجمالي","Total") }}</th><th class="px-2 py-1.5">{{ L("Account","الحساب","Compte") }}</th><th class="px-3 py-1.5"></th></tr>
          </thead>
          <tbody class="divide-y divide-line-hair">
            <tr v-for="v in posted" :key="v.name" :class="v.on_pl ? 'bg-amber-50/40' : ''">
              <td class="px-2.5 py-1.5 font-medium">{{ v.name }} <span class="text-ink-muted">· {{ v.basis }}</span></td>
              <td class="px-2 py-1.5 truncate max-w-[150px]"><router-link v-if="v.shipment && v.shipment !== '—'" :to="{ path: '/accounting/purchases/received', query: { id: v.shipment } }" class="text-accent-dark hover:underline">{{ v.shipment }}</router-link><span v-else class="text-ink-3">{{ v.shipment }}</span></td>
              <td class="px-2 py-1.5 text-end tnum">{{ fmt0(v.total) }}</td>
              <td class="px-2 py-1.5 text-center">
                <span v-if="v.on_pl" class="text-[10px] font-bold text-amber-700">770.07 (P&L)</span>
                <span v-else class="text-[10px] font-bold text-emerald-700">153.03 ✓</span>
              </td>
              <td class="px-3 py-1.5 text-end">
                <button v-if="canWrite && v.on_pl" @click="uncapitalise(v)" :disabled="busy===v.name"
                        class="h-7 px-2.5 rounded-chip text-[11px] font-bold text-rose-600 border border-rose-200 hover:bg-rose-50 disabled:opacity-40">
                  {{ busy===v.name ? '…' : L('Un-capitalise','ألغِ الرسملة','Décapitaliser') }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-if="onPlCount" class="px-4 py-2 text-[10.5px] text-ink-muted border-t border-line-hair">
          {{ L("After un-capitalising, kick the repost queue (Valuation → reposts) so stock & COGS revert, then rebuild the shipment above onto 153.03.","بعد الإلغاء، كِك الـrepost queue (Valuation) عشان المخزون وCOGS يرجعوا، وبعدين أعد بناء الشحنة على 153.03.","Relancer les reposts puis reconstruire.") }}
        </div>
      </div>
    </template>

    <LandedCostAllocModal v-if="modal" :prefill="modal" @close="modal=null" @posted="onPosted" />
  </div>
</template>

<script setup>
import { ref, computed } from "vue";
import { useI18n } from "vue-i18n";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useAuth } from "@/composables/useAuth";
import { useToast } from "@/composables/useToast";
import { useServerTable } from "@/composables/useServerTable";
import StatCard from "@/components/StatCard.vue";
import ServerPager from "@/components/ServerPager.vue";
import LandedCostAllocModal from "@/components/LandedCostAllocModal.vue";

const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt0 = (n) => Number(n || 0).toLocaleString("en-US", { maximumFractionDigits: 0 });
const { can } = useAuth();
const canWrite = computed(() => can("post_entries"));
const toast = useToast();

const ov = ref({});
const inbox = ref([]);
const posted = ref([]);
const staleTotals = ref([]);
const modal = ref(null);
const loading = ref(true);
const err = ref("");
const busy = ref("");

// Uncovered import receipts: server-paginated + searchable so the whole backlog
// is reachable (not just the first page), and domestic suppliers are excluded.
const recsT = useServerTable(
  (p) => api.call("accounting_portal.api.landed_pipeline.receipts_uncovered_page",
    { company: currentCompany(), start: p.start, page_size: p.page_size, search: p.search }, { fresh: true }),
  { pageSize: 25 },
);
recsT.load();

// currency follows the company, not a hardcoded MAD — take it from the overview or the first uncovered receipt
const ccy = computed(() => ov.value.currency || recsT.rows.value[0]?.currency || "");
const clearingOk = computed(() => Math.abs(Number(ov.value.clearing_balance || 0)) < 1);
const onPlCount = computed(() => posted.value.filter((v) => v.on_pl).length);

async function load() {
  loading.value = true;
  err.value = "";
  try {
    const c = currentCompany();
    const [o, ib, lc, st] = await Promise.all([
      api.call("accounting_portal.api.landed_pipeline.pipeline_overview", { company: c }),
      api.call("accounting_portal.api.landed_pipeline.charge_inbox", { company: c }),
      api.call("accounting_portal.api.items.list_landed_costs", { company: c, limit: 200 }),
      api.call("accounting_portal.api.landed_pipeline.stale_receipt_totals", { company: c }),
    ]);
    ov.value = o || {}; inbox.value = ib || [];
    posted.value = (lc || []).filter((v) => v.status === "Posted");
    staleTotals.value = st || [];
  } catch (e) { err.value = String(e?.message || e).slice(0, 200); toast.error(err.value); }
  finally { loading.value = false; }
}
load();

async function uncapitalise(v) {
  if (busy.value) return;
  if (!window.confirm(L(
    `Un-capitalise ${v.name} (${fmt0(v.total)})? Reverses inventory & COGS. Then kick the repost queue and rebuild the shipment onto 153.03.`,
    `إلغاء رسملة ${v.name} (${fmt0(v.total)})؟ بيعكس المخزون وCOGS. بعدها كِك الـrepost وأعد البناء على 153.03.`,
    `Décapitaliser ${v.name} ?`))) return;
  busy.value = v.name;
  try {
    const r = await api.call("accounting_portal.api.landed_pipeline.cancel_lcv", { company: currentCompany(), name: v.name });
    if (r && r.status === "Proposed") toast.info(L("Sent for approval", "اتبعت للموافقة", "Envoyé"));
    else toast.success(L("Un-capitalised — kick reposts, then rebuild", "اتلغت الرسملة — كِك الـrepost وأعد البناء", "Décapitalisé"));
    load(); recsT.load();
  } catch (e) { toast.error(String(e?.message || e).slice(0, 200)); }
  finally { busy.value = ""; }
}

// charges whose bill remark tags THIS shipment
function matchedFor(receipt) { return inbox.value.filter((c) => c.shipment === receipt); }
function matchedSum(receipt) { return matchedFor(receipt).reduce((s, c) => s + Number(c.amount || 0), 0); }

// Self-service single-shipment flow: its tagged charges come in pre-selected;
// every other unassigned charge is offered as an unchecked suggestion to add.
// (One shipment at a time — no multi-select, which would smear every charge
// across receipts it doesn't belong to.)
function openOne(receipt) {
  const mine = matchedFor(receipt).map((c) => ({ ...c, include: true, matched: true }));
  const others = inbox.value.filter((c) => c.shipment !== receipt).map((c) => ({ ...c, include: false, matched: false }));
  modal.value = { receipts: [receipt], charges: [...mine, ...others], clearing_account: ov.value.clearing_account };
}
function onPosted() { modal.value = null; load(); recsT.load(); }

async function fixTotals(r) {
  if (busy.value) return;
  busy.value = r.name;
  try {
    await api.call("accounting_portal.api.landed_pipeline.fix_receipt_totals", { company: currentCompany(), receipt: r.name });
    staleTotals.value = staleTotals.value.filter((x) => x.name !== r.name);
    toast.success(L(`Fixed ${r.name}`, `اتصلّح ${r.name}`, `Corrigé ${r.name}`));
    recsT.load();
  } catch (e) { toast.error(String(e?.message || e).slice(0, 200)); }
  finally { busy.value = ""; }
}
async function fixAllTotals() {
  if (busy.value) return;
  busy.value = "all";
  const rows = [...staleTotals.value];
  try {
    for (const r of rows) {
      await api.call("accounting_portal.api.landed_pipeline.fix_receipt_totals", { company: currentCompany(), receipt: r.name });
      staleTotals.value = staleTotals.value.filter((x) => x.name !== r.name);
    }
    toast.success(L(`Fixed ${rows.length} shipments`, `اتصلّح ${rows.length} شحنة`, `Corrigé ${rows.length}`));
    recsT.load();
  } catch (e) { toast.error(String(e?.message || e).slice(0, 200)); }
  finally { busy.value = ""; }
}
</script>
