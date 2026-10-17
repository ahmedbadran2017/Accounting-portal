<template>
  <div class="space-y-3.5">
    <!-- snapshot: when it was taken, and the two refresh buttons -->
    <div class="flex items-center gap-2 flex-wrap text-[11px] text-ink-muted">
      <Icon name="clock" :size="12" />
      <span>{{ L("Snapshot","لقطة","Instantané") }} <b class="tnum text-ink-3" dir="ltr">{{ d?.built_on || "—" }}</b></span>
      <span>·</span>
      <span>{{ L("Cathedis parcels","طرود كاتدييس","Colis Cathedis") }} <b class="tnum text-ink-3" dir="ltr">{{ n(d?.parcels) }}</b></span>
      <span v-if="d?.cathedis_sync" dir="ltr">· {{ L("synced","اتحدّث","synchro") }} {{ String(d.cathedis_sync.started || "").slice(0, 16) }}</span>
      <div class="ms-auto flex items-center gap-1.5">
        <UiButton variant="quiet" size="xs" icon="refresh" :busy="syncing" @click="syncCathedis">{{ L("Refresh from Cathedis","حدّث من كاتدييس","Synchro Cathedis") }}</UiButton>
        <UiButton variant="quiet" size="xs" :busy="rebuilding" @click="rebuild">{{ L("Rebuild","أعد البناء","Recalculer") }}</UiButton>
      </div>
    </div>
    <div v-if="note" class="text-[12px] text-ink-3 bg-app-warm/60 border border-line-hair rounded-chip px-3 py-2">{{ note }}</div>

    <TableLoading v-if="loading" :rows="8" />
    <div v-else-if="error" class="bg-white rounded-card border border-line shadow-card py-10 text-center text-[13px]" style="color:#b91c1c">{{ L("Load failed","فشل التحميل","Échec du chargement") }} — {{ error }}</div>
    <div v-else-if="d && d.building" class="bg-white rounded-card border border-line shadow-card py-10 text-center text-[13px] text-ink-3">{{ L("The snapshot is being built right now — reload in a minute.","اللقطة بتتبني دلوقتي — اعمل reload بعد دقيقة.","Instantané en cours de calcul — rechargez dans une minute.") }}</div>
    <div v-else-if="d && d.total && !d.total.money" class="bg-white rounded-card border border-line shadow-card py-10 text-center text-[13px] text-ink-3">{{ L("This snapshot predates the cycle view — press Rebuild.","اللقطة دي أقدم من شاشة الدورة — دوس أعد البناء.","Instantané ancien — Recalculer.") }}</div>

    <template v-else-if="d && d.total">
      <!-- ═══ the year as one cycle: sales → collected → cost → margin, then the radar ═══ -->
      <div class="grid grid-cols-2 lg:grid-cols-[1fr_auto_1fr_auto_1fr_auto_1fr_1fr] gap-2 lg:gap-0 items-stretch">
        <template v-for="(k, i) in KPI" :key="k.key">
          <div class="bg-white rounded-card border border-line shadow-card px-4 py-3 relative overflow-hidden" :class="k.key === 'radar' ? 'lg:ms-3' : ''">
            <span class="absolute inset-x-0 top-0 h-[3px]" :style="{ background: k.color }"></span>
            <div class="text-[10px] font-bold uppercase tracking-wider" :style="{ color: k.color }">{{ k.label() }}</div>
            <div class="text-[20px] font-extrabold tnum leading-tight mt-0.5" dir="ltr">{{ k.value() }}</div>
            <div class="text-[11px] text-ink-muted tnum mt-0.5" dir="ltr">{{ k.sub() }}</div>
            <svg v-if="k.key === 'margin' && spark" class="absolute end-3 bottom-2.5" width="64" height="22" viewBox="0 0 64 22">
              <polyline :points="spark" fill="none" stroke="#047857" stroke-width="1.5" stroke-linejoin="round" />
            </svg>
          </div>
          <div v-if="i < 3" class="hidden lg:flex items-center justify-center px-1.5 text-ink-muted"><Icon name="chev" :size="14" class="rtl:rotate-180" /></div>
        </template>
      </div>

      <!-- ═══ month by month: each station is a door to its documents ═══ -->
      <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-[12px] min-w-[860px]">
            <thead>
              <tr>
                <th class="px-4 pt-3 pb-2 text-start hcell w-[110px]">{{ L("Month","الشهر","Mois") }}</th>
                <th v-for="st in STATIONS" :key="st.key" class="px-4 pt-3 pb-2 text-start">
                  <div class="flex items-center gap-1.5"><span class="w-2 h-2 rounded-full" :style="{ background: st.color }"></span><span class="hcell" :style="{ color: st.color }">{{ st.label() }}</span></div>
                  <div class="text-[10px] font-normal text-ink-muted mt-0.5 normal-case tracking-normal">{{ st.hint() }}</div>
                </th>
              </tr>
            </thead>
            <tbody>
              <template v-for="m in months" :key="m.month">
                <tr class="border-t border-line-hair align-top" :class="sel.month === m.month ? 'bg-app-warm/50' : ''">
                  <td class="px-4 py-3">
                    <div class="font-bold text-[13px]">{{ monthName(m.month) }}</div>
                    <div class="text-[10px] text-ink-muted tnum" dir="ltr">{{ n(m.orders) }} {{ L("orders","أوردر","cmd") }}</div>
                  </td>
                  <!-- sales -->
                  <td class="p-1.5"><button class="cell" :class="cellCls(m, 'sales')" @click="openTab(m.month, 'sales')">
                    <div class="flex items-center gap-1.5"><span class="amt" dir="ltr">{{ n(m.money.sales) }}</span><Dot :sev="stationSev(m, 'sales')" /></div>
                    <div class="sub" dir="ltr">{{ n(m.money.invoices) }} {{ L("invoices","فاتورة","factures") }}</div>
                  </button></td>
                  <!-- collected -->
                  <td class="p-1.5"><button class="cell" :class="cellCls(m, 'collections')" @click="openTab(m.month, 'collections')">
                    <div class="flex items-center gap-1.5"><span class="amt" dir="ltr">{{ n(m.money.collected) }}</span><Dot :sev="stationSev(m, 'collections')" /></div>
                    <div class="flex items-center gap-1.5 mt-1">
                      <div class="flex-1 h-1 rounded-full overflow-hidden max-w-[90px]" style="background:#eef2ff"><div class="h-full rounded-full" style="background:#4338ca" :style="{ width: Math.min(100, ratio(m.money.collected, m.money.sales)) + '%' }"></div></div>
                      <span class="sub !mt-0" dir="ltr">{{ ratio(m.money.collected, m.money.sales) }}%</span>
                    </div>
                    <div v-if="m.money.uncollected > 500" class="sub" style="color:#b91c1c" dir="ltr">{{ n(m.money.uncollected) }} {{ L("unpaid","مش متحصّل","impayé") }}</div>
                  </button></td>
                  <!-- cost -->
                  <td class="p-1.5"><button class="cell" :class="cellCls(m, 'cost')" @click="openTab(m.month, 'cost')">
                    <div class="flex items-center gap-1.5"><span class="amt" dir="ltr">{{ n(m.money.cogs) }}</span><Dot :sev="stationSev(m, 'cost')" /></div>
                    <div class="sub" dir="ltr">{{ ratio(m.money.cogs, m.money.sales) }}% {{ L("of sales","من المبيعات","des ventes") }}</div>
                    <div v-if="Math.abs(m.money.cogs_other) > 0.03 * Math.abs(m.money.cogs || 1)" class="sub" style="color:#b45309" dir="ltr">{{ n(m.money.cogs_other) }} {{ L("outside deliveries","برة أذون التسليم","hors BL") }}</div>
                  </button></td>
                  <!-- margin -->
                  <td class="p-1.5"><button class="cell" :class="cellCls(m, 'margin')" @click="openTab(m.month, 'cost')">
                    <div class="flex items-center gap-2">
                      <span class="amt" dir="ltr">{{ n(m.money.margin) }}</span>
                      <span class="text-[11px] font-bold px-1.5 py-0.5 rounded-full tnum" :style="gmStyle(m)" dir="ltr">{{ pct(m.money.gm_pct) }}</span>
                    </div>
                    <div class="sub">{{ gmNote(m) }}</div>
                  </button></td>
                  <!-- radar -->
                  <td class="p-1.5"><button class="cell" :class="cellCls(m, 'radar')" @click="openTab(m.month, 'radar')">
                    <div class="flex items-center gap-1.5 flex-wrap">
                      <span v-if="m.anomalies.length" class="text-[11px] font-bold px-2 py-0.5 rounded-full" :style="m.anomalies.some((a) => a.sev === 'high') ? 'background:#fee2e2;color:#b91c1c' : 'background:#fef3c7;color:#92400e'" dir="ltr">{{ m.anomalies.length }} {{ alertsWord(m.anomalies.length) }}</span>
                      <span v-if="m.exceptions" class="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-app-warm text-ink-3" dir="ltr">{{ n(m.exceptions) }} {{ L("orders","أوردر","cmd") }}</span>
                      <span v-if="!m.anomalies.length && !m.exceptions" class="text-[11px] font-semibold" style="color:#047857">{{ L("clean","سليم","OK") }}</span>
                    </div>
                    <div class="sub" dir="ltr">{{ m.clean_pct == null ? "" : pct(m.clean_pct) + " " + L("closed clean","مقفول للآخر","clôturées") }}</div>
                  </button></td>
                </tr>

                <!-- ═══ the month opened: one station at a time ═══ -->
                <tr v-if="sel.month === m.month">
                  <td colspan="6" class="px-3 pb-4 pt-1 bg-app-warm/50">
                    <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
                      <div class="flex items-center gap-1 px-3 pt-2.5 border-b border-line-hair flex-wrap">
                        <button v-for="t in TABS" :key="t.key" @click="setTab(t.key)"
                                class="px-3 py-2 text-[12px] font-semibold border-b-2 -mb-px transition flex items-center gap-1.5"
                                :class="sel.tab === t.key ? 'border-current' : 'border-transparent text-ink-muted hover:text-ink-3'"
                                :style="sel.tab === t.key ? { color: t.color } : {}">
                          {{ t.label() }}
                          <span v-if="tabCount(m, t.key)" class="text-[10px] font-bold px-1.5 rounded-full tnum" style="background:#fee2e2;color:#b91c1c" dir="ltr">{{ tabCount(m, t.key) }}</span>
                        </button>
                        <button class="ms-auto text-ink-muted hover:text-ink p-1.5" @click="sel.month = ''"><Icon name="close" :size="15" /></button>
                      </div>

                      <div class="p-4 space-y-3.5">
                        <!-- facts for the station -->
                        <div class="grid grid-cols-2 md:grid-cols-4 gap-x-6 gap-y-2.5">
                          <div v-for="f in facts(m, sel.tab)" :key="f.label" class="min-w-0">
                            <div class="text-[10px] font-bold uppercase tracking-wider text-ink-muted truncate">{{ f.label }}</div>
                            <div class="text-[15px] font-bold tnum" :style="f.color ? { color: f.color } : {}" dir="ltr">{{ f.value }}</div>
                          </div>
                        </div>

                        <!-- sales: the month's orders as a funnel -->
                        <div v-if="sel.tab === 'sales'" class="space-y-1.5">
                          <div class="text-[11px] font-bold text-ink-3">{{ L("This month's orders, station by station","أوردرات الشهر محطة محطة","Commandes du mois, étape par étape") }}</div>
                          <div v-for="f in funnel(m)" :key="f.key" class="flex items-center gap-2 text-[11px]">
                            <span class="w-24 text-ink-3 truncate">{{ f.label }}</span>
                            <div class="flex-1 h-2.5 rounded-full overflow-hidden" style="background:#f5f5f4"><div class="h-full rounded-full" :style="{ width: f.pct + '%', background: f.color }"></div></div>
                            <span class="w-24 text-end tnum font-semibold" dir="ltr">{{ n(f.n) }} <span class="text-ink-muted font-normal">· {{ f.pct }}%</span></span>
                          </div>
                        </div>

                        <!-- month-level alerts for this station -->
                        <div v-for="a in alertsFor(m, sel.tab)" :key="a.key" class="flex items-start gap-2.5 rounded-[10px] px-3 py-2.5 border"
                             :style="a.sev === 'high' ? 'background:#fef2f2;border-color:#fecaca' : 'background:#fffbeb;border-color:#fde68a'">
                          <Icon name="alert" :size="15" :color="a.sev === 'high' ? '#b91c1c' : '#b45309'" class="mt-0.5 flex-shrink-0" />
                          <div class="flex-1 min-w-0">
                            <div class="text-[12px] font-semibold" :style="{ color: a.sev === 'high' ? '#991b1b' : '#92400e' }">{{ alertText(a) }}</div>
                            <div class="text-[11px] text-ink-3 mt-0.5">{{ alertWhy(a) }}</div>
                          </div>
                          <UiButton v-if="docsKind(a)" variant="secondary" size="xs" @click="openDocs(m.month, docsKind(a))">{{ L("Show documents","اعرض المستندات","Voir les documents") }}</UiButton>
                        </div>

                        <!-- order exceptions for this station -->
                        <div v-if="bucketsFor(m, sel.tab).length">
                          <div class="text-[11px] font-bold text-ink-3 mb-1.5">{{ L("Orders that do not add up","أوردرات مش مظبوطة","Commandes en écart") }} <span class="font-normal text-ink-muted">· {{ L("orders placed this month","أوردرات اتعملت الشهر ده","commandes du mois") }}</span></div>
                          <div class="flex items-center gap-1.5 flex-wrap">
                            <button v-for="b in bucketsFor(m, sel.tab)" :key="b.key" @click="pick(m.month, b.key)"
                                    class="text-[11px] font-semibold px-2.5 py-1 rounded-full border transition"
                                    :class="pickKey === m.month + '|' + b.key ? 'bg-ink text-white border-ink' : (b.watch ? 'bg-white text-ink-muted border-line-2 hover:bg-app-warm' : 'bg-white text-ink-2 border-line-2 hover:bg-app-warm')">
                              {{ label(b.key) }} · <span class="tnum" dir="ltr">{{ n(b.n) }} · {{ n(b.value) }}</span>
                            </button>
                          </div>
                        </div>
                        <div v-if="!alertsFor(m, sel.tab).length && !bucketsFor(m, sel.tab).filter((b) => !b.watch).length" class="text-[12px] font-semibold" style="color:#047857">
                          <Icon name="check" :size="13" class="inline me-1" />{{ L("Nothing abnormal at this station.","مفيش حاجة غريبة في المحطة دي.","Rien d'anormal ici.") }}
                        </div>

                        <!-- documents behind an alert -->
                        <div v-if="docs.kind" class="border border-line-hair rounded-[10px] overflow-hidden">
                          <div class="px-3 py-2 text-[11px] font-bold border-b border-line-hair flex items-center" style="background:#fafaf9">
                            {{ docsTitle(docs.kind) }} <span class="ms-auto font-normal text-ink-muted tnum" dir="ltr">{{ docs.rows.length }}</span>
                          </div>
                          <TableLoading v-if="docs.loading" :rows="3" />
                          <div v-else class="max-h-[420px] overflow-y-auto">
                            <table class="w-full text-[12px]">
                              <tbody>
                                <tr v-for="r in docs.rows" :key="r.doctype + r.name" class="border-t border-line-hair first:border-t-0 hover:bg-app-warm/30">
                                  <td class="px-3 py-2 whitespace-nowrap">
                                    <RouterLink v-if="routeForDoc(r.doctype, r.name)" :to="routeForDoc(r.doctype, r.name)" class="font-mono text-[11px] font-semibold hover:text-accent">{{ r.name }}</RouterLink>
                                    <span v-else class="font-mono text-[11px]">{{ r.name }}</span>
                                    <div class="text-[10px] text-ink-muted">{{ r.doctype }} · <span dir="ltr">{{ r.date }}</span></div>
                                  </td>
                                  <td class="px-3 py-2 text-ink-3 truncate max-w-[260px]">{{ r.party || "—" }}<div v-if="docs.kind === 'cost_outside'" class="text-[10px] text-ink-muted truncate">{{ r.note }}</div></td>
                                  <td v-if="docs.kind !== 'cost_outside'" class="px-3 py-2 text-end tnum text-ink-muted" dir="ltr">{{ money(r.note) }}</td>
                                  <td class="px-3 py-2 text-end tnum font-bold" dir="ltr">{{ money(r.amount) }}</td>
                                </tr>
                                <tr v-if="!docs.rows.length"><td class="px-3 py-6 text-center text-ink-muted">{{ L("No documents.","مفيش مستندات.","Aucun document.") }}</td></tr>
                              </tbody>
                            </table>
                          </div>
                        </div>

                        <!-- orders behind a bucket -->
                        <div v-if="pickKey" class="border border-line-hair rounded-[10px] overflow-hidden">
                          <div class="px-3 py-2 text-[11px] font-bold border-b border-line-hair flex items-center gap-2" style="background:#fafaf9">
                            {{ label(pickKey.split("|")[1]) }}<span class="font-normal text-ink-muted">— {{ hint(pickKey.split("|")[1]) }}</span>
                            <span class="ms-auto font-normal text-ink-muted tnum" dir="ltr">{{ drillRows.length }} / {{ drillTotal }}</span>
                          </div>
                          <TableLoading v-if="drillLoading" :rows="3" />
                          <div v-else class="overflow-x-auto max-h-[480px] overflow-y-auto">
                            <table class="w-full text-[12px]">
                              <thead class="sticky top-0 bg-white"><tr>
                                <th class="px-3 py-2 text-start hcell">{{ L("Order","الأوردر","Commande") }}</th>
                                <th class="px-3 py-2 text-start hcell">{{ L("Delivery · parcel","التسليم · الطرد","BL · colis") }}</th>
                                <th class="px-3 py-2 text-start hcell">{{ L("Cathedis says","كاتدييس بتقول","Cathedis") }}</th>
                                <th class="px-3 py-2 text-start hcell">{{ L("Invoice","الفاتورة","Facture") }}</th>
                                <th class="px-3 py-2 text-end hcell">{{ L("Invoiced","متفوتر","Facturé") }}</th>
                                <th class="px-3 py-2 text-end hcell">{{ L("Cathedis COD","تحصيل كاتدييس","COD") }}</th>
                                <th class="px-3 py-2 text-end hcell">{{ L("Receipts","التحصيل","Encaissé") }}</th>
                                <th class="px-3 py-2 text-end hcell">{{ L("Cost","التكلفة","Coût") }}</th>
                                <th class="px-3 py-2"></th>
                              </tr></thead>
                              <tbody>
                                <tr v-for="r in drillRows" :key="r.so" class="border-t border-line-hair hover:bg-app-warm/30">
                                  <td class="px-3 py-2 whitespace-nowrap">
                                    <RouterLink :to="routeForDoc('Sales Order', r.so)" class="font-mono text-[11px] font-semibold hover:text-accent">{{ r.so }}</RouterLink>
                                    <span v-if="r.exchange" class="ms-1 text-[9px] font-bold px-1.5 py-0.5 rounded-full" style="background:#fef3c7;color:#92400e">EX</span>
                                    <div class="text-[10px] text-ink-muted truncate max-w-[150px]">{{ r.customer }}</div>
                                  </td>
                                  <td class="px-3 py-2 whitespace-nowrap">
                                    <RouterLink v-if="r.dn" :to="routeForDoc('Delivery Note', r.dn)" class="font-mono text-[11px] hover:text-accent">{{ r.dn }}</RouterLink><span v-else class="text-ink-muted">—</span>
                                    <div class="font-mono text-[10px] text-ink-muted">{{ r.awb || "" }}</div>
                                  </td>
                                  <td class="px-3 py-2 text-[11px] text-ink-3 max-w-[170px]">{{ r.carrier || "—" }}</td>
                                  <td class="px-3 py-2 whitespace-nowrap"><RouterLink v-if="r.si" :to="routeForDoc('Sales Invoice', r.si)" class="font-mono text-[11px] hover:text-accent">{{ r.si }}</RouterLink><span v-else class="text-ink-muted">—</span></td>
                                  <td class="px-3 py-2 text-end tnum" dir="ltr">{{ money(r.invoiced) }}</td>
                                  <td class="px-3 py-2 text-end tnum" dir="ltr">{{ r.cod == null ? "—" : money(r.cod) }}</td>
                                  <td class="px-3 py-2 text-end tnum whitespace-nowrap" dir="ltr">{{ money(r.cathedis_receipt) }}<span v-if="r.other_receipt" class="text-ink-muted"> + {{ money(r.other_receipt) }}</span></td>
                                  <td class="px-3 py-2 text-end tnum" dir="ltr">{{ money(r.cost) }}</td>
                                  <td class="px-3 py-2 text-end w-28">
                                    <UiButton v-if="r.action === 'bill' && r.dn" variant="secondary" size="xs" :busy="busy === r.so" @click="bill(r)">{{ L("Make invoice","اعمل فاتورة","Facturer") }}</UiButton>
                                    <UiButton v-else-if="r.action === 'credit_note' && r.si" variant="danger" size="xs" :busy="busy === r.so" @click="creditNote(r)">{{ L("Credit note","إشعار دائن","Avoir") }}</UiButton>
                                    <span v-else class="text-[11px] text-ink-muted">{{ L("review","مراجعة","à revoir") }}</span>
                                  </td>
                                </tr>
                                <tr v-if="!drillRows.length"><td colspan="9" class="px-4 py-6 text-center text-[12px] text-ink-muted">{{ L("Nothing left in this bucket.","مفيش حاجة في السلة دي.","Rien ici.") }}</td></tr>
                              </tbody>
                            </table>
                          </div>
                        </div>

                        <!-- cost: items that cost more than they sell for (whole year) -->
                        <div v-if="sel.tab === 'cost' && d.items && d.items.length" class="border border-line-hair rounded-[10px] overflow-hidden">
                          <button class="w-full px-3 py-2 text-[11px] font-bold flex items-center gap-2 hover:bg-app-warm/40" style="background:#fafaf9" @click="showItems = !showItems">
                            <Icon :name="showItems ? 'chevDown' : 'chev'" :size="12" class="rtl:rotate-180" />
                            {{ L("Items that cost more than they sell for","أصناف تكلفتها أعلى من سعر بيعها","Articles au coût > prix") }}
                            <span class="font-normal text-ink-muted">· {{ L("whole year — fix at the source (Vendor Workbench)","السنة كلها — التصليح من المصدر (Vendor Workbench)","toute l'année — corriger à la source") }}</span>
                            <span class="ms-auto tnum" dir="ltr">{{ d.items.length }}</span>
                          </button>
                          <table v-if="showItems" class="w-full text-[12px]">
                            <tbody>
                              <tr v-for="it in d.items" :key="it.item" class="border-t border-line-hair">
                                <td class="px-3 py-1.5"><RouterLink :to="routeForDoc('Item', it.item)" class="font-mono text-[11px] hover:text-accent">{{ it.item }}</RouterLink></td>
                                <td class="px-3 py-1.5 text-end tnum text-ink-muted" dir="ltr">{{ n(it.deliveries) }} {{ L("deliveries","تسليم","livr.") }}</td>
                                <td class="px-3 py-1.5 text-end tnum font-bold" style="color:#b91c1c" dir="ltr">{{ money(it.unit_cost) }}</td>
                                <td class="px-3 py-1.5 text-end tnum" dir="ltr">{{ L("sells","بيتباع","vendu") }} {{ money(it.unit_price) }}</td>
                                <td class="px-3 py-1.5 text-end tnum text-ink-muted" dir="ltr">×{{ it.ratio }}</td>
                              </tr>
                            </tbody>
                          </table>
                        </div>
                      </div>
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
            <tfoot><tr class="border-t-2 border-line" style="background:#fafaf9">
              <td class="px-4 py-3 font-bold">{{ L("Year","السنة","Année") }}</td>
              <td class="px-4 py-3 font-bold tnum" dir="ltr">{{ n(T.sales) }}</td>
              <td class="px-4 py-3 font-bold tnum" dir="ltr">{{ n(T.collected) }} <span class="text-[11px] font-normal text-ink-muted">· {{ ratio(T.collected, T.sales) }}%</span></td>
              <td class="px-4 py-3 font-bold tnum" dir="ltr">{{ n(T.cogs) }} <span class="text-[11px] font-normal text-ink-muted">· {{ ratio(T.cogs, T.sales) }}%</span></td>
              <td class="px-4 py-3 font-bold tnum" dir="ltr">{{ n(T.margin) }} <span class="text-[11px] font-normal text-ink-muted">· {{ pct(T.gm_pct) }}</span></td>
              <td class="px-4 py-3 text-[11px] tnum" dir="ltr"><b style="color:#b91c1c">{{ d.total.anomalies }}</b> {{ L("alerts","تنبيه","alertes") }} · <b>{{ n(d.total.exceptions) }}</b> {{ L("orders","أوردر","cmd") }}</td>
            </tr></tfoot>
          </table>
        </div>
      </div>
      <div class="text-[11px] text-ink-muted leading-relaxed">
        {{ L("Sales, collections and cost are by posting date, so they agree with the P&L. Sales include VAT (what customers paid). Order exceptions are grouped by the month the order was placed.",
             "المبيعات والتحصيل والتكلفة بتاريخ القيد، فبتطابق قائمة الدخل. المبيعات شاملة الضريبة (اللي العميل دفعه). استثناءات الأوردرات متجمعة بشهر الأوردر.",
             "Ventes, encaissements et coûts par date comptable (comme le P&L). Ventes TTC. Écarts de commandes groupés par mois de commande.") }}
      </div>
    </template>
  </div>
