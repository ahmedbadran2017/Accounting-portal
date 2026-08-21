<template>
  <!-- Who touched this SKU's cost, and what they saved. Merges the gated
       applies, the draft saves and the item-field edits into one timeline. -->
  <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
    <button class="w-full px-4 py-3 flex items-center gap-2 text-start hover:bg-[#fafaf9]" @click="toggle">
      <span class="text-[13px] font-bold">🕘 {{ L("Activity — who did what","السجل — مين عمل إيه","Activité") }}</span>
      <span v-if="counts.apply" class="text-[10px] font-bold px-1.5 py-0.5 rounded-full" style="background:#eef2ff;color:#4338ca">
        {{ counts.apply }} {{ L("applies","تطبيق","applic.") }}
      </span>
      <span v-if="counts.save" class="text-[10px] font-bold px-1.5 py-0.5 rounded-full" style="background:#f0fdf4;color:#15803d">
        {{ counts.save }} {{ L("saves","حفظ","enreg.") }}
      </span>
      <span v-if="counts.edit" class="text-[10px] font-bold px-1.5 py-0.5 rounded-full" style="background:#fefce8;color:#a16207">
        {{ counts.edit }} {{ L("edits","تعديل","modif.") }}
      </span>
      <div class="flex-1"></div>
      <span class="text-[11px] text-ink-muted">{{ open ? "▾" : "▸" }}</span>
    </button>

    <div v-if="open" class="border-t border-line-hair">
      <div v-if="loading" class="px-4 py-6 text-[12px] text-ink-muted">{{ L("Loading…","جاري التحميل…","Chargement…") }}</div>
      <div v-else-if="err" class="px-4 py-6 text-[12px]" style="color:#b91c1c">{{ err }}</div>
      <div v-else-if="!rows.length" class="px-4 py-6 text-[12px] text-ink-muted">
        {{ L("Nothing recorded for this item yet.","مفيش أي حركة متسجلة على الصنف ده.","Aucune activité.") }}
      </div>
      <div v-else class="max-h-[340px] overflow-y-auto divide-y divide-line-hair">
        <div v-for="(r, i) in rows" :key="i" class="px-4 py-2.5 flex items-start gap-3">
          <span class="text-[13px] leading-none mt-0.5">{{ icon(r) }}</span>
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="text-[11.5px] font-bold">{{ title(r) }}</span>
              <span v-if="r.status" class="text-[9.5px] font-bold px-1.5 py-0.5 rounded-full" :style="badge(r.status)">{{ r.status }}</span>
              <span v-if="r.rate" class="text-[11px] tnum font-bold" dir="ltr">{{ fmt(r.rate, 2) }}</span>
              <span v-if="multi" class="text-[10px] text-ink-muted tnum" dir="ltr">{{ r.item }}</span>
            </div>
            <div class="text-[10.5px] text-ink-muted mt-0.5 break-words">
              <span v-if="r.kind === 'apply' && r.anchor" dir="ltr">
                {{ L("from","من","depuis") }} {{ r.anchor }}<span v-if="r.pins"> · {{ r.pins }} {{ L("pin(s)","تثبيت","points") }}</span>
                <span v-if="r.voucher"> · {{ r.voucher }}</span>
              </span>
              <span v-else-if="r.kind === 'edit'" dir="ltr">{{ r.old ?? "—" }} → {{ r.new ?? "—" }}</span>
              <span v-else-if="r.kind === 'save' && r.scope && r.scope !== 'item'" dir="ltr">{{ r.scope }}</span>
              <div v-if="r.note" class="mt-0.5 opacity-80">{{ r.note }}</div>
            </div>
          </div>
          <div class="text-end shrink-0">
            <div class="text-[10px] text-ink-muted tnum" dir="ltr">{{ (r.ts || "").slice(0, 16) }}</div>
            <div class="text-[10px] font-bold truncate max-w-[150px]">{{ who(r.who) }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useI18n } from "vue-i18n";
import api from "@/services/api";

const props = defineProps({
  itemCode: { type: String, default: "" },
  items: { type: Array, default: () => [] },
  startOpen: { type: Boolean, default: false },
});
const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

const open = ref(props.startOpen);
const loading = ref(false);
const err = ref("");
const rows = ref([]);
const counts = ref({});
const loadedKey = ref("");

const multi = computed(() => (props.items || []).length > 1);
const key = computed(() => `${props.itemCode}|${(props.items || []).join(",")}`);
const fmt = (n, d = 0) => new Intl.NumberFormat("en-US", { maximumFractionDigits: d, minimumFractionDigits: d }).format(n || 0);
const who = (u) => (u || "—").split("@")[0];

const icon = (r) => (r.kind === "save" ? "💾" : r.kind === "edit" ? "✏️"
  : r.status === "Reverted" ? "↩️" : r.status === "Failed" ? "⚠️" : "✅");

const title = (r) => {
  if (r.kind === "save") return r.scope && r.scope !== "item"
    ? L("Cost saved (shipment sheet)", "اتحفظت التكلفة (كشف شحنة)", "Coût enregistré")
    : L("Verified cost saved", "اتحفظت التكلفة المحققة", "Coût vérifié enregistré");
  if (r.kind === "edit") return r.title;
  return { "Cost applied": L("Cost applied", "التكلفة اتطبقت", "Coût appliqué"),
           "Apply undone": L("Apply undone", "اتلغى التطبيق", "Annulé"),
           "Apply proposed": L("Apply proposed", "التطبيق مقترح", "Proposé"),
           "Apply failed": L("Apply failed", "التطبيق فشل", "Échec"),
           "Apply rejected": L("Apply rejected", "التطبيق مرفوض", "Rejeté") }[r.title] || r.title;
};

const badge = (s) => ({
  Posted: "background:#ecfdf5;color:#047857",
  Reverted: "background:#f5f5f4;color:#57534e",
  Draft: "background:#f0fdf4;color:#15803d",
  Proposed: "background:#eff6ff;color:#1d4ed8",
  Failed: "background:#fef2f2;color:#b91c1c",
}[s] || "background:#f5f5f4;color:#57534e");

async function load() {
  if (!props.itemCode && !(props.items || []).length) return;
  loading.value = true; err.value = "";
  try {
    const p = props.items && props.items.length
      ? { items: JSON.stringify(props.items) }
      : { item_code: props.itemCode };
    const r = await api.call("accounting_portal.api.item_log.item_activity", p, { fresh: true });
    rows.value = r?.rows || [];
    counts.value = r?.counts || {};
    loadedKey.value = key.value;
  } catch (e) {
    err.value = e?.message || String(e);
  } finally {
    loading.value = false;
  }
}

function toggle() {
  open.value = !open.value;
  if (open.value && loadedKey.value !== key.value) load();
}

// a new item/model while the panel is open reloads it; closed panels stay lazy
watch(key, () => { rows.value = []; counts.value = {}; if (open.value) load(); });
if (props.startOpen) load();

defineExpose({ reload: load });
</script>
