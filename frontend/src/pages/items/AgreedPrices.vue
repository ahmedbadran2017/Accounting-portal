<template>
  <div class="space-y-3.5">
    <!-- what this screen is, and how it differs from the workbench next door -->
    <div class="rounded-[14px] px-4 py-3 border" style="background:#eff6ff;border-color:#bfdbfe">
      <div class="text-[12px] font-bold" style="color:#1e40af">
        {{ L("The agreed price — one record everything reads",
             "السعر المتفق عليه — سجل واحد كل حاجة بتقرا منه",
             "Le prix convenu — un seul enregistrement") }}
      </div>
      <div class="text-[11px] mt-0.5" style="color:#1d4ed8">
        {{ L("A supplier's price arrives — by sheet or from his own portal — is reviewed against what he last billed, and once approved it is the price the PO fetches, the receipt inherits, stock is valued at, and the site prices from. Vendors next door repairs history; this keeps it right from here on.",
             "سعر المورد بيوصل — بشيت أو من بوابته — يتراجع مقابل آخر فاتورة فوترها، وأول ما يتعتمد يبقى هو السعر اللي الـPO بتسحبه والاستلام بيرثه والمخزون بيتقيّم بيه والموقع بيسعّر منه. تبويب الموردين بيصلّح التاريخ، ودي بتخلّيه مظبوط من هنا ورايح.",
             "Le prix du fournisseur est examiné puis approuvé ; il devient la référence unique.") }}
      </div>
    </div>

    <div v-if="loading" class="py-16 text-center text-[12px] text-ink-muted">{{ L("Loading…","جاري التحميل…","Chargement…") }}</div>
    <div v-else-if="err" class="py-16 text-center text-[12px]" style="color:#b91c1c">{{ err }}</div>

    <template v-else>
      <!-- Day one shows an empty cycle, which reads as a broken screen unless
           it says what to do. Lead with the actual problem and the next action;
           swap to the running-cycle counters once anything is wired. -->
      <div v-if="!started" class="bg-white rounded-card border border-line shadow-card overflow-hidden">
        <div class="px-5 py-4 border-b border-line-hair">
          <div class="text-[14px] font-bold">{{ L("Nothing is priced yet — start here","لسه مفيش أسعار متفق عليها — ابدأ من هنا","Rien n'est encore tarifé") }}</div>
          <div class="text-[11.5px] text-ink-3 mt-1 leading-relaxed max-w-3xl">
            {{ L("Right now no product has a price anybody agreed to, so its cost is whatever someone happened to type on a receipt. Pick a supplier below and press Propose: we read what he actually invoiced (or what his receipts were paid at) and fill a grid for you to check — you review and approve, and from then on the PO, the receipt and the stock value all take that one number.",
                 "دلوقتي مفيش منتج ليه سعر حد اتفق عليه، فتكلفته هي أي رقم حد كتبه في إيصال. اختار مورد من تحت واضغط اقترح: بنقرا اللي فوتره فعلاً (أو اللي إيصالاته اتدفعت بيه) ونملّي لك جدول تراجعه — تعتمد، ومن ساعتها أمر الشراء والاستلام وقيمة المخزون كلهم بياخدوا الرقم ده.",
                 "Aucun produit n'a de prix convenu. Choisissez un fournisseur et lancez Proposer.") }}
          </div>
        </div>
        <div class="px-5 py-3 flex flex-wrap gap-x-8 gap-y-2 border-b border-line-hair" style="background:#fffbeb">
          <div><span class="text-[17px] font-bold tnum" style="color:#b45309">{{ n(unp.count) }}</span>
            <span class="text-[11.5px] text-ink-3 ms-1.5">{{ L("products on sale with no agreed price","منتج بيتباع بدون سعر متفق","produits sans prix convenu") }}</span></div>
          <div><span class="text-[17px] font-bold tnum" style="color:#b45309">{{ n(unp.units) }}</span>
            <span class="text-[11.5px] text-ink-3 ms-1.5">{{ L("units","قطعة","unités") }}</span></div>
          <div><span class="text-[17px] font-bold tnum" style="color:#be123c">{{ n(unp.zero_rate) }}</span>
            <span class="text-[11.5px] text-ink-3 ms-1.5">{{ L("of them cost nothing — they will sell at zero","منهم تكلفتهم صفر — هيتباعوا بتكلفة صفر","à coût nul") }}</span></div>
        </div>
        <div class="overflow-x-auto max-h-[420px] overflow-y-auto">
          <table class="w-full text-[12px]">
            <thead class="sticky top-0"><tr style="background:#fafaf9">
              <th class="px-5 py-2 text-start text-[10px] font-bold text-ink-muted">{{ L("Supplier","المورد","Fournisseur") }}</th>
              <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("Products","منتجات","Produits") }}</th>
              <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("Units on the shelf","قطع على الرف","Unités") }}</th>
              <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("Cost nothing","تكلفتهم صفر","Coût nul") }}</th>
              <th class="px-5 py-2"></th>
            </tr></thead>
            <tbody>
              <tr v-for="r in unp.by_supplier" :key="r.supplier" class="border-t border-line-hair hover:bg-app-warm/50">
                <td class="px-5 py-2 font-semibold">{{ r.supplier }}</td>
                <td class="px-3 py-2 text-end tnum text-ink-3">{{ n(r.items) }}</td>
                <td class="px-3 py-2 text-end tnum font-semibold">{{ n(r.units) }}</td>
                <td class="px-3 py-2 text-end tnum" :style="r.zero_rate ? 'color:#be123c;font-weight:700' : 'color:#a8a29e'">{{ r.zero_rate || "—" }}</td>
                <td class="px-5 py-2 text-end">
                  <button class="h-[26px] px-3 rounded-[8px] text-[11px] font-bold text-white bg-brand disabled:opacity-40"
                          :disabled="busy || r.supplier.startsWith('(')"
                          @click="seedFor = r.supplier; seed()">{{ L("Propose","اقترح","Proposer") }}</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- the running cycle: only meaningful once something is wired -->
      <div v-else class="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <div v-for="k in kpis" :key="k.label" class="bg-white border border-line rounded-card p-3.5">
          <div class="text-[20px] font-bold tnum" :style="{ color: k.color }">{{ n(k.value) }}</div>
          <div class="text-[11px] text-ink-3 mt-0.5">{{ k.label }}</div>
          <div class="text-[10px] text-ink-muted mt-1">{{ k.sub }}</div>
        </div>
      </div>

      <!-- ── the queue ── -->
      <div v-if="started || q.pending.length" class="bg-white rounded-card border border-line shadow-card overflow-hidden">
        <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2 flex-wrap">
          <span class="text-[12.5px] font-bold">{{ L("Waiting for review","مستني مراجعة","À examiner") }}</span>
          <span class="text-[10.5px] text-ink-muted">{{ L("worst deviation first","الأبعد عن الفاتورة الأول","écart le plus fort en premier") }}</span>
          <div class="flex-1"></div>
          <select v-model="seedFor" class="h-[28px] px-2 rounded-[8px] border border-line text-[11.5px] bg-white max-w-[240px]">
            <option value="">{{ L("Seed a supplier from history…","ازرع مورد من تاريخه…","Amorcer un fournisseur…") }}</option>
            <option v-for="s in suppliers" :key="s" :value="s">{{ s }}</option>
          </select>
          <button class="h-[28px] px-3 rounded-[8px] text-[11.5px] font-bold text-white bg-brand disabled:opacity-40"
                  :disabled="!seedFor || busy" @click="seed">{{ L("Propose","اقترح","Proposer") }}</button>
        </div>

        <div v-if="!q.pending.length" class="py-10 text-center text-[12px] text-ink-muted">
          {{ L("Nothing pending.","مفيش حاجة مستنية.","Rien en attente.") }}
        </div>
        <table v-else class="w-full text-[12px]">
          <thead><tr style="background:#fafaf9">
            <th class="px-4 py-2 text-start text-[10px] font-bold text-ink-muted">{{ L("Supplier","المورد","Fournisseur") }}</th>
            <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("Rows","صفوف","Lignes") }}</th>
            <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("Flagged","مُعلَّم","Signalés") }}</th>
            <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("Worst gap","أكبر فرق","Écart max") }}</th>
            <th class="px-3 py-2 text-start text-[10px] font-bold text-ink-muted">{{ L("Came from","المصدر","Source") }}</th>
            <th class="px-4 py-2"></th>
          </tr></thead>
          <tbody>
            <tr v-for="p in q.pending" :key="p.supplier" class="border-t border-line-hair hover:bg-app-warm/50">
              <td class="px-4 py-2.5 font-semibold">{{ p.supplier }}</td>
              <td class="px-3 py-2.5 text-end tnum">{{ p.rows }}</td>
              <td class="px-3 py-2.5 text-end tnum" :style="p.flagged ? 'color:#be123c;font-weight:700' : ''">{{ p.flagged || "—" }}</td>
              <td class="px-3 py-2.5 text-end tnum" dir="ltr">{{ p.worst_dev_pct }}%</td>
              <td class="px-3 py-2.5 text-[11px] text-ink-3">{{ srcLabel(p.source) }} · {{ p.on }}</td>
              <td class="px-4 py-2.5 text-end">
                <button class="h-[26px] px-3 rounded-[8px] border border-line text-[11px] bg-white font-semibold"
                        @click="openReview(p.supplier)">{{ L("Review","راجع","Examiner") }} →</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- ── review one supplier ── -->
      <div v-if="rv" class="bg-white rounded-card border border-line shadow-card overflow-hidden">
        <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2 flex-wrap">
          <button class="h-[26px] px-2.5 rounded-[8px] border border-line text-[11px] bg-white" @click="rv = null">←</button>
          <span class="text-[12.5px] font-bold">{{ rv.supplier }}</span>
          <span class="text-[10.5px] text-ink-muted">{{ rv.currency }} · {{ rv.items.length }} {{ L("rows","صف","lignes") }}</span>
          <span v-if="rv.flagged" class="text-[10px] font-bold px-2 py-0.5 rounded-full"
                style="background:#fef2f2;color:#be123c">{{ rv.flagged }} {{ L("past the guard","تعدّوا الحارس","au-delà du garde-fou") }}</span>
          <div class="flex-1"></div>
          <span class="text-[11px] text-ink-3">{{ chosen.length }} {{ L("selected","محدد","sélectionnés") }}</span>
          <button class="h-[28px] px-3 rounded-[8px] border border-line text-[11.5px] bg-white"
                  :disabled="busy" @click="doReject">{{ L("Reject","ارفض","Rejeter") }}</button>
          <button class="h-[28px] px-3 rounded-[8px] text-[11.5px] font-bold text-white bg-brand disabled:opacity-40"
                  :disabled="!chosen.length || busy" @click="doApprove">{{ L("Approve","اعتمد","Approuver") }}</button>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-[11.5px]">
            <thead><tr style="background:#fafaf9">
              <th class="px-3 py-2 w-[34px]"><input type="checkbox" :checked="allOn" @change="toggleAll" /></th>
              <th class="px-3 py-2 text-start text-[10px] font-bold text-ink-muted">{{ L("Item","الصنف","Article") }}</th>
              <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("Agreed now","المتفق حاليًا","Convenu") }}</th>
              <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("Proposed","المقترح","Proposé") }}</th>
              <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("He billed","اللي فوتره","Facturé") }}</th>
              <th class="px-3 py-2 text-center text-[10px] font-bold text-ink-muted">{{ L("Gap","الفرق","Écart") }}</th>
              <th class="px-4 py-2 text-start text-[10px] font-bold text-ink-muted">{{ L("From","سريان من","À partir de") }}</th>
            </tr></thead>
            <tbody>
              <tr v-for="it in rv.items" :key="it.item_code" class="border-t border-line-hair"
                  :style="it.flagged ? 'background:#fff7f7' : ''">
                <td class="px-3 py-1.5"><input type="checkbox" v-model="sel[it.item_code]" /></td>
                <td class="px-3 py-1.5">
                  <span class="block font-mono text-[10.5px]" dir="ltr">{{ it.item_code }}</span>
                  <span class="block text-[10px] text-ink-muted">{{ (it.item_name || "").slice(0, 46) }}</span>
                </td>
                <td class="px-3 py-1.5 text-end tnum text-ink-3">{{ it.current_agreed ? money(it.current_agreed) : "—" }}</td>
                <td class="px-3 py-1.5 text-end tnum font-semibold">{{ money(it.proposed) }}</td>
                <td class="px-3 py-1.5 text-end tnum text-ink-3">
                  {{ it.benchmark ? money(it.benchmark) : "—" }}
                  <span v-if="it.benchmark_source === 'receipt'" class="text-[9px] text-ink-muted">{{ L("(receipt)","(إيصال)","(réception)") }}</span>
                </td>
                <td class="px-3 py-1.5 text-center">
                  <span v-if="it.dev_pct !== null" class="text-[10px] font-bold px-1.5 py-0.5 rounded-full"
                        :style="it.flagged ? 'background:#fef2f2;color:#be123c' : 'background:#ecfdf5;color:#047857'"
                        dir="ltr">{{ it.dev_pct > 0 ? "+" : "" }}{{ it.dev_pct }}%</span>
                  <span v-else class="text-[10px] text-ink-muted">{{ L("no history","بدون تاريخ","—") }}</span>
                </td>
                <td class="px-4 py-1.5 text-[10.5px] text-ink-3" dir="ltr">{{ it.valid_from }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="rv.flagged" class="px-4 py-2 border-t border-line-hair text-[11px]" style="background:#fffbeb;color:#92400e">
          {{ L("Rows past ±50% of what he last billed need the confirm box — approving them is a deliberate act, not a click-through.",
               "الصفوف اللي بعدت أكتر من ±50% عن آخر فاتورة محتاجة تأكيد — اعتمادها قرار مقصود مش كليكة عابرة.",
               "Les lignes au-delà de ±50% exigent une confirmation.") }}
          <label class="ms-2 inline-flex items-center gap-1.5 font-bold">
            <input type="checkbox" v-model="confirmFlagged" />{{ L("confirm flagged","أأكد المُعلَّم","confirmer") }}
          </label>
        </div>
      </div>

      <!-- ── the audit: is every product priced, and priced consistently? ── -->
      <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
        <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2 flex-wrap">
          <span class="text-[12.5px] font-bold">🔍 {{ L("Price audit","تدقيق الأسعار","Audit des prix") }}</span>
          <span class="text-[10.5px] text-ink-muted">{{ L("every sellable product against the price agreed, the rate its stock is valued at, and what he billed","كل منتج قابل للبيع مقابل السعر المتفق وقيمة المخزون واللي فوتره","chaque produit vs prix convenu, valorisation et facture") }}</span>
          <div class="flex-1"></div>
          <button class="h-[28px] px-3 rounded-[8px] border border-line text-[11.5px] bg-white font-semibold"
                  :disabled="auditing" @click="runAudit">
            {{ auditing ? L("Checking…","بيفحص…","Analyse…") : (au ? L("Re-run","أعد الفحص","Relancer") : L("Run audit","افحص","Lancer")) }}
          </button>
        </div>
        <div v-if="!au" class="py-8 text-center text-[11.5px] text-ink-muted">
          {{ L("Not run yet.","ماتعملش لسه.","Pas encore lancé.") }}
        </div>
        <template v-else>
          <div class="px-4 py-3 grid grid-cols-2 lg:grid-cols-6 gap-3">
            <div v-for="v in verdicts" :key="v.key" class="text-center">
              <div class="text-[18px] font-bold tnum" :style="{ color: v.color }">{{ n(au.summary[v.key] || 0) }}</div>
              <div class="text-[10px] text-ink-3 leading-tight mt-0.5">{{ v.label }}</div>
            </div>
          </div>
          <div class="px-4 pb-2.5 text-[11px] text-ink-3">
            {{ n(au.checked) }} {{ L("checked","صنف اتفحص","vérifiés") }} ·
            <span class="font-bold" :style="{ color: au.clean_pct > 80 ? '#047857' : '#b45309' }">{{ au.clean_pct }}%</span>
            {{ L("clean","سليم","propres") }} ·
            {{ L("value at risk","قيمة في الخطر","valeur à risque") }}
            <span class="font-bold" style="color:#be123c">{{ money(au.at_risk) }}</span>
            <span class="text-ink-muted">· {{ L("tolerance","السماحية","tolérance") }} ±{{ au.tolerance_pct }}%</span>
          </div>
          <div class="overflow-x-auto max-h-[420px] overflow-y-auto">
            <table class="w-full text-[11px]">
              <thead class="sticky top-0"><tr style="background:#fafaf9">
                <th class="px-3 py-2 text-start text-[10px] font-bold text-ink-muted">{{ L("Item","الصنف","Article") }}</th>
                <th class="px-3 py-2 text-start text-[10px] font-bold text-ink-muted">{{ L("Supplier","المورد","Fournisseur") }}</th>
                <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("Qty","كمية","Qté") }}</th>
                <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("Books","الدفاتر","Livres") }}</th>
                <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("Agreed","المتفق","Convenu") }}</th>
                <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("He billed","فوتره","Facturé") }}</th>
                <th class="px-4 py-2 text-start text-[10px] font-bold text-ink-muted">{{ L("Verdict","الحكم","Verdict") }}</th>
              </tr></thead>
              <tbody>
                <tr v-for="r in au.rows" :key="r.item_code" class="border-t border-line-hair">
                  <td class="px-3 py-1.5">
                    <span class="block font-mono text-[10px]" dir="ltr">{{ r.item_code }}</span>
                    <span class="block text-[9.5px] text-ink-muted">{{ (r.item_name || "").slice(0, 40) }}</span>
                  </td>
                  <td class="px-3 py-1.5 text-ink-3">{{ (r.supplier || "—").slice(0, 22) }}</td>
                  <td class="px-3 py-1.5 text-end tnum text-ink-3">{{ n(r.qty) }}</td>
                  <td class="px-3 py-1.5 text-end tnum font-semibold">{{ money(r.book) }}</td>
                  <td class="px-3 py-1.5 text-end tnum text-ink-3">{{ r.agreed ? money(r.agreed) : "—" }}</td>
                  <td class="px-3 py-1.5 text-end tnum text-ink-3">{{ r.billed ? money(r.billed) : "—" }}</td>
                  <td class="px-4 py-1.5">
                    <span class="text-[9.5px] font-bold px-1.5 py-0.5 rounded-full whitespace-nowrap"
                          :style="vStyle(r.verdict)">{{ vLabel(r.verdict) }}</span>
                    <span v-if="r.gap_pct !== null" class="ms-1 text-[9.5px] tnum" dir="ltr">{{ r.gap_pct > 0 ? "+" : "" }}{{ r.gap_pct }}%</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-if="au.flagged > au.rows.length" class="px-4 py-2 border-t border-line-hair text-[10.5px] text-ink-muted">
            {{ L("Showing the worst","بيعرض الأسوأ","Les pires") }} {{ au.rows.length }} {{ L("of","من","sur") }} {{ n(au.flagged) }}.
          </div>
        </template>
      </div>

      <!-- ── what the cycle wants attention on ── -->
      <div class="grid gap-3.5">
        <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
          <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2">
            <span class="text-[12px] font-bold">{{ L("Billed above the agreed price","فوتر أعلى من المتفق","Facturé au-dessus") }}</span>
            <span v-if="ba.total_overcharge" class="text-[10.5px] font-bold" style="color:#be123c">{{ money(ba.total_overcharge) }}</span>
          </div>
          <div class="max-h-[280px] overflow-y-auto">
            <div v-if="!ba.cases.length" class="py-8 text-center text-[11.5px] text-ink-muted">
              {{ L("Nothing — or no agreed prices to compare against yet.","ولا حاجة — أو مفيش أسعار متفقة نقارن بيها لسه.","Rien à comparer.") }}
            </div>
            <div v-for="c in ba.cases.slice(0, 60)" :key="c.invoice + c.item_code"
                 class="px-4 py-1.5 border-t border-line-hair flex items-center gap-2 text-[11px]">
              <span class="truncate flex-1">{{ c.supplier }}</span>
              <span class="tnum text-ink-3" dir="ltr">{{ money(c.agreed) }} → {{ money(c.billed) }}</span>
              <span class="text-[9.5px] font-bold" style="color:#be123c" dir="ltr">+{{ c.over_pct }}%</span>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import api from "@/services/api";
