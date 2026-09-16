<template>
  <div class="fixed inset-0 z-[60] grid place-items-center bg-ink/30 p-3" @click.self="$emit('close')">
    <div class="bg-white rounded-card shadow-pop w-full max-w-4xl max-h-[92vh] flex flex-col">
      <div class="px-5 py-3 border-b border-line-hair flex items-center gap-2">
        <Icon name="receipt" :size="15" color="#0b5c4f" />
        <span class="text-[14px] font-bold">{{ sales ? L("New sales invoice", "فاتورة بيع جديدة", "Nouvelle facture de vente") : L("New supplier invoice", "فاتورة شراء جديدة", "Nouvelle facture d'achat") }}</span>
        <span class="text-[11px] text-ink-muted">{{ o.company }} · {{ form.currency || o.currency }}</span>
        <button class="ms-auto text-ink-muted hover:text-ink" @click="$emit('close')"><Icon name="close" :size="16" /></button>
      </div>

      <div class="flex-1 overflow-auto px-5 py-4 space-y-3">
        <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div class="sm:col-span-2">
            <label class="block text-[11px] font-bold text-ink-3 mb-1">{{ sales ? L("Customer", "العميل", "Client") : L("Supplier", "المورّد", "Fournisseur") }} *</label>
            <PartyBox v-model="form.party" :party-type="sales ? 'Customer' : 'Supplier'" />
          </div>
          <div><label class="block text-[11px] font-bold text-ink-3 mb-1">{{ L("Posting date", "تاريخ الترحيل", "Date") }}</label>
            <input type="date" v-model="form.posting_date" class="h-9 w-full rounded-[9px] border border-line-2 px-2.5 text-[12.5px] bg-white" /></div>
          <div><label class="block text-[11px] font-bold text-ink-3 mb-1">{{ L("Due date", "الاستحقاق", "Échéance") }}</label>
            <input type="date" v-model="form.due_date" class="h-9 w-full rounded-[9px] border border-line-2 px-2.5 text-[12.5px] bg-white" /></div>

          <template v-if="!sales">
            <div><label class="block text-[11px] font-bold text-ink-3 mb-1">{{ L("Supplier invoice no", "رقم فاتورة المورّد", "N° facture fourn.") }}</label>
              <input v-model.trim="form.bill_no" class="h-9 w-full rounded-[9px] border border-line-2 px-2.5 text-[12.5px] bg-white" /></div>
            <div><label class="block text-[11px] font-bold text-ink-3 mb-1">{{ L("Supplier invoice date", "تاريخ فاتورة المورّد", "Date facture") }}</label>
              <input type="date" v-model="form.bill_date" class="h-9 w-full rounded-[9px] border border-line-2 px-2.5 text-[12.5px] bg-white" /></div>
          </template>

          <div><label class="block text-[11px] font-bold text-ink-3 mb-1">{{ L("Tax template", "قالب الضريبة", "Taxes") }}</label>
            <select v-model="form.tax_template" class="h-9 w-full rounded-[9px] border border-line-2 px-2 text-[12.5px] bg-white">
              <option value="">{{ L("No tax", "بدون ضريبة", "Sans taxe") }}</option>
              <option v-for="t in o.tax_templates" :key="t" :value="t">{{ t }}</option>
            </select></div>
          <div><label class="block text-[11px] font-bold text-ink-3 mb-1">{{ L("Currency", "العملة", "Devise") }}</label>
            <select v-model="form.currency" class="h-9 w-full rounded-[9px] border border-line-2 px-2 text-[12.5px] bg-white">
              <option v-for="c in o.currencies" :key="c" :value="c">{{ c }}</option>
            </select></div>
          <div v-if="form.currency && form.currency !== o.currency">
            <label class="block text-[11px] font-bold text-ink-3 mb-1">{{ L("Exchange rate", "سعر الصرف", "Taux") }}</label>
            <input type="number" step="any" v-model="form.exchange_rate" dir="ltr" class="h-9 w-full rounded-[9px] border border-line-2 px-2.5 text-[12.5px] bg-white tnum" /></div>
        </div>

        <!-- lines -->
        <div class="border border-line rounded-[12px] overflow-hidden">
          <div class="px-3 py-2 border-b border-line-hair flex items-center gap-2 text-[12px] font-bold">
            <Icon name="list" :size="13" color="#0b5c4f" />{{ L("Items", "الأصناف", "Articles") }}
            <span class="ms-auto text-[11.5px] tnum text-ink-3">{{ L("Net", "الصافي", "HT") }} {{ fmt(net) }} {{ form.currency || o.currency }}</span>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full text-[12px]">
              <thead><tr class="text-[10px] font-bold uppercase tracking-wider text-ink-muted" style="background:#fafaf9">
                <th class="px-2 py-2 text-start w-6">#</th>
                <th class="px-2 py-2 text-start">{{ L("Item", "الصنف", "Article") }}</th>
                <th class="px-2 py-2 text-end w-24">{{ L("Qty", "الكمية", "Qté") }}</th>
                <th class="px-2 py-2 text-end w-28">{{ L("Rate", "السعر", "Prix") }}</th>
                <th class="px-2 py-2 text-end w-28">{{ L("Amount", "المبلغ", "Montant") }}</th>
                <th class="px-2 py-2 text-start w-56">{{ sales ? L("Income account", "حساب الإيراد", "Compte produit") : L("Expense account", "حساب المصروف", "Compte charge") }}</th>
                <th class="px-2 py-2 text-start w-44">{{ L("Cost centre", "مركز التكلفة", "Centre") }}</th>
                <th class="w-8"></th>
              </tr></thead>
              <tbody>
                <tr v-for="(ln, i) in lines" :key="i" class="border-t border-line-hair align-top">
                  <td class="px-2 py-1.5 text-ink-muted tnum">{{ i + 1 }}</td>
                  <td class="px-1.5 py-1"><ItemBox v-model="ln.item_code" @picked="(it) => onItem(ln, it)" /></td>
                  <td class="px-1.5 py-1"><input type="number" step="any" min="0" v-model="ln.qty" dir="ltr" class="h-8 w-full rounded-[8px] border border-line-2 px-2 text-[12px] text-end tnum bg-white" /></td>
                  <td class="px-1.5 py-1"><input type="number" step="any" min="0" v-model="ln.rate" dir="ltr" class="h-8 w-full rounded-[8px] border border-line-2 px-2 text-[12px] text-end tnum bg-white" /></td>
                  <td class="px-2 py-2 text-end tnum text-ink-2">{{ fmt((Number(ln.qty) || 0) * (Number(ln.rate) || 0)) }}</td>
                  <td class="px-1.5 py-1"><SearchSelect v-model="ln.account" :items="o.accounts || []" :placeholder="L('default','افتراضي','défaut')" inputClass="h-8 text-[12px] bg-white" /></td>
                  <td class="px-1.5 py-1"><SearchSelect v-model="ln.cost_center" :items="o.cost_centers || []" :placeholder="L('none','بدون','aucun')" inputClass="h-8 text-[12px] bg-white" /></td>
                  <td class="px-1 py-1.5 text-center"><button type="button" class="text-ink-muted hover:text-sale" @click="lines.splice(i, 1)"><Icon name="close" :size="13" /></button></td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="px-3 py-2 border-t border-line-hair">
            <button type="button" class="inline-flex items-center gap-1 text-[11.5px] font-semibold text-accent hover:text-accent-dark" @click="addLine"><Icon name="plus" :size="12" />{{ L("Add line", "إضافة سطر", "Ajouter") }}</button>
          </div>
        </div>

        <div><label class="block text-[11px] font-bold text-ink-3 mb-1">{{ L("Remarks", "ملاحظات", "Remarques") }}</label>
          <textarea v-model.trim="form.remarks" rows="2" class="w-full rounded-[9px] border border-line-2 px-2.5 py-1.5 text-[12.5px] bg-white"></textarea></div>

        <label class="inline-flex items-center gap-2 text-[12.5px]"><input type="checkbox" v-model="form.submit" /> {{ L("Submit now (otherwise saved as a draft to review)", "رحّلها الآن (وإلا تتحفظ كمسودة للمراجعة)", "Soumettre maintenant") }}</label>
        <p v-if="error" class="text-[12px] text-sale">{{ error }}</p>
      </div>

      <div class="px-5 py-3 border-t border-line-hair flex items-center gap-2">
        <span class="text-[11px] text-ink-muted">{{ L("Taxes are applied by the selected template on save.", "الضريبة بتتحسب من القالب عند الحفظ.", "Les taxes viennent du modèle.") }}</span>
        <div class="ms-auto flex gap-2">
          <button class="h-9 px-3.5 rounded-chip text-[12px] font-semibold text-ink-2 hover:bg-app-warm" @click="$emit('close')">{{ L("Cancel", "إلغاء", "Annuler") }}</button>
          <button class="h-9 px-4 rounded-chip text-[12px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand disabled:opacity-50" :disabled="busy || !form.party || !net" @click="save">
            {{ busy ? "…" : (form.submit ? L("Create & submit", "إنشاء وترحيل", "Créer et soumettre") : L("Save draft", "حفظ كمسودة", "Brouillon")) }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, h } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import Icon from "@/components/Icon.vue";
