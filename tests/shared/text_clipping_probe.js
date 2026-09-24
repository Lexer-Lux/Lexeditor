// Measure text, not element borders. Ellipsis permits horizontal truncation
// only; it cannot excuse a line cut off at the top or bottom.
(() => {
  const bad = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let text; (text = walker.nextNode());) {
    if (!text.textContent.trim()) continue;
    const leaf = text.parentElement;
    if (!leaf || leaf.closest('svg,script,style,option,textarea')) continue;
    if (getComputedStyle(leaf).visibility !== 'visible') continue;
    const range = document.createRange();
    range.selectNodeContents(text);
    const boxes = [...range.getClientRects()].filter(r => r.width && r.height);
    if (!boxes.length) continue;
    let checkX = true, checkY = true;
    for (let node = leaf; node && (checkX || checkY); node = node.parentElement) {
      const cs = getComputedStyle(node);
      // Overflow does not create a clipping box on ordinary inline text.
      if (cs.display === 'inline' || cs.display === 'contents') continue;
      const box = node.getBoundingClientRect();
      // Native scrolling can reveal text beyond this viewport. Do not report
      // it as a hard clip, including at enclosing non-scrolling containers.
      if (/auto|scroll/.test(cs.overflowX)) checkX = false;
      if (/auto|scroll/.test(cs.overflowY)) checkY = false;
      if (cs.textOverflow === 'ellipsis' && !/flex|grid/.test(cs.display)
          && cs.whiteSpace !== 'normal') checkX = false;
      const scaleX = node.offsetWidth ? box.width / node.offsetWidth : 1;
      const scaleY = node.offsetHeight ? box.height / node.offsetHeight : 1;
      const left = box.left + node.clientLeft * scaleX;
      const top = box.top + node.clientTop * scaleY;
      const right = left + node.clientWidth * scaleX;
      const bottom = top + node.clientHeight * scaleY;
      let overW = 0, overH = 0;
      for (const r of boxes) {
        if (checkX && /hidden|clip/.test(cs.overflowX))
          overW = Math.max(overW, left - r.left, r.right - right);
        if (checkY && /hidden|clip/.test(cs.overflowY))
          overH = Math.max(overH, top - r.top, r.bottom - bottom);
      }
      if (overW > 1 || overH > 1) {
        bad.push({text:text.textContent.trim().slice(0,60),
          cls:String(leaf.className).slice(0,60), tag:leaf.tagName,
          clippedBy:String(node.className || node.tagName).slice(0,60), overW, overH});
        break;
      }
    }
  }
  return JSON.stringify(bad.slice(0,100));
})()
