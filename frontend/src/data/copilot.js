// AI Auditor (Copilot) — anomaly feed + assistant scaffold. Anomalies are the
// June-2026 set the auditor flagged in the JoyAgent Books handoff. The chat
// composer is wired to canned, context-aware replies for now; a later slice
// connects it to the Claude API with the live ledger facts as a system prompt.
// The auditor NEVER posts directly — write-actions render a proposed-journal
// card gated by maker-checker approval.

const pick = (l, en, ar, fr) => (l === "ar" ? ar : l === "fr" ? fr : en);

export const SEV_META = {
  critical: { dot: "#dc2626", bg: "#fef2f2", fg: "#dc2626", bd: "#fecaca", en: "Critical", ar: "حرِج", fr: "Critique" },
  high:     { dot: "#ea580c", bg: "#fff7ed", fg: "#ea580c", bd: "#fed7aa", en: "High", ar: "مرتفع", fr: "Élevé" },
  medium:   { dot: "#d97706", bg: "#fffbeb", fg: "#b45309", bd: "#fde68a", en: "Medium", ar: "متوسط", fr: "Moyen" },
  low:      { dot: "#2563eb", bg: "#eff6ff", fg: "#2563eb", bd: "#bfdbfe", en: "Low", ar: "منخفض", fr: "Faible" },
};
export const sevLabel = (s, l) => { const x = SEV_META[s] || SEV_META.low; return x[l] || x.en; };

export const ANOMALIES = [
  { id: "an1", sev: "critical", icon: "alert", ref: "STE-05935", amount: "676,000,000", go: { module: "accountant", sub: "journals" },
    title: (l) => pick(l, "Outsized journal entry", "قيد ضخم غير معتاد", "Écriture démesurée"),
    desc: (l) => pick(l, "Manual journal to Suspense is 4,200× this account’s monthly norm — posting blocked pending review.",
      "قيد يدوي إلى حساب التعليق أكبر بـ٤٢٠٠ مرة من المعتاد — تم إيقاف الترحيل بانتظار المراجعة.",
      "Écriture manuelle vers Compte d’attente, 4 200× la norme — passation bloquée."),
    cta: (l) => pick(l, "Review journal", "مراجعة القيد", "Revoir l’écriture") },
  { id: "an2", sev: "high", icon: "truck", ref: "RB-0418", amount: "-12,400", go: { module: "banking", sub: "remittance" },
    title: (l) => pick(l, "Remittance shortfall", "نقص في التحصيل", "Manque d’encaissement"),
    desc: (l) => pick(l, "Sendit batch short 12,400 MAD across 31 orders — 2 orders never collected, 1 partial.",
      "دفعة Sendit ناقصة ١٢٬٤٠٠ درهم عبر ٣١ طلباً — طلبان لم يُحصَّلا وواحد جزئي.",
      "Lot Sendit en manque de 12 400 MAD sur 31 commandes — 2 non collectées, 1 partielle."),
    cta: (l) => pick(l, "Open batch", "فتح الدفعة", "Ouvrir le lot") },
  { id: "an3", sev: "high", icon: "box", ref: "JY-PNT-0145", amount: "", go: { module: "items", sub: "landed" },
    title: (l) => pick(l, "COGS gap on SKU", "فجوة تكلفة على الصنف", "Écart COGS sur SKU"),
    desc: (l) => pick(l, "Invoiced with no landed-cost-inclusive valuation — true margin understated.",
      "فوترة دون تقييم شامل للتكلفة المحمَّلة — الهامش الحقيقي غير دقيق.",
      "Facturée sans valorisation incluant le coût de revient — marge réelle faussée."),
    cta: (l) => pick(l, "Fix valuation", "تصحيح التقييم", "Corriger") },
  { id: "an4", sev: "medium", icon: "trend", ref: "DIM-CASA", amount: "34%", go: { module: "reports", sub: "dd" },
    title: (l) => pick(l, "RTO spike — Casablanca", "ارتفاع الإرجاع — الدار البيضاء", "Pic de retours — Casablanca"),
    desc: (l) => pick(l, "Casablanca RTO at 34% vs 24% network avg — concentrated on 3 media buyers.",
      "نسبة الإرجاع في الدار البيضاء ٣٤٪ مقابل ٢٤٪ — مركَّزة على ٣ مشترين إعلاميين.",
      "Taux de retour Casablanca à 34% vs 24% — concentré sur 3 acheteurs média."),
    cta: (l) => pick(l, "See breakdown", "عرض التفصيل", "Voir le détail") },
  { id: "an5", sev: "low", icon: "flag", ref: "2999", amount: "4,180", go: { module: "accountant", sub: "journals" },
    title: (l) => pick(l, "Suspense balance non-zero", "رصيد التعليق غير صفري", "Solde d’attente non nul"),
    desc: (l) => pick(l, "Suspense account holds 4,180 MAD at period-end — should clear before close.",
      "حساب التعليق يحتوي ٤٬١٨٠ درهم في نهاية الفترة — يجب تصفيته قبل الإقفال.",
      "Le compte d’attente conserve 4 180 MAD en fin de période — à solder avant clôture."),
    cta: (l) => pick(l, "Clear it", "تصفية", "Solder") },
];

