<template>
  <div v-if="b" class="space-y-3.5">
    <button class="inline-flex items-center gap-1.5 text-[12px] font-medium text-ink-3 hover:text-ink" @click="back">
      <span class="rtl:rotate-180"><Icon name="arrow" :size="15" /></span>{{ L("Back to bills","العودة للفواتير","Retour aux factures") }}
    </button>

    <div class="bg-white rounded-card border border-line p-5">
      <div class="flex flex-wrap items-start gap-3">
        <div class="min-w-0">
          <div class="text-[17px] font-bold tracking-tight font-mono">{{ b.id }}</div>
          <div class="text-[12.5px] text-ink-3">{{ b.vendor }}<span v-if="b.date"> · {{ b.date }}</span><span v-if="b.bill_no" class="text-ink-muted"> · {{ b.bill_no }}</span></div>
        </div>
        <div class="ms-auto text-end">
          <div class="text-[22px] font-bold tnum" :class="b.amount.includes('-') ? 'text-sale' : ''">{{ b.amount }}</div>
          <span class="inline-block text-[10px] font-bold px-2 py-0.5 rounded-badge border mt-1"
                :style="{ background: BILL_STATUS[b.status].bg, color: BILL_STATUS[b.status].fg, borderColor: BILL_STATUS[b.status].bd }">
            {{ billStatusLabel(b.status, locale) }}
          </span>
        </div>
      </div>
      <div v-if="b.status !== 'ret'" class="flex justify-end mt-3 pt-3 border-t border-line-hair">
        <button class="inline-flex items-center gap-1.5 text-[11.5px] font-semibold text-sale border border-sale/30 bg-sale/5 hover:bg-sale/10 px-3 py-1.5 rounded-chip disabled:opacity-50" :disabled="busy" @click="confirmDebit = true">
          <Icon name="refresh" :size="13" />{{ L("Debit note / return","إشعار مدين / مرتجع","Note de débit") }}
        </button>
      </div>
    </div>

    <div v-if="confirmDebit" class="fixed inset-0 z-50 grid place-items-center bg-ink/30 px-4" @click.self="confirmDebit = false">
      <div class="bg-white rounded-card shadow-pop w-full max-w-sm p-5">
        <div class="text-[14px] font-bold">{{ L("Create a debit note?","إنشاء إشعار مدين؟","Créer une note de débit ?") }}</div>
        <div class="text-[12px] text-ink-3 mt-1.5">{{ L("Posts a return against this bill (reverses it / claws back the payable). Amounts over 10,000 need approval.","يسجّل مرتجعًا مقابل هذه الفاتورة. ما فوق 10٬000 يحتاج موافقة.","Enregistre un retour sur cette facture.") }}</div>
        <div class="flex justify-end gap-2 mt-4">
          <button class="px-3.5 py-2 rounded-chip text-[12px] font-semibold text-ink-2 hover:bg-app-warm" @click="confirmDebit = false">{{ L("Cancel","إلغاء","Annuler") }}</button>
          <button class="px-4 py-2 rounded-chip text-[12px] font-bold text-white bg-sale disabled:opacity-50" :disabled="busy" @click="makeDebit">{{ busy ? L("Working…","جارٍ…","…") : L("Create","إنشاء","Créer") }}</button>
        </div>
      </div>
    </div>

    <!-- 3-way match panel -->
    <div class="bg-white rounded-card border border-line p-4">
      <div class="text-[13px] font-bold mb-3">{{ L("3-way match","المطابقة الثلاثية","Rapprochement 3 voies") }}</div>
      <div class="grid grid-cols-3 gap-2.5">
        <div v-for="leg in legs" :key="leg.key" class="rounded-card border p-3 text-center"
             :style="{ borderColor: leg.ok ? '#a7f3d0' : '#fecaca', background: leg.ok ? '#ecfdf5' : '#fef2f2' }">
          <Icon :name="leg.ok ? 'check' : 'alert'" :size="18" :color="leg.ok ? '#047857' : '#be123c'" />
          <div class="text-[11.5px] font-semibold mt-1.5">{{ leg.label }}</div>
          <div class="text-[10px] mt-0.5" :style="{ color: leg.ok ? '#047857' : '#be123c' }">{{ leg.state }}</div>
        </div>
      </div>
      <div class="mt-3 pt-2.5 border-t border-line text-[11px]" :class="matched ? 'text-success-dark' : 'text-sale'">
        {{ matched
          ? L("PO, Goods Receipt and Invoice agree — cleared to pay.","أمر الشراء وسند الاستلام والفاتورة متطابقة — جاهزة للدفع.","BC, réception et facture concordent — bon à payer.")
          : L("Quantity / price mismatch vs PO + Goods Receipt — held for review.","فرق كمية/سعر مقابل أمر الشراء والاستلام — موقوفة للمراجعة.","Écart quantité/prix vs BC + réception — en attente.") }}
      </div>
    </div>

    <!-- Line items -->
    <div v-if="items.length" class="bg-white rounded-card border border-line overflow-hidden">
      <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><Icon name="box" :size="14" color="#b45309" /><span class="text-[12.5px] font-bold">{{ L("Items","الأصناف","Articles") }}</span><span class="text-[10px] text-ink-muted">{{ items.length }}</span></div>
      <div class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead><tr style="background:#fafaf9">
            <th class="px-4 py-2 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Item","الصنف","Article") }}</th>
            <th class="px-4 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Qty","الكمية","Qté") }}</th>
            <th class="px-4 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Rate","السعر","Prix") }}</th>
            <th class="px-4 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Amount","المبلغ","Montant") }}</th>
          </tr></thead>
          <tbody>
            <tr v-for="(it, i) in items" :key="i" class="border-t border-line-hair">
              <td class="px-4 py-2.5">
                <span class="flex items-center gap-2.5">
                  <img v-if="it.image" :src="it.image" class="w-8 h-8 rounded-[7px] object-cover flex-shrink-0 border border-line-hair" />
                  <span v-else class="w-8 h-8 rounded-[7px] bg-app-warm grid place-items-center flex-shrink-0"><Icon name="box" :size="13" color="#a8a29e" /></span>
                  <span class="min-w-0"><span class="block font-medium truncate max-w-[300px]">{{ it.name }}</span><span v-if="it.sku || it.code" class="block text-[10px] text-ink-muted font-mono">{{ it.sku || it.code }}</span></span>
                </span>
              </td>
              <td class="px-4 py-2.5 text-end tnum">{{ it.qty }}</td>
              <td class="px-4 py-2.5 text-end tnum">{{ it.rate }}</td>
              <td class="px-4 py-2.5 text-end tnum font-semibold">{{ it.amount }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Related documents -->
    <div class="bg-white rounded-card border border-line p-4">
      <div class="flex items-center gap-2 mb-2.5"><span class="w-[24px] h-[24px] rounded-[7px] grid place-items-center" style="background:#f5f3ff"><Icon name="layers" :size="13" color="#7c3aed" /></span><span class="text-[12.5px] font-bold">{{ L("Related documents","المستندات المرتبطة","Documents liés") }}</span></div>
      <div v-if="related.orders.length || related.receipts.length || related.payments.length" class="flex flex-wrap gap-2">
        <button v-for="po in related.orders" :key="po" @click="openDoc('pos', po)" class="inline-flex items-center gap-1.5 text-[11.5px] font-semibold px-2.5 py-1.5 rounded-chip border border-line-2 bg-app-warm hover:bg-white"><Icon name="cart" :size="12" color="#b45309" />{{ po }}</button>
        <button v-for="gr in related.receipts" :key="gr" class="inline-flex items-center gap-1.5 text-[11.5px] font-semibold px-2.5 py-1.5 rounded-chip border border-line-2 bg-app-warm"><Icon name="truck" :size="12" color="#c2410c" />{{ gr }}</button>
        <button v-for="pe in related.payments" :key="pe" @click="openDoc('payments', pe)" class="inline-flex items-center gap-1.5 text-[11.5px] font-semibold px-2.5 py-1.5 rounded-chip border border-line-2 bg-app-warm hover:bg-white"><Icon name="coins" :size="12" color="#047857" />{{ pe }}</button>
      </div>
      <div v-else class="text-[11.5px] text-ink-muted">{{ L("No linked PO, receipt or payment.","لا أمر شراء أو استلام أو دفعة مرتبطة.","Aucun document lié.") }}</div>
    </div>

    <!-- Posted journal -->
    <div class="bg-white rounded-card border border-line overflow-hidden">
      <div class="px-4 py-3 border-b border-line flex items-center gap-2"><Icon name="ledger" :size="15" color="#0b5c4f" /><span class="text-[13px] font-bold">{{ L("Posted journal","القيد المُرحَّل","Écriture passée") }}</span></div>
      <table class="w-full text-[12px]">
        <tbody>
          <tr v-for="(j, i) in journal" :key="i" class="border-b border-line-hair">
            <td class="px-4 py-2.5 font-mono text-ink-2">{{ j.acc }}</td>
            <td class="px-4 py-2.5 text-end tnum font-semibold">{{ j.dr || "—" }}</td>
            <td class="px-4 py-2.5 text-end tnum font-semibold">{{ j.cr || "—" }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <DocHub v-if="route.query.id" :doctype="DOCTYPE" :name="route.query.id" class="mt-1" />
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
import { BILL_STATUS, billStatusLabel } from "@/data/purchases";
import { useBills } from "@/composables/useBills";

const { t, locale } = useI18n();
const route = useRoute();
const router = useRouter();
const toast = useToast();
const { loadDetail } = useBills();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const DOCTYPE = "Purchase Invoice";
const busy = ref(false);
const confirmDebit = ref(false);
async function makeDebit() {
  busy.value = true;
  try {
    const r = await api.call("accounting_portal.api.purchases.make_debit_note", { company: currentCompany(), invoice: route.query.id, submit: 1 });
    if (r && r.status && r.status !== "Posted") toast.success(L("Queued for approval (over 10,000)", "بانتظار الموافقة (فوق 10٬000)", "En attente d'approbation"));
    else { toast.success(L("Debit note created", "تم إنشاء الإشعار", "Note créée")); load(); }
    confirmDebit.value = false;
  } catch (err) { toast.error(String((err && err.message) || L("Failed", "فشل", "Échec")).slice(0, 160)); }
  finally { busy.value = false; }
}

// Live get_bill (real 3-way match + posted journal) with sample fallback.
const vm = ref(null);
const loading = ref(true);
async function load() {
  loading.value = true;
  vm.value = await loadDetail(route.query.id, locale.value);
  loading.value = false;
  if (route.query.id && !vm.value) router.replace("/accounting/purchases/bills");
}
watch(() => [route.query.id, locale.value], load, { immediate: true });

const b = computed(() => vm.value?.b || null);
const matched = computed(() => !!vm.value?.matched);
const legs = computed(() => vm.value?.legs || []);
const items = computed(() => vm.value?.items || []);
const journal = computed(() => vm.value?.journal || []);
const related = computed(() => vm.value?.related || { orders: [], receipts: [], payments: [] });
function openDoc(sub, id) { router.push({ path: `/accounting/purchases/${sub}`, query: { id } }); }

function back() { router.push({ path: "/accounting/purchases/bills" }); }
</script>
