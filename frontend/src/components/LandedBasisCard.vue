<template>
  <!-- B4: Landed basis — classify the year's charge pool, freeze rate/kg.
       Shared between the Cost Control Tower (step ②) and the Landed Cockpit. -->
  <div v-if="lp" class="bg-white rounded-card border shadow-card overflow-hidden" :style="lp.frozen ? 'border-color:#a7f3d0' : 'border-color:#c7d2fe'">
    <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2 flex-wrap cursor-pointer" @click="open = !open">
      <span class="text-[13px] font-bold">{{ L("Landed basis","أساس التكلفة المحمَّلة","Base landed") }} {{ lp.year }}</span>
      <span v-if="lp.frozen" class="text-[10.5px] font-bold px-2 py-0.5 rounded-full" style="background:#ecfdf5;color:#047857">
        ❄ {{ L("FROZEN","مجمّد","GELÉ") }} · {{ lp.frozen.rate_kg }} MAD/kg
      </span>
      <span v-else class="text-[10.5px] font-bold px-2 py-0.5 rounded-full" style="background:#eef2ff;color:#4338ca">
        {{ L("pending review","في انتظار المراجعة","à revoir") }} · {{ lp.rate_kg }} MAD/kg
      </span>
      <span class="text-[11px] text-ink-muted flex-1">{{ L("pool","المجمّع","pool") }} {{ fmt0(lp.pool) }} ÷ {{ fmt0(lp.kg.est_kg) }} kg ({{ lp.kg.coverage_pct }}% {{ L("weighed","موزون","pesé") }})</span>
      <span class="text-ink-3">{{ open ? "▾" : "▸" }}</span>
    </div>
    <div v-if="open" class="p-4 space-y-2.5">
      <table class="w-full text-[11.5px] border border-line rounded-[8px] overflow-hidden">
        <thead><tr style="background:#fafaf9">
          <th class="px-3 py-1.5 text-start text-[10px] font-bold text-ink-muted">{{ L("Account","الحساب","Compte") }}</th>
          <th class="px-3 py-1.5 text-end text-[10px] font-bold text-ink-muted">{{ L("Net","صافي","Net") }}</th>
          <th class="px-3 py-1.5 text-center text-[10px] font-bold text-ink-muted">{{ L("Suggested","مقترح","Suggéré") }}</th>
          <th class="px-3 py-1.5 text-center text-[10px] font-bold text-ink-muted">{{ L("In pool?","في المجمّع؟","Inclus?") }}</th>
        </tr></thead>
        <tbody>
          <tr v-for="r in lp.rows" :key="r.account" class="border-t border-line-hair" :style="r.included ? '' : 'opacity:.6'">
            <td class="px-3 py-1.5 truncate max-w-[260px]">{{ r.account }}<span class="text-[10px] text-ink-muted"> · {{ r.entries }}</span></td>
            <td class="px-3 py-1.5 text-end tnum font-semibold">{{ fmt0(r.net) }}</td>
            <td class="px-3 py-1.5 text-center">
              <span class="text-[10px] font-bold px-1.5 py-0.5 rounded-full"
                    :style="r.suggested==='inbound' ? 'background:#ecfdf5;color:#047857' : r.suggested==='outbound' ? 'background:#fef2f2;color:#b91c1c' : 'background:#fffbeb;color:#b45309'">
                {{ r.suggested==='inbound' ? L('inbound','وارد','entrant') : r.suggested==='outbound' ? L('outbound','صادر','sortant') : L('review','مراجعة','revue') }}
              </span>
            </td>
            <td class="px-3 py-1.5 text-center">
              <input type="checkbox" :checked="r.included" :disabled="!canWrite || !!lp.frozen"
                     class="accent-accent w-3.5 h-3.5 cursor-pointer" @change="togglePool(r)" />
            </td>
          </tr>
        </tbody>
      </table>
      <div class="flex items-center gap-2 flex-wrap">
        <span class="text-[11px] text-ink-muted flex-1">
          {{ L("Freeze locks the rate — Verify & Fix then adds landed = rate × item weight on top of the product cost.",
               "التجميد يقفل السعر — بعدها شاشة التحقق تضيف (السعر × وزن الصنف) فوق تكلفة المنتج.",
               "Geler fige le taux.") }}
        </span>
        <button v-if="canWrite && !lp.frozen" class="h-[30px] px-3.5 rounded-[8px] text-[11.5px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand disabled:opacity-50"
                :disabled="busy || !(lp.rate_kg > 0)" @click="freezeBasis">
          ❄ {{ L("Freeze basis","جمّد الأساس","Geler") }} ({{ lp.rate_kg }}/kg)
        </button>
        <button v-if="canWrite && lp.frozen" class="h-[30px] px-3 rounded-[8px] text-[11.5px] font-bold border border-line text-ink-2 hover:bg-app-warm disabled:opacity-50"
                :disabled="busy" @click="unfreezeBasis">{{ L("Unfreeze","فكّ التجميد","Dégeler") }}</button>
        <span v-if="lp.frozen" class="text-[10px] text-ink-3">{{ lp.frozen.by }} · {{ lp.frozen.on }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from "vue";
import { useI18n } from "vue-i18n";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useAuth } from "@/composables/useAuth";
import { useToast } from "@/composables/useToast";

const emit = defineEmits(["changed"]);
const props = defineProps({ startOpen: { type: Boolean, default: false } });
const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt0 = (n) => Number(n || 0).toLocaleString("en-US", { maximumFractionDigits: 0 });
const { can } = useAuth();
const canWrite = computed(() => can("post_entries"));
const toast = useToast();

const LP = "accounting_portal.api.landed_prep";
const lp = ref(null);
const open = ref(props.startOpen);
const busy = ref(false);

async function load() {
  try { lp.value = await api.call(`${LP}.charge_pool`, { company: currentCompany() }, { fresh: true }); }
  catch (e) { lp.value = null; }
}
load();

async function togglePool(r) {
  try {
    lp.value = await api.call(`${LP}.set_pool_include`, {
      company: currentCompany(), account: r.account, included: r.included ? 0 : 1,
    });
    emit("changed");
  } catch (e) { toast.error(e.message || "Failed"); await load(); }
}
async function freezeBasis() {
  if (!window.confirm(L(
    `Freeze the landed basis at ${lp.value.rate_kg} MAD/kg? Verify & Fix will start adding it on top of product costs.`,
    `تجميد الأساس على ${lp.value.rate_kg} درهم/كجم؟ شاشة التحقق هتبدأ تضيفه فوق تكلفة المنتج.`,
    `Geler à ${lp.value.rate_kg} MAD/kg ?`))) return;
  busy.value = true;
  try { await api.call(`${LP}.freeze_basis`, { company: currentCompany() }); toast.success(L("Basis frozen","اتجمّد الأساس","Gelé")); await load(); emit("changed"); }
  catch (e) { toast.error(e.message || "Failed"); }
  finally { busy.value = false; }
}
async function unfreezeBasis() {
  busy.value = true;
  try { await api.call(`${LP}.unfreeze_basis`, {}); toast.success(L("Unfrozen","اتفك التجميد","Dégelé")); await load(); emit("changed"); }
  catch (e) { toast.error(e.message || "Failed"); }
  finally { busy.value = false; }
}
</script>
