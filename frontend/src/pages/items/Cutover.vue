<template>
  <div class="space-y-3.5">
    <!-- the machine, explained once -->
    <div class="rounded-[14px] px-4 py-3 border" style="background:#eff6ff;border-color:#bfdbfe">
      <div class="text-[12px] font-bold" style="color:#1e40af">
        {{ L("Bring the whole catalogue to true cost — in light steps",
             "نوصّل كل الكتالوج للتكلفة الحقيقية — بخطوات خفيفة",
             "Amener tout le catalogue au vrai coût — par étapes légères") }}
      </div>
      <div class="text-[11px] mt-0.5" style="color:#1d4ed8">
        {{ L("Step 1 fixes the balance sheet today. Step 2 heals each past month's COGS one bounded chunk at a time, oldest first, so the reports read true. Step 3 is your audit team walking every product from ~85% to 100%. Each action is small, gated and reversible.",
             "الخطوة 1 بتصلّح الميزانية النهاردة. الخطوة 2 بتعالج COGS كل شهر فات لوحده، الأقدم الأول، عشان التقارير تقرا صح. الخطوة 3 فريق الـaudit بيمشي كل منتج من ~85% لـ100%. كل أكشن صغير، gated وقابل للعكس.",
             "Étape 1 : bilan. Étape 2 : COGS mois par mois. Étape 3 : audit.") }}
      </div>
    </div>

    <div v-if="loading" class="py-16 text-center text-[12px] text-ink-muted">{{ L("Loading…","جاري التحميل…","Chargement…") }}</div>
    <div v-else-if="err" class="py-16 text-center text-[12px]" style="color:#b91c1c">{{ err }}</div>

    <template v-else>
      <!-- headline: what the whole correction is worth + audit progress -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <div class="bg-white border border-line rounded-[14px] shadow-card px-4 py-3 lg:col-span-2">
          <div class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("COGS correction across 2026","تصحيح COGS عبر 2026","Correction COGS 2026") }}</div>
          <div class="text-[22px] font-extrabold tnum" :style="d.total_delta<0 ? 'color:#047857' : 'color:#b45309'" dir="ltr">
            {{ d.total_delta<0 ? '' : '+' }}{{ money(d.total_delta) }} <span class="text-[12px] font-bold text-ink-muted">MAD</span>
          </div>
          <div class="text-[11px] text-ink-muted mt-0.5">
            {{ d.total_delta<0
              ? L("the books currently OVER-state cost — correcting it raises historical profit by this much",
                  "الدفاتر بتضخّم التكلفة حاليًا — تصحيحها بيرفع الربح التاريخي بالمقدار ده",
                  "les livres surévaluent le coût — la correction augmente le profit")
              : L("correcting raises cost by this much","التصحيح بيرفع التكلفة بالمقدار ده","la correction augmente le coût") }}
          </div>
        </div>
        <div class="bg-white border border-line rounded-[14px] shadow-card px-4 py-3">
          <div class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Audit progress","تقدّم المراجعة","Audit") }}</div>
          <div class="text-[22px] font-extrabold tnum" dir="ltr">{{ d.verified.pct }}%</div>
          <div class="mt-1 h-2 rounded-full overflow-hidden" style="background:#f1f5f9">
            <div class="h-full rounded-full" style="background:#059669" :style="{ width: d.verified.pct + '%' }"></div>
          </div>
          <div class="text-[10.5px] text-ink-muted mt-1 tnum" dir="ltr">{{ n(d.verified.done) }} / {{ n(d.verified.total) }} {{ L("items verified","صنف متحقق","vérifiés") }}</div>
        </div>
      </div>

      <!-- step 1: forward -->
      <div class="bg-white border border-line rounded-[14px] shadow-card px-4 py-3.5 flex items-center gap-3 flex-wrap">
        <div class="w-8 h-8 rounded-full grid place-items-center text-[13px] font-extrabold" style="background:#eff6ff;color:#1e40af">1</div>
        <div class="min-w-0 flex-1">
          <div class="text-[13px] font-bold">{{ L("Fix the balance sheet (today-dated)","صلّح الميزانية (بتاريخ اليوم)","Corriger le bilan") }}</div>
          <div class="text-[11px] text-ink-muted">{{ L("Reprice every on-hand bin to true cost in one cutover reconciliation. Nothing reposts — cheap and safe.","إعادة تسعير كل مخزون حالي للتكلفة الحقيقية في تسوية واحدة. مفيش repost — رخيص وآمن.","Réévalue le stock en une réconciliation.") }}</div>
        </div>
        <span v-if="d.forward_done" class="text-[11px] font-bold px-2 py-1 rounded-full" style="background:#ecfdf5;color:#047857">{{ L("done","تم","fait") }}</span>
        <button v-else disabled class="h-[30px] px-3 rounded-[8px] text-[11px] font-bold border border-line text-ink-muted opacity-70"
                :title="L('arming next','بيتفعّل في الخطوة الجاية','bientôt')">{{ L("Run forward fix","شغّل التصحيح","Lancer") }} · {{ L("next","قريب","à venir") }}</button>
      </div>

      <!-- step 2: per-month retro -->
      <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
        <div class="px-4 py-3 border-b border-line-hair flex items-center gap-3">
          <div class="w-8 h-8 rounded-full grid place-items-center text-[13px] font-extrabold" style="background:#eff6ff;color:#1e40af">2</div>
          <div>
            <div class="text-[13px] font-bold">{{ L("Heal each past month (oldest first)","عالج كل شهر فات (الأقدم الأول)","Chaque mois passé") }}</div>
            <div class="text-[11px] text-ink-muted">{{ L("Each month reposts on its own so its P&L reads true. Only the next pending month is actionable.","كل شهر بيتعاد ترحيله لوحده عشان قائمة دخله تقرا صح. الشهر التالي بس هو القابل للتنفيذ.","Un mois à la fois.") }}</div>
          </div>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-[11.5px]">
            <thead><tr style="background:#fafaf9">
              <th class="px-3 py-2 text-start text-[10px] font-bold text-ink-muted">{{ L("Month","الشهر","Mois") }}</th>
              <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("Ledger rows","صفوف","Lignes") }}</th>
              <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("COGS now","COGS الحالي","COGS actuel") }}</th>
              <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("Corrected","المصحّح","Corrigé") }}</th>
              <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("Δ profit","Δ الربح","Δ profit") }}</th>
              <th class="px-3 py-2 text-center text-[10px] font-bold text-ink-muted">{{ L("No-cost u","بلا تكلفة","Sans coût") }}</th>
              <th class="px-3 py-2 text-end"></th>
            </tr></thead>
            <tbody>
              <tr v-for="m in d.months" :key="m.month" class="border-t border-line-hair"
                  :class="m.status==='done' ? 'bg-emerald-50/40' : (m.ready ? 'bg-blue-50/40' : '')">
                <td class="px-3 py-2 font-bold tnum" dir="ltr">{{ m.month }}</td>
                <td class="px-3 py-2 text-end tnum text-ink-muted" dir="ltr">{{ n(m.rows) }}</td>
                <td class="px-3 py-2 text-end tnum" dir="ltr">{{ money(m.cogs_booked) }}</td>
                <td class="px-3 py-2 text-end tnum" dir="ltr">{{ money(m.cogs_corrected) }}</td>
                <td class="px-3 py-2 text-end tnum font-bold" :style="(-m.delta)<0 ? 'color:#b45309' : 'color:#047857'" dir="ltr">
                  {{ (-m.delta)>=0 ? '+' : '' }}{{ money(-m.delta) }}
                </td>
                <td class="px-3 py-2 text-center tnum" :style="m.unpriced_units ? 'color:#b45309' : 'color:#cbd5e1'" dir="ltr">{{ n(m.unpriced_units) }}</td>
                <td class="px-3 py-2 text-end">
                  <span v-if="m.status==='done'" class="text-[10.5px] font-bold px-2 py-0.5 rounded-full" style="background:#ecfdf5;color:#047857">{{ L("done","تم","fait") }}</span>
                  <button v-else-if="m.ready" disabled class="h-[26px] px-2.5 rounded-[7px] text-[10.5px] font-bold border border-line text-ink-muted opacity-70"
                          :title="L('arming next','بيتفعّل في الخطوة الجاية','bientôt')">{{ L("Apply","طبّق","Appliquer") }} · {{ L("next","قريب","à venir") }}</button>
                  <span v-else class="text-[10px] text-ink-muted">{{ L("waiting","في الانتظار","en attente") }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- step 3 -->
      <div class="bg-white border border-line rounded-[14px] shadow-card px-4 py-3.5 flex items-center gap-3 flex-wrap">
        <div class="w-8 h-8 rounded-full grid place-items-center text-[13px] font-extrabold" style="background:#eff6ff;color:#1e40af">3</div>
        <div class="min-w-0 flex-1">
          <div class="text-[13px] font-bold">{{ L("Audit to 100%","المراجعة حتى 100%","Audit à 100%") }}</div>
          <div class="text-[11px] text-ink-muted">{{ L("The audit team confirms each product's cost one at a time (Items → each product's Fix); every confirmation stamps it verified and moves the bar above.","فريق المراجعة بيأكّد تكلفة كل منتج واحد واحد؛ كل تأكيد بيختمه متحقق ويحرّك الشريط فوق.","L'équipe valide chaque produit.") }}</div>
        </div>
      </div>

      <div class="text-[10.5px] text-ink-muted px-1">
        {{ L("Read-only plan. The forward and per-month write actions are gated, audited and reversible — armed as the next step, each previewed before it posts.",
             "خطة للقراءة فقط. أكشنات الكتابة (الأمام والشهور) gated وقابلة للعكس — بتتفعّل في الخطوة الجاية، وكل واحدة بمعاينة قبل الترحيل.",
             "Plan en lecture seule ; les actions d'écriture arrivent ensuite.") }}
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from "vue";
import { useI18n } from "vue-i18n";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";
import { fmtAmount } from "@/utils/helpers";

const { locale } = useI18n();
const { entityId } = useUi();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const money = (x) => fmtAmount(x);
const n = (x) => (x === null || x === undefined ? "—" : Math.round(x).toLocaleString("en-US"));

const loading = ref(true);
const err = ref("");
const d = ref({ months: [], verified: {} });

async function load() {
  loading.value = true; err.value = "";
  try {
    d.value = await api.call("accounting_portal.api.cutover.cutover_plan",
      { company: currentCompany() }, { fresh: true });
  } catch (e) {
    err.value = (e && e.message) || String(e);
  } finally {
    loading.value = false;
  }
}
onMounted(load);
watch(entityId, load);
</script>
