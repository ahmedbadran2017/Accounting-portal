<template>
  <div class="space-y-3.5">
    <div class="bg-white rounded-card border border-line overflow-hidden shadow-card">
      <!-- Header -->
      <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
        <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#fff4e0"><Icon name="building" :size="14" color="#b45309" /></span>
        <span class="text-[13px] font-bold">{{ L("Suppliers","الموردون","Fournisseurs") }}</span>
        <span v-if="isLive !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="isLive ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ isLive ? "Live" : "Sample" }}</span>
        <span class="hidden lg:inline text-[11px] text-ink-muted">{{ rows.length }} · {{ L("ranked by payable","حسب المستحق","par dû") }}</span>
        <!-- view toggle -->
        <div class="ms-auto flex items-center gap-1 bg-app-warm/60 rounded-chip p-0.5">
          <button v-for="v in ['list','cards']" :key="v" class="px-2.5 py-1 rounded-lg text-[11px] font-semibold inline-flex items-center gap-1" :class="view === v ? 'bg-white shadow-card text-ink' : 'text-ink-3'" @click="view = v">
            <Icon :name="v === 'list' ? 'list' : 'grid'" :size="12" />{{ v === 'list' ? L("List","قائمة","Liste") : L("Cards","بطاقات","Cartes") }}
          </button>
        </div>
        <div class="relative">
          <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
          <input v-model.trim="tt.search.value" :placeholder="L('Search supplier…','بحث…','Rechercher…')" class="w-44 sm:w-60 h-9 bg-app-warm/40 border border-line-2 rounded-[10px] ps-9 pe-3 text-[12.5px] focus:outline-none focus:border-accent/40 focus:bg-white" />
        </div>
        <button @click="importOpen = true" class="inline-flex items-center gap-1.5 h-9 px-3 rounded-chip text-[12px] font-semibold text-ink-2 bg-white border border-line-2 hover:bg-app-warm"><Icon name="layers" :size="14" />{{ L("Import","استيراد","Importer") }}</button>
        <button @click="openNew" class="inline-flex items-center gap-1.5 h-9 px-3 rounded-chip text-[12px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand"><Icon name="plus" :size="14" color="#fff" />{{ L("New","جديد","Nouveau") }}</button>
      </div>

      <TableToolbar :t="tt" filename="suppliers" />

      <!-- List view -->
      <div v-if="view === 'list'" class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead>
            <tr style="background:#fafaf9">
              <th class="px-3 py-2.5 w-9"><input type="checkbox" :checked="tt.allFilteredSelected.value" @change="tt.toggleAllFiltered()" class="accent-accent w-3.5 h-3.5 align-middle" /></th>
              <th v-for="c in cols" v-show="!tt.hidden.value.has(c.key)" :key="c.key"
                  class="px-4 py-2.5 text-[10px] font-bold uppercase tracking-wider text-ink-muted whitespace-nowrap cursor-pointer select-none hover:text-ink-2"
                  :class="c.align === 'e' ? 'text-end' : 'text-start'" @click="tt.toggleSort(c.key)">
                <span class="inline-flex items-center gap-1" :class="c.align === 'e' ? 'flex-row-reverse' : ''">{{ c.label }}
                  <Icon v-if="tt.sortKey.value === c.key" name="chevDown" :size="11" :class="tt.sortDir.value === 1 ? '' : 'rotate-180'" color="#0b5c4f" /></span>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(v, i) in tt.pageRows.value" :key="v.name" class="border-t border-line-hair hover:bg-app-warm/70 cursor-pointer" :class="tt.isSelected(v) ? 'bg-accent/5' : ''" @click="open(v.name)">
              <td class="px-3 py-2.5 w-9" @click.stop><input type="checkbox" :checked="tt.isSelected(v)" @change="tt.toggleRow(v)" class="accent-accent w-3.5 h-3.5 align-middle" /></td>
              <td v-show="!tt.hidden.value.has('supplier_name')" class="px-4 py-2.5">
                <span class="flex items-center gap-2.5">
                  <span class="w-7 h-7 rounded-[8px] grid place-items-center text-white text-[9px] font-bold flex-shrink-0" :style="{ background: badge(i) }">{{ ini(v.supplier_name) }}</span>
                  <span class="font-semibold truncate max-w-[260px]">{{ v.supplier_name }}</span>
                </span>
              </td>
              <td v-show="!tt.hidden.value.has('group')" class="px-4 py-2.5 text-ink-2">{{ v.group || "—" }}</td>
              <td v-show="!tt.hidden.value.has('n_bills')" class="px-4 py-2.5 text-end tnum">{{ v.n_bills }}</td>
              <td v-show="!tt.hidden.value.has('payable')" class="px-4 py-2.5 text-end tnum font-bold" :class="v.payable < 0 ? 'text-success-dark' : ''">{{ fmt(v.payable) }} <span class="text-[10px] text-ink-muted">{{ v.currency }}</span></td>
            </tr>
          </tbody>
        </table>
        <TableLoading v-if="loading" />
        <div v-else-if="!tt.sorted.value.length" class="py-12 text-center text-[12px] text-ink-muted">{{ L("No suppliers match.","لا موردين مطابقين.","Aucun fournisseur.") }}</div>
        <TablePager :t="tt" />
      </div>

      <!-- Cards view -->
      <div v-else class="p-3 grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        <button v-for="(v, i) in tt.pageRows.value" :key="v.name" class="yo-card text-start bg-white border border-line rounded-[14px] p-4 shadow-card w-full" @click="open(v.name)">
          <div class="flex items-center gap-2.5">
            <span class="w-[30px] h-[30px] rounded-[8px] grid place-items-center text-white text-[9.5px] font-bold flex-shrink-0" :style="{ background: badge(i) }">{{ ini(v.supplier_name) }}</span>
            <div class="flex-1 min-w-0"><div class="text-[12.5px] font-bold truncate">{{ v.supplier_name }}</div><div class="text-[10.5px] text-ink-muted">{{ v.group || "—" }}</div></div>
          </div>
          <div class="text-[20px] font-bold tnum mt-2.5" :class="v.payable < 0 ? 'text-success-dark' : ''">{{ fmt(v.payable) }}<span class="text-[11px] text-ink-muted ms-0.5">{{ v.currency }}</span></div>
          <div class="text-[10.5px] text-ink-muted mt-0.5">{{ v.n_bills }} {{ L("bills · payable","فاتورة · مستحق","factures") }}</div>
        </button>
      </div>
    </div>

    <BulkBar :t="tt" filename="vendors-selected" :actions="[]" />

    <!-- New supplier modal -->
    <div v-if="newOpen" class="fixed inset-0 z-50 grid place-items-center bg-black/30 p-4" @click.self="newOpen = false">
      <div class="bg-white rounded-card shadow-xl w-full max-w-sm p-5 space-y-3">
        <div class="text-[14px] font-bold">{{ L("New supplier","مورّد جديد","Nouveau fournisseur") }}</div>
        <div><label class="text-[11px] font-bold text-ink-3">{{ L("Name","الاسم","Nom") }} *</label><input v-model.trim="nf.supplier_name" class="w-full h-9 mt-1 border border-line-2 rounded-[9px] px-2 text-[12.5px] focus:outline-none focus:border-accent/40" /></div>
        <div><label class="text-[11px] font-bold text-ink-3">{{ L("Group","المجموعة","Groupe") }}</label>
          <select v-model="nf.supplier_group" class="w-full h-9 mt-1 border border-line-2 rounded-[9px] px-2 text-[12.5px] bg-white focus:outline-none focus:border-accent/40"><option value="">{{ L("Default","افتراضي","Défaut") }}</option><option v-for="g in groups" :key="g" :value="g">{{ g }}</option></select></div>
        <div class="grid grid-cols-2 gap-2">
          <div><label class="text-[11px] font-bold text-ink-3">{{ L("Tax ID","الرقم الضريبي","ID fiscal") }}</label><input v-model.trim="nf.tax_id" class="w-full h-9 mt-1 border border-line-2 rounded-[9px] px-2 text-[12.5px] focus:outline-none focus:border-accent/40" /></div>
          <div><label class="text-[11px] font-bold text-ink-3">{{ L("Currency","العملة","Devise") }}</label><input v-model.trim="nf.currency" class="w-full h-9 mt-1 border border-line-2 rounded-[9px] px-2 text-[12.5px] focus:outline-none focus:border-accent/40" placeholder="MAD" /></div>
        </div>
        <div class="flex gap-2 justify-end pt-1">
          <button @click="newOpen = false" class="h-9 px-3 rounded-[9px] text-[12px] font-semibold text-ink-3 hover:bg-app-warm">{{ L("Cancel","إلغاء","Annuler") }}</button>
          <button @click="createNew" :disabled="creating || !nf.supplier_name" class="h-9 px-4 rounded-[9px] text-[12px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand disabled:opacity-50">{{ creating ? L("Creating…","جارٍ…","…") : L("Create","إنشاء","Créer") }}</button>
        </div>
      </div>
    </div>

    <!-- Bulk import modal -->
    <div v-if="importOpen" class="fixed inset-0 z-50 grid place-items-center bg-black/30 p-4" @click.self="importOpen = false">
      <div class="bg-white rounded-card shadow-xl w-full max-w-md p-5 space-y-3">
        <div class="text-[14px] font-bold">{{ L("Import suppliers","استيراد موردين","Importer des fournisseurs") }}</div>
        <p class="text-[11px] text-ink-muted">{{ L("One per line: name, group, tax id, currency (only name required).","سطر لكل مورّد: الاسم، المجموعة، الرقم الضريبي، العملة (الاسم فقط مطلوب).","Une ligne par fournisseur : nom, groupe, ID fiscal, devise.") }}</p>
        <textarea v-model="importText" rows="6" :placeholder="L('ACME SARL, Morocco Local Suppliers, 123456, MAD\nOther Vendor', 'مورّد، مجموعة، رقم ضريبي', 'Fournisseur, groupe, ID')" class="w-full border border-line-2 rounded-[10px] px-3 py-2 text-[12px] font-mono focus:outline-none focus:border-accent/40 resize-y"></textarea>
        <div v-if="importResult" class="text-[11.5px] bg-app-warm/50 rounded-[9px] px-3 py-2">
          <b class="text-success-dark">{{ importResult.created }}</b> {{ L("created","أُنشئ","créés") }} · {{ importResult.exists }} {{ L("existed","موجود","existants") }}<span v-if="importResult.failed"> · <b class="text-sale">{{ importResult.failed }}</b> {{ L("failed","فشل","échecs") }}</span>
        </div>
        <div class="flex items-center justify-between pt-1">
          <span class="text-[11px] text-ink-muted">{{ parsedCount }} {{ L("rows","سطر","lignes") }}</span>
          <div class="flex gap-2">
            <button @click="importOpen = false" class="h-9 px-3 rounded-[9px] text-[12px] font-semibold text-ink-3 hover:bg-app-warm">{{ L("Close","إغلاق","Fermer") }}</button>
            <button @click="runImport" :disabled="importing || !parsedCount" class="h-9 px-4 rounded-[9px] text-[12px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand disabled:opacity-50">{{ importing ? L("Importing…","جارٍ…","…") : L("Import","استيراد","Importer") }}</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableToolbar from "@/components/TableToolbar.vue";
