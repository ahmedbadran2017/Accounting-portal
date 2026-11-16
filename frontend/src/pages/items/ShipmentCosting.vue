<template>
  <div class="space-y-3.5">
    <!-- headline -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <div v-for="k in kpis" :key="k.key" class="bg-white rounded-card border border-line shadow-card px-4 py-3">
        <div class="text-[11px] font-bold uppercase tracking-wider text-ink-muted">{{ k.label }}</div>
        <div class="text-[20px] font-extrabold mt-1 tnum" :style="{ color: k.color }" dir="ltr">{{ k.value }}</div>
        <div class="text-[11px] text-ink-muted mt-0.5">{{ k.sub }}</div>
      </div>
    </div>

    <div v-if="loadErr" class="bg-rose-50 border border-rose-200 rounded-card px-4 py-4 text-[12px] text-rose-700">{{ loadErr }}</div>

    <div class="flex flex-wrap gap-4 items-start">
      <!-- column: shipments + history -->
      <div class="flex-[1_1_300px] max-w-[380px] min-w-0 space-y-3">
        <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
          <div class="px-3.5 py-2.5 border-b border-line-hair flex items-center gap-2">
            <span class="text-[13px] font-bold">{{ L("Shipments", "الشحنات", "Expéditions") }}</span>
            <div class="ms-auto flex gap-1 bg-app-warm rounded-chip p-0.5">
              <button v-for="m in MODES" :key="m.k" class="px-2.5 py-1 rounded-lg text-[11px] font-semibold"
                      :class="modeFilter === m.k ? 'bg-white text-accent-dark shadow-card' : 'text-ink-3'" @click="modeFilter = m.k">{{ m.label() }}</button>
            </div>
          </div>
          <div v-if="ovLoad" class="px-4 py-6 text-[12px] text-ink-muted">{{ L("Loading…", "جارٍ التحميل…", "Chargement…") }}</div>
          <button v-for="r in rows" :key="r.key" class="w-full text-start px-3.5 py-2.5 border-b border-line-hair block"
                  :class="selKey === r.key ? 'bg-[#e7f4f1] shadow-[inset_-3px_0_0_#0f766e]' : 'hover:bg-app-warm/60'" @click="open(r.key)">
            <span class="flex items-center justify-between gap-2">
              <span class="font-mono text-[12.5px] font-semibold truncate" dir="ltr">{{ r.receipts[0] }}<span v-if="r.receipts.length > 1" class="text-ink-muted"> +{{ r.receipts.length - 1 }}</span></span>
              <span class="text-[10.5px] font-bold px-2 py-0.5 rounded-full whitespace-nowrap" :class="STATE[r.state].cls">{{ STATE[r.state].label() }}</span>
            </span>
            <span class="flex justify-between gap-2 text-[11.5px] text-ink-muted mt-1">
              <span class="truncate">{{ r.mode === 'Air' ? L('Air','جوي','Aérien') : L('Sea','بحري','Maritime') }} · {{ r.supplier }} · {{ r.date }}<span v-if="r.customs_declaration"> · #{{ r.customs_declaration }}</span></span>
              <span class="tnum whitespace-nowrap" dir="ltr">{{ r.per_kg ? fmt(r.per_kg, 2) + ' /kg' : fmt(r.kg, 0) + ' kg' }}</span>
            </span>
          </button>
        </div>

        <div v-if="det" class="bg-white rounded-card border border-line shadow-card overflow-hidden">
          <div class="px-3.5 py-2.5 border-b border-line-hair text-[13px] font-bold">{{ L("History", "سجل التعديلات", "Historique") }}</div>
          <div v-if="!history.length" class="px-3.5 py-3 text-[12px] text-ink-muted">{{ L("Nothing saved yet.", "لسه مفيش حاجة متسجلة.", "Rien d'enregistré.") }}</div>
          <div v-for="(h, i) in history" :key="i" class="px-3.5 py-2 border-b border-line-hair text-[12px]">
            <div class="flex justify-between gap-2"><span class="font-semibold truncate">{{ h.who }}</span><span class="text-ink-muted tnum" dir="ltr">{{ h.when }}</span></div>
            <div class="text-ink-3 mt-0.5 break-words">{{ h.what }}</div>
          </div>
        </div>

        <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
          <button class="w-full px-3.5 py-2.5 flex items-center gap-2 text-[13px] font-bold" @click="toggleFx">
            {{ L("TRY → MAD by month", "سعر الليرة بالشهر", "TRY → MAD par mois") }}
            <Icon name="chev" :size="14" class="ms-auto" :class="fxOpen ? '-rotate-90' : 'rotate-90'" />
          </button>
          <div v-if="fxOpen" class="px-3.5 pb-3 grid grid-cols-2 gap-2">
            <label v-for="f in fxRows" :key="f.month" class="block">
              <span class="text-[11px] text-ink-muted">{{ f.month }} <span v-if="f.estimate && !f.rate">· {{ L("est.", "تقدير", "est.") }} {{ f.estimate }}</span></span>
              <input type="number" step="0.0001" :value="f.rate || ''" :placeholder="f.estimate || '—'" :disabled="!canWrite"
                     class="fld fld-sm w-full tnum text-end" dir="ltr" @change="saveFx(f.month, $event.target.value)" />
            </label>
          </div>
        </div>
      </div>

      <!-- detail -->
      <div class="flex-[999_1_560px] min-w-0 space-y-3">
        <div v-if="!det && !detLoad" class="bg-white rounded-card border border-line shadow-card px-5 py-10 text-center text-[13px] text-ink-muted">
          {{ L("Pick a shipment on the side.", "اختار شحنة من القايمة.", "Choisissez une expédition.") }}
        </div>
        <div v-if="detLoad" class="bg-white rounded-card border border-line shadow-card px-5 py-10 text-center text-[12px] text-ink-muted">{{ L("Loading…", "جارٍ التحميل…", "Chargement…") }}</div>

        <div v-if="det && !detLoad" class="bg-white rounded-card border border-line shadow-card px-5 py-4 space-y-4">
          <!-- header -->
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div class="min-w-0">
              <div class="font-mono text-[18px] font-bold" dir="ltr">{{ ed.receipts.join(' + ') }}</div>
              <div class="text-[12.5px] text-ink-3 mt-0.5">
                {{ calc.receipts && calc.receipts[0] && calc.receipts[0].date }} · {{ calc.receipts && calc.receipts[0] && calc.receipts[0].supplier }}
                · <span class="tnum" dir="ltr">{{ fmt(t.units, 0) }}</span> {{ L("units", "قطعة", "unités") }} · <span class="tnum" dir="ltr">{{ fmt(t.kg, 0) }}</span> kg
              </div>
            </div>
            <div class="flex items-center gap-2 flex-wrap">
              <span class="text-[11px] font-bold px-2.5 py-1 rounded-full" :class="WF[status].cls">{{ WF[status].label() }}</span>
              <span v-if="dirty" class="text-[11px] font-semibold text-amber-700">{{ L("Unsaved changes", "تعديلات مش متسجلة", "Non enregistré") }}</span>
              <UiButton v-if="editable" variant="primary" size="sm" :busy="saving" :disabled="saving || !dirty" @click="save">{{ L("Save", "حفظ", "Enregistrer") }}</UiButton>
              <UiButton v-if="ed.name && status === 'Draft' && canWrite" variant="secondary" size="sm" :disabled="dirty" @click="setStatus('Review')">{{ L("Send for review", "إرسال للمراجعة", "Envoyer en revue") }}</UiButton>
              <template v-if="status === 'Review' && canWrite">
                <UiButton variant="secondary" size="sm" @click="setStatus('Draft')">{{ L("Back to draft", "رجّع للتعديل", "Retour brouillon") }}</UiButton>
                <UiButton variant="primary" size="sm" @click="setStatus('Locked')">{{ L("Approve and lock", "اعتماد وقفل", "Approuver et verrouiller") }}</UiButton>
              </template>
              <UiButton v-if="status === 'Locked' && canWrite" variant="secondary" size="sm" @click="setStatus('Draft')">{{ L("Reopen", "فتح للتعديل", "Rouvrir") }}</UiButton>
            </div>
          </div>
          <div v-if="actErr" class="text-[12px] text-rose-700">{{ actErr }}</div>

          <!-- shipment fields -->
          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 bg-app-warm/40 border border-line-hair rounded-[12px] p-3">
            <label class="block">
              <span class="text-[11px] font-semibold text-ink-3">{{ L("Mode", "نوع الشحن", "Mode") }}</span>
              <select v-model="ed.mode" :disabled="!editable" class="fld fld-md mt-1 w-full" @change="touch">
                <option value="Sea">{{ L("Sea — costs from bills", "بحري — المصاريف من الفواتير", "Maritime — frais des factures") }}</option>
                <option value="Air">{{ L("Air — flat rate per kg", "جوي — سعر كيلو ثابت", "Aérien — tarif au kg") }}</option>
              </select>
            </label>
            <label class="block">
              <span class="text-[11px] font-semibold text-ink-3">{{ L("TRY → MAD", "سعر الصرف ₺ ← د.م", "TRY → MAD") }}</span>
              <input v-model="ed.fx_rate" type="number" step="0.0001" :disabled="!editable" :placeholder="calc.fx ? String(calc.fx) : '—'"
                     class="fld fld-md mt-1 w-full tnum text-end" dir="ltr" @input="touch" />
              <span class="text-[10.5px] text-ink-muted">{{ fxSourceLabel }}</span>
            </label>
            <label class="block">
              <span class="text-[11px] font-semibold text-ink-3">{{ L("Customs declaration", "رقم التصريح الجمركي", "Déclaration douane") }}</span>
              <input v-model="ed.customs_declaration" :disabled="!editable" class="fld fld-md mt-1 w-full" dir="ltr" @input="touch" />
            </label>
            <label class="block">
              <span class="text-[11px] font-semibold text-ink-3">{{ L("B/L / container", "البوليصة / الكونتينر", "Connaissement / conteneur") }}</span>
              <input v-model="ed.bill_of_lading" :disabled="!editable" class="fld fld-md mt-1 w-full" dir="ltr" @input="touch" />
            </label>
            <div class="sm:col-span-2 lg:col-span-4">
              <div class="text-[11px] font-semibold text-ink-3 mb-1">{{ L("Receipts in this shipment", "الاستلامات في الشحنة", "Réceptions de l'expédition") }}</div>
              <div class="flex flex-wrap items-center gap-1.5">
                <span v-for="(r, i) in ed.receipts" :key="r" class="inline-flex items-center gap-1.5 font-mono text-[12px] px-2.5 py-1 rounded-full bg-[#e7f4f1] text-accent-dark" dir="ltr">
                  {{ r }}<button v-if="editable && i > 0" class="text-[12px]" :aria-label="L('Remove','شيل','Retirer')" @click="removeReceipt(r)">✕</button>
                </span>
                <button v-if="editable" class="text-[12px] px-2.5 py-1 rounded-full border border-dashed border-line text-ink-3" @click="toggleMerge">+ {{ L("Add receipt", "ضم استلام", "Ajouter réception") }}</button>
              </div>
              <div v-if="mergeOpen" class="mt-2 border border-line rounded-[10px] bg-white p-2 space-y-1">
                <div v-if="!mergeCands.length" class="text-[12px] text-ink-muted px-1">{{ L("No free receipts within three weeks.", "مفيش استلامات فاضية في حدود 3 أسابيع.", "Aucune réception libre.") }}</div>
                <div v-for="c in mergeCands" :key="c.name" class="flex items-center justify-between gap-2 text-[12px] px-1">
                  <span><span class="font-mono" dir="ltr">{{ c.name }}</span> · {{ c.date }} · {{ c.supplier }} · <span class="tnum" dir="ltr">{{ fmt(c.kg, 0) }}</span> kg</span>
                  <UiButton variant="secondary" size="xs" @click="addReceipt(c.name)">{{ L("Add", "ضم", "Ajouter") }}</UiButton>
                </div>
              </div>
            </div>
          </div>

          <!-- the equation -->
          <div class="flex flex-wrap items-stretch gap-2">
            <template v-for="(b, i) in eqBlocks" :key="b.key">
              <span v-if="i" class="self-center text-[18px] text-ink-muted px-0.5">{{ b.op }}</span>
              <div class="rounded-[12px] px-3 py-2 min-w-[100px]" :class="b.cls">
                <div class="text-[11px] text-ink-3">{{ b.label }}</div>
                <div class="text-[17px] font-bold tnum" dir="ltr">{{ b.value }}</div>
                <div class="text-[10.5px] text-ink-muted" :dir="b.ltrNote ? 'ltr' : null">{{ b.note }}</div>
              </div>
            </template>
          </div>
          <div v-if="issueList.length" class="flex flex-wrap gap-1.5">
            <span v-for="x in issueList" :key="x" class="text-[11.5px] px-2.5 py-1 rounded-full bg-amber-50 text-amber-800">{{ x }}</span>
          </div>

          <!-- costs -->
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-3">
            <div v-for="side in SIDES" :key="side.k" class="border border-line rounded-[12px] p-3 space-y-2">
              <div class="flex items-center justify-between gap-2">
                <span class="text-[13px] font-bold">{{ side.label() }}</span>
                <span class="text-[13px] font-bold tnum" dir="ltr">{{ fmt(sideTotal(side.k), 2) }} {{ side.ccy }}</span>
              </div>
              <div v-if="side.k === 'Morocco' && ed.mode === 'Air'" class="text-[12px] bg-amber-50 text-amber-800 rounded-lg px-2.5 py-1.5">
                {{ L("Air shipment: Morocco cost is the air rate per kg; bills are not spread.", "شحنة جوي: مصاريف المغرب بسعر كيلو الجوي، والفواتير مش بتتوزع.", "Aérien : tarif au kg, les factures ne sont pas réparties.") }}
              </div>
              <div v-for="(c, i) in chargesOf(side.k)" :key="c._k" class="grid grid-cols-[minmax(0,1fr)_96px_24px] gap-2 items-center bg-[#e7f4f1] rounded-lg px-2.5 py-1.5">
                <div class="min-w-0 text-[12px]">
                  <div class="font-mono font-semibold truncate" dir="ltr">{{ c.purchase_invoice || L('Manual', 'يدوي', 'Manuel') }}</div>
                  <div class="text-ink-3 truncate" dir="auto">{{ c.description }}<span v-if="c.full_amount"> · {{ L("of", "من", "sur") }} <span class="tnum" dir="ltr">{{ fmt(c.full_amount, 0) }}</span></span></div>
                </div>
                <input type="number" step="0.01" v-model.number="c.amount" :disabled="!editable" class="fld fld-sm w-full tnum text-end" dir="ltr" @input="touch" />
                <button v-if="editable" class="text-ink-muted hover:text-rose-700" :aria-label="L('Unlink','فك الربط','Délier')" @click="unlink(c)">✕</button>
              </div>
              <div v-if="editable" class="flex flex-wrap gap-2 items-center">
                <UiButton variant="secondary" size="xs" @click="toggleCands(side.k)">{{ cands[side.k].open ? L('Hide bills', 'اخفي الفواتير', 'Masquer') : L('Link bills', 'ربط فواتير', 'Lier des factures') }}</UiButton>
                <input v-model="manual[side.k].amount" type="number" step="0.01" :placeholder="L('Manual amount', 'مبلغ يدوي', 'Montant manuel')" class="fld fld-sm w-[120px] tnum text-end" dir="ltr" />
                <input v-model="manual[side.k].desc" :placeholder="L('What it is', 'وصف', 'Libellé')" class="fld fld-sm flex-1 min-w-[120px]" />
                <UiButton variant="secondary" size="xs" :disabled="!(Number(manual[side.k].amount) > 0)" @click="addManual(side.k)">{{ L("Add", "إضافة", "Ajouter") }}</UiButton>
              </div>
              <div v-if="cands[side.k].open" class="border border-line-hair rounded-lg max-h-[320px] overflow-y-auto">
                <div v-if="cands[side.k].loading" class="px-3 py-3 text-[12px] text-ink-muted">{{ L("Loading…", "جارٍ التحميل…", "Chargement…") }}</div>
                <div v-else-if="!freeCands(side.k).length" class="px-3 py-3 text-[12px] text-ink-muted">{{ L("No bill near these dates.", "مفيش فواتير قريبة من التاريخ ده.", "Aucune facture proche.") }}</div>
                <label v-for="b in freeCands(side.k)" :key="b.line" class="grid grid-cols-[18px_minmax(0,1fr)_auto] gap-2 items-center px-2.5 py-1.5 border-b border-line-hair cursor-pointer hover:bg-app-warm/50">
                  <input type="checkbox" class="accent-[#0f766e]" @change="link(side.k, b)" />
                  <span class="min-w-0 text-[12px]">
                    <span class="flex items-center gap-1.5"><span class="font-mono font-semibold" dir="ltr">{{ b.bill }}</span>
                      <span v-if="b.suggested" class="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-[#e7f4f1] text-accent-dark">{{ b.suggested === 'declaration' ? L('declaration no.', 'رقم التصريح', 'n° déclaration') : L('draft LCV', 'مسودة توزيع', 'brouillon LCV') }}</span></span>
                    <span class="block text-ink-3 truncate" dir="auto">{{ b.supplier }} · {{ b.what }} · {{ b.date }}<span v-if="b.bill_no"> · {{ b.bill_no }}</span></span>
                  </span>
                  <span class="text-end text-[12px] tnum" dir="ltr">{{ fmt(b.left, 0) }}<span v-if="b.taken" class="block text-[10.5px] text-ink-muted">{{ L("used", "متاخد", "pris") }} {{ fmt(b.taken, 0) }}</span></span>
                </label>
              </div>
            </div>
          </div>

          <!-- items -->
          <div class="flex flex-wrap items-center justify-between gap-2">
            <span class="text-[13px] font-bold">{{ L("Items", "الأصناف", "Articles") }}</span>
            <label class="flex items-center gap-2 text-[12px]">
              <span class="text-ink-3">{{ L("Turkey costs spread by", "توزيع مصاريف تركيا", "Frais Turquie répartis par") }}</span>
              <select v-model="ed.tr_basis" :disabled="!editable" class="fld fld-sm" @change="touch">
                <option value="Weight">{{ L("weight", "الوزن", "poids") }}</option>
                <option value="Value">{{ L("value", "القيمة", "valeur") }}</option>
              </select>
            </label>
          </div>
          <div class="overflow-x-auto border border-line rounded-[12px]">
            <table class="w-full min-w-[860px] text-[12.5px]">
              <thead class="bg-app-warm/40 text-[11px] text-ink-muted">
                <tr>
                  <th class="text-start px-3 py-2 font-semibold">{{ L("Item", "الصنف", "Article") }}</th>
                  <th class="text-end px-2 py-2 font-semibold">{{ L("Qty", "كمية", "Qté") }}</th>
                  <th class="text-end px-2 py-2 font-semibold">{{ L("kg / unit", "كجم / قطعة", "kg / unité") }}</th>
                  <th class="text-end px-2 py-2 font-semibold">{{ L("Supplier price", "سعر المورد", "Prix fournisseur") }}</th>
                  <th class="text-end px-2 py-2 font-semibold">{{ L("After Turkey", "بعد تركيا", "Après Turquie") }}</th>
                  <th class="text-end px-2 py-2 font-semibold">{{ L("+ Morocco", "+ المغرب", "+ Maroc") }}</th>
                  <th class="text-end px-2 py-2 font-semibold">{{ L("Final", "النهائي", "Final") }}</th>
                  <th class="text-end px-3 py-2 font-semibold">{{ L("Booked", "المتسجل", "Comptabilisé") }}</th>
                </tr>
              </thead>
              <tbody>
                <template v-for="it in calc.items || []" :key="it.item_code">
                  <tr class="border-t border-line-hair" :class="openItem === it.item_code ? 'bg-[#e7f4f1]' : ''">
                    <td class="px-3 py-1.5 max-w-[260px]">
                      <button class="text-start truncate block w-full hover:underline" dir="auto" @click="openItem = openItem === it.item_code ? '' : it.item_code">{{ it.item_name || it.item_code }}</button>
                      <span v-if="it.flag" class="text-[10.5px] font-semibold" :class="it.flag === 'from_receipt' ? 'text-amber-700' : 'text-rose-700'">{{ FLAG[it.flag] ? FLAG[it.flag]() : it.flag }}</span>
                    </td>
                    <td class="px-2 py-1.5 text-end tnum" dir="ltr">{{ fmt(it.qty, 0) }}</td>
                    <td class="px-2 py-1.5 text-end">
                      <input type="number" step="0.001" :value="it.weight || ''" :disabled="!canWrite || status === 'Locked'"
                             class="fld fld-sm w-[80px] tnum text-end" :class="it.no_weight ? 'border-rose-300 bg-rose-50' : ''" dir="ltr"
                             :aria-label="L('Weight per unit (kg)', 'وزن القطعة بالكيلو', 'Poids unitaire (kg)')" @change="saveWeight(it, $event.target.value)" />
                    </td>
                    <td class="px-2 py-1.5 text-end tnum" dir="ltr">{{ fmt(it.price, 2) }} <span class="text-ink-muted">{{ CCY[it.currency] || it.currency }}</span></td>
                    <td class="px-2 py-1.5 text-end tnum" dir="ltr">{{ fmt(it.after_turkey, 2) }}</td>
                    <td class="px-2 py-1.5 text-end tnum" dir="ltr">{{ fmt(it.ma_unit, 2) }}</td>
                    <td class="px-2 py-1.5 text-end tnum font-bold" dir="ltr">{{ fmt(it.final, 2) }}</td>
                    <td class="px-3 py-1.5 text-end tnum text-ink-3" dir="ltr">{{ fmt(it.booked_unit, 2) }}</td>
                  </tr>
                  <tr v-if="openItem === it.item_code" class="bg-app-warm/50">
                    <td colspan="8" class="px-3 py-2 text-[12px] text-ink-2">
                      <div class="tnum" dir="ltr">{{ eqLine(it) }}</div>
                      <div class="text-ink-muted mt-0.5">{{ L("Price from", "السعر من", "Prix de") }} {{ it.source === 'receipt' ? L('the receipt (no supplier bill found)', 'الاستلام (مفيش فاتورة مورد)', 'la réception') : it.source || '—' }}</div>
                    </td>
                  </tr>
                </template>
              </tbody>
            </table>
          </div>
          <div class="text-[11.5px] text-ink-muted">{{ L("Weights save straight to the item and are logged. Everything else is saved with the shipment.", "الأوزان بتتحفظ على الصنف نفسه على طول ومتسجلة. باقي التعديلات بتتحفظ مع الشحنة.", "Les poids sont enregistrés sur l'article ; le reste avec l'expédition.") }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
// Shipment costing — one import shipment at a time, from the supplier's price to
// the landed cost per unit. The numbers come from api/shipment_costing.py; this
// page only edits the shipment and asks the server to recalculate (preview) as
// fields change, so the formula lives in one place.
import { ref, computed, watch, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";
import { useAuth } from "@/composables/useAuth";
import { useToast } from "@/composables/useToast";
import Icon from "@/components/Icon.vue";
import UiButton from "@/components/UiButton.vue";

const { locale } = useI18n();
const { entityId } = useUi();
const { can } = useAuth();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const canWrite = computed(() => can("post_entries"));
const M = "accounting_portal.api.shipment_costing.";
const fmt = (n, d = 2) => (n === null || n === undefined || n === "" ? "—" : Number(n).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d }));

