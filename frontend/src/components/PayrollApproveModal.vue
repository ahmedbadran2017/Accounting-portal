<template>
  <div class="fixed inset-0 z-[100] overflow-y-auto flex items-start justify-center p-4"
       style="background:rgba(28,25,23,.45)" @click.self="$emit('close')">
    <div class="bg-white rounded-[16px] shadow-cardHover w-full max-w-3xl my-4">
      <header class="flex items-center gap-2.5 px-5 py-3.5 border-b border-line-hair">
        <span class="w-8 h-8 rounded-[10px] grid place-items-center" style="background:#ecfdf5">
          <Icon name="check" :size="16" color="#047857" /></span>
        <div class="min-w-0">
          <div class="text-[14px] font-bold">{{ L("Approve the month", "اعتماد الشهر", "Approuver le mois") }} · {{ month }}</div>
          <div class="text-[11px] text-ink-muted">
            {{ L("Everything this will write, before it writes it", "كل اللي هيتكتب، قبل ما يتكتب", "Tout ce qui sera écrit") }}
          </div>
        </div>
        <button @click="$emit('close')" class="ms-auto w-7 h-7 grid place-items-center rounded-[8px] hover:bg-app-warm text-ink-muted">
          <Icon name="close" :size="14" /></button>
      </header>

      <div class="p-5 space-y-3">
        <div v-if="loading" class="py-10 text-center text-[12px] text-ink-muted">…</div>
        <template v-else>
          <p class="text-[12px] text-ink-3 leading-relaxed">
            {{ L("The salary structure already pays each person the full month. Approving writes only what the sheet adds or takes away — as Additional Salary, on the same components your slips already use — so the slip lands on the sheet's net.",
                  "هيكل الرواتب بيدفع الشهر كامل لكل واحد. الاعتماد بيكتب بس اللي الورقة بتزوّده أو بتخصمه — كـAdditional Salary وعلى نفس المكوّنات اللي مسيّراتكم مستخدمينها — فالمسيّر ينزل على صافي الورقة بالظبط.",
                  "La structure paie déjà le mois complet ; l'approbation n'écrit que les variations.") }}
          </p>

          <div v-for="b in p.blocks" :key="b" class="px-3 py-2 rounded-[10px] text-[12px] leading-relaxed"
               style="background:#fef2f2;color:#b91c1c">{{ b }}</div>
          <div v-for="w in p.warnings" :key="w" class="px-3 py-2 rounded-[10px] text-[12px] leading-relaxed"
               style="background:#fffbeb;color:#b45309">{{ w }}</div>

          <div v-if="p.approved" class="px-3 py-2 rounded-[10px] text-[12px] leading-relaxed"
               style="background:#eff6ff;color:#0369a1">
            {{ L("Approved", "معتمد", "Approuvé") }} {{ p.approved.at }} · {{ p.approved.by }} —
            {{ p.approved.documents }}
            {{ L("adjustments. Approving again replaces exactly those and leaves anything keyed by hand alone.",
                  "بند. الاعتماد تاني بيستبدلهم هم بس، وأي حاجة مدخّلة بالإيد تفضل زي ماهي.",
                  "ajustements ; réapprouver ne remplace que ceux-là.") }}
          </div>

          <div class="grid grid-cols-2 sm:grid-cols-4 gap-px rounded-[10px] overflow-hidden" style="background:#f0efed">
            <div class="bg-white px-3 py-2">
              <div class="text-[10.5px] text-ink-muted">{{ L("Employees", "موظفين", "Employés") }}</div>
              <div class="text-[15px] font-medium tnum">{{ p.employees || 0 }}<span class="text-[11px] text-ink-muted">/{{ p.rows || 0 }}</span></div>
            </div>
            <div class="bg-white px-3 py-2">
              <div class="text-[10.5px] text-ink-muted">{{ L("Documents", "بنود", "Documents") }}</div>
              <div class="text-[15px] font-medium tnum">{{ p.documents || 0 }}</div>
            </div>
            <div class="bg-white px-3 py-2">
              <div class="text-[10.5px] text-ink-muted">{{ L("Added", "مضاف", "Ajouté") }}</div>
              <div class="text-[15px] font-medium tnum text-accent-dark">+{{ money(p.earn_total) }}</div>
            </div>
            <div class="bg-white px-3 py-2">
              <div class="text-[10.5px] text-ink-muted">{{ L("Deducted", "مخصوم", "Déduit") }}</div>
              <div class="text-[15px] font-medium tnum text-sale">−{{ money(p.ded_total) }}</div>
            </div>
          </div>

          <div v-if="p.lines && p.lines.length" class="border border-line rounded-[10px] overflow-hidden">
            <div class="max-h-[300px] overflow-y-auto">
              <table class="w-full text-[12px]">
                <thead><tr class="text-[10px] font-bold uppercase tracking-wider text-ink-muted" style="background:#fafaf9">
                  <th class="px-3 py-1.5 text-start">{{ L("Employee", "الموظف", "Employé") }}</th>
                  <th class="px-3 py-1.5 text-start">{{ L("Component", "المكوّن", "Composant") }}</th>
                  <th class="px-3 py-1.5 text-start">{{ L("Basis", "الأساس", "Base") }}</th>
                  <th class="px-3 py-1.5 text-end">{{ L("Amount", "المبلغ", "Montant") }}</th>
                </tr></thead>
                <tbody>
                  <template v-for="l in p.lines" :key="l.employee">
                    <tr v-for="(i, ix) in l.items" :key="l.employee + i.component" class="border-t border-line-hair">
                      <td class="px-3 py-1.5 truncate max-w-[170px]">{{ ix === 0 ? l.employee_name : "" }}</td>
                      <td class="px-3 py-1.5 text-ink-3 truncate max-w-[210px]" :title="i.component">{{ short(i.component) }}</td>
                      <td class="px-3 py-1.5 text-[11px] text-ink-muted tnum" dir="ltr">{{ i.basis }}</td>
                      <td class="px-3 py-1.5 text-end tnum font-medium" :class="i.type === 'Deduction' ? 'text-sale' : ''">
                        {{ i.type === "Deduction" ? "−" : "+" }}{{ money(i.amount) }}
                      </td>
                    </tr>
                  </template>
                </tbody>
              </table>
            </div>
          </div>

          <p class="text-[11px] text-ink-muted leading-relaxed">
            {{ L("Nothing touches the general ledger here — these are pre-slip inputs. The accrual posts when the slips are submitted, and every line stays cancellable from the audit trail.",
                  "مفيش حاجة بتنزل على الحسابات هنا — دي مدخلات قبل المسيّر. القيد بيتعمل وقت ترحيل المسيّرات، وكل بند يفضل قابل للإلغاء من سجل العمليات.",
                  "Rien ne touche le grand livre ici.") }}
          </p>
        </template>
      </div>

      <footer class="flex items-center justify-end gap-2 px-5 py-3 border-t border-line-hair">
        <UiButton variant="quiet" @click="$emit('close')">{{ L("Cancel", "إلغاء", "Annuler") }}</UiButton>
        <UiButton variant="primary" :busy="busy" :disabled="loading || !!(p.blocks && p.blocks.length) || !p.documents" @click="go">
          {{ p.approved ? L("Re-approve", "إعادة الاعتماد", "Réapprouver") : L("Approve the month", "اعتمد الشهر", "Approuver") }}
        </UiButton>
      </footer>
    </div>
  </div>
