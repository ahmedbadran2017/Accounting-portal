<template>
  <div class="bg-white border border-line rounded-card shadow-card overflow-hidden">
    <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
      <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#fff4e0"><Icon name="truck" :size="14" color="#b45309" /></span>
      <span class="text-[13px] font-bold">{{ L("COD remittance batches","دفعات تحصيل COD","Lots d’encaissement COD") }}</span>
      <span v-if="isLive !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="isLive ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ isLive ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échant.") }}</span>
      <span class="hidden lg:inline text-[11px] text-ink-muted">{{ L("carrier collected vs deposited","المُحصَّل مقابل المُودَع","collecté vs déposé") }}</span>
      <div class="ms-auto relative">
        <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
        <input v-model.trim="search" @input="onSearch" :placeholder="L('Search ref / carrier…','بحث…','Rechercher…')" class="w-44 sm:w-56 h-9 bg-app-warm/40 border border-line-2 rounded-[10px] ps-9 pe-3 text-[12.5px] focus:outline-none focus:border-accent/40 focus:bg-white" />
      </div>
    </div>
    <TableLoading v-if="loading" :rows="8" />
    <div v-else class="overflow-x-auto">
      <table class="w-full text-[12px]">
        <thead><tr style="background:#fafaf9">
          <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Batch","الدفعة","Lot") }}</th>
          <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Carrier","الناقل","Transp.") }}</th>
          <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Orders","الطلبات","Cmd") }}</th>
          <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Expected","المتوقَّع","Attendu") }}</th>
          <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Collected","المُحصَّل","Collecté") }}</th>
          <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Variance","الفرق","Écart") }}</th>
          <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Status","الحالة","Statut") }}</th>
        </tr></thead>
        <tbody>
          <tr v-for="b in rows" :key="b.ref" class="border-t border-line-hair hover:bg-app-warm/60 cursor-pointer" @click="open(b.ref)">
            <td class="px-4 py-2.5 font-mono text-[11px] font-semibold whitespace-nowrap">{{ b.ref }}<div class="text-[10px] text-ink-muted font-sans">{{ b.date }}</div></td>
            <td class="px-4 py-2.5">{{ b.carrier }}</td>
            <td class="px-4 py-2.5 text-end tnum text-ink-3">{{ b.orders }}</td>
            <td class="px-4 py-2.5 text-end tnum">{{ money(b.expected) }}</td>
            <td class="px-4 py-2.5 text-end tnum font-semibold">{{ money(b.collected) }}</td>
            <td class="px-4 py-2.5 text-end tnum font-bold" :class="b.variance < 0 ? 'text-sale' : b.variance > 0 ? 'text-amber-700' : 'text-ink-3'">{{ b.variance > 0 ? "+" : "" }}{{ money(b.variance) }}</td>
            <td class="px-4 py-2.5"><span class="inline-flex text-[10.5px] font-bold px-2 py-0.5 rounded-badge" :style="stBadge(b.status)">{{ stLabel(b.status) }}</span></td>
          </tr>
          <tr v-if="!rows.length"><td colspan="7" class="px-4 py-12 text-center text-ink-muted text-[12px]">{{ L("No remittance batches.","لا دفعات.","Aucun lot.") }}</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { usePersistedRef } from "@/composables/usePersistedRef";
import { useUi } from "@/composables/useUi";

const { locale } = useI18n();
const { entityId } = useUi();
const router = useRouter();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const money = (n) => { n = Number(n) || 0; const a = Math.abs(n); return (n < 0 ? "−" : "") + (a >= 1e6 ? (a / 1e6).toFixed(2) + "M" : a >= 1e3 ? Math.round(a / 1e3) + "K" : Math.round(a).toLocaleString()); };

const rows = ref([]);
const isLive = ref(null);
const loading = ref(true);
const search = usePersistedRef("ap_remit_search", "");
let t = null;
const SAMPLE = [{ ref: "CATH0102…0526", carrier: "Cathedis", date: "2026-05-02", orders: 716, expected: 150990, collected: 154153, variance: 3163, status: "over" }];
async function load() {
  loading.value = true;
  try { rows.value = await api.call("accounting_portal.api.cod.cod_remittances", { company: currentCompany(), search: search.value || undefined, limit: 2000 }); isLive.value = true; }
  catch { rows.value = SAMPLE; isLive.value = false; }
  finally { loading.value = false; }
}
function onSearch() { clearTimeout(t); t = setTimeout(load, 350); }
onMounted(load);
watch(entityId, load);
function open(ref) { router.push({ path: "/accounting/banking/remittance", query: { id: ref } }); }

const ST = {
  matched: { en: "Matched", ar: "مطابقة", fr: "Rapproché", bg: "#ecfdf5", fg: "#047857" },
  short: { en: "Short", ar: "نقص", fr: "Manque", bg: "#fef2f2", fg: "#b91c1c" },
  over: { en: "Over", ar: "زيادة", fr: "Excédent", bg: "#fffbeb", fg: "#b45309" },
};
function stLabel(s) { const x = ST[s] || ST.matched; return locale.value === "ar" ? x.ar : locale.value === "fr" ? x.fr : x.en; }
function stBadge(s) { const x = ST[s] || ST.matched; return `background:${x.bg};color:${x.fg}`; }
</script>
