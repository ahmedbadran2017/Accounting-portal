<template>
  <div class="space-y-3.5">
    <!-- rhythm header -->
    <div class="bg-white rounded-card border border-line shadow-card px-4 py-3">
      <div class="flex items-center gap-2 flex-wrap mb-3">
        <Icon name="clock" :size="14" color="#0b5c4f" />
        <span class="text-[12px] font-bold">{{ L("Working rhythm","إيقاع العمل","Rythme de travail") }}</span>
        <span v-if="a.tz" class="inline-flex items-center gap-1 text-[10px] font-semibold rounded-chip px-2 py-0.5 bg-app-warm text-ink-2" :title="tzTitle">
          <Icon name="clock" :size="10" color="#78716c" />{{ shortTz(a.tz.local) }}
          <span v-if="a.tz.shifted" class="text-accent-dark">{{ a.tz.label }}</span>
        </span>
        <span v-if="loading" class="text-[10.5px] text-ink-muted">{{ L("loading…","جارٍ التحميل…","chargement…") }}</span>
      </div>

      <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Stat :label="L('Actions','حركة','Actions')" :value="(st.actions||0).toLocaleString()"
              :sub="(st.per_day||0)+' / '+L('active day','يوم نشط','jour actif')+' · '+(st.active_days||0)+' '+L('days','أيام','jours')" color="#0369a1" />
        <Stat :label="L('Window','نافذة العمل','Plage')" :value="st.first_at ? st.first_at+'–'+st.last_at : '—'" :ltr="true"
              :sub="L('local time','التوقيت المحلي','heure locale')+' · '+(st.active_hours||0)+' '+L('active hours','ساعة نشطة','h actives')" color="#0f766e" />
        <Stat :label="L('Busiest hour','ذروة اليوم','Heure de pointe')" :value="st.busiest_hour===null||st.busiest_hour===undefined ? '—' : hhmm(st.busiest_hour)"
              :sub="(st.busiest_count||0)+' '+L('actions','حركة','actions')" color="#7c3aed" />
        <Stat :label="L('Peak day','أنشط يوم','Jour le plus actif')" :value="st.peak_day ? dLabel(st.peak_day) : '—'"
              :sub="peakSub" color="#b45309" />
      </div>
    </div>

    <!-- heatmap -->
    <div class="bg-white rounded-card border border-line shadow-card px-4 py-3">
      <div class="flex items-center gap-2 flex-wrap mb-3">
        <Icon name="chart" :size="14" color="#0b5c4f" />
        <span class="text-[12px] font-bold">{{ L("Activity by hour","الحركة حسب الساعة","Activité par heure") }}</span>
        <div class="ms-auto flex items-center gap-1.5">
          <button v-for="m in modes" :key="m.k" type="button"
                  class="h-7 px-2.5 rounded-chip text-[11px] font-semibold border transition"
                  :class="mode===m.k ? 'bg-ink text-white border-ink' : 'bg-white border-line-2 text-ink-2 hover:bg-app-warm'"
                  :disabled="m.k==='day' && !a.daily_grid"
                  @click="mode=m.k">{{ m.label() }}</button>
        </div>
      </div>

      <div v-if="!st.actions" class="py-10 text-center text-[12px] text-ink-muted">
        {{ L("No activity in this period.","لا حركة في هذه الفترة.","Aucune activité sur la période.") }}
      </div>

      <div v-else dir="ltr" class="overflow-x-auto -mx-1 px-1">
        <div class="min-w-[620px]">
          <!-- hour ruler — same 74px label gutter and 34px total column as the
               rows below, so the columns line up -->
          <div class="flex items-end gap-px ps-[74px] mb-1">
            <div v-for="h in 24" :key="'r'+h" class="flex-1 text-center text-[8.5px] text-ink-muted tnum">
              <span v-if="(h-1)%3===0">{{ String(h-1).padStart(2,'0') }}</span>
            </div>
            <div class="w-[34px] shrink-0"></div>
          </div>

          <!-- rows -->
          <div v-for="row in rows" :key="row.key"
               class="flex items-center gap-px mb-px group"
               :class="row.clickable ? 'cursor-pointer' : ''"
               @click="row.clickable && pick(row.key)">
            <div class="w-[74px] shrink-0 pe-2 text-[10px] tnum truncate"
                 :class="picked===row.key ? 'font-bold text-accent-dark' : 'text-ink-muted group-hover:text-ink-2'">{{ row.label }}</div>
            <div v-for="(n,h) in row.h" :key="h"
                 class="flex-1 h-[17px] rounded-[2px]"
                 :style="cell(n)"
                 :title="`${row.label} · ${String(h).padStart(2,'0')}:00 — ${n} ${n===1?'action':'actions'}`"></div>
            <div class="w-[34px] shrink-0 ps-1.5 text-[10px] tnum text-end"
                 :class="picked===row.key ? 'font-bold text-accent-dark' : 'text-ink-3'">{{ row.total || '' }}</div>
          </div>

          <!-- total profile -->
          <div class="flex items-end gap-px ps-[74px] mt-2 pt-2 border-t border-line-hair h-14">
            <div v-for="(n,h) in a.hours" :key="'p'+h" class="flex-1 flex flex-col justify-end h-full"
                 :title="`${String(h).padStart(2,'0')}:00 — ${n}`">
              <div class="rounded-t-[2px]" :style="`height:${profileH(n)}%;background:${n?'#0f766e':'transparent'};min-height:${n?'2px':'0'}`"></div>
            </div>
            <div class="w-[34px] shrink-0"></div>
          </div>
          <div class="flex items-center gap-2 ps-[74px] mt-1.5">
            <span class="text-[9.5px] text-ink-muted">{{ L("total by hour of day","الإجمالي حسب ساعة اليوم","total par heure") }}</span>
            <span class="ms-auto inline-flex items-center gap-1 text-[9.5px] text-ink-muted">
              {{ L("less","أقل","moins") }}
              <span v-for="s in 6" :key="s" class="w-3 h-3 rounded-[2px]" :style="swatch(s-1)"></span>
              {{ L("more","أكثر","plus") }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- timeline -->
    <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
      <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2 flex-wrap">
        <Icon name="list" :size="14" color="#0b5c4f" />
        <span class="text-[12px] font-bold">{{ L("Action trail","سجل الحركات","Journal d'activité") }}</span>
        <span class="text-[10.5px] text-ink-muted">{{ feed.length.toLocaleString() }}<span v-if="a.truncated"> / {{ (st.actions||0).toLocaleString() }}</span></span>
        <button v-if="picked" type="button" class="inline-flex items-center gap-1 h-6 px-2 rounded-chip bg-app-warm text-[10.5px] font-semibold text-ink-2 hover:bg-line" @click="picked=null">
          {{ pickedLabel }} <span class="text-ink-muted">×</span>
        </button>
        <span v-if="shortfall" class="text-[10.5px] text-amber-700">
          {{ L("showing","معروض","affiché") }} {{ feed.length }} {{ L("of","من","de") }} {{ shortfall }} — {{ L("narrow the date range for the rest","ضيّق الفترة لرؤية الباقي","affinez la période pour le reste") }}
        </span>
        <div class="ms-auto flex items-center gap-1.5">
          <button v-for="k in kindChips" :key="k.k" type="button"
                  class="h-7 px-2 rounded-chip text-[10.5px] font-semibold border transition"
                  :class="kindF===k.k ? 'bg-ink text-white border-ink' : 'bg-white border-line-2 text-ink-2 hover:bg-app-warm'"
                  @click="kindF = kindF===k.k ? null : k.k">{{ k.label() }} <span class="tnum opacity-70">{{ st[k.k] ?? '' }}</span></button>
        </div>
      </div>

      <table class="w-full text-[12px]">
        <tbody>
          <tr v-for="(e,i) in feed" :key="i" class="border-t border-line-hair first:border-t-0 hover:bg-app-warm/40"
              :class="canOpen(e) ? 'cursor-pointer group' : ''" @click="openDoc(e)">
            <td class="px-4 py-2 w-px whitespace-nowrap tnum text-ink-3">{{ e.at.slice(11,16) }}</td>
            <td class="px-1 py-2 w-px text-[9.5px] text-ink-muted tnum hidden sm:table-cell">{{ sameDay ? '' : e.at.slice(5,10) }}</td>
            <td class="px-2 py-2 w-px"><span class="text-[9.5px] font-bold px-1.5 py-0.5 rounded whitespace-nowrap" :class="kindClass(e.kind)">{{ kindLabel(e.kind) }}</span></td>
            <td class="px-2 py-2 w-px"><span class="text-[10px] font-bold rounded px-1.5 py-0.5 tnum" :style="`background:${tint(e.code)};color:${ink(e.code)}`">{{ e.code }}</span></td>
            <td class="px-2 py-2 font-mono text-[11px] whitespace-nowrap group-hover:text-accent-dark">{{ e.name }}</td>
            <td class="px-3 py-2 text-[11px] text-ink-muted truncate max-w-0 w-full" :title="e.note">{{ e.note }}</td>
            <td class="px-4 py-2 text-end tnum text-ink-2 whitespace-nowrap">{{ e.amount ? money(e.amount) : '' }}</td>
          </tr>
          <tr v-if="!feed.length"><td colspan="7" class="px-4 py-8 text-center text-ink-muted">{{ L("Nothing here.","لا شيء هنا.","Rien ici.") }}</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, h } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import api from "@/services/api";
