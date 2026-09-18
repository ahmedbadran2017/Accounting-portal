<template>
  <div class="fixed inset-0 z-50 grid place-items-center bg-ink/30 p-3" @click.self="$emit('close')">
    <div class="bg-white rounded-card shadow-pop w-full max-w-5xl max-h-[92vh] flex flex-col">
      <div class="px-5 py-3 border-b border-line-hair flex items-center gap-2">
        <Icon name="gear" :size="15" color="#0b5c4f" />
        <span class="text-[14px] font-bold">{{ L("Edit draft", "تعديل المسودة", "Modifier le brouillon") }}</span>
        <span class="font-mono text-[11.5px] text-ink-muted"><bdi dir="ltr">{{ name }}</bdi></span>
        <span v-if="d.currency" class="text-[10.5px] font-bold px-1.5 py-0.5 rounded-full bg-app-warm text-ink-3">{{ d.currency }}</span>
        <button class="ms-auto text-ink-muted hover:text-ink" @click="$emit('close')"><Icon name="close" :size="16" /></button>
      </div>

      <div class="flex-1 overflow-auto px-5 py-4 space-y-4">
        <div v-if="loading" class="py-10 text-center text-[12px] text-ink-muted">…</div>
        <div v-else-if="!d.supported" class="py-10 text-center text-[12px] text-ink-muted">
          {{ d.reason === 'not_draft' ? L("Only a draft can be edited here. Use Amend or Change date on a posted document.", "التعديل هنا للمسودات فقط. للمستند المرحّل استخدم «تعديل ونسخ» أو «تغيير التاريخ».", "Seul un brouillon est modifiable ici.") : L("This document type has no editor yet.", "لا يوجد محرر لهذا النوع بعد.", "Pas d'éditeur pour ce type.") }}
        </div>
        <template v-else>
          <div v-if="d.submitted_mode" class="rounded-[10px] px-3 py-2 text-[12px]" style="background:#fffbeb;color:#92400e">
            {{ d.submitted_kind === 'reaccount'
              ? L("This invoice is posted. Each line's account and cost centre can change, along with any field above — these are the ones ERPNext allows after submit. Changing an account reposts the ledger; changing a field above does not.", "الفاتورة مرحّلة. بيتعدل حساب كل سطر ومركز التكلفة، وكمان أي حقل فوق — دول اللي ERPNext بيسمح بيهم بعد الترحيل. تغيير الحساب بيعيد ترحيل القيود، أما الحقول اللي فوق فلأ.", "Facture comptabilisée. Le compte et le centre de coût des lignes, ainsi que les champs ci-dessus, restent modifiables.")
              : L("This order is submitted. Line quantities and rates change through ERPNext's 'Update Items'; the fields above are the ones it allows after submit. Totals, reservations and status are recomputed on save.", "الأمر مرحّل. الكميات والأسعار بتتعدل عن طريق Update Items، والحقول اللي فوق هي اللي مسموح بيها بعد الترحيل. الإجماليات والحجز والحالة بتتعاد حسابها عند الحفظ.", "Commande soumise. Quantités et prix via « Update Items » ; les champs ci-dessus restent modifiables.") }}
          </div>
          <div v-if="d.child && d.child.locked" class="rounded-[10px] px-3 py-2 text-[12px]" style="background:#fef2f2;color:#9f1239">
            {{ d.child.locked === "completed"
              ? L("The lines are fixed: this order is fully received and billed.", "السطور ثابتة: الأمر مستلم ومفوتر بالكامل.", "Lignes figées : commande entièrement reçue et facturée.")
              : L("The lines are fixed: this order is ", "السطور ثابتة: حالة الأمر ", "Lignes figées : commande ") + d.child.locked + "." }}
          </div>

          <!-- header fields -->
          <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <div v-for="f in d.header" :key="f.field" :class="f.type === 'Text' ? 'sm:col-span-2 lg:col-span-3' : ''">
              <label class="block text-[11px] font-bold text-ink-3 mb-1">{{ f.label }}</label>
              <component :is="'div'">
                <textarea v-if="f.type === 'Text'" v-model="hv[f.field]" :disabled="f.ro" rows="2" class="w-full rounded-[9px] border border-line-2 px-2.5 py-1.5 text-[12.5px] bg-white focus:outline-none focus:border-accent/40 disabled:bg-app-warm"></textarea>
                <input v-else-if="f.type === 'Date'" type="date" v-model="hv[f.field]" :disabled="f.ro" class="h-9 w-full rounded-[9px] border border-line-2 px-2.5 text-[12.5px] bg-white focus:outline-none focus:border-accent/40 disabled:bg-app-warm" />
                <input v-else-if="['Currency','Float','Int'].includes(f.type)" type="number" step="any" v-model="hv[f.field]" :disabled="f.ro" dir="ltr" class="h-9 w-full rounded-[9px] border border-line-2 px-2.5 text-[12.5px] bg-white tnum focus:outline-none focus:border-accent/40 disabled:bg-app-warm" />
                <label v-else-if="f.type === 'Check'" class="inline-flex items-center gap-2 h-9 text-[12.5px]"><input type="checkbox" :checked="hv[f.field] === '1' || hv[f.field] === true || hv[f.field] === 1" @change="hv[f.field] = $event.target.checked ? 1 : 0" :disabled="f.ro" /> {{ L("Yes", "نعم", "Oui") }}</label>
                <select v-else-if="f.type === 'Select'" v-model="hv[f.field]" :disabled="f.ro" class="h-9 w-full rounded-[9px] border border-line-2 px-2 text-[12.5px] bg-white focus:outline-none focus:border-accent/40 disabled:bg-app-warm">
                  <option v-for="o in (d.options[f.options] || [])" :key="o.value" :value="o.value">{{ o.label || o.value || "—" }}</option>
                </select>
                <SearchSelect v-else-if="f.type === 'Link'" v-model="hv[f.field]" :items="d.options[f.options] || []" :disabled="f.ro" :placeholder="L('Select…','اختر…','Choisir…')" inputClass="h-9 text-[12.5px] bg-white" />
                <PartyPick v-else-if="f.type === 'Party'" v-model="hv[f.field]" :party-type="d.party_type_fixed || hv.party_type" :disabled="f.ro" />
                <input v-else v-model="hv[f.field]" :disabled="f.ro" class="h-9 w-full rounded-[9px] border border-line-2 px-2.5 text-[12.5px] bg-white focus:outline-none focus:border-accent/40 disabled:bg-app-warm" />
              </component>
            </div>
          </div>

          <!-- child rows -->
          <div v-if="d.child" class="bg-white border border-line rounded-[12px] overflow-hidden">
            <div class="px-3 py-2 border-b border-line-hair flex items-center gap-2 text-[12px] font-bold">
              <Icon name="list" :size="13" color="#0b5c4f" />{{ d.child.label }}
              <span class="text-[10.5px] text-ink-muted font-normal">{{ rv.length }}</span>
              <span v-if="isJE" class="ms-auto text-[11px] tnum" :class="balanced ? 'text-success-dark' : 'text-sale'">
                Dr {{ fmt(totDr) }} · Cr {{ fmt(totCr) }} {{ balanced ? "✓" : "· Δ " + fmt(Math.abs(totDr - totCr)) }}
              </span>
            </div>
            <div class="overflow-x-auto">
              <table class="w-full text-[12px]">
                <thead><tr class="text-[10px] font-bold uppercase tracking-wider text-ink-muted" style="background:#fafaf9">
                  <th class="px-2 py-2 text-start w-8">#</th>
                  <th v-for="c in d.child.columns" :key="c.field" class="px-2 py-2 text-start whitespace-nowrap" :class="['Currency','Float'].includes(c.type) ? 'text-end' : ''">{{ c.label }}</th>
                  <th v-if="d.child.can_remove" class="w-8"></th>
                </tr></thead>
                <tbody>
                  <tr v-for="(r, i) in rv" :key="r.name || 'new' + i" class="border-t border-line-hair align-top">
                    <td class="px-2 py-1.5 text-ink-muted tnum">{{ i + 1 }}</td>
                    <td v-for="c in d.child.columns" :key="c.field" class="px-1.5 py-1" :style="cellWidth(c)">
                      <span v-if="c.ro || (c.ro_existing && r.name)" class="block px-1 py-1.5 text-ink-2 truncate max-w-[220px]" :class="['Currency','Float'].includes(c.type) ? 'text-end tnum' : ''">{{ ['Currency','Float'].includes(c.type) ? fmt(r[c.field]) : (r[c.field] || "—") }}</span>
                      <input v-else-if="['Currency','Float','Int'].includes(c.type)" type="number" step="any" v-model="r[c.field]" dir="ltr" class="h-8 w-full min-w-[96px] rounded-[8px] border border-line-2 px-2 text-[12px] text-end tnum bg-white focus:outline-none focus:border-accent/40" />
                      <select v-else-if="c.type === 'Select'" v-model="r[c.field]" class="h-8 w-full min-w-[110px] rounded-[8px] border border-line-2 px-1.5 text-[12px] bg-white focus:outline-none focus:border-accent/40">
                        <option v-for="o in (d.options[c.options] || [])" :key="o.value" :value="o.value">{{ o.label || o.value || "—" }}</option>
                      </select>
                      <SearchSelect v-else-if="c.type === 'Link'" v-model="r[c.field]" :items="d.options[c.options] || []" :placeholder="L('Select…','اختر…','Choisir…')" inputClass="h-8 text-[12px] bg-white min-w-[220px]" />
                      <PartyPick v-else-if="c.type === 'Party'" v-model="r[c.field]" :party-type="r.party_type" :disabled="!r.party_type" small />
                      <ItemPick v-else-if="c.type === 'Item'" v-model="r[c.field]" :side="BUYING.includes(d.doctype) ? 'buying' : 'selling'" @picked="(o) => onItemPicked(r, o)" />
                      <input v-else v-model="r[c.field]" class="h-8 w-full min-w-[120px] rounded-[8px] border border-line-2 px-2 text-[12px] bg-white focus:outline-none focus:border-accent/40" />
                    </td>
                    <td v-if="d.child.can_remove" class="px-1 py-1.5 text-center"><button type="button" class="text-ink-muted hover:text-sale" :title="L('Remove row','حذف السطر','Supprimer')" @click="rv.splice(i, 1)"><Icon name="close" :size="13" /></button></td>
                  </tr>
                  <tr v-if="!rv.length"><td :colspan="d.child.columns.length + 2" class="px-3 py-6 text-center text-ink-muted">{{ L("No rows.", "لا سطور.", "Aucune ligne.") }}</td></tr>
                </tbody>
              </table>
            </div>
            <div v-if="d.child.fill === 'outstanding'" class="px-3 py-2 border-t border-line-hair flex items-center gap-2 flex-wrap">
              <button type="button" class="inline-flex items-center gap-1 text-[11.5px] font-bold text-white bg-brand hover:bg-brand-dark h-7 px-2.5 rounded-chip disabled:opacity-50" :disabled="outLoading" @click="loadOutstanding">
                <Icon name="search" :size="12" color="#fff" />{{ outLoading ? "…" : L("Get outstanding invoices", "جلب الفواتير المستحقة", "Factures en attente") }}
              </button>
              <span v-if="out.unallocated" class="text-[11.5px] text-ink-3">{{ L("Unallocated", "غير مخصّص", "Non affecté") }} <b class="tnum">{{ fmt(out.unallocated) }}</b></span>
            </div>
            <div v-if="outRows.length" class="border-t border-line-hair bg-app-warm/20 max-h-[220px] overflow-auto">
              <table class="w-full text-[11.5px]">
                <thead><tr class="text-[10px] font-bold uppercase tracking-wider text-ink-muted"><th class="px-3 py-1.5 w-8"></th><th class="px-3 py-1.5 text-start">{{ L("Invoice","الفاتورة","Facture") }}</th><th class="px-3 py-1.5 text-start">{{ L("Date","التاريخ","Date") }}</th><th class="px-3 py-1.5 text-end">{{ L("Outstanding","المستحق","Restant") }}</th><th class="px-3 py-1.5 text-end w-28">{{ L("Allocate","المخصّص","Affecter") }}</th></tr></thead>
                <tbody>
                  <tr v-for="o in outRows" :key="o.name" class="border-t border-line-hair/60">
                    <td class="px-3 py-1"><input type="checkbox" v-model="o._on" @change="autoFill" /></td>
                    <td class="px-3 py-1 font-mono">{{ o.name }}</td>
                    <td class="px-3 py-1 text-ink-3">{{ o.date }}</td>
                    <td class="px-3 py-1 text-end tnum">{{ fmt(o.outstanding) }}</td>
                    <td class="px-3 py-1"><input type="number" step="any" min="0" v-model="o._amt" :disabled="!o._on" dir="ltr" class="h-7 w-full rounded-[7px] border border-line-2 px-1.5 text-[11.5px] text-end tnum bg-white disabled:bg-app-warm" /></td>
                  </tr>
                </tbody>
              </table>
              <div class="px-3 py-2 flex items-center gap-2 border-t border-line-hair">
                <span class="text-[11.5px] text-ink-3">{{ L("Selected", "المحدّد", "Sélection") }} <b class="tnum">{{ fmt(selectedAlloc) }}</b></span>
                <button type="button" class="ms-auto h-7 px-3 rounded-chip text-[11.5px] font-bold text-white bg-ink disabled:opacity-50" :disabled="!selectedAlloc || allocating" @click="allocate">{{ allocating ? "…" : L("Add to payment", "إضافة للدفعة", "Ajouter") }}</button>
              </div>
            </div>
            <div v-if="d.child.can_add" class="px-3 py-2 border-t border-line-hair flex items-center gap-4 flex-wrap">
              <button type="button" class="inline-flex items-center gap-1 text-[11.5px] font-semibold text-accent hover:text-accent-dark" @click="addRow"><Icon name="plus" :size="12" />{{ L("Add row", "إضافة سطر", "Ajouter une ligne") }}</button>
              <!-- The Desk's "Get Items From → Purchase Order", which takes several
                   orders at once: one supplier, three deliveries, one monthly bill. -->
              <button v-if="canPullPo" type="button" class="inline-flex items-center gap-1 text-[11.5px] font-semibold text-accent hover:text-accent-dark" @click="openPo"><Icon name="cart" :size="12" />{{ L("Get items from purchase order", "اسحب الأصناف من أمر شراء", "Importer d'une commande") }}</button>
            </div>
            <div v-if="poOpen" class="border-t border-line-hair bg-app-warm/30 px-3 py-2.5 space-y-2">
              <div class="text-[11.5px] font-bold">{{ L("Open purchase orders for", "أوامر الشراء المفتوحة لـ", "Commandes ouvertes de") }} {{ poSupplier }}</div>
              <div v-if="poLoading" class="text-[11.5px] text-ink-muted py-2">…</div>
              <div v-else-if="!pos.length" class="text-[11.5px] text-ink-muted py-2">{{ L("Nothing left to bill on this supplier's orders.", "مفيش حاجة متبقية للفوترة على أوامر المورّد ده.", "Rien à facturer.") }}</div>
              <label v-for="o in pos" :key="o.name" class="flex items-center gap-2.5 px-2.5 py-1.5 rounded-[9px] bg-white border border-line-2 cursor-pointer">
                <input type="checkbox" :value="o.name" v-model="poPicked" class="accent-accent w-3.5 h-3.5" />
                <span class="font-mono text-[11.5px] font-semibold flex-1 min-w-0 truncate">{{ o.name }}</span>
                <span class="text-[10.5px] text-ink-muted">{{ o.date }}</span>
                <span class="text-[10.5px] text-ink-muted tnum">{{ o.per_billed }}% {{ L("billed", "مفوتر", "facturé") }}</span>
                <span class="tnum text-[11.5px] font-bold">{{ fmt(o.total) }}</span>
              </label>
              <div class="flex justify-end gap-2 pt-0.5">
                <button type="button" class="h-8 px-3 rounded-chip text-[11.5px] font-semibold text-ink-3 hover:bg-white" @click="poOpen = false">{{ L("Back", "رجوع", "Retour") }}</button>
                <button type="button" class="h-8 px-3.5 rounded-chip text-[11.5px] font-bold text-white bg-ink disabled:opacity-40" :disabled="!poPicked.length || poBusy" @click="pullPo">{{ poBusy ? "…" : L("Add the lines", "أضف السطور", "Ajouter les lignes") }}</button>
              </div>
            </div>
          </div>

          <!-- tax rows: the account each tax line posts to, editable after submit -->
          <div v-if="d.tax && (d.tax.rows.length || d.tax.can_edit)" class="bg-white border border-line rounded-[12px] overflow-hidden">
            <div class="px-3 py-2 border-b border-line-hair flex items-center gap-2 text-[12px] font-bold">
              <Icon name="percent" :size="13" color="#0b5c4f" />{{ d.tax.label }}
              <span class="text-[10.5px] text-ink-muted font-normal">{{ d.tax.rows.length }}</span>
            </div>
            <div class="overflow-auto">
              <table class="w-full text-[12px]">
                <thead><tr class="bg-app-warm/60 text-[10px] font-bold uppercase tracking-wider text-ink-muted">
                  <th v-for="c in d.tax.columns" :key="c.field" class="px-2 py-2 text-start whitespace-nowrap" :class="c.type === 'Currency' ? 'text-end' : ''">{{ c.label }}</th>
                  <th v-if="d.tax.can_edit" class="w-8"></th>
                </tr></thead>
                <tbody>
                  <tr v-for="r in txv" :key="r.name" class="border-t border-line-hair align-top">
                    <td v-for="c in d.tax.columns" :key="c.field" class="px-1.5 py-1">
                      <span v-if="c.ro" class="block px-1 py-1.5 text-ink-2 truncate max-w-[280px]" :class="c.type === 'Currency' ? 'text-end tnum' : ''">{{ c.type === 'Currency' ? fmt(r[c.field]) : (r[c.field] || "—") }}</span>
                      <input v-else-if="['Currency','Float'].includes(c.type)" type="number" step="any" v-model="r[c.field]" dir="ltr"
                             :disabled="c.field === 'rate' ? r.charge_type === 'Actual' : (c.field === 'tax_amount' && r.charge_type !== 'Actual')"
                             class="h-8 w-full min-w-[96px] rounded-[8px] border border-line-2 px-2 text-[12px] text-end tnum bg-white disabled:bg-app-warm disabled:text-ink-muted" />
                      <select v-else-if="c.type === 'Select'" v-model="r[c.field]" class="h-8 w-full min-w-[130px] rounded-[8px] border border-line-2 px-1.5 text-[12px] bg-white">
                        <option v-for="op in (d.options[c.options] || [])" :key="op.value" :value="op.value">{{ op.label || op.value }}</option>
                      </select>
                      <SearchSelect v-else-if="c.type === 'Link'" v-model="r[c.field]" :items="d.options[c.options] || []" :placeholder="L('Select…','اختر…','Choisir…')" inputClass="h-8 text-[12px] bg-white min-w-[220px]" />
                      <input v-else v-model="r[c.field]" class="h-8 w-full min-w-[120px] rounded-[8px] border border-line-2 px-2 text-[12px] bg-white" />
                    </td>
                    <td v-if="d.tax.can_edit" class="px-1 py-1 text-center w-8"><button type="button" class="text-ink-muted hover:text-sale" @click="txv.splice(txv.indexOf(r), 1)"><Icon name="close" :size="13" /></button></td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-if="d.tax.can_edit" class="px-3 py-2 border-t border-line-hair flex items-center gap-3 flex-wrap">
              <button type="button" class="inline-flex items-center gap-1 text-[11.5px] font-semibold text-accent hover:text-accent-dark" @click="addTaxRow"><Icon name="plus" :size="12" />{{ L("Add a tax row", "إضافة سطر ضريبة", "Ajouter une taxe") }}</button>
              <span class="text-[10.5px] text-ink-muted">{{ L("Set the type to Actual and type the amount printed on the invoice when the rates are mixed.", "خلّي النوع Actual واكتبي المبلغ المطبوع في الفاتورة لما الضرايب تكون مختلطة.", "Type « Actual » pour saisir le montant figurant sur la facture.") }}</span>
            </div>
          </div>
        </template>
      </div>

      <div class="px-5 py-3 border-t border-line-hair flex items-center gap-2">
        <span v-if="error" class="text-[12px] text-sale truncate">{{ error }}</span>
        <span v-else class="text-[10.5px] text-ink-muted">{{ L("Saving runs ERPNext's own checks; totals and taxes recompute. Submit afterwards from the document.", "الحفظ بيمر على فحوصات ERPNext وبيعيد حساب الإجماليات. رحّل بعدها من المستند.", "L'enregistrement applique les contrôles ERPNext.") }}</span>
        <div class="ms-auto flex gap-2">
          <button class="h-9 px-3.5 rounded-chip text-[12px] font-semibold text-ink-2 hover:bg-app-warm" @click="$emit('close')">{{ L("Cancel", "إلغاء", "Annuler") }}</button>
          <button class="h-9 px-4 rounded-chip text-[12px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand disabled:opacity-50" :disabled="saving || !d.supported || (isJE && !balanced)" @click="save">{{ saving ? L("Saving…", "حفظ…", "…") : d.submitted_kind === 'reaccount' ? L("Save & repost ledger", "حفظ وإعادة ترحيل", "Enregistrer & reposter") : d.submitted_mode ? L("Update items", "تحديث السطور", "Mettre à jour") : L("Save draft", "حفظ المسودة", "Enregistrer") }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, h, watch, Teleport } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import SearchSelect from "@/components/SearchSelect.vue";
