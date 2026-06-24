<template>
  <div class="fixed inset-0 z-[100] flex items-start justify-center p-4 sm:p-8 overflow-y-auto" style="background:rgba(28,25,23,.45)" @click.self="$emit('close')">
    <div class="bg-white rounded-[18px] shadow-cardHover w-full max-w-2xl my-6 overflow-hidden">
      <div class="flex items-center gap-2.5 px-5 py-4 border-b border-line">
        <span class="w-8 h-8 rounded-[10px] grid place-items-center" style="background:#faf6f4"><Icon name="receipt" :size="16" color="#a33a22" /></span>
        <div class="flex-1 min-w-0">
          <div class="text-[14px] font-bold">{{ L("New sales order", "أمر بيع جديد", "Nouvelle commande") }}</div>
          <div class="text-[11px] text-ink-muted">{{ entityName }} · {{ L("COD · posts to ERPNext via the audit gateway", "COD · يُرحّل لـ ERPNext عبر بوابة التدقيق", "COD · via la passerelle d'audit") }}</div>
        </div>
        <button class="text-ink-3 hover:text-ink" @click="$emit('close')"><Icon name="close" :size="18" /></button>
      </div>

      <div class="p-5 space-y-3.5">
        <!-- Customer -->
        <label class="block relative">
          <span class="text-[11px] font-semibold text-ink-3">{{ L("Customer", "العميل", "Client") }}</span>
          <div class="mt-1 flex items-center gap-2 border rounded-chip px-3 py-2" :class="customer ? 'border-success/40 bg-success-soft/30' : 'border-line-2'">
            <Icon name="user" :size="14" :color="customer ? '#047857' : '#a8a29e'" />
            <input v-model="custQuery" :placeholder="L('Search customer…','ابحث عن عميل…','Rechercher…')" class="flex-1 bg-transparent text-[12px] focus:outline-none" @input="onCustSearch" @focus="custOpen = true" />
            <button v-if="customer" class="text-ink-muted hover:text-sale" @click="clearCust"><Icon name="close" :size="13" /></button>
          </div>
          <div v-if="custOpen && custResults.length" class="absolute z-10 mt-1 w-full bg-white border border-line rounded-[10px] shadow-cardHover max-h-48 overflow-y-auto">
            <button v-for="r in custResults" :key="r.name" class="w-full text-start px-3 py-2 text-[12px] hover:bg-app-warm border-b border-line-hair last:border-0" @click="pickCust(r)">{{ r.label || r.name }}</button>
          </div>
        </label>

        <!-- Items -->
        <div class="border border-line rounded-[12px] overflow-hidden">
          <div class="px-3 py-2 border-b border-line-hair bg-app-warm/40 relative">
            <div class="flex items-center gap-2">
              <Icon name="search" :size="13" color="#a8a29e" />
              <input v-model="itemQuery" :placeholder="L('Search item to add…','ابحث عن صنف لإضافته…','Ajouter un article…')" class="flex-1 bg-transparent text-[12px] focus:outline-none" @input="onItemSearch" @focus="itemOpen = true" />
            </div>
            <div v-if="itemOpen && itemResults.length" class="absolute z-20 mt-1 inset-x-3 bg-white border border-line rounded-[10px] shadow-cardHover max-h-52 overflow-y-auto">
              <button v-for="it in itemResults" :key="it.item_code" class="w-full text-start px-3 py-2 text-[12px] hover:bg-app-warm border-b border-line-hair last:border-0 flex items-center gap-2" @click="addItem(it)">
                <img v-if="it.image" :src="it.image" class="w-7 h-7 rounded object-cover border border-line flex-shrink-0" @error="$event.target.style.display='none'" />
                <span class="flex-1 min-w-0"><span class="font-medium truncate block">{{ it.item_name || it.item_code }}</span><span class="text-[10px] text-ink-muted">{{ it.item_code }}</span></span>
                <span class="text-[11px] tnum text-ink-3">{{ it.rate ? fmt(it.rate) : "" }}</span>
              </button>
            </div>
          </div>
          <table class="w-full text-[12px]">
            <tbody>
              <tr v-for="(ln, i) in lines" :key="i" class="border-b border-line-hair last:border-0">
                <td class="px-3 py-2"><div class="font-medium truncate max-w-[230px]">{{ ln.item_name }}</div><div class="text-[10px] text-ink-muted">{{ ln.item_code }}</div></td>
                <td class="px-2 py-2 w-16"><input type="number" min="1" v-model.number="ln.qty" class="w-full text-end tnum bg-transparent focus:outline-none border-b border-line-2" /></td>
                <td class="px-2 py-2 w-24"><input type="number" min="0" v-model.number="ln.rate" class="w-full text-end tnum bg-transparent focus:outline-none border-b border-line-2" /></td>
                <td class="px-3 py-2 text-end tnum font-semibold w-24">{{ fmt(ln.qty * ln.rate) }}</td>
                <td class="px-2 text-center w-8"><button class="text-ink-muted hover:text-sale" @click="lines.splice(i, 1)"><Icon name="close" :size="13" /></button></td>
              </tr>
              <tr v-if="!lines.length"><td colspan="5" class="px-3 py-4 text-center text-[11.5px] text-ink-muted">{{ L("No items yet — search above to add.", "لا أصناف بعد — ابحث للإضافة.", "Aucun article.") }}</td></tr>
            </tbody>
          </table>
        </div>

        <!-- Shipping -->
        <div class="grid grid-cols-3 gap-3">
          <label class="block"><span class="text-[11px] font-semibold text-ink-3">{{ L("City", "المدينة", "Ville") }}</span>
            <input v-model="city" class="mt-1 w-full border border-line-2 rounded-chip px-3 py-2 text-[12px] focus:outline-none focus:border-accent/40" /></label>
          <label class="block"><span class="text-[11px] font-semibold text-ink-3">{{ L("Phone", "الهاتف", "Téléphone") }}</span>
            <input v-model="phone" placeholder="+212" class="mt-1 w-full border border-line-2 rounded-chip px-3 py-2 text-[12px] focus:outline-none focus:border-accent/40" /></label>
          <label class="block"><span class="text-[11px] font-semibold text-ink-3">{{ L("Carrier", "الناقل", "Transporteur") }}</span>
            <input v-model="carrier" placeholder="Cathedis" class="mt-1 w-full border border-line-2 rounded-chip px-3 py-2 text-[12px] focus:outline-none focus:border-accent/40" /></label>
        </div>

        <!-- Totals -->
        <div class="flex items-center justify-end gap-5 text-[12px] bg-app-warm/40 rounded-[10px] px-4 py-2.5">
          <span class="text-ink-3">{{ L("Net", "الصافي", "HT") }} <b class="tnum text-ink">{{ fmt(net) }}</b></span>
          <span class="text-ink-3">{{ L("VAT 20%", "ض.ق.م 20%", "TVA 20%") }} <b class="tnum text-ink">{{ fmt(vat) }}</b></span>
          <span class="text-ink-3">{{ L("Total", "الإجمالي", "Total") }} <b class="tnum text-ink text-[14px]">{{ fmt(gross) }}</b> MAD</span>
        </div>
        <div v-if="gross >= 10000" class="text-[11px] text-amber-700 inline-flex items-center gap-1"><Icon name="shield" :size="12" />{{ L("≥ 10,000 — recorded as proposed, needs an approver", "≥ 10,000 — يُسجَّل كمقترح ويحتاج موافِق", "≥ 10 000 — proposé") }}</div>
        <div v-if="error" class="text-[11.5px] text-sale">{{ error }}</div>
      </div>

      <div class="flex items-center justify-end gap-2 px-5 py-3.5 border-t border-line bg-app-warm/40">
        <button class="px-3.5 py-2 rounded-chip text-[12px] font-semibold text-ink-2 hover:bg-white" @click="$emit('close')">{{ L("Cancel", "إلغاء", "Annuler") }}</button>
        <button class="px-4 py-2 rounded-chip text-[12px] font-bold text-white bg-accent hover:bg-accent-dark shadow-prim disabled:opacity-50" :disabled="!canPost || posting" @click="post">
          {{ posting ? L("Creating…", "جارٍ…", "…") : L("Create order", "إنشاء الطلب", "Créer") }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from "vue";
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
const fmt = (n) => Number(n || 0).toLocaleString("en-US", { maximumFractionDigits: 2 });

const custQuery = ref(""); const customer = ref(""); const custResults = ref([]); const custOpen = ref(false);
const itemQuery = ref(""); const itemResults = ref([]); const itemOpen = ref(false);
const lines = ref([]);
const city = ref(""); const phone = ref(""); const carrier = ref("");
const posting = ref(false); const error = ref("");

const net = computed(() => lines.value.reduce((s, l) => s + (Number(l.qty) || 0) * (Number(l.rate) || 0), 0));
const vat = computed(() => Math.round(net.value * 0.2 * 100) / 100);
const gross = computed(() => Math.round((net.value + vat.value) * 100) / 100);
const canPost = computed(() => customer.value && lines.value.some((l) => l.item_code && Number(l.qty) > 0));

let ct, it;
function onCustSearch() {
  customer.value = ""; clearTimeout(ct);
  ct = setTimeout(async () => {
    const q = custQuery.value.trim(); if (q.length < 2) { custResults.value = []; return; }
    try { custResults.value = await api.call("accounting_portal.api.payments.party_options", { company: currentCompany(), party_type: "Customer", search: q }) || []; } catch { custResults.value = []; }
  }, 220);
}
function pickCust(r) { customer.value = r.name; custQuery.value = r.label || r.name; custOpen.value = false; custResults.value = []; }
function clearCust() { customer.value = ""; custQuery.value = ""; }

function onItemSearch() {
  clearTimeout(it);
  it = setTimeout(async () => {
    const q = itemQuery.value.trim(); if (q.length < 2) { itemResults.value = []; return; }
    try { itemResults.value = await api.call("accounting_portal.api.sales.item_options", { company: currentCompany(), search: q }) || []; } catch { itemResults.value = []; }
  }, 220);
}
function addItem(i) {
  lines.value.push({ item_code: i.item_code, item_name: i.item_name || i.item_code, qty: 1, rate: Number(i.rate) || 0 });
  itemQuery.value = ""; itemResults.value = []; itemOpen.value = false;
}

async function post() {
  error.value = ""; if (!canPost.value) return;
  posting.value = true;
  try {
    const res = await api.call("accounting_portal.api.sales.create_sales_order", {
      company: currentCompany(), customer: customer.value,
      items: lines.value.map((l) => ({ item_code: l.item_code, qty: Number(l.qty) || 1, rate: Number(l.rate) || 0 })),
      city: city.value, phone: phone.value, carrier: carrier.value,
    });
    emit("posted", res); emit("close");
  } catch (e) {
    error.value = (e && e.message) || L("Failed to create order.", "فشل إنشاء الطلب.", "Échec.");
  } finally { posting.value = false; }
}
</script>
