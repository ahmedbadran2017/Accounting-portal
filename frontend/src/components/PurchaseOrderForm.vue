<template>
  <div class="fixed inset-0 z-50 grid place-items-center bg-ink/30 px-4" @click.self="close">
    <div class="bg-white rounded-card shadow-pop w-full max-w-2xl max-h-[92vh] overflow-auto">
      <div class="flex items-center gap-2 px-5 py-3.5 border-b border-line-hair sticky top-0 bg-white z-10">
        <Icon name="cart" :size="16" color="#7c3aed" />
        <span class="text-[14px] font-bold">{{ L("New purchase order","أمر شراء جديد","Nouvelle commande") }}</span>
        <button class="ms-auto text-ink-muted hover:text-ink" @click="close"><Icon name="x" :size="16" /></button>
      </div>

      <div class="p-5 space-y-4">
        <!-- Supplier -->
        <div class="relative">
          <label class="text-[11px] font-semibold text-ink-3">{{ L("Supplier","المورّد","Fournisseur") }}</label>
          <input v-model="supplierSearch" @input="searchSuppliers" @focus="supOpen = true" :placeholder="L('Search supplier…','بحث عن مورّد…','Rechercher…')" class="mt-1 w-full h-9 bg-app-warm/40 border border-line-2 rounded-[8px] px-3 text-[13px] focus:outline-none focus:border-accent/40 focus:bg-white" />
          <div v-if="supOpen && supList.length" class="absolute z-20 mt-1 w-full bg-white border border-line rounded-[10px] shadow-pop py-1 max-h-52 overflow-auto">
            <button v-for="s in supList" :key="s.name" @click="pickSupplier(s)" class="w-full text-start px-3 py-1.5 text-[12.5px] hover:bg-app-warm flex items-center justify-between"><span class="truncate">{{ s.supplier_name || s.name }}</span><span class="text-[10px] text-ink-muted">{{ s.ccy }}</span></button>
          </div>
          <div v-if="supplier" class="mt-1 text-[11px] text-success-dark font-semibold">✓ {{ supplier }}</div>
        </div>

        <!-- Dates -->
        <div class="grid grid-cols-2 gap-3">
          <div><label class="text-[11px] font-semibold text-ink-3">{{ L("Order date","تاريخ الأمر","Date") }}</label>
            <input v-model="transactionDate" type="date" class="mt-1 w-full h-9 bg-app-warm/40 border border-line-2 rounded-[8px] px-2.5 text-[13px] focus:outline-none focus:border-accent/40 focus:bg-white" /></div>
          <div><label class="text-[11px] font-semibold text-ink-3">{{ L("Required by","مطلوب بحلول","Requis le") }}</label>
            <input v-model="scheduleDate" type="date" class="mt-1 w-full h-9 bg-app-warm/40 border border-line-2 rounded-[8px] px-2.5 text-[13px] focus:outline-none focus:border-accent/40 focus:bg-white" /></div>
        </div>

        <!-- Items -->
        <div>
          <div class="flex items-center justify-between mb-1.5"><label class="text-[11px] font-semibold text-ink-3">{{ L("Items","الأصناف","Articles") }}</label>
            <span class="text-[11px] font-bold tnum">{{ L("Total","الإجمالي","Total") }}: {{ money(total) }}</span></div>
          <div class="space-y-2">
            <div v-for="(ln, i) in lines" :key="i" class="flex items-center gap-2">
              <div class="relative flex-1">
                <input v-model="ln.search" @input="searchItems(i)" @focus="ln.open = true" :placeholder="L('Item…','صنف…','Article…')" class="w-full h-8 bg-white border border-line-2 rounded-[8px] px-2.5 text-[12px] focus:outline-none focus:border-accent/40" />
                <div v-if="ln.open && ln.opts && ln.opts.length" class="absolute z-30 mt-1 w-full bg-white border border-line rounded-[10px] shadow-pop py-1 max-h-48 overflow-auto">
                  <button v-for="o in ln.opts" :key="o.item_code" @click="pickItem(i, o)" class="w-full text-start px-3 py-1.5 text-[12px] hover:bg-app-warm"><div class="font-semibold truncate">{{ o.item_name || o.item_code }}</div><div class="text-[10px] text-ink-muted">{{ o.sku || o.item_code }} · {{ money(o.rate) }}</div></button>
                </div>
                <div v-if="ln.item_code" class="text-[10px] text-success-dark mt-0.5 truncate">✓ {{ ln.item_code }}</div>
              </div>
              <input v-model.number="ln.qty" type="number" min="0" step="any" :placeholder="L('Qty','كمية','Qté')" class="w-16 h-8 bg-white border border-line-2 rounded-[8px] px-2 text-[12px] text-end tnum focus:outline-none focus:border-accent/40" />
              <input v-model.number="ln.rate" type="number" min="0" step="any" :placeholder="L('Rate','السعر','Prix')" class="w-24 h-8 bg-white border border-line-2 rounded-[8px] px-2 text-[12px] text-end tnum focus:outline-none focus:border-accent/40" />
              <button @click="lines.splice(i, 1)" :disabled="lines.length === 1" class="text-ink-muted hover:text-sale disabled:opacity-30"><Icon name="x" :size="14" /></button>
            </div>
          </div>
          <button @click="addLine" class="mt-2 text-[11.5px] font-semibold text-accent-dark hover:underline inline-flex items-center gap-1"><Icon name="plus" :size="12" />{{ L("Add line","إضافة سطر","Ajouter") }}</button>
        </div>

        <label class="flex items-center gap-2 text-[12px] text-ink-2 cursor-pointer">
          <input type="checkbox" v-model="submitNow" class="accent-brand" />
          {{ L("Submit immediately (otherwise saved as draft)","ترحيل فورًا (وإلا تُحفظ كمسودة)","Soumettre tout de suite") }}
        </label>
      </div>

      <div class="flex justify-end gap-2 px-5 py-3.5 border-t border-line-hair sticky bottom-0 bg-white">
        <button class="px-4 py-2 rounded-chip text-[12px] font-semibold text-ink-2 hover:bg-app-warm" @click="close">{{ L("Cancel","إلغاء","Annuler") }}</button>
        <button class="px-4 py-2 rounded-chip text-[12px] font-bold text-white bg-brand hover:bg-brand-dark disabled:opacity-50" :disabled="busy || !canSave" @click="save">{{ busy ? L("Saving…","جارٍ…","…") : L("Create PO","إنشاء الأمر","Créer") }}</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useToast } from "@/composables/useToast";

