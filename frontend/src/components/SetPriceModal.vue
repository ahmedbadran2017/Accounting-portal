<template>
  <div v-if="open" class="fixed inset-0 z-[110] flex items-start justify-center p-4 overflow-y-auto" style="background:rgba(28,25,23,.45)" @click.self="$emit('close')">
    <div class="bg-white rounded-[16px] shadow-cardHover w-full max-w-md my-8">
      <div class="flex items-center gap-2.5 px-5 py-3.5 border-b border-line">
        <span class="w-8 h-8 rounded-[10px] grid place-items-center" style="background:#faf6f4"><Icon name="scale" :size="16" color="#0b5c4f" /></span>
        <div class="text-[14px] font-bold">{{ L("Set item price","تعيين سعر صنف","Définir un prix") }}</div>
        <button class="ms-auto h-8 w-8 grid place-items-center rounded-[8px] text-ink-3 hover:bg-app-warm" @click="$emit('close')">✕</button>
      </div>
      <div class="p-5 space-y-3">
        <!-- Item picker -->
        <div>
          <label class="text-[11px] font-bold text-ink-3">{{ L("Item","الصنف","Article") }}</label>
          <div v-if="picked" class="flex items-center gap-2 mt-1 h-9 px-2.5 border border-line-2 rounded-[9px] bg-app-warm/40">
            <span class="font-mono text-[11px] text-ink-2 truncate">{{ picked.sku || picked.item_code }}</span>
            <span class="text-[11.5px] truncate flex-1">{{ picked.item_name }}</span>
            <button class="text-ink-muted hover:text-ink" @click="picked = null">✕</button>
          </div>
          <div v-else class="relative">
            <input v-model.trim="q" @input="onSearch" :placeholder="L('Search SKU / item…','بحث…','Rechercher…')" class="w-full h-9 mt-1 border border-line-2 rounded-[9px] px-2.5 text-[12.5px] focus:outline-none focus:border-accent/40" />
            <div v-if="opts.length" class="absolute z-10 top-full inset-x-0 mt-1 bg-white border border-line rounded-[10px] shadow-card max-h-52 overflow-y-auto">
              <button v-for="o in opts" :key="o.item_code" @click="pick(o)" class="w-full text-start px-3 py-2 hover:bg-app-warm border-b border-line-hair last:border-0">
                <span class="block text-[12px] font-medium truncate">{{ o.item_name }}</span>
                <span class="block text-[10px] text-ink-muted font-mono">{{ o.sku || o.item_code }}</span>
              </button>
            </div>
          </div>
        </div>
        <!-- Price list -->
        <div>
          <label class="text-[11px] font-bold text-ink-3">{{ L("Price list","القائمة","Liste") }}</label>
          <select v-model="priceList" class="w-full h-9 mt-1 border border-line-2 rounded-[9px] px-2 text-[12.5px] bg-white focus:outline-none focus:border-accent/40">
            <option v-for="pl in lists" :key="pl.name" :value="pl.name">{{ pl.name }} ({{ pl.currency }}{{ pl.selling ? " · sell" : "" }}{{ pl.buying ? " · buy" : "" }})</option>
          </select>
        </div>
        <!-- Rate -->
        <div>
          <label class="text-[11px] font-bold text-ink-3">{{ L("Rate","السعر","Prix") }}</label>
          <input v-model.number="rate" type="number" min="0" step="0.01" class="w-full h-9 mt-1 border border-line-2 rounded-[9px] px-2.5 text-[12.5px] text-end tnum focus:outline-none focus:border-accent/40" />
        </div>
        <div v-if="error" class="text-[11.5px] text-sale">{{ error }}</div>
        <div class="flex justify-end gap-2 pt-1">
          <button class="px-3.5 py-2 rounded-chip text-[12px] font-semibold text-ink-2 hover:bg-app-warm" @click="$emit('close')">{{ L("Cancel","إلغاء","Annuler") }}</button>
          <button class="px-4 py-2 rounded-chip text-[12px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand disabled:opacity-50" :disabled="busy || !picked || !priceList || !rate" @click="submit">
            {{ busy ? L("Saving…","جارٍ…","…") : L("Save price","حفظ السعر","Enregistrer") }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import api from "@/services/api";
import { useToast } from "@/composables/useToast";

const props = defineProps({ open: Boolean, presetList: String });
const emit = defineEmits(["close", "done"]);
const { locale } = useI18n();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

const q = ref("");
const opts = ref([]);
const picked = ref(null);
const lists = ref([]);
const priceList = ref("");
const rate = ref(null);
const busy = ref(false);
const error = ref("");
let t = null;

watch(() => props.open, async (o) => {
  if (!o) return;
  q.value = ""; opts.value = []; picked.value = null; rate.value = null; error.value = "";
  if (!lists.value.length) { try { lists.value = await api.call("accounting_portal.api.items.list_price_lists", {}); } catch { lists.value = []; } }
  priceList.value = props.presetList || (lists.value[0] && lists.value[0].name) || "";
});

function onSearch() {
  clearTimeout(t);
  t = setTimeout(async () => {
    if (q.value.length < 2) { opts.value = []; return; }
    try { opts.value = await api.call("accounting_portal.api.items.item_options", { search: q.value }); } catch { opts.value = []; }
  }, 300);
}
function pick(o) { picked.value = o; opts.value = []; q.value = ""; }

async function submit() {
  error.value = ""; busy.value = true;
  try {
    const r = await api.call("accounting_portal.api.items.set_item_price", { item_code: picked.value.item_code, price_list: priceList.value, rate: rate.value });
    toast.success(r.updated ? L("Price updated", "تم تحديث السعر", "Prix mis à jour") : L("Price added", "تمت إضافة السعر", "Prix ajouté"));
    emit("done"); emit("close");
  } catch (e) { error.value = String((e && e.message) || L("Failed", "فشل", "Échec")).slice(0, 150); }
  finally { busy.value = false; }
}
</script>