import api from "@/services/api";
import { useToast } from "@/composables/useToast";
import { currentCompany } from "@/composables/useLive";
import { useAnchoredMenu } from "@/utils/anchoredMenu";
import { fmtAmount } from "@/utils/helpers";

const props = defineProps({ doctype: { type: String, required: true }, name: { type: String, required: true } });
const emit = defineEmits(["close", "saved"]);
const { locale } = useI18n();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmt = (n) => fmtAmount(Number(n) || 0);

const d = ref({ supported: false, header: [], child: null, options: {} });
const hv = reactive({});
const rv = ref([]);
const txv = ref([]);
const loading = ref(true);
const saving = ref(false);
const error = ref("");

const isJE = computed(() => props.doctype === "Journal Entry");
const BUYING = ["Purchase Invoice", "Purchase Order", "Purchase Receipt"];

// ── Pull a supplier's open purchase orders into this draft bill ──
const poOpen = ref(false);
const poLoading = ref(false);
const poBusy = ref(false);
const pos = ref([]);
const poPicked = ref([]);
const poSupplier = ref("");
const canPullPo = computed(() => props.doctype === "Purchase Invoice" && d.value.docstatus === 0);
async function openPo() {
  poOpen.value = true; poLoading.value = true; poPicked.value = []; pos.value = [];
  try {
    const r = await api.call("accounting_portal.api.purchases.open_pos_for_supplier",
      { company: currentCompany(), invoice: props.name }) || {};
    pos.value = r.orders || [];
    poSupplier.value = r.supplier || "";
  } catch (e) { error.value = String(e?.message || e).slice(0, 200); }
  finally { poLoading.value = false; }
}
async function pullPo() {
  poBusy.value = true; error.value = "";
  try {
    const r = await api.call("accounting_portal.api.purchases.pull_po_items",
      { company: currentCompany(), invoice: props.name, orders: poPicked.value });
    toast.success(L(`${r.added} line(s) added`, `اتضافت ${r.added} سطر`, `${r.added} ligne(s) ajoutée(s)`));
    poOpen.value = false;
    await load();                       // the server appended them; re-read the draft
  } catch (e) { error.value = String(e?.message || e).slice(0, 220); }
  finally { poBusy.value = false; }
}
const totDr = computed(() => rv.value.reduce((s, r) => s + (Number(r.debit_in_account_currency) || 0), 0));
const totCr = computed(() => rv.value.reduce((s, r) => s + (Number(r.credit_in_account_currency) || 0), 0));
const balanced = computed(() => Math.abs(totDr.value - totCr.value) < 0.005 && totDr.value > 0);
const cellWidth = (c) => (["Currency", "Float", "Int"].includes(c.type) ? "width:120px" : c.type === "Select" ? "width:130px" : c.type === "Item" ? "width:190px" : "");

