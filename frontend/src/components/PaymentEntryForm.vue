<template>
  <div class="fixed inset-0 z-[100] flex items-start justify-center p-4 sm:p-8 overflow-y-auto" style="background:rgba(28,25,23,.45)" @click.self="$emit('close')">
    <div class="bg-white rounded-[18px] shadow-cardHover w-full max-w-lg my-6 overflow-hidden">
      <div class="flex items-center gap-2.5 px-5 py-4 border-b border-line">
        <span class="w-8 h-8 rounded-[10px] grid place-items-center" style="background:#ecfdf5"><Icon name="coins" :size="16" color="#047857" /></span>
        <div class="flex-1 min-w-0">
          <div class="text-[14px] font-bold">{{ L("Record a receipt", "تسجيل دفعة", "Enregistrer un encaissement") }}</div>
          <div class="text-[11px] text-ink-muted">{{ entityName }} · {{ L("posts a Payment Entry via the audit gateway", "يُرحّل سند قبض عبر بوابة التدقيق", "passe via la passerelle d'audit") }}</div>
        </div>
        <button class="text-ink-3 hover:text-ink" @click="$emit('close')"><Icon name="close" :size="18" /></button>
      </div>

      <div class="p-5 space-y-3.5">
        <!-- Party search -->
        <label class="block relative">
          <span class="text-[11px] font-semibold text-ink-3">{{ L("Customer", "العميل", "Client") }}</span>
          <div class="mt-1 flex items-center gap-2 border rounded-chip px-3 py-2" :class="party ? 'border-success/40 bg-success-soft/30' : 'border-line-2'">
            <Icon name="user" :size="14" :color="party ? '#047857' : '#a8a29e'" />
            <input v-model="partyQuery" :placeholder="L('Search customer…','ابحث عن عميل…','Rechercher…')"
                   class="flex-1 bg-transparent text-[12px] focus:outline-none" @input="onSearch" @focus="open=true" />
            <button v-if="party" class="text-ink-muted hover:text-sale" @click="clearParty"><Icon name="close" :size="13" /></button>
          </div>
          <div v-if="open && results.length" class="absolute z-10 mt-1 w-full bg-white border border-line rounded-[10px] shadow-cardHover max-h-52 overflow-y-auto">
            <button v-for="r in results" :key="r.name" class="w-full text-start px-3 py-2 text-[12px] hover:bg-app-warm border-b border-line-hair last:border-0"
                    @click="pick(r)"><span class="font-medium">{{ r.label || r.name }}</span></button>
          </div>
        </label>

        <div class="grid grid-cols-2 gap-3">
          <label class="block">
            <span class="text-[11px] font-semibold text-ink-3">{{ L("Amount", "المبلغ", "Montant") }}</span>
            <input type="number" min="0" v-model.number="amount" placeholder="0.00" class="mt-1 w-full border border-line-2 rounded-chip px-3 py-2 text-[12px] text-end tnum focus:outline-none focus:border-accent/40" />
          </label>
          <label class="block">
            <span class="text-[11px] font-semibold text-ink-3">{{ L("Date", "التاريخ", "Date") }}</span>
            <input type="date" v-model="postingDate" class="mt-1 w-full border border-line-2 rounded-chip px-3 py-2 text-[12px] focus:outline-none focus:border-accent/40" />
          </label>
        </div>

        <label class="block">
          <span class="text-[11px] font-semibold text-ink-3">{{ L("Deposit to", "إيداع في", "Déposé sur") }}</span>
          <select v-model="account" class="mt-1 w-full border border-line-2 rounded-chip px-3 py-2 text-[12px] focus:outline-none focus:border-accent/40 cursor-pointer">
            <option value="">{{ L("Select bank / cash account…", "اختر حساب بنك / نقدية…", "Choisir un compte…") }}</option>
            <option v-for="a in accounts" :key="a.name" :value="a.name">{{ a.account_name }} · {{ a.currency }}</option>
          </select>
        </label>

        <label class="block">
          <span class="text-[11px] font-semibold text-ink-3">{{ L("Reference no.", "رقم المرجع", "Référence") }} <span class="text-ink-muted font-normal">{{ L("(optional)", "(اختياري)", "(facultatif)") }}</span></span>
          <input v-model="referenceNo" :placeholder="L('Carrier remittance / receipt no.', 'رقم تحويل الناقل / الإيصال', 'N° de versement')" class="mt-1 w-full border border-line-2 rounded-chip px-3 py-2 text-[12px] focus:outline-none focus:border-accent/40" />
        </label>

        <div v-if="amount >= 10000" class="text-[11px] text-amber-700 inline-flex items-center gap-1"><Icon name="shield" :size="12" />{{ L("≥ 10,000 — recorded as proposed, needs an approver", "≥ 10,000 — يُسجَّل كمقترح ويحتاج موافِق", "≥ 10 000 — proposé, approbation requise") }}</div>
        <div v-if="error" class="text-[11.5px] text-sale">{{ error }}</div>
      </div>

      <div class="flex items-center justify-end gap-2 px-5 py-3.5 border-t border-line bg-app-warm/40">
        <button class="px-3.5 py-2 rounded-chip text-[12px] font-semibold text-ink-2 hover:bg-white" @click="$emit('close')">{{ L("Cancel", "إلغاء", "Annuler") }}</button>
        <button class="px-4 py-2 rounded-chip text-[12px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand disabled:opacity-50" :disabled="!canPost || posting" @click="post">
          {{ posting ? L("Recording…", "جارٍ…", "…") : L("Record receipt", "تسجيل الدفعة", "Enregistrer") }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";

const emit = defineEmits(["close", "posted"]);
const { locale } = useI18n();
const { entityId, entities } = useUi();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const entityName = computed(() => (entities.find((e) => e.id === entityId.value) || entities[0]).name);

const postingDate = ref(new Date().toISOString().slice(0, 10));
const partyQuery = ref("");
const party = ref("");
const results = ref([]);
const open = ref(false);
const amount = ref(null);
const account = ref("");
const referenceNo = ref("");
const accounts = ref([]);
const posting = ref(false);
const error = ref("");

const canPost = computed(() => party.value && Number(amount.value) > 0 && account.value);

onMounted(async () => {
  try { accounts.value = await api.call("accounting_portal.api.payments.deposit_accounts", { company: currentCompany() }) || []; } catch { accounts.value = []; }
});

let timer = null;
function onSearch() {
  party.value = "";
  clearTimeout(timer);
  timer = setTimeout(async () => {
    const q = partyQuery.value.trim();
    if (q.length < 2) { results.value = []; return; }
    try { results.value = await api.call("accounting_portal.api.payments.party_options", { company: currentCompany(), party_type: "Customer", search: q }) || []; } catch { results.value = []; }
  }, 220);
}
function pick(r) { party.value = r.name; partyQuery.value = r.label || r.name; open.value = false; results.value = []; }
function clearParty() { party.value = ""; partyQuery.value = ""; }

async function post() {
  error.value = "";
  if (!canPost.value) return;
  posting.value = true;
  try {
    const res = await api.call("accounting_portal.api.payments.create_payment_entry", {
      company: currentCompany(), party: party.value, amount: Number(amount.value),
      account: account.value, reference_no: referenceNo.value, posting_date: postingDate.value,
      payment_type: "Receive",
    });
    emit("posted", res);
    emit("close");
  } catch (e) {
    error.value = (e && e.message) || L("Failed to record.", "فشل التسجيل.", "Échec.");
  } finally {
    posting.value = false;
  }
}
</script>
