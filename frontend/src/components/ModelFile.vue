<template>
  <div class="space-y-4">
    <div v-if="loading" class="py-12 text-center text-[12px] text-ink-muted">{{ L("Loading model…","بيحمّل الموديل…","Chargement…") }}</div>
    <div v-else-if="err" class="py-12 text-center text-[12px] text-sale">{{ err }} <button class="underline" @click="load">{{ L("Retry","إعادة","Réessayer") }}</button></div>

    <template v-else-if="d">
      <!-- model header -->
      <div class="bg-white border border-line rounded-[14px] shadow-card px-5 py-4 flex items-center gap-4 flex-wrap">
        <div class="min-w-0 flex-1">
          <div class="text-[15px] font-bold truncate">{{ modelName }}</div>
          <div class="text-[11px] text-ink-muted mt-0.5">
            {{ d.model.n_stocked }} {{ L("variant(s) in stock","variant في المخزون","variantes en stock") }}
            · {{ L("one price for the whole model","سعر واحد للموديل كله","un prix pour le modèle") }}
          </div>
        </div>
        <div class="text-end">
          <div class="text-[10.5px] text-ink-muted font-semibold">{{ L("Suggested (family evidence)","المقترح (دليل العائلة)","Suggéré") }}</div>
          <div class="text-[18px] font-bold tnum" :class="d.model.suggested ? 'text-emerald-700' : 'text-amber-600'">
            {{ d.model.suggested != null ? fmtNum(d.model.suggested, 2) : L("no source","بلا مصدر","—") }}
          </div>
          <div v-if="d.model.basis_qty" class="text-[10px] text-ink-3 tnum">{{ L("basis","أساس","base") }} {{ d.model.basis_qty }}u</div>
        </div>
      </div>

      <!-- ① pooled evidence + one verified cost -->
      <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
        <div class="px-4 py-3 border-b border-line-hair"><span class="text-[13px] font-bold">① {{ L("Product cost — one verification for the family","تكلفة المنتج — تحقق واحد للعيلة كلها","① Coût produit") }}</span></div>
        <div class="p-4 space-y-3">
          <table v-if="d.evidence.length" class="w-full text-[11.5px]">
            <thead><tr style="background:#fafaf9">
              <th class="px-3 py-1.5 text-start text-[10px] font-bold text-ink-muted">{{ L("Document","المستند","Document") }}</th>
              <th class="px-3 py-1.5 text-start text-[10px] font-bold text-ink-muted">{{ L("Supplier","المورّد","Fournisseur") }}</th>
              <th class="px-3 py-1.5 text-end text-[10px] font-bold text-ink-muted">{{ L("Qty","كمية","Qté") }}</th>
              <th class="px-3 py-1.5 text-end text-[10px] font-bold text-ink-muted">{{ L("Rate","السعر","Taux") }}</th>
              <th class="px-3 py-1.5 text-end text-[10px] font-bold text-ink-muted">→ MAD</th>
            </tr></thead>
            <tbody>
              <tr v-for="e in d.evidence" :key="e.doc + (e.via || '')" class="border-t border-line-hair">
                <td class="px-3 py-1.5 font-mono text-[10.5px]" dir="ltr">{{ e.doc }}<span class="text-ink-muted font-sans"> · {{ e.dt }}</span><span v-if="e.via" class="font-sans text-[10px] text-violet-700"> 👪 {{ e.via }}</span></td>
                <td class="px-3 py-1.5 truncate max-w-[150px]">{{ e.supplier }}</td>
                <td class="px-3 py-1.5 text-end tnum">{{ fmtNum(e.qty) }}</td>
                <td class="px-3 py-1.5 text-end tnum">{{ fmtNum(e.rate, 2) }} {{ e.cur }}</td>
                <td class="px-3 py-1.5 text-end tnum font-bold" :class="e.rate_mad >= 0.5 ? 'text-emerald-700' : 'text-sale'">{{ fmtNum(e.rate_mad, 2) }}</td>
              </tr>
            </tbody>
          </table>
          <div v-else class="text-[11px] text-amber-700">{{ L("No purchase documents anywhere in the family — enter the cost manually (note required).","مفيش مستندات في العيلة كلها — أدخلوا التكلفة يدويًا (الملاحظة إجبارية).","Aucun document — saisir manuellement.") }}</div>
          <div class="flex items-center gap-2 flex-wrap pt-1 border-t border-line-hair">
            <label class="text-[11.5px] text-ink-2 font-semibold">{{ L("Verified cost (MAD/unit)","التكلفة المعتمدة (درهم/وحدة)","Coût vérifié") }}</label>
            <input v-model.number="rate" type="number" step="0.01" min="0" class="h-[30px] w-[110px] text-[12px] text-end px-2 rounded-[8px] border border-line tnum" dir="ltr" />
            <input v-model="note" :placeholder="L('Note (required if you change the figure)','ملاحظة (إجبارية لو غيرتوا الرقم)','Note')"
                   class="h-[30px] flex-1 min-w-[220px] text-[12px] px-2.5 rounded-[8px] border"
                   :class="noteNeeded ? 'border-amber-400' : 'border-line'" />
            <span v-if="savedCost && rate === savedCost" class="text-[10.5px] font-bold text-emerald-700">✓ {{ L("saved","محفوظ","enregistré") }}</span>
            <span v-else-if="savedCost && rate !== savedCost" class="text-[10.5px] font-bold text-amber-600" :title="L('differs from the saved draft','مختلف عن المحفوظ','différent')">✎ {{ savedCost }}</span>
            <button v-if="canWrite" class="h-[30px] px-3.5 rounded-[9px] text-[11.5px] font-bold text-white bg-brand hover:bg-brand-dark disabled:opacity-40"
                    :disabled="!(rate >= 0.5) || savingCost || posting" @click="saveCost">{{ savingCost ? "…" : L("Save","حفظ","OK") }}</button>
          </div>
        </div>
      </div>

      <!-- ② freight — the family's shipments, same actions as the SKU page -->
      <div v-if="d.receipts && d.receipts.length" class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
        <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2">
          <span class="text-[13px] font-bold">② {{ L("Freight — the family's shipments","الشحن — شحنات العيلة","② Fret") }}</span>
          <span v-if="!d.waiting_prs.length" class="text-[10px] font-bold px-1.5 py-0.5 rounded-full" style="background:#ecfdf5;color:#047857">✓ {{ L("complete","مكتمل","complet") }}</span>
          <span v-else class="text-[10px] font-bold px-1.5 py-0.5 rounded-full" style="background:#fffbeb;color:#b45309">⏳ {{ d.waiting_prs.length }} {{ L("missing freight","ناقصها شحن","sans fret") }}</span>
        </div>
        <div class="overflow-x-auto max-h-[220px] overflow-y-auto">
          <table class="w-full text-[11.5px]">
            <thead><tr style="background:#fafaf9" class="sticky top-0">
              <th class="px-3 py-1.5 text-start text-[10px] font-bold text-ink-muted">{{ L("Shipment","الشحنة","Expédition") }}</th>
              <th class="px-3 py-1.5 text-center text-[10px] font-bold text-ink-muted">{{ L("Ch.","قناة","Can.") }}</th>
              <th class="px-3 py-1.5 text-end text-[10px] font-bold text-ink-muted">{{ L("PR qty","كمية","Qté") }}</th>
              <th class="px-3 py-1.5 text-start text-[10px] font-bold text-ink-muted">{{ L("Freight","الشحن","Fret") }}</th>
              <th class="px-3 py-1.5 text-start text-[10px] font-bold text-ink-muted">{{ L("Variants in it","الأصناف فيها","Variantes") }}</th>
            </tr></thead>
            <tbody>
              <tr v-for="r in d.receipts" :key="r.pr" class="border-t border-line-hair">
                <td class="px-3 py-1.5 font-mono text-[10.5px] whitespace-nowrap" dir="ltr">{{ r.pr }}<div class="text-[10px] text-ink-muted font-sans">{{ r.dt }}</div></td>
                <td class="px-3 py-1.5 text-center whitespace-nowrap">
                  <button v-if="canWrite && !d.frozen" class="text-[12px]"
                          :title="r.channel_confirmed ? L('confirmed — click to flip','مؤكدة — دوس للقلب','confirmé') : L('SUGGESTED — click to flip','اقتراح — دوس للقلب','suggestion')"
                          @click="flipChannel(r)">{{ r.channel === "air" ? "🛫" : "🚢" }}<span v-if="!r.channel_confirmed" class="text-[10px] text-amber-600 font-bold">?</span></button>
                  <button v-if="canWrite && !d.frozen && !r.channel_confirmed" class="ms-0.5 text-[10px] font-bold text-emerald-700 hover:underline"
                          :title="L('confirm as-is','تأكيد زي ما هي','confirmer')" @click="confirmChannel(r)">✓</button>
                  <template v-if="!canWrite || d.frozen">{{ r.channel === "air" ? "🛫" : "🚢" }}<span v-if="!r.channel_confirmed" class="text-[10px] text-amber-600 font-bold">?</span></template>
                </td>
                <td class="px-3 py-1.5 text-end tnum">{{ fmtNum(r.pr_qty) }}</td>
                <td class="px-3 py-1.5 whitespace-nowrap">
                  <template v-if="['bills','rate'].includes(r.source)">
                    <span class="text-[10px] font-bold px-1.5 py-0.5 rounded-full" style="background:#ecfdf5;color:#047857">{{ r.source === 'bills' ? L("bills","فواتير","factures") : L("rate ✓","سعر ✓","taux ✓") }}</span>
                    <span class="text-[10px] text-ink-muted" dir="ltr"> @{{ r.rate_kg }}/kg</span>
                  </template>
                  <template v-else-if="r.channel === 'air' && (r.channel_confirmed || r.pr_qty < 500) && canWrite && !d.frozen">
                    <input type="number" step="1" min="0" v-model.number="r._draft" :placeholder="String(r.band_rate || '')"
                           class="w-[58px] h-[24px] px-1.5 text-end tnum text-[11px] border border-amber-300 rounded-[6px] outline-none" />
                    <button class="ms-1 h-[24px] px-2 rounded-[6px] text-[10px] font-bold text-white bg-brand hover:bg-brand-dark disabled:opacity-50"
                            :disabled="!((r._draft ?? r.band_rate) > 0) || fBusy" @click="confirmRate(r)">✓ {{ L("rate","السعر","taux") }}</button>
                  </template>
                  <template v-else>
                    <span class="text-[10px] font-bold px-1.5 py-0.5 rounded-full" style="background:#fef2f2;color:#b91c1c">{{ L("none","لا يوجد","aucun") }}</span>
                    <span class="text-[10px] text-ink-muted ms-1">{{ L("attach its bills in Shipments","ارفقوا فواتيرها في الشحنات","joindre dans Expéditions") }}</span>
                  </template>
                </td>
                <td class="px-3 py-1.5 text-[10px] text-ink-muted truncate max-w-[180px]">{{ r.members.join("، ") }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 🏠 truly LOCAL (cost source = local supplier invoice) — no freight by nature -->
      <div v-if="d.receipts && !d.receipts.length && d.model.source === 'local_pi'" class="rounded-[12px] border px-4 py-2.5 flex items-center gap-2" style="background:#fff7ed;border-color:#fed7aa">
        <span class="text-[13px]">🏠</span>
        <span class="text-[11.5px]" style="color:#c2410c">{{ L("Local / domestic product — no freight layer by nature: the supplier invoice IS the full cost. Weight is irrelevant here.","منتج محلي — مفيش طبقة شحن بطبيعته: فاتورة المورد هي التكلفة الكاملة، والوزن مش مطلوب هنا.","Produit local — pas de fret : la facture fournisseur est le coût complet.") }}</span>
      </div>
      <!-- 🚢❓ IMPORTED but NO import receipts on record — manual landed calculator -->
      <div v-else-if="d.receipts && !d.receipts.length" class="rounded-[12px] border px-4 py-2.5 space-y-2" style="background:#fffbeb;border-color:#fde68a">
        <div class="flex items-center gap-2">
          <span class="text-[13px]">🚢❓</span>
          <span class="text-[11.5px]" style="color:#b45309">{{ L("IMPORTED but NO import receipts on record — stock arrived via manual entries, so freight can't distribute automatically. Estimate it here: real weight × the era's contract tariff, and it folds into the verified cost with an audit note.","مستورد لكن مفيش استلامات استيراد مسجلة — دخل باستلامات يدوية فالشحن مش بيتوزع تلقائيًا. قدّره هنا: الوزن الحقيقي × تعريفة العقد لفترته، وهيتجمع على التكلفة المعتمدة بملاحظة توثيق.","Importé sans réceptions — estimer le fret ici.") }}</span>
        </div>
        <div v-if="canWrite" class="flex items-center gap-2 flex-wrap">
          <span class="text-[11px] font-bold">{{ L("Freight estimate:","تقدير الشحن:","Fret :") }}</span>
          <input v-model.number="mlW" type="number" step="0.01" min="0.01" max="50" placeholder="kg"
                 class="h-[26px] w-[70px] text-[11.5px] text-end px-1.5 rounded-[7px] border border-line tnum" dir="ltr"
                 :title="L('REAL unit weight incl. packaging — weigh it, don\'t guess','الوزن الحقيقي للوحدة بالتغليف — اتوزن متتخمنش','poids réel')" />
          <span class="text-[11px]">×</span>
          <input v-model.number="mlRate" type="number" step="0.1" min="0.1"
                 class="h-[26px] w-[74px] text-[11.5px] text-end px-1.5 rounded-[7px] border border-line tnum" dir="ltr"
                 :title="L('MAD per kg — type ANY rate; the chips are just the known contract tariffs','درهم/كجم — اكتب أي رقم؛ الأزرار مجرد التعريفات المعروفة','MAD/kg — libre')" />
          <span class="text-[10px] text-ink-muted">{{ L("/kg","درهم/كجم","/kg") }}</span>
          <span class="inline-flex gap-1">
            <button v-for="c in [[100,'جوي 25'],[110,'جوي 26'],[126,'جوي الآن'],[23.6,'بحري']]" :key="c[0]"
                    class="h-[22px] px-1.5 rounded-[6px] text-[10px] font-bold border"
                    :class="mlRate === c[0] ? 'text-white bg-brand border-brand' : 'text-ink-3 border-line hover:bg-white'"
                    @click="mlRate = c[0]">{{ c[0] }} {{ locale === 'ar' ? c[1] : '' }}</button>
          </span>
          <span v-if="mlEst > 0" class="text-[11.5px] tnum font-bold" dir="ltr">= {{ mlEst.toFixed(2) }}</span>
          <span v-if="mlEst > 0" class="text-[11px] text-ink-muted tnum" dir="ltr">→ {{ L("full","الشامل","total") }} {{ ((rate || d.model.suggested || 0) + mlEst).toFixed(2) }}</span>
          <button v-if="mlEst > 0" class="h-[26px] px-2.5 rounded-[7px] text-[10.5px] font-bold text-white bg-brand hover:bg-brand-dark"
                  @click="applyManualLanded">{{ L("Fold into the cost","اجمعها على التكلفة","Ajouter au coût") }}</button>
        </div>
      </div>

      <!-- ⚖️ family weight — only meaningful for IMPORTED models -->
      <div v-if="canWrite && suspectWeights.length && d.receipts && d.receipts.length" class="rounded-[12px] border px-4 py-2.5 flex items-center gap-2 flex-wrap" style="background:#fffbeb;border-color:#fde68a">
        <span class="text-[11.5px] font-bold">⚖️ {{ L("Family weight","وزن العيلة","Poids famille") }}</span>
        <span class="text-[10.5px]" style="color:#b45309">{{ suspectWeights.length }} {{ L("variant(s) with suspect weight — freight shares are unfair until fixed","variant وزنهم مشكوك — نصيب الشحن مش عادل لحد ما يتظبطوا","poids suspects") }}</span>
        <div class="flex-1"></div>
        <input v-model.number="famWeight" type="number" step="0.01" min="0.005" max="50" placeholder="kg"
               class="h-[26px] w-[76px] text-[11.5px] text-end px-1.5 rounded-[7px] border border-line tnum" dir="ltr" />
        <button class="h-[26px] px-2.5 rounded-[7px] text-[10.5px] font-bold text-white bg-brand hover:bg-brand-dark disabled:opacity-40"
                :disabled="!(famWeight > 0) || fBusy" @click="applyFamilyWeight">{{ L("Fill the suspects","املأ الناقصين","Remplir") }}</button>
      </div>

      <!-- ③ variants -->
      <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
        <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2">
          <span class="text-[13px] font-bold">③ {{ L("Variants — what one Submit will do","الـvariants — اللي الاعتماد الواحد هيعمله","③ Variantes") }}</span>
          <span v-if="d.waiting_prs.length" class="text-[10.5px] font-bold px-2 py-0.5 rounded-full" style="background:#fffbeb;color:#b45309">
            ⏳ {{ d.waiting_prs.length }} {{ L("shipment(s) missing freight","شحنة ناقصها شحن","expéditions sans fret") }}
          </span>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-[11.5px]">
            <thead><tr style="background:#fafaf9">
              <th class="px-3 py-2 text-center text-[10px] font-bold text-ink-muted">{{ L("Apply","تطبيق","OK") }}</th>
              <th class="px-4 py-2 text-start text-[10px] font-bold text-ink-muted">{{ L("Variant","الصنف","Variante") }}</th>
              <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("Qty","كمية","Qté") }}</th>
              <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("Book","الدفاتر","Livre") }}</th>
              <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">kg</th>
              <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("Landed","الشحن","Fret") }}</th>
              <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("New → Δ","الجديد → Δ","Nouveau") }}</th>
              <th class="px-3 py-2 text-center text-[10px] font-bold text-ink-muted">{{ L("Status","الحالة","Statut") }}</th>
              <th class="px-3 py-2 text-center text-[10px] font-bold text-ink-muted"></th>
            </tr></thead>
            <tbody>
              <tr v-for="v in d.variants" :key="v.item_code" class="border-t border-line-hair" :class="results[v.item_code] === 'ok' ? 'bg-emerald-50/40' : ''">
                <td class="px-3 py-1.5 text-center">
                  <input type="checkbox" :checked="!excluded.has(v.item_code) && !v.waiting.length" :disabled="v.fixed || v.batch_tracked || v.waiting.length > 0 || posting"
                         @change="toggleExclude(v.item_code)" />
                </td>
                <td class="px-4 py-1.5"><span class="font-semibold">{{ v.sku || v.item_code }}</span><span class="text-[10px] text-ink-muted"> · {{ v.item_name }}</span></td>
                <td class="px-3 py-1.5 text-end tnum">{{ fmtNum(v.qty) }}</td>
                <td class="px-3 py-1.5 text-end tnum">{{ fmtNum(v.book_rate, 2) }}</td>
                <td class="px-3 py-1.5 text-end tnum" :class="v.weight_suspect ? 'text-amber-600 font-bold' : 'text-ink-3'">{{ v.weight.toFixed(2) }}</td>
                <td class="px-3 py-1.5 text-end tnum text-ink-3">{{ v.landed_unit ? "+" + fmtNum(v.landed_unit, 2) : "—" }}</td>
                <td class="px-3 py-1.5 text-end tnum whitespace-nowrap" dir="ltr">
                  <template v-if="rate > 0 && !v.fixed">
                    <b>{{ fmtNum(rate + v.landed_unit, 2) }}</b>
                    <span class="text-[10px]" :style="{ color: (rate + v.landed_unit - v.book_rate) > 0 ? '#b45309' : '#047857' }">
                      {{ (rate + v.landed_unit - v.book_rate) > 0 ? "▲" : "▼" }}{{ fmtNum(Math.abs(rate + v.landed_unit - v.book_rate), 2) }}</span>
                  </template>
                  <span v-else class="text-ink-3">—</span>
                </td>
                <td class="px-3 py-1.5 text-center">
                  <span v-if="v.fixed" class="text-[10px] font-bold px-1.5 py-0.5 rounded-full" style="background:#ecfdf5;color:#047857">✓ {{ L("fixed","متظبط","corrigé") }}</span>
                  <span v-else-if="v.batch_tracked" class="text-[10px] font-bold px-1.5 py-0.5 rounded-full" style="background:#faf5ff;color:#7c3aed" :title="L('batch/serial tracked — manual path','بتتبع باتشات — مسار يدوي','suivi par lot')">🧬</span>
                  <span v-else-if="v.waiting.length" class="text-[10px] font-bold px-1.5 py-0.5 rounded-full" style="background:#fffbeb;color:#b45309" :title="v.waiting.join(', ')">⏳ {{ L("freight","شحن","fret") }}</span>
                  <span v-else class="text-[10px] font-bold px-1.5 py-0.5 rounded-full" style="background:#eff6ff;color:#2563eb">{{ L("ready","جاهز","prêt") }}</span>
                </td>
                <td class="px-3 py-1.5 text-center text-[12px]">
                  <span v-if="results[v.item_code] === 'ok'" class="text-emerald-700 font-bold">✓</span>
                  <span v-else-if="results[v.item_code] === 'proposed'" class="text-indigo-600 font-bold" :title="L('proposed — awaiting approval','مقترح — في انتظار الموافقة','proposé')">📩</span>
                  <span v-else-if="results[v.item_code]" class="text-sale font-bold" :title="results[v.item_code]">✕</span>
                  <button class="ms-1 text-[10px] text-accent-dark hover:underline" :title="L('open the item page','افتح صفحة الصنف','ouvrir')"
                          @click="$emit('open-item', v.item_code)">↗</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- ④ submit -->
      <div v-if="canWrite" class="bg-white border rounded-[14px] shadow-card px-4 py-3.5 flex items-center gap-3 flex-wrap" :style="canSubmit ? 'border-color:#a7f3d0' : 'border-color:#e7e5e4'">
        <div class="flex-1 min-w-[260px]">
          <div class="text-[12px] font-bold">④ {{ L("Submit — the whole model, retroactively","الاعتماد — الموديل كله بأثر رجعي","④ Soumettre") }}</div>
          <div class="text-[11px] text-ink-muted mt-0.5">{{ L("Each variant posts its OWN retro schedule (its receipts, its dates) at this one product cost — one undoable action per variant.","كل variant بياخد جدوله الزمني الخاص (استلاماته وتواريخه) بنفس تكلفة المنتج — وUndo مستقل لكل واحد.","Chaque variante a son propre plan rétro.") }}</div>
        </div>
        <template v-if="posting">
          <div class="flex-1 h-[8px] rounded-full overflow-hidden min-w-[140px]" style="background:#f5f5f4">
            <div class="h-full rounded-full transition-all" style="background:#059669" :style="{ width: (progress / Math.max(targetCount, 1) * 100) + '%' }"></div>
          </div>
          <span class="text-[11.5px] tnum text-ink-muted">{{ progress }} / {{ targetCount }}</span>
        </template>
        <template v-else>
          <span v-if="finished" class="text-[12px] font-bold text-emerald-700">✓ {{ posted }} {{ L("posted","اترحّل","comptabilisés") }}<span v-if="failed" class="text-sale"> · {{ failed }} {{ L("failed","فشل","échoués") }}</span></span>
          <span v-if="draining" class="text-[11px] text-ink-muted">⏳ {{ L("reposting old moves…","بيعاد حساب الحركات القديمة…","recalcul…") }}</span>
          <button class="h-[34px] px-5 rounded-[10px] text-[12.5px] font-bold text-white bg-brand hover:bg-brand-dark disabled:opacity-40"
                  :disabled="!canSubmit" @click="runSubmit">
            {{ L("Submit","اعتماد","Soumettre") }} {{ targetCount }}
          </button>
        </template>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed } from "vue";
