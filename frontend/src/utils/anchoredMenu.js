// A type-ahead menu that no ancestor can clip.
//
// The item pickers live inside a table, inside a card, inside the modal's
// scrolling body. Each of those clips: `overflow-x-auto` on the table clips
// vertically too, so an absolutely-positioned menu is cut to the height of one
// row and the accountant sees nothing at all. Raising z-index does not help —
// clipping happens before stacking.
//
// So the menu leaves the tree: teleported to <body> and positioned `fixed` from
// the input's own rectangle. It follows the input while anything scrolls, and
// flips above when there is no room below.
import { ref, onBeforeUnmount } from "vue";

const GAP = 4;
const MARGIN = 8;
const MAX_H = 320;
const MIN_H = 150;

export function useAnchoredMenu(width = 340) {
  const style = ref({});
  let anchor = null;

  function place(el) {
    anchor = el || anchor;
    if (!anchor || !anchor.getBoundingClientRect) return;
    const r = anchor.getBoundingClientRect();
    const below = window.innerHeight - r.bottom - MARGIN;
    const above = r.top - MARGIN;
    const flip = below < MIN_H && above > below;
    const w = Math.min(width, window.innerWidth - MARGIN * 2);
    style.value = {
      position: "fixed",
      left: Math.max(MARGIN, Math.min(r.left, window.innerWidth - w - MARGIN)) + "px",
      width: w + "px",
      maxHeight: Math.min(MAX_H, Math.max(MIN_H, flip ? above : below)) + "px",
      overflowY: "auto",
      zIndex: 200,
      ...(flip ? { bottom: window.innerHeight - r.top + GAP + "px" } : { top: r.bottom + GAP + "px" }),
    };
  }

  const reposition = () => place();
  function follow() {
    window.addEventListener("scroll", reposition, true);   // capture: inner scrollers too
    window.addEventListener("resize", reposition);
  }
  function unfollow() {
    window.removeEventListener("scroll", reposition, true);
    window.removeEventListener("resize", reposition);
  }
  onBeforeUnmount(unfollow);
  return { style, place, follow, unfollow };
}
