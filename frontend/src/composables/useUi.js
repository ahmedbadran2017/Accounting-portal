import { ref } from "vue";
import { ENTITIES } from "@/data/nav";

// Selected entity (top-left switcher), persisted across reloads.
const saved = (() => { try { return localStorage.getItem("ap_entity"); } catch { return null; } })();
const explicit = ENTITIES.some((e) => e.id === saved); // user has picked before
const entityId = ref(explicit ? saved : "sarl");
const entityExplicit = ref(explicit);

function setEntity(id) {
  entityId.value = id;
  entityExplicit.value = true;
  try { localStorage.setItem("ap_entity", id); } catch {}
}

/**
 * Default landing entity by role, applied once after login when the user hasn't
 * explicitly chosen an entity. Management/owners (Accounting Viewer) open on the
 * consolidated group view; the accounting team opens on Morocco (where the books
 * live). Does not persist — switching still wins and is remembered.
 */
function applyRoleDefault(role) {
  if (entityExplicit.value) return;
  entityId.value = role === "Accounting Viewer" ? "group" : "sarl";
}

export function useUi() {
  return { entityId, setEntity, applyRoleDefault, entities: ENTITIES };
}
