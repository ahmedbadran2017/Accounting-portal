<template>
  <div class="fixed inset-0 z-[100] flex items-start justify-center p-4 sm:p-8 overflow-y-auto" style="background:rgba(28,25,23,.45)" @click.self="$emit('close')">
    <div class="bg-white rounded-[18px] shadow-cardHover w-full max-w-md my-8 overflow-hidden">
      <div class="flex items-center gap-2.5 px-5 py-4 border-b border-line">
        <span class="w-8 h-8 rounded-[10px] grid place-items-center" style="background:#ecfdf5"><Icon name="scale" :size="16" color="#0f766e" /></span>
        <div class="flex-1 min-w-0">
          <div class="text-[14px] font-bold">{{ L("Assign salary structure", "تعيين هيكل راتب", "Affecter une structure") }}</div>
          <div class="text-[11px] text-ink-muted truncate">{{ employeeName || employee }}</div>
        </div>
        <button class="text-ink-3 hover:text-ink" @click="$emit('close')"><Icon name="close" :size="18" /></button>
      </div>

      <div v-if="loadingOpt" class="p-8 text-center text-[12px] text-ink-muted">{{ L("Loading…", "جارٍ التحميل…", "…") }}</div>
      <template v-else>
        <div class="p-5 space-y-3.5">
          <label class="block">
            <span class="text-[11px] font-semibold text-ink-3">{{ L("Salary structure", "هيكل الراتب", "Structure") }}</span>
            <select v-model="structure" class="mt-1 w-full border border-line-2 rounded-chip px-3 py-2 text-[12px] focus:outline-none focus:border-accent/40 cursor-pointer">
              <option value="">—</option>
              <option v-for="s in opt.structures || []" :key="s.name" :value="s.name">{{ s.name }}{{ s.currency && s.currency !== opt.currency ? " · " + s.currency : "" }}</option>
            </select>
          </label>
          <div class="grid grid-cols-2 gap-3">
            <label class="block">
              <span class="text-[11px] font-semibold text-ink-3">{{ L("Effective from", "ساري من", "À partir de") }}</span>
              <input type="date" v-model="fromDate" class="mt-1 w-full border border-line-2 rounded-chip px-3 py-2 text-[12px] focus:outline-none focus:border-accent/40" />
            </label>
            <label class="block">
              <span class="text-[11px] font-semibold text-ink-3">{{ L("Base", "الأساسي", "Base") }} <span class="text-ink-muted font-normal">({{ L("optional", "اختياري", "opt.") }})</span></span>
              <input type="number" min="0" step="0.01" v-model.number="base" class="mt-1 w-full border border-line-2 rounded-chip px-3 py-2 text-[12px] tnum text-end focus:outline-none focus:border-accent/40" placeholder="0.00" />
            </label>
          </div>
          <div class="text-[10.5px] text-ink-muted">{{ L("Most structures already encode the salary — leave Base at 0 unless the structure needs it.", "أغلب الهياكل بتحدّد الراتب — سيب الأساسي 0 إلا لو الهيكل محتاجه.", "Laissez Base à 0 sauf si nécessaire.") }}</div>
          <div v-if="error" class="text-[11.5px] text-sale">{{ error }}</div>
        </div>
        <div class="flex items-center justify-end gap-2 px-5 py-3.5 border-t border-line bg-app-warm/40">
          <button class="px-3.5 py-2 rounded-chip text-[12px] font-semibold text-ink-2 hover:bg-white" @click="$emit('close')">{{ L("Cancel", "إلغاء", "Annuler") }}</button>
          <button class="px-4 py-2 rounded-chip text-[12px] font-bold text-white bg-emerald-600 hover:bg-emerald-700 shadow-brand disabled:opacity-50" :disabled="!structure || saving" @click="submit">
            {{ saving ? L("Assigning…", "جارٍ…", "…") : L("Assign", "تعيين", "Affecter") }}
          </button>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useToast } from "@/composables/useToast";

const props = defineProps({ employee: { type: String, required: true }, employeeName: { type: String, default: "" } });
const emit = defineEmits(["close", "done"]);
const { locale } = useI18n();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

const opt = ref({ structures: [] });
const loadingOpt = ref(true);
const structure = ref("");
const fromDate = ref(new Date().toISOString().slice(0, 8) + "01");
const base = ref(null);
const saving = ref(false);
const error = ref("");

onMounted(async () => {
  try {
    opt.value = await api.call("accounting_portal.api.payroll.assignment_options", { company: currentCompany() }) || { structures: [] };
    if (opt.value.default_from) fromDate.value = opt.value.default_from;
  } catch (e) { error.value = String(e?.message || e).slice(0, 160); }
  finally { loadingOpt.value = false; }
});

async function submit() {
  if (!structure.value || saving.value) return;
  saving.value = true; error.value = "";
  try {
    await api.call("accounting_portal.api.payroll.assign_structure", {
      company: currentCompany(), employee: props.employee, salary_structure: structure.value,
      from_date: fromDate.value, base: Number(base.value) || 0,
    });
    toast.success(L("Structure assigned", "تم تعيين الهيكل", "Structure affectée"));
    emit("done"); emit("close");
  } catch (e) { error.value = String(e?.message || e).slice(0, 200); }
  finally { saving.value = false; }
}
</script>