// Seed conversation shown when the desk opens.
export function seedMessages(l) {
  return [{
    role: "ai",
    text: pick(l,
      "I’ve reviewed Justyol Morocco’s June books. 5 anomalies are open — 1 critical. Ask me anything, or say “draft the suspense fix” and I’ll prepare a journal for your approval. I never post directly.",
      "راجعتُ دفاتر Justyol Morocco ليونيو. هناك ٥ ملاحظات مفتوحة — واحدة حرِجة. اسألني أي شيء، أو قل «جهّز تصفية التعليق» وسأُعدّ قيداً لاعتمادك. أنا لا أُرحّل مباشرةً.",
      "J’ai revu les comptes de juin de Justyol Morocco. 5 anomalies ouvertes — 1 critique. Demandez-moi, ou dites « prépare la correction d’attente » et je rédige une écriture pour votre validation. Je ne passe jamais directement."),
  }];
}

// Context-aware canned reply (stand-in until the Claude API is wired).
export function replyTo(text, l) {
  const q = (text || "").toLowerCase();
  if (/suspense|attente|تعليق|fix|2999|clear|solder|تصفية/.test(q)) {
    return {
      role: "ai",
      text: pick(l,
        "I’ve drafted a journal to clear the Suspense balance (4,180 MAD) to sundry expense. I won’t post it — it needs your sign-off (maker-checker):",
        "جهّزتُ قيداً لتصفية رصيد التعليق (٤٬١٨٠ درهم) إلى مصاريف متنوعة. لن أُرحّله — يحتاج اعتمادك (صانع–مراجع):",
        "J’ai rédigé une écriture pour solder le compte d’attente (4 180 MAD) vers charges diverses. Je ne la passe pas — validation requise :"),
      proposal: {
        title: pick(l, "Proposed journal · clear Suspense 2999", "قيد مقترح · تصفية التعليق ٢٩٩٩", "Écriture proposée · solder l’attente 2999"),
        note: pick(l, "Above auto-post threshold — checker required", "فوق حد الترحيل التلقائي — مطلوب مُراجِع", "Au-dessus du seuil — validateur requis"),
        lines: [
          { acc: "6358 Sundry expense", dr: "4,180", cr: "" },
          { acc: "2999 Suspense", dr: "", cr: "4,180" },
        ],
      },
    };
  }
  if (/bounce|maker|ste-05935|صانع|renvoy/.test(q)) {
    return { role: "ai", text: pick(l,
      "I’ll bounce STE-05935 back to its maker with a note that the amount is 4,200× the norm. It stays blocked until they correct it.",
      "سأُرجع STE-05935 إلى منشئه مع ملاحظة بأن المبلغ أكبر ٤٢٠٠ مرة من المعتاد. يبقى محظوراً حتى يُصحَّح.",
      "Je renvoie STE-05935 à son créateur avec une note : 4 200× la norme. Reste bloquée jusqu’à correction.") };
  }
  return { role: "ai", text: pick(l,
    "Noted. I can pull the detail behind any anomaly, draft a correcting journal for approval, or explain a balance. Try “draft the suspense fix”.",
    "تمام. أقدر أعرض تفاصيل أي ملاحظة، أو أُجهّز قيد تصحيح للاعتماد، أو أشرح أي رصيد. جرّب «جهّز تصفية التعليق».",
    "Noté. Je peux détailler une anomalie, rédiger une écriture corrective pour validation, ou expliquer un solde. Essayez « prépare la correction d’attente ».") };
}
