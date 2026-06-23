// Settings — users & roles, taxes, currencies. June-2026 snapshot from the
// JoyAgent Books handoff; live ERPNext later.

const pick = (l, en, ar, fr) => (l === "ar" ? ar : l === "fr" ? fr : en);

export function settingsUsers(l) {
  return [
    { name: "Soukaina Karimi", role: pick(l, "Finance Lead", "مسؤولة المالية", "Resp. finance"), access: pick(l, "Full · checker", "كامل · مراجِع", "Complet · valideur"), av: "accent" },
    { name: "Yassine Berrada", role: pick(l, "Accountant", "محاسب", "Comptable"), access: pick(l, "Journals · maker", "قيود · صانع", "Écritures · maker"), av: "sky" },
    { name: "Omar Idrissi", role: pick(l, "Ops / dimensions", "عمليات", "Ops"), access: pick(l, "Sales · read", "مبيعات · قراءة", "Ventes · lecture"), av: "emerald" },
    { name: "External auditor", role: pick(l, "Auditor", "مدقّق", "Auditeur"), access: pick(l, "Read-only · data room", "قراءة · غرفة بيانات", "Lecture · data room"), av: "violet" },
  ];
}

export function settingsTaxes(l) {
  return [
    { name: "TVA standard", rate: "20%", region: "Maroc" },
    { name: pick(l, "TVA reduced", "TVA مخفّضة", "TVA réduite"), rate: "14%", region: "Maroc" },
    { name: "KDV", rate: "18%", region: "Türkiye" },
    { name: pick(l, "Exempt / export", "معفى / تصدير", "Exonéré / export"), rate: "0%", region: "—" },
  ];
}

export function settingsCurrencies(l) {
  const role = (base) => base ? pick(l, "Base", "أساس", "Base") : pick(l, "Foreign", "أجنبي", "Étranger");
  return [
    { ccy: "MAD", role: role(true), rate: "1.000" },
    { ccy: "TRY", role: role(false), rate: "0.262" },
    { ccy: "USD", role: role(false), rate: "9.94" },
    { ccy: "CNY", role: role(false), rate: "1.371" },
  ];
}
