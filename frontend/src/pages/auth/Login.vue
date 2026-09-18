<template>
  <div class="min-h-screen grid place-items-center bg-app-bg p-4">
    <div class="w-full max-w-sm bg-white rounded-card shadow-card border border-line p-7">
      <div class="flex items-center justify-center gap-3 mb-7 mt-1">
        <img :src="LOGO_URL" alt="Justyol" class="h-[26px] w-auto" />
        <span class="w-px h-7 bg-line-2"></span>
        <span class="text-[24px] font-bold tracking-tight text-brand-dark">Books</span>
      </div>

      <form @submit.prevent="onSubmit" class="space-y-4">
        <div>
          <label class="block text-[13px] font-medium text-ink-2 mb-1">{{ t("auth.email") }}</label>
          <input v-model.trim="email" type="email" autocomplete="username" required
                 class="fld fld-md fld-sunk w-full" />
        </div>
        <div>
          <label class="block text-[13px] font-medium text-ink-2 mb-1">{{ t("auth.password") }}</label>
          <input v-model="password" type="password" autocomplete="current-password" required
                 class="fld fld-md fld-sunk w-full" />
        </div>

        <p v-if="error" class="text-[13px] text-sale">{{ error }}</p>

        <UiButton variant="primary" size="md" class="w-full" type="submit" :disabled="busy" >
          <SpinnerIcon v-if="busy" :size="16" />
          {{ busy ? t("auth.signing_in") : t("auth.sign_in") }}
        </UiButton>
      </form>

      <div class="flex justify-center gap-3 mt-5 text-[12px] text-ink-muted">
        <button v-for="l in LOCALES" :key="l" class="hover:text-ink font-medium"
                :class="locale === l ? 'text-accent-dark font-semibold' : ''" @click="setLocale(l)">{{ LOCALE_LABEL[l] }}</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { useAuth } from "@/composables/useAuth";
import { applyLocale, LOCALES, LOCALE_LABEL } from "@/i18n";
import { LOGO_URL } from "@/utils/constants";
import SpinnerIcon from "@/components/shared/SpinnerIcon.vue";
import UiButton from "@/components/UiButton.vue";

const { t, locale } = useI18n();
const route = useRoute();
const router = useRouter();
const { login } = useAuth();

const email = ref("");
const password = ref("");
const busy = ref(false);
const error = ref("");

function setLocale(l) { locale.value = l; applyLocale(l); }

async function onSubmit() {
  busy.value = true;
  error.value = "";
  try {
    await login(email.value, password.value);
    router.push(route.query.redirect || "/accounting/dashboard");
  } catch (e) {
    error.value = e?.status === 401 ? t("auth.invalid") : (e?.message || t("auth.invalid"));
  } finally {
    busy.value = false;
  }
}
</script>
