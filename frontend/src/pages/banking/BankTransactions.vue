<template>
  <div class="space-y-3">
    <DateFilterBar :df="df" />
    <div class="bg-white rounded-card border border-line overflow-hidden shadow-card">
      <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
        <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#faf6f4"><Icon name="ledger" :size="14" color="#0b5c4f" /></span>
        <span class="text-[13px] font-bold">{{ L("Bank transactions", "حركات البنوك", "Transactions bancaires") }}</span>
        <span v-if="live !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="live ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ live ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échant.") }}</span>
        <span class="hidden lg:inline text-[11px] text-ink-muted">{{ (st.total.value || 0).toLocaleString() }} {{ L("movements", "حركة", "mouvements") }}</span>
        <div class="relative ms-auto">
          <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
          <input v-model.trim="st.search.value" :placeholder="L('Voucher / account…', 'مستند / حساب…', 'Pièce / compte…')" class="w-44 sm:w-56 h-9 bg-app-warm/40 border border-line-2 rounded-[10px] ps-9 pe-3 text-[12.5px] focus:outline-none focus:border-accent/40 focus:bg-white" />
        </div>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead><tr style="background:#fafaf9">
            <th v-for="c in cols" :key="c.key" class="px-4 py-2.5 text-[10px] font-bold uppercase tracking-wider text-ink-muted whitespace-nowrap select-none"
                :class="[c.align === 'e' ? 'text-end' : 'text-start', c.sort ? 'cursor-pointer hover:text-ink-2' : '']" @click="c.sort && st.setSort(c.sort)">
              <span class="inline-flex items-center gap-1" :class="c.align === 'e' ? 'flex-row-reverse' : ''">{{ c.label }}
                <Icon v-if="c.sort && st.sortField.value === c.sort" name="chevDown" :size="11" :class="st.sortDir.value === 'asc' ? 'rotate-180' : ''" color="#0b5c4f" /></span>
            </th>
          </tr></thead>
          <tbody>
            <tr v-for="o in st.rows.value" :key="o.voucher + o.date" class="border-t border-line-hair hover:bg-app-warm/70 cursor-pointer" @click="open(o)">
              <td class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ o.date }}</td>
              <td class="px-4 py-2.5"><div class="font-mono font-semibold">{{ o.voucher }}</div><div class="text-[10px] text-ink-muted">{{ o.type }}<span v-if="o.against"> · {{ o.against }}</span></div></td>
              <td class="px-4 py-2.5 text-ink-2 truncate max-w-[200px]">{{ o.account }}</td>
              <td class="px-4 py-2.5 text-end font-bold tnum whitespace-nowrap" :class="o.amount < 0 ? 'text-sale' : 'text-success-dark'">{{ o.amount < 0 ? "−" : "+" }}{{ fmt(Math.abs(o.amount)) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <TableLoading v-if="st.loading.value" :rows="6" />
      <div v-else-if="!st.rows.value.length" class="py-12 text-center text-[12px] text-ink-muted">{{ L("No transactions.", "لا حركات.", "Aucune transaction.") }}</div>
      <ServerPager :t="st" />
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import ServerPager from "@/components/ServerPager.vue";
import TableLoading from "@/components/TableLoading.vue";
import DateFilterBar from "@/components/DateFilterBar.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useServerTable } from "@/composables/useServerTable";
import { useDateFilter } from "@/composables/useDateFilter";
import { useUi } from "@/composables/useUi";

const { locale } = useI18n();
const router = useRouter();
const { entityId } = useUi();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const cols = [
  { key: "date", label: L("Date", "التاريخ", "Date"), align: "s", sort: "date" },
  { key: "voucher", label: L("Voucher", "المستند", "Pièce"), align: "s", sort: "voucher" },
  { key: "account", label: L("Account", "الحساب", "Compte"), align: "s", sort: "account" },
  { key: "amount", label: L("Amount", "المبلغ", "Montant"), align: "e", sort: "amount" },
];

const live = ref(null);
const df = useDateFilter("banktx", (f) => st.setFilters(f), "month");
const st = useServerTable(
  (params) => api.call("accounting_portal.api.reconciliation.bank_transactions", { company: currentCompany(), ...params }).then((r) => { live.value = true; return r; }),
  { pageSize: 50, sortField: "date", sortDir: "desc", filters: df.filterValue() },
);
st.load();
watch(entityId, () => { st.page.value = 1; st.load(); });

function open(o) {
  if (o.type === "Payment Entry") router.push({ path: "/accounting/purchases/payments", query: { id: o.voucher } });
  else if (o.type === "Journal Entry") router.push({ path: "/accounting/accountant/journals", query: { id: o.voucher } });
}
</script>
