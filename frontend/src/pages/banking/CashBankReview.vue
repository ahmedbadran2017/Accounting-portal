<template>
  <div class="space-y-3.5">
    <!-- summary -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <Kpi :label="L('Bank/Cash accounts','حسابات بنك/كاش','Comptes')" :value="String(sum.total||0)" color="#0369a1" :sub="L('typed as Bank or Cash','مُصنّفة بنك أو كاش','type banque/caisse')" />
      <button class="text-start" @click="filter='dead'"><Kpi :label="L('Dead (closeable)','ميّتة (تُقفل)','Mortes')" :value="String(sum.dead||0)" color="#78716c" :sub="L('0 balance · 0 activity','رصيد 0 · بلا حركة','0 solde')" /></button>
      <button class="text-start" @click="filter='misclassified'"><Kpi :label="L('Misclassified','غير مصنّفة صح','Mal classés')" :value="String(sum.misclassified||0)" color="#b45309" :sub="L('not really cash','ليست كاش فعلًا','pas cash')" /></button>
      <button class="text-start" @click="filter='neg'"><Kpi :label="L('Negative cash','كاش بالسالب','Caisse négative')" :value="String(sum.negative_cash||0)" color="#e11d48" :sub="L('impossible — review','مستحيل — راجع','à vérifier')" /></button>
    </div>

    <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
      <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2 flex-wrap">
        <Icon name="bank" :size="14" color="#0b5c4f" /><span class="text-[12px] font-bold">{{ L('Cash & bank cleanup','تنظيف الكاش والبنوك','Nettoyage') }}</span>
        <div class="flex gap-1 bg-app-warm/50 rounded-chip p-0.5 ms-1">
          <button v-for="fb in FILTERS" :key="fb.k" class="px-2.5 py-1 rounded-lg text-[11px] font-semibold" :class="filter===fb.k ? 'bg-white text-accent-dark shadow-card' : 'text-ink-3'" @click="filter=fb.k">{{ fb.label() }}</button>
        </div>
        <button v-if="isAdmin && sum.dead" type="button" :disabled="busy==='bulk'" class="ms-auto inline-flex items-center gap-1.5 h-9 px-3.5 rounded-chip text-[12px] font-bold text-white bg-ink hover:brightness-110 disabled:opacity-50" @click="disableDead">
          <Icon :name="busy==='bulk' ? 'clock' : 'close'" :size="13" />{{ L('Close all dead','اقفل الميّتة كلها','Fermer les mortes') }} ({{ sum.dead }})
        </button>
      </div>
      <TableLoading v-if="loading" :rows="8" />
      <div v-else class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead><tr style="background:#fafaf9" class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">
            <th class="px-4 py-2 text-start">{{ L('Account','الحساب','Compte') }}</th>
            <th class="px-3 py-2 text-start">{{ L('Type','النوع','Type') }}</th>
            <th class="px-3 py-2 text-end">{{ L('Balance','الرصيد','Solde') }}</th>
            <th class="px-3 py-2 text-end hidden sm:table-cell">{{ L('Txns','حركات','Écrit.') }}</th>
            <th class="px-3 py-2 text-start">{{ L('Suggestion','الاقتراح','Suggestion') }}</th>
            <th class="px-4 py-2 text-end">{{ L('Action','إجراء','Action') }}</th>
          </tr></thead>
          <tbody>
            <tr v-for="r in shown" :key="r.name" class="border-t border-line-hair" :class="r.disabled ? 'opacity-50' : ''">
              <td class="px-4 py-2.5"><div class="font-semibold truncate max-w-[280px]">{{ r.nm }}</div><div class="text-[10px] text-ink-muted font-mono">{{ r.num }}<span v-if="r.last"> · {{ r.last }}</span></div></td>
              <td class="px-3 py-2.5"><span class="text-[10px] font-bold px-1.5 py-0.5 rounded-chip" :class="r.typ==='Cash' ? 'bg-amber-50 text-amber-700' : 'bg-sky-50 text-sky-700'">{{ r.typ }}</span></td>
              <td class="px-3 py-2.5 text-end tnum font-semibold" :class="r.bal < 0 ? 'text-rose-600' : ''">{{ money(r.bal) }} <span class="text-[9px] text-ink-muted">{{ r.ccy }}</span></td>
              <td class="px-3 py-2.5 text-end tnum text-ink-3 hidden sm:table-cell">{{ r.n }}</td>
              <td class="px-3 py-2.5"><span class="text-[10.5px] font-semibold px-1.5 py-0.5 rounded-chip" :style="`background:${bColor(r.bucket)}18;color:${bColor(r.bucket)}`">{{ r.suggestion }}</span></td>
              <td class="px-4 py-2.5 text-end whitespace-nowrap">
                <span v-if="r.disabled" class="text-[10px] text-ink-muted">{{ L('closed','مقفول','fermé') }}</span>
                <template v-else-if="isAdmin">
                  <button v-if="r.dead" type="button" :disabled="busy===r.name" class="inline-flex items-center gap-1 h-7 px-2.5 rounded-chip text-[11px] font-bold text-white bg-ink hover:brightness-110 disabled:opacity-50" @click="disableOne(r)">{{ L('Close','اقفل','Fermer') }}</button>
                  <select v-else-if="r.misclassified" class="h-7 bg-app-warm/40 border border-line-2 rounded-chip px-2 text-[11px] focus:outline-none" :disabled="busy===r.name" @change="reclass(r, $event.target.value)">
                    <option value="">{{ L('reclassify…','أعِد التصنيف…','reclasser…') }}</option>
                    <option value="">{{ L('Remove type (not cash)','شيل النوع (مش كاش)','Retirer le type') }}</option>
                    <option value="Receivable">Receivable</option>
                    <option value="Payable">Payable</option>
                  </select>
                  <span v-else class="text-[10px] text-ink-muted">—</span>
                </template>
                <span v-else class="text-[10px] text-ink-muted">{{ L('admin only','للمشرف فقط','admin') }}</span>
              </td>
            </tr>
            <tr v-if="!shown.length"><td colspan="6" class="px-4 py-10 text-center text-ink-muted">{{ L('Nothing here.','لا شيء هنا.','Rien.') }}</td></tr>
          </tbody>
        </table>
      </div>
      <div class="px-4 py-2 border-t border-line-hair text-[10.5px] text-ink-muted flex items-center gap-1.5">
        <Icon name="shield" :size="11" color="#9a8f86" />{{ L('Closing hides only dead (empty) accounts; reclassifying removes it from the cash picture. Both are audited & reversible in Activity.','الإقفال يخفي الحسابات الميّتة فقط؛ إعادة التصنيف تشيله من صورة الكاش. الاتنين مدقّقين وقابلين للتراجع.','Réversible & audité.') }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, h } from "vue";
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
const isAdmin = computed(() => can("manage_users"));
const Kpi = (p) => h("div", { class: "bg-white rounded-card border border-line shadow-card px-4 py-3 w-full" }, [
  h("div", { class: "text-[10px] font-bold uppercase tracking-wider text-ink-muted" }, p.label),
  h("div", { class: "text-[20px] font-extrabold mt-1 tnum", style: `color:${p.color}` }, p.value),
  h("div", { class: "text-[10px] text-ink-muted mt-0.5" }, p.sub)]);
