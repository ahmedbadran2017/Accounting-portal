<template>
  <div class="bg-white rounded-card border border-line overflow-hidden shadow-card">
    <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
      <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#faf6f4"><Icon name="scale" :size="14" color="#0b5c4f" /></span>
      <span class="text-[13px] font-bold">{{ L("Price lists","قوائم الأسعار","Listes de prix") }}</span>
      <span v-if="isLive !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="isLive ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ isLive ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échant.") }}</span>
      <span class="hidden lg:inline text-[11px] text-ink-muted">{{ rows.length }} {{ L("lists","قائمة","listes") }}</span>
    </div>
    <TableLoading v-if="loading" :rows="5" />
    <div v-else class="overflow-x-auto">
      <table class="w-full text-[12px]">
        <thead><tr style="background:#fafaf9">
          <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Price list","القائمة","Liste") }}</th>
          <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Use","الاستخدام","Usage") }}</th>
          <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Currency","العملة","Devise") }}</th>
          <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Items","الأصناف","Articles") }}</th>
          <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Updated","آخر تحديث","MàJ") }}</th>
        </tr></thead>
        <tbody>
          <tr v-for="r in rows" :key="r.name" class="border-t border-line-hair hover:bg-app-warm/50 cursor-pointer" @click="open(r.name)">
            <td class="px-4 py-2.5 font-semibold">{{ r.name }}</td>
            <td class="px-4 py-2.5">
              <span v-if="r.selling" class="text-[9.5px] font-bold px-1.5 py-0.5 rounded-badge me-1" style="background:#ecfdf5;color:#047857">{{ L("Selling","بيع","Vente") }}</span>
              <span v-if="r.buying" class="text-[9.5px] font-bold px-1.5 py-0.5 rounded-badge" style="background:#eff6ff;color:#0369a1">{{ L("Buying","شراء","Achat") }}</span>
            </td>
            <td class="px-4 py-2.5 font-mono">{{ r.currency }}</td>
            <td class="px-4 py-2.5 text-end tnum font-semibold">{{ (r.items || 0).toLocaleString() }}</td>
            <td class="px-4 py-2.5 text-end text-ink-3 whitespace-nowrap">{{ r.updated || "—" }}</td>
          </tr>
          <tr v-if="!rows.length"><td colspan="5" class="px-4 py-12 text-center text-ink-muted text-[12px]">{{ L("No price lists.","لا قوائم.","Aucune liste.") }}</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";

const { locale } = useI18n();
const router = useRouter();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

const rows = ref([]);
const isLive = ref(null);
const loading = ref(true);
const SAMPLE = [{ name: "Morocco", currency: "MAD", selling: 0, buying: 1, items: 27457, updated: "2026-06-21" }];
async function load() {
  loading.value = true;
  try { rows.value = await api.call("accounting_portal.api.items.list_price_lists", {}); isLive.value = true; }
  catch { rows.value = SAMPLE; isLive.value = false; }
  finally { loading.value = false; }
}
onMounted(load);
function open(name) { router.push({ path: "/accounting/items/pricelists", query: { id: name } }); }
</script>
