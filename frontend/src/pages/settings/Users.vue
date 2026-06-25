<template>
  <div class="space-y-3">
    <div class="flex items-center gap-2 flex-wrap">
      <span class="inline-flex items-center gap-1.5 text-[10.5px] font-bold uppercase tracking-wider px-2 py-1 rounded-chip"
            :class="live ? 'text-success-dark bg-success-soft' : 'text-amber-700 bg-amber-50'">
        <span class="w-1.5 h-1.5 rounded-full" :class="live ? 'bg-success' : 'bg-amber-500'"></span>{{ live ? L("Live","مباشر","Live") : L("Sample","عيّنة","Échantillon") }}
      </span>
      <span class="text-[11px] text-ink-muted">{{ L("Everyone with portal access and their role.","كل من لديه صلاحية الدخول ودوره.","Chaque utilisateur du portail et son rôle.") }}</span>
      <button v-if="canManage" @click="openInvite" class="ms-auto inline-flex items-center gap-1.5 h-8 px-3 rounded-chip text-[12px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand"><Icon name="plus" :size="13" color="#fff" />{{ L("Invite","دعوة","Inviter") }}</button>
    </div>

    <div class="bg-white border border-line rounded-[14px] shadow-card overflow-hidden">
      <table class="w-full text-[12px]">
        <thead><tr style="background:#fafaf9">
          <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("User","المستخدم","Utilisateur") }}</th>
          <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Role","الدور","Rôle") }}</th>
          <th class="px-4 py-2.5 text-start text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Last active","آخر نشاط","Dernière activité") }}</th>
          <th class="px-4 py-2.5 text-end text-[10px] font-bold uppercase tracking-wider text-ink-muted">{{ L("Status","الحالة","Statut") }}</th>
        </tr></thead>
        <tbody>
          <tr v-for="u in users" :key="u.user" class="border-t border-line-hair hover:bg-app-warm/40" :class="!u.enabled && 'opacity-55'">
            <td class="px-4 py-2.5">
              <span class="flex items-center gap-2.5">
                <span class="w-7 h-7 rounded-full grid place-items-center text-white text-[10px] font-bold flex-shrink-0" :style="{ background: badge(u.user) }">{{ ini(u.full_name) }}</span>
                <span class="min-w-0"><span class="block font-semibold truncate max-w-[200px]">{{ u.full_name }}</span><span class="block text-[10.5px] text-ink-muted truncate max-w-[200px]">{{ u.user }}</span></span>
                <span v-if="u.user === me" class="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-app-warm text-ink-3">{{ L("you","أنت","vous") }}</span>
              </span>
            </td>
            <td class="px-4 py-2.5">
              <select v-if="canManage" :value="u.role" @change="changeRole(u, $event.target.value)" :disabled="busy"
                      class="h-8 border border-line-2 rounded-[8px] px-2 text-[11.5px] bg-white focus:outline-none focus:border-accent/40 disabled:opacity-50">
                <option v-for="r in roles" :key="r.role" :value="r.role">{{ r.label }}</option>
              </select>
              <span v-else class="inline-flex text-[11px] font-bold px-2 py-0.5 rounded-badge" style="background:#faf6f4;color:#0b5c4f">{{ roleLabel(u.role) }}</span>
            </td>
            <td class="px-4 py-2.5 text-ink-3 whitespace-nowrap">{{ u.last_active ? when(u.last_active) : "—" }}</td>
            <td class="px-4 py-2.5 text-end">
              <button v-if="canManage && u.user !== me && u.user !== 'Administrator'" @click="toggle(u)" :disabled="busy"
                      class="text-[10.5px] font-bold px-2 py-0.5 rounded-full border disabled:opacity-50"
                      :style="u.enabled ? 'background:#ecfdf5;color:#047857;border-color:#a7f3d0' : 'background:#fef2f2;color:#b91c1c;border-color:#fecaca'">
                {{ u.enabled ? L("Active","نشط","Actif") : L("Disabled","معطّل","Désactivé") }}
              </button>
              <span v-else class="text-[10.5px] font-bold px-2 py-0.5 rounded-full" :style="u.enabled ? 'background:#ecfdf5;color:#047857' : 'background:#fef2f2;color:#b91c1c'">{{ u.enabled ? L("Active","نشط","Actif") : L("Disabled","معطّل","Désactivé") }}</span>
            </td>
          </tr>
          <tr v-if="!users.length"><td colspan="4" class="px-4 py-10 text-center text-ink-muted text-[12px]">{{ L("No portal users.","لا مستخدمين.","Aucun utilisateur.") }}</td></tr>
        </tbody>
      </table>
    </div>

    <!-- Invite modal -->
    <div v-if="inviteOpen" class="fixed inset-0 z-50 grid place-items-center bg-black/30 p-4" @click.self="inviteOpen = false">
      <div class="bg-white rounded-card shadow-xl w-full max-w-sm p-5 space-y-3">
        <div class="text-[14px] font-bold">{{ L("Invite teammate","دعوة عضو","Inviter un membre") }}</div>
        <div><label class="text-[11px] font-bold text-ink-3">{{ L("Email","البريد","E-mail") }} *</label><input v-model.trim="inv.email" type="email" class="w-full h-9 mt-1 border border-line-2 rounded-[9px] px-2 text-[12.5px] focus:outline-none focus:border-accent/40" /></div>
        <div><label class="text-[11px] font-bold text-ink-3">{{ L("Full name","الاسم","Nom complet") }}</label><input v-model.trim="inv.full_name" class="w-full h-9 mt-1 border border-line-2 rounded-[9px] px-2 text-[12.5px] focus:outline-none focus:border-accent/40" /></div>
        <div><label class="text-[11px] font-bold text-ink-3">{{ L("Role","الدور","Rôle") }}</label>
          <select v-model="inv.role" class="w-full h-9 mt-1 border border-line-2 rounded-[9px] px-2 text-[12.5px] bg-white focus:outline-none focus:border-accent/40"><option v-for="r in roles" :key="r.role" :value="r.role">{{ r.label }} — {{ r.desc }}</option></select></div>
        <p class="text-[10px] text-ink-muted">{{ L("They receive a welcome email to set a password.","سيصلهم إيميل ترحيبي لتعيين كلمة المرور.","Ils reçoivent un e-mail de bienvenue.") }}</p>
        <div class="flex gap-2 justify-end pt-1">
          <button @click="inviteOpen = false" class="h-9 px-3 rounded-[9px] text-[12px] font-semibold text-ink-3 hover:bg-app-warm">{{ L("Cancel","إلغاء","Annuler") }}</button>
          <button @click="sendInvite" :disabled="inviting || !inv.email" class="h-9 px-4 rounded-[9px] text-[12px] font-bold text-white bg-brand hover:bg-brand-dark shadow-brand disabled:opacity-50">{{ inviting ? L("Inviting…","جارٍ…","…") : L("Send invite","إرسال","Envoyer") }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import api from "@/services/api";
import { useToast } from "@/composables/useToast";

const { locale } = useI18n();
const toast = useToast();
const L = (en, ar, fr) => (locale.value === "ar" ? ar : locale.value === "fr" ? fr : en);
const ini = (n) => String(n || "?").trim().split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
const PALETTE = ["#2563eb", "#7c3aed", "#0891b2", "#c2410c", "#16a34a", "#be123c", "#a16207", "#0b5c4f"];
const badge = (s) => { let h = 0; for (const c of String(s)) h = (h * 31 + c.charCodeAt(0)) % PALETTE.length; return `linear-gradient(135deg,${PALETTE[h]},${PALETTE[(h + 3) % PALETTE.length]})`; };

const live = ref(false);
const users = ref([]);
const roles = ref([]);
const canManage = ref(false);
const me = ref("");
const busy = ref(false);

async function load() {
  try {
    const r = await api.call("accounting_portal.api.users.list_portal_users", {});
    users.value = r.users || []; roles.value = r.roles || []; canManage.value = !!r.can_manage; me.value = r.me; live.value = true;
  } catch { live.value = false; users.value = []; }
}
onMounted(load);

const roleLabel = (role) => (roles.value.find((r) => r.role === role)?.label || role || "—");
function when(d) { return String(d).slice(0, 16).replace("T", " "); }

async function changeRole(u, role) {
  if (role === u.role) return;
  busy.value = true;
  try { await api.call("accounting_portal.api.users.set_portal_role", { user: u.user, role }); toast.success(L("Role updated", "تم تحديث الدور", "Rôle mis à jour")); load(); }
  catch (e) { toast.error(String((e && e.message) || L("Failed", "فشل", "Échec")).slice(0, 140)); load(); }
  finally { busy.value = false; }
}
async function toggle(u) {
  busy.value = true;
  try { await api.call("accounting_portal.api.users.set_user_enabled", { user: u.user, enabled: u.enabled ? 0 : 1 }); toast.success(u.enabled ? L("Disabled", "تم التعطيل", "Désactivé") : L("Enabled", "تم التفعيل", "Activé")); load(); }
  catch (e) { toast.error(String((e && e.message) || L("Failed", "فشل", "Échec")).slice(0, 140)); }
  finally { busy.value = false; }
}

// ── Invite ──
const inviteOpen = ref(false);
const inviting = ref(false);
const inv = ref({ email: "", full_name: "", role: "Accounting Viewer" });
function openInvite() { inv.value = { email: "", full_name: "", role: "Accounting Viewer" }; inviteOpen.value = true; }
async function sendInvite() {
  inviting.value = true;
  try {
    const r = await api.call("accounting_portal.api.users.invite_user", { email: inv.value.email, full_name: inv.value.full_name, role: inv.value.role });
    inviteOpen.value = false; toast.success(r.existed ? L("Access granted", "تم منح الصلاحية", "Accès accordé") : L("Invite sent", "تم إرسال الدعوة", "Invitation envoyée")); load();
  } catch (e) { toast.error(String((e && e.message) || L("Failed", "فشل", "Échec")).slice(0, 140)); }
  finally { inviting.value = false; }
}
</script>
