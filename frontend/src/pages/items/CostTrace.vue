<template>
  <div class="space-y-3.5">
    <!-- Headline -->
    <div class="flex items-center gap-2 flex-wrap">
      <span class="text-[13px] font-bold">{{ L("Product cost trace","تتبّع تكلفة المنتج","Traçage coût produit") }}</span>
      <span class="text-[11px] text-ink-muted flex-1">{{ L("The true cost of a product, from its source supplier through every company to Morocco — where the price diverged.","التكلفة الحقيقية للمنتج، من المورّد الأصلي عبر كل الشركات للمغرب — والفرق حصل فين.","Le vrai coût d'un produit, de la source jusqu'au Maroc.") }}</span>
    </div>

    <!-- Search -->
    <div class="bg-white border border-line rounded-[12px] shadow-card p-3 relative">
      <div class="flex items-center gap-2">
        <Icon name="search" :size="16" color="#9a8f88" />
        <input v-model="q" @input="onSearch" @focus="onSearch" @blur="hideResultsSoon"
               :placeholder="L('Search SKU / name / code…','بحث SKU / اسم / كود…','Rechercher…')"
               class="flex-1 h-[30px] text-[13px] outline-none bg-transparent" />
        <span v-if="loading" class="text-[11px] text-ink-muted">{{ L("…","…","…") }}</span>
      </div>
      <div v-if="results.length && showResults" class="absolute z-20 left-3 right-3 top-[52px] bg-white border border-line rounded-[10px] shadow-cardHover max-h-[320px] overflow-y-auto">
        <button v-for="r in results" :key="r.item_code" class="w-full text-start px-3 py-2 hover:bg-app-warm border-b border-line-hair last:border-0 flex items-center gap-2"
                @click="pick(r.item_code)">
          <div class="flex-1 min-w-0">
            <div class="text-[12px] font-semibold truncate">{{ r.sku || r.item_code }}</div>
            <div class="text-[10.5px] text-ink-muted truncate">{{ r.item_name }}</div>
          </div>
          <span v-if="r.stock_qty > 0" class="text-[10px] font-bold text-emerald-700 whitespace-nowrap">{{ fmtNum(r.stock_qty) }} {{ L("in stock","بالمخزن","stock") }}</span>
        </button>
      </div>
    </div>

    <div v-if="err" class="rounded-[10px] border border-amber-200 bg-amber-50 text-amber-800 px-4 py-3 text-[12px]">{{ err }}</div>

    <!-- ══ Shipment costing file (opened from the queue below or from Purchases → Shipments) ══ -->
    <template v-if="openPr">
      <button class="text-[11.5px] font-semibold text-brand hover:underline inline-flex items-center gap-1" @click="openPr = null; loadTower();">
        <Icon name="arrow" :size="12" class="rtl:rotate-180" />{{ L("Back to catalogue","رجوع للكتالوج","Retour") }}
      </button>
      <ShipmentCostSheet :pr="openPr" :year="openPrYear" @saved="loadTower" />
    </template>

    <!-- Catalogue overview + worklist (shown when no single item is picked) -->
    <template v-else-if="!trace">
      <!-- ══ Cost Control Tower — the 5-step guided process ══ -->
      <div v-if="tower" class="bg-white border border-line rounded-[14px] shadow-card px-4 py-3">
        <div class="flex items-center gap-1.5 flex-wrap text-[11px] font-semibold">
          <span v-for="(s, i) in steps" :key="i" class="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-[9px]"
                :style="s.state==='done' ? 'background:#ecfdf5;color:#047857' : s.state==='active' ? 'background:#eef2ff;color:#4338ca' : 'background:#f5f5f4;color:#a8a29e'">
            <b>{{ i+1 }}</b> {{ s.label }}
            <span v-if="s.state==='done'">✅</span><span v-else-if="s.state==='locked'">🔒</span>
          </span>
        </div>
        <div class="text-[11px] text-ink-muted mt-1.5 flex items-center gap-2 flex-wrap">
          <span class="flex-1">{{ nextHint }}</span>
          <span v-if="tower" class="text-[10px] font-bold px-1.5 py-0.5 rounded-full whitespace-nowrap"
                :style="tower.guard.enabled ? 'background:#ecfdf5;color:#047857' : 'background:#fef2f2;color:#b91c1c'"
                :title="L('Every new purchase document with an implausible FX rate is rejected at entry.','أي مستند شراء بسعر صرف غير منطقي بيترفض لحظة الإدخال.','Garde FX.')">
            {{ tower.guard.enabled ? L("FX guard ON","حارس الصرف شغّال","Garde FX ON") : L("FX guard OFF!","الحارس متوقف!","Garde OFF!") }}</span>
        </div>
      </div>

      <!-- ③ the catalogue crawl -->
      <div v-if="tower" class="bg-white border border-line rounded-[14px] shadow-card px-4 py-3">
        <div class="flex items-center gap-2 flex-wrap">
          <span class="text-[13px] font-bold">③ {{ L("The catalogue crawl","زحفة التكلفة","La revue catalogue") }}</span>
          <span class="text-[11px] font-bold tnum">{{ fmtNum(tower.crawl.fixed) }} / {{ fmtNum(tower.crawl.total) }} {{ L("fixed","متظبط","corrigés") }}</span>
          <span class="text-[11px] text-ink-muted flex-1">{{ L("remaining distortion","التشوّه المتبقّي","distorsion restante") }}: <b class="tnum" style="color:#b91c1c">{{ fmtNum(tower.crawl.remaining_over) }}</b> MAD</span>
        </div>
        <div class="h-[7px] bg-app-warm rounded-full mt-2 overflow-hidden">
          <div class="h-full rounded-full" style="background:#047857"
               :style="{ width: (tower.crawl.total ? Math.round(100 * tower.crawl.fixed / tower.crawl.total) : 0) + '%' }"></div>
        </div>
      </div>

      <div v-if="ov" class="grid grid-cols-2 lg:grid-cols-4 gap-2.5">
        <div class="bg-white rounded-[12px] border border-line p-3.5 shadow-card">
          <div class="text-[10.5px] text-ink-muted font-semibold">{{ L("Current book value","القيمة الحالية","Valeur actuelle") }}</div>
          <div class="text-[18px] font-bold tnum mt-[3px]">{{ fmtNum(ov.current_value) }}</div>
          <div class="text-[10px] text-ink-3">{{ fmtNum(ov.items) }} {{ L("stocked items","صنف بالمخزن","articles") }}</div>
        </div>
        <div class="bg-white rounded-[12px] border border-line p-3.5 shadow-card">
          <div class="text-[10.5px] text-ink-muted font-semibold">{{ L("True value (priced)","القيمة الحقيقية","Valeur vraie") }}</div>
          <div class="text-[18px] font-bold tnum mt-[3px] text-emerald-700">{{ fmtNum(ov.true_value_priced) }}</div>
          <div class="text-[10px] text-ink-3">{{ fmtNum(ov.maslak_pi + ov.morocco_pr) }} {{ L("priced","مسعّر","tarifés") }}</div>
        </div>
        <div class="bg-white rounded-[12px] border p-3.5 shadow-card" style="border-color:#fecaca">
          <div class="text-[10.5px] text-ink-muted font-semibold">{{ L("Overvaluation","التشوّه","Survalorisation") }}</div>
          <div class="text-[18px] font-bold tnum mt-[3px]" style="color:#b91c1c">{{ fmtNum(ov.overvaluation) }}</div>
          <div class="text-[10px] text-ink-3">{{ L("to remove from stock","يتشال من المخزون","à retirer") }}</div>
        </div>
        <div class="bg-white rounded-[12px] border p-3.5 shadow-card" style="border-color:#fde68a">
          <div class="text-[10.5px] text-ink-muted font-semibold">{{ L("Unpriced (no source)","بلا مصدر","sans source") }}</div>
          <div class="text-[18px] font-bold tnum mt-[3px]" style="color:#b45309">{{ fmtNum(ov.unpriced) }}</div>
          <div class="text-[10px] text-ink-3">{{ L("need manual cost","محتاجة تسعير يدوي","coût manuel") }}</div>
        </div>
      </div>

      <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
        <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2 flex-wrap">
          <span class="text-[13px] font-bold">{{ L("③ Catalogue — true cost vs book","③ الكتالوج — الحقيقة مقابل الدفاتر","③ Catalogue") }}</span>
          <div class="flex-1"></div>
          <!-- supplier → month audit filter -->
          <select v-model="supFilter" class="h-[28px] text-[11.5px] px-2 rounded-[8px] border border-line max-w-[180px]">
            <option value="">{{ L("All suppliers","كل الموردين","Fournisseurs") }}</option>
            <option v-for="s in filters.suppliers" :key="s.supplier" :value="s.supplier">{{ shortSup(s.supplier) }} ({{ s.items }})</option>
          </select>
          <select v-model="moFilter" class="h-[28px] text-[11.5px] px-2 rounded-[8px] border border-line">
            <option value="">{{ L("All months","كل الشهور","Mois") }}</option>
            <option v-for="m in filters.months" :key="m" :value="m">{{ m }}</option>
          </select>
          <select v-model="srcFilter" class="h-[28px] text-[11.5px] px-2 rounded-[8px] border border-line">
            <option value="">{{ L("All sources","كل المصادر","Toutes") }}</option>
            <option value="maslak_pi">{{ L("Maslak-sourced","مصدر Maslak","Maslak") }}</option>
            <option value="local_pi">{{ L("Local suppliers","موردين محليين","Fourn. locaux") }}</option>
            <option value="morocco_pr">{{ L("Morocco-direct","مغرب مباشر","Maroc") }}</option>
            <option value="unpriced">{{ L("Unpriced","بلا سعر","Sans prix") }}</option>
          </select>
          <select v-model="fixFilter" class="h-[28px] text-[11.5px] px-2 rounded-[8px] border border-line">
            <option value="">{{ L("All statuses","كل الحالات","Tous") }}</option>
            <option value="pending">{{ L("Pending review","في انتظار المراجعة","En attente") }}</option>
            <option value="fixed">{{ L("Fixed ✓","متظبطة ✓","Corrigés ✓") }}</option>
          </select>
          <button v-if="canWrite && srcFilter === 'local_pi'" @click="openLocalBulk"
                  class="h-[28px] px-3 rounded-[8px] text-[11.5px] font-bold text-white bg-brand hover:bg-brand-dark">
            ⚡ {{ L("Apply all local","تطبيق كل المحلي","Tout appliquer") }}
          </button>
        </div>
        <div v-if="ct.error.value" class="py-8 text-center text-[12px] text-sale">{{ ct.error.value }}</div>
        <div v-else class="overflow-x-auto">
          <table class="w-full text-[12px]">
            <thead>
              <tr style="background:#fafaf9">
                <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Product","المنتج","Produit") }}</th>
                <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Supplier","المورّد","Fournisseur") }}</th>
                <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Source","المصدر","Source") }}</th>
                <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Qty","كمية","Qté") }}</th>
                <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Book","الدفاتر","Livre") }}</th>
                <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("True","الحقيقي","Vrai") }}</th>
                <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Overvaluation","التشوّه","Survalo.") }}</th>
                <th class="px-4 py-2.5 text-center text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Fixed","متظبط","OK") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in ct.rows.value" :key="r.item_code" class="border-t border-line-hair hover:bg-app-warm/60 cursor-pointer" @click="pick(r.item_code)">
                <td class="px-4 py-2.5 truncate max-w-[220px]"><span class="font-semibold">{{ r.sku || r.item_code }}</span><div class="text-[10px] text-ink-muted truncate">{{ r.item_name }}</div></td>
                <td class="px-4 py-2.5 text-ink-3 truncate max-w-[130px] text-[11px]">{{ shortSup(r.supplier) || "—" }}</td>
                <td class="px-4 py-2.5"><span class="text-[10px] font-bold px-1.5 py-0.5 rounded-full" :style="srcChip(r.source)">{{ srcShort(r.source) }}</span></td>
                <td class="px-4 py-2.5 text-end tnum text-ink-3">{{ fmtNum(r.qty) }}</td>
                <td class="px-4 py-2.5 text-end tnum">{{ fmtNum(r.current_rate, 1) }}</td>
                <td class="px-4 py-2.5 text-end tnum font-semibold text-emerald-700">{{ r.true_cost != null ? fmtNum(r.true_cost, 1) : "—" }}</td>
                <td class="px-4 py-2.5 text-end tnum font-bold" :style="{ color: (r.overvaluation || 0) > 0 ? '#b91c1c' : '#78716c' }">{{ r.overvaluation != null ? fmtNum(r.overvaluation) : "—" }}</td>
                <td class="px-4 py-2.5 text-center" :title="r.repolluted ? L('Fixed before but drifted again — a new bad inbound entry needs source-fixing','اتظبط قبل كده ورجع انحرف — فيه إدخال جديد غلط لازم يتصلح من مصدره','Re-pollué') : ''">
                  <span :class="r.repolluted ? 'text-amber-600' : 'text-emerald-700'" class="font-bold">{{ r.repolluted ? "⚠" : (r.fixed ? "✓" : "") }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="!ct.loading.value && !ct.rows.value.length && !ct.error.value" class="py-10 text-center text-[12px] text-ink-muted">{{ L("No items.","لا أصناف.","Aucun.") }}</div>
        <ServerPager :t="ct" />
      </div>


      <!-- B6: Monthly COGS true-up -->
      <div v-if="tu" class="bg-white border rounded-[14px] shadow-card overflow-hidden" :style="tu.basis_frozen ? 'border-color:#e7e5e4' : 'border-color:#fde68a'">
        <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2 flex-wrap cursor-pointer" @click="tuOpen = !tuOpen">
          <span class="text-[13px] font-bold">④ {{ L("Monthly COGS true-up","تسوية COGS الشهرية","Régularisation COGS mensuelle") }} {{ tu.year }}</span>
          <span v-if="!tu.basis_frozen" class="text-[10.5px] font-bold px-2 py-0.5 rounded-full" style="background:#fffbeb;color:#b45309">{{ L("landed basis not frozen — posting blocked","أساس الشحن مش مجمّد — الترحيل متقفل","base non gelée") }}</span>
          <span class="text-[11px] text-ink-muted flex-1">{{ L("Restates each month's ledger COGS to the true full cost — GL-only, reversible, zero net-profit impact.","بتظبط COGS كل شهر في الدفاتر على التكلفة الكاملة — GL فقط، قابلة للعكس، صافي الربح لا يتغيّر.","GL uniquement, réversible.") }}</span>
          <span class="text-ink-3">{{ tuOpen ? "▾" : "▸" }}</span>
        </div>
        <div v-if="tuOpen" class="overflow-x-auto">
          <table class="w-full text-[12px]">
            <thead><tr style="background:#fafaf9">
              <th class="px-4 py-2 text-start text-[10px] font-bold text-ink-muted">{{ L("Month","الشهر","Mois") }}</th>
              <th class="px-4 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("Booked COGS","المسجّل","Comptabilisé") }}</th>
              <th class="px-4 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("True COGS","الحقيقي","Vrai") }}</th>
              <th class="px-4 py-2 text-end text-[10px] font-bold text-ink-muted">Δ</th>
              <th class="px-4 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("Coverage","تغطية","Couv.") }}</th>
              <th class="px-4 py-2 text-end text-[10px] font-bold text-ink-muted"></th>
            </tr></thead>
            <tbody>
              <tr v-for="r in tu.rows" :key="r.month" class="border-t border-line-hair">
                <td class="px-4 py-2 font-semibold whitespace-nowrap">{{ r.month }}
                  <span v-if="r.open_month" class="text-[9.5px] font-bold text-amber-600">· {{ L("open","مفتوح","ouvert") }}</span>
                </td>
                <td class="px-4 py-2 text-end tnum">{{ fmtNum(r.booked) }}</td>
                <td class="px-4 py-2 text-end tnum text-emerald-700 font-semibold">{{ fmtNum(r.true) }}</td>
                <td class="px-4 py-2 text-end tnum font-bold" :style="{ color: r.delta > 0 ? '#b91c1c' : '#2563eb' }">{{ fmtNum(r.delta) }}</td>
                <td class="px-4 py-2 text-end tnum text-ink-3">{{ r.coverage_pct }}%</td>
                <td class="px-4 py-2 text-end whitespace-nowrap">
                  <span v-if="r.posted" class="text-[10.5px] font-bold" :class="r.posted.stale_basis ? 'text-amber-600' : 'text-emerald-700'">{{ r.posted.stale_basis ? '⚠' : '✅' }} <span dir="ltr">{{ r.posted.voucher_no }}</span><template v-if="r.posted.stale_basis"> · {{ L("basis changed — revert & re-post","الأساس اتغيّر — اعكسوه ورحّلوه تاني","base modifiée") }}</template></span>
                  <button v-else-if="canWrite" class="h-[26px] px-2.5 rounded-[7px] text-[10.5px] font-bold text-white bg-brand hover:bg-brand-dark disabled:opacity-40"
                          :disabled="tuBusy === r.month || !tu.basis_frozen || r.open_month || Math.abs(r.delta) < 1"
                          @click="postTrueup(r)">
                    {{ tuBusy === r.month ? L("…","…","…") : L("Post true-up","رحّل التسوية","Poster") }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- ⑤ closings -->
      <div v-if="tower" class="bg-white border border-line rounded-[14px] shadow-card px-4 py-3">
        <div class="flex items-center gap-2 flex-wrap">
          <span class="text-[13px] font-bold">⑤ {{ L("Closings","الإقفالات","Clôtures") }}</span>
          <span class="text-[10.5px] font-bold px-2 py-0.5 rounded-full"
                :style="tower.close2025.done ? 'background:#ecfdf5;color:#047857' : 'background:#fffbeb;color:#b45309'">
            {{ L("2025 dummy-customer residual","متبقّي العميل المجمّع 2025","résidu 2025") }}: {{ fmtNum(tower.close2025.dummy_balance) }}
          </span>
          <span class="text-[11px] text-ink-muted flex-1">
            {{ L("Plan: docs/CLOSE_2025_PLAN.md — 3 open decisions (entry dating per tax filing, VAT treatment, single vs monthly) must be settled before posting. Then intercompany / Maslak / consolidation.",
                 "الخطة: docs/CLOSE_2025_PLAN.md — لازم حسم 3 قرارات (التأريخ حسب الإقرار الضريبي، الـVAT، قيد واحد أم شهري) قبل الترحيل. بعدها الانتر-كومباني / Maslak / التوحيد.",
                 "The close plan is prepared — 3 decisions pending with management.") }}
          </span>
        </div>
      </div>
      <!-- admin corner: reconciliation & freeze — not part of daily work -->
      <details>
        <summary class="cursor-pointer text-[11px] font-semibold text-ink-3 hover:text-ink px-1 py-1 select-none">
          ⚙️ {{ L("Admin — freight reconciliation & basis freeze (needed for monthly true-ups only)","إداري — تسوية الشحن وتجميد الأساس (لازم لتسويات الشهور فقط)","Admin — réconciliation & gel") }}
        </summary>
        <div class="mt-2">
          <LandedBasisCard @changed="loadTower(); loadTu();" />
        </div>
      </details>
    </template>

    <!-- Trace result -->
    <div v-if="trace" class="space-y-3">
      <button class="text-[11.5px] font-semibold text-brand hover:underline inline-flex items-center gap-1" @click="trace = null; q = ''">
        <Icon name="arrow" :size="12" class="rtl:rotate-180" />{{ L("Back to catalogue","رجوع للكتالوج","Retour") }}
      </button>
      <!-- Product header + KPIs -->
      <div class="bg-white border border-line rounded-[14px] shadow-card p-4">
        <div class="flex items-start gap-3 flex-wrap">
          <div class="flex-1 min-w-[200px]">
            <div class="text-[14px] font-bold">{{ trace.sku || trace.item_code }}</div>
            <div class="text-[11.5px] text-ink-muted">{{ trace.item_name }}</div>
            <div class="text-[10.5px] text-ink-3 mt-0.5">{{ trace.item_code }} · {{ trace.uom }} · {{ trace.weight_per_unit }}kg</div>
          </div>
          <div class="grid grid-cols-3 gap-2.5">
            <div class="text-center px-3">
              <div class="text-[10px] text-ink-muted font-semibold">{{ L("True cost","التكلفة الحقيقية","Vrai coût") }}</div>
              <div class="text-[18px] font-bold tnum text-emerald-700">{{ trace.true_cost.cost_mad != null ? fmtNum(trace.true_cost.cost_mad) : "—" }}</div>
              <div class="text-[9.5px]" :class="srcColor">{{ srcLabel }}</div>
            </div>
            <div class="text-center px-3">
              <div class="text-[10px] text-ink-muted font-semibold">{{ L("Current book","الدفاتر الحالية","Livre actuel") }}</div>
              <div class="text-[18px] font-bold tnum">{{ trace.current_valuation_mad != null ? fmtNum(trace.current_valuation_mad) : "—" }}</div>
              <div class="text-[9.5px] text-ink-3">{{ fmtNum(trace.current_qty) }} {{ L("units","وحدة","u.") }}</div>
            </div>
            <div class="text-center px-3">
              <div class="text-[10px] text-ink-muted font-semibold">{{ L("Distortion","التشوّه","Distorsion") }}</div>
              <div class="text-[18px] font-bold tnum" :style="{ color: distColor }">{{ trace.distortion_pct != null ? (trace.distortion_pct > 0 ? "+" : "") + fmtNum(trace.distortion_pct) + "%" : "—" }}</div>
              <div class="text-[9.5px] text-ink-3">{{ L("vs true cost","مقابل الحقيقة","vs vrai") }}</div>
            </div>
          </div>
        </div>
        <div class="text-[10.5px] text-ink-muted mt-2.5 pt-2.5 border-t border-line-hair">
          ⓘ {{ L("Product cost only — the freight of this product is added on top in section ② below.","تكلفة المنتج فقط — شحن المنتج بيتضاف فوقها في سكشن ② تحت.","Coût produit uniquement — le fret est ajouté en ② ci-dessous.") }}
        </div>
      </div>

      <!-- ① PRODUCT COST — its own card with its own Save -->
      <div v-if="fixPrev" class="bg-white border rounded-[14px] shadow-card overflow-hidden" :style="fixPrev.fixed ? 'border-color:#a7f3d0' : 'border-color:#e7e5e4'">
        <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2 flex-wrap">
          <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#fffbeb"><Icon name="shield" :size="14" color="#b45309" /></span>
          <span class="text-[13px] font-bold">① {{ L("Product cost — verify & save","تكلفة المنتج — تحقق واحفظ","① Coût produit") }}</span>
          <span v-if="savedCost != null" class="text-[10px] font-bold px-1.5 py-0.5 rounded-full" style="background:#ecfdf5;color:#047857">
            💾 {{ L("saved","محفوظ","enregistré") }} {{ fmtNum(savedCost, 2) }}</span>
          <span v-if="costDirty" class="text-[10px] font-bold px-1.5 py-0.5 rounded-full" style="background:#fffbeb;color:#b45309">{{ L("unsaved changes","تغييرات مش محفوظة","non enregistré") }}</span>
        </div>
        <div class="p-4 space-y-2.5">
          <table class="w-full text-[11.5px] border border-line rounded-[8px] overflow-hidden">
            <thead><tr style="background:#fafaf9">
              <th class="px-3 py-1.5 text-start text-[10px] font-bold text-ink-muted">{{ L("Document","المستند","Doc") }}</th>
              <th class="px-3 py-1.5 text-start text-[10px] font-bold text-ink-muted">{{ L("Supplier","المورّد","Fourn.") }}</th>
              <th class="px-3 py-1.5 text-end text-[10px] font-bold text-ink-muted">{{ L("Qty","كمية","Qté") }}</th>
              <th class="px-3 py-1.5 text-end text-[10px] font-bold text-ink-muted">{{ L("Rate","السعر","Taux") }}</th>
              <th class="px-3 py-1.5 text-end text-[10px] font-bold text-ink-muted">→ MAD</th>
            </tr></thead>
            <tbody>
              <tr v-for="e in fixPrev.evidence" :key="e.doc" class="border-t border-line-hair">
                <td class="px-3 py-1.5 font-mono text-[10.5px]" dir="ltr">{{ e.doc }}<span class="text-ink-muted font-sans"> · {{ e.dt }}</span></td>
                <td class="px-3 py-1.5 truncate max-w-[140px]">{{ shortSup(e.supplier) }}</td>
                <td class="px-3 py-1.5 text-end tnum">{{ fmtNum(e.qty) }}</td>
                <td class="px-3 py-1.5 text-end tnum font-semibold">{{ fmtNum(e.rate, 2) }} {{ e.cur }}</td>
                <td class="px-3 py-1.5 text-end tnum font-bold" :class="e.rate_mad >= 0.5 ? 'text-emerald-700' : 'text-sale'">
                  {{ fmtNum(e.rate_mad, 2) }}<span v-if="e.rate_mad < 0.5" :title="L('FX conversion missing for this date/currency — figure unusable','تحويل العملة ناقص للتاريخ/العملة دي — الرقم غير صالح','Conversion FX manquante')"> ⚠</span></td>
              </tr>
            </tbody>
          </table>
          <div v-if="!fixPrev.evidence.length" class="text-[11px] text-amber-700">{{ L("No purchase documents — enter the verified cost manually (a note is required).","مفيش مستندات شراء — أدخلوا التكلفة يدويًا (الملاحظة إجبارية).","Aucun document — saisir manuellement.") }}</div>
          <div v-if="canWrite && !fixPrev.fixed" class="flex items-center gap-2 flex-wrap pt-1 border-t border-line-hair">
            <label class="text-[11.5px] text-ink-2 font-semibold">{{ L("Verified cost (MAD/unit)","التكلفة المعتمدة (درهم/وحدة)","Coût vérifié") }}</label>
            <input v-model.number="fixRate" type="number" step="0.01" class="h-[30px] w-[110px] text-[12.5px] px-2 rounded-[8px] border tnum outline-none focus:border-accent"
                   :style="costDirty ? 'border-color:#fde68a;background:#fffbeb' : savedCost != null ? 'border-color:#a7f3d0;background:#f0fdf4' : 'border-color:#e7e5e4'" />
            <input v-model.trim="fixNote" :placeholder="L('Note (required if you change the figure)','ملاحظة (إجبارية لو غيّرتوا الرقم)','Note')"
                   class="h-[30px] flex-1 min-w-[180px] text-[12px] px-2 rounded-[8px] border border-line outline-none" />
            <button class="h-[30px] px-3.5 rounded-[8px] text-[11.5px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand disabled:opacity-50"
                    :disabled="fixing || !(fixRate > 0)" @click="saveItemCost">{{ L("Save","حفظ","Enregistrer") }}</button>
          </div>
        </div>
      </div>

      <!-- ② FREIGHT — its own card, its own actions (confirm rate / attach) -->
      <div v-if="itemLanded" class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
        <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2 flex-wrap">
          <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#eef6ff"><Icon name="box" :size="14" color="#2563eb" /></span>
          <span class="text-[13px] font-bold">② {{ L("Freight — this product's shipments","الشحن — شحنات المنتج","② Fret") }}</span>
          <span v-if="itemLanded.complete" class="text-[10px] font-bold px-1.5 py-0.5 rounded-full" style="background:#ecfdf5;color:#047857">✓ {{ L("complete","مكتمل","complet") }} · <span class="tnum">{{ fmtNum(itemLanded.landed_unit, 2) }}</span>/{{ L("unit","وحدة","u") }}</span>
          <span v-else-if="itemLanded.waiting.length" class="text-[10px] font-bold px-1.5 py-0.5 rounded-full" style="background:#fffbeb;color:#b45309">⏳ {{ itemLanded.waiting.length }} {{ L("shipment(s) missing freight","شحنة ناقصة شحن","exp. sans fret") }}</span>
        </div>
        <div class="p-4 space-y-2">
          <div v-if="itemLanded.receipts.length" class="border border-line rounded-[8px] overflow-hidden max-h-[190px] overflow-y-auto">
            <table class="w-full text-[11.5px]">
              <thead><tr style="background:#fafaf9" class="sticky top-0">
                <th class="px-3 py-1.5 text-start text-[10px] font-bold text-ink-muted">{{ L("Shipment","الشحنة","Expédition") }}</th>
                <th class="px-3 py-1.5 text-center text-[10px] font-bold text-ink-muted" :title="L('Channel: 🛫 air · 🚢 sea','القناة: 🛫 جوي · 🚢 بحري','Canal')">{{ L("Ch.","قناة","Can.") }}</th>
                <th class="px-3 py-1.5 text-end text-[10px] font-bold text-ink-muted">{{ L("Qty","كمية","Qté") }}</th>
                <th class="px-3 py-1.5 text-start text-[10px] font-bold text-ink-muted">{{ L("Freight","الشحن","Fret") }}</th>
                <th class="px-3 py-1.5 text-end text-[10px] font-bold text-ink-muted">{{ L("Item's share","نصيب الصنف","Part") }}</th>
              </tr></thead>
              <tbody>
                <tr v-for="r in itemLanded.receipts" :key="r.pr" class="border-t border-line-hair">
                  <td class="px-3 py-1.5 font-mono text-[10.5px] whitespace-nowrap" dir="ltr">{{ r.pr }}<div class="text-[10px] text-ink-muted font-sans">{{ r.dt }}</div></td>
                  <td class="px-3 py-1.5 text-center">{{ r.channel === "air" ? "🛫" : "🚢" }}</td>
                  <td class="px-3 py-1.5 text-end tnum">{{ fmtNum(r.qty) }}</td>
                  <td class="px-3 py-1.5 whitespace-nowrap">
                    <template v-if="['bills','rate'].includes(r.source)">
                      <FreightChip :source="r.source" /> <span class="text-[10px] text-ink-muted" dir="ltr">@{{ r.rate_kg }}/kg</span>
                    </template>
                    <template v-else-if="r.channel === 'air' && canWrite && !itemLanded.frozen">
                      <input type="number" step="1" min="0" v-model.number="r._draft" :placeholder="String(r.band_rate || '')"
                             class="w-[62px] h-[26px] px-1.5 text-end tnum text-[11px] border border-amber-300 rounded-[6px] outline-none" />
                      <button class="ms-1 h-[26px] px-2.5 rounded-[7px] text-[10.5px] font-bold text-white bg-brand hover:bg-brand-dark disabled:opacity-50"
                              :disabled="!( (r._draft ?? r.band_rate) > 0 ) || fixing" @click="confirmPrRate(r)">✓ {{ L("confirm rate","اعتماد السعر","confirmer") }}</button>
                    </template>
                    <template v-else>
                      <FreightChip source="none" />
                      <span class="text-[10px] text-ink-muted ms-1">{{ L("attach its bills in Shipments","ارفقوا فواتيرها في الشحنات","joindre dans Expéditions") }}</span>
                    </template>
                  </td>
                  <td class="px-3 py-1.5 text-end tnum font-semibold">{{ r.share ? fmtNum(r.share) : "—" }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-if="itemLanded.historical" class="rounded-[8px] px-3 py-2 text-[11.5px] flex items-center gap-2 flex-wrap" style="background:#faf5ff;border:1px solid #e9d5ff">
            <span class="font-bold" style="color:#7c3aed">🕰 {{ L("Historical shipments (pre-2026)","شحنات تاريخية (قبل 2026)","Expéditions historiques") }}</span>
            <span class="tnum">{{ itemLanded.historical.n_prs }} {{ L("receipt(s)","استلام","réc.") }} · {{ fmtNum(itemLanded.historical.qty) }} {{ L("pcs","قطعة","pcs") }}</span>
            <span>{{ itemLanded.historical.channels.includes("sea") ? "🚢" : "" }}{{ itemLanded.historical.channels.includes("air") ? "🛫" : "" }}</span>
            <span class="tnum font-semibold flex-1 text-end" dir="ltr">{{ fmtNum(itemLanded.historical.unit, 2) }} / {{ L("unit","وحدة","u") }}</span>
            <span class="text-[10px] text-ink-muted">{{ L("contract tariff (100/110/126 air · 23.6 sea) × receipt date","تعريفة العقد (جوي 100/110/126 · بحري 23.6) بتاريخ الاستلام","tarif contractuel") }}</span>
          </div>
          <div v-if="itemLanded.local" class="rounded-[8px] px-3 py-2 text-[11.5px]" style="background:#fff7ed;border:1px solid #fed7aa">
            🏠 <b style="color:#c2410c">{{ L("Local product","منتج محلي","Produit local") }}</b> —
            {{ L("bought inside Morocco: no freight layer by nature. The fix = match the receipt value to the supplier invoice (① evidence).","مشتريات داخل المغرب: مفيش طبقة شحن بطبيعته. الإصلاح = مطابقة قيمة الاستلام بفاتورة المورد (الدليل في ①).","Acheté au Maroc : pas de fret ; alignement sur la facture fournisseur.") }}
          </div>
          <div v-else-if="!itemLanded.receipts.length && !itemLanded.historical" class="text-[11px] text-ink-muted">{{ L("No import shipments at all — landed = 0 (manual-cost product).","مفيش شحنات استيراد خالص — الشحن = 0 (منتج بتكلفة يدوية).","Aucune expédition — fret 0.") }}</div>
        </div>
      </div>

      <!-- ③ SUMMARY & IMPACT -->
      <div v-if="fixPrev" class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
        <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2">
          <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#f0fdf4"><Icon name="chart" :size="14" color="#047857" /></span>
          <span class="text-[13px] font-bold">③ {{ L("Summary & impact","الملخص والأثر","③ Résumé & impact") }}</span>
          <span class="text-[11px] text-ink-muted">{{ L("one today-dated entry moves every bin","قيد واحد بتاريخ اليوم بيظبط كل المخازن","une écriture datée du jour") }}</span>
        </div>
        <div class="p-4 space-y-2.5">
          <div class="text-[12px] tnum bg-app-warm/60 rounded-[8px] px-3 py-2">
            {{ L("Product","منتج","Produit") }} <b>{{ fmtNum(fixRate || 0, 2) }}</b>
            + {{ L("landed","شحن","landed") }} <b>{{ fmtNum(itemLanded?.landed_unit || 0, 2) }}</b>
            <span class="text-ink-muted">({{ itemLanded?.receipts?.length || 0 }} {{ L("shipment(s)","شحنة","exp.") }})</span>
            = <b class="text-emerald-700">{{ fmtNum(appliedRate, 2) }} {{ L("applied","المعتمد","appliqué") }}</b>
          </div>
          <div v-if="fixPrev.bins.length" class="border border-line rounded-[8px] overflow-hidden max-h-[190px] overflow-y-auto">
            <table class="w-full text-[11.5px]">
              <thead><tr style="background:#fafaf9" class="sticky top-0">
                <th class="px-3 py-1.5 text-start text-[10px] font-bold text-ink-muted">{{ L("Warehouse","المخزن","Entrepôt") }}</th>
                <th class="px-3 py-1.5 text-end text-[10px] font-bold text-ink-muted">{{ L("Qty","كمية","Qté") }}</th>
                <th class="px-3 py-1.5 text-end text-[10px] font-bold text-ink-muted">{{ L("Rate: old → new","السعر: قديم → جديد","Taux") }}</th>
                <th class="px-3 py-1.5 text-end text-[10px] font-bold text-ink-muted">Δ MAD</th>
              </tr></thead>
              <tbody>
                <tr v-for="b in fixPrev.bins" :key="b.warehouse" class="border-t border-line-hair first:border-0" :style="b.disabled ? 'opacity:.55' : ''">
                  <td class="px-3 py-1.5 truncate max-w-[180px]">{{ b.warehouse }}
                    <span v-if="b.cycle" class="ms-1 text-[9.5px] font-bold px-1.5 py-0.5 rounded-full" style="background:#eef2ff;color:#4338ca"
                          :title="L('The reservation is released, the fix posts, then it re-reserves automatically — one atomic operation.','الحجز بيتفك، الفيكس بيترحّل، والحجز بيرجع تلقائيًا — عملية واحدة.','Réservation recyclée automatiquement.')">🔓 {{ b.reserved }} {{ L("reserved — auto-cycled","محجوز — هيتفك ويرجع","recyclé") }}</span>
                    <span v-else-if="b.disabled" class="ms-1 text-[9.5px] font-bold px-1.5 py-0.5 rounded-full" style="background:#f5f5f4;color:#78716c">{{ L("disabled wh — skipped","مخزن موقوف — هيتعدّى","désactivé") }}</span>
                  </td>
                  <td class="px-3 py-1.5 text-end tnum text-ink-3">{{ fmtNum(b.qty) }}</td>
                  <td class="px-3 py-1.5 text-end tnum">{{ fmtNum(b.old_rate, 1) }} → <b>{{ b.disabled ? fmtNum(b.old_rate, 1) : fmtNum(appliedRate || b.new_rate, 1) }}</b></td>
                  <td class="px-3 py-1.5 text-end tnum font-semibold" :style="{ color: (b.delta || 0) < 0 ? '#b91c1c' : '#047857' }">{{ b.delta != null ? fmtNum(b.delta) : "—" }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="text-[11px] text-ink-3">{{ L("Net inventory change","صافي تغيير المخزون","Δ stock") }}: <b class="tnum" :style="{ color: fixPrev.net_change < 0 ? '#b91c1c' : '#047857' }">{{ fmtNum(fixPrev.net_change) }}</b> MAD</div>
          <div v-if="fixPrev.skipped_reserved" class="text-[11px] text-amber-700">
            ⚠ {{ L(`${fixPrev.skipped_reserved} bin(s) in a DISABLED warehouse — skipped; re-enable the warehouse then re-run.`,
                   `${fixPrev.skipped_reserved} مخزن موقوف — هيتعدّى؛ فعّلوا المخزن وأعيدوا الفيكس.`,
                   `${fixPrev.skipped_reserved} entrepôt(s) désactivé(s).`) }}
          </div>
        </div>
      </div>

      <!-- ④ SUBMIT -->
      <div v-if="fixPrev && fixPrev.fixed" class="bg-white border rounded-[14px] shadow-card px-4 py-3 flex items-center gap-2 flex-wrap" style="border-color:#a7f3d0">
        <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#ecfdf5"><Icon name="check" :size="14" color="#047857" /></span>
        <span class="text-[13px] font-bold" style="color:#047857">✓ {{ L("Applied","متطبّق","Appliqué") }}</span>
        <span class="text-[11px] text-ink-muted" dir="ltr">{{ fixPrev.fixed.voucher_no }} · {{ String(fixPrev.fixed.posted_on || "").slice(0,16) }}</span>
        <span class="text-[11px] text-ink-3 flex-1 text-end">{{ L("undoable in Settings → Activity","قابل للعكس من Settings → Activity","réversible dans Activity") }}</span>
      </div>
      <div v-else-if="fixPrev && canWrite" class="bg-white border rounded-[14px] shadow-card overflow-hidden" :style="canSubmit ? 'border-color:#a7f3d0' : 'border-color:#e7e5e4'">
        <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2">
          <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#fff7ed"><Icon name="check" :size="14" color="#c2410c" /></span>
          <span class="text-[13px] font-bold">④ {{ L("Submit — apply the full cost","الاعتماد النهائي — تطبيق التكلفة الكاملة","④ Soumettre") }}</span>
        </div>
        <div class="p-4 space-y-2">
          <div v-if="fixPrev.batch_tracked" class="rounded-[8px] border border-amber-200 bg-amber-50 text-amber-800 px-3 py-2 text-[11.5px]">
            🧬 {{ L("Batch/serial-tracked item — revaluation needs a batch bundle; handle via ERPNext for now.","منتج متتبع بباتش/سيريال — إعادة التقييم محتاجة bundle؛ اتعامل معاه من ERPNext مؤقتًا.","Article à lot/série — via ERPNext pour le moment.") }}
          </div>
          <div v-if="itemLanded && itemLanded.waiting.length" class="rounded-[8px] border border-amber-200 bg-amber-50 text-amber-800 px-3 py-2 text-[11.5px]">
            🔒 {{ L("Waiting for freight of:","مستني شحن:","En attente du fret de :") }}
            <span class="font-mono text-[10.5px]" dir="ltr">{{ itemLanded.waiting.join(", ") }}</span>
            — {{ L("finish step ② first.","كمّلوا خطوة ② الأول.","finir ② d'abord.") }}
          </div>
          <div v-else-if="costDirty || (fixRate > 0 && savedCost == null)" class="rounded-[8px] border border-amber-200 bg-amber-50 text-amber-800 px-3 py-2 text-[11.5px]">
            💾 {{ L("Save the product cost first (①).","احفظوا تكلفة المنتج الأول (①).","Enregistrer le coût d'abord (①).") }}
          </div>
          <label class="flex items-center gap-2 text-[12px] text-ink-2 cursor-pointer">
            <input type="checkbox" v-model="fixConfirm" class="accent-accent w-3.5 h-3.5" />
            {{ L("I verified this figure against the actual supplier invoice","اتحققت من الرقم ده من فاتورة المورّد الفعلية","J'ai vérifié ce chiffre") }}
          </label>
          <label class="flex items-center gap-2 text-[12px] text-ink-2 cursor-pointer">
            <input type="checkbox" v-model="fixRetro" class="accent-accent w-3.5 h-3.5" />
            🕰 {{ L("Retro — apply from the item's first 2026 receipt and heal past months (reposts its old moves)","رجعي — يتطبق من أول استلام في 2026 ويصلح الشهور اللي فاتت (بيعيد حساب حركاته القديمة)","Rétro — depuis la première réception 2026") }}
          </label>
          <button class="h-[30px] px-3.5 rounded-[8px] text-[11.5px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand disabled:opacity-50"
                  :disabled="!canSubmit || fixing"
                  :title="!canSubmit ? submitBlockReason : ''"
                  @click="applyFix">
            {{ fixing ? L("Applying…","جارٍ التطبيق…","…") : L("Submit","اعتماد","Soumettre") }} · <span class="tnum" dir="ltr">{{ fmtNum(appliedRate, 2) }}</span>
          </button>
        </div>
      </div>

      <!-- The cost ladder -->
      <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
        <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2">
          <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#eef6ff"><Icon name="layers" :size="14" color="#2563eb" /></span>
          <span class="text-[13px] font-bold">{{ L("Cost ladder — source → Morocco","سلّم التكلفة — المصدر → المغرب","Échelle du coût") }}</span>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-[12px]">
            <thead>
              <tr style="background:#fafaf9">
                <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Stage","المرحلة","Étape") }}</th>
                <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Company","الشركة","Société") }}</th>
                <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Document","المستند","Document") }}</th>
                <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Rate","السعر","Taux") }}</th>
                <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("→ MAD","→ MAD","→ MAD") }}</th>
                <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Δ vs true","Δ الحقيقة","Δ") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(h, i) in trace.ladder" :key="i" class="border-t border-line-hair" :style="rowStyle(h)">
                <td class="px-4 py-2.5 font-semibold whitespace-nowrap">{{ stageLabel(h.stage) }}</td>
                <td class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ h.company }}</td>
                <td class="px-4 py-2.5 font-mono text-[11px] whitespace-nowrap" dir="ltr">{{ h.name }}<div class="text-[10px] text-ink-muted font-sans">{{ h.date }}</div></td>
                <td class="px-4 py-2.5 text-end tnum whitespace-nowrap">{{ fmtNum(h.rate, 2) }} {{ h.currency }}<span v-if="h.conversion_rate" class="text-[10px] text-ink-muted"> @{{ h.conversion_rate }}</span></td>
                <td class="px-4 py-2.5 text-end tnum font-bold">{{ fmtNum(h.rate_mad, 2) }}</td>
                <td class="px-4 py-2.5 text-end tnum">
                  <span v-if="h.dev_pct != null" :style="{ color: devColor(h) }" class="font-semibold">{{ h.dev_pct > 0 ? "+" : "" }}{{ fmtNum(h.dev_pct) }}%</span>
                  <span v-else class="text-ink-muted">—</span>
                  <span class="ms-1.5 text-[13px]">{{ flagIcon(h.flag) }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="!trace.ladder.length" class="py-10 text-center text-[12px] text-ink-muted">{{ L("No purchase documents found for this product.","لا مستندات شراء لهذا المنتج.","Aucun document d'achat.") }}</div>
      </div>
    </div>

    <div v-else-if="!loading && !err" class="py-16 text-center text-[12px] text-ink-muted">
      {{ L("Search for a product to trace its cost across companies.","ابحث عن منتج لتتبّع تكلفته عبر الشركات.","Recherchez un produit.") }}
    </div>

    <!-- Bulk local apply — preview → confirm → waves -->
    <div v-if="lb" class="fixed inset-0 z-50 flex items-center justify-center p-4" style="background:rgba(28,25,23,.45)" @click.self="lb.posting ? null : (lb = null)">
      <div class="bg-white rounded-[16px] shadow-xl w-full max-w-[760px] max-h-[86vh] flex flex-col overflow-hidden">
        <div class="px-5 py-3.5 border-b border-line-hair flex items-center gap-2">
          <span class="text-[14px] font-bold">⚡ {{ L("Apply all local products","تطبيق كل المنتجات المحلية","Appliquer tous les produits locaux") }}</span>
          <span class="text-[11px] text-ink-muted flex-1">{{ L("invoice = full cost (no landed) · one reversible reco per item","الفاتورة = التكلفة الكاملة (بدون شحن) · تسوية مستقلة قابلة للعكس لكل صنف","facture = coût complet") }}</span>
          <button v-if="!lb.posting" class="text-ink-3 hover:text-ink text-[18px] leading-none" @click="lb = null">×</button>
        </div>

        <div v-if="lb.loading" class="py-14 text-center text-[12px] text-ink-muted">{{ L("Scanning the local catalogue…","بجهّز المعاينة…","Analyse…") }}</div>

        <template v-else>
          <div class="px-5 py-3 flex items-center gap-4 flex-wrap border-b border-line-hair text-[11.5px]">
            <span><b class="text-[15px] tnum">{{ lb.stats.ready }}</b> {{ L("ready","جاهز","prêts") }}</span>
            <span class="text-ink-muted">{{ L("weak basis (manual)","أساس ضعيف (يدوي)","base faible") }}: <b class="tnum">{{ lb.stats.weak_basis }}</b></span>
            <span class="text-ink-muted">{{ L("already fixed","متظبط","corrigés") }}: <b class="tnum">{{ lb.stats.already_fixed }}</b></span>
            <span class="flex-1"></span>
            <span>{{ L("net book change","صافي التغيير الدفتري","Δ net") }}:
              <b class="tnum" dir="ltr" :style="{ color: lb.total_delta > 0 ? '#b45309' : '#047857' }">{{ fmtNum(lb.total_delta) }} MAD</b></span>
          </div>

          <div class="flex-1 overflow-y-auto">
            <table class="w-full text-[11.5px]">
              <thead class="sticky top-0" style="background:#fafaf9">
                <tr>
                  <th class="px-4 py-2 text-start text-[10px] font-bold uppercase text-ink-muted">{{ L("Product","المنتج","Produit") }}</th>
                  <th class="px-3 py-2 text-end text-[10px] font-bold uppercase text-ink-muted">{{ L("Qty","كمية","Qté") }}</th>
                  <th class="px-3 py-2 text-end text-[10px] font-bold uppercase text-ink-muted">{{ L("Book","الدفاتر","Livre") }}</th>
                  <th class="px-3 py-2 text-end text-[10px] font-bold uppercase text-ink-muted">{{ L("Invoice","الفاتورة","Facture") }}</th>
                  <th class="px-3 py-2 text-end text-[10px] font-bold uppercase text-ink-muted">Δ MAD</th>
                  <th class="px-3 py-2 text-center text-[10px] font-bold uppercase text-ink-muted"></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="r in lb.rows" :key="r.item_code" class="border-t border-line-hair">
                  <td class="px-4 py-1.5 truncate max-w-[240px]"><span class="font-semibold">{{ r.sku || r.item_code }}</span><span class="text-[10px] text-ink-muted"> · {{ r.item_name }}</span></td>
                  <td class="px-3 py-1.5 text-end tnum text-ink-3">{{ fmtNum(r.qty) }}</td>
                  <td class="px-3 py-1.5 text-end tnum">{{ fmtNum(r.book_rate, 2) }}</td>
                  <td class="px-3 py-1.5 text-end tnum font-semibold text-emerald-700">{{ fmtNum(r.rate, 2) }}</td>
                  <td class="px-3 py-1.5 text-end tnum" dir="ltr" :style="{ color: r.delta > 0 ? '#b45309' : '#78716c' }">{{ fmtNum(r.delta) }}</td>
                  <td class="px-3 py-1.5 text-center text-[12px]">
                    <span v-if="lb.done[r.item_code] === 'ok'" class="text-emerald-700 font-bold">✓</span>
                    <span v-else-if="lb.done[r.item_code]" class="text-sale font-bold" :title="lb.done[r.item_code]">✕</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="px-5 py-3.5 border-t border-line-hair flex items-center gap-3">
            <template v-if="lb.posting">
              <div class="flex-1 h-[8px] rounded-full overflow-hidden" style="background:#f5f5f4">
                <div class="h-full rounded-full transition-all" style="background:#059669" :style="{ width: (lb.progress / Math.max(lb.stats.ready, 1) * 100) + '%' }"></div>
              </div>
              <span class="text-[11.5px] tnum text-ink-muted">{{ lb.progress }} / {{ lb.stats.ready }}</span>
            </template>
            <template v-else-if="lb.finished">
              <span class="text-[12px] font-bold text-emerald-700">✓ {{ L("Posted","اترحّل","Comptabilisé") }} {{ lb.posted }}</span>
              <span v-if="lb.failed" class="text-[12px] font-bold text-sale">· {{ L("failed","فشل","échoués") }} {{ lb.failed }}</span>
              <span v-if="lb.error" class="text-[11px] text-sale truncate max-w-[260px]">⚠ {{ lb.error }}</span>
              <span v-if="lb.draining" class="text-[11px] text-ink-muted">⏳ {{ L("reposting old moves…","بيعاد حساب الحركات القديمة…","recalcul en cours…") }}</span>
              <span class="flex-1"></span>
              <button class="h-[32px] px-4 rounded-[9px] text-[12px] font-bold border border-line hover:bg-app-warm" @click="lb = null">{{ L("Close","إغلاق","Fermer") }}</button>
            </template>
            <template v-else>
              <label class="flex items-center gap-1.5 text-[11.5px] text-ink-2 cursor-pointer">
                <input type="checkbox" v-model="lbRetro" class="accent-accent w-3.5 h-3.5" />
                🕰 {{ L("Retro from first 2026 receipt","رجعي من أول استلام 2026","Rétro 2026") }}
              </label>
              <span class="text-[11px] text-ink-muted flex-1">{{ L("Each item posts as its own Stock Reco — individually undoable from the Activity Log.","كل صنف بيترحّل بتسوية مستقلة — ليه Undo لوحده من سجل النشاط.","Chaque article est réversible individuellement.") }}</span>
              <button class="h-[32px] px-4 rounded-[9px] text-[12px] font-bold border border-line hover:bg-app-warm" @click="lb = null">{{ L("Cancel","إلغاء","Annuler") }}</button>
              <button class="h-[32px] px-4 rounded-[9px] text-[12px] font-bold text-white bg-brand hover:bg-brand-dark disabled:opacity-40"
                      :disabled="!lb.stats.ready" @click="runLocalBulk">
                {{ L("Post","ترحيل","Comptabiliser") }} {{ lb.stats.ready }}
              </button>
            </template>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useRoute } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import ServerPager from "@/components/ServerPager.vue";
