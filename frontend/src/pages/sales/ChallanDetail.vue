<template>
  <div class="space-y-3.5">
    <button class="inline-flex items-center gap-1.5 text-[12px] font-semibold text-ink-3 hover:text-ink" @click="back">
      <Icon name="arrow" :size="14" class="rtl:rotate-180 rotate-180" />{{ L("Back to delivery notes", "العودة لسندات التسليم", "Retour aux bons") }}
    </button>

    <div v-if="loading" class="bg-white rounded-card border border-line shadow-card"><TableLoading :rows="4" /></div>
    <template v-else-if="d">
      <!-- Header -->
      <div class="bg-white rounded-card border border-line shadow-card p-5">
        <div class="flex items-start gap-3 flex-wrap">
          <span class="w-11 h-11 rounded-[12px] grid place-items-center flex-shrink-0" style="background:#eef6ff"><Icon name="truck" :size="20" color="#0369a1" /></span>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="text-[16px] font-bold font-mono">{{ d.name }}</span>
              <span class="text-[10px] font-bold px-2 py-0.5 rounded-full" :style="statusBadge(d.ship_status)">{{ d.ship_status }}</span>
            </div>
            <div class="text-[12px] text-ink-2 mt-0.5 truncate max-w-[460px]">{{ d.customer }}<span v-if="d.city"> · {{ d.city }}</span></div>
            <div class="text-[11px] text-ink-muted mt-0.5">{{ d.posting_date }} · {{ L("carrier", "الناقل", "transporteur") }}: {{ d.carrier }}<span v-if="d.tracking && d.tracking !== '—'"> · {{ d.tracking }}</span></div>
          </div>
          <div class="text-end">
            <div class="text-[22px] font-extrabold tnum">{{ fmt(d.grand_total) }}<span class="text-[12px] text-ink-muted ms-1">MAD</span></div>
            <a v-if="d.tracking_url" :href="d.tracking_url" target="_blank" rel="noopener" class="text-[11px] font-semibold text-accent-dark hover:underline inline-flex items-center gap-1 mt-1"><Icon name="truck" :size="12" />{{ L("Track shipment", "تتبّع الشحنة", "Suivre") }}</a>
          </div>
        </div>
        <!-- Linked docs -->
        <div v-if="d.related_orders.length || d.related_invoices.length" class="flex flex-wrap gap-2 mt-3 pt-3 border-t border-line-hair">
          <button v-for="so in d.related_orders" :key="so" @click="goOrder(so)" class="text-[11px] font-semibold px-2.5 py-1 rounded-chip bg-app-warm text-ink-2 hover:bg-app-warm/70 inline-flex items-center gap-1"><Icon name="cart" :size="12" />{{ so }}</button>
          <button v-for="si in d.related_invoices" :key="si" @click="goInvoice(si)" class="text-[11px] font-semibold px-2.5 py-1 rounded-chip bg-app-warm text-ink-2 hover:bg-app-warm/70 inline-flex items-center gap-1"><Icon name="receipt" :size="12" />{{ si }}</button>
        </div>
      </div>

      <!-- Line items -->
      <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
        <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><Icon name="box" :size="14" color="#0369a1" /><span class="text-[12px] font-bold">{{ L("Items", "الأصناف", "Articles") }}</span><span class="text-[10px] text-ink-muted">{{ d.lines.length }}</span></div>
        <div class="overflow-x-auto">
          <table class="w-full text-[12px]">
            <thead><tr style="background:#fafaf9">
              <th class="px-4 py-2 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Item", "الصنف", "Article") }}</th>
              <th class="px-4 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Qty", "الكمية", "Qté") }}</th>
              <th class="px-4 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Rate", "السعر", "Prix") }}</th>
              <th class="px-4 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Amount", "المبلغ", "Montant") }}</th>
            </tr></thead>
            <tbody>
              <tr v-for="(l, i) in d.lines" :key="i" class="border-t border-line-hair">
                <td class="px-4 py-2.5">
                  <span class="flex items-center gap-2.5">
                    <img v-if="l.image" :src="l.image" class="w-8 h-8 rounded-[7px] object-cover flex-shrink-0 border border-line-hair" />
                    <span v-else class="w-8 h-8 rounded-[7px] bg-app-warm grid place-items-center flex-shrink-0"><Icon name="box" :size="13" color="#a8a29e" /></span>
                    <span class="min-w-0"><span class="block font-medium truncate max-w-[280px]">{{ l.name }}</span><span v-if="l.sku || l.item_code" class="block text-[10px] text-ink-muted font-mono">{{ l.sku || l.item_code }}</span></span>
                  </span>
                </td>
                <td class="px-4 py-2.5 text-end tnum">{{ l.qty }}</td>
                <td class="px-4 py-2.5 text-end tnum">{{ fmt(l.rate) }}</td>
                <td class="px-4 py-2.5 text-end tnum font-semibold">{{ fmt(l.amount) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <DocHub v-if="route.query.id" doctype="Delivery Note" :name="route.query.id" class="mt-1" />
    </template>
  </div>
</template>

<script setup>
import { ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import DocHub from "@/components/DocHub.vue";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";

const route = useRoute();
const router = useRouter();
const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const d = ref(null);
const loading = ref(true);

function back() { router.push("/accounting/sales/challans"); }
function goOrder(so) { router.push({ path: "/accounting/sales/orders", query: { id: so } }); }
function goInvoice(si) { router.push({ path: "/accounting/sales/invoices", query: { id: si } }); }

async function load() {
  const id = route.query.id;
  if (!id) { loading.value = false; return; }
  loading.value = true; d.value = null;
  try { d.value = await api.call("accounting_portal.api.sales.get_challan", { name: id }); }
  catch { d.value = null; }
  finally { loading.value = false; }
  if (!d.value) router.replace({ path: "/accounting/sales/challans", query: {} });
}
watch(() => route.query.id, load, { immediate: true });

function statusBadge(s) {
  const v = String(s || "").toLowerCase();
  if (v.includes("deliver") && !v.includes("out") && !v.includes("excep")) return "background:#ecfdf5;color:#047857";
  if (v.includes("transit") || v.includes("out for")) return "background:#eff6ff;color:#0369a1";
  if (v.includes("excep") || v.includes("fail") || v.includes("return")) return "background:#fef2f2;color:#b91c1c";
  return "background:#f5f5f4;color:#57534e";
}
</script>
