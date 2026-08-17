<template>
  <!-- Shipment Costing: the PR-centric workspace. List = the work queue
       (51 shipments, statuses, bill inbox, recon); click a shipment → its
       costing FILE: verify line costs, attach freight bills, save draft. -->
  <div class="space-y-3">

    <!-- ══ SHEET MODE ══ -->
    <template v-if="sheet">
      <button class="text-[12px] font-bold text-accent-dark hover:underline" @click="closeSheet">← {{ L("Back to shipments","رجوع للشحنات","Retour") }}</button>

      <div class="bg-white rounded-card border border-line shadow-card p-4">
        <div class="flex items-center gap-3 flex-wrap">
          <span class="text-[15px] font-bold font-mono" dir="ltr">{{ sheet.pr }}</span>
          <span class="text-[12px] text-ink-muted">{{ sheet.dt }} · {{ sheet.supplier }}</span>
          <span class="text-[12px]">{{ sheet.channel === "air" ? "🛫" : "🚢" }} {{ fmt0(sheet.kg) }}kg · {{ fmt0(sheet.qty) }} {{ L("units","قطعة","unités") }}</span>
          <span class="flex-1"></span>
          <span class="text-[12px] tnum"><b>{{ L("Freight","الشحن","Fret") }}:</b> {{ fmt0(sheet.freight.landed) }}
            <span class="text-[10px] font-bold px-1.5 py-0.5 rounded-full ms-1"
                  :style="sheet.freight.source==='bills' ? 'background:#ecfdf5;color:#047857' : sheet.freight.source==='est' ? 'background:#fffbeb;color:#b45309' : 'background:#fef2f2;color:#b91c1c'">
              {{ sheet.freight.source==='bills' ? L("actual","فعلي","réel") : sheet.freight.source==='est' ? L("estimate","تقديري","estimé") : L("none","بدون","aucun") }}</span>
            <span class="text-[10.5px] text-ink-muted"> @{{ sheet.freight.rate_kg }}/kg</span>
          </span>
        </div>
      </div>

      <!-- ② freight bills -->
      <div class="bg-white rounded-card border border-line shadow-card p-4">
        <div class="text-[12px] font-bold mb-2">🧾 {{ L("Freight bills of this shipment","فواتير شحن الشحنة دي","Factures fret") }}</div>
        <div class="flex gap-1.5 flex-wrap mb-2">
          <span v-for="b in attachedBills" :key="b.voucher" class="inline-flex items-center gap-1.5 text-[11px] border rounded-[8px] px-2 py-1" style="background:#f0fdf4;border-color:#bbf7d0">
            <span class="font-mono text-[10.5px]" dir="ltr">{{ b.voucher }}</span>
            <span class="tnum font-semibold">{{ fmt0(shareOf(b)) }}</span>
            <span v-if="b.n_prs > 1" class="text-[10px] text-ink-muted">÷{{ b.n_prs }}</span>
            <button v-if="canWrite && !sheet.frozen" class="text-sale" @click="toggleBill(b, false)">✕</button>
          </span>
          <span v-if="!attachedBills.length" class="text-[11px] text-ink-muted">{{ L("No bills attached yet — pick from the list:","لسه مفيش فواتير مرفقة — اختاروا من القايمة:","Aucune facture.") }}</span>
        </div>
        <details class="text-[11.5px]" :open="!attachedBills.length">
          <summary class="cursor-pointer text-accent-dark font-bold text-[11.5px]">{{ L("+ Attach a bill","+ إرفاق فاتورة","+ Joindre") }} ({{ availableBills.length }})</summary>
          <div class="mt-2 border border-line rounded-[8px] max-h-[220px] overflow-y-auto">
            <div v-for="b in availableBills" :key="b.voucher" class="flex items-center gap-2 px-3 py-1.5 border-b border-line-hair last:border-0 hover:bg-app-warm">
              <span class="font-mono text-[10.5px]" dir="ltr">{{ b.voucher }}</span>
              <span class="text-[10px] text-ink-muted">{{ b.dt }}</span>
              <span class="truncate flex-1 text-[11px]">{{ b.supplier || b.account }}</span>
              <span class="tnum font-semibold">{{ fmt0(b.amount) }}</span>
              <span v-if="b.n_prs" class="text-[10px] text-ink-muted">{{ L("covers","بتغطي","couvre") }} {{ b.n_prs }}</span>
              <button v-if="canWrite && !sheet.frozen" class="text-[10.5px] font-bold px-2 py-0.5 rounded-[6px] border border-line hover:bg-white" @click="toggleBill(b, true)">{{ L("Attach","إرفاق","Joindre") }}</button>
            </div>
          </div>
        </details>
        <div v-if="sheet.frozen" class="text-[10.5px] text-ink-muted mt-1.5">❄ {{ L("Basis frozen — unfreeze (Super Admin) to change freight.","الأساس مجمّد — فك التجميد لتغيير الشحن.","Base gelée.") }}</div>
      </div>

      <!-- ① product lines -->
      <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
        <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2 flex-wrap">
          <span class="text-[12px] font-bold">📦 {{ L("Product costs — verify each line against the supplier invoice","تكلفة البضاعة — اتحققوا من كل سطر مع فاتورة المورد","Coûts produits") }}</span>
          <span class="text-[11px] text-ink-muted flex-1">{{ verifiedCount }}/{{ sheet.lines.length }} {{ L("verified","متحقق","vérifié") }}</span>
          <button v-if="canWrite" class="h-[26px] px-2.5 rounded-[7px] text-[10.5px] font-bold border border-line text-ink-2 hover:bg-app-warm"
                  @click="useSuggestedAll">{{ L("Use suggested for empty lines","استخدام المقترح للفاضي","Suggestions") }}</button>
        </div>
        <div class="max-h-[420px] overflow-y-auto">
          <table class="w-full text-[11.5px]">
            <thead><tr style="background:#fafaf9" class="sticky top-0 z-[1]">
              <th class="px-3 py-1.5 text-start text-[10px] font-bold text-ink-muted">{{ L("Item","الصنف","Article") }}</th>
              <th class="px-3 py-1.5 text-end text-[10px] font-bold text-ink-muted">{{ L("Qty","كمية","Qté") }}</th>
              <th class="px-3 py-1.5 text-end text-[10px] font-bold text-ink-muted">{{ L("Booked","المسجّل","Comptab.") }}</th>
              <th class="px-3 py-1.5 text-end text-[10px] font-bold text-ink-muted">{{ L("Suggested","المقترح","Suggéré") }}</th>
              <th class="px-3 py-1.5 text-end text-[10px] font-bold text-ink-muted w-[110px]">{{ L("Verified ✎","المعتمد ✎","Vérifié ✎") }}</th>
              <th class="px-3 py-1.5 text-end text-[10px] font-bold text-ink-muted">+ {{ L("freight","شحن","fret") }}</th>
              <th class="px-3 py-1.5 text-end text-[10px] font-bold text-ink-muted">{{ L("Full","الكاملة","Total") }}</th>
            </tr></thead>
            <tbody>
              <tr v-for="l in sheet.lines" :key="l.item_code" class="border-t border-line-hair" :style="l.fixed ? 'background:#f0fdf4' : ''">
                <td class="px-3 py-1.5">
                  <span class="font-mono text-[10.5px]" dir="ltr">{{ l.item_code }}</span>
                  <span v-if="l.fixed" class="text-[9.5px] font-bold ms-1" style="color:#047857">✓ {{ L("applied","مطبَّق","appliqué") }}</span>
                  <div class="text-[10px] text-ink-muted truncate max-w-[260px]">{{ l.sku || l.item_name }}</div>
                </td>
                <td class="px-3 py-1.5 text-end tnum">{{ fmt0(l.qty) }}</td>
                <td class="px-3 py-1.5 text-end tnum text-ink-muted">{{ l.book_rate }}</td>
                <td class="px-3 py-1.5 text-end tnum">
                  <button v-if="l.suggested" class="hover:underline decoration-dotted" :title="l.source" @click="edits[l.item_code] = l.suggested">{{ l.suggested }}</button>
                  <span v-else class="text-ink-3">—</span>
                </td>
                <td class="px-2 py-1 text-end">
                  <input type="number" step="0.01" min="0" v-model.number="edits[l.item_code]" :disabled="!canWrite"
                         class="w-[92px] h-[26px] px-1.5 text-end tnum text-[11.5px] border rounded-[6px] outline-none focus:border-accent"
                         :style="edits[l.item_code] > 0 ? 'border-color:#a7f3d0;background:#f0fdf4' : 'border-color:#e7e5e4'" />
                </td>
                <td class="px-3 py-1.5 text-end tnum text-ink-muted">{{ l.landed_unit }}</td>
                <td class="px-3 py-1.5 text-end tnum font-semibold">{{ edits[l.item_code] > 0 ? (Number(edits[l.item_code]) + l.landed_unit).toFixed(2) : "—" }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <!-- save -->
        <div class="px-4 py-3 border-t border-line-hair flex items-center gap-2 flex-wrap">
          <input v-model="note" :placeholder="L('Note (which invoice was checked…)','ملاحظة (اتراجعت على أنهي فاتورة…)','Note…')"
                 class="h-[30px] px-2.5 text-[11.5px] border border-line rounded-[8px] outline-none flex-1 min-w-[200px]" />
          <span class="text-[11px] text-ink-muted" v-if="sheet.sheet.on" dir="ltr">💾 {{ sheet.sheet.by }} · {{ sheet.sheet.on }}</span>
          <button v-if="canWrite" class="h-[32px] px-4 rounded-[8px] text-[12px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand disabled:opacity-50"
                  :disabled="busy" @click="saveSheet">💾 {{ L("Save draft","حفظ المسودة","Enregistrer") }}</button>
        </div>
      </div>
    </template>

    <!-- ══ LIST MODE ══ -->
    <template v-else-if="data">
      <!-- progress + recon -->
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <div class="bg-white border border-line rounded-card shadow-card px-3.5 py-2.5">
          <div class="text-[10px] text-ink-muted">{{ L("Shipments costed","شحنات اتقفلت تكلفتها","Expéditions costées") }}</div>
          <div class="text-[16px] font-bold tnum">{{ data.counts.costed + data.counts.applied }} / {{ data.rows.length }}</div>
          <div class="h-[5px] rounded-full bg-app-warm mt-1.5 overflow-hidden"><div class="h-full rounded-full" style="background:linear-gradient(90deg,#34d399,#059669)" :style="{width: pct + '%'}"></div></div>
        </div>
        <div class="bg-white border border-line rounded-card shadow-card px-3.5 py-2.5">
          <div class="text-[10px] text-ink-muted">{{ L("Freight bills","فواتير الشحن","Factures fret") }}</div>
          <div class="text-[16px] font-bold tnum">{{ fmt0(data.recon.bills_total) }}</div>
          <div class="text-[10px] text-ink-3">{{ L("allocated","موزَّع","alloué") }} {{ fmt0(data.recon.allocated) }}</div>
        </div>
        <div class="bg-white border rounded-card shadow-card px-3.5 py-2.5" :style="data.inbox.length ? 'border-color:#fde68a;background:#fffbeb' : 'border-color:#e7e5e4'">
          <div class="text-[10px] text-ink-muted">{{ L("Bill inbox (unallocated)","فواتير غير موزَّعة","Non alloué") }}</div>
          <div class="text-[16px] font-bold tnum" :style="data.inbox.length ? 'color:#b45309' : 'color:#047857'">{{ data.inbox.length }}</div>
          <div class="text-[10px] text-ink-3">{{ L("open a shipment → attach","افتحوا شحنة → إرفاق","à joindre") }}</div>
        </div>
        <div class="bg-white border border-line rounded-card shadow-card px-3.5 py-2.5">
          <div class="text-[10px] text-ink-muted">{{ L("Status","الحالة","Statut") }}</div>
          <div class="text-[11px] tnum mt-1">⬜ {{ data.counts.pending }} · 🟡 {{ data.counts.progress }} · ✅ {{ data.counts.costed }} · 🔒 {{ data.counts.applied }}</div>
          <div class="text-[10px] text-ink-3 mt-0.5">{{ data.frozen ? "❄ " + L("basis frozen","الأساس مجمّد","base gelée") : L("basis not frozen","الأساس مش مجمّد","non gelée") }}</div>
        </div>
      </div>

      <!-- inbox strip -->
      <div v-if="data.inbox.length" class="bg-white border rounded-card shadow-card px-4 py-2.5" style="border-color:#fde68a">
        <span class="text-[11px] font-bold" style="color:#b45309">🧾 {{ L("Unallocated freight bills:","فواتير شحن مستنية توزيع:","Factures à allouer :") }}</span>
        <span v-for="b in data.inbox.slice(0, 8)" :key="b.voucher" class="inline-flex items-center gap-1 text-[10.5px] border border-line rounded-[6px] px-1.5 py-0.5 ms-1.5 bg-white">
          <span class="font-mono" dir="ltr">{{ b.voucher.slice(-9) }}</span><span class="tnum font-semibold">{{ fmt0(b.amount) }}</span>
        </span>
        <span v-if="data.inbox.length > 8" class="text-[10.5px] text-ink-muted ms-1">+{{ data.inbox.length - 8 }}</span>
      </div>

      <!-- shipments table -->
      <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
        <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-1.5 flex-wrap">
          <span class="text-[12px] font-bold flex-1">📦 {{ L("Import shipments","شحنات الاستيراد","Expéditions") }} {{ data.year }}</span>
          <button v-for="f in FILTERS" :key="f.id" class="text-[10.5px] font-bold px-2 py-0.5 rounded-full border"
                  :style="filter===f.id ? 'background:#eef2ff;color:#4338ca;border-color:#c7d2fe' : 'border-color:#e7e5e4;color:#78716c'"
                  @click="filter = filter===f.id ? '' : f.id">{{ f.icon }} {{ L(...f.label) }}</button>
        </div>
        <table class="w-full text-[11.5px]">
          <thead><tr style="background:#fafaf9">
            <th class="px-4 py-2 text-start text-[10px] font-bold text-ink-muted">{{ L("Shipment","الشحنة","Expédition") }}</th>
            <th class="px-3 py-2 text-start text-[10px] font-bold text-ink-muted">{{ L("Supplier","المورّد","Fourn.") }}</th>
            <th class="px-3 py-2 text-center text-[10px] font-bold text-ink-muted">{{ L("Ch.","قناة","Can.") }}</th>
            <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">kg</th>
            <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("Lines verified","سطور متحققة","Lignes") }}</th>
            <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("Freight","الشحن","Fret") }}</th>
            <th class="px-3 py-2 text-center text-[10px] font-bold text-ink-muted">{{ L("Status","الحالة","Statut") }}</th>
          </tr></thead>
          <tbody>
            <tr v-for="r in shownRows" :key="r.name" class="border-t border-line-hair cursor-pointer hover:bg-app-warm" @click="openSheet(r.name)">
              <td class="px-4 py-2 font-mono text-[10.5px] whitespace-nowrap" dir="ltr">{{ r.name }}<div class="text-[10px] text-ink-muted font-sans">{{ r.dt }}</div></td>
              <td class="px-3 py-2 truncate max-w-[150px]">{{ r.supplier }}</td>
              <td class="px-3 py-2 text-center">{{ r.channel === "air" ? "🛫" : "🚢" }}</td>
              <td class="px-3 py-2 text-end tnum">{{ fmt0(r.kg) }}</td>
              <td class="px-3 py-2 text-end tnum">
                <b :style="r.n_verified >= r.n_lines && r.n_lines ? 'color:#047857' : ''">{{ r.n_verified }}</b>/{{ r.n_lines }}
              </td>
              <td class="px-3 py-2 text-end tnum whitespace-nowrap">{{ fmt0(r.freight.landed) }}
                <span class="text-[9.5px] font-bold px-1 py-0.5 rounded-full ms-0.5"
                      :style="r.freight.source==='bills' ? 'background:#ecfdf5;color:#047857' : r.freight.source==='est' ? 'background:#fffbeb;color:#b45309' : 'background:#fef2f2;color:#b91c1c'">
                  {{ r.freight.source==='bills' ? L("actual","فعلي","réel") : r.freight.source==='est' ? L("est.","تقديري","est.") : L("none","بدون","aucun") }}</span>
              </td>
              <td class="px-3 py-2 text-center">
                <span class="text-[10.5px] font-bold px-2 py-0.5 rounded-full" :style="STATUS_STYLE[r.status]">{{ STATUS_ICON[r.status] }} {{ statusLabel(r.status) }}</span>
              </td>
            </tr>
            <tr v-if="!shownRows.length"><td colspan="7" class="px-4 py-4 text-center text-[11.5px] text-ink-muted">{{ L("No shipments match.","مفيش شحنات مطابقة.","Aucune expédition.") }}</td></tr>
          </tbody>
        </table>
      </div>

      <!-- Final apply -->
      <div class="bg-white rounded-card border shadow-card p-4" :style="ready?.frozen && ready?.items_ready ? 'border-color:#a7f3d0' : 'border-color:#e7e5e4'">
        <div class="flex items-center gap-3 flex-wrap">
          <div class="flex-1 min-w-[260px]">
            <div class="text-[12px] font-bold">🚀 {{ L("Final apply — product + freight, new AND retroactive","التطبيق النهائي — بضاعة + شحن، للجديد والقديم بأثر رجعي","Application finale") }}</div>
            <div class="text-[11px] text-ink-muted mt-0.5">
              {{ L("Runs in waves through the same gated, undoable fix — each item revalued at its qty-weighted verified cost + its frozen freight share.",
                   "بيشتغل على دفعات بنفس آلية الفيكس المؤمَّنة القابلة للعكس — كل صنف بياخد متوسط تكلفته المعتمدة + نصيبه من الشحن المجمّد.",
                   "Par vagues, via le correctif réversible existant.") }}
            </div>
            <div v-if="ready" class="text-[11px] tnum mt-1">
              {{ L("items with verified cost","أصناف بتكلفة معتمدة","articles vérifiés") }}: <b>{{ ready.items_with_verified_cost }}</b> ·
              {{ L("ready to apply","جاهزة للتطبيق","prêts") }}: <b style="color:#b45309">{{ ready.items_ready }}</b> ·
              {{ L("applied","اتطبّقت","appliqués") }}: <b style="color:#047857">{{ ready.items_applied }}</b>
              <span v-if="!ready.frozen" class="ms-2" style="color:#b45309">❄ {{ L("blocked: freeze the landed basis first","متقفل: جمّدوا أساس الشحن الأول","gelez d'abord la base") }}</span>
            </div>
          </div>
          <button v-if="canWrite" class="h-[30px] px-3 rounded-[8px] text-[11.5px] font-bold border border-line text-ink-2 hover:bg-app-warm disabled:opacity-50"
                  :disabled="busy" @click="previewApply">{{ L("Preview next wave","معاينة الدفعة الجاية","Aperçu") }}</button>
          <button v-if="canWrite" class="h-[30px] px-3.5 rounded-[8px] text-[11.5px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand disabled:opacity-50"
                  :disabled="busy || !ready?.frozen || !ready?.items_ready" @click="runApply">🚀 {{ L("Apply 20","طبّق 20","Appliquer 20") }}</button>
        </div>
        <div v-if="applyPrev" class="mt-2.5 border-t border-line-hair pt-2 text-[11px]">
          <template v-if="applyPrev.dry_run">
            <b>{{ L("Next wave","الدفعة الجاية","Prochaine vague") }} ({{ applyPrev.next_wave.length }}):</b>
            <span v-for="w in applyPrev.next_wave.slice(0, 10)" :key="w.item_code" class="inline-flex items-center gap-1 border border-line rounded-[6px] px-1.5 py-0.5 ms-1 tnum">
              <span class="font-mono text-[10px]" dir="ltr">{{ w.item_code }}</span> @{{ w.rate }}</span>
            <span v-if="applyPrev.next_wave.length > 10" class="text-ink-muted ms-1">+{{ applyPrev.next_wave.length - 10 }}</span>
            <span class="text-ink-muted ms-2">({{ L("remaining after","المتبقي بعدها","restant") }}: {{ applyPrev.remaining }})</span>
          </template>
          <template v-else>
            <b style="color:#047857">✅ {{ applyPrev.posted.length }} {{ L("applied","اتطبّقوا","appliqués") }}</b>
            <span v-if="applyPrev.skipped.length" class="ms-2" style="color:#b45309">⚠ {{ applyPrev.skipped.length }} {{ L("skipped","اتعدّوا","ignorés") }} — {{ applyPrev.skipped[0]?.reason }}</span>
            <span class="text-ink-muted ms-2">({{ L("remaining","المتبقي","restant") }}: {{ applyPrev.remaining }})</span>
          </template>
        </div>
      </div>
    </template>

    <div v-else class="text-[12px] text-ink-muted py-8 text-center">{{ L("Loading shipments…","بيحمّل الشحنات…","Chargement…") }}</div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from "vue";
