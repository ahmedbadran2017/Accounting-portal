import { ref, computed, watch } from "vue";

// Shared list mechanics (search · date presets/range · sort · column show/hide ·
// pagination) for any table. Pass a ref of row objects and a column spec; the
// component renders the chrome via <TableToolbar>/<TablePager> using the
// returned state. `accessor(row, colKey)` returns the comparable value for a
// column (sorting/search/date) so each screen maps its own row shape.
export function useTableTools(rowsRef, cols, opts = {}) {
  const accessor = opts.accessor || ((row, key) => row[key]);
  const dateKey = opts.dateKey || null; // column key holding a date string

  const search = ref("");
  const datePreset = ref("all");
  const from = ref("");
  const to = ref("");
  const sortKey = ref(opts.defaultSort || null);
  const sortDir = ref(opts.defaultDir || -1);
  const hidden = ref(new Set());
  const page = ref(1);
  const pageSize = ref(opts.pageSize || 50);

  function parseDate(v) {
    if (!v) return null;
    const s = String(v).trim();
    let m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (m) return new Date(+m[1], +m[2] - 1, +m[3]);
    m = s.match(/^(\d{2})-(\d{2})-(\d{4})/);
    if (m) return new Date(+m[3], +m[2] - 1, +m[1]);
    const d = new Date(s);
    return isNaN(d) ? null : d;
  }
  function bounds(key) {
    const now = new Date();
    const sod = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
    const today = sod(now);
    if (key === "today") return [today, now];
    if (key === "yesterday") { const y = new Date(today); y.setDate(y.getDate() - 1); return [y, today]; }
    if (key === "7d") { const s = new Date(today); s.setDate(s.getDate() - 7); return [s, now]; }
    if (key === "30d") { const s = new Date(today); s.setDate(s.getDate() - 30); return [s, now]; }
    if (key === "month") return [new Date(now.getFullYear(), now.getMonth(), 1), now];
    if (key === "range") return [from.value ? new Date(from.value) : null, to.value ? new Date(to.value + "T23:59:59") : null];
    return [null, null];
  }

  const dated = computed(() => {
    if (!dateKey || datePreset.value === "all") return rowsRef.value;
    const [lo, hi] = bounds(datePreset.value);
    if (!lo && !hi) return rowsRef.value;
    return rowsRef.value.filter((r) => {
      const d = parseDate(accessor(r, dateKey));
      if (!d) return false;
      if (lo && d < lo) return false;
      if (hi && d > hi) return false;
      return true;
    });
  });

  const searched = computed(() => {
    const q = search.value.toLowerCase();
    if (!q) return dated.value;
    return dated.value.filter((r) => cols.some((c) => String(accessor(r, c.key) ?? "").toLowerCase().includes(q)));
  });

  function sortVal(v) {
    const s = String(v ?? "").trim();
    const n = parseFloat(s.replace(/[^\d.-]/g, ""));
    return /^-?[\d.,\s]+%?$/.test(s) && !isNaN(n) ? n : s.toLowerCase();
  }
  const sorted = computed(() => {
    if (!sortKey.value) return searched.value;
    const k = sortKey.value, dir = sortDir.value;
    return [...searched.value].sort((a, b) => {
      const va = sortVal(accessor(a, k)), vb = sortVal(accessor(b, k));
      return va < vb ? -dir : va > vb ? dir : 0;
    });
  });

  const totalPages = computed(() => Math.max(1, Math.ceil(sorted.value.length / pageSize.value)));
  const pageRows = computed(() => sorted.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value));
  const rangeStart = computed(() => (sorted.value.length ? (page.value - 1) * pageSize.value + 1 : 0));
  const rangeEnd = computed(() => Math.min(page.value * pageSize.value, sorted.value.length));
  const visibleCols = computed(() => cols.filter((c) => !hidden.value.has(c.key)));

  function toggleSort(k) {
    if (sortKey.value === k) { sortDir.value === 1 ? (sortDir.value = -1) : (sortKey.value = null); }
    else { sortKey.value = k; sortDir.value = 1; }
  }
  function toggleCol(k) { const h = new Set(hidden.value); h.has(k) ? h.delete(k) : h.add(k); hidden.value = h; }
  function setPreset(k) { datePreset.value = k; page.value = 1; }
  function reset() { search.value = ""; datePreset.value = "all"; sortKey.value = opts.defaultSort || null; hidden.value = new Set(); page.value = 1; }

  watch([search, datePreset, from, to, pageSize, sorted], () => { if (page.value > totalPages.value) page.value = 1; });

  return {
    search, datePreset, from, to, sortKey, sortDir, hidden, page, pageSize,
    cols, visibleCols, sorted, pageRows, totalPages, rangeStart, rangeEnd,
    hasDate: !!dateKey, toggleSort, toggleCol, setPreset, reset,
  };
}
