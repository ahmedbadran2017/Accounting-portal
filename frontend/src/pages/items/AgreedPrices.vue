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
      <!-- what the cycle is waiting on today -->
      <div class="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <div v-for="k in kpis" :key="k.label" class="bg-white border border-line rounded-card p-3.5">
          <div class="text-[20px] font-bold tnum" :style="{ color: k.color }">{{ n(k.value) }}</div>
          <div class="text-[11px] text-ink-3 mt-0.5">{{ k.label }}</div>
          <div class="text-[10px] text-ink-muted mt-1">{{ k.sub }}</div>
        </div>
      </div>

      <!-- the gate cannot go on before prices exist, so say so plainly -->
      <div v-if="h.lists_wired === 0" class="rounded-[12px] border px-4 py-2.5 flex items-start gap-2.5"
           style="background:#fffbeb;border-color:#fde68a">
        <Icon name="alert" :size="15" color="#b45309" class="mt-0.5 flex-shrink-0" />
        <span class="text-[11.5px] text-ink-2">
          {{ L("No supplier has an approved list yet, so every live product would fail the publish gate. Seed and approve first; switch the gate on after.",
               "مفيش مورد عنده قائمة معتمدة لسه، يعني كل منتج شغال هيتوقف على بوابة النشر. ازرع واعتمد الأول، وشغّل البوابة بعدين.",
               "Aucune liste approuvée : amorcez et approuvez avant d'activer le contrôle.") }}
        </span>
      </div>

      <!-- ── the queue ── -->
      <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
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

      <!-- ── what the cycle wants attention on ── -->
      <div class="grid lg:grid-cols-2 gap-3.5">
        <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
          <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2">
            <span class="text-[12px] font-bold">{{ L("Live with no agreed price","شغال بدون سعر متفق","En vente sans prix convenu") }}</span>
            <span class="text-[10.5px] text-ink-muted">{{ n(unp.count) }} · {{ n(unp.units) }} {{ L("units","قطعة","unités") }}</span>
          </div>
          <div class="max-h-[280px] overflow-y-auto">
            <div v-if="!unp.items.length" class="py-8 text-center text-[11.5px] text-ink-muted">—</div>
            <div v-for="i in unp.items.slice(0, 60)" :key="i.item_code"
                 class="px-4 py-1.5 border-t border-line-hair flex items-center gap-2 text-[11px]">
              <span class="font-mono text-[10px] flex-shrink-0" dir="ltr">{{ i.item_code }}</span>
              <span class="text-ink-muted truncate flex-1">{{ i.supplier || L("no supplier","بدون مورد","—") }}</span>
              <span v-if="i.zero_rate" class="text-[9px] font-bold px-1.5 py-0.5 rounded" style="background:#fef2f2;color:#be123c">{{ L("zero cost","تكلفة صفر","coût nul") }}</span>
              <span class="tnum text-ink-3">{{ n(i.qty) }}</span>
            </div>
          </div>
        </div>

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
