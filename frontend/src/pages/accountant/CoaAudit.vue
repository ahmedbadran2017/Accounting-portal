<template>
  <div class="space-y-3.5">
    <!-- per-company health -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <button v-for="c in overview" :key="c.company" type="button" class="bg-white rounded-card border shadow-card px-4 py-3.5 text-start transition-all"
              :class="sel === c.company ? 'shadow-cardHover -translate-y-0.5 border-accent/50' : 'border-line hover:-translate-y-0.5'" @click="pick(c.company)">
        <div class="flex items-center justify-between gap-2">
          <span class="text-[12px] font-bold truncate">{{ c.company }}</span>
          <span class="text-[15px] font-extrabold tnum" :style="`color:${scoreColor(c.score)}`">{{ c.score }}</span>
        </div>
        <div class="mt-1.5 flex flex-wrap gap-1 text-[10px] font-semibold">
          <span v-if="c.counts.sign" class="px-1.5 py-0.5 rounded-chip bg-rose-50 text-rose-600">{{ c.counts.sign }} {{ L('sign','إشارة','signe') }}</span>
          <span v-if="c.counts.miscash" class="px-1.5 py-0.5 rounded-chip bg-amber-50 text-amber-700">{{ c.counts.miscash }} {{ L('cash','كاش','caisse') }}</span>
          <span v-if="c.counts.junk" class="px-1.5 py-0.5 rounded-chip bg-stone-100 text-stone-600">{{ c.counts.junk }} {{ L('junk','زبالة','junk') }}</span>
          <span v-if="c.counts.dead" class="px-1.5 py-0.5 rounded-chip bg-app-warm text-ink-muted">{{ c.counts.dead }} {{ L('dead','ميّت','morts') }}</span>
          <span v-if="c.counts.duplicates" class="px-1.5 py-0.5 rounded-chip bg-sky-50 text-sky-700">{{ c.counts.duplicates }} {{ L('dup','مكرّر','dup') }}</span>
        </div>
        <div class="mt-1.5 h-1.5 rounded-full bg-app-warm overflow-hidden"><span class="block h-full rounded-full" :style="`width:${c.score}%;background:${scoreColor(c.score)}`"></span></div>
      </button>
      <div v-if="!overview.length && !ovLoad" class="text-[12px] text-ink-muted py-8">{{ L('No companies.','لا شركات.','Aucune.') }}</div>
    </div>

    <!-- findings for the selected company -->
    <div v-if="sel" class="bg-white rounded-card border border-line shadow-card overflow-hidden">
      <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2 flex-wrap">
        <Icon name="ledger" :size="14" color="#0b5c4f" /><span class="text-[12px] font-bold truncate max-w-[200px]">{{ sel }}</span>
        <span class="text-[10px] text-ink-muted">{{ d.total }} {{ L('accounts','حساب','comptes') }} · {{ L('score','النقاط','score') }} <b :style="`color:${scoreColor(d.score)}`">{{ d.score }}</b></span>
        <div class="flex gap-1 bg-app-warm/50 rounded-chip p-0.5 ms-auto overflow-x-auto">
          <button v-for="ch in CHECKS" :key="ch.k" class="px-2.5 py-1 rounded-lg text-[11px] font-semibold whitespace-nowrap" :class="tab===ch.k ? 'bg-white text-accent-dark shadow-card' : 'text-ink-3'" @click="tab=ch.k">
            {{ ch.label() }} <span v-if="count(ch.k)" class="tnum">({{ count(ch.k) }})</span>
          </button>
        </div>
      </div>

      <div class="px-4 py-2 bg-app-warm/30 border-b border-line-hair text-[11px] text-ink-2 flex items-center gap-2 flex-wrap">
        <Icon name="alert" :size="12" color="#b45309" /><span>{{ tabHint() }}</span>
        <button v-if="tab==='dead' && isAdmin && count('dead')" type="button" :disabled="busy==='bulk'" class="ms-auto h-7 px-2.5 rounded-chip text-[11px] font-bold text-white bg-ink hover:brightness-110 disabled:opacity-50" @click="disableDead">{{ L('Close all dead','اقفل الميّتة','Fermer morts') }} ({{ count('dead') }})</button>
        <button v-if="tab==='empty_group' && isAdmin && count('empty_group')" type="button" :disabled="busy==='bulk'" class="ms-auto h-7 px-2.5 rounded-chip text-[11px] font-bold text-white bg-teal-700 hover:bg-teal-800 disabled:opacity-50" @click="makePostableAll">{{ L('Make all postable','خلّيهم قابلين للترحيل','Rendre saisissables') }} ({{ count('empty_group') }})</button>
      </div>

      <TableLoading v-if="loading" :rows="8" />
      <div v-else class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <tbody>
            <!-- duplicate groups -->
            <template v-if="tab==='duplicates'">
              <tr v-for="(g,i) in rows" :key="i" class="border-t border-line-hair first:border-t-0">
                <td class="px-4 py-2"><div class="text-[10px] text-ink-muted uppercase tracking-wider mb-0.5">{{ g.accounts.length }} {{ L('same name','بنفس الاسم','même nom') }}</div>
                  <div v-for="a in g.accounts" :key="a.account" class="flex items-center gap-2 py-0.5"><span class="font-mono text-[10px] text-ink-muted w-24">{{ a.num || '—' }}</span><button class="text-[11.5px] hover:text-accent-dark text-start truncate max-w-[420px]" @click="gl(a.account)">{{ a.account }}</button><span class="text-[9px] px-1 rounded bg-app-warm text-ink-muted">{{ a.root }}</span></div>
                </td>
              </tr>
            </template>
            <!-- account rows -->
            <template v-else>
              <tr v-for="r in rows" :key="r.account" class="border-t border-line-hair first:border-t-0 hover:bg-app-warm/40" :class="r.disabled ? 'opacity-50' : ''">
                <td class="px-4 py-2.5"><button class="font-semibold text-start hover:text-accent-dark truncate max-w-[300px] block" @click="gl(r.account)">{{ r.nm }}</button><div class="text-[10px] text-ink-muted font-mono">{{ r.num }} · {{ r.root }}<span v-if="r.typ"> · {{ r.typ }}</span></div></td>
                <td class="px-3 py-2.5 text-end tnum" :class="r.bal < 0 ? 'text-rose-600' : 'text-ink-3'">{{ money(r.bal) }} <span class="text-[9px] text-ink-muted">{{ r.ccy }}</span></td>
                <td class="px-3 py-2.5 text-end tnum text-ink-muted hidden sm:table-cell">{{ r.n }} {{ L('txn','حركة','écr.') }}</td>
                <td class="px-4 py-2.5 text-end whitespace-nowrap">
                  <span v-if="r.suggestion" class="text-[10px] text-amber-700 me-2">{{ r.suggestion }}</span>
                  <span v-if="r.expected" class="text-[10px] text-rose-600 me-2">{{ L('should be','المفروض','devrait') }} {{ r.expected }}</span>
                  <template v-if="isAdmin && !r.disabled">
                    <button v-if="tab==='dead' || (tab==='junk' && r.n===0)" type="button" :disabled="busy===r.account" class="inline-flex items-center gap-1 h-7 px-2.5 rounded-chip text-[11px] font-bold text-white bg-ink hover:brightness-110 disabled:opacity-50" @click="disableOne(r)">{{ L('Close','اقفل','Fermer') }}</button>
                    <button v-else-if="tab==='spaces'" type="button" :disabled="busy===r.account" class="inline-flex items-center gap-1 h-7 px-2.5 rounded-chip text-[11px] font-bold text-white bg-teal-700 hover:bg-teal-800 disabled:opacity-50" @click="trim(r)">{{ L('Trim','قصّ','Nettoyer') }}</button>
                    <button v-else-if="tab==='empty_group'" type="button" :disabled="busy===r.account" class="inline-flex items-center gap-1 h-7 px-2.5 rounded-chip text-[11px] font-bold text-white bg-teal-700 hover:bg-teal-800 disabled:opacity-50" @click="makePostable(r)">{{ L('Make postable','قابل للترحيل','Rendre saisissable') }}</button>
                    <select v-else-if="tab==='miscash'" class="h-7 bg-app-warm/40 border border-line-2 rounded-chip px-2 text-[11px]" :disabled="busy===r.account" @change="reclass(r,$event.target.value)">
                      <option value="__">{{ L('reclassify…','أعِد التصنيف…','reclasser…') }}</option>
                      <option value="">{{ L('Remove type','شيل النوع','Retirer type') }}</option>
                      <option value="Receivable">Receivable</option><option value="Payable">Payable</option>
                    </select>
                  </template>
                </td>
              </tr>
            </template>
            <tr v-if="!rows.length"><td colspan="4" class="px-4 py-10 text-center text-ink-muted">{{ L('Nothing flagged here. ✓','لا شيء هنا. ✓','Rien. ✓') }}</td></tr>
          </tbody>
        </table>
      </div>
    </div>
    <div v-else-if="!ovLoad" class="bg-white rounded-card border border-line shadow-card py-12 text-center text-[12px] text-ink-muted">{{ L('Pick a company to audit its chart of accounts.','اختر شركة لتدقيق دليل حساباتها.','Choisissez une société.') }}</div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
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
const router = useRouter();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const money = (n) => fmtAmount(n);
const isAdmin = computed(() => can("manage_users"));
const scoreColor = (s) => (s >= 85 ? "#047857" : s >= 60 ? "#b45309" : "#e11d48");

