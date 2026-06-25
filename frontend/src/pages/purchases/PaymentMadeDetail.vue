<template>
  <div class="space-y-3.5">
    <button class="inline-flex items-center gap-1.5 text-[12px] font-semibold text-ink-3 hover:text-ink" @click="back">
      <Icon name="arrow" :size="14" class="rotate-180" />{{ L("Back", "رجوع", "Retour") }}
    </button>

    <div v-if="loading" class="bg-white rounded-card border border-line shadow-card"><TableLoading :rows="4" /></div>
    <div v-else-if="!d" class="bg-white rounded-card border border-line shadow-card py-16 text-center text-[12px] text-ink-muted">{{ L("Payment not found.", "الدفعة غير موجودة.", "Introuvable.") }}</div>

    <template v-else>
      <!-- Header -->
      <div class="bg-white rounded-card border border-line shadow-card p-5">
        <div class="flex items-start gap-3 flex-wrap">
          <span class="w-11 h-11 rounded-[12px] grid place-items-center flex-shrink-0" style="background:#ecfdf5"><Icon name="wallet" :size="20" color="#047857" /></span>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="text-[16px] font-bold font-mono">{{ d.name }}</span>
              <span class="text-[10px] font-bold px-2 py-0.5 rounded-full" style="background:#ecfdf5;color:#047857">{{ L("Payment made", "دفعة صادرة", "Paiement émis") }}</span>
              <span v-if="d.status" class="text-[10px] font-bold px-2 py-0.5 rounded-full" style="background:#f1efe8;color:#5f5e5a">{{ d.status }}</span>
            </div>
            <div class="text-[13px] text-ink-2 mt-0.5">{{ d.party }}</div>
            <div class="text-[11px] text-ink-muted mt-0.5">{{ d.date }}<span v-if="d.reference_no"> · {{ L("ref", "مرجع", "réf") }} {{ d.reference_no }}</span></div>
          </div>
          <div class="text-end">
            <div class="text-[24px] font-extrabold tnum">{{ fmt(d.amount) }}<span class="text-[12px] text-ink-muted ms-1">{{ d.currency }}</span></div>
            <div class="text-[11px] text-ink-muted mt-0.5">{{ d.method }}</div>
          </div>
        </div>
        <div class="flex items-center gap-1.5 flex-wrap mt-4 pt-3 border-t border-line-hair text-[11px]">
          <span class="text-ink-muted">{{ L("Paid from", "مدفوع من", "Payé depuis") }}</span>
          <span class="font-semibold text-ink-2">{{ d.paid_from }}</span>
          <span v-if="d.unallocated > 0" class="ms-2 text-[10px] font-bold px-2 py-0.5 rounded-full" style="background:#fffbeb;color:#b45309">{{ L("unallocated", "غير مخصص", "non affecté") }} {{ fmt(d.unallocated) }}</span>
          <button v-if="d.unallocated > 0" @click="openMatch" class="ms-auto inline-flex items-center gap-1.5 h-7 px-3 rounded-chip text-[11px] font-bold text-white bg-accent hover:bg-accent-dark shadow-prim">
            <Icon name="scale" :size="12" color="#fff" />{{ L("Match to bills", "طابق بالفواتير", "Affecter") }}
          </button>
        </div>
      </div>

      <div class="grid lg:grid-cols-3 gap-3.5">
        <!-- Bills settled -->
        <div class="lg:col-span-2 bg-white rounded-card border border-line shadow-card overflow-hidden">
          <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><Icon name="doc" :size="14" color="#0b5c4f" /><span class="text-[12px] font-bold">{{ L("Bills settled", "الفواتير المسدّدة", "Factures réglées") }}</span><span class="text-[10px] text-ink-muted">{{ d.references.length }}</span></div>
          <table v-if="d.references.length" class="w-full text-[12px]">
            <thead><tr style="background:#fafaf9">
              <th class="px-4 py-2 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Bill", "الفاتورة", "Facture") }}</th>
              <th class="px-4 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Total", "الإجمالي", "Total") }}</th>
              <th class="px-4 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Allocated", "المخصّص", "Affecté") }}</th>
            </tr></thead>
            <tbody>
              <tr v-for="r in d.references" :key="r.name" class="border-t border-line-hair hover:bg-app-warm/60 cursor-pointer" @click="openBill(r)">
                <td class="px-4 py-2.5 font-mono font-semibold">{{ r.name }}</td>
                <td class="px-4 py-2.5 text-end tnum text-ink-3">{{ fmt(r.total) }}</td>
                <td class="px-4 py-2.5 text-end tnum font-semibold">{{ fmt(r.allocated) }}</td>
              </tr>
            </tbody>
          </table>
          <div v-else class="py-8 text-center text-[11px] text-ink-muted">{{ L("On-account payment — no bills allocated.", "دفعة على الحساب — بدون فواتير.", "Paiement sur compte — aucune facture.") }}</div>
        </div>

        <!-- GL -->
        <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
          <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><Icon name="ledger" :size="14" color="#0b5c4f" /><span class="text-[12px] font-bold">{{ L("Journal impact", "الأثر المحاسبي", "Impact GL") }}</span></div>
          <table v-if="d.gl.length" class="w-full text-[12px]">
            <thead><tr style="background:#fafaf9"><th class="px-3 py-2 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Account", "الحساب", "Compte") }}</th><th class="px-3 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Dr", "مدين", "D") }}</th><th class="px-3 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Cr", "دائن", "C") }}</th></tr></thead>
            <tbody>
              <tr v-for="(g, i) in d.gl" :key="i" class="border-t border-line-hair">
                <td class="px-3 py-2"><div class="truncate max-w-[150px]">{{ g.name }}</div></td>
                <td class="px-3 py-2 text-end tnum" :class="g.dr ? 'font-semibold' : 'text-ink-muted'">{{ g.dr ? fmt(g.dr) : "—" }}</td>
                <td class="px-3 py-2 text-end tnum" :class="g.cr ? 'font-semibold' : 'text-ink-muted'">{{ g.cr ? fmt(g.cr) : "—" }}</td>
              </tr>
            </tbody>
          </table>
          <div v-else class="py-8 text-center text-[11px] text-ink-muted">{{ L("No journal.", "لا قيد.", "Aucune écriture.") }}</div>
        </div>
      </div>

      <DocHub v-if="route.query.id" :doctype="DOCTYPE" :name="route.query.id" class="mt-1" />
    </template>

    <!-- Advance matching modal -->
    <div v-if="matchOpen" class="fixed inset-0 z-50 grid place-items-center bg-black/30 p-4" @click.self="matchOpen = false">
      <div class="bg-white rounded-card shadow-xl w-full max-w-lg p-5 space-y-3.5 max-h-[85vh] flex flex-col">
        <div class="flex items-center gap-2 flex-shrink-0">
          <span class="w-8 h-8 rounded-[9px] grid place-items-center" style="background:#ecfdf5"><Icon name="scale" :size="16" color="#0b5c4f" /></span>
          <div>
            <div class="text-[14px] font-bold">{{ L("Match advance to bills", "طابق المقدّم بالفواتير", "Affecter l'avance") }}</div>
            <div class="text-[11px] text-ink-muted">{{ match.party_name }} · {{ L("available", "متاح", "dispo") }} <b class="text-accent-dark">{{ fmt(remaining) }} {{ match.currency }}</b></div>
          </div>
        </div>
        <div v-if="matchLoading" class="py-6"><TableLoading :rows="4" /></div>
        <div v-else-if="!match.bills.length" class="py-8 text-center text-[12px] text-ink-muted">{{ L("No open bills for this supplier.", "لا فواتير مفتوحة لهذا المورّد.", "Aucune facture ouverte.") }}</div>
        <div v-else class="overflow-y-auto -mx-1 px-1 flex-1">
          <div v-for="b in match.bills" :key="b.name" class="flex items-center gap-2.5 px-2.5 py-2 rounded-[10px] border mb-1.5 cursor-pointer" :class="picked.has(b.name) ? 'border-accent/40 bg-accent/5' : 'border-line-2 hover:bg-app-warm/50'" @click="togglePick(b)">
            <input type="checkbox" :checked="picked.has(b.name)" class="accent-accent w-3.5 h-3.5" @click.stop="togglePick(b)" />
            <div class="flex-1 min-w-0">
              <div class="text-[12px] font-mono font-semibold">{{ b.name }}</div>
              <div class="text-[10.5px] text-ink-muted">{{ b.date }}<span v-if="b.due_date"> · {{ L("due", "استحقاق", "éch.") }} {{ b.due_date }}</span></div>
            </div>
            <span class="tnum font-bold text-[12px] text-sale">{{ fmt(b.outstanding) }}</span>
          </div>
        </div>
        <div class="flex items-center justify-between pt-1 border-t border-line-hair flex-shrink-0">
          <div class="text-[11px]"><span class="text-ink-muted">{{ L("Selected", "محدد", "Sél.") }}</span> <b class="tnum">{{ fmt(pickedTotal) }}</b> / {{ fmt(match.unallocated) }} {{ match.currency }}</div>
          <div class="flex gap-2">
            <button @click="matchOpen = false" class="h-9 px-3 rounded-[9px] text-[12px] font-semibold text-ink-3 hover:bg-app-warm">{{ L("Cancel", "إلغاء", "Annuler") }}</button>
            <button @click="confirmMatch" :disabled="posting || !picked.size" class="h-9 px-4 rounded-[9px] text-[12px] font-bold text-white disabled:opacity-50 bg-accent">{{ posting ? L("Applying…", "جارٍ…", "…") : L("Apply", "طبّق", "Affecter") }}</button>
          </div>
        </div>
        <p class="text-[10px] text-ink-muted flex-shrink-0">{{ L("Allocates oldest-due first; over-selection is fine (only the available amount is applied).", "يُخصّص للأقدم استحقاقًا أولًا.", "Affecte au plus ancien d'abord.") }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import DocHub from "@/components/DocHub.vue";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useToast } from "@/composables/useToast";