import { useI18n } from "vue-i18n";
import api from "@/services/api";
import { useToast } from "@/composables/useToast";
import { useAuth } from "@/composables/useAuth";

const props = defineProps({ seed: { type: String, required: true } });
const emit = defineEmits(["applied", "open-item"]);
const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const toast = useToast();
const { can } = useAuth();
const canWrite = computed(() => can("post_entries"));
const M = "accounting_portal.api.model_costing";
const fmtNum = (n, d = 0) => new Intl.NumberFormat("en-US", { maximumFractionDigits: d }).format(n || 0);

const d = ref(null);
const loading = ref(false);
const err = ref("");
const rate = ref(null);
const note = ref("");
const excluded = ref(new Set());
const results = ref({});
const posting = ref(false);
const finished = ref(false);
const draining = ref(false);
const posted = ref(0);
const failed = ref(0);
const progress = ref(0);

const modelName = computed(() => {
  const n = d.value?.variants?.[0]?.item_name || props.seed;
  return n.split(" / ")[0];
});
const targetCount = computed(() =>
  (d.value?.variants || []).filter((v) => !v.fixed && !v.batch_tracked && !v.waiting.length && !excluded.value.has(v.item_code)).length);
// M5 guard: a sub-0.5 "cost" is a broken FX artefact; M7: changing the figure
// away from the evidence requires a note
const noteNeeded = computed(() =>
  d.value?.model?.suggested != null && rate.value !== d.value.model.suggested && !(note.value || "").trim());