async function load() {
  loading.value = true; error.value = "";
  try {
    d.value = (await api.call("accounting_portal.api.docedit.get_draft", { doctype: props.doctype, name: props.name }, { fresh: true })) || { supported: false };
    for (const k of Object.keys(hv)) delete hv[k];
    for (const f of d.value.header || []) hv[f.field] = f.value;
    rv.value = (d.value.child?.rows || []).map((r) => ({ ...r }));
    txv.value = (d.value.tax?.rows || []).map((r) => ({ ...r }));
  } catch (e) { d.value = { supported: false }; error.value = String(e?.message || e).slice(0, 160); }
  finally { loading.value = false; }
}
onMounted(load);
watch(() => props.name, load);

function addTaxRow() {
  const row = {};
  for (const c of d.value.tax?.columns || []) row[c.field] = "";
  row.charge_type = "Actual";
  txv.value.push(row);
}
function addRow() {
  const row = {};
  for (const c of d.value.child?.columns || []) row[c.field] = "";
  // A credit / debit note is booked with negative quantities.
  if (d.value.child?.columns?.some((c) => c.field === "qty")) row.qty = d.value.is_return ? -1 : 1;
  rv.value.push(row);
}

// Picking an item fills the name straight away and seeds the rate from the last
// price, so the accountant sees what they chose instead of a bare code.
function onItemPicked(r, o) {
  r.item_code = o.item_code;
  if ("item_name" in r) r.item_name = o.item_name || o.item_code;
  if ("rate" in r && !Number(r.rate) && Number(o.rate)) r.rate = Number(o.rate);
  if ("qty" in r && !Number(r.qty)) r.qty = d.value.is_return ? -1 : 1;
}

