<template>
  <div class="space-y-3.5">
    <div class="grid grid-cols-2 lg:grid-cols-3 gap-2.5">
      <div class="bg-white rounded-[13px] border border-line px-4 py-3 shadow-card">
        <div class="text-[11px] text-ink-muted font-semibold">{{ L("Waiting for your confirmation","بانتظار تأكيدك","En attente de confirmation") }}</div>
        <div class="text-[20px] font-bold tnum mt-0.5">{{ (sum.count || 0).toLocaleString() }}</div>
      </div>
      <div class="bg-white rounded-[13px] border border-line px-4 py-3 shadow-card">
        <div class="text-[11px] text-ink-muted font-semibold">{{ L("Value to confirm","القيمة للتأكيد","Montant à confirmer") }}</div>
        <div class="text-[20px] font-bold tnum mt-0.5 text-sale">{{ money(sum.value) }} <span class="text-[11px] text-ink-muted font-normal">MAD</span></div>
      </div>
    </div>

    <!-- Why this list exists: logistics will not prepare these orders until the
         transfer is on the books, because the courier label is printed for the
         total minus what is already paid. -->
    <div class="rounded-[12px] border border-amber-200 bg-amber-50 px-4 py-2.5 flex items-start gap-2.5">
      <Icon name="alert" :size="15" color="#b45309" class="mt-0.5 flex-shrink-0" />
      <span class="text-[12px] text-ink-2">{{ L(
        "Customers who paid by bank transfer. Logistics holds these orders until you confirm the money arrived. Confirming records the transfer on the order — the order is released to logistics and its courier label prints at 0, so the customer is not charged again at the door.",
        "عملاء دفعوا بالتحويل البنكي. اللوجستيك يوقف هذه الطلبات حتى تؤكد وصول المبلغ. التأكيد يسجّل التحويل على الطلب — فيُفرج عنه للوجستيك وتُطبع بوليصة الشحن بصفر، فلا يُطالَب العميل بالدفع مرة أخرى عند التسليم.",
        "Clients ayant payé par virement. La logistique bloque ces commandes jusqu'à votre confirmation. Confirmer enregistre le virement sur la commande — elle est libérée et son étiquette transporteur sort à 0, le client ne repaie pas à la livraison.") }}</span>
    </div>

    <div class="bg-white rounded-card border border-line overflow-hidden shadow-card">
      <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
        <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#fff4e0"><Icon name="bank" :size="14" color="#b45309" /></span>
        <span class="text-[13px] font-bold">{{ L("Bank transfers to confirm","تحويلات بنكية للتأكيد","Virements à confirmer") }}</span>
        <LiveBadge :live="isLive" />
        <span class="hidden lg:inline text-[11px] text-ink-muted">{{ (st.total.value || 0).toLocaleString() }} · {{ L("oldest first","الأقدم أولاً","plus anciens") }}</span>
        <div class="ms-auto relative">
          <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
          <input v-model.trim="st.search.value" :placeholder="L('Order / customer / phone…','طلب / عميل / هاتف…','Commande / client / tél…')" class="fld fld-md fld-sunk w-44 sm:w-60" />
        </div>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead><tr style="background:#fafaf9">
            <th class="px-4 py-2.5 text-start text-[11px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Order","الطلب","Commande") }}</th>
            <th class="px-4 py-2.5 text-start text-[11px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Customer","العميل","Client") }}</th>
            <th class="px-4 py-2.5 text-start text-[11px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Phone","الهاتف","Tél.") }}</th>
            <th class="px-4 py-2.5 text-end text-[11px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Age","العمر","Âge") }}</th>
            <th class="px-4 py-2.5 text-end text-[11px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Due","المستحق","Dû") }}</th>
            <th class="px-4 py-2.5 text-end text-[11px] font-bold uppercase tracking-wider text-ink-muted"></th>
          </tr></thead>
          <tbody>
            <tr v-for="r in st.rows.value" :key="r.name" class="border-t border-line-hair hover:bg-app-warm/50">
              <td class="px-4 py-2.5 font-mono text-[12px] font-semibold cursor-pointer hover:text-accent-dark" @click="openOrder(r.name)">{{ r.name }}</td>
              <td class="px-4 py-2.5 truncate max-w-[220px]" dir="auto">{{ r.customer_name || r.customer }}</td>
              <td class="px-4 py-2.5 tnum text-ink-muted" dir="ltr">{{ r.phone }}</td>
              <td class="px-4 py-2.5 text-end"><span class="text-[11px] font-bold px-2 py-0.5 rounded-badge" :style="ageBadge(r.age)">{{ r.age }}{{ L("d","ي","j") }}</span></td>
              <td class="px-4 py-2.5 text-end tnum font-semibold">{{ fmt(r.due) }}</td>
              <td class="px-4 py-2.5 text-end">
                <UiButton variant="secondary" size="xs" icon="check" @click.stop="openConfirm(r)">{{ L("Transfer received","وصل التحويل","Virement reçu") }}</UiButton>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <TableLoading v-if="st.loading.value" :rows="6" />
      <div v-else-if="!st.rows.value.length" class="px-4 py-12 text-center text-ink-muted text-[12px]">{{ L("No transfer is waiting. 🎉","لا يوجد تحويل بانتظار التأكيد. 🎉","Aucun virement en attente. 🎉") }}</div>
      <ServerPager :t="st" />
    </div>

    <!-- Confirm: the transfer is on the bank statement -->
    <div v-if="cur" class="fixed inset-0 z-50 grid place-items-center bg-black/30 p-4" @click.self="cur = null">
      <div class="bg-white rounded-card shadow-xl w-full max-w-sm p-5 space-y-3.5">
        <div class="flex items-center gap-2">
          <span class="w-8 h-8 rounded-[9px] grid place-items-center" style="background:#ecfdf5"><Icon name="bank" :size="16" color="#047857" /></span>
          <div class="min-w-0">
            <div class="text-[14px] font-bold">{{ L("Confirm bank transfer","تأكيد التحويل البنكي","Confirmer le virement") }}</div>
            <div class="text-[11px] text-ink-muted truncate" dir="auto">{{ cur.name }} · {{ cur.customer_name || cur.customer }} · {{ fmt(cur.due) }} MAD</div>
          </div>
        </div>
        <div>
          <label for="tr-amount" class="text-[11px] font-bold text-ink-3">{{ L("Amount received","المبلغ المستلم","Montant reçu") }}</label>
          <input id="tr-amount" type="number" min="0" step="0.01" :max="cur.due" v-model.number="amount" dir="ltr" class="fld fld-md w-full mt-1 tnum text-end" />
          <div v-if="amount > 0 && cur.due - amount >= 1" class="text-[11px] text-amber-700 mt-0.5">{{ L("Partial — the order stays held until the rest arrives.","جزئي — يبقى الطلب موقوفًا حتى يصل الباقي.","Partiel — la commande reste bloquée jusqu'au reste.") }}</div>
        </div>
        <div>
          <label for="tr-acct" class="text-[11px] font-bold text-ink-3">{{ L("Received into","استُلم في","Reçu sur") }}</label>
          <select id="tr-acct" v-model="account" class="fld fld-md w-full mt-1">
            <option v-for="a in accounts" :key="a.name" :value="a.name">{{ a.name }}</option>
          </select>
        </div>
        <div class="grid grid-cols-2 gap-2">
          <div>
            <label for="tr-ref" class="text-[11px] font-bold text-ink-3">{{ L("Bank reference","مرجع البنك","Réf. bancaire") }}</label>
            <input id="tr-ref" v-model.trim="reference" :placeholder="L('Statement line','سطر الكشف','Ligne du relevé')" class="fld fld-md w-full mt-1" />
          </div>
          <div>
            <label for="tr-date" class="text-[11px] font-bold text-ink-3">{{ L("Date","التاريخ","Date") }}</label>
            <input id="tr-date" type="date" v-model="date" class="fld fld-md w-full mt-1" />
          </div>
        </div>
        <p v-if="error" class="text-[12px] text-rose-600">{{ error }}</p>
        <div class="flex gap-2 justify-end pt-1">
          <UiButton variant="quiet" @click="cur = null">{{ L("Cancel","إلغاء","Annuler") }}</UiButton>
          <UiButton variant="primary" size="md" :disabled="posting || !(amount > 0) || !account" @click="confirm">
            {{ posting ? L("Recording…","جارٍ التسجيل…","Enregistrement…") : L("Confirm","تأكيد","Confirmer") }}
          </UiButton>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
