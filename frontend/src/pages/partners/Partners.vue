<template>
  <div class="jp" :dir="dir" :lang="lang" :class="{ phone: isPhone }">
    <!-- ── app bar ── -->
    <header class="jp-bar">
      <div class="jp-brand">
        <img :src="LOGO" alt="Justyol" class="jp-logo" />
        <span class="jp-brand-sep" aria-hidden="true"></span>
        <div class="jp-brand-txt">
          <div class="jp-title">{{ isPhone ? TAB_TITLE[tab]() : L("لوحة الشركاء", "Partners dashboard") }}</div>
          <div class="jp-sub">
            <span class="jp-dot" :class="{ off: !online }" aria-hidden="true"></span>
            <span v-if="!online">{{ L("من غير نت — آخر أرقام محفوظة", "Offline — last saved numbers") }}</span>
            <span v-else-if="loading && !data">{{ L("جارٍ التحميل…", "Loading…") }}</span>
            <span v-else>{{ L("محدّث", "Updated") }} <span dir="ltr">{{ updatedLabel }}</span></span>
          </div>
        </div>
      </div>
      <div class="jp-actions">
        <button type="button" class="jp-icon-btn" :aria-label="L('تحديث', 'Refresh')" :class="{ spin: loading }" @click="load(true)">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12a9 9 0 1 1-2.6-6.3M21 4v5h-5" /></svg>
        </button>
        <button type="button" class="jp-pill-btn" @click="toggleLang">{{ lang === "ar" ? "EN" : "عربي" }}</button>
        <div class="jp-menu-wrap">
          <button type="button" class="jp-icon-btn" :aria-label="L('القائمة', 'Menu')" :aria-expanded="menuOpen" @click="menuOpen = !menuOpen">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 6h.01M12 12h.01M12 18h.01" /></svg>
          </button>
          <div v-if="menuOpen" class="jp-menu" role="menu">
            <div class="jp-menu-head">{{ fullName || user }}</div>
            <button v-if="pushSupported" type="button" role="menuitem" @click="menuOpen = false; togglePush()">
              {{ pushOn ? L("إيقاف إشعار الصبح", "Turn off morning summary") : L("تفعيل إشعار الصبح", "Turn on morning summary") }}
            </button>
            <button v-if="pushOn" type="button" role="menuitem" @click="menuOpen = false; testPush()">{{ L("جرّب الإشعار دلوقتي", "Send a test notification") }}</button>
            <button v-if="canInstall" type="button" role="menuitem" @click="menuOpen = false; install()">{{ L("تثبيت على الموبايل", "Install the app") }}</button>
            <a v-if="!partnerOnly" href="/accounting/dashboard" role="menuitem">{{ L("رجوع للبورتال", "Back to the portal") }}</a>
            <button type="button" role="menuitem" class="danger" @click="signOut">{{ L("تسجيل الخروج", "Sign out") }}</button>
          </div>
        </div>
      </div>
    </header>

    <main ref="scroller" class="jp-main" @touchstart.passive="pullStart" @touchmove.passive="pullMove" @touchend="pullEnd">
      <div v-if="isPhone" class="jp-pull" :style="{ height: pull + 'px', opacity: pull ? 1 : 0 }">
        <svg viewBox="0 0 24 24" :style="{ transform: `rotate(${pull * 3}deg)` }" aria-hidden="true"><path d="M21 12a9 9 0 1 1-2.6-6.3M21 4v5h-5" /></svg>
        {{ pull > 60 ? L("سيب للتحديث", "Release to refresh") : L("اسحب للتحديث", "Pull to refresh") }}
      </div>

      <!-- install / notifications banner -->
      <div v-if="banner" class="jp-banner jp-rise">
        <img :src="ICON" alt="" class="jp-banner-ico" />
        <div class="jp-banner-txt">
          <b>{{ banner.title }}</b>
          <span>{{ banner.sub }}</span>
        </div>
        <button v-if="banner.action" type="button" class="jp-red-btn" @click="banner.action()">{{ banner.cta }}</button>
        <button type="button" class="jp-x" :aria-label="L('إغلاق', 'Close')" @click="dismissBanner(banner.key)">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 6L6 18M6 6l12 12" /></svg>
        </button>
      </div>

      <div v-if="err && !data" class="jp-error">
        <b>{{ L("الأرقام ما اتحملتش", "The numbers did not load") }}</b>
        <span>{{ err }}</span>
        <button type="button" class="jp-red-btn" @click="load(true)">{{ L("حاول تاني", "Try again") }}</button>
      </div>
      <div v-if="toastMsg" class="jp-toast" role="status">{{ toastMsg }}</div>

      <template v-if="data">
        <!-- ══ TODAY ══ -->
        <section v-if="show('today')" class="jp-sec">
          <div v-if="!isPhone" class="jp-sec-head">
            <h2>{{ L("النهارده", "Today") }} <small>{{ dayLabel(T.date) }}</small></h2>
            <span class="jp-note">{{ L("الطلبات لحد دلوقتي، مقارنة بنفس الساعة إمبارح والأسبوع اللي فات", "Orders so far, against the same hour yesterday and last week") }}</span>
          </div>
          <div class="jp-today">
            <div class="jp-hero jp-rise" style="--d: .05s">
              <div class="jp-hero-glow" aria-hidden="true"></div>
              <div class="jp-hero-top">
                <span>{{ L("طلبات النهارده لحد دلوقتي", "Orders today so far") }}</span>
                <span class="jp-live"><span class="jp-dot" aria-hidden="true"></span>{{ L("مباشر", "Live") }}</span>
              </div>
              <div class="jp-hero-num" dir="ltr">{{ n(T.orders) }}</div>
              <div class="jp-hero-chips">
                <span class="jp-chip" :class="tone(T.vs_yesterday_pct)"><b dir="ltr">{{ arrow(T.vs_yesterday_pct) }}</b> {{ L("عن نفس الساعة إمبارح", "vs same hour yesterday") }}</span>
                <span class="jp-chip" :class="tone(T.vs_last_week_pct)"><b dir="ltr">{{ arrow(T.vs_last_week_pct) }}</b> {{ L("عن الأسبوع اللي فات", "vs last week") }}</span>
              </div>
              <div class="jp-hero-meta">
                <span>{{ L("قيمتها", "Worth") }} <b dir="ltr">{{ n(T.orders_value) }}</b> {{ MAD }}</span>
                <span>{{ L("اتأكد منها", "Confirmed") }} <b dir="ltr">{{ n(T.confirmed) }}</b></span>
              </div>
              <div class="jp-hours-wrap">
                <div class="jp-hours-label">{{ L("الطلبات بالساعة (توقيت المغرب)", "Orders by hour (Morocco time)") }}</div>
                <div class="jp-hours" dir="ltr">
                  <div v-for="(h, i) in hours" :key="i" class="jp-hcol">
                    <div class="jp-hbar jp-grow" :class="{ now: i === T.hour_now, future: i > T.hour_now }" :style="{ height: h.h, '--d': (0.1 + i * 0.025) + 's' }" :title="h.label + ':00 · ' + h.v"></div>
                  </div>
                </div>
                <div class="jp-hours-axis" dir="ltr"><span v-for="a in hourAxis" :key="a">{{ a }}</span></div>
              </div>
            </div>

            <div class="jp-cards-head" v-if="!isPhone">{{ L("آخر 7 أيام كاملة", "The last 7 full days") }} · <span dir="ltr">{{ weekLabel }}</span></div>
            <div class="jp-cards">
              <div v-if="isPhone" class="jp-cards-head phone">{{ L("آخر 7 أيام كاملة", "The last 7 full days") }} · <span dir="ltr">{{ weekLabel }}</span></div>
              <article v-for="(c, i) in dayCards" :key="c.key" class="jp-card jp-rise" :style="{ '--d': (0.1 + i * 0.05) + 's' }">
                <div class="jp-card-top">
                  <span>{{ c.label }}</span>
                  <span class="jp-ico" :style="{ background: c.tint, color: c.ink }"><svg viewBox="0 0 24 24" aria-hidden="true"><path :d="c.icon" /></svg></span>
                </div>
                <div class="jp-card-num" dir="ltr">{{ c.value }} <small>{{ c.unit }}</small></div>
                <div class="jp-card-foot">
                  <span class="jp-delta" :class="c.good === null ? '' : (c.good ? 'up' : 'down')" dir="ltr">{{ c.delta }}</span>
                  <svg class="jp-spark" viewBox="0 0 96 28" aria-hidden="true"><path class="jp-draw" :d="c.spark" :stroke="c.ink" /></svg>
                </div>
                <div class="jp-card-note">{{ c.note }}</div>
              </article>
            </div>
          </div>

          <!-- funnel -->
          <div class="jp-panel jp-rise" style="--d: .25s">
            <div class="jp-sec-head in">
              <h3>{{ L("طلبات آخر 30 يوم: وصلت لحد فين", "The last 30 days of orders: how far they got") }}</h3>
              <span class="jp-note">{{ L("كل طلب محسوب في آخر محطة وصلها", "Each order counted at the furthest station it reached") }}</span>
            </div>
            <div class="jp-funnel">
              <div v-for="(f, i) in funnel" :key="f.key" class="jp-frow">
                <span class="jp-flabel">{{ f.label }}</span>
                <div class="jp-ftrack">
                  <div class="jp-fbar jp-growx" :style="{ width: f.w, background: f.color, '--d': (0.3 + i * 0.1) + 's' }"><span dir="ltr">{{ n(f.v) }}</span></div>
                </div>
                <span class="jp-fpct" :class="{ warn: f.warn }" dir="ltr">{{ f.pct }}</span>
              </div>
            </div>
          </div>
        </section>

        <!-- ══ MONTH ══ -->
        <section v-if="show('month')" class="jp-sec">
          <div class="jp-sec-head">
            <h2 v-if="!isPhone">{{ L("الشهر لحد النهارده", "Month to date") }} <small dir="ltr">{{ rangeLabel(M.from, M.to) }}</small></h2>
            <span class="jp-note">{{ L("مقارنة بنفس الأيام من الشهر اللي فات", "Against the same days last month") }} · <span dir="ltr">{{ rangeLabel(M.prev_from, M.prev_to) }}</span></span>
          </div>
          <div class="jp-grid">
            <article class="jp-card ring jp-rise" style="--d: .05s">
              <svg viewBox="0 0 124 124" class="jp-ring" role="img" :aria-label="L('نسبة التسليم', 'Delivery rate')">
                <circle cx="62" cy="62" r="52" class="bg" />
                <circle cx="62" cy="62" r="52" class="fg" :stroke-dasharray="ringDash" transform="rotate(-90 62 62)" />
                <text x="62" y="62" text-anchor="middle" class="big">{{ M.delivery_rate == null ? "—" : n(M.delivery_rate, 1) + "%" }}</text>
                <text x="62" y="82" text-anchor="middle" direction="ltr" class="small" :class="(M.delivery_rate_delta_pt || 0) >= 0 ? 'up' : 'down'">{{ ptLabel(M.delivery_rate_delta_pt) }}</text>
              </svg>
              <div class="jp-ring-txt">
                <b>{{ L("نسبة التسليم", "Delivery rate") }} · {{ M.delivery_rate_month ? monthName(M.delivery_rate_month) : "—" }}</b>
                <span>{{ L("من الطرود اللي اتشحنت في الشهر: اتسلّمت قصاد رجعت (آخر شهر طروده خلصت)", "Of the parcels shipped that month: delivered vs returned (latest month whose parcels have ended)") }}</span>
                <span class="jp-mini">{{ L("الشهر ده لحد دلوقتي:", "This month so far:") }} <span dir="ltr">{{ n(M.delivered_parcels) }}</span> {{ L("اتسلّم", "delivered") }} · <span dir="ltr">{{ n(M.returned_parcels) }}</span> {{ L("رجع", "returned") }} · <span dir="ltr">{{ n(M.open_parcels) }}</span> {{ L("لسه في الطريق", "still moving") }}</span>
              </div>
            </article>
            <article v-for="(c, i) in monthCards" :key="c.key" class="jp-card jp-rise" :style="{ '--d': (0.1 + i * 0.05) + 's' }">
              <div class="jp-card-top">
                <span>{{ c.label }}</span>
                <span v-if="c.badge" class="jp-badge" :title="c.badgeWhy">{{ c.badge }}</span>
                <span v-else class="jp-delta" :class="c.good === null ? '' : (c.good ? 'up' : 'down')" dir="ltr">{{ c.delta }}</span>
              </div>
              <div class="jp-card-num" dir="ltr">{{ c.value }} <small>{{ c.unit }}</small></div>
              <div class="jp-meter"><div class="jp-growx" :style="{ width: c.fill, background: c.ink, '--d': (0.15 + i * 0.05) + 's' }"></div></div>
              <div class="jp-card-note">{{ c.note }}</div>
            </article>
          </div>
        </section>

        <!-- ══ CASH & STOCK ══ -->
        <section v-if="show('cash')" class="jp-sec jp-two">
          <div class="jp-panel jp-rise" style="--d: .05s">
            <div class="jp-sec-head in"><h3>{{ L("الفلوس والمخزون", "Cash and stock") }}</h3><span class="jp-note">{{ L("من الدفاتر النهارده", "From the books today") }}</span></div>
            <div class="jp-cash">
              <button type="button" class="jp-cashbox dark" :aria-expanded="banksOpen" @click="banksOpen = !banksOpen">
                <span>{{ L("الكاش في البنوك والخزنة", "Cash in banks and petty cash") }}</span>
                <b dir="ltr">{{ n(C.banks) }} <small>{{ MAD }}</small></b>
                <em>{{ L(C.accounts.length + " حساب · دوس للتفاصيل", C.accounts.length + " accounts · tap for detail") }}</em>
              </button>
              <div class="jp-cashbox blue">
                <span>{{ L("عند Cathedis في الطريق", "COD held by Cathedis") }}</span>
                <b dir="ltr">{{ n(C.cod_at_carrier) }} <small>{{ MAD }}</small></b>
                <em>{{ L(n(C.cod_parcels) + " طرد اتسلّم ولسه ما اتحولش", n(C.cod_parcels) + " parcels delivered, not yet paid out") }}</em>
              </div>
              <div class="jp-cashbox green">
                <span>{{ L("قيمة المخزون في المغرب", "Stock value in Morocco") }}</span>
                <b dir="ltr">{{ n(C.stock_value) }} <small>{{ MAD }}</small></b>
                <em>{{ L(n(C.stock_units) + " قطعة · بالتكلفة المسجلة", n(C.stock_units) + " units · at booked cost") }}</em>
              </div>
              <div class="jp-cashbox red">
                <span>{{ L("رصيد الموردين في الدفاتر", "Suppliers' balance in the books") }}</span>
                <b dir="ltr">{{ n(C.suppliers_balance) }} <small>{{ MAD }}</small></b>
                <em>{{ L("مستحق علينا قبل التسويات", "Owed, before reconciliations") }}</em>
              </div>
            </div>
            <div v-if="banksOpen" class="jp-accounts">
              <div v-for="a in C.accounts" :key="a.account" class="jp-acc"><span dir="auto">{{ a.account }}</span><b dir="ltr">{{ n(a.balance) }}</b></div>
            </div>
          </div>

          <div class="jp-panel dark jp-rise" style="--d: .1s">
            <div class="jp-sec-head in"><h3>{{ L("كونتينرات في البحر", "Containers at sea") }}</h3><span class="jp-note">{{ L("من الـ packing list: اللي خرج فعلاً", "From the packing list: what actually left") }}</span></div>
            <div v-if="!data.containers.length" class="jp-empty">{{ L("مفيش كونتينرات في الطريق دلوقتي.", "No container at sea right now.") }}</div>
            <div v-for="s in data.containers" :key="s.no" class="jp-ship">
              <div class="jp-ship-top">
                <b>{{ L("كونتينر", "Container") }} {{ s.no }} <code dir="ltr">{{ s.container_id }}</code></b>
                <span class="jp-ship-days">{{ s.days_at_sea == null ? "—" : L("في البحر من " + s.days_at_sea + " يوم", s.days_at_sea + " days at sea") }}</span>
              </div>
              <div class="jp-route" dir="ltr">
                <span class="dot from"></span><span class="line"></span><span class="done" :style="{ width: voyage(s) }"></span><span class="dot to"></span>
                <svg class="boat" :style="{ left: `calc(${voyage(s)} - 6px)` }" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 15h18l-2.5 4.5h-13zM6 15V9h12v6M9 9V6h6v3" /></svg>
              </div>
              <div class="jp-route-lbl" dir="ltr"><span>Istanbul · {{ s.shipped_on || "" }}</span><span>Casablanca</span></div>
              <div class="jp-ship-stats">
                <span><b dir="ltr">{{ n(s.units) }}</b> {{ L("قطعة", "units") }}</span>
                <span><b dir="ltr">{{ n(s.skus) }}</b> {{ L("صنف", "SKUs") }}</span>
                <span v-if="s.kg"><b dir="ltr">{{ n(s.kg) }}</b> kg</span>
              </div>
            </div>
          </div>
        </section>

        <!-- ══ TREND ══ -->
        <section v-if="show('trend')" class="jp-sec">
          <div class="jp-panel jp-rise" style="--d: .05s">
            <div class="jp-sec-head in">
              <h3 v-if="!isPhone">{{ L("آخر 12 شهر", "The last 12 months") }}</h3>
              <div class="jp-seg" role="group" :aria-label="L('المؤشر', 'Metric')">
                <button v-for="m in METRICS" :key="m.k" type="button" :class="{ on: metric === m.k }" @click="pickMetric(m.k)">{{ m.label() }}</button>
              </div>
            </div>
            <div class="jp-chart-wrap">
              <div class="jp-chart" dir="ltr">
                <div v-for="(m, i) in trend" :key="m.month" class="jp-col">
                  <span class="jp-col-val" :class="{ open: !m.complete }">{{ m.label }}</span>
                  <div class="jp-col-bar jp-grow" :class="{ open: !m.complete, last: i === trend.length - 2 }" :style="{ height: m.h, '--d': (0.05 + i * 0.04) + 's' }"></div>
                  <span class="jp-col-m">{{ monthName(m.month, true) }}</span>
                </div>
              </div>
            </div>
            <div class="jp-legend">
              <span><i class="sq solid"></i>{{ L("شهر مكتمل", "Complete month") }}</span>
              <span><i class="sq dashed"></i>{{ L("الشهر الجاري — لسه بيتحسب", "Current month — still running") }}</span>
            </div>
            <div v-if="isPhone" class="jp-mlist">
              <div v-for="m in trendDesc" :key="m.month" class="jp-mrow">
                <span>{{ monthName(m.month) }}</span>
                <span><b dir="ltr" :class="{ open: !m.complete }">{{ m.label }}</b><em :class="m.complete ? 'ok' : 'run'">{{ m.complete ? L("مكتمل", "Complete") : L("جاري", "Running") }}</em></span>
              </div>
            </div>
          </div>
        </section>

        <footer v-if="!isPhone || tab === 'trend'" class="jp-foot">
          <span>{{ L("المصادر: الطلبات · Cathedis · البنوك · الدفاتر", "Sources: orders · Cathedis · banks · the books") }}</span>
          <span>{{ L("المبالغ بالدرهم شاملة الضريبة · من غير الطلبات الملغية والوهمية", "MAD, VAT included · cancelled and test orders left out") }}</span>
        </footer>
      </template>

      <div v-if="!data && loading" class="jp-skel">
        <div class="sk hero"></div><div class="sk"></div><div class="sk"></div><div class="sk"></div>
      </div>
    </main>

    <!-- ── phone tab bar ── -->
    <nav v-if="isPhone" class="jp-tabs" :aria-label="L('الأقسام', 'Sections')">
      <button v-for="t in TABS" :key="t.k" type="button" :class="{ on: tab === t.k }" :aria-current="tab === t.k ? 'page' : null" @click="go(t.k)">
        <i aria-hidden="true"></i>
        <svg viewBox="0 0 24 24" aria-hidden="true"><path :d="t.icon" /></svg>
        {{ t.label() }}
      </button>
    </nav>
  </div>