import LandedBasisCard from "@/components/LandedBasisCard.vue";
import ShipmentCostSheet from "@/components/ShipmentCostSheet.vue";
import FreightChip from "@/components/FreightChip.vue";
import { useServerTable } from "@/composables/useServerTable";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useToast } from "@/composables/useToast";
import { useAuth } from "@/composables/useAuth";

const { locale } = useI18n();
const toast = useToast();
const { can } = useAuth();
const canWrite = computed(() => can("post_entries"));
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const fmtNum = (n, d = 0) => {
  const v = Number(n);
  if (!isFinite(v)) return "—";
  return v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
};
const M = "accounting_portal.api.cost_trace";

const route = useRoute();
const openPr = ref(route.query.pr || null);
const openPrYear = ref(route.query.year || null);

const q = ref("");
const results = ref([]);
const showResults = ref(false);
const trace = ref(null);
const loading = ref(false);
const err = ref("");

function hideResultsSoon() { setTimeout(() => { showResults.value = false; }, 200); }
let t = null;
function onSearch() {
  showResults.value = true;
  clearTimeout(t);
  const term = q.value.trim();
  if (term.length < 2) { results.value = []; return; }
  t = setTimeout(async () => {
    try { results.value = await api.call(`${M}.search_items`, { query: term }); }
    catch (e) { results.value = []; }
  }, 250);
}

