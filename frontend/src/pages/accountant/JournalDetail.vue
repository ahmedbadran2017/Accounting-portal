<template>
  <div class="space-y-3.5">
    <button class="inline-flex items-center gap-1.5 text-[12px] font-semibold text-ink-3 hover:text-ink" @click="back">
      <Icon name="arrow" :size="14" class="rotate-180" />{{ L("Back", "رجوع", "Retour") }}
    </button>

    <div v-if="loading" class="bg-white rounded-card border border-line shadow-card"><TableLoading :rows="4" /></div>
    <div v-else-if="!j" class="bg-white rounded-card border border-line shadow-card py-16 text-center text-[12px] text-ink-muted">{{ L("Journal not found.", "القيد غير موجود.", "Introuvable.") }}</div>

    <template v-else>
      <!-- Header -->
      <div class="bg-white rounded-card border border-line shadow-card p-5">
        <div class="flex items-start gap-3 flex-wrap">
          <span class="w-11 h-11 rounded-[12px] grid place-items-center flex-shrink-0" style="background:#faf6f4"><Icon name="ledger" :size="20" color="#0b5c4f" /></span>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="text-[16px] font-bold font-mono">{{ j.name }}</span>
              <span class="text-[10px] font-bold px-2 py-0.5 rounded-full" style="background:#faf6f4;color:#0b5c4f">{{ j.voucher_type }}</span>
              <span v-if="j.status" class="text-[10px] font-bold px-2 py-0.5 rounded-full" :style="j.status === 'Cancelled' ? 'background:#fef2f2;color:#be123c' : j.status === 'Draft' ? 'background:#fffbeb;color:#b45309' : 'background:#ecfdf5;color:#047857'">{{ j.status }}</span>
              <span v-if="j.clearance_date" class="text-[10px] font-bold px-2 py-0.5 rounded-full" style="background:#eff6ff;color:#0369a1">{{ L("reconciled", "مُسوّى", "rapproché") }} {{ j.clearance_date }}</span>
            </div>
            <div class="text-[12px] text-ink-2 mt-0.5 truncate max-w-[460px]">{{ j.user_remark || "—" }}</div>
            <div class="text-[11px] text-ink-muted mt-0.5">{{ j.posting_date }}<span v-if="j.cheque_no"> · {{ L("ref", "مرجع", "réf") }} {{ j.cheque_no }}</span></div>
          </div>
          <div class="text-end">
            <div class="text-[24px] font-extrabold tnum">{{ fmt(j.total_debit) }}<span class="text-[12px] text-ink-muted ms-1">MAD</span></div>
            <div class="text-[10.5px] text-ink-muted">{{ L("total", "الإجمالي", "total") }}</div>
          </div>
        </div>
      </div>

      <!-- Account lines -->
      <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
        <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><Icon name="list" :size="14" color="#0b5c4f" /><span class="text-[12px] font-bold">{{ L("Entries", "البنود", "Lignes") }}</span><span class="text-[10px] text-ink-muted">{{ j.accounts.length }}</span></div>
        <div class="overflow-x-auto">
          <table class="w-full text-[12px]">
            <thead><tr style="background:#fafaf9">
              <th class="px-4 py-2 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Account", "الحساب", "Compte") }}</th>
              <th class="px-4 py-2 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Party", "الطرف", "Tiers") }}</th>
              <th class="px-4 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Debit", "مدين", "Débit") }}</th>
              <th class="px-4 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Credit", "دائن", "Crédit") }}</th>
            </tr></thead>
            <tbody>
              <tr v-for="(a, i) in j.accounts" :key="i" class="border-t border-line-hair hover:bg-app-warm/50">
                <td class="px-4 py-2.5"><div class="font-medium truncate max-w-[280px]">{{ a.account_name }}</div><div v-if="a.reference_name" class="text-[10px] text-ink-muted font-mono">{{ a.reference_name }}</div></td>
                <td class="px-4 py-2.5 text-ink-3 truncate max-w-[160px]">{{ a.party || "—" }}</td>
                <td class="px-4 py-2.5 text-end tnum" :class="a.debit ? 'font-semibold' : 'text-ink-muted'">{{ a.debit ? fmt(a.debit) : "—" }}</td>
                <td class="px-4 py-2.5 text-end tnum" :class="a.credit ? 'font-semibold' : 'text-ink-muted'">{{ a.credit ? fmt(a.credit) : "—" }}</td>
              </tr>
            </tbody>
            <tfoot>
              <tr class="border-t-2 border-line-2 font-bold" style="background:#fafaf9">
                <td class="px-4 py-2.5" colspan="2">{{ L("Total", "الإجمالي", "Total") }}</td>
                <td class="px-4 py-2.5 text-end tnum">{{ fmt(totalDr) }}</td>
                <td class="px-4 py-2.5 text-end tnum">{{ fmt(totalCr) }}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      <DocHub v-if="route.query.id" :doctype="DOCTYPE" :name="route.query.id" class="mt-1" />
    </template>
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

const route = useRoute();
const router = useRouter();
const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const DOCTYPE = "Journal Entry";
const fmt = (n) => Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const j = ref(null);
const loading = ref(true);
const totalDr = computed(() => (j.value?.accounts || []).reduce((a, r) => a + Number(r.debit || 0), 0));
const totalCr = computed(() => (j.value?.accounts || []).reduce((a, r) => a + Number(r.credit || 0), 0));

function back() { router.push("/accounting/accountant/journals"); }
async function load() {
  const id = route.query.id;
  if (!id) { loading.value = false; return; }
  loading.value = true; j.value = null;
  try { j.value = await api.call("accounting_portal.api.accountant.get_journal", { name: id, company: currentCompany() }); }
  catch { j.value = null; }
  finally { loading.value = false; }
  if (!j.value) router.replace({ path: "/accounting/accountant/journals", query: {} });
}
watch(() => route.query.id, load, { immediate: true });
</script>
