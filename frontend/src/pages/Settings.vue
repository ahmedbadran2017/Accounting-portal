<template>
  <div class="space-y-3.5">
    <PageHeader :title="title" :subtitle="entityName" />

    <div class="flex flex-wrap gap-1 bg-white border border-line rounded-chip p-1 w-fit max-w-full overflow-x-auto">
      <button v-for="s in subs" :key="s[0]" class="px-3 py-1.5 rounded-lg text-[12px] whitespace-nowrap"
              :class="activeSub === s[0] ? 'text-accent-dark font-semibold bg-app-warm shadow-card' : 'text-ink-3 font-medium hover:text-ink'"
              @click="goSub(s[0])">{{ t(s[1]) }}</button>
    </div>

    <!-- Activity & audit trail -->
    <ActivityLog v-if="activeSub === 'activity'" />

    <!-- Users & roles -->
    <PortalUsers v-else-if="activeSub === 'users'" />

    <!-- Taxes -->
    <div v-else-if="activeSub === 'taxconf'" class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
      <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2"><span class="text-[13px] font-bold">{{ L("Taxes","الضرائب","Taxes") }}</span><span class="text-[9px] font-bold px-1.5 py-0.5 rounded-full" :style="refLive ? 'background:#ecfdf5;color:#047857' : 'background:#fffbeb;color:#b45309'">{{ refLive ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échant.") }}</span></div>
      <table class="w-full text-[12px]">
        <thead><tr style="background:#fafaf9">
          <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Tax template","قالب الضريبة","Modèle") }}</th>
          <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Rate","النسبة","Taux") }}</th>
          <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Company","الشركة","Société") }}</th>
        </tr></thead>
        <tbody>
          <tr v-for="x in taxRows" :key="x.name" class="border-t border-line-hair">
            <td class="px-4 py-2.5 font-semibold">{{ x.name }}</td>
            <td class="px-4 py-2.5 text-end tnum font-bold">{{ x.rate }}%</td>
            <td class="px-4 py-2.5 text-ink-3">{{ x.company }}</td>
          </tr>
          <tr v-if="!taxRows.length"><td colspan="3" class="px-4 py-8 text-center text-ink-muted">{{ L("No tax templates.","لا قوالب.","Aucun modèle.") }}</td></tr>
        </tbody>
      </table>
    </div>

    <!-- Currencies -->
    <div v-else-if="activeSub === 'currencies'" class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
      <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2"><span class="text-[13px] font-bold">{{ L("Currency exchange rates","أسعار صرف العملات","Taux de change") }}</span><span class="text-[9px] font-bold px-1.5 py-0.5 rounded-full" :style="refLive ? 'background:#ecfdf5;color:#047857' : 'background:#fffbeb;color:#b45309'">{{ refLive ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échant.") }}</span></div>
      <table class="w-full text-[12px]">
        <thead><tr style="background:#fafaf9">
          <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Pair","الزوج","Paire") }}</th>
          <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Rate","السعر","Taux") }}</th>
          <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("As of","حتى","Au") }}</th>
        </tr></thead>
        <tbody>
          <tr v-for="(c, i) in fxRows" :key="i" class="border-t border-line-hair">
            <td class="px-4 py-2.5 font-mono font-bold">{{ c.frm }} → {{ c.too }}</td>
            <td class="px-4 py-2.5 text-end tnum font-semibold">
              <template v-if="canWrite && editKey === i"><input v-model.number="editRate" type="number" step="any" class="w-24 h-7 border border-line-2 rounded-[6px] px-2 text-end text-[12px]" /></template>
              <template v-else>{{ c.rate }}</template>
            </td>
            <td class="px-4 py-2.5 text-end text-ink-3">{{ String(c.date).slice(0,10) }}</td>
            <td v-if="canWrite" class="px-4 py-2.5 text-end">
              <template v-if="editKey === i"><button class="text-[11px] font-bold text-success-dark me-2" :disabled="fxBusy" @click="saveRate(c)">{{ L("Save","حفظ","OK") }}</button><button class="text-[11px] text-ink-3" @click="editKey = null">✕</button></template>
              <button v-else class="text-[11px] font-semibold text-accent-dark" @click="startEdit(i, c)">{{ L("Edit","تعديل","Modifier") }}</button>
            </td>
          </tr>
          <tr v-if="!fxRows.length"><td :colspan="canWrite ? 4 : 3" class="px-4 py-8 text-center text-ink-muted">{{ L("No exchange rates.","لا أسعار.","Aucun taux.") }}</td></tr>
        </tbody>
      </table>
      <!-- Add a new rate -->
      <div v-if="canWrite" class="flex items-center gap-2 px-4 py-3 border-t border-line-hair flex-wrap bg-app-warm/20">
        <input v-model.trim="nf.frm" :placeholder="L('From','من','De')" class="w-16 h-8 border border-line-2 rounded-[8px] px-2 text-[12px] uppercase" maxlength="3" />
        <span class="text-ink-muted">→</span>
        <input v-model.trim="nf.too" :placeholder="L('To','إلى','Vers')" class="w-16 h-8 border border-line-2 rounded-[8px] px-2 text-[12px] uppercase" maxlength="3" />
        <input v-model.number="nf.rate" type="number" step="any" :placeholder="L('Rate','السعر','Taux')" class="w-28 h-8 border border-line-2 rounded-[8px] px-2 text-[12px] text-end" />
        <input v-model="nf.date" type="date" class="h-8 border border-line-2 rounded-[8px] px-2 text-[12px]" />
        <button class="h-8 px-3 rounded-[8px] text-[11.5px] font-bold text-white bg-brand hover:bg-brand-dark disabled:opacity-50" :disabled="fxBusy || !nf.frm || !nf.too || !nf.rate" @click="addRate">{{ L("Add / update","إضافة/تحديث","Ajouter") }}</button>
      </div>
    </div>

    <!-- Organizations -->
    <div v-else-if="activeSub === 'orgs'" class="grid sm:grid-cols-2 gap-3">
      <div v-for="e in orgRows" :key="e.name" class="bg-white border border-line rounded-[14px] p-4 shadow-card flex items-center gap-2.5">
        <span class="w-9 h-9 rounded-lg grid place-items-center text-white text-[11px] font-bold" :style="{ background: orgColor(e.name) }">{{ e.abbr || e.name.slice(0,2) }}</span>
        <div class="min-w-0">
          <div class="text-[13px] font-bold truncate">{{ e.name }}</div>
          <div class="text-[11px] text-ink-muted">{{ e.country || "—" }} · {{ e.ccy }}</div>
        </div>
      </div>
    </div>

    <!-- Other settings -->
    <ScaffoldTable v-else />
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import api from "@/services/api";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import PageHeader from "@/components/PageHeader.vue";
import ScaffoldTable from "@/components/ScaffoldTable.vue";
import ActivityLog from "@/pages/settings/ActivityLog.vue";
import PortalUsers from "@/pages/settings/Users.vue";
import { useUi } from "@/composables/useUi";
import { useAuth } from "@/composables/useAuth";
import { useToast } from "@/composables/useToast";
import { SUBTABS, defaultSub } from "@/data/nav";
import { settingsUsers, settingsTaxes, settingsCurrencies } from "@/data/settings";
import { AV } from "@/data/orders";