// ── Verify & Fix (human-in-the-loop) ──
const V = "accounting_portal.api.valuation";
const fixPrev = ref(null);
const fixRate = ref(null);
const fixNote = ref("");
const fixConfirm = ref(false);
const fixRetro = ref(true);   // retro is the default: verified cost heals history too
const fixing = ref(false);
const SCM = "accounting_portal.api.shipment_costing";
const itemLanded = ref(null);
async function loadItemLanded(itemCode) {
  try { itemLanded.value = await api.call(`${SCM}.item_landed_detail`, { item_code: itemCode }, { fresh: true }); }
  catch (e) { itemLanded.value = null; }
}
async function confirmPrRate(r) {
  fixing.value = true;
  try {
    await api.call("accounting_portal.api.landed_prep.set_pr_rate", { pr: r.pr, rate: r._draft ?? r.band_rate });
    toast.success(L("Rate confirmed", "السعر اتعتمد", "Tarif confirmé"));
    await loadItemLanded(trace.value.item_code);
  } catch (e) { toast.error(e.message || "Failed"); }
  finally { fixing.value = false; }
}
const savedCost = computed(() => itemLanded.value?.sheet_cost ?? null);
const costDirty = computed(() =>
  fixRate.value > 0 && savedCost.value != null && Math.abs(fixRate.value - savedCost.value) > 0.009);
