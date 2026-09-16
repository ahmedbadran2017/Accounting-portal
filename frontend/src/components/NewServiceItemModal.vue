<template>
  <div v-if="open" class="fixed inset-0 z-50 grid place-items-center bg-ink/30 p-4" @click.self="$emit('close')">
    <div class="bg-white rounded-card shadow-pop w-full max-w-lg p-5 space-y-3">
      <div class="text-[14px] font-bold flex items-center gap-2"><Icon name="plus" :size="14" color="#0b5c4f" />{{ L("New service item", "صنف خدمة جديد", "Nouvel article de service") }}</div>
      <p class="text-[11px] text-ink-muted">{{ L("A non-stock item for bills: fees, taxes, insurance, subscriptions. Product items still come from Shopify.", "صنف غير مخزني للفواتير: رسوم، ضرائب، تأمين، اشتراكات. أصناف المنتجات لسه من Shopify.", "Article hors stock pour les factures.") }}</p>
      <div class="grid grid-cols-2 gap-2">
        <div class="col-span-2"><label class="block text-[11px] font-bold text-ink-3 mb-1">{{ L("Item code / name", "كود الصنف / الاسم", "Code / nom") }} *</label><input v-model.trim="f.item_code" class="h-9 w-full rounded-[9px] border border-line-2 px-2.5 text-[12.5px] bg-white" /></div>
        <div><label class="block text-[11px] font-bold text-ink-3 mb-1">{{ L("Group", "المجموعة", "Groupe") }} *</label><select v-model="f.item_group" class="h-9 w-full rounded-[9px] border border-line-2 px-2 text-[12.5px] bg-white"><option v-for="g in o.groups" :key="g" :value="g">{{ g }}</option></select></div>
        <div><label class="block text-[11px] font-bold text-ink-3 mb-1">{{ L("Unit", "الوحدة", "Unité") }}</label><select v-model="f.uom" class="h-9 w-full rounded-[9px] border border-line-2 px-2 text-[12.5px] bg-white"><option v-for="u in o.uoms" :key="u" :value="u">{{ u }}</option></select></div>
      </div>
      <div v-if="(o.companies || []).length">
        <label class="block text-[11px] font-bold text-ink-3 mb-1">{{ L("Default expense account (per company, optional)", "حساب المصروف الافتراضي (لكل شركة، اختياري)", "Compte de charge par défaut") }}</label>
        <div class="space-y-1.5">
          <div v-for="c in o.companies" :key="c" class="grid grid-cols-[150px_1fr] gap-2 items-center">
            <span class="text-[11.5px] text-ink-2 truncate">{{ c }}</span>
            <SearchSelect v-model="f.defaults[c]" :items="o.expense_accounts?.[c] || []" :placeholder="L('none','بدون','aucun')" inputClass="h-8 text-[12px] bg-white" />
          </div>
        </div>
      </div>
      <p v-if="err" class="text-[12px] text-sale">{{ err }}</p>
      <div class="flex gap-2 justify-end pt-1">
        <button @click="$emit('close')" class="h-9 px-3 rounded-[9px] text-[12px] font-semibold text-ink-3 hover:bg-app-warm">{{ L("Cancel", "إلغاء", "Annuler") }}</button>
        <button @click="save" :disabled="busy || !f.item_code || !f.item_group" class="h-9 px-4 rounded-[9px] text-[12px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand disabled:opacity-50">{{ busy ? "…" : L("Create", "إنشاء", "Créer") }}</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, watch } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import SearchSelect from "@/components/SearchSelect.vue";
import api from "@/services/api";
import { useToast } from "@/composables/useToast";

const props = defineProps({ open: { type: Boolean, default: false } });
const emit = defineEmits(["close", "created"]);
const { locale } = useI18n();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

const o = ref({ groups: [], uoms: [], companies: [], expense_accounts: {} });
const f = reactive({ item_code: "", item_group: "Service", uom: "Nos", defaults: {} });
const busy = ref(false); const err = ref("");

watch(() => props.open, async (v) => {
  if (!v) return;
  err.value = ""; Object.assign(f, { item_code: "", item_group: "Service", uom: "Nos", defaults: {} });
  try { o.value = (await api.call("accounting_portal.api.items.service_item_options", {})) || o.value; } catch { /* */ }
  if (!o.value.groups.includes(f.item_group)) f.item_group = o.value.groups[0] || "";
});

async function save() {
  busy.value = true; err.value = "";
  try {
    const r = await api.call("accounting_portal.api.items.create_service_item", { item_code: f.item_code, item_name: f.item_code, item_group: f.item_group, uom: f.uom, defaults: f.defaults });
    let res = r && r.result; res = typeof res === "string" ? JSON.parse(res) : res;
    toast.success(L("Item created", "تم إنشاء الصنف", "Article créé") + (res?.item ? " · " + res.item : ""));
    emit("created", res?.item); emit("close");
  } catch (e) { err.value = String(e?.message || e).slice(0, 200); }
  finally { busy.value = false; }
}
</script>