// ── Allocation against open invoices (Payment Entry drafts) ──
const out = ref({ unallocated: 0 });
const outRows = ref([]);
const outLoading = ref(false);
const allocating = ref(false);
const selectedAlloc = computed(() => outRows.value.filter((o) => o._on).reduce((s2, o) => s2 + (Number(o._amt) || 0), 0));
async function loadOutstanding() {
  outLoading.value = true;
  try {
    const r = await api.call("accounting_portal.api.docedit.outstanding_for_payment", { name: props.name }, { fresh: true });
    out.value = r || {};
    outRows.value = (r?.rows || []).map((o) => ({ ...o, _on: false, _amt: 0 }));
    autoFillInitial();
  } catch (e) { error.value = String(e?.message || e).slice(0, 180); }
  finally { outLoading.value = false; }
}
// Oldest first against the unallocated balance — the Desk's default behaviour.
function autoFillInitial() {
  let left = Number(out.value.unallocated) || 0;
  for (const o of outRows.value) {
    if (left <= 0) break;
    const take = Math.min(left, Number(o.outstanding) || 0);
    o._on = take > 0; o._amt = Math.round(take * 100) / 100; left -= take;
  }
}
function autoFill() {
  for (const o of outRows.value) if (o._on && !Number(o._amt)) o._amt = Number(o.outstanding) || 0;
}
async function allocate() {
  allocating.value = true; error.value = "";
  try {
    const rows2 = outRows.value.filter((o) => o._on && Number(o._amt) > 0).map((o) => ({ name: o.name, doctype: out.value.doctype, amount: Number(o._amt) }));
    const r = await api.call("accounting_portal.api.docedit.allocate_payment", { name: props.name, rows: rows2 });
    d.value = r || d.value;
    rv.value = (d.value.child?.rows || []).map((x) => ({ ...x }));
    txv.value = (d.value.tax?.rows || []).map((x) => ({ ...x }));
    outRows.value = []; out.value = {};
  } catch (e) { error.value = String(e?.message || e).slice(0, 200); }
  finally { allocating.value = false; }
}