const canSubmit = computed(() =>
  fixConfirm.value && fixRate.value > 0 && itemLanded.value && !itemLanded.value.waiting.length
  && !fixPrev.value?.batch_tracked
  && !costDirty.value && !(fixRate.value > 0 && savedCost.value == null));
const submitBlockReason = computed(() => {
  if (itemLanded.value?.waiting?.length) return L("Waiting for freight — finish ②", "مستني شحن — كمّلوا ②", "Fret manquant (②)");
  if (costDirty.value || (fixRate.value > 0 && savedCost.value == null)) return L("Save the product cost first (①)", "احفظوا تكلفة المنتج الأول (①)", "Enregistrer d'abord (①)");
  if (!fixConfirm.value) return L("Tick the verification checkbox", "علّموا على مربع التحقق", "Cocher la case");
  return "";
});
async function saveItemCost() {
  fixing.value = true;
  try {
    const r = await api.call(`${SCM}.save_item_cost`, { item_code: trace.value.item_code, cost: fixRate.value, note: fixNote.value || undefined });
    if (r?.kept_different?.length) {
      toast.info(L(`Saved, but ${r.kept_different.length} shipment sheet(s) keep a DIFFERENT deliberate price — edit those in their shipment files`,
                   `اتحفظ، بس ${r.kept_different.length} شحنة محتفظة بسعر مختلف متعمد — عدّلوه من ملف الشحنة نفسه`,
                   "Enregistré ; certains prix par expédition diffèrent"));
    } else {
      toast.success(L("Saved — reflected in the shipment sheets too", "اتحفظ — وبيظهر في مسودات الشحنات كمان", "Enregistré"));
    }
    await loadItemLanded(trace.value.item_code);
  } catch (e) { toast.error(e.message || "Failed"); }
  finally { fixing.value = false; }
}
// the FULL rate that will actually be applied = verified product + LIVE landed
const appliedRate = computed(() => {
  const p = Number(fixRate.value) || 0;
  const l = Number(itemLanded.value?.landed_unit) || 0;
  return p > 0 ? Math.round((p + l) * 100) / 100 : 0;
});

