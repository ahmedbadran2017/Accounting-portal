<template>
  <!-- B4 v2: two-channel landed basis — AIR (date-banded tariff) vs SEA (pooled
       bills ÷ sea kg), classified per Purchase Receipt (one PR = one shipment).
       Shared between the Cost Control Tower (step ②) and the Landed Cockpit. -->
  <div v-if="sr" class="bg-white rounded-card border shadow-card overflow-hidden" :style="sr.frozen ? 'border-color:#a7f3d0' : 'border-color:#c7d2fe'">
    <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2 flex-wrap cursor-pointer" @click="open = !open">
      <span class="text-[13px] font-bold">{{ L("Landed basis","أساس التكلفة المحمَّلة","Base landed") }} {{ sr.year }}</span>
      <span v-if="sr.frozen" class="text-[10.5px] font-bold px-2 py-0.5 rounded-full" style="background:#ecfdf5;color:#047857">❄ {{ L("FROZEN","مجمّد","GELÉ") }}</span>
      <span v-else class="text-[10.5px] font-bold px-2 py-0.5 rounded-full" style="background:#eef2ff;color:#4338ca">{{ L("pending review","في انتظار المراجعة","à revoir") }}</span>
      <span class="text-[11px] text-ink-muted flex-1">
        🛫 {{ L("air","جوي","air") }} {{ fmt0(sr.air.kg) }}kg ≈ {{ fmt0(sr.air.cost) }} ·
        🚢 {{ L("sea","بحري","mer") }} {{ fmt0(sr.sea.kg) }}kg @ {{ sr.sea.rate_kg }}/kg ({{ L("pool","مجمّع","pool") }} {{ fmt0(sr.sea.pool) }})
      </span>
      <span class="text-ink-3">{{ open ? "▾" : "▸" }}</span>
    </div>

    <div v-if="open" class="p-4 space-y-3.5">
      <!-- A) Air tariff bands -->
      <div>
        <div class="text-[11px] font-bold text-ink-2 mb-1.5">🛫 {{ L("Air tariff (door-to-door, MAD/kg) — date bands","تعريفة الجوي (door-to-door درهم/كجم) — فترات","Tarif aérien") }}</div>
        <div class="flex items-center gap-2 flex-wrap">
          <span v-for="(r, i) in airRates" :key="i" class="inline-flex items-center gap-1.5 border border-line rounded-[8px] px-2 py-1 text-[11.5px] tnum">
            {{ L("from","من","dès") }} <input type="date" v-model="r.from" :disabled="!canWrite || !!sr.frozen" class="border-0 outline-none bg-transparent w-[120px]" @change="saveAirRates" />
            → <input type="number" step="1" v-model.number="r.rate" :disabled="!canWrite || !!sr.frozen" class="border-0 outline-none bg-transparent w-[52px] font-bold" @change="saveAirRates" /> /kg
            <button v-if="canWrite && !sr.frozen" class="text-sale text-[12px]" @click="airRates.splice(i,1); saveAirRates()">✕</button>
          </span>
          <button v-if="canWrite && !sr.frozen" class="h-[26px] px-2.5 rounded-[7px] text-[11px] font-bold border border-line text-ink-2 hover:bg-app-warm"
                  @click="airRates.push({ from: '', rate: null })">+ {{ L("band","فترة","période") }}</button>
        </div>
        <div v-if="!airRates.length" class="text-[11px] text-amber-700 mt-1">{{ L("Add the tariff bands (e.g. 100 → 110 → 126 MAD/kg with their start dates).","ضيفوا فترات التعريفة (مثال: 100 ثم 110 ثم 126 بتواريخ بدايتها).","Ajouter les périodes.") }}</div>
      </div>

      <!-- B) Sea pool (accounts) -->
      <div>
        <div class="text-[11px] font-bold text-ink-2 mb-1.5">🚢 {{ L("Sea pool — inbound bills included","مجمّع البحري — الفواتير الداخلة","Pool maritime") }}</div>
        <table class="w-full text-[11.5px] border border-line rounded-[8px] overflow-hidden">
          <tbody>
            <tr v-for="r in sr.pool_rows" :key="r.account" class="border-t border-line-hair first:border-0" :style="r.included ? '' : 'opacity:.55'">
              <td class="px-3 py-1.5 truncate max-w-[250px]">{{ r.account }}<span class="text-[10px] text-ink-muted"> · {{ r.entries }}</span></td>
              <td class="px-3 py-1.5 text-end tnum font-semibold">{{ fmt0(r.net) }}</td>
              <td class="px-3 py-1.5 text-center w-[90px]">
                <span class="text-[10px] font-bold px-1.5 py-0.5 rounded-full"
                      :style="r.suggested==='inbound' ? 'background:#ecfdf5;color:#047857' : r.suggested==='outbound' ? 'background:#fef2f2;color:#b91c1c' : 'background:#fffbeb;color:#b45309'">
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

      <!-- C) Shipment (PR) classification -->
      <div>
        <div class="text-[11px] font-bold text-ink-2 mb-1.5">📦 {{ L("Shipments — each Purchase Receipt = one shipment; set its channel","الشحنات — كل استلام = شحنة؛ حدّدوا قناتها","Expéditions") }} ({{ sr.receipts.length }})</div>
        <div class="border border-line rounded-[8px] overflow-hidden max-h-[300px] overflow-y-auto">
          <table class="w-full text-[11.5px]">
            <thead><tr style="background:#fafaf9" class="sticky top-0">
              <th class="px-3 py-1.5 text-start text-[10px] font-bold text-ink-muted">{{ L("Receipt","الاستلام","Réception") }}</th>
              <th class="px-3 py-1.5 text-start text-[10px] font-bold text-ink-muted">{{ L("Supplier","المورّد","Fourn.") }}</th>
              <th class="px-3 py-1.5 text-end text-[10px] font-bold text-ink-muted">kg</th>
              <th class="px-3 py-1.5 text-center text-[10px] font-bold text-ink-muted">{{ L("Channel","القناة","Canal") }}</th>
              <th class="px-3 py-1.5 text-end text-[10px] font-bold text-ink-muted">{{ L("Landed","الشحن","Landed") }}</th>
            </tr></thead>
            <tbody>
              <tr v-for="r in sr.receipts" :key="r.name" class="border-t border-line-hair">
                <td class="px-3 py-1.5 font-mono text-[10.5px] whitespace-nowrap">{{ r.name }}<div class="text-[10px] text-ink-muted font-sans">{{ r.dt }}</div></td>
                <td class="px-3 py-1.5 truncate max-w-[130px]">{{ r.supplier }}</td>
                <td class="px-3 py-1.5 text-end tnum">{{ fmt0(r.kg) }}</td>
                <td class="px-3 py-1.5 text-center whitespace-nowrap">
                  <button class="text-[10.5px] font-bold px-2 py-0.5 rounded-s-full border"
                          :style="r.channel==='air' ? 'background:#eef2ff;color:#4338ca;border-color:#c7d2fe' : 'opacity:.45;border-color:#e7e5e4'"
                          :disabled="!canWrite || !!sr.frozen" @click="setChannel(r, 'air')">🛫</button>
                  <button class="text-[10.5px] font-bold px-2 py-0.5 rounded-e-full border"
                          :style="r.channel==='sea' ? 'background:#ecfeff;color:#0e7490;border-color:#a5f3fc' : 'opacity:.45;border-color:#e7e5e4'"
                          :disabled="!canWrite || !!sr.frozen" @click="setChannel(r, 'sea')">🚢</button>
                </td>
                <td class="px-3 py-1.5 text-end tnum font-semibold">{{ fmt0(r.landed) }} <span class="text-[10px] text-ink-muted">@{{ r.rate_kg }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Freeze -->
      <div class="flex items-center gap-2 flex-wrap pt-1 border-t border-line-hair">
        <span class="text-[11px] text-ink-muted flex-1">
          {{ L("Freeze locks the tariff, the pool and the channel map — Verify & Fix then adds each item's landed (its receipts' air/sea mix) on top of the product cost.",
               "التجميد يقفل التعريفة والمجمّع وتصنيف الشحنات — بعدها شاشة التحقق تضيف شحن كل صنف (حسب شحناته جوي/بحري) فوق تكلفة المنتج.",
               "Geler fige tout.") }}
        </span>
        <button v-if="canWrite && !sr.frozen" class="h-[30px] px-3.5 rounded-[8px] text-[11.5px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand disabled:opacity-50"
                :disabled="busy" @click="freezeBasis">❄ {{ L("Freeze basis","جمّد الأساس","Geler") }}</button>
        <button v-if="canWrite && sr.frozen" class="h-[30px] px-3 rounded-[8px] text-[11.5px] font-bold border border-line text-ink-2 hover:bg-app-warm disabled:opacity-50"
                :disabled="busy" @click="unfreezeBasis">{{ L("Unfreeze","فكّ التجميد","Dégeler") }}</button>
        <span v-if="sr.frozen" class="text-[10px] text-ink-3">{{ sr.frozen.by }} · {{ sr.frozen.on }}</span>
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
const toast = useToast();

const LP = "accounting_portal.api.landed_prep";
const sr = ref(null);
const airRates = ref([]);
const open = ref(props.startOpen);
const busy = ref(false);

async function load() {
  try {
    const r = await api.call(`${LP}.shipment_review`, { company: currentCompany() }, { fresh: true });
    sr.value = r;
    airRates.value = (r.air_rates || []).map((x) => ({ ...x }));
  } catch (e) { sr.value = null; }
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

async function togglePool(r) {
  try {
    await api.call(`${LP}.set_pool_include`, { company: currentCompany(), account: r.account, included: r.included ? 0 : 1 });
    await load(); emit("changed");
  } catch (e) { toast.error(e.message || "Failed"); await load(); }
}

async function setChannel(r, ch) {
  if (r.channel === ch) return;
  try {
    await api.call(`${LP}.set_pr_channel`, { company: currentCompany(), pr: r.name, channel: ch });
    await load(); emit("changed");
  } catch (e) { toast.error(e.message || "Failed"); await load(); }
}

async function freezeBasis() {
  if (!window.confirm(L(
    "Freeze the landed basis (air tariff + sea rate + channel map)? Verify & Fix will start applying full costs.",
    "تجميد الأساس (تعريفة الجوي + سعر البحري + تصنيف الشحنات)؟ شاشة التحقق هتبدأ تطبّق التكلفة الكاملة.",
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