const MODES = [
  { k: "", label: () => L("All", "الكل", "Tout") },
  { k: "Sea", label: () => L("Sea", "بحري", "Mer") },
  { k: "Air", label: () => L("Air", "جوي", "Air") },
];
const STATE = {
  complete: { cls: "bg-emerald-50 text-emerald-700", label: () => L("Complete", "كاملة", "Complète") },
  partial: { cls: "bg-amber-50 text-amber-800", label: () => L("Morocco only", "المغرب بس", "Maroc seul") },
  no_costs: { cls: "bg-rose-50 text-rose-700", label: () => L("No costs", "مفيش مصاريف", "Sans frais") },
  air: { cls: "bg-sky-50 text-sky-800", label: () => L("Air rate", "سعر الجوي", "Tarif aérien") },
};
const WF = {
  Draft: { cls: "bg-stone-100 text-stone-600", label: () => L("Draft", "مسودة", "Brouillon") },
  Review: { cls: "bg-amber-50 text-amber-800", label: () => L("In review", "في المراجعة", "En revue") },
  Locked: { cls: "bg-emerald-50 text-emerald-700", label: () => L("Locked", "مقفولة", "Verrouillée") },
};
const SIDES = [
  { k: "Morocco", ccy: "MAD", label: () => L("Morocco costs (freight + customs)", "مصاريف المغرب (شحن + جمارك)", "Frais Maroc (fret + douane)") },
  { k: "Turkey", ccy: "TRY", label: () => L("Turkey costs (Maslak)", "مصاريف تركيا (مسلك)", "Frais Turquie (Maslak)") },
];
const FLAG = {
  from_receipt: () => L("price from receipt", "السعر من الاستلام", "prix de la réception"),
  missing: () => L("no price", "مفيش سعر", "sans prix"),
  fx_missing: () => L("no exchange rate", "مفيش سعر صرف", "sans taux"),
};
const CCY = { TRY: "₺", MAD: "د.م", USD: "$" };