async function pick(itemCode) {
  showResults.value = false;
  loading.value = true;
  err.value = "";
  trace.value = null;
  fixPrev.value = null; fixConfirm.value = false; fixNote.value = "";
  itemLanded.value = null; fixRate.value = null;
  try {
    trace.value = await api.call(`${M}.trace_item`, { item_code: itemCode });
    q.value = trace.value.sku || itemCode;
    fixPrev.value = await api.call(`${V}.item_fix_preview`, { company: currentCompany(), item_code: itemCode }, { fresh: true });
    await loadItemLanded(itemCode);
    // prefer the team's own bulk-sheet figure over the engine suggestion —
    // and NEVER prefill a near-zero figure (a missing FX conversion, not a price)
    const pf = itemLanded.value?.sheet_cost ?? fixPrev.value?.true_cost?.cost_mad ?? null;
    fixRate.value = pf != null && pf >= 0.5 ? pf : null;
  } catch (e) {
    err.value = e.message || "Failed to load trace";
  } finally {
    loading.value = false;
  }
}

async function applyFix() {
  if (fixing.value || !trace.value) return;
  fixing.value = true;
  try {
    const res = await api.call(`${SCM}.apply_item`, {
      item_code: trace.value.item_code,
      rate: fixRate.value, note: fixNote.value || undefined,
      retro: fixRetro.value ? 1 : 0,
    });
    if (res.status === "Posted") toast.success(fixRetro.value
      ? L("Cost fixed retroactively — old moves are reposting", "اتظبطت بأثر رجعي — الحركات القديمة بيعاد حسابها", "Corrigé rétroactivement")
      : L("Cost fixed — one today-dated entry posted", "اتظبطت — قيد واحد بتاريخ اليوم", "Corrigé"));
    else toast.info(res.status);
    fixPrev.value = await api.call(`${V}.item_fix_preview`, { company: currentCompany(), item_code: trace.value.item_code }, { fresh: true });
    ct.load();
    loadTower();
    api.call(`${M}.cost_overview`, {}, { fresh: true }).then((r) => { ov.value = r; }).catch(() => {});
    // drain AFTER the UI refreshed — the reco is already posted; this only
    // catches the GL up, so release the Submit spinner first
    if (res.status === "Posted" && fixRetro.value) {
      fixing.value = false;
      await drainReposts();
    }
  } catch (e) { toast.error(e.message || "Failed"); }
  finally { fixing.value = false; }
}

