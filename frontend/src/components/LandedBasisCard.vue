<template>
  <!-- Landed basis — the RECONCILIATION + FREEZE view only. The daily work
       (attach bills per shipment, confirm air rates, verify lines) happens in
       Purchases → Shipments and the SKU page; freezing is required ONLY for
       the monthly COGS true-ups. -->
  <div v-if="loadErr && !sr" class="bg-white rounded-card border border-line shadow-card px-4 py-3 flex items-center gap-2">
    <span class="text-[12px] text-sale font-semibold">{{ L("Couldn't load the landed basis.","معرفناش نحمّل أساس الشحن.","Échec de chargement.") }}</span>
    <button class="h-[26px] px-2.5 rounded-[7px] text-[10.5px] font-bold border border-line text-ink-2 hover:bg-app-warm" @click="load">{{ L("Retry","إعادة المحاولة","Réessayer") }}</button>
  </div>
  <div v-else-if="sr" class="bg-white rounded-card border shadow-card overflow-hidden" :style="sr.frozen ? 'border-color:#a7f3d0' : 'border-color:#e7e5e4'">
    <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2 flex-wrap cursor-pointer" @click="open = !open">
      <span class="text-[13px] font-bold">{{ L("Landed basis (reconciliation & freeze)","أساس الشحن (التسوية والتجميد)","Base landed (réconciliation)") }} {{ sr.year }}</span>
      <span v-if="sr.frozen" class="text-[10.5px] font-bold px-2 py-0.5 rounded-full" style="background:#ecfdf5;color:#047857">❄ {{ L("FROZEN","مجمّد","GELÉ") }}</span>
      <span v-if="sr.frozen && sr.recon.post_freeze_receipts" class="text-[10.5px] font-bold px-2 py-0.5 rounded-full" style="background:#fffbeb;color:#b45309"
            :title="L('Shipments received after the freeze carry no landed in the frozen snapshot — unfreeze and re-freeze to refresh it.','شحنات وصلت بعد التجميد مش جوه اللقطة المجمّدة — فكّوا وجمّدوا تاني لتحديثها.','Expéditions reçues après le gel.')">
        ⚠ {{ sr.recon.post_freeze_receipts }} {{ L("new shipments since freeze","شحنات جديدة بعد التجميد","depuis le gel") }}</span>
      <span class="text-[11px] text-ink-muted flex-1">
        {{ L("bills","فواتير","factures") }} {{ fmt0(sr.recon.bills_total) }} ·
        {{ L("on shipments","على الشحنات","sur expéditions") }} {{ fmt0(sr.recon.actual_total) }} ·
        <b :style="sr.recon.unallocated_count ? 'color:#b45309' : 'color:#047857'">{{ L("unallocated","غير موزَّع","non alloué") }} {{ fmt0(sr.recon.unallocated) }} ({{ sr.recon.unallocated_count }})</b>
      </span>
      <span class="text-ink-3">{{ open ? "▾" : "▸" }}</span>
    </div>

    <div v-if="open" class="p-4 space-y-3.5">
      <div class="text-[11px] text-ink-muted -mt-1"
           :title="L('Attach bills / confirm rates in Purchases → Shipments or on the product page. Freezing is needed only before posting monthly true-ups.','الإرفاق واعتماد الأسعار من المشتريات (الشحنات) أو صفحة المنتج. التجميد مطلوب فقط قبل ترحيل تسويات الشهور.','Le travail se fait dans Expéditions / page produit.')">
        {{ L("Reconciliation only: entered bills vs what shipments carry + the air cross-check.","للتسوية بس: الفواتير المُدخلة مقابل المتحمّل على الشحنات + الفحص التقاطعي للجوي.","Réconciliation uniquement.") }}
      </div>

      <!-- freight bills (status + exclude only — allocation happens in Shipments) -->
      <div>
        <div class="text-[11px] font-bold text-ink-2 mb-1.5">🧾 {{ L("Freight bills on the included accounts","فواتير الشحن على الحسابات المفعّلة","Factures fret") }}</div>
        <div class="border border-line rounded-[8px] overflow-hidden max-h-[240px] overflow-y-auto">
          <table class="w-full text-[11.5px]">
            <thead><tr style="background:#fafaf9" class="sticky top-0">
              <th class="px-3 py-1.5 text-start text-[10px] font-bold text-ink-muted">{{ L("Bill","الفاتورة","Facture") }}</th>
              <th class="px-3 py-1.5 text-start text-[10px] font-bold text-ink-muted">{{ L("Supplier / account","المورّد / الحساب","Fourn.") }}</th>
              <th class="px-3 py-1.5 text-end text-[10px] font-bold text-ink-muted">{{ L("Amount","المبلغ","Montant") }}</th>
              <th class="px-3 py-1.5 text-center text-[10px] font-bold text-ink-muted">{{ L("Covers","بتغطي","Couvre") }}</th>
              <th class="px-3 py-1.5"></th>
            </tr></thead>
            <tbody>
              <tr v-for="b in sortedBills" :key="b.voucher" class="border-t border-line-hair first:border-0" :style="b.excluded ? 'opacity:.45' : b.prs.length ? '' : 'background:#fffbeb'">
                <td class="px-3 py-1.5 font-mono text-[10.5px] whitespace-nowrap" dir="ltr">{{ b.voucher }}<div class="text-[10px] text-ink-muted font-sans">{{ b.dt }}</div></td>
                <td class="px-3 py-1.5"><div class="truncate max-w-[180px]">{{ b.supplier || "—" }}</div><div class="text-[10px] text-ink-muted truncate max-w-[180px]">{{ b.account }}</div></td>
                <td class="px-3 py-1.5 text-end tnum font-semibold">{{ fmt0(b.amount) }}</td>
                <td class="px-3 py-1.5 text-center">
                  <span v-if="b.excluded" class="text-[10px] font-bold px-1.5 py-0.5 rounded-full" style="background:#f5f5f4;color:#78716c">{{ L("not freight","مش شحن","hors fret") }}</span>
                  <span v-else-if="b.prs.length" class="text-[10px] font-bold px-1.5 py-0.5 rounded-full" style="background:#ecfdf5;color:#047857">{{ b.prs.length }} {{ L("shipment(s)","شحنة","exp.") }}</span>
                  <span v-else class="text-[10px] font-bold px-1.5 py-0.5 rounded-full" style="background:#fffbeb;color:#b45309">{{ L("unallocated","غير موزعة","non allouée") }}</span>
                </td>
                <td class="px-3 py-1.5 text-end">
                  <button v-if="canWrite && !sr.frozen" class="text-[10.5px] px-1.5 py-1 rounded-[6px] border border-line text-ink-3 hover:bg-app-warm"
                          :title="b.excluded ? L('Restore — it IS a freight bill','رجّعها — دي فاتورة شحن','Restaurer') : L('Exclude — not a freight bill','استبعدها — مش فاتورة شحن','Exclure')"
                          @click="toggleExclude(b)">{{ b.excluded ? "↺" : "✕" }}</button>
                </td>
              </tr>
              <tr v-if="!sr.bills.length"><td colspan="5" class="px-3 py-3 text-center text-[11px] text-ink-muted">{{ L("No freight bills yet — enter them from Purchases → New bill.","لسه مفيش فواتير شحن — دخّلوها من المشتريات → فاتورة جديدة.","Aucune facture.") }}</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- air tariff bands (prefills the per-shipment rate) + cross-check -->
      <div>
        <div class="text-[11px] font-bold text-ink-2 mb-1.5">🛫 {{ L("Air tariff bands (MAD/kg) — prefill for the per-shipment rate confirm","تعريفة الجوي بالفترات (درهم/كجم) — بتتعبّى تلقائيًا في اعتماد سعر كل شحنة","Barème aérien") }}</div>
        <div class="flex items-center gap-2 flex-wrap">
          <span v-for="(r, i) in airRates" :key="i" class="inline-flex items-center gap-1.5 border border-line rounded-[8px] px-2 py-1 text-[11.5px] tnum" dir="ltr">
            {{ L("from","من","dès") }} <input type="date" v-model="r.from" :disabled="!canWrite || !!sr.frozen" class="border-0 outline-none bg-transparent w-[120px]" @change="saveAirRates" />
            → <input type="number" step="1" v-model.number="r.rate" :disabled="!canWrite || !!sr.frozen" class="border-0 outline-none bg-transparent w-[52px] font-bold" @change="saveAirRates" /> /kg
            <button v-if="canWrite && !sr.frozen" class="text-sale text-[12px]" @click="airRates.splice(i,1); saveAirRates()">✕</button>
          </span>
          <button v-if="canWrite && !sr.frozen" class="h-[26px] px-2.5 rounded-[7px] text-[11px] font-bold border border-line text-ink-2 hover:bg-app-warm"
                  @click="airRates.push({ from: '', rate: null })">+ {{ L("band","فترة","période") }}</button>
        </div>
        <div class="text-[11px] mt-1.5" :style="crossOk ? 'color:#047857' : 'color:#b45309'">
          {{ L("Cross-check:","الفحص التقاطعي:","Contrôle :") }}
          Σ({{ L("air kg × rate","كجم جوي × السعر","kg air × tarif") }}) = {{ fmt0(sr.crosscheck.air_tariff_cost) }}
          {{ L("vs air bills allocated","مقابل فواتير الجوي الموزعة","vs factures air") }} = {{ fmt0(sr.crosscheck.air_bills) }}
          <template v-if="!crossOk"> — {{ L("gap: bills still missing or a rate is off","فيه فرق: فواتير ناقصة أو سعر محتاج مراجعة","écart à résoudre") }}</template>
          <template v-else> ✓</template>
        </div>
      </div>

      <!-- bill-source accounts -->
      <div>
        <div class="text-[11px] font-bold text-ink-2 mb-1.5">🗂 {{ L("Freight accounts (bill sources)","حسابات الشحن (مصادر الفواتير)","Comptes fret") }}</div>
        <table class="w-full text-[11.5px] border border-line rounded-[8px] overflow-hidden">
          <thead><tr style="background:#fafaf9">
            <th class="px-3 py-1.5 text-start text-[10px] font-bold text-ink-muted">{{ L("Account","الحساب","Compte") }}</th>
            <th class="px-3 py-1.5 text-end text-[10px] font-bold text-ink-muted">{{ L("Net","الصافي","Net") }}</th>
            <th class="px-3 py-1.5 text-center text-[10px] font-bold text-ink-muted">{{ L("Type","النوع","Type") }}</th>
            <th class="px-3 py-1.5 text-center text-[10px] font-bold text-ink-muted">{{ L("Include","تفعيل","Inclure") }}</th>
          </tr></thead>
          <tbody>
            <tr v-for="r in sr.pool_rows" :key="r.account" class="border-t border-line-hair first:border-0" :style="r.included ? '' : 'opacity:.55'">
              <td class="px-3 py-1.5 truncate max-w-[250px]">{{ r.account }}<span class="text-[10px] text-ink-muted"> · {{ r.entries }}</span></td>
              <td class="px-3 py-1.5 text-end tnum font-semibold">{{ fmt0(r.net) }}</td>
              <td class="px-3 py-1.5 text-center w-[90px]">
                <span class="text-[10px] font-bold px-1.5 py-0.5 rounded-full"
                      :style="r.suggested==='inbound' ? 'background:#ecfdf5;color:#047857' : r.suggested==='outbound' ? 'background:#f5f5f4;color:#78716c' : 'background:#fffbeb;color:#b45309'">
                  {{ r.suggested==='inbound' ? L('inbound','وارد','entrant') : r.suggested==='outbound' ? L('outbound','صادر','sortant') : L('review','مراجعة','revue') }}
                </span>
              </td>
              <td class="px-3 py-1.5 text-center w-[46px]">
                <input type="checkbox" :checked="r.included" :disabled="!canWrite || !!sr.frozen"
                       class="accent-accent w-3.5 h-3.5 cursor-pointer" @change="togglePool(r)" />
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Freeze (true-up prerequisite) -->
      <div class="flex items-center gap-2 flex-wrap pt-1 border-t border-line-hair">
        <span class="text-[11px] text-ink-muted flex-1">
          <span :title="L('Item fixes do NOT need the freeze — they gate on per-item shipment completeness.','تظبيط الأصناف مش محتاج التجميد — بوابته اكتمال شحنات الصنف.','Les corrections ne dépendent pas du gel.')">
            {{ L("Freeze snapshots every shipment's cost — required only for the monthly true-ups.","التجميد بياخد لقطة بتكلفة كل شحنة — مطلوب فقط لتسويات الشهور.","Gel requis uniquement pour les régularisations.") }}</span>
        </span>
        <button v-if="canFreeze && !sr.frozen" class="h-[30px] px-3.5 rounded-[8px] text-[11.5px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand disabled:opacity-50"
                :disabled="busy || !!sr.recon.unallocated_count"
                :title="sr.recon.unallocated_count ? L('Blocked: unallocated bills','متقفل: فيه فواتير غير موزَّعة','Bloqué : factures non allouées') : ''"
                @click="freezeBasis">❄ {{ L("Freeze basis","جمّد الأساس","Geler") }}</button>
        <button v-if="canFreeze && sr.frozen" class="h-[30px] px-3 rounded-[8px] text-[11.5px] font-bold border border-line text-ink-2 hover:bg-app-warm disabled:opacity-50"
                :disabled="busy" @click="unfreezeBasis">{{ L("Unfreeze","فكّ التجميد","Dégeler") }}</button>
        <span v-if="!canFreeze" class="text-[10px] text-ink-3">{{ L("Freezing is Super-Admin only","التجميد للسوبر أدمن فقط","Gel : Super-Admin uniquement") }}</span>
        <span v-if="sr.frozen" class="text-[10px] text-ink-3" dir="ltr">{{ sr.frozen.by }} · {{ sr.frozen.on }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from "vue";
import { useI18n } from "vue-i18n";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useAuth } from "@/composables/useAuth";
import { useToast } from "@/composables/useToast";