</template>

<script setup>
// Partners — the numbers the partners follow, daily and monthly (api/partners.py).
// One component for both the desktop page and the phone app: under 760px it
// becomes an app (top bar, four tabs, pull to refresh) and it is installable
// (manifest + service worker at /partners-sw.js, scope /accounting/partners).
// Bilingual on its own (Arabic RTL by default, English), independent of the
// portal's i18n, because partners never see the rest of the portal.
import { ref, computed, onMounted, onBeforeUnmount, watch } from "vue";
import api from "@/services/api";
import { useAuth } from "@/composables/useAuth";
import { LOGO_URL, asset } from "@/utils/constants";

const M_ = "accounting_portal.api.partners.";
const LOGO = LOGO_URL;
const ICON = asset("/partners/icon-192.png");
const { user, fullName, role, logout } = useAuth();
const partnerOnly = computed(() => role.value === "Partner");

function stored(k, d) { try { return localStorage.getItem(k) || d; } catch { return d; } }
function store(k, v) { try { localStorage.setItem(k, v); } catch { /* private mode */ } }

const lang = ref(stored("jp_lang", "ar"));
const dir = computed(() => (lang.value === "ar" ? "rtl" : "ltr"));
const L = (ar, en) => (lang.value === "ar" ? ar : en);
const MAD = computed(() => L("د.م", "MAD"));
function toggleLang() { lang.value = lang.value === "ar" ? "en" : "ar"; store("jp_lang", lang.value); }

