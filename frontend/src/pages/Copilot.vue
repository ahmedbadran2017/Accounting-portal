<template>
  <div class="grid lg:grid-cols-[360px_1fr] gap-3.5 lg:h-[calc(100vh-104px)]">
    <!-- Anomaly feed -->
    <div class="bg-white rounded-card border border-line flex flex-col min-h-0">
      <div class="px-4 py-3 border-b border-line flex items-center gap-2">
        <Icon name="shield" :size="15" color="#7c3aed" />
        <span class="text-[13px] font-bold">{{ L("Anomalies","الشذوذ","Anomalies") }}</span>
        <span class="ms-auto text-[11px] text-ink-muted tnum">{{ ANOMALIES.length }} {{ L("open","مفتوحة","ouvertes") }}</span>
      </div>
      <div class="flex-1 overflow-y-auto p-3 space-y-2.5">
        <div v-for="a in ANOMALIES" :key="a.id" class="rounded-card border border-line p-3 hover:bg-app-warm/50">
          <div class="flex items-start gap-2.5">
            <span class="w-7 h-7 rounded-[8px] grid place-items-center flex-shrink-0" :style="{ background: sev(a).bg }">
              <Icon :name="a.icon" :size="14" :color="sev(a).fg" />
            </span>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-1.5 flex-wrap">
                <span class="text-[12.5px] font-semibold">{{ a.title(locale) }}</span>
                <span class="text-[9px] font-bold px-1.5 py-0.5 rounded-badge border"
                      :style="{ background: sev(a).bg, color: sev(a).fg, borderColor: sev(a).bd }">{{ sevLabel(a.sev, locale) }}</span>
              </div>
              <div class="text-[11px] text-ink-3 mt-0.5 leading-snug">{{ a.desc(locale) }}</div>
              <div class="flex items-center gap-2 mt-1.5">
                <span class="font-mono text-[10.5px] text-ink-muted">{{ a.ref }}</span>
                <span v-if="a.amount" class="text-[10.5px] font-bold tnum" :class="a.amount.includes('-') ? 'text-sale' : ''">{{ a.amount }}</span>
                <button class="ms-auto text-[10.5px] font-semibold text-accent-dark hover:underline" @click="go(a.go)">{{ a.cta(locale) }} →</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Chat composer -->
    <div class="bg-white rounded-card border border-line flex flex-col min-h-0">
      <div class="px-4 py-3 border-b border-line flex items-center gap-2" style="background:linear-gradient(115deg,#1e1b3a,#3b2566);border-radius:15px 15px 0 0">
        <Icon name="shield" :size="15" color="#e9d5ff" />
        <span class="text-[13px] font-bold text-white">{{ t("nav.copilot") }}</span>
        <span class="inline-flex items-center gap-1.5 text-[10.5px] font-semibold text-violet-100 bg-white/15 px-2 py-0.5 rounded-full ms-1">
          <span class="w-1.5 h-1.5 rounded-full bg-violet-300 animate-pulse"></span>{{ t("dash.auditing") }}
        </span>
      </div>

      <div ref="thread" class="flex-1 overflow-y-auto p-4 space-y-3">
        <div v-for="(m, i) in messages" :key="i" class="flex" :class="m.role === 'user' ? 'justify-end' : 'justify-start'">
          <div class="max-w-[80%]">
            <div class="rounded-2xl px-3.5 py-2.5 text-[12.5px] leading-relaxed"
                 :class="m.role === 'user' ? 'bg-accent text-white' : 'bg-app-warm text-ink'">{{ m.text }}</div>

            <!-- Proposed-journal card (maker-checker gated) -->
            <div v-if="m.proposal" class="mt-2 rounded-card border border-violet-200 bg-violet-50/40 overflow-hidden">
              <div class="px-3 py-2 border-b border-violet-100 flex items-center gap-1.5">
                <Icon name="ledger" :size="13" color="#7c3aed" />
                <span class="text-[12px] font-bold text-violet-900">{{ m.proposal.title }}</span>
              </div>
              <table class="w-full text-[11.5px]">
                <tbody>
                  <tr v-for="(j, k) in m.proposal.lines" :key="k" class="border-b border-violet-100/60">
                    <td class="px-3 py-1.5 font-mono text-ink-2">{{ j.acc }}</td>
                    <td class="px-3 py-1.5 text-end tnum font-semibold">{{ j.dr || "—" }}</td>
                    <td class="px-3 py-1.5 text-end tnum font-semibold">{{ j.cr || "—" }}</td>
                  </tr>
                </tbody>
              </table>
              <div class="px-3 py-2 flex items-center gap-2">
                <span class="text-[10px] text-violet-700 flex items-center gap-1"><Icon name="alert" :size="11" color="#7c3aed" />{{ m.proposal.note }}</span>
                <button v-if="!m.proposal.queued" class="ms-auto inline-flex items-center gap-1.5 text-[11.5px] font-semibold text-white bg-violet px-2.5 py-1.5 rounded-chip hover:opacity-90" @click="queue(m)">
                  <Icon name="check" :size="13" />{{ L("Approve & queue","اعتماد وإرسال","Approuver & mettre en file") }}
                </button>
                <span v-else class="ms-auto inline-flex items-center gap-1.5 text-[11.5px] font-semibold text-success-dark">
                  <Icon name="check" :size="14" />{{ L("Queued for checker","في طابور المراجع","En file validateur") }}
                </span>
              </div>
            </div>
          </div>
        </div>
        <div v-if="typing" class="flex justify-start">
          <div class="bg-app-warm rounded-2xl px-3.5 py-2.5 text-[12.5px] text-ink-muted">…</div>
        </div>
      </div>

      <!-- Composer -->
      <div class="p-3 border-t border-line">
        <div class="flex items-end gap-2">
          <textarea ref="input" v-model="draft" :placeholder="L('Ask the auditor… (Enter to send)','اسأل المدقّق… (Enter للإرسال)','Demandez à l’auditeur…')"
                    rows="1" class="flex-1 resize-none bg-app-warm border border-line-2 rounded-chip px-3 py-2 text-[12.5px] focus:outline-none focus:border-accent/40 focus:bg-white"
                    @keydown.enter.exact.prevent="send"></textarea>
          <button class="inline-flex items-center justify-center w-9 h-9 rounded-chip text-white bg-accent hover:bg-accent-dark shadow-prim flex-shrink-0" @click="send">
            <Icon name="send" :size="16" />
          </button>
        </div>
        <div class="flex flex-wrap gap-1.5 mt-2">
          <button v-for="s in suggestions" :key="s" class="text-[10.5px] font-medium text-ink-3 bg-app-warm hover:text-ink px-2.5 py-1 rounded-chip" @click="quick(s)">{{ s }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, nextTick, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { ANOMALIES, SEV_META, sevLabel, seedMessages, replyTo } from "@/data/copilot";

const { t, locale } = useI18n();
const router = useRouter();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);

const messages = reactive(seedMessages(locale.value));
const draft = ref("");
const typing = ref(false);
const thread = ref(null);
const sev = (a) => SEV_META[a.sev] || SEV_META.low;

const suggestions = [
  L("Draft the suspense fix", "جهّز تصفية التعليق", "Prépare la correction d’attente"),
  L("Bounce STE-05935", "أرجِع STE-05935", "Renvoyer STE-05935"),
];

function scrollEnd() { nextTick(() => { if (thread.value) thread.value.scrollTop = thread.value.scrollHeight; }); }

function send() {
  const text = draft.value.trim();
  if (!text) return;
  messages.push({ role: "user", text });
  draft.value = "";
  scrollEnd();
  typing.value = true;
  // Canned reply stand-in (real Claude API wired in a later slice).
  setTimeout(() => {
    typing.value = false;
    messages.push(replyTo(text, locale.value));
    scrollEnd();
  }, 650);
}
function quick(s) { draft.value = s; send(); }
function queue(m) { m.proposal.queued = true; }
function go(g) { router.push(g.sub ? `/accounting/${g.module}/${g.sub}` : `/accounting/${g.module}`); }

onMounted(scrollEnd);
</script>
