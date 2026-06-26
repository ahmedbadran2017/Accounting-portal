<template>
  <div class="space-y-3.5">
    <div class="flex items-center gap-2 flex-wrap">
      <span class="text-[13px] font-bold">{{ L("Missing documents","مستندات ناقصة","Documents manquants") }}</span>
      <span v-if="isLive !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="isLive ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ isLive ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échant.") }}</span>
      <span class="text-[11px] text-ink-muted">{{ L("documents with no source file attached — attach to clear the audit gap","مستندات بدون ملف مرفق — ارفع المستند لإغلاق فجوة التدقيق","sans pièce jointe — joignez pour combler le manque") }}</span>
    </div>

    <!-- Kind tabs with counts -->
    <div class="flex items-center gap-1.5 flex-wrap">
      <button v-for="k in KINDS" :key="k.key" @click="setKind(k.key)" class="text-[11.5px] font-semibold px-3 py-1.5 rounded-full border transition inline-flex items-center gap-1.5"
              :class="kind === k.key ? 'bg-ink text-white border-ink' : 'bg-white text-ink-3 border-line-2 hover:bg-app-warm'">
        {{ k.label() }}<span v-if="counts[k.key] != null" class="text-[10px] font-bold px-1.5 py-0.5 rounded-full" :class="kind === k.key ? 'bg-white/20' : 'bg-app-warm text-ink-3'">{{ counts[k.key] }}</span>
      </button>
      <div class="ms-auto relative">
        <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
        <input v-model.trim="search" @input="onSearch" :placeholder="L('Search doc / party…','بحث…','Rechercher…')" class="w-44 sm:w-56 h-9 bg-app-warm/40 border border-line-2 rounded-[10px] ps-9 pe-3 text-[12.5px] focus:outline-none focus:border-accent/40 focus:bg-white" />
      </div>
    </div>

    <div class="bg-white rounded-card border border-line overflow-hidden shadow-card">
      <TableLoading v-if="loading" :rows="8" />
      <div v-else-if="!rows.length" class="py-14 text-center"><Icon name="check" :size="22" color="#047857" /><div class="text-[12.5px] text-success-dark font-semibold mt-1">{{ L("All caught up — every document here has its source file.","تمام — كل المستندات هنا مرفوعة.","Tout est à jour.") }}</div></div>
      <div v-else class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead><tr style="background:#fafaf9">
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Document","المستند","Document") }}</th>
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Party","الطرف","Tiers") }}</th>
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Date","التاريخ","Date") }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Amount","المبلغ","Montant") }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted"></th>
          </tr></thead>
          <tbody>
            <tr v-for="r in rows" :key="r.name" class="border-t border-line-hair hover:bg-app-warm/40">
              <td class="px-4 py-2.5 font-mono text-[11.5px] font-semibold cursor-pointer hover:text-accent-dark" @click="openDoc(r.name)">{{ r.name }}</td>
              <td class="px-4 py-2.5 truncate max-w-[200px]">{{ r.party || "—" }}</td>
              <td class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ r.date }}</td>
              <td class="px-4 py-2.5 text-end tnum">{{ fmt(r.amount) }}</td>
              <td class="px-4 py-2.5 text-end">
                <button class="h-7 px-2.5 rounded-[8px] text-[11px] font-bold text-white bg-brand hover:bg-brand-dark inline-flex items-center gap-1 disabled:opacity-50" :disabled="busy === r.name" @click="pickFile(r)">
                  <Icon name="plus" :size="12" color="#fff" />{{ busy === r.name ? L("Uploading…","جارٍ…","…") : L("Attach","إرفاق","Joindre") }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    <input ref="fileInput" type="file" class="hidden" @change="onFile" />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";
import { useToast } from "@/composables/useToast";

const { locale } = useI18n();
const { entityId } = useUi();
const router = useRouter();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US");

const KINDS = [
  { key: "bills", label: () => L("Supplier bills", "فواتير الموردين", "Factures fourn.") },
  { key: "payments", label: () => L("Payments out", "مدفوعات", "Paiements") },
  { key: "journals", label: () => L("Journals", "قيود", "Écritures") },
];
const kind = ref("bills");
const rows = ref([]);
const counts = reactive({});
const isLive = ref(null);
const loading = ref(true);
const search = ref("");
const busy = ref("");
const doctype = ref("Purchase Invoice");
let t = null;

async function load() {
  loading.value = true;
  try {
    const r = await api.call("accounting_portal.api.docmeta.missing_documents", { company: currentCompany(), kind: kind.value, search: search.value || undefined });
    rows.value = r.rows || []; doctype.value = r.doctype; Object.assign(counts, r.counts || {}); isLive.value = true;
  } catch { rows.value = []; isLive.value = false; }
  finally { loading.value = false; }
}
function setKind(k) { kind.value = k; load(); }
function onSearch() { clearTimeout(t); t = setTimeout(load, 350); }
onMounted(load);
watch(entityId, load);

const ROUTE = { "Purchase Invoice": "purchases/bills", "Payment Entry": "purchases/payments", "Journal Entry": "accountant/journals" };
function openDoc(name) { router.push({ path: `/accounting/${ROUTE[doctype.value] || "purchases/bills"}`, query: { id: name } }); }

// ── inline attach ──
const fileInput = ref(null);
const pending = ref(null);
function pickFile(r) { pending.value = r; fileInput.value.value = ""; fileInput.value.click(); }
function onFile(e) {
  const f = e.target.files && e.target.files[0];
  if (!f || !pending.value) return;
  const row = pending.value; busy.value = row.name;
  const reader = new FileReader();
  reader.onload = async () => {
    try {
      await api.call("accounting_portal.api.docmeta.add_attachment", { doctype: doctype.value, name: row.name, filename: f.name, content: reader.result });
      toast.success(L("Attached", "تم الإرفاق", "Joint"));
      rows.value = rows.value.filter((x) => x.name !== row.name);
      if (counts[kind.value] != null) counts[kind.value] = Math.max(0, counts[kind.value] - 1);
    } catch (err) { toast.error(String((err && err.message) || L("Failed", "فشل", "Échec")).slice(0, 140)); }
    finally { busy.value = ""; pending.value = null; }
  };
  reader.readAsDataURL(f);
}
</script>