import { fmtAmount } from "@/utils/helpers";

const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const money = (x) => fmtAmount(x);
const n = (x) => (x === null || x === undefined ? "—" : Math.round(x).toLocaleString("en-US"));

const loading = ref(true);
const busy = ref(false);
const err = ref("");
const h = ref({});
const q = ref({ pending: [] });
const unp = ref({ items: [], count: 0, units: 0 });
const ba = ref({ cases: [], total_overcharge: 0 });
const suppliers = ref([]);
const seedFor = ref("");
const rv = ref(null);
const sel = ref({});
const confirmFlagged = ref(false);

const au = ref(null);
const auditing = ref(false);
const V = {
  zero_cost: ["ZERO cost", "تكلفة صفر", "Coût nul", "#be123c"],
  book_vs_agreed: ["books ≠ agreed", "الدفاتر ≠ المتفق", "livres ≠ convenu", "#b45309"],
  book_vs_billed: ["books ≠ billed", "الدفاتر ≠ الفاتورة", "livres ≠ facturé", "#b45309"],
  no_price: ["no agreed price", "بدون سعر متفق", "sans prix convenu", "#0369a1"],
  no_evidence: ["nothing to check", "مفيش مرجع", "aucune référence", "#78716c"],
  ok: ["OK", "سليم", "OK", "#047857"],
};
const vLabel = (k) => { const v = V[k] || [k, k, k]; return L(v[0], v[1], v[2]); };
const vStyle = (k) => ({ background: (V[k] || [])[3] + "18", color: (V[k] || [])[3] || "#57534e" });
const verdicts = computed(() => ["ok", "zero_cost", "book_vs_agreed", "book_vs_billed", "no_price", "no_evidence"]
  .map((k) => ({ key: k, label: vLabel(k), color: (V[k] || [])[3] })));

