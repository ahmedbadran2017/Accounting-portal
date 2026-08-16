<template>
  <!-- B4 v3: ACTUAL cost per shipment, bill by bill. Every freight bill gets
       allocated to the shipment(s) it covers (kg split); the reconciliation
       counter (unallocated = 0) is the freeze gate. Shared between the Cost
       Control Tower (step ②) and the Landed Cockpit. -->
  <div v-if="sr" class="bg-white rounded-card border shadow-card overflow-hidden" :style="sr.frozen ? 'border-color:#a7f3d0' : 'border-color:#c7d2fe'">
    <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2 flex-wrap cursor-pointer" @click="open = !open">
      <span class="text-[13px] font-bold">{{ L("Landed basis","أساس التكلفة المحمَّلة","Base landed") }} {{ sr.year }}</span>
      <span v-if="sr.frozen" class="text-[10.5px] font-bold px-2 py-0.5 rounded-full" style="background:#ecfdf5;color:#047857">❄ {{ L("FROZEN","مجمّد","GELÉ") }}</span>
      <span v-else class="text-[10.5px] font-bold px-2 py-0.5 rounded-full" style="background:#eef2ff;color:#4338ca">{{ L("pending review","في انتظار المراجعة","à revoir") }}</span>
      <span v-if="sr.frozen && sr.recon.post_freeze_receipts" class="text-[10.5px] font-bold px-2 py-0.5 rounded-full" style="background:#fffbeb;color:#b45309"
            :title="L('Shipments received after the freeze carry no landed cost — unfreeze, allocate their bills, re-freeze.','شحنات وصلت بعد التجميد من غير تكلفة شحن — فكّوا التجميد ووزّعوا فواتيرها وجمّدوا تاني.','Expéditions reçues après le gel.')">
        ⚠ {{ sr.recon.post_freeze_receipts }} {{ L("new shipments since freeze","شحنات جديدة بعد التجميد","depuis le gel") }}</span>
      <span class="text-[11px] text-ink-muted flex-1">
        {{ L("bills","فواتير","factures") }} {{ fmt0(sr.recon.bills_total) }} ·
        {{ L("allocated","موزَّع","alloué") }} {{ fmt0(sr.recon.allocated) }} ·
        <b :style="sr.recon.unallocated_count ? 'color:#b45309' : 'color:#047857'">{{ L("unallocated","غير موزَّع","non alloué") }} {{ fmt0(sr.recon.unallocated) }} ({{ sr.recon.unallocated_count }})</b>
      </span>
      <span class="text-ink-3">{{ open ? "▾" : "▸" }}</span>
    </div>

    <div v-if="open" class="p-4 space-y-3.5">
      <!-- Reconciliation counter -->
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <div class="border border-line rounded-[10px] px-3 py-2"><div class="text-[10px] text-ink-muted">{{ L("Freight bills (entered)","فواتير الشحن (المُدخلة)","Factures fret") }}</div><div class="text-[14px] font-bold tnum">{{ fmt0(sr.recon.bills_total) }}</div><div class="text-[10px] text-ink-3">{{ sr.bills.length }} {{ L("bills","فاتورة","factures") }}</div></div>
        <div class="border border-line rounded-[10px] px-3 py-2"><div class="text-[10px] text-ink-muted">{{ L("Allocated to shipments","موزَّع على الشحنات","Alloué") }}</div><div class="text-[14px] font-bold tnum" style="color:#047857">{{ fmt0(sr.recon.allocated) }}</div></div>
        <div class="border rounded-[10px] px-3 py-2" :style="sr.recon.unallocated_count ? 'border-color:#fde68a;background:#fffbeb' : 'border-color:#a7f3d0;background:#ecfdf5'"><div class="text-[10px] text-ink-muted">{{ L("Unallocated","غير موزَّع","Non alloué") }}</div><div class="text-[14px] font-bold tnum" :style="sr.recon.unallocated_count ? 'color:#b45309' : 'color:#047857'">{{ fmt0(sr.recon.unallocated) }}</div><div class="text-[10px] text-ink-3">{{ sr.recon.unallocated_count }} {{ L("bills","فاتورة","fact.") }} — {{ L("freeze gate","شرط التجميد","condition de gel") }}</div></div>
        <div class="border rounded-[10px] px-3 py-2" :style="sr.recon.uncosted_receipts ? 'border-color:#fde68a;background:#fffbeb' : 'border-color:#a7f3d0;background:#ecfdf5'"><div class="text-[10px] text-ink-muted">{{ L("Shipments w/o bills","شحنات بدون فواتير","Sans factures") }}</div><div class="text-[14px] font-bold tnum" :style="sr.recon.uncosted_receipts ? 'color:#b45309' : 'color:#047857'">{{ sr.recon.uncosted_receipts }}</div><div class="text-[10px] text-ink-3">{{ L("still on tariff estimate","لسه على التقدير","sur estimation") }}</div></div>
      </div>
      <div class="text-[11px] text-ink-muted -mt-1">
        {{ L("Workflow: enter ALL freight bills (Purchases → New bill, to the freight accounts below) → each bill appears here → allocate it to its shipment(s) → when unallocated = 0, freeze.",
             "الخطوات: دخّلوا كل فواتير الشحن الأول (المشتريات → فاتورة جديدة على حسابات الشحن اللي تحت) → كل فاتورة هتظهر هنا → وزّعوها على شحنتها/شحناتها → لما «غير موزَّع» يبقى صفر، جمّدوا.",
             "Saisir toutes les factures → les allouer → geler quand non alloué = 0.") }}
      </div>

      <!-- A) The freight bills + allocation -->
      <div>
        <div class="text-[11px] font-bold text-ink-2 mb-1.5">🧾 {{ L("Freight bills — allocate each to the shipment(s) it covers","فواتير الشحن — وزّعوا كل فاتورة على شحنتها/شحناتها","Factures fret — à allouer") }}</div>
        <div class="border border-line rounded-[8px] overflow-hidden max-h-[320px] overflow-y-auto">
          <table class="w-full text-[11.5px]">
            <thead><tr style="background:#fafaf9" class="sticky top-0 z-[1]">
              <th class="px-3 py-1.5 text-start text-[10px] font-bold text-ink-muted">{{ L("Bill","الفاتورة","Facture") }}</th>
              <th class="px-3 py-1.5 text-start text-[10px] font-bold text-ink-muted">{{ L("Supplier / account","المورّد / الحساب","Fourn.") }}</th>
              <th class="px-3 py-1.5 text-end text-[10px] font-bold text-ink-muted">{{ L("Amount","المبلغ","Montant") }}</th>
              <th class="px-3 py-1.5 text-center text-[10px] font-bold text-ink-muted">{{ L("Covers","بتغطي","Couvre") }}</th>
              <th class="px-3 py-1.5 w-[70px]"></th>
            </tr></thead>
            <tbody>
              <template v-for="b in sortedBills" :key="b.voucher">
                <tr class="border-t border-line-hair" :style="b.excluded ? 'opacity:.45' : b.prs.length ? '' : 'background:#fffbeb'">
                  <td class="px-3 py-1.5 font-mono text-[10.5px] whitespace-nowrap" dir="ltr">{{ b.voucher }}<div class="text-[10px] text-ink-muted font-sans">{{ b.dt }}</div></td>
                  <td class="px-3 py-1.5"><div class="truncate max-w-[160px]">{{ b.supplier || "—" }}</div><div class="text-[10px] text-ink-muted truncate max-w-[160px]">{{ b.account }}</div></td>
                  <td class="px-3 py-1.5 text-end tnum font-semibold">{{ fmt0(b.amount) }}</td>
                  <td class="px-3 py-1.5 text-center">
                    <span v-if="b.excluded" class="text-[10px] font-bold px-1.5 py-0.5 rounded-full" style="background:#f5f5f4;color:#78716c">{{ L("not freight","مش شحن","hors fret") }}</span>
                    <span v-else-if="b.prs.length" class="text-[10px] font-bold px-1.5 py-0.5 rounded-full" style="background:#ecfdf5;color:#047857">{{ b.prs.length }} {{ L("shipment(s)","شحنة","exp.") }}</span>
                    <span v-else class="text-[10px] font-bold px-1.5 py-0.5 rounded-full" style="background:#fffbeb;color:#b45309">{{ L("unallocated","غير موزعة","non allouée") }}</span>
                  </td>
                  <td class="px-3 py-1.5 text-end whitespace-nowrap">
                    <button v-if="canWrite && !sr.frozen && !b.excluded" class="text-[10.5px] font-bold px-2 py-1 rounded-[6px] border border-line text-ink-2 hover:bg-app-warm"
                            @click="toggleAlloc(b)">{{ allocFor === b.voucher ? L("close","إغلاق","fermer") : L("Allocate","توزيع","Allouer") }}</button>
                    <button v-if="canWrite && !sr.frozen" class="text-[10.5px] px-1.5 py-1 rounded-[6px] border border-line text-ink-3 hover:bg-app-warm ms-1"
                            :title="b.excluded ? L('Restore — it IS a freight bill','رجّعها — دي فاتورة شحن','Restaurer') : L('Exclude — not a freight bill','استبعدها — مش فاتورة شحن','Exclure')"
                            @click="toggleExclude(b)">{{ b.excluded ? "↺" : "✕" }}</button>
                  </td>
                </tr>
                <tr v-if="allocFor === b.voucher" class="border-t border-line-hair" style="background:#fafaf9">
                  <td colspan="5" class="px-3 py-2.5">
                    <div class="flex items-center gap-2 mb-1.5">
                      <span class="text-[10.5px] text-ink-muted flex-1">{{ L("Tick the shipment(s) this bill covers — the amount splits across them by kg:","علّموا على الشحنة/الشحنات اللي الفاتورة دي بتغطيها — المبلغ هيتقسم عليهم بالكيلو:","Cocher les expéditions couvertes :") }}</span>
                      <input v-model="allocSearch" :placeholder="L('search receipt/supplier…','بحث استلام/مورّد…','rechercher…')"
                             class="h-[24px] px-2 text-[10.5px] border border-line rounded-[6px] outline-none w-[170px]" />
                    </div>
                    <div class="max-h-[180px] overflow-y-auto border border-line rounded-[8px] bg-white">
                      <label v-for="r in allocReceipts" :key="r.name" class="flex items-center gap-2 px-3 py-1.5 border-b border-line-hair last:border-0 cursor-pointer hover:bg-app-warm text-[11px]">
                        <input type="checkbox" class="accent-accent w-3.5 h-3.5" :checked="allocSel.has(r.name)" @change="allocSel.has(r.name) ? allocSel.delete(r.name) : allocSel.add(r.name)" />
                        <span class="font-mono text-[10.5px]" dir="ltr">{{ r.name }}</span>
                        <span class="text-ink-muted">{{ r.dt }}</span>
                        <span>{{ r.channel === "air" ? "🛫" : "🚢" }}</span>
                        <span class="tnum text-ink-muted">{{ fmt0(r.kg) }}kg</span>
                        <span class="flex-1 truncate text-ink-3">{{ r.supplier }}</span>
                        <span v-if="allocSel.has(r.name) && allocKg > 0" class="tnum font-semibold" style="color:#047857">≈ {{ fmt0(b.amount * r.kg / allocKg) }}</span>
                      </label>
                    </div>
                    <div class="flex items-center gap-2 mt-2">
                      <span class="text-[10.5px] text-ink-muted flex-1">{{ allocSel.size }} {{ L("selected","مختارة","sél.") }} · {{ fmt0(allocKg) }}kg</span>
                      <button class="h-[26px] px-2.5 rounded-[7px] text-[10.5px] font-bold border border-line text-ink-2 hover:bg-app-warm" :disabled="busy" @click="saveAlloc(b, true)">{{ L("Clear","مسح","Vider") }}</button>
                      <button class="h-[26px] px-3 rounded-[7px] text-[10.5px] font-bold text-white bg-brand hover:bg-brand-dark disabled:opacity-50" :disabled="busy || !allocSel.size" @click="saveAlloc(b)">{{ L("Save allocation","حفظ التوزيع","Enregistrer") }}</button>
                    </div>
                  </td>
                </tr>
              </template>
              <tr v-if="!sr.bills.length"><td colspan="5" class="px-3 py-3 text-center text-[11px] text-ink-muted">{{ L("No freight bills on the included accounts yet — enter them from Purchases → New bill.","لسه مفيش فواتير شحن على الحسابات المفعّلة — دخّلوها من المشتريات → فاتورة جديدة.","Aucune facture.") }}</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- B) Shipments with their ACTUAL cost -->
      <div>
        <div class="flex items-center gap-2 mb-1.5 flex-wrap">
          <span class="text-[11px] font-bold text-ink-2">📦 {{ L("Shipments — each Purchase Receipt = one shipment with its own freight cost","الشحنات — كل استلام = شحنة بتكلفة شحنها الفعلية","Expéditions") }} ({{ shownReceipts.length }}/{{ sr.receipts.length }})</span>
          <button class="text-[10px] font-bold px-2 py-0.5 rounded-full border"
                  :style="onlyUnbilled ? 'background:#fffbeb;color:#b45309;border-color:#fde68a' : 'border-color:#e7e5e4;color:#78716c'"
                  @click="onlyUnbilled = !onlyUnbilled">{{ L("missing bills only","بدون فواتير فقط","sans factures") }} ({{ sr.recon.uncosted_receipts }})</button>
          <span class="text-[10px] text-ink-3 flex-1 text-end">
            <b style="color:#047857">{{ L("actual","فعلي","réel") }}</b> = {{ L("from allocated bills","من الفواتير الموزَّعة","factures allouées") }} ·
            <b style="color:#b45309">{{ L("est.","تقديري","est.") }}</b> = {{ L("tariff × kg until its bills arrive","تعريفة × كجم لحد ما فواتيرها تتدخل","tarif × kg") }} ·
            <b style="color:#b91c1c">{{ L("none","بدون","aucun") }}</b> = {{ L("no bills, no tariff","لا فواتير ولا تعريفة","rien") }}
          </span>
        </div>
        <div class="border border-line rounded-[8px] overflow-hidden max-h-[300px] overflow-y-auto">
          <table class="w-full text-[11.5px]">
            <thead><tr style="background:#fafaf9" class="sticky top-0 z-[1]">
              <th class="px-3 py-1.5 text-start text-[10px] font-bold text-ink-muted">{{ L("Receipt","الاستلام","Réception") }}</th>
              <th class="px-3 py-1.5 text-start text-[10px] font-bold text-ink-muted">{{ L("Supplier","المورّد","Fourn.") }}</th>
              <th class="px-3 py-1.5 text-end text-[10px] font-bold text-ink-muted">kg</th>
              <th class="px-3 py-1.5 text-center text-[10px] font-bold text-ink-muted">{{ L("Channel","القناة","Canal") }}</th>
              <th class="px-3 py-1.5 text-start text-[10px] font-bold text-ink-muted">{{ L("Bills","الفواتير","Factures") }}</th>
              <th class="px-3 py-1.5 text-end text-[10px] font-bold text-ink-muted">{{ L("Freight cost","تكلفة الشحن","Coût fret") }}</th>
            </tr></thead>
            <tbody>
              <tr v-for="r in shownReceipts" :key="r.name" class="border-t border-line-hair">
                <td class="px-3 py-1.5 font-mono text-[10.5px] whitespace-nowrap" dir="ltr">{{ r.name }}<div class="text-[10px] text-ink-muted font-sans">{{ r.dt }}</div></td>
                <td class="px-3 py-1.5 truncate max-w-[120px]">{{ r.supplier }}</td>
                <td class="px-3 py-1.5 text-end tnum">{{ fmt0(r.kg) }}</td>
                <td class="px-3 py-1.5 text-center whitespace-nowrap">
                  <button class="text-[10.5px] font-bold px-2 py-0.5 rounded-s-full border"
                          :style="r.channel==='air' ? 'background:#eef2ff;color:#4338ca;border-color:#c7d2fe' : 'opacity:.45;border-color:#e7e5e4'"
                          :disabled="!canWrite || !!sr.frozen" @click="setChannel(r, 'air')">🛫</button>
                  <button class="text-[10.5px] font-bold px-2 py-0.5 rounded-e-full border"
                          :style="r.channel==='sea' ? 'background:#ecfeff;color:#0e7490;border-color:#a5f3fc' : 'opacity:.45;border-color:#e7e5e4'"
                          :disabled="!canWrite || !!sr.frozen" @click="setChannel(r, 'sea')">🚢</button>
                </td>
                <td class="px-3 py-1.5">
                  <span v-for="bb in r.bills" :key="bb.voucher" class="inline-block text-[9.5px] font-mono px-1.5 py-0.5 rounded-[5px] me-1 mb-0.5" dir="ltr" style="background:#f0fdf4;color:#166534" :title="`${bb.voucher} · ${fmt0(bb.share)}`">{{ bb.voucher.slice(-9) }}<template v-if="bb.n_prs > 1"> ÷{{ bb.n_prs }}</template></span>
                  <span v-if="!r.bills.length" class="text-[10px] text-ink-3">—</span>
                </td>
                <td class="px-3 py-1.5 text-end tnum font-semibold whitespace-nowrap">
                  {{ fmt0(r.landed) }}
                  <span v-if="r.source==='bills'" class="text-[9.5px] font-bold px-1 py-0.5 rounded-full ms-0.5" style="background:#ecfdf5;color:#047857">{{ L("actual","فعلي","réel") }}</span>
                  <span v-else-if="r.source==='est'" class="text-[9.5px] font-bold px-1 py-0.5 rounded-full ms-0.5" style="background:#fffbeb;color:#b45309" :title="`@${r.rate_kg}/kg`">{{ L("est.","تقديري","est.") }}</span>
                  <span v-else class="text-[9.5px] font-bold px-1 py-0.5 rounded-full ms-0.5" style="background:#fef2f2;color:#b91c1c">{{ L("none","بدون","aucun") }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- C) Air tariff (estimate + cross-check) -->
      <div>
        <div class="text-[11px] font-bold text-ink-2 mb-1.5">🛫 {{ L("Air tariff (MAD/kg, date bands) — estimate for unbilled shipments + cross-check","تعريفة الجوي (درهم/كجم بفترات) — تقدير للشحنات اللي لسه من غير فواتير + فحص تقاطعي","Tarif aérien (estimation + contrôle)") }}</div>
        <div class="flex items-center gap-2 flex-wrap">
          <span v-for="(r, i) in airRates" :key="i" class="inline-flex items-center gap-1.5 border border-line rounded-[8px] px-2 py-1 text-[11.5px] tnum">
            {{ L("from","من","dès") }} <input type="date" v-model="r.from" :disabled="!canWrite || !!sr.frozen" class="border-0 outline-none bg-transparent w-[120px]" @change="saveAirRates" />
            → <input type="number" step="1" v-model.number="r.rate" :disabled="!canWrite || !!sr.frozen" class="border-0 outline-none bg-transparent w-[52px] font-bold" @change="saveAirRates" /> /kg
            <button v-if="canWrite && !sr.frozen" class="text-sale text-[12px]" @click="airRates.splice(i,1); saveAirRates()">✕</button>
          </span>
          <button v-if="canWrite && !sr.frozen" class="h-[26px] px-2.5 rounded-[7px] text-[11px] font-bold border border-line text-ink-2 hover:bg-app-warm"
                  @click="airRates.push({ from: '', rate: null })">+ {{ L("band","فترة","période") }}</button>
        </div>
        <div class="text-[11px] mt-1.5" :style="crossOk ? 'color:#047857' : 'color:#b45309'">
          {{ L("Cross-check:","الفحص التقاطعي:","Contrôle :") }}
          Σ({{ L("air kg × tariff","كجم جوي × التعريفة","kg air × tarif") }}) = {{ fmt0(sr.crosscheck.air_tariff_cost) }}
          {{ L("vs air bills allocated","مقابل فواتير الجوي الموزعة","vs factures air") }} = {{ fmt0(sr.crosscheck.air_bills) }}
          <template v-if="!crossOk"> — {{ L("gap: enter the missing bills or fix the band dates","فيه فرق: كمّلوا إدخال الفواتير أو ظبطوا تواريخ الفترات","écart à résoudre") }}</template>
          <template v-else> ✓</template>
        </div>
      </div>

      <!-- D) Bill-source accounts -->
      <div>
        <div class="text-[11px] font-bold text-ink-2 mb-1.5">🗂 {{ L("Freight accounts (bill sources) — included accounts feed the bill list above","حسابات الشحن (مصادر الفواتير) — الحسابات المفعّلة بتغذي قايمة الفواتير فوق","Comptes fret (sources)") }}</div>
        <table class="w-full text-[11.5px] border border-line rounded-[8px] overflow-hidden">
          <tbody>
            <tr v-for="r in sr.pool_rows" :key="r.account" class="border-t border-line-hair first:border-0" :style="r.included ? '' : 'opacity:.55'">
              <td class="px-3 py-1.5 truncate max-w-[250px]">{{ r.account }}<span class="text-[10px] text-ink-muted"> · {{ r.entries }}</span></td>
              <td class="px-3 py-1.5 text-end tnum font-semibold">{{ fmt0(r.net) }}</td>
              <td class="px-3 py-1.5 text-center w-[90px]">
                <span class="text-[10px] font-bold px-1.5 py-0.5 rounded-full"
                      :style="r.suggested==='inbound' ? 'background:#ecfdf5;color:#047857' : r.suggested==='outbound' ? 'background:#fef2f2;color:#b91c1c' : 'background:#fffbeb;color:#b45309'">
                  {{ r.suggested==='inbound' ? L('inbound','وارد','entrant') : r.suggested==='outbound' ? L('outbound','صادر','sortant') : L('review','مراجعة','revue') }}
                </span>
              </td>
              <td class="px-3 py-1.5 text-center w-[46px]">
                <input type="checkbox" :checked="r.included" :disabled="!canWrite || !!sr.frozen"
                       class="accent-accent w-3.5 h-3.5 cursor-pointer" @change="togglePool(r)" />
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Freeze -->
      <div class="flex items-center gap-2 flex-wrap pt-1 border-t border-line-hair">
        <span class="text-[11px] text-ink-muted flex-1">
          {{ L("Freeze locks each shipment's ACTUAL cost. Blocked while any bill is unallocated; sea shipments must have real bills. Verify & Fix then adds each item's landed share on top of the product cost.",
               "التجميد يقفل التكلفة الفعلية لكل شحنة. متقفل طالما فيه فاتورة غير موزَّعة، والبحري لازم فواتير فعلية. بعدها شاشة التحقق تضيف نصيب كل صنف من شحنه فوق تكلفة المنتج.",
               "Geler fige le coût réel de chaque expédition.") }}
        </span>
        <button v-if="canFreeze && !sr.frozen" class="h-[30px] px-3.5 rounded-[8px] text-[11.5px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand disabled:opacity-50"
                :disabled="busy || !!sr.recon.unallocated_count"
                :title="sr.recon.unallocated_count ? L('Blocked: unallocated bills','متقفل: فيه فواتير غير موزَّعة','Bloqué : factures non allouées') : ''"
                @click="freezeBasis">❄ {{ L("Freeze basis","جمّد الأساس","Geler") }}</button>
        <button v-if="canFreeze && sr.frozen" class="h-[30px] px-3 rounded-[8px] text-[11.5px] font-bold border border-line text-ink-2 hover:bg-app-warm disabled:opacity-50"
                :disabled="busy" @click="unfreezeBasis">{{ L("Unfreeze","فكّ التجميد","Dégeler") }}</button>
        <span v-if="!canFreeze" class="text-[10px] text-ink-3">{{ L("Freezing is Super-Admin only","التجميد للسوبر أدمن فقط","Gel : Super-Admin uniquement") }}</span>
        <span v-if="sr.frozen" class="text-[10px] text-ink-3" dir="ltr">{{ sr.frozen.by }} · {{ sr.frozen.on }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, reactive } from "vue";
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
// freeze/unfreeze are Super-Admin-only on the backend — don't show an
// accountant a button that can only error
const canFreeze = computed(() => can("manage_users"));
const toast = useToast();

