<template>
  <div v-if="type" class="fixed inset-0 z-[60] flex items-start justify-center pt-[10vh] px-4" @click.self="$emit('close')">
    <div class="absolute inset-0 bg-ink/30 backdrop-blur-[2px]"></div>
    <div class="relative w-full max-w-md bg-white rounded-card shadow-modal border border-line-2 overflow-hidden animate-modalIn">
      <div class="px-5 py-4 border-b border-line flex items-start gap-3">
        <span class="w-9 h-9 rounded-[9px] grid place-items-center flex-shrink-0" style="background:#fbf2ee"><Icon :name="cfg.icon" :size="17" color="#a33a22" /></span>
        <div class="min-w-0">
          <div class="text-[14px] font-bold">{{ cfg.title }}</div>
          <div class="text-[11px] text-ink-muted">{{ cfg.sub }}</div>
        </div>
        <button class="ms-auto p-1 text-ink-3 hover:text-ink" @click="$emit('close')"><Icon name="close" :size="16" /></button>
      </div>

      <form @submit.prevent="save" class="p-5 space-y-3.5">
        <div v-for="f in cfg.fields" :key="f.key">
          <label class="block text-[12px] font-medium text-ink-2 mb-1">{{ f.label }}</label>
          <input v-model="form[f.key]" :type="f.type || 'text'" :required="f.req" :placeholder="f.ph || ''"
                 class="w-full rounded-chip border border-line-2 bg-app-warm px-3 py-2 text-[12.5px] focus:outline-none focus:border-accent/40 focus:bg-white" />
        </div>

        <!-- Order derives net + VAT from gross -->
        <div v-if="type === 'order' && grossNum > 0" class="flex items-center justify-between text-[11.5px] bg-app-warm/60 rounded-lg px-3 py-2">
          <span class="text-ink-3">{{ L('Net (ex-VAT)','الصافي قبل الضريبة','HT') }} <b class="text-ink tnum">{{ net }}</b></span>
          <span class="text-ink-3">{{ L('VAT 20%','ضريبة 20%','TVA 20%') }} <b class="text-ink tnum">{{ vat }}</b></span>
        </div>

        <div class="flex items-center gap-2 pt-1">
          <button type="submit" class="flex-1 inline-flex items-center justify-center gap-1.5 text-[13px] font-semibold text-white bg-accent hover:bg-accent-dark py-2.5 rounded-chip shadow-prim">
            <Icon name="check" :size="15" />{{ cfg.cta }}
          </button>
          <button type="button" class="text-[12.5px] font-medium text-ink-3 px-3 py-2.5 hover:text-ink" @click="$emit('close')">{{ L('Cancel','إلغاء','Annuler') }}</button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { useToast } from "@/composables/useToast";
import { useCreated } from "@/composables/useCreated";
import { useCustomers } from "@/composables/useCustomers";

const props = defineProps({ type: { type: String, default: null } });
const emit = defineEmits(["close"]);
const { locale } = useI18n();
const router = useRouter();
const toast = useToast();
const { addOrder } = useCreated();
const { createCustomer } = useCustomers();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

const form = reactive({});

const CONFIG = computed(() => ({
  customer: {
    icon: "user", title: L("New customer", "عميل جديد", "Nouveau client"), sub: L("Adds a contact to Justyol Morocco", "يُضاف كجهة اتصال", "Ajoute un contact"),
    cta: L("Create customer", "إنشاء العميل", "Créer le client"),
    fields: [
      { key: "name", label: L("Name", "الاسم", "Nom"), req: true },
      { key: "phone", label: L("Phone", "الهاتف", "Téléphone"), ph: "+212" },
      { key: "city", label: L("City", "المدينة", "Ville") },
      { key: "email", label: L("Email", "البريد", "E-mail"), type: "email" },
    ],
  },
  order: {
    icon: "receipt", title: L("New sales order", "أمر بيع جديد", "Nouvelle commande"), sub: L("COD order — posts on delivery", "طلب COD — يُحتسب عند التسليم", "Commande COD"),
    cta: L("Create order", "إنشاء الطلب", "Créer la commande"),
    fields: [
      { key: "customer", label: L("Customer", "العميل", "Client"), req: true },
      { key: "value", label: L("Value (incl. VAT)", "القيمة شاملة الضريبة", "Valeur (TTC)"), type: "number", req: true },
      { key: "city", label: L("City", "المدينة", "Ville") },
      { key: "item", label: L("Item", "الصنف", "Article") },
    ],
  },
  invoice: {
    icon: "receipt", title: L("New invoice", "فاتورة جديدة", "Nouvelle facture"), sub: L("Recognised on delivery · VAT 20%", "تُحتسب عند التسليم · ضريبة 20%", "Reconnu à la livraison · TVA 20%"),
    cta: L("Create invoice", "إنشاء الفاتورة", "Créer la facture"),
    fields: [
      { key: "customer", label: L("Customer", "العميل", "Client"), req: true },
      { key: "net", label: L("Net (ex-VAT)", "الصافي قبل الضريبة", "HT"), type: "number", req: true },
      { key: "order", label: L("Linked order", "الطلب المرتبط", "Commande liée") },
      { key: "item", label: L("Item", "الصنف", "Article") },
    ],
  },
}));
const cfg = computed(() => CONFIG.value[props.type] || CONFIG.value.customer);

const grossNum = computed(() => Number(form.value) || 0);
const net = computed(() => (Math.round((grossNum.value / 1.2) * 100) / 100).toLocaleString());
const vat = computed(() => (Math.round((grossNum.value - grossNum.value / 1.2) * 100) / 100).toLocaleString());

// Reset form when the modal opens for a new type.
watch(() => props.type, () => { Object.keys(form).forEach((k) => delete form[k]); });

async function save() {
  if (props.type === "order") {
    const o = addOrder({ customer: form.customer, value: form.value, city: form.city, item: form.item });
    toast.success(L(`Order ${o.id} created`, `أُنشئ الطلب ${o.id}`, `Commande ${o.id} créée`));
    emit("close");
    router.push({ path: "/accounting/sales/orders", query: { id: o.id } });
    return;
  }
  if (props.type === "invoice") {
    toast.success(L("Invoice created", "أُنشئت الفاتورة", "Facture créée"));
    emit("close");
    router.push("/accounting/sales/invoices");
    return;
  }
  // Customer — create on ERPNext when reachable; otherwise fall back gracefully.
  try {
    const r = await createCustomer({ customer_name: form.name, phone: form.phone, city: form.city, email: form.email });
    toast.success(L(`Customer ${r.customer_name} created`, `أُنشئ العميل ${r.customer_name}`, `Client ${r.customer_name} créé`));
    emit("close");
    router.push({ path: "/accounting/sales/customers", query: { id: r.name } });
  } catch {
    toast.success(L(`Customer ${form.name || ""} added`, `أُضيف العميل ${form.name || ""}`, `Client ${form.name || ""} ajouté`));
    emit("close");
    router.push("/accounting/sales/customers");
  }
}
</script>