async function save() {
  // Rewriting a reserved order's lines releases the reservation — stock someone
  // has already set aside for this customer goes back to the free pool. The Desk
  // asks first; a save that quietly unreserved would be the portal's to explain.
  if (d.value.reserved_stock && !confirm(L(
    "The stock reserved for this order will be released when the lines change. Continue?",
    "المخزون المحجوز للأمر ده هيتفكّ لما السطور تتغير. نكمل؟",
    "Le stock réservé sera libéré. Continuer ?"))) return;
  saving.value = true; error.value = "";
  try {
    const header = {};
    for (const f of d.value.header || []) if (!f.ro) header[f.field] = hv[f.field];
    const rows = d.value.child ? rv.value : null;
    const tax = d.value.tax ? txv.value : null;
    await api.call("accounting_portal.api.docedit.save_draft", { doctype: props.doctype, name: props.name, header, rows, tax });
    toast.success(L("Draft saved", "تم حفظ المسودة", "Brouillon enregistré"));
    emit("saved");
  } catch (e) { error.value = String(e?.message || e).slice(0, 220); }
  finally { saving.value = false; }
}

// ── Item picker: type-ahead against sales.item_options (code, name, last rate) ──
const ItemPick = {
  props: { modelValue: { type: String, default: "" }, side: { type: String, default: "selling" } },
  emits: ["update:modelValue", "picked"],
  setup(p, { emit: em }) {
    const hits = ref([]); const open = ref(false); let t = null;
    const inputEl = ref(null);
    const { style, place, follow, unfollow } = useAnchoredMenu(400);
    const show = () => { open.value = true; place(inputEl.value); follow(); };
    const hide = () => { open.value = false; unfollow(); };
    async function onInput(ev) {
      const q = ev.target.value; em("update:modelValue", q); show();
      clearTimeout(t);
      t = setTimeout(async () => {
        try { hits.value = (await api.call("accounting_portal.api.sales.item_options", { search: q, limit: 15, side: p.side })) || []; }
        catch { hits.value = []; }
        place(inputEl.value);
      }, 220);
    }
    function pick(o) { em("update:modelValue", o.item_code); em("picked", o); hide(); hits.value = []; }
    return () => h("div", { class: "relative" }, [
      h("input", { ref: inputEl, value: p.modelValue, placeholder: "—", dir: "ltr",
        class: "h-8 w-full min-w-[170px] rounded-[8px] border border-line-2 px-2 text-[12px] bg-white focus:outline-none focus:border-accent/40",
        onInput, onFocus: () => { if (hits.value.length) show(); }, onBlur: () => setTimeout(hide, 150) }),
      // to <body>: the rows table scrolls, and a scrolling ancestor clips an
      // absolute child no matter how high its z-index is
      open.value && hits.value.length
        ? h(Teleport, { to: "body" }, [
            h("div", { class: "bg-white border border-line rounded-[10px] shadow-pop py-1", style: style.value },
              // Picture, then the name, then the code — and the description under
              // it, because two items can share one and differ only in code.
              hits.value.map((o) => h("button", {
                type: "button", key: o.item_code,
                class: "w-full text-start px-3 py-2 text-[12px] hover:bg-app-warm flex items-center gap-2.5",
                onMousedown: (e) => { e.preventDefault(); pick(o); },
              }, [
                o.image
                  ? h("img", { src: o.image, loading: "lazy", class: "w-9 h-9 rounded-[7px] object-cover border border-line flex-shrink-0",
                               onError: (e) => { e.target.style.display = "none"; } })
                  : h("span", { class: "w-9 h-9 rounded-[7px] bg-app-warm border border-line flex-shrink-0" }),
                h("div", { class: "min-w-0 flex-1" }, [
                  h("div", { class: "truncate" }, o.item_name || o.item_code),
                  h("div", { class: "text-[10.5px] text-ink-muted font-mono truncate" }, o.sku ? `${o.item_code} · ${o.sku}` : o.item_code),
                  o.description && o.description !== o.item_name
                    ? h("div", { class: "text-[10.5px] text-ink-muted truncate" }, o.description) : null,
                  o.variant_of_name
                    ? h("div", { class: "text-[10.5px] text-ink-muted truncate" }, "\u21b3 " + o.variant_of_name) : null,
                ]),
              ])))
          ])
        : null,
    ]);
  },
};