// ── layout ──
const isPhone = ref(false);
let mq = null;
function setPhone() { isPhone.value = !!(mq && mq.matches); }
const tab = ref(stored("jp_tab", "today"));
const TABS = [
  { k: "today", label: () => L("النهارده", "Today"), icon: "M12 4V2M12 22v-2M4 12H2M22 12h-2M5.6 5.6L4.2 4.2M19.8 19.8l-1.4-1.4M5.6 18.4l-1.4 1.4M19.8 4.2l-1.4 1.4M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z" },
  { k: "month", label: () => L("الشهر", "Month"), icon: "M4 6h16v14H4zM4 10h16M9 3v4M15 3v4" },
  { k: "cash", label: () => L("الفلوس", "Cash"), icon: "M3 7h15a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H4a1 1 0 0 1-1-1V6a2 2 0 0 1 2-2h11M17 13h.01" },
  { k: "trend", label: () => L("الاتجاه", "Trend"), icon: "M3 17l5-5 4 3 6-8M21 7h-4M21 7v4" },
];
const TAB_TITLE = { today: () => L("النهارده", "Today"), month: () => L("الشهر لحد النهارده", "Month to date"), cash: () => L("الفلوس والمخزون", "Cash and stock"), trend: () => L("آخر 12 شهر", "Last 12 months") };
const show = (k) => !isPhone.value || tab.value === k;
const scroller = ref(null);
function go(k) { tab.value = k; store("jp_tab", k); play(); if (scroller.value) scroller.value.scrollTop = 0; }

// ── data ──
const data = ref(null), loading = ref(false), err = ref(""), online = ref(true);
const T = computed(() => (data.value && data.value.today) || {});
const M = computed(() => (data.value && data.value.mtd) || {});
const C = computed(() => (data.value && data.value.cash) || { accounts: [] });
async function load(fresh = false) {
  if (loading.value) return;
  loading.value = true; err.value = "";
  try {
    const res = await api.call(M_ + "get_summary", fresh ? { fresh: 1 } : {}, { fresh: true });
    if (res) { data.value = res; play(); }
  } catch (e) {
    err.value = String((e && e.message) || e).slice(0, 180);
  } finally { loading.value = false; }
}
const updatedLabel = computed(() => {
  const g = data.value && data.value.generated_at;
  if (!g) return "—";
  // generated_at is on the server clock (Istanbul); partners read Morocco time,
  // two hours behind (tz_shift) — shifted by hand, browsers disagree on Morocco's zone
  const h = Number(g.slice(11, 13)), m = g.slice(14, 16);
  if (isNaN(h)) return g.slice(11, 16);
  return String((h + ((T.value && T.value.tz_shift) || -2) + 24) % 24).padStart(2, "0") + ":" + m;
});