const ov = ref({}), ovLoad = ref(true), loadErr = ref("");
const modeFilter = ref("");
const selKey = ref("");
const det = ref(null), detLoad = ref(false);
const ed = ref({ receipts: [], charges: [] });
const calc = ref({});
const history = ref([]);
const dirty = ref(false), saving = ref(false), actErr = ref("");
const openItem = ref("");
const mergeOpen = ref(false), mergeCands = ref([]);
const cands = ref({ Morocco: { open: false, loading: false, rows: [] }, Turkey: { open: false, loading: false, rows: [] } });
const manual = ref({ Morocco: { amount: "", desc: "" }, Turkey: { amount: "", desc: "" } });
const fxOpen = ref(false), fxRows = ref([]);

const rows = computed(() => (ov.value.rows || []).filter((r) => !modeFilter.value || r.mode === modeFilter.value));
const t = computed(() => calc.value.totals || {});
const status = computed(() => (det.value && det.value.shipment.status) || "Draft");
const editable = computed(() => canWrite.value && status.value === "Draft");
const kpis = computed(() => {
  const k = ov.value.kpi || {};
  return [
    { key: "n", label: L("Import receipts 2026", "استلامات مستوردة 2026", "Réceptions import 2026"), value: fmt(k.receipts, 0), sub: fmt(k.kg, 0) + " kg", color: "#1c2622" },
    { key: "c", label: L("Waiting on 153.03", "مستنية على 153.03", "En attente 153.03"), value: fmt(k.clearing_153, 0), sub: L("MAD not in any cost yet", "د.م مش داخلة في أي تكلفة", "MAD hors coût"), color: "#b45309" },
    { key: "d", label: L("Complete shipments", "شحنات مكتملة", "Expéditions complètes"), value: (k.complete || 0) + " / " + (k.shipments || 0), sub: L("Morocco + Turkey linked", "المغرب وتركيا مربوطين", "Maroc + Turquie liés"), color: "#047857" },
    { key: "w", label: L("Lines without weight", "أسطر من غير وزن", "Lignes sans poids"), value: fmt(k.no_weight_lines, 0), sub: L("fill before spreading by kg", "تتكمّل قبل التوزيع بالكيلو", "à compléter"), color: "#be123c" },
  ];
});
const fxSourceLabel = computed(() => ({
  override: L("set for this shipment", "متعدّل للشحنة دي", "fixé pour l'expédition"),
  table: L("from the month table", "من جدول الشهر", "table du mois"),
  estimate: L("estimate from the month's receipts — set the real rate", "تقدير من استلامات الشهر — اكتب السعر الحقيقي", "estimation — saisir le vrai taux"),
  missing: L("no rate for this month", "مفيش سعر للشهر ده", "aucun taux"),
}[calc.value.fx_source] || ""));
const eqBlocks = computed(() => {
  const c = calc.value, x = t.value, air = c.mode === "Air";
  const warn = "bg-amber-50 border border-dashed border-amber-300";
  return [
    { key: "p", label: L("Supplier prices", "سعر المنتجات", "Prix fournisseurs"), value: x.product_try ? fmt(x.product_try, 0) + " ₺" : fmt(x.product_mad, 0), note: L("supplier bills", "فواتير المورد", "factures fournisseur"), cls: "bg-app-warm" },
    { key: "tr", op: "+", label: L("Turkey costs", "مصاريف تركيا", "Frais Turquie"), value: fmt(x.turkey_try, 0) + " ₺", note: x.turkey_try ? "" : L("none linked", "مفيش مربوط", "aucun"), cls: x.turkey_try ? "bg-app-warm" : warn },
    { key: "fx", op: "×", label: L("Exchange rate", "سعر الصرف", "Taux"), value: c.fx ? String(c.fx) : "?", note: fxSourceLabel.value, cls: c.fx_source === "estimate" || !c.fx ? warn : "bg-app-warm" },
    { key: "a", op: "=", label: L("After Turkey", "بعد تركيا", "Après Turquie"), value: fmt(x.after_turkey, 0), note: "MAD", cls: "bg-app-warm" },
    { key: "m", op: "+", label: air ? L("Air rate × kg", "كيلو الجوي × الوزن", "Tarif × kg") : L("Morocco costs", "مصاريف المغرب", "Frais Maroc"), value: fmt(x.morocco, 0), note: fmt(x.morocco_per_kg, 2) + " MAD/kg", ltrNote: true, cls: x.morocco ? "bg-app-warm" : warn },
    { key: "f", op: "=", label: L("Final cost", "التكلفة النهائية", "Coût final"), value: fmt(x.total, 0), note: L("booked", "المتسجل", "comptabilisé") + " " + fmt(x.booked, 0) + " · " + (x.diff > 0 ? "+" : "") + fmt(x.diff, 0), cls: "bg-[#e7f4f1]" },
  ];
});
const issueList = computed(() => {
  const i = calc.value.issues || {}, out = [];
  if (i.no_weight) out.push(i.no_weight + " " + L("items without weight", "صنف من غير وزن", "articles sans poids"));
  if (i.no_price) out.push(i.no_price + " " + L("items without a price", "صنف من غير سعر", "articles sans prix"));
  if (i.price_from_receipt) out.push(i.price_from_receipt + " " + L("priced from the receipt", "سعرهم من الاستلام", "prix de la réception"));
  if (i.fx_missing) out.push(L("exchange rate missing", "سعر الصرف ناقص", "taux manquant"));
  if (i.no_morocco_costs) out.push(L("no Morocco costs linked", "مفيش مصاريف مغرب مربوطة", "aucun frais Maroc"));
  return out;
});

