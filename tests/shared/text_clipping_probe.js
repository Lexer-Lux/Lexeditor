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
    // Absolute descendants escape overflow between themselves and their
    // containing block, but that block can still be clipped by its ancestors.
    // Relative positioning never exempts text from ancestor clipping.
    let checkX = true, checkY = true, containingBlock = null;
    for (let node = leaf; node && (checkX || checkY); node = node.parentElement) {
      if (containingBlock && node !== containingBlock) continue;
      containingBlock = null;
      const cs = getComputedStyle(node);
      // Overflow does not create a clipping box on ordinary inline text.
      if (cs.display === 'inline' || cs.display === 'contents') continue;
      const box = node.getBoundingClientRect();
      // A screen-reader-only box is one pixel square and clipped away on
      // purpose: nothing there is meant to be read on screen.
      if (node.clientWidth <= 2 || node.clientHeight <= 2) break;
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
      // A line box may overhang its box by up to about two pixels without any
      // ink being lost: the shared text nudge and the .14em descender padding
      // both work that way. A horizontal shave is visible at two pixels, so the
      // axes keep different tolerances. The ink probe is what proves whether a
      // glyph was really cut.
      if (overW > 1 || overH > 2.5) {
        bad.push({text:text.textContent.trim().slice(0,60),
          cls:String(leaf.className).slice(0,60), tag:leaf.tagName,
          clippedBy:String(node.className || node.tagName).slice(0,60), overW, overH});
        break;
      }
      if (cs.position === 'fixed' && !node.offsetParent) break;
      if (cs.position === 'absolute' || cs.position === 'fixed') containingBlock = node.offsetParent;
    }
  }
  return JSON.stringify(bad.slice(0,100));
})()
