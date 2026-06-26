<template>
  <div class="space-y-3.5">
    <!-- Auditor flag -->
    <div class="flex items-center gap-2.5 px-[15px] py-[13px] rounded-[13px]" style="background:#fff7ed;border:1px solid #fed7aa">
      <span class="w-[30px] h-[30px] rounded-[8px] grid place-items-center flex-shrink-0" style="background:#ffedd5"><Icon name="alert" :size="16" color="#ea580c" /></span>
      <div class="flex-1">
        <div class="text-[12.5px] font-bold" style="color:#9a3412">{{ L("True margin needs RTO allocated to SKU","الهامش الحقيقي يحتاج توزيع الإرجاع على الصنف","Marge réelle : retours à imputer au SKU") }}</div>
        <div class="text-[11.5px] mt-px" style="color:#c2410c">{{ L("Margin = avg sold − cost. Stock valuation is broken (cost falls back to last purchase); return shipping isn’t yet costed back to the item.","الهامش = متوسط البيع − التكلفة. تقييم المخزون معطّل (التكلفة من آخر شراء)؛ شحن الإرجاع غير محمَّل بعد.","Marge = vente moy. − coût. Valorisation cassée; retour non imputé.") }}</div>
      </div>
      <span class="inline-flex items-center gap-1 text-[10px] font-bold px-2.5 py-[3px] rounded-full flex-shrink-0" style="background:#f5f3ff;color:#7c3aed;border:1px solid #ddd6fe"><Icon name="shield" :size="11" />{{ L("Auditor","المدقّق","Auditeur") }}</span>
    </div>

    <div class="bg-white rounded-card border border-line overflow-hidden shadow-card">
      <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
        <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#faf6f4"><Icon name="box" :size="14" color="#0b5c4f" /></span>
        <span class="text-[13px] font-bold">{{ L("Items & true margin","الأصناف والهامش الحقيقي","Articles & marge") }}</span>
        <span v-if="isLive !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="isLive ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ isLive ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échant.") }}</span>
        <div class="ms-auto flex items-center gap-2">
          <select v-model="group" @change="load" class="h-9 border border-line-2 rounded-[10px] px-2 text-[12px] bg-white max-w-[150px] focus:outline-none focus:border-accent/40">
            <option value="">{{ L("All groups","كل المجموعات","Tous") }}</option>
            <option v-for="g in groups" :key="g" :value="g">{{ g }}</option>
          </select>
          <div class="relative">
            <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
            <input v-model.trim="search" @input="onSearch" :placeholder="L('Search SKU / item…','بحث…','Rechercher…')" class="w-40 sm:w-56 h-9 bg-app-warm/40 border border-line-2 rounded-[10px] ps-9 pe-3 text-[12.5px] focus:outline-none focus:border-accent/40 focus:bg-white" />
          </div>
        </div>
      </div>

      <TableLoading v-if="loading" :rows="8" />
      <div v-else class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead><tr style="background:#fafaf9">
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Item","الصنف","Article") }}</th>
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Group","المجموعة","Groupe") }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Cost","التكلفة","Coût") }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Avg sold","متوسط البيع","Vente moy.") }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Margin","الهامش","Marge") }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Stock","المخزون","Stock") }}</th>
          </tr></thead>
          <tbody>
            <tr v-for="r in rows" :key="r.item_code" class="border-t border-line-hair hover:bg-app-warm/50 cursor-pointer" @click="open(r.item_code)">
              <td class="px-4 py-2.5">
                <span class="flex items-center gap-2.5">
                  <img v-if="r.image" :src="r.image" class="w-9 h-9 rounded-[8px] object-cover flex-shrink-0 border border-line-hair" />
                  <span v-else class="w-9 h-9 rounded-[8px] bg-app-warm grid place-items-center flex-shrink-0"><Icon name="box" :size="14" color="#a8a29e" /></span>
                  <span class="min-w-0"><span class="block font-semibold truncate max-w-[280px]">{{ r.item_name }}</span><span v-if="r.sku" class="block text-[10px] text-ink-muted font-mono">{{ r.sku }}</span></span>
                </span>
              </td>
              <td class="px-4 py-2.5 text-ink-3 truncate max-w-[140px]">{{ r.item_group }}</td>
              <td class="px-4 py-2.5 text-end tnum">{{ r.cost ? fmt(r.cost) : "—" }}</td>
              <td class="px-4 py-2.5 text-end tnum">{{ r.avg_sold ? fmt(r.avg_sold) : "—" }}</td>
              <td class="px-4 py-2.5 text-end">
                <span v-if="r.avg_sold" class="inline-flex items-center gap-1.5 tnum font-bold" :class="r.margin >= 0 ? 'text-success-dark' : 'text-sale'">
                  {{ r.margin >= 0 ? "+" : "" }}{{ fmt(r.margin) }}<span class="text-[10px] font-semibold px-1.5 py-0.5 rounded-badge" :style="marginBadge(r.margin_pct)">{{ r.margin_pct }}%</span>
                </span>
                <span v-else class="text-ink-muted">—</span>
              </td>
              <td class="px-4 py-2.5 text-end tnum" :class="r.stock_qty < 0 ? 'text-sale font-semibold' : 'text-ink-3'">{{ r.stock_qty }}</td>
            </tr>
            <tr v-if="!rows.length"><td colspan="6" class="px-4 py-12 text-center text-ink-muted text-[12px]">{{ L("No items match.","لا أصناف.","Aucun article.") }}</td></tr>
          </tbody>
        </table>
      </div>
      <div class="px-4 py-2.5 border-t border-line-hair text-[11px] text-ink-muted">{{ rows.length }} {{ L("items shown","صنف معروض","articles") }}</div>
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
import { useUi } from "@/composables/useUi";

const { locale } = useI18n();
const { entityId } = useUi();
const router = useRouter();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const rows = ref([]);
const groups = ref([]);
const isLive = ref(null);
const loading = ref(true);
const search = ref("");
const group = ref("");
let t = null;

const SAMPLE = [
  { item_code: "JY-JKT-0301", item_name: "Veste en Jean", sku: "JY-JKT-0301", item_group: "Vestes", cost: 104.65, avg_sold: 299, margin: 194.35, margin_pct: 65, stock_qty: 120 },
];
async function load() {
  loading.value = true;
  try {
    rows.value = await api.call("accounting_portal.api.items.list_items", { company: currentCompany(), search: search.value || undefined, group: group.value || undefined, limit: 80 });
    isLive.value = true;
  } catch { rows.value = SAMPLE; isLive.value = false; }
  finally { loading.value = false; }
}
async function loadGroups() {
  try { groups.value = await api.call("accounting_portal.api.items.item_groups", {}); } catch { groups.value = []; }
}
function onSearch() { clearTimeout(t); t = setTimeout(load, 350); }
onMounted(() => { load(); loadGroups(); });
watch(entityId, load);

function open(code) { router.push({ path: "/accounting/items/items", query: { id: code } }); }
function marginBadge(p) {
  if (p >= 40) return "background:#ecfdf5;color:#047857";
  if (p >= 20) return "background:#fffbeb;color:#b45309";
  if (p > 0) return "background:#fff7ed;color:#c2410c";
  return "background:#fef2f2;color:#b91c1c";
}
</script>
