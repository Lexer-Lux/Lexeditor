/* Panel text audit: canvas ink versus clip boxes, both axes.
 *
 * Range rects only see line boxes, so they miss the two cut-off classes users
 * keep reporting: a column narrower than its ink (Armor stat-bonuses #), and a
 * line-height:1 box cropping descenders (Tiger Fang's g's). Canvas ink sees
 * both. Vertical clipping is never intended, so every text cell in scope is
 * checked vertically; horizontal callers nominate the cells that must fit
 * (identity columns), since long labels truncate with an ellipsis by design.
 */
(() => {
  const canvas = document.createElement("canvas").getContext("2d");

  const fontOf = element => {
    const style = getComputedStyle(element);
    return `${style.fontStyle} ${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
  };

  const inkOf = (text, font) => {
    canvas.font = font;
    const metrics = canvas.measureText(text);
    const width = metrics.actualBoundingBoxLeft + metrics.actualBoundingBoxRight;
    return {
      width: Number.isFinite(width) ? width : metrics.width,
      height: metrics.actualBoundingBoxAscent + metrics.actualBoundingBoxDescent,
    };
  };

  // The text run inside a list cell: the content wrapper's first text-bearing
  // child, skipping editable controls.
  const textRun = cell => {
    const content = cell.querySelector(":scope > .lex-column-cell-content")
      || cell.querySelector(".lex-column-cell-content");
    const box = content || cell;
    const child = content
      ? [...content.childNodes].find(node =>
        node.nodeType === Node.TEXT_NODE ? node.textContent.trim() !== ""
        : node instanceof Element && !node.matches("input,select,textarea,.lex-source-control"))
      : null;
    const holder = child instanceof Element ? child : box;
    const text = (holder === box ? box.innerText : holder.innerText || "").replace(/\n/g, "");
    if (!text.trim()) return null;
    return {text, box: holder, style: getComputedStyle(holder)};
  };

  const auditCell = (cell, {horizontal}) => {
    const run = textRun(cell);
    if (!run) return [];
    const ink = inkOf(run.text, fontOf(run.box));
    const findings = [];
    const height = run.box.clientHeight;
    if (Number.isFinite(ink.height) && ink.height - height > 1) {
      findings.push({
        axis: "vertical", text: run.text.slice(0, 40),
        ink: Math.round(ink.height * 10) / 10, box: height,
      });
    }
    if (horizontal) {
      const width = run.box.clientWidth
        - parseFloat(run.style.paddingLeft) - parseFloat(run.style.paddingRight);
      if (Number.isFinite(ink.width) && ink.width - width > 1) {
        findings.push({
          axis: "horizontal", text: run.text.slice(0, 40),
          ink: Math.round(ink.width * 10) / 10, box: Math.round(width * 10) / 10,
        });
      }
    }
    return findings;
  };

  window.__lexPanelTextAudit = (root, mustFit = []) => {
    const scope = root instanceof Element ? root : document;
    const findings = [];
    for (const cell of scope.querySelectorAll(".lex-column-list-cell")) {
      const wanted = mustFit.some(selector => cell.matches(selector));
      for (const finding of auditCell(cell, {horizontal: wanted})) {
        findings.push({...finding,
          cell: cell.getAttribute("data-column") || cell.cellIndex || ""});
      }
    }
    return findings;
  };
})();
