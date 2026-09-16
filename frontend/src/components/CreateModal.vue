<template>
  <div v-if="type" class="fixed inset-0 z-[60] flex items-start justify-center pt-[10vh] px-4" @click.self="$emit('close')">
    <div class="absolute inset-0 bg-ink/30 backdrop-blur-[2px]"></div>
    <div class="relative w-full max-w-md bg-white rounded-card shadow-modal border border-line-2 overflow-hidden animate-modalIn">
      <div class="px-5 py-4 border-b border-line flex items-start gap-3">
        <span class="w-9 h-9 rounded-[9px] grid place-items-center flex-shrink-0" style="background:#e7f4f1"><Icon :name="cfg.icon" :size="17" color="#0b5c4f" /></span>
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

        <div class="flex items-center gap-2 pt-1">
          <button type="submit" class="flex-1 inline-flex items-center justify-center gap-1.5 text-[13px] font-semibold text-white bg-brand hover:bg-brand-dark py-2.5 rounded-chip shadow-brand">
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
import { useCustomers } from "@/composables/useCustomers";

const props = defineProps({ type: { type: String, default: null } });
const emit = defineEmits(["close"]);
const { locale } = useI18n();
const router = useRouter();
const toast = useToast();
const { createCustomer } = useCustomers();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

const form = reactive({});
const saving = ref(false);

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
}));
const cfg = computed(() => CONFIG.value[props.type] || CONFIG.value.customer);


// Reset form when the modal opens for a new type.
watch(() => props.type, () => { Object.keys(form).forEach((k) => delete form[k]); });

async function save() {
  // Customer — create on ERPNext. Surface the real error so a failure is visible
  // (don't fake success: that routed to a customer that didn't exist).
  if (saving.value) return;
  saving.value = true;
  try {
    const r = await createCustomer({ customer_name: form.name, phone: form.phone, city: form.city, email: form.email });
    toast.success(L(`Customer ${r.customer_name} created`, `أُنشئ العميل ${r.customer_name}`, `Client ${r.customer_name} créé`));
    emit("close");
    router.push({ path: "/accounting/sales/customers", query: { id: r.name } });
  } catch (e) {
    toast.error((e && e.message) || L("Couldn't create the customer.", "تعذّر إنشاء العميل.", "Échec de la création."));
  } finally {
    saving.value = false;
  }
}
</script>
