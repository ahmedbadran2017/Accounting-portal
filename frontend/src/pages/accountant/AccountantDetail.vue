<template>
  <div class="space-y-3.5">
    <!-- back + date -->
    <div class="flex items-center gap-3 flex-wrap">
      <button type="button" class="inline-flex items-center gap-1.5 h-8 px-3 rounded-chip border border-line-2 bg-white text-[12px] font-semibold text-ink-2 hover:bg-app-warm" @click="back">
        <Icon name="arrow" :size="13" class="rotate-180" />{{ L("All accountants","كل المحاسبين","Tous") }}
      </button>
      <DateFilterBar :df="df" class="ms-auto" />
    </div>

    <TableLoading v-if="loading" :rows="3" />
    <div v-else-if="!d.user" class="bg-white rounded-card border border-line shadow-card px-4 py-14 text-center text-[12px] text-ink-muted">{{ L("No data for this accountant.","لا بيانات.","Aucune donnée.") }}</div>

    <template v-else>
      <!-- identity header -->
      <div class="bg-white rounded-card border border-line shadow-card px-4 py-3.5 flex items-center gap-3.5 flex-wrap">
        <span class="w-11 h-11 rounded-full grid place-items-center text-[14px] font-bold text-white shrink-0" :style="`background:${avatarColor(d.user)}`">{{ initials(d.name) }}</span>
        <div class="min-w-0">
          <div class="text-[15px] font-extrabold flex items-center gap-2">{{ d.name }}
            <span v-if="!d.enabled" class="text-[9px] font-semibold text-ink-muted bg-app-warm rounded px-1.5 py-0.5">{{ L("disabled","معطّل","désactivé") }}</span>
          </div>
          <div class="text-[11.5px] text-ink-muted">{{ d.user }}</div>
        </div>
        <div v-if="d.rank" class="ms-auto text-end">
          <div class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Rank by volume","الترتيب","Rang") }}</div>
          <div class="text-[17px] font-extrabold">#{{ d.rank }} <span class="text-[11px] text-ink-muted font-semibold">/ {{ d.members }}</span></div>
        </div>
      </div>

      <!-- KPI cards -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard :label="L('Submitted','معتمدة','Validés')" :value="(sm.submitted||0).toLocaleString()" :sub="(sm.created||0).toLocaleString() + ' ' + L('created','منشأة','créés')" icon="check" color="#0369a1" />
        <KpiCard :label="L('Rework rate','معدل إعادة العمل','Reprise')" :value="(sm.rework_pct||0)+'%'" :sub="(sm.cancelled||0).toLocaleString()+' '+L('cancelled','ملغاة','annulés')+' · '+L('team','الفريق','équipe')+' '+(d.team.rework_pct||0)+'%'" icon="alert" :color="reworkHex(sm.rework_pct)" :valueClass="reworkColor(sm.rework_pct)" />
        <KpiCard :label="L('Active days','أيام نشطة','Jours actifs')" :value="(sm.active_days||0)" :sub="(sm.per_day||0)+' / '+L('day','يوم','jour')+' · '+L('team','الفريق','équipe')+' '+(d.team.avg_per_day||0)" icon="clock" color="#0f766e" />
        <KpiCard :label="L('Value moved','القيمة','Valeur')" :value="money(sm.value)" :sub="ccy + ' · ' + (sm.draft||0)+' '+L('drafts','مسودّات','brouillons')" icon="wallet" color="#7c3aed" :valueClass="sm.draft>0 ? '' : ''" />
      </div>

      <!-- by doctype -->
      <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
        <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><Icon name="list" :size="14" color="#0b5c4f" /><span class="text-[12px] font-bold">{{ L("By document type","حسب نوع المستند","Par type") }}</span></div>
        <table class="w-full text-[12px]">
          <thead><tr style="background:#fafaf9" class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">
            <th class="px-4 py-2 text-start">{{ L("Type","النوع","Type") }}</th>
            <th class="px-3 py-2 text-end">{{ L("Created","منشأة","Créés") }}</th>
            <th class="px-3 py-2 text-end">{{ L("Submitted","معتمدة","Validés") }}</th>
            <th class="px-3 py-2 text-end">{{ L("Cancelled","ملغاة","Annulés") }}</th>
            <th class="px-3 py-2 text-end hidden sm:table-cell">{{ L("Drafts","مسودّات","Brouillons") }}</th>
            <th class="px-3 py-2 text-end">{{ L("Rework","إعادة عمل","Reprise") }}</th>
            <th class="px-4 py-2 text-end">{{ L("Value","القيمة","Valeur") }}</th>
          </tr></thead>
          <tbody>
            <tr v-for="r in d.by_doctype" :key="r.code" class="border-t border-line-hair">
              <td class="px-4 py-2.5"><span class="text-[10px] font-bold rounded px-1.5 py-0.5 tnum" :style="`background:${tint(r.code)};color:${ink(r.code)}`">{{ r.code }}</span> <span class="text-ink-2">{{ r.label }}</span></td>
              <td class="px-3 py-2.5 text-end tnum font-semibold">{{ r.created.toLocaleString() }}</td>
              <td class="px-3 py-2.5 text-end tnum">{{ r.submitted.toLocaleString() }}</td>
              <td class="px-3 py-2.5 text-end tnum" :class="r.cancelled>0 ? 'text-rose-600 font-semibold' : 'text-ink-muted'">{{ r.cancelled.toLocaleString() }}</td>
              <td class="px-3 py-2.5 text-end tnum hidden sm:table-cell" :class="r.draft>0 ? 'text-amber-700' : 'text-ink-muted'">{{ r.draft.toLocaleString() }}</td>
              <td class="px-3 py-2.5 text-end tnum font-bold" :class="reworkColor(r.rework_pct)">{{ r.rework_pct }}%</td>
              <td class="px-4 py-2.5 text-end tnum text-ink-2 whitespace-nowrap">{{ money(r.value) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- monthly trend -->
      <div v-if="d.monthly && d.monthly.length" class="bg-white rounded-card border border-line shadow-card px-4 py-3">
        <div class="flex items-center gap-2 mb-3"><Icon name="chart" :size="14" color="#0b5c4f" /><span class="text-[12px] font-bold">{{ L("Monthly activity","النشاط الشهري","Activité mensuelle") }}</span>
          <span class="ms-auto inline-flex items-center gap-3 text-[10px] text-ink-muted">
            <span class="inline-flex items-center gap-1"><span class="w-2.5 h-2.5 rounded-sm" style="background:#0f766e"></span>{{ L("submitted","معتمد","validé") }}</span>
            <span class="inline-flex items-center gap-1"><span class="w-2.5 h-2.5 rounded-sm" style="background:#f43f5e"></span>{{ L("cancelled","ملغي","annulé") }}</span>
          </span>
        </div>
        <div class="flex items-end gap-2 h-32">
          <div v-for="mo in d.monthly" :key="mo.m" class="flex-1 flex flex-col items-center gap-1 min-w-0">
            <div class="w-full flex-1 flex flex-col justify-end items-stretch gap-0.5" :title="`${mo.m}: ${mo.created} created, ${mo.submitted} submitted, ${mo.cancelled} cancelled`">
              <div v-if="mo.cancelled" class="rounded-t-sm" :style="`height:${barH(mo.cancelled)}%;background:#f43f5e;min-height:2px`"></div>
              <div class="rounded-sm" :style="`height:${barH(mo.submitted)}%;background:#0f766e;min-height:2px`"></div>
            </div>
            <span class="text-[9.5px] text-ink-muted whitespace-nowrap">{{ mLabel(mo.m) }}</span>
          </div>
        </div>
      </div>

      <!-- recent docs -->
      <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
        <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><Icon name="list" :size="14" color="#0b5c4f" /><span class="text-[12px] font-bold">{{ L("Recent documents","آخر المستندات","Documents récents") }}</span></div>
        <table class="w-full text-[12px]">
          <tbody>
            <tr v-for="(r,i) in d.recent" :key="i" class="border-t border-line-hair first:border-t-0 hover:bg-app-warm/40 cursor-pointer group" @click="openDoc(r)">
              <td class="px-4 py-2 w-px"><span class="text-[10px] font-bold rounded px-1.5 py-0.5 tnum" :style="`background:${tint(r.code)};color:${ink(r.code)}`">{{ r.code }}</span></td>
              <td class="px-2 py-2 font-mono text-[11px] group-hover:text-accent-dark">{{ r.name }}</td>
              <td class="px-3 py-2 text-ink-3 whitespace-nowrap">{{ r.date }}</td>
              <td class="px-3 py-2"><span class="text-[10px] font-semibold px-1.5 py-0.5 rounded" :class="statusClass(r.docstatus)">{{ statusLabel(r.docstatus) }}</span></td>
              <td class="px-4 py-2 text-end tnum text-ink-2 whitespace-nowrap">{{ money(r.amount) }}<Icon name="arrow" :size="11" color="#cbd5e1" class="inline ms-1 opacity-0 group-hover:opacity-100" /></td>
            </tr>
            <tr v-if="!d.recent || !d.recent.length"><td colspan="5" class="px-4 py-8 text-center text-ink-muted">{{ L("No documents.","لا مستندات.","Aucun.") }}</td></tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, h } from "vue";
import { useRoute, useRouter } from "vue-router";
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
const route = useRoute();
const router = useRouter();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const money = (n) => { n = Number(n) || 0; const a = Math.abs(n); return (n < 0 ? "−" : "") + (a >= 1e6 ? (a / 1e6).toFixed(2) + "M" : a >= 1e3 ? (a / 1e3).toFixed(0) + "K" : Math.round(a).toLocaleString()); };

// inline KPI card (keeps this page self-contained)
const KpiCard = (props) => h("div", { class: "bg-white rounded-card border border-line shadow-card px-4 py-3" }, [
  h("div", { class: "text-[10px] font-bold uppercase tracking-wider text-ink-muted flex items-center gap-1.5" }, [
    h(Icon, { name: props.icon, size: 13, color: props.color }), props.label]),
  h("div", { class: "text-[20px] font-extrabold mt-1 tnum " + (props.valueClass || ""), style: props.valueClass ? "" : `color:${props.color}` }, props.value),
  h("div", { class: "text-[10.5px] text-ink-muted mt-0.5" }, props.sub),
]);
KpiCard.props = ["label", "value", "sub", "icon", "color", "valueClass"];

const d = ref({});
const loading = ref(true);
const user = computed(() => route.query.user);
const sm = computed(() => d.value.summary || {});
const ccy = computed(() => d.value.currency || "MAD");

const df = useDateFilter("teamperf", () => load(), "quarter");

async function load() {
  if (!user.value) return;
  loading.value = true;
  try { d.value = await api.call("accounting_portal.api.team.accountant_detail", { company: currentCompany(), user: user.value, ...df.filterValue() }) || {}; }
  catch { d.value = {}; }
  finally { loading.value = false; }
}
load();
watch(user, load);
watch(entityId, () => router.push({ path: "/accounting/accountant/team" }));

function back() { router.push({ path: "/accounting/accountant/team" }); }
const DOC_ROUTE = { JE: "/accounting/accountant/journals", PE: "/accounting/sales/payments", PI: "/accounting/purchases/bills", SI: "/accounting/sales/invoices" };
function openDoc(r) { const p = DOC_ROUTE[r.code]; if (p && r.name) router.push({ path: p, query: { id: r.name } }); }

const maxCreated = computed(() => Math.max(1, ...(d.value.monthly || []).map((m) => m.created)));
const barH = (n) => Math.round((Number(n) || 0) / maxCreated.value * 100);
const mLabel = (m) => { const p = String(m || "").split("-"); return p.length === 2 ? p[1] + "/" + p[0].slice(2) : m; };

const reworkColor = (p) => (p >= 20 ? "text-rose-600" : p >= 5 ? "text-amber-600" : "text-success-dark");
const reworkHex = (p) => (p >= 20 ? "#e11d48" : p >= 5 ? "#d97706" : "#047857");
function initials(name) { return String(name || "?").trim().split(/\s+/).slice(0, 2).map((w) => w[0]).join("").toUpperCase() || "?"; }
const AV = ["#0f766e", "#0369a1", "#7c3aed", "#b45309", "#be123c", "#0891b2", "#4f46e5", "#15803d"];
function avatarColor(u) { let hsh = 0; for (const ch of String(u)) hsh = (hsh * 31 + ch.charCodeAt(0)) >>> 0; return AV[hsh % AV.length]; }
const TINT = { JE: "#f0fdfa", PE: "#eff6ff", PI: "#fef2f2", SI: "#f5f3ff" };
const INK = { JE: "#0f766e", PE: "#0369a1", PI: "#be123c", SI: "#7c3aed" };
const tint = (c) => TINT[c] || "#f5f5f4";
const ink = (c) => INK[c] || "#57534e";
const statusLabel = (ds) => (ds === 1 ? L("Submitted", "معتمد", "Validé") : ds === 2 ? L("Cancelled", "ملغي", "Annulé") : L("Draft", "مسودة", "Brouillon"));
const statusClass = (ds) => (ds === 1 ? "bg-emerald-50 text-emerald-700" : ds === 2 ? "bg-rose-50 text-rose-600" : "bg-amber-50 text-amber-700");
</script>