const route = useRoute();
const router = useRouter();
const { locale } = useI18n();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const DOCTYPE = "Payment Entry";
const fmt = (n) => Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const d = ref(null);
const loading = ref(true);

// ── Advance matching ──
const matchOpen = ref(false);
const matchLoading = ref(false);
const posting = ref(false);
const match = ref({ party_name: "", unallocated: 0, currency: "MAD", bills: [] });
const picked = ref(new Set());
const pickedTotal = computed(() => match.value.bills.filter((b) => picked.value.has(b.name)).reduce((a, b) => a + Number(b.outstanding || 0), 0));
const remaining = computed(() => Math.max(0, Number(match.value.unallocated || 0) - pickedTotal.value));
function togglePick(b) { const s = new Set(picked.value); s.has(b.name) ? s.delete(b.name) : s.add(b.name); picked.value = s; }
async function openMatch() {
  matchOpen.value = true; matchLoading.value = true; picked.value = new Set();
  try { match.value = await api.call("accounting_portal.api.purchases.advance_match_options", { company: currentCompany(), payment: d.value.name }); }
  catch { match.value = { party_name: "", unallocated: 0, currency: "MAD", bills: [] }; }
  finally { matchLoading.value = false; }
}
async function confirmMatch() {
  posting.value = true;
  try {
    const res = await api.call("accounting_portal.api.purchases.apply_advance", { company: currentCompany(), payment: d.value.name, invoices: [...picked.value] });
    matchOpen.value = false;
    if (res && res.status === "Proposed") toast.info(L("Sent for approval", "أُرسل للموافقة", "Envoyé pour approbation"));
    else { toast.success(L("Advance applied", "تم تطبيق المقدّم", "Avance affectée")); load(); }
  } catch (e) { toast.error(String((e && e.message) || L("Failed", "فشل", "Échec")).slice(0, 160)); }
  finally { posting.value = false; }
}

function back() { router.push("/accounting/purchases/payments"); }
function openBill(r) {
  if (r.doctype === "Purchase Invoice") router.push({ path: "/accounting/purchases/topay", query: { id: r.name } });
}

async function load() {
  const id = route.query.id;
  if (!id) { loading.value = false; return; }
  loading.value = true; d.value = null;
  try { d.value = await api.call("accounting_portal.api.payments.get_receipt", { name: id, company: currentCompany() }); }
  catch { d.value = null; }
  finally { loading.value = false; }
  if (!d.value) router.replace({ path: "/accounting/purchases/payments", query: {} });
}
watch(() => route.query.id, load, { immediate: true });
</script>
