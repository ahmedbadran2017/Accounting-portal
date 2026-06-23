<template>
  <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
    <!-- Header -->
    <div class="flex items-center gap-2.5 px-4 py-3.5 border-b border-line-hair">
      <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#fef2f2"><Icon name="lock" :size="14" color="#dc2626" /></span>
      <div class="flex-1">
        <div class="text-[13px] font-bold">{{ L("Maker-checker queue","طابور الصانع–المراجع","File maker-checker") }}</div>
        <div class="text-[11px] text-ink-muted">{{ L("Every manual journal needs a second sign-off before it posts","كل قيد يدوي يحتاج اعتماداً ثانياً قبل ترحيله","Chaque écriture manuelle exige une seconde validation") }}</div>
      </div>
      <button class="inline-flex items-center gap-1.5 h-[33px] px-3 rounded-[9px] text-white text-[12px] font-bold" style="background:linear-gradient(135deg,#c4492a,#a33a22)" @click="showForm = true">
        <Icon name="plus" :size="13" />{{ L("New JE","قيد جديد","Nouvelle écriture") }}
      </button>
    </div>

    <!-- Rows -->
    <div class="flex flex-col">
      <div v-for="j in items" :key="j.ref" class="flex items-center gap-3 px-4 py-3 border-t border-line-hair"
           :style="j.status === 'blocked' ? 'background:#fffbfb' : ''">
        <span class="w-8 h-8 rounded-[9px] grid place-items-center flex-shrink-0" :style="{ background: j.iconBg }"><Icon :name="j.icon" :size="16" :color="j.iconColor" /></span>
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 flex-wrap">
            <span class="text-[12.5px] font-bold font-mono">{{ j.ref }}</span>
            <span class="inline-block text-[9.5px] font-bold px-2 py-0.5 rounded-badge border" :style="{ background: st(j).bg, color: st(j).fg, borderColor: st(j).bd }">{{ journalStatusLabel(j.status, locale) }}</span>
          </div>
          <div class="text-[11.5px] text-ink-3 mt-0.5 truncate">{{ j.desc(locale) }}</div>
        </div>
        <div class="text-end flex-shrink-0">
          <div class="text-[13.5px] font-bold tnum">{{ j.amount }}</div>
          <div class="text-[10px] text-ink-muted font-mono">{{ j.account }}</div>
        </div>
        <div class="flex gap-[7px] flex-shrink-0">
          <template v-if="j.status === 'pending'">
            <button class="h-[30px] px-3 rounded-[8px] text-[11.5px] font-bold" style="background:#ecfdf5;color:#047857;border:1px solid #a7f3d0" @click="approve(j)">{{ L("Approve","اعتماد","Approuver") }}</button>
            <button class="h-[30px] px-3 rounded-[8px] text-[11.5px] font-semibold text-ink-3 bg-white border border-line-2" @click="reject(j)">{{ L("Reject","رفض","Rejeter") }}</button>
          </template>
          <span v-else-if="j.status === 'blocked'" class="inline-flex items-center gap-1.5 h-[30px] px-3 rounded-[8px] text-[11px] font-bold" style="background:#f5f3ff;color:#7c3aed;border:1px solid #ddd6fe">
            <Icon name="shield" :size="12" />{{ L("Blocked by Auditor","أوقفه المدقّق","Bloquée par l’auditeur") }}
          </span>
          <span v-else class="inline-flex items-center gap-1.5 h-[30px] px-2 text-[11.5px] font-semibold" :style="{ color: st(j).fg }">
            <Icon :name="j.status === 'approved' ? 'check' : 'arrow'" :size="13" />{{ journalStatusLabel(j.status, locale) }}
          </span>
        </div>
      </div>
    </div>
  </div>

  <JournalEntryForm v-if="showForm" @close="showForm = false" @posted="onPosted" />
</template>

<script setup>
import { ref, reactive } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { useToast } from "@/composables/useToast";
import { JOURNALS, JOURNAL_STATUS, journalStatusLabel } from "@/data/accountant";
import JournalEntryForm from "@/components/JournalEntryForm.vue";

const { locale } = useI18n();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

const showForm = ref(false);
const items = reactive(JOURNALS.map((j) => ({ ...j })));
const st = (j) => JOURNAL_STATUS[j.status] || JOURNAL_STATUS.pending;

function onPosted(res) {
  if (res && res.status === "Posted") {
    toast.success(L(`Journal ${res.voucher_no || ""} posted`, `قيد ${res.voucher_no || ""} رُحّل`, `Écriture ${res.voucher_no || ""} passée`));
  } else {
    toast.info(L("Entry recorded — awaiting an approver", "القيد سُجّل — بانتظار موافِق", "Écriture enregistrée — en attente"));
  }
}

function approve(j) { j.status = "approved"; toast.success(L(`${j.ref} approved & posted`, `${j.ref} اعتُمد ورُحِّل`, `${j.ref} approuvée & passée`)); }
function reject(j) { j.status = "rejected"; toast.info(L(`${j.ref} bounced to maker`, `${j.ref} أُرجع للصانع`, `${j.ref} renvoyée au maker`)); }
</script>
