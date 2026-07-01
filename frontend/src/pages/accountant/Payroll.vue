<template>
  <div class="space-y-3.5">
    <div class="flex items-center gap-2 flex-wrap">
      <div class="flex gap-1 bg-white border border-line rounded-chip p-1 w-fit shadow-card overflow-x-auto">
        <button v-for="v in VIEWS" :key="v.k" class="px-3 py-1.5 rounded-lg text-[12px] font-semibold whitespace-nowrap inline-flex items-center gap-1.5" :class="view === v.k ? 'bg-app-warm text-accent-dark shadow-card' : 'text-ink-3 hover:text-ink'" @click="view = v.k">
          <Icon :name="v.icon" :size="13" />{{ v.label() }}
        </button>
      </div>
      <DateFilterBar v-if="['cockpit','components','accounting'].includes(view)" :df="df" class="ms-auto" />
    </div>

    <!-- ── COCKPIT ── -->
    <template v-if="view==='cockpit'">
      <TableLoading v-if="cLoad" :rows="4" />
      <template v-else>
        <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <Kpi :label="L('Headcount','عدد الموظفين','Effectif')" :value="String(c.headcount||0)" icon="layers" color="#0f766e" :sub="L('active','نشط','actifs')" />
          <Kpi :label="L('Cost to company','تكلفة الشركة','Coût total')" :value="money(c.cost_to_company)" icon="wallet" color="#7c3aed" :sub="ccy + ' · +' + L('employer','صاحب العمل','employeur')" />
          <Kpi :label="L('Net paid','الصافي المدفوع','Net payé')" :value="money(c.net)" icon="check" color="#0369a1" :sub="(c.slips||0)+' '+L('slips','مسير','bulletins')" />
          <Kpi :label="L('Owed to staff','مستحق للموظفين','Dû au personnel')" :value="money(c.salary_payable)" icon="clock" :color="c.salary_payable ? '#b45309' : '#94a3b8'" :sub="L('salary payable','رواتب مستحقة','à payer')" />
        </div>

        <div v-if="c.missing_slips || c.no_structure" class="flex flex-wrap gap-2">
          <button v-if="c.missing_slips" class="inline-flex items-center gap-1.5 px-3 py-2 rounded-card border border-amber-200 bg-amber-50/70 text-[12px] font-semibold text-amber-800" @click="view='close'">
            <Icon name="alert" :size="14" color="#b45309" />{{ c.missing_slips }} {{ L('active staff with no','موظف نشط بلا مسير','sans bulletin') }} {{ c.last_month }} {{ L('slip','','') }}
          </button>
          <span v-if="c.no_structure" class="inline-flex items-center gap-1.5 px-3 py-2 rounded-card border border-line bg-white text-[12px] font-semibold text-ink-2">
            <Icon name="alert" :size="14" color="#9a8f86" />{{ c.no_structure }} {{ L('with no salary structure','بلا هيكل راتب','sans structure') }}
          </span>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-3">
          <div class="bg-white rounded-card border border-line shadow-card px-4 py-3">
            <div class="text-[12px] font-bold mb-3 flex items-center gap-2"><Icon name="chart" :size="14" color="#0b5c4f" />{{ L('Monthly payroll','الرواتب الشهرية','Paie mensuelle') }}</div>
            <div class="flex items-end gap-2 h-28">
              <div v-for="mo in c.monthly" :key="mo.m" class="flex-1 flex flex-col items-center gap-1 min-w-0" :title="mo.m+': '+money(mo.net)+' '+ccy">
                <div class="w-full flex-1 flex items-end"><div class="w-full rounded-t-sm bg-teal-600" :style="`height:${mBar(mo.net)}%;min-height:2px`"></div></div>
                <span class="text-[9px] text-ink-muted whitespace-nowrap">{{ mo.m.slice(5) }}</span>
              </div>
            </div>
          </div>
          <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
            <div class="px-4 py-2.5 border-b border-line-hair text-[12px] font-bold flex items-center gap-2"><Icon name="building" :size="14" color="#0b5c4f" />{{ L('By department','حسب القسم','Par service') }}<span class="text-[10px] text-ink-muted font-normal">{{ L('click to view staff','اضغط لعرض الموظفين','cliquer') }}</span></div>
            <table class="w-full text-[12px]"><tbody>
              <tr v-for="dep in c.by_department" :key="dep.dept" class="border-t border-line-hair first:border-t-0 hover:bg-app-warm/50 cursor-pointer group" @click="openDept(dep.dept)">
                <td class="px-4 py-2 truncate max-w-[180px] group-hover:text-accent-dark">{{ dep.dept }}</td>
                <td class="px-3 py-2 text-end tnum text-ink-muted whitespace-nowrap">{{ dep.heads }} <Icon name="users" :size="12" class="inline -mt-0.5" /></td>
                <td class="px-4 py-2 text-end tnum font-semibold">{{ money(dep.net) }}</td>
              </tr>
            </tbody></table>
          </div>
        </div>
      </template>
    </template>

    <!-- ── MONTH CLOSE ── -->
    <template v-else-if="view==='close'">
      <TableLoading v-if="clLoad" :rows="5" />
      <template v-else>
        <!-- header: month picker + lock state -->
        <div class="bg-white rounded-card border border-line shadow-card px-4 py-3.5 flex items-center gap-3 flex-wrap">
          <Icon name="lock" :size="18" :color="cl.closed ? '#047857' : '#b45309'" />
          <div>
            <div class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L('Payroll month','شهر الرواتب','Mois de paie') }}</div>
            <select v-model="clMonth" class="mt-0.5 text-[16px] font-extrabold bg-transparent focus:outline-none cursor-pointer -ms-0.5" @change="loadClose()">
              <option v-for="m in cl.months" :key="m" :value="m">{{ m }}</option>
            </select>
          </div>
          <span class="text-[11px] font-bold px-2.5 py-1 rounded-chip" :class="cl.closed ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'">
            {{ cl.closed ? L('Locked','مقفول','Verrouillé') : L('Open','مفتوح','Ouvert') }}
          </span>
          <div v-if="cl.closed" class="text-[11px] text-ink-muted">{{ L('closed','أُقفل','clôturé') }} {{ cl.closed_on }}<span v-if="cl.closed_by"> · {{ cl.closed_by }}</span></div>
          <div class="ms-auto flex items-center gap-2">
            <button v-if="!cl.closed && can('post_entries')" type="button" :disabled="clBusy"
                    class="inline-flex items-center gap-1.5 h-9 px-4 rounded-chip text-[12.5px] font-bold text-white disabled:opacity-50"
                    :class="cl.ready ? 'bg-emerald-600 hover:bg-emerald-700' : 'bg-amber-600 hover:bg-amber-700'"
                    @click="doClose">
              <Icon :name="clBusy ? 'clock' : 'lock'" :size="14" />{{ clBusy ? L('Closing…','جارٍ الإقفال…','…') : cl.ready ? L('Close month','إقفال الشهر','Clôturer') : L('Close anyway','إقفال رغم النقص','Clôturer quand même') }}
            </button>
            <button v-if="cl.closed && can('manage_users')" type="button" :disabled="clBusy"
                    class="inline-flex items-center gap-1.5 h-9 px-4 rounded-chip text-[12.5px] font-semibold text-ink-2 bg-white border border-line-2 hover:bg-app-warm disabled:opacity-50" @click="doReopen">
              <Icon :name="clBusy ? 'clock' : 'arrow'" :size="14" />{{ L('Reopen','إعادة فتح','Rouvrir') }}
            </button>
          </div>
        </div>

        <!-- KPIs -->
        <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <Kpi :label="L('Slips','المسيّرات','Bulletins')" :value="cl.emps_with_slip + ' / ' + cl.active" icon="list" :color="cl.missing_count ? '#b45309' : '#0f766e'" :sub="L('active staff covered','من الموظفين النشطين','couverts')" />
          <Kpi :label="L('Net paid','الصافي','Net payé')" :value="money(cl.net)" icon="check" color="#0369a1" :sub="ccy" />
          <Kpi :label="L('Employer cost','تكلفة صاحب العمل','Charges patronales')" :value="money(cl.employer_contrib)" icon="coins" color="#7c3aed" :sub="ccy" />
          <Kpi :label="L('Cost to company','تكلفة الشركة','Coût total')" :value="money(cl.cost_to_company)" icon="wallet" color="#0f766e" :sub="ccy" />
        </div>

        <!-- ── RUN PAYROLL: generate → submit → pay, all from here ── -->
        <div v-if="can('post_entries') && !cl.closed" class="bg-white rounded-card border border-line shadow-card overflow-hidden">
          <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><Icon name="coins" :size="14" color="#0b5c4f" /><span class="text-[12px] font-bold">{{ L('Run payroll','تشغيل الرواتب','Exécuter la paie') }}</span><span class="text-[10px] text-ink-muted">{{ L('generate → submit → pay','إنشاء ← اعتماد ← دفع','générer → soumettre → payer') }}</span></div>
          <div class="p-4 grid grid-cols-1 sm:grid-cols-3 gap-3">
            <!-- 1. Generate -->
            <div class="rounded-card border border-line-2 p-3 flex flex-col gap-2">
              <div class="flex items-center gap-2"><span class="w-5 h-5 rounded-full grid place-items-center text-[10px] font-bold text-white bg-ink">1</span><span class="text-[12px] font-bold">{{ L('Generate slips','إنشاء المسيّرات','Générer') }}</span></div>
              <div class="text-[11px] text-ink-muted flex-1">{{ pv.eligible_count || 0 }} {{ L('eligible staff with no slip yet','موظف مؤهّل بلا مسيّر','éligibles sans bulletin') }}</div>
              <button type="button" :disabled="runBusy || !(pv.eligible_count>0)" class="h-8 px-3 rounded-chip text-[12px] font-bold text-white bg-teal-700 hover:bg-teal-800 disabled:opacity-40" @click="doGenerate">
                <Icon :name="runBusy==='gen' ? 'clock' : 'plus'" :size="12" class="inline -mt-0.5 me-1" />{{ pv.eligible_count>0 ? L('Generate','إنشاء','Générer')+' '+pv.eligible_count : L('None eligible','لا مؤهّلين','Aucun') }}
              </button>
            </div>
            <!-- 2. Submit -->
            <div class="rounded-card border border-line-2 p-3 flex flex-col gap-2">
              <div class="flex items-center gap-2"><span class="w-5 h-5 rounded-full grid place-items-center text-[10px] font-bold text-white bg-ink">2</span><span class="text-[12px] font-bold">{{ L('Submit slips','اعتماد المسيّرات','Soumettre') }}</span></div>
              <div class="text-[11px] text-ink-muted flex-1">{{ pv.draft_count || 0 }} {{ L('draft slips → posts the accrual','مسودّة ← ترحيل الاستحقاق','brouillons → comptabilise') }}</div>
              <button type="button" :disabled="runBusy || !(pv.draft_count>0)" class="h-8 px-3 rounded-chip text-[12px] font-bold text-white bg-sky-700 hover:bg-sky-800 disabled:opacity-40" @click="doSubmitSlips">
                <Icon :name="runBusy==='sub' ? 'clock' : 'check'" :size="12" class="inline -mt-0.5 me-1" />{{ pv.draft_count>0 ? L('Submit','اعتماد','Soumettre')+' '+pv.draft_count : L('No drafts','لا مسودّات','Aucun') }}
              </button>
            </div>
            <!-- 3. Pay -->
            <div class="rounded-card border border-line-2 p-3 flex flex-col gap-2">
              <div class="flex items-center gap-2"><span class="w-5 h-5 rounded-full grid place-items-center text-[10px] font-bold text-white bg-ink">3</span><span class="text-[12px] font-bold">{{ L('Pay salaries','دفع الرواتب','Payer') }}</span></div>
              <div class="text-[11px] text-ink-muted flex-1">{{ money(pv.to_pay_net) }} {{ ccy }} · {{ pv.to_pay_count || 0 }} {{ L('unpaid','غير مدفوع','non payés') }}</div>
              <div class="flex gap-1.5">
                <select v-model="payBank" class="h-8 min-w-0 flex-1 bg-app-warm/40 border border-line-2 rounded-chip px-2 text-[11px] focus:outline-none">
                  <option value="">{{ L('bank…','البنك…','banque…') }}</option>
                  <option v-for="b in pv.banks || []" :key="b.name" :value="b.name">{{ b.nm }}</option>
                </select>
                <button type="button" :disabled="runBusy || !(pv.to_pay_count>0) || !payBank" class="h-8 px-3 rounded-chip text-[12px] font-bold text-white bg-emerald-600 hover:bg-emerald-700 disabled:opacity-40" @click="doPay">
                  <Icon :name="runBusy==='pay' ? 'clock' : 'wallet'" :size="12" class="inline -mt-0.5" />
                </button>
              </div>
            </div>
          </div>
          <div class="px-4 py-2 border-t border-line-hair text-[10.5px] text-ink-muted flex items-center gap-1.5">
            <Icon name="shield" :size="11" color="#9a8f86" />{{ L('Submit & Pay are gated for material amounts and fully reversible (Undo in Activity).','الاعتماد والدفع مبوّبان بالموافقة للمبالغ الكبيرة وقابلان للتراجع بالكامل.','Soumettre & Payer sont contrôlés et réversibles.') }}
          </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-3">
          <!-- checklist -->
          <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
            <div class="px-4 py-2.5 border-b border-line-hair text-[12px] font-bold flex items-center gap-2"><Icon name="check" :size="14" color="#0b5c4f" />{{ L('Close checklist','قائمة الإقفال','Contrôles') }}</div>
            <div class="divide-y divide-line-hair">
              <div v-for="s in cl.checklist" :key="s.key" class="px-4 py-3 flex items-center gap-3">
                <span class="w-6 h-6 rounded-full grid place-items-center shrink-0" :style="`background:${s.ok ? '#ecfdf5' : '#fff7ed'}`">
                  <Icon :name="s.ok ? 'check' : 'alert'" :size="14" :color="s.ok ? '#047857' : '#b45309'" />
                </span>
                <div class="text-[12.5px] font-semibold" :class="s.ok ? 'text-ink' : 'text-amber-800'">{{ checkLabel(s) }}</div>
                <span v-if="s.of !== undefined" class="ms-auto tnum text-[12px] font-bold" :class="s.ok ? 'text-success-dark' : 'text-amber-700'">{{ s.n }} / {{ s.of }}</span>
                <span v-else-if="s.n !== undefined && !s.ok" class="ms-auto tnum text-[12px] font-bold text-amber-700">{{ s.n }}</span>
                <Icon v-else-if="s.ok" name="check" :size="14" color="#047857" class="ms-auto" />
              </div>
            </div>
            <div class="px-4 py-2.5 border-t border-line-hair bg-app-warm/40 text-[11px]" :class="cl.ready ? 'text-success-dark' : 'text-amber-800'">
              <Icon :name="cl.ready ? 'check' : 'alert'" :size="12" class="inline -mt-0.5 me-1" />{{ cl.ready ? L('Ready to close.','جاهز للإقفال.','Prêt à clôturer.') : L('Some checks are incomplete — you can still close, but review first.','بعض الفحوصات غير مكتملة — يمكنك الإقفال لكن راجع أولًا.','Contrôles incomplets — vérifiez.') }}
            </div>
          </div>

          <!-- missing roster / runs -->
          <div class="space-y-3">
            <div v-if="cl.missing_count" class="bg-white rounded-card border border-line shadow-card overflow-hidden">
              <div class="px-4 py-2.5 border-b border-line-hair text-[12px] font-bold flex items-center gap-2"><Icon name="alert" :size="14" color="#b45309" />{{ cl.missing_count }} {{ L('active staff without a slip','موظف نشط بلا مسيّر','sans bulletin') }}</div>
              <div class="max-h-52 overflow-y-auto">
                <table class="w-full text-[12px]"><tbody>
                  <tr v-for="m in cl.missing" :key="m.name" class="border-t border-line-hair first:border-t-0 hover:bg-app-warm/50 cursor-pointer group" @click="openEmp(m.name)">
                    <td class="px-4 py-2 font-semibold group-hover:text-accent-dark">{{ m.nm }}</td>
                    <td class="px-4 py-2 text-end text-ink-muted truncate max-w-[140px]">{{ m.dept }}</td>
                  </tr>
                </tbody></table>
              </div>
              <div class="px-4 py-2 border-t border-line-hair text-[10.5px] text-ink-muted">{{ L('Slips are created in ERPNext HR; the portal verifies & locks the month.','المسيّرات تُنشأ في ERPNext HR؛ البوابة تتحقق وتقفل الشهر.','Bulletins créés dans ERPNext HR.') }}</div>
            </div>
            <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
              <div class="px-4 py-2.5 border-b border-line-hair text-[12px] font-bold flex items-center gap-2"><Icon name="list" :size="14" color="#0b5c4f" />{{ L('Payroll runs this month','تشغيلات الشهر','Exécutions du mois') }}</div>
              <table class="w-full text-[12px]"><tbody>
                <tr v-for="r in cl.runs" :key="r.name" class="border-t border-line-hair first:border-t-0 hover:bg-app-warm/50 cursor-pointer group" @click="openRun(r.name)">
                  <td class="px-4 py-2 font-mono text-[11px]">{{ r.name }}</td>
                  <td class="px-3 py-2 text-end tnum text-ink-muted">{{ r.slips }} {{ L('slips','مسير','bull.') }}</td>
                  <td class="px-4 py-2 text-end"><span class="text-[10px] font-semibold px-1.5 py-0.5 rounded" :class="r.status==='Posted' ? 'bg-emerald-50 text-emerald-700' : r.status==='Cancelled' ? 'bg-rose-50 text-rose-600' : 'bg-amber-50 text-amber-700'">{{ r.status }}</span></td>
                </tr>
                <tr v-if="!cl.runs.length"><td colspan="3" class="px-4 py-6 text-center text-ink-muted">{{ L('No payroll run for this month.','لا تشغيل رواتب لهذا الشهر.','Aucune exécution.') }}</td></tr>
              </tbody></table>
            </div>
          </div>
        </div>
      </template>
    </template>

    <!-- ── ADJUSTMENTS (bonuses & deductions, reviewed before the slip) ── -->
    <PayAdjustments v-else-if="view==='adjustments'" />

    <!-- ── EMPLOYEES ── -->
    <div v-else-if="view==='employees'" class="bg-white rounded-card border border-line shadow-card overflow-hidden">
      <div class="px-4 py-3 border-b border-line-hair flex items-center gap-2.5 flex-wrap">
        <Icon name="layers" :size="14" color="#0b5c4f" /><span class="text-[12px] font-bold">{{ L('Employees','الموظفون','Employés') }}</span>
        <button v-if="can('post_entries')" type="button" class="inline-flex items-center gap-1.5 h-9 px-3 rounded-chip text-[12px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand" @click="newEmp = true">
          <Icon name="plus" :size="13" />{{ L('New employee','موظف جديد','Nouvel employé') }}
        </button>
        <div class="ms-auto flex items-center gap-2 flex-wrap">
          <select v-model="empDept" class="h-9 bg-app-warm/40 border border-line-2 rounded-[10px] px-2.5 text-[12px] focus:outline-none focus:border-accent/40" @change="loadEmps">
            <option value="all">{{ L('All departments','كل الأقسام','Tous services') }}</option>
            <option v-for="d in empMeta.departments" :key="d" :value="d">{{ d }}</option>
          </select>
          <select v-model="empStatus" class="h-9 bg-app-warm/40 border border-line-2 rounded-[10px] px-2.5 text-[12px] focus:outline-none focus:border-accent/40" @change="loadEmps">
            <option value="all">{{ L('All statuses','كل الحالات','Tous statuts') }}</option>
            <option v-for="s in empMeta.statuses" :key="s" :value="s">{{ s }}</option>
          </select>
          <div class="relative">
            <span class="absolute top-1/2 -translate-y-1/2 start-3 text-ink-muted pointer-events-none flex"><Icon name="search" :size="15" /></span>
            <input v-model.trim="empSearch" :placeholder="L('Search…','بحث…','Rechercher…')" class="w-40 sm:w-52 h-9 bg-app-warm/40 border border-line-2 rounded-[10px] ps-9 pe-3 text-[12.5px] focus:outline-none focus:border-accent/40 focus:bg-white" />
          </div>
        </div>
      </div>
      <TableLoading v-if="eLoad" :rows="8" />
      <div v-else class="overflow-x-auto">
        <table class="w-full text-[12px]">
          <thead><tr style="background:#fafaf9" class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">
            <th class="px-4 py-2 text-start">{{ L('Employee','الموظف','Employé') }}</th>
            <th class="px-3 py-2 text-start hidden sm:table-cell">{{ L('Department','القسم','Service') }}</th>
            <th class="px-3 py-2 text-start">{{ L('Status','الحالة','Statut') }}</th>
            <th class="px-3 py-2 text-start">{{ L('Structure','الهيكل','Structure') }}</th>
            <th class="px-3 py-2 text-end">{{ L('Base','الأساسي','Base') }}</th>
            <th class="px-3 py-2 text-start hidden md:table-cell">{{ L('Last slip','آخر مسير','Dernier') }}</th>
            <th class="px-4 py-2 text-end">{{ L('YTD net','صافي السنة','Net cumul') }}</th>
          </tr></thead>
          <tbody>
            <tr v-for="r in emps" :key="r.name" class="border-t border-line-hair hover:bg-app-warm/50 cursor-pointer group" @click="openEmp(r.name)">
              <td class="px-4 py-2.5"><div class="font-semibold group-hover:text-accent-dark">{{ r.nm }}</div><div class="text-[10px] text-ink-muted">{{ r.desig || r.name }}</div></td>
              <td class="px-3 py-2.5 text-ink-2 hidden sm:table-cell truncate max-w-[160px]">{{ r.dept || "—" }}</td>
              <td class="px-3 py-2.5"><span class="text-[10px] font-bold px-1.5 py-0.5 rounded-chip" :class="r.status==='Active' ? 'bg-emerald-50 text-emerald-700' : 'bg-app-warm text-ink-muted'">{{ r.status || "—" }}</span></td>
              <td class="px-3 py-2.5" @click.stop>
                <span v-if="r.has_structure" class="text-[11px] text-ink-2 truncate max-w-[150px] inline-block align-middle">{{ r.structure }}</span>
                <button v-else-if="r.status==='Active' && can('post_entries')" type="button" class="inline-flex items-center gap-1 h-6 px-2 rounded-chip text-[10.5px] font-bold text-white bg-teal-700 hover:bg-teal-800" @click="assignFor(r)">
                  <Icon name="plus" :size="11" />{{ L('Assign','تعيين','Affecter') }}
                </button>
                <span v-else class="text-[11px] text-ink-muted">—</span>
              </td>
              <td class="px-3 py-2.5 text-end tnum">{{ money(r.base) }}</td>
              <td class="px-3 py-2.5 text-ink-3 hidden md:table-cell whitespace-nowrap" :class="isStale(r.last_slip) ? 'text-amber-700 font-semibold' : ''">{{ r.last_slip || "—" }}</td>
              <td class="px-4 py-2.5 text-end tnum font-semibold">{{ money(r.ytd_net) }}</td>
            </tr>
            <tr v-if="!emps.length"><td colspan="7" class="px-4 py-8 text-center text-ink-muted">{{ L('No employees match.','لا موظفين مطابقين.','Aucun.') }}</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ── RUNS ── -->
    <div v-else-if="view==='runs'" class="bg-white rounded-card border border-line shadow-card overflow-hidden">
      <div class="px-4 py-2.5 border-b border-line-hair text-[12px] font-bold flex items-center gap-2"><Icon name="list" :size="14" color="#0b5c4f" />{{ L('Payroll runs','تشغيلات الرواتب','Exécutions') }}</div>
      <TableLoading v-if="rLoad" :rows="8" />
      <table v-else class="w-full text-[12px]">
        <thead><tr style="background:#fafaf9" class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">
          <th class="px-4 py-2 text-start">{{ L('Run','التشغيل','Exéc.') }}</th>
          <th class="px-3 py-2 text-start">{{ L('Period','الفترة','Période') }}</th>
          <th class="px-3 py-2 text-end">{{ L('Slips','مسيّرات','Bulletins') }}</th>
          <th class="px-3 py-2 text-start">{{ L('Status','الحالة','Statut') }}</th>
          <th class="px-4 py-2 text-end">{{ L('Net','الصافي','Net') }}</th>
        </tr></thead>
        <tbody>
          <tr v-for="r in runs" :key="r.name" class="border-t border-line-hair hover:bg-app-warm/50 cursor-pointer group" @click="openRun(r.name)">
            <td class="px-4 py-2.5 font-mono text-[11px]">{{ r.name }}</td>
            <td class="px-3 py-2.5 text-ink-2">{{ r.month }}</td>
            <td class="px-3 py-2.5 text-end tnum">{{ r.slips }}</td>
            <td class="px-3 py-2.5"><span class="text-[10px] font-semibold px-1.5 py-0.5 rounded" :class="r.status==='Posted' ? 'bg-emerald-50 text-emerald-700' : r.status==='Cancelled' ? 'bg-rose-50 text-rose-600' : 'bg-amber-50 text-amber-700'">{{ r.status }}</span></td>
            <td class="px-4 py-2.5 text-end tnum font-semibold">{{ money(r.net) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- ── ACCOUNTING (GL reconciliation) ── -->
    <template v-else-if="view==='accounting'">
      <TableLoading v-if="gLoad" :rows="6" />
      <template v-else>
        <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <Kpi :label="L('Expected (slips)','المتوقّع (المسيّرات)','Attendu')" :value="money(gl.total_expected)" icon="scale" color="#0369a1" :sub="ccy" />
          <Kpi :label="L('Actual (GL)','الفعلي (الأستاذ)','Réel')" :value="money(gl.total_actual)" icon="check" color="#0f766e" :sub="ccy" />
          <Kpi :label="L('Variance','الفرق','Écart')" :value="money(gl.total_variance)" icon="alert" :color="Math.abs(gl.total_variance||0)>0.01 ? '#e11d48' : '#047857'" :sub="L('GL − slips','الأستاذ − المسيّرات','GL − paie')" />
          <Kpi :label="L('Mismatched','غير مطابقة','Non concordés')" :value="String(gl.mismatched || 0)" icon="alert" :color="gl.mismatched ? '#b45309' : '#94a3b8'" :sub="L('accounts','حساب','comptes')" />
        </div>
        <div class="bg-white rounded-card border border-line shadow-card overflow-hidden">
          <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><Icon name="scale" :size="14" color="#0b5c4f" /><span class="text-[12px] font-bold">{{ L('Payroll → GL reconciliation','مطابقة الرواتب بالأستاذ','Rapprochement paie → GL') }}</span><span class="text-[10px] text-ink-muted">{{ L('slip totals vs the account they post to','إجمالي المسيّرات مقابل حسابها','par compte') }}</span></div>
          <div class="overflow-x-auto">
            <table class="w-full text-[12px]">
              <thead><tr style="background:#fafaf9" class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">
                <th class="px-4 py-2 text-start">{{ L('Account','الحساب','Compte') }}</th>
                <th class="px-3 py-2 text-end">{{ L('Expected','المتوقّع','Attendu') }}</th>
                <th class="px-3 py-2 text-end">{{ L('Actual','الفعلي','Réel') }}</th>
                <th class="px-4 py-2 text-end">{{ L('Variance','الفرق','Écart') }}</th>
              </tr></thead>
              <tbody>
                <tr v-for="r in gl.rows" :key="r.account" class="border-t border-line-hair" :class="r.tied ? '' : 'bg-rose-50/40'">
                  <td class="px-4 py-2.5"><span class="font-mono text-[10px] text-ink-muted">{{ r.num }}</span> {{ r.name }}</td>
                  <td class="px-3 py-2.5 text-end tnum text-ink-3">{{ money(r.expected) }}</td>
                  <td class="px-3 py-2.5 text-end tnum">{{ money(r.actual) }}</td>
                  <td class="px-4 py-2.5 text-end tnum font-bold" :class="r.tied ? 'text-success-dark' : 'text-rose-600'">{{ r.tied ? '✓' : money(r.variance) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </template>
    </template>

    <!-- ── COMPONENTS ── -->
    <template v-else-if="view==='components'">
      <TableLoading v-if="kLoad" :rows="8" />
      <div v-else class="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <div v-for="grp in [{k:'earnings',t:L('Earnings','الاستحقاقات','Gains'),c:'#0f766e'},{k:'deductions',t:L('Deductions','الخصومات','Retenues'),c:'#be123c'}]" :key="grp.k" class="bg-white rounded-card border border-line shadow-card overflow-hidden">
          <div class="px-4 py-2.5 border-b border-line-hair flex items-center gap-2"><span class="w-2.5 h-2.5 rounded-sm" :style="`background:${grp.c}`"></span><span class="text-[12px] font-bold">{{ grp.t }}</span><span class="ms-auto tnum font-bold text-[12px]">{{ money(grp.k==='earnings' ? k.earning_total : k.deduction_total) }}</span></div>
          <table class="w-full text-[12px]"><tbody>
            <tr v-for="(cmp,i) in (k[grp.k]||[])" :key="i" class="border-t border-line-hair first:border-t-0">
              <td class="px-4 py-2"><div class="truncate max-w-[220px]">{{ cmp.component }}</div><div class="text-[10px] text-ink-muted font-mono">{{ cmp.account_short || "—" }}</div></td>
              <td class="px-4 py-2 text-end tnum font-semibold">{{ money(cmp.total) }}</td>
            </tr>
          </tbody></table>
        </div>
      </div>
    </template>
    <AssignStructureModal v-if="assignEmp" :employee="assignEmp.name" :employee-name="assignEmp.nm" @close="assignEmp = null" @done="onAssigned" />
    <EmployeeEditModal v-if="newEmp" @close="newEmp = false" @done="loadEmps" />
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useI18n } from "vue-i18n";
import { h } from "vue";
import Icon from "@/components/Icon.vue";
import TableLoading from "@/components/TableLoading.vue";
import AssignStructureModal from "@/components/AssignStructureModal.vue";
import EmployeeEditModal from "@/components/EmployeeEditModal.vue";
import PayAdjustments from "@/pages/accountant/PayAdjustments.vue";
import DateFilterBar from "@/components/DateFilterBar.vue";
import api from "@/services/api";
import { currentCompany } from "@/composables/useLive";
import { useUi } from "@/composables/useUi";
import { useAuth } from "@/composables/useAuth";
import { useToast } from "@/composables/useToast";
import { useDateFilter } from "@/composables/useDateFilter";
import { fmtMoney } from "@/utils/helpers";

const { locale } = useI18n();
const { entityId } = useUi();
const { can } = useAuth();
const toast = useToast();
const router = useRouter();
const route = useRoute();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
// Accounting precision: exact, grouped, 2 decimals — never abbreviated to K/M.
const money = (n) => fmtMoney(n);

const Kpi = (p) => h("div", { class: "bg-white rounded-card border border-line shadow-card px-4 py-3" }, [
  h("div", { class: "text-[10px] font-bold uppercase tracking-wider text-ink-muted flex items-center gap-1.5" }, [h(Icon, { name: p.icon, size: 13, color: p.color }), p.label]),
  h("div", { class: "text-[19px] font-extrabold mt-1 tnum whitespace-nowrap", style: `color:${p.color}` }, p.value),
  h("div", { class: "text-[10.5px] text-ink-muted mt-0.5" }, p.sub)]);
Kpi.props = ["label", "value", "sub", "icon", "color"];

// The active tab lives in the URL (?t=…) so browser Back / reload return you to
// the same tab instead of resetting to the cockpit or bouncing you out.
const TABS = ["cockpit", "close", "adjustments", "employees", "runs", "components", "accounting"];
const view = ref(TABS.includes(route.query.t) ? route.query.t : "cockpit");
watch(view, (v) => { if (route.query.t !== v) router.replace({ query: { ...route.query, t: v } }); });
const VIEWS = [
  { k: "cockpit", icon: "chart", label: () => L("Cockpit", "اللوحة", "Cockpit") },
  { k: "close", icon: "lock", label: () => L("Month close", "إقفال الشهر", "Clôture") },
  { k: "adjustments", icon: "coins", label: () => L("Adjustments", "الحوافز والخصومات", "Ajustements") },
  { k: "employees", icon: "layers", label: () => L("Employees", "الموظفون", "Employés") },
  { k: "runs", icon: "list", label: () => L("Runs", "التشغيلات", "Exécutions") },
  { k: "components", icon: "scale", label: () => L("Components", "المكوّنات", "Composants") },
  { k: "accounting", icon: "check", label: () => L("Accounting", "المحاسبة", "Compta") },
];

const c = ref({}), cLoad = ref(true);
const emps = ref([]), eLoad = ref(true), empSearch = ref(""), empDept = ref("all"), empStatus = ref("Active");
const empMeta = ref({ departments: [], statuses: ["Active", "Inactive", "Left", "Suspended"] });
const runs = ref([]), rLoad = ref(true);
const k = ref({}), kLoad = ref(true);
const gl = ref({}), gLoad = ref(true);
const cl = ref({ months: [], missing: [], runs: [], checklist: [] }), clLoad = ref(true), clMonth = ref(""), clBusy = ref(false);
const pv = ref({}), payBank = ref(""), runBusy = ref("");
const ccy = computed(() => c.value.currency || cl.value.currency || "MAD");
const df = useDateFilter("payroll", () => { loadCockpit(); loadComponents(); if (view.value === "accounting") loadGL(); }, "year");

async function loadCockpit() { cLoad.value = true; try { c.value = await api.call("accounting_portal.api.payroll.payroll_cockpit", { company: currentCompany(), ...df.filterValue() }) || {}; } catch { c.value = {}; } finally { cLoad.value = false; } }
async function loadEmps() { eLoad.value = true; try { const r = await api.call("accounting_portal.api.payroll.payroll_employees", { company: currentCompany(), search: empSearch.value, department: empDept.value, status: empStatus.value }); emps.value = r?.rows || []; if (r?.departments) empMeta.value = { departments: r.departments, statuses: r.statuses || empMeta.value.statuses }; } catch { emps.value = []; } finally { eLoad.value = false; } }
async function loadRuns() { rLoad.value = true; try { const r = await api.call("accounting_portal.api.payroll.payroll_runs", { company: currentCompany() }); runs.value = r?.runs || []; } catch { runs.value = []; } finally { rLoad.value = false; } }
async function loadComponents() { kLoad.value = true; try { k.value = await api.call("accounting_portal.api.payroll.payroll_components", { company: currentCompany(), ...df.filterValue() }) || {}; } catch { k.value = {}; } finally { kLoad.value = false; } }
async function loadGL() { gLoad.value = true; try { gl.value = await api.call("accounting_portal.api.payroll.payroll_gl_recon", { company: currentCompany(), ...df.filterValue() }) || {}; } catch { gl.value = {}; } finally { gLoad.value = false; } }
async function loadClose() {
  clLoad.value = true;
  try {
    cl.value = await api.call("accounting_portal.api.payroll.payroll_close_status", { company: currentCompany(), month: clMonth.value || undefined }) || { months: [], missing: [], runs: [], checklist: [] };
    clMonth.value = cl.value.month || clMonth.value;
  } catch { cl.value = { months: [], missing: [], runs: [], checklist: [] }; }
  finally { clLoad.value = false; }
  loadPreview();
}
async function loadPreview() {
  if (!clMonth.value) { pv.value = {}; return; }
  try { pv.value = await api.call("accounting_portal.api.payroll.payroll_run_preview", { company: currentCompany(), month: clMonth.value }, { fresh: true }) || {}; }
  catch { pv.value = {}; }
}
async function runStep(kind, method, extra) {
  if (runBusy.value) return;
  runBusy.value = kind;
  try {
    const res = await api.call(method, { company: currentCompany(), month: clMonth.value, ...(extra || {}) });
    if (res && res.status === "Proposed") toast.success(L("Sent for approval", "أُرسل للموافقة", "Envoyé pour approbation"));
    else toast.success(L("Done", "تم", "Terminé"));
    await loadClose();
  } catch (e) { toast.error(L("Failed", "فشل", "Échec") + ": " + String(e?.message || e).slice(0, 160)); }
  finally { runBusy.value = ""; }
}
function doGenerate() {
  if (!window.confirm(L(`Generate salary slips for ${pv.value.eligible_count} employee(s) for ${clMonth.value}? (drafts — no ledger impact yet)`, `إنشاء مسيّرات لـ ${pv.value.eligible_count} موظف لشهر ${clMonth.value}؟ (مسودّات بدون أثر على الأستاذ)`, `Générer les bulletins ?`))) return;
  runStep("gen", "accounting_portal.api.payroll.payroll_generate");
}
function doSubmitSlips() {
  if (!window.confirm(L(`Submit ${pv.value.draft_count} draft slip(s) for ${clMonth.value}? This posts the salary accrual to the ledger.`, `اعتماد ${pv.value.draft_count} مسيّر مسودّة لشهر ${clMonth.value}؟ ده بيرحّل استحقاق الرواتب للأستاذ.`, `Soumettre les bulletins ?`))) return;
  runStep("sub", "accounting_portal.api.payroll.payroll_submit_slips");
}
function doPay() {
  if (!payBank.value) return;
  if (!window.confirm(L(`Pay ${money(pv.value.to_pay_net)} ${ccy.value} in salaries for ${clMonth.value} from the selected bank? Posts a bank entry clearing salary payable.`, `دفع ${money(pv.value.to_pay_net)} ${ccy.value} رواتب لشهر ${clMonth.value} من البنك المختار؟ بيرحّل قيد بنكي يقفل الرواتب المستحقة.`, `Payer les salaires ?`))) return;
  runStep("pay", "accounting_portal.api.payroll.payroll_pay", { bank_account: payBank.value });
}

loadCockpit();
watch(view, (v) => {
  if (v === "employees" && !emps.value.length) loadEmps();
  if (v === "runs" && !runs.value.length) loadRuns();
  if (v === "components" && !k.value.earnings) loadComponents();
  if (v === "accounting" && !gl.value.rows) loadGL();
  if (v === "close" && !cl.value.month) loadClose();
});
let t; watch(empSearch, () => { clearTimeout(t); t = setTimeout(loadEmps, 300); });
watch(entityId, () => {
  c.value = {}; emps.value = []; runs.value = []; k.value = {}; gl.value = {};
  cl.value = { months: [], missing: [], runs: [], checklist: [] }; clMonth.value = "";
  loadCockpit();
  if (view.value === "employees") loadEmps();
  if (view.value === "runs") loadRuns();
  if (view.value === "components") loadComponents();
  if (view.value === "accounting") loadGL();
  if (view.value === "close") loadClose();
});

const maxNet = computed(() => Math.max(1, ...(c.value.monthly || []).map((m) => m.net)));
const mBar = (v) => Math.round((Number(v) || 0) / maxNet.value * 100);
const isStale = (d) => { if (!d) return true; const m = new Date(); m.setMonth(m.getMonth() - 2); return new Date(d) < m; };
function openEmp(name) { router.push({ path: "/accounting/payroll", query: { employee: name } }); }
function openRun(name) { router.push({ path: "/accounting/payroll", query: { run: name } }); }
const assignEmp = ref(null);
const newEmp = ref(false);
function assignFor(r) { assignEmp.value = r; }
function onAssigned() { loadEmps(); if (view.value === "close") loadClose(); }
function openDept(dept) { empDept.value = dept; empStatus.value = "all"; empSearch.value = ""; view.value = "employees"; loadEmps(); }

function checkLabel(s) {
  if (s.key === "slips") return L("Every active employee has a slip", "كل موظف نشط له مسيّر", "Chaque employé actif a un bulletin");
  if (s.key === "drafts") return L("No draft slips pending", "لا مسيّرات مسودّة معلّقة", "Aucun brouillon en attente");
  if (s.key === "posted") return L("Posted to the ledger", "مُرحّل إلى الأستاذ", "Comptabilisé au grand livre");
  return s.key;
}

async function doClose() {
  if (clBusy.value) return;
  clBusy.value = true;
  try {
    await api.call("accounting_portal.api.payroll.payroll_close_month", { company: currentCompany(), month: clMonth.value });
    toast.success(L("Month locked", "تم إقفال الشهر", "Mois verrouillé"));
    await loadClose();
  } catch (e) { toast.error(L("Failed", "فشل", "Échec") + ": " + String(e?.message || e).slice(0, 140)); }
  finally { clBusy.value = false; }
}
async function doReopen() {
  if (clBusy.value) return;
  clBusy.value = true;
  try {
    await api.call("accounting_portal.api.payroll.payroll_close_month", { company: currentCompany(), month: clMonth.value, reopen: 1 });
    toast.success(L("Month reopened", "تم إعادة فتح الشهر", "Mois rouvert"));
    await loadClose();
  } catch (e) { toast.error(L("Failed", "فشل", "Échec") + ": " + String(e?.message || e).slice(0, 140)); }
  finally { clBusy.value = false; }
}
</script>