const CHECKS = [
  { k: "sign", label: () => L("Wrong sign", "إشارة عكسية", "Signe") },
  { k: "miscash", label: () => L("Miscl. cash", "كاش مصنّف غلط", "Caisse") },
  { k: "junk", label: () => L("Junk", "زبالة", "Junk") },
  { k: "duplicates", label: () => L("Duplicates", "مكرّر", "Doublons") },
  { k: "outliers", label: () => L("Outliers", "قيم شاذّة", "Aberrants") },
  { k: "spaces", label: () => L("Name spaces", "مسافات", "Espaces") },
  { k: "empty_group", label: () => L("Empty groups", "مجموعات فاضية", "Groupes vides") },
  { k: "dead", label: () => L("Dead", "ميّت", "Morts") },
  { k: "group_with_gl", label: () => L("Group w/ GL", "مجموعة عليها قيود", "Groupe+GL") },
];

const overview = ref([]), ovLoad = ref(true);
const sel = ref(""), d = ref({ counts: {}, checks: {} }), loading = ref(false), tab = ref("sign"), busy = ref("");

const count = (k) => (d.value.counts && d.value.counts[k]) || 0;
const rows = computed(() => (d.value.checks && d.value.checks[tab.value]) || []);

function tabHint() {
  const m = {
    sign: L("Asset/Expense with a credit balance or Liability/Income with a debit balance — likely mis-stated. Drill to fix in the GL.", "أصل/مصروف برصيد دائن أو التزام/دخل برصيد مدين — غالبًا مغلوط. افتح الأستاذ لتصحيحه.", "Solde du mauvais côté."),
    miscash: L("Typed Bank/Cash but really a credit card / carrier clearing / intercompany — reclassify out of the cash picture.", "مصنّف بنك/كاش لكنه كارت/مقاصّة/بينيّ — أعِد تصنيفه.", "Reclasser."),
    junk: L("Placeholder / junk accounts. Close the empty ones.", "حسابات مؤقتة/زبالة. اقفل الفاضي منها.", "Fermer."),
    duplicates: L("Same-name accounts — often a legit AR/AP pair, sometimes a true duplicate. Review each.", "أسماء مكرّرة — غالبًا زوج AR/AP مشروع، أحيانًا تكرار حقيقي. راجع كلًا.", "Vérifier."),
    outliers: L("Balances above 50M — inspect for the stock/correction distortions.", "أرصدة فوق 50 مليون — افحصها.", "Inspecter."),
    spaces: L("Leading/trailing spaces in the name or number — trim to clean.", "مسافات زائدة في الاسم/الرقم — قصّها للتنظيف.", "Nettoyer."),
    dead: L("Leaf accounts with zero activity — close to declutter the tree.", "حسابات بلا حركة — اقفلها لتنظيف الشجرة.", "Fermer."),
    group_with_gl: L("Group accounts carrying postings — a structural error (postings belong on leaves).", "حسابات مجموعة عليها قيود — خطأ هيكلي.", "Erreur structurelle."),
    empty_group: L("Group accounts with no children and no postings — you can't book to them, so that expense can't be recorded. Make them postable leaves.", "حسابات مجموعة بلا فروع وبلا قيود — مايتقيّدش عليها فالمصروف مستحيل يتسجّل. خليها أوراق قابلة للترحيل.", "Rendre saisissables."),
  };
  return m[tab.value] || "";
}