const { t, locale } = useI18n();
const route = useRoute();
const router = useRouter();
const { entityId, entities } = useUi();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const ini = (n) => n.split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();

const subs = SUBTABS.settings;
const activeSub = computed(() => route.params.sub || defaultSub("settings"));
const entityName = computed(() => (entities.find((e) => e.id === entityId.value) || entities[0]).name);
const title = computed(() => {
  const found = subs.find((s) => s[0] === activeSub.value);
  return found ? t(found[1]) : t("nav.settings");
});
const users = computed(() => settingsUsers(locale.value));
function goSub(s) { router.push(`/accounting/settings/${s}`); }

// Live reference data (taxes / FX / companies).
const ref_ = ref({ taxes: [], fx: [], companies: [] });
const refLive = ref(false);
async function loadRef() {
  try { ref_.value = await api.call("accounting_portal.api.settings.settings_reference", {}); refLive.value = true; }
  catch { refLive.value = false; ref_.value = { taxes: settingsTaxes(locale.value).map((x) => ({ name: x.name, rate: x.rate, company: x.region })), fx: [], companies: [] }; }
}
onMounted(loadRef);
const taxRows = computed(() => ref_.value.taxes || []);
const fxRows = computed(() => ref_.value.fx || []);
const orgRows = computed(() => ref_.value.companies || []);
const PAL = ["#7c3aed", "#0369a1", "#047857", "#b45309"];
function orgColor(n) { let h = 0; for (const ch of String(n)) h = (h * 31 + ch.charCodeAt(0)) % PAL.length; return PAL[h]; }

// ── FX rate editing ──
const { can } = useAuth();
const toast = useToast();
const canWrite = computed(() => can("post_entries"));
const editKey = ref(null);
const editRate = ref(0);
const fxBusy = ref(false);
const today = new Date().toISOString().slice(0, 10);
const nf = ref({ frm: "", too: "", rate: null, date: today });
function startEdit(i, c) { editKey.value = i; editRate.value = Number(c.rate) || 0; }
async function saveRate(c) {
  fxBusy.value = true;
  try {
    await api.call("accounting_portal.api.settings.set_exchange_rate", { from_currency: c.frm, to_currency: c.too, rate: editRate.value, date: today });
    toast.success(L("Rate saved", "تم الحفظ", "Taux enregistré")); editKey.value = null; loadRef();
  } catch (e) { toast.error(String((e && e.message) || L("Failed", "فشل", "Échec")).slice(0, 140)); }
  finally { fxBusy.value = false; }
}
async function addRate() {
  fxBusy.value = true;
  try {
    await api.call("accounting_portal.api.settings.set_exchange_rate", { from_currency: nf.value.frm.toUpperCase(), to_currency: nf.value.too.toUpperCase(), rate: nf.value.rate, date: nf.value.date || today });
    toast.success(L("Rate saved", "تم الحفظ", "Taux enregistré")); nf.value = { frm: "", too: "", rate: null, date: today }; loadRef();
  } catch (e) { toast.error(String((e && e.message) || L("Failed", "فشل", "Échec")).slice(0, 140)); }
  finally { fxBusy.value = false; }
}
</script>
