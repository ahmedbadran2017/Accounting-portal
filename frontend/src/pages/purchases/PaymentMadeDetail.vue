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
    </template>
  </div>
</template>

<script setup>
import { ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";

const route = useRoute();
const router = useRouter();
const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const d = ref(null);
const loading = ref(true);

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
