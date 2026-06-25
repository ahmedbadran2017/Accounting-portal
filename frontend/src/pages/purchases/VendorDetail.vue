<template>
  <div v-if="d" class="max-w-[1080px] mx-auto space-y-3.5">
    <div class="flex items-center gap-2">
      <button class="inline-flex items-center gap-1.5 text-[12px] font-medium text-ink-3 hover:text-ink" @click="back">
        <span class="rtl:rotate-180"><Icon name="arrow" :size="15" /></span>{{ L("Back to suppliers","العودة للموردين","Retour aux fournisseurs") }}
      </button>
      <button class="ms-auto inline-flex items-center gap-1.5 text-[12px] font-semibold text-ink-2 bg-white border border-line-2 px-3 py-1.5 rounded-chip hover:bg-app-warm" @click="showStatement = true">
        <Icon name="ledger" :size="14" />{{ L("Statement","كشف حساب","Relevé") }}
      </button>
      <button class="inline-flex items-center gap-1.5 text-[12px] font-semibold text-ink-2 bg-white border border-line-2 px-3 py-1.5 rounded-chip hover:bg-app-warm" @click="openEdit">
        <Icon name="gear" :size="14" />{{ L("Edit","تعديل","Modifier") }}
      </button>
    </div>
    <PartyStatement :open="showStatement" party-type="Supplier" :party="d.name" :party-name="d.supplier_name" @close="showStatement = false" />

    <!-- Header -->
    <div class="bg-white rounded-[16px] border border-line px-5 py-[18px] shadow-card">
      <div class="flex items-center gap-3.5 flex-wrap">
        <span class="w-12 h-12 rounded-[12px] grid place-items-center text-white text-[15px] font-bold flex-shrink-0" :style="{ background: badge }">{{ ini(d.supplier_name) }}</span>
        <div class="flex-1 min-w-[180px]">
          <div class="text-[18px] font-bold">{{ d.supplier_name }}</div>
          <div class="text-[12px] text-ink-3 mt-0.5">
            <span v-if="d.group">{{ d.group }}</span><span v-if="d.type"> · {{ d.type }}</span><span v-if="d.country"> · {{ d.country }}</span> · {{ L("since","منذ","depuis") }} {{ d.since }}
          </div>
        </div>
        <div class="text-end">
          <div class="text-[10.5px] text-ink-muted font-semibold">{{ L("Outstanding payable","المستحق","Dû") }}</div>
          <div class="text-[20px] font-bold tnum" :class="d.payable < 0 ? 'text-success-dark' : 'text-sale'">{{ fmt(d.payable) }} <span class="text-[11px] text-ink-muted">{{ d.currency }}</span></div>
        </div>
      </div>
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-2.5 mt-[15px]">
        <div v-for="s in statCards" :key="s.label" class="rounded-[11px] px-[13px] py-[11px]" style="background:#fafaf9;border:1px solid #f0efed">
          <div class="text-[10.5px] text-ink-muted font-semibold">{{ s.label }}</div>
          <div class="text-[18px] font-bold tnum mt-[3px]">{{ s.value }}</div>
        </div>
      </div>
    </div>

    <!-- Connections -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-2.5">
      <button v-for="cn in connections" :key="cn.label" class="yo-card bg-white border border-line rounded-[12px] p-3.5 shadow-card text-start" @click="go(cn.sub)">
        <div class="flex items-center justify-between">
          <span class="text-[10.5px] text-ink-muted font-semibold">{{ cn.label }}</span>
          <Icon name="chevDown" :size="14" color="#cbb5ad" class="-rotate-90 rtl:rotate-90" />
        </div>
        <div class="text-[20px] font-bold tnum mt-[3px]">{{ cn.value }}</div>
      </button>
    </div>

    <!-- Supplier ledger -->
    <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
      <div class="px-4 py-3 border-b border-line-hair text-[13px] font-bold">{{ L("Supplier ledger","كشف حساب المورّد","Grand livre fournisseur") }}</div>
      <div class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead>
            <tr style="background:#fafaf9">
              <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Date","التاريخ","Date") }}</th>
              <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Document","المستند","Document") }}</th>
              <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Type","النوع","Type") }}</th>
              <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Debit","مدين","Débit") }}</th>
              <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Credit","دائن","Crédit") }}</th>
              <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Balance","الرصيد","Solde") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(l, i) in ledger" :key="i" class="border-t border-line-hair" :class="l.go ? 'hover:bg-app-warm/70 cursor-pointer' : ''" @click="openVoucher(l)">
              <td class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ l.date }}</td>
              <td class="px-4 py-2.5 font-mono font-semibold whitespace-nowrap" :class="l.go ? 'text-accent-dark' : ''">{{ l.doc }}<Icon v-if="l.go" name="arrow" :size="11" class="inline ms-1 -mt-0.5 rtl:rotate-180" /></td>
              <td class="px-4 py-2.5 text-ink-3">{{ l.type }}</td>
              <td class="px-4 py-2.5 text-end tnum text-success-dark">{{ l.dr || "—" }}</td>
              <td class="px-4 py-2.5 text-end tnum text-sale">{{ l.cr || "—" }}</td>
              <td class="px-4 py-2.5 text-end tnum font-bold">{{ l.bal }}</td>
            </tr>
            <tr v-if="!ledger.length"><td colspan="6" class="px-4 py-8 text-center text-ink-muted text-[12px]">{{ L("No ledger entries.","لا قيود.","Aucune écriture.") }}</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <DocHub v-if="route.query.id" :doctype="DOCTYPE" :name="route.query.id" class="mt-1" />

    <!-- Edit modal -->
    <div v-if="editOpen" class="fixed inset-0 z-50 grid place-items-center bg-black/30 p-4" @click.self="editOpen = false">
      <div class="bg-white rounded-card shadow-xl w-full max-w-sm p-5 space-y-3">
        <div class="text-[14px] font-bold">{{ L("Edit supplier","تعديل المورّد","Modifier le fournisseur") }}</div>
        <div><label class="text-[11px] font-bold text-ink-3">{{ L("Name","الاسم","Nom") }}</label><input v-model.trim="ef.supplier_name" class="w-full h-9 mt-1 border border-line-2 rounded-[9px] px-2 text-[12.5px] focus:outline-none focus:border-accent/40" /></div>
        <div><label class="text-[11px] font-bold text-ink-3">{{ L("Group","المجموعة","Groupe") }}</label>
          <select v-model="ef.supplier_group" class="w-full h-9 mt-1 border border-line-2 rounded-[9px] px-2 text-[12.5px] bg-white focus:outline-none focus:border-accent/40"><option v-for="g in groups" :key="g" :value="g">{{ g }}</option></select></div>
        <div class="grid grid-cols-2 gap-2">
          <div><label class="text-[11px] font-bold text-ink-3">{{ L("Tax ID","الرقم الضريبي","ID fiscal") }}</label><input v-model.trim="ef.tax_id" class="w-full h-9 mt-1 border border-line-2 rounded-[9px] px-2 text-[12.5px] focus:outline-none focus:border-accent/40" /></div>
          <div><label class="text-[11px] font-bold text-ink-3">{{ L("Currency","العملة","Devise") }}</label><input v-model.trim="ef.currency" class="w-full h-9 mt-1 border border-line-2 rounded-[9px] px-2 text-[12.5px] focus:outline-none focus:border-accent/40" placeholder="MAD" /></div>
        </div>
        <div class="flex gap-2 justify-end pt-1">
          <button @click="editOpen = false" class="h-9 px-3 rounded-[9px] text-[12px] font-semibold text-ink-3 hover:bg-app-warm">{{ L("Cancel","إلغاء","Annuler") }}</button>
          <button @click="saveEdit" :disabled="saving" class="h-9 px-4 rounded-[9px] text-[12px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand disabled:opacity-50">{{ saving ? L("Saving…","حفظ…","…") : L("Save","حفظ","Enregistrer") }}</button>
        </div>
      </div>
    </div>
  </div>
  <div v-else-if="loading" class="py-20 text-center text-[12px] text-ink-muted">{{ t("common.loading") }}</div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import DocHub from "@/components/DocHub.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useToast } from "@/composables/useToast";