// ── Catalogue overview + worklist table ──
const ov = ref(null);
const srcFilter = ref("");
const supFilter = ref("");
const moFilter = ref("");
const fixFilter = ref("");
const filters = ref({ suppliers: [], months: [] });
api.call(`${M}.cost_overview`, {}).then((r) => { ov.value = r; }).catch(() => {});
api.call(`${M}.cost_filters`, {}).then((r) => { filters.value = r; }).catch(() => {});
const ct = useServerTable(
  (params) => api.call(`${M}.cost_table`, {
    source: srcFilter.value || undefined,
    supplier: supFilter.value || undefined,
    month: moFilter.value || undefined,
    fix_status: fixFilter.value || undefined,
    ...params,
  }),
  { pageSize: 50 });
ct.load();
watch([srcFilter, supFilter, moFilter, fixFilter], () => { ct.page.value = 1; ct.load(); });
// retro applies leave Repost jobs Queued (the known scheduler gotcha) — drain
// them synchronously in short budgeted calls until the ledger has caught up
async function drainReposts() {
  for (let i = 0; i < 12; i++) {
    try {
      const r = await api.call(`${V}.drain_reposts`, { budget_s: 45 }, { fresh: true });
      if (!r.remaining) return true;
    } catch (e) { toast.error(e.message || "Repost drain failed"); return false; }
  }
  toast.info(L("Reposts still running — they'll finish in the background", "إعادة الحساب لسه شغالة — هتكمل في الخلفية", "Recalcul en cours"));
  return false;
}