</template>

<script setup>
// The monthly cycle: sales → collections → cost of goods → margin, one row per
// month, with the radar beside it. Every station opens its own facts, the
// month-level alerts that belong to it, the orders that do not add up, and the
// documents behind them. Rules live in api/radar.py; this page only reads the
// snapshot and drills into it.
import { ref, reactive, computed, watch, onMounted, h } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import UiButton from "@/components/UiButton.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { routeForDoc } from "@/utils/helpers";

const props = defineProps({ year: { type: Number, required: true } });

const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const n = (v) => (v == null ? "—" : Math.round(v).toLocaleString("en-US"));
const money = (v) => (v == null || v === "" ? "—" : Number(v).toLocaleString("en-US", { maximumFractionDigits: 2 }));
const pct = (v) => (v == null ? "—" : v + "%");
const ratio = (a, b) => (b ? Math.round((100 * (a || 0)) / b) : 0);
const monthName = (ym) => {
  const [y, mo] = ym.split("-").map(Number);
  const loc = locale.value === "ar" ? "ar-EG-u-nu-latn" : locale.value === "fr" ? "fr-FR" : "en-GB";
  return new Date(y, mo - 1, 1).toLocaleDateString(loc, { month: "short", year: "numeric" });
};

// a small severity dot next to a station's amount
const Dot = (p) => p.sev ? h("span", { class: "w-1.5 h-1.5 rounded-full flex-shrink-0", style: { background: p.sev === "high" ? "#b91c1c" : "#d97706" } }) : null;
Dot.props = ["sev"];

