<template>
  <div class="space-y-3.5">
    <div class="rounded-[14px] px-4 py-3 border" style="background:#eff6ff;border-color:#bfdbfe">
      <div class="text-[12px] font-bold" style="color:#1e40af">
        {{ L("Daily entries checklist — leave the system updated before you leave the desk",
             "تشيك ليست الإدخالات اليومية — سيب السيستم محدث قبل ما تقوم من المكتب",
             "Liste quotidienne — le système doit être à jour avant de partir") }}
      </div>
      <div class="text-[11px] mt-0.5" style="color:#1d4ed8">
        {{ L("Every item is checked live from the books for the selected day. Red blocks the day; amber is work to finish.",
             "كل بند بيتفحص لايف من الدفاتر لليوم المختار. الأحمر بيقفل اليوم، والبرتقالي شغل يتقفل قبل الانصراف.",
             "Chaque point est vérifié en direct pour le jour choisi.") }}
      </div>
    </div>

    <div class="bg-white border border-line rounded-[14px] p-4 shadow-card">
      <div class="flex items-center gap-2 flex-wrap">
        <span class="text-[13px] font-bold">{{ L("Day status","حالة اليوم","État du jour") }}</span>
        <input v-model="day" type="date" class="h-[30px] px-2 rounded-[8px] border border-line text-[12px]" @change="load" />
        <button class="h-[30px] px-3 rounded-[8px] border border-line text-[12px] bg-white" @click="load">⟳ {{ L("Refresh","تحديث","Actualiser") }}</button>
        <span v-if="data.items" class="ms-auto text-[11px] font-bold px-2 py-0.5 rounded-full"
              :style="data.ready ? 'background:#ecfdf5;color:#047857' : (data.blocked ? 'background:#fef2f2;color:#be123c' : 'background:#fffbeb;color:#b45309')">
          {{ data.ready ? L("Day is clean ✓","اليوم نضيف ✓","Journée propre ✓")
             : (data.blocked ? data.blocked + " " + L("blocking","بند مانع","bloquants") + " · " : "") + (data.pending || 0) + " " + L("to finish","بند متبقي","à finir") }}
        </span>
      </div>

      <div v-if="loading" class="py-10 text-center text-[12px] text-ink-muted">{{ L("Checking the books…","جاري فحص الدفاتر…","Vérification…") }}</div>
      <div v-else-if="err" class="py-10 text-center text-[12px]" style="color:#b91c1c">{{ err }}</div>
      <div v-else class="flex flex-col gap-2.5 mt-3">
        <button v-for="c in data.items" :key="c.key" @click="go(c.link)"
                class="flex items-center gap-2.5 px-3 py-2.5 border rounded-[11px] text-start hover:shadow-card transition-all"
                :style="{ borderColor: m(c).bd, background: c.state === 'done' ? '#fdfdfc' : m(c).bg + '55' }">
          <span class="w-[24px] h-[24px] rounded-[7px] grid place-items-center flex-shrink-0 text-[13px]" :style="{ background: m(c).bg, color: m(c).fg }">
            {{ c.state === "done" ? "✓" : (c.state === "blocked" ? "✕" : "…") }}
          </span>
          <div class="flex-1 min-w-0">
            <div class="text-[12px] font-semibold">{{ L(c.en, c.ar, c.fr) }}</div>
            <div v-if="c.state !== 'done' || c.key === 'collections'" class="text-[10.5px] text-ink-muted tnum" dir="ltr">
              {{ c.value }} {{ c.unit }}<template v-if="c.hint_amount"> · {{ n(c.hint_amount) }} MAD</template>
            </div>
          </div>
          <span class="text-[10px] font-bold px-2 py-0.5 rounded-badge border whitespace-nowrap"
                :style="{ background: m(c).bg, color: m(c).fg, borderColor: m(c).bd }">
            {{ c.state === "done" ? L("Done","تمام","Fait") : c.state === "blocked" ? L("Fix now","اتصرف فورًا","À corriger") : L("Finish today","اقفله النهاردة","À finir") }}
          </span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";

const { locale } = useI18n();
const router = useRouter();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const n = (x) => (x === null || x === undefined ? "—" : Math.round(x).toLocaleString("en-US"));

const day = ref(new Date().toISOString().slice(0, 10));
const data = ref({});
const loading = ref(true);
const err = ref("");

function m(c) {
  if (c.state === "done") return { bg: "#ecfdf5", fg: "#047857", bd: "#a7f3d0" };
  if (c.state === "blocked") return { bg: "#fef2f2", fg: "#be123c", bd: "#fecdd3" };
  return { bg: "#fffbeb", fg: "#b45309", bd: "#fde68a" };
}
function go(link) { if (link) router.push(link); }

async function load() {
  loading.value = true; err.value = "";
  try {
    data.value = await api.call("accounting_portal.api.reports.daily_entry_checklist",
      { company: currentCompany(), date: day.value }, { fresh: true });
  } catch (e) { err.value = (e && e.message) || String(e); }
  finally { loading.value = false; }
}
onMounted(load);
</script>
