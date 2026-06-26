<template>
  <div class="space-y-3.5">
    <!-- Headline: the −2.85M over-collection story -->
    <div class="flex items-center gap-2 flex-wrap">
      <span class="text-[13px] font-bold">{{ L("COD cash reconciliation","تسوية كاش COD","Rapprochement COD") }}</span>
      <span v-if="isLive !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border"
            :style="isLive ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ isLive ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échant.") }}</span>
      <span class="text-[11px] text-ink-muted flex-1">{{ L("Unallocated COD receipts vs open invoices — clear the debtor balance","سندات COD غير مخصّصة مقابل فواتير مفتوحة — صفِّ رصيد المدينون","Encaissements COD non lettrés vs factures ouvertes") }}</span>
    </div>

    <div class="grid grid-cols-2 lg:grid-cols-4 gap-2.5">
      <div v-for="s in stats" :key="s.label" class="bg-white rounded-[12px] border p-3.5 shadow-card" :style="{ borderColor: s.bd || '#efe9e6' }">
        <div class="text-[10.5px] text-ink-muted font-semibold">{{ s.label }}</div>
        <div class="text-[19px] font-bold tnum mt-[3px]" :style="{ color: s.color || '#1c1917' }">{{ s.value }}</div>
        <div class="text-[10.5px] text-ink-3 mt-0.5">{{ s.sub }}</div>
      </div>
    </div>

    <!-- Unallocated receipts queue -->
    <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
      <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2">
        <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#fff7ed"><Icon name="coins" :size="14" color="#c2410c" /></span>
        <span class="text-[13px] font-bold">{{ L("Unallocated COD receipts","سندات COD غير مخصّصة","Encaissements non lettrés") }}</span>
        <span class="text-[11px] text-ink-muted">{{ L("Cash collected, not yet matched to an invoice","كاش محصّل، غير مطابق لفاتورة","Cash encaissé, non rapproché") }}</span>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead>
            <tr style="background:#fafaf9">
              <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Receipt","السند","Reçu") }}</th>
              <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Customer","العميل","Client") }}</th>
              <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Channel","القناة","Canal") }}</th>
              <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Unallocated","غير مخصّص","Non lettré") }}</th>
              <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Date","التاريخ","Date") }}</th>
              <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in rows" :key="r.name" class="border-t border-line-hair hover:bg-app-warm/60">
              <td class="px-4 py-2.5 font-mono font-semibold whitespace-nowrap">{{ r.name }}</td>
              <td class="px-4 py-2.5 truncate max-w-[180px]">{{ r.customer }}</td>
              <td class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ r.mode || "—" }}</td>
              <td class="px-4 py-2.5 text-end tnum font-bold">{{ fmtNum(r.unallocated_amount) }}</td>
              <td class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ r.date }}</td>
              <td class="px-4 py-2.5 text-end">
                <button class="h-[27px] px-2.5 rounded-[7px] text-[10.5px] font-bold text-white bg-brand hover:bg-brand-dark" @click="openMatch(r)">{{ L("Match","طابِق","Lettrer") }}</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="!rows.length" class="py-12 text-center text-[12px] text-ink-muted">{{ L("Nothing to reconcile.","لا شيء للتسوية.","Rien à rapprocher.") }}</div>
    </div>

    <!-- Match modal -->
    <div v-if="matchRow" class="fixed inset-0 z-[110] flex items-start justify-center p-4 overflow-y-auto" style="background:rgba(28,25,23,.45)" @click.self="matchRow = null">
      <div class="bg-white rounded-[16px] shadow-cardHover w-full max-w-lg my-8">
        <div class="flex items-center gap-2.5 px-5 py-3.5 border-b border-line">
          <span class="w-8 h-8 rounded-[10px] grid place-items-center" style="background:#fff7ed"><Icon name="coins" :size="16" color="#c2410c" /></span>
          <div><div class="text-[14px] font-bold">{{ L("Match receipt","مطابقة سند","Lettrer le reçu") }}</div><div class="text-[11px] text-ink-muted">{{ matchRow.customer }} · {{ fmtNum(matchRow.unallocated_amount) }} {{ L("unallocated","غير مخصّص","non lettré") }}</div></div>
          <button class="ms-auto h-8 w-8 grid place-items-center rounded-[8px] text-ink-3 hover:bg-app-warm" @click="matchRow = null">✕</button>
        </div>
        <div class="p-5">
          <div v-if="candLoading" class="py-8 text-center text-[12px] text-ink-muted">{{ L("Finding invoices…","البحث…","…") }}</div>
          <div v-else-if="!cands.length" class="py-8 text-center text-[12px] text-ink-muted">{{ L("No open invoices for this customer.","لا فواتير مفتوحة.","Aucune facture ouverte.") }}</div>
          <div v-else class="border border-line rounded-[10px] overflow-hidden max-h-[300px] overflow-y-auto">
            <table class="w-full text-[12px]">
              <tbody>
                <tr v-for="ci in cands" :key="ci.name" class="border-t border-line-hair first:border-0 hover:bg-app-warm/50 cursor-pointer" @click="toggle(ci.name)">
                  <td class="px-3 py-2 w-8"><input type="checkbox" :checked="picked.has(ci.name)" class="accent-accent w-3.5 h-3.5" @click.stop="toggle(ci.name)" /></td>
                  <td class="px-3 py-2 font-mono text-[11px]">{{ ci.name }}<div class="text-[10px] text-ink-muted font-sans">{{ ci.date }}</div></td>
                  <td class="px-3 py-2 text-end tnum font-semibold">{{ fmtNum(ci.outstanding_amount) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-if="matchError" class="text-[11.5px] text-sale mt-2">{{ matchError }}</div>
          <div class="flex items-center justify-between mt-3">
            <span class="text-[11px] text-ink-muted">{{ picked.size }} {{ L("selected","محدّد","sélectionnées") }}</span>
            <div class="flex gap-2">
              <button class="px-3.5 py-2 rounded-chip text-[12px] font-semibold text-ink-2 hover:bg-app-warm" @click="matchRow = null">{{ L("Cancel","إلغاء","Annuler") }}</button>
              <button class="px-4 py-2 rounded-chip text-[12px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand disabled:opacity-50" :disabled="matching || !picked.size" @click="reconcile">{{ matching ? L("Matching…","جارٍ…","…") : L("Reconcile","تسوية","Lettrer") }}</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { useReconciliation, fmtMAD } from "@/composables/useReconciliation";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useToast } from "@/composables/useToast";

const { locale } = useI18n();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmtNum = (n) => Math.round(Number(n) || 0).toLocaleString("en-US");

const { summary, unmatchedPayments, candidates } = useReconciliation();
const sum = ref(null);
const rows = ref([]);
const isLive = ref(null);

async function reload() {
  const [s, u] = await Promise.all([summary(), unmatchedPayments(50)]);
  sum.value = s; rows.value = u.rows; isLive.value = !!(s && s.company);
}
onMounted(reload);

// ── Match a receipt to invoices ──
const matchRow = ref(null);
const cands = ref([]);
const candLoading = ref(false);
const picked = ref(new Set());
const matching = ref(false);
const matchError = ref("");
async function openMatch(r) {
  matchRow.value = r; cands.value = []; picked.value = new Set(); matchError.value = ""; candLoading.value = true;
  try { const c = await candidates(r.name); cands.value = (c && c.candidates) || []; } catch { cands.value = []; }
  finally { candLoading.value = false; }
}
function toggle(name) { const s = new Set(picked.value); s.has(name) ? s.delete(name) : s.add(name); picked.value = s; }
async function reconcile() {
  matchError.value = ""; matching.value = true;
  try {
    const res = await api.call("accounting_portal.api.reconciliation.reconcile_receipt", { company: currentCompany(), payment: matchRow.value.name, invoices: JSON.stringify([...picked.value]) });
    if (res && res.status === "Posted") toast.success(L("Reconciled", "تمت التسوية", "Rapproché"));
    else toast.info(L("Sent for approval", "أُرسل للموافقة", "Envoyé pour approbation"));
    matchRow.value = null; reload();
  } catch (e) { matchError.value = String((e && e.message) || L("Failed", "فشل", "Échec")).slice(0, 150); }
  finally { matching.value = false; }
}

// Sample headline (June snapshot) used until the live summary lands.
const SAMPLE = { net_debtor: -2851163, unallocated_amount: 3505260, unallocated_count: 1079, outstanding_amount: 113803, outstanding_count: 265, collected_no_invoice: 3391457 };

const stats = computed(() => {
  const d = sum.value && sum.value.company ? sum.value : SAMPLE;
  return [
    { label: L("Net debtor balance","رصيد المدينون","Solde débiteurs"), value: fmtMAD(d.net_debtor) + " MAD", sub: L("credit = over-collected","دائن = تحصيل زائد","créditeur = sur-encaissé"), color: d.net_debtor < 0 ? "#be123c" : "#047857", bd: "#fecaca" },
    { label: L("Unallocated receipts","سندات غير مخصّصة","Encaissements non lettrés"), value: fmtMAD(d.unallocated_amount) + " MAD", sub: `${d.unallocated_count} ${L("receipts","سند","reçus")}` },
    { label: L("Open invoices","فواتير مفتوحة","Factures ouvertes"), value: fmtMAD(d.outstanding_amount) + " MAD", sub: `${d.outstanding_count} ${L("invoices","فاتورة","factures")}` },
    { label: L("Collected, no invoice","محصّل بلا فاتورة","Encaissé sans facture"), value: fmtMAD(d.collected_no_invoice) + " MAD", sub: L("needs an invoice or write-off","يحتاج فاتورة أو شطب","facture ou perte requise"), color: "#b45309", bd: "#fde68a" },
  ];
});
</script>