const d = ref(null);
const loading = ref(false);
const error = ref("");
const note = ref("");
const sel = reactive({ month: "", tab: "sales" });
const pickKey = ref("");
const drillRows = ref([]);
const drillTotal = ref(0);
const drillLoading = ref(false);
const docs = reactive({ kind: "", rows: [], loading: false });
const busy = ref("");
const syncing = ref(false);
const rebuilding = ref(false);
const showItems = ref(false);

const months = computed(() => (d.value?.months || []).filter((m) => m.money));
const T = computed(() => d.value?.total?.money || {});
const spark = computed(() => {
  const vals = months.value.map((m) => m.money.gm_pct).filter((v) => v != null);
  if (vals.length < 2) return "";
  const lo = Math.min(...vals), hi = Math.max(...vals), span = hi - lo || 1;
  return vals.map((v, i) => `${(i * 64) / (vals.length - 1)},${20 - ((v - lo) / span) * 18}`).join(" ");
});

const C = { sales: "#0f766e", collections: "#4338ca", cost: "#b45309", margin: "#047857", radar: "#b91c1c" };
const KPI = [
  { key: "sales", color: C.sales, label: () => L("Sales (incl. VAT)", "المبيعات (شامل الضريبة)", "Ventes TTC"),
    value: () => n(T.value.sales), sub: () => `${n(T.value.invoices)} ${L("invoices", "فاتورة", "factures")}` },
  { key: "collections", color: C.collections, label: () => L("Collected", "المتحصّل", "Encaissé"),
    value: () => n(T.value.collected), sub: () => `${ratio(T.value.collected, T.value.sales)}% ${L("of sales", "من المبيعات", "des ventes")} · ${n(T.value.uncollected)} ${L("unpaid", "مش متحصّل", "impayé")}` },
  { key: "cost", color: C.cost, label: () => L("Cost of goods", "تكلفة البضاعة", "Coût des ventes"),
    value: () => n(T.value.cogs), sub: () => `${ratio(T.value.cogs, T.value.sales)}% ${L("of sales", "من المبيعات", "des ventes")}` },
  { key: "margin", color: C.margin, label: () => L("Gross margin", "الهامش الإجمالي", "Marge brute"),
    value: () => n(T.value.margin), sub: () => `${pct(T.value.gm_pct)} ${L("of sales", "من المبيعات", "des ventes")}` },
  { key: "radar", color: C.radar, label: () => L("Radar", "الرادار", "Radar"),
    value: () => `${d.value?.total?.anomalies || 0} ${alertsWord(d.value?.total?.anomalies || 0)}`,
    sub: () => `${n(d.value?.total?.exceptions)} ${L("orders off", "أوردر مش مظبوط", "commandes en écart")} · ${pct(d.value?.total?.clean_pct)} ${L("clean", "سليم", "OK")}` },
];
const alertsWord = (k) => (k === 1 ? L("alert", "تنبيه", "alerte") : L("alerts", "تنبيهات", "alertes"));
const STATIONS = [
  { key: "sales", color: C.sales, label: () => L("Sales", "المبيعات", "Ventes"), hint: () => L("invoiced, incl. VAT", "المتفوتر شامل الضريبة", "facturé TTC") },
  { key: "collections", color: C.collections, label: () => L("Collected", "التحصيل", "Encaissé"), hint: () => L("receipts booked this month", "التحصيل المسجل في الشهر", "encaissements du mois") },
  { key: "cost", color: C.cost, label: () => L("Cost of goods", "تكلفة البضاعة", "Coût des ventes"), hint: () => L("as booked in the ledger", "زي ما هي في الدفاتر", "comptabilisé") },
  { key: "margin", color: C.margin, label: () => L("Margin", "الهامش", "Marge"), hint: () => L("sales − cost of goods", "المبيعات − التكلفة", "ventes − coût") },
  { key: "radar", color: C.radar, label: () => L("Radar", "الرادار", "Radar"), hint: () => L("what does not add up", "اللي مش منطقي", "ce qui cloche") },
];
const TABS = [
  { key: "sales", color: C.sales, label: () => L("Sales", "المبيعات", "Ventes") },
  { key: "collections", color: C.collections, label: () => L("Collections", "التحصيل", "Encaissements") },
  { key: "cost", color: C.cost, label: () => L("Cost & margin", "التكلفة والهامش", "Coût & marge") },
  { key: "radar", color: C.radar, label: () => L("Radar — everything", "الرادار — كله", "Radar — tout") },
];