// Accounting's side of the logistics hold on bank-transfer orders
// (backend: accounting_portal.api.transfers).
import { fmtAmount } from "@/utils/helpers";
import { ref, computed, watch } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import LiveBadge from "@/components/LiveBadge.vue";
import ServerPager from "@/components/ServerPager.vue";
import TableLoading from "@/components/TableLoading.vue";
import UiButton from "@/components/UiButton.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useServerTable } from "@/composables/useServerTable";
import { useUi } from "@/composables/useUi";
import { useToast } from "@/composables/useToast";

const { locale } = useI18n();
const { entityId } = useUi();
const router = useRouter();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US");
const money = (n) => fmtAmount(n);

const isLive = ref(null);
const st = useServerTable(
  (params) => api.call("accounting_portal.api.transfers.awaiting", { company: currentCompany(), ...params }).then((r) => { isLive.value = true; return r; }),
  { pageSize: 25, sortField: "date", sortDir: "asc", storeKey: "transfers" },
);
st.load();
watch(entityId, () => { st.page.value = 1; st.load(); });
const sum = computed(() => (st.extra.value && st.extra.value.summary) || {});

const cur = ref(null);
const amount = ref(0);
const account = ref("");
const reference = ref("");
const date = ref(new Date().toISOString().slice(0, 10));
const accounts = ref([]);
const posting = ref(false);
const error = ref("");

