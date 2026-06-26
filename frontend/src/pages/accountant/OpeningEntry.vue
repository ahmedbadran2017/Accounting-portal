<template>
  <div class="space-y-3">
    <div class="flex items-center gap-2 flex-wrap">
      <span class="text-[13px] font-bold">{{ L("Opening balances","الأرصدة الافتتاحية","Soldes d'ouverture") }}</span>
      <button class="ms-auto inline-flex items-center gap-1.5 text-[12px] font-semibold text-white bg-brand hover:bg-brand-dark px-3 py-1.5 rounded-chip shadow-brand" @click="showForm = true">
        <Icon name="plus" :size="14" />{{ L("New opening entry","قيد افتتاحي","Écriture d'ouverture") }}
      </button>
    </div>

    <div class="bg-white border border-line rounded-card shadow-card overflow-hidden">
      <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2">
        <span class="text-[12.5px] font-bold">{{ L("Recent opening entries","قيود افتتاحية حديثة","Écritures d'ouverture récentes") }}</span>
        <span v-if="isLive !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="isLive ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ isLive ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échant.") }}</span>
      </div>
      <TableLoading v-if="loading" :rows="5" />
      <table v-else class="w-full text-[12px]">
        <thead><tr style="background:#fafaf9">
          <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Entry","القيد","Écriture") }}</th>
          <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Date","التاريخ","Date") }}</th>
          <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Memo","ملاحظة","Mémo") }}</th>
          <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Amount","المبلغ","Montant") }}</th>
        </tr></thead>
        <tbody>
          <tr v-for="r in rows" :key="r.name" class="border-t border-line-hair hover:bg-app-warm/40 cursor-pointer" @click="openJe(r.name)">
            <td class="px-4 py-2.5 font-mono text-[11px] font-semibold hover:text-accent-dark">{{ r.name }}</td>
            <td class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ r.date }}</td>
            <td class="px-4 py-2.5 truncate max-w-[280px]">{{ r.remark || "—" }}</td>
            <td class="px-4 py-2.5 text-end tnum font-semibold">{{ money(r.amount) }}</td>
          </tr>
          <tr v-if="!rows.length"><td colspan="4" class="px-4 py-10 text-center text-ink-muted text-[12px]">{{ L("No opening entries yet — create one to seed account balances.","لا قيود افتتاحية بعد.","Aucune écriture d'ouverture.") }}</td></tr>
        </tbody>
      </table>
    </div>

    <JournalEntryForm v-if="showForm" :opening="true" @close="showForm = false" @posted="onPosted" />
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import JournalEntryForm from "@/components/JournalEntryForm.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";
import { useToast } from "@/composables/useToast";

const { locale } = useI18n();
const { entityId } = useUi();
const router = useRouter();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const money = (n) => Number(n || 0).toLocaleString("en-US", { maximumFractionDigits: 0 });

const rows = ref([]);
const isLive = ref(null);
const loading = ref(true);
const showForm = ref(false);

async function load() {
  loading.value = true;
  try {
    const all = await api.call("accounting_portal.api.accountant.list_journals", { company: currentCompany(), search: "Opening", limit: 50 });
    rows.value = (all || []).filter((j) => (j.type || j.voucher_type) === "Opening Entry").map((j) => ({ name: j.name, date: j.date || j.posting_date, remark: j.remark || j.user_remark, amount: j.amount || j.total_debit }));
    isLive.value = true;
  } catch { rows.value = []; isLive.value = false; }
  finally { loading.value = false; }
}
onMounted(load);
watch(entityId, load);

function openJe(name) { router.push({ path: "/accounting/accountant/journals", query: { id: name } }); }
function onPosted(res) {
  if (res && res.status && res.status !== "Posted") toast.success(L("Queued for approval (over 10,000)", "بانتظار الموافقة (فوق 10٬000)", "En attente d'approbation"));
  else toast.success(L("Opening entry posted", "تم ترحيل القيد الافتتاحي", "Écriture passée"));
  load();
}
</script>
