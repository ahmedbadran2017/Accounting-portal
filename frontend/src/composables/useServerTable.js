import { ref, computed, watch } from "vue";

// Server-side paginated table. The `fetcher(params)` returns { rows, total, ... }
// for the current page / search / sort / filters; Next·Prev·search·sort·filter
// each refetch from the server (one page at a time) instead of pulling everything
// and paginating in the browser — so a list of 100k+ rows stays fast.
export function useServerTable(fetcher, opts = {}) {
  // Opening a document unmounts the list; without this the accountant came back
  // to page 1 with the search cleared after every single document.
  const memKey = opts.storeKey ? `ap_tbl:${opts.storeKey}` : null;
  let mem = {};
  if (memKey) { try { mem = JSON.parse(sessionStorage.getItem(memKey) || "{}"); } catch { mem = {}; } }
  const pageSize = ref(mem.pageSize || opts.pageSize || 25);
  const page = ref(mem.page || 1);
  const rows = ref([]);
  const total = ref(0);
  const extra = ref({}); // full payload (e.g. state_counts)
  const loading = ref(true);
  const error = ref(""); // set when a fetch throws — callers must NOT render empty-success on error
  const search = ref(mem.search || "");
  const sortField = ref(mem.sortField || opts.sortField || "date");
  const sortDir = ref(mem.sortDir || opts.sortDir || "desc");
  const filters = ref({ ...(opts.filters || {}), ...(mem.filters || {}) });

  const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)));
  const rangeStart = computed(() => (total.value ? (page.value - 1) * pageSize.value + 1 : 0));
  const rangeEnd = computed(() => Math.min(page.value * pageSize.value, total.value));

  let seq = 0;
  async function load() {
    loading.value = true;
    error.value = "";
    const my = ++seq;
    try {
      const res = await fetcher({
        start: (page.value - 1) * pageSize.value,
        page_size: pageSize.value,
        search: search.value || undefined,
        sort_field: sortField.value,
        sort_dir: sortDir.value,
        ...filters.value,
      });
      if (my !== seq) return; // a newer request already superseded this one
      rows.value = res.rows || [];
      total.value = res.total || 0;
      extra.value = res || {};
    } catch (e) {
      // surface the failure — an empty table on error must never read as "all clear"
      if (my === seq) { rows.value = []; total.value = 0; error.value = String(e?.message || e).slice(0, 200) || "load failed"; }
    } finally {
      if (my === seq) loading.value = false;
    }
  }

  function go(p) { page.value = Math.min(Math.max(1, p), totalPages.value); load(); }
  function next() { if (page.value < totalPages.value) go(page.value + 1); }
  function prev() { if (page.value > 1) go(page.value - 1); }
  function setFilters(f) { filters.value = { ...filters.value, ...f }; page.value = 1; load(); }
  function setSort(field) {
    if (sortField.value === field) sortDir.value = sortDir.value === "asc" ? "desc" : "asc";
    else { sortField.value = field; sortDir.value = "desc"; }
    page.value = 1;
    load();
  }

  // Remember where the user was, per list, for this browser session.
  if (memKey) {
    watch([page, pageSize, search, sortField, sortDir, filters], () => {
      try {
        sessionStorage.setItem(memKey, JSON.stringify({
          page: page.value, pageSize: pageSize.value, search: search.value,
          sortField: sortField.value, sortDir: sortDir.value, filters: filters.value,
        }));
      } catch { /* private mode */ }
    }, { deep: true });
  }

  let t = null;
  watch(search, () => { clearTimeout(t); t = setTimeout(() => { page.value = 1; load(); }, 300); });

  // ── Row selection (BulkBar contract: selected · selectedRows · clearSelection · exportSelectedCSV) ──
  // Keys survive paging so a batch can be picked across pages; selectedRows only
  // resolves the rows on the current page (callers send `selected` keys to the server).
  const keyOf = (r) => (opts.key ? r[opts.key] : (r.name ?? r.id));
  const selected = ref(new Set());
  const selectedRows = computed(() => rows.value.filter((r) => selected.value.has(keyOf(r))));
  const allSelected = computed(() => rows.value.length > 0 && rows.value.every((r) => selected.value.has(keyOf(r))));
  function toggle(k) { const s = new Set(selected.value); if (s.has(k)) s.delete(k); else s.add(k); selected.value = s; }
  function toggleAll() {
    const s = new Set(selected.value);
    if (allSelected.value) rows.value.forEach((r) => s.delete(keyOf(r))); else rows.value.forEach((r) => s.add(keyOf(r)));
    selected.value = s;
  }
  function clearSelection() { selected.value = new Set(); }
  function exportSelectedCSV(filename = "selection") {
    const rs = selectedRows.value.length ? selectedRows.value : rows.value;
    if (!rs.length) return;
    const cols = Object.keys(rs[0]).filter((c) => typeof rs[0][c] !== "object");
    const esc = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
    const csv = [cols.join(","), ...rs.map((r) => cols.map((c) => esc(r[c])).join(","))].join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" }));
    a.download = `${filename}.csv`; a.click(); URL.revokeObjectURL(a.href);
  }

  return {
    page, pageSize, rows, total, extra, loading, error, search, sortField, sortDir, filters,
    totalPages, rangeStart, rangeEnd, load, go, next, prev, setFilters, setSort,
    selected, selectedRows, allSelected, toggle, toggleAll, clearSelection, exportSelectedCSV, keyOf,
  };
}
