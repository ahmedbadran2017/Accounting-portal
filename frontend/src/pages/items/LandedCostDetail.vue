<template>
  <div class="space-y-3.5">
    <button class="inline-flex items-center gap-1.5 text-[12px] font-semibold text-ink-3 hover:text-ink" @click="back">
      <Icon name="arrow" :size="14" class="rtl:rotate-180 rotate-180" />{{ L("Back to landed cost","العودة للتكلفة المحمَّلة","Retour") }}
    </button>
    <div v-if="loading" class="bg-white rounded-card border border-line shadow-card"><TableLoading :rows="4" /></div>
    <template v-else-if="d">
      <!-- Header -->
      <div class="bg-white rounded-card border border-line shadow-card p-5">
        <div class="flex items-start gap-3 flex-wrap">
          <span class="w-11 h-11 rounded-[12px] grid place-items-center flex-shrink-0" style="background:#eff6ff"><Icon name="truck" :size="20" color="#0369a1" /></span>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="text-[16px] font-bold font-mono">{{ d.name }}</span>
              <span class="text-[10px] font-bold px-2 py-0.5 rounded-full" :style="statusBadge(d.status)">{{ d.status }}</span>
            </div>
            <div class="text-[11px] text-ink-muted mt-0.5">{{ d.posting_date }} · {{ L("distributed by","التوزيع حسب","réparti par") }} {{ d.basis }}</div>
          </div>
          <div class="text-end"><div class="text-[22px] font-extrabold tnum">{{ fmt(d.total) }}<span class="text-[12px] text-ink-muted ms-1">MAD</span></div><div class="text-[10.5px] text-ink-muted">{{ L("total charges","إجمالي الرسوم","charges") }}</div></div>
        </div>
        <!-- charges -->
        <div class="flex flex-wrap gap-2 mt-3 pt-3 border-t border-line-hair">
          <div v-for="(c, i) in d.charges" :key="i" class="rounded-[9px] px-3 py-1.5" style="background:#fafaf9;border:1px solid #f0efed">
            <span class="text-[10px] font-bold uppercase tracking-wide" :style="{ color: kindColor(c.kind) }">{{ kindLabel(c.kind) }}</span>
            <span class="text-[12px] font-semibold tnum ms-1.5">{{ fmt(c.amount) }}</span>
            <span class="text-[10px] text-ink-muted ms-1">{{ c.description }}</span>
          </div>
        </div>
        <!-- linked receipts -->
        <div v-if="d.receipts.length" class="flex flex-wrap gap-2 mt-2">
          <button v-for="(r, i) in d.receipts" :key="i" @click="goReceipt(r.doc)" class="text-[11px] font-semibold px-2.5 py-1 rounded-chip bg-app-warm text-ink-2 hover:bg-app-warm/70 inline-flex items-center gap-1"><Icon name="box" :size="12" />{{ r.doc }}<span v-if="r.supplier" class="text-ink-muted"> · {{ r.supplier }}</span></button>
        </div>
      </div>

      <!-- Allocation = the capitalisation into each item's inventory -->
      <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
        <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><Icon name="layers" :size="14" color="#7c3aed" /><span class="text-[12px] font-bold">{{ L("Allocation · capitalised into inventory","التوزيع · يُرسمل في المخزون","Répartition dans le stock") }}</span><span class="text-[10px] text-ink-muted">{{ d.items.length }}</span></div>
        <div class="overflow-x-auto">
          <table class="w-full text-[12px]">
            <thead><tr style="background:#fafaf9">
              <th class="px-4 py-2 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Item","الصنف","Article") }}</th>
              <th class="px-4 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Receipt value","قيمة الاستلام","Valeur") }}</th>
              <th class="px-4 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Allocated","المُوزّع","Alloué") }}</th>
              <th class="px-4 py-2 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Per unit","للوحدة","Par u") }}</th>
            </tr></thead>
            <tbody>
              <tr v-for="(it, i) in d.items" :key="i" class="border-t border-line-hair">
                <td class="px-4 py-2.5">
                  <span class="flex items-center gap-2.5">
                    <img v-if="it.image" :src="it.image" class="w-8 h-8 rounded-[7px] object-cover flex-shrink-0 border border-line-hair" />
                    <span v-else class="w-8 h-8 rounded-[7px] bg-app-warm grid place-items-center flex-shrink-0"><Icon name="box" :size="13" color="#a8a29e" /></span>
                    <span class="min-w-0"><span class="block font-medium truncate max-w-[260px]">{{ it.item_name || it.item_code }}</span><span class="block text-[10px] text-ink-muted">{{ it.qty }} {{ L("units","وحدة","u") }}</span></span>
                  </span>
                </td>
                <td class="px-4 py-2.5 text-end tnum">{{ fmt(it.receipt_value) }} <span class="text-[10px] text-ink-muted">{{ it.share }}%</span></td>
                <td class="px-4 py-2.5 text-end tnum font-semibold text-success-dark">+{{ fmt(it.allocated) }}</td>
                <td class="px-4 py-2.5 text-end tnum">+{{ fmt(it.per_unit) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Capitalisation journal (if posted to GL) -->
      <div v-if="d.journal.length" class="bg-white rounded-card border border-line shadow-card overflow-hidden">
        <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><Icon name="ledger" :size="14" color="#0b5c4f" /><span class="text-[12px] font-bold">{{ L("Capitalisation journal","قيد الرسملة","Écriture de capitalisation") }}</span></div>
        <table class="w-full text-[12px]">
          <tbody>
            <tr v-for="(j, i) in d.journal" :key="i" class="border-t border-line-hair">
              <td class="px-4 py-2 font-mono text-ink-2">{{ j.acc }}</td>
              <td class="px-4 py-2 text-end tnum font-semibold">{{ j.dr ? fmt(j.dr) : "—" }}</td>
              <td class="px-4 py-2 text-end tnum font-semibold">{{ j.cr ? fmt(j.cr) : "—" }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <DocHub v-if="route.query.id" doctype="Landed Cost Voucher" :name="route.query.id" class="mt-1" />
    </template>
  </div>
</template>

<script setup>
import { ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import DocHub from "@/components/DocHub.vue";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";

const route = useRoute();
const router = useRouter();
const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const d = ref(null);
const loading = ref(true);
function back() { router.push("/accounting/items/landed"); }
function goReceipt(doc) { router.push({ path: "/accounting/purchases/received", query: { id: doc } }); }
async function load() {
  const id = route.query.id;
  if (!id) { loading.value = false; return; }
  loading.value = true; d.value = null;
  try { d.value = await api.call("accounting_portal.api.items.get_landed_cost", { name: id }); }
  catch { d.value = null; }
  finally { loading.value = false; }
  if (!d.value) router.replace({ path: "/accounting/items/landed", query: {} });
}
watch(() => route.query.id, load, { immediate: true });

const KIND = {
  freight: { en: "Freight", ar: "الشحن", fr: "Fret", c: "#0369a1" },
  customs: { en: "Customs", ar: "الجمارك", fr: "Douane", c: "#b45309" },
  duties: { en: "Duties", ar: "الرسوم", fr: "Droits", c: "#be123c" },
  insurance: { en: "Insurance", ar: "التأمين", fr: "Assurance", c: "#7c3aed" },
  other: { en: "Other", ar: "أخرى", fr: "Autre", c: "#57534e" },
};
function kindLabel(k) { const x = KIND[k] || KIND.other; return locale.value === "ar" ? x.ar : locale.value === "fr" ? x.fr : x.en; }
function kindColor(k) { return (KIND[k] || KIND.other).c; }
function statusBadge(s) {
  if (s === "Posted") return "background:#ecfdf5;color:#047857";
  if (s === "Cancelled") return "background:#fef2f2;color:#b91c1c";
  return "background:#fffbeb;color:#b45309";
}
</script>
