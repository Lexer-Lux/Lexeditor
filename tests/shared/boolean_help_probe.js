(() => {
  const bad = [];
  for (const field of document.querySelectorAll('.lex-boolean-field')) {
    const label = field.querySelector('.lex-detail-field-label');
    const text = label?.querySelector('.lex-detail-field-label-text');
    const help = label?.querySelector('.lex-info-help');
    if (!text || !help) continue;
    const h = help.getBoundingClientRect();
    if (!h.width || !h.height) continue;
    const range = document.createRange();
    range.selectNodeContents(text);
    const lines = [...range.getClientRects()].filter(r => r.width && r.height);
    const last = lines.at(-1);
    if (!last) continue;
    const gap = h.left - last.right;
    const center = h.top + h.height / 2;
    if (gap < -1 || gap > 14 || center < last.top - 2 || center > last.bottom + 2) {
      bad.push({kind: 'boolean-help-away-from-name', label: text.textContent.trim(),
        gap: Math.round(gap), vertical: Math.round(center - (last.top + last.height / 2))});
    }
  }
  return JSON.stringify(bad.slice(0, 10));
})()