import TablePager from "@/components/TablePager.vue";
import TableLoading from "@/components/TableLoading.vue";
import { VENDORS } from "@/data/purchases";
import { liveOrSample, currentCompany } from "@/composables/useLive";
import { useTableTools } from "@/composables/useTableTools";
import BulkBar from "@/components/BulkBar.vue";
import api from "@/services/api";
import { useToast } from "@/composables/useToast";

const { locale } = useI18n();
const router = useRouter();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US");
const ini = (n) => String(n || "?").trim().split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
const PALETTE = ["#2563eb", "#7c3aed", "#0891b2", "#c2410c", "#16a34a", "#be123c", "#a16207", "#4f46e5"];
const badge = (i) => `linear-gradient(135deg,${PALETTE[i % PALETTE.length]},${PALETTE[(i + 3) % PALETTE.length]})`;

const view = ref("list");
const cols = [
  { key: "supplier_name", label: L("Supplier", "المورّد", "Fournisseur"), align: "s" },
  { key: "group", label: L("Group", "المجموعة", "Groupe"), align: "s" },
  { key: "n_bills", label: L("Bills", "الفواتير", "Factures"), align: "e" },
  { key: "payable", label: L("Payable", "المستحق", "Dû"), align: "e" },
];

const SAMPLE = VENDORS.map((v) => ({ name: v.id, supplier_name: v.name, group: v.place, payable: Number(String(v.payable).replace(/,/g, "")) || 0, currency: v.ccy, n_bills: 0 }));
const rows = ref([]);
const isLive = ref(null);
const loading = ref(true);
const tt = useTableTools(rows, cols, { keyField: "name", defaultSort: "payable", defaultDir: -1, facets: [{ key: "group", label: L("group", "مجموعة", "groupe") }] });

