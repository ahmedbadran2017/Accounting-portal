// Tiny, dependency-free Markdown → HTML renderer for the AI auditor chat.
// Handles the subset Claude actually emits (headings, bold, inline code, bullet/
// numbered lists, tables, horizontal rules, paragraphs). Input is HTML-escaped
// FIRST, then formatted — so it's safe to drop into v-html. Class names are kept
// as literals here so Tailwind's JIT scanner includes them in the bundle.
function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// Inline formatting applied to already-escaped text.
function inline(s) {
  return esc(s)
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code class="px-1 py-0.5 rounded bg-app-warm text-[12px] font-mono">$1</code>');
}

const isSep = (t) => /^[\s|:\-]+$/.test(t) && t.includes("-") && t.includes("|");

export function renderMarkdown(src) {
  const lines = String(src || "").split(/\r?\n/);
  const out = [];
  let listType = null, listBuf = [];
  const flushList = () => {
    if (!listBuf.length) return;
    const cls = listType === "ul" ? "list-disc" : "list-decimal";
    out.push(`<${listType} class="my-1.5 ps-5 space-y-0.5 ${cls}">${listBuf.join("")}</${listType}>`);
    listBuf = []; listType = null;
  };

  let i = 0;
  while (i < lines.length) {
    const t = lines[i].trim();

    // Table: a "| a | b |" row followed by a "|---|---|" separator.
    if (/^\|.*\|/.test(t) && i + 1 < lines.length && isSep(lines[i + 1].trim())) {
      flushList();
      const cells = (row) => row.replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
      const header = cells(t);
      i += 2;
      const rows = [];
      while (i < lines.length && /^\|.*\|/.test(lines[i].trim())) { rows.push(cells(lines[i].trim())); i++; }
      let tb = '<div class="overflow-x-auto my-2"><table class="w-full text-[12px] border border-line rounded-lg overflow-hidden"><thead><tr class="bg-app-warm">';
      tb += header.map((h) => `<th class="px-2.5 py-1.5 text-start font-bold border-b border-line">${inline(h)}</th>`).join("");
      tb += "</tr></thead><tbody>";
      tb += rows.map((r) => '<tr class="border-b border-line-hair">' + r.map((c) => `<td class="px-2.5 py-1.5 align-top">${inline(c)}</td>`).join("") + "</tr>").join("");
      tb += "</tbody></table></div>";
      out.push(tb);
      continue;
    }

    const h = /^(#{1,4})\s+(.*)$/.exec(t);
    if (h) { flushList(); const lvl = h[1].length; const sz = lvl <= 1 ? "15px" : lvl === 2 ? "13.5px" : "12.5px"; out.push(`<div class="font-bold mt-2.5 mb-1" style="font-size:${sz}">${inline(h[2])}</div>`); i++; continue; }

    if (/^(---+|\*\*\*+|___+)$/.test(t)) { flushList(); out.push('<hr class="my-2.5 border-line-hair">'); i++; continue; }

    const b = /^[-*]\s+(.*)$/.exec(t);
    if (b) { if (listType !== "ul") { flushList(); listType = "ul"; } listBuf.push(`<li>${inline(b[1])}</li>`); i++; continue; }

    const n = /^\d+\.\s+(.*)$/.exec(t);
    if (n) { if (listType !== "ol") { flushList(); listType = "ol"; } listBuf.push(`<li>${inline(n[1])}</li>`); i++; continue; }

    if (t === "") { flushList(); i++; continue; }

    flushList();
    out.push(`<p class="my-1">${inline(t)}</p>`);
    i++;
  }
  flushList();
  return out.join("");
}