// ── count-up ──
const p = ref(1);
let raf = 0;
const reduce = typeof window !== "undefined" && window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
function play() {
  if (reduce) { p.value = 1; return; }
  cancelAnimationFrame(raf);
  let start = null;
  const dur = 1100;
  const step = (ts) => {
    if (start === null) start = ts;
    const x = Math.min(1, (ts - start) / dur);
    p.value = 1 - Math.pow(1 - x, 4);
    if (x < 1) raf = requestAnimationFrame(step);
  };
  p.value = 0;
  raf = requestAnimationFrame(step);
  // a hidden tab pauses animation frames: never leave the numbers at zero
  clearTimeout(settle);
  settle = setTimeout(() => { if (p.value < 1) { cancelAnimationFrame(raf); p.value = 1; } }, dur + 400);
}
let settle = 0;
function n(v, d = 0) {
  if (v === null || v === undefined || v === "") return "—";
  return (Number(v) * p.value).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
}
function compact(v) {
  if (v === null || v === undefined) return "—";
  const x = Number(v) * p.value, a = Math.abs(x);
  if (a >= 1e6) return (x / 1e6).toFixed(2) + "M";
  if (a >= 1e4) return (x / 1e3).toFixed(0) + "k";
  return Math.round(x).toLocaleString("en-US");
}
const pct = (v) => (v === null || v === undefined ? "—" : (v > 0 ? "▲ " : v < 0 ? "▼ " : "") + Math.abs(v).toFixed(1) + "%");
const arrow = (v) => pct(v);
const tone = (v) => (v === null || v === undefined ? "flat" : v >= 0 ? "good" : "bad");
const ptLabel = (v) => (v === null || v === undefined ? "" : (v >= 0 ? "▲ " : "▼ ") + Math.abs(v).toFixed(1) + " pt");
function spark(pts) {
  const xs = (pts || []).map(Number);
  if (!xs.length) return "";
  const max = Math.max(...xs), min = Math.min(...xs), span = max - min || 1;
  return xs.map((v, i) => (i ? "L" : "M") + (i * 96 / Math.max(1, xs.length - 1)).toFixed(1) + " " + (25 - ((v - min) / span) * 22).toFixed(1)).join(" ");
}
const MONTHS_AR = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"];
const MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
function monthName(ym, short = false) {
  const i = Number(ym.slice(5, 7)) - 1;
  if (short) return lang.value === "ar" ? MONTHS_AR[i].slice(0, 3) : MONTHS_EN[i];
  return (lang.value === "ar" ? MONTHS_AR[i] : MONTHS_EN[i]) + " " + ym.slice(0, 4);
}
function dayLabel(d) {
  if (!d) return "";
  const x = new Date(d + "T12:00:00");
  return x.toLocaleDateString(lang.value === "ar" ? "ar-MA" : "en-GB", { weekday: "long", day: "numeric", month: "long", numberingSystem: "latn" });
}
function rangeLabel(a, b) { return a && b ? `${a.slice(8)}/${a.slice(5, 7)} – ${b.slice(8)}/${b.slice(5, 7)}` : ""; }
const weekLabel = computed(() => { const d = T.value.days || []; return d.length > 8 ? rangeLabel(d[d.length - 8], d[d.length - 2]) : ""; });

// ── today ──
// The books' day runs on the server clock (Istanbul); each hour is labelled in
// Morocco time, so the bars read 22:00 (the evening before) → 21:00.
const mhour = (i) => String((i + (T.value.tz_shift || 0) + 24) % 24).padStart(2, "0");
const hours = computed(() => {
  const hs = T.value.hours || [];
  const max = Math.max(1, ...hs);
  return hs.map((v, i) => ({ v, label: mhour(i), h: Math.max(4, (v / max) * 100) + "%" }));
});
const hourAxis = computed(() => [0, 6, 12, 18, 23].map(mhour));
const ICONS = {
  truck: "M3 6h11v9H3zM14 9h4l3 3v3h-7zM7 18a1.6 1.6 0 1 0 0-3.2 1.6 1.6 0 0 0 0 3.2zM18 18a1.6 1.6 0 1 0 0-3.2 1.6 1.6 0 0 0 0 3.2z",
  check: "M20 6L9 17l-5-5", back: "M9 14L4 9l5-5M4 9h11a5 5 0 0 1 0 10h-3", cash: "M2 7h20v10H2zM12 12h.01M6 12h.01M18 12h.01",
  bag: "M6 7h12l1 13H5zM9 7a3 3 0 0 1 6 0", box: "M21 8l-9-5-9 5 9 5 9-5zM3 8v8l9 5 9-5V8M12 13v8",
};
// Week cards: the last 7 full days against the 7 before them. Cathedis neither
// delivers nor pays on Sundays, so a single day (a Monday looking at Sunday)
// would read as a collapse; a week never does. The line is the 7 days, day by day.
const wsum = (s, a, b) => s.slice(a, b).reduce((x, y) => x + Number(y || 0), 0);
function dcard(key, s, label, unit, ink, tint, icon, opts = {}) {
  s = s || [];
  const y = opts.value != null ? opts.value : wsum(s, -8, -1);
  const b = opts.prev != null ? opts.prev : wsum(s, -15, -8);
  const d = b ? ((y - b) / b) * 100 : null;
  const upIsGood = opts.upIsGood !== false;
  return {
    key, label, unit, ink, tint, icon: ICONS[icon],
    value: opts.compact ? compact(y) : n(y, opts.dec || 0),
    delta: d === null ? "—" : (d >= 0 ? "▲ " : "▼ ") + Math.abs(d).toFixed(1) + "%",
    good: d === null || Math.abs(d) < 0.05 ? null : (d >= 0) === upIsGood,
    spark: spark(s.slice(-8, -1)),
    note: opts.note || L("عن الـ 7 أيام اللي قبلها · الخط: يوم بيوم", "vs the 7 days before · line: day by day"),
  };
}
const dayCards = computed(() => {
  const t = (T.value && T.value.series) || null;
  if (!t) return [];
  return [
    dcard("ship", t.shipped, L("اتشحنت لـ Cathedis", "Shipped to Cathedis"), L("طرد", "parcels"), "#1d349a", "#e7f2ff", "truck"),
    dcard("del", t.delivered, L("اتسلّمت للزبون", "Delivered"), L("طرد", "parcels"), "#0d8756", "#e7f5ee", "check", { note: L("حسب Cathedis · بيتحدّث كل ليلة", "Per Cathedis · updated nightly") }),
    dcard("ret", t.returned, L("رجعت المخزن", "Returned to stock"), L("طرد", "parcels"), "#a3271a", "#fcefec", "back", { upIsGood: false }),
    dcard("bank", t.banked, L("دخل البنك من التحصيل", "COD cash banked"), MAD.value, "#15110d", "#f4f1ea", "cash", { compact: isPhone.value }),
    dcard("dval", t.delivered_value, L("قيمة اللي اتسلّم", "Delivered value"), MAD.value, "#b5811f", "#fff7e3", "bag", { compact: isPhone.value }),
    dcard("aov", t.avg_order, L("متوسط الطلب", "Average order"), MAD.value, "#46413a", "#f4f1ea", "box", {
      dec: 0, note: L("قيمة الطلبات ÷ عددها · عن الأسبوع اللي قبله", "Orders value ÷ count · vs the week before"),
      value: wsum(t.orders_value || [], -8, -1) / Math.max(1, wsum(t.orders || [], -8, -1)),
      prev: wsum(t.orders_value || [], -15, -8) / Math.max(1, wsum(t.orders || [], -15, -8)) }),
  ];
});
const funnel = computed(() => {
  const f = (data.value && data.value.funnel) || {};
  const base = f.received || 1;
  const steps = [
    ["rec", L("جات", "Received"), f.received, "#15110d", null],
    ["conf", L("اتأكدت", "Confirmed"), f.confirmed, "#46413a", f.received],
    ["ship", L("اتشحنت", "Shipped"), f.shipped, "#1d349a", f.confirmed],
    ["del", L("اتسلّمت", "Delivered"), f.delivered, "#0d8756", f.shipped],
    ["col", L("الفلوس دخلت", "Paid out by Cathedis"), f.collected, "#b5811f", f.delivered],
  ];
  return steps.map(([key, label, v, color, of]) => {
    const r = of ? (v || 0) / of : 1;
    return { key, label, v: v || 0, color, w: Math.max(2, ((v || 0) / base) * 100) + "%", pct: of ? Math.round(r * 100) + "%" : "100%", warn: of && r < 0.75 };
  });
});