function chargesOf(side) { return (ed.value.charges || []).filter((c) => c.side === side); }
function sideTotal(side) { return chargesOf(side).reduce((a, c) => a + (Number(c.amount) || 0), 0); }
function freeCands(side) {
  const used = new Set((ed.value.charges || []).map((c) => c.invoice_item).filter(Boolean));
  return (cands.value[side].rows || []).filter((b) => !used.has(b.line));
}
function eqLine(it) {
  const fx = calc.value.fx;
  const p = it.currency === "MAD" ? fmt(it.price, 2) : `${fmt(it.price, 2)} ${CCY[it.currency] || it.currency} × ${it.currency === "TRY" ? fx : "rate"}`;
  return `${p} = ${fmt(it.price_mad, 2)}  +  Turkey ${fmt(it.tr_unit, 2)}  +  ${fmt(it.weight, 3)} kg × ${fmt(calc.value.totals.morocco_per_kg, 2)} = ${fmt(it.ma_unit, 2)}   →   ${fmt(it.final, 2)} MAD`;
}

let k = 0;
const keyed = (c) => Object.assign({ _k: ++k }, c);
function payload() {
  const e = ed.value;
  return {
    name: e.name, receipts: e.receipts, mode: e.mode, fx_rate: e.fx_rate ? Number(e.fx_rate) : null,
    customs_declaration: e.customs_declaration, bill_of_lading: e.bill_of_lading, tr_basis: e.tr_basis,
    charges: (e.charges || []).map(({ _k, ...c }) => c),
  };
}

