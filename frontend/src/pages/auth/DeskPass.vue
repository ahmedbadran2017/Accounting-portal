<template>
  <div class="min-h-screen grid place-items-center bg-app-bg p-4">
    <div class="w-full max-w-md bg-white rounded-card shadow-card border border-line p-7">
      <div class="flex items-center gap-3 mb-5">
        <span class="w-10 h-10 rounded-full grid place-items-center" style="background:#fef3c7"><Icon name="lock" :size="18" color="#b45309" /></span>
        <div>
          <div class="text-[18px] font-bold text-ink">{{ L("The Desk is closed for your account", "الـ Desk مقفول على حسابك", "Le Desk est fermé pour votre compte") }}</div>
          <div class="text-[12px] text-ink-muted">{{ me || "…" }}</div>
        </div>
      </div>

      <div v-if="loading" class="text-[12px] text-ink-muted py-6 text-center">…</div>

      <!-- not locked at all -->
      <template v-else-if="!st.locked">
        <p class="text-[13px] text-ink-2 mb-4">{{ L("Your account is not locked. You can open the Desk directly.", "حسابك مش مقفول. تقدر تفتح الـ Desk مباشرة.", "Votre compte n'est pas verrouillé.") }}</p>
        <a :href="next" class="block text-center rounded-chip bg-brand hover:bg-brand-dark text-white text-[13px] font-semibold py-2.5 shadow-btn">{{ L("Open the Desk", "افتح الـ Desk", "Ouvrir le Desk") }}</a>
      </template>

      <!-- active pass -->
      <template v-else-if="st.remaining_min > 0">
        <div class="rounded-[10px] px-3 py-2.5 mb-4 text-[13px]" style="background:#ecfdf5;color:#065f46">
          {{ L("You hold a desk pass until", "عندك تصريح Desk لحد", "Vous avez un accès Desk jusqu'à") }} <b><bdi dir="ltr">{{ (st.pass_until || "").slice(11, 16) }}</bdi></b>
          · {{ st.remaining_min }} {{ L("min left", "دقيقة باقية", "min restantes") }}
        </div>
        <a :href="next" class="block text-center rounded-chip bg-brand hover:bg-brand-dark text-white text-[13px] font-semibold py-2.5 shadow-btn">{{ L("Open the Desk", "افتح الـ Desk", "Ouvrir le Desk") }}</a>
      </template>

      <!-- locked, no pass: ask for one -->
      <template v-else>
        <p class="text-[13px] text-ink-2 leading-relaxed mb-3">
          {{ L("Daily work happens in the portal. If something is still only possible in the Desk, write what you need it for and you get the Desk for one hour — immediately, no approval. Every pass is logged with the reason and what was done, so the portal gets built where it is actually missing.",
               "الشغل اليومي بيتعمل من البورتال. لو في حاجة لسه مش ممكنة غير من الـ Desk، اكتب محتاجه في إيه وهتاخد الـ Desk ساعة فورًا من غير موافقة. كل تصريح بيتسجل بالسبب واللي اتعمل فيه، علشان البورتال يتبني في المكان الناقص فعلًا.",
               "Le travail quotidien se fait dans le portail. Si une tâche n'est possible que dans le Desk, indiquez le besoin et vous obtenez le Desk pour une heure, immédiatement. Chaque accès est journalisé.") }}
        </p>
        <label class="block text-[12px] font-bold text-ink-3 mb-1">{{ L("What do you need the Desk for?", "كنت هتعمل إيه في الـ Desk؟", "Pourquoi avez-vous besoin du Desk ?") }}</label>
        <textarea v-model.trim="reason" rows="3" :placeholder="L('e.g. run December payroll for Morocco', 'مثال: تشغيل مرتبات ديسمبر للمغرب', 'ex. lancer la paie de décembre')"
                  class="fld fld-md fld-sunk w-full"></textarea>
        <p v-if="error" class="text-[12px] text-sale mt-2">{{ error }}</p>
        <UiButton variant="primary" size="md" icon="clock" class="mt-3 w-full" @click="ask" :disabled="busy || reason.length < 3" > {{ busy ? "…" : L("Open the Desk for 1 hour", "افتحلي الـ Desk ساعة", "Ouvrir le Desk pour 1 h") }}
        </UiButton>
      </template>

      <div class="mt-5 pt-4 border-t border-line-hair flex items-center justify-between text-[12px]">
        <router-link to="/accounting/dashboard" class="text-brand-dark font-semibold hover:underline">← {{ L("Back to the portal", "رجوع للبورتال", "Retour au portail") }}</router-link>
        <span class="text-ink-muted"><bdi dir="ltr">{{ next }}</bdi></span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { useRoute } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import api from "@/services/api";
import { useAuth } from "@/composables/useAuth";
import UiButton from "@/components/UiButton.vue";

const { locale } = useI18n();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const route = useRoute();
const auth = useAuth();
const me = computed(() => auth.user?.value || "");

// Only a same-site Desk path is ever honoured (the backend re-checks too).
const next = computed(() => {
  const n = String(route.query.next || "");
  return n.startsWith("/app") && !n.includes("://") && !n.startsWith("//") ? n : "/app";
});

const st = ref({ locked: true, remaining_min: 0, pass_until: null });
const loading = ref(true);
const reason = ref("");
const busy = ref(false);
const error = ref("");

async function load() {
  loading.value = true;
  try { st.value = (await api.call("accounting_portal.api.deskguard.desk_status", {}, { fresh: true })) || st.value; }
  catch { /* keep the locked default: the page is still usable */ }
  finally { loading.value = false; }
}
onMounted(load);

async function ask() {
  busy.value = true; error.value = "";
  try {
    const r = await api.call("accounting_portal.api.deskguard.request_desk_pass", { reason: reason.value, next: next.value });
    window.location.href = r?.redirect || next.value;
  } catch (e) {
    error.value = String(e?.message || e).slice(0, 160);
  } finally { busy.value = false; }
}
</script>