import PartyStatement from "@/components/PartyStatement.vue";

const showStatement = ref(false);
const toast = useToast();
const { t, locale } = useI18n();
const route = useRoute();
const router = useRouter();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const DOCTYPE = "Supplier";
const fmt = (n) => Number(n || 0).toLocaleString("en-US");
const ini = (n) => String(n || "?").trim().split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
const badge = "linear-gradient(135deg,#b45309,#7c2d12)";

const d = ref(null);
const loading = ref(true);
async function load() {
  const id = route.query.id;
  if (!id) { d.value = null; loading.value = false; return; }
  loading.value = true;
  try { d.value = await api.call("accounting_portal.api.purchases.get_supplier", { name: id, company: currentCompany() }); }
  catch { d.value = null; }
  finally { loading.value = false; }
  if (id && !d.value) router.replace("/accounting/purchases/vendors");
}
watch(() => [route.query.id, locale.value], load, { immediate: true });

const statCards = computed(() => {
  const s = d.value?.stats || {};
  return [
    { label: L("Total billed", "إجمالي الفواتير", "Total facturé"), value: fmt(s.billed) },
    { label: L("Outstanding", "المتبقّي", "Restant"), value: fmt(s.outstanding) },
    { label: L("Bills", "الفواتير", "Factures"), value: String(s.n_bills || 0) },
    { label: L("Payable", "المستحق", "Dû"), value: fmt(s.payable) },
  ];
});
const connections = computed(() => {
  const c = d.value?.connections || {};
  return [
    { label: L("Bills", "الفواتير", "Factures"), value: String(c.bills || 0), sub: "bills" },
    { label: L("Purchase orders", "أوامر الشراء", "Bons de commande"), value: String(c.pos || 0), sub: "pos" },
    { label: L("Goods receipts", "سندات الاستلام", "Réceptions"), value: String(c.receipts || 0), sub: "received" },
    { label: L("Payments", "المدفوعات", "Paiements"), value: String(c.payments || 0), sub: "payments" },
  ];
});
const ledger = computed(() => (d.value?.ledger || []).map((e) => ({
  date: e.date, doc: e.doc, type: e.type,
  dr: e.dr ? Number(e.dr).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "",
  cr: e.cr ? Number(e.cr).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "",
  bal: e.balance != null ? Number(e.balance).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "",
  go: e.type === "Purchase Invoice" ? { path: "/accounting/purchases/bills", query: { id: e.doc } } : null,
})));