const canSubmit = computed(() =>
  rate.value >= 0.5 && targetCount.value > 0 && !posting.value && !draining.value && !noteNeeded.value);

function toggleExclude(ic) {
  const s = new Set(excluded.value);
  s.has(ic) ? s.delete(ic) : s.add(ic);
  excluded.value = s;
}

// ── ② freight + ⚖️ weight actions (same endpoints as the SKU page) ──
const fBusy = ref(false);
const famWeight = ref(null);
const suspectWeights = computed(() =>
  (d.value?.variants || []).filter((v) => v.weight_suspect && !v.fixed));
async function setChannel(r, to) {
  if (fBusy.value) return;
  fBusy.value = true;
  try {
    await api.call("accounting_portal.api.landed_prep.set_pr_channel", { pr: r.pr, channel: to, year: d.value?.year });
    toast.success(L("Channel confirmed", "القناة اتأكدت", "Canal confirmé"));
    await load();
  } catch (e) { toast.error(e.message || "Failed"); }
  finally { fBusy.value = false; }
}
async function flipChannel(r) {
  const to = r.channel === "air" ? "sea" : "air";
  if (!window.confirm(L(`Classify ${r.pr} as ${to === "sea" ? "SEA 🚢" : "AIR 🛫"}?`,
                        `تصنيف ${r.pr} ${to === "sea" ? "بحري 🚢" : "جوي 🛫"}؟`, `Classer ${to} ?`))) return;
  await setChannel(r, to);
}
async function confirmChannel(r) { await setChannel(r, r.channel); }
async function confirmRate(r) {
  fBusy.value = true;
  try {
    await api.call("accounting_portal.api.landed_prep.set_pr_rate", { pr: r.pr, rate: r._draft ?? r.band_rate, year: d.value?.year });
    toast.success(L("Rate confirmed", "السعر اتعتمد", "Tarif confirmé"));
    await load();
  } catch (e) { toast.error(e.message || "Failed"); }
  finally { fBusy.value = false; }
}
async function applyFamilyWeight() {
  if (!(famWeight.value > 0)) return;
  if (!window.confirm(L(
    `Set ${famWeight.value} kg on ${suspectWeights.value.length} suspect variant(s)? Measured weights are untouched.`,
    `تسجيل ${famWeight.value} كجم على ${suspectWeights.value.length} variant وزنهم مشكوك؟ الأوزان المقاسة متتلمسش.`,
    `Appliquer ${famWeight.value} kg ?`))) return;
  fBusy.value = true;
  try {
    const r = await api.call(`${M}.set_family_weight`, { item_code: props.seed, weight: famWeight.value, only_suspect: 1 });
    toast.success(L(`Weight set on ${r.applied.length} variant(s) — freight shares recalculated`, `الوزن اتسجل على ${r.applied.length} — الشحن اتعاد حسابه`, `${r.applied.length} appliqués`));
    famWeight.value = null;
    await load();
  } catch (e) { toast.error(e.message || "Failed"); }
  finally { fBusy.value = false; }
}

