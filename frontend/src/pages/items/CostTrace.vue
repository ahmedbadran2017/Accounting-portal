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
        <input v-model="q" @input="onSearch" @focus="onSearch"
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
      <button class="text-[11.5px] font-semibold text-brand hover:underline inline-flex items-center gap-1" @click="openPr = null; loadReady(); loadTower();">
        <Icon name="arrow" :size="12" class="rtl:rotate-180" />{{ L("Back to catalogue","رجوع للكتالوج","Retour") }}
      </button>
      <ShipmentCostSheet :pr="openPr" @saved="loadReady" />
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
        <div class="text-[11px] text-ink-muted mt-1.5">{{ nextHint }}</div>
      </div>

      <!-- ① secure the source -->
      <div v-if="tower" class="bg-white border rounded-[14px] shadow-card px-4 py-3 flex items-center gap-2 flex-wrap"
           :style="tower.guard.enabled ? 'border-color:#a7f3d0' : 'border-color:#fecaca'">
        <span class="text-[13px] font-bold">① {{ L("Secure the source","أمّن المنبع","Sécuriser la source") }}</span>
        <span v-if="tower.guard.enabled" class="text-[10.5px] font-bold px-2 py-0.5 rounded-full" style="background:#ecfdf5;color:#047857">
          {{ L("FX guard ON","حارس الصرف شغّال","Garde FX ON") }} · ±{{ Math.round(tower.guard.tolerance * 100) }}%
        </span>
        <span v-else class="text-[10.5px] font-bold px-2 py-0.5 rounded-full" style="background:#fef2f2;color:#b91c1c">{{ L("FX guard OFF!","الحارس متوقف!","OFF!") }}</span>
        <span class="text-[11px] text-ink-muted flex-1">{{ L("Every new purchase document with an implausible exchange rate is rejected at entry — no new contamination.","أي مستند شراء جديد بسعر صرف غلط بيترفض لحظة الإدخال — مفيش تلوّث جديد.","Tout document au taux invraisemblable est rejeté.") }}</span>
      </div>

      <!-- ② freeze the landed basis — the day-to-day work happens in the
           PR-centric Shipments workspace; this card stays as the recon/freeze view -->
      <router-link to="/accounting/purchases/shipments"
                   class="block bg-white border rounded-[14px] shadow-card px-4 py-3 hover:bg-app-warm" style="border-color:#c7d2fe">
        <span class="text-[12px] font-bold">📦 {{ L("Freight assembly (Purchases → Shipments)","تجميع الشحن (المشتريات → الشحنات)","Assemblage du fret") }}</span>
        <span class="text-[11px] text-ink-muted ms-2">{{ L("attach each shipment's freight bills there; once a shipment's freight is actual it appears below, ready for product-cost verification HERE.",
             "ارفقوا فواتير شحن كل شحنة هناك؛ أول ما شحن الشحنة يبقى فعلي بتظهر تحت هنا جاهزة للتحقق من تكلفة البضاعة.",
             "Joindre les factures là-bas ; la vérification se fait ici.") }}</span>
        <span class="text-[12px] font-bold text-accent-dark ms-2">→</span>
      </router-link>
      <div v-if="readyPrs.length" class="bg-white border rounded-[14px] shadow-card px-4 py-3" style="border-color:#a7f3d0">
        <div class="text-[12px] font-bold mb-1.5">🧾 {{ L("Shipment files — bulk verification","ملفات الشحنات — تحقق مجمّع","Dossiers d'expédition") }} ({{ readyPrs.length }})
          <span class="text-[10.5px] text-ink-muted font-normal ms-1">{{ L("open a file to verify all its lines at once + confirm its freight","افتحوا الملف للتحقق من كل سطوره مرة واحدة + اعتماد شحنه","vérification groupée") }}</span>
        </div>
        <div class="flex gap-1.5 flex-wrap">
          <button v-for="r in readyPrs.slice(0, 12)" :key="r.name"
                  class="inline-flex items-center gap-1.5 text-[11px] border border-line rounded-[8px] px-2 py-1 hover:bg-app-warm"
                  @click="openPr = r.name">
            <span class="font-mono text-[10.5px]" dir="ltr">{{ r.name }}</span>
            <span>{{ r.channel === "air" ? "🛫" : "🚢" }}</span>
            <span class="tnum text-ink-muted">{{ r.n_verified }}/{{ r.n_lines }}</span>
          </button>
          <span v-if="readyPrs.length > 12" class="text-[10.5px] text-ink-muted self-center">+{{ readyPrs.length - 12 }}</span>
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
            <option value="morocco_pr">{{ L("Morocco-direct","مغرب مباشر","Maroc") }}</option>
            <option value="unpriced">{{ L("Unpriced","بلا سعر","Sans prix") }}</option>
          </select>
          <select v-model="fixFilter" class="h-[28px] text-[11.5px] px-2 rounded-[8px] border border-line">
            <option value="">{{ L("All statuses","كل الحالات","Tous") }}</option>
            <option value="pending">{{ L("Pending review","في انتظار المراجعة","En attente") }}</option>
            <option value="fixed">{{ L("Fixed ✓","متظبطة ✓","Corrigés ✓") }}</option>
          </select>
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
                  {{ r.repolluted ? "⚠️" : (r.fixed ? "✅" : "") }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="!ct.loading.value && !ct.rows.value.length && !ct.error.value" class="py-10 text-center text-[12px] text-ink-muted">{{ L("No items.","لا أصناف.","Aucun.") }}</div>
        <ServerPager :t="ct" />
      </div>

      <LandedBasisCard @changed="loadTower(); loadTu();" />

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
                  <span v-if="r.posted" class="text-[10.5px] font-bold" :class="r.posted.stale_basis ? 'text-amber-600' : 'text-emerald-700'">{{ r.posted.stale_basis ? '⚠' : '✅' }} {{ r.posted.voucher_no }}<template v-if="r.posted.stale_basis"> · {{ L("basis changed — revert & re-post","الأساس اتغيّر — اعكسوه ورحّلوه تاني","base modifiée") }}</template></span>
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
                 "Plan: docs/CLOSE_2025_PLAN.md.") }}
          </span>
        </div>
      </div>
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

      <!-- Verification & Fix (human-in-the-loop) -->
      <div v-if="fixPrev" class="bg-white border rounded-[14px] shadow-card overflow-hidden" :style="fixPrev.fixed ? 'border-color:#a7f3d0' : 'border-color:#fde68a'">
        <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2">
          <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" :style="fixPrev.fixed ? 'background:#ecfdf5' : 'background:#fffbeb'">
            <Icon :name="fixPrev.fixed ? 'check' : 'shield'" :size="14" :color="fixPrev.fixed ? '#047857' : '#b45309'" />
          </span>
          <span class="text-[13px] font-bold">{{ fixPrev.fixed ? L("Cost verified & fixed","التكلفة متحققة ومتظبطة","Coût vérifié") : L("Verify & fix this product's cost","تحقق وظبّط تكلفة المنتج","Vérifier & corriger") }}</span>
          <span v-if="fixPrev.fixed" class="text-[11px] text-ink-muted">{{ fixPrev.fixed.voucher_no }} · {{ String(fixPrev.fixed.posted_on || "").slice(0,16) }}</span>
        </div>
        <div class="p-4 space-y-3">
          <!-- Evidence -->
          <div>
            <div class="text-[11px] font-bold text-ink-2 mb-1.5">① {{ L("Product cost — evidence from the actual purchase documents","تكلفة المنتج — الدليل من مستندات الشراء الفعلية","① Coût produit — preuves") }}</div>
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
                  <td class="px-3 py-1.5 font-mono text-[10.5px]">{{ e.doc }}<span class="text-ink-muted font-sans"> · {{ e.dt }}</span></td>
                  <td class="px-3 py-1.5 truncate max-w-[140px]">{{ shortSup(e.supplier) }}</td>
                  <td class="px-3 py-1.5 text-end tnum">{{ fmtNum(e.qty) }}</td>
                  <td class="px-3 py-1.5 text-end tnum font-semibold">{{ fmtNum(e.rate, 2) }} {{ e.cur }}</td>
                  <td class="px-3 py-1.5 text-end tnum font-bold" :class="e.rate_mad >= 0.5 ? 'text-emerald-700' : 'text-sale'">
                    {{ fmtNum(e.rate_mad, 2) }}<span v-if="e.rate_mad < 0.5" :title="L('FX conversion missing for this date/currency — figure unusable','تحويل العملة ناقص للتاريخ/العملة دي — الرقم غير صالح','Conversion FX manquante')"> ⚠</span></td>
                </tr>
              </tbody>
            </table>
            <div v-if="!fixPrev.evidence.length" class="text-[11px] text-amber-700 mt-1">{{ L("No purchase documents — enter the verified cost manually below (a note is required).","مفيش مستندات شراء — أدخل التكلفة المتحققة يدويًا (النوت إجباري).","Aucun document — saisir manuellement.") }}</div>
          </div>
          <!-- ② the item's shipments → live landed -->
          <div v-if="itemLanded">
            <div class="text-[11px] font-bold text-ink-2 mb-1.5">② {{ L("Freight — this product's shipments","الشحن — شحنات المنتج ده","② Fret — ses expéditions") }}
              <b v-if="itemLanded.complete" class="tnum ms-1" style="color:#047857">= {{ fmtNum(itemLanded.landed_unit, 2) }} / {{ L("unit","وحدة","unité") }}</b>
            </div>
            <div v-if="itemLanded.receipts.length" class="border border-line rounded-[8px] overflow-hidden max-h-[190px] overflow-y-auto">
              <table class="w-full text-[11.5px]">
                <tbody>
                  <tr v-for="r in itemLanded.receipts" :key="r.pr" class="border-t border-line-hair first:border-0">
                    <td class="px-3 py-1.5 font-mono text-[10.5px] whitespace-nowrap" dir="ltr">{{ r.pr }}<div class="text-[10px] text-ink-muted font-sans">{{ r.dt }}</div></td>
                    <td class="px-3 py-1.5 text-center">{{ r.channel === "air" ? "🛫" : "🚢" }}</td>
                    <td class="px-3 py-1.5 text-end tnum">{{ fmtNum(r.qty) }} {{ L("pcs","قطعة","pcs") }}</td>
                    <td class="px-3 py-1.5">
                      <span v-if="['bills','rate'].includes(r.source)" class="text-[9.5px] font-bold px-1.5 py-0.5 rounded-full" style="background:#ecfdf5;color:#047857">
                        {{ L("actual","فعلي","réel") }} @{{ r.rate_kg }}/kg</span>
                      <template v-else-if="r.channel === 'air' && canWrite && !itemLanded.frozen">
                        <input type="number" step="1" min="0" v-model.number="r._draft" :placeholder="String(r.band_rate || '')"
                               class="w-[62px] h-[24px] px-1.5 text-end tnum text-[11px] border border-amber-300 rounded-[6px] outline-none" />
                        <button class="ms-1 text-[10.5px] font-bold px-2 py-0.5 rounded-[6px] text-white bg-brand hover:bg-brand-dark disabled:opacity-50"
                                :disabled="!( (r._draft ?? r.band_rate) > 0 ) || fixing" @click="confirmPrRate(r)">✓ {{ L("confirm rate","اعتماد السعر","confirmer") }}</button>
                      </template>
                      <span v-else class="text-[9.5px] font-bold px-1.5 py-0.5 rounded-full" style="background:#fef2f2;color:#b91c1c">
                        {{ L("bills missing — attach in Shipments","الفواتير ناقصة — ارفقوها في الشحنات","factures manquantes") }}</span>
                    </td>
                    <td class="px-3 py-1.5 text-end tnum font-semibold">{{ r.share ? fmtNum(r.share) : "—" }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-else class="text-[11px] text-ink-muted">{{ L("No import shipments this year — landed = 0 (manual-cost product).","مفيش شحنات استيراد السنة دي — الشحن = 0 (منتج بتكلفة يدوية).","Aucune expédition — fret 0.") }}</div>
          </div>
          <!-- Impact preview -->
          <div v-if="fixPrev.bins.length">
            <div class="text-[11px] font-bold text-ink-2 mb-1.5">③ {{ L("Summary & impact — every bin moves to the full cost (one today-dated entry)","الملخص والأثر — كل المخازن تتظبط بالتكلفة الكاملة (قيد واحد بتاريخ اليوم)","③ Résumé & impact") }}</div>
            <div class="border border-line rounded-[8px] overflow-hidden max-h-[190px] overflow-y-auto">
              <table class="w-full text-[11.5px]">
                <tbody>
                  <tr v-for="b in fixPrev.bins" :key="b.warehouse" class="border-t border-line-hair first:border-0" :style="(b.reserved || b.disabled) ? 'opacity:.55' : ''">
                    <td class="px-3 py-1.5 truncate max-w-[180px]">{{ b.warehouse }}
                      <span v-if="b.reserved" class="ms-1 text-[9.5px] font-bold px-1.5 py-0.5 rounded-full" style="background:#fffbeb;color:#b45309">{{ b.reserved }} {{ L("reserved — skipped","محجوز — هيتعدّى","réservé") }}</span>
                      <span v-else-if="b.disabled" class="ms-1 text-[9.5px] font-bold px-1.5 py-0.5 rounded-full" style="background:#f5f5f4;color:#78716c">{{ L("disabled wh — skipped","مخزن موقوف — هيتعدّى","désactivé") }}</span>
                    </td>
                    <td class="px-3 py-1.5 text-end tnum text-ink-3">{{ fmtNum(b.qty) }}</td>
                    <td class="px-3 py-1.5 text-end tnum">{{ fmtNum(b.old_rate, 1) }} → <b>{{ (b.reserved || b.disabled) ? fmtNum(b.old_rate, 1) : fmtNum(appliedRate || b.new_rate, 1) }}</b></td>
                    <td class="px-3 py-1.5 text-end tnum font-semibold" :style="{ color: (b.delta || 0) < 0 ? '#b91c1c' : '#047857' }">{{ b.delta != null ? fmtNum(b.delta) : "—" }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="text-[11px] text-ink-3 mt-1">{{ L("Net inventory change","صافي تغيير المخزون","Δ stock") }}: <b class="tnum" :style="{ color: fixPrev.net_change < 0 ? '#b91c1c' : '#047857' }">{{ fmtNum(fixPrev.net_change) }}</b> MAD</div>
            <div v-if="fixPrev.skipped_reserved" class="text-[11px] text-amber-700 mt-0.5">
              ⚠ {{ L(`${fixPrev.skipped_reserved} bin(s) blocked (reserved stock / disabled warehouse) — skipped now; re-run the fix once the reservation ships or the warehouse is re-enabled.`,
                     `${fixPrev.skipped_reserved} مخزن متعطّل (حجز أوردرات / مخزن موقوف) — هيتعدّى دلوقتي؛ أعد الفيكس بعد فكّ الحجز أو تفعيل المخزن.`,
                     `${fixPrev.skipped_reserved} emplacement(s) bloqué(s) — ignorés.`) }}
            </div>
          </div>
          <!-- Confirm + fix -->
          <div v-if="canWrite && !fixPrev.fixed" class="pt-2 border-t border-line-hair space-y-2">
            <!-- ④ submit gate: every shipment of this item must be freight-costed -->
            <div v-if="itemLanded && itemLanded.waiting.length" class="rounded-[8px] border border-amber-200 bg-amber-50 text-amber-800 px-3 py-2 text-[11.5px]">
              🔒 {{ L("Waiting for freight of:","مستني شحن:","En attente du fret de :") }}
              <span class="font-mono text-[10.5px]" dir="ltr">{{ itemLanded.waiting.join(", ") }}</span>
              — {{ L("confirm the rate above (air) or attach the bills (Shipments) so the landed isn't understated.","اعتمدوا السعر فوق (جوي) أو ارفقوا الفواتير (الشحنات) علشان الشحن ما يتحسبش ناقص.","confirmer le tarif ou joindre les factures.") }}
            </div>
            <div class="flex items-center gap-2 flex-wrap">
              <label class="text-[11.5px] text-ink-2 font-semibold">{{ L("Verified product cost (MAD/unit)","تكلفة المنتج المتحققة (درهم/وحدة)","Coût produit vérifié") }}</label>
              <input v-model.number="fixRate" type="number" step="0.01" class="h-[30px] w-[110px] text-[12.5px] px-2 rounded-[8px] border border-line tnum" />
              <input v-model.trim="fixNote" :placeholder="L('Note (required if you change the figure)','ملاحظة (إجبارية لو غيّرت الرقم)','Note')"
                     class="h-[30px] flex-1 min-w-[180px] text-[12px] px-2 rounded-[8px] border border-line" />
            </div>
            <div v-if="itemLanded && !itemLanded.waiting.length" class="text-[12px] tnum bg-app-warm/60 rounded-[8px] px-3 py-2">
              {{ L("Product","منتج","Produit") }} <b>{{ fmtNum(fixRate || 0, 2) }}</b>
              + {{ L("landed","شحن","landed") }} <b>{{ fmtNum(itemLanded.landed_unit, 2) }}</b>
              <span class="text-ink-muted">({{ itemLanded.receipts.length }} {{ L("shipment(s)","شحنة","exp.") }})</span>
              = <b class="text-emerald-700">{{ fmtNum(appliedRate, 2) }} {{ L("applied","المعتمد","appliqué") }}</b>
            </div>
            <label class="flex items-center gap-2 text-[12px] text-ink-2 cursor-pointer">
              <input type="checkbox" v-model="fixConfirm" class="accent-accent w-3.5 h-3.5" />
              {{ L("I verified this figure against the actual supplier invoice","اتحققت من الرقم ده من فاتورة المورّد الفعلية","J'ai vérifié ce chiffre") }}
            </label>
            <button class="h-[32px] px-4 rounded-[8px] text-[12px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand disabled:opacity-50"
                    :disabled="!fixConfirm || fixing || !(fixRate > 0) || !itemLanded || itemLanded.waiting.length > 0" @click="applyFix">
              🚀 {{ fixing ? L("Applying…","جارٍ التطبيق…","…") : L("④ Submit — apply full cost","④ الاعتماد النهائي — تطبيق التكلفة الكاملة","④ Soumettre") }}
            </button>
          </div>
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
                <td class="px-4 py-2.5 font-mono text-[11px] whitespace-nowrap">{{ h.name }}<div class="text-[10px] text-ink-muted font-sans">{{ h.date }}</div></td>
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
const readyPrs = ref([]);
async function loadReady() {
  try {
    const d = await api.call("accounting_portal.api.shipment_costing.shipments", { company: currentCompany() }, { fresh: true });
    readyPrs.value = (d.rows || []).filter((r) => r.n_verified < r.n_lines || !["bills", "rate"].includes(r.freight.source));
  } catch (e) { readyPrs.value = []; }
}
loadReady();

const q = ref("");
const results = ref([]);
const showResults = ref(false);
const trace = ref(null);
const loading = ref(false);
const err = ref("");

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
    });
    if (res.status === "Posted") toast.success(L("Cost fixed — one today-dated entry posted", "اتظبطت — قيد واحد بتاريخ اليوم", "Corrigé"));
    else toast.info(res.status);
    fixPrev.value = await api.call(`${V}.item_fix_preview`, { company: currentCompany(), item_code: trace.value.item_code }, { fresh: true });
    ct.load();
    loadTower();
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
  morocco_pr: [L("Morocco", "مغرب", "Maroc"), "background:#eff6ff;color:#2563eb"],
  unpriced: [L("unpriced", "بلا سعر", "sans prix"), "background:#fffbeb;color:#b45309"],
};
const srcShort = (s) => (SRC[s] ? SRC[s][0] : s);
const srcChip = (s) => (SRC[s] ? SRC[s][1] : "");

const srcLabel = computed(() => ({
  maslak_pi: L("Maslak invoice", "فاتورة Maslak", "Facture Maslak"),
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
