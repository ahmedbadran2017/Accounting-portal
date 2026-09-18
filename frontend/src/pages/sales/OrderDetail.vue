<template>
  <div v-if="o" class="max-w-[1080px] mx-auto space-y-3.5">
    <button class="inline-flex items-center gap-1.5 text-[12px] font-medium text-ink-3 hover:text-ink" @click="back">
      <span class="rotate-180 rtl:rotate-0"><Icon name="arrow" :size="15" /></span>{{ L("Back to orders","العودة للطلبات","Retour aux commandes") }}
    </button>
    <!-- document action bar (DocHub teleports Create / status / submit / edit / print here) -->
    <!-- The action bar. It used to live inside DocHub at the foot of the page and
         be teleported up here, which made it depend on this div existing at the
         moment DocHub mounted — a DOM probe in an onMounted. When that probe read
         false the whole bar rendered at the bottom instead, and when the target
         was not reachable it rendered nowhere at all. The page draws it now. -->
    <DocActions v-if="route.query.id" :doctype="DOCTYPE" :name="route.query.id"
                class="relative z-20 bg-white rounded-card border border-line shadow-card"
                @changed="load" @open="(n) => router.push({ query: { id: n } })" />

    <!-- PE-only: carrier ref is on the payment but not the order → shows as Delivered -->
    <div v-if="fixable.fixable" class="flex items-center gap-3 px-4 py-2.5 rounded-card border border-amber-200 bg-amber-50/70">
      <Icon name="alert" :size="16" color="#b45309" class="shrink-0" />
      <div class="min-w-0 text-[12px]">
        <span class="font-bold text-amber-800">{{ L("Collected via payment only","محصّل عبر الدفعة فقط","Encaissé via paiement") }}</span>
        <span class="text-amber-700"> — {{ L("carrier ref","مرجع الشحن","réf.") }} <b class="font-mono">{{ fixable.ref }}</b> {{ L("is on the payment, not this order — so it shows Delivered.","على الدفعة مش الأوردر — فبيظهر Delivered.","sur le paiement.") }}</span>
      </div>
      <button v-if="canFix" type="button" :disabled="fixing" class="ms-auto shrink-0 inline-flex items-center gap-1.5 h-8 px-3 rounded-chip text-[12px] font-bold text-white bg-amber-600 hover:bg-amber-700 disabled:opacity-60" @click="stampRef">
        <Icon :name="fixing ? 'clock' : 'check'" :size="13" />{{ fixing ? L("Stamping…","جارٍ…","…") : L("Stamp & fix","اختم وصلّح","Corriger") }}
      </button>
    </div>

    <!-- Header card -->
    <div class="bg-white rounded-[16px] border border-line px-5 py-[18px] shadow-card">
      <div class="flex items-start gap-3.5 flex-wrap">
        <div class="flex-1 min-w-[200px]">
          <div class="flex items-center gap-2.5 flex-wrap">
            <span class="text-[20px] font-bold font-mono">{{ o.id }}</span>
            <span class="inline-block text-[11px] font-bold px-2.5 py-1 rounded-[7px] border"
                  :style="{ background: sm.bg, color: sm.fg, borderColor: sm.bd }">{{ stateLabel(o.state, locale) }}</span>
            <span class="inline-block text-[11px] font-bold px-2.5 py-1 rounded-[7px] border"
                  :style="post.posted ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#f5f5f4;color:#a8a29e;border-color:#e7e5e4'">{{ post.label }}</span>
          </div>
          <div class="flex items-center gap-3.5 mt-[7px] text-[12px] text-ink-3 flex-wrap">
            <span class="inline-flex items-center gap-1.5">
              <span class="w-6 h-6 rounded-full grid place-items-center text-white text-[11px] font-bold" :style="{ background: AV[o.av] }">{{ o.initials }}</span>{{ o.customer }}
            </span>
            <span>{{ o.date }}</span>
          </div>
        </div>
        <div class="text-end">
          <div class="text-[11px] text-ink-muted font-semibold">{{ L("Order total (gross)","إجمالي الطلب","Total commande (TTC)") }}</div>
          <div class="text-[24px] font-bold tnum">{{ o.value }} <span class="text-[13px] text-ink-3">{{ o.currency }}</span></div>
        </div>
      </div>
      <!-- The chip row that used to sit here repeated all ten of its facts
           further down the page — carrier, tracking and shipment three times
           over, net and VAT twice, city twice — and six of the ten were a dash
           or a zero on a normal order. Each fact is stated once now, in the card
           it belongs to. -->
    </div>

    <!-- Products -->
    <div v-if="items.length" class="bg-white rounded-[14px] border border-line shadow-card overflow-hidden">
      <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2">
        <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#faf6f4"><Icon name="box" :size="14" color="#0b5c4f" /></span>
        <span class="text-[13px] font-bold">{{ L("Products","المنتجات","Produits") }}</span>
        <span class="text-[11px] text-ink-muted">{{ items.length }} {{ L("items","صنف","articles") }}</span>
      </div>
      <div>
        <div v-for="(it, i) in items" :key="i" class="flex items-center gap-3.5 px-4 py-3 border-t border-line-hair first:border-t-0 hover:bg-app-warm/40">
          <img v-if="it.image" :src="it.image" :alt="it.name" loading="lazy"
               class="w-14 h-14 rounded-[10px] object-cover border border-line bg-app-warm flex-shrink-0"
               @error="$event.target.style.display='none'" />
          <span v-else class="w-14 h-14 rounded-[10px] grid place-items-center bg-app-warm border border-line flex-shrink-0"><Icon name="box" :size="20" color="#a8a29e" /></span>
          <div class="flex-1 min-w-0">
            <div class="text-[13px] font-semibold leading-snug">{{ it.name }}</div>
            <div class="text-[11px] text-ink-3 mt-0.5">{{ it.qty }} × {{ it.rate }} <span class="text-ink-muted">{{ o.currency }}</span></div>
          </div>
          <div class="text-[14px] font-bold tnum whitespace-nowrap">{{ it.amount }} <span class="text-[11px] text-ink-muted">{{ o.currency }}</span></div>
        </div>
      </div>
    </div>

    <!-- Operational + financial sections -->
    <div class="grid sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
      <FactCard :title="L('Customer &amp; shipping','العميل والشحن','Client &amp; livraison')"
                icon="user" tint="#eff6ff" color="#0369a1" :facts="shippingFacts"
                :empty="L('No address on this order.','لا يوجد عنوان على هذا الطلب.','Aucune adresse sur cette commande.')" />

      <FactCard :title="L('Delivery','التسليم','Livraison')"
                icon="truck" tint="#fff7ed" color="#c2410c" :facts="deliveryFacts"
                :empty="L('Not handed to a carrier yet.','لم تُسلَّم لشركة شحن بعد.','Pas encore remise au transporteur.')">
        <a v-if="tracking.url" :href="tracking.url" target="_blank" rel="noopener" class="mt-2.5 inline-flex items-center gap-1.5 text-[12px] font-bold text-accent hover:text-accent-dark"><Icon name="arrow" :size="13" class="rtl:rotate-180" />{{ L("Track shipment","تتبّع الشحنة","Suivre") }}</a>
      </FactCard>

      <FactCard :title="L('Financial','المالي','Financier')"
                icon="coins" tint="#ecfdf5" color="#047857" :facts="financialFacts" />
    </div>

    <!-- Related documents -->
    <div class="bg-white rounded-[14px] border border-line p-4 shadow-card">
      <div class="flex items-center gap-2 mb-2.5"><span class="w-[24px] h-[24px] rounded-[7px] grid place-items-center" style="background:#f5f3ff"><Icon name="layers" :size="13" color="#7c3aed" /></span><span class="text-[13px] font-bold">{{ L("Related documents","المستندات المرتبطة","Documents liés") }}</span></div>
      <div v-if="related.invoices.length || related.deliveries.length || related.payments.length" class="flex flex-wrap gap-2">
        <button v-for="dn in related.deliveries" :key="dn" @click="openDoc('sales','challans',dn)" class="inline-flex items-center gap-1.5 text-[12px] font-semibold px-2.5 py-1.5 rounded-chip border border-line-2 bg-app-warm hover:bg-white"><Icon name="truck" :size="12" color="#c2410c" />{{ dn }}</button>
        <button v-for="inv in related.invoices" :key="inv" @click="openDoc('sales','invoices',inv)" class="inline-flex items-center gap-1.5 text-[12px] font-semibold px-2.5 py-1.5 rounded-chip border border-line-2 bg-app-warm hover:bg-white"><Icon name="doc" :size="12" color="#0b5c4f" />{{ inv }}</button>
        <button v-for="pe in related.payments" :key="pe" @click="openDoc('sales','payments',pe)" class="inline-flex items-center gap-1.5 text-[12px] font-semibold px-2.5 py-1.5 rounded-chip border border-line-2 bg-app-warm hover:bg-white"><Icon name="coins" :size="12" color="#047857" />{{ pe }}</button>
      </div>
      <div v-else class="text-[12px] text-ink-muted">{{ L("No delivery, invoice or payment yet — this order hasn't reached a posting state.","لا يوجد تسليم أو فاتورة أو دفعة بعد — الطلب لم يصل لحالة ترحيل.","Aucun document lié pour le moment.") }}</div>
    </div>

    <div class="grid lg:grid-cols-[1fr_1.25fr] gap-3.5">
      <!-- Lifecycle timeline -->
      <div class="bg-white rounded-[14px] border border-line p-[17px] shadow-card">
        <div class="text-[13px] font-bold mb-3.5">{{ L("Lifecycle & posting","الدورة والترحيل","Cycle & passation") }}</div>
        <div class="flex flex-col">
          <div v-for="(e, i) in timeline" :key="i" class="flex gap-[11px]">
            <div class="flex flex-col items-center flex-shrink-0">
              <span class="w-6 h-6 rounded-full grid place-items-center flex-shrink-0"
                    :style="e.done ? 'background:linear-gradient(135deg,#34d399,#059669);color:#fff' : 'background:#f4f2f0;color:#bcb6b0;border:1px solid #e7e5e4'">
                <Icon :name="e.done ? 'check' : e.icon" :size="12" />
              </span>
              <span v-if="!e.last" class="w-0.5 flex-1 min-h-[18px]" :style="{ background: e.done ? '#a7f3d0' : '#f0efed' }"></span>
            </div>
            <div class="pb-4 flex-1">
              <div class="flex items-center gap-2">
                <span class="text-[13px] font-bold" :class="e.done ? 'text-ink' : 'text-ink-muted'">{{ e.title }}</span>
                <span class="text-[11px] text-ink-muted">{{ e.time }}</span>
              </div>
              <div class="text-[12px] text-ink-3 mt-0.5 leading-snug">{{ e.desc }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Auto-posted journal -->
      <div class="bg-white rounded-[14px] border border-line p-[17px] shadow-card">
        <div class="flex items-center gap-2 mb-1.5">
          <div class="flex-1">
            <div class="text-[13px] font-bold">{{ L("Auto-posted journal","قيد تلقائي","Écriture auto-passée") }}</div>
            <div class="text-[11px] text-ink-muted">{{ L("No manual GL — every state posts itself","لا قيود يدوية — كل حالة تُرحّل نفسها","Aucun GL manuel — chaque état se passe seul") }}</div>
          </div>
          <span v-if="!journal.noJournal" class="inline-flex items-center gap-1 text-[11px] font-bold px-2 py-[3px] rounded-full" style="background:#ecfdf5;color:#047857;border:1px solid #a7f3d0">
            <Icon name="check" :size="11" />{{ L("Balanced","متوازن","Équilibrée") }}
          </span>
        </div>
        <div class="flex flex-col gap-3 mt-2.5">
          <div v-for="(j, i) in journal.stages" :key="i" class="border border-line rounded-[11px] overflow-hidden">
            <div class="flex items-center gap-2 px-3 py-2.5 bg-app-warm2 border-b border-line-hair">
              <span class="w-1.5 h-1.5 rounded-full" :style="{ background: j.dot }"></span>
              <span class="text-[12px] font-bold">{{ j.stage }}</span>
              <span class="text-[11px] text-ink-muted ms-auto font-mono">{{ j.ref }}</span>
            </div>
            <table class="w-full">
              <tbody>
                <tr v-for="(ln, k) in j.lines" :key="k" class="border-t border-line-hair">
                  <td class="px-3 py-[7px] text-[12px] text-ink-2" :class="ln.indent ? 'ps-7' : ''">{{ ln.acc }}</td>
                  <td class="px-2 py-[7px] text-end text-[12px] font-semibold w-[90px] text-success-dark">{{ ln.dr || "" }}</td>
                  <td class="px-3 py-[7px] text-end text-[12px] font-semibold w-[90px] text-sale">{{ ln.cr || "" }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-if="journal.noJournal" class="text-center px-3 py-6 text-ink-muted text-[12px] leading-relaxed">{{ journal.msg }}</div>
        </div>
      </div>
    </div>

    <DocHub v-if="route.query.id" :doctype="DOCTYPE" :name="route.query.id" class="mt-1" />
  </div>
  <div v-else-if="loading" class="py-20 text-center text-[12px] text-ink-muted">{{ t("common.loading") }}</div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import FactCard from "@/components/FactCard.vue";
import DocHub from "@/components/DocHub.vue";
import DocActions from "@/components/DocActions.vue";
import { STATE_META, stateLabel, AV, postingInfo } from "@/data/orders";
import { useOrders } from "@/composables/useOrders";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useAuth } from "@/composables/useAuth";
import { useToast } from "@/composables/useToast";

const { t, locale } = useI18n();
const route = useRoute();
const router = useRouter();
const { loadDetail } = useOrders();
const DOCTYPE = "Sales Order";

// Live get_order (real posted journal) with sample fallback; rebuilt on id/locale change.
const vm = ref(null);
const loading = ref(true);
const { can } = useAuth();
const toast = useToast();
const canFix = computed(() => can("manage_users"));
const fixable = ref({ fixable: false });
const fixing = ref(false);

async function load() {
  loading.value = true;
  vm.value = await loadDetail(route.query.id, locale.value);
  loading.value = false;
  if (route.query.id && !vm.value) router.replace("/accounting/sales/orders");
  loadFixable();
}
watch(() => [route.query.id, locale.value], load, { immediate: true });

async function loadFixable() {
  fixable.value = { fixable: false };
  if (!route.query.id) return;
  try { fixable.value = await api.call("accounting_portal.api.cod.pe_ref_fixable", { company: currentCompany(), order: route.query.id }) || { fixable: false }; }
  catch { fixable.value = { fixable: false }; }
}
async function stampRef() {
  if (fixing.value) return;
  fixing.value = true;
  try {
    await api.call("accounting_portal.api.cod.backfill_pe_refs", { company: currentCompany(), orders: [route.query.id], dry_run: 0 });
    toast.success(L("Stamped — now collected", "تم الختم — أصبح محصّلاً", "Corrigé — encaissé"));
    fixable.value = { fixable: false };
    load();
  } catch (e) {
    toast.error(L("Failed", "فشل", "Échec") + ": " + String(e?.message || e).slice(0, 120));
  } finally { fixing.value = false; }
}

const o = computed(() => vm.value?.o || null);
const dims = computed(() => vm.value?.dims || []);
const items = computed(() => vm.value?.items || []);
const shipping = computed(() => vm.value?.shipping || {});
const tracking = computed(() => vm.value?.tracking || {});
const financial = computed(() => vm.value?.financial || {});
const related = computed(() => vm.value?.related || { invoices: [], deliveries: [], payments: [] });
const timeline = computed(() => vm.value?.timeline || []);
const journal = computed(() => vm.value?.journal || { noJournal: true, msg: "" });
function openDoc(module, sub, id) { router.push({ path: `/accounting/${module}/${sub}`, query: { id } }); }
const sm = computed(() => STATE_META[o.value?.state] || STATE_META.placed);
const post = computed(() => postingInfo(o.value?.state, locale.value));

const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

// FactCard drops any row whose value is blank, so these lists can name every
// field the document *could* carry and the card shows only what it has.
const shippingFacts = computed(() => [
  { label: L("Phone", "الهاتف", "Tél."), value: shipping.value.phone, num: true },
  { label: L("City", "المدينة", "Ville"), value: shipping.value.city },
  { label: L("Governorate", "المحافظة", "Région"), value: shipping.value.governorate },
]);

const deliveryFacts = computed(() => [
  { label: L("Carrier", "الناقل", "Transporteur"), value: tracking.value.carrier },
  { label: L("Tracking #", "رقم التتبّع", "N° suivi"), value: tracking.value.number, mono: true },
  { label: L("Status", "الحالة", "Statut"), value: tracking.value.shipment },
  { label: L("Expected", "متوقّع", "Prévu"), value: tracking.value.expected },
  { label: L("Remittance ref", "مرجع التحصيل", "Réf. remise"), value: tracking.value.remittance, mono: true },
]);

const financialFacts = computed(() => {
  const f = financial.value;
  // "VAT 20%" beside a zero asserts a rate the order does not carry. Nine
  // percent of 2026 orders have no tax rows at all.
  const noTax = !Number(String(f.vat || "0").replace(/[^\d.-]/g, ""));
  return [
    { label: L("Net", "الصافي", "Net"), value: f.net, num: true },
    { label: L("VAT", "ض.ق.م", "TVA"), value: f.vat, num: true,
      note: noTax ? L("no tax on this order", "بدون ضريبة على هذا الطلب", "aucune taxe") : "" },
    { label: L("Gross", "الإجمالي", "TTC"), value: f.gross, num: true, strong: true, rule: true },
    { label: L("Advance paid", "مدفوع مقدمًا", "Avance"), value: Number(String(f.advance || 0).replace(/[^\d.-]/g, "")) ? f.advance : "", num: true },
    { label: L("Billed / delivered", "مفوتر / مُسلّم", "Facturé / livré"),
      value: (f.billed || f.delivered) ? `${f.billed}% / ${f.delivered}%` : "", num: true },
  ];
});
function back() { router.push({ path: "/accounting/sales/orders" }); }
</script>
