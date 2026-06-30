<template>
  <div class="space-y-3.5">
    <button type="button" class="inline-flex items-center gap-1.5 h-8 px-3 rounded-chip border border-line-2 bg-white text-[12px] font-semibold text-ink-2 hover:bg-app-warm" @click="back">
      <Icon name="arrow" :size="13" class="rotate-180" />{{ L("Costing","حساب التكلفة","Coûts") }}
    </button>

    <TableLoading v-if="loading" :rows="4" />
    <div v-else-if="!d.item_code" class="bg-white rounded-card border border-line shadow-card px-4 py-14 text-center text-[12px] text-ink-muted">{{ L("Item not found.","الصنف غير موجود.","Introuvable.") }}</div>

    <template v-else>
      <!-- identity -->
      <div class="bg-white rounded-card border border-line shadow-card px-4 py-3.5 flex items-center gap-3.5 flex-wrap">
        <img v-if="d.image" :src="d.image" class="w-14 h-14 rounded-xl object-cover bg-app-warm shrink-0" />
        <span v-else class="w-14 h-14 rounded-xl bg-app-warm grid place-items-center shrink-0"><Icon name="grid" :size="20" color="#9a8f86" /></span>
        <div class="min-w-0">
          <div class="text-[14px] font-extrabold leading-snug">{{ d.item_name || d.item_code }}</div>
          <div class="text-[11.5px] text-ink-muted font-mono">{{ d.sku || d.item_code }}</div>
          <div class="text-[10.5px] text-ink-muted mt-0.5">{{ d.item_group }}<span v-if="d.country"> · {{ d.country }}</span><span v-if="d.brand"> · {{ d.brand }}</span></div>
        </div>
        <div class="ms-auto flex items-center gap-2 flex-wrap">
          <span v-if="d.flags.no_purchase" class="text-[10px] font-bold text-amber-700 bg-amber-50 border border-amber-200 rounded-chip px-2 py-1">{{ L("no purchase invoice","لا فاتورة شراء","sans facture") }}</span>
          <span v-if="d.flags.fx_off" class="text-[10px] font-bold text-rose-600 bg-rose-50 border border-rose-200 rounded-chip px-2 py-1 inline-flex items-center gap-1"><Icon name="alert" :size="10" />{{ L("FX rate off","سعر الصرف خطأ","change erroné") }}</span>
        </div>
      </div>

      <!-- result hero -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <div class="lg:col-span-2 bg-white rounded-card border border-line shadow-card px-4 py-4">
          <div class="flex items-end gap-4 flex-wrap">
            <div>
              <div class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Landed unit cost","تكلفة الوحدة المحمّلة","Coût unitaire") }}</div>
              <div class="text-[28px] font-extrabold tnum leading-none mt-1" style="color:#0f766e">{{ fmt(landed) }} <span class="text-[13px] text-ink-muted font-bold">{{ ccy }}</span></div>
              <div class="text-[10.5px] text-ink-muted mt-1">{{ L("current item cost","تكلفة الصنف الحالية","coût actuel") }}: <b class="tnum">{{ Number(d.valuation_rate)>0 ? fmt(d.valuation_rate) : "—" }}</b></div>
            </div>
            <button v-if="canWrite && landed>0" type="button" :disabled="saving" class="inline-flex items-center gap-1.5 h-9 px-3.5 rounded-chip text-[12px] font-bold text-white bg-teal-700 hover:bg-teal-800 disabled:opacity-60 self-center" @click="saveCost">
              <Icon :name="saving ? 'clock' : 'check'" :size="14" />{{ saving ? L("Saving…","جارٍ…","…") : L("Set as item cost","حفظ كتكلفة","Définir") }}
            </button>
            <div v-if="bookLanded && Math.abs(bookLanded-landed)>0.5" class="text-[11px]">
              <div class="text-ink-muted">{{ L("as booked","كما هو مسجّل","au livre") }}</div>
              <div class="tnum font-bold text-rose-500 line-through">{{ fmt(bookLanded) }}</div>
            </div>
            <div v-if="d.sell" class="ms-auto text-end">
              <div class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Margin vs sell","الهامش","Marge") }}</div>
              <div class="text-[18px] font-extrabold tnum" :class="margin>=0 ? 'text-success-dark' : 'text-rose-600'">{{ fmt(margin) }} <span class="text-[11px] font-bold">({{ marginPct }}%)</span></div>
              <div class="text-[10px] text-ink-muted">{{ L("sell","بيع","vente") }} {{ fmt(d.sell) }} · {{ d.sell_src }}</div>
            </div>
          </div>
          <!-- breakdown bar -->
          <div class="mt-3.5">
            <div class="flex h-2.5 rounded-full overflow-hidden bg-app-warm">
              <div class="bg-teal-600" :style="`width:${pct(productCost)}%`" :title="L('Product','المنتج','Produit')"></div>
              <div class="bg-sky-500" :style="`width:${pct(freightUnit)}%`" :title="L('Freight','الشحن','Fret')"></div>
            </div>
            <div class="flex items-center gap-4 mt-2 text-[11px]">
              <span class="inline-flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-sm bg-teal-600"></span>{{ L("Product","المنتج","Produit") }} <b class="tnum">{{ fmt(productCost) }}</b></span>
              <span class="inline-flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-sm bg-sky-500"></span>{{ L("Freight","الشحن","Fret") }} <b class="tnum">{{ fmt(freightUnit) }}</b></span>
            </div>
          </div>
        </div>

        <!-- inputs -->
        <div class="bg-white rounded-card border border-line shadow-card px-4 py-4 space-y-3">
          <div>
            <label class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Exchange rate","سعر الصرف","Change") }}</label>
            <div class="flex gap-1 bg-app-warm/60 rounded-chip p-0.5 mt-1">
              <button class="flex-1 px-2 py-1 rounded-lg text-[11.5px] font-semibold" :class="fxMode==='live' ? 'bg-white shadow-card text-accent-dark' : 'text-ink-3'" @click="fxMode='live'">{{ L("Corrected","مصحّح","Corrigé") }}</button>
              <button class="flex-1 px-2 py-1 rounded-lg text-[11.5px] font-semibold" :class="fxMode==='book' ? 'bg-white shadow-card text-accent-dark' : 'text-ink-3'" @click="fxMode='book'">{{ L("As booked","مسجّل","Au livre") }}</button>
            </div>
          </div>
          <div>
            <label class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Weight (kg)","الوزن (كجم)","Poids (kg)") }}</label>
            <input v-model.number="weight" type="number" step="0.001" min="0" class="w-full h-9 mt-1 bg-app-warm/40 border rounded-[10px] px-3 text-[13px] tnum focus:outline-none focus:bg-white" :class="weightBad ? 'border-rose-300' : 'border-line-2 focus:border-accent/40'" />
            <div v-if="weightBad" class="text-[10px] text-rose-600 mt-1">{{ L("missing / implausible — check the item","ناقص / غير منطقي — راجع الصنف","manquant / improbable") }}</div>
          </div>
          <div>
            <label class="text-[10px] font-bold uppercase tracking-wider text-ink-muted flex items-center justify-between">{{ L("Freight / kg","شحن / كجم","Fret / kg") }}
              <button class="text-[10px] font-semibold text-accent-dark hover:underline" @click="freightPerKg = d.suggested_freight_per_kg">{{ L("suggest","اقتراح","suggéré") }} {{ d.suggested_freight_per_kg }}</button>
            </label>
            <input v-model.number="freightPerKg" type="number" step="0.1" min="0" class="w-full h-9 mt-1 bg-app-warm/40 border border-line-2 rounded-[10px] px-3 text-[13px] tnum focus:outline-none focus:border-accent/40 focus:bg-white" />
          </div>
          <p class="text-[10px] text-ink-muted leading-relaxed pt-1">{{ L("A calculator — nothing is written to the books yet. Posting the cost is a later step.","حاسبة — لسه مفيش كتابة للدفاتر. ترحيل التكلفة خطوة لاحقة.","Calculateur — rien n'est écrit.") }}</p>
        </div>
      </div>

      <!-- purchase basis -->
      <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
        <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><Icon name="truck" :size="14" color="#0b5c4f" /><span class="text-[12px] font-bold">{{ L("Purchase basis","أساس الشراء","Base d'achat") }}</span>
          <span class="text-[10px] text-ink-muted">{{ L("weighted avg","متوسط مرجّح","moy. pond.") }} · {{ d.purchases.length }} {{ L("lines","سطر","lignes") }}</span>
        </div>
        <div v-if="d.purchases.length" class="overflow-x-auto">
          <table class="w-full text-[12px]">
            <thead><tr style="background:#fafaf9" class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">
              <th class="px-4 py-2 text-start">{{ L("Invoice","الفاتورة","Facture") }}</th>
              <th class="px-3 py-2 text-start hidden sm:table-cell">{{ L("Supplier","المورّد","Fourn.") }}</th>
              <th class="px-3 py-2 text-end">{{ L("Qty","كمية","Qté") }}</th>
              <th class="px-3 py-2 text-end">{{ L("Rate","سعر","Taux") }}</th>
              <th class="px-3 py-2 text-end">{{ L("Booked FX","صرف مسجّل","FX livre") }}</th>
              <th class="px-3 py-2 text-end">{{ L("Live FX","صرف حيّ","FX réel") }}</th>
              <th class="px-4 py-2 text-end">{{ L("Unit MAD","وحدة درهم","Unité") }}</th>
            </tr></thead>
            <tbody>
              <tr v-for="(p,i) in d.purchases" :key="i" class="border-t border-line-hair" :class="p.fx_off ? 'bg-rose-50/40' : ''">
                <td class="px-4 py-2 font-mono text-[11px]">{{ p.doc }}<div class="text-[10px] text-ink-muted">{{ p.dt }}</div></td>
                <td class="px-3 py-2 text-ink-2 hidden sm:table-cell truncate max-w-[140px]">{{ p.supplier }}</td>
                <td class="px-3 py-2 text-end tnum">{{ p.qty }}</td>
                <td class="px-3 py-2 text-end tnum whitespace-nowrap">{{ p.rate_fc }} {{ p.cur }}</td>
                <td class="px-3 py-2 text-end tnum" :class="p.fx_off ? 'text-rose-600 font-semibold line-through' : 'text-ink-3'">{{ p.book_fx }}</td>
                <td class="px-3 py-2 text-end tnum" :class="p.fx_off ? 'text-success-dark font-bold' : 'text-ink-3'">{{ p.live_fx || "—" }}</td>
                <td class="px-4 py-2 text-end tnum font-semibold">{{ fmt(fxMode==='live' ? p.rate_live : p.rate_book) }}</td>
              </tr>
            </tbody>
            <tfoot><tr class="border-t-2 border-line bg-app-warm/40 text-[12px] font-bold">
              <td class="px-4 py-2" colspan="6">{{ L("Weighted-average unit cost","متوسط تكلفة الوحدة","Coût moyen") }} ({{ fxMode==='live' ? L('corrected','مصحّح','corrigé') : L('booked','مسجّل','livre') }})</td>
              <td class="px-4 py-2 text-end tnum" style="color:#0f766e">{{ fmt(productCost) }}</td>
            </tr></tfoot>
          </table>
        </div>
        <div v-else class="px-4 py-8 text-center text-[12px] text-ink-muted">{{ L("No purchase invoice for this item — cost basis unknown.","لا فاتورة شراء لهذا الصنف.","Aucune facture d'achat.") }}</div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";
