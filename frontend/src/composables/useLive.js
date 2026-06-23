import api from "@/services/api";
import { useUi } from "@/composables/useUi";

// The ERPNext company for the entity currently selected in the switcher.
// resolve_companies() on the backend expands "Justyol Holding" to its tree.
export function currentCompany() {
  const { entityId, entities } = useUi();
  return (entities.find((e) => e.id === entityId.value) || entities[0]).name;
}

// Shared live⇄sample bridge used by every module's list/detail. Tries the
// ERPNext endpoint; if it's unreachable (app not installed yet / 403 pre-login)
// it returns the sample so the UI always renders. Returns the source so each
// screen can show a Live/Sample badge.
export async function liveOrSample(method, args, fallback, normalize) {
  try {
    const r = await api.call(method, args || {});
    return { live: true, data: normalize ? normalize(r) : r };
  } catch {
    return { live: false, data: fallback() };
  }
}

const AVS = ["rose", "sky", "amber", "emerald", "violet", "accent"];
export const avFor = (i) => AVS[i % AVS.length];
export const iniOf = (name) =>
  (name || "?").trim().split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
