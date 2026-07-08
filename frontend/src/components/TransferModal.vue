<template>
  <div class="fixed inset-0 z-[110] flex items-start justify-center p-4 sm:p-8 overflow-y-auto" style="background:rgba(28,25,23,.45)" @click.self="$emit('close')">
    <div class="bg-white rounded-[18px] shadow-cardHover w-full max-w-md my-8 overflow-hidden">
      <div class="flex items-center gap-2.5 px-5 py-4 border-b border-line">
        <span class="w-8 h-8 rounded-[10px] grid place-items-center" style="background:#eff6ff"><Icon name="bank" :size="16" color="#0369a1" /></span>
        <div class="flex-1"><div class="text-[14px] font-bold">{{ L("Transfer between accounts","تحويل بين الحسابات","Virement interne") }}</div>
          <div class="text-[11px] text-ink-muted">{{ L("Internal Transfer · Cr source / Dr target","تحويل داخلي · دائن المصدر / مدين الوجهة","Transfert interne") }}</div></div>
        <button class="text-ink-3 hover:text-ink" @click="$emit('close')"><Icon name="close" :size="18" /></button>
      </div>

      <div v-if="loadingOpt" class="p-8 text-center text-ink-muted text-[12px]">{{ L("Loading…","جارٍ التحميل…","…") }}</div>
      <template v-else>
        <div class="p-5 space-y-3.5">
          <!-- from account — searchable -->
          <div class="block"><span class="text-[11px] font-semibold text-ink-3">{{ L("From account","من حساب","Depuis") }}</span>
            <div class="relative mt-1" v-click-outside="() => (fromOpen = false)">
              <input v-model="fromQuery" @focus="fromOpen = true" @input="fromOpen = true; fromAccount = ''"
                     :placeholder="L('search account…','ابحث عن حساب…','rechercher…')"
                     class="w-full border border-line-2 rounded-chip ps-3 pe-8 py-2 text-[12px] focus:outline-none focus:border-accent/40" />
              <span class="absolute top-1/2 -translate-y-1/2 end-3 text-ink-muted pointer-events-none flex"><Icon :name="fromOpen ? 'search' : 'chev'" :size="14" /></span>
              <div v-if="fromOpen" class="absolute z-20 mt-1 w-full max-h-52 overflow-y-auto bg-white border border-line rounded-[12px] shadow-cardHover">
                <button v-for="a in filtered(fromQuery, fromAccount)" :key="a.name" type="button" class="w-full flex items-center gap-2 px-3 py-2 text-start hover:bg-app-warm/60 text-[12px] border-t border-line-hair first:border-t-0" :class="a.name===fromAccount ? 'bg-accent-soft font-semibold' : ''" @click="pickFrom(a)">
                  <span class="flex-1 truncate">{{ label(a) }}</span><Icon v-if="a.name===fromAccount" name="check" :size="13" color="#047857" /></button>
                <div v-if="!filtered(fromQuery, fromAccount).length" class="px-3 py-3 text-center text-[11px] text-ink-muted">{{ L("No account.","لا حساب.","Aucun.") }}</div>
              </div>
            </div>
          </div>
          <div class="flex justify-center -my-1"><Icon name="arrow" :size="16" color="#9a8f86" class="rotate-90" /></div>
          <!-- to account — searchable -->
          <div class="block"><span class="text-[11px] font-semibold text-ink-3">{{ L("To account","إلى حساب","Vers") }}</span>
            <div class="relative mt-1" v-click-outside="() => (toOpen = false)">
              <input v-model="toQuery" @focus="toOpen = true" @input="toOpen = true; toAccount = ''"
                     :placeholder="L('search account…','ابحث عن حساب…','rechercher…')"
                     class="w-full border border-line-2 rounded-chip ps-3 pe-8 py-2 text-[12px] focus:outline-none focus:border-accent/40" />
              <span class="absolute top-1/2 -translate-y-1/2 end-3 text-ink-muted pointer-events-none flex"><Icon :name="toOpen ? 'search' : 'chev'" :size="14" /></span>
              <div v-if="toOpen" class="absolute z-20 mt-1 w-full max-h-52 overflow-y-auto bg-white border border-line rounded-[12px] shadow-cardHover">
                <button v-for="a in filtered(toQuery, toAccount)" :key="a.name" type="button" :disabled="a.name===fromAccount" class="w-full flex items-center gap-2 px-3 py-2 text-start hover:bg-app-warm/60 text-[12px] border-t border-line-hair first:border-t-0 disabled:opacity-40" :class="a.name===toAccount ? 'bg-accent-soft font-semibold' : ''" @click="pickTo(a)">
                  <span class="flex-1 truncate">{{ label(a) }}</span><Icon v-if="a.name===toAccount" name="check" :size="13" color="#047857" /></button>
                <div v-if="!filtered(toQuery, toAccount).length" class="px-3 py-3 text-center text-[11px] text-ink-muted">{{ L("No account.","لا حساب.","Aucun.") }}</div>
              </div>
            </div>
          </div>

          <div class="grid grid-cols-2 gap-3">
            <label class="block"><span class="text-[11px] font-semibold text-ink-3">{{ L("Amount sent","المبلغ المُرسَل","Montant") }} <span v-if="fromCcy" class="text-ink-muted">({{ fromCcy }})</span></span>
              <input type="number" min="0" step="0.01" v-model.number="amount" class="mt-1 w-full border border-line-2 rounded-chip px-3 py-2 text-[13px] tnum text-end font-semibold focus:outline-none focus:border-accent/40" placeholder="0.00" /></label>
            <label class="block"><span class="text-[11px] font-semibold text-ink-3">{{ L("Date","التاريخ","Date") }}</span>
              <input type="date" v-model="postingDate" class="mt-1 w-full border border-line-2 rounded-chip px-3 py-2 text-[12px] focus:outline-none focus:border-accent/40" /></label>
          </div>

          <!-- cross-currency: received amount in the target's currency -->
          <label v-if="crossCurrency" class="block"><span class="text-[11px] font-semibold text-ink-3">{{ L("Amount received","المبلغ المُستلَم","Reçu") }} ({{ toCcy }})</span>
            <input type="number" min="0" step="0.01" v-model.number="receivedAmount" class="mt-1 w-full border border-line-2 rounded-chip px-3 py-2 text-[13px] tnum text-end font-semibold focus:outline-none focus:border-accent/40" :placeholder="String(amount || 0)" />
            <span class="text-[10px] text-ink-muted">{{ L("different currency — enter what actually landed; ERPNext books the FX difference.","عملة مختلفة — اكتب اللي وصل فعلاً؛ ERPNext بيسجّل فرق الصرف.","devise différente") }}</span>
          </label>

          <label class="block"><span class="text-[11px] font-semibold text-ink-3">{{ L("Reference #","المرجع","Référence") }} <span class="text-ink-muted font-normal">({{ L("optional","اختياري","opt.") }})</span></span>
            <input v-model.trim="referenceNo" class="mt-1 w-full border border-line-2 rounded-chip px-3 py-2 text-[12px] focus:outline-none focus:border-accent/40" :placeholder="L('transfer ref','مرجع التحويل','réf.')" /></label>

          <!-- attachment -->
          <div class="border border-dashed border-line-2 rounded-[12px] px-3 py-2.5">
            <div v-if="!fileUrl" class="flex items-center gap-2">
              <Icon name="doc" :size="14" color="#9a8f86" />
              <label class="text-[11.5px] font-semibold text-accent-dark cursor-pointer hover:underline">
                {{ uploading ? L("Uploading…","جارٍ الرفع…","…") : L("Attach receipt (PDF / photo)","أرفق الإيصال (PDF / صورة)","Joindre le reçu") }}
                <input type="file" accept=".pdf,.png,.jpg,.jpeg,.webp,.heic" class="hidden" @change="onFile" :disabled="uploading" />
              </label>
              <span class="text-[10px] text-ink-muted">{{ L("pinned to the payment entry","بتتعلق على سند الدفع","liée à l'écriture") }}</span>
            </div>
            <div v-else class="flex items-center gap-2">
              <Icon name="check" :size="14" color="#047857" />
              <span class="text-[11.5px] font-medium truncate flex-1">{{ fileName }}</span>
              <button type="button" class="text-[11px] text-rose-500 hover:underline" @click="fileUrl=''; fileName=''">{{ L("remove","إزالة","retirer") }}</button>
            </div>
          </div>

          <div v-if="amount >= threshold" class="text-[11px] text-amber-700 inline-flex items-center gap-1.5"><Icon name="shield" :size="12" />{{ L("Material — goes for approval first.","مبلغ جوهري — للموافقة الأول.","Approbation requise.") }}</div>
          <div v-if="error" class="text-[11.5px] text-sale">{{ error }}</div>
        </div>
        <div class="flex items-center justify-end gap-2 px-5 py-3.5 border-t border-line bg-app-warm/40">
          <button class="px-3.5 py-2 rounded-chip text-[12px] font-semibold text-ink-2 hover:bg-white" @click="$emit('close')">{{ L("Cancel","إلغاء","Annuler") }}</button>
          <button class="px-4 py-2 rounded-chip text-[12px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand disabled:opacity-50" :disabled="!canSubmit || posting || uploading" @click="submit">{{ posting ? "…" : L("Transfer","حوّل","Transférer") }}</button>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useToast } from "@/composables/useToast";