const savedCost = ref(null);
const savingCost = ref(false);
// manual landed calculator (imported, no receipts): weight × era tariff
const mlW = ref(null);
const mlRate = ref(100);
const mlEst = computed(() => (mlW.value > 0 && mlRate.value > 0 ? +(mlW.value * mlRate.value).toFixed(2) : 0));
function applyManualLanded() {
  const product = rate.value || d.value?.model?.suggested || 0;
  if (!(product >= 0.5) || !(mlEst.value > 0)) return;
  rate.value = +(product + mlEst.value).toFixed(2);
  const stamp = `شامل شحن تقديري: ${mlW.value}kg × ${mlRate.value}/kg = ${mlEst.value.toFixed(2)} (منتج ${product})`;
  note.value = note.value ? `${note.value} · ${stamp}` : stamp;
  toast.success(L("Freight folded into the verified cost — the note documents the math",
                  "الشحن اتجمع على التكلفة المعتمدة — والملاحظة وثّقت الحسبة",
                  "Fret ajouté au coût"));
}
async function saveCost() {
  if (!(rate.value >= 0.5)) return;
  savingCost.value = true;
  try {
    const r = await api.call(`${M}.save_model_cost`, { item_code: props.seed, rate: rate.value, note: note.value || undefined });
    savedCost.value = r.cost;
    toast.success(L(`Saved on ${r.saved.length} variant(s)`, `اتحفظ على ${r.saved.length} variant`, `${r.saved.length} enregistrés`));
  } catch (e) { toast.error(e.message || "Failed"); }
  finally { savingCost.value = false; }
}
async function load() {
  loading.value = true;
  err.value = "";
  try {
    d.value = await api.call(`${M}.model_detail`, { item_code: props.seed }, { fresh: true });
    savedCost.value = d.value.model.saved_cost >= 0.5 ? d.value.model.saved_cost : null;
    // manual-landed calculator prefills — REFERENCE numbers, always editable:
    // weight = median of the variants' TRUSTED weights (suspect ones ignored);
    // rate = the contract tariff of the model's own invoice era
    if (!mlW.value) {
      const tw = (d.value.variants || []).filter((v) => !v.weight_suspect && v.weight > 0)
        .map((v) => v.weight).sort((a, b) => a - b);
      if (tw.length) mlW.value = +tw[Math.floor(tw.length / 2)].toFixed(2);
    }
    const lastDt = (d.value.evidence || []).map((e) => e.dt).sort().pop() || "";
    mlRate.value = lastDt >= "2026-04-23" ? 126 : lastDt >= "2025-07-25" ? 110 : 100;
    // prefill priority: the team's own SAVED draft > the engine suggestion
    if (!rate.value) {
      if (savedCost.value) rate.value = savedCost.value;
      else if (d.value.model.suggested >= 0.5) rate.value = d.value.model.suggested;
    }
  } catch (e) { err.value = e.message || "Failed"; }
  finally { loading.value = false; }
}
load();