// ── month ──
const C_RING = 2 * Math.PI * 52;
const ringDash = computed(() => ((C_RING * (M.value.delivery_rate || 0)) / 100 * p.value).toFixed(1) + " " + C_RING.toFixed(1));
const monthCards = computed(() => {
  const m = M.value;
  if (!m.from) return [];
  const mg = m.margin || {};
  const d = (a, b) => (b ? ((a - b) / b) * 100 : null);
  const cards = [
    { key: "ov", label: L("قيمة الطلبات (شاملة الضريبة)", "Orders value (VAT incl.)"), value: n(m.orders_value), unit: MAD.value, ink: "#15110d",
      dpct: m.orders_value_delta_pct, note: L("الشهر اللي فات لنفس اليوم: ", "Last month to the same day: ") + n(m.orders_value_prev) },
    { key: "dv", label: L("قيمة اللي اتسلّم", "Delivered value"), value: n(m.delivered_value), unit: MAD.value, ink: "#0d8756",
      dpct: m.delivered_value_delta_pct, note: L("الشهر اللي فات لنفس اليوم: ", "Last month to the same day: ") + n(m.delivered_value_prev) },
    { key: "aov", label: L("متوسط الطلب", "Average order"), value: n(m.avg_order), unit: MAD.value, ink: "#b5811f",
      dpct: d(m.avg_order, m.avg_order_prev), note: L("الشهر اللي فات: ", "Last month: ") + n(m.avg_order_prev) },
    { key: "cr", label: L("الشحن للطرد", "Courier per parcel"), value: m.courier_per_parcel == null ? "—" : n(m.courier_per_parcel, 1), unit: MAD.value, ink: "#1d349a",
      dpct: d(m.courier_per_parcel, m.courier_per_parcel_prev), upBad: true,
      note: L("شهر ", "Month of ") + monthName(m.courier_month) + L(" — فواتير الشحن بتيجي آخر الشهر", " — courier bills arrive at month end") },
    { key: "gm", label: L("هامش الربح الإجمالي", "Gross margin"), value: mg.pct == null ? "—" : n(mg.pct, 1), unit: "%", ink: "#c4301c",
      badge: L("تقديري", "Estimated"), badgeWhy: L("يتثبت لما تكلفة الكونتينرات تتقفل", "Final once container costing is locked"),
      note: mg.month ? monthName(mg.month) + " · " + L("تكلفة محسوبة لـ ", "cost modelled for ") + (mg.coverage || 0) + L("% من القطع", "% of units") : L("مش متاح", "Not available"), fillPct: mg.pct },
  ];
  return cards.map((c) => {
    const dv = c.dpct;
    return Object.assign(c, {
      delta: dv === null || dv === undefined ? "—" : (dv >= 0 ? "▲ " : "▼ ") + Math.abs(dv).toFixed(1) + "%",
      good: dv === null || dv === undefined ? null : (dv >= 0) !== !!c.upBad,
      fill: Math.max(3, Math.min(100, c.fillPct != null ? c.fillPct : 30 + Math.max(-30, Math.min(60, dv || 0)))) + "%",
    });
  });
});

// ── cash ──
const banksOpen = ref(false);
function voyage(s) { const d = s.days_at_sea || 0; return Math.min(92, Math.max(6, (d / 25) * 100)) * p.value + "%"; }

// ── trend ──
const METRICS = [
  { k: "orders_value", label: () => L("قيمة الطلبات", "Orders value") },
  { k: "orders", label: () => L("الطلبات", "Orders") },
  { k: "delivered_value", label: () => L("اللي اتسلّم", "Delivered") },
  { k: "delivery_rate", label: () => L("التسليم %", "Delivery %") },
];
const metric = ref(stored("jp_metric", "orders_value"));
function pickMetric(k) { metric.value = k; store("jp_metric", k); play(); }
const trend = computed(() => {
  const ms = (data.value && data.value.months) || [];
  const k = metric.value;
  const vals = ms.map((m) => Number(m[k] || 0));
  const isRate = k === "delivery_rate";
  const nonzero = vals.filter((v) => v > 0);
  const floor = isRate && nonzero.length ? Math.max(0, Math.min(...nonzero) - 5) : 0;
  const top = Math.max(1, ...vals);
  return ms.map((m, i) => {
    const v = vals[i];
    const label = isRate ? (m[k] == null ? "—" : (v * p.value).toFixed(1) + "%") : (v ? compact(v) : "—");
    const room = isPhone.value ? 150 : 180;
    return { month: m.month, complete: m.complete, label, h: (v > 0 ? ((v - floor) / (top - floor || 1)) * room + 6 : 4) + "px" };
  });
});
const trendDesc = computed(() => trend.value.slice().reverse());

// ── pull to refresh (phone) ──
const pull = ref(0);
let y0 = null;
function pullStart(e) { if (!isPhone.value || !scroller.value || scroller.value.scrollTop > 0) { y0 = null; return; } y0 = e.touches[0].clientY; }
function pullMove(e) { if (y0 === null) return; const dy = e.touches[0].clientY - y0; pull.value = dy > 0 ? Math.min(90, dy * 0.5) : 0; }
function pullEnd() { if (pull.value > 60) load(true); pull.value = 0; y0 = null; }

// ── install + notifications ──
const toastMsg = ref("");
let toastT = 0;
function toast(m) { toastMsg.value = m; clearTimeout(toastT); toastT = setTimeout(() => (toastMsg.value = ""), 3500); }
const deferredPrompt = ref(null);
const standalone = ref(false);
const isIOS = typeof navigator !== "undefined" && /iphone|ipad|ipod/i.test(navigator.userAgent);
const canInstall = computed(() => !!deferredPrompt.value && !standalone.value);
async function install() {
  if (!deferredPrompt.value) return;
  deferredPrompt.value.prompt();
  try { await deferredPrompt.value.userChoice; } catch { /* dismissed */ }
  deferredPrompt.value = null;
}
const pushSupported = typeof window !== "undefined" && "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
const pushOn = ref(false);
let reg = null;
function b64ToBytes(s) {
  const pad = "=".repeat((4 - (s.length % 4)) % 4);
  const raw = atob((s + pad).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}
async function registerSW() {
  if (!("serviceWorker" in navigator)) return null;
  try {
    reg = await navigator.serviceWorker.register("/partners-sw.js", { scope: "/accounting/partners" });
    const sub = reg.pushManager ? await reg.pushManager.getSubscription() : null;
    pushOn.value = !!sub && Notification.permission === "granted";
    return reg;
  } catch { return null; }
}
async function togglePush() {
  if (!pushSupported) return;
  if (isIOS && !standalone.value) { toast(L("على الآيفون: ثبّت التطبيق الأول (مشاركة ← إضافة للشاشة الرئيسية)، وبعدين فعّل الإشعار من جوه.", "On iPhone: add the app to your home screen first, then turn notifications on from inside it.")); return; }
  try {
    reg = reg || (await registerSW());
    if (!reg) throw new Error("no service worker");
    if (pushOn.value) {
      const sub = await reg.pushManager.getSubscription();
      if (sub) { await api.call(M_ + "push_unsubscribe", { endpoint: sub.endpoint }); await sub.unsubscribe(); }
      pushOn.value = false;
      toast(L("الإشعار اتقفل", "Notifications turned off"));
      return;
    }
    const perm = await Notification.requestPermission();
    if (perm !== "granted") { toast(L("الإذن اترفض — فعّله من إعدادات المتصفح", "Permission denied — allow it in the browser settings")); return; }
    const { public_key } = await api.call(M_ + "push_key", {}, { fresh: true });
    const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64ToBytes(public_key) });
    await api.call(M_ + "push_subscribe", { subscription: JSON.stringify(sub.toJSON ? sub.toJSON() : sub), user_agent: navigator.userAgent.slice(0, 140) });
    pushOn.value = true;
    dismissBanner("push");
    toast(L("تمام — هيوصلك ملخص إمبارح كل يوم الساعة 9 الصبح", "Done — yesterday's summary will arrive every day at 9:00"));
  } catch (e) {
    toast(L("ما قدرناش نفعّل الإشعار: ", "Could not turn notifications on: ") + String((e && e.message) || e).slice(0, 80));
  }
}
async function testPush() {
  try {
    const r = await api.call(M_ + "push_test", {});
    toast(r && r.sent ? L("اتبعت — بص على الإشعارات", "Sent — check your notifications") : L("ما اتبعتش لأي جهاز", "Nothing was sent"));
  } catch (e) { toast(String((e && e.message) || e).slice(0, 100)); }
}
const dismissed = ref(stored("jp_dismissed", ""));
function dismissBanner(k) { dismissed.value = (dismissed.value + "," + k); store("jp_dismissed", dismissed.value); }
const banner = computed(() => {
  const off = (k) => dismissed.value.split(",").includes(k);
  if (canInstall.value && !off("install")) {
    return { key: "install", title: L("نزّل لوحة الشركاء على موبايلك", "Add Partners to your home screen"), sub: L("تفتح زي التطبيق، حتى من غير نت", "Opens like an app, even offline"), cta: L("تثبيت", "Install"), action: install };
  }
  if (isIOS && !standalone.value && !off("ios")) {
    return { key: "ios", title: L("ثبّتها على الآيفون", "Install on iPhone"), sub: L("اضغط زرار المشاركة ⎋ وبعدين «إضافة للشاشة الرئيسية»", "Tap Share ⎋, then “Add to Home Screen”"), cta: "", action: null };
  }
  if (pushSupported && !pushOn.value && !off("push") && (!isIOS || standalone.value)) {
    return { key: "push", title: L("ملخص كل يوم الصبح", "A summary every morning"), sub: L("إشعار الساعة 9 بأرقام إمبارح", "A 9:00 notification with yesterday's numbers"), cta: L("فعّل", "Turn on"), action: togglePush };
  }
  return null;
});

const menuOpen = ref(false);
async function signOut() {
  menuOpen.value = false;
  try { await logout(); } catch { /* ignore */ }
  window.location.assign("/accounting/login?redirect=/accounting/partners");
}