import { useAuth } from "@/composables/useAuth";
import { useToast } from "@/composables/useToast";

const { locale } = useI18n();
const { entityId } = useUi();
const { can } = useAuth();
const toast = useToast();
const canWrite = computed(() => can("manage_users"));
const saving = ref(false);
const route = useRoute();
const router = useRouter();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const d = ref({ purchases: [], flags: {} });
const loading = ref(true);
const code = computed(() => route.query.item);
const ccy = computed(() => d.value.currency || "MAD");

const fxMode = ref("live");
const weight = ref(0);
const freightPerKg = ref(0);

async function load() {
  if (!code.value) return;
  loading.value = true;
  try {
    d.value = await api.call("accounting_portal.api.landed_engine.item_landed_cost", { company: currentCompany(), item_code: code.value }) || { purchases: [], flags: {} };
    fxMode.value = "live";
    weight.value = Number(d.value.weight) || 0;
    freightPerKg.value = Number(d.value.freight_per_kg) || 0;
  } catch { d.value = { purchases: [], flags: {} }; }
  finally { loading.value = false; }
}
load();
watch(code, load);
watch(entityId, () => router.push({ path: "/accounting/items/costing" }));

const productCost = computed(() => Number(fxMode.value === "live" ? d.value.wavg_live : d.value.wavg_book) || 0);
const freightUnit = computed(() => +( (Number(freightPerKg.value) || 0) * (Number(weight.value) || 0) ).toFixed(3));
const landed = computed(() => +(productCost.value + freightUnit.value).toFixed(2));
const bookLanded = computed(() => +((Number(d.value.wavg_book) || 0) + (Number(d.value.suggested_freight_per_kg) || 0) * (Number(d.value.weight) || 0)).toFixed(2));
const margin = computed(() => d.value.sell ? +(d.value.sell - landed.value).toFixed(2) : 0);
const marginPct = computed(() => d.value.sell ? Math.round(margin.value / d.value.sell * 100) : 0);
const weightBad = computed(() => !(Number(weight.value) > 0) || Number(weight.value) > 20 || (Number(weight.value) > 0 && Number(weight.value) < 0.01));
const pct = (v) => { const t = productCost.value + freightUnit.value; return t > 0 ? Math.round((Number(v) || 0) / t * 100) : 0; };

function back() { router.push({ path: "/accounting/items/costing" }); }

async function saveCost() {
  if (saving.value || !(landed.value > 0)) return;
  const old = Number(d.value.valuation_rate) || 0;
  if (!window.confirm(L(
    `Set this item's cost (valuation rate) to ${fmt(landed.value)} ${ccy.value}? (was ${fmt(old)}). Logged in the audit trail; reversible.`,
    `تعيين تكلفة الصنف (valuation rate) إلى ${fmt(landed.value)} ${ccy.value}؟ (كانت ${fmt(old)}). مسجّل في سجل التدقيق وقابل للتراجع.`,
    `Définir le coût à ${fmt(landed.value)} ${ccy.value} ?`))) return;
  saving.value = true;
  try {
    await api.call("accounting_portal.api.landed_engine.set_item_cost", { company: currentCompany(), item_code: d.value.item_code, cost: landed.value, dry_run: 0 });
    d.value.valuation_rate = landed.value;
    toast.success(L("Cost saved", "تم حفظ التكلفة", "Coût enregistré"));
  } catch (e) {
    toast.error(L("Save failed", "فشل الحفظ", "Échec") + ": " + String(e?.message || e).slice(0, 120));
  } finally { saving.value = false; }
}
</script>