const emit = defineEmits(["close", "created"]);
const router = useRouter();
const { locale } = useI18n();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const money = (n) => Number(n || 0).toLocaleString("en-US", { maximumFractionDigits: 2 });

const supplier = ref("");
const supplierSearch = ref("");
const supList = ref([]);
const supOpen = ref(false);
const transactionDate = ref(new Date().toISOString().slice(0, 10));
const scheduleDate = ref(new Date().toISOString().slice(0, 10));
const lines = ref([{ search: "", item_code: "", qty: 1, rate: 0, opts: [], open: false }]);
const submitNow = ref(true);
const busy = ref(false);
let st = null;

async function searchSuppliers() {
  supOpen.value = true;
  clearTimeout(st);
  st = setTimeout(async () => {
    try { supList.value = await api.call("accounting_portal.api.purchases.supplier_options", { search: supplierSearch.value, company: currentCompany() }) || []; } catch { supList.value = []; }
  }, 250);
}
function pickSupplier(s) { supplier.value = s.name; supplierSearch.value = s.supplier_name || s.name; supOpen.value = false; }

const its = {};
async function searchItems(i) {
  const ln = lines.value[i]; ln.open = true;
  clearTimeout(its[i]);
  its[i] = setTimeout(async () => {
    try { ln.opts = await api.call("accounting_portal.api.purchases.po_item_options", { search: ln.search }) || []; } catch { ln.opts = []; }
  }, 250);
}
function pickItem(i, o) { const ln = lines.value[i]; ln.item_code = o.item_code; ln.search = o.item_name || o.item_code; if (!ln.rate) ln.rate = Number(o.rate) || 0; ln.open = false; }
function addLine() { lines.value.push({ search: "", item_code: "", qty: 1, rate: 0, opts: [], open: false }); }

const total = computed(() => lines.value.reduce((s, l) => s + (Number(l.qty) || 0) * (Number(l.rate) || 0), 0));
const canSave = computed(() => supplier.value && lines.value.some((l) => l.item_code && Number(l.qty) > 0));

async function save() {
  busy.value = true;
  try {
    const items = lines.value.filter((l) => l.item_code && Number(l.qty) > 0).map((l) => ({ item_code: l.item_code, qty: Number(l.qty), rate: Number(l.rate) || 0 }));
    const r = await api.call("accounting_portal.api.purchases.create_purchase_order", {
      company: currentCompany(), supplier: supplier.value, items: JSON.stringify(items),
      transaction_date: transactionDate.value, schedule_date: scheduleDate.value, submit: submitNow.value ? 1 : 0,
    });
    if (r && r.status && r.status !== "Posted") {
      toast.success(L("Queued for approval (over 10,000)", "بانتظار الموافقة (فوق 10٬000)", "En attente d'approbation"));
    } else {
      let res = r && r.result; res = typeof res === "string" ? JSON.parse(res) : res;
      const po = res && res.voucher_no || r.voucher_no;
      toast.success(L("Purchase order created", "تم إنشاء أمر الشراء", "Commande créée"));
      if (po) router.push({ path: "/accounting/purchases/tobuy", query: { id: po } });
    }
    emit("created");
    close();
  } catch (err) { toast.error(String((err && err.message) || L("Failed", "فشل", "Échec")).slice(0, 160)); }
  finally { busy.value = false; }
}
function close() { emit("close"); }
</script>