async function loadOverview() {
  ovLoad.value = true; loadErr.value = "";
  try { ov.value = await api.call(M + "shipments_overview", { company: currentCompany() }, { fresh: true }) || {}; }
  catch (e) { ov.value = {}; loadErr.value = L("Load failed", "التحميل فشل", "Échec du chargement") + ": " + String(e?.message || e).slice(0, 160); }
  finally { ovLoad.value = false; }
}
function take(r) {
  det.value = r;
  ed.value = Object.assign({}, r.shipment, { fx_rate: r.shipment.fx_rate || "", charges: (r.shipment.charges || []).map(keyed) });
  calc.value = r.calc || {};
  history.value = r.history || [];
  dirty.value = false; actErr.value = "";
  cands.value = { Morocco: { open: false, loading: false, rows: [] }, Turkey: { open: false, loading: false, rows: [] } };
  mergeOpen.value = false;
}
async function open(key) {
  if (dirty.value && !window.confirm(L("Discard unsaved changes?", "تسيب التعديلات من غير حفظ؟", "Abandonner les modifications ?"))) return;
  selKey.value = key; detLoad.value = true;
  try { take(await api.call(M + "get_shipment", { company: currentCompany(), key }, { fresh: true })); }
  catch (e) { det.value = null; loadErr.value = String(e?.message || e).slice(0, 200); }
  finally { detLoad.value = false; }
}

