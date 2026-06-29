<template>
  <div class="bg-white rounded-card border border-line overflow-hidden shadow-card">
    <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
      <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#faf6f4"><Icon name="list" :size="14" color="#0b5c4f" /></span>
      <span class="text-[13px] font-bold">{{ L("Bank transactions", "حركات البنوك", "Transactions bancaires") }}</span>
      <span v-if="live !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="live ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ live ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échant.") }}</span>
      <span class="hidden lg:inline text-[11px] text-ink-muted">{{ rows.length }} {{ L("movements", "حركة", "mouvements") }}</span>
      <div class="relative ms-auto">
        <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
        <input v-model.trim="srch" :placeholder="L('Voucher / account…', 'مستند / حساب…', 'Pièce / compte…')" class="w-44 sm:w-56 h-9 bg-app-warm/40 border border-line-2 rounded-[10px] ps-9 pe-3 text-[12.5px] focus:outline-none focus:border-accent/40 focus:bg-white" />
      </div>
    </div>

    <div class="flex items-center gap-2 px-4 py-2.5 border-b border-line-hair flex-wrap bg-app-warm/20">
      <Icon name="clock" :size="13" color="#a8a29e" />
      <button v-for="x in PRESETS" :key="x.key" class="text-[11px] font-semibold px-2.5 py-1 rounded-full border transition" :class="preset === x.key ? 'bg-ink text-white border-ink' : 'bg-white text-ink-3 border-line-2 hover:bg-app-warm'" @click="setPreset(x.key)">{{ x.label() }}</button>
      <span v-if="loading" class="ms-2 text-[11px] text-ink-muted inline-flex items-center gap-1.5"><span class="w-1.5 h-1.5 rounded-full bg-accent animate-pulse"></span>{{ L("loading…", "تحميل…", "…") }}</span>
    </div>

    <TableToolbar :t="tt" filename="bank-transactions" />
    <div v-if="loading" class="px-1"><TableLoading :rows="6" /></div>
    <div v-else class="overflow-x-auto">
      <table class="w-full text-[12px]">
        <thead><tr style="background:#fafaf9">
          <th v-for="c in cols" v-show="!tt.hidden.value.has(c.key)" :key="c.key"
              class="px-4 py-2.5 text-[10px] font-bold uppercase tracking-wider text-ink-muted whitespace-nowrap cursor-pointer select-none hover:text-ink-2" :class="c.align === 'e' ? 'text-end' : 'text-start'" @click="tt.toggleSort(c.key)">
            <span class="inline-flex items-center gap-1" :class="c.align === 'e' ? 'flex-row-reverse' : ''">{{ c.label }}<Icon v-if="tt.sortKey.value === c.key" name="chevDown" :size="11" :class="tt.sortDir.value === 1 ? '' : 'rotate-180'" color="#0b5c4f" /></span>
          </th>
        </tr></thead>
        <tbody>
          <tr v-for="o in tt.pageRows.value" :key="o.voucher + o.date" class="border-t border-line-hair hover:bg-app-warm/70 cursor-pointer" @click="open(o)">
            <td v-show="!tt.hidden.value.has('date')" class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ o.date }}</td>
            <td v-show="!tt.hidden.value.has('voucher')" class="px-4 py-2.5"><div class="font-mono font-semibold">{{ o.voucher }}</div><div class="text-[10px] text-ink-muted">{{ o.type }}<span v-if="o.against"> · {{ o.against }}</span></div></td>
            <td v-show="!tt.hidden.value.has('account')" class="px-4 py-2.5 text-ink-2 truncate max-w-[200px]">{{ o.account }}</td>
            <td v-show="!tt.hidden.value.has('amount')" class="px-4 py-2.5 text-end font-bold tnum whitespace-nowrap" :class="o.amount < 0 ? 'text-sale' : 'text-success-dark'">{{ o.amount < 0 ? "−" : "+" }}{{ fmt(Math.abs(o.amount)) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="!loading && !tt.sorted.value.length" class="py-12 text-center text-[12px] text-ink-muted">{{ L("No transactions.", "لا حركات.", "Aucune transaction.") }}</div>
    <TablePager :t="tt" />
  </div>
</template>

<script setup>
import { ref, watch } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableToolbar from "@/components/TableToolbar.vue";
import TablePager from "@/components/TablePager.vue";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { usePersistedRef } from "@/composables/usePersistedRef";
import { useUi } from "@/composables/useUi";
import { useTableTools } from "@/composables/useTableTools";

const { locale } = useI18n();
const router = useRouter();
const { entityId } = useUi();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const PRESETS = [
  { key: "30d", label: () => L("30 days", "30 يوم", "30 j") },
  { key: "month", label: () => L("This month", "هذا الشهر", "Ce mois") },
  { key: "7d", label: () => L("7 days", "7 أيام", "7 j") },
  { key: "all", label: () => L("All", "الكل", "Tout") },
];
const cols = [
  { key: "date", label: L("Date", "التاريخ", "Date"), align: "s" },
  { key: "voucher", label: L("Voucher", "المستند", "Pièce"), align: "s" },
  { key: "account", label: L("Account", "الحساب", "Compte"), align: "s" },
  { key: "amount", label: L("Amount", "المبلغ", "Montant"), align: "e" },
];

const rows = ref([]);
const live = ref(null);
const loading = ref(false);
const srch = ref("");
const preset = usePersistedRef("ap_banktx_preset", "30d");
const tt = useTableTools(rows, cols, { storeKey: "banktx", defaultSort: "date", defaultDir: -1, accessor: (r, k) => (k === "amount" ? Number(r.amount) || 0 : r[k]) });

function bounds() {
  const iso = (d) => d.toISOString().slice(0, 10);
  const now = new Date(); const t = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  if (preset.value === "7d") { const s = new Date(t); s.setDate(s.getDate() - 7); return [iso(s), iso(now)]; }
  if (preset.value === "30d") { const s = new Date(t); s.setDate(s.getDate() - 30); return [iso(s), iso(now)]; }
  if (preset.value === "month") return [iso(new Date(now.getFullYear(), now.getMonth(), 1)), iso(now)];
  return [null, null];
}
const SAMPLE = [
  { date: "2026-06-21", type: "Payment Entry", voucher: "PAY-22493", account: "Cathedis", against: "", amount: 63700 },
  { date: "2026-06-20", type: "Payment Entry", voucher: "PAY-20918", account: "320.01", against: "Meta", amount: -44800 },
];
async function load() {
  loading.value = true;
  const [fd, td] = bounds();
  try { rows.value = await api.call("accounting_portal.api.reconciliation.bank_transactions", { company: currentCompany(), from_date: fd || undefined, to_date: td || undefined, search: srch.value || undefined, limit: 500 }) || []; live.value = true; }
  catch { rows.value = SAMPLE; live.value = false; }
  finally { loading.value = false; }
}
function setPreset(k) { preset.value = k; load(); }
function open(o) {
  if (o.type === "Payment Entry") router.push({ path: "/accounting/purchases/payments", query: { id: o.voucher } });
  else if (o.type === "Journal Entry") router.push({ path: "/accounting/accountant/journals", query: { id: o.voucher } });
}
let timer;
watch(entityId, load, { immediate: true });
watch(srch, () => { clearTimeout(timer); timer = setTimeout(load, 300); });
</script>
