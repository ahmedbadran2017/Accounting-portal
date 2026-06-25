<template>
  <div class="space-y-3.5">
    <button class="inline-flex items-center gap-1.5 text-[12px] font-semibold text-ink-3 hover:text-ink" @click="back">
      <Icon name="arrow" :size="14" class="rotate-180" />{{ L("Payments received","المدفوعات المُحصّلة","Encaissements") }}
    </button>

    <div v-if="loading" class="bg-white rounded-card border border-line shadow-card"><TableLoading :rows="4" /></div>
    <div v-else-if="!d" class="bg-white rounded-card border border-line shadow-card py-16 text-center text-[12px] text-ink-muted">{{ L("Payment not found.","الدفعة غير موجودة.","Introuvable.") }}</div>

    <template v-else>
      <!-- Header -->
      <div class="bg-white rounded-card border border-line shadow-card p-5">
        <div class="flex items-start gap-3 flex-wrap">
          <span class="w-11 h-11 rounded-[12px] grid place-items-center flex-shrink-0" style="background:#e1f5ee"><Icon name="coins" :size="20" color="#0f766e" /></span>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="text-[16px] font-bold font-mono">{{ d.name }}</span>
              <span class="text-[10px] font-bold px-2 py-0.5 rounded-full" :style="statusStyle(d.status)">{{ d.status }}</span>
              <span v-if="/cath/i.test(d.method)" class="text-[10px] font-bold px-2 py-0.5 rounded-full inline-flex items-center gap-1" style="background:#f5f3ff;color:#6d28d9"><Icon name="truck" :size="11" />{{ d.method }}</span>
            </div>
            <div class="text-[13px] text-ink-2 mt-0.5">{{ d.party }}</div>
            <div class="text-[11px] text-ink-muted mt-0.5">{{ d.date }}<span v-if="d.reference_no"> · {{ L("ref","مرجع","réf") }} {{ d.reference_no }}</span></div>
          </div>
          <div class="text-end">
            <div class="text-[24px] font-extrabold tnum" style="color:#0f766e">{{ fmt(d.amount) }}</div>
            <div class="text-[11px] text-ink-muted">{{ d.currency }} {{ L("received","محصّل","reçu") }}</div>
          </div>
        </div>
      </div>

      <div class="grid lg:grid-cols-2 gap-3.5">
        <!-- Allocation -->
        <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
          <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2">
            <Icon name="layers" :size="14" color="#0b5c4f" /><span class="text-[12px] font-bold">{{ L("Allocated to","مخصّص لـ","Affecté à") }}</span>
            <span class="text-[10px] text-ink-muted">{{ d.references.length }}</span>
          </div>
          <table class="w-full text-[12px]">
            <tbody>
              <tr v-for="(r, i) in d.references" :key="i" class="border-t border-line-hair hover:bg-app-warm/60 cursor-pointer" @click="openRef(r)">
                <td class="px-4 py-2.5">
                  <div class="font-mono font-semibold">{{ r.name }}</div>
                  <div class="text-[10px] text-ink-muted">{{ r.doctype }}</div>
                </td>
                <td class="px-4 py-2.5 text-end tnum font-bold whitespace-nowrap">{{ fmt(r.allocated) }}</td>
              </tr>
              <tr v-if="!d.references.length"><td class="px-4 py-5 text-center text-ink-muted" colspan="2">{{ L("Unallocated","غير مخصّص","Non affecté") }}</td></tr>
            </tbody>
          </table>
          <div v-if="d.orders.length" class="px-4 py-2.5 border-t border-line-hair flex items-center gap-2 flex-wrap">
            <span class="text-[10.5px] text-ink-muted font-semibold uppercase tracking-wider">{{ L("Orders","الطلبات","Cmds") }}</span>
            <button v-for="o in d.orders" :key="o" class="font-mono text-[11px] font-semibold text-accent-dark hover:underline" @click="openOrder(o)">{{ o }}</button>
          </div>
        </div>

        <!-- GL impact -->
        <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
          <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2">
            <Icon name="ledger" :size="14" color="#0b5c4f" /><span class="text-[12px] font-bold">{{ L("Journal impact","الأثر المحاسبي","Impact GL") }}</span>
          </div>
          <table class="w-full text-[12px]">
            <thead><tr style="background:#fafaf9">
              <th class="px-4 py-2 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Account","الحساب","Compte") }}</th>
              <th class="px-4 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Debit","مدين","Débit") }}</th>
              <th class="px-4 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Credit","دائن","Crédit") }}</th>
            </tr></thead>
            <tbody>
              <tr v-for="(g, i) in d.gl" :key="i" class="border-t border-line-hair">
                <td class="px-4 py-2.5"><div class="truncate max-w-[200px]">{{ g.name }}</div><div class="text-[10px] text-ink-muted font-mono">{{ g.account }}</div></td>
                <td class="px-4 py-2.5 text-end tnum" :class="g.dr ? 'font-semibold' : 'text-ink-muted'">{{ g.dr ? fmt(g.dr) : "—" }}</td>
                <td class="px-4 py-2.5 text-end tnum" :class="g.cr ? 'font-semibold' : 'text-ink-muted'">{{ g.cr ? fmt(g.cr) : "—" }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <DocHub v-if="route.query.id" :doctype="DOCTYPE" :name="route.query.id" class="mt-1" />
    </template>
  </div>
</template>

<script setup>
import { ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import DocHub from "@/components/DocHub.vue";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";

const route = useRoute();
const router = useRouter();
const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const DOCTYPE = "Payment Entry";
const fmt = (n) => Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
function statusStyle(s) {
  if (s === "Submitted") return "background:#ecfdf5;color:#047857";
  if (s === "Cancelled") return "background:#fef2f2;color:#b91c1c";
  return "background:#f1efe8;color:#5f5e5a";
}

const d = ref(null);
const loading = ref(true);

function back() { router.push("/accounting/sales/payments"); }
function openRef(r) {
  if (r.doctype === "Sales Invoice") router.push({ path: "/accounting/sales/invoices", query: { id: r.name } });
  else if (r.doctype === "Sales Order") router.push({ path: "/accounting/sales/orders", query: { id: r.name } });
}
function openOrder(o) { router.push({ path: "/accounting/sales/orders", query: { id: o } }); }

watch(() => route.query.id, async (id) => {
  if (!id) return;
  loading.value = true; d.value = null;
  try { d.value = await api.call("accounting_portal.api.payments.get_receipt", { name: id, company: currentCompany() }); }
  catch { d.value = null; }
  finally { loading.value = false; }
}, { immediate: true });
</script>