let timer = null, seq = 0;
function touch() { dirty.value = true; recalc(); }
function recalc() {
  clearTimeout(timer);
  timer = setTimeout(async () => {
    const my = ++seq;
    try {
      const c = await api.call(M + "preview", { company: currentCompany(), shipment: JSON.stringify(payload()) }, { fresh: true });
      if (my === seq) calc.value = c || {};
    } catch { /* keep the last good figures */ }
  }, 350);
}

async function toggleCands(side) {
  const c = cands.value[side];
  c.open = !c.open;
  if (!c.open || c.rows.length) return;
  c.loading = true;
  try { c.rows = await api.call(M + "charge_candidates", { company: currentCompany(), shipment: JSON.stringify(payload()), side }, { fresh: true }) || []; }
  catch { c.rows = []; }
  finally { c.loading = false; }
}
function link(side, b) {
  ed.value.charges.push(keyed({ side, invoice_item: b.line, purchase_invoice: b.bill, description: `${b.supplier} · ${b.what}`, full_amount: b.full, amount: b.left }));
  touch();
}
function unlink(c) { ed.value.charges = ed.value.charges.filter((x) => x._k !== c._k); touch(); }
function addManual(side) {
  const m = manual.value[side];
  ed.value.charges.push(keyed({ side, invoice_item: null, purchase_invoice: null, description: m.desc || L("Manual", "يدوي", "Manuel"), full_amount: 0, amount: Number(m.amount) }));
  manual.value[side] = { amount: "", desc: "" };
  touch();
}
async function toggleMerge() {
  mergeOpen.value = !mergeOpen.value;
  if (!mergeOpen.value) return;
  try { mergeCands.value = await api.call(M + "merge_candidates", { company: currentCompany(), shipment: JSON.stringify(payload()) }, { fresh: true }) || []; }
  catch { mergeCands.value = []; }
}
function addReceipt(name) { ed.value.receipts = ed.value.receipts.concat([name]); mergeOpen.value = false; touch(); }
function removeReceipt(name) { ed.value.receipts = ed.value.receipts.filter((r) => r !== name); touch(); }

