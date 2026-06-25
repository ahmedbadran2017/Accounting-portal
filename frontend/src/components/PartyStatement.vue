<template>
  <div v-if="open" class="fixed inset-0 z-[110] flex items-start justify-center p-4 overflow-y-auto" style="background:rgba(28,25,23,.45)" @click.self="$emit('close')">
    <div class="bg-white rounded-[16px] shadow-cardHover w-full max-w-2xl my-6 print-statement">
      <!-- toolbar -->
      <div class="flex items-center gap-2 px-5 py-3 border-b border-line no-print flex-wrap">
        <span class="text-[14px] font-bold">{{ L("Account statement","كشف حساب","Relevé de compte") }}</span>
        <div class="ms-auto flex items-center gap-1.5">
          <input type="date" v-model="from" @change="load" class="h-8 border border-line-2 rounded-[8px] px-2 text-[11.5px] focus:outline-none focus:border-accent/40" />
          <span class="text-ink-muted text-[11px]">→</span>
          <input type="date" v-model="to" @change="load" class="h-8 border border-line-2 rounded-[8px] px-2 text-[11.5px] focus:outline-none focus:border-accent/40" />
          <button @click="exportCsv" class="h-8 px-2.5 rounded-[8px] text-[11.5px] font-semibold text-ink-2 border border-line-2 hover:bg-app-warm">CSV</button>
          <button @click="printIt" class="h-8 px-2.5 rounded-[8px] text-[11.5px] font-bold text-white bg-ink hover:opacity-90 inline-flex items-center gap-1"><Icon name="doc" :size="12" color="#fff" />{{ L("Print","طباعة","Imprimer") }}</button>
          <button @click="$emit('close')" class="h-8 w-8 grid place-items-center rounded-[8px] text-ink-3 hover:bg-app-warm">✕</button>
        </div>
      </div>

      <!-- printable body -->
      <div class="p-5">
        <div class="flex justify-between items-start mb-4 flex-wrap gap-2">
          <div>
            <div class="text-[16px] font-bold">{{ partyName }}</div>
            <div class="text-[11px] text-ink-3">{{ s.company }} · {{ partyType === "Supplier" ? L("Supplier","مورّد","Fournisseur") : L("Customer","عميل","Client") }}</div>
          </div>
          <div class="text-end">
            <div class="text-[12px] font-bold text-ink-2">{{ L("Statement period","فترة الكشف","Période") }}</div>
            <div class="text-[11px] text-ink-3 tnum">{{ from || "—" }} → {{ to || "—" }}</div>
          </div>
        </div>

        <div class="grid grid-cols-3 gap-2 mb-3">
          <div class="rounded-[10px] px-3 py-2" style="background:#fafaf9;border:1px solid #f0efed">
            <div class="text-[9.5px] text-ink-muted font-semibold uppercase tracking-wide">{{ L("Opening","رصيد افتتاحي","Ouverture") }}</div>
            <div class="text-[14px] font-bold tnum">{{ f2(s.opening) }}</div>
          </div>
          <div class="rounded-[10px] px-3 py-2" style="background:#fafaf9;border:1px solid #f0efed">
            <div class="text-[9.5px] text-ink-muted font-semibold uppercase tracking-wide">{{ L("Movement","الحركة","Mouvement") }}</div>
            <div class="text-[14px] font-bold tnum">{{ f2((s.debit_total||0) - (s.credit_total||0)) }}</div>
          </div>
          <div class="rounded-[10px] px-3 py-2" style="background:#f0fdf4;border:1px solid #bbf7d0">
            <div class="text-[9.5px] text-ink-muted font-semibold uppercase tracking-wide">{{ L("Closing","رصيد ختامي","Clôture") }}</div>
            <div class="text-[14px] font-bold tnum text-success-dark">{{ f2(s.closing) }} <span class="text-[10px] text-ink-muted">{{ s.currency }}</span></div>
          </div>
        </div>

        <div v-if="loading" class="py-10 text-center text-[12px] text-ink-muted">{{ L("Loading…","تحميل…","…") }}</div>
        <div v-else class="border border-line rounded-[10px] overflow-hidden overflow-x-auto">
          <table class="w-full text-[11.5px]">
            <thead><tr style="background:#fafaf9">
              <th class="px-3 py-2 text-start text-[9.5px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Date","التاريخ","Date") }}</th>
              <th class="px-3 py-2 text-start text-[9.5px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Voucher","المستند","Pièce") }}</th>
              <th class="px-3 py-2 text-end text-[9.5px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Debit","مدين","Débit") }}</th>
              <th class="px-3 py-2 text-end text-[9.5px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Credit","دائن","Crédit") }}</th>
              <th class="px-3 py-2 text-end text-[9.5px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Balance","الرصيد","Solde") }}</th>
            </tr></thead>
            <tbody>
              <tr style="background:#fcfcfb"><td class="px-3 py-1.5 text-ink-muted italic" colspan="4">{{ L("Opening balance","الرصيد الافتتاحي","Solde d'ouverture") }}</td><td class="px-3 py-1.5 text-end tnum font-semibold">{{ f2(s.opening) }}</td></tr>
              <tr v-for="(r, i) in (s.rows || [])" :key="i" class="border-t border-line-hair">
                <td class="px-3 py-1.5 text-ink-3 whitespace-nowrap">{{ r.date }}</td>
                <td class="px-3 py-1.5 font-mono text-[10.5px]">{{ r.doc }}<span v-if="r.type" class="text-ink-muted"> · {{ r.type }}</span></td>
                <td class="px-3 py-1.5 text-end tnum">{{ r.debit ? f2(r.debit) : "" }}</td>
                <td class="px-3 py-1.5 text-end tnum">{{ r.credit ? f2(r.credit) : "" }}</td>
                <td class="px-3 py-1.5 text-end tnum font-semibold">{{ f2(r.balance) }}</td>
              </tr>
              <tr v-if="!(s.rows || []).length"><td colspan="5" class="px-3 py-6 text-center text-ink-muted">{{ L("No movements in this period.","لا حركات في هذه الفترة.","Aucun mouvement.") }}</td></tr>
            </tbody>
            <tfoot>
              <tr class="border-t-2 border-line-2 font-bold" style="background:#fafaf9">
                <td class="px-3 py-2" colspan="2">{{ L("Closing balance","الرصيد الختامي","Solde de clôture") }}</td>
                <td class="px-3 py-2 text-end tnum">{{ f2(s.debit_total) }}</td>
                <td class="px-3 py-2 text-end tnum">{{ f2(s.credit_total) }}</td>
                <td class="px-3 py-2 text-end tnum text-success-dark">{{ f2(s.closing) }}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";