async function runAudit() {
  auditing.value = true;
  try { au.value = await api.call("accounting_portal.api.pricing.price_audit", {}, { fresh: true }); }
  catch (e) { alert((e && e.message) || String(e)); }
  finally { auditing.value = false; }
}

const started = computed(() => (h.value.lists_wired || 0) > 0);

const chosen = computed(() => Object.keys(sel.value).filter((k) => sel.value[k]));
const allOn = computed(() => !!rv.value && rv.value.items.length > 0
  && rv.value.items.every((i) => sel.value[i.item_code]));

const kpis = computed(() => [
  { label: L("Waiting for review", "مستني مراجعة", "À examiner"), value: h.value.pending_submissions,
    sub: L("suppliers", "مورد", "fournisseurs"), color: h.value.pending_submissions ? "#b45309" : "#047857" },
  { label: L("Past the guard", "تعدّى الحارس", "Au-delà du garde-fou"), value: h.value.flagged_rows,
    sub: L("rows > ±50%", "صف > ±50%", "lignes"), color: h.value.flagged_rows ? "#be123c" : "#047857" },
  { label: L("Live, unpriced", "شغال بدون سعر", "Sans prix"), value: h.value.unpriced_live,
    sub: n(h.value.unpriced_units) + " " + L("units", "قطعة", "unités"), color: h.value.unpriced_live ? "#be123c" : "#047857" },
  { label: L("Stale suppliers", "أسعار قديمة", "Prix périmés"), value: h.value.stale_suppliers,
    sub: L("no update in months", "مالهاش تحديث من شهور", "sans mise à jour"), color: h.value.stale_suppliers ? "#b45309" : "#047857" },
  { label: L("Lists wired", "قوائم موصولة", "Listes câblées"), value: h.value.lists_wired,
    sub: n(h.value.suppliers_wired) + " " + L("suppliers", "مورد", "fournisseurs"), color: "#0369a1" },
]);