import { useI18n } from "vue-i18n";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useAuth } from "@/composables/useAuth";
import { useToast } from "@/composables/useToast";

const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt0 = (n) => Number(n || 0).toLocaleString("en-US", { maximumFractionDigits: 0 });
const { can } = useAuth();
const canWrite = computed(() => can("post_entries"));
const toast = useToast();

const SC = "accounting_portal.api.shipment_costing";
const data = ref(null);
const sheet = ref(null);
const edits = reactive({});
const note = ref("");
const busy = ref(false);
const filter = ref("");

const FILTERS = [
  { id: "pending", icon: "⬜", label: ["Pending", "بانتظار", "En attente"] },
  { id: "progress", icon: "🟡", label: ["In progress", "جارية", "En cours"] },
  { id: "costed", icon: "✅", label: ["Costed", "مكتملة", "Costée"] },
  { id: "applied", icon: "🔒", label: ["Applied", "مطبَّقة", "Appliquée"] },
];
const STATUS_ICON = { pending: "⬜", progress: "🟡", costed: "✅", applied: "🔒" };
const STATUS_STYLE = {
  pending: "background:#f5f5f4;color:#78716c",
  progress: "background:#fffbeb;color:#b45309",
  costed: "background:#ecfdf5;color:#047857",
  applied: "background:#eef2ff;color:#4338ca",
};
const statusLabel = (s) => ({
  pending: L("pending", "بانتظار", "attente"), progress: L("in progress", "جارية", "en cours"),
  costed: L("costed", "مكتملة", "costée"), applied: L("applied", "مطبَّقة", "appliquée"),
}[s] || s);

