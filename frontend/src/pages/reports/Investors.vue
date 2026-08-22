<template>
  <div class="space-y-3.5">
    <!-- what the numbers can and cannot be used for, said before they are read -->
    <div class="rounded-[14px] px-4 py-3 border" style="background:#fffbeb;border-color:#fde68a">
      <div class="text-[12px] font-bold text-amber-900">
        {{ L("Provisional — the cost correction is still running","أرقام مبدئية — تصحيح التكلفة لسه جارٍ","Provisoire") }}
      </div>
      <div class="text-[11px] text-amber-800/80 mt-0.5">
        {{ L("Capital and drawings are facts and settle today. The cycle result moves while costs are being corrected, so agree the method now and the figure at close.",
             "رأس المال والمسحوبات حقائق ثابتة. نتيجة الدورة بتتحرك مع تصحيح التكاليف — فاتفق على المنهج دلوقتي والرقم عند الإقفال.",
             "Capital et retraits sont définitifs ; le résultat du cycle bouge encore.") }}
      </div>
    </div>

    <div v-if="loading" class="py-16 text-center text-[12px] text-ink-muted">{{ L("Loading…","جاري التحميل…","Chargement…") }}</div>
    <div v-else-if="err" class="py-16 text-center text-[12px]" style="color:#b91c1c">{{ err }}</div>

    <template v-else>
      <!-- who has money in -->
      <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
        <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2">
          <span class="text-[13px] font-bold">{{ L("Investors","المستثمرون","Investisseurs") }}</span>
          <span class="text-[10.5px] text-ink-muted">{{ list.length }}</span>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-[11.5px]">
            <thead><tr style="background:#fafaf9">
              <th class="px-3 py-2 text-start text-[10px] font-bold text-ink-muted">{{ L("Investor","المستثمر","Investisseur") }}</th>
              <th class="px-3 py-2 text-start text-[10px] font-bold text-ink-muted">{{ L("Entity","الكيان","Entité") }}</th>
              <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("Capital","رأس المال","Capital") }}</th>
              <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("Drawn","المسحوب","Retiré") }}</th>
              <th class="px-3 py-2 text-center text-[10px] font-bold text-ink-muted">{{ L("Terms","الشروط","Conditions") }}</th>
              <th class="px-3 py-2"></th>
            </tr></thead>
            <tbody>
              <tr v-for="i in list" :key="i.account" class="border-t border-line-hair hover:bg-[#fafaf9]">
                <td class="px-3 py-2 font-bold">{{ i.name }}</td>
                <td class="px-3 py-2 text-ink-muted">{{ i.company }}</td>
                <td class="px-3 py-2 text-end tnum" dir="ltr">{{ fmt(i.capital) }} <span class="text-[9.5px] text-ink-muted">{{ i.currency }}</span></td>
                <td class="px-3 py-2 text-end tnum" dir="ltr">{{ i.drawn ? fmt(i.drawn) : "—" }}</td>
                <td class="px-3 py-2 text-center">
                  <span v-if="i.configured" class="text-[10px] font-bold px-1.5 py-0.5 rounded-full" style="background:#ecfdf5;color:#047857">
                    {{ i.share_pct }}% · {{ i.basis }}
                  </span>
                  <span v-else class="text-[10px] font-bold px-1.5 py-0.5 rounded-full" style="background:#fef2f2;color:#b91c1c">
                    {{ L("not set","غير محددة","non définies") }}
                  </span>
                </td>
                <td class="px-3 py-2 text-end">
                  <button class="h-[26px] px-2.5 rounded-[7px] text-[10.5px] font-bold border border-line hover:bg-app-warm"
                          @click="open(i.account)">{{ L("Statement","كشف الحساب","Relevé") }}</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- one investor -->
      <template v-if="st">
        <div class="bg-white border border-line rounded-[14px] shadow-card px-4 py-3.5">
          <div class="flex items-start gap-3 flex-wrap">
            <div class="min-w-0">
              <div class="text-[14px] font-bold">{{ st.name }}</div>
              <div class="text-[11px] text-ink-muted">{{ st.company }} · {{ L("agreed in","متفق عليه بـ","conclu en") }} {{ st.deal_currency }}</div>
            </div>
            <div class="flex-1"></div>
            <div v-for="f in headline" :key="f.k" class="text-end">
              <div class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ f.label }}</div>
              <div class="text-[17px] font-extrabold tnum" :class="f.tone" dir="ltr">{{ f.v }}</div>
              <div v-if="f.sub" class="text-[10px] text-ink-muted tnum" dir="ltr">{{ f.sub }}</div>
            </div>
          </div>
          <!-- the drift between the books and the obligation, named plainly -->
          <div v-if="st.fx_gap && Math.abs(st.fx_gap) > 1" class="mt-3 pt-3 border-t border-line-hair text-[11px]">
            <span class="font-bold" style="color:#b45309">{{ L("Unrecorded exchange movement","فرق عملة غير مسجّل","Écart de change non comptabilisé") }}:</span>
            <span class="tnum font-bold" dir="ltr"> {{ fmt(st.fx_gap) }} {{ st.currency }}</span>
            <span class="text-ink-muted"> — {{ L("the obligation is held in " + st.deal_currency + " but the books still carry it at the old rate; a revaluation has not been run.",
              "الالتزام بالـ" + st.deal_currency + " والدفاتر لسه بسعر قديم — إعادة التقييم ما اتعملتش.",
              "réévaluation non effectuée.") }}</span>
          </div>
        </div>

        <!-- the cycle, layer by layer -->
        <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
          <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2 flex-wrap">
            <span class="text-[13px] font-bold">{{ L("The cycle their money financed","الدورة اللي موّلها","Le cycle financé") }}</span>
            <span class="text-[10.5px] text-ink-muted tnum" dir="ltr">{{ st.cycle.from }} → {{ st.cycle.to }} · USD</span>
          </div>
          <table class="w-full text-[11.5px]">
            <tbody>
              <tr v-for="l in st.layers" :key="l.key" class="border-t border-line-hair"
                  :class="st.terms && st.terms.basis === l.key ? 'bg-emerald-50/50' : ''">
                <td class="px-4 py-2 font-bold" :class="st.terms && st.terms.basis === l.key ? 'text-emerald-800' : ''">
                  {{ l.label }}
                  <span v-if="st.terms && st.terms.basis === l.key" class="text-[9.5px] font-bold px-1.5 py-0.5 rounded-full ms-1" style="background:#ecfdf5;color:#047857">
                    {{ L("agreed basis","الأساس المتفق عليه","base convenue") }}
                  </span>
                </td>
                <td class="px-4 py-2 text-[10.5px] text-ink-muted">{{ l.hint }}</td>
                <td class="px-4 py-2 text-end tnum font-bold" :class="l.value < 0 ? 'text-sale' : ''" dir="ltr">{{ fmt(l.value) }}</td>
              </tr>
            </tbody>
          </table>
          <div class="px-4 py-2.5 border-t border-line-hair text-[11px]" :style="st.share ? '' : 'color:#b91c1c'">
            <template v-if="st.share">
              <span class="font-bold">{{ L("Their share","نصيبه","Sa part") }} ({{ st.terms.share_pct }}%):</span>
              <span class="tnum font-extrabold text-[13px]" dir="ltr"> {{ fmt(st.share.amount) }} USD</span>
              <span v-if="st.share.note" class="text-ink-muted"> — {{ st.share.note }}</span>
            </template>
            <template v-else>
              {{ L("No terms recorded — the share cannot be computed. Set the percentage, the basis line, and whether losses are shared.",
                   "مفيش شروط مسجّلة — النصيب مش هيتحسب. حدد النسبة والسطر الأساس وهل الخسارة بتتشارك.",
                   "Conditions non enregistrées.") }}
            </template>
          </div>
        </div>

        <!-- movements -->
        <div class="grid lg:grid-cols-2 gap-3">
          <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
            <div class="px-4 py-2.5 border-b border-line-hair text-[12px] font-bold">{{ L("Capital movements","حركات رأس المال","Mouvements de capital") }}</div>
            <table class="w-full text-[11px]">
              <tbody>
                <tr v-for="(m, i) in st.moves" :key="i" class="border-t border-line-hair">
                  <td class="px-3 py-1.5 tnum text-ink-muted" dir="ltr">{{ m.date }}</td>
                  <td class="px-3 py-1.5 text-end tnum" dir="ltr">{{ fmt(m.local) }}</td>
                  <td class="px-3 py-1.5 text-end tnum text-[10px] text-ink-muted" dir="ltr">@{{ m.rate }}</td>
                  <td class="px-3 py-1.5 text-end tnum font-bold" dir="ltr">{{ fmt(m.deal) }} {{ st.deal_currency }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
            <div class="px-4 py-2.5 border-b border-line-hair text-[12px] font-bold">
              {{ L("Drawings","المسحوبات","Retraits") }}
              <span v-if="!st.profit_account" class="text-[10px] font-normal text-ink-muted"> — {{ L("no drawings account","مفيش حساب مسحوبات","aucun compte") }}</span>
            </div>
            <table class="w-full text-[11px]">
              <tbody>
                <tr v-for="(d, i) in st.draws" :key="i" class="border-t border-line-hair">
                  <td class="px-3 py-1.5 tnum text-ink-muted" dir="ltr">{{ d.date }}</td>
                  <td class="px-3 py-1.5 text-end tnum" dir="ltr">{{ fmt(d.local) }}</td>
                  <td class="px-3 py-1.5 text-end tnum font-bold" dir="ltr">{{ fmt(d.deal) }} {{ st.deal_currency }}</td>
                </tr>
                <tr v-if="!st.draws.length"><td class="px-3 py-4 text-center text-[11px] text-ink-muted">—</td></tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- why the cycle figure is not final -->
        <div v-if="st.quality.length" class="bg-white border rounded-[14px] shadow-card overflow-hidden" style="border-color:#fde68a">
          <div class="px-4 py-2.5 border-b text-[12px] font-bold" style="border-color:#fde68a;background:#fffbeb">
            {{ L("What would still move this figure","الحاجات اللي لسه هتحرك الرقم ده","Ce qui peut encore bouger") }}
          </div>
          <table class="w-full text-[11px]">
            <tbody>
              <tr v-for="(q, i) in st.quality" :key="i" class="border-t border-line-hair">
                <td class="px-4 py-2">{{ q.issue }}</td>
                <td class="px-4 py-2 text-end text-[10.5px] font-bold"
                    :style="q.effect.includes('overstated') ? 'color:#b91c1c' : 'color:#b45309'">{{ q.effect }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import api from "@/services/api";

const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const A = "accounting_portal.api.investors";

const loading = ref(true);
const err = ref("");
const list = ref([]);
const st = ref(null);

const fmt = (n) => (n === null || n === undefined ? "—"
  : new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(n));

const headline = computed(() => {
  const d = st.value;
  if (!d) return [];
  return [
    { k: "cap", label: L("Capital", "رأس المال", "Capital"),
      v: `${fmt(d.capital_deal)} ${d.deal_currency}`, sub: `${fmt(d.capital_local)} ${d.currency}`, tone: "" },
    { k: "drawn", label: L("Drawn", "المسحوب", "Retiré"),
      v: `${fmt(d.drawn_deal)} ${d.deal_currency}`, sub: `${fmt(d.drawn_local)} ${d.currency}`, tone: "text-ink-3" },
    { k: "share", label: L("Share of cycle", "نصيبه من الدورة", "Part du cycle"),
      v: d.share ? `${fmt(d.share.amount)} USD` : L("not set", "غير محدد", "non défini"),
      sub: "", tone: d.share && d.share.amount < 0 ? "text-sale" : "" },
  ];
});

async function load() {
  loading.value = true; err.value = "";
  try {
    const r = await api.call(`${A}.investor_list`, {}, { fresh: true });
    list.value = r?.investors || [];
    if (list.value.length) await open(list.value[0].account);
  } catch (e) { err.value = e?.message || String(e); }
  finally { loading.value = false; }
}

async function open(account) {
  try { st.value = await api.call(`${A}.investor_statement`, { account }, { fresh: true }); }
  catch (e) { err.value = e?.message || String(e); }
}

onMounted(load);
</script>