// ── lifecycle ──
let timer = 0;
function onVisible() { if (document.visibilityState === "visible") load(); }
function onBip(e) { e.preventDefault(); deferredPrompt.value = e; }
function onNet() { online.value = navigator.onLine; if (online.value) load(); }
function addFonts() {
  if (document.getElementById("jp-fonts")) return;
  const l = document.createElement("link");
  l.id = "jp-fonts"; l.rel = "stylesheet";
  l.href = "https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap";
  document.head.appendChild(l);
}
onMounted(() => {
  addFonts();
  mq = window.matchMedia("(max-width: 760px)");
  setPhone();
  mq.addEventListener ? mq.addEventListener("change", setPhone) : mq.addListener(setPhone);
  standalone.value = window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;
  online.value = navigator.onLine;
  window.addEventListener("beforeinstallprompt", onBip);
  window.addEventListener("online", onNet);
  window.addEventListener("offline", onNet);
  document.addEventListener("visibilitychange", onVisible);
  document.title = "Justyol Partners";
  registerSW();
  load();
  timer = setInterval(() => { if (document.visibilityState === "visible") load(); }, 5 * 60 * 1000);
});
onBeforeUnmount(() => {
  clearInterval(timer); cancelAnimationFrame(raf);
  window.removeEventListener("beforeinstallprompt", onBip);
  window.removeEventListener("online", onNet);
  window.removeEventListener("offline", onNet);
  document.removeEventListener("visibilitychange", onVisible);
  if (mq) mq.removeEventListener ? mq.removeEventListener("change", setPhone) : mq.removeListener(setPhone);
});
watch(lang, () => { document.documentElement.setAttribute("lang", lang.value); });
</script>

