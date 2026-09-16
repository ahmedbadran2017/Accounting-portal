import api, { apiHealth } from "@/services/api";
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
// The books are live. A fabricated figure that renders exactly like a real one is
// worse than a blank screen, so a failed load keeps the SHAPE of the fallback —
// so every downstream computed and template still resolves — and none of its
// numbers: arrays empty, numbers zero, strings blank.
export function blankLike(v) {
  if (Array.isArray(v)) return [];
  if (v && typeof v === "object") {
    const out = {};
    for (const k of Object.keys(v)) out[k] = blankLike(v[k]);
    return out;
  }
  if (typeof v === "number") return 0;
  if (typeof v === "string") return "";
  if (typeof v === "boolean") return false;
  return v;
}

export async function liveOrSample(method, args, fallback, normalize) {
  try {
    const r = await api.call(method, args || {});
    return { live: true, data: normalize ? normalize(r) : r };
  } catch (e) {
    // Never silent: the header shows an amber chip naming every endpoint that
    // failed, so a blank figure can't pass for a real zero either.
    apiHealth.samples++;
    if (!apiHealth.sampleMethods.includes(method)) apiHealth.sampleMethods.push(method);
    const shape = typeof fallback === "function" ? fallback() : fallback;
    return { live: false, error: String(e?.message || e).slice(0, 180), data: blankLike(shape) };
  }
}

const AVS = ["rose", "sky", "amber", "emerald", "violet", "accent"];
export const avFor = (i) => AVS[i % AVS.length];
export const iniOf = (name) =>
  (name || "?").trim().split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