async function openConfirm(r) {
  cur.value = r; amount.value = r.due; reference.value = ""; error.value = "";
  date.value = new Date().toISOString().slice(0, 10);
  if (!accounts.value.length) {
    try { accounts.value = await api.call("accounting_portal.api.payments.deposit_accounts", { company: currentCompany() }) || []; } catch { accounts.value = []; }
  }
  const dflt = sum.value.default_account;
  account.value = (dflt && accounts.value.some((a) => a.name === dflt)) ? dflt : (accounts.value[0] && accounts.value[0].name) || "";
}

async function confirm() {
  if (!cur.value || posting.value) return;
  posting.value = true; error.value = "";
  try {
    const res = await api.call("accounting_portal.api.transfers.confirm", {
      company: currentCompany(), sales_order: cur.value.name, amount: amount.value,
      account: account.value, reference_no: reference.value, posting_date: date.value,
    });
    if (res && res.status && res.status !== "Posted") {
      toast.success(L("Recorded — awaiting approval", "سُجّل — بانتظار الموافقة", "Enregistré — en attente d'approbation"));
    } else {
      toast.success(L("Transfer recorded — order released to logistics", "سُجّل التحويل — أُفرج عن الطلب للوجستيك", "Virement enregistré — commande libérée"));
    }
    cur.value = null;
    st.load();
  } catch (err) {
    error.value = String((err && err.message) || L("Failed", "فشل", "Échec")).slice(0, 200);
  } finally { posting.value = false; }
}

function openOrder(name) { router.push({ path: "/accounting/sales/orders", query: { id: name } }); }
function ageBadge(d) {
  d = Number(d) || 0;
  if (d > 3) return "background:#fef2f2;color:#b91c1c";
  if (d > 1) return "background:#fffbeb;color:#b45309";
  return "background:#ecfdf5;color:#047857";
}
</script>
