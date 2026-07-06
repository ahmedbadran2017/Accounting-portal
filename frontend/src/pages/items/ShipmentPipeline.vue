<template>
  <div class="space-y-3.5">
    <div class="flex items-center gap-2 flex-wrap">
      <span class="text-[11px] text-ink-muted">{{ L("Charge → shipment → capitalised into product cost. Posting credits the same expense account, so the P&L charge zeroes out and later deliveries repost with true COGS.","مصروف ← شحنة ← يترسمل في تكلفة المنتج. الترحيل بيصفّر حساب المصروف في الأرباح والخسائر ويعيد حساب COGS للتسليمات اللاحقة.","Charge → expédition → capitalisé.") }}</span>
      <button type="button" class="ms-auto text-[11px] font-semibold text-accent-dark hover:underline" @click="load">{{ L("Refresh","تحديث","Actualiser") }}</button>
    </div>

    <!-- overview -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <div class="bg-white rounded-card border border-rose-200 shadow-card px-4 py-3">
        <div class="text-[10px] font-bold uppercase tracking-wider text-rose-600">{{ L("Receipts w/o landed cost","استلامات بدون تحميل","Sans coût") }}</div>
        <div class="text-[20px] font-extrabold tnum mt-0.5">{{ ov.uncovered_receipts?.n ?? "—" }}</div>
        <div class="text-[10.5px] text-ink-muted">{{ money(ov.uncovered_receipts?.value) }} {{ L("since","منذ","depuis") }} {{ ov.from_date }}</div>
      </div>
      <div class="bg-white rounded-card border border-amber-200 shadow-card px-4 py-3">
        <div class="text-[10px] font-bold uppercase tracking-wider text-amber-700">{{ L("Draft vouchers","درافت واقفة","Brouillons") }}</div>
        <div class="text-[20px] font-extrabold tnum mt-0.5">{{ ov.drafts?.n ?? "—" }}</div>
        <div class="text-[10.5px] text-ink-muted">{{ money(ov.drafts?.value) }} {{ L("stuck","محبوسة","bloqués") }}</div>
      </div>
      <div class="bg-white rounded-card border border-line shadow-card px-4 py-3">
        <div class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Charge inbox","صندوق المصاريف","Charges") }}</div>
        <div class="text-[20px] font-extrabold tnum mt-0.5">{{ money(ov.inbox_total) }}</div>
        <div class="text-[10.5px] text-ink-muted">{{ ov.inbox_n }} {{ L("booked, not capitalised","مسجل ومش مرسمَل","non capitalisées") }}</div>
      </div>
      <div class="bg-white rounded-card border border-emerald-200 shadow-card px-4 py-3">
        <div class="text-[10px] font-bold uppercase tracking-wider text-emerald-700">{{ L("Posted 2026","مرحّل 2026","Validés") }}</div>
        <div class="text-[20px] font-extrabold tnum mt-0.5">{{ ov.posted?.n ?? "—" }}</div>
        <div class="text-[10.5px] text-ink-muted">{{ money(ov.posted?.value) }} {{ L("capitalised","مرسمَل","capitalisé") }}</div>
      </div>
    </div>

    <!-- draft triage -->
    <div v-if="drafts.length" class="bg-white rounded-card border border-amber-200 shadow-card overflow-hidden">
      <div class="px-4 py-2.5 border-b border-line-hair text-[12px] font-bold flex items-center gap-2">
        <Icon name="clock" :size="14" color="#b45309" />{{ L("Stalled drafts — finish or drop","درافت واقفة — كمّلها أو امسحها","Brouillons en attente") }}
        <span class="text-[10px] text-ink-muted">{{ drafts.length }}</span>
      </div>
      <div class="overflow-x-auto"><table class="w-full text-[12px]">
        <thead><tr style="background:#fffbeb" class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">
          <th class="px-4 py-2 text-start">{{ L("Voucher","السند","Bon") }}</th>
          <th class="px-3 py-2 text-start">{{ L("Date","التاريخ","Date") }}</th>
          <th class="px-3 py-2 text-start">{{ L("Receipts","الاستلامات","Réceptions") }}</th>
          <th class="px-3 py-2 text-start">{{ L("Charges","المصاريف","Charges") }}</th>
          <th class="px-3 py-2 text-end">{{ L("Total","الإجمالي","Total") }}</th>
          <th class="px-4 py-2 text-end"></th>
        </tr></thead>
        <tbody>
          <tr v-for="d0 in drafts" :key="d0.name" class="border-t border-line-hair align-top">
            <td class="px-4 py-2.5 font-mono text-[11px]">
              <router-link :to="{ path: '/accounting/items/landed', query: { id: d0.name } }" class="text-accent-dark hover:underline">{{ d0.name }}</router-link>
              <div class="text-[9.5px] text-ink-muted">{{ d0.items_n }} {{ L("item lines","سطر صنف","lignes") }} · {{ d0.basis }}</div>
            </td>
            <td class="px-3 py-2.5 whitespace-nowrap text-ink-3">{{ d0.dt }}</td>
            <td class="px-3 py-2.5 text-[10.5px] font-mono max-w-[160px]">
              <router-link v-for="r in d0.receipts.slice(0,3)" :key="r" :to="{ path: '/accounting/purchases/received', query: { id: r } }" class="truncate block text-accent-dark hover:underline">{{ r }}</router-link>
              <div v-if="d0.receipts.length>3" class="text-ink-muted">+{{ d0.receipts.length-3 }}</div>
            </td>
            <td class="px-3 py-2.5 text-[10.5px] max-w-[220px]"><div v-for="(c,i) in d0.charges.slice(0,3)" :key="i" class="truncate">{{ money(c.amount) }} — {{ (c.description || c.expense_account).slice(0,40) }}</div><div v-if="d0.charges.length>3" class="text-ink-muted">+{{ d0.charges.length-3 }}</div></td>
            <td class="px-3 py-2.5 text-end tnum font-semibold whitespace-nowrap">{{ money(d0.total) }}</td>
            <td class="px-4 py-2.5 text-end whitespace-nowrap">
              <div v-if="canWrite" class="inline-flex items-center gap-1.5">
                <button type="button" class="h-7 px-2.5 rounded-chip text-[11px] font-bold text-white bg-emerald-600 hover:bg-emerald-700 disabled:opacity-40" :disabled="busy===d0.name" @click="submitDraft(d0)">{{ busy===d0.name ? '…' : L('Post','رحّل','Valider') }}</button>
                <button type="button" class="h-7 px-2.5 rounded-chip text-[11px] font-semibold text-rose-600 border border-rose-200 hover:bg-rose-50 disabled:opacity-40" :disabled="busy===d0.name" @click="dropDraft(d0)">{{ L("Delete","احذف","Suppr.") }}</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table></div>
    </div>

    <!-- shipment builder -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-3">
      <!-- receipts panel -->
      <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
        <div class="px-4 py-2.5 border-b border-line-hair text-[12px] font-bold flex items-center gap-2">
          <Icon name="truck" :size="14" color="#0b5c4f" />{{ L("1 · Pick the shipment's receipts","١ · اختار استلامات الشحنة","1 · Réceptions") }}
          <span class="text-[10px] text-ink-muted">{{ selReceipts.length }} {{ L("selected","مختار","choisis") }}</span>
          <input v-model="rq" @input="debouncedReceipts" :placeholder="L('search receipt / supplier…','ابحث استلام / مورّد…','rechercher…')" class="ms-auto w-[180px] h-7 bg-app-warm/40 border border-line-2 rounded-chip px-2.5 text-[11px] focus:outline-none" />
        </div>
        <TableLoading v-if="loading" :rows="5" />
        <div v-else class="overflow-y-auto max-h-[320px]">
          <table class="w-full text-[12px]">
            <tbody>
              <tr v-for="r in receipts" :key="r.name" class="border-t border-line-hair hover:bg-app-warm/40 cursor-pointer" @click="toggleReceipt(r.name)">
                <td class="ps-4 py-2 w-8"><input type="checkbox" :checked="selReceipts.includes(r.name)" class="accent-emerald-700 pointer-events-none" /></td>
                <td class="px-2 py-2 font-mono text-[10.5px] whitespace-nowrap"><router-link :to="{ path: '/accounting/purchases/received', query: { id: r.name } }" class="text-accent-dark hover:underline" @click.stop>{{ r.name }}</router-link></td>
                <td class="px-2 py-2 truncate max-w-[140px]">{{ r.supplier }}</td>
                <td class="px-2 py-2 text-ink-3 whitespace-nowrap">{{ String(r.dt).slice(0,10) }}</td>
                <td class="px-3 py-2 text-end tnum whitespace-nowrap">{{ money(r.value) }} <span class="text-[9px] text-ink-muted">· {{ r.items }} {{ L("items","صنف","art.") }}</span></td>
              </tr>
              <tr v-if="!receipts.length"><td colspan="5" class="px-4 py-6 text-center text-ink-muted text-[11px]">{{ L("All 2026 receipts are covered 🎉","كل استلامات 2026 متغطية 🎉","Tout est couvert") }}</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- charges panel -->
      <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
        <div class="px-4 py-2.5 border-b border-line-hair text-[12px] font-bold flex items-center gap-2">
          <Icon name="cash" :size="14" color="#0b5c4f" />{{ L("2 · Attach the charges","٢ · علّق المصاريف","2 · Charges") }}
          <span class="text-[10px] text-ink-muted">{{ money(chargesTotal) }}</span>
          <button type="button" class="ms-auto text-[10.5px] font-bold text-accent-dark hover:underline" @click="manual = !manual">{{ manual ? L("hide manual","اخفي اليدوي","cacher") : L("+ manual charge","+ مصروف يدوي","+ manuel") }}</button>
        </div>
        <div v-if="manual" class="px-4 py-3 border-b border-line-hair bg-app-warm/30 flex items-center gap-2 flex-wrap">
          <input v-model.trim="mCharge.description" :placeholder="L('description','الوصف','description')" class="flex-1 min-w-[140px] h-8 bg-white border border-line-2 rounded-chip px-2.5 text-[11px] focus:outline-none" />
          <select v-model="mCharge.expense_account" class="w-[210px] h-8 bg-white border border-line-2 rounded-chip px-2 text-[11px] focus:outline-none">
            <option value="">{{ L("expense account…","حساب المصروف…","compte…") }}</option>
            <option v-for="a in inboxAccounts" :key="a" :value="a">{{ a }}</option>
          </select>
          <input v-model.number="mCharge.amount" type="number" min="0" step="0.01" placeholder="0.00" class="w-[100px] h-8 bg-white border border-line-2 rounded-chip px-2.5 text-[11px] tnum text-end focus:outline-none" />
          <button type="button" class="h-8 px-3 rounded-chip text-[11px] font-bold text-white bg-brand hover:bg-brand-dark disabled:opacity-50" :disabled="!(mCharge.amount>0) || !mCharge.expense_account" @click="addManual">{{ L("Add","أضف","OK") }}</button>
        </div>
        <div class="overflow-y-auto max-h-[280px]">
          <table class="w-full text-[12px]">
            <tbody>
              <tr v-for="(c, i) in inbox" :key="c.vn + c.account + c.dt" class="border-t border-line-hair hover:bg-app-warm/40 cursor-pointer" @click="toggleCharge(i)">
                <td class="ps-4 py-2 w-8"><input type="checkbox" :checked="selCharges.includes(i)" class="accent-emerald-700 pointer-events-none" /></td>
                <td class="px-2 py-2"><router-link :to="chargeLink(c)" class="font-mono text-[10.5px] text-accent-dark hover:underline" @click.stop>{{ c.vn }}</router-link>
                  <div class="text-[10px] text-ink-muted truncate max-w-[200px]">{{ c.account_name }} · {{ c.remarks || c.vt }}</div>
                  <div v-if="c.account_absorbed" class="text-[9.5px] text-amber-700">⚠ {{ money(c.account_absorbed) }} {{ L("already capitalised on this account — don't re-attach the same bill","اترسمل قبل كده على الحساب ده — متعلقش نفس الفاتورة تاني","déjà capitalisé sur ce compte") }}</div>
                </td>
                <td class="px-2 py-2 text-ink-3 whitespace-nowrap text-[11px]">{{ c.dt }}</td>
                <td class="px-3 py-2 text-end tnum font-semibold whitespace-nowrap">{{ money(c.amount) }}</td>
              </tr>
              <tr v-for="(m, i) in manualCharges" :key="'m'+i" class="border-t border-line-hair" style="background:#f0fdf4">
                <td class="ps-4 py-2 w-8"><button type="button" class="text-rose-500 text-[13px]" @click="manualCharges.splice(i,1)">×</button></td>
                <td class="px-2 py-2 text-[11px]" colspan="2">{{ m.description }} <span class="text-[10px] text-ink-muted">{{ m.expense_account }}</span></td>
                <td class="px-3 py-2 text-end tnum font-semibold">{{ money(m.amount) }}</td>
              </tr>
              <tr v-if="inbox.length >= 500"><td colspan="4" class="px-4 py-2 text-center text-[10px] text-amber-700">{{ L("Showing the latest 500 charges — post some to surface older ones.","بيعرض أحدث 500 مصروف — رحّل شوية عشان الأقدم يظهر.","500 dernières charges.") }}</td></tr>
              <tr v-if="!inbox.length && !manualCharges.length"><td colspan="4" class="px-4 py-6 text-center text-ink-muted text-[11px]">{{ L("No unallocated charges — add one manually if the bill isn't booked yet.","مفيش مصاريف غير موزعة — أضف يدوي لو الفاتورة لسه ماتسجلتش.","Aucune charge.") }}</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- preview + post -->
    <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
      <div class="px-4 py-2.5 border-b border-line-hair text-[12px] font-bold flex items-center gap-2 flex-wrap">
        <Icon name="layers" :size="14" color="#0b5c4f" />{{ L("3 · Preview allocation → 4 · Post","٣ · عاين التوزيع ← ٤ · رحّل","3 · Aperçu → 4 · Valider") }}
        <select v-model="basis" class="h-7 bg-app-warm/40 border border-line-2 rounded-chip px-2 text-[11px] focus:outline-none" @change="preview = null">
          <option value="Amount">{{ L("by value (customs)","بالقيمة (جمارك)","par valeur") }}</option>
          <option value="Weight">{{ L("by weight (freight)","بالوزن (شحن)","par poids") }}</option>
          <option value="Qty">{{ L("by qty","بالكمية","par qté") }}</option>
        </select>
        <div class="ms-auto inline-flex items-center gap-2">
          <button type="button" class="h-8 px-3.5 rounded-chip text-[12px] font-semibold text-accent-dark border border-line-2 hover:bg-app-warm disabled:opacity-40" :disabled="!canPreview || previewing" @click="doPreview">{{ previewing ? '…' : L("Preview","عاين","Aperçu") }}</button>
          <button type="button" class="h-8 px-4 rounded-chip text-[12px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand disabled:opacity-40" :disabled="!preview || posting || !canWrite" @click="doPost">{{ posting ? '…' : L("Post landed cost","رحّل التحميل","Valider") }}</button>
        </div>
      </div>
      <div v-if="preview" class="px-4 py-2 border-b border-line-hair text-[11px] text-ink-3 flex items-center gap-3 flex-wrap" style="background:#f0fdf4">
        <span class="font-bold text-emerald-700">{{ money(preview.total_charge) }} {{ L("over","على","sur") }} {{ preview.lines_n }} {{ L("item lines","سطر","lignes") }}</span>
        <span>· {{ preview.later_moves_to_repost.toLocaleString() }} {{ L("later stock moves will be reposted (COGS heals)","حركة لاحقة هيتعاد حسابها (الـ COGS يتصلح)","mouvements recalculés") }}</span>
        <span v-if="preview.weightless_n" class="text-amber-700 font-semibold">· ⚠ {{ preview.weightless_n }} {{ L("lines have no weight → get 0 share","سطر بدون وزن ← نصيبه صفر","lignes sans poids") }}</span>
      </div>
      <div v-if="preview" class="overflow-x-auto max-h-[300px] overflow-y-auto">
        <table class="w-full text-[12px]">
          <thead><tr style="background:#fafaf9" class="text-[10px] font-bold uppercase tracking-wider text-ink-muted sticky top-0">
            <th class="px-4 py-2 text-start">{{ L("Item","الصنف","Article") }}</th>
            <th class="px-3 py-2 text-end">{{ L("Qty","كمية","Qté") }}</th>
            <th class="px-3 py-2 text-end">{{ L("Rate now","السعر الحالي","Taux") }}</th>
            <th class="px-3 py-2 text-end">{{ L("Allocated","الموزَّع","Alloué") }}</th>
            <th class="px-3 py-2 text-end">{{ L("+ / unit","+ للوحدة","+ / unité") }}</th>
            <th class="px-4 py-2 text-end">{{ L("New rate","السعر الجديد","Nouveau") }}</th>
          </tr></thead>
          <tbody>
            <tr v-for="(ln, i) in preview.lines" :key="i" class="border-t border-line-hair">
              <td class="px-4 py-1.5 font-mono text-[10.5px]">{{ ln.item_code }}</td>
              <td class="px-3 py-1.5 text-end tnum">{{ ln.qty }}</td>
              <td class="px-3 py-1.5 text-end tnum">{{ money(ln.rate) }}</td>
              <td class="px-3 py-1.5 text-end tnum text-emerald-700">+{{ money(ln.alloc) }}</td>
              <td class="px-3 py-1.5 text-end tnum text-ink-3">+{{ money(ln.per_unit) }}</td>
              <td class="px-4 py-1.5 text-end tnum font-semibold">{{ money(ln.new_rate) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="px-4 py-6 text-center text-[11.5px] text-ink-muted">{{ L("Pick receipts + charges, then Preview — nothing posts until step 4.","اختار استلامات ومصاريف وبعدين عاين — مفيش ترحيل قبل الخطوة ٤.","Choisissez puis aperçu.") }}</div>
      <div class="px-4 py-2 border-t border-line-hair text-[10.5px] text-ink-muted flex items-center gap-1.5">
        <Icon name="alert" :size="11" color="#9a8f86" />{{ L("Posting: Dr stock / Cr the charge's own expense account — audited, gated over 10K, revert = cancel the voucher.","الترحيل: مدين المخزون / دائن نفس حساب المصروف — مدقّق، فوق 10K موافقة، والتراجع = إلغاء السند.","Validation auditée & réversible.") }}
      </div>
    </div>

    <!-- recent vouchers -->
    <div class="text-[11px] text-ink-muted">
      <router-link :to="{ path: '/accounting/items/landed', query: { list: 1 } }" class="text-accent-dark font-semibold hover:underline">{{ L("View all landed-cost vouchers →","كل سندات التحميل ←","Tous les bons →") }}</router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";
import { useAuth } from "@/composables/useAuth";
import { useToast } from "@/composables/useToast";
import { fmtAmount } from "@/utils/helpers";

const { locale } = useI18n();
const { entityId } = useUi();
const { can } = useAuth();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const money = (n) => fmtAmount(n);
const canWrite = computed(() => can("post_entries"));

const ov = ref({});
const drafts = ref([]);
const receipts = ref([]);
const inbox = ref([]);
const loading = ref(true);
const busy = ref("");
const rq = ref("");
const selReceipts = ref([]);
const selCharges = ref([]);
const manualCharges = ref([]);
const manual = ref(false);
const mCharge = reactive({ description: "", expense_account: "", amount: null });
const basis = ref("Amount");
const preview = ref(null);
const previewing = ref(false), posting = ref(false);

const inboxAccounts = computed(() => [...new Set(inbox.value.map((c) => c.account))]);
const chargesTotal = computed(() =>
  selCharges.value.reduce((s, i) => s + Number(inbox.value[i]?.amount || 0), 0) +
  manualCharges.value.reduce((s, m) => s + Number(m.amount || 0), 0));
const canPreview = computed(() => selReceipts.value.length && (selCharges.value.length || manualCharges.value.length));

async function load() {
  loading.value = true;
  preview.value = null; selReceipts.value = []; selCharges.value = [];
  try {
    const c = { company: currentCompany() };
    [ov.value, drafts.value, receipts.value, inbox.value] = await Promise.all([
      api.call("accounting_portal.api.landed_pipeline.pipeline_overview", c, { fresh: true }),
      api.call("accounting_portal.api.landed_pipeline.draft_lcvs", c, { fresh: true }),
      api.call("accounting_portal.api.landed_pipeline.receipts_uncovered", c, { fresh: true }),
      api.call("accounting_portal.api.landed_pipeline.charge_inbox", c, { fresh: true }),
    ]);
  } catch { /* keep last */ }
  finally { loading.value = false; }
}
load();
watch(entityId, load);

let t = null;
function debouncedReceipts() {
  clearTimeout(t);
  t = setTimeout(async () => {
    receipts.value = await api.call("accounting_portal.api.landed_pipeline.receipts_uncovered",
      { company: currentCompany(), q: rq.value || undefined }, { fresh: true });
  }, 350);
}

function chargeLink(c) {
  if (c.vt === "Journal Entry") return { path: "/accounting/accountant/journals", query: { id: c.vn } };
  if (c.vt === "Purchase Invoice") return { path: "/accounting/purchases/bills", query: { id: c.vn } };
  if (c.vt === "Payment Entry") return { path: "/accounting/purchases/payments", query: { id: c.vn } };
  return { path: "/accounting/accountant/gl", query: { voucher: c.vn } };
}

function toggleReceipt(name) {
  const i = selReceipts.value.indexOf(name);
  i >= 0 ? selReceipts.value.splice(i, 1) : selReceipts.value.push(name);
  preview.value = null;
}
function toggleCharge(i) {
  const j = selCharges.value.indexOf(i);
  j >= 0 ? selCharges.value.splice(j, 1) : selCharges.value.push(i);
  preview.value = null;
}
function addManual() {
  manualCharges.value.push({ ...mCharge });
  mCharge.description = ""; mCharge.amount = null;
  preview.value = null;
}

function buildCharges() {
  return [
    ...selCharges.value.map((i) => {
      const c = inbox.value[i];
      return { expense_account: c.account, amount: c.amount, description: c.account_name, source: c.vn };
    }),
    ...manualCharges.value.map((m) => ({ expense_account: m.expense_account, amount: m.amount, description: m.description || m.expense_account })),
  ];
}

async function doPreview() {
  if (!canPreview.value || previewing.value) return;
  previewing.value = true;
  try {
    preview.value = await api.call("accounting_portal.api.landed_pipeline.preview_lcv", {
      company: currentCompany(), receipts: selReceipts.value, charges: buildCharges(), distribute_by: basis.value,
    }, { fresh: true });
  } catch (e) { toast.error(String(e?.message || e).slice(0, 180)); }
  finally { previewing.value = false; }
}

async function doPost() {
  if (!preview.value || posting.value) return;
  if (!window.confirm(L(
    `Post ${money(preview.value.total_charge)} over ${selReceipts.value.length} receipt(s)? ${preview.value.later_moves_to_repost} later moves will be reposted.`,
    `ترحيل ${money(preview.value.total_charge)} على ${selReceipts.value.length} استلام؟ هيتعاد حساب ${preview.value.later_moves_to_repost} حركة لاحقة.`,
    `Valider ${money(preview.value.total_charge)} ?`))) return;
  posting.value = true;
  try {
    const res = await api.call("accounting_portal.api.landed_pipeline.post_lcv", {
      company: currentCompany(), receipts: selReceipts.value, charges: buildCharges(), distribute_by: basis.value,
    });
    if (res && res.status === "Proposed") toast.success(L("Sent for approval", "أُرسل للموافقة", "Envoyé"));
    else toast.success(L("Landed cost posted — repost running", "اترحّل — إعادة الحساب شغالة", "Validé"));
    manualCharges.value = [];
    load();
  } catch (e) { toast.error(String(e?.message || e).slice(0, 180)); }
  finally { posting.value = false; }
}

async function submitDraft(d0) {
  if (busy.value) return;
  if (!window.confirm(L(`Post draft ${d0.name} (${money(d0.total)})?`, `ترحيل الدرافت ${d0.name} (${money(d0.total)})؟`, `Valider ${d0.name} ?`))) return;
  busy.value = d0.name;
  try {
    const res = await api.call("accounting_portal.api.landed_pipeline.submit_draft_lcv", { company: currentCompany(), name: d0.name });
    if (res && res.status === "Proposed") toast.success(L("Sent for approval", "أُرسل للموافقة", "Envoyé"));
    else toast.success(L("Posted", "اترحّل", "Validé"));
    load();
  } catch (e) { toast.error(String(e?.message || e).slice(0, 180)); }
  finally { busy.value = ""; }
}

async function dropDraft(d0) {
  if (busy.value) return;
  if (!window.confirm(L(`Delete draft ${d0.name}? This cannot be undone.`, `حذف الدرافت ${d0.name}؟ مفيش رجوع.`, `Supprimer ${d0.name} ?`))) return;
  busy.value = d0.name;
  try {
    await api.call("accounting_portal.api.landed_pipeline.delete_draft_lcv", { company: currentCompany(), name: d0.name });
    toast.success(L("Deleted", "اتحذف", "Supprimé"));
    load();
  } catch (e) { toast.error(String(e?.message || e).slice(0, 180)); }
  finally { busy.value = ""; }
}
</script>
