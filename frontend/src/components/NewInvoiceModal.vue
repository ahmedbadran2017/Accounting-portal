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
            <input type="date" v-model="form.posting_date" class="h-9 w-full rounded-[9px] border border-line-2 px-2.5 text-[13px] bg-white" /></div>
          <div><label class="block text-[11px] font-bold text-ink-3 mb-1">{{ L("Due date", "الاستحقاق", "Échéance") }}</label>
            <input type="date" v-model="form.due_date" class="h-9 w-full rounded-[9px] border border-line-2 px-2.5 text-[13px] bg-white" /></div>

          <template v-if="!sales">
            <div><label class="block text-[11px] font-bold text-ink-3 mb-1">{{ L("Supplier invoice no", "رقم فاتورة المورّد", "N° facture fourn.") }}</label>
              <input v-model.trim="form.bill_no" class="h-9 w-full rounded-[9px] border border-line-2 px-2.5 text-[13px] bg-white" /></div>
            <div><label class="block text-[11px] font-bold text-ink-3 mb-1">{{ L("Supplier invoice date", "تاريخ فاتورة المورّد", "Date facture") }}</label>
              <input type="date" v-model="form.bill_date" class="h-9 w-full rounded-[9px] border border-line-2 px-2.5 text-[13px] bg-white" /></div>
          </template>

          <div><label class="block text-[11px] font-bold text-ink-3 mb-1">{{ L("VAT", "الضريبة", "TVA") }}</label>
            <select v-model="vatMode" class="h-9 w-full rounded-[9px] border border-line-2 px-2 text-[13px] bg-white">
              <option value="none">{{ L("No tax", "بدون ضريبة", "Sans taxe") }}</option>
              <option value="template">{{ L("A rate on everything", "نسبة على الكل", "Un taux sur tout") }}</option>
              <option value="amount">{{ L("The amount on the invoice", "المبلغ المكتوب في الفاتورة", "Le montant figurant") }}</option>
            </select></div>
          <div><label class="block text-[11px] font-bold text-ink-3 mb-1">{{ L("Currency", "العملة", "Devise") }}</label>
            <select v-model="form.currency" class="h-9 w-full rounded-[9px] border border-line-2 px-2 text-[13px] bg-white">
              <option v-for="c in o.currencies" :key="c" :value="c">{{ c }}</option>
            </select></div>
          <div v-if="form.currency && form.currency !== o.currency">
            <label class="block text-[11px] font-bold text-ink-3 mb-1">{{ L("Exchange rate", "سعر الصرف", "Taux") }}</label>
            <input type="number" step="any" v-model="form.exchange_rate" dir="ltr" class="h-9 w-full rounded-[9px] border border-line-2 px-2.5 text-[13px] bg-white tnum" /></div>
        </div>

        <!-- lines -->
        <div class="border border-line rounded-[12px] overflow-hidden">
          <div class="px-3 py-2 border-b border-line-hair flex items-center gap-2 text-[12px] font-bold">
            <Icon name="list" :size="13" color="#0b5c4f" />{{ L("Items", "الأصناف", "Articles") }}
            <span class="ms-auto text-[12px] tnum text-ink-3">{{ L("Net", "الصافي", "HT") }} {{ fmt(net) }} {{ form.currency || o.currency }}</span>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full text-[12px]">
              <thead><tr class="text-[11px] font-bold uppercase tracking-wider text-ink-muted" style="background:#fafaf9">
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
            <button type="button" class="inline-flex items-center gap-1 text-[12px] font-semibold text-accent hover:text-accent-dark" @click="addLine"><Icon name="plus" :size="12" />{{ L("Add line", "إضافة سطر", "Ajouter") }}</button>
          </div>
        </div>

        <!-- VAT. A percentage template cannot reproduce an invoice that mixes
             rates — an exempt sea-freight line beside taxed local charges — so
             the amount printed on the paper can be typed instead, and the strip
             below is what gets ticked against it. -->
        <div v-if="vatMode !== 'none'" class="border border-line rounded-[12px] p-3 space-y-2.5">
          <div v-if="vatMode === 'template'" class="grid sm:grid-cols-2 gap-3">
            <div><label class="block text-[11px] font-bold text-ink-3 mb-1">{{ L("Tax template", "قالب الضريبة", "Modèle") }}</label>
              <select v-model="form.tax_template" class="h-9 w-full rounded-[9px] border border-line-2 px-2 text-[13px] bg-white">
                <option value="">{{ L("Choose…", "اختر…", "Choisir…") }}</option>
                <option v-for="t in o.tax_templates" :key="t" :value="t">{{ t }}</option>
              </select></div>
          </div>
          <div v-else class="grid sm:grid-cols-2 gap-3">
            <div><label class="block text-[11px] font-bold text-ink-3 mb-1">{{ L("VAT amount on the invoice", "مبلغ الضريبة في الفاتورة", "Montant de TVA") }}</label>
              <input type="number" step="any" min="0" v-model="form.vat_amount" dir="ltr"
                     class="h-9 w-full rounded-[9px] border border-line-2 px-2.5 text-[13px] text-end tnum bg-white" /></div>
            <div><label class="block text-[11px] font-bold text-ink-3 mb-1">{{ L("Posts to", "يترحّل إلى", "Compte") }}</label>
              <select v-model="form.vat_account" class="h-9 w-full rounded-[9px] border border-line-2 px-2 text-[13px] bg-white">
                <option v-for="a in vatAccounts" :key="a.value" :value="a.value">{{ a.label }}</option>
              </select></div>
          </div>
          <div class="flex items-center gap-4 flex-wrap text-[12px] pt-0.5 border-t border-line-hair">
            <span class="text-ink-muted">{{ L("Net", "الصافي", "HT") }} <b class="tnum">{{ fmt(net) }}</b></span>
            <span class="text-ink-muted">{{ L("VAT", "الضريبة", "TVA") }} <b class="tnum">{{ fmt(vatShown) }}</b></span>
            <span class="font-bold">{{ L("Total", "الإجمالي", "TTC") }} <span class="tnum">{{ fmt(net + vatShown) }}</span> {{ form.currency || o.currency }}</span>
            <span v-if="vatMode === 'template'" class="text-[11px] text-ink-muted">{{ L("computed on save from the template", "بتتحسب عند الحفظ من القالب", "calculée à l'enregistrement") }}</span>
          </div>
        </div>

        <div><label class="block text-[11px] font-bold text-ink-3 mb-1">{{ L("Remarks", "ملاحظات", "Remarques") }}</label>
          <textarea v-model.trim="form.remarks" rows="2" class="w-full rounded-[9px] border border-line-2 px-2.5 py-1.5 text-[13px] bg-white"></textarea></div>

        <label class="inline-flex items-center gap-2 text-[13px]"><input type="checkbox" v-model="form.submit" /> {{ L("Submit now (otherwise saved as a draft to review)", "رحّلها الآن (وإلا تتحفظ كمسودة للمراجعة)", "Soumettre maintenant") }}</label>
        <p v-if="error" class="text-[12px] text-sale">{{ error }}</p>
      </div>

      <div class="px-5 py-3 border-t border-line-hair flex items-center gap-2">
        <span class="text-[11px] text-ink-muted">{{ vatMode === "amount"
  ? L("The VAT you typed is posted as-is, exactly as on the invoice.", "مبلغ الضريبة اللي كتبتيه بيتسجّل زي ما هو، مطابق للفاتورة.", "La TVA saisie est comptabilisée telle quelle.")
  : L("Taxes are applied by the selected template on save.", "الضريبة بتتحسب من القالب عند الحفظ.", "Les taxes viennent du modèle.") }}</span>
        <div class="ms-auto flex gap-2">
          <UiButton variant="quiet" @click="$emit('close')">{{ L("Cancel", "إلغاء", "Annuler") }}</UiButton>
          <UiButton variant="primary" :busy="busy" :disabled="busy || !form.party || !net" @click="save">
            {{ busy ? "…" : (form.submit ? L("Create & submit", "إنشاء وترحيل", "Créer et soumettre") : L("Save draft", "حفظ كمسودة", "Brouillon")) }}
          </UiButton>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, h, Teleport } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import Icon from "@/components/Icon.vue";