function srcLabel(s) {
  return s === "supplier" ? L("supplier portal", "بوابة المورد", "portail")
    : s === "sheet" ? L("sheet", "شيت", "fichier") : L("team", "الفريق", "équipe");
}

function toggleAll(e) {
  const on = e.target.checked;
  const m = {};
  (rv.value?.items || []).forEach((i) => { m[i.item_code] = on; });
  sel.value = m;
}

async function load() {
  loading.value = true; err.value = "";
  try {
    const [a, b, c, d] = await Promise.all([
      api.call("accounting_portal.api.pricing.cycle_health", {}, { fresh: true }),
      api.call("accounting_portal.api.pricing.queue", {}, { fresh: true }),
      api.call("accounting_portal.api.pricing.unpriced_live_items", { limit: 400 }, { fresh: true }),
      api.call("accounting_portal.api.pricing.billed_above_agreed", {}, { fresh: true }),
    ]);
    h.value = a || {}; q.value = b || { pending: [] };
    unp.value = c || { items: [], count: 0, units: 0 };
    ba.value = d || { cases: [], total_overcharge: 0 };
    suppliers.value = [...new Set((unp.value.items || []).map((i) => i.supplier).filter(Boolean))].sort();
  } catch (e) { err.value = (e && e.message) || String(e); }
  finally { loading.value = false; }
}

