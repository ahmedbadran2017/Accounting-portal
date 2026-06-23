<template>
  <div class="space-y-2.5">
    <div v-for="j in items" :key="j.ref" class="bg-white rounded-card border p-4"
         :style="j.status === 'blocked' ? 'border-color:#fecaca;background:#fffbfb' : 'border-color:#f0efed'">
      <div class="flex items-start gap-3">
        <span class="w-9 h-9 rounded-[9px] grid place-items-center flex-shrink-0" :style="{ background: j.iconBg }">
          <Icon :name="j.icon" :size="16" :color="j.iconColor" />
        </span>
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-2 flex-wrap">
            <span class="font-mono font-semibold text-[13px]">{{ j.ref }}</span>
            <span class="inline-block text-[9.5px] font-bold px-2 py-0.5 rounded-badge border"
                  :style="{ background: st(j).bg, color: st(j).fg, borderColor: st(j).bd }">{{ journalStatusLabel(j.status, locale) }}</span>
          </div>
          <div class="text-[12px] text-ink-2 mt-0.5">{{ j.desc(locale) }}</div>
          <div class="text-[11px] text-ink-muted mt-0.5 font-mono">{{ j.account }}</div>
          <!-- Auditor block note -->
          <div v-if="j.status === 'blocked'" class="mt-2 text-[11px] text-rose-700 bg-rose-50 border border-rose-100 rounded-lg p-2 flex items-start gap-1.5">
            <Icon name="shield" :size="13" color="#dc2626" class="flex-shrink-0 mt-px" />{{ j.why(locale) }}
          </div>
        </div>
        <div class="text-end flex-shrink-0">
          <div class="text-[16px] font-bold tnum">{{ j.amount }}</div>
          <div class="text-[10px] text-ink-muted">MAD</div>
        </div>
      </div>

      <!-- Actions -->
      <div class="flex items-center gap-2 mt-3 pt-3 border-t border-line">
        <template v-if="j.status === 'pending'">
          <button class="inline-flex items-center gap-1.5 text-[12px] font-semibold text-white bg-success-dark hover:opacity-90 px-3 py-1.5 rounded-chip" @click="approve(j)">
            <Icon name="check" :size="14" />{{ L("Approve & post","اعتماد وترحيل","Approuver & passer") }}
          </button>
          <button class="inline-flex items-center gap-1.5 text-[12px] font-medium text-ink-2 bg-white border border-line-2 px-3 py-1.5 rounded-chip hover:bg-app-warm" @click="reject(j)">
            {{ L("Bounce to maker","إرجاع للصانع","Renvoyer au maker") }}
          </button>
        </template>
        <template v-else-if="j.status === 'blocked'">
          <button class="inline-flex items-center gap-1.5 text-[12px] font-semibold text-white bg-accent hover:bg-accent-dark px-3 py-1.5 rounded-chip shadow-prim" @click="reject(j)">
            <Icon name="arrow" :size="14" class="rtl:rotate-180" />{{ L("Bounce STE-05935 to maker","أرجِع للصانع","Renvoyer au maker") }}
          </button>
          <span class="text-[11px] text-ink-muted">{{ L("Auditor halted posting — approval disabled.","المدقّق أوقف الترحيل — الاعتماد معطّل.","L’auditeur a stoppé la passation — approbation désactivée.") }}</span>
        </template>
        <span v-else class="inline-flex items-center gap-1.5 text-[12px] font-semibold" :style="{ color: st(j).fg }">
          <Icon :name="j.status === 'approved' ? 'check' : 'arrow'" :size="14" />{{ journalStatusLabel(j.status, locale) }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { useToast } from "@/composables/useToast";
import { JOURNALS, JOURNAL_STATUS, journalStatusLabel } from "@/data/accountant";

const { locale } = useI18n();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

// Local copy so approve/reject mutate state without touching the source data.
const items = reactive(JOURNALS.map((j) => ({ ...j })));
const st = (j) => JOURNAL_STATUS[j.status] || JOURNAL_STATUS.pending;

function approve(j) { j.status = "approved"; toast.success(L(`${j.ref} approved & posted`, `${j.ref} اعتُمد ورُحِّل`, `${j.ref} approuvée & passée`)); }
function reject(j) { j.status = "rejected"; toast.info(L(`${j.ref} bounced to maker`, `${j.ref} أُرجع للصانع`, `${j.ref} renvoyée au maker`)); }
</script>
