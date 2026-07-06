<template>
  <div class="space-y-3.5">
    <div class="flex items-center gap-2 flex-wrap">
      <span class="text-[11px] text-ink-muted">{{ L("Every bin vs its FX-corrected landed benchmark. Fixing posts a Stock Reconciliation and ERPNext reposts later Delivery Notes' COGS — the retroactive fix.","كل مخزن مقارنةً بالتكلفة المصححة. التصحيح بيرحّل Stock Reconciliation وERPNext بيعيد حساب COGS للدليفري نوتس اللاحقة — تصحيح بأثر رجعي.","Chaque stock vs son coût corrigé.") }}</span>
      <button type="button" class="ms-auto text-[11px] font-semibold text-accent-dark hover:underline" @click="load">{{ L("Refresh","تحديث","Actualiser") }}</button>
    </div>

    <!-- summary -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <div class="bg-white rounded-card border border-line shadow-card px-4 py-3">
        <div class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Flagged bins","مخازن معلَّمة","Signalés") }}</div>
        <div class="text-[20px] font-extrabold tnum mt-0.5">{{ d.summary?.flagged ?? "—" }} <span class="text-[10px] text-ink-muted">/ {{ d.summary?.bins }}</span></div>
      </div>
      <div class="bg-white rounded-card border border-rose-200 shadow-card px-4 py-3">
        <div class="text-[10px] font-bold uppercase tracking-wider text-rose-600">{{ L("Overvalued","مقيَّم بالزيادة","Survalorisé") }}</div>
        <div class="text-[20px] font-extrabold tnum mt-0.5 text-rose-600">{{ money(d.summary?.overvalued_mad) }} <span class="text-[10px]">MAD</span></div>
      </div>
      <div class="bg-white rounded-card border border-amber-200 shadow-card px-4 py-3">
        <div class="text-[10px] font-bold uppercase tracking-wider text-amber-700">{{ L("Undervalued","مقيَّم بالنقص","Sous-valorisé") }}</div>
        <div class="text-[20px] font-extrabold tnum mt-0.5 text-amber-700">{{ money(d.summary?.undervalued_mad) }} <span class="text-[10px]">MAD</span></div>
      </div>
      <div class="bg-white rounded-card border border-line shadow-card px-4 py-3">
        <div class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Repost queue","طابور إعادة الحساب","File repost") }}</div>
        <div class="text-[13px] font-bold mt-1 flex items-center gap-2 flex-wrap">
          <span v-for="(n, s) in (rq.counts || {})" :key="s" class="px-2 py-0.5 rounded-chip text-[10px]" :class="s==='Failed' ? 'bg-rose-50 text-rose-700' : s==='Queued' ? 'bg-amber-50 text-amber-700' : 'bg-app-warm text-ink-3'">{{ s }} {{ n }}</span>
          <span v-if="!Object.keys(rq.counts || {}).length" class="text-[11px] text-ink-muted">{{ L("empty","فاضي","vide") }}</span>
        </div>
      </div>
    </div>

    <!-- repost jobs needing a kick -->
    <div v-if="(rq.rows || []).length" class="bg-white rounded-card border border-amber-200 shadow-card overflow-hidden">
      <div class="px-4 py-2.5 border-b border-line-hair text-[12px] font-bold flex items-center gap-2">
        <Icon name="clock" :size="14" color="#b45309" />{{ L("Repost jobs not finished","إعادة حسابات لسه ماخلصتش","Reposts en attente") }}
        <span class="text-[10px] text-ink-muted">{{ rq.rows.length }}</span>
      </div>
      <div class="overflow-x-auto"><table class="w-full text-[12px]">
        <tbody>
          <tr v-for="r in rq.rows" :key="r.name" class="border-t border-line-hair">
            <td class="px-4 py-2 font-mono text-[10.5px]">{{ r.name }}</td>
            <td class="px-3 py-2">{{ r.item_code || r.voucher_no }}</td>
            <td class="px-3 py-2 text-ink-3">{{ r.posting_date }}</td>
            <td class="px-3 py-2"><span class="px-2 py-0.5 rounded-chip text-[10px]" :class="r.status==='Failed' ? 'bg-rose-50 text-rose-700' : 'bg-amber-50 text-amber-700'">{{ r.status }}</span></td>
            <td class="px-3 py-2 text-end">
              <button v-if="canWrite && ['Queued','Failed'].includes(r.status)" type="button" class="h-7 px-2.5 rounded-chip text-[11px] font-bold text-white bg-amber-600 hover:bg-amber-700 disabled:opacity-40" :disabled="kicking===r.name" @click="kick(r)">{{ kicking===r.name ? '…' : L('Kick','ادفع','Relancer') }}</button>
            </td>
          </tr>
        </tbody>
      </table></div>
    </div>

    <!-- bins table -->
    <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
      <div class="px-4 py-2.5 border-b border-line-hair text-[12px] font-bold flex items-center gap-2">
        <Icon name="box" :size="14" color="#0b5c4f" />{{ L("Bins by distortion","المخازن حسب حجم التشويه","Stocks par écart") }}
        <label class="ms-auto inline-flex items-center gap-1.5 text-[11px] font-medium text-ink-3"><input type="checkbox" v-model="onlyFlagged" class="accent-emerald-700" />{{ L("flagged only","المعلَّم فقط","signalés") }}</label>
      </div>
      <TableLoading v-if="loading" :rows="8" />
      <div v-else class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead><tr style="background:#fafaf9" class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">
            <th class="px-4 py-2 text-start">{{ L("Item","الصنف","Article") }}</th>
            <th class="px-3 py-2 text-start">{{ L("Warehouse","المخزن","Dépôt") }}</th>
            <th class="px-3 py-2 text-end">{{ L("Qty","كمية","Qté") }}</th>
            <th class="px-3 py-2 text-end">{{ L("Current","الحالي","Actuel") }}</th>
            <th class="px-3 py-2 text-end">{{ L("Benchmark","المرجعي","Référence") }}</th>
            <th class="px-3 py-2 text-end">{{ L("Distortion","التشويه","Écart") }}</th>
            <th class="px-4 py-2 text-end">{{ L("Fix at rate / date","صحّح بسعر / تاريخ","Corriger") }}</th>
          </tr></thead>
          <tbody>
            <tr v-for="r in visible" :key="r.item_code + r.warehouse" class="border-t border-line-hair hover:bg-app-warm/40">
              <td class="px-4 py-2 max-w-[240px]">
                <router-link :to="{ path: '/accounting/items/costing', query: { item: r.item_code } }" class="hover:underline">
                  <div class="truncate font-medium">{{ r.item_name }}</div>
                  <div class="text-[10px] text-ink-muted font-mono">{{ r.sku || r.item_code }}</div>
                </router-link>
              </td>
              <td class="px-3 py-2 text-[11px] whitespace-nowrap">{{ r.warehouse.replace(/ - \w+$/, "") }}</td>
              <td class="px-3 py-2 text-end tnum">{{ Number(r.qty).toLocaleString() }}</td>
              <td class="px-3 py-2 text-end tnum font-semibold" :class="r.flag==='overvalued' ? 'text-rose-600' : r.flag==='undervalued' || r.flag==='zero_rate' ? 'text-amber-700' : ''">{{ money(r.vr) }}</td>
              <td class="px-3 py-2 text-end tnum">{{ r.benchmark != null ? money(r.benchmark) : "—" }}</td>
              <td class="px-3 py-2 text-end tnum whitespace-nowrap">
                <span v-if="r.dev_pct != null" :class="r.flag==='overvalued' ? 'text-rose-600' : r.flag==='undervalued' ? 'text-amber-700' : 'text-ink-3'">{{ money(r.distortion) }} <span class="text-[9.5px]">({{ r.dev_pct > 0 ? "+" : "" }}{{ r.dev_pct }}%)</span></span>
                <span v-else class="text-[10px] text-ink-muted">{{ r.flag === 'zero_rate' ? L('zero rate','سعر صفري','taux zéro') : L('no purchase basis','بدون أساس شراء','sans base') }}</span>
              </td>
              <td class="px-4 py-2 text-end whitespace-nowrap">
                <div v-if="canWrite && r.flag !== 'ok' && r.flag !== 'no_basis'" class="inline-flex items-center gap-1.5">
                  <input v-model.number="fixRate[key(r)]" type="number" step="0.01" min="0" class="w-[84px] h-7 bg-app-warm/40 border border-line-2 rounded-chip px-2 text-[11px] tnum text-end focus:outline-none" :placeholder="r.benchmark != null ? String(r.benchmark) : '0.00'" />
                  <input v-model="fixDate[key(r)]" type="date" :max="today" class="h-7 bg-app-warm/40 border border-line-2 rounded-chip px-1.5 text-[10.5px] focus:outline-none" />
                  <button type="button" class="h-7 px-2.5 rounded-chip text-[11px] font-bold text-white bg-emerald-600 hover:bg-emerald-700 disabled:opacity-40" :disabled="busy===key(r) || !(Number(fixRate[key(r)] ?? r.benchmark) > 0)" @click="fix(r)">{{ busy===key(r) ? '…' : L('Fix','صحّح','OK') }}</button>
                </div>
              </td>
            </tr>
            <tr v-if="!visible.length"><td colspan="7" class="px-4 py-8 text-center text-ink-muted">{{ L("Nothing flagged — valuations look consistent.","مفيش حاجة معلَّمة — التقييمات متسقة.","Rien à signaler.") }}</td></tr>
          </tbody>
        </table>
      </div>
      <div class="px-4 py-2 border-t border-line-hair text-[10.5px] text-ink-muted flex items-center gap-1.5">
        <Icon name="alert" :size="11" color="#9a8f86" />
        {{ L("Benchmark = FX-corrected purchase cost + freight","المرجعي = تكلفة الشراء المصححة + الشحن","Référence = coût corrigé + fret") }}
        <template v-if="d.freight">({{ d.freight.rate }}/kg · {{ L("weights known for","الوزن معروف لـ","poids") }} {{ d.freight.coverage_pct }}%)</template>
        · {{ L("corrections never post before","التصحيحات لا تُرحَّل قبل","jamais avant") }} {{ d.summary?.policy_floor }} ·
        {{ L("material fixes go to approval","التصحيحات الكبيرة بتروح للموافقة","gros montants → approbation") }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";
import { useAuth } from "@/composables/useAuth";
import { useToast } from "@/composables/useToast";
import { fmtAmount } from "@/utils/helpers";

const { locale } = useI18n();
const { entityId } = useUi();
const { can } = useAuth();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const money = (n) => fmtAmount(n);
const canWrite = computed(() => can("post_entries"));
const today = new Date().toISOString().slice(0, 10);

const d = ref({ rows: [] });
const rq = ref({ rows: [], counts: {} });
const loading = ref(true);
const onlyFlagged = ref(true);
const busy = ref(""), kicking = ref("");
const fixRate = reactive({}), fixDate = reactive({});
const key = (r) => r.item_code + "|" + r.warehouse;

const visible = computed(() => {
  const rows = d.value.rows || [];
  return onlyFlagged.value ? rows.filter((r) => !["ok", "no_basis"].includes(r.flag)) : rows;
});

async function load() {
  loading.value = true;
  try {
    [d.value, rq.value] = await Promise.all([
      api.call("accounting_portal.api.valuation.valuation_review", { company: currentCompany() }, { fresh: true }),
      api.call("accounting_portal.api.valuation.repost_queue", { company: currentCompany() }, { fresh: true }),
    ]);
  } catch { d.value = { rows: [] }; }
  finally { loading.value = false; }
}
load();
watch(entityId, load);

async function fix(r) {
  const k = key(r);
  const rate = Number(fixRate[k] ?? r.benchmark);
  if (!(rate > 0) || busy.value) return;
  const impact = Math.abs(rate - r.vr) * r.qty;
  if (!window.confirm(L(
    `Set ${r.item_code} @ ${r.warehouse} to ${money(rate)} (impact ~${money(impact)} MAD)? Later Delivery Notes will be reposted.`,
    `تصحيح ${r.item_code} في ${r.warehouse} إلى ${money(rate)} (أثر ~${money(impact)} درهم)؟ الدليفري نوتس اللاحقة هيتعاد حسابها.`,
    `Corriger à ${money(rate)} ?`))) return;
  busy.value = k;
  try {
    const res = await api.call("accounting_portal.api.valuation.correct_valuation", {
      company: currentCompany(), item_code: r.item_code, warehouse: r.warehouse,
      correct_rate: rate, effective_date: fixDate[k] || undefined,
    });
    if (res && res.status === "Proposed") toast.success(L("Sent for approval", "أُرسل للموافقة", "Envoyé"));
    else toast.success(L("Corrected — repost running", "اتصحح — إعادة الحساب شغالة", "Corrigé"));
    load();
  } catch (e) { toast.error(String(e?.message || e).slice(0, 180)); }
  finally { busy.value = ""; }
}

async function kick(r) {
  if (kicking.value) return;
  kicking.value = r.name;
  try {
    await api.call("accounting_portal.api.valuation.kick_repost", { name: r.name });
    toast.success(L("Enqueued", "اتدفع للطابور", "Relancé"));
    load();
  } catch (e) { toast.error(String(e?.message || e).slice(0, 180)); }
  finally { kicking.value = ""; }
}
</script>