import { fmtAmount, routeForDoc, DOC_CODE } from "@/utils/helpers";

const props = defineProps({ company: String, user: String, from: String, to: String });
const { locale } = useI18n();
const router = useRouter();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const money = (n) => fmtAmount(n);

const Stat = (p) => h("div", { class: "rounded-card border border-line-hair bg-app-warm/40 px-3 py-2" }, [
  h("div", { class: "text-[9.5px] font-bold uppercase tracking-wider text-ink-muted" }, p.label),
  // `ltr` wraps the value in a bidi isolate: a range like 10:05–18:19 is otherwise
  // reordered to 18:19–10:05 when the page is Arabic.
  h("div", { class: "text-[16px] font-extrabold mt-0.5 tnum", style: `color:${p.color}` },
    p.ltr ? [h("bdi", { dir: "ltr" }, p.value)] : p.value),
  h("div", { class: "text-[10px] text-ink-muted mt-0.5 truncate", title: p.sub }, p.sub),
]);
Stat.props = ["label", "value", "sub", "color", "ltr"];

const a = ref({});
const loading = ref(false);
const mode = ref("day");
const picked = ref(null);
const kindF = ref(null);

const st = computed(() => a.value.stats || {});
const DOW = () => [L("Sun", "أحد", "Dim"), L("Mon", "إثنين", "Lun"), L("Tue", "ثلاثاء", "Mar"),
  L("Wed", "أربعاء", "Mer"), L("Thu", "خميس", "Jeu"), L("Fri", "جمعة", "Ven"), L("Sat", "سبت", "Sam")];