const LP = "accounting_portal.api.landed_prep";
const sr = ref(null);
const airRates = ref([]);
const open = ref(props.startOpen);
const busy = ref(false);
const allocFor = ref(null);
const allocSel = reactive(new Set());
const allocSearch = ref("");
const onlyUnbilled = ref(false);

const sortedBills = computed(() =>
  [...(sr.value?.bills || [])].sort((a, b) =>
    (a.excluded ? 2 : a.prs.length ? 1 : 0) - (b.excluded ? 2 : b.prs.length ? 1 : 0)));
const shownReceipts = computed(() => {
  const all = sr.value?.receipts || [];
  return onlyUnbilled.value ? all.filter((r) => r.source !== "bills") : all;
});
const allocReceipts = computed(() => {
  const q = allocSearch.value.trim().toLowerCase();
  const all = sr.value?.receipts || [];
  if (!q) return all;
  return all.filter((r) => (r.name + " " + (r.supplier || "")).toLowerCase().includes(q));
});
const allocKg = computed(() => {
  let t = 0;
  for (const r of sr.value?.receipts || []) if (allocSel.has(r.name)) t += Number(r.kg || 0);
  return t;
});
const crossOk = computed(() => {
  const c = sr.value?.crosscheck || {};
  const a = Number(c.air_tariff_cost || 0), b = Number(c.air_bills || 0);
  if (!a && !b) return true;
  return Math.abs(a - b) <= 0.15 * Math.max(a, b);
});

