// Config-driven list views for the remaining generic sub-tabs (the ones the
// design only scaffolds, with no bespoke layout). One ScaffoldTable component
// renders any of these. Representative June-2026 rows; live ERPNext later.
// cols: [label, align?]  ('e' = end-aligned). rows: array of cell arrays.

export const SCAFFOLDS = {
  sales: {
    challans: { icon: "truck", cols: [["Challan"], ["Customer"], ["City"], ["Carrier"], ["Status"]], rows: [
      ["DN-167144", "زكرياء الرحماني", "Casablanca", "Cathedis", "To Bill"],
      ["DN-167002", "Salsabil El Kati", "Rabat", "Cathedis", "Completed"],
      ["DN-166890", "Siham Elfilali", "Marrakech", "Sendit", "Return Issued"],
    ] },
    receipts: { icon: "coins", cols: [["Receipt"], ["Customer"], ["Order"], ["Method"], ["Collected", "e"]], rows: [
      ["REC-19042", "Siham Elfilali", "#242385", "COD · Cathedis", "298.00"],
      ["REC-19041", "Jihad Elouarti", "#242542", "COD · Cathedis", "546.00"],
      ["REC-19040", "مليكة بلالي", "#242458", "COD · Cathedis", "149.00"],
    ] },
    payments: { icon: "wallet", cols: [["Payment"], ["Customer"], ["Date"], ["Method"], ["Amount", "e"]], rows: [
      ["PAY-22493", "Lachhed najia", "20 Jun", "Cathedis clearing", "129.00"],
      ["PAY-22491", "زكرياء الرحماني", "21 Jun", "Cathedis clearing", "129.00"],
      ["PAY-22475", "Siham Elfilali", "20 Jun", "Cathedis clearing", "298.00"],
    ] },
    credits: { icon: "receipt", cols: [["Credit note"], ["Customer"], ["Reason"], ["Date"], ["Amount", "e"]], rows: [
      ["CN-00231", "Khadija", "Return — size", "19 Jun", "-149.00"],
      ["CN-00230", "Attman", "Delivery exception", "18 Jun", "-144.00"],
    ] },
  },
  purchases: {
    pos: { icon: "cart", cols: [["PO"], ["Vendor"], ["Date"], ["Amount", "e"], ["Status"]], rows: [
      ["PO-3009", "TOMMYLIFE", "09 Jun", "TRY 412,000", "Open"],
      ["PO-3008", "SLA Import", "07 Jun", "MAD 96,400", "Received"],
      ["PO-3007", "Justyol China", "03 Jun", "USD 21,525", "Open"],
    ] },
    expenses: { icon: "wallet", cols: [["Expense"], ["Category"], ["Date"], ["Amount", "e"], ["Status"]], rows: [
      ["EXP-0512", "Meta / Facebook Ads", "21 Jun", "MAD 44,800", "Paid"],
      ["EXP-0511", "Rent — warehouse", "01 Jun", "MAD 18,000", "Paid"],
      ["EXP-0510", "SaaS · ERPNext", "01 Jun", "MAD 2,400", "Paid"],
    ] },
    recurring: { icon: "refresh", cols: [["Template"], ["Vendor"], ["Frequency"], ["Next run"], ["Amount", "e"]], rows: [
      ["REC-RENT", "DIA Property Invest", "Monthly", "01 Jul", "MAD 18,000"],
      ["REC-ADS", "Meta / Facebook Ads", "Weekly", "28 Jun", "MAD ~45,000"],
    ] },
    payments: { icon: "wallet", cols: [["Payment"], ["Vendor"], ["Date"], ["Method"], ["Amount", "e"]], rows: [
      ["PE-9912", "Meta / Facebook Ads", "20 Jun", "BMCE Bank", "MAD 44,800"],
      ["PE-9910", "TOMMYLIFE", "12 Jun", "Kuveyt Türk", "TRY 200,000"],
    ] },
    vcredits: { icon: "receipt", cols: [["Vendor credit"], ["Vendor"], ["Reason"], ["Date"], ["Amount", "e"]], rows: [
      ["VC-0042", "Vienev", "Return — defective", "12 Jun", "-2,651"],
    ] },
  },
  items: {
    pricelists: { icon: "list", cols: [["Price list"], ["Currency"], ["Items"], ["Updated"]], rows: [
      ["Storefront — Retail", "MAD", "1,284", "21 Jun"],
      ["Supplier — Cost (TR)", "TRY", "612", "13 Jun"],
      ["Supplier — Cost (CN)", "USD", "208", "03 Jun"],
    ] },
  },
  reports: {
    taxreports: { icon: "percent", cols: [["Report"], ["Basis"], ["Value", "e"]], rows: [
      ["VAT declaration — June", "Output − Input VAT", "+167K"],
      ["VAT by rate (20% / 14%)", "Sales Invoice tax", "209K"],
      ["Sales by city", "Reporting tag · city", "2% tagged"],
    ] },
    dataroom: { icon: "doc", cols: [["Document"], ["Type"], ["Status"]], rows: [
      ["Consolidated financials", "PDF · P&L / BS / CF", "Tied"],
      ["Trial balance — June", "XLSX", "Tied"],
      ["Verified DD pack", "PDF", "Ready"],
    ] },
  },
  banking: {
    accounts: { icon: "bank", cols: [["Account"], ["Number"], ["Currency"], ["Balance", "e"]], rows: [
      ["Cathadis – COD clearing", "108.021.003", "MAD", "471,081"],
      ["BMCE Bank", "••• 1303", "MAD", "12,483"],
      ["Kuveyt Türk", "•••• 4471", "TRY", "1,284,000"],
    ] },
    transactions: { icon: "list", cols: [["Date"], ["Description"], ["Account"], ["Amount", "e"]], rows: [
      ["21 Jun", "COD remittance · Sendit", "108.021.003", "+63,700"],
      ["20 Jun", "Supplier payment · Meta", "320.01", "-44,800"],
      ["18 Jun", "COD remittance · Cathedis", "108.021.003", "+50,200"],
    ] },
    rules: { icon: "filter", cols: [["Rule"], ["Match"], ["Action"], ["Hits", "e"]], rows: [
      ["Cathedis remittance", "desc ~ 'Cathedis'", "→ 108.021.003", "4,629"],
      ["Meta Ads", "desc ~ 'Meta'", "→ 320.01 · Ad spend", "31"],
      ["Bank fee", "desc ~ 'fee'", "→ 627 · Bank charges", "12"],
    ] },
  },
  settings: {
    locations: { icon: "building", cols: [["Location"], ["Type"], ["Entity"]], rows: [
      ["Softgroup Warehouse", "Warehouse", "Justyol Morocco"],
      ["İstanbul Hub", "Supply", "Maslak LTD"],
    ] },
    tags: { icon: "list", cols: [["Reporting tag"], ["Dimension"], ["Coverage"]], rows: [
      ["City", "custom_shipping_city", "80.6% of orders"],
      ["Channel", "custom_channel", "sparse"],
      ["Media buyer", "custom_utm_source", "Ads only"],
    ] },
    custom: { icon: "gear", cols: [["Module"], ["Type"], ["Status"]], rows: [
      ["COD lifecycle", "Sales Order fields", "Active"],
      ["Landed cost", "Item valuation", "Active"],
    ] },
    integrations: { icon: "plug", cols: [["Integration"], ["Scope"], ["Status"]], rows: [
      ["Shopify", "Orders → Sales Order", "Synced"],
      ["Cathedis", "COD remittance feed", "Synced"],
      ["Meta Ads", "Ad spend → Expense", "Synced"],
    ] },
    anomrules: { icon: "shield", cols: [["Rule"], ["Trigger"], ["Severity"]], rows: [
      ["Outsized journal", "> 100× 90-day avg", "Critical"],
      ["Clearing concentration", "> 90% via one account", "High"],
      ["Negative debtor", "Receivable credit balance", "High"],
      ["Zero margin", "custom_margin = 0", "Medium"],
    ] },
  },
};

export const scaffoldFor = (module, sub) => SCAFFOLDS[module]?.[sub] || null;