const emit = defineEmits(["changed"]);
const props = defineProps({ startOpen: { type: Boolean, default: false } });
const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt0 = (n) => Number(n || 0).toLocaleString("en-US", { maximumFractionDigits: 0 });
const { can } = useAuth();
const canWrite = computed(() => can("post_entries"));
const canFreeze = computed(() => can("manage_users"));
const toast = useToast();

const LP = "accounting_portal.api.landed_prep";
const sr = ref(null);
const loadErr = ref(false);
const airRates = ref([]);
const open = ref(props.startOpen);
const busy = ref(false);

const sortedBills = computed(() =>
  [...(sr.value?.bills || [])].sort((a, b) =>
    (a.excluded ? 2 : a.prs.length ? 1 : 0) - (b.excluded ? 2 : b.prs.length ? 1 : 0)));
const crossOk = computed(() => {
  const c = sr.value?.crosscheck || {};
  const a = Number(c.air_tariff_cost || 0), b = Number(c.air_bills || 0);
  if (!a && !b) return true;
  return Math.abs(a - b) <= 0.15 * Math.max(a, b);
});

async function load() {
  try {
    const r = await api.call(`${LP}.shipment_review`, { company: currentCompany() }, { fresh: true });
    sr.value = r;
    const editing = airRates.value.some((x) => !x.from || !(x.rate > 0));
    if (!editing) airRates.value = (r.air_rates || []).map((x) => ({ ...x }));
    loadErr.value = false;
  } catch (e) { loadErr.value = true; }
}
load();