import { getCsrfToken } from "@/utils/helpers";

const props = defineProps({ prefill: { type: Object, default: null } });
const emit = defineEmits(["close", "posted"]);
const { locale } = useI18n();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

const accounts = ref([]);
const baseCcy = ref("MAD");
const loadingOpt = ref(true);
const threshold = 10000;
const fromAccount = ref("");
const toAccount = ref("");
const fromQuery = ref(""), toQuery = ref("");
const fromOpen = ref(false), toOpen = ref(false);
const fileUrl = ref(""), fileName = ref(""), uploading = ref(false);
const amount = ref(null);
const receivedAmount = ref(null);
const postingDate = ref(new Date().toISOString().slice(0, 10));
const referenceNo = ref("");
const posting = ref(false);
const error = ref("");

const label = (a) => `${a.num ? a.num + " · " : ""}${a.nm}${a.ccy && a.ccy !== baseCcy.value ? " · " + a.ccy : ""}`;
function filtered(query, picked) {
  const q = (query || "").trim().toLowerCase();
  if (!q || q === (accMap.value[picked] ? label(accMap.value[picked]).toLowerCase() : "")) return accounts.value.slice(0, 80);
  return accounts.value.filter((a) => label(a).toLowerCase().includes(q)).slice(0, 80);
}
function pickFrom(a) { fromAccount.value = a.name; fromQuery.value = label(a); fromOpen.value = false; }
function pickTo(a) { toAccount.value = a.name; toQuery.value = label(a); toOpen.value = false; }
async function onFile(e) {
  const f = e.target.files[0];
  if (!f) return;
  uploading.value = true; error.value = "";
  try {
    const fd = new FormData();
    fd.append("file", f); fd.append("is_private", 1); fd.append("folder", "Home");
    const res = await fetch("/api/method/upload_file", { method: "POST", headers: { "X-Frappe-CSRF-Token": getCsrfToken() }, body: fd });
    const body = await res.json();
    if (!res.ok) throw new Error("Upload failed");
    fileUrl.value = body.message.file_url; fileName.value = f.name;
  } catch (err) { error.value = String(err?.message || err).slice(0, 160); }
  finally { uploading.value = false; e.target.value = ""; }
}
const accMap = computed(() => Object.fromEntries(accounts.value.map((a) => [a.name, a])));
const fromCcy = computed(() => (accMap.value[fromAccount.value]?.ccy) || baseCcy.value);
const toCcy = computed(() => (accMap.value[toAccount.value]?.ccy) || baseCcy.value);
const crossCurrency = computed(() => fromAccount.value && toAccount.value && fromCcy.value !== toCcy.value);
const canSubmit = computed(() => fromAccount.value && toAccount.value && fromAccount.value !== toAccount.value && Number(amount.value) > 0);