async function save() {
  saving.value = true; actErr.value = "";
  try {
    take(await api.call(M + "save_shipment", { company: currentCompany(), shipment: JSON.stringify(payload()) }));
    selKey.value = det.value.shipment.name;
    toast.success(L("Saved", "اتحفظت", "Enregistré"));
    loadOverview();
  } catch (e) { if (!e?.explained) actErr.value = String(e?.message || e).slice(0, 240); }
  finally { saving.value = false; }
}
async function setStatus(s) {
  actErr.value = "";
  try {
    take(await api.call(M + "set_status", { company: currentCompany(), name: ed.value.name, status: s }));
    loadOverview();
  } catch (e) { if (!e?.explained) actErr.value = String(e?.message || e).slice(0, 240); }
}
async function saveWeight(it, v) {
  const w = Number(v);
  if (!(w > 0) || w === Number(it.weight)) return;
  try {
    await api.call(M + "set_item_weight", { company: currentCompany(), item_code: it.item_code, weight: w, shipment: ed.value.name || undefined });
    toast.success(L("Weight saved", "الوزن اتحفظ", "Poids enregistré"));
    recalc();
  } catch (e) { if (!e?.explained) toast.error(String(e?.message || e).slice(0, 160)); }
}
async function toggleFx() {
  fxOpen.value = !fxOpen.value;
  if (fxOpen.value && !fxRows.value.length) {
    try { fxRows.value = await api.call(M + "fx_table", { company: currentCompany() }, { fresh: true }) || []; } catch { fxRows.value = []; }
  }
}
async function saveFx(month, v) {
  try {
    fxRows.value = await api.call(M + "set_fx", { company: currentCompany(), month, rate: v ? Number(v) : 0 }) || fxRows.value;
    toast.success(L("Rate saved", "السعر اتحفظ", "Taux enregistré"));
    if (det.value) recalc();
  } catch (e) { if (!e?.explained) toast.error(String(e?.message || e).slice(0, 160)); }
}

onMounted(loadOverview);
watch(entityId, () => { det.value = null; selKey.value = ""; loadOverview(); });
</script>
