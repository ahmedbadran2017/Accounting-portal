import { ref, computed, watch } from "vue";

// Shared list mechanics (search · date presets/range · sort · column show/hide ·
// pagination) for any table. Pass a ref of row objects and a column spec; the
// component renders the chrome via <TableToolbar>/<TablePager> using the
// returned state. `accessor(row, colKey)` returns the comparable value for a
// column (sorting/search/date) so each screen maps its own row shape.
export function useTableTools(rowsRef, cols, opts = {}) {
  const accessor = opts.accessor || ((row, key) => row[key]);
  const dateKey = opts.dateKey || null; // column key holding a date string
  const facetDefs = opts.facets || []; // [{key, label}] columns exposed as dropdowns

  // Lists with a date column open on "This month" by default (focused, not a
  // 500-row dump); date-less lists open on "all".
  const initialPreset = dateKey ? (opts.defaultDate || "month") : "all";
  const search = ref("");
  const facetActive = ref({}); // { colKey: selectedValue }
  const datePreset = ref(initialPreset);
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
    // "22 Jun" without a year — JS would parse it as 2001, so handle first.
    if (/^\d{1,2}\s+[A-Za-z]{3,}$/.test(s)) {
      const dy = new Date(s + " " + new Date().getFullYear());
      return isNaN(dy) ? null : dy;
    }
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

  // Distinct, sorted values per facet column (for the dropdowns).
  const facetOptions = computed(() => {
    const out = {};
    for (const f of facetDefs) {
      const seen = new Set();
      for (const r of rowsRef.value) {
        const v = String(accessor(r, f.key) ?? "").trim();
        if (v && v !== "—") seen.add(v);
      }
      out[f.key] = [...seen].sort((a, b) => a.localeCompare(b)).slice(0, 60);
    }
    return out;
  });

  const faceted = computed(() => {
    const active = Object.entries(facetActive.value).filter(([, v]) => v);
    if (!active.length) return rowsRef.value;
    return rowsRef.value.filter((r) => active.every(([k, v]) => String(accessor(r, k) ?? "").trim() === v));
  });

  const dated = computed(() => {
    if (!dateKey || datePreset.value === "all") return faceted.value;
    const [lo, hi] = bounds(datePreset.value);
    if (!lo && !hi) return faceted.value;
    return faceted.value.filter((r) => {
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
  function setFacet(k, v) { facetActive.value = { ...facetActive.value, [k]: v || undefined }; page.value = 1; }
  function reset() { search.value = ""; datePreset.value = initialPreset; facetActive.value = {}; sortKey.value = opts.defaultSort || null; hidden.value = new Set(); page.value = 1; }

  // Export the current (filtered + sorted) view to CSV, visible columns only.
  function exportCSV(filename) {
    const vc = visibleCols.value;
    const esc = (v) => {
      const s = String(v ?? "").replace(/"/g, '""');
      return /[",\n]/.test(s) ? `"${s}"` : s;
    };
    const head = vc.map((c) => esc(c.label)).join(",");
    const body = sorted.value.map((r) => vc.map((c) => esc(accessor(r, c.key))).join(",")).join("\n");
    const csv = "﻿" + head + "\n" + body; // BOM for Excel/Arabic
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = (filename || "export") + ".csv";
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
  }

  watch([search, datePreset, from, to, pageSize, sorted], () => { if (page.value > totalPages.value) page.value = 1; });

  return {
    search, datePreset, from, to, sortKey, sortDir, hidden, page, pageSize,
    cols, visibleCols, sorted, pageRows, totalPages, rangeStart, rangeEnd,
    hasDate: !!dateKey, facets: facetDefs, facetOptions, facetActive, setFacet,
    toggleSort, toggleCol, setPreset, reset, exportCSV,
  };
}
