<template>
  <div class="space-y-3.5">
    <div class="flex items-center gap-2 flex-wrap">
      <span v-if="isLive !== null" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full border"
            :style="isLive ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fffbeb;color:#b45309;border-color:#fde68a'">{{ isLive ? "Live" : "Sample" }}</span>
      <span class="text-[11px] text-ink-muted">{{ rows.length }} {{ L("suppliers · ranked by payable","مورّد · مرتّب حسب المستحق","fournisseurs · par dû") }}</span>
      <div class="relative ms-auto">
        <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
        <input v-model.trim="search" :placeholder="L('Search supplier…','بحث عن مورّد…','Rechercher…')" class="w-48 sm:w-64 h-9 bg-white border border-line-2 rounded-[10px] ps-9 pe-3 text-[12.5px] focus:outline-none focus:border-accent/40" />
      </div>
    </div>

    <div class="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
      <div v-for="(v, i) in filtered" :key="v.name" class="yo-card text-start bg-white border border-line rounded-[14px] p-4 shadow-card w-full">
        <div class="flex items-center gap-2.5">
          <span class="w-[30px] h-[30px] rounded-[8px] grid place-items-center text-white text-[9.5px] font-bold flex-shrink-0" :style="{ background: badge(i) }">{{ ini(v.name) }}</span>
          <div class="flex-1 min-w-0">
            <div class="text-[12.5px] font-bold truncate">{{ v.name }}</div>
            <div class="text-[10.5px] text-ink-muted">{{ v.group || "—" }}</div>
          </div>
        </div>
        <div class="text-[20px] font-bold tnum mt-2.5" :class="v.payable < 0 ? 'text-success-dark' : ''">{{ fmt(v.payable) }}<span class="text-[11px] text-ink-muted ms-0.5">{{ v.currency }}</span></div>
        <div class="text-[10.5px] text-ink-muted mt-0.5">{{ v.n_bills }} {{ L("bills · outstanding payable","فاتورة · مستحق","factures · dû") }}</div>
      </div>
    </div>
    <div v-if="!filtered.length" class="py-12 text-center text-[12px] text-ink-muted">{{ L("No suppliers match.","لا موردين مطابقين.","Aucun fournisseur.") }}</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { VENDORS } from "@/data/purchases";
import { liveOrSample, currentCompany } from "@/composables/useLive";

const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => Number(n || 0).toLocaleString("en-US");
const ini = (n) => String(n || "?").trim().split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
const PALETTE = ["#2563eb", "#7c3aed", "#0891b2", "#c2410c", "#16a34a", "#be123c", "#a16207", "#4f46e5"];
const badge = (i) => `linear-gradient(135deg,${PALETTE[i % PALETTE.length]},${PALETTE[(i + 3) % PALETTE.length]})`;

const SAMPLE = VENDORS.map((v) => ({ name: v.name, group: v.place, payable: Number(String(v.payable).replace(/,/g, "")) || 0, currency: v.ccy, n_bills: 0 }));
const rows = ref(SAMPLE);
const isLive = ref(null);
const search = ref("");
const filtered = computed(() => {
  const q = search.value.toLowerCase();
  return q ? rows.value.filter((v) => (v.name + " " + (v.group || "")).toLowerCase().includes(q)) : rows.value;
});

onMounted(async () => {
  const res = await liveOrSample(
    "accounting_portal.api.purchases.list_vendors", { company: currentCompany(), limit: 100 }, () => SAMPLE,
    (data) => data.map((r) => ({ name: r.supplier_name || r.name, group: r.supplier_group, payable: Number(r.payable) || 0, currency: r.currency || "MAD", n_bills: r.n_bills || 0 })),
  );
  rows.value = res.data; isLive.value = res.live;
});
</script>