</template>

<script setup>
// The crossing from reference sheet to posted payroll, shown as the list of
// documents it will create. "Are you sure?" tells you nothing; this names the
// component, the arithmetic and the amount for every line, and refuses outright
// when something upstream would make the slip wrong.
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import UiButton from "@/components/UiButton.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useToast } from "@/composables/useToast";
import { fmtAmount } from "@/utils/helpers";

const props = defineProps({ month: { type: String, required: true } });
const emit = defineEmits(["close", "done"]);
const { locale } = useI18n();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const money = (n) => fmtAmount(n || 0);
// These components carry their Turkish originals after a dash; the head of the
// name is the part that identifies them in a narrow column.
const short = (c) => String(c || "").split(" - ")[0].replace(/\s+/g, " ").trim();

const p = ref({});
const loading = ref(true);
const busy = ref(false);

async function load() {
  loading.value = true;
  try {
    p.value = await api.call("accounting_portal.api.payroll.payroll_sheet_approve_preview",
      { company: currentCompany(), month: props.month }, { fresh: true }) || {};
  } catch (e) { toast.error(String(e?.message || e).slice(0, 200)); }
  finally { loading.value = false; }
}

async function go() {
  busy.value = true;
  try {
    await api.call("accounting_portal.api.payroll.payroll_sheet_approve",
      { company: currentCompany(), month: props.month });
    toast.success(L("Month approved", "الشهر اتعمد", "Mois approuvé"));
    emit("done");
    emit("close");
  } catch (e) { toast.error(String(e?.message || e).slice(0, 300)); }
  finally { busy.value = false; }
}
load();
</script>
