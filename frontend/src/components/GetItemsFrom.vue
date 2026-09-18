<template>
  <div class="space-y-2">
    <!-- Two sources, because they close different things. Billing off the ORDER
         leaves the receipt in "To Bill"; billing off the RECEIPT is what closes
         the three-way match. The Desk puts both behind one dropdown and so does
         this. -->
    <div class="flex items-center gap-2 flex-wrap">
      <span class="text-[12px] font-semibold">{{ L("Get items from", "اسحب الأصناف من", "Importer depuis") }}</span>
      <div class="flex items-center gap-1">
        <button v-for="s in SOURCES" :key="s.k" type="button"
                class="h-7 px-2.5 rounded-chip text-[11px] font-medium border transition"
                :class="source === s.k ? 'text-white bg-accent border-accent' : 'text-ink-3 bg-white border-line-2 hover:bg-app-warm'"
                @click="pick(s.k)">{{ s.label() }}</button>
      </div>
      <span v-if="who" class="text-[11px] text-ink-muted truncate">{{ who }}</span>
      <input v-model="q" :placeholder="L('Search by number…','ابحث بالرقم…','Rechercher…')" dir="ltr"
             class="fld fld-xs w-40 ms-auto" @input="debounced" />
    </div>

    <!-- Justyol China alone has 2,587 un-billed receipts. Say so rather than
         show sixty of them as if that were the list. -->
    <div v-if="truncated" class="text-[11px] text-ink-muted">
      {{ L("Showing the newest", "بيعرض أحدث", "Les plus récents") }} {{ rows.length }}
      {{ L("of", "من", "sur") }} {{ total.toLocaleString() }} — {{ L("search by number to narrow it.", "ابحث بالرقم علشان تضيّقها.", "affinez par numéro.") }}
    </div>

    <div v-if="loading" class="text-[12px] text-ink-muted py-2">…</div>
    <div v-else-if="error" class="text-[12px] text-sale py-2">{{ error }}</div>
    <div v-else-if="!rows.length" class="text-[12px] text-ink-muted py-2">
      {{ source === 'Purchase Order'
          ? L("Nothing left to bill on this supplier's orders.", "مفيش حاجة متبقية للفوترة على أوامر المورّد ده.", "Rien à facturer sur les commandes.")
          : L("Nothing left to bill on this supplier's receipts.", "مفيش حاجة متبقية للفوترة على استلامات المورّد ده.", "Rien à facturer sur les réceptions.") }}
    </div>

    <div v-else class="max-h-[260px] overflow-y-auto space-y-1.5 -mx-0.5 px-0.5">
      <label v-for="r in rows" :key="r.name"
             class="flex items-center gap-2.5 px-2.5 py-1.5 rounded-[9px] bg-white border border-line-2 cursor-pointer hover:border-ink-muted/40">
        <input type="checkbox" :value="r.name" v-model="picked" class="accent-accent w-3.5 h-3.5" />
        <span class="font-mono text-[12px] font-medium flex-1 min-w-0 truncate">{{ r.name }}</span>
        <span class="text-[11px] text-ink-muted whitespace-nowrap">{{ r.date }}</span>
        <!-- Partly-billed is the row you have to look at twice: some of it is
             already on another bill, and only the remainder comes across. -->
        <span v-if="r.per_billed > 0" class="text-[11px] tnum whitespace-nowrap" style="color:#b45309">
          {{ r.per_billed }}% {{ L("billed", "مفوتر", "facturé") }}
        </span>
        <span class="tnum text-[12px] font-semibold whitespace-nowrap">{{ money(r.total) }}</span>
      </label>
    </div>

    <div class="flex items-center gap-2 pt-0.5">
      <span v-if="picked.length" class="text-[11px] text-ink-muted">{{ picked.length }} {{ L("selected", "محدَّد", "sélectionné(s)") }}</span>
      <span class="ms-auto flex gap-2">
        <UiButton variant="quiet" size="sm" type="button" @click="$emit('close')">{{ L("Back", "رجوع", "Retour") }}</UiButton>
        <UiButton variant="primary" size="sm" type="button" :busy="busy" :disabled="!picked.length"
                  @click="$emit('picked', { source, names: [...picked] })">
          {{ L("Get items", "أضف الأصناف", "Importer") }}
        </UiButton>
      </span>
    </div>
  </div>
</template>

<script setup>
// "Get Items From" — the Desk control the portal never had on a new bill.
//
// It existed here only as a purchase-order panel inside the draft editor, which
// means it was reachable after the bill was saved and never while you were
// keying one, and it could not see purchase receipts at all. Same picker for
// both places now; the caller decides what to do with the chosen documents,
// because a saved draft appends server-side and an unsaved one needs the lines
// back to render.
import { ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import UiButton from "@/components/UiButton.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { fmtAmount } from "@/utils/helpers";

const props = defineProps({
  supplier: { type: String, default: "" },
  invoice: { type: String, default: "" },   // when the draft already exists
  busy: { type: Boolean, default: false },
});
defineEmits(["picked", "close"]);
const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const money = (n) => fmtAmount(n || 0);

const SOURCES = [
  { k: "Purchase Order", label: () => L("Purchase Order", "أمر شراء", "Commande") },
  { k: "Purchase Receipt", label: () => L("Purchase Receipt", "إيصال استلام", "Réception") },
];
const source = ref("Purchase Order");
const rows = ref([]);
const picked = ref([]);
const loading = ref(false);
const error = ref("");
// The server resolves the supplier from the draft when the caller only knows
// the invoice, so this is the one that is always right to show.
const who = ref("");
const q = ref("");
const total = ref(0);
const truncated = ref(false);
let t = null;
function debounced() { clearTimeout(t); t = setTimeout(load, 250); }

async function load() {
  if (!props.supplier && !props.invoice) { rows.value = []; return; }
  loading.value = true; error.value = ""; rows.value = [];
  try {
    const r = await api.call("accounting_portal.api.purchases.billable_sources", {
      company: currentCompany(), supplier: props.supplier || undefined,
      invoice: props.invoice || undefined, source: source.value,
      search: q.value.trim() || undefined,
    }) || {};
    rows.value = r.rows || [];
    total.value = r.total || rows.value.length;
    truncated.value = !!r.truncated;
    who.value = r.supplier || props.supplier || "";
  } catch (e) { error.value = String(e?.message || e).slice(0, 200); }
  finally { loading.value = false; }
}
// Switching source clears the selection — an order and a receipt are different
// documents and "keep what I ticked" across them would be a trap.
function pick(k) { if (k !== source.value) { source.value = k; picked.value = []; q.value = ""; load(); } }
watch(() => [props.supplier, props.invoice], load, { immediate: true });
</script>