Kpi.props = ["label", "value", "color", "sub"];

const BCOLOR = { bank: "#0369a1", petty: "#b45309", credit_card: "#be123c", clearing: "#7c3aed", interco: "#0891b2", junk: "#78716c", advance: "#db2777" };
const bColor = (b) => BCOLOR[b] || "#78716c";
const FILTERS = [
  { k: "all", label: () => L("All", "الكل", "Tout") },
  { k: "dead", label: () => L("Dead", "ميّتة", "Mortes") },
  { k: "misclassified", label: () => L("Misclassified", "غير مصنّفة", "Mal classés") },
  { k: "neg", label: () => L("Negative", "سالب", "Négatif") },
  { k: "active", label: () => L("Active", "نشطة", "Actifs") },
];

const d = ref({ rows: [], summary: {} });
const loading = ref(true);
const filter = ref("all");
const busy = ref("");
const sum = computed(() => d.value.summary || {});
const shown = computed(() => {
  const rows = d.value.rows || [];
  if (filter.value === "dead") return rows.filter((r) => r.dead && !r.disabled);
  if (filter.value === "misclassified") return rows.filter((r) => r.misclassified && !r.dead);
  if (filter.value === "neg") return rows.filter((r) => r.neg_cash);
  if (filter.value === "active") return rows.filter((r) => r.n > 0);
  return rows;
});

async function load() {
  loading.value = true;
  try { d.value = await api.call("accounting_portal.api.ledger.cash_bank_review", { company: currentCompany() }, { fresh: true }) || { rows: [], summary: {} }; }
  catch { d.value = { rows: [], summary: {} }; }
  finally { loading.value = false; }
}
load();
watch(entityId, load);

async function disableOne(r) {
  if (busy.value) return;
  if (!window.confirm(L(`Close (disable) ${r.nm}?`, `اقفل ${r.nm}؟`, `Fermer ${r.nm} ?`))) return;
  busy.value = r.name;
  try { await api.call("accounting_portal.api.ledger.set_account_disabled", { company: currentCompany(), account: r.name, disabled: 1, dry_run: 0 }); toast.success(L("Closed", "تم الإقفال", "Fermé")); load(); }
  catch (e) { toast.error(String(e?.message || e).slice(0, 160)); }
  finally { busy.value = ""; }
}
async function disableDead() {
  if (busy.value) return;
  if (!window.confirm(L(`Close all ${sum.value.dead} dead accounts? Each is reversible in Activity.`, `اقفل كل الـ ${sum.value.dead} حساب ميّت؟ كله قابل للتراجع.`, `Fermer ${sum.value.dead} comptes morts ?`))) return;
  busy.value = "bulk";
  try { const r = await api.call("accounting_portal.api.ledger.disable_dead_accounts", { company: currentCompany() }); toast.success(L(`Closed ${r.disabled} accounts`, `تم إقفال ${r.disabled} حساب`, `${r.disabled} fermés`)); load(); }
  catch (e) { toast.error(String(e?.message || e).slice(0, 160)); }
  finally { busy.value = ""; }
}
async function reclass(r, newType) {
  if (busy.value || newType === undefined) return;
  busy.value = r.name;
  try { await api.call("accounting_portal.api.ledger.reclassify_account", { company: currentCompany(), account: r.name, account_type: newType }); toast.success(L("Reclassified", "أُعيد التصنيف", "Reclassé")); load(); }
  catch (e) { toast.error(String(e?.message || e).slice(0, 160)); }
  finally { busy.value = ""; }
}
</script>
