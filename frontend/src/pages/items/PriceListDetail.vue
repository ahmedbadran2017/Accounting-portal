<template>
  <div class="space-y-3.5">
    <button class="inline-flex items-center gap-1.5 text-[12px] font-semibold text-ink-3 hover:text-ink" @click="back">
      <Icon name="arrow" :size="14" class="rtl:rotate-180 rotate-180" />{{ L("Back to price lists","العودة للقوائم","Retour aux listes") }}
    </button>
    <div v-if="loading" class="bg-white rounded-card border border-line shadow-card"><TableLoading :rows="4" /></div>
    <template v-else-if="d">
      <div class="bg-white rounded-card border border-line shadow-card p-5 flex items-center gap-3 flex-wrap">
        <span class="w-11 h-11 rounded-[12px] grid place-items-center flex-shrink-0" style="background:#faf6f4"><Icon name="scale" :size="20" color="#0b5c4f" /></span>
        <div class="flex-1 min-w-0">
          <div class="text-[16px] font-bold">{{ d.name }}</div>
          <div class="text-[11.5px] text-ink-muted">
            <span v-if="d.selling" class="text-[9.5px] font-bold px-1.5 py-0.5 rounded-badge me-1" style="background:#ecfdf5;color:#047857">{{ L("Selling","بيع","Vente") }}</span>
            <span v-if="d.buying" class="text-[9.5px] font-bold px-1.5 py-0.5 rounded-badge" style="background:#eff6ff;color:#0369a1">{{ L("Buying","شراء","Achat") }}</span>
            <span class="ms-1">{{ d.currency }}</span>
          </div>
        </div>
        <div class="text-end"><div class="text-[22px] font-extrabold tnum">{{ (d.total || 0).toLocaleString() }}</div><div class="text-[10.5px] text-ink-muted">{{ L("items priced","صنف مُسعّر","articles") }}</div></div>
      </div>

      <div class="bg-white rounded-card border border-line overflow-hidden shadow-card">
        <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair">
          <span class="text-[12px] font-bold">{{ L("Prices","الأسعار","Prix") }}</span>
          <div class="ms-auto relative">
            <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
            <input v-model.trim="search" @input="onSearch" :placeholder="L('Search SKU / item…','بحث…','Rechercher…')" class="w-44 sm:w-60 h-9 bg-app-warm/40 border border-line-2 rounded-[10px] ps-9 pe-3 text-[12.5px] focus:outline-none focus:border-accent/40 focus:bg-white" />
          </div>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-[12px]">
            <thead><tr style="background:#fafaf9">
              <th class="px-4 py-2 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Item","الصنف","Article") }}</th>
              <th class="px-4 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Rate","السعر","Prix") }}</th>
            </tr></thead>
            <tbody>
              <tr v-for="(r, i) in d.rows" :key="i" class="border-t border-line-hair hover:bg-app-warm/50 cursor-pointer" @click="goItem(r.item_code)">
                <td class="px-4 py-2.5">
                  <span class="flex items-center gap-2.5">
                    <img v-if="r.image" :src="r.image" class="w-8 h-8 rounded-[7px] object-cover flex-shrink-0 border border-line-hair" />
                    <span v-else class="w-8 h-8 rounded-[7px] bg-app-warm grid place-items-center flex-shrink-0"><Icon name="box" :size="13" color="#a8a29e" /></span>
                    <span class="min-w-0"><span class="block font-medium truncate max-w-[300px]">{{ r.item_name || r.item_code }}</span><span v-if="r.sku" class="block text-[10px] text-ink-muted font-mono">{{ r.sku }}</span></span>
                  </span>
                </td>
                <td class="px-4 py-2.5 text-end tnum font-semibold">{{ fmt(r.rate) }} <span class="text-[10px] text-ink-muted">{{ d.currency }}</span></td>
              </tr>
              <tr v-if="!d.rows.length"><td colspan="2" class="px-4 py-10 text-center text-ink-muted">{{ L("No items.","لا أصناف.","Aucun.") }}</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { usePersistedRef } from "@/composables/usePersistedRef";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";

const route = useRoute();
const router = useRouter();
const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const d = ref(null);
const loading = ref(true);
const search = usePersistedRef("ap_pricelist_search", "");
let t = null;
function back() { router.push("/accounting/items/pricelists"); }
function goItem(code) { router.push({ path: "/accounting/items/items", query: { id: code } }); }
async function load() {
  const id = route.query.id;
  if (!id) { loading.value = false; return; }
  loading.value = true;
  try { d.value = await api.call("accounting_portal.api.items.get_price_list", { name: id, search: search.value || undefined }); }
  catch { d.value = null; }
  finally { loading.value = false; }
  if (!d.value) router.replace({ path: "/accounting/items/pricelists", query: {} });
}
function onSearch() { clearTimeout(t); t = setTimeout(load, 350); }
watch(() => route.query.id, load, { immediate: true });
</script>
