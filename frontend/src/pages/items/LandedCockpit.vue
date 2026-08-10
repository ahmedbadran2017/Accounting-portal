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
const sel = ref([]);
const modal = ref(null);
const loading = ref(true);
const ccy = ref("MAD");
const clearingOk = computed(() => Math.abs(Number(ov.value.clearing_balance || 0)) < 1);

async function load() {
  loading.value = true;
  try {
    const c = currentCompany();
    const [o, u, ib] = await Promise.all([
      api.call("accounting_portal.api.landed_pipeline.pipeline_overview", { company: c }),
      api.call("accounting_portal.api.landed_pipeline.receipts_uncovered", { company: c, limit: 100 }),
      api.call("accounting_portal.api.landed_pipeline.charge_inbox", { company: c }),
    ]);
    ov.value = o || {}; recs.value = u || []; inbox.value = ib || [];
  } catch (e) { toast.error(String(e?.message || e).slice(0, 160)); }
  finally { loading.value = false; }
}
load();

function toggle(name) { const i = sel.value.indexOf(name); if (i >= 0) sel.value.splice(i, 1); else sel.value.push(name); }
function toggleAll() { sel.value = sel.value.length === recs.value.length ? [] : recs.value.map((r) => r.name); }

function openAlloc() {
  if (!sel.value.length) return;
  modal.value = { receipts: [...sel.value], charges: inbox.value, clearing_account: ov.value.clearing_account };
}
function onPosted() { sel.value = []; load(); }
</script>
