<template>
  <!-- Closed: the offer. The Desk shows "Create a new Item" under a link field
       that matched nothing; this is that, and it also shows when there ARE hits,
       because "similar name, different article" is the common case on a
       supplier's invoice. -->
  <button v-if="!qi.form.value" type="button"
          class="w-full text-start px-3 py-2 text-[11px] font-semibold text-accent hover:bg-app-warm border-t border-line-hair"
          @mousedown.prevent="qi.open(q)">
    + {{ hasHits ? L("Create a new item", "إنشاء صنف جديد", "Créer un article") : L("Not found — create", "غير موجود — أنشئه", "Introuvable — créer") }}
    <span class="font-mono">« {{ q }} »</span>
  </button>

  <!-- Open: four fields, which is all a non-stock item needs. -->
  <div v-else class="border-t border-line-hair p-3 space-y-2" @mousedown.prevent>
    <div class="text-[12px] font-semibold">{{ L("New item", "صنف جديد", "Nouvel article") }}</div>
    <input v-model="qi.form.value.item_code" :placeholder="L('Code','الكود','Code')" :class="INP" dir="ltr" />
    <input v-model="qi.form.value.item_name" :placeholder="L('Name','الاسم','Nom')" :class="INP" />
    <select v-model="qi.form.value.item_group" :class="INP">
      <option v-for="g in qi.opts.value.groups" :key="g" :value="g">{{ g }}</option>
    </select>
    <select v-model="qi.form.value.uom" :class="INP">
      <option v-for="u in qi.opts.value.uoms" :key="u" :value="u">{{ u }}</option>
    </select>
    <div v-if="qi.error.value" class="text-[11px] text-sale">{{ qi.error.value }}</div>
    <div class="text-[11px] text-ink-muted leading-relaxed">
      {{ L("Created as a non-stock item. Anything that moves through a warehouse belongs in Items.",
            "بيتعمل كصنف غير مخزني. أي حاجة بتتحرك في مخزن مكانها شاشة الأصناف.",
            "Créé comme article hors stock.") }}
    </div>
    <div class="flex justify-end gap-2">
      <UiButton variant="quiet" size="sm" @click="qi.close()">{{ L("Back", "رجوع", "Retour") }}</UiButton>
      <UiButton variant="primary" size="sm" :busy="qi.busy.value" @click="make">
        {{ L("Create and use", "أنشئ واستخدم", "Créer et utiliser") }}
      </UiButton>
    </div>
  </div>
</template>

<script setup>
// The offer to create the article you just failed to find, in one place.
//
// It existed only inside DraftEditor's picker — so it was there when you edited
// a draft bill and missing from every screen where you actually key a NEW bill:
// the New invoice/bill modal, the purchase-order form, the sales-order form.
// Three copies of the same twenty lines was the reason it never spread; one
// component is.
import { useI18n } from "vue-i18n";
import UiButton from "@/components/UiButton.vue";
import { useQuickItem } from "@/utils/quickItem";

const props = defineProps({
  q: { type: String, default: "" },
  hasHits: { type: Boolean, default: false },
});
const emit = defineEmits(["created"]);
const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const qi = useQuickItem();
const INP = "h-8 w-full rounded-[8px] border border-line-2 px-2 text-[12px] bg-white focus:outline-none focus:border-accent/40";

async function make() {
  const made = await qi.create();
  if (made) emit("created", made);
}
defineExpose({ close: qi.close });
</script>