<style scoped>
.jp {
  --ink: #16130f; --ink2: #46413a; --mut: #6f695f; --line: #ece8e1; --bg: #faf8f4; --bg3: #f4f1ea;
  --red: #c4301c; --red7: #a3271a; --red0: #fcefec; --blk: #15110d; --grn: #0d8756; --grn7: #0b6b45; --grn0: #e7f5ee;
  --gold: #b5811f; --gold0: #fff7e3; --blue: #1d349a; --blue0: #e7f2ff;
  --ease: cubic-bezier(.3, 1, .3, 1);
  min-height: 100vh; background: var(--bg); color: var(--ink);
  font-family: "Plus Jakarta Sans", system-ui, sans-serif;
  display: flex; flex-direction: column;
}
.jp[dir="rtl"] { font-family: "IBM Plex Sans Arabic", "Plus Jakarta Sans", system-ui, sans-serif; }
.jp *, .jp *::before, .jp *::after { box-sizing: border-box; }
svg { fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
button { font: inherit; color: inherit; cursor: pointer; }
button:focus-visible, a:focus-visible { outline: 2px solid var(--red); outline-offset: 2px; }
[dir="ltr"] { unicode-bidi: isolate; }

/* app bar */
.jp-bar { position: sticky; top: 0; z-index: 20; display: flex; align-items: center; justify-content: space-between; gap: 12px;
  padding: calc(env(safe-area-inset-top, 0px) + 14px) max(16px, env(safe-area-inset-right, 0px)) 12px max(16px, env(safe-area-inset-left, 0px));
  background: rgba(250, 248, 244, .92); backdrop-filter: saturate(1.4) blur(10px); -webkit-backdrop-filter: saturate(1.4) blur(10px); border-bottom: 1px solid var(--line); }
.jp-brand { display: flex; align-items: center; gap: 14px; min-width: 0; }
.jp-logo { height: 22px; width: auto; display: block; }
.jp-brand-sep { width: 1px; height: 30px; background: var(--line); }
.jp-title { font-size: 18px; font-weight: 700; line-height: 1.2; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.jp-sub { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--ink2); margin-top: 2px; }
.jp-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--grn); display: inline-block; animation: jpPulse 1.8s ease-out infinite; }
.jp-dot.off { background: var(--mut); animation: none; }
@keyframes jpPulse { 0% { box-shadow: 0 0 0 0 rgba(13,135,86,.5); } 80%, 100% { box-shadow: 0 0 0 8px rgba(13,135,86,0); } }
.jp-actions { display: flex; align-items: center; gap: 8px; }
.jp-icon-btn { width: 40px; height: 40px; border-radius: 12px; border: 1px solid var(--line); background: #fff; display: grid; place-items: center; }
.jp-icon-btn svg { width: 18px; height: 18px; }
.jp-icon-btn.spin svg { animation: jpSpin .9s linear infinite; }
@keyframes jpSpin { to { transform: rotate(360deg); } }
.jp-pill-btn { min-height: 40px; min-width: 52px; padding: 0 14px; border-radius: 999px; border: 1px solid #e3ddd3; background: #fff; font-weight: 700; font-size: 13px; font-family: "Plus Jakarta Sans", "IBM Plex Sans Arabic", sans-serif; }
.jp-menu-wrap { position: relative; }
.jp-menu { position: absolute; inset-inline-end: 0; top: 46px; min-width: 230px; background: #fff; border: 1px solid var(--line); border-radius: 14px; box-shadow: 0 12px 34px rgba(22,19,15,.14); padding: 6px; display: flex; flex-direction: column; z-index: 30; }
.jp-menu-head { font-size: 12px; color: var(--mut); padding: 8px 10px; border-bottom: 1px solid var(--line); margin-bottom: 4px; overflow: hidden; text-overflow: ellipsis; }
.jp-menu button, .jp-menu a { text-align: start; border: 0; background: transparent; padding: 11px 10px; border-radius: 10px; font-size: 14px; color: var(--ink); text-decoration: none; }
.jp-menu button:hover, .jp-menu a:hover { background: var(--bg3); }
.jp-menu .danger { color: var(--red7); }

.jp-main { flex: 1; width: 100%; max-width: 1360px; margin: 0 auto; padding: 20px max(16px, env(safe-area-inset-right, 0px)) 48px max(16px, env(safe-area-inset-left, 0px)); display: flex; flex-direction: column; gap: 22px; }
.jp-sec { display: flex; flex-direction: column; gap: 14px; }
.jp-sec-head { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
.jp-sec-head h2 { margin: 0; font-size: 20px; font-weight: 700; }
.jp-sec-head h3 { margin: 0; font-size: 16px; font-weight: 700; }
.jp-sec-head small { font-size: 13px; font-weight: 500; color: var(--mut); margin-inline-start: 6px; }
.jp-note { font-size: 12.5px; color: var(--mut); }

/* motion */
.jp-rise { animation: jpRise .65s var(--ease) both; animation-delay: var(--d, 0s); }
@keyframes jpRise { from { transform: translateY(14px); opacity: .25; } to { transform: none; opacity: 1; } }
.jp-grow { transform-origin: bottom; animation: jpGrow .85s var(--ease) both; animation-delay: var(--d, 0s); }
@keyframes jpGrow { from { transform: scaleY(.04); } to { transform: scaleY(1); } }
.jp-growx { transform-origin: left; animation: jpGrowX .95s var(--ease) both; animation-delay: var(--d, 0s); }
.jp[dir="rtl"] .jp-growx { transform-origin: right; }
[dir="ltr"] .jp-growx { transform-origin: left; }
@keyframes jpGrowX { from { transform: scaleX(.03); } to { transform: scaleX(1); } }
.jp-draw { stroke-dasharray: 400; animation: jpDraw 1.5s var(--ease) both; }
@keyframes jpDraw { from { stroke-dashoffset: 400; } to { stroke-dashoffset: 0; } }

/* today */
.jp-today { display: grid; grid-template-columns: minmax(300px, 1fr) minmax(0, 2fr); grid-template-areas: "hero head" "hero cards"; gap: 10px 14px; }
.jp-hero { grid-area: hero; position: relative; overflow: hidden; background: var(--blk); color: #fff; border-radius: 22px; padding: 22px; display: flex; flex-direction: column; gap: 14px; }
.jp-hero-glow { position: absolute; inset-inline-end: -60px; top: -60px; width: 220px; height: 220px; border-radius: 50%; background: radial-gradient(circle, rgba(196,48,28,.45), rgba(196,48,28,0) 70%); pointer-events: none; }
.jp-hero-top { display: flex; justify-content: space-between; align-items: center; gap: 8px; font-size: 13px; color: #e3ddd3; font-weight: 600; position: relative; }
.jp-live { display: inline-flex; align-items: center; gap: 6px; font-size: 11.5px; font-weight: 700; background: rgba(255,255,255,.1); border-radius: 999px; padding: 4px 10px; color: #fff; }
.jp-hero-num { position: relative; font-family: "Plus Jakarta Sans", sans-serif; font-size: 64px; font-weight: 800; line-height: 1; letter-spacing: -2px; }
.jp-hero-chips { position: relative; display: flex; gap: 8px; flex-wrap: wrap; }
.jp-chip { font-size: 12.5px; font-weight: 600; border-radius: 999px; padding: 4px 10px; color: var(--blk); background: #cdeeda; }
.jp-chip.bad { background: #f8d7d1; }
.jp-chip.flat { background: #e3ddd3; }
.jp-chip b { font-family: "Plus Jakarta Sans", sans-serif; font-weight: 800; }
.jp-hero-meta { position: relative; display: flex; gap: 16px; flex-wrap: wrap; font-size: 12.5px; color: #e3ddd3; }
.jp-hero-meta b { color: #fff; font-family: "Plus Jakarta Sans", sans-serif; font-size: 15px; }
.jp-hours-wrap { position: relative; margin-top: auto; }
.jp-hours-label { font-size: 11.5px; color: #b9b2a6; margin-bottom: 8px; }
.jp-hours { display: flex; align-items: flex-end; gap: 3px; height: 110px; }
.jp-hcol { flex: 1; height: 100%; display: flex; align-items: flex-end; }
.jp-hbar { width: 100%; background: rgba(255,255,255,.82); border-radius: 4px 4px 2px 2px; }
.jp-hbar.now { background: var(--red); }
.jp-hbar.future { background: rgba(255,255,255,.12); }
.jp-hours-axis { display: flex; justify-content: space-between; font-size: 10px; color: #8f887d; margin-top: 6px; }
.jp-cards-head { grid-area: head; font-size: 13px; font-weight: 700; color: var(--ink2); align-self: end; }
.jp-cards-head.phone { grid-column: 1 / -1; }
.jp-cards { grid-area: cards; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.jp-card { background: #fff; border: 1px solid var(--line); border-radius: 18px; padding: 16px; display: flex; flex-direction: column; gap: 8px; transition: transform .25s var(--ease), box-shadow .25s; }
.jp-card:hover { transform: translateY(-3px); box-shadow: 0 12px 34px rgba(22,19,15,.08); }
.jp-card-top { display: flex; align-items: center; justify-content: space-between; gap: 8px; font-size: 13px; font-weight: 600; color: var(--ink2); }
.jp-ico { width: 32px; height: 32px; border-radius: 10px; display: grid; place-items: center; flex-shrink: 0; }
.jp-ico svg { width: 16px; height: 16px; }
.jp-card-num { font-family: "Plus Jakarta Sans", sans-serif; font-size: 28px; font-weight: 800; letter-spacing: -.6px; line-height: 1.1; }
.jp-card-num small { font-size: 12px; font-weight: 600; color: var(--mut); letter-spacing: 0; }
.jp-card-foot { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.jp-delta { font-size: 12px; font-weight: 700; border-radius: 999px; padding: 3px 9px; background: var(--bg3); color: var(--ink2); font-family: "Plus Jakarta Sans", sans-serif; }
.jp-delta.up { background: var(--grn0); color: var(--grn7); }
.jp-delta.down { background: var(--red0); color: var(--red7); }
.jp-spark { width: 96px; height: 28px; }
.jp-spark path { stroke-width: 2; }
.jp-card-note { font-size: 11.5px; color: var(--mut); line-height: 1.4; }

/* panels */
.jp-panel { background: #fff; border: 1px solid var(--line); border-radius: 22px; padding: 20px; display: flex; flex-direction: column; gap: 16px; }
.jp-panel.dark { background: var(--blk); color: #fff; border-color: var(--blk); }
.jp-panel.dark .jp-note { color: #b9b2a6; }
.jp-sec-head.in { align-items: center; }

/* funnel */
.jp-funnel { display: flex; flex-direction: column; gap: 10px; }
.jp-frow { display: grid; grid-template-columns: minmax(96px, 170px) minmax(0, 1fr) 54px; align-items: center; gap: 12px; }
.jp-flabel { font-size: 14px; font-weight: 600; }
.jp-ftrack { background: var(--bg3); border-radius: 12px; height: 36px; overflow: hidden; }
.jp-fbar { height: 100%; border-radius: 12px; display: flex; align-items: center; padding-inline: 12px; color: #fff; font-family: "Plus Jakarta Sans", sans-serif; font-weight: 800; font-size: 14px; white-space: nowrap; }
.jp-fpct { font-size: 13px; font-weight: 700; color: var(--ink2); text-align: end; font-family: "Plus Jakarta Sans", sans-serif; }
.jp-fpct.warn { color: var(--red7); }

/* month */
.jp-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 14px; }
.jp-card.ring { flex-direction: row; align-items: center; gap: 14px; }
.jp-ring { width: 118px; height: 118px; flex-shrink: 0; }
.jp-ring .bg { stroke: var(--bg3); stroke-width: 12; }
.jp-ring .fg { stroke: var(--grn); stroke-width: 12; stroke-linecap: round; }
.jp-ring text { stroke: none; font-family: "Plus Jakarta Sans", sans-serif; }
.jp-ring .big { font-size: 24px; font-weight: 800; fill: var(--ink); }
.jp-ring .small { font-size: 11px; font-weight: 700; }
.jp-ring .small.up { fill: var(--grn7); }
.jp-ring .small.down { fill: var(--red7); }
.jp-ring-txt { display: flex; flex-direction: column; gap: 5px; font-size: 12px; color: var(--mut); line-height: 1.45; }
.jp-ring-txt b { font-size: 14px; color: var(--ink); }
.jp-mini { font-family: "Plus Jakarta Sans", sans-serif; font-weight: 700; color: var(--ink2); }
.jp-badge { font-size: 11px; font-weight: 700; color: #7a5b1c; background: var(--gold0); border-radius: 999px; padding: 3px 9px; }
.jp-meter { background: var(--bg3); border-radius: 999px; height: 6px; overflow: hidden; }
.jp-meter > div { height: 100%; border-radius: 999px; }

/* cash */
.jp-two { display: grid; grid-template-columns: repeat(auto-fit, minmax(380px, 1fr)); gap: 14px; }
.jp-cash { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.jp-cashbox { border: 0; text-align: start; border-radius: 16px; padding: 16px; display: flex; flex-direction: column; gap: 6px; min-height: 120px; }
.jp-cashbox span { font-size: 12.5px; font-weight: 600; opacity: .85; }
.jp-cashbox b { font-family: "Plus Jakarta Sans", sans-serif; font-size: 22px; font-weight: 800; letter-spacing: -.4px; }
.jp-cashbox b small { font-size: 11.5px; font-weight: 600; opacity: .7; }
.jp-cashbox em { font-style: normal; font-size: 11.5px; opacity: .8; line-height: 1.4; }
.jp-cashbox.dark { background: var(--blk); color: #fff; }
.jp-cashbox.blue { background: var(--blue0); }
.jp-cashbox.green { background: var(--grn0); }
.jp-cashbox.red { background: var(--red0); }
.jp-accounts { border-top: 1px solid var(--line); display: flex; flex-direction: column; }
.jp-acc { display: flex; justify-content: space-between; gap: 10px; padding: 9px 2px; border-bottom: 1px solid var(--line); font-size: 12.5px; }
.jp-acc b { font-family: "Plus Jakarta Sans", sans-serif; }
.jp-empty { font-size: 13px; color: #b9b2a6; }
.jp-ship { background: rgba(255,255,255,.06); border: 1px solid rgba(255,255,255,.1); border-radius: 16px; padding: 14px; display: flex; flex-direction: column; gap: 10px; }
.jp-ship-top { display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 14px; }
.jp-ship-top code { font-family: "Plus Jakarta Sans", monospace; font-size: 11.5px; color: #b9b2a6; margin-inline-start: 6px; }
.jp-ship-days { font-size: 11.5px; font-weight: 700; background: var(--red); border-radius: 999px; padding: 4px 10px; }
.jp-route { position: relative; height: 30px; }
.jp-route .line { position: absolute; left: 8px; right: 8px; top: 14px; border-top: 2px dashed rgba(255,255,255,.25); }
.jp-route .done { position: absolute; left: 8px; top: 14px; height: 2px; background: #e2a93b; }
.jp-route .dot { position: absolute; top: 9px; width: 12px; height: 12px; border-radius: 50%; }
.jp-route .from { left: 0; background: #e2a93b; }
.jp-route .to { right: 0; border: 2px solid #fff; }
.jp-route .boat { position: absolute; top: 0; width: 26px; height: 26px; color: #fff; animation: jpSail 5s cubic-bezier(.45,0,.55,1) infinite alternate; }
@keyframes jpSail { from { transform: translateX(-4px); } to { transform: translateX(8px); } }
.jp-route-lbl { display: flex; justify-content: space-between; font-size: 11.5px; color: #b9b2a6; }
.jp-ship-stats { display: flex; gap: 16px; flex-wrap: wrap; font-size: 12px; color: #e3ddd3; }
.jp-ship-stats b { font-family: "Plus Jakarta Sans", sans-serif; font-size: 15px; color: #fff; }

/* trend */
.jp-seg { display: inline-flex; flex-wrap: wrap; background: var(--bg3); border-radius: 999px; padding: 4px; gap: 2px; }
.jp-seg button { border: 0; background: transparent; border-radius: 999px; padding: 8px 14px; min-height: 38px; font-size: 13px; font-weight: 700; color: var(--ink2); transition: background .2s, color .2s; }
.jp-seg button.on { background: var(--blk); color: #fff; }
.jp-chart-wrap { overflow-x: auto; overflow-y: hidden; }
.jp-chart { min-width: 640px; height: 250px; display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 10px; align-items: end; }
.jp-col { height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; gap: 7px; }
.jp-col-val { font-family: "Plus Jakarta Sans", sans-serif; font-size: 11.5px; font-weight: 700; }
.jp-col-val.open { color: var(--red7); }
.jp-col-bar { width: 100%; max-width: 54px; background: var(--blk); border-radius: 10px 10px 4px 4px; }
.jp-col-bar.last { background: var(--red); }
.jp-col-bar.open { background: repeating-linear-gradient(135deg, var(--red0) 0 6px, #fff 6px 12px); border: 2px dashed var(--red); }
.jp-col-m { font-size: 11.5px; font-weight: 600; color: var(--ink2); }
.jp-legend { display: flex; gap: 16px; flex-wrap: wrap; font-size: 12px; color: var(--ink2); }
.jp-legend span { display: inline-flex; align-items: center; gap: 6px; }
.sq { width: 10px; height: 10px; border-radius: 3px; display: inline-block; }
.sq.solid { background: var(--blk); }
.sq.dashed { border: 2px dashed var(--red); }
.jp-mlist { display: flex; flex-direction: column; border: 1px solid var(--line); border-radius: 14px; overflow: hidden; }
.jp-mrow { display: flex; justify-content: space-between; align-items: center; gap: 8px; padding: 11px 14px; border-bottom: 1px solid var(--line); font-size: 13px; font-weight: 600; }
.jp-mrow:last-child { border-bottom: 0; }
.jp-mrow span:last-child { display: flex; align-items: center; gap: 8px; }
.jp-mrow b { font-family: "Plus Jakarta Sans", sans-serif; font-size: 14px; }
.jp-mrow b.open { color: var(--red7); }
.jp-mrow em { font-style: normal; font-size: 10.5px; font-weight: 700; border-radius: 999px; padding: 2px 8px; }
.jp-mrow em.ok { background: var(--grn0); color: var(--grn7); }
.jp-mrow em.run { background: var(--red0); color: var(--red7); }

.jp-foot { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 10px; font-size: 12px; color: var(--mut); padding-inline: 4px; }

/* banners, errors, skeleton */
.jp-banner { display: flex; align-items: center; gap: 12px; background: var(--blk); color: #fff; border-radius: 16px; padding: 12px; }
.jp-banner-ico { width: 42px; height: 42px; border-radius: 11px; flex-shrink: 0; }
.jp-banner-txt { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.jp-banner-txt b { font-size: 14px; }
.jp-banner-txt span { font-size: 12px; color: #b9b2a6; }
.jp-red-btn { border: 0; background: var(--red); color: #fff; border-radius: 999px; min-height: 38px; padding: 0 16px; font-weight: 700; font-size: 13px; white-space: nowrap; }
.jp-x { border: 0; background: transparent; color: #b9b2a6; width: 34px; height: 38px; display: grid; place-items: center; }
.jp-x svg { width: 16px; height: 16px; }
.jp-error { background: var(--red0); color: var(--red7); border-radius: 16px; padding: 16px; display: flex; flex-direction: column; gap: 8px; align-items: flex-start; font-size: 13px; }
.jp-toast { position: fixed; z-index: 40; left: 50%; transform: translateX(-50%); bottom: calc(env(safe-area-inset-bottom, 0px) + 96px); background: var(--blk); color: #fff; padding: 12px 16px; border-radius: 14px; font-size: 13px; max-width: min(92vw, 460px); box-shadow: 0 12px 34px rgba(22,19,15,.25); }
.jp-skel { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 14px; }
.sk { height: 140px; border-radius: 18px; background: linear-gradient(90deg, var(--bg3), #fff, var(--bg3)); background-size: 200% 100%; animation: jpShim 1.2s linear infinite; }
.sk.hero { height: 320px; grid-row: span 2; }
@keyframes jpShim { to { background-position: -200% 0; } }

/* ── phone app ── */
.phone .jp-bar { padding-top: calc(env(safe-area-inset-top, 0px) + 10px); }
.phone .jp-logo { height: 16px; }
.phone .jp-brand { gap: 10px; }
.phone .jp-brand-sep { height: 26px; }
.phone .jp-title { font-size: 16px; }
.phone .jp-main { padding: 6px 14px calc(env(safe-area-inset-bottom, 0px) + 92px); gap: 14px; }
.phone .jp-today { grid-template-columns: 1fr; grid-template-areas: "hero" "cards"; gap: 12px; }
.phone .jp-hero { padding: 18px; border-radius: 20px; }
.phone .jp-hero-num { font-size: 52px; }
.phone .jp-hours { height: 74px; gap: 2px; }
.phone .jp-cards { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.phone .jp-card { padding: 12px; border-radius: 16px; gap: 6px; }
.phone .jp-card-top { font-size: 11.5px; }
.phone .jp-ico { width: 28px; height: 28px; border-radius: 8px; }
.phone .jp-card-num { font-size: 21px; }
.phone .jp-spark { width: 54px; height: 20px; }
.phone .jp-card-note { display: none; }
.phone .jp-grid .jp-card-note { display: block; }
.phone .jp-panel { padding: 14px; border-radius: 18px; }
.phone .jp-frow { grid-template-columns: 1fr 46px; grid-template-areas: "l p" "t t"; gap: 4px 8px; }
.phone .jp-flabel { grid-area: l; font-size: 12.5px; }
.phone .jp-fpct { grid-area: p; }
.phone .jp-ftrack { grid-area: t; height: 26px; border-radius: 9px; }
.phone .jp-fbar { font-size: 12px; border-radius: 9px; }
.phone .jp-grid { grid-template-columns: 1fr; gap: 10px; }
.phone .jp-two { grid-template-columns: 1fr; }
.phone .jp-cash { gap: 10px; }
.phone .jp-cashbox { padding: 13px; min-height: 110px; }
.phone .jp-cashbox b { font-size: 18px; }
.phone .jp-chart { min-width: 0; height: 200px; gap: 4px; }
.phone .jp-col-val { display: none; }
.phone .jp-col-m { font-size: 9.5px; }
.phone .jp-seg { display: flex; width: 100%; }
.phone .jp-seg button { flex: 1; padding: 8px 4px; font-size: 12px; }
.jp-pull { display: flex; align-items: center; justify-content: center; gap: 8px; font-size: 12px; color: var(--mut); overflow: hidden; transition: height .2s; }
.jp-pull svg { width: 16px; height: 16px; }
.jp-tabs { position: fixed; z-index: 25; left: 0; right: 0; bottom: 0; background: #fff; border-top: 1px solid var(--line); box-shadow: 0 -8px 20px rgba(16,24,40,.06);
  padding: 6px 8px calc(env(safe-area-inset-bottom, 0px) + 8px); display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); }
.jp-tabs button { position: relative; border: 0; background: transparent; min-height: 54px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px; color: var(--mut); font-size: 11.5px; font-weight: 700; transition: color .2s; }
.jp-tabs button svg { width: 22px; height: 22px; }
.jp-tabs button i { position: absolute; top: -7px; width: 28px; height: 3px; border-radius: 0 0 3px 3px; background: transparent; }
.jp-tabs button.on { color: var(--red); }
.jp-tabs button.on i { background: var(--red); }

@media (max-width: 1180px) and (min-width: 761px) {
  .jp-today { grid-template-columns: 1fr; grid-template-areas: "hero" "head" "cards"; }
}
@media (prefers-reduced-motion: reduce) {
  .jp-rise, .jp-grow, .jp-growx, .jp-draw, .jp-route .boat, .jp-dot, .sk { animation: none !important; }
  .jp-card { transition: none; }
}
</style>