import SearchSelect from "@/components/SearchSelect.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useToast } from "@/composables/useToast";
import { fmtAmount } from "@/utils/helpers";

const props = defineProps({ kind: { type: String, default: "sales" } });
const emit = defineEmits(["close", "posted"]);
const { locale } = useI18n();
const router = useRouter();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => fmtAmount(Number(n) || 0);
const sales = computed(() => props.kind !== "purchase");

const o = ref({ tax_templates: [], accounts: [], cost_centers: [], currencies: [], currency: "" });
const today = new Date().toISOString().slice(0, 10);
const form = reactive({ party: "", posting_date: today, due_date: "", bill_no: "", bill_date: "",
  tax_template: "", currency: "", exchange_rate: "", remarks: "", submit: false });
const newLine = () => ({ item_code: "", qty: 1, rate: 0, account: "", cost_center: "" });
const lines = ref([newLine()]);
const busy = ref(false);
const error = ref("");
const net = computed(() => lines.value.reduce((s, l) => s + (Number(l.qty) || 0) * (Number(l.rate) || 0), 0));
function addLine() { lines.value.push(newLine()); }
function onItem(ln, it) { if (it?.item_name && !ln.rate) ln.description = it.item_name; }

onMounted(async () => {
  try {
    o.value = (await api.call("accounting_portal.api.invoicing.invoice_options", { company: currentCompany(), kind: props.kind })) || o.value;
    form.currency = o.value.currency || "";
    form.tax_template = o.value.default_tax_template || "";
  } catch (e) { error.value = String(e?.message || e).slice(0, 160); }
});

