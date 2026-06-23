<template>
  <div class="space-y-3.5">
    <PageHeader :title="title" :subtitle="entityName" />

    <div class="flex flex-wrap gap-1 bg-white border border-line rounded-chip p-1 w-fit max-w-full overflow-x-auto">
      <button v-for="s in subs" :key="s[0]" class="px-3 py-1.5 rounded-lg text-[12px] whitespace-nowrap"
              :class="activeSub === s[0] ? 'text-accent-dark font-semibold bg-app-warm shadow-card' : 'text-ink-3 font-medium hover:text-ink'"
              @click="goSub(s[0])">{{ t(s[1]) }}</button>
    </div>

    <!-- Users & roles -->
    <div v-if="activeSub === 'users'" class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
      <div class="px-4 py-3 border-b border-line-hair text-[13px] font-bold">{{ L("Users & roles","المستخدمون والأدوار","Utilisateurs & rôles") }}</div>
      <table class="w-full text-[12px]">
        <thead><tr style="background:#fafaf9">
          <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("User","المستخدم","Utilisateur") }}</th>
          <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Role","الدور","Rôle") }}</th>
          <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Access","الصلاحية","Accès") }}</th>
        </tr></thead>
        <tbody>
          <tr v-for="u in users" :key="u.name" class="border-t border-line-hair">
            <td class="px-4 py-2.5"><span class="flex items-center gap-2.5"><span class="w-7 h-7 rounded-full grid place-items-center text-white text-[10px] font-bold" :style="{ background: AV[u.av] }">{{ ini(u.name) }}</span><span class="font-semibold">{{ u.name }}</span></span></td>
            <td class="px-4 py-2.5 text-ink-2">{{ u.role }}</td>
            <td class="px-4 py-2.5 text-ink-3">{{ u.access }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Taxes -->
    <div v-else-if="activeSub === 'taxconf'" class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
      <div class="px-4 py-3 border-b border-line-hair text-[13px] font-bold">{{ L("Taxes","الضرائب","Taxes") }}</div>
      <table class="w-full text-[12px]">
        <thead><tr style="background:#fafaf9">
          <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Tax","الضريبة","Taxe") }}</th>
          <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Rate","النسبة","Taux") }}</th>
          <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Region","المنطقة","Région") }}</th>
        </tr></thead>
        <tbody>
          <tr v-for="x in taxes" :key="x.name" class="border-t border-line-hair">
            <td class="px-4 py-2.5 font-semibold">{{ x.name }}</td>
            <td class="px-4 py-2.5 text-end tnum font-bold">{{ x.rate }}</td>
            <td class="px-4 py-2.5 text-ink-3">{{ x.region }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Currencies -->
    <div v-else-if="activeSub === 'currencies'" class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
      <div class="px-4 py-3 border-b border-line-hair text-[13px] font-bold">{{ L("Currencies · base MAD","العملات · الأساس درهم","Devises · base MAD") }}</div>
      <table class="w-full text-[12px]">
        <thead><tr style="background:#fafaf9">
          <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Currency","العملة","Devise") }}</th>
          <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Role","الدور","Rôle") }}</th>
          <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Rate → MAD","السعر → درهم","Taux → MAD") }}</th>
        </tr></thead>
        <tbody>
          <tr v-for="c in currencies" :key="c.ccy" class="border-t border-line-hair">
            <td class="px-4 py-2.5 font-mono font-bold">{{ c.ccy }}</td>
            <td class="px-4 py-2.5 text-ink-2">{{ c.role }}</td>
            <td class="px-4 py-2.5 text-end tnum font-semibold">{{ c.rate }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Organizations -->
    <div v-else-if="activeSub === 'orgs'" class="grid sm:grid-cols-2 gap-3">
      <div v-for="e in entities" :key="e.id" class="bg-white border border-line rounded-[14px] p-4 shadow-card flex items-center gap-2.5">
        <span class="w-9 h-9 rounded-lg grid place-items-center text-white text-[11px] font-bold" :style="{ background: e.badge }">{{ e.code }}</span>
        <div class="min-w-0">
          <div class="text-[13px] font-bold truncate">{{ e.name }}</div>
          <div class="text-[11px] text-ink-muted">{{ e.place }} · {{ e.ccy }}</div>
        </div>
      </div>
    </div>

    <!-- Other settings -->
    <div v-else class="bg-white rounded-card border border-line">
      <div class="flex flex-col items-center justify-center text-center py-20 px-6">
        <div class="w-12 h-12 rounded-card grid place-items-center mb-4" style="background:#fbf2ee"><Icon name="gear" :size="22" color="#a33a22" /></div>
        <h3 class="text-[14px] font-bold">{{ title }} · {{ t("module.placeholder_title") }}</h3>
        <p class="text-[12px] text-ink-3 mt-1.5 max-w-md leading-relaxed">{{ t("module.placeholder_body") }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import PageHeader from "@/components/PageHeader.vue";
import { useUi } from "@/composables/useUi";
import { SUBTABS, defaultSub } from "@/data/nav";
import { settingsUsers, settingsTaxes, settingsCurrencies } from "@/data/settings";
import { AV } from "@/data/orders";

const { t, locale } = useI18n();
const route = useRoute();
const router = useRouter();
const { entityId, entities } = useUi();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const ini = (n) => n.split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();

const subs = SUBTABS.settings;
const activeSub = computed(() => route.params.sub || defaultSub("settings"));
const entityName = computed(() => (entities.find((e) => e.id === entityId.value) || entities[0]).name);
const title = computed(() => {
  const found = subs.find((s) => s[0] === activeSub.value);
  return found ? t(found[1]) : t("nav.settings");
});
const users = computed(() => settingsUsers(locale.value));
const taxes = computed(() => settingsTaxes(locale.value));
const currencies = computed(() => settingsCurrencies(locale.value));
function goSub(s) { router.push(`/accounting/settings/${s}`); }
</script>
