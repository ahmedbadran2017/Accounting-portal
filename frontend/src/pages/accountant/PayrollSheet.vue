<template>
  <div class="space-y-3">
    <!-- Header -->
    <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
      <div class="flex items-center gap-2.5 px-4 py-3 border-b border-line-hair flex-wrap">
        <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#ecfdf5">
          <Icon name="list" :size="14" color="#047857" /></span>
        <span class="text-[13px] font-semibold">{{ L("Payroll sheet", "ورقة الرواتب", "Feuille de paie") }}</span>
        <input v-model="month" type="month" class="fld fld-sm w-36" @change="load" />
        <span class="text-[11px] text-ink-muted hidden lg:inline">
          {{ L("hours × rate, the way the team already computes it",
                "بالساعة × السعر — نفس طريقة الفريق",
                "heures × taux, comme l'équipe calcule déjà") }}
        </span>
        <!-- The delay column needs a start of day, and the Shift Type is not
             it: 09:30 with late marking switched off, against an arrival mode
             of 11:00. Putting the reference on screen is what makes the
             suggestion checkable instead of authoritative. -->
        <span class="flex items-center gap-1.5 text-[11px] text-ink-3">
          <span :class="d.day_start ? '' : 'text-[#b45309] font-medium'">{{ L("Day starts", "بداية اليوم", "Début") }}</span>
          <input v-model="dayStart" type="time" dir="ltr" class="fld fld-xs w-[92px]" @change="saveSettings" />
          <span>+</span>
          <input v-model.number="grace" type="number" min="0" step="5" dir="ltr"
                 class="fld fld-xs w-[56px] text-end tnum" @change="saveSettings" />
          <span>{{ L("min grace", "د سماح", "min") }}</span>
          <!-- Empty is a real state, not a missing default: with no reference
               start there is no delay suggestion at all. -->
          <span v-if="!d.day_start" class="text-[10px]" style="color:#b45309">
            {{ L("set it to read delay from the punches", "حدّديها علشان التأخير يتقري من البصمة", "à définir pour les retards") }}
          </span>
        </span>
        <span class="ms-auto flex items-center gap-2">
          <UiButton variant="secondary" size="sm" icon="inbox" @click="showImport = true">
            {{ L("Upload", "ارفع", "Importer") }}
          </UiButton>
          <UiButton v-if="canWrite" variant="create" size="sm" icon="check" @click="showApprove = true">
            {{ d.approved ? L("Re-approve", "إعادة الاعتماد", "Réapprouver") : L("Approve month", "اعتماد الشهر", "Approuver") }}
          </UiButton>
          <a :href="excelUrl" class="h-8 px-3 rounded-[9px] text-[12px] font-medium text-white inline-flex items-center gap-1.5"
             style="background:#1d6f42" :title="L('Excel in the sheet\'s own layout','إكسيل بنفس شكل الشيت','Excel')">
            <Icon name="download" :size="13" color="#fff" />Excel
          </a>
        </span>
      </div>

      <!-- The banner has to tell the truth about the month it is showing. Once a
           month is approved the sheet is no longer "a reference that writes
           nothing", and a stale reassurance is worse than none. -->
      <div v-if="d.approved" class="px-4 py-2 text-[11px] leading-relaxed" style="background:#ecfdf5;color:#047857">
        {{ L("Approved", "معتمد", "Approuvé") }} {{ d.approved.at }} · {{ d.approved.by }} —
        {{ d.approved.documents }}
        {{ L("adjustments written to ERPNext. Edit and re-approve to replace them; the run picks them up when slips are generated.",
              "بند اتكتبوا في ERPNext. عدّلي واعتمدي تاني علشان يتبدّلوا؛ والتشغيل بياخدهم وقت توليد المسيّرات.",
              "ajustements écrits dans ERPNext.") }}
      </div>
      <div v-else class="px-4 py-2 text-[11px] leading-relaxed" style="background:#eff6ff;color:#0369a1">
        {{ L("Nothing here is written to ERPNext until you approve the month. Compare it with the spreadsheet first.",
              "مفيش حاجة هنا بتتكتب في ERPNext لحد ما تعتمدي الشهر. قارنيها بالشيت الأول.",
              "Rien n'est écrit dans ERPNext avant l'approbation du mois.") }}
      </div>

      <!-- Not one of the 27 active people carries a bank account on their
           employee record; the numbers live only in the spreadsheet's RIB tab,
           which is one of the two reasons payroll cannot leave it. -->
      <div v-if="d.no_rib_count" class="px-4 py-2 text-[11px] leading-relaxed" style="background:#fffbeb;color:#b45309">
        {{ d.no_rib_count }}
        {{ L("employees have no bank account on file — type it in the RIB column once and it stays on the employee record.",
              "موظف مفيش عندهم رقم حساب — اكتبيه في عمود RIB مرة واحدة ويتسجّل على الموظف نفسه.",
              "employés sans RIB — saisissez-le une fois dans la colonne RIB.") }}
      </div>

      <div class="grid grid-cols-2 sm:grid-cols-5 gap-px" style="background:#f0efed">
        <div class="bg-white px-4 py-3">
          <div class="text-[11px] text-ink-muted">{{ L("Employees", "الموظفون", "Employés") }}</div>
          <div class="text-[18px] font-medium tnum">{{ d.count || 0 }}</div>
        </div>
        <div class="bg-white px-4 py-3">
          <div class="text-[11px] text-ink-muted">{{ L("Gross", "المستحق", "Brut") }}</div>
          <div class="text-[18px] font-medium tnum">{{ money(d.total_gross) }}</div>
        </div>
        <div class="bg-white px-4 py-3">
          <div class="text-[11px] text-ink-muted">{{ L("Advances", "السلف", "Avances") }}</div>
          <div class="text-[18px] font-medium tnum text-sale">−{{ money(d.total_advance) }}</div>
        </div>
        <div class="bg-white px-4 py-3">
          <div class="text-[11px] text-ink-muted">{{ L("Net", "الصافي", "Net") }}</div>
          <div class="text-[18px] font-semibold tnum text-accent-dark">{{ money(d.total_net) }} <span class="text-[11px] font-normal text-ink-3">{{ d.currency }}</span></div>
        </div>
        <div class="bg-white px-4 py-3">
          <div class="text-[11px] text-ink-muted">{{ L("Sent", "اتحوّل", "Envoyé") }}</div>
          <div class="text-[18px] font-medium tnum">
            {{ d.sent_count || 0 }}<span class="text-[12px] text-ink-muted">/{{ d.count || 0 }}</span>
            <span v-if="d.sent_count" class="text-[11px] font-normal text-ink-3"> · {{ money(d.sent_net) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- The sheet -->
    <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
      <TableLoading v-if="loading" :rows="8" />
      <div v-else-if="!rows.length" class="px-4 py-12 text-center text-[12px] text-ink-muted">
        {{ L("No employees with a salary structure this month.", "مفيش موظفين عليهم هيكل رواتب في الشهر ده.", "Aucun employé.") }}
      </div>
      <div v-else class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead>
            <tr class="text-[10px] font-bold uppercase tracking-wider text-ink-muted" style="background:#fafaf9">
              <th class="px-3 py-2 text-start">{{ L("Employee", "الموظف", "Employé") }}</th>
              <th class="px-2 py-2 text-start">{{ L("Contract", "العقد", "Contrat") }}</th>
              <th class="px-2 py-2 text-end">{{ L("Base", "الأساسي", "Base") }}</th>
              <th class="px-2 py-2 text-end">{{ L("/hour", "/ساعة", "/heure") }}</th>
              <th class="px-2 py-2 text-end">{{ L("Contract h", "تعاقدي", "Contrat") }}</th>
              <th class="px-2 py-2 text-end">{{ L("Holiday", "أعياد", "Fériés") }}</th>
              <th class="px-2 py-2 text-end">{{ L("Overtime", "إضافي", "Heures sup") }}</th>
              <th class="px-2 py-2 text-end">{{ L("Missing", "غياب", "Absence") }}</th>
              <th class="px-2 py-2 text-end">{{ L("Delay", "تأخير", "Retard") }}</th>
              <th class="px-2 py-2 text-end">{{ L("Total h", "إجمالي س", "Total h") }}</th>
              <th class="px-2 py-2 text-end">{{ L("Gross", "المستحق", "Brut") }}</th>
              <th class="px-2 py-2 text-end">{{ L("Bonus", "مكافأة", "Prime") }}</th>
              <th class="px-2 py-2 text-end">{{ L("Advance", "سلفة", "Avance") }}</th>
              <th class="px-3 py-2 text-end">{{ L("Net", "الصافي", "Net") }}</th>
              <th class="px-2 py-2 text-start">{{ L("RIB", "رقم الحساب", "RIB") }}</th>
              <th class="px-2 py-2 text-center">{{ L("Sent", "اتحوّل", "Envoyé") }}</th>
            </tr>
          </thead>
          <tbody>
            <!-- Two different states, so two different signals: shading means
                 a figure was overridden, the green edge means the money is out. -->
            <tr v-for="r in rows" :key="r.employee" class="border-t border-line-hair align-top"
                :class="[r.edited.length ? 'bg-app-warm/40' : '', r.sent ? 'border-s-[3px] border-s-[#047857]' : '']">
              <td class="px-3 py-2">
                <div class="font-medium truncate max-w-[190px]">{{ r.employee_name }}</div>
                <div class="text-[10px] text-ink-muted truncate max-w-[190px]">{{ r.designation || r.department || "—" }}</div>
                <!-- Untracked is a fact about the device, not about the person. -->
                <span v-if="!r.tracked" class="inline-block mt-0.5 text-[9.5px] px-1.5 rounded-badge"
                      style="background:#eff6ff;color:#0369a1">{{ L("no device", "مفيش جهاز", "sans pointeuse") }}</span>
              </td>
              <!-- ERPNext holds Full-time / Part-time here and no contract end
                   date at all, so this shows the master's answer and accepts the
                   CDI / CDD the team actually tracks typed over it. -->
              <td class="px-2 py-2">
                <input :value="r.contract" dir="auto" maxlength="20"
                       class="fld fld-xs w-[78px]"
                       :class="r.edited.includes('contract') ? 'fld-sunk' : ''"
                       :placeholder="r.employment_type || '—'"
                       @change="save(r, { contract: $event.target.value })" />
              </td>
              <td class="px-2 py-2 text-end tnum">{{ money(r.base) }}</td>
              <td class="px-2 py-2 text-end tnum text-ink-3">{{ Number(r.rate).toFixed(2) }}</td>
              <td class="px-2 py-2 text-end"><Cell :r="r" f="contract_hours" @save="save" /></td>
              <td class="px-2 py-2 text-end"><Cell :r="r" f="holiday_hours" @save="save" /></td>
              <td class="px-2 py-2 text-end"><Cell :r="r" f="overtime_hours" @save="save" /></td>
              <td class="px-2 py-2 text-end">
                <Cell :r="r" f="missing_hours" @save="save" />
                <!-- The attendance figure is offered, never applied. 69% of what
                     the device calls absence is noise; a one-click accept keeps
                     the judgement with the person doing the payroll. -->
                <button v-if="r.auto_missing_hours && r.missing_hours !== r.auto_missing_hours"
                        type="button" class="block ms-auto mt-0.5 text-[9.5px] px-1.5 rounded-badge hover:underline"
                        style="background:#fffbeb;color:#b45309"
                        :title="L('Attendance suggests this — click to apply','الحضور بيقترح الرقم ده — اضغط لتطبيقه','Suggestion de la présence')"
                        @click="save(r, { missing_hours: r.auto_missing_hours })">
                  {{ L("attendance", "الحضور", "présence") }}: {{ r.auto_missing_hours }}
                </button>
              </td>
              <td class="px-2 py-2 text-end">
                <Cell :r="r" f="delay_hours" @save="save" />
                <!-- Same contract as absence: computed from the punches, offered,
                     never applied on its own. -->
                <button v-if="r.auto_delay_hours && r.delay_hours !== r.auto_delay_hours"
                        type="button" class="block ms-auto mt-0.5 text-[9.5px] px-1.5 rounded-badge hover:underline"
                        style="background:#fffbeb;color:#b45309"
                        :title="L('Late arrivals measured from ','التأخير محسوب من ','Retards depuis ') + (d.day_start || L('the shift','الوردية','le poste')) + ' +' + (d.grace_minutes || 0) + 'm'"
                        @click="save(r, { delay_hours: r.auto_delay_hours })">
                  {{ L("punches", "البصمة", "pointages") }}: {{ r.auto_delay_hours }}
                </button>
              </td>
              <td class="px-2 py-2 text-end tnum font-medium">{{ Number(r.total_hours).toFixed(2) }}</td>
              <td class="px-2 py-2 text-end tnum">{{ money(r.gross) }}</td>
              <td class="px-2 py-2 text-end"><Cell :r="r" f="bonus" @save="save" /></td>
              <td class="px-2 py-2 text-end"><Cell :r="r" f="advance" @save="save" /></td>
              <td class="px-3 py-2 text-end">
                <div class="tnum font-semibold">{{ money(r.net) }}</div>
                <!-- A posted slip that disagrees is the thing worth seeing. -->
                <div v-if="r.slip && Math.abs(r.gap) >= 1" class="text-[9.5px] tnum" style="color:#b45309"
                     :title="r.slip">{{ L("slip", "المسيّر", "bulletin") }} {{ money(r.slip_net) }}</div>
                <div v-else-if="r.slip" class="text-[9.5px]" style="color:#047857">✓ {{ L("matches slip", "مطابق للمسيّر", "conforme") }}</div>
              </td>
              <!-- Written straight onto the employee record, not parked in the
                   sheet: a bank account is a fact about the person and the rest
                   of the system needs it too. -->
              <td class="px-2 py-2">
                <input :value="r.rib" dir="ltr" maxlength="60" inputmode="numeric"
                       class="fld fld-xs w-[148px] font-mono text-[11px]"
                       :class="r.rib ? '' : 'fld-sunk'"
                       :title="r.bank_name || L('Not on the employee record yet','لسه مش متسجّل على الموظف','Absent de la fiche')"
                       placeholder="—" @change="saveRib(r, $event.target.value)" />
              </td>
              <td class="px-2 py-2 text-center">
                <input type="checkbox" class="accent-accent w-3.5 h-3.5 align-middle" :checked="!!r.sent"
                       :title="r.sent ? `${r.sent_on} · ${r.sent_by}` : L('Mark once the transfer is out','علّميها لما التحويل يخرج','Cocher après le virement')"
                       @change="save(r, { sent: $event.target.checked ? 1 : 0 })" />
                <div v-if="r.sent" class="text-[9px] text-ink-muted tnum">{{ (r.sent_on || "").slice(5, 10) }}</div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="px-4 py-2 border-t border-line-hair text-[11px] text-ink-muted leading-relaxed">
        {{ L("Rate = base ÷ contract hours. Total = contract + holiday + overtime×1.5 − missing − delay. Edited cells are shaded; clear one to hand it back to the system. RIB is written onto the employee record; Sent records who ticked it and when.",
              "سعر الساعة = الأساسي ÷ الساعات التعاقدية. الإجمالي = تعاقدي + أعياد + إضافي×١٫٥ − غياب − تأخير. الخلايا المعدّلة مظللة؛ فضّيها ترجع للنظام. رقم الحساب بيتكتب على الموظف نفسه، و«اتحوّل» بيسجّل مين علّمها وإمتى.",
              "Taux = base ÷ heures. Total = contrat + fériés + sup×1,5 − absence − retard. Le RIB est écrit sur la fiche employé.") }}
      </div>
    </div>
    <PayrollApproveModal v-if="showApprove" :month="month" @close="showApprove = false" @done="load" />
    <PayrollSheetImportModal v-if="showImport" :month="month" @close="showImport = false" @done="load" />
  </div>
</template>

<script setup>
// The monthly payroll sheet.
//
// The team's real model lives in a Google Sheet and is hour-based:
//   rate  = base / 208
//   hours = 208 + public holidays + overtime×1.5 − missing − delay
//   gross = hours × rate
// Checked against their own January figures to the dirham, and against August's
// submitted slips, which match the spreadsheet on every line — because the sheet
// is calculated and the result is then typed into ERPNext by hand.
//
// This screen does that calculation once, from data we already hold. It posts
// nothing: the banner says so, and it runs beside the spreadsheet until the two
// agree for a full month.
import { computed, h, ref } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import UiButton from "@/components/UiButton.vue";
import TableLoading from "@/components/TableLoading.vue";
import PayrollApproveModal from "@/components/PayrollApproveModal.vue";
import PayrollSheetImportModal from "@/components/PayrollSheetImportModal.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useToast } from "@/composables/useToast";
import { useAuth } from "@/composables/useAuth";
import { fmtAmount } from "@/utils/helpers";

const { locale } = useI18n();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const money = (n) => fmtAmount(n || 0);

const now = new Date();
const month = ref(`${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`);
const d = ref({});
const loading = ref(true);
const rows = computed(() => d.value.rows || []);
const dayStart = ref("");
const grace = ref(15);
const showApprove = ref(false);
const showImport = ref(false);
const { can } = useAuth();
const canWrite = computed(() => can("post_entries"));

// One editable cell. Blank means "no override" — the field goes back to whatever
// the system derives, which is why an empty box and a zero must look different.
const Cell = {
  props: { r: { type: Object, required: true }, f: { type: String, required: true } },
  emits: ["save"],
  setup(p, { emit }) {
    return () => {
      const on = p.r.edited.includes(p.f);
      return h("input", {
        type: "number", step: "any", dir: "ltr",
        value: p.r[p.f] || (p.r[p.f] === 0 ? 0 : ""),
        class: "fld fld-xs w-[74px] text-end tnum " + (on ? "fld-sunk" : ""),
        title: on ? "edited" : "",
        onChange: (e) => emit("save", p.r, { [p.f]: e.target.value }),
      });
    };
  },
};

async function load() {
  loading.value = true;
  try {
    d.value = await api.call("accounting_portal.api.payroll.payroll_sheet",
      { company: currentCompany(), month: month.value }, { fresh: true }) || {};
    dayStart.value = d.value.day_start || "";
    grace.value = Number(d.value.grace_minutes ?? 15);
  } catch (e) { toast.error(String(e?.message || e).slice(0, 200)); d.value = {}; }
  finally { loading.value = false; }
}

async function save(r, values) {
  try {
    await api.call("accounting_portal.api.payroll.payroll_sheet_save", {
      company: currentCompany(), month: month.value, employee: r.employee,
      values: JSON.stringify(values),
    });
    await load();
  } catch (e) { toast.error(String(e?.message || e).slice(0, 200)); }
}

async function saveSettings() {
  try {
    await api.call("accounting_portal.api.payroll.payroll_sheet_settings", {
      company: currentCompany(), month: month.value,
      values: JSON.stringify({ day_start: dayStart.value || "", grace_minutes: grace.value || 0 }),
    });
    await load();
  } catch (e) { toast.error(String(e?.message || e).slice(0, 200)); }
}

async function saveRib(r, rib) {
  if ((rib || "").trim() === (r.rib || "")) return;
  try {
    await api.call("accounting_portal.api.payroll.payroll_sheet_bank", {
      company: currentCompany(), employee: r.employee, rib,
    });
    toast.success(L("Bank account saved", "اتسجّل رقم الحساب", "RIB enregistré"));
    await load();
  } catch (e) { toast.error(String(e?.message || e).slice(0, 200)); }
}

const excelUrl = computed(() => {
  const q = new URLSearchParams({ key: "payroll_sheet", company: currentCompany(), month: month.value });
  return `/api/method/accounting_portal.api.export.list_xlsx?${q.toString()}`;
});

load();
</script>
