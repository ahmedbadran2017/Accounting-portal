<template>
  <div class="space-y-3.5">
    <!-- what the numbers can and cannot be used for, said before they are read -->
    <div class="rounded-[14px] px-4 py-3 border" style="background:#fffbeb;border-color:#fde68a">
      <div class="text-[12px] font-bold text-amber-900">
        {{ L("Provisional — the cost correction is still running","أرقام مبدئية — تصحيح التكلفة لسه جارٍ","Provisoire") }}
      </div>
      <div class="text-[11px] text-amber-800/80 mt-0.5">
        {{ L("Capital and drawings are facts and settle today. The cycle result moves while costs are being corrected, so agree the method now and the figure at close.",
             "رأس المال والمسحوبات حقائق ثابتة. نتيجة الدورة بتتحرك مع تصحيح التكاليف — فاتفق على المنهج دلوقتي والرقم عند الإقفال.",
             "Capital et retraits sont définitifs ; le résultat du cycle bouge encore.") }}
      </div>
    </div>

    <div v-if="loading" class="py-16 text-center text-[12px] text-ink-muted">{{ L("Loading…","جاري التحميل…","Chargement…") }}</div>
    <div v-else-if="err" class="py-16 text-center text-[12px]" style="color:#b91c1c">{{ err }}</div>

    <template v-else>
      <!-- who has money in -->
      <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
        <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2">
          <span class="text-[13px] font-bold">{{ L("Investors","المستثمرون","Investisseurs") }}</span>
          <span class="text-[10.5px] text-ink-muted">{{ list.length }}</span>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-[11.5px]">
            <thead><tr style="background:#fafaf9">
              <th class="px-3 py-2 text-start text-[10px] font-bold text-ink-muted">{{ L("Investor","المستثمر","Investisseur") }}</th>
              <th class="px-3 py-2 text-start text-[10px] font-bold text-ink-muted">{{ L("Entity","الكيان","Entité") }}</th>
              <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("Capital","رأس المال","Capital") }}</th>
              <th class="px-3 py-2 text-end text-[10px] font-bold text-ink-muted">{{ L("Drawn","المسحوب","Retiré") }}</th>
              <th class="px-3 py-2 text-center text-[10px] font-bold text-ink-muted">{{ L("Terms","الشروط","Conditions") }}</th>
              <th class="px-3 py-2"></th>
            </tr></thead>
            <tbody>
              <tr v-for="i in list" :key="i.account" class="border-t border-line-hair hover:bg-[#fafaf9]">
                <td class="px-3 py-2 font-bold">{{ i.name }}</td>
                <td class="px-3 py-2 text-ink-muted">{{ i.company }}</td>
                <td class="px-3 py-2 text-end tnum" dir="ltr">{{ fmt(i.capital) }} <span class="text-[9.5px] text-ink-muted">{{ i.currency }}</span></td>
                <td class="px-3 py-2 text-end tnum" dir="ltr">{{ i.drawn ? fmt(i.drawn) : "—" }}</td>
                <td class="px-3 py-2 text-center">
                  <span v-if="i.configured" class="text-[10px] font-bold px-1.5 py-0.5 rounded-full" style="background:#ecfdf5;color:#047857">
                    {{ i.share_pct }}% · {{ i.basis }}
                  </span>
                  <span v-else class="text-[10px] font-bold px-1.5 py-0.5 rounded-full" style="background:#fef2f2;color:#b91c1c">
                    {{ L("not set","غير محددة","non définies") }}
                  </span>
                </td>
                <td class="px-3 py-2 text-end">
                  <button class="h-[26px] px-2.5 rounded-[7px] text-[10.5px] font-bold border border-line hover:bg-app-warm"
                          @click="open(i.account)">{{ L("Statement","كشف الحساب","Relevé") }}</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- one investor -->
      <template v-if="st">
        <div class="bg-white border border-line rounded-[14px] shadow-card px-4 py-3.5">
          <div class="flex items-start gap-3 flex-wrap">
            <div class="min-w-0">
              <div class="text-[14px] font-bold">{{ st.name }}</div>
              <div class="text-[11px] text-ink-muted">{{ st.company }} · {{ L("agreed in","متفق عليه بـ","conclu en") }} {{ st.deal_currency }}</div>
            </div>
            <div class="flex-1"></div>
            <div v-for="f in headline" :key="f.k" class="text-end">
              <div class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ f.label }}</div>
              <div class="text-[17px] font-extrabold tnum" :class="f.tone" dir="ltr">{{ f.v }}</div>
              <div v-if="f.sub" class="text-[10px] text-ink-muted tnum" dir="ltr">{{ f.sub }}</div>
            </div>
          </div>
          <!-- the drift between the books and the obligation, named plainly -->
          <div v-if="st.fx_gap && Math.abs(st.fx_gap) > 1" class="mt-3 pt-3 border-t border-line-hair text-[11px]">
            <span class="font-bold" style="color:#b45309">{{ L("Unrecorded exchange movement","فرق عملة غير مسجّل","Écart de change non comptabilisé") }}:</span>
            <span class="tnum font-bold" dir="ltr"> {{ fmt(st.fx_gap) }} {{ st.currency }}</span>
            <span class="text-ink-muted"> — {{ L("the obligation is held in " + st.deal_currency + " but the books still carry it at the old rate; a revaluation has not been run.",
              "الالتزام بالـ" + st.deal_currency + " والدفاتر لسه بسعر قديم — إعادة التقييم ما اتعملتش.",
              "réévaluation non effectuée.") }}</span>
          </div>
        </div>

        <!-- the cycle, layer by layer -->
        <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
          <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2 flex-wrap">
            <span class="text-[13px] font-bold">{{ L("The cycle their money financed","الدورة اللي موّلها","Le cycle financé") }}</span>
            <span class="text-[10.5px] text-ink-muted tnum" dir="ltr">{{ st.cycle.from }} → {{ st.cycle.to }} · {{ st.cycle.months.length }}{{ L("m","ش","m") }} · USD</span>
            <span class="text-[10px] px-1.5 py-0.5 rounded-full font-bold" style="background:#f5f5f4;color:#57534e"
                  :title="L('the month being posted is never included — its revenue is in but its payroll, rent and courier bills are not',
                            'الشهر الجاري مش داخل — إيراده اتسجّل بس مرتباته وإيجاره وفواتير شحنه لسه',
                            'le mois en cours est exclu')">
              {{ L("closed months only","شهور مقفولة فقط","mois clos") }}
            </span>
            <div class="flex-1"></div>
            <span v-if="st.model" class="text-[10px] text-ink-muted tnum" dir="ltr"
                  :title="L('product cost is modelled, not read from the ledger','تكلفة المنتج محسوبة بالنموذج مش من الدفاتر','coût modélisé')">
              {{ st.cycle.units }} {{ L("units","قطعة","unités") }} ·
              {{ st.model.verified }} {{ L("verified","متحقق منها","vérifiés") }} ·
              <span :style="st.cycle.units_unpriced ? 'color:#b45309' : ''">{{ st.cycle.units_unpriced }} {{ L("unpriced","بدون تكلفة","sans coût") }}</span>
            </span>
          </div>
          <table class="w-full text-[11.5px]">
            <tbody>
              <tr v-for="l in st.layers" :key="l.key" class="border-t border-line-hair"
                  :class="st.terms && st.terms.basis === l.key ? 'bg-emerald-50/50' : ''">
                <td class="px-4 py-2 font-bold" :class="st.terms && st.terms.basis === l.key ? 'text-emerald-800' : ''">
                  {{ l.label }}
                  <span v-if="st.terms && st.terms.basis === l.key" class="text-[9.5px] font-bold px-1.5 py-0.5 rounded-full ms-1" style="background:#ecfdf5;color:#047857">
                    {{ L("agreed basis","الأساس المتفق عليه","base convenue") }}
                  </span>
                </td>
                <td class="px-4 py-2 text-[10.5px] text-ink-muted">{{ l.hint }}</td>
                <td class="px-4 py-2 text-end tnum font-bold" :class="l.value < 0 ? 'text-sale' : ''" dir="ltr">{{ fmt(l.value) }}</td>
              </tr>
            </tbody>
          </table>
          <div class="px-4 py-2.5 border-t border-line-hair text-[11px]" :style="st.share ? '' : 'color:#b91c1c'">
            <template v-if="st.share">
              <span class="font-bold">{{ L("Their share","نصيبه","Sa part") }} ({{ st.terms.share_pct }}%):</span>
              <span class="tnum font-extrabold text-[13px]" dir="ltr"> {{ fmt(st.share.amount) }} USD</span>
              <span v-if="st.share.note" class="text-ink-muted"> — {{ st.share.note }}</span>
            </template>
            <template v-else-if="st.goods">
              {{ L("The share is computed from the capital table below, not from a percentage typed into terms.",
                   "النصيب محسوب من جدول رأس المال تحت، مش من نسبة متكتوبة في الشروط.",
                   "Part calculée depuis le tableau de capital.") }}
            </template>
            <template v-else>
              {{ L("No terms recorded — the share cannot be computed. Set the percentage, the basis line, and whether losses are shared.",
                   "مفيش شروط مسجّلة — النصيب مش هيتحسب. حدد النسبة والسطر الأساس وهل الخسارة بتتشارك.",
                   "Conditions non enregistrées.") }}
            </template>
          </div>
        </div>

        <!-- what the goods actually cost to run, and who carried it -->
        <div v-if="st.overhead_rows && st.overhead_rows.length" class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
          <div class="px-4 py-3 border-b border-line-hair">
            <div class="text-[13px] font-bold">{{ L("Running costs charged to the goods","المصاريف المحمّلة على البضاعة","Frais imputés aux marchandises") }}</div>
            <div class="text-[11px] text-ink-muted mt-0.5">
              {{ L("A cost is charged here when handling or selling the goods required it. Building the sourcing operation is an investment in the group, not a cost of this cycle.",
                   "المصروف بيتحمّل هنا لما تشغيل أو بيع البضاعة يحتاجه. بناء عملية التوريد استثمار في المجموعة، مش تكلفة الدورة دي.",
                   "Un coût est imputé ici lorsqu'il a été nécessaire.") }}
            </div>
          </div>
          <table class="w-full text-[11.5px]">
            <tbody>
              <tr v-for="(o, i) in st.overhead_rows" :key="i" class="border-t border-line-hair">
                <td class="px-4 py-2 font-bold">{{ o.label }}</td>
                <td class="px-4 py-2 text-[10.5px] text-ink-muted">{{ o.why }}</td>
                <td class="px-4 py-2 text-end text-[10.5px] text-ink-muted tnum" dir="ltr">{{ o.share_pct }}%</td>
                <td class="px-4 py-2 text-end tnum font-bold" dir="ltr">{{ fmt(o.usd) }}</td>
              </tr>
              <tr class="border-t border-line" style="background:#fafaf9">
                <td class="px-4 py-2 font-bold" colspan="3">
                  {{ L("Charged to the goods","المحمّل على البضاعة","Imputé") }}
                  <span class="text-[10.5px] font-normal text-ink-muted">
                    {{ L("of","من","de") }} {{ fmt(st.cycle.overhead_total) }} {{ L("total running costs","إجمالي المصاريف","total") }}
                    ({{ st.cycle.overhead_goods_pct }}%)</span>
                </td>
                <td class="px-4 py-2 text-end tnum font-extrabold" dir="ltr">{{ fmt(st.cycle.overhead_goods) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- capital, share, and what it turns into -->
        <template v-if="st.goods">
          <div class="grid lg:grid-cols-2 gap-3">
            <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
              <div class="px-4 py-2.5 border-b border-line-hair">
                <div class="text-[12px] font-bold">{{ L("Capital in the goods","رأس المال في البضاعة","Capital dans les marchandises") }}</div>
                <div class="text-[10.5px] text-ink-muted tnum" dir="ltr">
                  {{ st.capital_basis && st.capital_basis.date }} · {{ st.capital_basis && st.capital_basis.source }}
                </div>
              </div>
              <table class="w-full text-[11.5px]">
                <tbody>
                  <tr v-for="(d, i) in (st.capital_basis && st.capital_basis.detail) || []" :key="i" class="border-t border-line-hair">
                    <td class="px-4 py-1.5">{{ d.location }}</td>
                    <td class="px-4 py-1.5 text-end text-[10.5px] text-ink-muted tnum" dir="ltr">{{ d.native }}</td>
                    <td class="px-4 py-1.5 text-end tnum" dir="ltr">{{ fmt(d.usd) }}</td>
                  </tr>
                  <tr class="border-t border-line" style="background:#fafaf9">
                    <td class="px-4 py-2 font-bold">{{ L("Counted stock","المخزون المجرود","Stock compté") }}</td>
                    <td></td>
                    <td class="px-4 py-2 text-end tnum font-extrabold" dir="ltr">{{ fmt(st.goods.stock_usd) }}</td>
                  </tr>
                  <tr class="border-t border-line-hair">
                    <td class="px-4 py-1.5 font-bold">{{ st.name }}</td>
                    <td class="px-4 py-1.5 text-end text-[10.5px] font-bold tnum" style="color:#047857" dir="ltr">{{ st.goods.pct }}%</td>
                    <td class="px-4 py-1.5 text-end tnum font-bold" dir="ltr">{{ fmt(st.goods.capital_usd) }}</td>
                  </tr>
                  <tr class="border-t border-line-hair">
                    <td class="px-4 py-1.5">{{ L("The company","الشركة","La société") }}</td>
                    <td class="px-4 py-1.5 text-end text-[10.5px] text-ink-muted tnum" dir="ltr">{{ st.goods.company_pct }}%</td>
                    <td class="px-4 py-1.5 text-end tnum" dir="ltr">{{ fmt(st.goods.company_usd) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
              <div class="px-4 py-2.5 border-b border-line-hair text-[12px] font-bold">
                {{ L("What it comes to","اللي بيطلع منها","Ce qui en résulte") }}
              </div>
              <table class="w-full text-[11.5px]">
                <tbody>
                  <tr class="border-t border-line-hair">
                    <td class="px-4 py-2 font-bold">{{ L("Profit on the goods","ربح البضاعة","Profit") }}</td>
                    <td class="px-4 py-2 text-end tnum font-bold" :class="st.goods.profit < 0 ? 'text-sale' : ''" dir="ltr">{{ fmt(st.goods.profit) }}</td>
                  </tr>
                  <tr class="border-t border-line-hair">
                    <td class="px-4 py-2 ps-7">{{ L("earned by his capital","اللي كسبه رأس ماله","part de son capital") }} · {{ st.goods.pct }}%</td>
                    <td class="px-4 py-2 text-end tnum" dir="ltr">{{ fmt(st.goods.his_capital_share) }}</td>
                  </tr>
                  <tr class="border-t border-line-hair">
                    <td class="px-4 py-2 ps-7 text-ink-muted">{{ L("earned by the company's capital","اللي كسبه رأس مال الشركة","part de la société") }} · {{ st.goods.company_pct }}%</td>
                    <td class="px-4 py-2 text-end tnum text-ink-muted" dir="ltr">{{ fmt(st.goods.company_capital_share) }}</td>
                  </tr>
                  <tr class="border-t border-line-hair">
                    <td class="px-4 py-2 font-bold">{{ L("His half of his own share","نصه من نصيبه","Sa moitié") }}</td>
                    <td class="px-4 py-2 text-end tnum font-bold" dir="ltr">{{ fmt(st.goods.his_half) }}</td>
                  </tr>
                  <tr class="border-t border-line-hair">
                    <td class="px-4 py-2 text-ink-muted">{{ L("the operator's half","نص المشغّل","la moitié de l'opérateur") }}</td>
                    <td class="px-4 py-2 text-end tnum text-ink-muted" dir="ltr">{{ fmt(st.goods.operator_half) }}</td>
                  </tr>
                  <tr class="border-t border-line-hair">
                    <td class="px-4 py-2">{{ L("Already drawn","المسحوب بالفعل","Déjà retiré") }}</td>
                    <td class="px-4 py-2 text-end tnum text-sale" dir="ltr">−{{ fmt(st.goods.drawn) }}</td>
                  </tr>
                  <tr class="border-t border-line" :style="st.goods.loss && !st.goods.shares_losses ? 'background:#fffbeb' : 'background:#ecfdf5'">
                    <td class="px-4 py-2.5 font-extrabold" :style="st.goods.loss && !st.goods.shares_losses ? 'color:#b45309' : 'color:#047857'">
                      {{ st.goods.loss && !st.goods.shares_losses
                          ? L("Drawings to recover from a later cycle","مسحوبات تُسترد من دورة جاية","Avances à récupérer")
                          : L("Outstanding to him","المستحق له","Solde dû") }}
                    </td>
                    <td class="px-4 py-2.5 text-end tnum font-extrabold text-[14px]"
                        :style="st.goods.loss && !st.goods.shares_losses ? 'color:#b45309' : 'color:#047857'" dir="ltr">
                      {{ fmt(st.goods.loss && !st.goods.shares_losses ? st.goods.advance_outstanding : st.goods.outstanding) }} USD
                    </td>
                  </tr>
                </tbody>
              </table>
              <div v-if="st.goods.loss && !st.goods.shares_losses" class="px-4 py-2.5 border-t border-line-hair text-[11px]" style="background:#fffbeb;color:#92400e">
                {{ L("The cycle lost money and the terms do not make him carry losses, so his share is nil rather than negative. What he has drawn stands as an advance against a later cycle — not a balance he owes back.",
                     "الدورة خسرت والشروط ما بتحمّلهوش الخسارة، فنصيبه صفر مش بالسالب. اللي سحبه يفضل سلفة على دورة جاية — مش دين عليه يرجّعه.",
                     "Le cycle est déficitaire ; sa part est nulle, non négative.") }}
              </div>
            </div>
          </div>

          <!-- the one judgement in the whole statement, argued in the open -->
          <div v-if="st.goods.sensitivity.length > 1" class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
            <div class="px-4 py-2.5 border-b border-line-hair">
              <div class="text-[12px] font-bold">{{ L("If the capital base were read differently","لو اتقرأ رأس المال بشكل تاني","Autres lectures du capital") }}</div>
              <div class="text-[10.5px] text-ink-muted">
                {{ L("His percentage depends on what counts as the stock he bought into — the only judgement in this statement.",
                     "نسبته بتتغير حسب إيه اللي يتحسب مخزون اشترى فيه — دي الحاجة الوحيدة اللي فيها اجتهاد هنا.",
                     "Le seul jugement de ce relevé.") }}
              </div>
            </div>
            <table class="w-full text-[11.5px]">
              <tbody>
                <tr v-for="(x, i) in st.goods.sensitivity" :key="i" class="border-t border-line-hair" :class="x.chosen ? 'bg-emerald-50/50' : ''">
                  <td class="px-4 py-2" :class="x.chosen ? 'font-bold text-emerald-800' : ''">{{ x.label }}</td>
                  <td class="px-4 py-2 text-end text-[10.5px] text-ink-muted tnum" dir="ltr">{{ fmt(x.base_usd) }}</td>
                  <td class="px-4 py-2 text-end tnum font-bold" dir="ltr">{{ x.pct }}%</td>
                  <td class="px-4 py-2 text-end tnum font-bold" dir="ltr">{{ fmt(x.amount) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>

        <!-- movements -->
        <div class="grid lg:grid-cols-2 gap-3">
          <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
            <div class="px-4 py-2.5 border-b border-line-hair text-[12px] font-bold">{{ L("Capital movements","حركات رأس المال","Mouvements de capital") }}</div>
            <table class="w-full text-[11px]">
              <tbody>
                <tr v-for="(m, i) in st.moves" :key="i" class="border-t border-line-hair">
                  <td class="px-3 py-1.5 tnum text-ink-muted" dir="ltr">{{ m.date }}</td>
                  <td class="px-3 py-1.5 text-end tnum" dir="ltr">{{ fmt(m.local) }}</td>
                  <td class="px-3 py-1.5 text-end tnum text-[10px] text-ink-muted" dir="ltr">@{{ m.rate }}</td>
                  <td class="px-3 py-1.5 text-end tnum font-bold" dir="ltr">
                    {{ fmt(m.deal) }} {{ st.deal_currency }}
                    <span v-if="m.estimated" class="text-[9px] font-bold px-1 py-0.5 rounded ms-1" style="background:#fffbeb;color:#b45309"
                          :title="L('converted at the rate of that date — the amount was not recorded in ' + st.deal_currency,'محوّل بسعر التاريخ — المبلغ مش متسجل بالـ' + st.deal_currency,'estimé')">≈</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
            <div class="px-4 py-2.5 border-b border-line-hair text-[12px] font-bold">
              {{ L("Drawings","المسحوبات","Retraits") }}
              <span class="text-[10px] font-normal text-ink-muted">
                — {{ L("each valued at its own date's rate","كل واحد بسعر تاريخه","au taux de sa date") }}</span>
              <span v-if="!st.profit_account" class="text-[10px] font-normal text-ink-muted"> — {{ L("no drawings account","مفيش حساب مسحوبات","aucun compte") }}</span>
            </div>
            <table class="w-full text-[11px]">
              <tbody>
                <tr v-for="(d, i) in st.draws" :key="i" class="border-t border-line-hair">
                  <td class="px-3 py-1.5 tnum text-ink-muted" dir="ltr">{{ d.date }}</td>
                  <td class="px-3 py-1.5 text-end tnum" dir="ltr">{{ fmt(d.local) }}</td>
                  <td class="px-3 py-1.5 text-end tnum text-[10px] text-ink-muted" dir="ltr">@{{ d.rate }}</td>
                  <td class="px-3 py-1.5 text-end tnum font-bold" dir="ltr">
                    {{ fmt(d.deal) }} {{ st.deal_currency }}
                    <span v-if="d.estimated" class="text-[9px] font-bold px-1 py-0.5 rounded ms-1" style="background:#fffbeb;color:#b45309">≈</span>
                  </td>
                </tr>
                <tr v-if="!st.draws.length"><td class="px-3 py-4 text-center text-[11px] text-ink-muted">—</td></tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- why the cycle figure is not final -->
        <div v-if="st.quality.length" class="bg-white border rounded-[14px] shadow-card overflow-hidden" style="border-color:#fde68a">
          <div class="px-4 py-2.5 border-b text-[12px] font-bold" style="border-color:#fde68a;background:#fffbeb">
            {{ L("What would still move this figure","الحاجات اللي لسه هتحرك الرقم ده","Ce qui peut encore bouger") }}
          </div>
          <table class="w-full text-[11px]">
            <tbody>
              <tr v-for="(q, i) in st.quality" :key="i" class="border-t border-line-hair">
                <td class="px-4 py-2">{{ q.issue }}</td>
                <td class="px-4 py-2 text-end text-[10.5px] font-bold"
                    :style="q.effect.includes('overstated') ? 'color:#b91c1c' : 'color:#b45309'">{{ q.effect }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import api from "@/services/api";

const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const A = "accounting_portal.api.investors";

const loading = ref(true);
const err = ref("");
const list = ref([]);
const st = ref(null);

const fmt = (n) => (n === null || n === undefined ? "—"
  : new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(n));

const headline = computed(() => {
  const d = st.value;
  if (!d) return [];
  return [
    { k: "cap", label: L("Capital", "رأس المال", "Capital"),
      v: `${fmt(d.capital_deal)} ${d.deal_currency}`, sub: `${fmt(d.capital_local)} ${d.currency}`, tone: "" },
    { k: "drawn", label: L("Drawn", "المسحوب", "Retiré"),
      v: `${fmt(d.drawn_deal)} ${d.deal_currency}`, sub: `${fmt(d.drawn_local)} ${d.currency}`, tone: "text-ink-3" },
    { k: "share", label: L("Share of cycle", "نصيبه من الدورة", "Part du cycle"),
      v: d.share ? `${fmt(d.share.amount)} USD` : L("not set", "غير محدد", "non défini"),
      sub: "", tone: d.share && d.share.amount < 0 ? "text-sale" : "" },
  ];
});

async function load() {
  loading.value = true; err.value = "";
  try {
    const r = await api.call(`${A}.investor_list`, {}, { fresh: true });
    list.value = r?.investors || [];
    if (list.value.length) await open(list.value[0].account);
  } catch (e) { err.value = e?.message || String(e); }
  finally { loading.value = false; }
}

async function open(account) {
  try { st.value = await api.call(`${A}.investor_statement`, { account }, { fresh: true }); }
  catch (e) { err.value = e?.message || String(e); }
}

onMounted(load);
</script>
