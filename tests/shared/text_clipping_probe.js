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
    // A fixed-position control is laid out against the viewport - the pager
    // reserves its own space in #main and is never cut by the panel it is
    // nested in - and an absolutely positioned one is cut only by its
    // containing block. Walking past either reported the page's own pager and
    // its ROWS readout as clipped text that the user can plainly see.
    let checkX = true, checkY = true, positioned = false;
    for (let node = leaf; node && (checkX || checkY); node = node.parentElement) {
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
      const clipsX = /hidden|clip/.test(cs.overflowX);
      const clipsY = /hidden|clip/.test(cs.overflowY);
      const here = cs.position !== 'static';
      // An absolutely positioned box is cut only by its containing block, so a
      // clipping ancestor above that point never reaches it.
      if ((clipsX || clipsY) && positioned && !here) break;
      if (!clipsX && !clipsY) {
        if (cs.position === 'fixed') break;  // laid out against the viewport
        if (here) positioned = true;
      }
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
    }
  }
  return JSON.stringify(bad.slice(0,100));
})()
