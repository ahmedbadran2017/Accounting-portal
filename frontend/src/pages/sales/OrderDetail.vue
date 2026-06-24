<template>
  <div v-if="o" class="max-w-[1080px] mx-auto space-y-3.5">
    <button class="inline-flex items-center gap-1.5 text-[12px] font-medium text-ink-3 hover:text-ink" @click="back">
      <span class="rtl:rotate-180"><Icon name="arrow" :size="15" /></span>{{ L("Back to orders","العودة للطلبات","Retour aux commandes") }}
    </button>

    <!-- Header card -->
    <div class="bg-white rounded-[16px] border border-line px-5 py-[18px] shadow-card">
      <div class="flex items-start gap-3.5 flex-wrap">
        <div class="flex-1 min-w-[200px]">
          <div class="flex items-center gap-2.5 flex-wrap">
            <span class="text-[19px] font-bold font-mono">{{ o.id }}</span>
            <span class="inline-block text-[11px] font-bold px-2.5 py-1 rounded-[7px] border"
                  :style="{ background: sm.bg, color: sm.fg, borderColor: sm.bd }">{{ stateLabel(o.state, locale) }}</span>
            <span class="inline-block text-[10px] font-bold px-2.5 py-1 rounded-[7px] border"
                  :style="post.posted ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#f5f5f4;color:#a8a29e;border-color:#e7e5e4'">{{ post.label }}</span>
          </div>
          <div class="flex items-center gap-3.5 mt-[7px] text-[12px] text-ink-3 flex-wrap">
            <span class="inline-flex items-center gap-1.5">
              <span class="w-6 h-6 rounded-full grid place-items-center text-white text-[9px] font-bold" :style="{ background: AV[o.av] }">{{ o.initials }}</span>{{ o.customer }}
            </span>
            <span>{{ o.city }}</span><span>{{ o.carrier }}</span><span>{{ o.date }}</span>
          </div>
        </div>
        <div class="text-end">
          <div class="text-[10.5px] text-ink-muted font-semibold">{{ L("Order total (gross)","إجمالي الطلب","Total commande (TTC)") }}</div>
          <div class="text-[24px] font-bold tnum">{{ o.value }} <span class="text-[13px] text-ink-3">MAD</span></div>
        </div>
      </div>
      <!-- Dimensions -->
      <div class="flex gap-2 flex-wrap mt-3.5 pt-3.5 border-t border-line-hair">
        <span v-for="d in dims" :key="d.k" class="inline-flex items-center gap-1.5 text-[11px] px-2.5 py-[5px] rounded-[8px] bg-app-warm2 border border-line text-ink-2">
          <span class="font-semibold text-ink-muted">{{ d.k }}</span>{{ d.v || "—" }}
        </span>
      </div>
    </div>

    <!-- Products -->
    <div v-if="items.length" class="bg-white rounded-[14px] border border-line shadow-card overflow-hidden">
      <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2">
        <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#faf6f4"><Icon name="box" :size="14" color="#a33a22" /></span>
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
            <div class="text-[12.5px] font-semibold leading-snug">{{ it.name }}</div>
            <div class="text-[11px] text-ink-3 mt-0.5">{{ it.qty }} × {{ it.rate }} <span class="text-ink-muted">MAD</span></div>
          </div>
          <div class="text-[13.5px] font-bold tnum whitespace-nowrap">{{ it.amount }} <span class="text-[11px] text-ink-muted">MAD</span></div>
        </div>
      </div>
    </div>

    <!-- Operational + financial sections -->
    <div class="grid sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
      <!-- Customer & shipping -->
      <div class="bg-white rounded-[14px] border border-line p-4 shadow-card">
        <div class="flex items-center gap-2 mb-2.5"><span class="w-[24px] h-[24px] rounded-[7px] grid place-items-center" style="background:#eff6ff"><Icon name="user" :size="13" color="#0369a1" /></span><span class="text-[12.5px] font-bold">{{ L("Customer & shipping","العميل والشحن","Client & livraison") }}</span></div>
        <dl class="space-y-1.5 text-[12px]">
          <div class="flex justify-between gap-2"><dt class="text-ink-muted">{{ L("Phone","الهاتف","Tél.") }}</dt><dd class="font-medium tnum">{{ shipping.phone }}</dd></div>
          <div class="flex justify-between gap-2"><dt class="text-ink-muted">{{ L("City","المدينة","Ville") }}</dt><dd class="font-medium">{{ shipping.city }}</dd></div>
          <div class="flex justify-between gap-2"><dt class="text-ink-muted">{{ L("Governorate","المحافظة","Région") }}</dt><dd class="font-medium">{{ shipping.governorate }}</dd></div>
        </dl>
      </div>
      <!-- Tracking -->
      <div class="bg-white rounded-[14px] border border-line p-4 shadow-card">
        <div class="flex items-center gap-2 mb-2.5"><span class="w-[24px] h-[24px] rounded-[7px] grid place-items-center" style="background:#fff7ed"><Icon name="truck" :size="13" color="#c2410c" /></span><span class="text-[12.5px] font-bold">{{ L("Tracking","التتبّع","Suivi") }}</span></div>
        <dl class="space-y-1.5 text-[12px]">
          <div class="flex justify-between gap-2"><dt class="text-ink-muted">{{ L("Carrier","الناقل","Transporteur") }}</dt><dd class="font-medium">{{ tracking.carrier }}</dd></div>
          <div class="flex justify-between gap-2"><dt class="text-ink-muted">{{ L("Tracking #","رقم التتبّع","N° suivi") }}</dt><dd class="font-medium font-mono">{{ tracking.number }}</dd></div>
          <div class="flex justify-between gap-2"><dt class="text-ink-muted">{{ L("Status","الحالة","Statut") }}</dt><dd class="font-medium">{{ tracking.shipment }}</dd></div>
        </dl>
        <a v-if="tracking.url" :href="tracking.url" target="_blank" rel="noopener" class="mt-2.5 inline-flex items-center gap-1.5 text-[11.5px] font-bold text-accent hover:text-accent-dark"><Icon name="arrow" :size="13" class="rtl:rotate-180" />{{ L("Track shipment","تتبّع الشحنة","Suivre") }}</a>
      </div>
      <!-- Financial -->
      <div class="bg-white rounded-[14px] border border-line p-4 shadow-card">
        <div class="flex items-center gap-2 mb-2.5"><span class="w-[24px] h-[24px] rounded-[7px] grid place-items-center" style="background:#ecfdf5"><Icon name="coins" :size="13" color="#047857" /></span><span class="text-[12.5px] font-bold">{{ L("Financial","المالي","Financier") }}</span></div>
        <dl class="space-y-1.5 text-[12px]">
          <div class="flex justify-between gap-2"><dt class="text-ink-muted">{{ L("Net","الصافي","Net") }}</dt><dd class="font-medium tnum">{{ financial.net }}</dd></div>
          <div class="flex justify-between gap-2"><dt class="text-ink-muted">{{ L("VAT 20%","ض.ق.م","TVA") }}</dt><dd class="font-medium tnum">{{ financial.vat }}</dd></div>
          <div class="flex justify-between gap-2 pt-1 border-t border-line-hair"><dt class="font-semibold">{{ L("Gross","الإجمالي","TTC") }}</dt><dd class="font-bold tnum">{{ financial.gross }}</dd></div>
          <div class="flex items-center gap-2 pt-1"><dt class="text-ink-muted flex-1">{{ L("Billed / delivered","مفوتر / مُسلّم","Facturé / livré") }}</dt><dd class="font-medium tnum">{{ financial.billed }}% / {{ financial.delivered }}%</dd></div>
        </dl>
      </div>
    </div>

    <!-- Related documents -->
    <div class="bg-white rounded-[14px] border border-line p-4 shadow-card">
      <div class="flex items-center gap-2 mb-2.5"><span class="w-[24px] h-[24px] rounded-[7px] grid place-items-center" style="background:#f5f3ff"><Icon name="layers" :size="13" color="#7c3aed" /></span><span class="text-[12.5px] font-bold">{{ L("Related documents","المستندات المرتبطة","Documents liés") }}</span></div>
      <div v-if="related.invoices.length || related.deliveries.length || related.payments.length" class="flex flex-wrap gap-2">
        <button v-for="dn in related.deliveries" :key="dn" @click="openDoc('sales','challans',dn)" class="inline-flex items-center gap-1.5 text-[11.5px] font-semibold px-2.5 py-1.5 rounded-chip border border-line-2 bg-app-warm hover:bg-white"><Icon name="truck" :size="12" color="#c2410c" />{{ dn }}</button>
        <button v-for="inv in related.invoices" :key="inv" @click="openDoc('sales','invoices',inv)" class="inline-flex items-center gap-1.5 text-[11.5px] font-semibold px-2.5 py-1.5 rounded-chip border border-line-2 bg-app-warm hover:bg-white"><Icon name="doc" :size="12" color="#a33a22" />{{ inv }}</button>
        <button v-for="pe in related.payments" :key="pe" @click="openDoc('sales','payments',pe)" class="inline-flex items-center gap-1.5 text-[11.5px] font-semibold px-2.5 py-1.5 rounded-chip border border-line-2 bg-app-warm hover:bg-white"><Icon name="coins" :size="12" color="#047857" />{{ pe }}</button>
      </div>
      <div v-else class="text-[11.5px] text-ink-muted">{{ L("No delivery, invoice or payment yet — this order hasn't reached a posting state.","لا يوجد تسليم أو فاتورة أو دفعة بعد — الطلب لم يصل لحالة ترحيل.","Aucun document lié pour le moment.") }}</div>
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
                <span class="text-[12.5px] font-bold" :class="e.done ? 'text-ink' : 'text-ink-muted'">{{ e.title }}</span>
                <span class="text-[10.5px] text-ink-muted">{{ e.time }}</span>
              </div>
              <div class="text-[11.5px] text-ink-3 mt-0.5 leading-snug">{{ e.desc }}</div>
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
          <span v-if="!journal.noJournal" class="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-[3px] rounded-full" style="background:#ecfdf5;color:#047857;border:1px solid #a7f3d0">
            <Icon name="check" :size="11" />{{ L("Balanced","متوازن","Équilibrée") }}
          </span>
        </div>
        <div class="flex flex-col gap-3 mt-2.5">
          <div v-for="(j, i) in journal.stages" :key="i" class="border border-line rounded-[11px] overflow-hidden">
            <div class="flex items-center gap-2 px-3 py-2.5 bg-app-warm2 border-b border-line-hair">
              <span class="w-1.5 h-1.5 rounded-full" :style="{ background: j.dot }"></span>
              <span class="text-[11.5px] font-bold">{{ j.stage }}</span>
              <span class="text-[10.5px] text-ink-muted ms-auto font-mono">{{ j.ref }}</span>
            </div>
            <table class="w-full">
              <tbody>
                <tr v-for="(ln, k) in j.lines" :key="k" class="border-t border-line-hair">
                  <td class="px-3 py-[7px] text-[11.5px] text-ink-2" :class="ln.indent ? 'ps-7' : ''">{{ ln.acc }}</td>
                  <td class="px-2 py-[7px] text-end text-[11.5px] font-semibold w-[90px] text-success-dark">{{ ln.dr || "" }}</td>
                  <td class="px-3 py-[7px] text-end text-[11.5px] font-semibold w-[90px] text-sale">{{ ln.cr || "" }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-if="journal.noJournal" class="text-center px-3 py-6 text-ink-muted text-[12px] leading-relaxed">{{ journal.msg }}</div>
        </div>
      </div>
    </div>
  </div>
  <div v-else class="py-20 text-center text-[12px] text-ink-muted">{{ t("common.error_loading") }}</div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { STATE_META, stateLabel, AV, postingInfo } from "@/data/orders";
import { useOrders } from "@/composables/useOrders";

const { t, locale } = useI18n();
const route = useRoute();
const router = useRouter();
const { loadDetail } = useOrders();

// Live get_order (real posted journal) with sample fallback; rebuilt on id/locale change.
const vm = ref(null);
async function load() { vm.value = await loadDetail(route.query.id, locale.value); }
watch(() => [route.query.id, locale.value], load, { immediate: true });

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
function back() { router.push({ path: "/accounting/sales/orders" }); }
</script>