// which order buckets and which month alerts belong to which station
const STATION_BUCKETS = {
  sales: ["collected_no_invoice", "delivered_no_invoice", "prepaid_no_invoice", "exchange_overbilled", "invoiced_not_delivered", "invoice_no_shipment", "returned_invoice_stands"],
  collections: ["prepaid_cod_receipt", "prepaid_unmatched", "funded_no_receipt", "amount_mismatch", "invoice_vs_paid", "transfer_late", "returned_but_collected", "stuck_at_carrier", "no_carrier_record"],
  cost: ["cogs_high", "cogs_zero", "cogs_low", "dup_dn", "cancelled_goods_out", "return_not_received"],
};
const WATCH = ["in_transit", "awaiting_transfer", "return_in_progress"];
const ALERT_STATION = {
  negative_margin: "cost", margin_off: "cost", cost_outside_deliveries: "cost", unit_cost_jump: "cost",
  uncollected: "collections", overcollected: "collections", bank_gap: "collections", returns_spike: "sales",
};

function bucketsFor(m, tab) {
  const keys = tab === "radar" ? Object.keys(m.buckets || {}) : (STATION_BUCKETS[tab] || []);
  return keys.filter((k) => m.buckets?.[k]?.n)
    .map((k) => ({ key: k, n: m.buckets[k].n, value: m.buckets[k].value, watch: WATCH.includes(k) }))
    .sort((a, b) => (a.watch - b.watch) || (b.value - a.value));
}
function alertsFor(m, tab) {
  return (m.anomalies || []).filter((a) => tab === "radar" || ALERT_STATION[a.key] === tab);
}
function stationSev(m, st) {
  const al = alertsFor(m, st);
  if (al.some((a) => a.sev === "high")) return "high";
  const bad = bucketsFor(m, st).filter((b) => !b.watch).reduce((s, b) => s + b.value, 0);
  if (al.length || bad > 0.01 * (m.money.sales || 1)) return "medium";
  return "";
}
function tabCount(m, tab) {
  return alertsFor(m, tab).length + bucketsFor(m, tab).filter((b) => !b.watch).length;
}
const cellCls = (m, st) => (sel.month === m.month && (sel.tab === st || (st === "margin" && sel.tab === "cost")) ? "cell-on" : "");