import UiButton from "@/components/UiButton.vue";
import SearchSelect from "@/components/SearchSelect.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useToast } from "@/composables/useToast";
import { fmtAmount } from "@/utils/helpers";
import { useAnchoredMenu } from "@/utils/anchoredMenu";

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
  tax_template: "", currency: "", exchange_rate: "", remarks: "", submit: false,
  vat_amount: "", vat_account: "" });
// "template" = a rate on the whole invoice; "amount" = the figure printed on it.
const vatMode = ref("template");
const vatAccounts = ref([]);
// Only the typed amount is known before the save; a template's VAT is computed
// by ERPNext, and guessing it here would put a number on screen that the saved
// document might not agree with.
const vatShown = computed(() => (vatMode.value === "amount" ? Number(form.vat_amount) || 0 : 0));
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
    vatMode.value = form.tax_template ? "template" : "none";
    const tx = await api.call("accounting_portal.api.invoicing.tax_options",
      { company: currentCompany(), side: sales.value ? "selling" : "buying" }) || {};
    vatAccounts.value = tx.accounts || [];
    form.vat_account = tx.default_account || (vatAccounts.value[0] || {}).value || "";
  } catch (e) { error.value = String(e?.message || e).slice(0, 160); }
});

async function save() {
  busy.value = true; error.value = "";
  try {
    const method = sales.value ? "create_sales_invoice" : "create_purchase_invoice";
    const args = { company: currentCompany(), items: lines.value.filter((l) => l.item_code && Number(l.qty) > 0),
      posting_date: form.posting_date, due_date: form.due_date || undefined,
      tax_template: vatMode.value === "template" ? (form.tax_template || undefined) : undefined,
      vat_amount: vatMode.value === "amount" ? (Number(form.vat_amount) || 0) : undefined,
      vat_account: vatMode.value === "amount" ? (form.vat_account || undefined) : undefined,
      currency: form.currency || undefined,
      exchange_rate: form.exchange_rate || undefined, remarks: form.remarks || undefined,
      submit: form.submit ? 1 : 0, client_key: `${Date.now()}` };
    if (sales.value) args.customer = form.party; else { args.supplier = form.party; args.bill_no = form.bill_no || undefined; args.bill_date = form.bill_date || undefined; }
    const r = await api.call(`accounting_portal.api.invoicing.${method}`, args);
    let res = r && r.result; res = typeof res === "string" ? JSON.parse(res) : res;
    // Above the materiality threshold the gateway files the action for approval
    // instead of posting it — say so, rather than claiming a draft that isn't there.
    if (r?.status === "Proposed") {
      toast.info(L("Sent for approval — nothing posted yet", "أُرسلت للموافقة — لم يتم الترحيل بعد", "Envoyée pour approbation — rien n'est encore comptabilisé"));
      emit("posted", r); emit("close");
      return;
    }
    toast.success((res?.docstatus === 1 ? L("Invoice submitted", "تم ترحيل الفاتورة", "Facture soumise") : L("Draft created", "أُنشئت المسودة", "Brouillon créé")) + (res?.invoice ? " · " + res.invoice : ""));
    emit("posted", res); emit("close");
    if (res?.invoice) router.push({ path: sales.value ? "/accounting/sales/invoices" : "/accounting/purchases/bills", query: { id: res.invoice } });
  } catch (e) { error.value = String(e?.message || e).slice(0, 220); }
  finally { busy.value = false; }
}