async function save() {
  busy.value = true; error.value = "";
  try {
    const method = sales.value ? "create_sales_invoice" : "create_purchase_invoice";
    const args = { company: currentCompany(), items: lines.value.filter((l) => l.item_code && Number(l.qty) > 0),
      posting_date: form.posting_date, due_date: form.due_date || undefined,
      tax_template: form.tax_template || undefined, currency: form.currency || undefined,
      exchange_rate: form.exchange_rate || undefined, remarks: form.remarks || undefined,
      submit: form.submit ? 1 : 0, client_key: `${Date.now()}` };
    if (sales.value) args.customer = form.party; else { args.supplier = form.party; args.bill_no = form.bill_no || undefined; args.bill_date = form.bill_date || undefined; }
    const r = await api.call(`accounting_portal.api.invoicing.${method}`, args);
    let res = r && r.result; res = typeof res === "string" ? JSON.parse(res) : res;
    toast.success((res?.docstatus === 1 ? L("Invoice submitted", "تم ترحيل الفاتورة", "Facture soumise") : L("Draft created", "أُنشئت المسودة", "Brouillon créé")) + (res?.invoice ? " · " + res.invoice : ""));
    emit("posted", res); emit("close");
    if (res?.invoice) router.push({ path: sales.value ? "/accounting/sales/invoices" : "/accounting/purchases/bills", query: { id: res.invoice } });
  } catch (e) { error.value = String(e?.message || e).slice(0, 220); }
  finally { busy.value = false; }
}

// ── tiny type-ahead pickers (party + item) ──
function makeBox(fetch, labelOf, idOf) {
  return {
    props: { modelValue: { type: String, default: "" }, partyType: { type: String, default: "" } },
    emits: ["update:modelValue", "picked"],
    setup(p, { emit: em }) {
      const hits = ref([]); const open = ref(false); let t = null;
      function onInput(ev) {
        const q = ev.target.value; em("update:modelValue", q); open.value = true;
        clearTimeout(t); t = setTimeout(async () => { hits.value = await fetch(q, p.partyType); }, 220);
      }
      function pick(x) { em("update:modelValue", idOf(x)); em("picked", x); open.value = false; hits.value = []; }
      return () => h("div", { class: "relative" }, [
        h("input", { value: p.modelValue, dir: "ltr", placeholder: "…",
          class: "h-8 w-full min-w-[180px] rounded-[8px] border border-line-2 px-2 text-[12px] bg-white focus:outline-none focus:border-accent/40",
          onInput, onFocus: () => { if (hits.value.length) open.value = true; }, onBlur: () => setTimeout(() => (open.value = false), 150) }),
        open.value && hits.value.length
          ? h("div", { class: "absolute z-40 mt-1 start-0 w-80 max-h-56 overflow-auto bg-white border border-line rounded-[10px] shadow-pop py-1" },
              hits.value.map((x) => h("button", { type: "button", class: "w-full text-start px-3 py-1.5 text-[12px] hover:bg-app-warm",
                onMousedown: (e) => { e.preventDefault(); pick(x); } }, labelOf(x))))
          : null,
      ]);
    },
  };
}
const PartyBox = makeBox(
  async (q, pt) => { try { return await api.call("accounting_portal.api.accountant.party_options", { party_type: pt, q, limit: 12 }) || []; } catch { return []; } },
  (x) => `${x.label || ""} — ${x.name}`, (x) => x.name);
const ItemBox = makeBox(
  async (q) => { try { return await api.call("accounting_portal.api.items.item_options", { search: q, limit: 12 }) || []; } catch { return []; } },
  (x) => `${x.sku ? x.sku + " · " : ""}${x.item_name || x.item_code}`, (x) => x.item_code);
</script>