async function loadOverview() {
  ovLoad.value = true;
  try { const r = await api.call("accounting_portal.api.ledger.coa_audit_all", {}, { fresh: true }); overview.value = r?.companies || []; }
  catch { overview.value = []; }
  finally { ovLoad.value = false; }
  if (!sel.value && overview.value.length) pick((overview.value.find((c) => c.company === currentCompany()) || overview.value[0]).company);
}
async function pick(co) {
  sel.value = co; loading.value = true;
  try { d.value = await api.call("accounting_portal.api.ledger.coa_audit", { company: co }, { fresh: true }) || { counts: {}, checks: {} }; }
  catch { d.value = { counts: {}, checks: {} }; }
  finally { loading.value = false; }
  const firstWithCount = CHECKS.find((c) => count(c.k)) || CHECKS[0];
  tab.value = firstWithCount.k;
}
loadOverview();
watch(entityId, loadOverview);

function gl(account) { router.push({ path: "/accounting/accountant/gl", query: { account } }); }
async function act(fn, r) {
  busy.value = r.account;
  try { await fn(); toast.success(L("Done", "تم", "OK")); await pick(sel.value); await loadOverviewSilent(); }
  catch (e) { toast.error(String(e?.message || e).slice(0, 160)); }
  finally { busy.value = ""; }
}
async function loadOverviewSilent() { try { const r = await api.call("accounting_portal.api.ledger.coa_audit_all", {}, { fresh: true }); overview.value = r?.companies || overview.value; } catch { /* ignore */ } }
function disableOne(r) { if (!window.confirm(L(`Close ${r.nm}?`, `اقفل ${r.nm}؟`, `Fermer ?`))) return; act(() => api.call("accounting_portal.api.ledger.set_account_disabled", { company: sel.value, account: r.account, disabled: 1, dry_run: 0 }), r); }
function trim(r) { act(() => api.call("accounting_portal.api.ledger.trim_account", { company: sel.value, account: r.account }), r); }
function reclass(r, t) { if (t === "__") return; act(() => api.call("accounting_portal.api.ledger.reclassify_account", { company: sel.value, account: r.account, account_type: t }), r); }
function makePostable(r) { act(() => api.call("accounting_portal.api.ledger.make_account_postable", { company: sel.value, account: r.account }), r); }
async function makePostableAll() {
  if (busy.value) return;
  if (!window.confirm(L(`Make all ${count('empty_group')} empty groups postable in ${sel.value}? Reversible.`, `خلّي كل الـ ${count('empty_group')} مجموعة فاضية قابلة للترحيل؟`, `Convertir ?`))) return;
  busy.value = "bulk";
  try {
    const accts = (d.value.checks?.empty_group || []).map((x) => x.account);
    const r = await api.call("accounting_portal.api.ledger.make_postable_bulk", { company: sel.value, accounts: accts });
    toast.success(L(`${r.converted} made postable`, `${r.converted} بقوا قابلين للترحيل`, `${r.converted} convertis`));
    await pick(sel.value); await loadOverviewSilent();
  } catch (e) { toast.error(String(e?.message || e).slice(0, 160)); }
  finally { busy.value = ""; }
}
async function disableDead() {
  if (busy.value) return;
  if (!window.confirm(L(`Close all ${count('dead')} dead accounts in ${sel.value}? Reversible.`, `اقفل كل الـ ${count('dead')} حساب ميّت؟`, `Fermer ?`))) return;
  busy.value = "bulk";
  try { const r = await api.call("accounting_portal.api.ledger.disable_dead_accounts", { company: sel.value }); toast.success(L(`Closed ${r.disabled}`, `أُقفل ${r.disabled}`, `${r.disabled} fermés`)); await pick(sel.value); await loadOverviewSilent(); }
  catch (e) { toast.error(String(e?.message || e).slice(0, 160)); }
  finally { busy.value = ""; }
}
</script>
