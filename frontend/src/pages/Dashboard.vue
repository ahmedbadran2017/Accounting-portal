<template>
  <!-- Holding shows a genuine group rollup, not the Morocco COD cockpit. -->
  <Consolidated v-if="entityId === 'group'" />

  <div v-else class="space-y-3.5">
    <DashboardSkeleton v-if="!loaded" />
    <template v-else>
    <!-- Entity banner (non-Morocco) — shown first to set context -->
    <div v-if="vm.entityBanner" class="rounded-[14px] p-4 border" style="background:#fffbeb;border-color:#fde68a">
      <div class="flex flex-wrap items-center gap-x-6 gap-y-2">
        <div class="min-w-0">
          <div class="text-[13px] font-bold text-amber-900">{{ vm.entityBanner.name }} · {{ vm.entityBanner.ccy }}</div>
          <div class="text-[11.5px] text-amber-800/80 max-w-xl">{{ vm.entityBanner.role }}</div>
        </div>
        <div class="flex items-center gap-5 ms-auto">
          <div v-for="f in vm.entityBanner.figs" :key="f.label" class="leading-tight">
            <div class="text-[10px] text-amber-700/80 uppercase tracking-wide">{{ f.label }}</div>
            <div class="text-[14px] font-bold text-amber-900 tnum">{{ f.value }}</div>
          </div>
        </div>
      </div>
      <div class="text-[11px] text-amber-800/70 mt-2 pt-2 border-t border-amber-200">{{ vm.entityBanner.note }}</div>
    </div>

    <!-- Auditor digest banner -->
    <div class="rounded-[18px] px-5 py-[18px] text-white relative overflow-hidden"
         style="background:linear-gradient(115deg,#1e1b3a 0%,#2e1065 55%,#4c1d95 100%);box-shadow:0 14px 40px -16px rgba(76,29,149,.5)">
      <div class="absolute inset-0" style="background:radial-gradient(60% 120% at 88% -10%,rgba(167,139,250,.35),transparent 60%)"></div>
      <div class="relative flex items-start gap-3.5 flex-wrap">
        <span class="w-10 h-10 rounded-[11px] grid place-items-center flex-shrink-0"
              style="background:rgba(255,255,255,.13);border:1px solid rgba(255,255,255,.18)"><Icon name="shield" :size="20" color="#fff" /></span>
        <div class="flex-1 min-w-[240px]">
          <div class="flex items-center gap-2 flex-wrap">
            <span class="text-[14.5px] font-bold">{{ t("dash.auditor_name") }}</span>
            <span class="inline-flex items-center gap-1.5 text-[10px] font-bold px-2 py-0.5 rounded-full" style="background:rgba(167,139,250,.25);color:#ddd6fe">
              <span class="w-[5px] h-[5px] rounded-full bg-violet-400 animate-pulse"></span>{{ t("dash.auditing") }}
            </span>
            <span v-if="isLive" class="inline-flex items-center gap-1.5 text-[10px] font-bold px-2 py-0.5 rounded-full" style="background:rgba(52,211,153,.22);color:#a7f3d0">
              <span class="w-[5px] h-[5px] rounded-full bg-emerald-400"></span>Live{{ asOf ? " · " + asOf : "" }}
            </span>
          </div>
          <p class="text-[13px] mt-1.5 leading-relaxed max-w-2xl" style="color:#e9e3ff">{{ liveDigest }}</p>
        </div>
        <button class="h-9 px-4 rounded-[10px] bg-white text-[12.5px] font-bold inline-flex items-center gap-1.5"
                style="color:#5b21b6;box-shadow:0 4px 14px -4px rgba(0,0,0,.4)" @click="goCopilot">
          {{ t("dash.open_auditor") }}<Icon name="arrow" :size="14" class="rtl:rotate-180" />
        </button>
      </div>
      <div class="relative flex flex-wrap gap-2.5 mt-3.5">
        <button v-for="c in vm.digestChips" :key="c.label"
                class="inline-flex items-center gap-2 px-[11px] py-[7px] rounded-[10px] text-[11.5px] font-semibold text-start"
                style="background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.14)" @click="goChip(c)">
          <span class="w-1.5 h-1.5 rounded-full flex-shrink-0" :style="{ background: c.dot }"></span>{{ c.label }}
        </button>
      </div>
    </div>

    <!-- COD pipeline funnel -->
    <div v-if="cod.pipeline" class="grid grid-cols-2 lg:grid-cols-5 gap-3">
      <button v-for="b in funnel" :key="b.key" @click="goBucket(b.key)"
              class="relative bg-white rounded-[14px] border border-line p-3.5 shadow-card text-start overflow-hidden hover:-translate-y-0.5 hover:shadow-cardHover transition-all">
        <span class="absolute top-0 inset-x-0 h-[3px]" :style="{ background: b.color, opacity: .3 }"></span>
        <div class="flex items-center gap-2">
          <span class="w-8 h-8 rounded-[10px] grid place-items-center flex-shrink-0" :style="{ background: b.tint }"><Icon :name="b.icon" :size="15" :color="b.color" /></span>
          <span class="text-[10px] font-bold uppercase tracking-wider text-ink-muted leading-tight">{{ b.label }}</span>
        </div>
        <div class="text-[22px] font-extrabold tnum mt-1.5 leading-none" :style="{ color: b.color }">{{ (b.count || 0).toLocaleString() }}</div>
        <div class="text-[11px] text-ink-3 mt-1 tnum">{{ money(b.value) }} <span class="text-ink-muted">MAD</span></div>
      </button>
    </div>

    <!-- Carrier float + reconciliation (the collection gap) -->
    <div class="grid lg:grid-cols-[1fr_1fr] gap-3.5">
      <div class="relative bg-white rounded-[16px] border border-line p-[17px] shadow-card overflow-hidden">
        <div class="absolute -top-10 -end-10 w-28 h-28 rounded-full blur-2xl pointer-events-none" style="background:#be123c;opacity:.08"></div>
        <div class="relative flex items-center gap-2">
          <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#fef2f2"><Icon name="truck" :size="14" color="#be123c" /></span>
          <span class="text-[13px] font-bold">{{ L("Carrier float · uncollected","رصيد لدى الناقل · غير محصّل","Flottant transporteur") }}</span>
        </div>
        <div class="relative text-[28px] font-extrabold text-sale tnum mt-2.5 tracking-tight leading-none">{{ money(cod.carrier_float) }}<span class="text-[13px] text-ink-muted ms-1">MAD</span></div>
        <div class="relative text-[11.5px] text-ink-3 mt-2 leading-snug">{{ L("Cash for delivered orders that hasn't been reconciled yet — it's with Cathedis.","كاش طلبات مُسلّمة لسه ماتطابقش — لسه مع كاتدييس.","Encaisse livrée non rapprochée — chez Cathedis.") }}</div>
      </div>
      <div class="bg-white rounded-[16px] border border-line p-[17px] shadow-card flex flex-col">
        <div class="flex items-center gap-2">
          <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#e1f5ee"><Icon name="check" :size="14" color="#0f766e" /></span>
          <span class="text-[13px] font-bold">{{ L("Collection reconciled","نسبة التحصيل المطابَق","Encaissement rapproché") }}</span>
          <span class="ms-auto text-[20px] font-extrabold tnum" style="color:#0f766e">{{ Math.round(cod.reconciled_pct || 0) }}%</span>
        </div>
        <div class="h-2.5 rounded-full bg-app-warm overflow-hidden mt-3">
          <div class="h-full rounded-full transition-all" :style="{ width: Math.max(2, cod.reconciled_pct || 0) + '%', background: '#0f766e' }"></div>
        </div>
        <div class="text-[11.5px] text-ink-3 mt-2">{{ L("of delivered cash matched to remittances.","من كاش المُسلّم مطابق للتحويلات.","du livré rapproché.") }}</div>
        <button class="mt-auto inline-flex items-center justify-center gap-1.5 text-[12px] font-bold text-white bg-brand hover:bg-brand-dark px-3 py-2 rounded-chip shadow-brand mt-3" @click="goBucket('delivered')">
          <Icon name="trend" :size="14" />{{ L("Reconcile Cathedis file","مطابقة ملف كاتدييس","Rapprocher Cathedis") }}
        </button>
      </div>
    </div>

    <!-- KPI row -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <div v-for="(k, ki) in vm.kpis" :key="k.label"
           class="relative bg-white rounded-[16px] border border-line p-4 shadow-card overflow-hidden transition-all duration-200 hover:shadow-cardHover hover:-translate-y-[2px]">
        <!-- soft accent glow tinted to the metric -->
        <div class="absolute -top-10 -end-10 w-28 h-28 rounded-full blur-2xl pointer-events-none" :style="{ background: k.ic, opacity: 0.07 }"></div>
        <div class="relative flex items-center justify-between">
          <span class="text-[11.5px] font-semibold text-ink-3">{{ k.label }}</span>
          <span class="w-8 h-8 rounded-[10px] grid place-items-center shadow-sm" :style="{ background: k.ibg }"><Icon :name="k.icon" :size="16" :color="k.ic" /></span>
        </div>
        <div class="relative text-[27px] font-extrabold tracking-tight tnum mt-2.5 leading-none">
          {{ k.value }}<span class="text-[13px] text-ink-muted font-bold ms-0.5">{{ k.unit }}</span>
        </div>
        <div class="relative text-[10.5px] text-ink-muted mt-1.5">{{ k.sub }}</div>
        <!-- live sparkline -->
        <svg v-if="k.spark" class="relative block w-full h-[26px] mt-2.5" viewBox="0 0 100 26" preserveAspectRatio="none">
          <defs>
            <linearGradient :id="'kspark' + ki" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" :stop-color="k.ic" stop-opacity="0.20" />
              <stop offset="100%" :stop-color="k.ic" stop-opacity="0" />
            </linearGradient>
          </defs>
          <polygon :points="k.spark + ' 100,26 0,26'" :fill="'url(#kspark' + ki + ')'" />
          <polyline :points="k.spark" fill="none" :stroke="k.ic" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke" />
        </svg>
      </div>
    </div>

    <!-- Cash flow + Collection by channel -->
    <div class="grid lg:grid-cols-[1.5fr_1fr] gap-3.5">
      <!-- Cash flow chart -->
      <div class="bg-white rounded-[14px] border border-line p-[17px] shadow-card">
        <div class="flex items-baseline justify-between gap-2.5 flex-wrap">
          <div>
            <div class="text-[13.5px] font-bold">{{ vm.cashflow.title }}</div>
            <div class="text-[11px] text-ink-muted">{{ vm.cashflow.sub }}</div>
          </div>
          <div class="flex items-center gap-3 text-[11px] text-ink-2">
            <span class="inline-flex items-center gap-1.5"><span class="w-[9px] h-[9px] rounded-[3px]" style="background:#10b981"></span>{{ vm.cashflow.inLbl }}</span>
            <span class="inline-flex items-center gap-1.5"><span class="w-[9px] h-[9px] rounded-[3px]" style="background:#f59e0b"></span>{{ vm.cashflow.outLbl }}</span>
          </div>
        </div>
        <div class="flex items-end gap-[3px] h-20 mt-[18px]">
          <div v-for="d in vm.cashflow.days" :key="d.d" class="flex-1 flex flex-col justify-end gap-[2px] h-full" :title="d.title">
            <div class="rounded-t-[2px] origin-bottom animate-barGrow" :style="{ height: d.inH + 'px', background: 'linear-gradient(180deg,#34d399,#059669)' }"></div>
            <div class="rounded-b-[2px] origin-bottom animate-barGrow" :style="{ height: d.outH + 'px', background: 'linear-gradient(180deg,#fcd34d,#f59e0b)' }"></div>
          </div>
        </div>
        <div class="flex gap-6 mt-3.5 pt-3 border-t border-line-hair">
          <div>
            <div class="text-[10px] font-semibold text-ink-muted">{{ vm.cashflow.inLbl }}</div>
            <div class="text-[18px] font-bold text-success-dark tnum mt-px">{{ vm.cashflow.totalIn }}<span class="text-[11px] text-ink-muted ms-0.5">MAD</span></div>
          </div>
          <div>
            <div class="text-[10px] font-semibold text-ink-muted">{{ vm.cashflow.outLbl }}</div>
            <div class="text-[18px] font-bold text-amber-700 tnum mt-px">{{ vm.cashflow.totalOut }}</div>
          </div>
          <div>
            <div class="text-[10px] font-semibold text-ink-muted">{{ t("dash.net") }}</div>
            <div class="text-[18px] font-bold text-info tnum mt-px">{{ vm.cashflow.net }}</div>
          </div>
        </div>
      </div>

      <!-- Collection by channel -->
      <div class="bg-white rounded-[14px] border border-line p-[17px] shadow-card">
        <div class="text-[13.5px] font-bold">{{ vm.channelMeta.title }}</div>
        <div class="text-[11px] text-ink-muted">{{ vm.channelMeta.sub }}</div>
        <div class="flex flex-col gap-3 mt-[15px]">
          <div v-for="c in vm.channels" :key="c.name">
            <div class="flex items-center justify-between mb-1">
              <span class="inline-flex items-center gap-1.5 text-[12px] font-semibold text-ink-2 truncate">
                {{ c.name }}<Icon v-if="c.warn" name="alert" :size="12" color="#d97706" />
              </span>
              <span class="text-[11.5px] font-bold text-ink tnum">{{ c.share }}%</span>
            </div>
            <div class="h-[7px] rounded-[5px] bg-line-hair overflow-hidden">
              <div class="h-full rounded-[5px] animate-barGrow origin-left" :style="{ width: Math.max(c.share, 2.5) + '%', background: c.bar }"></div>
            </div>
            <div class="text-[10px] text-ink-muted mt-[3px] font-mono tnum">{{ c.sub }} · {{ c.amount }} MAD</div>
          </div>
        </div>
        <div class="flex gap-2 mt-3.5 px-3 py-2.5 rounded-[10px]" style="background:#fffbeb;border:1px solid #fde68a">
          <Icon name="alert" :size="13" color="#b45309" class="flex-shrink-0 mt-px" />
          <span class="text-[11px] leading-snug" style="color:#92400e">{{ vm.channelMeta.warn }}</span>
        </div>
      </div>
    </div>

    <!-- Sales & collections by order month (cohort mini) -->
    <div v-if="cod.cohort && cod.cohort.length" class="bg-white rounded-[14px] border border-line p-[17px] shadow-card">
      <div class="flex items-baseline justify-between gap-2 flex-wrap">
        <div>
          <div class="text-[13.5px] font-bold">{{ L("Sales & collections by order month","المبيعات والتحصيلات بشهر الطلب","Ventes & encaissements") }}</div>
          <div class="text-[11px] text-ink-muted">{{ L("revenue attributed to when the order was placed","الإيراد منسوب لوقت الطلب","produit par date de commande") }}</div>
        </div>
        <div class="flex items-center gap-3 text-[11px] text-ink-2">
          <span class="inline-flex items-center gap-1.5"><span class="w-[9px] h-[9px] rounded-[3px]" style="background:#0f766e"></span>{{ L("Invoiced","مفوتر","Facturé") }}</span>
          <span class="inline-flex items-center gap-1.5"><span class="w-[9px] h-[9px] rounded-[3px]" style="background:#7c3aed"></span>{{ L("Collected","محصّل","Encaissé") }}</span>
          <button class="text-[11px] font-semibold text-accent-dark hover:underline" @click="goReport">{{ L("Open report","افتح التقرير","Rapport") }} →</button>
        </div>
      </div>
      <div class="flex items-end gap-3 h-24 mt-4">
        <div v-for="m in cod.cohort" :key="m.month" class="flex-1 flex flex-col items-center gap-1">
          <div class="w-full flex items-end justify-center gap-[3px] h-full">
            <div class="w-1/2 rounded-t-[3px] animate-barGrow origin-bottom" :style="{ height: barH(m.invoiced) + '%', background: '#0f766e', minHeight: '2px' }" :title="'Invoiced ' + fmt(m.invoiced)"></div>
            <div class="w-1/2 rounded-t-[3px] animate-barGrow origin-bottom" :style="{ height: barH(m.collected) + '%', background: '#7c3aed', minHeight: '2px' }" :title="'Collected ' + fmt(m.collected)"></div>
          </div>
          <span class="text-[10px] text-ink-muted font-semibold">{{ monthLabel(m.month) }}</span>
        </div>
      </div>
    </div>

    <!-- Procurement gaps (GRNI + AP) -->
    <div v-if="cod.purchases && Object.keys(cod.purchases).length" class="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
      <button v-for="p in procStrip" :key="p.key" @click="goPurch(p.key)"
              class="relative bg-white rounded-[16px] border border-line p-[17px] shadow-card text-start overflow-hidden hover:-translate-y-0.5 hover:shadow-cardHover transition-all">
        <span class="absolute top-0 inset-x-0 h-[3px]" :style="{ background: p.color, opacity: .3 }"></span>
        <div class="flex items-center gap-2">
          <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" :style="{ background: p.tint }"><Icon :name="p.icon" :size="14" :color="p.color" /></span>
          <span class="text-[12px] font-bold text-ink-3">{{ p.label }}</span>
        </div>
        <div class="text-[24px] font-extrabold tnum mt-2 leading-none" :style="{ color: p.color }">{{ money(p.value) }}<span class="text-[12px] text-ink-muted ms-1">MAD</span></div>
        <div class="text-[11px] text-ink-muted mt-1.5">{{ (p.count || 0).toLocaleString() }} {{ L("docs","مستند","docs") }}</div>
      </button>
    </div>

    <!-- Receivables & Payables reconciliation -->
    <button v-if="arap && arap.working_capital !== undefined" @click="goArap"
            class="w-full bg-white rounded-[16px] border border-line p-[17px] shadow-card text-start hover:-translate-y-0.5 hover:shadow-cardHover transition-all">
      <div class="flex items-center gap-2 mb-3">
        <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#faf6f4"><Icon name="scale" :size="14" color="#0b5c4f" /></span>
        <span class="text-[12px] font-bold">{{ L("Receivables & Payables","الذمم المدينة والدائنة","Créances & Dettes") }}</span>
        <span class="text-[10px] text-ink-muted">{{ L("operational vs book","تشغيلي مقابل دفتري","op. vs comptable") }}</span>
        <Icon name="arrow" :size="13" color="#a8a29e" class="ms-auto rtl:rotate-180" />
      </div>
      <div class="grid grid-cols-3 gap-3">
        <div>
          <div class="text-[10px] text-ink-muted font-semibold uppercase tracking-wider">{{ L("Receivables","مدينة","Créances") }}</div>
          <div class="text-[19px] font-extrabold tnum mt-0.5" style="color:#0369a1">{{ money(arap.ar_operational) }}</div>
          <div v-if="arap.ar_broken" class="text-[9.5px] font-bold text-sale mt-0.5 inline-flex items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-sale"></span>{{ L("GL broken","الـ GL مكسور","GL cassé") }}</div>
        </div>
        <div>
          <div class="text-[10px] text-ink-muted font-semibold uppercase tracking-wider">{{ L("Payables","دائنة","Dettes") }}</div>
          <div class="text-[19px] font-extrabold tnum mt-0.5" style="color:#be123c">{{ money(arap.ap_net) }}</div>
          <div class="text-[9.5px] font-bold mt-0.5 inline-flex items-center gap-1" :style="arap.ap_reconciled ? 'color:#047857' : 'color:#b45309'"><span class="w-1.5 h-1.5 rounded-full" :style="arap.ap_reconciled ? 'background:#047857' : 'background:#b45309'"></span>{{ arap.ap_reconciled ? L("ties to GL","مطابق","concorde") : L("small gap","فرق بسيط","léger écart") }}</div>
        </div>
        <div>
          <div class="text-[10px] text-ink-muted font-semibold uppercase tracking-wider">{{ L("Working capital","رأس المال العامل","BFR") }}</div>
          <div class="text-[19px] font-extrabold tnum mt-0.5" :style="{ color: (arap.working_capital || 0) >= 0 ? '#047857' : '#be123c' }">{{ money(arap.working_capital) }}</div>
          <div class="text-[9.5px] text-ink-muted mt-0.5">{{ L("AR − AP","مدينة − دائنة","AR − AP") }}</div>
        </div>
      </div>
    </button>

    <!-- Working capital -->
    <div class="grid sm:grid-cols-2 gap-3.5">
      <div class="relative bg-white rounded-[16px] border border-line p-[17px] shadow-card overflow-hidden transition-all duration-200 hover:shadow-cardHover hover:-translate-y-[2px]">
        <div class="absolute -top-10 -end-10 w-28 h-28 rounded-full blur-2xl pointer-events-none" style="background:#be123c;opacity:.07"></div>
        <div class="relative flex items-center gap-2">
          <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#fff1f2"><Icon name="wallet" :size="14" color="#be123c" /></span>
          <span class="text-[13px] font-bold">{{ vm.arap.arLabel }}</span>
          <span class="text-[10.5px] text-ink-muted ms-auto">{{ vm.arap.arRows }} {{ t("dash.lines") }}</span>
        </div>
        <div class="relative text-[26px] font-bold text-sale tnum mt-2.5 tracking-tight">{{ vm.arap.arVal }}<span class="text-[12px] text-ink-muted ms-1">MAD</span></div>
        <div class="relative flex gap-2 mt-2.5 px-3 py-2.5 rounded-[10px]" style="background:#fef2f2;border:1px solid #fecaca">
          <Icon name="alert" :size="13" color="#be123c" class="flex-shrink-0 mt-px" />
          <span class="text-[11px] leading-snug" style="color:#991b1b">{{ vm.arap.arNote }}</span>
        </div>
      </div>
      <div class="relative bg-white rounded-[16px] border border-line p-[17px] shadow-card overflow-hidden transition-all duration-200 hover:shadow-cardHover hover:-translate-y-[2px]">
        <div class="absolute -top-10 -end-10 w-28 h-28 rounded-full blur-2xl pointer-events-none" style="background:#b45309;opacity:.06"></div>
        <div class="relative flex items-center gap-2">
          <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#fff4e0"><Icon name="bank" :size="14" color="#b45309" /></span>
          <span class="text-[13px] font-bold">{{ vm.arap.apLabel }}</span>
          <span class="text-[10.5px] text-ink-muted ms-auto">{{ vm.arap.apRows }} {{ t("dash.lines") }}</span>
        </div>
        <div class="relative text-[26px] font-bold text-ink tnum mt-2.5 tracking-tight">{{ vm.arap.apVal }}<span class="text-[12px] text-ink-muted ms-1">MAD</span></div>
        <div class="relative text-[11.5px] text-ink-3 mt-3.5 leading-snug">{{ vm.arap.apNote }}</div>
      </div>
    </div>

    <!-- Anomalies feed -->
    <div class="bg-white rounded-[14px] border border-line p-[17px] shadow-card">
      <div class="flex items-center gap-2.5">
        <span class="w-[26px] h-[26px] rounded-[8px] grid place-items-center" style="background:#f5f3ff"><Icon name="shield" :size="14" color="#7c3aed" /></span>
        <div class="flex-1">
          <div class="text-[13.5px] font-bold">{{ t("dash.flagged_title") }}</div>
          <div class="text-[11px] text-ink-muted">{{ t("dash.flagged_sub") }}</div>
        </div>
        <button class="text-[11px] font-semibold text-accent-dark hover:underline" @click="goCopilot">{{ t("dash.view_all") }} →</button>
      </div>
      <div class="flex flex-col gap-2 mt-3">
        <button v-for="a in anomalies" :key="a.id"
                class="yo-row flex items-center gap-3 px-3 py-[11px] rounded-[11px] border border-line text-start w-full hover:bg-app-warm/60"
                style="background:#fdfcfb" @click="go(a.go)">
          <span class="w-[30px] h-[30px] rounded-[8px] grid place-items-center flex-shrink-0" :style="{ background: sev(a).bg }"><Icon :name="a.icon" :size="15" :color="sev(a).fg" /></span>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <span class="text-[12.5px] font-bold">{{ a.title(locale) }}</span>
              <span class="text-[9px] font-bold px-1.5 py-0.5 rounded-badge border" :style="{ background: sev(a).bg, color: sev(a).fg, borderColor: sev(a).bd }">{{ sevLabel(a.sev, locale) }}</span>
            </div>
            <div class="text-[11.5px] text-ink-3 mt-0.5 truncate">{{ a.desc(locale) }}</div>
          </div>
          <span v-if="a.amount" class="text-[12px] font-bold tnum flex-shrink-0" :class="a.amount.includes('-') ? 'text-sale' : ''">{{ a.amount }}</span>
          <Icon name="chev" :size="15" color="#cfc9c4" class="rtl:rotate-180 flex-shrink-0" />
        </button>
      </div>
    </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import Consolidated from "@/pages/Consolidated.vue";