async function openReview(sup) {
  busy.value = true;
  try {
    rv.value = await api.call("accounting_portal.api.pricing.review", { supplier: sup }, { fresh: true });
    // nothing pre-selected: approving a price is a decision, not a default
    sel.value = {}; confirmFlagged.value = false;
  } catch (e) { alert((e && e.message) || String(e)); }
  finally { busy.value = false; }
}

async function seed() {
  if (!seedFor.value) return;
  busy.value = true;
  try {
    const p = await api.call("accounting_portal.api.pricing.seed_proposal",
      { supplier: seedFor.value }, { fresh: true });
    if (!p.proposed.length) {
      alert(L("Nothing to propose — no invoice or receipt carries a usable rate.",
              "مفيش حاجة نقترحها — مفيش فاتورة ولا إيصال فيه سعر صالح.",
              "Rien à proposer.")); return;
    }
    if (!confirm(L(`Propose ${p.proposed.length} prices from history for review?`,
                   `نقترح ${p.proposed.length} سعر من التاريخ للمراجعة؟`,
                   `Proposer ${p.proposed.length} prix ?`))) return;
    await api.call("accounting_portal.api.pricing.submit_prices",
      { supplier: seedFor.value, rows: JSON.stringify(p.proposed), source: "team" });
    seedFor.value = "";
    await load();
  } catch (e) { alert((e && e.message) || String(e)); }
  finally { busy.value = false; }
}

