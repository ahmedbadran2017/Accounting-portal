<template>
  <div class="space-y-3.5">
    <!-- snapshot strip: when it was taken, and the two refresh buttons -->
    <div class="bg-white rounded-card border border-line shadow-card px-4 py-2.5 flex items-center gap-2 flex-wrap text-[12px]">
      <Icon name="clock" :size="13" class="text-ink-muted" />
      <span class="text-ink-3">{{ L("Snapshot","لقطة","Instantané") }}: <b class="tnum" dir="ltr">{{ d?.built_on || "—" }}</b></span>
      <span class="text-ink-muted">·</span>
      <span class="text-ink-3">{{ L("Cathedis parcels","طرود كاتدييس","Colis Cathedis") }}: <b class="tnum" dir="ltr">{{ n(d?.parcels) }}</b></span>
      <span v-if="d?.cathedis_sync" class="text-ink-muted" dir="ltr">({{ L("last sync","آخر تحديث","dernière synchro") }} {{ String(d.cathedis_sync.started || "").slice(0, 16) }})</span>
      <span v-if="d && !d.parcels" class="text-[11px] font-semibold" style="color:#b45309">{{ L("No Cathedis data yet — carrier status falls back to the delivery note.","لسه مفيش داتا كاتدييس — الحالة من إذن التسليم.","Pas encore de données Cathedis.") }}</span>
      <div class="ms-auto flex items-center gap-1.5">
        <UiButton variant="secondary" size="xs" icon="refresh" :busy="syncing" @click="syncCathedis">{{ L("Refresh from Cathedis","حدّث من كاتدييس","Synchro Cathedis") }}</UiButton>
        <UiButton variant="secondary" size="xs" :busy="rebuilding" @click="rebuild">{{ L("Rebuild","أعد البناء","Recalculer") }}</UiButton>
      </div>
    </div>
    <div v-if="note" class="text-[12px] text-ink-3 bg-app-warm/60 border border-line-hair rounded-chip px-3 py-2">{{ note }}</div>

    <TableLoading v-if="loading" :rows="8" />
    <div v-else-if="error" class="bg-white rounded-card border border-line shadow-card py-10 text-center text-[13px]" style="color:#b91c1c">{{ L("Load failed","فشل التحميل","Échec du chargement") }} — {{ error }}</div>
    <div v-else-if="d && d.building" class="bg-white rounded-card border border-line shadow-card py-10 text-center text-[13px] text-ink-3">{{ L("The snapshot is being built right now — reload in a minute.","اللقطة بتتبني دلوقتي — اعمل reload بعد دقيقة.","Instantané en cours de calcul — rechargez dans une minute.") }}</div>
    <template v-else-if="d && d.total">
      <!-- the year in four numbers -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div class="bg-white rounded-card border border-line shadow-card px-4 py-3">
          <div class="text-[11px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Orders","أوردرات","Commandes") }}</div>
          <div class="text-[20px] font-extrabold tnum" dir="ltr">{{ n(d.total.orders) }}</div>
          <div class="text-[11px] text-ink-muted tnum" dir="ltr">{{ n(d.total.order_value) }} MAD</div>
        </div>
        <div class="bg-white rounded-card border border-line shadow-card px-4 py-3">
          <div class="text-[11px] font-bold uppercase tracking-wider" style="color:#047857">{{ L("Closed clean","مقفول للآخر","Clôturées sans écart") }}</div>
          <div class="text-[20px] font-extrabold tnum" style="color:#047857" dir="ltr">{{ pct(d.total.clean_pct) }}</div>
          <div class="text-[11px] text-ink-muted tnum" dir="ltr">{{ n(d.total.clean) }} {{ L("of finished orders","من الأوردرات المنتهية","des commandes terminées") }}</div>
        </div>
        <div class="bg-white rounded-card border border-line shadow-card px-4 py-3">
          <div class="text-[11px] font-bold uppercase tracking-wider" style="color:#b91c1c">{{ L("Exceptions","استثناءات","Exceptions") }}</div>
          <div class="text-[20px] font-extrabold tnum" style="color:#b91c1c" dir="ltr">{{ n(d.total.exceptions) }}</div>
          <div class="text-[11px] text-ink-muted tnum" dir="ltr">{{ n(d.total.exception_value) }} MAD</div>
        </div>
        <div class="bg-white rounded-card border border-line shadow-card px-4 py-3">
          <div class="text-[11px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Still moving","لسه في السكة","En cours") }}</div>
          <div class="text-[20px] font-extrabold tnum" dir="ltr">{{ n(d.total.watch) }}</div>
          <div class="text-[11px] text-ink-muted">{{ L("in transit · awaiting transfer · return on its way","في الطريق · مستني تحويل · مرتجع جاي","transit · virement · retour") }}</div>
        </div>
      </div>

      <!-- month by month: the funnel -->
      <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
        <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2" style="background:#fafaf9">
          <span class="text-[12px] font-bold">{{ L("Each month's orders, station by station","أوردرات كل شهر، محطة محطة","Les commandes du mois, étape par étape") }}</span>
          <span class="text-[11px] text-ink-muted">{{ L("month = order date; click a month for its exceptions","الشهر = تاريخ الأوردر؛ اضغط على الشهر تشوف استثناءاته","mois = date de commande") }}</span>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-[12px]">
            <thead><tr>
              <th class="px-3 py-2.5 text-start hcell">{{ L("Month","الشهر","Mois") }}</th>
              <th class="px-3 py-2.5 text-end hcell">{{ L("Orders","أوردرات","Cmd") }}</th>
              <th class="px-3 py-2.5 text-end hcell">{{ L("Shipped","اتشحن","Expédiées") }}</th>
              <th class="px-3 py-2.5 text-end hcell">{{ L("Delivered","اتسلّم","Livrées") }}</th>
              <th class="px-3 py-2.5 text-end hcell">{{ L("Returned","رجع","Retours") }}</th>
              <th class="px-3 py-2.5 text-end hcell">{{ L("Invoiced","اتفوتر","Facturées") }}</th>
              <th class="px-3 py-2.5 text-end hcell">{{ L("Cathedis paid","كاتدييس حوّلت","Versé Cathedis") }}</th>
              <th class="px-3 py-2.5 text-start hcell w-40">{{ L("Closed clean","مقفول للآخر","Sans écart") }}</th>
              <th class="px-3 py-2.5 text-end hcell" style="color:#b91c1c">{{ L("Exceptions","استثناءات","Exceptions") }}</th>
              <th class="px-3 py-2.5 text-end hcell" :title="L('bank remittances booked on the Cathedis account minus what Cathedis says it paid that month','تحويلات البنك على حساب كاتدييس ناقص اللي كاتدييس بتقول إنها حولته','versements banque − versé Cathedis')">{{ L("Bank − Cathedis","البنك − كاتدييس","Banque − Cathedis") }}</th>
            </tr></thead>
            <tbody>
              <template v-for="m in d.months" :key="m.month">
                <tr class="border-t border-line-hair hover:bg-app-warm/40 cursor-pointer" :class="open === m.month ? 'bg-app-warm/60' : ''" @click="toggle(m.month)">
                  <td class="px-3 py-2.5 font-semibold whitespace-nowrap"><Icon :name="open === m.month ? 'chevDown' : 'chev'" :size="12" class="inline me-1 rtl:rotate-180" />{{ m.month }}</td>
                  <td class="px-3 py-2.5 text-end tnum">{{ n(m.orders) }}</td>
                  <td class="px-3 py-2.5 text-end tnum">{{ n(m.shipped) }}</td>
                  <td class="px-3 py-2.5 text-end tnum">{{ n(m.delivered) }}</td>
                  <td class="px-3 py-2.5 text-end tnum text-ink-muted">{{ n(m.returned) }}</td>
                  <td class="px-3 py-2.5 text-end tnum">{{ n(m.invoiced) }}</td>
                  <td class="px-3 py-2.5 text-end tnum">{{ n(m.cod_collected) }}</td>
                  <td class="px-3 py-2.5">
                    <div class="flex items-center gap-2">
                      <div class="flex-1 h-1.5 rounded-full overflow-hidden" style="background:#f5f5f4">
                        <div class="h-full rounded-full" :style="{ width: (m.clean_pct || 0) + '%', background: tone(m.clean_pct) }"></div>
                      </div>
                      <span class="tnum font-bold text-[11px] w-11 text-end" :style="{ color: tone(m.clean_pct) }" dir="ltr">{{ pct(m.clean_pct) }}</span>
                    </div>
                  </td>
                  <td class="px-3 py-2.5 text-end tnum whitespace-nowrap" dir="ltr"><b :style="m.exceptions ? 'color:#b91c1c' : 'color:#047857'">{{ n(m.exceptions) }}</b> <span class="text-ink-muted text-[11px]">· {{ n(m.exception_value) }}</span></td>
                  <td class="px-3 py-2.5 text-end tnum" dir="ltr" :style="Math.abs(m.bank?.diff || 0) > 1000 ? 'color:#b45309;font-weight:700' : 'color:#78716c'">{{ m.bank && (m.bank.cathedis_funded || m.bank.bank_credited) ? n(m.bank.diff) : "—" }}</td>
                </tr>
                <tr v-if="open === m.month" class="border-t border-line-hair" style="background:#fafaf9">
                  <td colspan="10" class="px-4 py-3">
                    <div v-for="st in stationsOf(m.buckets)" :key="st.key" class="flex items-start gap-2 mb-1.5">
                      <span class="text-[10px] font-bold uppercase tracking-wider text-ink-muted w-28 pt-1.5 flex-shrink-0">{{ st.label }}</span>
                      <div class="flex items-center gap-1.5 flex-wrap">
                        <button v-for="b in st.items" :key="b.key" @click="pick(m.month, b.key)"
                                class="text-[11px] font-semibold px-2.5 py-1 rounded-full border transition"
                                :class="pickKey === m.month + '|' + b.key ? 'bg-ink text-white border-ink' : 'bg-white text-ink-3 border-line-2 hover:bg-app-warm'">
                          {{ label(b.key) }} · <span class="tnum" dir="ltr">{{ n(b.n) }} · {{ n(b.value) }}</span>
                        </button>
                      </div>
                    </div>
                    <div v-if="!Object.keys(m.buckets || {}).length" class="text-[12px] py-1" style="color:#047857">{{ L("Every order of this month closed clean.","كل أوردرات الشهر ده اتقفلت سليمة.","Tout est clôturé sans écart.") }}</div>
                  </td>
                </tr>
              </template>
            </tbody>
            <tfoot><tr class="border-t-2 border-line font-bold" style="background:#fafaf9">
              <td class="px-3 py-2.5">{{ L("Year","السنة","Année") }}</td>
              <td class="px-3 py-2.5 text-end tnum">{{ n(d.total.orders) }}</td>
              <td class="px-3 py-2.5 text-end tnum">{{ n(d.total.shipped) }}</td>
              <td class="px-3 py-2.5 text-end tnum">{{ n(d.total.delivered) }}</td>
              <td class="px-3 py-2.5 text-end tnum">{{ n(d.total.returned) }}</td>
              <td class="px-3 py-2.5 text-end tnum">{{ n(d.total.invoiced) }}</td>
              <td class="px-3 py-2.5 text-end tnum">{{ n(d.total.cod_collected) }}</td>
              <td class="px-3 py-2.5 tnum" :style="{ color: tone(d.total.clean_pct) }" dir="ltr">{{ pct(d.total.clean_pct) }}</td>
              <td class="px-3 py-2.5 text-end tnum" style="color:#b91c1c" dir="ltr">{{ n(d.total.exceptions) }} <span class="text-[11px] font-normal text-ink-muted">· {{ n(d.total.exception_value) }}</span></td>
              <td></td>
            </tr></tfoot>
          </table>
        </div>
      </div>

      <!-- the whole year, by station -->
      <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
        <div class="px-4 py-2.5 border-b border-line-hair text-[12px] font-bold" style="background:#fafaf9">{{ L("Where the year's orders break","الأوردرات بتقف فين على مدار السنة","Où l'année casse") }}</div>
        <table class="w-full text-[12px]">
          <tbody>
            <template v-for="st in stationsOf(d.total.buckets)" :key="st.key">
              <tr class="border-t border-line-hair first:border-t-0"><td colspan="4" class="px-4 pt-2.5 pb-1 text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ st.label }}</td></tr>
              <tr v-for="b in st.items" :key="b.key" class="hover:bg-app-warm/40 cursor-pointer" :class="pickKey === 'all|' + b.key ? 'bg-app-warm/60' : ''" @click="pick('all', b.key)">
                <td class="px-4 py-2 font-semibold">{{ label(b.key) }}<div class="text-[11px] font-normal text-ink-muted">{{ hint(b.key) }}</div></td>
                <td class="px-4 py-2 text-end tnum" dir="ltr">{{ n(b.n) }}</td>
                <td class="px-4 py-2 text-end tnum" dir="ltr">{{ n(b.value) }}</td>
                <td class="px-4 py-2 text-end text-[11px] text-ink-muted w-28">{{ fixLabel(d.actions?.[b.key]) }}</td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>

      <!-- drill: the orders behind one bucket -->
      <div v-if="pickKey" class="bg-white rounded-card border border-line shadow-card overflow-hidden">
        <div class="px-4 py-2.5 text-[12px] font-bold border-b border-line-hair flex items-center gap-2" style="background:#fafaf9">
          {{ label(pickKey.split("|")[1]) }} <span class="text-ink-muted font-normal">· {{ pickKey.split("|")[0] === "all" ? L("whole year","السنة كلها","toute l'année") : pickKey.split("|")[0] }}</span>
          <span class="ms-auto text-ink-muted font-normal tnum" dir="ltr">{{ drillRows.length }} / {{ drillTotal }}</span>
        </div>
        <TableLoading v-if="drillLoading" :rows="4" />
        <div v-else class="overflow-x-auto">
          <table class="w-full text-[12px]">
            <thead><tr>
              <th class="px-3 py-2 text-start hcell">{{ L("Order","الأوردر","Commande") }}</th>
              <th class="px-3 py-2 text-start hcell">{{ L("Delivery note · parcel","إذن التسليم · الطرد","BL · colis") }}</th>
              <th class="px-3 py-2 text-start hcell">{{ L("Cathedis says","كاتدييس بتقول","Cathedis") }}</th>
              <th class="px-3 py-2 text-start hcell">{{ L("Invoice","الفاتورة","Facture") }}</th>
              <th class="px-3 py-2 text-end hcell">{{ L("Invoiced","متفوتر","Facturé") }}</th>
              <th class="px-3 py-2 text-end hcell">{{ L("Cathedis COD","تحصيل كاتدييس","COD Cathedis") }}</th>
              <th class="px-3 py-2 text-end hcell">{{ L("Receipts","التحصيل المسجل","Encaissements") }}</th>
              <th class="px-3 py-2 text-end hcell">{{ L("Cost","التكلفة","Coût") }}</th>
              <th class="px-3 py-2 text-end hcell"></th>
            </tr></thead>
            <tbody>
              <tr v-for="r in drillRows" :key="r.so" class="border-t border-line-hair hover:bg-app-warm/30">
                <td class="px-3 py-2 whitespace-nowrap">
                  <RouterLink :to="routeForDoc('Sales Order', r.so)" class="font-mono text-[11px] font-semibold hover:text-accent">{{ r.so }}</RouterLink>
                  <span v-if="r.exchange" class="ms-1 text-[10px] font-bold px-1.5 py-0.5 rounded-full" style="background:#fef3c7;color:#92400e">EX</span>
                  <div class="text-[11px] text-ink-muted truncate max-w-[160px]">{{ r.customer }} · {{ r.payment_type }}</div>
                </td>
                <td class="px-3 py-2 whitespace-nowrap">
                  <RouterLink v-if="r.dn" :to="routeForDoc('Delivery Note', r.dn)" class="font-mono text-[11px] hover:text-accent">{{ r.dn }}</RouterLink><span v-else class="text-ink-muted">—</span>
                  <div class="font-mono text-[10px] text-ink-muted">{{ r.awb || "" }}</div>
                </td>
                <td class="px-3 py-2 text-[11px] text-ink-3 max-w-[180px]">{{ r.carrier || "—" }}</td>
                <td class="px-3 py-2 whitespace-nowrap"><RouterLink v-if="r.si" :to="routeForDoc('Sales Invoice', r.si)" class="font-mono text-[11px] hover:text-accent">{{ r.si }}</RouterLink><span v-else class="text-ink-muted">—</span></td>
                <td class="px-3 py-2 text-end tnum" dir="ltr">{{ money(r.invoiced) }}</td>
                <td class="px-3 py-2 text-end tnum" dir="ltr">{{ r.cod == null ? "—" : money(r.cod) }}</td>
                <td class="px-3 py-2 text-end tnum whitespace-nowrap" dir="ltr">{{ money(r.cathedis_receipt) }}<span v-if="r.other_receipt" class="text-ink-muted"> + {{ money(r.other_receipt) }}</span></td>
                <td class="px-3 py-2 text-end tnum" dir="ltr">{{ money(r.cost) }}</td>
                <td class="px-3 py-2 text-end w-28">
                  <UiButton v-if="r.action === 'bill' && r.dn" variant="secondary" size="xs" :busy="busy === r.so" @click="bill(r)">{{ L("Make invoice","اعمل فاتورة","Facturer") }}</UiButton>
                  <UiButton v-else-if="r.action === 'credit_note' && r.si" variant="danger" size="xs" :busy="busy === r.so" @click="creditNote(r)">{{ L("Credit note","إشعار دائن","Avoir") }}</UiButton>
                  <span v-else class="text-[11px] text-ink-muted">{{ L("review","مراجعة","à revoir") }}</span>
                </td>
              </tr>
              <tr v-if="!drillRows.length"><td colspan="9" class="px-4 py-8 text-center text-[12px] text-ink-muted">{{ L("Nothing left in this bucket.","مفيش حاجة في السلة دي.","Rien dans cette catégorie.") }}</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- items whose whole history costs more than they sell for -->
      <div v-if="d.items && d.items.length" class="bg-white rounded-card border border-line shadow-card overflow-hidden">
        <div class="px-4 py-2.5 border-b border-line-hair" style="background:#fafaf9">
          <div class="text-[12px] font-bold">{{ L("Items that cost more than they sell for","أصناف تكلفتها أعلى من سعر بيعها","Articles au coût supérieur au prix") }}</div>
          <div class="text-[11px] text-ink-muted">{{ L("median cost vs median selling price (excl. VAT) over the year's deliveries — fix the cost at its source (Vendor Workbench), not order by order","متوسط التكلفة قصاد متوسط سعر البيع (من غير ضريبة) على مدار السنة — التصليح من المصدر (Vendor Workbench) مش أوردر أوردر","coût médian vs prix médian HT — corriger à la source") }}</div>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-[12px]">
            <thead><tr>
              <th class="px-3 py-2 text-start hcell">{{ L("Item","الصنف","Article") }}</th>
              <th class="px-3 py-2 text-end hcell">{{ L("Deliveries","تسليمات","Livraisons") }}</th>
              <th class="px-3 py-2 text-end hcell">{{ L("Unit cost","تكلفة الوحدة","Coût unit.") }}</th>
              <th class="px-3 py-2 text-end hcell">{{ L("Sells for (HT)","بيتباع بـ (بدون ضريبة)","Prix HT") }}</th>
              <th class="px-3 py-2 text-end hcell">×</th>
            </tr></thead>
            <tbody>
              <tr v-for="it in d.items.slice(0, itemsShown)" :key="it.item" class="border-t border-line-hair">
                <td class="px-3 py-2"><RouterLink :to="routeForDoc('Item', it.item)" class="font-mono text-[11px] hover:text-accent">{{ it.item }}</RouterLink></td>
                <td class="px-3 py-2 text-end tnum" dir="ltr">{{ n(it.deliveries) }}</td>
                <td class="px-3 py-2 text-end tnum font-bold" style="color:#b91c1c" dir="ltr">{{ money(it.unit_cost) }}</td>
                <td class="px-3 py-2 text-end tnum" dir="ltr">{{ money(it.unit_price) }}</td>
                <td class="px-3 py-2 text-end tnum" dir="ltr">{{ it.ratio }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <button v-if="d.items.length > itemsShown" class="w-full py-2 text-[11px] font-semibold text-accent border-t border-line-hair hover:bg-app-warm/40" @click="itemsShown = d.items.length">{{ L("Show all","اعرض الكل","Tout afficher") }} ({{ d.items.length }})</button>
      </div>
    </template>
  </div>
</template>

<script setup>
// The cycle radar: every order of a month carried to its last station
// (shipped → Cathedis → invoice → collection → cost). The rules live in
// api/radar.py; this page only shows the snapshot and drills into it.
import { ref, watch, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import UiButton from "@/components/UiButton.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { routeForDoc } from "@/utils/helpers";

const props = defineProps({ year: { type: Number, required: true } });

const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const n = (v) => (v == null ? "—" : Math.round(v).toLocaleString("en-US"));
const money = (v) => (v == null ? "—" : Number(v).toLocaleString("en-US", { maximumFractionDigits: 2 }));
const pct = (v) => (v == null ? "—" : v + "%");
const tone = (v) => (v == null ? "#78716c" : v >= 97 ? "#047857" : v >= 90 ? "#b45309" : "#b91c1c");

const d = ref(null);
const loading = ref(false);
const error = ref("");
const note = ref("");
const open = ref("");
const pickKey = ref("");
const drillRows = ref([]);
const drillTotal = ref(0);
const drillLoading = ref(false);
const busy = ref("");
const syncing = ref(false);
const rebuilding = ref(false);
const itemsShown = ref(10);

// [key, en, ar, fr, hint en, hint ar, hint fr]
const B = {
  collected_no_invoice: ["Collected, no invoice", "اتحصّل ومالوش فاتورة", "Encaissé sans facture", "Cathedis paid us; no revenue booked", "كاتدييس حوّلت ومفيش إيراد متسجل", "Cathedis a versé, pas de CA"],
  delivered_no_invoice: ["Delivered, no invoice", "اتسلّم ومالوش فاتورة", "Livré sans facture", "carrier confirms delivery", "الكاريير مأكد التسليم", "livraison confirmée"],
  prepaid_no_invoice: ["Prepaid, no invoice", "مدفوع مقدم ومالوش فاتورة", "Prépayé sans facture", "Cathedis collected 0 — paid before shipping", "كاتدييس حصّلت صفر — اتدفع قبل الشحن", "COD 0 — payé avant"],
  exchange_overbilled: ["Exchange billed at full price", "تبديل متفوتر بالسعر الكامل", "Échange facturé plein tarif", "only the exchange difference is owed", "المستحق فرق التبديل بس", "seule la différence est due"],
  prepaid_cod_receipt: ["Prepaid, but a COD receipt", "مدفوع مقدم وعليه تحصيل كاتدييس", "Prépayé avec encaissement COD", "Cathedis collected 0, a Cathedis receipt was booked", "كاتدييس حصّلت صفر واتسجل تحصيل كاتدييس", "COD 0 mais encaissement Cathedis"],
  prepaid_unmatched: ["Prepaid, payment not found", "مدفوع مقدم والفلوس مش متسجلة", "Prépayé, paiement introuvable", "no Payzone / bank receipt on the order", "مفيش تحصيل Payzone أو بنك على الأوردر", "aucun encaissement Payzone/banque"],
  funded_no_receipt: ["Cathedis paid, no receipt", "كاتدييس حوّلت ومفيش تحصيل", "Versé, pas d'encaissement", "money arrived, invoice still open", "الفلوس وصلت والفاتورة لسه مفتوحة", "facture encore ouverte"],
  amount_mismatch: ["Collected ≠ receipt", "المحصّل ≠ المسجل", "Encaissé ≠ enregistré", "Cathedis collected a different amount than we booked", "كاتدييس حصّلت مبلغ غير اللي اتسجل", "montant différent"],
  invoice_vs_paid: ["Invoice ≠ money received", "الفاتورة ≠ الفلوس اللي وصلت", "Facture ≠ encaissé", "open balance or overpaid", "رصيد مفتوح أو مدفوع زيادة", "solde ouvert ou trop-perçu"],
  transfer_late: ["Delivered, Cathedis late to pay", "اتسلّم وكاتدييس اتأخرت في التحويل", "Livré, versement en retard", "more than 15 days", "أكتر من 15 يوم", "plus de 15 jours"],
  returned_but_collected: ["Returned, but a receipt stands", "رجع وعليه تحصيل", "Retourné mais encaissé", "a COD receipt on a parcel that came back", "تحصيل على طرد رجع", "encaissement sur un retour"],
  returned_invoice_stands: ["Returned, invoice stands", "رجع والفاتورة واقفة", "Retourné, facture maintenue", "needs a credit note", "محتاج إشعار دائن", "avoir nécessaire"],
  return_not_received: ["Returned at Cathedis, not in stock", "مرتجع عند كاتدييس ومش في المخزن", "Retour non réceptionné", "no return delivery note after 20 days", "مفيش إذن مرتجع بعد 20 يوم", "pas de BL retour après 20 j"],
  invoiced_not_delivered: ["Invoiced, not delivered", "متفوتر ومااتسلمش", "Facturé non livré", "revenue before the carrier delivered", "إيراد قبل التسليم", "CA avant livraison"],
  stuck_at_carrier: ["Stuck at Cathedis", "واقف عند كاتدييس", "Bloqué chez Cathedis", "no delivery, no return after 20 days", "لا اتسلّم ولا رجع بعد 20 يوم", "ni livré ni retourné"],
  no_carrier_record: ["Unknown to Cathedis", "كاتدييس مش لاقياه", "Inconnu de Cathedis", "the parcel number is not in Cathedis", "رقم الطرد مش عند كاتدييس", "AWB absent"],
  dup_dn: ["Two delivery notes, one parcel", "إذنين تسليم لطرد واحد", "Deux BL, un colis", "stock counted twice", "المخزون اتخصم مرتين", "stock compté deux fois"],
  cancelled_goods_out: ["Cancelled, goods went out", "ملغي والبضاعة خرجت", "Annulée, marchandise sortie", "no return recorded", "مفيش مرتجع متسجل", "aucun retour"],
  invoice_no_shipment: ["Invoice, nothing shipped", "فاتورة ومفيش شحن", "Facture sans expédition", "revenue with no delivery note", "إيراد من غير إذن تسليم", "CA sans BL"],
  cogs_zero: ["Cost is zero", "التكلفة صفر", "Coût nul", "goods left the warehouse at no cost", "البضاعة خرجت بتكلفة صفر", "sortie à coût nul"],
  cogs_high: ["Cost looks inflated", "التكلفة متضخمة", "Coût gonflé", "≥1.8× the item's own history, or above its selling price", "≥1.8 مرة من تاريخ الصنف أو أعلى من سعر بيعه", "≥1,8× l'historique ou > prix"],
  cogs_low: ["Cost looks too low", "التكلفة قليلة بشكل غريب", "Coût trop bas", "under 0.4× the item's own history", "أقل من 0.4 من تاريخ الصنف", "< 0,4× l'historique"],
  in_transit: ["In transit", "في الطريق", "En transit", "younger than 20 days", "أحدث من 20 يوم", "moins de 20 jours"],
  awaiting_transfer: ["Delivered, transfer coming", "اتسلّم والتحويل جاي", "Livré, versement à venir", "Cathedis has not paid yet", "كاتدييس لسه ماحوّلتش", "pas encore versé"],
  return_in_progress: ["Return on its way", "المرتجع في الطريق", "Retour en cours", "younger than 20 days", "أحدث من 20 يوم", "moins de 20 jours"],
};
const label = (k) => (B[k] ? L(B[k][0], B[k][1], B[k][2]) : k);
const hint = (k) => (B[k] ? L(B[k][3], B[k][4], B[k][5]) : "");
const fixLabel = (a) => a === "bill" ? L("Make invoice", "فاتورة", "Facturer")
  : a === "credit_note" ? L("Credit note", "إشعار دائن", "Avoir")
  : L("review", "مراجعة", "revoir");

const STATIONS = [
  ["money", "Revenue & cash", "الإيراد والفلوس", "CA & encaissement",
    ["collected_no_invoice", "delivered_no_invoice", "prepaid_no_invoice", "exchange_overbilled", "prepaid_cod_receipt",
     "prepaid_unmatched", "funded_no_receipt", "amount_mismatch", "invoice_vs_paid", "transfer_late"]],
  ["returns", "Returns", "المرتجعات", "Retours", ["returned_but_collected", "returned_invoice_stands", "return_not_received"]],
  ["carrier", "Carrier", "الكاريير", "Transporteur", ["invoiced_not_delivered", "stuck_at_carrier", "no_carrier_record"]],
  ["docs", "Documents", "المستندات", "Documents", ["dup_dn", "cancelled_goods_out", "invoice_no_shipment"]],
  ["cost", "Cost of goods", "تكلفة البضاعة", "Coût", ["cogs_zero", "cogs_high", "cogs_low"]],
  ["watch", "Still moving", "لسه في السكة", "En cours", ["in_transit", "awaiting_transfer", "return_in_progress"]],
];
function stationsOf(buckets) {
  const out = [];
  for (const [key, en, ar, fr, keys] of STATIONS) {
    const items = keys.filter((k) => buckets && buckets[k] && buckets[k].n)
      .map((k) => ({ key: k, n: buckets[k].n, value: buckets[k].value }));
    if (items.length) out.push({ key, label: L(en, ar, fr), items });
  }
  return out;
}

async function load() {
  loading.value = true; error.value = ""; open.value = ""; pickKey.value = ""; drillRows.value = [];
  try {
    d.value = await api.call("accounting_portal.api.radar.summary",
      { company: currentCompany(), year: props.year }, { fresh: true });
  } catch (e) { error.value = (e && e.message) || String(e); d.value = null; }
  finally { loading.value = false; }
}
function toggle(m) { open.value = open.value === m ? "" : m; }
async function pick(month, bucket) {
  pickKey.value = `${month}|${bucket}`; drillLoading.value = true;
  try {
    const r = await api.call("accounting_portal.api.radar.drill",
      { company: currentCompany(), year: props.year, month, bucket, limit: 300 }, { fresh: true });
    drillRows.value = r.rows || []; drillTotal.value = r.total || 0;
  } catch (e) { alert((e && e.message) || e); }
  finally { drillLoading.value = false; }
}
async function bill(r) {
  if (!confirm(L(`Invoice ${r.so} and record its Cathedis receipt?`, `فوترة ${r.so} وتسجيل تحصيل كاتدييس؟`, `Facturer ${r.so} ?`))) return;
  busy.value = r.so;
  try {
    await api.call("accounting_portal.api.radar.bill_order", { company: currentCompany(), so: r.so, dn: r.dn });
    drillRows.value = drillRows.value.filter((x) => x.so !== r.so);
  } catch (e) { alert((e && e.message) || e); }
  finally { busy.value = ""; }
}
async function creditNote(r) {
  if (!confirm(L(`Issue a credit note against ${r.si}? The parcel came back.`, `إصدار إشعار دائن على ${r.si}؟ الطرد رجع.`, `Émettre un avoir sur ${r.si} ?`))) return;
  busy.value = r.so;
  try {
    await api.call("accounting_portal.api.sales.create_sales_return",
      { company: currentCompany(), invoice: r.si, reason: "cycle radar — parcel returned, invoice stood" });
    drillRows.value = drillRows.value.filter((x) => x.so !== r.so);
  } catch (e) { alert((e && e.message) || e); }
  finally { busy.value = ""; }
}
async function syncCathedis() {
  syncing.value = true;
  try {
    await api.call("accounting_portal.api.cathedis_sync.sync_now", {});
    note.value = L("Asking Cathedis about the open parcels in the background — the snapshot rebuilds when it finishes (about a minute). Reload then.",
      "بنسأل كاتدييس عن الطرود المفتوحة في الخلفية — اللقطة هتتبني لما يخلص (حوالي دقيقة). اعمل reload بعدها.",
      "Synchro en arrière-plan (~1 min), puis rechargez.");
  } catch (e) { alert((e && e.message) || e); }
  finally { syncing.value = false; }
}
async function rebuild() {
  rebuilding.value = true;
  try {
    await api.call("accounting_portal.api.radar.rebuild_now", { company: currentCompany(), year: props.year });
    note.value = L("Rebuilding in the background (about 30 seconds). Reload then.", "بيتبني في الخلفية (حوالي 30 ثانية). اعمل reload بعدها.", "Recalcul en cours (~30 s).");
  } catch (e) { alert((e && e.message) || e); }
  finally { rebuilding.value = false; }
}
watch(() => props.year, load);
onMounted(load);
defineExpose({ reload: load });
</script>

<style scoped>
.hcell { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--ink-muted, #78716c); }
</style>
