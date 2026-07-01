<template>
  <div class="space-y-3.5">
    <div class="grid grid-cols-2 lg:grid-cols-3 gap-3">
      <div class="bg-white rounded-card border shadow-card px-4 py-3" :class="d.dead_active ? 'border-amber-200' : 'border-line'">
        <div class="text-[10px] font-bold uppercase tracking-wider flex items-center gap-1.5" :class="d.dead_active ? 'text-amber-700' : 'text-ink-muted'"><Icon name="alert" :size="13" :color="d.dead_active ? '#b45309' : '#94a3b8'" />{{ L("Unused accounts","حسابات غير مستخدمة","Comptes inutilisés") }}</div>
        <div class="text-[20px] font-extrabold mt-1 tnum" :class="d.dead_active ? 'text-amber-700' : ''">{{ loading ? "—" : (d.dead_active || 0) }}</div>
        <div class="text-[10.5px] text-ink-muted mt-0.5">{{ L("of","من","sur") }} {{ (d.leaves || 0) }} · {{ L("no ledger activity","بلا حركة","aucune écriture") }}</div>
      </div>
      <div class="bg-white rounded-card border border-line shadow-card px-4 py-3">
        <div class="text-[10px] font-bold uppercase tracking-wider text-ink-muted flex items-center gap-1.5"><Icon name="layers" :size="13" color="#0369a1" />{{ L("Same-name pairs","أسماء مكرّرة","Noms dupliqués") }}</div>
        <div class="text-[20px] font-extrabold mt-1 tnum">{{ loading ? "—" : (d.name_pair_count || 0) }}</div>
        <div class="text-[10.5px] text-ink-muted mt-0.5">{{ L("review — often AR/AP pairs","راجع — غالباً مدين/دائن","souvent AR/AP") }}</div>
      </div>
      <div class="col-span-2 lg:col-span-1 bg-white rounded-card border border-line shadow-card px-4 py-3 flex items-center">
        <div class="text-[11px] text-ink-2 leading-relaxed"><Icon name="alert" :size="12" color="#9a8f86" class="inline" /> {{ L("Disabling an unused account just hides it — it's reversible and only allowed when the account has no ledger entries.","تعطيل الحساب غير المستخدم بيخفيه بس — قابل للتراجع ومسموح فقط لو مفيش حركة.","Désactiver = masquer, réversible.") }}</div>
      </div>
    </div>

    <!-- dead accounts -->
    <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
      <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2 flex-wrap">
        <Icon name="list" :size="14" color="#0b5c4f" /><span class="text-[12px] font-bold">{{ L("Unused accounts","الحسابات غير المستخدمة","Comptes inutilisés") }}</span>
        <div class="ms-auto relative">
          <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
          <input v-model.trim="q" :placeholder="L('Search…','بحث…','Rechercher…')" class="w-44 sm:w-56 h-9 bg-app-warm/40 border border-line-2 rounded-[10px] ps-9 pe-3 text-[12.5px] focus:outline-none focus:border-accent/40 focus:bg-white" />
        </div>
      </div>
      <TableLoading v-if="loading" :rows="8" />
      <div v-else-if="err" class="px-4 py-10 text-center"><Icon name="alert" :size="18" color="#e11d48" /><p class="text-[12px] text-ink-2 mt-1">{{ L("Couldn't load.","تعذّر التحميل.","Échec.") }}</p><button class="mt-2 h-8 px-3 rounded-chip border border-line-2 text-[12px] font-semibold" @click="load">{{ L("Retry","إعادة","Réessayer") }}</button></div>
      <div v-else class="max-h-[560px] overflow-auto">
        <table class="w-full text-[12px]">
          <tbody>
            <tr v-for="a in filtered" :key="a.account" class="border-t border-line-hair first:border-t-0 hover:bg-app-warm/40">
              <td class="px-4 py-2 font-mono text-[11px] text-ink-3 w-px whitespace-nowrap">{{ a.num || "—" }}</td>
              <td class="px-2 py-2"><span :class="a.disabled ? 'text-ink-muted line-through' : ''">{{ a.name }}</span></td>
              <td class="px-3 py-2 text-ink-muted text-[10.5px]">{{ a.root }}</td>
              <td class="px-4 py-2 text-end w-px">
                <span v-if="a.disabled" class="text-[10px] font-semibold text-ink-muted bg-app-warm rounded-chip px-2 py-0.5">{{ L("disabled","معطّل","désactivé") }}
                  <button v-if="canManage" class="ms-1 text-accent-dark hover:underline" @click="toggle(a, 0)">{{ L("enable","تفعيل","activer") }}</button>
                </span>
                <button v-else-if="canManage" type="button" :disabled="busy===a.account" class="h-7 px-2.5 rounded-chip text-[11px] font-semibold text-ink-2 bg-white border border-line-2 hover:bg-app-warm disabled:opacity-60" @click="toggle(a, 1)">{{ busy===a.account ? "…" : L("Disable","تعطيل","Désactiver") }}</button>
              </td>
            </tr>
            <tr v-if="!filtered.length"><td colspan="4" class="px-4 py-8 text-center text-ink-muted text-[12px]">{{ L("No unused accounts.","لا حسابات غير مستخدمة.","Aucun.") }}</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- same-name review -->
    <div v-if="(d.name_pairs||[]).length" class="bg-white rounded-card border border-line shadow-card overflow-hidden">
      <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><Icon name="layers" :size="14" color="#0b5c4f" /><span class="text-[12px] font-bold">{{ L("Same-name accounts to review","حسابات بنفس الاسم للمراجعة","Noms identiques") }}</span></div>
      <div class="max-h-72 overflow-auto">
        <div v-for="(p,i) in d.name_pairs" :key="i" class="border-t border-line-hair first:border-t-0 px-4 py-2 text-[11.5px]">
          <div class="font-semibold truncate">{{ p.name }}</div>
          <div class="text-[10.5px] text-ink-muted flex flex-wrap gap-x-3">
            <span v-for="(a,j) in p.accounts" :key="j" class="font-mono">{{ a.num }} <span class="text-ink-3">({{ a.root }})</span></span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";