async function load() {
  try {
    const r = await api.call(`${LP}.shipment_review`, { company: currentCompany() }, { fresh: true });
    sr.value = r;
    // don't clobber a band the user is still typing (e.g. rate entered, date
    // pending) — only re-sync from the server when nothing is half-filled
    const editing = airRates.value.some((x) => !x.from || !(x.rate > 0));
    if (!editing) airRates.value = (r.air_rates || []).map((x) => ({ ...x }));
  } catch (e) { sr.value = null; }
}
load();

function toggleAlloc(b) {
  if (allocFor.value === b.voucher) { allocFor.value = null; return; }
  allocFor.value = b.voucher;
  allocSearch.value = "";
  allocSel.clear();
  for (const p of b.prs || []) allocSel.add(p);
}

async function toggleExclude(b) {
  try {
    await api.call(`${LP}.exclude_bill`, { company: currentCompany(), voucher: b.voucher, excluded: b.excluded ? 0 : 1 });
    if (allocFor.value === b.voucher) allocFor.value = null;
    await load(); emit("changed");
  } catch (e) { toast.error(e.message || "Failed"); }
}

async function saveAlloc(b, clear = false) {
  busy.value = true;
  try {
    const prs = clear ? [] : [...allocSel];
    await api.call(`${LP}.allocate_bill`, { company: currentCompany(), voucher: b.voucher, prs: JSON.stringify(prs) });
    allocFor.value = null;
    await load(); emit("changed");
  } catch (e) { toast.error(e.message || "Failed"); }
  finally { busy.value = false; }
}