const pct = computed(() => {
  if (!data.value?.rows?.length) return 0;
  return Math.round(100 * (data.value.counts.costed + data.value.counts.applied) / data.value.rows.length);
});
const shownRows = computed(() => {
  const rows = data.value?.rows || [];
  return filter.value ? rows.filter((r) => r.status === filter.value) : rows;
});
const verifiedCount = computed(() =>
  (sheet.value?.lines || []).filter((l) => edits[l.item_code] > 0).length);
const attachedBills = computed(() => (sheet.value?.picker || []).filter((b) => b.attached));
const availableBills = computed(() => (sheet.value?.picker || []).filter((b) => !b.attached));
const shareOf = (b) => {
  const hit = (sheet.value?.freight?.bills || []).find((x) => x.voucher === b.voucher);
  return hit ? hit.share : 0;
};

const ready = ref(null);
const applyPrev = ref(null);

async function loadList() {
  try {
    data.value = await api.call(`${SC}.shipments`, { company: currentCompany() }, { fresh: true });
    ready.value = await api.call(`${SC}.readiness`, { company: currentCompany() }, { fresh: true });
  } catch (e) { toast.error(e.message || "Failed"); }
}
loadList();

async function previewApply() {
  busy.value = true;
  try { applyPrev.value = await api.call(`${SC}.apply_batch`, { company: currentCompany(), dry_run: 1 }, { fresh: true }); }
  catch (e) { toast.error(e.message || "Failed"); }
  finally { busy.value = false; }
}
async function runApply() {
  if (!window.confirm(L(
    "Apply the next wave (up to 20 items)? Each posts a today-dated revaluation — undoable one by one in Activity.",
    "تطبيق الدفعة الجاية (لحد 20 صنف)؟ كل صنف بياخد قيد إعادة تقييم بتاريخ النهاردة — قابل للعكس واحد واحد من Activity.",
    "Appliquer la prochaine vague ?"))) return;
  busy.value = true;
  try {
    applyPrev.value = await api.call(`${SC}.apply_batch`, { company: currentCompany(), dry_run: 0 });
    await loadList();
  } catch (e) { toast.error(e.message || "Failed"); }
  finally { busy.value = false; }
}