function go(sub) { router.push(`/accounting/purchases/${sub}`); }
function openVoucher(l) { if (l.go) router.push(l.go); }
function back() { router.push({ path: "/accounting/purchases/vendors" }); }

// ── Edit ──
const editOpen = ref(false);
const saving = ref(false);
const groups = ref([]);
const ef = ref({ supplier_name: "", supplier_group: "", tax_id: "", currency: "" });
async function openEdit() {
  ef.value = { supplier_name: d.value.supplier_name, supplier_group: d.value.group || "", tax_id: d.value.tax_id || "", currency: d.value.currency === "—" ? "" : d.value.currency };
  editOpen.value = true;
  if (!groups.value.length) { try { groups.value = await api.call("accounting_portal.api.purchases.supplier_groups", {}); } catch { groups.value = []; } }
  if (ef.value.supplier_group && !groups.value.includes(ef.value.supplier_group)) groups.value.unshift(ef.value.supplier_group);
}
async function saveEdit() {
  saving.value = true;
  try {
    await api.call("accounting_portal.api.purchases.update_supplier", { name: d.value.name, supplier_name: ef.value.supplier_name, supplier_group: ef.value.supplier_group, tax_id: ef.value.tax_id, currency: ef.value.currency });
    editOpen.value = false; toast.success(L("Saved", "تم الحفظ", "Enregistré")); load();
  } catch (e) { toast.error(String((e && e.message) || L("Save failed", "فشل", "Échec")).slice(0, 140)); }
  finally { saving.value = false; }
}
</script>