const props = defineProps({ open: Boolean, partyType: String, party: String, partyName: String });
defineEmits(["close"]);
const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const f2 = (n) => (n || n === 0 ? Number(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "");

const y = new Date().getFullYear();
const from = ref(`${y}-01-01`);
const to = ref(new Date().toISOString().slice(0, 10));
const s = ref({});
const loading = ref(false);

async function load() {
  if (!props.party) return;
  loading.value = true;
  try { s.value = await api.call("accounting_portal.api.reports.party_statement", { party_type: props.partyType, party: props.party, company: currentCompany(), from_date: from.value, to_date: to.value }); }
  catch { s.value = {}; }
  finally { loading.value = false; }
}
watch(() => [props.open, props.party], () => { if (props.open && props.party) load(); }, { immediate: true });

function printIt() { window.print(); }
function exportCsv() {
  const rows = s.value.rows || [];
  const head = ["Date", "Voucher", "Type", "Debit", "Credit", "Balance"];
  const lines = [head.join(",")];
  lines.push(`Opening,,,,,"${s.value.opening}"`);
  rows.forEach((r) => lines.push([r.date, r.doc, r.type, r.debit, r.credit, r.balance].map((x) => `"${x ?? ""}"`).join(",")));
  lines.push(`Closing,,,"${s.value.debit_total}","${s.value.credit_total}","${s.value.closing}"`);
  const blob = new Blob([lines.join("\n")], { type: "text/csv" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `statement-${props.party}-${from.value}.csv`;
  a.click();
}
</script>

<style>
@media print {
  body * { visibility: hidden !important; }
  .print-statement, .print-statement * { visibility: visible !important; }
  .print-statement { position: absolute !important; left: 0; top: 0; width: 100%; max-width: none !important; margin: 0 !important; box-shadow: none !important; }
  .no-print { display: none !important; }
}
</style>