async function doApprove() {
  busy.value = true;
  try {
    const r = await api.call("accounting_portal.api.pricing.approve", {
      supplier: rv.value.supplier, item_codes: JSON.stringify(chosen.value),
      confirm_flagged: confirmFlagged.value ? 1 : 0,
    });
    let msg = L(`Approved ${r.approved}.`, `اتعتمد ${r.approved}.`, `Approuvés : ${r.approved}.`);
    if (r.blocked.length) {
      msg += "\n" + L(`Held back: ${r.blocked.length} — tick "confirm flagged" to approve those.`,
                      `اتوقف: ${r.blocked.length} — علّم "أأكد المُعلَّم" عشان تعتمدهم.`,
                      `Retenus : ${r.blocked.length}.`);
    }
    alert(msg);
    if (r.still_pending) { await openReview(rv.value.supplier); } else { rv.value = null; }
    await load();
  } catch (e) { alert((e && e.message) || String(e)); }
  finally { busy.value = false; }
}

async function doReject() {
  const why = prompt(L("Why is this rejected?", "سبب الرفض؟", "Motif du rejet ?"));
  if (why === null) return;
  busy.value = true;
  try {
    await api.call("accounting_portal.api.pricing.reject", {
      supplier: rv.value.supplier,
      item_codes: JSON.stringify(chosen.value), reason: why,
    });
    rv.value = null;
    await load();
  } catch (e) { alert((e && e.message) || String(e)); }
  finally { busy.value = false; }
}

onMounted(load);
</script>