const modes = [
  { k: "day", label: () => L("By day", "باليوم", "Par jour") },
  { k: "week", label: () => L("By weekday", "بأيام الأسبوع", "Par jour de semaine") },
];
const kindChips = [
  { k: "created", label: () => L("Created", "إنشاء", "Créés") },
  { k: "submitted", label: () => L("Submitted", "اعتماد", "Validés") },
  { k: "edited", label: () => L("Edited", "تعديل", "Modifiés") },
  { k: "cancelled", label: () => L("Cancelled", "إلغاء", "Annulés") },
];

async function load() {
  if (!props.user || !props.company) return;
  loading.value = true;
  try {
    a.value = await api.call("accounting_portal.api.team.accountant_activity",
      { company: props.company, user: props.user, from_date: props.from, to_date: props.to }) || {};
    if (!a.value.daily_grid) mode.value = "week";
    picked.value = null;
  } catch { a.value = {}; }
  finally { loading.value = false; }
}
load();
watch(() => [props.user, props.company, props.from, props.to].join("|"), load);

// ── grid rows ──
const rows = computed(() => {
  if (mode.value === "week") {
    const names = DOW();
    return (a.value.week || []).map((hrs, i) => ({
      key: "w" + i, label: names[i], h: hrs, total: hrs.reduce((s, n) => s + n, 0), clickable: false,
    }));
  }
  return (a.value.heatmap || []).map((r) => ({
    key: r.d, label: dLabel(r.d), h: r.h, total: r.total, clickable: true,
  }));
});
const maxCell = computed(() => Math.max(1, ...rows.value.flatMap((r) => r.h)));
const maxProfile = computed(() => Math.max(1, ...(a.value.hours || [0])));