// ── tiny type-ahead pickers (party + item) ──
function makeBox(fetch, rowOf, idOf) {
  return {
    props: { modelValue: { type: String, default: "" }, partyType: { type: String, default: "" } },
    emits: ["update:modelValue", "picked"],
    setup(p, { emit: em }) {
      const hits = ref([]); const open = ref(false); let t = null;
      const inputEl = ref(null);
      const { style, place, follow, unfollow } = useAnchoredMenu(360);
      function show() { open.value = true; place(inputEl.value); follow(); }
      function hide() { open.value = false; unfollow(); }
      function onInput(ev) {
        const q = ev.target.value; em("update:modelValue", q); show();
        clearTimeout(t); t = setTimeout(async () => { hits.value = await fetch(q, p.partyType); place(inputEl.value); }, 220);
      }
      function pick(x) { em("update:modelValue", idOf(x)); em("picked", x); hide(); hits.value = []; }
      return () => h("div", { class: "relative" }, [
        h("input", { ref: inputEl, value: p.modelValue, dir: "ltr", placeholder: "…",
          class: "h-8 w-full min-w-[180px] rounded-[8px] border border-line-2 px-2 text-[12px] bg-white focus:outline-none focus:border-accent/40",
          onInput, onFocus: () => { if (hits.value.length) show(); }, onBlur: () => setTimeout(hide, 150) }),
        // to <body>, so the table's overflow cannot cut the list to one row
        open.value && hits.value.length
          ? h(Teleport, { to: "body" }, [
              h("div", { class: "bg-white border border-line rounded-[10px] shadow-pop py-1", style: style.value },
                hits.value.map((x) => h("button", { type: "button", class: "w-full text-start px-3 py-2 text-[12px] hover:bg-app-warm flex items-center gap-2.5",
                  onMousedown: (e) => { e.preventDefault(); pick(x); } }, rowOf(x))))])
          : null,
      ]);
    },
  };
}
const PartyBox = makeBox(
  async (q, pt) => { try { return await api.call("accounting_portal.api.accountant.party_options", { party_type: pt, q, limit: 12 }) || []; } catch { return []; } },
  (x) => [h("span", { class: "truncate" }, `${x.label || ""} — ${x.name}`)], (x) => x.name);
const ItemBox = makeBox(
  async (q) => { try { return await api.call("accounting_portal.api.items.item_options", { search: q, limit: 12 }) || []; } catch { return []; } },
  (x) => [
    x.image ? h("img", { src: x.image, loading: "lazy", class: "w-9 h-9 rounded-[7px] object-cover border border-line flex-shrink-0",
                         onError: (e) => { e.target.style.display = "none"; } })
            : h("span", { class: "w-9 h-9 rounded-[7px] bg-app-warm border border-line flex-shrink-0" }),
    h("span", { class: "min-w-0 flex-1" }, [
      h("span", { class: "block truncate" }, x.item_name || x.item_code),
      h("span", { class: "block text-[11px] text-ink-muted font-mono truncate" }, x.sku ? `${x.item_code} · ${x.sku}` : x.item_code),
      x.variant_of_name ? h("span", { class: "block text-[11px] text-ink-muted truncate" }, "↳ " + x.variant_of_name) : null,
    ]),
  ], (x) => x.item_code);
</script>