const medGm = computed(() => {
  const cur = new Date().toISOString().slice(0, 7);
  const v = months.value.filter((m) => m.month < cur && m.money.gm_pct != null).map((m) => m.money.gm_pct).sort((a, b) => a - b);
  return v.length ? v[Math.floor(v.length / 2)] : null;
});
function gmStyle(m) {
  const a = (m.anomalies || []).find((x) => x.key === "margin_off" || x.key === "negative_margin");
  if (a && a.sev === "high") return "background:#fee2e2;color:#b91c1c";
  if (a) return "background:#fef3c7;color:#92400e";
  return "background:#d1fae5;color:#065f46";
}
function gmNote(m) {
  if (medGm.value == null || m.money.gm_pct == null) return "";
  const diff = Math.round((m.money.gm_pct - medGm.value) * 10) / 10;
  return Math.abs(diff) < 1 ? L("in line", "طبيعي", "normal") : `${diff > 0 ? "+" : ""}${diff} ${L("pts vs usual", "نقطة عن المعتاد", "pts vs habituel")}`;
}

function facts(m, tab) {
  const x = m.money;
  if (tab === "sales") return [
    { label: L("Sales incl. VAT", "المبيعات شامل الضريبة", "Ventes TTC"), value: n(x.sales) },
    { label: L("Invoices", "فواتير", "Factures"), value: n(x.invoices) },
    { label: L("Credit notes", "إشعارات دائنة", "Avoirs"), value: n(x.credit_notes) },
    { label: L("Return rate", "نسبة المرتجع", "Taux de retour"), value: pct(m.return_rate) },
  ];
  if (tab === "collections") return [
    { label: L("Cathedis COD", "تحصيل كاتدييس", "COD Cathedis"), value: n(x.cathedis) },
    { label: L("Payzone", "Payzone", "Payzone"), value: n(x.payzone) },
    { label: L("Bank / deposit", "بنك / إيداع", "Banque / dépôt"), value: n(x.bank) },
    { label: L("Refunds", "مرتجع فلوس", "Remboursements"), value: n(-x.refunds) },
    { label: L("Unpaid on this month's invoices", "غير متحصّل من فواتير الشهر", "Impayé du mois"), value: n(x.uncollected), color: x.uncollected > 500 ? "#b91c1c" : null },
    { label: L("Cathedis paid us", "كاتدييس حوّلت", "Versé par Cathedis"), value: n(m.bank?.cathedis_funded) },
    { label: L("Bank received", "البنك استلم", "Reçu en banque"), value: n(m.bank?.bank_credited) },
    { label: L("Bank − Cathedis", "البنك − كاتدييس", "Banque − Cathedis"), value: n(m.bank?.diff), color: Math.abs(m.bank?.diff || 0) > 0.03 * (m.bank?.cathedis_funded || 1) ? "#b45309" : null },
  ];
  if (tab === "cost") return [
    { label: L("Cost of goods", "تكلفة البضاعة", "Coût des ventes"), value: n(x.cogs) },
    { label: L("From delivery notes", "من أذون التسليم", "Depuis les BL"), value: n(x.cogs_dn) },
    { label: L("Booked outside deliveries", "متسجلة برة الأذون", "Hors BL"), value: n(x.cogs_other), color: Math.abs(x.cogs_other) > 0.03 * Math.abs(x.cogs || 1) ? "#b45309" : null },
    { label: L("Gross margin", "الهامش الإجمالي", "Marge brute"), value: `${n(x.margin)} · ${pct(x.gm_pct)}` },
    { label: L("Supplier bills in cost", "فواتير موردين في التكلفة", "Factures fournisseurs"), value: n(x.cogs_bills) },
    { label: L("Journals in cost", "قيود في التكلفة", "OD en coût"), value: n(x.cogs_journals) },
    { label: L("Units delivered", "وحدات اتسلّمت", "Unités livrées"), value: n(x.units) },
    { label: L("Cost per unit", "تكلفة الوحدة", "Coût unitaire"), value: money(x.unit_cost) },
  ];
  return [
    { label: L("Month alerts", "تنبيهات الشهر", "Alertes du mois"), value: n((m.anomalies || []).length), color: (m.anomalies || []).length ? "#b91c1c" : null },
    { label: L("Order exceptions", "أوردرات مش مظبوطة", "Écarts commandes"), value: `${n(m.exceptions)} · ${n(m.exception_value)}` },
    { label: L("Closed clean", "مقفول للآخر", "Clôturées OK"), value: pct(m.clean_pct) },
    { label: L("Still moving", "لسه في السكة", "En cours"), value: n(m.watch) },
  ];
}
function funnel(m) {
  const base = m.orders || 1;
  return [
    { key: "o", label: L("Ordered", "اتطلب", "Commandé"), n: m.orders, color: "#a8a29e" },
    { key: "s", label: L("Shipped", "اتشحن", "Expédié"), n: m.shipped, color: "#78716c" },
    { key: "d", label: L("Delivered", "اتسلّم", "Livré"), n: m.delivered, color: C.sales },
    { key: "i", label: L("Invoiced", "اتفوتر", "Facturé"), n: m.invoiced, color: C.sales },
    { key: "c", label: L("Cathedis paid", "كاتدييس حوّلت", "Versé"), n: m.collected, color: C.collections },
    { key: "r", label: L("Returned", "رجع", "Retourné"), n: m.returned, color: "#d6d3d1" },
  ].map((f) => ({ ...f, pct: Math.round((100 * (f.n || 0)) / base) }));
}