// ── Party picker: type-ahead against accountant.party_options for the row's party_type ──
const PartyPick = {
  props: { modelValue: { type: String, default: "" }, partyType: { type: String, default: "" }, disabled: Boolean, small: Boolean },
  emits: ["update:modelValue"],
  setup(p, { emit: em }) {
    const hits = ref([]); const open = ref(false); let t = null;
    async function onInput(ev) {
      const q = ev.target.value; em("update:modelValue", q); open.value = true;
      clearTimeout(t);
      t = setTimeout(async () => {
        if (!p.partyType) { hits.value = []; return; }
        try { hits.value = (await api.call("accounting_portal.api.accountant.party_options", { party_type: p.partyType, q, limit: 12 })) || []; } catch { hits.value = []; }
      }, 220);
    }
    function pick(o) { em("update:modelValue", o.name); open.value = false; hits.value = []; }
    return () => h("div", { class: "relative" }, [
      h("input", { value: p.modelValue, disabled: p.disabled, placeholder: p.partyType || "—", dir: "ltr",
        class: (p.small ? "h-8 text-[12px] min-w-[160px]" : "h-9 text-[12.5px]") + " w-full rounded-[8px] border border-line-2 px-2 bg-white focus:outline-none focus:border-accent/40 disabled:bg-app-warm",
        onInput, onFocus: () => { if (hits.value.length) open.value = true; }, onBlur: () => setTimeout(() => (open.value = false), 150) }),
      open.value && hits.value.length ? h("div", { class: "absolute z-30 mt-1 start-0 w-72 max-h-56 overflow-auto bg-white border border-line rounded-[10px] shadow-pop py-1" },
        hits.value.map((o) => h("button", { type: "button", class: "w-full text-start px-3 py-1.5 text-[12px] hover:bg-app-warm", onMousedown: (e) => { e.preventDefault(); pick(o); } },
          [h("span", { class: "font-mono text-[10.5px] text-ink-muted me-2" }, o.name), h("span", {}, o.label || "")]))) : null,
    ]);
  },
};
</script>
