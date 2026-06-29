import { ref, computed, watch } from "vue";

// Server-side paginated table. The `fetcher(params)` returns { rows, total, ... }
// for the current page / search / sort / filters; Next·Prev·search·sort·filter
// each refetch from the server (one page at a time) instead of pulling everything
// and paginating in the browser — so a list of 100k+ rows stays fast.
export function useServerTable(fetcher, opts = {}) {
  const pageSize = ref(opts.pageSize || 25);
  const page = ref(1);
  const rows = ref([]);
  const total = ref(0);
  const extra = ref({}); // full payload (e.g. state_counts)
  const loading = ref(true);
  const search = ref("");
  const sortField = ref(opts.sortField || "date");
  const sortDir = ref(opts.sortDir || "desc");
  const filters = ref({ ...(opts.filters || {}) });

  const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)));
  const rangeStart = computed(() => (total.value ? (page.value - 1) * pageSize.value + 1 : 0));
  const rangeEnd = computed(() => Math.min(page.value * pageSize.value, total.value));

  let seq = 0;
  async function load() {
    loading.value = true;
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
    } catch {
      if (my === seq) { rows.value = []; total.value = 0; }
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

  let t = null;
  watch(search, () => { clearTimeout(t); t = setTimeout(() => { page.value = 1; load(); }, 300); });

  return {
    page, pageSize, rows, total, extra, loading, search, sortField, sortDir, filters,
    totalPages, rangeStart, rangeEnd, load, go, next, prev, setFilters, setSort,
  };
}
