<template>
  <div class="fixed inset-0 z-[100] flex items-start justify-center p-4 sm:p-8 overflow-y-auto" style="background:rgba(28,25,23,.45)" @click.self="$emit('close')">
    <div class="bg-white rounded-[18px] shadow-cardHover w-full max-w-3xl my-6 overflow-hidden">
      <div class="flex items-center gap-2.5 px-5 py-4 border-b border-line">
        <span class="w-8 h-8 rounded-[10px] grid place-items-center" style="background:#fef2f2"><Icon name="refresh" :size="16" color="#be123c" /></span>
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2">
            <span class="text-[14px] font-bold font-mono">{{ name }}</span>
            <span v-if="d" class="text-[10px] font-bold px-2 py-0.5 rounded-full" :style="statusStyle(d.status)">{{ d.status }}</span>
          </div>
          <div class="text-[11px] text-ink-muted">{{ L("Warehouse return batch","دفعة إرجاع المخزن","Lot de retour entrepôt") }}<span v-if="d && d.posting_date"> · {{ d.posting_date }}</span></div>
        </div>
        <button class="text-ink-3 hover:text-ink" @click="$emit('close')"><Icon name="close" :size="18" /></button>
      </div>

      <div class="p-5 space-y-3.5">
        <div v-if="loading" class="py-10 text-center text-[12px] text-ink-muted inline-flex items-center gap-2 w-full justify-center"><SpinnerIcon :size="16" /> {{ L("Loading…","تحميل…","Chargement…") }}</div>
        <div v-else-if="!d" class="py-10 text-center text-[12px] text-ink-muted">{{ L("Not found.","غير موجود.","Introuvable.") }}</div>
        <template v-else>
          <!-- stat tiles -->
          <div class="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
            <div class="rounded-[11px] px-3 py-2.5 border" style="background:#fafaf9;border-color:#f0efed">
              <div class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Orders","الطلبات","Commandes") }}</div>
              <div class="text-[18px] font-extrabold tnum mt-0.5">{{ (d.total_orders || d.orders.length).toLocaleString() }}</div>
            </div>
            <div class="rounded-[11px] px-3 py-2.5 border" style="background:#ecfdf5;border-color:#a7f3d0;color:#047857">
              <div class="text-[10px] font-bold uppercase tracking-wider opacity-70">{{ L("Items back","أصناف رجعت","Articles") }}</div>
              <div class="text-[18px] font-extrabold tnum mt-0.5">{{ Math.round(d.total_actual_qty).toLocaleString() }}</div>
            </div>
            <div class="rounded-[11px] px-3 py-2.5 border" :style="d.total_missing_qty ? 'background:#fffbeb;border-color:#fde68a;color:#b45309' : 'background:#fafaf9;border-color:#f0efed'">
              <div class="text-[10px] font-bold uppercase tracking-wider opacity-70">{{ L("Missing","ناقص","Manquant") }}</div>
              <div class="text-[18px] font-extrabold tnum mt-0.5">{{ Math.round(d.total_missing_qty).toLocaleString() }}</div>
            </div>
            <div class="rounded-[11px] px-3 py-2.5 border" style="background:#f5f3ff;border-color:#ddd6fe;color:#7c3aed">
              <div class="text-[10px] font-bold uppercase tracking-wider opacity-70">{{ L("Return rate","نسبة الإرجاع","Taux retour") }}</div>
              <div class="text-[18px] font-extrabold tnum mt-0.5">{{ Math.round(d.return_percentage) }}%</div>
            </div>
          </div>

          <div v-if="d.missing_skus" class="text-[11px] bg-amber-50 border border-amber-200 rounded-chip px-3 py-2 text-amber-800">
            <b>{{ L("Missing SKUs","أصناف ناقصة","SKUs manquants") }}:</b> {{ d.missing_skus }}
          </div>

          <!-- items -->
          <div class="flex items-center gap-2 text-[11px] text-ink-muted">
            <span class="font-bold uppercase tracking-wider">{{ L("Scanned items","الأصناف المسحوبة","Articles scannés") }}</span>
            <span>· {{ d.n_items }}</span>
            <span v-if="d.sales_returns" class="ms-auto text-ink-3">{{ L("Sales returns","مرتجعات","Retours") }}: {{ d.sales_returns }}</span>
          </div>
          <div class="border border-line rounded-[10px] overflow-hidden max-h-[260px] overflow-y-auto">
            <table class="w-full text-[12px]">
              <thead class="sticky top-0"><tr style="background:#fafaf9">
                <th class="px-3 py-2 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Item","الصنف","Article") }}</th>
                <th class="px-3 py-2 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("AWB","AWB","AWB") }}</th>
                <th class="px-3 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Ordered","مطلوب","Cmdé") }}</th>
                <th class="px-3 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Back","رجع","Reçu") }}</th>
                <th class="px-3 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Missing","ناقص","Manq.") }}</th>
              </tr></thead>
              <tbody>
                <tr v-for="(it, i) in d.items" :key="i" class="border-t border-line-hair">
                  <td class="px-3 py-1.5"><div class="font-medium truncate max-w-[260px]">{{ it.item_name || it.item_code }}</div><div class="text-[10px] text-ink-muted font-mono">{{ it.sku }}</div></td>
                  <td class="px-3 py-1.5 font-mono text-[11px] text-ink-3">{{ it.awb || "—" }}</td>
                  <td class="px-3 py-1.5 text-end tnum">{{ it.ordered_qty }}</td>
                  <td class="px-3 py-1.5 text-end tnum font-semibold text-success-dark">{{ it.actual_qty }}</td>
                  <td class="px-3 py-1.5 text-end tnum" :class="it.missing_qty ? 'text-sale font-semibold' : 'text-ink-muted'">{{ Math.round(it.missing_qty) || "—" }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import SpinnerIcon from "@/components/shared/SpinnerIcon.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";

const props = defineProps({ name: { type: String, required: true } });
defineEmits(["close"]);
const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const d = ref(null);
const loading = ref(true);

function statusStyle(s) {
  if (s === "Returned") return "background:#ecfdf5;color:#047857";
  if (s === "Cancelled") return "background:#fef2f2;color:#b91c1c";
  if (!s || s === "Draft") return "background:#f1efe8;color:#5f5e5a";
  return "background:#fffbeb;color:#b45309";
}

watch(() => props.name, async (nm) => {
  if (!nm) return;
  loading.value = true; d.value = null;
  try { d.value = await api.call("accounting_portal.api.cod.get_return_shipment", { name: nm, company: currentCompany() }); }
  catch { d.value = null; }
  finally { loading.value = false; }
}, { immediate: true });
</script>