// Action counts are heavily skewed — one batch hour can be 100× an ordinary one —
// so a linear ramp washes every normal hour out to the same faint tint. Square
// root compresses the peak and keeps the working hours legible.
const RAMP = [0.2, 0.36, 0.56, 0.78, 1];
function level(n) {
  if (!n) return -1;
  const t = Math.sqrt(Math.min(1, n / maxCell.value));
  return t > 0.8 ? 4 : t > 0.6 ? 3 : t > 0.4 ? 2 : t > 0.2 ? 1 : 0;
}
const cell = (n) => (level(n) < 0 ? "background:#f5f5f4" : `background:rgba(15,118,110,${RAMP[level(n)]})`);
const swatch = (i) => (i === 0 ? "background:#f5f5f4" : `background:rgba(15,118,110,${RAMP[i - 1]})`);
const profileH = (n) => Math.round((Number(n) || 0) / maxProfile.value * 100);
const hhmm = (h) => String(h).padStart(2, "0") + ":00";
function dLabel(d) {
  const dt = new Date(d + "T00:00:00");
  return DOW()[dt.getDay()] + " " + d.slice(8) + "/" + d.slice(5, 7);
}
function pick(k) { picked.value = picked.value === k ? null : k; }
const pickedLabel = computed(() => (picked.value ? dLabel(picked.value) : ""));
const peakSub = computed(() => {
  const r = (a.value.heatmap || []).find((x) => x.d === st.value.peak_day);
  const n = r ? r.total : 0;
  return `${n.toLocaleString()} ${L("actions", "حركة", "actions")} · ${st.value.cancelled || 0} ${L("cancelled", "ملغاة", "annulés")}`;
});

// ── timeline ──
const feed = computed(() => (a.value.timeline || []).filter(
  (e) => (!picked.value || e.at.slice(0, 10) === picked.value) && (!kindF.value || e.kind === kindF.value)));

// The payload is capped, so a long range can hold fewer events for a picked day
// than the grid counts. Say so rather than letting the two disagree silently.
const shortfall = computed(() => {
  if (!a.value.truncated || kindF.value) return 0;
  if (!picked.value) return a.value.stats?.actions || 0;
  const row = (a.value.heatmap || []).find((x) => x.d === picked.value);
  return row && row.total > feed.value.length ? row.total : 0;
});
const sameDay = computed(() => props.from === props.to || !!picked.value);

const tzTitle = computed(() => {
  const t = a.value.tz || {};
  if (!t.local) return "";
  return `${t.local} · ${L("server", "الخادم", "serveur")} ${t.server}${t.shifted ? ` (${t.label})` : ""}`;
});
const shortTz = (z) => String(z || "").split("/").pop().replace(/_/g, " ");

const KIND = {
  created: "bg-sky-50 text-sky-700", submitted: "bg-emerald-50 text-emerald-700",
  cancelled: "bg-rose-50 text-rose-600", edited: "bg-amber-50 text-amber-700",
  comment: "bg-stone-100 text-stone-600",
};
const kindClass = (k) => KIND[k] || "bg-stone-100 text-stone-600";
function kindLabel(k) {
  return k === "created" ? L("new", "إنشاء", "créé")
    : k === "submitted" ? L("submit", "اعتماد", "validé")
    : k === "cancelled" ? L("cancel", "إلغاء", "annulé")
    : k === "comment" ? L("note", "ملاحظة", "note")
    : L("edit", "تعديل", "modif");
}
const TINT = { JE: "#f0fdfa", PE: "#eff6ff", PI: "#fef2f2", SI: "#f5f3ff", PO: "#fffbeb", PR: "#f0f9ff", SO: "#f7fee7", DN: "#fdf4ff" };
const INK = { JE: "#0f766e", PE: "#0369a1", PI: "#be123c", SI: "#7c3aed", PO: "#b45309", PR: "#0284c7", SO: "#4d7c0f", DN: "#a21caf" };
const tint = (c) => TINT[c] || "#f5f5f4";
const ink = (c) => INK[c] || "#57534e";

// A row is only clickable when we know where it goes; otherwise the hand
// cursor promised a navigation that silently did nothing.
function canOpen(e) { return !!routeForDoc(DOC_CODE[e?.code], e?.name, e?.party_type); }
function openDoc(e) { const to = routeForDoc(DOC_CODE[e.code], e.name, e.party_type); if (to) router.push(to); }
</script>
