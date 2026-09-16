// Module tree, entities, and sub-tabs for the JoyAgent Books portal.
// Labels are i18n keys resolved at render time; raw English/Arabic/French
// strings live in the locale files.

// 4 Justyol entities (top-left switcher).
export const ENTITIES = [
  { id: "sarl", name: "Justyol Morocco", place: "Maroc", ccy: "MAD", code: "MA", badge: "linear-gradient(135deg,#e17f62,#a33a22)" },
  { id: "maslak", name: "Maslak LTD", place: "İstanbul, TR", ccy: "TRY", code: "TR", badge: "linear-gradient(135deg,#38bdf8,#0369a1)" },
  { id: "hk", name: "Justyol China", place: "Shenzhen, CN", ccy: "USD", code: "CN", badge: "linear-gradient(135deg,#34d399,#047857)" },
  { id: "group", name: "Justyol Holding", place: "Consolidated", ccy: "USD", code: "GRP", badge: "linear-gradient(135deg,#a78bfa,#7c3aed)" },
];

// Sub-tabs per module. Each entry: [slug, i18nKey].
export const SUBTABS = {
  sales: [
    ["customers", "sub.customers"], ["orders", "sub.orders"],
    ["todeliver", "sub.todeliver"], ["delivered", "sub.delivered"], ["collected", "sub.collected"], ["toreturn", "sub.toreturn"], ["returned", "sub.returned"],
    ["challans", "sub.challans"], ["tobill", "sub.tobill"], ["invoices", "sub.invoices"], ["credits", "sub.credits"], ["payments", "sub.payments_in"],
  ],
  purchases: [
    ["vendors", "sub.vendors"],
    ["tobuy", "sub.tobuy"], ["received", "sub.received"], ["shipments", "sub.shipments"], ["billed", "sub.billed"], ["topay", "sub.topay"], ["paid", "sub.paid"],
    ["bills", "sub.bills"], ["payments", "sub.payments_out"], ["cheques", "sub.cheques"], ["intermediaries", "sub.intermediaries"],
  ],
  // legacy screens (costing / valuation / landed / cockpit) are hidden, not
  // deleted — their pages still resolve by direct URL if ever needed
  items: [["items", "sub.items"], ["vendors", "sub.vendors"], ["costtrace", "sub.costtrace"], ["weights", "sub.weights"], ["zerocost", "sub.zerocost"], ["cutover", "sub.cutover"], ["agreed", "sub.agreed"], ["pricelists", "sub.pricelists"],
    // These four render real screens in Items.vue and were never listed here,
    // so the landed-cost workbench, the item cost card, the valuation doctor
    // and the landed cockpit could only be reached by typing a URL.
    ["landed", "sub.landed"], ["costing", "sub.costing"],
    ["valuation", "sub.valuation"], ["cockpit", "sub.cockpit"]],
  banking: [
    ["accounts", "sub.accounts"],
    ["remittance", "sub.remittance"], ["variance", "sub.variance"], ["codclose", "sub.codclose"], ["settlements", "sub.settlements"], ["aging", "sub.aging"], ["bankrec", "sub.bankrec"], ["cleanup", "sub.cleanup"],
  ],
  accountant: [
    ["journals", "sub.journals"], ["triage", "sub.triage"], ["coa", "sub.coa"], ["gl", "sub.gl"], ["trial", "sub.trial"],
    ["assets", "sub.assets"], ["fx", "sub.fx"], ["opening", "sub.opening"], ["close", "sub.close"], ["team", "sub.team"],
  ],
  // Expenses & Payroll are now top-level modules. Each is a self-tabbed page
  // (its own inner tabs), so it carries no sidebar sub-tabs.
  expenses: [],
  payroll: [],
  reports: [["grouppnl", "sub.grouppnl"], ["matching", "sub.matching"], ["salescol", "sub.salescol"], ["arap", "sub.arap"], ["forecast", "sub.forecast"], ["missingdocs", "sub.missingdocs"], ["statements", "sub.statements"], ["investors", "sub.investors"], ["taxreports", "sub.taxreports"], ["dd", "sub.dd"],],
  settings: [
    ["orgs", "sub.orgs"], ["users", "sub.users"], ["activity", "sub.activity"], ["taxconf", "sub.taxconf"], ["currencies", "sub.currencies"],
  ],
};

// Sidebar groups → modules. icon = Icon.vue name; badge = count chip (or null).
export const NAV_GROUPS = [
  { label: "groups.overview", items: [{ id: "dashboard", icon: "grid" }, { id: "copilot", icon: "shield" }, { id: "mywork", icon: "check" }] },
  { label: "groups.operations", items: [
    { id: "sales", icon: "receipt" }, { id: "purchases", icon: "cart" }, { id: "items", icon: "box" },
  ] },
  { label: "groups.money", items: [{ id: "banking", icon: "bank" }] },
  { label: "groups.people", items: [
    { id: "expenses", icon: "wallet" }, { id: "payroll", icon: "users" },
  ] },
  { label: "groups.books", items: [
    { id: "accountant", icon: "ledger" }, { id: "reports", icon: "chart" }, { id: "settings", icon: "gear" },
  ] },
];

// ★ Justyol-only shortcuts (jump straight to a module+sub). label = i18n key.

export function defaultSub(module) {
  const s = SUBTABS[module];
  // Guard the empty-array case (self-tabbed modules like expenses/payroll have
  // no sidebar sub-tabs): `[]` is truthy but `[][0][0]` throws.
  return s && s.length ? s[0][0] : null;
}

// Stages of one pipeline, not separate screens. `CodBucket` and `PurchaseBucket`
// already render the whole pipeline as a strip of clickable cards with counts at
// the top of the page, so repeating those stages in the tab row above it gave
// the accountant ten tab targets for two screens — and the tab row carried less
// information than the strip it duplicated.
//
// They stay in SUBTABS so every existing URL and bookmark keeps resolving; they
// are simply not drawn as tabs. One entry each leads into the pipeline.
export const PIPELINE_SUBS = new Set([
  "delivered", "collected", "toreturn", "returned",   // sales — `todeliver` stays as the way in
  "tobuy", "received", "billed", "paid",              // purchases — `topay` stays as the way in
]);

export const tabsFor = (mod) => (SUBTABS[mod] || []).filter((s) => !PIPELINE_SUBS.has(s[0]));