function alertText(a) {
  const f = (v) => n(v);
  switch (a.key) {
    case "negative_margin": return L(`Cost of goods (${f(a.a)}) is higher than sales (${f(a.b)})`, `تكلفة البضاعة (${f(a.a)}) أعلى من المبيعات (${f(a.b)})`, `Coût (${f(a.a)}) > ventes (${f(a.b)})`);
    case "margin_off": return L(`Margin ${a.a}% against the usual ${a.b}%`, `الهامش ${a.a}% والمعتاد ${a.b}%`, `Marge ${a.a}% vs ${a.b}% habituel`);
    case "cost_outside_deliveries": return L(`${f(a.a)} of cost booked outside delivery notes`, `${f(a.a)} تكلفة متسجلة برة أذون التسليم`, `${f(a.a)} de coût hors BL`);
    case "unit_cost_jump": return L(`Cost per unit ${a.a} against the usual ${a.b}`, `تكلفة الوحدة ${a.a} والمعتاد ${a.b}`, `Coût unitaire ${a.a} vs ${a.b}`);
    case "uncollected": return L(`${f(a.a)} of this month's invoices still unpaid`, `${f(a.a)} من فواتير الشهر لسه مش متحصّلة`, `${f(a.a)} de factures impayées`);
    case "overcollected": return L(`${f(a.a)} received above the invoices`, `${f(a.a)} متحصّل زيادة عن الفواتير`, `${f(a.a)} encaissé en trop`);
    case "bank_gap": return L(`Bank received ${f(a.a)}, Cathedis says it paid ${f(a.b)}`, `البنك استلم ${f(a.a)} وكاتدييس بتقول حوّلت ${f(a.b)}`, `Banque ${f(a.a)} vs Cathedis ${f(a.b)}`);
    case "returns_spike": return L(`Returns ${a.a}% against the usual ${a.b}%`, `المرتجع ${a.a}% والمعتاد ${a.b}%`, `Retours ${a.a}% vs ${a.b}%`);
    default: return a.key;
  }
}
function alertWhy(a) {
  switch (a.key) {
    case "negative_margin":
    case "margin_off": return L("Usually cost booked outside delivery notes, or invoices missing — open the documents.", "غالبًا تكلفة متسجلة برة الأذون أو فواتير ناقصة — افتح المستندات.", "Souvent un coût hors BL ou des factures manquantes.");
    case "cost_outside_deliveries": return L(`Supplier bills ${n(a.b)} and journals ${n(a.c)} posted straight to cost; cost of goods should come from delivery notes.`, `فواتير موردين ${n(a.b)} وقيود ${n(a.c)} متسجلة على التكلفة مباشرة؛ التكلفة المفروض تيجي من أذون التسليم.`, `Factures ${n(a.b)} et OD ${n(a.c)} passées en coût direct.`);
    case "unit_cost_jump": return L("Check the items in the cost exceptions below.", "راجع الأصناف في استثناءات التكلفة تحت.", "Voir les écarts de coût ci-dessous.");
    case "uncollected": return L("Delivered and invoiced, but no receipt — usually a missing COD receipt or a prepaid order.", "اتسلّم واتفوتر ومفيش تحصيل — غالبًا تحصيل ناقص أو أوردر مدفوع مقدم.", "Livré et facturé sans encaissement.");
    case "overcollected": return L("A receipt larger than its invoice, or allocated twice.", "تحصيل أكبر من الفاتورة أو متخصص مرتين.", "Encaissement supérieur à la facture.");
    case "bank_gap": return L("Partly timing (Cathedis pays, the bank books later); a lasting gap is a missing or extra remittance.", "جزء منه توقيت؛ لو الفرق مستمر يبقى تحويل ناقص أو زيادة.", "En partie un décalage de date.");
    case "returns_spike": return L("More parcels came back than usual — check the carrier and the products.", "طرود رجعت أكتر من المعتاد — راجع الكاريير والمنتجات.", "Plus de retours que d'habitude.");
    default: return "";
  }
}
const docsKind = (a) => ({ uncollected: "unpaid_invoices", overcollected: "overpaid_invoices", cost_outside_deliveries: "cost_outside",
  margin_off: "cost_outside", negative_margin: "cost_outside" }[a.key] || "");
