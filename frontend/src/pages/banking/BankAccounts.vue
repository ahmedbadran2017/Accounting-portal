<template>
  <div class="space-y-3.5">
    <!-- Insights -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <div class="relative bg-white border border-line rounded-[16px] p-4 shadow-card overflow-hidden">
        <span class="absolute top-0 inset-x-0 h-[3px]" style="background:#0b5c4f;opacity:.3"></span>
        <div class="flex items-center gap-2"><span class="w-8 h-8 rounded-[10px] grid place-items-center" style="background:#faf6f4"><Icon name="scale" :size="15" color="#0b5c4f" /></span><span class="text-[10.5px] text-ink-muted font-bold uppercase tracking-wider">{{ L("Cash position", "المركز النقدي", "Trésorerie") }}</span></div>
        <div class="text-[22px] font-extrabold tnum mt-2 leading-none" :class="ins.position < 0 ? 'text-sale' : ''">{{ money(ins.position) }}<span class="text-[11px] text-ink-muted ms-1">MAD</span></div>
        <div class="text-[11px] text-ink-muted mt-1.5">{{ accounts.length }} {{ L("accounts", "حساب", "comptes") }}</div>
      </div>
      <div class="relative bg-white border border-line rounded-[16px] p-4 shadow-card overflow-hidden">
        <span class="absolute top-0 inset-x-0 h-[3px]" style="background:#0369a1;opacity:.3"></span>
        <div class="flex items-center gap-2"><span class="w-8 h-8 rounded-[10px] grid place-items-center" style="background:#eff6ff"><Icon name="bank" :size="15" color="#0369a1" /></span><span class="text-[10.5px] text-ink-muted font-bold uppercase tracking-wider">{{ L("In banks", "في البنوك", "En banque") }}</span></div>
        <div class="text-[22px] font-extrabold tnum mt-2 leading-none">{{ money(ins.bank) }}<span class="text-[11px] text-ink-muted ms-1">MAD</span></div>
        <div class="text-[11px] text-ink-muted mt-1.5">{{ L("Cash on hand", "نقد بالخزينة", "Caisse") }} {{ money(ins.cash) }}</div>
      </div>
      <button @click="goRec" class="relative bg-white border rounded-[16px] p-4 shadow-card overflow-hidden text-start hover:-translate-y-0.5 hover:shadow-cardHover transition-all" style="border-color:#fde68a">
        <span class="absolute top-0 inset-x-0 h-[3px]" style="background:#b45309;opacity:.4"></span>
        <div class="flex items-center gap-2"><span class="w-8 h-8 rounded-[10px] grid place-items-center" style="background:#fffbeb"><Icon name="clock" :size="15" color="#b45309" /></span><span class="text-[10.5px] text-ink-muted font-bold uppercase tracking-wider">{{ L("Unreconciled", "غير مُسوّى", "Non rapproché") }}</span></div>
        <div class="text-[22px] font-extrabold tnum mt-2 leading-none" style="color:#b45309">{{ money(ins.uncleared) }}<span class="text-[11px] text-ink-muted ms-1">MAD</span></div>
        <div class="text-[11px] text-brand font-semibold mt-1.5">{{ ins.uncleared_n }} {{ L("entries → reconcile", "قيد → سوِّ", "écritures") }}</div>
      </button>
      <div class="relative bg-white border rounded-[16px] p-4 shadow-card overflow-hidden" :style="{ borderColor: ins.overdraft_n ? '#fecaca' : '#e7e5e4' }">
        <span class="absolute top-0 inset-x-0 h-[3px]" :style="{ background: ins.overdraft_n ? '#be123c' : '#a8a29e', opacity: .4 }"></span>
        <div class="flex items-center gap-2"><span class="w-8 h-8 rounded-[10px] grid place-items-center" :style="{ background: ins.overdraft_n ? '#fef2f2' : '#f5f5f4' }"><Icon name="alert" :size="15" :color="ins.overdraft_n ? '#be123c' : '#a8a29e'" /></span><span class="text-[10.5px] text-ink-muted font-bold uppercase tracking-wider">{{ L("Overdrafts", "كشوفات مدينة", "Découverts") }}</span></div>
        <div class="text-[22px] font-extrabold tnum mt-2 leading-none" :class="ins.overdraft_n ? 'text-sale' : 'text-ink-muted'">{{ ins.overdraft_n }}</div>
        <div class="text-[11px] mt-1.5" :class="ins.overdraft_n ? 'text-sale font-semibold' : 'text-ink-muted'">{{ ins.overdraft_n ? money(ins.overdraft_v) + " MAD" : L("all positive ✓", "كلها موجبة ✓", "tous positifs ✓") }}</div>
      </div>
    </div>

    <!-- Accounts table -->
    <div class="bg-white rounded-card border border-line overflow-hidden shadow-card">
      <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
        <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#eff6ff"><Icon name="bank" :size="14" color="#0369a1" /></span>
        <span class="text-[13px] font-bold">{{ L("Bank & cash accounts", "حسابات البنوك والنقد", "Comptes bancaires & caisse") }}</span>
        <span v-if="live !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border" :style="live ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ live ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échant.") }}</span>
        <div class="relative ms-auto">
          <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
          <input v-model.trim="tt.search.value" :placeholder="L('Account…', 'حساب…', 'Compte…')" class="w-40 sm:w-52 h-9 bg-app-warm/40 border border-line-2 rounded-[10px] ps-9 pe-3 text-[12.5px] focus:outline-none focus:border-accent/40 focus:bg-white" />
        </div>
      </div>
      <TableToolbar :t="tt" filename="bank-accounts" />
      <div v-if="loading" class="px-1"><TableLoading :rows="4" /></div>
      <div v-else class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead><tr style="background:#fafaf9">
            <th v-for="c in cols" v-show="!tt.hidden.value.has(c.key)" :key="c.key"
                class="px-4 py-2.5 text-[10px] font-bold uppercase tracking-wider text-ink-muted whitespace-nowrap cursor-pointer select-none hover:text-ink-2" :class="c.align === 'e' ? 'text-end' : 'text-start'" @click="tt.toggleSort(c.key)">
              <span class="inline-flex items-center gap-1" :class="c.align === 'e' ? 'flex-row-reverse' : ''">{{ c.label }}<Icon v-if="tt.sortKey.value === c.key" name="chevDown" :size="11" :class="tt.sortDir.value === 1 ? '' : 'rotate-180'" color="#0b5c4f" /></span>
            </th>
          </tr></thead>
          <tbody>
            <tr v-for="o in tt.pageRows.value" :key="o.name" class="border-t border-line-hair hover:bg-app-warm/70 cursor-pointer" @click="open(o.name)">
              <td v-show="!tt.hidden.value.has('account_name')" class="px-4 py-2.5"><div class="font-semibold truncate max-w-[280px]">{{ o.account_name }}</div><div class="text-[10px] text-ink-muted font-mono">{{ o.name.split(' - ')[0] }}</div></td>
              <td v-show="!tt.hidden.value.has('account_type')" class="px-4 py-2.5"><span class="text-[10px] font-bold px-2 py-0.5 rounded-full" :style="o.account_type === 'Cash' ? 'background:#fffbeb;color:#b45309' : 'background:#eff6ff;color:#0369a1'">{{ o.account_type }}</span></td>
              <td v-show="!tt.hidden.value.has('ccy')" class="px-4 py-2.5 text-ink-3">{{ o.ccy }}</td>
              <td v-show="!tt.hidden.value.has('uncleared_n')" class="px-4 py-2.5 text-end tnum" :class="o.uncleared_n ? 'text-brand font-semibold' : 'text-ink-muted'">{{ o.uncleared_n || "—" }}</td>
              <td v-show="!tt.hidden.value.has('book')" class="px-4 py-2.5 text-end font-bold tnum whitespace-nowrap" :class="o.book < 0 ? 'text-sale' : ''">{{ fmt(o.book) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="!loading && !tt.sorted.value.length" class="py-12 text-center text-[12px] text-ink-muted">{{ L("No accounts.", "لا حسابات.", "Aucun compte.") }}</div>
      <TablePager :t="tt" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableToolbar from "@/components/TableToolbar.vue";
import TablePager from "@/components/TablePager.vue";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";
import { useTableTools } from "@/composables/useTableTools";

const { locale } = useI18n();
const router = useRouter();
const { entityId } = useUi();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const money = (n) => { n = Number(n) || 0; const a = Math.abs(n); return a >= 1e6 ? (n / 1e6).toFixed(2) + "M" : a >= 1e3 ? Math.round(n / 1e3) + "K" : Math.round(n).toLocaleString(); };

const cols = [
  { key: "account_name", label: L("Account", "الحساب", "Compte"), align: "s" },
  { key: "account_type", label: L("Type", "النوع", "Type"), align: "s" },
  { key: "ccy", label: L("Currency", "العملة", "Devise"), align: "s" },
  { key: "uncleared_n", label: L("Uncleared", "غير مُسوّى", "Non rappr."), align: "e" },
  { key: "book", label: L("Balance", "الرصيد", "Solde"), align: "e" },
];

const accounts = ref([]);
const live = ref(null);
const loading = ref(false);
const tt = useTableTools(accounts, cols, { keyField: "name", defaultSort: "book", defaultDir: -1, accessor: (r, k) => (k === "book" || k === "uncleared_n" ? Number(r[k]) || 0 : r[k]) });

const ins = computed(() => {
  const mad = accounts.value.filter((a) => a.ccy === "MAD");
  const sum = (f) => mad.reduce((s, a) => s + (f(a) ? Number(a.book) || 0 : 0), 0);
  const od = accounts.value.filter((a) => Number(a.book) < 0);
  return {
    position: sum(() => true),
    bank: sum((a) => a.account_type === "Bank"),
    cash: sum((a) => a.account_type === "Cash"),
    uncleared: accounts.value.reduce((s, a) => s + (Number(a.uncleared_v) || 0), 0),
    uncleared_n: accounts.value.reduce((s, a) => s + (Number(a.uncleared_n) || 0), 0),
    overdraft_n: od.length, overdraft_v: od.reduce((s, a) => s + (Number(a.book) || 0), 0),
  };
});

const SAMPLE = [
  { name: "108.021.003 - Cathedis - JM", account_name: "Cathedis", account_type: "Bank", ccy: "MAD", book: 471081, uncleared_n: 642, uncleared_v: 1208400 },
  { name: "102.02.01.01 - BMCE - JM", account_name: "BMCE-…130355", account_type: "Bank", ccy: "MAD", book: 12483, uncleared_n: 3407, uncleared_v: 44372442 },
  { name: "100.002.002 - Petty cash - JM", account_name: "Petty cash", account_type: "Cash", ccy: "MAD", book: -845264, uncleared_n: 120, uncleared_v: 280000 },
];
async function load() {
  loading.value = true;
  try { accounts.value = await api.call("accounting_portal.api.reconciliation.bank_rec_accounts", { company: currentCompany() }) || []; live.value = true; }
  catch { accounts.value = SAMPLE; live.value = false; }
  finally { loading.value = false; }
}
function open(name) { router.push({ path: "/accounting/banking/accounts", query: { id: name } }); }
function goRec() { router.push("/accounting/banking/bankrec"); }
watch(entityId, load, { immediate: true });
</script>
