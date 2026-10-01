<template>
  <div class="fixed inset-0 z-[100] overflow-y-auto flex items-start justify-center p-4"
       style="background:rgba(28,25,23,.45)" @click.self="$emit('close')">
    <div class="bg-white rounded-[16px] shadow-cardHover w-full max-w-2xl my-4 flex flex-col max-h-[calc(100vh-2rem)]">
      <header class="shrink-0 flex items-center gap-2.5 px-5 py-3.5 border-b border-line-hair">
        <span class="w-8 h-8 rounded-[10px] grid place-items-center" style="background:#f0fdf4">
          <Icon name="inbox" :size="16" color="#15803d" /></span>
        <div class="min-w-0">
          <div class="text-[14px] font-bold">{{ L("Upload the sheet", "رفع الورقة", "Importer la feuille") }} · {{ month }}</div>
          <div class="text-[11px] text-ink-muted">
            {{ L("Download, edit in Excel, upload it back", "نزّلها، عدّلها في إكسل، وارفعها تاني", "Téléchargez, modifiez, réimportez") }}
          </div>
        </div>
        <button @click="$emit('close')" class="ms-auto w-7 h-7 grid place-items-center rounded-[8px] hover:bg-app-warm text-ink-muted">
          <Icon name="close" :size="14" /></button>
      </header>

      <div class="p-5 space-y-3 overflow-y-auto min-h-0 flex-1">
        <p class="text-[12px] text-ink-3 leading-relaxed">
          {{ L("Only the columns the sheet does not calculate are read: general hours, public holiday, overtime, missing, delay, performance, advance, contract, RIB and Send. Rate, total hours, payment and net are recomputed here, so a stale formula in the workbook can never become a salary.",
                "بيتقرا بس الأعمدة اللي الورقة مابتحسبهاش: الساعات التعاقدية، الأعياد، الإضافي، الغياب، التأخير، المكافأة، السلفة، العقد، رقم الحساب، واتحوّل. سعر الساعة والإجمالي والمستحق والصافي بيتحسبوا هنا من جديد، فمعادلة قديمة في الملف عمرها ما تبقى راتب.",
                "Seules les colonnes non calculées sont lues ; les totaux sont recalculés ici.") }}
        </p>

        <div class="flex items-center gap-2 flex-wrap">
          <a :href="excelUrl" class="h-8 px-3 rounded-[9px] text-[12px] font-medium text-white inline-flex items-center gap-1.5"
             style="background:#1d6f42"><Icon name="download" :size="13" color="#fff" />
            {{ L("Download this month", "نزّل الشهر ده", "Télécharger") }}</a>
          <label class="h-8 px-3 rounded-[9px] text-[12px] font-medium inline-flex items-center gap-1.5 cursor-pointer text-ink-2 bg-white border border-line-2 hover:bg-app-warm">
            <Icon name="inbox" :size="13" />
            {{ fileName || L("Choose a file…", "اختاري ملف…", "Choisir un fichier…") }}
            <input type="file" accept=".xlsx,.xlsm,.csv" class="hidden" @change="onFile" />
          </label>
          <span v-if="uploading" class="text-[11px] text-ink-muted">{{ L("reading…", "بيقرا…", "lecture…") }}</span>
        </div>

        <div v-if="err" class="px-3 py-2 rounded-[10px] text-[12px] leading-relaxed" style="background:#fef2f2;color:#b91c1c">{{ err }}</div>

        <template v-if="r">
          <div class="grid grid-cols-3 gap-px rounded-[10px] overflow-hidden" style="background:#f0efed">
            <div class="bg-white px-3 py-2">
              <div class="text-[10.5px] text-ink-muted">{{ L("Rows matched", "صفوف مطابقة", "Lignes") }}</div>
              <div class="text-[15px] font-medium tnum">{{ r.matched }}</div>
            </div>
            <div class="bg-white px-3 py-2">
              <div class="text-[10.5px] text-ink-muted">{{ L("Changes", "تغييرات", "Modifications") }}</div>
              <div class="text-[15px] font-medium tnum">{{ r.change_count }}</div>
            </div>
            <div class="bg-white px-3 py-2">
              <div class="text-[10.5px] text-ink-muted">{{ L("Not matched", "مش متطابق", "Non trouvés") }}</div>
              <div class="text-[15px] font-medium tnum" :class="r.unmatched_count ? 'text-sale' : ''">{{ r.unmatched_count }}</div>
            </div>
          </div>

          <div v-if="r.change_count" class="flex items-center justify-end">
            <UiButton variant="primary" size="sm" :busy="busy" @click="apply">
              {{ L("Apply", "طبّق", "Appliquer") }} ({{ r.change_count }})
            </UiButton>
          </div>
          <!-- A name the file carries and the company does not is the one thing a
               silent import would lose, so it is named, not counted. -->
          <div v-if="r.unmatched_count" class="px-3 py-2 rounded-[10px] text-[12px] leading-relaxed" style="background:#fffbeb;color:#b45309">
            {{ L("Skipped — no such employee on this company:", "اتخطّوا — مفيش موظف بالاسم ده في الشركة:", "Ignorés :") }}
            {{ r.unmatched.join(" · ") }}
          </div>

          <div v-if="r.change_count" class="border border-line rounded-[10px] overflow-hidden">
            <div class="max-h-[260px] overflow-y-auto">
              <table class="w-full text-[12px]">
                <thead><tr class="text-[10px] font-bold uppercase tracking-wider text-ink-muted" style="background:#fafaf9">
                  <th class="px-3 py-1.5 text-start">{{ L("Employee", "الموظف", "Employé") }}</th>
                  <th class="px-3 py-1.5 text-start">{{ L("Column", "العمود", "Colonne") }}</th>
                  <th class="px-3 py-1.5 text-end">{{ L("Now", "الحالي", "Actuel") }}</th>
                  <th class="px-3 py-1.5 text-end">{{ L("From the file", "من الملف", "Du fichier") }}</th>
                </tr></thead>
                <tbody>
                  <tr v-for="(c, i) in r.changes" :key="i" class="border-t border-line-hair">
                    <td class="px-3 py-1.5 truncate max-w-[170px]">{{ c.employee_name }}</td>
                    <td class="px-3 py-1.5 text-ink-3">{{ label(c.field) }}</td>
                    <td class="px-3 py-1.5 text-end tnum text-ink-muted" dir="ltr">{{ c.from === "" ? "—" : c.from }}</td>
                    <td class="px-3 py-1.5 text-end tnum font-medium" dir="ltr">{{ c.to === "" ? "—" : c.to }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          <div v-else class="text-[12px] text-ink-muted">{{ L("Nothing differs from what is already on screen.", "مفيش أي فرق عن اللي على الشاشة.", "Aucune différence.") }}</div>
        </template>
      </div>

      <footer class="shrink-0 flex items-center justify-end gap-2 px-5 py-3 border-t border-line-hair">
        <UiButton variant="quiet" @click="$emit('close')">{{ L("Cancel", "إلغاء", "Annuler") }}</UiButton>
        <UiButton variant="primary" :busy="busy" :disabled="!r || !r.change_count" @click="apply">
          {{ L("Apply", "طبّق", "Appliquer") }} {{ r && r.change_count ? `(${r.change_count})` : "" }}
        </UiButton>
      </footer>
    </div>
  </div>
</template>

<script setup>
// Download → edit → upload, with the diff shown before anything is written.
// The file is parsed on the server and read back against the live sheet, so what
// the table lists is the actual change each cell would make, not the file's
// contents restated.
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import UiButton from "@/components/UiButton.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useToast } from "@/composables/useToast";
import { getCsrfToken } from "@/utils/helpers";

const props = defineProps({ month: { type: String, required: true } });
const emit = defineEmits(["close", "done"]);
const { locale } = useI18n();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

const LABELS = {
  contract_hours: () => L("General hours", "ساعات تعاقدية", "Heures"),
  holiday_hours: () => L("Public holiday", "أعياد", "Fériés"),
  overtime_hours: () => L("Overtime", "إضافي", "Heures sup"),
  missing_hours: () => L("Missing", "غياب", "Absence"),
  delay_hours: () => L("Delay", "تأخير", "Retard"),
  bonus: () => L("Performance", "مكافأة", "Prime"),
  advance: () => L("Advance", "سلفة", "Avance"),
  contract: () => L("Contract", "العقد", "Contrat"),
  sent: () => L("Sent", "اتحوّل", "Envoyé"),
  rib: () => L("RIB", "رقم الحساب", "RIB"),
};
const label = (f) => (LABELS[f] ? LABELS[f]() : f);

const fileName = ref("");
const fileUrl = ref("");
const uploading = ref(false);
const busy = ref(false);
const err = ref("");
const r = ref(null);

const excelUrl = computed(() => {
  const q = new URLSearchParams({ key: "payroll_sheet", company: currentCompany(), month: props.month });
  return `/api/method/accounting_portal.api.export.list_xlsx?${q.toString()}`;
});

async function onFile(e) {
  const f = e.target.files[0];
  if (!f) return;
  fileName.value = f.name; err.value = ""; r.value = null; uploading.value = true;
  try {
    const fd = new FormData();
    fd.append("file", f); fd.append("is_private", 1); fd.append("folder", "Home");
    const res = await fetch("/api/method/upload_file", {
      method: "POST", headers: { "X-Frappe-CSRF-Token": getCsrfToken() }, body: fd,
    });
    const body = await res.json();
    if (!res.ok) throw new Error(body?._server_messages || "Upload failed");
    fileUrl.value = body.message.file_url;
    r.value = await api.call("accounting_portal.api.payroll.payroll_sheet_import", {
      company: currentCompany(), month: props.month, file_url: fileUrl.value, apply: 0,
    }, { fresh: true });
  } catch (e2) { err.value = String(e2?.message || e2).slice(0, 300); }
  finally { uploading.value = false; }
}

async function apply() {
  busy.value = true;
  try {
    const out = await api.call("accounting_portal.api.payroll.payroll_sheet_import", {
      company: currentCompany(), month: props.month, file_url: fileUrl.value, apply: 1,
    });
    toast.success(L("Applied", "اتطبّق", "Appliqué") + ` · ${out?.change_count || 0}`);
    emit("done");
    emit("close");
  } catch (e) { toast.error(String(e?.message || e).slice(0, 300)); }
  finally { busy.value = false; }
}
</script>