onMounted(async () => {
  try {
    const r = await api.call("accounting_portal.api.reconciliation.transfer_accounts", { company: currentCompany() });
    accounts.value = r.accounts || [];
    baseCcy.value = r.currency || "MAD";
    const p = props.prefill;
    if (p) {
      if (p.from_account && accMap.value[p.from_account]) { fromAccount.value = p.from_account; fromQuery.value = label(accMap.value[p.from_account]); }
      if (p.to_account && accMap.value[p.to_account]) { toAccount.value = p.to_account; toQuery.value = label(accMap.value[p.to_account]); }
      if (p.amount) amount.value = Number(p.amount);
      if (p.posting_date) postingDate.value = String(p.posting_date).slice(0, 10);
      if (p.reference_no) referenceNo.value = p.reference_no;
    }
  } catch (e) { error.value = String(e?.message || e).slice(0, 160); }
  finally { loadingOpt.value = false; }
});

async function submit() {
  if (!canSubmit.value || posting.value) return;
  posting.value = true; error.value = "";
  try {
    const res = await api.call("accounting_portal.api.reconciliation.internal_transfer", {
      company: currentCompany(), from_account: fromAccount.value, to_account: toAccount.value,
      amount: Number(amount.value), posting_date: postingDate.value,
      received_amount: crossCurrency.value && Number(receivedAmount.value) > 0 ? Number(receivedAmount.value) : undefined,
      reference_no: referenceNo.value || undefined,
      attachment: fileUrl.value || undefined,
      attachment_name: fileName.value || undefined,
    });
    if (res?.status === "Proposed") toast.success(L("Sent for approval", "أُرسل للموافقة", "Envoyé"));
    else toast.success(L("Transferred", "تم التحويل", "Transféré"));
    emit("posted", res);
    emit("close");
  } catch (e) { error.value = String(e?.message || e).slice(0, 200); }
  finally { posting.value = false; }
}
</script>