// ── Bulk local apply — preview (dry_run) → confirm → post in waves ──
const lb = ref(null);
const lbRetro = ref(true);
async function openLocalBulk() {
  lb.value = { loading: true, rows: [], stats: {}, total_delta: 0, posting: false, finished: false, progress: 0, posted: 0, failed: 0, done: {} };
  try {
    const r = await api.call(`${M}.apply_local_batch`, { dry_run: 1 }, { fresh: true });
    lb.value = { ...lb.value, loading: false, rows: r.rows, stats: r.stats, total_delta: r.total_delta };
  } catch (e) { toast.error(e.message || "Failed"); lb.value = null; }
}
async function runLocalBulk() {
  if (!lb.value || lb.value.posting) return;
  lb.value.posting = true;
  let exhausted = true;
  try {
    // waves of 25 so one long request never times out; the server re-scans each
    // wave, so anything already fixed simply drops out of the next one
    for (let guard = 0; guard < 40; guard++) {
      const r = await api.call(`${M}.apply_local_batch`, { dry_run: 0, limit: 25, retro: lbRetro.value ? 1 : 0 }, { fresh: true });
      // a failed item stays "ready" on the server and reappears next wave —
      // count each item once (a retry that succeeds moves failed → posted),
      // and stop when a wave makes no forward progress
      for (const p of r.posted) {
        const prev = lb.value.done[p.item_code];
        if (!prev) lb.value.posted++;
        else if (prev !== "ok") { lb.value.failed--; lb.value.posted++; }
        lb.value.done[p.item_code] = "ok";
      }
      for (const s of r.skipped) { if (!lb.value.done[s.item_code]) lb.value.failed++; lb.value.done[s.item_code] = s.reason || "failed"; }
      lb.value.progress = lb.value.posted + lb.value.failed;
      if (!r.posted.length || !r.remaining) { exhausted = false; break; }
    }
    if (exhausted) toast.info(L("Stopped at the wave cap — reopen to continue the rest", "وقفنا عند حد الدفعات — افتحوه تاني لتكملة الباقي", "Limite atteinte — rouvrir pour continuer"));
    toast.success(L(`Posted ${lb.value?.posted ?? 0} item(s)`, `اترحّل ${lb.value?.posted ?? 0} صنف`, `${lb.value?.posted ?? 0} comptabilisés`));
  } catch (e) { toast.error(e.message || "Failed"); if (lb.value) lb.value.error = e.message || "Failed"; }
  finally {
    // refresh even after a mid-run failure — earlier waves DID post
    ct.load();
    api.call(`${M}.cost_overview`, {}, { fresh: true }).then((r) => { ov.value = r; }).catch(() => {});
    loadTower();
    if (lb.value) { lb.value.posting = false; lb.value.finished = true; lb.value.draining = lbRetro.value; }
    if (lbRetro.value) { await drainReposts(); if (lb.value) lb.value.draining = false; }
  }
}