async function load() {
  loading.value = true;
  try {
    const res = await liveOrSample(
      "accounting_portal.api.purchases.list_vendors", { company: currentCompany(), limit: 200 }, () => SAMPLE,
      (data) => data.map((r) => ({ name: r.name, supplier_name: r.supplier_name || r.name, group: r.supplier_group, payable: Number(r.payable) || 0, currency: r.currency || "MAD", n_bills: r.n_bills || 0 })),
    );
    rows.value = res.data; isLive.value = res.live;
  } finally { loading.value = false; tt.clearSelection(); }
}
onMounted(load);

function open(name) { router.push({ path: "/accounting/purchases/vendors", query: { id: name } }); }

// ── New supplier ──
const newOpen = ref(false);
const creating = ref(false);
const groups = ref([]);
const nf = ref({ supplier_name: "", supplier_group: "", tax_id: "", currency: "" });
async function openNew() {
  nf.value = { supplier_name: "", supplier_group: "", tax_id: "", currency: "" };
  newOpen.value = true;
  if (!groups.value.length) { try { groups.value = await api.call("accounting_portal.api.purchases.supplier_groups", {}); } catch { groups.value = []; } }
}
// ── Bulk import ──
const importOpen = ref(false);
const importText = ref("");
const importing = ref(false);
const importResult = ref(null);
const parsedRows = computed(() => importText.value.split(/\n+/).map((line) => {
  const p = line.split(",").map((x) => x.trim());
  return p[0] ? { supplier_name: p[0], group: p[1] || "", tax_id: p[2] || "", currency: p[3] || "" } : null;
}).filter(Boolean));
const parsedCount = computed(() => parsedRows.value.length);
async function runImport() {
  importing.value = true; importResult.value = null;
  try {
    importResult.value = await api.call("accounting_portal.api.purchases.bulk_create_suppliers", { rows: parsedRows.value });
    toast.success(L(`${importResult.value.created} created`, `${importResult.value.created} أُنشئ`, `${importResult.value.created} créés`));
    load();
  } catch (e) { toast.error(String((e && e.message) || L("Failed", "فشل", "Échec")).slice(0, 140)); }
  finally { importing.value = false; }
}

async function createNew() {
  creating.value = true;
  try {
    const r = await api.call("accounting_portal.api.purchases.create_supplier", { supplier_name: nf.value.supplier_name, supplier_group: nf.value.supplier_group || undefined, tax_id: nf.value.tax_id || undefined, currency: nf.value.currency || undefined });
    newOpen.value = false; toast.success(L("Supplier created", "أُنشئ المورّد", "Fournisseur créé"));
    router.push({ path: "/accounting/purchases/vendors", query: { id: r.name } });
  } catch (e) { toast.error(String((e && e.message) || L("Failed", "فشل", "Échec")).slice(0, 140)); }
  finally { creating.value = false; }
}
</script>