async function runSubmit() {
  if (!canSubmit.value) return;
  if (!window.confirm(L(
    `Apply ${targetCount.value} variant(s) at ${rate.value} MAD product cost, RETROACTIVELY from each one's first 2026 receipt?`,
    `تطبيق ${targetCount.value} variant بتكلفة منتج ${rate.value} درهم، بأثر رجعي من أول استلام 2026 لكل واحد؟`,
    `Appliquer ${targetCount.value} variante(s) ?`))) return;
  posting.value = true;
  finished.value = false;
  results.value = {};
  posted.value = 0; failed.value = 0; progress.value = 0;
  let proposedN = 0;
  try {
    for (let w = 0; w < 20; w++) {
      const r = await api.call(`${M}.apply_model`, {
        item_code: props.seed, rate: rate.value, note: note.value || undefined,
        retro: 1, exclude: JSON.stringify([...excluded.value]), limit: 15,
      }, { fresh: true });
      for (const p of r.posted) {
        const prev = results.value[p.item_code];
        if (prev !== "ok") { posted.value++; if (prev && prev !== "proposed") failed.value--; }
        results.value[p.item_code] = "ok";
      }
      for (const p of r.proposed || []) {
        if (results.value[p.item_code] !== "proposed") proposedN++;
        results.value[p.item_code] = "proposed";
      }
      for (const sk of r.skipped) { if (!results.value[sk.item_code]) failed.value++; results.value[sk.item_code] = sk.reason || "failed"; }
      progress.value = posted.value + failed.value + proposedN;
      if ((!r.posted.length && !(r.proposed || []).length) || !r.remaining) break;
    }
    if (posted.value || proposedN) {
      toast.success(proposedN
        ? L(`${posted.value} posted · ${proposedN} proposed for approval`, `${posted.value} اترحّل · ${proposedN} مقترح للموافقة`, `${posted.value} + ${proposedN} proposés`)
        : L(`Model applied — ${posted.value} variant(s)`, `الموديل اتطبق — ${posted.value} variant`, `${posted.value} appliqués`));
    } else if (failed.value) {
      toast.error(L("Nothing posted — see the row reasons", "مفيش حاجة اترحّلت — شوفوا أسباب الصفوف", "Rien comptabilisé"));
    }
  } catch (e) { toast.error(e.message || "Failed"); }
  finally {
    posting.value = false;
    finished.value = true;
    emit("applied");
    await load();
    if (posted.value) {
      draining.value = true;
      let drained = false;
      for (let i = 0; i < 12; i++) {
        try {
          const r = await api.call("accounting_portal.api.valuation.drain_reposts", { budget_s: 45 }, { fresh: true });
          if (!r.remaining) { drained = true; break; }
        } catch (e) { toast.error(e.message || "Repost drain failed"); break; }
      }
      if (!drained) toast.info(L("Reposts still running — they'll finish in the background", "إعادة الحساب لسه شغالة — هتكمل في الخلفية", "Recalcul en cours"));
      draining.value = false;
    }
  }
}
</script>