const docsTitle = (k) => ({
  unpaid_invoices: L("Unpaid invoices of the month", "فواتير الشهر غير المتحصّلة", "Factures impayées du mois"),
  overpaid_invoices: L("Invoices paid above their total", "فواتير متحصّلة زيادة", "Factures trop payées"),
  cost_outside: L("Cost of goods not from a delivery note", "تكلفة مش من إذن تسليم", "Coût hors BL"),
}[k] || k);

// [en, ar, fr, hint en, hint ar, hint fr]
const B = {
  collected_no_invoice: ["Collected, no invoice", "اتحصّل ومالوش فاتورة", "Encaissé sans facture", "Cathedis paid us; no revenue booked", "كاتدييس حوّلت ومفيش إيراد", "pas de CA"],
  delivered_no_invoice: ["Delivered, no invoice", "اتسلّم ومالوش فاتورة", "Livré sans facture", "carrier confirms delivery", "الكاريير مأكد التسليم", "livraison confirmée"],
  prepaid_no_invoice: ["Prepaid, no invoice", "مدفوع مقدم ومالوش فاتورة", "Prépayé sans facture", "Cathedis collected 0", "كاتدييس حصّلت صفر", "COD 0"],
  exchange_overbilled: ["Exchange billed at full price", "تبديل متفوتر بالسعر الكامل", "Échange facturé plein tarif", "only the difference is owed", "المستحق الفرق بس", "seule la différence est due"],
  prepaid_cod_receipt: ["Prepaid, but a COD receipt", "مدفوع مقدم وعليه تحصيل كاتدييس", "Prépayé avec COD", "Cathedis collected 0", "كاتدييس حصّلت صفر", "COD 0"],
  prepaid_unmatched: ["Prepaid, payment not found", "مدفوع مقدم والفلوس مش متسجلة", "Prépayé, paiement introuvable", "no Payzone / bank receipt", "مفيش تحصيل Payzone أو بنك", "aucun encaissement"],
  funded_no_receipt: ["Cathedis paid, no receipt", "كاتدييس حوّلت ومفيش تحصيل", "Versé sans encaissement", "invoice still open", "الفاتورة لسه مفتوحة", "facture ouverte"],
  amount_mismatch: ["Collected ≠ receipt", "المحصّل ≠ المسجل", "Encaissé ≠ enregistré", "Cathedis collected a different amount", "كاتدييس حصّلت مبلغ تاني", "montant différent"],
  invoice_vs_paid: ["Invoice ≠ money received", "الفاتورة ≠ الفلوس", "Facture ≠ encaissé", "open balance or overpaid", "رصيد مفتوح أو زيادة", "solde ou trop-perçu"],
  transfer_late: ["Cathedis late to pay", "كاتدييس اتأخرت", "Versement en retard", "more than 15 days", "أكتر من 15 يوم", "plus de 15 jours"],
  returned_but_collected: ["Returned, but a receipt stands", "رجع وعليه تحصيل", "Retourné mais encaissé", "receipt on a returned parcel", "تحصيل على طرد رجع", "encaissement sur retour"],
  returned_invoice_stands: ["Returned, invoice stands", "رجع والفاتورة واقفة", "Retourné, facture maintenue", "needs a credit note", "محتاج إشعار دائن", "avoir nécessaire"],
  return_not_received: ["Returned, not back in stock", "مرتجع ومش في المخزن", "Retour non réceptionné", "no return note after 20 days", "مفيش إذن مرتجع بعد 20 يوم", "pas de BL retour"],
  invoiced_not_delivered: ["Invoiced, not delivered", "متفوتر ومااتسلمش", "Facturé non livré", "revenue before delivery", "إيراد قبل التسليم", "CA avant livraison"],
  stuck_at_carrier: ["Stuck at Cathedis", "واقف عند كاتدييس", "Bloqué chez Cathedis", "no delivery, no return after 20 days", "لا اتسلّم ولا رجع", "ni livré ni retourné"],
  no_carrier_record: ["Unknown to Cathedis", "كاتدييس مش لاقياه", "Inconnu de Cathedis", "parcel number not found", "رقم الطرد مش موجود", "AWB absent"],
  dup_dn: ["Two delivery notes, one parcel", "إذنين لطرد واحد", "Deux BL, un colis", "stock counted twice", "المخزون اتخصم مرتين", "stock compté 2×"],
  cancelled_goods_out: ["Cancelled, goods went out", "ملغي والبضاعة خرجت", "Annulée, marchandise sortie", "no return recorded", "مفيش مرتجع", "aucun retour"],
  invoice_no_shipment: ["Invoice, nothing shipped", "فاتورة ومفيش شحن", "Facture sans expédition", "revenue with no delivery note", "إيراد من غير إذن", "CA sans BL"],
  cogs_zero: ["Cost is zero", "التكلفة صفر", "Coût nul", "left the warehouse at no cost", "خرجت بتكلفة صفر", "sortie à coût nul"],
  cogs_high: ["Cost looks inflated", "التكلفة متضخمة", "Coût gonflé", "≥1.8× its history, or above its price", "≥1.8× تاريخه أو أعلى من سعره", "≥1,8× l'historique"],
  cogs_low: ["Cost looks too low", "التكلفة قليلة بشكل غريب", "Coût trop bas", "under 0.4× its history", "أقل من 0.4× تاريخه", "< 0,4× l'historique"],
  in_transit: ["In transit", "في الطريق", "En transit", "younger than 20 days", "أحدث من 20 يوم", "< 20 jours"],
  awaiting_transfer: ["Delivered, transfer coming", "اتسلّم والتحويل جاي", "Livré, versement à venir", "Cathedis has not paid yet", "كاتدييس لسه ماحوّلتش", "pas encore versé"],
  return_in_progress: ["Return on its way", "المرتجع في الطريق", "Retour en cours", "younger than 20 days", "أحدث من 20 يوم", "< 20 jours"],
};
const label = (k) => (B[k] ? L(B[k][0], B[k][1], B[k][2]) : k);
const hint = (k) => (B[k] ? L(B[k][3], B[k][4], B[k][5]) : "");

