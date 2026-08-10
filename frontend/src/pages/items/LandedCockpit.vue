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

    <template v-else>
      <!-- Uncovered receipts -->
      <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
        <div class="flex items-center gap-2 px-4 py-2.5 border-b border-line-hair">
          <h3 class="text-[13px] font-bold">{{ L("Shipments awaiting landed cost","شحنات مستنية التكلفة","Expéditions à couvrir") }}</h3>
          <span class="text-[11px] text-ink-muted">{{ recs.length }}</span>
          <button v-if="canWrite && sel.length" @click="openAlloc" class="ms-auto h-8 px-3 rounded-chip text-[12px] font-bold text-white bg-emerald-600 hover:bg-emerald-700">
            {{ L("Capitalise "+sel.length+" selected","ترسيم "+sel.length+" مختار","Capitaliser "+sel.length) }}
          </button>
        </div>
        <table class="w-full text-[12px]">
          <thead class="bg-app-warm/40 text-[10px] uppercase text-ink-muted">
            <tr>
              <th class="w-8 px-2 py-1.5"><input type="checkbox" :checked="sel.length===recs.length && recs.length>0" @change="toggleAll" /></th>
              <th class="text-start px-2 py-1.5">{{ L("Receipt","الاستلام","Réception") }}</th>
              <th class="text-start px-2 py-1.5">{{ L("Supplier","المورد","Fournisseur") }}</th>
              <th class="text-end px-2 py-1.5">{{ L("Value","القيمة","Valeur") }}</th>
              <th class="text-end px-2 py-1.5">{{ L("Items","أصناف","Articles") }}</th>
              <th class="text-end px-3 py-1.5">{{ L("Date","التاريخ","Date") }}</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-line-hair">
            <tr v-for="r in recs" :key="r.name" class="hover:bg-app-warm/30 cursor-pointer" @click="toggle(r.name)">
              <td class="px-2 py-1.5"><input type="checkbox" :checked="sel.includes(r.name)" @click.stop="toggle(r.name)" /></td>
              <td class="px-2 py-1.5 font-medium">{{ r.name }} <span class="text-ink-muted">· {{ r.currency }}</span></td>
              <td class="px-2 py-1.5 truncate max-w-[160px]">{{ r.supplier }}</td>
              <td class="px-2 py-1.5 text-end tnum">{{ fmt0(r.value) }}</td>
              <td class="px-2 py-1.5 text-end tnum">{{ r.items }}</td>
              <td class="px-3 py-1.5 text-end text-ink-muted">{{ r.dt }}</td>
            </tr>
            <tr v-if="!recs.length"><td colspan="6" class="px-3 py-8 text-center text-[12px] text-ink-muted">{{ L("Every shipment is covered ✓","كل الشحنات مغطّاة ✓","Tout est couvert ✓") }}</td></tr>
          </tbody>
        </table>
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
              <td class="px-2 py-1.5 truncate max-w-[150px] text-ink-3">{{ v.shipment }}</td>
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
import StatCard from "@/components/StatCard.vue";
import LandedCostAllocModal from "@/components/LandedCostAllocModal.vue";

const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt0 = (n) => Number(n || 0).toLocaleString("en-US", { maximumFractionDigits: 0 });
const { can } = useAuth();
const canWrite = computed(() => can("post_entries"));
const toast = useToast();

const ov = ref({});
const recs = ref([]);
const inbox = ref([]);
const posted = ref([]);
const sel = ref([]);
const modal = ref(null);
const loading = ref(true);
const busy = ref("");
const ccy = ref("MAD");
const clearingOk = computed(() => Math.abs(Number(ov.value.clearing_balance || 0)) < 1);
const onPlCount = computed(() => posted.value.filter((v) => v.on_pl).length);

async function load() {
  loading.value = true;
  try {
    const c = currentCompany();
    const [o, u, ib, lc] = await Promise.all([
      api.call("accounting_portal.api.landed_pipeline.pipeline_overview", { company: c }),
      api.call("accounting_portal.api.landed_pipeline.receipts_uncovered", { company: c, limit: 100 }),
      api.call("accounting_portal.api.landed_pipeline.charge_inbox", { company: c }),
      api.call("accounting_portal.api.items.list_landed_costs", { company: c, limit: 200 }),
    ]);
    ov.value = o || {}; recs.value = u || []; inbox.value = ib || [];
    posted.value = (lc || []).filter((v) => v.status === "Posted");
  } catch (e) { toast.error(String(e?.message || e).slice(0, 160)); }
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
    load();
  } catch (e) { toast.error(String(e?.message || e).slice(0, 200)); }
  finally { busy.value = ""; }
}

function toggle(name) { const i = sel.value.indexOf(name); if (i >= 0) sel.value.splice(i, 1); else sel.value.push(name); }
function toggleAll() { sel.value = sel.value.length === recs.value.length ? [] : recs.value.map((r) => r.name); }

function openAlloc() {
  if (!sel.value.length) return;
  modal.value = { receipts: [...sel.value], charges: inbox.value, clearing_account: ov.value.clearing_account };
}
function onPosted() { sel.value = []; load(); }
</script>