async function openSheet(pr) {
  busy.value = true;
  try {
    const s = await api.call(`${SC}.get_sheet`, { pr }, { fresh: true });
    Object.keys(edits).forEach((k) => delete edits[k]);
    for (const l of s.lines) if (l.verified > 0) edits[l.item_code] = l.verified;
    note.value = s.sheet?.note || "";
    sheet.value = s;
  } catch (e) { toast.error(e.message || "Failed"); }
  finally { busy.value = false; }
}
function closeSheet() { sheet.value = null; loadList(); }

function useSuggestedAll() {
  for (const l of sheet.value.lines)
    if (!(edits[l.item_code] > 0) && l.suggested > 0) edits[l.item_code] = l.suggested;
}

async function saveSheet() {
  busy.value = true;
  try {
    const costs = {};
    for (const l of sheet.value.lines) if (edits[l.item_code] > 0) costs[l.item_code] = edits[l.item_code];
    await api.call(`${SC}.save_sheet`, { pr: sheet.value.pr, costs: JSON.stringify(costs), note: note.value });
    toast.success(L("Draft saved", "المسودة اتحفظت", "Brouillon enregistré"));
    await openSheet(sheet.value.pr);
  } catch (e) { toast.error(e.message || "Failed"); }
  finally { busy.value = false; }
}

async function toggleBill(b, attach) {
  busy.value = true;
  try {
    await api.call(`${SC}.attach_bill`, { pr: sheet.value.pr, voucher: b.voucher, attached: attach ? 1 : 0 });
    await openSheet(sheet.value.pr);
  } catch (e) { toast.error(e.message || "Failed"); }
  finally { busy.value = false; }
}
</script>
