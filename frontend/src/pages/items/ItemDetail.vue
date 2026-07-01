<template>
  <div class="space-y-3.5">
    <button class="inline-flex items-center gap-1.5 text-[12px] font-semibold text-ink-3 hover:text-ink" @click="back">
      <Icon name="arrow" :size="14" class="rtl:rotate-180 rotate-180" />{{ L("Back to items","العودة للأصناف","Retour aux articles") }}
    </button>

    <div v-if="loading" class="bg-white rounded-card border border-line shadow-card"><TableLoading :rows="4" /></div>
    <template v-else-if="d">
      <!-- Header + margin -->
      <div class="bg-white rounded-card border border-line shadow-card p-5">
        <div class="flex items-start gap-3.5 flex-wrap">
          <img v-if="d.image" :src="d.image" class="w-16 h-16 rounded-[12px] object-cover flex-shrink-0 border border-line-hair" />
          <span v-else class="w-16 h-16 rounded-[12px] bg-app-warm grid place-items-center flex-shrink-0"><Icon name="box" :size="26" color="#a8a29e" /></span>
          <div class="flex-1 min-w-0">
            <div class="text-[16px] font-bold leading-snug">{{ d.item_name }}</div>
            <div class="text-[11.5px] text-ink-muted mt-0.5"><span v-if="d.sku" class="font-mono">{{ d.sku }}</span><span v-if="d.item_group"> · {{ d.item_group }}</span><span v-if="d.uom"> · {{ d.uom }}</span></div>
          </div>
          <div class="text-end">
            <div v-if="d.avg_sold" class="text-[24px] font-extrabold tnum" :class="d.margin >= 0 ? 'text-success-dark' : 'text-sale'">{{ d.margin_pct }}%</div>
            <div class="text-[10.5px] text-ink-muted">{{ L("gross margin","الهامش الإجمالي","marge brute") }}</div>
          </div>
        </div>
        <!-- margin breakdown -->
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-4">
          <div class="rounded-[10px] px-3 py-2" style="background:#fafaf9;border:1px solid #f0efed">
            <div class="text-[9.5px] text-ink-muted font-bold uppercase tracking-wide">{{ L("Cost","التكلفة","Coût") }}</div>
            <div class="text-[15px] font-bold tnum">{{ fmt(d.cost) }}</div>
            <div v-if="d.valuation_broken" class="text-[9px] text-amber-600">{{ L("last purchase","آخر شراء","dernier achat") }}</div>
          </div>
          <div class="rounded-[10px] px-3 py-2" style="background:#fafaf9;border:1px solid #f0efed">
            <div class="text-[9.5px] text-ink-muted font-bold uppercase tracking-wide">{{ L("Avg sold","متوسط البيع","Vente moy.") }}</div>
            <div class="text-[15px] font-bold tnum">{{ d.avg_sold ? fmt(d.avg_sold) : "—" }}</div>
          </div>
          <div class="rounded-[10px] px-3 py-2" style="background:#f0fdf4;border:1px solid #bbf7d0">
            <div class="text-[9.5px] text-ink-muted font-bold uppercase tracking-wide">{{ L("Margin / unit","الهامش/وحدة","Marge/u") }}</div>
            <div class="text-[15px] font-bold tnum text-success-dark">{{ d.avg_sold ? fmt(d.margin) : "—" }}</div>
          </div>
          <div class="rounded-[10px] px-3 py-2" style="background:#fafaf9;border:1px solid #f0efed">
            <div class="text-[9.5px] text-ink-muted font-bold uppercase tracking-wide">{{ L("Units sold","الكمية المباعة","Vendus") }}</div>
            <div class="text-[15px] font-bold tnum">{{ Math.round(d.qty_sold).toLocaleString() }}<span class="text-[10px] text-ink-muted ms-1">· {{ d.orders }} {{ L("ord","طلب","cmd") }}</span></div>
          </div>
        </div>
      </div>

      <div class="grid lg:grid-cols-2 gap-3.5">
        <!-- Prices across lists -->
        <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
          <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><Icon name="scale" :size="14" color="#0b5c4f" /><span class="text-[12px] font-bold">{{ L("Prices across lists","الأسعار في القوائم","Prix par liste") }}</span></div>
          <table class="w-full text-[12px]">
            <tbody>
              <tr v-for="(p, i) in d.prices" :key="i" class="border-t border-line-hair">
                <td class="px-4 py-2"><span class="font-medium">{{ p.price_list }}</span> <span class="text-[9px] font-bold px-1.5 py-0.5 rounded-badge" :style="p.selling ? 'background:#ecfdf5;color:#047857' : 'background:#eff6ff;color:#0369a1'">{{ p.selling ? L("sell","بيع","vente") : L("buy","شراء","achat") }}</span></td>
                <td class="px-4 py-2 text-end tnum font-semibold">{{ fmt(p.rate) }} <span class="text-[10px] text-ink-muted">{{ p.currency }}</span></td>
              </tr>
              <tr v-if="!d.prices.length"><td class="px-4 py-4 text-center text-ink-muted">{{ L("No price-list entries.","لا أسعار.","Aucun prix.") }}</td></tr>
            </tbody>
          </table>
        </div>

        <!-- Stock + recent purchases -->
        <div class="space-y-3.5">
          <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
            <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><Icon name="box" :size="14" color="#b45309" /><span class="text-[12px] font-bold">{{ L("Stock on hand","المخزون","Stock") }}</span></div>
            <table class="w-full text-[12px]">
              <tbody>
                <tr v-for="(s, i) in d.stock" :key="i" class="border-t border-line-hair">
                  <td class="px-4 py-2 truncate max-w-[200px]">{{ s.warehouse }}</td>
                  <td class="px-4 py-2 text-end tnum font-semibold" :class="s.qty < 0 ? 'text-sale' : ''">{{ Math.round(s.qty).toLocaleString() }}</td>
                </tr>
                <tr v-if="!d.stock.length"><td class="px-4 py-4 text-center text-ink-muted">{{ L("No stock movement.","لا حركة مخزون.","Aucun stock.") }}</td></tr>
              </tbody>
            </table>
          </div>
          <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
            <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><Icon name="cart" :size="14" color="#b45309" /><span class="text-[12px] font-bold">{{ L("Recent purchases","مشتريات حديثة","Achats récents") }}</span></div>
            <table class="w-full text-[12px]">
              <tbody>
                <tr v-for="(p, i) in d.purchases" :key="i" class="border-t border-line-hair hover:bg-app-warm/50 cursor-pointer group" @click="openPO(p.doc)">
                  <td class="px-4 py-2 font-mono text-[10.5px] group-hover:text-accent-dark">{{ p.doc }}</td>
                  <td class="px-4 py-2 text-ink-3 truncate max-w-[120px]">{{ p.supplier }}</td>
                  <td class="px-4 py-2 text-end tnum">{{ p.qty }} × {{ fmt(p.rate) }}<Icon name="arrow" :size="11" color="#cbd5e1" class="inline ms-1 opacity-0 group-hover:opacity-100" /></td>
                </tr>
                <tr v-if="!d.purchases.length"><td colspan="3" class="px-4 py-4 text-center text-ink-muted">{{ L("No purchase orders.","لا مشتريات.","Aucun achat.") }}</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <DocHub v-if="route.query.id" doctype="Item" :name="route.query.id" class="mt-1" />
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
function back() { router.push("/accounting/items/items"); }
function openPO(doc) { if (doc) router.push({ path: "/accounting/purchases/tobuy", query: { id: doc } }); }
async function load() {
  const id = route.query.id;
  if (!id) { loading.value = false; return; }
  loading.value = true; d.value = null;
  try { d.value = await api.call("accounting_portal.api.items.get_item", { item_code: id }); }
  catch { d.value = null; }
  finally { loading.value = false; }
  if (!d.value) router.replace({ path: "/accounting/items/items", query: {} });
}
watch(() => route.query.id, load, { immediate: true });
</script>