let t = null;
function saveAirRates() {
  clearTimeout(t);
  t = setTimeout(async () => {
    try {
      const clean = airRates.value.filter((r) => r.from && r.rate > 0);
      await api.call(`${LP}.set_air_rates`, { rates: JSON.stringify(clean) });
      // incomplete rows stay local (load() keeps them while editing)
      await load(); emit("changed");
    } catch (e) { toast.error(e.message || "Failed"); await load(); }
  }, 400);
}

async function togglePool(r) {
  try {
    await api.call(`${LP}.set_pool_include`, { company: currentCompany(), account: r.account, included: r.included ? 0 : 1 });
    await load(); emit("changed");
  } catch (e) { toast.error(e.message || "Failed"); await load(); }
}

async function setChannel(r, ch) {
  if (r.channel === ch) return;
  try {
    await api.call(`${LP}.set_pr_channel`, { company: currentCompany(), pr: r.name, channel: ch });
    await load(); emit("changed");
  } catch (e) { toast.error(e.message || "Failed"); await load(); }
}

async function freezeBasis() {
  if (!window.confirm(L(
    "Freeze the landed basis? Each shipment's ACTUAL cost gets locked and Verify & Fix starts applying full costs.",
    "تجميد الأساس؟ التكلفة الفعلية لكل شحنة هتتقفل وشاشة التحقق هتبدأ تطبّق التكلفة الكاملة.",
    "Geler la base ?"))) return;
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