import { useAuth } from "@/composables/useAuth";
import { useToast } from "@/composables/useToast";

const { locale } = useI18n();
const { entityId } = useUi();
const { can } = useAuth();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

const d = ref({});
const loading = ref(true);
const err = ref(false);
const q = ref("");
const busy = ref("");
const canManage = computed(() => can("manage_users"));

async function load() {
  loading.value = true; err.value = false;
  try { d.value = await api.call("accounting_portal.api.ledger.account_cleanup", { company: currentCompany() }) || {}; }
  catch { d.value = {}; err.value = true; }
  finally { loading.value = false; }
}
load();
watch(entityId, load);

const filtered = computed(() => {
  const list = d.value.dead || [];
  const n = q.value.toLowerCase();
  return n ? list.filter((a) => String(a.name).toLowerCase().includes(n) || String(a.num || "").includes(n)) : list;
});

async function toggle(a, to) {
  if (busy.value) return;
  if (to && !window.confirm(L(`Disable "${a.name}"? Reversible.`, `تعطيل "${a.name}"؟ قابل للتراجع.`, `Désactiver « ${a.name} » ?`))) return;
  busy.value = a.account;
  try {
    await api.call("accounting_portal.api.ledger.set_account_disabled", { company: currentCompany(), account: a.account, disabled: to, dry_run: 0 });
    a.disabled = to;
    d.value.dead_active = (d.value.dead_active || 0) + (to ? -1 : 1);
    toast.success(to ? L("Disabled", "تم التعطيل", "Désactivé") : L("Enabled", "تم التفعيل", "Activé"));
  } catch (e) {
    toast.error(L("Failed", "فشل", "Échec") + ": " + String(e?.message || e).slice(0, 120));
  } finally { busy.value = ""; }
}
</script>