// a Turkish supplier name can be very long — trim for chips/cells
const shortSup = (s) => (s ? String(s).replace(/\s*(T[İI]C\.?|SAN\.?|LTD\.?|Ş[Tt][İI]\.?|A\.?Ş\.?|İMALAT).*$/i, "").trim().slice(0, 22) || String(s).slice(0, 22) : "");

// ── Cost Control Tower: the 5-step process status ──
const tower = ref(null);
async function loadTower() {
  try { tower.value = await api.call(`${M}.control_tower`, { company: currentCompany() }, { fresh: true }); }
  catch (e) { tower.value = null; }
}
loadTower();

const steps = computed(() => {
  const t = tower.value;
  if (!t) return [];
  const s1 = t.guard.enabled ? "done" : "active";
  const fr = t.freight || { costed: 0, total: 0 };
  const s2 = fr.total > 0 && fr.costed >= fr.total ? "done" : (t.guard.enabled ? "active" : "locked");
  const crawlDone = t.crawl.total > 0 && t.crawl.fixed >= t.crawl.total;
  const s3 = crawlDone ? "done" : "active";   // item fixes gate per-item, not on freeze
  const tuDone = t.trueup.closable_months > 0 && t.trueup.posted_months.length >= t.trueup.closable_months;
  const s4 = !t.basis ? "locked" : (tuDone ? "done" : "active");
  const s5 = t.close2025.done ? "done" : (s4 === "done" ? "active" : "locked");
  return [
    { label: L("Secure the source", "أمّن المنبع", "Source"), state: s1 },
    { label: L("Freight per shipment", "شحن الشحنات", "Fret/expédition") + ` ${fr.costed}/${fr.total}`, state: s2 },
    { label: L("Verify & apply costs", "تحقق وتطبيق التكاليف", "Vérifier & appliquer"), state: s3 },
    { label: L("Monthly true-ups", "التسوية الرجعية", "Régularisations"), state: s4 },
    { label: L("Closings", "الإقفالات", "Clôtures"), state: s5 },
  ];
});
const nextHint = computed(() => {
  const t = tower.value;
  if (!t) return "";
  if (!t.guard.enabled) return L("Next: turn the FX guard ON (Super Admin).", "التالي: شغّل حارس الصرف (Super Admin).", "Activer la garde FX.");
  const fr = t.freight || { costed: 0, total: 0 };
  if (fr.total > 0 && fr.costed < fr.total) return L(`Next (②): cost the freight of ${fr.total - fr.costed} shipment(s) — confirm air rates / attach sea bills (Purchases → Shipments or the product page).`, `التالي (②): كمّلوا شحن ${fr.total - fr.costed} شحنة — اعتماد سعر الجوي / إرفاق فواتير البحري (المشتريات → الشحنات أو صفحة المنتج).`, "Coster le fret des expéditions (②).");
  if (t.crawl.fixed < t.crawl.total) return L(`Next (③): verify & apply — ${fmtNum(t.crawl.total - t.crawl.fixed)} products left (${fmtNum(t.crawl.remaining_over)} MAD distortion) — product page or shipment files.`, `التالي (③): تحقق وتطبيق — فاضل ${fmtNum(t.crawl.total - t.crawl.fixed)} منتج (${fmtNum(t.crawl.remaining_over)} درهم تشوّه) — من صفحة المنتج أو ملفات الشحنات.`, "Vérifier & appliquer (③).");
  if (!t.basis) return L("Next (④): freeze the landed basis (card below) to unlock the monthly true-ups.", "التالي (④): جمّدوا أساس الشحن (الكارت تحت) لفتح تسويات الشهور.", "Geler la base pour les régularisations (④).");
  if (t.trueup.posted_months.length < t.trueup.closable_months) return L("Next: post the monthly true-ups (④).", "التالي: رحّلوا تسويات الشهور (④).", "Poster les régularisations (④).");
  if (!t.close2025.done) return L("Next: settle the 3 open decisions and execute the 2025 close (⑤).", "التالي: احسموا القرارات الثلاثة ونفّذوا قفل 2025 (⑤).", "Clôturer 2025 (⑤).");
  return L("All steps complete — costs are clean and protected. 🎉", "كل الخطوات خلصت — التكاليف نضيفة ومحمية. 🎉", "Terminé. 🎉");
});

// ── B6: monthly COGS true-up ──
const TU = "accounting_portal.api.cogs_trueup";
const tu = ref(null);
const tuOpen = ref(false);
const tuBusy = ref("");
async function loadTu() {
  try { tu.value = await api.call(`${TU}.monthly_review`, { company: currentCompany() }, { fresh: true }); }
  catch (e) { tu.value = null; }
}
loadTu();
async function postTrueup(r) {
  if (!window.confirm(L(
    `Post the ${r.month} true-up? COGS ${fmtNum(r.booked)} → ${fmtNum(r.true)} (Δ ${fmtNum(r.delta)}). GL-only, reversible.`,
    `ترحيل تسوية ${r.month}؟ COGS ${fmtNum(r.booked)} → ${fmtNum(r.true)} (Δ ${fmtNum(r.delta)}). قيد GL فقط وقابل للعكس.`,
    `Poster la régularisation ${r.month} ?`))) return;
  tuBusy.value = r.month;
  try {
    const res = await api.call(`${TU}.post_trueup`, { company: currentCompany(), year: tu.value.year, month: Number(r.month.split("-")[1]) });
    if (res.status === "Posted") toast.success(L("True-up posted","اترحّلت التسوية","Posté"));
    else toast.info(res.status);
    await loadTu();
    loadTower();
  } catch (e) { toast.error(e.message || "Failed"); }
  finally { tuBusy.value = ""; }
}

const SRC = {
  maslak_pi: [L("Maslak", "Maslak", "Maslak"), "background:#ecfdf5;color:#047857"],
  local_pi: [L("Local", "محلي", "Local"), "background:#fff7ed;color:#c2410c"],
  morocco_pr: [L("Morocco", "مغرب", "Maroc"), "background:#eff6ff;color:#2563eb"],
  unpriced: [L("unpriced", "بلا سعر", "sans prix"), "background:#fffbeb;color:#b45309"],
};
const srcShort = (s) => (SRC[s] ? SRC[s][0] : s);
const srcChip = (s) => (SRC[s] ? SRC[s][1] : "");

const srcLabel = computed(() => ({
  maslak_pi: L("Maslak invoice", "فاتورة Maslak", "Facture Maslak"),
  local_pi: L("Local supplier invoice", "فاتورة مورد محلي", "Facture fournisseur local"),
  morocco_pr: L("Morocco receipt", "استلام المغرب", "Réception Maroc"),
  orphan: L("no source", "بلا مصدر", "sans source"),
  fx_unavailable: L("no FX rate", "بلا سعر صرف", "sans taux"),
}[trace.value?.true_cost?.source] || ""));
const srcColor = computed(() => (
  trace.value?.true_cost?.source === "maslak_pi" ? "text-emerald-700"
    : ["orphan", "fx_unavailable"].includes(trace.value?.true_cost?.source) ? "text-amber-600" : "text-ink-3"));
const distColor = computed(() => {
  const d = trace.value?.distortion_pct;
  if (d == null) return "#78716c";
  return Math.abs(d) < 15 ? "#047857" : Math.abs(d) < 60 ? "#b45309" : "#b91c1c";
});

const stageLabels = {
  source_po: L("① PO (source)", "① أمر شراء", "① Commande"),
  source_pr: L("② Receipt (source)", "② استلام (مصدر)", "② Réception"),
  source_pi: L("③ Invoice (source) ⭐", "③ فاتورة (مصدر) ⭐", "③ Facture ⭐"),
  transfer_paper: L("④ Transfer (paper)", "④ تحويل (ورقي)", "④ Transfert"),
  dest_pr: L("⑤ Receipt (Morocco)", "⑤ استلام (المغرب)", "⑤ Réception Maroc"),
};
const stageLabel = (s) => stageLabels[s] || s;
const flagIcon = (f) => ({ ok: "✅", inflated: "🔴", low: "🔵", no_basis: "⚪" }[f] || "");
const devColor = (h) => (h.flag === "inflated" ? "#b91c1c" : h.flag === "low" ? "#2563eb" : "#047857");
function rowStyle(h) {
  if (h.stage === "source_pi") return { background: "#f0fdf4" };
  if (h.stage === "transfer_paper") return { background: "#fffbeb" };
  return {};
}
</script>
