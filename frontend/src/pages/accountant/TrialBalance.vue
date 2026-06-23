<template>
  <div class="bg-white rounded-[14px] border border-line shadow-card overflow-hidden">
    <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair">
      <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#ecfdf5"><Icon name="list" :size="14" color="#047857" /></span>
      <span class="text-[13px] font-bold">{{ L("Trial balance","ميزان المراجعة","Balance") }}</span>
      <span class="text-[11px] text-ink-muted">{{ L("Net balance per account · reconciled to the GL","الرصيد الصافي لكل حساب · مطابق للأستاذ","Solde net par compte · rapproché au GL") }}</span>
    </div>
    <div class="overflow-x-auto">
      <table class="w-full text-[12px]">
        <thead>
          <tr class="border-b border-line">
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Code","الرمز","Code") }}</th>
            <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Account","الحساب","Compte") }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Debit","مدين","Débit") }}</th>
            <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Credit","دائن","Crédit") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(r, i) in rows" :key="i" class="border-b border-line-hair" :class="r.anomaly ? 'bg-rose-50/40' : 'hover:bg-app-warm/60'">
            <td class="px-4 py-2.5 font-mono text-ink-3 whitespace-nowrap">{{ r.code }}</td>
            <td class="px-4 py-2.5">
              <span class="inline-flex items-center gap-1.5">{{ r.name }}<Icon v-if="r.anomaly" name="alert" :size="12" color="#be123c" /></span>
            </td>
            <td class="px-4 py-2.5 text-end tnum font-semibold" :class="r.anomaly && r.dr ? 'text-sale' : ''">{{ r.dr || "—" }}</td>
            <td class="px-4 py-2.5 text-end tnum font-semibold" :class="r.anomaly && r.cr ? 'text-sale' : ''">{{ r.cr || "—" }}</td>
          </tr>
        </tbody>
        <tfoot>
          <tr class="border-t-2 border-line-2 font-bold">
            <td class="px-4 py-2.5" colspan="2">{{ L("Total","الإجمالي","Total") }}</td>
            <td class="px-4 py-2.5 text-end tnum">{{ totalDr }}</td>
            <td class="px-4 py-2.5 text-end tnum">{{ totalCr }}</td>
          </tr>
        </tfoot>
      </table>
    </div>
    <div class="px-4 py-2.5 border-t border-line text-[11px] text-amber-700 flex items-start gap-1.5">
      <Icon name="alert" :size="13" color="#b45309" class="flex-shrink-0 mt-px" />
      {{ L("Totals are skewed by the 168.8M 153.01 spike — exclude it to see the operating trial balance.",
            "الإجماليات متأثرة بقفزة 153.01 البالغة ١٦٨٫٨ مليون — استبعدها لرؤية ميزان التشغيل.",
            "Les totaux sont faussés par le pic 153.01 de 168,8M — excluez-le pour la balance d’exploitation.") }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { TRIAL } from "@/data/accountant";
import { liveOrSample, currentCompany } from "@/composables/useLive";

const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

const fmt = (n) => (n ? Number(n).toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 }) : "");
const rows = ref(TRIAL);
const isLive = ref(null);
onMounted(async () => {
  const res = await liveOrSample(
    "accounting_portal.api.ledger.trial_balance", { company: currentCompany() }, () => TRIAL,
    (data) => (data.rows || data).map((r) => ({ code: r.code, name: r.name, dr: fmt(r.dr), cr: fmt(r.cr), anomaly: r.anomaly })),
  );
  rows.value = res.data;
  isLive.value = res.live;
});

const sum = (k) => rows.value.reduce((s, r) => s + Number((r[k] || "0").replace(/,/g, "")), 0);
const totalDr = computed(() => sum("dr").toLocaleString("en-US"));
const totalCr = computed(() => sum("cr").toLocaleString("en-US"));
</script>