function resetDrill() { pickKey.value = ""; drillRows.value = []; docs.kind = ""; docs.rows = []; }
function openTab(month, tab) {
  if (sel.month === month && sel.tab === tab) { sel.month = ""; return; }
  sel.month = month; sel.tab = tab; resetDrill();
}
function setTab(tab) { sel.tab = tab; resetDrill(); }

async function load() {
  loading.value = true; error.value = ""; sel.month = ""; resetDrill();
  try {
    d.value = await api.call("accounting_portal.api.radar.summary", { company: currentCompany(), year: props.year }, { fresh: true });
  } catch (e) { error.value = (e && e.message) || String(e); d.value = null; }
  finally { loading.value = false; }
}
async function pick(month, bucket) {
  docs.kind = "";
  pickKey.value = `${month}|${bucket}`; drillLoading.value = true;
  try {
    const r = await api.call("accounting_portal.api.radar.drill", { company: currentCompany(), year: props.year, month, bucket, limit: 300 }, { fresh: true });
    drillRows.value = r.rows || []; drillTotal.value = r.total || 0;
  } catch (e) { alert((e && e.message) || e); }
  finally { drillLoading.value = false; }
}
async function openDocs(month, kind) {
  pickKey.value = "";
  docs.kind = kind; docs.loading = true; docs.rows = [];
  try {
    const r = await api.call("accounting_portal.api.radar.month_docs", { company: currentCompany(), month, kind }, { fresh: true });
    docs.rows = r.rows || [];
  } catch (e) { alert((e && e.message) || e); }
  finally { docs.loading = false; }
}
async function bill(r) {
  if (!confirm(L(`Invoice ${r.so} and record its Cathedis receipt?`, `فوترة ${r.so} وتسجيل تحصيل كاتدييس؟`, `Facturer ${r.so} ?`))) return;
  busy.value = r.so;
  try {
    await api.call("accounting_portal.api.radar.bill_order", { company: currentCompany(), so: r.so, dn: r.dn });
    drillRows.value = drillRows.value.filter((x) => x.so !== r.so);
  } catch (e) { alert((e && e.message) || e); }
  finally { busy.value = ""; }
}
async function creditNote(r) {
  if (!confirm(L(`Issue a credit note against ${r.si}? The parcel came back.`, `إصدار إشعار دائن على ${r.si}؟ الطرد رجع.`, `Émettre un avoir sur ${r.si} ?`))) return;
  busy.value = r.so;
  try {
    await api.call("accounting_portal.api.sales.create_sales_return", { company: currentCompany(), invoice: r.si, reason: "monthly cycle — parcel returned, invoice stood" });
    drillRows.value = drillRows.value.filter((x) => x.so !== r.so);
  } catch (e) { alert((e && e.message) || e); }
  finally { busy.value = ""; }
}
async function syncCathedis() {
  syncing.value = true;
  try {
    await api.call("accounting_portal.api.cathedis_sync.sync_now", {});
    note.value = L("Asking Cathedis about the open parcels in the background — the snapshot rebuilds when it finishes (about two minutes). Reload then.",
      "بنسأل كاتدييس عن الطرود المفتوحة في الخلفية — اللقطة هتتبني لما يخلص (حوالي دقيقتين). اعمل reload بعدها.", "Synchro en arrière-plan (~2 min), puis rechargez.");
  } catch (e) { alert((e && e.message) || e); }
  finally { syncing.value = false; }
}
async function rebuild() {
  rebuilding.value = true;
  try {
    await api.call("accounting_portal.api.radar.rebuild_now", { company: currentCompany(), year: props.year });
    note.value = L("Rebuilding in the background (about a minute). Reload then.", "بيتبني في الخلفية (حوالي دقيقة). اعمل reload بعدها.", "Recalcul en cours (~1 min).");
  } catch (e) { alert((e && e.message) || e); }
  finally { rebuilding.value = false; }
}
watch(() => props.year, load);
onMounted(load);
defineExpose({ reload: load });
</script>

<style scoped>
.hcell { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--ink-muted, #78716c); }
.cell { width: 100%; text-align: start; border-radius: 10px; padding: 8px 10px; border: 1px solid transparent; transition: background-color .12s, border-color .12s; }
.cell:hover { background: rgba(245, 245, 244, .9); border-color: #e7e5e4; }
.cell:focus-visible { outline: 2px solid #0f766e; outline-offset: 1px; }
.cell-on { background: #fff; border-color: #d6d3d1; box-shadow: 0 1px 2px rgba(28, 25, 23, .06); }
.amt { font-size: 14px; font-weight: 800; font-variant-numeric: tabular-nums; }
.sub { font-size: 10.5px; color: #78716c; margin-top: 2px; font-variant-numeric: tabular-nums; }
</style>
