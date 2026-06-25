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
    ["invoices", "sub.invoices"], ["payments", "sub.payments_in"],
  ],
  purchases: [
    ["vendors", "sub.vendors"],
    ["tobuy", "sub.tobuy"], ["received", "sub.received"], ["billed", "sub.billed"], ["topay", "sub.topay"], ["paid", "sub.paid"],
    ["bills", "sub.bills"], ["payments", "sub.payments_out"], ["cheques", "sub.cheques"],
  ],
  items: [["items", "sub.items"], ["pricelists", "sub.pricelists"], ["landed", "sub.landed"]],
  banking: [
    ["accounts", "sub.accounts"], ["transactions", "sub.transactions"], ["rules", "sub.rules"],
    ["remittance", "sub.remittance"], ["variance", "sub.variance"], ["aging", "sub.aging"], ["bankrec", "sub.bankrec"],
  ],
  accountant: [
    ["journals", "sub.journals"], ["coa", "sub.coa"], ["gl", "sub.gl"], ["trial", "sub.trial"],
    ["assets", "sub.assets"], ["fx", "sub.fx"], ["opening", "sub.opening"], ["close", "sub.close"],
  ],
  reports: [["salescol", "sub.salescol"], ["arap", "sub.arap"], ["statements", "sub.statements"], ["taxreports", "sub.taxreports"], ["dd", "sub.dd"], ["dataroom", "sub.dataroom"]],
  settings: [
    ["orgs", "sub.orgs"], ["users", "sub.users"], ["activity", "sub.activity"], ["taxconf", "sub.taxconf"], ["currencies", "sub.currencies"],
    ["locations", "sub.locations"], ["tags", "sub.tags"], ["custom", "sub.custom"], ["integrations", "sub.integrations"], ["anomrules", "sub.anomrules"],
  ],
};

// Sidebar groups → modules. icon = Icon.vue name; badge = count chip (or null).
export const NAV_GROUPS = [
  { label: "groups.overview", items: [{ id: "dashboard", icon: "grid" }] },
  { label: "groups.operations", items: [
    { id: "sales", icon: "receipt" }, { id: "purchases", icon: "cart" }, { id: "items", icon: "box" },
  ] },
  { label: "groups.money", items: [{ id: "banking", icon: "bank", badge: "3" }] },
  { label: "groups.books", items: [
    { id: "accountant", icon: "ledger", badge: "1" }, { id: "reports", icon: "chart" }, { id: "settings", icon: "gear" },
  ] },
];

// ★ Justyol-only shortcuts (jump straight to a module+sub). label = i18n key.
export const JONLY = [
  { label: "jonly.cod", icon: "truck", module: "banking", sub: "remittance" },
  { label: "jonly.carrier", icon: "clock", module: "banking", sub: "aging" },
  { label: "jonly.margin", icon: "box", module: "items", sub: "landed" },
  { label: "jonly.consolidation", icon: "layers", module: "dashboard", sub: null, entity: "group" },
  { label: "jonly.dd", icon: "chart", module: "reports", sub: "dd" },
  { label: "jonly.copilot", icon: "shield", module: "copilot", sub: null },
];

export function defaultSub(module) {
  const s = SUBTABS[module];
  return s ? s[0][0] : null;
}
