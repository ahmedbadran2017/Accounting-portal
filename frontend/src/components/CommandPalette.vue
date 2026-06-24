<template>
  <div v-if="open" class="fixed inset-0 z-[60] flex items-start justify-center pt-[12vh] px-4" @click.self="$emit('close')">
    <div class="absolute inset-0 bg-ink/30 backdrop-blur-[2px]"></div>
    <div class="relative w-full max-w-lg bg-white rounded-card shadow-modal border border-line-2 overflow-hidden animate-modalIn">
      <div class="flex items-center gap-2 px-4 border-b border-line">
        <Icon name="search" :size="16" color="#a8a29e" />
        <input ref="box" v-model="q" :placeholder="L('Jump to… orders, journals, COD remittance','اذهب إلى… طلبات، قيود، تحصيل','Aller à… commandes, écritures…')"
               class="flex-1 py-3 text-[13px] bg-transparent focus:outline-none"
               @keydown.down.prevent="move(1)" @keydown.up.prevent="move(-1)" @keydown.enter.prevent="choose(items[active])" @keydown.esc="$emit('close')" />
        <kbd class="text-[10px] text-ink-muted border border-line-2 rounded px-1.5 py-0.5">esc</kbd>
      </div>
      <div ref="list" class="max-h-[52vh] overflow-y-auto p-2">
        <button v-for="(it, i) in items" :key="it.key"
                class="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-start"
                :class="i === active ? 'bg-app-warm' : 'hover:bg-app-warm/60'"
                @mouseenter="active = i" @click="choose(it)">
          <span class="w-7 h-7 rounded-[8px] grid place-items-center flex-shrink-0" :style="{ background: it.create ? '#e7f4f1' : '#faf6f4' }">
            <Icon :name="it.icon" :size="15" :color="it.create ? '#0b5c4f' : '#78716c'" />
          </span>
          <span class="flex-1 min-w-0">
            <span class="block text-[12.5px] font-medium truncate">{{ it.label }}</span>
            <span v-if="it.sub" class="block text-[10.5px] text-ink-muted truncate">{{ it.sub }}</span>
          </span>
          <Icon name="arrow" :size="14" color="#cfc9c4" class="rtl:rotate-180" />
        </button>
        <div v-if="!items.length" class="py-10 text-center text-[12px] text-ink-muted">{{ L('No matches','لا نتائج','Aucun résultat') }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { NAV_GROUPS, SUBTABS } from "@/data/nav";

const props = defineProps({ open: Boolean });
const emit = defineEmits(["close", "create"]);
const { t, locale } = useI18n();
const router = useRouter();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

const q = ref("");
const active = ref(0);
const box = ref(null);
const list = ref(null);

// Flat index: every module + sub-page + the create actions.
const index = computed(() => {
  const out = [];
  out.push({ key: "create-customer", create: true, icon: "user", label: L("Create customer", "إنشاء عميل", "Créer un client"), action: "customer" });
  out.push({ key: "create-order", create: true, icon: "receipt", label: L("Create sales order", "إنشاء أمر بيع", "Créer une commande"), action: "order" });
  out.push({ key: "create-invoice", create: true, icon: "receipt", label: L("Create invoice", "إنشاء فاتورة", "Créer une facture"), action: "invoice" });
  for (const g of NAV_GROUPS) {
    for (const m of g.items) {
      out.push({ key: "m-" + m.id, icon: m.icon, label: t("nav." + m.id), to: `/accounting/${m.id}` });
      for (const s of (SUBTABS[m.id] || [])) {
        out.push({ key: `s-${m.id}-${s[0]}`, icon: m.icon, label: t(s[1]), sub: t("nav." + m.id), to: `/accounting/${m.id}/${s[0]}` });
      }
    }
  }
  out.push({ key: "copilot", icon: "shield", label: t("nav.copilot"), to: "/accounting/copilot" });
  return out;
});

const items = computed(() => {
  const s = q.value.trim().toLowerCase();
  if (!s) return index.value;
  return index.value.filter((it) => (it.label + " " + (it.sub || "")).toLowerCase().includes(s));
});

watch(() => props.open, (v) => { if (v) { q.value = ""; active.value = 0; nextTick(() => box.value?.focus()); } });
watch(items, () => { active.value = 0; });

function move(d) {
  if (!items.value.length) return;
  active.value = (active.value + d + items.value.length) % items.value.length;
  nextTick(() => list.value?.children[active.value]?.scrollIntoView({ block: "nearest" }));
}
function choose(it) {
  if (!it) return;
  emit("close");
  if (it.action) emit("create", it.action);
  else if (it.to) router.push(it.to);
}
</script>