let t = null;
function saveAirRates() {
  clearTimeout(t);
  t = setTimeout(async () => {
    try {
      const clean = airRates.value.filter((r) => r.from && r.rate > 0);
      await api.call(`${LP}.set_air_rates`, { rates: JSON.stringify(clean) });
      await load(); emit("changed");
    } catch (e) { toast.error(e.message || "Failed"); await load(); }
  }, 400);
}

async function toggleExclude(b) {
  if (busy.value) return;
  busy.value = true;
  try {
    await api.call(`${LP}.exclude_bill`, { company: currentCompany(), voucher: b.voucher, excluded: b.excluded ? 0 : 1 });
    await load(); emit("changed");
  } catch (e) { toast.error(e.message || "Failed"); }
  finally { busy.value = false; }
}

async function togglePool(r) {
  if (busy.value) return;
  busy.value = true;
  try {
    await api.call(`${LP}.set_pool_include`, { company: currentCompany(), account: r.account, included: r.included ? 0 : 1 });
    await load(); emit("changed");
  } catch (e) { toast.error(e.message || "Failed"); await load(); }
  finally { busy.value = false; }
}

async function freezeBasis() {
  if (!window.confirm(L(
    "Freeze the landed basis? It snapshots every shipment's current cost for the monthly true-ups.",
    "تجميد الأساس؟ بياخد لقطة بتكلفة كل شحنة لتسويات الشهور.",
    "Geler la base ?"))) return;
  busy.value = true;
  try { await api.call(`${LP}.freeze_basis`, { company: currentCompany() }); toast.success(L("Basis frozen","اتجمّد الأساس","Gelé")); await load(); emit("changed"); }
  catch (e) { toast.error(e.message || "Failed"); }
  finally { busy.value = false; }
}
async function unfreezeBasis() {
  busy.value = true;
  try { await api.call(`${LP}.unfreeze_basis`, {}); toast.success(L("Unfrozen","اتفك التجميد","Dégelé")); await load(); emit("changed"); }
  catch (e) { toast.error(e.message || "Failed"); }
  finally { busy.value = false; }
}
</script>
