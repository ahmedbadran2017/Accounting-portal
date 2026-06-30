<template>
  <div class="space-y-3.5">
    <DateFilterBar :df="df" />

    <!-- restricted (defensive — the tab is hidden for non–super-admins) -->
    <div v-if="restricted" class="bg-white rounded-card border border-line shadow-card px-4 py-14 text-center">
      <Icon name="alert" :size="22" color="#b45309" class="inline-block mb-2" />
      <p class="text-[13px] font-bold">{{ L("Restricted","صلاحية مقصورة","Restreint") }}</p>
      <p class="text-[12px] text-ink-muted mt-1">{{ L("This page is visible to the Super Admin only.","هذه الصفحة للسوبر أدمن فقط.","Réservé au Super Admin.") }}</p>
    </div>

    <template v-else>
      <!-- Summary cards -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div class="bg-white rounded-card border border-line shadow-card px-4 py-3">
          <div class="text-[10px] font-bold uppercase tracking-wider text-ink-muted flex items-center gap-1.5"><Icon name="layers" :size="13" color="#0f766e" />{{ L("Accountants","المحاسبون","Comptables") }}</div>
          <div class="text-[20px] font-extrabold mt-1 tnum">{{ loading ? "—" : (t.members || 0) }}</div>
          <div class="text-[10.5px] text-ink-muted mt-0.5">{{ L("posted in this period","سجّلوا في هذه الفترة","actifs sur la période") }}</div>
        </div>
        <div class="bg-white rounded-card border border-line shadow-card px-4 py-3">
          <div class="text-[10px] font-bold uppercase tracking-wider text-ink-muted flex items-center gap-1.5"><Icon name="list" :size="13" color="#0369a1" />{{ L("Documents","المستندات","Documents") }}</div>
          <div class="text-[20px] font-extrabold mt-1 tnum" style="color:#0369a1">{{ loading ? "—" : (t.submitted || 0).toLocaleString() }}</div>
          <div class="text-[10.5px] text-ink-muted mt-0.5">{{ L("submitted","معتمدة","validés") }} · {{ money(t.value) }} {{ ccy }}</div>
        </div>
        <div class="bg-white rounded-card border shadow-card px-4 py-3" :class="t.rework_pct >= 20 ? 'border-rose-200' : 'border-line'">
          <div class="text-[10px] font-bold uppercase tracking-wider flex items-center gap-1.5" :class="t.rework_pct >= 20 ? 'text-rose-600' : 'text-ink-muted'"><Icon name="alert" :size="13" :color="t.rework_pct >= 20 ? '#e11d48' : '#94a3b8'" />{{ L("Rework rate","معدل إعادة العمل","Taux reprise") }}</div>
          <div class="text-[20px] font-extrabold mt-1 tnum" :class="reworkColor(t.rework_pct)">{{ loading ? "—" : (t.rework_pct || 0) + "%" }}</div>
          <div class="text-[10.5px] text-ink-muted mt-0.5">{{ (t.cancelled || 0).toLocaleString() }} {{ L("cancelled","ملغاة","annulés") }}</div>
        </div>
        <div class="bg-white rounded-card border shadow-card px-4 py-3" :class="t.flagged ? 'border-amber-200' : 'border-line'">
          <div class="text-[10px] font-bold uppercase tracking-wider text-ink-muted flex items-center gap-1.5"><Icon name="alert" :size="13" :color="t.flagged ? '#b45309' : '#94a3b8'" />{{ L("Flagged","تحت الملاحظة","Signalés") }}</div>
          <div class="text-[20px] font-extrabold mt-1 tnum" :class="t.flagged ? 'text-amber-700' : 'text-ink'">{{ loading ? "—" : (t.flagged || 0) }}</div>
          <div class="text-[10.5px] text-ink-muted mt-0.5">{{ L("high rework · stuck drafts","إعادة عمل عالية · مسودّات عالقة","reprise élevée · brouillons") }}</div>
        </div>
      </div>

      <!-- Leaderboard -->
      <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
        <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2">
          <Icon name="chart" :size="14" color="#0b5c4f" /><span class="text-[12px] font-bold">{{ L("Accountant scorecards","بطاقات أداء المحاسبين","Performance comptables") }}</span>
          <span class="text-[10px] text-ink-muted">{{ L("ranked by volume","مرتّب حسب الحجم","par volume") }}</span>
          <span v-if="loading" class="text-[10px] text-ink-muted">…</span>
        </div>
        <TableLoading v-if="loading" :rows="8" />
        <div v-else-if="!members.length" class="px-4 py-12 text-center text-[12px] text-ink-muted">{{ L("No accounting activity in this period.","لا نشاط محاسبي في هذه الفترة.","Aucune activité.") }}</div>
        <div v-else class="overflow-x-auto">
          <table class="w-full text-[12px]">
            <thead><tr style="background:#fafaf9" class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">
              <th class="px-4 py-2 text-start">{{ L("Accountant","المحاسب","Comptable") }}</th>
              <th class="px-3 py-2 text-end">{{ L("Posted","سجّل","Saisis") }}</th>
              <th class="px-3 py-2 text-start hidden md:table-cell">{{ L("Mix","التوزيع","Répartition") }}</th>
              <th class="px-3 py-2 text-end hidden sm:table-cell">{{ L("Active days","أيام نشطة","Jours actifs") }}</th>
              <th class="px-3 py-2 text-end hidden lg:table-cell">{{ L("Per day","يوميًا","Par jour") }}</th>
              <th class="px-3 py-2 text-end">{{ L("Rework","إعادة عمل","Reprise") }}</th>
              <th class="px-3 py-2 text-end hidden sm:table-cell">{{ L("Drafts","مسودّات","Brouillons") }}</th>
              <th class="px-4 py-2 text-end hidden lg:table-cell">{{ L("Value","القيمة","Valeur") }}</th>
            </tr></thead>
            <tbody>
              <tr v-for="(m, i) in members" :key="m.user" class="border-t border-line-hair" :class="m.flagged ? 'bg-rose-50/40' : 'hover:bg-app-warm/40'">
                <!-- identity -->
                <td class="px-4 py-2.5">
                  <div class="flex items-center gap-2.5">
                    <span class="w-7 h-7 rounded-full grid place-items-center text-[10.5px] font-bold text-white shrink-0" :style="`background:${avatarColor(m.user)}`">{{ initials(m.name) }}</span>
                    <div class="min-w-0">
                      <div class="font-semibold flex items-center gap-1.5">
                        <span class="text-ink-muted text-[10px] tnum w-4">{{ i + 1 }}</span>{{ m.name }}
                        <span v-if="m.flagged" class="text-[9px] font-bold text-rose-600 bg-rose-100 rounded px-1.5 py-0.5">{{ L("review","مراجعة","à revoir") }}</span>
                        <span v-if="!m.enabled" class="text-[9px] font-semibold text-ink-muted bg-app-warm rounded px-1.5 py-0.5">{{ L("disabled","معطّل","désactivé") }}</span>
                      </div>
                      <div class="text-[10.5px] text-ink-muted truncate">{{ m.user }} · {{ L("last","آخر","dernier") }} {{ m.last_at }}</div>
                    </div>
                  </div>
                </td>
                <!-- posted -->
                <td class="px-3 py-2.5 text-end">
                  <div class="tnum font-extrabold text-[13px]">{{ m.submitted.toLocaleString() }}</div>
                  <div class="tnum text-[10px] text-ink-muted">{{ m.created.toLocaleString() }} {{ L("created","أنشأ","créés") }}</div>
                </td>
                <!-- doctype mix -->
                <td class="px-3 py-2.5 hidden md:table-cell">
                  <div class="flex items-center gap-1 flex-wrap">
                    <span v-for="dc in doctypes" v-show="m.by[dc.code]" :key="dc.code" class="text-[9.5px] font-semibold rounded px-1.5 py-0.5 tnum" :style="`background:${mixTint(dc.code)};color:${mixInk(dc.code)}`">{{ dc.code }} {{ (m.by[dc.code] || 0).toLocaleString() }}</span>
                  </div>
                </td>
                <td class="px-3 py-2.5 text-end tnum hidden sm:table-cell">{{ m.active_days }}</td>
                <td class="px-3 py-2.5 text-end tnum text-ink-2 hidden lg:table-cell">{{ m.per_day }}</td>
                <!-- rework -->
                <td class="px-3 py-2.5 text-end">
                  <span class="tnum font-bold" :class="reworkColor(m.rework_pct)">{{ m.rework_pct }}%</span>
                  <div class="tnum text-[10px] text-ink-muted">{{ m.cancelled.toLocaleString() }}</div>
                </td>
                <td class="px-3 py-2.5 text-end tnum hidden sm:table-cell" :class="m.draft > 0 ? 'text-amber-700 font-semibold' : 'text-ink-muted'">{{ m.draft.toLocaleString() }}</td>
                <td class="px-4 py-2.5 text-end tnum text-ink-2 hidden lg:table-cell whitespace-nowrap">{{ money(m.value) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="px-4 py-2 border-t border-line-hair text-[10px] text-ink-muted flex items-center gap-1.5">
          <Icon name="alert" :size="11" color="#9a8f86" />
          {{ L("Rework = cancelled ÷ created. Counts attribute each document to the user who created it (JE · PE · Purchase & Sales invoices).","إعادة العمل = الملغاة ÷ المُنشأة. كل مستند يُنسب لمن أنشأه (قيود · سندات دفع · فواتير شراء/بيع).","Reprise = annulés ÷ créés.") }}
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import DateFilterBar from "@/components/DateFilterBar.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";
import { useDateFilter } from "@/composables/useDateFilter";

const { locale } = useI18n();
const { entityId } = useUi();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const money = (n) => { n = Number(n) || 0; const a = Math.abs(n); return (n < 0 ? "−" : "") + (a >= 1e6 ? (a / 1e6).toFixed(2) + "M" : a >= 1e3 ? (a / 1e3).toFixed(0) + "K" : Math.round(a).toLocaleString()); };

const data = ref({});
const loading = ref(true);
const restricted = ref(false);

const members = computed(() => data.value.members || []);
const t = computed(() => data.value.totals || {});
const doctypes = computed(() => data.value.doctypes || []);
const ccy = computed(() => data.value.currency || "MAD");

const df = useDateFilter("teamperf", () => load(), "quarter");

async function load() {
  loading.value = true; restricted.value = false;
  try {
    data.value = await api.call("accounting_portal.api.team.team_performance", { company: currentCompany(), ...df.filterValue() }) || {};
  } catch (e) {
    data.value = {};
    if (String(e?.message || e).match(/permitted|Super Admin|restrict/i)) restricted.value = true;
  } finally { loading.value = false; }
}
load();
watch(entityId, () => load());

const reworkColor = (p) => (p >= 20 ? "text-rose-600" : p >= 5 ? "text-amber-600" : "text-success-dark");
function initials(name) { return String(name || "?").trim().split(/\s+/).slice(0, 2).map((w) => w[0]).join("").toUpperCase() || "?"; }
const AV = ["#0f766e", "#0369a1", "#7c3aed", "#b45309", "#be123c", "#0891b2", "#4f46e5", "#15803d"];
function avatarColor(u) { let h = 0; for (const ch of String(u)) h = (h * 31 + ch.charCodeAt(0)) >>> 0; return AV[h % AV.length]; }
const TINT = { JE: "#f0fdfa", PE: "#eff6ff", PI: "#fef2f2", SI: "#f5f3ff" };
const INK = { JE: "#0f766e", PE: "#0369a1", PI: "#be123c", SI: "#7c3aed" };
const mixTint = (c) => TINT[c] || "#f5f5f4";
const mixInk = (c) => INK[c] || "#57534e";
</script>