import DashboardSkeleton from "@/components/DashboardSkeleton.vue";
import { useUi } from "@/composables/useUi";
import { buildDashVM } from "@/data/dashboard";
import { ANOMALIES, SEV_META, sevLabel } from "@/data/copilot";
import { useDashboard, overlayCockpit } from "@/composables/useDashboard";

const { t, locale } = useI18n();
const router = useRouter();
const { entityId } = useUi();
const { loadCockpit } = useDashboard();

// CFO cockpit from live ERPNext (KPIs, digest, working capital all computed
// from real figures); reloads when the entity changes.
const cockpit = ref(null);
const isLive = ref(null);
const loaded = ref(false);
// Show a skeleton until the live cockpit resolves — no flash of sample/fake data.
async function load() {
  loaded.value = false;
  try { cockpit.value = await loadCockpit(); isLive.value = !!(cockpit.value && cockpit.value.company); }
  finally { loaded.value = true; }
}
watch(entityId, load, { immediate: true });

const vm = computed(() => overlayCockpit(buildDashVM(locale.value, entityId.value), cockpit.value, locale.value));
const asOf = computed(() => cockpit.value?.as_of || "");

// COD control-tower sections read the live cockpit directly.
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const cod = computed(() => cockpit.value || {});
const fmt = (n) => Number(n || 0).toLocaleString("en-US");
const money = (n) => { n = Number(n) || 0; const a = Math.abs(n); return a >= 1e6 ? (n / 1e6).toFixed(2) + "M" : a >= 1e3 ? Math.round(n / 1e3) + "K" : Math.round(n).toLocaleString(); };
const MON = { "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr", "05": "May", "06": "Jun", "07": "Jul", "08": "Aug", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec" };
const monthLabel = (m) => MON[String(m).split("-")[1]] || m;
const FUNNEL = [
  { key: "todeliver", color: "#0369a1", tint: "#eff6ff", icon: "truck", label: () => L("To deliver", "للتسليم", "À livrer") },
  { key: "delivered", color: "#047857", tint: "#ecfdf5", icon: "check", label: () => L("Delivered", "مُسلّمة", "Livrées") },
  { key: "collected", color: "#7c3aed", tint: "#f5f3ff", icon: "coins", label: () => L("Collected", "محصّلة", "Encaissées") },
  { key: "toreturn", color: "#b45309", tint: "#fffbeb", icon: "clock", label: () => L("To return", "للإرجاع", "À retourner") },
  { key: "returned", color: "#be123c", tint: "#fef2f2", icon: "refresh", label: () => L("Returned", "مرتجعة", "Retournées") },
];
const funnel = computed(() => FUNNEL.map((b) => ({ ...b, label: b.label(), count: (cod.value.pipeline?.[b.key] || {}).count || 0, value: (cod.value.pipeline?.[b.key] || {}).value || 0 })));
const cohortMax = computed(() => Math.max(1, ...(cod.value.cohort || []).flatMap((m) => [m.invoiced, m.collected])));
const barH = (v) => Math.round((Number(v) || 0) / cohortMax.value * 100);

// Live auditor narration off the real pipeline (falls back to the static digest).
const liveDigest = computed(() => {
  const c = cod.value;
  if (!c.pipeline) return vm.value.digest;
  const f = (k) => funnel.value.find((b) => b.key === k) || { count: 0, value: 0 };
  const dv = f("delivered"), tr = f("toreturn");
  return L(
    `${(dv.count || 0).toLocaleString()} delivered orders await collection — ${money(c.carrier_float)} MAD float with Cathedis, ${Math.round(c.reconciled_pct || 0)}% reconciled. ${(tr.count || 0).toLocaleString()} orders to return (${money(tr.value)} MAD) pending the warehouse.`,
    `${(dv.count || 0).toLocaleString()} طلب مُسلّم مستني التحصيل — ${money(c.carrier_float)} درهم مع كاتدييس، ${Math.round(c.reconciled_pct || 0)}% اتطابق. و${(tr.count || 0).toLocaleString()} طلب للإرجاع (${money(tr.value)} درهم) مستني المخزن.`,
    `${(dv.count || 0).toLocaleString()} livrées à encaisser — ${money(c.carrier_float)} MAD chez Cathedis, ${Math.round(c.reconciled_pct || 0)}% rapproché.`);
});
function goBucket(k) { router.push(`/accounting/sales/${k}`); }
function goReport() { router.push("/accounting/reports/salescol"); }
function goPurch(k) { router.push(`/accounting/purchases/${k}`); }
function goArap() { router.push("/accounting/reports/arap"); }
const arap = computed(() => cod.value.arap || {});
const PROC = [
  { key: "tobuy", color: "#0369a1", tint: "#eff6ff", icon: "cart", label: () => L("Open POs · to buy", "أوامر مفتوحة", "BC ouverts") },
  { key: "received", color: "#b45309", tint: "#fffbeb", icon: "box", label: () => L("GRNI · received not billed", "مُستلم بلا فاتورة", "Reçu non facturé") },
  { key: "topay", color: "#be123c", tint: "#fef2f2", icon: "wallet", label: () => L("To pay · due", "مستحق للدفع", "À payer") },
];
const procStrip = computed(() => PROC.map((p) => ({ ...p, label: p.label(), count: (cod.value.purchases?.[p.key] || {}).count || 0, value: (cod.value.purchases?.[p.key] || {}).value || 0 })));
const anomalies = ANOMALIES.slice(0, 4);
const sev = (a) => SEV_META[a.sev] || SEV_META.low;

function go(g) {
  if (!g) return;
  router.push(g.sub ? `/accounting/${g.module}/${g.sub}` : `/accounting/${g.module}`);
}
const goChip = (c) => go(c.go);
const goCopilot = () => router.push("/accounting/copilot");
</script>
