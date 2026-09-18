<template>
  <div class="fixed inset-0 z-50 grid place-items-center bg-black/30 p-4" @click.self="$emit('close')">
    <div class="bg-white rounded-card shadow-xl w-full max-w-sm p-5 space-y-3.5">
      <div class="flex items-center gap-2">
        <span class="w-8 h-8 rounded-[9px] grid place-items-center" style="background:#ecfdf5"><Icon name="wallet" :size="16" color="#047857" /></span>
        <div class="min-w-0">
          <div class="text-[14px] font-bold">{{ L("Record payment", "تسجيل دفعة", "Enregistrer paiement") }}</div>
          <div class="text-[11px] text-ink-muted truncate">{{ invoice }} · {{ fmt(outstanding) }} {{ currency }}</div>
        </div>
      </div>

      <div>
        <label for="pay-mode" class="text-[11px] font-bold text-ink-3">{{ L("Method", "الطريقة", "Méthode") }}</label>
        <select id="pay-mode" v-model="mode" class="fld fld-md w-full mt-1">
          <option value="">{{ L("Select…", "اختر…", "Choisir…") }}</option>
          <option v-for="m in modes" :key="m.mode" :value="m.mode">{{ m.mode }}</option>
        </select>
      </div>

      <div>
        <label for="pay-amount" class="text-[11px] font-bold text-ink-3 flex items-center justify-between">{{ L("Amount", "المبلغ", "Montant") }}
          <button type="button" class="text-[11px] text-accent-dark font-semibold hover:underline" @click="amount = outstanding">{{ L("full","الكامل","total") }} {{ fmt(outstanding) }}</button>
        </label>
        <input id="pay-amount" type="number" min="0" step="0.01" :max="outstanding" v-model.number="amount" dir="ltr"
               class="fld fld-md w-full mt-1 tnum text-end" :placeholder="String(outstanding)" />
        <div v-if="amount > 0 && amount < outstanding" class="text-[11px] text-amber-700 mt-0.5">{{ L("Partial — ","جزئي — ","Partiel — ") }}{{ fmt(outstanding - amount) }} {{ L("stays outstanding","يبقى مستحقًا","restant") }}</div>
      </div>

      <div class="grid grid-cols-2 gap-2">
        <div>
          <label for="pay-ref" class="text-[11px] font-bold text-ink-3">{{ L("Reference No", "رقم المرجع", "Référence") }}</label>
          <input id="pay-ref" v-model.trim="reference" :placeholder="L('Cheque / txn no', 'شيك / معاملة', 'Chèque / réf')" class="fld fld-md w-full mt-1" />
        </div>
        <div>
          <label for="pay-date" class="text-[11px] font-bold text-ink-3">{{ L("Date", "التاريخ", "Date") }}</label>
          <input id="pay-date" type="date" v-model="date" class="fld fld-md w-full mt-1" />
        </div>
      </div>

      <p class="text-[11px] text-ink-muted">{{ L("Bank / cheque methods require a reference.", "طرق البنك/الشيك تتطلب مرجعًا.", "Les méthodes banque/chèque exigent une référence.") }}</p>
      <p v-if="error" class="text-[12px] text-rose-600">{{ error }}</p>

      <div class="flex gap-2 justify-end pt-1">
        <UiButton variant="quiet" @click="$emit('close')">{{ L("Cancel", "إلغاء", "Annuler") }}</UiButton>
        <UiButton variant="primary" size="md" @click="pay" :disabled="posting || !mode" >{{ posting ? L("Paying…", "جارٍ…", "…") : L("Pay", "دفع", "Payer") }}</UiButton>
      </div>
    </div>
  </div>
</template>

<script setup>
// Paying a supplier bill, from anywhere a bill is shown.
//
// This used to live inside one of the two screens that render a Purchase
// Invoice — and not the one you reach from the bill list or from a vendor's
// ledger. So the AP clerk had to know that the same document has a second page
// under a different tab, because the page they landed on had Hold, Write off
// and Debit note, and no way to pay.
import { ref, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import UiButton from "@/components/UiButton.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";

const props = defineProps({
  invoice: { type: String, required: true },
  outstanding: { type: Number, default: 0 },
  currency: { type: String, default: "" },
});
const emit = defineEmits(["close", "paid"]);

const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const modes = ref([]);
const mode = ref("");
const reference = ref("");
const date = ref(new Date().toISOString().slice(0, 10));
const amount = ref(0);
const posting = ref(false);
const error = ref("");

onMounted(async () => {
  try { modes.value = await api.call("accounting_portal.api.purchases.payment_modes", { company: currentCompany() }) || []; }
  catch (e) { error.value = String(e?.message || e).slice(0, 160); }
});

async function pay() {
  posting.value = true;
  error.value = "";
  try {
    const m = modes.value.find((x) => x.mode === mode.value);
    const partial = amount.value > 0 && amount.value < props.outstanding;
    const res = await api.call("accounting_portal.api.purchases.pay_bill", {
      company: currentCompany(), invoice: props.invoice, mode: mode.value,
      paid_from: (m && m.account) || undefined,
      reference_no: reference.value || undefined,
      reference_date: date.value || undefined,
      pay_amount: partial ? amount.value : undefined,
    });
    emit("paid", res);
    emit("close");
  } catch (e) {
    error.value = String(e?.message || e).slice(0, 200);
  } finally {
    posting.value = false;
  }
}
</script>
